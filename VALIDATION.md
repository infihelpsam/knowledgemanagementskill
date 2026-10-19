# Validation evidence

Executed on 2026-10-20 (Asia/Dubai client date), Windows x64, Python 3.12.14.

| Check | Observed result |
|---|---|
| pytest: repository generator/distribution + backend suite | **34 passed, 5 skipped**, 1.50 seconds |
| PostgreSQL integration cases | Four skipped: TEST_DATABASE_URL unset; Docker daemon unavailable |
| Symlink protection test | Skipped: Windows host denied symlink creation |
| FastAPI authentication, spoofed tenant headers/body, import validation, body limit | Passed |
| Format extraction, PDF/DOCX fixtures, normalization, chunks and hashes | Passed |
| SSRF private destinations, scheme/port restrictions, DNS pin/redirect behavior | Passed with network mocks |
| Evidence citations, abstention, inert injection, provider failure, log redaction | Passed |
| Generator dry-run, collisions, stale approval, path escapes and blocking parents | Passed |
| Deterministic archive / secret-cache exclusion tests | Passed |
| Official skill-creator quick_validate.py | Skill is valid |
| Repository metadata, links, TOML and Python syntax validation | Passed |
| Backend wheel | Built successfully; SQL migration confirmed inside wheel |
| TypeScript client | tsc --noEmit --strict --target es2022 --module nodenext passed |
| Local installation smoke test | Installed to workspace test directory, leaving user's global skills unchanged |
| Generated project and Compose configuration | 33 files generated; docker compose config --quiet passed |
| Release ZIPs | Installable/source archives built; integrity, migration inclusion, extracted-generator dry run passed; SHA256 manifest produced |

Test dependencies required downloads. The first editable build hit Windows' long-path limit; a non-editable wheel build succeeded using a shorter temporary directory. FastAPI TestClient's local socket pair stalled under the managed sandbox; the complete passing test run used approved execution outside the sandbox. Stalled test processes were interrupted. One upstream Starlette/httpx TestClient deprecation warning remains; tests still pass. Resolved package versions are recorded in requirements-tested.txt; this is not a signed lockfile or a vulnerability scan.

## Outstanding verification and limits

The SQL migration, pgvector ranking, database ACL filtering, versioning, worker publication, lease recovery, cascaded deletion and retention have real integration tests supplied, but those tests were **not executed here**. Do not interpret unit tests as proof of SQL behavior. `.github/workflows/ci.yml` provisions disposable pgvector for these tests; no remote CI run has occurred. Generated Compose provides an isolated test service (`docker compose --profile test run --build --rm tests`). Docker image builds and full service startup remain unverified locally.

Optional OpenAI and sentence-transformers adapters were not exercised against live providers/models. Retrieval quality, embedding costs, load/failover behavior, untrusted parser resource isolation, generative LLM prompt-injection resistance, auth-provider integration and penetration testing remain deployment work. The default hash embedder is an offline lexical baseline, and the extractive answerer's token-coverage heuristic does not prove entailment. Source text may contain malicious instructions; quoted answers must be rendered as data. Redis is provisioned/readiness-checked, while PostgreSQL owns durable jobs.

Tenant/document isolation is enforced in application SQL predicates, not RLS. Static token identities have no built-in expiry; operators must provision, rotate and revoke tokens. API reads are authorized at query time; deletion cannot recall data already returned. Raw file binaries are not retained, revision ACL snapshots are not historical, and external provider/backup retention requires separate processes. License selection remains an owner decision, with explicit placeholders included. No enterprise certification, security audit or production-readiness claim is made.
