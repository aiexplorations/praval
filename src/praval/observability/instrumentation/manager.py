"""
Instrumentation manager.

Coordinates all instrumentation of Praval components.
"""

import logging
from typing import Optional

from ..config import get_config

logger = logging.getLogger(__name__)

# Global flag to track if instrumentation is initialized
_instrumentation_initialized = False


def initialize_instrumentation() -> bool:
    """Initialize automatic instrumentation of Praval framework.

    This should be called once when the observability module is imported.

    Returns:
        True if instrumentation was initialized, False if disabled or already initialized
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
        from .utils import instrument_function
        from ..tracing import SpanKind

        # Store original agent_handler creation
        original_agent = decorators.agent

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
                    inject_context_to_arg="spore"
                )
                def instrumented_handler(spore):
                    return original_handler(spore)

                # Replace handler with instrumented version
                original_agent_obj.set_spore_handler(instrumented_handler)

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
        from .utils import instrument_function
        from ..tracing import SpanKind

        # Instrument Reef.send
        original_send = reef.Reef.send

        @instrument_function(
            span_name="reef.send",
            kind=SpanKind.PRODUCER
        )
        def instrumented_send(self, from_agent, to_agent, knowledge, **kwargs):
            return original_send(self, from_agent, to_agent, knowledge, **kwargs)

        reef.Reef.send = instrumented_send

        # Instrument Reef.broadcast
        original_broadcast = reef.Reef.broadcast

        @instrument_function(
            span_name="reef.broadcast",
            kind=SpanKind.PRODUCER
        )
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
        from .utils import instrument_function
        from ..tracing import SpanKind

        # Instrument MemoryManager.store_conversation_turn
        original_store = memory_manager.MemoryManager.store_conversation_turn

        @instrument_function(
            span_name="memory.store_conversation_turn",
            kind=SpanKind.INTERNAL
        )
        def instrumented_store(self, agent_id, user_message, agent_response, **kwargs):
            return original_store(self, agent_id, user_message, agent_response, **kwargs)

        memory_manager.MemoryManager.store_conversation_turn = instrumented_store

        # Instrument MemoryManager.store_memory
        try:
            original_store_mem = memory_manager.MemoryManager.store_memory

            @instrument_function(
                span_name="memory.store_memory",
                kind=SpanKind.INTERNAL
            )
            def instrumented_store_mem(self, content, memory_type, **kwargs):
                return original_store_mem(self, content, memory_type, **kwargs)

            memory_manager.MemoryManager.store_memory = instrumented_store_mem
        except AttributeError:
            pass  # Method doesn't exist

        # Instrument MemoryManager.retrieve_memory
        try:
            original_retrieve = memory_manager.MemoryManager.retrieve_memory

            @instrument_function(
                span_name="memory.retrieve_memory",
                kind=SpanKind.INTERNAL
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
        # Instrument the simpler EmbeddedStore instead of BaseStorageProvider
        from praval.storage.embedded_store import EmbeddedStore
        from .utils import instrument_function
        from ..tracing import SpanKind

        # Instrument EmbeddedStore.save
        try:
            original_save = EmbeddedStore.save

            @instrument_function(
                span_name="storage.save",
                kind=SpanKind.CLIENT
            )
            def instrumented_save(self, key, value):
                return original_save(self, key, value)

            EmbeddedStore.save = instrumented_save
        except AttributeError:
            pass

        # Instrument EmbeddedStore.load
        try:
            original_load = EmbeddedStore.load

            @instrument_function(
                span_name="storage.load",
                kind=SpanKind.CLIENT
            )
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
        from .utils import instrument_function
        from ..tracing import SpanKind

        # Instrument OpenAI provider
        try:
            from praval.providers.openai import OpenAIProvider

            original_generate = OpenAIProvider.generate

            @instrument_function(
                span_name="llm.OpenAIProvider.generate",
                kind=SpanKind.CLIENT
            )
            def instrumented_generate(self, messages, tools=None):
                return original_generate(self, messages, tools)

            OpenAIProvider.generate = instrumented_generate
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not instrument OpenAI provider: {e}")

        # Instrument Anthropic provider
        try:
            from praval.providers.anthropic import AnthropicProvider

            original_generate = AnthropicProvider.generate

            @instrument_function(
                span_name="llm.AnthropicProvider.generate",
                kind=SpanKind.CLIENT
            )
            def instrumented_generate_anthropic(self, messages, tools=None):
                return original_generate(self, messages, tools)

            AnthropicProvider.generate = instrumented_generate_anthropic
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not instrument Anthropic provider: {e}")

        # Instrument Cohere provider
        try:
            from praval.providers.cohere import CohereProvider

            original_generate = CohereProvider.generate

            @instrument_function(
                span_name="llm.CohereProvider.generate",
                kind=SpanKind.CLIENT
            )
            def instrumented_generate_cohere(self, messages, tools=None):
                return original_generate(self, messages, tools)

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
