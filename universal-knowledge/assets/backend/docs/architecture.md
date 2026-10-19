# Architecture and trust boundaries

The client authenticates with an opaque bearer token. AUTH_TOKENS maps SHA256 token digests to trusted tenant, subject and groups. Requests cannot override identity. Write/history/job operations require ownership; read operations permit ownership or user/group readers within the same tenant. Empty readers means owner-only. There is no anonymous/public document flag.

The API validates and extracts a bounded file or public HTTPS website, normalizes Unicode/control characters, and atomically stores a document revision and ingestion job. Each revision preserves normalized text, source, metadata and hash. Original binary files are not retained. Hash matches are reported only for documents owned by that caller, avoiding duplicate detection as a privacy oracle. Equivalent same-ID upserts are idempotent. Distinct IDs remain separate even with identical content so ACL/provenance do not merge accidentally.

Workers claim jobs with SKIP LOCKED and five-minute leases. Embedding calls run outside transactions; publication locks the document and verifies revision, embedding identity and lease token before atomically replacing chunks. Expired leases may retry up to JOB_ATTEMPTS; final expired jobs fail. There is no heartbeat: long jobs may be recomputed. Deletions cascade through revisions, jobs and chunks. A deleted job cannot publish its content. Retention periodically hard-deletes documents based on document updated_at; history does not have an independent expiry.

Search materializes an authorized relation using tenant, owner/readers, metadata JSON containment, current revision and embedding identity predicates. Exact cosine and PostgreSQL English full-text candidate rankings combine through reciprocal rank fusion (RRF, k=60). Optional token overlap reranking runs only on authorized hits. Embedding spaces must not mix. New revisions hide old chunks immediately while ingestion is pending, preferring freshness/security to continuous availability.

The baseline RAG answerer retrieves authorized text, checks query token coverage, and returns up to three verbatim chunks with document/version/offset citations. It abstains without qualifying evidence. This is extractive retrieval-augmented answering, not generative synthesis or a calibrated entailment classifier. Retrieved malicious instructions may appear as quoted data; clients must render plain text or sanitize Markdown/HTML and source links. No document can invoke tools, change prompts or obtain credentials. For generative extensions implement Answerer with separate system/data channels, no tool execution, strict citation verification, and new adversarial evaluations; prompt wording alone is not a security boundary.

Local default feature hashing is deterministic and offline but lacks learned semantics. Install the semantic extra for sentence-transformers; the initial model download needs network access. The OpenAI adapter sends document/query text to OpenAI, uses the official fixed endpoint, validates embedding shapes, and does not silently fall back on provider errors. Embedding or dimension changes require deliberate migration/reindex. Same-dimension reindex can run per document; dimension changes need a new database/schema and reimport in this MVP.

## Deployment boundaries

The application database role in local Compose owns its schema. Tenant isolation is enforced by parameterized application queries, not PostgreSQL RLS. Do not expose database credentials or permit untrusted SQL. Separate migration/runtime roles, database RLS, egress firewall, TLS termination, secret management, rate limiting, quotas, request duration limits, parser sandboxing, backup policies, audit exports and load/penetration tests are deployment work. The default database listens only on the Compose network; API binds localhost. Redis has no external port and is not a source of truth.

File parsers are third-party libraries operating inside the process. Byte/text/page/DOCX expansion bounds mitigate common abuse but do not prove CPU/memory safety against every crafted PDF or DOCX. Process isolation and resource limits are required for hostile multi-user deployment. Website fetching rejects all redirects, pins validated public DNS results, preserves TLS hostname verification, rejects compressed payloads, and caps read bytes/socket timeouts. Network egress controls remain recommended; the MVP does not implement site crawling, JavaScript rendering, OCR, proxy access, or a hard overall fetch deadline.

Search results are authorized at query time. ACL changes/deletion cannot retract responses already returned, client caches, or external embedding provider logs. Backups, replicas, telemetry and external systems require their own retention/deletion procedures. App logs omit raw text, tokens, SQL errors and upstream response bodies. Request IDs and job IDs provide correlation, not a compliance audit ledger.

## Extension interfaces

Embedder, Reranker and Answerer protocols live in providers.py; Principal is the identity integration boundary. Preserve filtering before any reranker/LLM invocation. Future knowledge graph, fine-tuning, billing, and SSO adapters should be separate modules around these boundaries; none ships in this release. Redis can support events/cache only if cache keys and invalidation preserve tenant/ACL/deletion semantics.

## Authoritative implementation references

- [pgvector Python integration](https://github.com/pgvector/pgvector-python)
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), for a future defense-in-depth deployment
- [FastAPI bearer security](https://fastapi.tiangolo.com/tutorial/security/)
