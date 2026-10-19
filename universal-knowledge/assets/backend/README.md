# Universal Knowledge reference backend

Project-owned FastAPI ingestion and ACL-filtered PostgreSQL/pgvector retrieval. Version 0.1.0 is an MVP requiring deployment review, not a certified or production-proven service.

## Start locally

Requires Docker Compose v2. Copy `.env.example` to `.env`. Replace POSTGRES_PASSWORD and the matching password in DATABASE_URL with the same long random value. Leave database hostname `postgres` inside Compose. `.env` must never be committed.

Create an opaque token and SHA256 digest locally:

```sh
python -c "import secrets,hashlib; t=secrets.token_urlsafe(32); print('TOKEN='+t); print('DIGEST='+hashlib.sha256(t.encode()).hexdigest())"
```

Set `AUTH_TOKENS` to a JSON object such as `{"DIGEST":{"tenant":"acme","subject":"alice","groups":["support"]}}`, replacing DIGEST with the actual hash. Do not use sample credentials. The empty default denies all access. Different user tokens must map to their actual server-side identities; do not route all users through an owner token.

```sh
docker compose up --build -d
docker compose logs migrate worker
```

API: http://localhost:8000/docs. `/health/live` is public, `/health/ready` requires bearer auth and checks PostgreSQL and Redis. Migrations run before API/worker. Database volume persists data; deleting that volume destroys it. Do not run destructive cleanup against needed data.

For native development: Python 3.11+, `python -m venv .venv`, activate it, `pip install -e '.[test]'`, configure reachable database/Redis URLs, `python -m knowledge.migrate`, `python -m knowledge.worker`, and `uvicorn knowledge.api:app --no-access-log`. Migrations live in knowledge/migrations and ship as Python package data. PostgreSQL must have the vector extension available.

## API

All `/v1` endpoints require `Authorization: Bearer TOKEN`.

| Route | Behavior |
|---|---|
| POST /v1/documents | Generate ID, import base64 file or website URL, return job |
| PUT /v1/documents/{id} | Owner upsert, or create caller-owned ID |
| DELETE /v1/documents/{id} | Owner hard deletion including revisions/jobs/chunks |
| GET /v1/documents/{id}/versions | Owner version metadata |
| POST /v1/documents/{id}/reindex | Owner enqueue current text with configured embedder |
| GET /v1/jobs/{id} | Owner status, attempts and safe error code |
| POST /v1/search | Hybrid hits and provenance |
| POST /v1/answer | Evidence extracts/citations or abstention |

Import JSON: `{"filename":"manual.md","content_base64":"BASE64","source":"manual-v1","metadata":{"collection":"support"},"readers":["group:support"]}`. Supply exactly one of content_base64 or url. Website example: `{"url":"https://example.com/manual"}`. Files: PDF, DOCX, UTF-8 TXT/Markdown/HTML/CSV. Metadata/source are caller-provided provenance labels, not verified authenticity. History stores normalized text, not original binaries or prior ACL snapshots. Owner-only ACL changes are made through a same-content PUT; they create a new revision.

Search/answer JSON: `{"query":"How long is the warranty?","filters":{"collection":"support"},"limit":8,"rerank":true}`. Filters use JSON containment. Poll queued/running jobs until complete before expecting new chunks. The API does not crawl linked pages. Citation offsets refer to normalized text (Python Unicode character offsets), not original PDF page coordinates or JavaScript UTF-16 indices.

The default answer is extractive, with a heuristic evidence threshold. It may quote malicious document text as data. Render as text; do not insert answers or sources into unsanitized HTML or execute returned links. No LLM synthesis is enabled. See architecture before adding a generative adapter.

## Providers

- `hash` (default): offline token hashing baseline, no model download, weak synonym/semantic recall.
- `sentence-transformers`: install `pip install -e '.[semantic]'`, use EMBEDDING_MODEL and matching EMBEDDING_DIMENSIONS. Initial model download required.
- `openai`: set OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL and matching dimensions. Explicit external data disclosure; provider errors fail/retry jobs rather than silently mixing spaces.

Changing embedding identity hides old chunks until reindex. A vector dimension change requires a fresh schema/reimport. Optional overlap reranking is a local baseline, not a cross-encoder. Exact vector search is used for correctness; benchmark and add suitable indexes for scale.

## Verify

```sh
pip install -e '.[test]'
pytest -q
```

Unit tests run without services. PostgreSQL integration tests skip unless TEST_DATABASE_URL is set. **Use only a disposable database: tests truncate application tables.** Compose includes an isolated, ephemeral test database:

```sh
docker compose --profile test run --build --rm tests
```

Alternatively run pytest natively with TEST_DATABASE_URL for a dedicated PostgreSQL instance. CI provisions an isolated pgvector service. Tests cover parsing, limits, API authentication, spoofed tenant assertions, SSRF, citations, inert prompt injection, SQL isolation, upserts, deletion, reindex, stale jobs and retention. Optional provider quality, large-document behavior, throughput, infrastructure failover and hostile-parser resource isolation are not established by this suite.

Python and TypeScript server clients are in integrations/. Sample projects in examples/ demonstrate support-team ACLs and named employee access. They require configured tokens and a running worker. See [architecture](docs/architecture.md) and [troubleshooting](docs/troubleshooting.md).
