"""Service-free behavioral tests for worker failure boundaries, not SQL substitutes."""
from contextlib import contextmanager
from types import SimpleNamespace
import uuid
from knowledge.worker import tick


class Cursor:
    def __init__(self, row=None): self.row = row
    def fetchone(self): return self.row


class FailingStore:
    def __init__(self):
        self.config = SimpleNamespace(job_attempts=3, chunk_chars=200, chunk_overlap=20, embedding_dimensions=384)
        self.embedder = SimpleNamespace(embed=self.fail)
        self.commands = []
        self.job = {'id': uuid.uuid4(), 'tenant': 't', 'document_id': uuid.uuid4(), 'version': 1}

    def fail(self, texts):
        raise RuntimeError('provider outage with sensitive upstream message')

    def execute(self, sql, params=()):
        self.commands.append((sql, params))
        if 'RETURNING jobs.*' in sql: return Cursor(self.job)
        if 'SELECT text FROM versions' in sql: return Cursor({'text': 'Warranty evidence'})
        return Cursor()

    @contextmanager
    def connection(self): yield self


def test_provider_failure_retries_without_index_publication():
    store = FailingStore()
    assert tick(store)
    updates = [sql for sql, params in store.commands]
    assert any("error_code='ingestion_failed'" in sql for sql in updates)
    assert not any('INSERT INTO chunks' in sql for sql in updates)
    # Error stored in DB is a safe code, not exception/provider text.
    assert all('sensitive upstream' not in str(params) for sql, params in store.commands)
