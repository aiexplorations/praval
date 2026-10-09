# Tools

Tools expose Python functions to agents. Legacy decorators and provider imports
remain compatible, but runtime-owned orchestration is the preferred direction.

```python
from praval import Agent

agent = Agent("calculator", provider="openai", model="gpt-5.4-mini")

@agent.tool
def add(x: int, y: int) -> int:
    return x + y

try:
    print(agent.chat("Use the tool to add 2 and 3."))
finally:
    agent.close()
```

Tool declarations are normalized into `ToolSpec` objects with JSON Schema
parameters. HITL metadata such as `requires_approval`, `risk_level`, and
`approval_reason` is preserved when legacy tool dictionaries are converted.

Register an existing JSON Schema, including an MCP tool's input schema, with
`Agent.add_tool_spec(ToolSpec(...), handler)`. Object schemas retain their
properties, required fields, nested arrays/objects, integer and boolean types,
enums and constraints. Anthropic sends them as `input_schema`; Gemini sends
them through its native `parametersJsonSchema` field, separate from the older
`parameters` representation. OpenAI and Cohere v2 send JSON Schema. Cohere v1
translates it into native parameter definitions and includes the complete schema
in the tool description; runtime argument validation still uses the original
schema.
Provider APIs may reject schema features outside their supported subset.
See [Gemini function declarations](https://ai.google.dev/api/generate-content#FunctionDeclaration)
and [Anthropic tool schemas](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools).

The registration contract tests exercise `add_tool_spec` through real adapters
with fake SDK/HTTP clients and inspect declarations on every dependent request.
The live certificate in `examples/certification/live_provider_tools.py` also
uses this registration path, requires integer and boolean arguments, and checks
actual handler execution and per-request usage. For a Gemini release-branch
check with a configured key and model:

```bash
source venv/bin/activate
export PRAVAL_GEMINI_MODEL="gemini-3.1-flash-lite"
export PRAVAL_DEMO_REPORT_DIR="/tmp/praval-gemini-tools"
python examples/certification/live_provider_tools.py --provider gemini
```

For Anthropic, set `ANTHROPIC_API_KEY` and `PRAVAL_ANTHROPIC_MODEL`, select a
separate report directory, and use `--provider anthropic`. These checks call
paid APIs and require available quota.

`Agent.tool` and `Agent.add_tool_spec` also add the tool to the global tool
registry for discovery, unless that name is already registered. `close()`
removes the entries the agent added; entries registered elsewhere, including
shared tools attached to the agent, stay in the registry.

## Argument validation

Model-supplied arguments are validated before the handler runs, on the sync,
async and HITL paths alike (for HITL, after approval, so edited arguments are
checked too):

- A Python function is validated against its signature with pydantic in lax
  mode, so `"3"` becomes `3` for an `int` parameter and the handler receives
  the coerced values. A number is accepted for a `str` parameter and passed as
  a string (`42` becomes `"42"`; `true` is still rejected), when the installed
  pydantic supports `coerce_numbers_to_str`. A parameter whose default is
  `None` accepts `None`, as if annotated `Optional[...]`. Unknown arguments are
  rejected unless the function takes `**kwargs`. A parameter whose annotation
  cannot be resolved, or has none, is passed through unchanged.
- A tool whose handler only accepts `**kwargs` and that declares a JSON Schema
  object (tools added with `Agent.add_tool_spec`, including MCP tools) is
  validated with `jsonschema`, Draft 2020-12 unless the schema declares another
  `$schema`. This path does not coerce values. An invalid schema is skipped
  with a warning. A `$ref` resolves only inside the schema itself: remote and
  `file:` references are never fetched, and a schema whose `$ref` cannot be
  resolved, or that is nested too deeply to check, is skipped with a warning.
  Arguments nested too deeply to validate are rejected. A string longer than
  10,000 characters (`praval.tool_execution.MAX_PATTERN_STRING_CHARS`) fails a
  `pattern` keyword without the pattern being evaluated. Shorter inputs use
  the `regex` engine in compatible VERSION0 mode with a 50 ms matching timeout.
  A timeout returns a typed validation failure and the handler does not run.
  Patterns themselves are limited to 10,000 characters. External
  `patternProperties` schemas are rejected before validation because
  `jsonschema` also matches those patterns inside `additionalProperties` and
  `unevaluatedProperties` helpers without a timeout. Nested `$schema` dialect
  changes are also rejected so they cannot restore an untimed validator.
  Ordinary `properties`, `propertyNames`, and nested `pattern` checks remain
  supported. These limits
  apply to external schemas; trusted response-schema matching retains its
  existing behavior. The timeout applies to each match rather than the entire
  validation operation. See [regex timeout documentation](https://github.com/mrabarnett/mrab-regex#timeout).

An argument string from the model that is not a JSON object (malformed JSON,
or a JSON array or scalar) is passed to validation as `{"raw": "<string>"}`,
so it fails as an unexpected `raw` argument instead of the tool running with
its defaults. An empty string means no arguments.

When validation fails the handler is not called. The model receives an error
result naming each failing field and the expected type, for example:

```text
Error: Invalid arguments for tool 'add': x: Input should be a valid integer,
unable to parse string as an integer, expected int; z: unexpected argument
```

## Tool results

Every tool call produces one `ToolResult`, in sync and async runs alike:

- A handler that returns a `ToolResult` keeps its `content`, `is_error` and
  `metadata`; the runtime sets `tool_call_id` and `name` from the model's call.
- Any other return value becomes `content=str(value)`. A string that starts with
  `Error:`, `Unknown function:` or `Rejected by human reviewer:` is an error, as
  in earlier releases.
- An exception becomes an error result with content
  `Error: <ExceptionType>: <message>`.
- Unknown tools and rejected HITL calls are error results.

`execute_legacy_tool_call` and `HITLRuntime.execute_or_interrupt` /
`execute_with_decision` still return the result content as a string for
provider adapters; `HITLRuntime.execute_or_interrupt_result` and
`execute_with_decision_result` return the `ToolResult`, as do the async
variants.

## Execution

Providers translate declarations and provider-specific tool-call wire shapes.
Runtime code owns execution, approval and resume state, tracing, and final
follow-up calls. Retry behavior is provider and error specific; Praval does not
promise universal retries or a circuit breaker.
