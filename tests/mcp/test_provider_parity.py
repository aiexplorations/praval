"""Provider parity for async MCP tools through the neutral ModelRuntime path."""

from typing import Any

import pytest

from praval.core.agent import AgentConfig
from praval.model_runtime import ModelRuntime
from praval.models import (
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
)
from praval.providers.anthropic import AnthropicProvider
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider


class FakeProvider:
    """Marker base for the provider-neutral contract case."""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_name, provider_base",
    [
        ("openai", OpenAIProvider),
        ("anthropic", AnthropicProvider),
        ("gemini", GeminiProvider),
        ("fake", FakeProvider),
    ],
)
async def test_mcp_tool_uses_same_runtime_path_for_all_providers(
    provider_name: str, provider_base: type
) -> None:
    class ContractProvider(provider_base):
        capabilities = ProviderCapabilities(tools=True)

        def invoke(self, request: Any) -> ModelResponse:
            self.request = request
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id=f"{provider_name}-call",
                        name="server__lookup",
                        arguments={"query": "praval"},
                    )
                ]
            )

        def continue_with_tool_results(
            self, request: Any, response: ModelResponse, results: list
        ) -> ModelResponse:
            return ModelResponse(content=results[0].content)

    provider = ContractProvider.__new__(ContractProvider)
    runtime = ModelRuntime(
        provider=provider,
        provider_name=provider_name,
        config=AgentConfig(provider=provider_name, model="contract-model"),
    )

    async def lookup(query: str) -> ToolResult:
        return ToolResult(
            tool_call_id="mcp-internal",
            name="server__lookup",
            content=f"found:{query}",
            metadata={"source": "mcp"},
        )

    response = await runtime.ainvoke(
        messages=[{"role": "user", "content": "look up Praval"}],
        tools=[
            {
                "name": "server__lookup",
                "function": lookup,
                "description": "Look up a record",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                "async_only": True,
            }
        ],
    )

    assert response.content == "found:praval"
    assert provider.request.tools[0].name == "server__lookup"
    assert response.metadata["tool_results"][0]["metadata"] == {"source": "mcp"}
