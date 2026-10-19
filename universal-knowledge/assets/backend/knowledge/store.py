import uuid
from contextlib import contextmanager
import numpy as np
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pgvector.psycopg import register_vector
from .ingestion import fingerprint


class Store:
    def __init__(self, config, embedder):
        self.config, self.embedder = config, embedder

    @contextmanager
    def connection(self):
        with psycopg.connect(self.config.database_url, row_factory=dict_row) as db:
            register_vector(db)
            yield db

    def put(self, principal, document_id, text, source, metadata, readers):
        digest = fingerprint(text)
        with self.connection() as db:
            # Serialize creation and updates, including concurrent first inserts.
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (f'{principal.tenant}:{document_id}',))
            old = db.execute('SELECT * FROM documents WHERE tenant=%s AND id=%s FOR UPDATE', (principal.tenant, document_id)).fetchone()
            if old and old['owner_id'] != principal.subject:
                raise PermissionError('Document is not owned by caller')
            duplicates = db.execute('SELECT id FROM documents WHERE tenant=%s AND content_hash=%s AND owner_id=%s AND id<>%s', (principal.tenant, digest, principal.subject, document_id)).fetchall()
            if old and old['content_hash'] == digest and old['source'] == source and old['metadata'] == metadata and old['readers'] == readers and old['embedding_id'] == self.embedder.identity:
                return {'document_id': str(document_id), 'version': old['version'], 'unchanged': True, 'duplicates': [str(r['id']) for r in duplicates]}
            version = old['version'] + 1 if old else 1
            db.execute('''INSERT INTO documents(tenant,id,owner_id,readers,source,metadata,version,content_hash,embedding_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(tenant,id) DO UPDATE SET
                readers=excluded.readers,source=excluded.source,metadata=excluded.metadata,version=excluded.version,
                content_hash=excluded.content_hash,embedding_id=excluded.embedding_id,updated_at=now()''',
                (principal.tenant, document_id, principal.subject, readers, source, Jsonb(metadata), version, digest, self.embedder.identity))
            db.execute('DELETE FROM chunks WHERE tenant=%s AND document_id=%s', (principal.tenant, document_id))
            db.execute('INSERT INTO versions(tenant,document_id,version,text,content_hash,source,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s)', (principal.tenant, document_id, version, text, digest, source, Jsonb(metadata)))
            job = uuid.uuid4()
            db.execute('INSERT INTO jobs(id,tenant,document_id,version) VALUES(%s,%s,%s,%s)', (job, principal.tenant, document_id, version))
            return {'document_id': str(document_id), 'version': version, 'job_id': str(job), 'unchanged': False, 'duplicates': [str(r['id']) for r in duplicates]}

    def search(self, principal, query, filters=None, limit=8, rerank=False):
        vector = np.asarray(self.embedder.embed([query])[0])
        # MATERIALIZED ensures only authorized, current chunks enter candidate ranking.
        sql = '''WITH authorized AS MATERIALIZED (
          SELECT c.*, d.source, d.embedding_id FROM chunks c JOIN documents d ON d.tenant=c.tenant AND d.id=c.document_id
          WHERE d.tenant=%s AND (d.owner_id=%s OR d.readers && %s::text[])
          AND d.metadata @> %s::jsonb AND d.version=c.version AND d.embedding_id=%s
        ), semantic AS (
          SELECT document_id,ordinal,row_number() OVER(ORDER BY embedding <=> %s) AS rank
          FROM authorized ORDER BY embedding <=> %s LIMIT 100
        ), lexical AS (
          SELECT document_id,ordinal,row_number() OVER(ORDER BY ts_rank_cd(lexical,plainto_tsquery('english',%s)) DESC) AS rank
          FROM authorized WHERE lexical @@ plainto_tsquery('english',%s)
          ORDER BY ts_rank_cd(lexical,plainto_tsquery('english',%s)) DESC LIMIT 100
        ) SELECT a.document_id,a.version,a.ordinal,a.text,a.start_char,a.end_char,a.source,
          (COALESCE(1.0/(60+s.rank),0)+COALESCE(1.0/(60+l.rank),0))::float AS score
          FROM authorized a LEFT JOIN semantic s USING(document_id,ordinal) LEFT JOIN lexical l USING(document_id,ordinal)
          WHERE s.rank IS NOT NULL OR l.rank IS NOT NULL ORDER BY score DESC, a.document_id,a.ordinal LIMIT %s'''
        with self.connection() as db:
            hits = db.execute(sql, (principal.tenant, principal.subject, principal.readers, Jsonb(filters or {}), self.embedder.identity, vector, vector, query, query, query, limit)).fetchall()
        if rerank:
            from .providers import OverlapReranker
            hits = OverlapReranker().rank(query, hits)
        return hits

    def owned(self, db, principal, document_id):
        row = db.execute('SELECT * FROM documents WHERE tenant=%s AND id=%s AND owner_id=%s FOR UPDATE', (principal.tenant, document_id, principal.subject)).fetchone()
        if not row:
            raise LookupError('Document not found')
        return row

    def delete(self, principal, document_id):
        with self.connection() as db:
            self.owned(db, principal, document_id)
            db.execute('DELETE FROM documents WHERE tenant=%s AND id=%s', (principal.tenant, document_id))

    def history(self, principal, document_id):
        with self.connection() as db:
            self.owned(db, principal, document_id)
            return db.execute('SELECT version,content_hash,source,metadata,created_at FROM versions WHERE tenant=%s AND document_id=%s ORDER BY version DESC', (principal.tenant, document_id)).fetchall()

    def reindex(self, principal, document_id):
        with self.connection() as db:
            doc = self.owned(db, principal, document_id)
            db.execute('UPDATE documents SET embedding_id=%s WHERE tenant=%s AND id=%s', (self.embedder.identity, principal.tenant, document_id))
            db.execute('DELETE FROM chunks WHERE tenant=%s AND document_id=%s', (principal.tenant, document_id))
            job = uuid.uuid4()
            db.execute('INSERT INTO jobs(id,tenant,document_id,version) VALUES(%s,%s,%s,%s)', (job, principal.tenant, document_id, doc['version']))
            return {'job_id': str(job)}

    def job(self, principal, job_id):
        with self.connection() as db:
            return db.execute('''SELECT j.id,j.status,j.attempts,j.error_code,j.updated_at FROM jobs j JOIN documents d
              ON d.tenant=j.tenant AND d.id=j.document_id WHERE j.id=%s AND j.tenant=%s AND d.owner_id=%s''', (job_id, principal.tenant, principal.subject)).fetchone()

    def purge(self):
        if not self.config.retention_days:
            return 0
        with self.connection() as db:
            return db.execute("DELETE FROM documents WHERE updated_at < now() - make_interval(days => %s)", (self.config.retention_days,)).rowcount
