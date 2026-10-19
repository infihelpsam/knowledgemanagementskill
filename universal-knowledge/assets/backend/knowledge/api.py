import base64
import binascii
import json
import logging
import uuid
from functools import lru_cache
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from .config import settings
from .security import authenticate, Principal, fetch_url
from .ingestion import extract
from .providers import provider, grounded_answer
from .store import Store
from .observability import configure_logging

configure_logging()
log = logging.getLogger('knowledge.api')
app = FastAPI(title='Universal Knowledge', version='0.1.0')
Identity = Annotated[Principal, Depends(authenticate)]


@lru_cache
def get_store():
    config = settings()
    return Store(config, provider(config))


class BoundedRequest:
    """ASGI boundary: bound actual bytes before JSON parsing, including chunked input."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = str(uuid.uuid4())
        maximum = settings().max_file_bytes * 2 + 65536
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            part = message.get('body', b'')
            if len(body) + len(part) > maximum:
                return await JSONResponse({'detail': 'Request too large'}, status_code=413)(scope, receive, send)
            body.extend(part)
            if not message.get('more_body', False):
                break
        delivered = False
        started = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        async def tagged(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
                message['headers'] = [*message.get('headers', []), (b'x-request-id', request_id.encode())]
            await send(message)
        try:
            await self.app(scope, replay, tagged)
        except Exception:
            log.exception('request_failed', extra={'request_id': request_id})
            if started:
                raise
            await JSONResponse({'detail': 'Internal service error', 'request_id': request_id}, status_code=500)(scope, receive, tagged)
        log.info('request_complete', extra={'request_id': request_id})


app.add_middleware(BoundedRequest)


@app.exception_handler(ValueError)
async def bad_input(request, error):
    return JSONResponse({'detail': 'Invalid input or extraction failed'}, status_code=400)


@app.exception_handler(PermissionError)
async def forbidden(request, error):
    return JSONResponse({'detail': 'Document not found'}, status_code=404)


@app.exception_handler(LookupError)
async def not_found(request, error):
    return JSONResponse({'detail': 'Resource not found'}, status_code=404)


class ImportRequest(BaseModel):
    filename: str = Field(default='document.txt', max_length=255)
    content_base64: str | None = None
    url: str | None = Field(default=None, max_length=4096)
    source: str = Field(default='', max_length=4096)
    metadata: dict = Field(default_factory=dict)
    readers: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def valid(self):
        if (self.content_base64 is None) == (self.url is None):
            raise ValueError('Provide exactly one of content_base64 or url')
        if len(json.dumps(self.metadata)) > 16384:
            raise ValueError('Metadata too large')
        if any(not r.startswith(('user:', 'group:')) or len(r) > 256 for r in self.readers):
            raise ValueError('Readers must be user:subject or group:name')
        return self


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    filters: dict = Field(default_factory=dict)
    limit: int = Field(default=8, ge=1, le=30)
    rerank: bool = False

    @model_validator(mode='after')
    def bounded_filters(self):
        if len(json.dumps(self.filters)) > 16384:
            raise ValueError('Filters too large')
        return self


@app.get('/health/live')
def live():
    return {'status': 'ok'}


@app.get('/health/ready')
def ready(identity: Identity, store=Depends(get_store)):
    import redis
    try:
        with store.connection() as db:
            db.execute('SELECT 1 FROM schema_version WHERE version=1').fetchone()
        redis.Redis.from_url(settings().redis_url, socket_timeout=2, socket_connect_timeout=2).ping()
    except Exception:
        raise HTTPException(503, 'Dependencies unavailable')
    return {'status': 'ready', 'embedding_id': store.embedder.identity}


def ingest(document_id, body, identity, store):
    config = settings()
    if body.url:
        data, extension = fetch_url(body.url, config.max_file_bytes)
        filename = 'website' + extension
    else:
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Invalid base64')
        filename = body.filename
    text = extract(data, filename, config.max_file_bytes, config.max_text_chars)
    return store.put(identity, document_id, text, body.url or body.source or body.filename, body.metadata, sorted(set(body.readers)))


@app.post('/v1/documents', status_code=202)
def create(body: ImportRequest, identity: Identity, store=Depends(get_store)):
    return ingest(uuid.uuid4(), body, identity, store)


@app.put('/v1/documents/{document_id}', status_code=202)
def upsert(document_id: uuid.UUID, body: ImportRequest, identity: Identity, store=Depends(get_store)):
    return ingest(document_id, body, identity, store)


@app.delete('/v1/documents/{document_id}')
def delete(document_id: uuid.UUID, identity: Identity, store=Depends(get_store)):
    store.delete(identity, document_id)
    return {'deleted': True}


@app.get('/v1/documents/{document_id}/versions')
def versions(document_id: uuid.UUID, identity: Identity, store=Depends(get_store)):
    return store.history(identity, document_id)


@app.post('/v1/documents/{document_id}/reindex', status_code=202)
def reindex(document_id: uuid.UUID, identity: Identity, store=Depends(get_store)):
    return store.reindex(identity, document_id)


@app.get('/v1/jobs/{job_id}')
def status(job_id: uuid.UUID, identity: Identity, store=Depends(get_store)):
    job = store.job(identity, job_id)
    if not job:
        raise HTTPException(404, 'Job not found')
    return job


@app.post('/v1/search')
def search(body: SearchRequest, identity: Identity, store=Depends(get_store)):
    return {'hits': store.search(identity, body.query, body.filters, body.limit, body.rerank)}


@app.post('/v1/answer')
def answer(body: SearchRequest, identity: Identity, store=Depends(get_store)):
    hits = store.search(identity, body.query, body.filters, body.limit, body.rerank)
    return grounded_answer(body.query, hits, settings().minimum_evidence)
