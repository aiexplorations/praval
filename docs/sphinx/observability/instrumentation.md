# Instrumentation map

Praval creates one observation per agent or workflow and aggregates facts
rather than creating an observation for every internal call. Nested entry into
the same identity joins the active observation.

| Runtime boundary | Telemetry |
|---|---|
| Agent | `praval.agent.invoke` span and one `ExecutionObservation` |
| Workflow/composition | `praval.workflow.invoke` span and one observation |
| ModelRuntime/provider | provider, model, request mode, token usage, errors |
| Tool and MCP call | bounded tool name, status, duration, error type |
| Reef/Spore | producer, delivery, and consumer spans plus aggregated handoff facts |
| Retry | attempt, operation, bounded reason type, backoff |
| HITL | decision identity, decision, tool, reviewer type |
| Memory, storage, and media | active execution correlation; content stays behind the privacy policy |

Identity fields include observation, run, agent or workflow, conversation,
response, trace, and span IDs where available. Error types are structured;
exception messages, prompts, responses, tool payloads, retrieved documents,
media, and credentials are not metric dimensions.

The frozen schema is `ExecutionObservation.schema_version == 1`. The complete
field and recorder contracts are in [API and migration](api-migration.md).

