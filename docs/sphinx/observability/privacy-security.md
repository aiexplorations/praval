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

## Content enablement checklist

Before setting `capture_content=true`:

1. Name the diagnostic purpose and the exact allowlisted content kinds.
2. Redact secrets and regulated identifiers before they reach Praval; built-in
   patterns are a safety net, not a complete DLP policy.
3. Set retention by both age and trace count, and test whole-trace deletion.
4. Restrict filesystem/database and backend access, backups, and exports.
5. Confirm cross-region transfer, incident response, and user deletion rules.
6. Run privacy tests with representative prompts, tool payloads, retrieved
   material, media metadata, credentials, and exporter failures.

Content allowlisting never makes a value suitable as a metric dimension.
Allowed content belongs only in privacy-filtered local diagnostic attributes or
an application-owned protected evidence store.

## Threat boundaries

Trace carriers cross process boundaries and are validated as W3C metadata;
they are not authorization. Secure Spores protect carrier integrity together
with the payload, but receivers must still authorize message source and
operation. OTLP headers authenticate export, not agent requests. Evaluation
databases and telemetry backends require separate identities and permissions.

Local SQLite may contain linked identifiers and opted-in redacted content even
when raw content is absent. Protect, rotate, and delete it like diagnostic data,
and never publish it with the generated documentation site or release wheel.
