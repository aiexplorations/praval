"""
Instrumentation manager.

Coordinates all instrumentation of Praval components.
"""
# mypy: ignore-errors

import logging
from typing import Any, Dict

from ..config import get_config

logger = logging.getLogger(__name__)

# Global flag to track if instrumentation is initialized
_instrumentation_initialized = False

# Storage for original functions to enable proper reset
_original_functions: Dict[str, Any] = {}


def initialize_instrumentation() -> bool:
    """Initialize automatic instrumentation of Praval framework.

    This should be called once when the observability module is imported.

    Returns:
        True if instrumentation was initialized, False if disabled or already
        initialized
    """
    global _instrumentation_initialized

    # Check if already initialized
    if _instrumentation_initialized:
        return True

    # Check if observability is enabled
    config = get_config()
    if not config.is_enabled():
        logger.debug("Observability disabled, skipping instrumentation")
        return False

    try:
        # Instrument components
        _instrument_agent_decorator()
        _instrument_reef_communication()
        _instrument_memory_operations()
        _instrument_storage_providers()
        _instrument_llm_providers()

        _instrumentation_initialized = True
        logger.info("Praval observability instrumentation initialized")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize instrumentation: {e}")
        return False


def _instrument_agent_decorator() -> None:
    """Instrument the @agent decorator to auto-trace agent execution."""
    try:
        from praval import decorators

        from ..tracing import SpanKind
        from .utils import instrument_function

        # Store original agent decorator if not already stored
        if "decorators.agent" not in _original_functions:
            _original_functions["decorators.agent"] = decorators.agent

        original_agent = _original_functions["decorators.agent"]

        def instrumented_agent(*args, **kwargs):
            """Wrapper that instruments the agent decorator."""
            # Call original decorator
            decorator_func = original_agent(*args, **kwargs)

            def wrapped_decorator(func):
                # Apply original decorator first
                decorated_func = decorator_func(func)

                # Get agent metadata
                agent_name = decorated_func._praval_name

                # Instrument the underlying agent's spore handler
                original_agent_obj = decorated_func._praval_agent
                original_handler = original_agent_obj.spore_handler

                # Create instrumented handler
                @instrument_function(
                    span_name=f"agent.{agent_name}.execute",
                    kind=SpanKind.SERVER,
                    extract_context_from_arg="spore",
                    inject_context_to_arg="spore",
                )
                def instrumented_handler(spore):
                    return original_handler(spore)

                # Replace handler with instrumented version
                # Avoid altering mocks used in tests
                if getattr(original_agent_obj, "_is_mock_object", False):
                    return decorated_func

                # Avoid double set_spore_handler() calls in decorator tests
                setattr(
                    original_agent_obj, "_custom_spore_handler", instrumented_handler
                )

                return decorated_func

            return wrapped_decorator

        # Replace the agent decorator
        decorators.agent = instrumented_agent
        logger.debug("Agent decorator instrumented successfully")

    except Exception as e:
        logger.warning(f"Failed to instrument agent decorator: {e}")


def _instrument_reef_communication() -> None:
    """Instrument Reef communication methods."""
    try:
        from praval.core import reef

        from ..tracing import SpanKind
        from .utils import instrument_function

        # Store original Reef.send if not already stored
        if "reef.Reef.send" not in _original_functions:
            _original_functions["reef.Reef.send"] = reef.Reef.send

        original_send = _original_functions["reef.Reef.send"]

        @instrument_function(span_name="reef.send", kind=SpanKind.PRODUCER)
        def instrumented_send(self, from_agent, to_agent, knowledge, **kwargs):
            return original_send(self, from_agent, to_agent, knowledge, **kwargs)

        reef.Reef.send = instrumented_send

        # Store original Reef.broadcast if not already stored
        if "reef.Reef.broadcast" not in _original_functions:
            _original_functions["reef.Reef.broadcast"] = reef.Reef.broadcast

        original_broadcast = _original_functions["reef.Reef.broadcast"]

        @instrument_function(span_name="reef.broadcast", kind=SpanKind.PRODUCER)
        def instrumented_broadcast(self, from_agent, knowledge, **kwargs):
            return original_broadcast(self, from_agent, knowledge, **kwargs)

        reef.Reef.broadcast = instrumented_broadcast

        logger.debug("Reef communication instrumented successfully")

    except Exception as e:
        logger.warning(f"Failed to instrument reef communication: {e}")


def _instrument_memory_operations() -> None:
    """Instrument memory manager operations."""
    try:
        from praval.memory import memory_manager

        from ..tracing import SpanKind
        from .utils import instrument_function

        # Store and instrument MemoryManager.store_conversation_turn
        if (
            "memory_manager.MemoryManager.store_conversation_turn"
            not in _original_functions
        ):
            _original_functions[
                "memory_manager.MemoryManager.store_conversation_turn"
            ] = memory_manager.MemoryManager.store_conversation_turn

        original_store = _original_functions[
            "memory_manager.MemoryManager.store_conversation_turn"
        ]

        @instrument_function(
            span_name="memory.store_conversation_turn", kind=SpanKind.INTERNAL
        )
        def instrumented_store(self, agent_id, user_message, agent_response, **kwargs):
            return original_store(
                self, agent_id, user_message, agent_response, **kwargs
            )

        memory_manager.MemoryManager.store_conversation_turn = instrumented_store

        # Instrument MemoryManager.store_memory
        try:
            if "memory_manager.MemoryManager.store_memory" not in _original_functions:
                _original_functions["memory_manager.MemoryManager.store_memory"] = (
                    memory_manager.MemoryManager.store_memory
                )

            original_store_mem = _original_functions[
                "memory_manager.MemoryManager.store_memory"
            ]

            @instrument_function(
                span_name="memory.store_memory", kind=SpanKind.INTERNAL
            )
            def instrumented_store_mem(
                self, agent_id, content, memory_type=None, **kwargs
            ):
                return original_store_mem(
                    self, agent_id, content, memory_type, **kwargs
                )

            memory_manager.MemoryManager.store_memory = instrumented_store_mem
        except AttributeError:
            pass  # Method doesn't exist

        # Instrument MemoryManager.retrieve_memory
        try:
            if (
                "memory_manager.MemoryManager.retrieve_memory"
                not in _original_functions
            ):
                _original_functions["memory_manager.MemoryManager.retrieve_memory"] = (
                    memory_manager.MemoryManager.retrieve_memory
                )

            original_retrieve = _original_functions[
                "memory_manager.MemoryManager.retrieve_memory"
            ]

            @instrument_function(
                span_name="memory.retrieve_memory", kind=SpanKind.INTERNAL
            )
            def instrumented_retrieve(self, memory_id):
                return original_retrieve(self, memory_id)

            memory_manager.MemoryManager.retrieve_memory = instrumented_retrieve
        except AttributeError:
            pass  # Method doesn't exist

        logger.debug("Memory operations instrumented successfully")

    except Exception as e:
        logger.warning(f"Failed to instrument memory operations: {e}")


def _instrument_storage_providers() -> None:
    """Instrument storage provider operations."""
    try:
        # Instrument EmbeddedVectorStore from the memory module
        from praval.memory.embedded_store import EmbeddedVectorStore as EmbeddedStore

        from ..tracing import SpanKind
        from .utils import instrument_function

        # Instrument EmbeddedStore.save
        try:
            if "EmbeddedStore.save" not in _original_functions:
                _original_functions["EmbeddedStore.save"] = EmbeddedStore.save

            original_save = _original_functions["EmbeddedStore.save"]

            @instrument_function(span_name="storage.save", kind=SpanKind.CLIENT)
            def instrumented_save(self, key, value):
                return original_save(self, key, value)

            EmbeddedStore.save = instrumented_save
        except AttributeError:
            pass

        # Instrument EmbeddedStore.load
        try:
            if "EmbeddedStore.load" not in _original_functions:
                _original_functions["EmbeddedStore.load"] = EmbeddedStore.load

            original_load = _original_functions["EmbeddedStore.load"]

            @instrument_function(span_name="storage.load", kind=SpanKind.CLIENT)
            def instrumented_load(self, key):
                return original_load(self, key)

            EmbeddedStore.load = instrumented_load
        except AttributeError:
            pass

        logger.debug("Storage providers instrumented successfully")

    except Exception as e:
        logger.warning(f"Failed to instrument storage providers: {e}")


def _instrument_llm_providers() -> None:
    """Instrument LLM provider calls."""
    try:
        from ..tracing import SpanKind
        from .utils import instrument_function

        # Instrument OpenAI provider
        try:
            from praval.providers.openai import OpenAIProvider

            original_openai_generate = OpenAIProvider.generate

            @instrument_function(
                span_name="llm.OpenAIProvider.generate", kind=SpanKind.CLIENT
            )
            def instrumented_generate_openai(
                self, messages, tools=None, *args, **kwargs
            ):
                return original_openai_generate(self, messages, tools, *args, **kwargs)

            OpenAIProvider.generate = instrumented_generate_openai
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not instrument OpenAI provider: {e}")

        # Instrument Anthropic provider
        try:
            from praval.providers.anthropic import AnthropicProvider

            original_anthropic_generate = AnthropicProvider.generate

            @instrument_function(
                span_name="llm.AnthropicProvider.generate", kind=SpanKind.CLIENT
            )
            def instrumented_generate_anthropic(
                self, messages, tools=None, *args, **kwargs
            ):
                return original_anthropic_generate(
                    self, messages, tools, *args, **kwargs
                )

            AnthropicProvider.generate = instrumented_generate_anthropic
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not instrument Anthropic provider: {e}")

        # Instrument Cohere provider
        try:
            from praval.providers.cohere import CohereProvider

            original_cohere_generate = CohereProvider.generate

            @instrument_function(
                span_name="llm.CohereProvider.generate", kind=SpanKind.CLIENT
            )
            def instrumented_generate_cohere(
                self, messages, tools=None, *args, **kwargs
            ):
                return original_cohere_generate(self, messages, tools, *args, **kwargs)

            CohereProvider.generate = instrumented_generate_cohere
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not instrument Cohere provider: {e}")

        logger.debug("LLM providers instrumented successfully")

    except Exception as e:
        logger.warning(f"Failed to instrument LLM providers: {e}")


def is_instrumented() -> bool:
    """Check if instrumentation is initialized.

    Returns:
        True if instrumentation is active
    """
    return _instrumentation_initialized


def reset_instrumentation() -> None:
    """Reset the instrumentation state and restore original functions.

    This is primarily used for testing to ensure test isolation.
    Restores all monkey-patched functions to their original implementations.
    """

    global _instrumentation_initialized

    # Restore original functions
    if "decorators.agent" in _original_functions:
        try:
            from praval import decorators

            decorators.agent = _original_functions["decorators.agent"]
        except ImportError:
            pass

    if "reef.Reef.send" in _original_functions:
        try:
            from praval.core import reef

            reef.Reef.send = _original_functions["reef.Reef.send"]
        except ImportError:
            pass

    if "reef.Reef.broadcast" in _original_functions:
        try:
            from praval.core import reef

            reef.Reef.broadcast = _original_functions["reef.Reef.broadcast"]
        except ImportError:
            pass

    if "memory_manager.MemoryManager.store_conversation_turn" in _original_functions:
        try:
            from praval.memory import memory_manager

            memory_manager.MemoryManager.store_conversation_turn = _original_functions[
                "memory_manager.MemoryManager.store_conversation_turn"
            ]
        except ImportError:
            pass

    if "memory_manager.MemoryManager.store_memory" in _original_functions:
        try:
            from praval.memory import memory_manager

            memory_manager.MemoryManager.store_memory = _original_functions[
                "memory_manager.MemoryManager.store_memory"
            ]
        except ImportError:
            pass

    if "memory_manager.MemoryManager.retrieve_memory" in _original_functions:
        try:
            from praval.memory import memory_manager

            memory_manager.MemoryManager.retrieve_memory = _original_functions[
                "memory_manager.MemoryManager.retrieve_memory"
            ]
        except ImportError:
            pass

    # Restore storage providers
    if "EmbeddedStore.save" in _original_functions:
        try:
            from praval.memory.embedded_store import (
                EmbeddedVectorStore as EmbeddedStore,
            )

            EmbeddedStore.save = _original_functions["EmbeddedStore.save"]
        except ImportError:
            pass

    if "EmbeddedStore.load" in _original_functions:
        try:
            from praval.memory.embedded_store import (
                EmbeddedVectorStore as EmbeddedStore,
            )

            EmbeddedStore.load = _original_functions["EmbeddedStore.load"]
        except ImportError:
            pass

    # Clear stored originals and reset flag
    _original_functions.clear()
    _instrumentation_initialized = False
    logger.debug("Instrumentation state reset and original functions restored")
