# Universal Knowledge Management Skill for Codex

A portable code-generating skill that adds project-owned ingestion, indexing, retrieval and RAG integration to new or existing projects. The self-contained skill is [universal-knowledge/SKILL.md](universal-knowledge/SKILL.md); the deployable reference source is in its assets/backend directory.

## Install

From a local checkout: `python scripts/install.py` installs into the Codex skills directory, refusing existing installations. Use `--skills-dir PATH` for another destination. To install from GitHub, ask Codex's skill installer: `Install the skill from https://github.com/infihelpsam/knowledgemanagementskill/tree/main/universal-knowledge`.

Download distribution: run `python scripts/package_release.py`. The `dist/universal-knowledge-0.1.0.zip` archive contains the installable folder; extract it under your Codex skills directory. The source ZIP contains the complete repository. Verify SHA256SUMS.json before installation through a trusted release channel. Checksums are integrity aids, not signatures.

Invoke `$universal-knowledge` in a target project. Or generate directly:

```sh
python universal-knowledge/scripts/setup.py --target /path/to/project --output knowledge --plan
python universal-knowledge/scripts/setup.py --target /path/to/project --output knowledge
```

For interactive setup run `python universal-knowledge/scripts/setup.py`. The target project must exist. Stack detection identifies Python, Node, Go and Rust manifests; output is a standalone Python service with Python and TypeScript integrations. Automatic host framework route/auth rewriting is intentionally left to the Codex integration workflow. Output paths are configurable. Existing files require review and explicit digest-bound confirmation; there is no silent overwrite switch.

## Included MVP

- PDF, DOCX, TXT, Markdown, HTML, CSV and single-page public HTTPS imports; normalized text, source/metadata, content hashes, duplicate detection, chunk offsets and revision history.
- Offline hashing baseline, optional local learned sentence embeddings, and OpenAI embedding adapter. PostgreSQL/pgvector cosine retrieval plus full-text RRF, optional local overlap reranking and metadata filters.
- Server-side opaque token identities, tenant namespaces and document owner/user/group ACL predicates applied before retrieval rankings. Owner-controlled writes, jobs, versions and deletion.
- Extractive grounded answers, citation offsets/versions, heuristic abstention, and extension protocols for model synthesis/reranking.
- Durable leased background ingestion jobs, status/retries, stale revision protection, hard deletion, retention, structured redacted logs and health checks.
- FastAPI, migrations, Docker Compose (PostgreSQL/pgvector, Redis, API and worker), Python/TypeScript clients, support and employee-assistant examples, tests and CI.

Start with the [backend README](universal-knowledge/assets/backend/README.md), [architecture/security](universal-knowledge/assets/backend/docs/architecture.md), and [troubleshooting](universal-knowledge/assets/backend/docs/troubleshooting.md).

## Development and validation

Requires Python 3.11+. Create/activate a virtual environment, then:

```sh
pip install -e './universal-knowledge/assets/backend[test]'
python scripts/validate.py
pytest -q tests universal-knowledge/assets/backend/tests
python scripts/package_release.py
```

Real SQL tests require TEST_DATABASE_URL for a disposable pgvector database and truncate its application tables. CI supplies one. Optional model adapters require separate credentials/model downloads and quality evaluations. See [validation evidence](VALIDATION.md) for what actually ran in the build environment.

## Scope and release gate

This is an MVP reference implementation, not enterprise-certified or established production-ready software. The offline default has limited semantic recall; default answers quote evidence rather than synthesize prose. Local Compose uses application-enforced isolation, not database RLS. Before commercial deployment: run PostgreSQL integration tests, choose/review legal licensing, pin and scan deployment images/dependencies, exercise your selected provider/auth integration, and add suitable operational protections described in architecture docs.

Knowledge graphs, fine-tuning, hosted billing and enterprise SSO are excluded. Provider/answerer/reranker/identity boundaries support future extensions. Redis is provisioned and checked for readiness; it does not own the ingestion queue.

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). License placeholders must be resolved by the owner before redistribution under a commercial/open-source license.
