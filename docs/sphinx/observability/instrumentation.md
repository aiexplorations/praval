# Instrumentation map

Praval creates one observation per agent or workflow and aggregates facts
rather than creating an observation for every internal call. Nested entry into
the same identity joins the active observation.

| Runtime boundary | Telemetry |
|---|---|
| Agent | `praval.agent.invoke` span and one `ExecutionObservation` |
| Workflow/composition | `praval.workflow.invoke` span and one observation |
| ModelRuntime | `model.invoke` client span, request mode, tool-round bound, usage |
| Provider | `provider.invoke` or `provider.stream` client span, provider/model/status |
| Tool and MCP call | operation span, bounded tool name/call ID/status/duration/error type |
| Reef/Spore | `praval.reef.producer`, `.delivery`, and `.consumer` spans plus one handoff fact |
| Retry | `praval.retry` event with attempt, operation, reason type, and backoff |
| Resource limit | `praval.limit.reached` event with the bounded limit name/value |
| HITL | decision identity, decision, tool, and reviewer type aggregated on the root |
| Memory and retrieval | active root correlation; references, counts, and bounded status only |
| Storage | active root correlation; provider/operation/status without stored values |
| Media | request mode and provider facts; audio/image bytes are never attributes |

Identity fields include observation, run, agent or workflow, conversation,
response, trace, and span IDs where available. Error types are structured;
exception messages, prompts, responses, tool payloads, retrieved documents,
media, and credentials are not metric dimensions.

The frozen schema is `ExecutionObservation.schema_version == 1`. The complete
field and recorder contracts are in [API and migration](api-migration.md).

## Root identity and completion

Root spans begin with observation/run/kind plus the applicable agent,
workflow, conversation, and request-mode fields. Completion adds status,
duration, provider/model, response ID, terminal outcome, and usage when known.
Exceptions retain their Python type as a bounded error class. Messages and
stack-local values are not metric dimensions.

Nested entry for the same agent/workflow joins the active root rather than
creating a second observation. A nested different identity can have its own
span while the outer workflow continues aggregating handoff facts. This is why
evaluation receives one subject per declared target boundary even though the
trace still shows its internal work.

## Instrumentation ownership

`initialize_instrumentation()` applies supported provider wrappers
idempotently. Instrumentation records metadata around normal provider calls;
it does not replace provider selection, retry policy, exceptions, or return
types. Base-package API instrumentation remains safe when there is no SDK.

MCP, memory, storage, HITL, and media correlation occurs only while an agent or
workflow observation scope is active. Standalone calls remain application
operations and are not mislabeled as completed agents.
