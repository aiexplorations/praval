"""External JSON Schema tools traverse the real Chat Completions adapter."""

from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from openai.types.chat import ChatCompletion

from praval import Agent
from praval.models import ToolSpec


@pytest.mark.parametrize("strict", [False, True])
def test_agent_external_schema_survives_chat_tool_continuation(monkeypatch, strict):
    monkeypatch.setenv("OPENAI_API_KEY", "test-external-schema-key")
    requests = []
    replies = [
        ChatCompletion.model_validate(
            {
                "id": "completion-tool",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "external-1",
                                    "type": "function",
                                    "function": {
                                        "name": "weather__lookup",
                                        "arguments": '{"city":"Paris"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ),
        ChatCompletion.model_validate(
            {
                "id": "completion-final",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Sunny in Paris."},
                    }
                ],
            }
        ),
    ]

    def respond(**params):
        requests.append(deepcopy(params))
        return replies.pop(0)

    client = Mock()
    client.chat.completions.create.side_effect = respond
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        agent = Agent("external-schema", provider="openai", model="gpt-test")
    schema = {
        "type": "object",
        "properties": {"city": {"type": "string", "enum": ["Paris", "Lyon"]}},
        "required": ["city"],
        "additionalProperties": False,
    }
    calls = []

    def lookup(city):
        calls.append(city)
        return "Sunny"

    agent.add_tool_spec(
        ToolSpec(
            name="weather__lookup",
            description="Look up the weather.",
            parameters=schema,
            strict=strict,
        ),
        lookup,
    )
    try:
        assert agent.chat("Forecast for Paris?") == "Sunny in Paris."
        assert calls == ["Paris"] and len(requests) == 2
        for request in requests:
            function = request["tools"][0]["function"]
            assert function["name"] == "weather__lookup"
            assert function["parameters"] == schema
            assert function.get("strict", False) is strict
        assert requests[1]["messages"][-1] == {
            "role": "tool",
            "tool_call_id": "external-1",
            "content": "Sunny",
        }
        assert schema["properties"]["city"]["enum"] == ["Paris", "Lyon"]
    finally:
        agent.close()
