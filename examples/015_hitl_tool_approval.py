"""HITL example: tool call approval/edit/resume with @agent(hitl=True)."""

import os

# Keep example self-contained without external API calls.
os.environ.setdefault("OPENAI_API_KEY", "demo-key")
os.environ.setdefault("PRAVAL_HITL_DB_PATH", "/tmp/praval_hitl_example_015.db")

import openai

from praval import InterventionRequired, agent, tool


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
                        _Message(content="Final answer after human-approved tool run.")
                    )
                return _Response(
                    _Message(
                        content=None,
                        tool_calls=[
                            _ToolCall(
                                "call_demo_1",
                                "add_numbers",
                                '{"x": 2, "y": 3}',
                            )
                        ],
                    )
                )

        def __init__(self):
            self.completions = self._Completions()

    def __init__(self, api_key=None):
        self.chat = self._Chat()


# Monkey patch OpenAI SDK client for this example process.
openai.OpenAI = _DummyOpenAIClient


@tool(
    tool_name="add_numbers",
    description="Add two numbers",
    requires_approval=True,
    risk_level="high",
    approval_reason="Arithmetic tool execution requires human sign-off in this demo.",
)
def add_numbers(x: int, y: int) -> int:
    return x + y


@agent(
    "hitl_demo_agent",
    provider="openai",
    model="gpt-5-mini",
    config={"provider_options": {"endpoint": "chat_completions"}},
    tools=["add_numbers"],
    hitl=True,
    auto_broadcast=False,
)
def hitl_demo_agent(spore):
    return {"status": "ready", "spore": spore.id}


if __name__ == "__main__":
    agent_obj = hitl_demo_agent._praval_agent

    print("Running HITL demo chat...")
    try:
        print(agent_obj.chat("Please add 2 and 3 using the tool."))
    except InterventionRequired as interruption:
        print(f"Intervention queued: {interruption.intervention_id}")
        hitl_demo_agent.approve_intervention(
            interruption.intervention_id,
            reviewer="demo-operator",
        )
        resumed = hitl_demo_agent.resume_run(interruption.run_id)
        print(f"Resumed response: {resumed}")
