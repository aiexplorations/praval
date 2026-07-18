import builtins
import logging


def test_initialize_instrumentation_disabled(monkeypatch):
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "off")
    from praval.observability.config import reset_config

    reset_config()

    from praval.observability.instrumentation.manager import (
        initialize_instrumentation,
        reset_instrumentation,
    )

    reset_instrumentation()
    assert initialize_instrumentation() is False


def test_initialize_and_reset_instrumentation(monkeypatch):
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "on")
    from praval.observability.config import reset_config

    reset_config()

    from praval.observability.instrumentation import manager

    manager.reset_instrumentation()

    from praval import decorators

    original = decorators.agent

    from praval.core.reef import Reef
    from praval.providers.openai import OpenAIProvider

    original_send = Reef.send
    original_generate = OpenAIProvider.generate

    assert manager.initialize_instrumentation() is True
    assert decorators.agent is not original
    initialized_agent = decorators.agent
    initialized_send = Reef.send
    initialized_generate = OpenAIProvider.generate

    assert manager.initialize_instrumentation() is True
    assert decorators.agent is initialized_agent
    assert Reef.send is initialized_send
    assert OpenAIProvider.generate is initialized_generate

    manager.reset_instrumentation()
    assert decorators.agent is original
    assert Reef.send is original_send
    assert OpenAIProvider.generate is original_generate

    manager.reset_instrumentation()
    assert decorators.agent is original
    assert Reef.send is original_send
    assert OpenAIProvider.generate is original_generate


def test_instrumented_component_wrappers_delegate_consistently(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "on")
    monkeypatch.setenv("PRAVAL_TRACES_PATH", str(tmp_path / "traces.db"))

    from praval.memory.embedded_store import EmbeddedVectorStore
    from praval.memory.memory_manager import MemoryManager
    from praval.observability.config import reset_config
    from praval.observability.instrumentation import manager
    from praval.observability.storage.sqlite_store import reset_trace_store
    from praval.providers.anthropic import AnthropicProvider
    from praval.providers.cohere import CohereProvider
    from praval.providers.gemini import GeminiProvider
    from praval.providers.openai import OpenAIProvider

    reset_config()
    reset_trace_store()
    manager.reset_instrumentation()
    calls = []

    monkeypatch.setattr(
        MemoryManager,
        "store_conversation_turn",
        lambda self, agent_id, user, response, **kwargs: calls.append(
            ("conversation", agent_id, user, response, kwargs)
        ),
    )
    monkeypatch.setattr(
        MemoryManager,
        "store_memory",
        lambda self, agent_id, content, memory_type=None, **kwargs: calls.append(
            ("store_memory", agent_id, content, memory_type, kwargs)
        ),
    )
    monkeypatch.setattr(
        MemoryManager,
        "retrieve_memory",
        lambda self, memory_id: calls.append(("retrieve", memory_id)),
    )
    monkeypatch.setattr(
        EmbeddedVectorStore,
        "save",
        lambda self, key, value: calls.append(("save", key, value)),
        raising=False,
    )
    monkeypatch.setattr(
        EmbeddedVectorStore,
        "load",
        lambda self, key: calls.append(("load", key)),
        raising=False,
    )

    for provider_class in (
        OpenAIProvider,
        AnthropicProvider,
        CohereProvider,
        GeminiProvider,
    ):
        monkeypatch.setattr(
            provider_class,
            "generate",
            lambda self, messages, tools=None, *args, **kwargs: calls.append(
                ("generate", messages, tools, args, kwargs)
            ),
        )

    assert manager.initialize_instrumentation() is True
    MemoryManager.store_conversation_turn(None, "a", "u", "r", source="test")
    MemoryManager.store_memory(None, "a", "content", "semantic", score=1)
    MemoryManager.retrieve_memory(None, "memory-1")
    EmbeddedVectorStore.save(None, "key", "value")
    EmbeddedVectorStore.load(None, "key")
    for provider_class in (
        OpenAIProvider,
        AnthropicProvider,
        CohereProvider,
        GeminiProvider,
    ):
        provider_class.generate(None, [{"role": "user"}], [], "extra", flag=True)

    assert {call[0] for call in calls} == {
        "conversation",
        "store_memory",
        "retrieve",
        "save",
        "load",
        "generate",
    }
    assert sum(call[0] == "generate" for call in calls) == 4
    manager.reset_instrumentation()


def test_initialize_failure_resets_partial_state(monkeypatch):
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "on")
    from praval.observability.config import reset_config
    from praval.observability.instrumentation import manager

    reset_config()
    manager.reset_instrumentation()
    monkeypatch.setattr(
        manager,
        "_instrument_agent_decorator",
        lambda: (_ for _ in ()).throw(RuntimeError("instrumentation failed")),
    )

    assert manager.initialize_instrumentation() is False
    assert manager.is_instrumented() is False


def test_optional_instrumentation_dependencies_are_debug_only(monkeypatch, caplog):
    from praval.observability.instrumentation import manager

    original_import = builtins.__import__

    def without_optional_memory(name, *args, **kwargs):
        if name in {"praval.memory", "praval.memory.embedded_store"}:
            raise ImportError("optional memory dependency unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_optional_memory)
    with caplog.at_level(logging.DEBUG):
        manager._instrument_memory_operations()
        manager._instrument_storage_providers()

    assert "dependency unavailable" in caplog.text
    assert not [
        record for record in caplog.records if record.levelno >= logging.WARNING
    ]
