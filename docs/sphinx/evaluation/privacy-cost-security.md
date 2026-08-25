# Cost, privacy, and security

Candidate and reference content is untrusted and may contain personal data,
secrets, retrieved copyrighted material, or prompt-injection instructions.
Default persistence and telemetry are metadata-only.

## Safe defaults

- Store hashes, sizes, stable references, status, usage, cost, and bounded error
  types. Keep raw input/output/context ephemeral.
- Use a separate judge model profile and credentials with the minimum provider
  permissions.
- Give evaluator agents only explicitly allowlisted read-only or
  `evaluation_safe` tools. v0.8.3 does not support evaluator side effects.
- Isolate evaluator memory by namespace and retention. Do not expose target
  operational memory or conversation history.
- Treat candidate text as data. The evaluator system prompt and rubric outrank
  any instruction inside it.
- Cap input tokens, output tokens, retries, tool rounds, time, concurrency, and
  cost per case and online job.
- Keep database DSNs, OTLP headers, and provider keys in named environment
  variables. Diagnostics may report whether they exist, never their values.
- Restrict evaluation databases and evidence stores more tightly than ordinary
  telemetry; evidence can reveal full outputs when content capture is enabled.

`JudgeResult` records usage and cost only when providers report them. A missing
cost is unknown, not zero. Budget breaches become bounded error results.
RAGAS may perform more than one model or embedding operation; test and budget
each selected metric before production use.

Online evaluation should begin with low deterministic sampling. Sampling is
not a privacy control: any selected subject must still satisfy the content,
access, region, encryption, and retention policy.

If explicit redacted-content capture is needed, redact before building the
evaluation context, store the content in an application-owned protected store,
and persist only its `ContentReference`. Never place redacted or raw content in
high-cardinality OpenTelemetry attributes.
