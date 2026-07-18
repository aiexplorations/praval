"""Public Agent edge cases for the 0.8 runtime surface."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from praval.core.agent import Agent, AgentConfig
from praval.core.exceptions import PravalError, ProviderError, ToolError
from praval.models import AudioResponse, ModelEvent, ModelResponse


def _agent(provider=None, **kwargs):
    provider = provider or Mock()
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        return Agent(
            "edge-agent",
            provider="fake",
            model="fake-model",
            **kwargs,
        )


def test_agent_config_rejects_invalid_output_tokens_and_retries():
    with pytest.raises(ValueError, match="max_output_tokens"):
        AgentConfig(max_output_tokens=0)
    with pytest.raises(ValueError, match="retries"):
        AgentConfig(retries=-1)


def test_agent_history_trimming_handles_unbounded_zero_and_limit():
    agent = _agent(max_history=None)
    agent.conversation_history = [{"role": "user", "content": str(i)} for i in range(3)]
    agent._trim_history()
    assert len(agent.conversation_history) == 3

    agent.max_history = 0
    agent._trim_history()
    assert agent.conversation_history == []

    agent.max_history = 2
    agent.conversation_history = [{"content": str(i)} for i in range(4)]
    agent._trim_history()
    assert agent.conversation_history == [{"content": "2"}, {"content": "3"}]


def test_agent_provider_detection_environment_and_compact_model(monkeypatch):
    agent = _agent()
    agent.config.provider = None
    agent.config.model = "gemini:gemini-test"
    assert agent._detect_provider() == "gemini"
    assert agent.config.model == "gemini-test"

    agent.config.provider = None
    agent.config.model = None
    monkeypatch.setenv("PRAVAL_DEFAULT_PROVIDER", "local")
    assert agent._detect_provider() == "local"
    monkeypatch.delenv("PRAVAL_DEFAULT_PROVIDER")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert agent._detect_provider() == "anthropic"


def test_agent_chat_and_generate_wrap_runtime_errors_and_validate_empty():
    agent = _agent()
    with pytest.raises(ValueError, match="empty"):
        agent.chat("")
    with pytest.raises(ValueError, match="empty"):
        agent.generate(None)

    agent.runtime.generate_text = Mock(side_effect=RuntimeError("chat failed"))
    with pytest.raises(PravalError, match="chat failed"):
        agent.chat("hello")
    agent.runtime.invoke = Mock(side_effect=RuntimeError("generate failed"))
    with pytest.raises(PravalError, match="generate failed"):
        agent.generate("hello")


def test_agent_voice_delegation_accepts_legacy_and_neutral_responses():
    provider = Mock()
    agent = _agent(provider)
    provider.transcribe.return_value = "legacy text"
    assert agent.transcribe(b"audio") == "legacy text"
    provider.transcribe.return_value = AudioResponse(text="neutral text")
    assert agent.transcribe(b"audio") == "neutral text"
    provider.transcribe.return_value = AudioResponse()
    with pytest.raises(ProviderError, match="no transcription"):
        agent.transcribe(b"audio")
    provider.transcribe.return_value = object()
    with pytest.raises(ProviderError, match="invalid transcription"):
        agent.transcribe(b"audio")

    provider.speak.return_value = b"legacy audio"
    assert agent.speak("hello") == b"legacy audio"
    provider.speak.return_value = AudioResponse(data=b"neutral audio")
    assert agent.speak("hello") == b"neutral audio"
    provider.speak.return_value = AudioResponse()
    with pytest.raises(ProviderError, match="no synthesized"):
        agent.speak("hello")
    provider.speak.return_value = object()
    with pytest.raises(ProviderError, match="invalid speech"):
        agent.speak("hello")
    with pytest.raises(ValueError, match="empty"):
        agent.speak("  ")


def test_agent_voice_reports_unsupported_provider():
    class BasicProvider:
        pass

    agent = _agent(BasicProvider())
    with pytest.raises(ProviderError, match="does not support audio transcription"):
        agent.transcribe(b"audio")
    with pytest.raises(ProviderError, match="does not support speech generation"):
        agent.speak("hello")


@pytest.mark.asyncio
async def test_agent_async_generate_forwards_and_persists_response():
    agent = _agent(persist_state=True)
    agent.runtime.ainvoke = AsyncMock(return_value=ModelResponse(content="async"))
    agent._save_state = Mock()
    with pytest.raises(ValueError, match="empty"):
        await agent.agenerate("")

    response = await agent.agenerate("hello", provider_options={"seed": 7}, timeout=2)
    assert response.content == "async"
    assert agent.conversation_history[-1]["content"] == "async"
    assert agent.runtime.ainvoke.call_args.kwargs["provider_options"] == {"seed": 7}
    agent._save_state.assert_called_once()


def test_agent_stream_and_astream_validate_empty():
    agent = _agent()
    with pytest.raises(ValueError, match="empty"):
        agent.stream("")

    async def consume():
        generator = agent.astream("")
        await generator.__anext__()

    with pytest.raises(ValueError, match="empty"):
        import asyncio

        asyncio.run(consume())


def test_agent_configure_hitl_resets_cached_service():
    agent = _agent()
    agent._hitl_service = Mock()
    agent.configure_hitl(enabled=True, db_path="/tmp/agent-edge-hitl.db")
    assert agent._hitl_enabled is True
    assert agent._hitl_db_path == "/tmp/agent-edge-hitl.db"
    assert agent._hitl_service is None


def test_agent_intervention_ownership_and_missing_errors():
    agent = _agent()
    service = Mock()
    agent._hitl_service = service
    service.get_intervention.return_value = None
    with pytest.raises(ValueError, match="not found"):
        agent.approve_intervention("missing")
    with pytest.raises(ValueError, match="not found"):
        agent.reject_intervention("missing", reason="no")

    service.get_intervention.return_value = SimpleNamespace(agent_name="other")
    with pytest.raises(ValueError, match="does not belong"):
        agent.approve_intervention("wrong")
    with pytest.raises(ValueError, match="does not belong"):
        agent.reject_intervention("wrong", reason="no")


@pytest.mark.parametrize(
    ("suspended", "intervention", "message"),
    [
        (None, None, "not found"),
        (
            SimpleNamespace(agent_name="other", status="pending", state={}),
            None,
            "belongs",
        ),
        (
            SimpleNamespace(agent_name="edge-agent", status="completed", state={}),
            None,
            "not pending",
        ),
        (
            SimpleNamespace(agent_name="edge-agent", status="pending", state={}),
            None,
            "no linked intervention",
        ),
        (
            SimpleNamespace(
                agent_name="edge-agent",
                status="pending",
                state={"intervention_id": "missing"},
            ),
            None,
            "linked to run",
        ),
        (
            SimpleNamespace(
                agent_name="edge-agent",
                status="pending",
                state={"intervention_id": "pending"},
            ),
            SimpleNamespace(status=SimpleNamespace(value="PENDING")),
            "still pending",
        ),
    ],
)
def test_agent_resume_run_validation_errors(suspended, intervention, message):
    agent = _agent()
    service = Mock()
    agent._hitl_service = service
    service.get_suspended_run.return_value = suspended
    service.get_intervention.return_value = intervention
    with pytest.raises(ValueError, match=message):
        agent.resume_run("run")


def test_agent_tool_requires_complete_type_hints():
    agent = _agent()

    def missing_parameter(value):
        return value

    with pytest.raises(ValueError, match="type hints"):
        agent.tool(missing_parameter)

    def missing_return(value: str):
        return value

    with pytest.raises(ValueError, match="return type"):
        agent.tool(missing_return)


@pytest.mark.parametrize(
    ("key", "provider"),
    [
        ("OPENAI_API_KEY", "openai"),
        ("COHERE_API_KEY", "cohere"),
    ],
)
def test_agent_provider_detection_remaining_credentials(monkeypatch, key, provider):
    agent = _agent()
    agent.config.provider = None
    agent.config.model = None
    for env_name in (
        "PRAVAL_DEFAULT_MODEL",
        "PRAVAL_DEFAULT_PROVIDER",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "COHERE_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(key, "test-key")
    assert agent._detect_provider() == provider

    monkeypatch.delenv(key)
    with pytest.raises(ProviderError, match="No LLM provider credentials"):
        agent._detect_provider()


def test_agent_default_model_resolution_uses_environment_and_tolerates_registry_error(
    monkeypatch,
):
    agent = _agent()
    agent.config.model = None
    monkeypatch.setenv("PRAVAL_DEFAULT_MODEL", "environment-model")
    agent._resolve_default_model()
    assert agent.config.model == "environment-model"

    monkeypatch.delenv("PRAVAL_DEFAULT_MODEL")
    agent.config.model = None
    with patch(
        "praval.core.agent.get_provider_registry",
        side_effect=RuntimeError("registry unavailable"),
    ):
        agent._resolve_default_model()
    assert agent.config.model is None


@pytest.mark.asyncio
async def test_agent_astream_forwards_runtime_events():
    agent = _agent()

    async def events(**kwargs):
        assert kwargs["metadata"] == {"request": "stream"}
        yield ModelEvent(type="text_delta", delta="hello")

    agent.runtime.astream = events
    received = [
        event async for event in agent.astream("hello", metadata={"request": "stream"})
    ]
    assert received[0].delta == "hello"


def test_agent_tool_registry_collision_and_registration_failures():
    agent = _agent()

    def calculate(value: int) -> int:
        return value

    registry = Mock()
    registry.get_tool.return_value = SimpleNamespace(func=calculate)
    with patch("praval.core.agent.get_tool_registry", return_value=registry):
        assert agent.tool(calculate) is calculate
    registry.register_tool.assert_not_called()

    registry.get_tool.return_value = SimpleNamespace(func=lambda: None)
    with patch("praval.core.agent.get_tool_registry", return_value=registry):
        assert agent.tool(calculate) is calculate

    for error in (ToolError("duplicate"), RuntimeError("broken registry")):
        registry.get_tool.side_effect = error
        with patch("praval.core.agent.get_tool_registry", return_value=registry):
            assert agent.tool(calculate) is calculate


def test_agent_memory_helpers_cover_success_failure_and_disabled_paths():
    agent = _agent()
    assert agent.remember("nothing") is None
    assert agent.recall("nothing") == []
    assert agent.recall_by_id("missing") == []
    assert agent.get_conversation_context() == []
    assert agent.create_knowledge_reference("nothing") == []

    memory = Mock()
    memory.store_memory.return_value = "memory-1"
    memory.search_memories.return_value = SimpleNamespace(entries=["entry"])
    memory.recall_by_id.return_value = ["by-id"]
    memory.get_conversation_context.return_value = ["context"]
    memory.get_knowledge_references.return_value = ["ref-1"]
    agent.memory = memory

    assert agent.remember("remember me", memory_type="unknown") == "memory-1"
    assert agent.recall("remember me") == ["entry"]
    assert agent.recall_by_id("memory-1") == ["by-id"]
    assert agent.get_conversation_context(3) == ["context"]
    assert agent.create_knowledge_reference("large") == ["ref-1"]

    memory.store_memory.side_effect = RuntimeError("store failed")
    memory.search_memories.side_effect = RuntimeError("search failed")
    memory.get_knowledge_references.side_effect = RuntimeError("refs failed")
    assert agent.remember("failure") is None
    assert agent.recall("failure") == []
    assert agent.create_knowledge_reference("failure") == []


def test_agent_resolves_and_sends_lightweight_knowledge_with_fallback():
    agent = _agent()
    spore = SimpleNamespace(knowledge={"summary": "direct"})
    assert agent.resolve_spore_knowledge(spore) == spore.knowledge

    agent.memory = Mock()
    reef = Mock()
    reef.resolve_knowledge_references.return_value = {"resolved": True}
    reef.create_knowledge_reference_spore.return_value = "spore-ref"
    with patch("praval.core.reef.get_reef", return_value=reef):
        assert agent.resolve_spore_knowledge(spore) == {"resolved": True}
        agent.create_knowledge_reference = Mock(return_value=["ref-1"])
        assert (
            agent.send_lightweight_knowledge("other", "large", "summary") == "spore-ref"
        )

    with patch("praval.core.reef.get_reef", side_effect=RuntimeError("reef failed")):
        assert agent.resolve_spore_knowledge(spore) == spore.knowledge

    agent.create_knowledge_reference = Mock(return_value=[])
    agent.send_knowledge = Mock(return_value="direct-spore")
    assert (
        agent.send_lightweight_knowledge("other", "large", "summary") == "direct-spore"
    )


def test_agent_request_knowledge_receives_response_and_cleans_handler():
    from praval.core.reef import SporeType

    agent = _agent()
    reef = Mock()
    channel = SimpleNamespace(subscribers={agent.name: []})
    reef.default_channel = "main"
    reef.get_channel.return_value = channel

    def subscribe(_name, handler, replace=False):
        channel.subscribers[agent.name].append(handler)
        handler(
            SimpleNamespace(
                spore_type=SporeType.RESPONSE,
                to_agent=agent.name,
                from_agent="source",
                knowledge={"answer": 42},
            )
        )

    reef.subscribe.side_effect = subscribe
    with patch("praval.core.reef.get_reef", return_value=reef):
        result = agent.request_knowledge("source", {"question": "life"}, 1)
    assert result == {"answer": 42}
    assert channel.subscribers[agent.name] == []


def test_agent_close_tolerates_cleanup_errors_and_is_idempotent():
    provider = Mock()
    provider.close.side_effect = RuntimeError("close failed")
    agent = _agent(provider)
    agent._subscribed_channels = ["broken", "ok"]
    agent.conversation_history = [{"role": "user", "content": "hello"}]
    agent.memory = Mock()
    agent.memory.shutdown.side_effect = RuntimeError("memory failed")
    channel = Mock()
    channel.unsubscribe.side_effect = RuntimeError("unsubscribe failed")
    reef = Mock()
    reef.get_channel.side_effect = [channel, None]

    with patch("praval.core.reef.get_reef", return_value=reef):
        agent.close()
        agent.close()

    assert agent.is_closed is True
    assert agent.memory is None
    assert agent.conversation_history == []
    provider.close.assert_called_once()


def test_agent_resume_requires_provider_support_for_legacy_state():
    agent = _agent(provider=object())
    service = Mock()
    agent._hitl_service = service
    intervention = SimpleNamespace(
        status=SimpleNamespace(value="APPROVED"),
        to_dict=Mock(return_value={"decision": "APPROVE"}),
    )
    service.get_suspended_run.return_value = SimpleNamespace(
        agent_name=agent.name,
        status="pending",
        state={"intervention_id": "intervention-1", "schema": "legacy"},
    )
    service.get_intervention.return_value = intervention
    with pytest.raises(PravalError, match="does not support HITL resume"):
        agent.resume_run("run-1")


def test_agent_resume_persists_and_records_observability_event():
    provider = Mock()
    provider.resume_tool_flow.return_value = "resumed"
    agent = _agent(provider=provider)
    agent.persist_state = True
    agent._save_state = Mock()
    service = Mock()
    agent._hitl_service = service
    intervention = SimpleNamespace(
        status=SimpleNamespace(value="APPROVED"),
        to_dict=Mock(return_value={"decision": "APPROVE"}),
    )
    service.get_suspended_run.return_value = SimpleNamespace(
        agent_name=agent.name,
        status="pending",
        state={"intervention_id": "intervention-1", "schema": "legacy"},
    )
    service.get_intervention.return_value = intervention
    span = Mock()
    with patch("praval.observability.tracing.get_current_span", return_value=span):
        assert agent.resume_run("run-1") == "resumed"
    agent._save_state.assert_called_once()
    service.mark_run_completed.assert_called_once_with("run-1", "resumed")
    span.add_event.assert_called_once()


def test_agent_spore_handler_runs_async_callback_without_active_loop():
    agent = _agent()
    callback = AsyncMock()
    agent.set_spore_handler(callback)
    spore = Mock()
    agent.on_spore_received(spore)
    callback.assert_awaited_once_with(spore)
