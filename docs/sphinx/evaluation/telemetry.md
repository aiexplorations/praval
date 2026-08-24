# Evaluation telemetry and trace correlation

Evaluation records are authoritative. Telemetry is an operational projection
for dashboards, alerts, and correlation.

Offline runners emit `gen_ai.evaluation.result` events for persisted judge and
metric results. Counters track result status and failures, and a histogram
records finite scores with bounded attributes such as suite/run/case/subject,
judge or metric identity, version, and status. Candidate content, evidence,
exception messages, prompts, and credentials are excluded.

Sampled online evaluation additionally emits scheduled, dropped, retry,
failure, completion, duration, and queue-depth signals. Its worker span carries
a post-hoc `Link` to the original `trace_id` and `span_id`; the original request
has already completed, so parent/child would be semantically wrong.

Use the evaluation run and subject IDs to move from an alert to the
`EvaluationStore`, then use the linked trace to diagnose execution. A useful
dashboard groups pass rate and score distribution by stable judge/metric
version, with separate panels for judge errors, queue drops, result latency,
and cost. Do not compare scores across unversioned rubric or metric changes.

Telemetry emission is best effort and cannot change a persisted evaluation
outcome. Collector outage is visible through observability health signals; it
does not make the store result disappear.
