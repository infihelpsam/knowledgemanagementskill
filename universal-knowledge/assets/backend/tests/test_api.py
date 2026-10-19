import base64
import hashlib
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from knowledge.api import app, get_store
from knowledge.config import settings


class FakeStore:
    def __init__(self): self.calls = []
    def search(self, principal, query, filters, limit, rerank):
        self.calls.append(principal)
        return []
    def put(self, principal, document_id, text, source, metadata, readers):
        self.calls.append((principal, text, readers))
        return {'document_id': str(document_id), 'version': 1}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('AUTH_TOKENS', json.dumps({hashlib.sha256(b'secret-token').hexdigest(): {'tenant': 'trusted', 'subject': 'alice', 'groups': ['staff']}}))
    settings.cache_clear()
    store = FakeStore()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        yield client, store
    app.dependency_overrides.clear()
    settings.cache_clear()


def test_authentication_and_spoofed_identity(client):
    http, store = client
    assert http.post('/v1/search', json={'query': 'test'}).status_code in {401, 403}
    assert http.post('/v1/search', headers={'Authorization': 'Bearer bad'}, json={'query': 'test'}).status_code == 401
    response = http.post('/v1/search', headers={'Authorization': 'Bearer secret-token', 'X-Tenant': 'victim'}, json={'query': 'test', 'tenant': 'victim', 'groups': ['admin']})
    assert response.status_code == 200
    assert store.calls[-1].tenant == 'trusted' and store.calls[-1].subject == 'alice'


def test_ingestion_and_validation(client):
    http, store = client
    headers = {'Authorization': 'Bearer secret-token'}
    response = http.put(f'/v1/documents/{uuid.uuid4()}', headers=headers, json={'filename': 'a.txt', 'content_base64': base64.b64encode(b'Evidence').decode(), 'readers': ['group:staff']})
    assert response.status_code == 202
    assert store.calls[-1][1] == 'Evidence'
    assert http.post('/v1/documents', headers=headers, json={'content_base64': '!'}).status_code == 400
    assert http.post('/v1/documents', headers=headers, json={'content_base64': 'eA==', 'url': 'https://example.com'}).status_code == 422
    assert http.post('/v1/search', headers=headers, json={'query': 'x', 'limit': 1000}).status_code == 422
    assert http.post('/v1/answer', headers=headers, json={'query': 'x'}) .json()['abstained']


def test_request_size(client):
    http, _ = client
    settings().max_file_bytes = 1024
    assert http.post('/v1/documents', content=b'x' * 70000).status_code == 413
