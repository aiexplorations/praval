"""HITL example: mixed agents with hitl=False and hitl=True."""

import os

os.environ.setdefault("OPENAI_API_KEY", "demo-key")
os.environ.setdefault("PRAVAL_HITL_DB_PATH", "/tmp/praval_hitl_example_016.db")

import openai

from praval import HITLConfigurationError, InterventionRequired, agent, tool


class _Function:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, call_id: str, name: str, arguments: str):
        self.id = call_id
        self.type = "function"
        self.function = _Function(name, arguments)


class _Message:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message):
        self.message = message


class _Response:
    def __init__(self, message):
        self.choices = [_Choice(message)]


class _DummyOpenAIClient:
    class _Chat:
        class _Completions:
            def create(self, **kwargs):
                messages = kwargs.get("messages", [])
                has_tool_output = any(
                    m.get("role") == "tool" for m in messages if isinstance(m, dict)
                )
                if has_tool_output:
                    return _Response(
                        _Message(content="Action completed after HITL decision.")
                    )
                return _Response(
                    _Message(
                        content=None,
                        tool_calls=[
                            _ToolCall(
                                "call_mixed_1",
                                "dangerous_action",
                                '{"target": "prod-db"}',
                            )
                        ],
                    )
                )

        def __init__(self):
            self.completions = self._Completions()

    def __init__(self, api_key=None):
        self.chat = self._Chat()


openai.OpenAI = _DummyOpenAIClient


@tool(
    tool_name="dangerous_action",
    description="Simulate risky action",
    requires_approval=True,
    risk_level="critical",
    approval_reason="Critical operation in mixed-agent demo.",
)
def dangerous_action(target: str) -> str:
    return f"Simulated operation against {target}"


@agent(
    "non_hitl_agent",
    provider="openai",
    model="gpt-5-mini",
    config={"provider_options": {"endpoint": "chat_completions"}},
    tools=["dangerous_action"],
    hitl=False,
    auto_broadcast=False,
)
def non_hitl_agent(spore):
    return {"status": "non-hitl"}


@agent(
    "hitl_enabled_agent",
    provider="openai",
    model="gpt-5-mini",
    config={"provider_options": {"endpoint": "chat_completions"}},
    tools=["dangerous_action"],
    hitl=True,
    auto_broadcast=False,
)
def hitl_enabled_agent(spore):
    return {"status": "hitl-enabled"}


if __name__ == "__main__":
    no_hitl = non_hitl_agent._praval_agent
    with_hitl = hitl_enabled_agent._praval_agent

    print("Running non-HITL agent path (expected configuration error)...")
    try:
        print(no_hitl.chat("Run dangerous action now."))
    except HITLConfigurationError as err:
        print(f"Expected failure: {err}")

    print("\nRunning HITL-enabled agent path...")
    try:
        print(with_hitl.chat("Run dangerous action now."))
    except InterventionRequired as interruption:
        print(f"Intervention required: {interruption.intervention_id}")
        hitl_enabled_agent.approve_intervention(
            interruption.intervention_id, reviewer="ops"
        )
        print(with_hitl.resume_run(interruption.run_id))
