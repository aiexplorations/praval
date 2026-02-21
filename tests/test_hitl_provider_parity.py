"""HITL interruption/resume parity tests across providers."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import HITLConfigurationError, InterventionRequired
from praval.hitl.service import HITLService
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.openai import OpenAIProvider


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_openai_hitl_interruption_enabled(mock_openai_class, tmp_path: Path):
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    tool_call = Mock()
    tool_call.type = "function"
    tool_call.id = "call_1"
    tool_call.function.name = "add_numbers"
    tool_call.function.arguments = '{"x": 1, "y": 2}'

    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = None
    response.choices[0].message.tool_calls = [tool_call]
    mock_client.chat.completions.create.return_value = response

    provider = OpenAIProvider(AgentConfig())

    def add_numbers(x: int, y: int) -> int:
        return x + y

    tools = [
        {
            "function": add_numbers,
            "description": "Add numbers",
            "requires_approval": True,
            "risk_level": "high",
            "approval_reason": "operator approval required",
        }
    ]
    hitl_context = {
        "enabled": True,
        "run_id": "run-openai-1",
        "agent_name": "agent-openai",
        "provider_name": "openai",
        "db_path": str(tmp_path / "hitl.db"),
    }

    with pytest.raises(InterventionRequired):
        provider.generate([{"role": "user", "content": "add"}], tools, hitl_context)


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_openai_hitl_disabled_conflict_raises_config_error(
    mock_openai_class, tmp_path: Path
):
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    tool_call = Mock()
    tool_call.type = "function"
    tool_call.id = "call_1"
    tool_call.function.name = "dangerous"
    tool_call.function.arguments = "{}"

    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = None
    response.choices[0].message.tool_calls = [tool_call]
    mock_client.chat.completions.create.return_value = response

    provider = OpenAIProvider(AgentConfig())

    def dangerous() -> str:
        return "done"

    tools = [
        {
            "function": dangerous,
            "description": "Dangerous",
            "requires_approval": True,
        }
    ]
    hitl_context = {
        "enabled": False,
        "run_id": "run-openai-2",
        "agent_name": "agent-openai",
        "provider_name": "openai",
        "db_path": str(tmp_path / "hitl.db"),
    }

    with pytest.raises(HITLConfigurationError):
        provider.generate([{"role": "user", "content": "run"}], tools, hitl_context)


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_openai_hitl_resume_after_approval(mock_openai_class, tmp_path: Path):
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    tool_call = Mock()
    tool_call.type = "function"
    tool_call.id = "call_1"
    tool_call.function.name = "add_numbers"
    tool_call.function.arguments = '{"x": 2, "y": 3}'

    first = Mock()
    first.choices = [Mock()]
    first.choices[0].message.content = None
    first.choices[0].message.tool_calls = [tool_call]

    followup = Mock()
    followup.choices = [Mock()]
    followup.choices[0].message.content = "Result is 5"

    mock_client.chat.completions.create.return_value = first

    provider = OpenAIProvider(AgentConfig())

    def add_numbers(x: int, y: int) -> int:
        return x + y

    tools = [
        {
            "function": add_numbers,
            "description": "Add numbers",
            "requires_approval": True,
        }
    ]
    db_path = str(tmp_path / "hitl.db")
    hitl_context = {
        "enabled": True,
        "run_id": "run-openai-3",
        "agent_name": "agent-openai",
        "provider_name": "openai",
        "db_path": db_path,
    }

    with pytest.raises(InterventionRequired):
        provider.generate([{"role": "user", "content": "add"}], tools, hitl_context)

    service = HITLService(db_path=db_path)
    pending = service.get_pending_interventions(run_id="run-openai-3")
    assert len(pending) == 1
    approved = service.approve_intervention(pending[0].id, reviewer="qa")
    suspended = service.get_suspended_run("run-openai-3")
    assert suspended is not None

    mock_client.chat.completions.create.return_value = followup

    result = provider.resume_tool_flow(
        suspended.state,
        tools,
        {
            **hitl_context,
            "resume_intervention": approved.to_dict(),
        },
    )
    assert result == "Result is 5"


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_openai_hitl_resume_after_edit_uses_edited_args(
    mock_openai_class, tmp_path: Path
):
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    tool_call = Mock()
    tool_call.type = "function"
    tool_call.id = "call_edit_1"
    tool_call.function.name = "add_numbers"
    tool_call.function.arguments = '{"x": 2, "y": 3}'

    first = Mock()
    first.choices = [Mock()]
    first.choices[0].message.content = None
    first.choices[0].message.tool_calls = [tool_call]

    followup = Mock()
    followup.choices = [Mock()]
    followup.choices[0].message.content = "Edited path complete"

    mock_client.chat.completions.create.return_value = first

    provider = OpenAIProvider(AgentConfig())

    def add_numbers(x: int, y: int) -> int:
        return x + y

    tools = [
        {
            "function": add_numbers,
            "description": "Add numbers",
            "requires_approval": True,
        }
    ]
    db_path = str(tmp_path / "hitl_edit.db")
    hitl_context = {
        "enabled": True,
        "run_id": "run-openai-edit-1",
        "agent_name": "agent-openai",
        "provider_name": "openai",
        "db_path": db_path,
    }

    with pytest.raises(InterventionRequired):
        provider.generate([{"role": "user", "content": "add"}], tools, hitl_context)

    service = HITLService(db_path=db_path)
    pending = service.get_pending_interventions(run_id="run-openai-edit-1")
    assert len(pending) == 1
    edited = service.approve_intervention(
        pending[0].id, reviewer="qa", edited_args={"x": 10, "y": 7}
    )
    suspended = service.get_suspended_run("run-openai-edit-1")
    assert suspended is not None

    mock_client.chat.completions.create.return_value = followup

    result = provider.resume_tool_flow(
        suspended.state,
        tools,
        {
            **hitl_context,
            "resume_intervention": edited.to_dict(),
        },
    )
    assert result == "Edited path complete"

    last_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    tool_messages = [
        m for m in last_messages if isinstance(m, dict) and m.get("role") == "tool"
    ]
    assert tool_messages
    assert tool_messages[-1]["content"] == "17"


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_openai_hitl_resume_after_reject_returns_deterministic_message(
    mock_openai_class, tmp_path: Path
):
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    tool_call = Mock()
    tool_call.type = "function"
    tool_call.id = "call_reject_1"
    tool_call.function.name = "dangerous"
    tool_call.function.arguments = "{}"

    first = Mock()
    first.choices = [Mock()]
    first.choices[0].message.content = None
    first.choices[0].message.tool_calls = [tool_call]

    followup = Mock()
    followup.choices = [Mock()]
    followup.choices[0].message.content = "Reject path complete"

    mock_client.chat.completions.create.return_value = first

    provider = OpenAIProvider(AgentConfig())

    def dangerous() -> str:
        return "should-not-run"

    tools = [
        {
            "function": dangerous,
            "description": "Dangerous",
            "requires_approval": True,
        }
    ]
    db_path = str(tmp_path / "hitl_reject.db")
    hitl_context = {
        "enabled": True,
        "run_id": "run-openai-reject-1",
        "agent_name": "agent-openai",
        "provider_name": "openai",
        "db_path": db_path,
    }

    with pytest.raises(InterventionRequired):
        provider.generate([{"role": "user", "content": "run"}], tools, hitl_context)

    service = HITLService(db_path=db_path)
    pending = service.get_pending_interventions(run_id="run-openai-reject-1")
    assert len(pending) == 1
    rejected = service.reject_intervention(
        pending[0].id, reviewer="qa", reason="unsafe in production"
    )
    suspended = service.get_suspended_run("run-openai-reject-1")
    assert suspended is not None

    mock_client.chat.completions.create.return_value = followup

    result = provider.resume_tool_flow(
        suspended.state,
        tools,
        {
            **hitl_context,
            "resume_intervention": rejected.to_dict(),
        },
    )
    assert result == "Reject path complete"

    last_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    tool_messages = [
        m for m in last_messages if isinstance(m, dict) and m.get("role") == "tool"
    ]
    assert tool_messages
    assert (
        "Rejected by human reviewer: unsafe in production"
        in tool_messages[-1]["content"]
    )


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
@patch("anthropic.Anthropic")
def test_anthropic_hitl_interruption_enabled(mock_anthropic_class, tmp_path: Path):
    mock_client = Mock()
    mock_anthropic_class.return_value = mock_client

    tool_use = Mock()
    tool_use.type = "tool_use"
    tool_use.id = "tool_1"
    tool_use.name = "echo"
    tool_use.input = {"text": "hello"}

    first_response = Mock()
    first_response.content = [tool_use]
    mock_client.messages.create.return_value = first_response

    provider = AnthropicProvider(AgentConfig())

    def echo(text: str) -> str:
        return text

    tools = [
        {
            "function": echo,
            "description": "Echo",
            "requires_approval": True,
        }
    ]
    hitl_context = {
        "enabled": True,
        "run_id": "run-anthropic-1",
        "agent_name": "agent-anthropic",
        "provider_name": "anthropic",
        "db_path": str(tmp_path / "hitl.db"),
    }

    with pytest.raises(InterventionRequired):
        provider.generate([{"role": "user", "content": "echo"}], tools, hitl_context)


@patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
@patch("cohere.Client")
def test_cohere_hitl_interruption_enabled(mock_cohere_class, tmp_path: Path):
    mock_client = Mock()
    mock_cohere_class.return_value = mock_client

    first_response = Mock()
    first_response.tool_calls = [{"name": "echo", "args": {"text": "hello"}}]
    mock_client.chat.return_value = first_response

    provider = CohereProvider(AgentConfig())

    def echo(text: str) -> str:
        return text

    tools = [
        {
            "function": echo,
            "description": "Echo",
            "requires_approval": True,
        }
    ]
    hitl_context = {
        "enabled": True,
        "run_id": "run-cohere-1",
        "agent_name": "agent-cohere",
        "provider_name": "cohere",
        "db_path": str(tmp_path / "hitl.db"),
    }

    with pytest.raises(InterventionRequired):
        provider.generate([{"role": "user", "content": "echo"}], tools, hitl_context)
