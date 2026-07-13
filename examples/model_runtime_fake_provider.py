"""Offline model runtime example using a fake provider.

Run:
    python examples/model_runtime_fake_provider.py
"""

from praval.core.agent import AgentConfig
from praval.model_runtime import ModelRuntime
from praval.models import ModelEvent, ModelResponse, ProviderCapabilities


class FakeProvider:
    """Small provider adapter that needs no network or credentials."""

    provider_name = "fake"
    capabilities = ProviderCapabilities(
        tools=True,
        streaming=True,
        native_streaming=True,
        structured_outputs=True,
    )

    def invoke(self, request):
        return ModelResponse(
            content='{"summary": "runtime contracts are explicit"}',
            provider=self.provider_name,
            model=request.model,
        )

    def stream(self, request):
        yield ModelEvent(type="delta", delta="streamed ")
        yield ModelEvent(type="delta", delta="text")
        yield ModelEvent(
            type="final",
            response=ModelResponse(
                content="streamed text",
                provider=self.provider_name,
                model=request.model,
            ),
        )


def main() -> None:
    runtime = ModelRuntime(
        provider=FakeProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )

    response = runtime.invoke(
        messages=[{"role": "user", "content": "Summarize the runtime."}],
        response_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )
    print(response.content)

    for event in runtime.stream(
        messages=[{"role": "user", "content": "Stream a short answer."}]
    ):
        if event.type == "delta":
            print(event.delta, end="")
    print()


if __name__ == "__main__":
    main()
