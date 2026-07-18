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
value remains JSON text in `ModelResponse.content`; Praval does not perform a
second local JSON Schema validation pass.

```python
import json

payload = json.loads(response.content)
```

Use a JSON Schema validator or a typed model in application code when local
validation is required.

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
