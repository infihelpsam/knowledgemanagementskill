# Implementation plan

Repository inspection: empty workspace, no AGENTS.md, no Git metadata. Python is available through the Codex runtime; Docker CLI exists but its daemon is unavailable.

1. Package `universal-knowledge` as a self-contained skill. Build a stack-detecting CLI with dry-run manifests, configurable destination, collision refusal, and explicit reviewed overwrite plans. Test generation and release archives.
2. Implement a Python 3.11+ FastAPI reference backend, format extractors, bounded website import, normalization, provenance, deduplication, versioning, interchangeable embeddings, PostgreSQL/pgvector migration, ACL-filtered hybrid retrieval and extractive grounded answers.
3. Add durable PostgreSQL ingestion jobs with leases/retries, Redis readiness, authenticated endpoints, retention/deletion, Compose, Python/TypeScript clients, two sample applications, and extension protocols.
4. Run unit/API/security tests and optional real PostgreSQL tests. Fix observed failures. Validate generated artifacts and ZIP contents. Document operational gaps and exact test evidence.

Design decisions: bearer tokens map to server-configured identities; callers never supply trusted tenant or groups. Document ACLs permit owner or configured readers. Jobs and all document access are tenant scoped. Grounded default answers return verbatim evidence with stable citations, avoiding unconstrained document-to-instruction execution. Optional external model adapters require independent security evaluation. PostgreSQL remains the source of truth and durable queue; Redis is available for future cache/event adapters.

No hosted deployment, billing, SSO, fine-tuning, or knowledge graph implementation. No certification or production-readiness claim. New files only in this empty repository; the distributed generator must refuse collisions unless the user confirms a digest-bound plan.

## Milestone results

1. Implemented self-contained skill, interactive/dry-run generator, collision plans, installer and deterministic ZIP packaging; generation/approval/distribution tests passed.
2. Implemented extractors, providers, migrations, hybrid retrieval, ACLs, versions, citations and extractive abstaining answers. Unit tests passed; four real PostgreSQL cases remain skipped without a database.
3. Implemented FastAPI, durable worker, retention/deletion, examples, clients and local/test Compose services. API tests and TypeScript checks passed; Docker service startup remains unverified.
4. Final suite: 34 passed, five skipped (four database cases and Windows symlink capability), one upstream deprecation warning. Official skill validation, wheel/migration packaging, generation and Compose config checks passed. See VALIDATION.md for evidence and limitations.
