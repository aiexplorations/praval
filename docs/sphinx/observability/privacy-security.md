# Privacy and security

The default policy is metadata-only. Raw prompts, responses, contexts, tool
arguments and results, retrieved documents, media, and future judge evidence
are excluded. `ExecutionObservation` represents such material with bounded
`ContentReference` hashes and metadata.

Content export requires both `capture_content = true` and an exact
`content_allowlist`. Allowed string values are still redacted for recognized
secrets and truncated to the configured byte limit before local export. This is
an explicit diagnostic capability, not consent or a complete data-loss
prevention system.

- Keep credentials in the environment variable named by `headers_env`.
- Use TLS to the Collector outside a trusted local network.
- Restrict backend, SQLite, and evaluation-store access.
- Align local `max_age_days` and `max_traces` with the data policy.
- Test content capture disabled and scan examples and fixtures for credentials.

Metric and log dimensions use bounded names and structured error types; secret
looking dimension values are redacted. Exporter exceptions are reported by
type rather than by potentially sensitive message.

