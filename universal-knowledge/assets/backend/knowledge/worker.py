import logging
import time
import uuid
import numpy as np
from .config import settings
from .providers import provider
from .store import Store
from .ingestion import chunks

log = logging.getLogger('knowledge.worker')


def tick(store):
    token = uuid.uuid4()
    with store.connection() as db:
        # Expired final attempts must not remain stuck in running state.
        db.execute("UPDATE jobs SET status='failed',error_code='lease_expired',updated_at=now() WHERE status='running' AND lease_until<now() AND attempts>=%s", (store.config.job_attempts,))
        job = db.execute('''WITH candidate AS (
          SELECT id FROM jobs WHERE (status='queued' OR (status='running' AND lease_until<now()))
          AND attempts<%s ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
          UPDATE jobs SET status='running',attempts=attempts+1,lease_until=now()+interval '5 minutes',lease_token=%s,updated_at=now()
          FROM candidate WHERE jobs.id=candidate.id RETURNING jobs.*''', (store.config.job_attempts, token)).fetchone()
    if not job:
        return False
    try:
        with store.connection() as db:
            version = db.execute('SELECT text FROM versions WHERE tenant=%s AND document_id=%s AND version=%s', (job['tenant'], job['document_id'], job['version'])).fetchone()
        if not version:
            return True  # deletion cascaded job and source
        pieces = list(chunks(version['text'], store.config.chunk_chars, store.config.chunk_overlap))
        vectors = []
        for offset in range(0, len(pieces), 32):
            vectors.extend(store.embedder.embed([c['text'] for c in pieces[offset:offset + 32]]))
        if len(vectors) != len(pieces) or any(len(v) != store.config.embedding_dimensions or not np.isfinite(v).all() for v in vectors):
            raise ValueError('Invalid embedding output')
        with store.connection() as db:
            doc = db.execute('SELECT * FROM documents WHERE tenant=%s AND id=%s FOR UPDATE', (job['tenant'], job['document_id'])).fetchone()
            active = db.execute("SELECT id FROM jobs WHERE id=%s AND lease_token=%s AND status='running' FOR UPDATE", (job['id'], token)).fetchone()
            if not active:
                return True
            if not doc or doc['version'] != job['version'] or doc['embedding_id'] != store.embedder.identity:
                db.execute("UPDATE jobs SET status='superseded',updated_at=now() WHERE id=%s", (job['id'],))
                return True
            db.execute('DELETE FROM chunks WHERE tenant=%s AND document_id=%s', (job['tenant'], job['document_id']))
            with db.cursor() as cursor:
                cursor.executemany('INSERT INTO chunks(tenant,document_id,version,ordinal,text,start_char,end_char,embedding) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                    [(job['tenant'], job['document_id'], job['version'], c['ordinal'], c['text'], c['start'], c['end'], np.asarray(v)) for c, v in zip(pieces, vectors)])
            db.execute("UPDATE jobs SET status='complete',error_code=NULL,updated_at=now() WHERE id=%s", (job['id'],))
        log.info('job_complete', extra={'job_id': str(job['id'])})
    except Exception:
        log.exception('job_failed', extra={'job_id': str(job['id'])})
        with store.connection() as db:
            db.execute("UPDATE jobs SET status=CASE WHEN attempts<%s THEN 'queued' ELSE 'failed' END,error_code='ingestion_failed',updated_at=now() WHERE id=%s AND lease_token=%s", (store.config.job_attempts, job['id'], token))
    return True


def main():
    from .observability import configure_logging
    configure_logging()
    config = settings()
    store = Store(config, provider(config))
    last_purge = 0
    while True:
        try:
            if time.monotonic() - last_purge > 3600:
                store.purge()
                last_purge = time.monotonic()
            if not tick(store):
                time.sleep(1)
        except Exception:
            log.exception('worker_unavailable')
            time.sleep(5)


if __name__ == '__main__':
    main()
