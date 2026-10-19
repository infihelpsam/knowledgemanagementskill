"""Real SQL/worker tests. Set TEST_DATABASE_URL to a disposable pgvector database."""
import os
import uuid
from pathlib import Path
import pytest
from knowledge.config import Settings
from knowledge.providers import HashEmbedder, grounded_answer
from knowledge.store import Store
from knowledge.security import Principal
from knowledge.worker import tick

pytestmark = pytest.mark.integration


@pytest.fixture
def store():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not configured')
    import psycopg
    config = Settings(database_url=url, auth_tokens='{}')
    with psycopg.connect(url) as db:
        db.execute((Path(__file__).parents[1] / 'knowledge/migrations/001_initial.sql').read_text().replace('__DIMENSIONS__', '384'))
        # Must be a disposable database: fixture clears application tables.
        db.execute('TRUNCATE documents CASCADE')
    yield Store(config, HashEmbedder(384))
    with psycopg.connect(url) as db:
        db.execute('TRUNCATE documents CASCADE')


def drain(store):
    for _ in range(30):
        if not tick(store): return
    raise AssertionError('Queue did not drain')


def test_hybrid_acl_tenant_and_filters(store):
    alice, bob, outsider = Principal('tenant-a', 'alice'), Principal('tenant-a', 'bob', ('support',)), Principal('tenant-b', 'alice', ('support',))
    shared, private = uuid.uuid4(), uuid.uuid4()
    store.put(alice, shared, 'Warranty lasts two years.', 'manual', {'type': 'support'}, ['group:support'])
    store.put(alice, private, 'Secret warranty lasts seven years.', 'private', {}, [])
    drain(store)
    hits = store.search(bob, 'warranty', {'type': 'support'})
    assert {h['document_id'] for h in hits} == {shared}
    assert not store.search(outsider, 'warranty')
    assert not store.search(bob, 'warranty', {'type': 'missing'})
    assert grounded_answer('warranty', hits)['citations'][0]['document_id'] == str(shared)
    with pytest.raises(PermissionError): store.put(bob, shared, 'takeover', 'x', {}, [])
    with pytest.raises(LookupError): store.delete(bob, shared)
    with pytest.raises(LookupError): store.history(outsider, shared)


def test_upsert_dedup_history_reindex_and_delete(store):
    owner = Principal('t', 'owner')
    doc = uuid.uuid4()
    first = store.put(owner, doc, 'Warranty two years', 'manual', {}, [])
    assert store.put(owner, doc, 'Warranty two years', 'manual', {}, [])['unchanged']
    assert store.put(owner, uuid.uuid4(), 'Warranty two years', 'copy', {}, [])['duplicates'] == [str(doc)]
    drain(store)
    assert store.search(owner, 'warranty')
    second = store.put(owner, doc, 'Warranty five years', 'manual', {}, [])
    assert second['version'] == 2
    assert not [h for h in store.search(owner, 'warranty') if h['document_id'] == doc]
    drain(store)
    assert len(store.history(owner, doc)) == 2
    store.reindex(owner, doc)
    drain(store)
    store.delete(owner, doc)
    assert store.job(owner, uuid.UUID(first['job_id'])) is None
    assert not [h for h in store.search(owner, 'warranty') if h['document_id'] == doc]
    with store.connection() as db:
        for table in ['chunks', 'versions', 'jobs']:
            assert db.execute(f'SELECT count(*) AS n FROM {table} WHERE tenant=%s AND document_id=%s', ('t', doc)).fetchone()['n'] == 0


def test_stale_jobs_and_retention(store):
    owner, doc = Principal('t', 'u'), uuid.uuid4()
    store.put(owner, doc, 'old evidence', 'manual', {}, [])
    store.put(owner, doc, 'current evidence', 'manual', {}, [])
    with store.connection() as db:
        db.execute("UPDATE jobs SET status='running',attempts=1,lease_until=now()-interval '10 minutes' WHERE version=1")
    drain(store)
    with store.connection() as db:
        stale = db.execute('SELECT status,attempts FROM jobs WHERE version=1').fetchone()
        assert stale['status'] == 'superseded' and stale['attempts'] == 2
    assert all('old' not in h['text'] for h in store.search(owner, 'evidence'))
    with store.connection() as db:
        db.execute("UPDATE documents SET updated_at=now()-interval '10 days'")
    store.config.retention_days = 3
    assert store.purge() == 1
    assert not store.search(owner, 'evidence')


def test_acl_revocation_and_deleted_pending_job(store):
    owner, reader = Principal('t', 'owner'), Principal('t', 'reader')
    doc = uuid.uuid4()
    store.put(owner, doc, 'Warranty evidence', 'manual', {}, ['user:reader'])
    drain(store)
    assert store.search(reader, 'warranty')
    store.put(owner, doc, 'Warranty evidence', 'manual', {}, [])
    assert not store.search(reader, 'warranty')
    # Delete while a fresh revision is pending: no queued source can resurrect it.
    store.delete(owner, doc)
    drain(store)
    assert not store.search(owner, 'warranty')

    exhausted = uuid.uuid4()
    result = store.put(owner, exhausted, 'Retry budget example', 'manual', {}, [])
    with store.connection() as db:
        db.execute("UPDATE jobs SET status='running',attempts=%s,lease_until=now()-interval '10 minutes' WHERE id=%s", (store.config.job_attempts, uuid.UUID(result['job_id'])))
    drain(store)
    assert store.job(owner, uuid.UUID(result['job_id']))['status'] == 'failed'
