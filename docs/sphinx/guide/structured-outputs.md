# Structured Outputs

Use `response_schema` to ask providers for schema-shaped output:

```python
from praval import Agent

agent = Agent("extractor", provider="openai", model="gpt-5.4-mini")
response = agent.generate(
    "Extract company and amount: Acme paid $42.",
    response_schema={
        "type": "object",
        "properties": {
            "company": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["company", "amount"],
    },
)
```

The runtime rejects structured output requests when the resolved capability
profile does not support them. It also enforces a schema size limit to avoid
oversized provider payloads.

The schema is sent to the provider as a generation constraint. The returned
value remains JSON text in `ModelResponse.content`:

```python
import json

payload = json.loads(response.content)
```

Provider adapters map the neutral schema into provider-specific fields:

| Provider | Mapping |
| --- | --- |
| OpenAI Chat Completions | `response_format.type=json_schema` |
| OpenAI Responses | `text.format.type=json_schema` |
| Anthropic Messages | `output_config.format.type=json_schema` |
| Gemini | `generationConfig.responseMimeType` and `responseSchema` |
| Local OpenAI-compatible | Disabled unless explicitly enabled |

`Agent.chat()` still returns text. Prefer `Agent.generate()` when you need a
provider-constrained schema, response metadata, or usage.

## Local validation

Set `validate_locally=True` to have Praval check the final answer itself. The
runtime parses the content as JSON and validates it against the schema with
`jsonschema` (Draft 2020-12 unless the schema declares another `$schema`
dialect). Content that is not JSON, or does not match, raises
`ProviderInvalidResponseError`, a subclass of `ProviderError`, naming each
failing path:

```python
from praval import ProviderInvalidResponseError, StructuredOutputConfig

config = StructuredOutputConfig(
    schema={
        "type": "object",
        "properties": {"company": {"type": "string"}},
        "required": ["company"],
    },
    validate_locally=True,
)
try:
    response = agent.generate("Extract the company.", response_schema=config)
except ProviderInvalidResponseError as exc:
    print(exc)  # ...: $: 'company' is a required property
```

The same option is accepted in dict form:
`response_schema={"schema": {...}, "validate_locally": True}`. A dict without a
`schema` key is still treated as the schema itself.

Local validation runs on the final response of `chat`, `generate` and
`agenerate` (the model runtime's `invoke` and `ainvoke`), including the answer
after a tool loop and after a HITL resume. It does not run on streamed responses (`stream` and
`astream`); validate the `final` event's content in application code there. The
option is off by default, and it is never sent to the provider.
