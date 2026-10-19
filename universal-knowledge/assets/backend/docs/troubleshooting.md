# Troubleshooting

- **401/403:** AUTH_TOKENS is empty or the token digest differs. Hash the exact token bytes; restart the API after configuration changes. Never log the raw bearer token.
- **503 readiness:** Confirm migration completed, database credentials match POSTGRES_PASSWORD, and Redis resolves inside Compose. For native execution change postgres/redis hostnames to localhost and publish local-only database ports deliberately.
- **Empty results:** Poll the job until complete; verify tenant, reader ACL, metadata filters, provider identity, and revision. Hash fallback does not understand synonyms. Install/use learned embeddings if needed and reindex.
- **Worker failed:** Look up the safe error_code and structured exception_type. Check provider availability, dimensions, parse limits and database connectivity. Reindex creates a new job after the underlying problem is fixed. No unbounded automatic retry.
- **No extractable text:** Scanned PDF needs an external OCR step; encrypted PDFs and legacy DOC are unsupported.
- **URL rejected:** Only public HTTPS port 443 with no credentials is supported. Redirects, private/mixed DNS, compressed responses and non-text website types are intentionally rejected. Import an exported file instead.
- **Dimension mismatch:** Do not alter vector size in place and mix old/new embeddings. Provision a fresh database/schema, migrate with the new dimensions, reimport source documents, verify results, then switch traffic.
- **File collision:** Rerun setup with --plan, review every proposed replacement, and supply the exact plan digest only after confirming the replacements. Changed files invalidate the digest. Use a different output path to preserve existing files.
- **Docker unavailable:** Start Docker Desktop/Engine; `docker info` must succeed. Integration tests skip without TEST_DATABASE_URL and must be run in CI or a disposable local database before deployment.
