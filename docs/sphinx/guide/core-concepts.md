# Core concepts and API layers

Praval separates model execution from agent collaboration. Understanding that
boundary makes the rest of the framework easier to use.

## Mental model

```text
Application
  ├─ Agent ── ModelRuntime ── Provider adapter ── model API
  │    ├─ tools and HITL
  │    ├─ conversation state
  │    └─ optional memory
  └─ Reef
       ├─ Agent handlers
       └─ Spores carrying structured knowledge
```

- **Agent** owns an identity, provider configuration, conversation history,
  registered tools, and optional memory/HITL state.
- **ModelRuntime** translates provider-neutral requests into an adapter call
  and normalizes responses, usage, tool calls, and stream events.
- **Provider adapter** handles the actual OpenAI, Anthropic, Cohere, Gemini, or
  OpenAI-compatible wire format.
- **Spore** is the immutable message envelope used for agent-to-agent delivery.
- **Reef** routes Spores locally or through its RabbitMQ distributed backend.
- **Decorated agent** connects a Python handler and an underlying `Agent` to
  Reef delivery.
- **PravalApp** retains agents and a Reef for cleanup; it is not an isolated
  provider/communication container in this release.

## Direct Agent API

Use `Agent` when the application is initiating a model operation directly:

```python
from praval import Agent

agent = Agent("reviewer", provider="anthropic", model="claude-sonnet-5")
response = agent.generate("Review this design in three bullets.")
print(response.content)
agent.close()
```

The primary methods are:

- `generate()` and `agenerate()` for complete `ModelResponse` objects.
- `stream()` and `astream()` for normalized `ModelEvent` sequences.
- `add_tool_spec()` and `Agent.tool()` for model-callable functions.
- `transcribe()` and `speak()` for request-based OpenAI media operations.
- `chat()` for the established string-returning compatibility path.

Provider capabilities are resolved before execution. A capability error means
the selected profile does not advertise the requested behavior; it does not
mean another provider is selected automatically.

## Decorated agents

`@agent` constructs an underlying `Agent`, attaches a handler, and registers
metadata used by Reef startup:

```python
from praval import agent


@agent("auditor", responds_to=["draft_ready"])
def audit_draft(spore):
    return {
        "type": "audit_complete",
        "draft_id": spore.knowledge["draft_id"],
        "status": "accepted",
    }
```

If `auto_broadcast=True` (the default), a returned dictionary is broadcast as a
new Spore. Calling `broadcast()` explicitly is useful when a handler emits more
than one message or needs to choose the emission point.

`responds_to` compares its values with `spore.knowledge.get("type")`. Praval
does not impose a domain schema beyond the Spore envelope; applications should
define and validate stable message contracts for important workflows.

## Spores

A Spore includes:

- `id`, `from_agent`, optional `to_agent`, and `spore_type` routing fields.
- `knowledge`, a JSON-oriented dictionary carrying the domain payload.
- timestamps, priority, reply/correlation metadata, and optional references.
- optional content parts and knowledge/data references in the newer wire form.

Treat Spores as immutable. Create a derived Spore rather than changing a
received one. Keep payloads serializable when a workflow may move to RabbitMQ.

## Reef delivery

The built-in Reef supports:

- direct delivery to an agent;
- broadcast delivery;
- named channels;
- request/reply metadata;
- completion tracking and shutdown;
- an optional RabbitMQ backend for distributed delivery.

Redis, PostgreSQL, S3-compatible stores, and Qdrant belong to the storage
system. Redis is not a Reef transport. AMQP, MQTT, and STOMP adapters are part
of the optional secure transport subsystem and should not be described as
interchangeable core Reef backends.

Delivery is concurrent, but application correctness still requires explicit
termination, correlation, idempotency, error results, and cleanup. Praval does
not promise that every failure is retried or that a circuit breaker exists.

## Tools and human approval

Tools use JSON-schema argument contracts and normal Python handlers. A tool may
declare `requires_approval`, a risk level, a reason, and metadata. When HITL is
enabled for the owning agent, a model-generated call can persist an
intervention, pause the run, accept approval/edited arguments/rejection, and
resume.

If a tool requires approval and the agent has HITL disabled, Praval raises
`HITLConfigurationError`; it does not silently bypass the policy.

MCP-discovered tools use the same Agent tool registry through
`Agent.add_tool_spec()`. MCP tools are async-only in this release and therefore
use `agenerate()` or `astream()`.

## Memory, embeddings, and storage

Memory and storage are separate concerns:

- Memory manages short-term, episodic, semantic, and long-term recall paths.
- `EmbeddingRuntime` creates vectors through a configured local or provider
  embedding model.
- `DataManager` exposes asynchronous storage operations through registered
  providers.
- `DataReference` lets a Spore refer to stored data without embedding the full
  payload.

There is no implicit cross-provider storage fallback. Applications that need a
fallback policy must implement it and decide which errors permit fallback.

## Lifecycle

Every example and service should close what it opens:

- call `Agent.close()` for direct agents;
- call `Reef.wait_for_completion()` before process shutdown when work is
  outstanding;
- call `Reef.shutdown()` after completion;
- close MCP clients and storage providers;
- use `PravalApp` when retaining several agents under one cleanup owner helps.

## What to read next

- {doc}`model-runtime` for request and response contracts.
- {doc}`reef-protocol` for routing details.
- {doc}`tool-system` and {doc}`../tutorials/hitl-interventions` for tools.
- {doc}`storage` and {doc}`embeddings` for data paths.
- {doc}`mcp` for external tool servers.
- {doc}`application-lifecycle` for the exact `PravalApp` boundary.
