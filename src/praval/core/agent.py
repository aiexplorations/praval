"""
Core Agent class for the Praval framework.

The Agent class provides a simple, composable interface for LLM-based
conversations with support for multiple providers, tools, and state persistence.
"""

import asyncio
import inspect
import json
import logging
import os
import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..model_runtime import ModelRuntime
from ..models import (
    AudioResponse,
    ReasoningConfig,
    SpeechRequest,
    ToolSpec,
    TranscriptionRequest,
)
from ..models.observation import ContentKind, ObservationKind
from ..providers.factory import ProviderFactory
from ..providers.registry import get_provider_registry
from ..runtime_observation import (
    ObservationScope,
    record_content_reference,
    record_model_facts,
)
from .exceptions import (
    PravalError,
    ProviderError,
    ToolError,
)
from .storage import StateStorage
from .tool_registry import Tool, ToolMetadata, get_tool_registry

# Auto-load .env files if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    pass

logger = logging.getLogger(__name__)

# Options forwarded unchanged to every ModelRuntime entry point.
_RUNTIME_OPTION_NAMES: Tuple[str, ...] = (
    "response_schema",
    "reasoning",
    "provider_options",
    "timeout",
    "metadata",
    "stream_options",
    "max_tool_rounds",
)
# Options applied by the agent itself before the runtime is called.
_CALL_CONTROL_NAMES: Tuple[str, ...] = (
    "allowed_tool_names",
    "additional_system_message",
)
# Options that only some runtime entry points accept.
_ENTRY_POINT_OPTION_NAMES: Dict[str, Tuple[str, ...]] = {
    "chat": ("stream",),
    "generate": ("stream",),
}


class _CallToken:
    """Commit guard for one agent call whose caller may stop waiting.

    The caller cancels the token when it gives up (for example on a timeout).
    The agent commits the answer to history only through ``try_commit``, so a
    cancelled call never writes its late answer.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = "pending"

    def cancel(self) -> bool:
        """Abandon the call; return False if its answer is already committed."""
        with self._lock:
            if self._state == "committed":
                return False
            self._state = "cancelled"
            return True

    def try_commit(self, commit: Callable[[], None]) -> bool:
        """Run ``commit`` unless the call was cancelled; return whether it ran."""
        with self._lock:
            if self._state == "cancelled":
                return False
            commit()
            self._state = "committed"
            return True


# Set by decorator chat()/achat() in the worker's copied context. The first
# Agent.chat()/generate() running in that context consumes it.
_CALL_TOKEN: ContextVar[Optional[_CallToken]] = ContextVar(
    "praval_agent_call_token", default=None
)


@dataclass(frozen=True)
class _RuntimeCallOptions:
    """Per-call options resolved once and applied the same way everywhere."""

    tools: Optional[List[Dict[str, Any]]]
    additional_system_message: Optional[str]
    runtime_kwargs: Dict[str, Any] = field(default_factory=dict)

    def request_messages(
        self, history: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return the messages to send; the extra system message is not stored."""
        messages = list(history)
        if self.additional_system_message:
            messages.insert(
                0, {"role": "system", "content": self.additional_system_message}
            )
        return messages


@dataclass
class AgentConfig:
    """Configuration for Agent behavior and LLM parameters."""

    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    max_output_tokens: Optional[int] = None
    system_message: Optional[str] = None
    timeout: Optional[float] = None
    retries: int = 2
    max_tool_rounds: int = 8
    stream: bool = False
    response_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None
    store: bool = False
    cache: Optional[Dict[str, Any]] = None
    strict_tools: bool = False
    provider_options: Optional[Dict[str, Any]] = None
    stream_options: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.model and ":" in self.model and not self.provider:
            provider, model = self.model.split(":", 1)
            self.provider = provider
            self.model = model
        if not (0 <= self.temperature <= 2):
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.max_output_tokens is None:
            self.max_output_tokens = self.max_tokens
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if self.retries < 0:
            raise ValueError("retries must be non-negative")
        if self.max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        if self.max_tool_rounds > 1000:
            raise ValueError("max_tool_rounds must not exceed 1000")
        if self.provider_options is None:
            self.provider_options = {}
        if self.stream_options is None:
            self.stream_options = {}


class Agent:
    """
    A simple, composable LLM agent.

    The Agent class provides the core functionality for LLM-based conversations
    with support for multiple providers, conversation history, tools, and
    state persistence.

    Examples:
        Basic usage:
        >>> agent = Agent("assistant")
        >>> response = agent.chat("Hello!")

        With persistence:
        >>> agent = Agent("my_agent", persist_state=True)
        >>> agent.chat("Remember this conversation")

        With tools:
        >>> agent = Agent("calculator")
        >>> @agent.tool
        >>> def add(x: int, y: int) -> int:
        ...     return x + y
    """

    def __init__(
        self,
        name: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        persist_state: bool = False,
        system_message: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        memory_enabled: bool = False,
        memory_config: Optional[Dict[str, Any]] = None,
        knowledge_base: Optional[str] = None,
        max_history: Optional[int] = 100,
        hitl_enabled: bool = False,
        hitl_db_path: Optional[str] = None,
        reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None,
    ):
        """
        Initialize a new Agent.

        Args:
            name: Unique identifier for this agent
            provider: LLM provider to use (openai, anthropic, cohere)
            persist_state: Whether to persist conversation state
            system_message: System message to set agent behavior
            config: Additional configuration parameters
            reasoning: Portable level or provider-specific reasoning controls
            memory_enabled: Whether to enable vector memory capabilities
            memory_config: Configuration for memory system
            knowledge_base: Path to knowledge base files to auto-index
            max_history: Max non-system messages to retain, trimmed in whole
                user-turn units; the newest unit is always kept (None for
                unbounded)

        Raises:
            ValueError: If name is empty or configuration is invalid
            ProviderError: If provider setup fails
        """
        if not name:
            raise ValueError("Agent name cannot be empty")

        self.name = name
        self.persist_state = persist_state
        self.memory_enabled = memory_enabled
        self.knowledge_base = knowledge_base
        self.tools: Dict[str, Dict[str, Any]] = {}
        # Functions this agent added to the global tool registry, by name, so
        # close() can remove exactly those entries.
        self._registry_tools: Dict[str, Callable[..., Any]] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self._hitl_enabled = hitl_enabled
        self._hitl_db_path = hitl_db_path
        self._hitl_service = None
        self._conversation_id = str(uuid.uuid4())
        # Guards every change that a model call makes to conversation_history.
        self._history_lock = threading.RLock()

        # Lifecycle management
        self._closed = False
        self._subscribed_channels: List[str] = []
        # Channels this agent owns (an @agent's "<name>_channel"); close()
        # removes each from the Reef once nothing else subscribes to it.
        self._owned_channels: List[str] = []

        # Setup configuration
        config_dict = dict(config or {})
        if system_message:
            config_dict["system_message"] = system_message
        if provider:
            config_dict["provider"] = provider
        if model:
            config_dict["model"] = model
        if reasoning is not None:
            config_dict["reasoning"] = reasoning

        self.config = AgentConfig(**config_dict)

        # Setup provider
        self.provider_name = self._detect_provider()
        if not self.config.provider:
            self.config.provider = self.provider_name
        self._resolve_default_model()
        self.provider = ProviderFactory.create_provider(self.provider_name, self.config)
        self.runtime = ModelRuntime(
            provider=self.provider,
            provider_name=self.provider_name,
            config=self.config,
        )

        # Setup memory system
        if self.memory_enabled:
            self._init_memory_system(memory_config)
        else:
            self.memory = None

        # Setup state storage
        if self.persist_state:
            self._storage = StateStorage()
            self._load_state()
        else:
            self._storage = None

        # The configured system message replaces any system turns loaded by
        # persist_state, so a changed system_message takes effect and restarts
        # never add copies (trimming keeps every system message). Without a
        # configured one, persisted system turns are kept as they are.
        if self.config.system_message:
            system_turn = {"role": "system", "content": self.config.system_message}
            self.conversation_history[:] = [system_turn] + [
                message
                for message in self.conversation_history
                if message.get("role") != "system"
            ]
            self._trim_history()

    # ==========================================

    def _trim_history(self) -> None:
        """Trim history to ``max_history`` non-system messages in whole units.

        A unit is a user message and everything up to the next user message,
        so an assistant tool turn is never separated from its tool results.
        System messages are always kept and do not count towards the limit.
        The newest unit is always kept, even when it alone exceeds the limit.
        """
        if self.max_history is None:
            return
        limit = max(self.max_history, 0)
        history = self.conversation_history
        units: List[List[int]] = []
        for index, message in enumerate(history):
            role = message.get("role")
            if role == "system":
                continue
            if role == "user" or not units:
                units.append([])
            units[-1].append(index)
        retained = sum(len(unit) for unit in units)
        dropped = set()
        for unit in units[:-1]:
            if retained <= limit:
                break
            dropped.update(unit)
            retained -= len(unit)
        if dropped:
            history[:] = [
                message for index, message in enumerate(history) if index not in dropped
            ]

    def _runtime_call_options(
        self, kwargs: Dict[str, Any], *, entry_point: str
    ) -> _RuntimeCallOptions:
        """Resolve the per-call keyword options of one agent entry point.

        Args:
            kwargs: Keyword options passed to the entry point.
            entry_point: Public method name, used in warnings.

        Returns:
            The request tools, the extra system message, and the keyword
            arguments for the runtime call.

        Raises:
            ValueError: If ``allowed_tool_names`` names an unregistered tool.
        """
        extra_names = _ENTRY_POINT_OPTION_NAMES.get(entry_point, ())
        known = {*_RUNTIME_OPTION_NAMES, *_CALL_CONTROL_NAMES, *extra_names}
        for name in kwargs:
            if name not in known:
                logger.warning(
                    "Agent.%s() ignored unknown keyword argument '%s'; "
                    "it will be an error in a future release",
                    entry_point,
                    name,
                )

        allowed_tool_names = kwargs.get("allowed_tool_names")
        if allowed_tool_names is None:
            tools = list(self.tools.values()) if self.tools else None
        else:
            names = tuple(allowed_tool_names)
            unknown = sorted(set(names) - set(self.tools))
            if unknown:
                raise ValueError(f"Unknown allowed tools: {unknown}")
            tools = [self.tools[name] for name in names]

        runtime_kwargs = {name: kwargs.get(name) for name in _RUNTIME_OPTION_NAMES}
        if "stream" in extra_names:
            runtime_kwargs["stream"] = bool(kwargs.get("stream", False))
        return _RuntimeCallOptions(
            tools=tools,
            additional_system_message=kwargs.get("additional_system_message"),
            runtime_kwargs=runtime_kwargs,
        )

    def _append_user_turn(
        self, message: Any
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Append a user turn, trim, and return the turn and a history snapshot.

        The returned turn is the dict stored in history; pass it to
        ``_commit_answer`` so the answer is placed directly after it.
        """
        turn: Dict[str, Any] = {"role": "user", "content": message}
        with self._history_lock:
            self.conversation_history.append(turn)
            self._trim_history()
            return turn, list(self.conversation_history)

    def _commit_answer(
        self,
        content: Any,
        token: Optional[_CallToken] = None,
        *,
        user_turn: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Insert an accepted assistant answer, trim, and persist state.

        With ``user_turn``, the answer goes directly after that turn (matched
        by identity), so overlapping calls on one agent keep each question
        next to its answer. If the turn has left the history before the
        answer arrives (trimmed away by later calls, or the history was
        cleared), the answer is dropped: placing it anywhere else would pair
        it with another question. Without ``user_turn`` the answer is
        appended at the end.

        Returns:
            False when ``token`` was cancelled and the answer was discarded.
        """

        def commit() -> None:
            answer = {"role": "assistant", "content": content}
            with self._history_lock:
                history = self.conversation_history
                if user_turn is None:
                    history.append(answer)
                else:
                    position = next(
                        (
                            index
                            for index in range(len(history) - 1, -1, -1)
                            if history[index] is user_turn
                        ),
                        None,
                    )
                    if position is None:
                        logger.debug(
                            "Agent %s dropped an answer whose user turn is no "
                            "longer in history",
                            self.name,
                        )
                        return
                    history.insert(position + 1, answer)
                self._trim_history()
                if self.persist_state:
                    self._save_state()

        if token is None:
            commit()
            return True
        if token.try_commit(commit):
            return True
        logger.debug("Agent %s discarded the answer of an abandoned call", self.name)
        return False

    @staticmethod
    def _take_call_token() -> Optional[_CallToken]:
        """Consume the call token that chat()/achat() set for this call."""
        token = _CALL_TOKEN.get()
        if token is not None:
            _CALL_TOKEN.set(None)
        return token

    def _detect_provider(self) -> str:
        """
        Automatically detect LLM provider from environment variables or config.

        Returns:
            Provider name (openai, anthropic, cohere)

        Raises:
            ProviderError: If no provider credentials are found
        """
        if self.config.provider:
            return self.config.provider

        if os.getenv("PRAVAL_DEFAULT_MODEL") and not self.config.model:
            self.config.model = str(os.getenv("PRAVAL_DEFAULT_MODEL"))

        if self.config.model and ":" in self.config.model:
            provider, model = self.config.model.split(":", 1)
            self.config.provider = provider
            self.config.model = model
            return provider

        if os.getenv("PRAVAL_DEFAULT_PROVIDER"):
            return str(os.getenv("PRAVAL_DEFAULT_PROVIDER"))

        # Check environment variables for API keys
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        elif os.getenv("COHERE_API_KEY"):
            return "cohere"
        else:
            raise ProviderError(
                "No LLM provider credentials found. Set OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, COHERE_API_KEY, or PRAVAL_DEFAULT_PROVIDER "
                "environment variable, "
                "or specify provider explicitly."
            )

    def _resolve_default_model(self) -> None:
        """Apply environment or registry model defaults."""
        if not self.config.model and os.getenv("PRAVAL_DEFAULT_MODEL"):
            self.config.model = str(os.getenv("PRAVAL_DEFAULT_MODEL"))
        if not self.config.model:
            try:
                self.config.model = get_provider_registry().default_model_for(
                    self.provider_name
                )
            except Exception:
                self.config.model = None

    def _build_hitl_context(self, run_id: str) -> Dict[str, Any]:
        """Build provider-facing HITL context for a run."""
        return {
            "enabled": self._hitl_enabled,
            "run_id": run_id,
            "agent_name": self.name,
            "provider_name": self.provider_name,
            "db_path": self._hitl_db_path,
        }

    def _get_hitl_service(self) -> Any:
        """Get or lazily initialize HITL service."""
        if self._hitl_service is None:
            from ..hitl.service import HITLService

            self._hitl_service = HITLService(db_path=self._hitl_db_path)
        return self._hitl_service

    def _observation_scope(self, run_id: str, request_mode: str) -> ObservationScope:
        """Create or join this agent's invocation observation."""
        return ObservationScope(
            kind=ObservationKind.AGENT,
            run_id=run_id,
            agent_id=self.name,
            agent_name=self.name,
            conversation_id=self._conversation_id,
            request_mode=request_mode,
        )

    def chat(self, message: Union[str, None], **kwargs: Any) -> str:
        """
        Send a message to the agent and get a response.

        Args:
            message: User message to send to the agent
            **kwargs: Per-call options, the same as for generate()

        Returns:
            Agent's response as a string

        Raises:
            ValueError: If message is empty or None, or a tool name is unknown
            PravalError: If response generation fails
        """
        token = self._take_call_token()
        if not message:
            raise ValueError("Message cannot be empty")

        options = self._runtime_call_options(kwargs, entry_point="chat")
        user_turn, history = self._append_user_turn(message)
        run_id = str(uuid.uuid4())

        with self._observation_scope(run_id, "chat"):
            record_content_reference(ContentKind.PROMPT, message)
            try:
                # Generate response using the provider-neutral runtime.
                response = self.runtime.generate_text(
                    messages=options.request_messages(history),
                    tools=options.tools,
                    hitl_context=self._build_hitl_context(run_id),
                    **options.runtime_kwargs,
                )
                self._commit_answer(response, token, user_turn=user_turn)
                record_content_reference(ContentKind.RESPONSE, response)
                return response

            except PravalError:
                # Typed errors (provider, HITL, tool) reach the caller as
                # raised, matching agenerate(), stream() and astream().
                raise
            except Exception as e:
                raise PravalError(f"Failed to generate response: {str(e)}") from e

    def generate(self, message: Any, **kwargs: Any) -> Any:
        """
        Generate a provider-neutral model response.

        This is the richer counterpart to chat(); chat() remains the
        compatibility API that returns only text.

        Args:
            message: User message to send to the agent
            **kwargs: Per-call options: ``response_schema``, ``reasoning``,
                ``provider_options``, ``timeout``, ``metadata``,
                ``stream_options``, ``stream``, ``max_tool_rounds``,
                ``allowed_tool_names`` and ``additional_system_message``.
                Unknown keywords are logged and ignored.

        Raises:
            ValueError: If message is empty or a tool name is unknown
            PravalError: If response generation fails
        """
        token = self._take_call_token()
        if not message:
            raise ValueError("Message cannot be empty")

        options = self._runtime_call_options(kwargs, entry_point="generate")
        user_turn, history = self._append_user_turn(message)
        run_id = str(uuid.uuid4())

        with self._observation_scope(run_id, "generate"):
            record_content_reference(ContentKind.PROMPT, message)
            try:
                response = self.runtime.invoke(
                    messages=options.request_messages(history),
                    tools=options.tools,
                    hitl_context=self._build_hitl_context(run_id),
                    **options.runtime_kwargs,
                )
                self._commit_answer(response.content, token, user_turn=user_turn)
                record_content_reference(ContentKind.RESPONSE, response.content)
                return response
            except PravalError:
                # Typed errors (provider, HITL, tool) reach the caller as
                # raised, matching agenerate(), stream() and astream().
                raise
            except Exception as e:
                raise PravalError(f"Failed to generate response: {str(e)}") from e

    def transcribe(
        self,
        audio: Any,
        *,
        model: Optional[str] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json",
        temperature: Optional[float] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Transcribe request-based audio without changing chat history."""
        run_id = str(uuid.uuid4())
        with self._observation_scope(run_id, "transcription"):
            record_content_reference(ContentKind.MEDIA, audio, media_type=mime_type)
            transcribe = getattr(self.provider, "transcribe", None)
            if not callable(transcribe):
                raise ProviderError(
                    f"Provider '{self.provider_name}' does not support "
                    "audio transcription"
                )
            response = transcribe(
                TranscriptionRequest(
                    audio=audio,
                    provider=self.provider_name,
                    model=model,
                    filename=filename,
                    mime_type=mime_type,
                    language=language,
                    prompt=prompt,
                    response_format=response_format,
                    temperature=temperature,
                    provider_options=provider_options or {},
                    timeout=timeout,
                    metadata=metadata or {},
                )
            )
            record_model_facts(
                provider=self.provider_name,
                model=(
                    response.model
                    if isinstance(response, AudioResponse) and response.model
                    else model or self.config.model
                ),
                request_mode="transcription",
            )
            if isinstance(response, AudioResponse):
                if response.text:
                    record_content_reference(ContentKind.RESPONSE, response.text)
                    return response.text
                raise ProviderError(
                    f"Provider '{self.provider_name}' returned no transcription text"
                )
            if isinstance(response, str) and response:
                record_content_reference(ContentKind.RESPONSE, response)
                return response
            raise ProviderError(
                f"Provider '{self.provider_name}' returned an invalid "
                "transcription response"
            )

    def speak(
        self,
        text: str,
        *,
        model: Optional[str] = None,
        voice: str = "alloy",
        response_format: str = "mp3",
        speed: float = 1.0,
        instructions: Optional[str] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Synthesize request-based speech without changing chat history."""
        if not text or not text.strip():
            raise ValueError("Speech text cannot be empty")
        run_id = str(uuid.uuid4())
        with self._observation_scope(run_id, "speech"):
            record_content_reference(ContentKind.PROMPT, text)
            speak = getattr(self.provider, "speak", None)
            if not callable(speak):
                raise ProviderError(
                    f"Provider '{self.provider_name}' does not support speech "
                    "generation"
                )
            response = speak(
                SpeechRequest(
                    input=text,
                    provider=self.provider_name,
                    model=model,
                    voice=voice,
                    response_format=response_format,
                    speed=speed,
                    instructions=instructions,
                    provider_options=provider_options or {},
                    timeout=timeout,
                    metadata=metadata or {},
                )
            )
            record_model_facts(
                provider=self.provider_name,
                model=(
                    response.model
                    if isinstance(response, AudioResponse) and response.model
                    else model or self.config.model
                ),
                request_mode="speech",
            )
            if isinstance(response, AudioResponse):
                if response.data:
                    record_content_reference(
                        ContentKind.MEDIA,
                        response.data,
                        media_type=response.mime_type,
                    )
                    return response.data
                raise ProviderError(
                    f"Provider '{self.provider_name}' returned no synthesized audio"
                )
            if isinstance(response, bytes) and response:
                record_content_reference(ContentKind.MEDIA, response)
                return response
            raise ProviderError(
                f"Provider '{self.provider_name}' returned an invalid speech response"
            )

    async def agenerate(self, message: Any, **kwargs: Any) -> Any:
        """Async wrapper for generate()."""
        if not message:
            raise ValueError("Message cannot be empty")

        options = self._runtime_call_options(kwargs, entry_point="agenerate")
        user_turn, history = self._append_user_turn(message)
        run_id = str(uuid.uuid4())

        with self._observation_scope(run_id, "generate_async"):
            record_content_reference(ContentKind.PROMPT, message)
            response = await self.runtime.ainvoke(
                messages=options.request_messages(history),
                tools=options.tools,
                hitl_context=self._build_hitl_context(run_id),
                **options.runtime_kwargs,
            )
            self._commit_answer(response.content, user_turn=user_turn)
            record_content_reference(ContentKind.RESPONSE, response.content)
            return response

    def stream(self, message: Any, **kwargs: Any) -> Any:
        """Stream provider-neutral model events.

        The user turn enters history when the stream is created. The answer
        enters history when the ``final`` event is produced, before it is
        yielded; a failed or abandoned stream leaves only the user turn.
        """
        if not message:
            raise ValueError("Message cannot be empty")
        options = self._runtime_call_options(kwargs, entry_point="stream")
        user_turn, history = self._append_user_turn(message)
        run_id = str(uuid.uuid4())

        def observed_stream() -> Any:
            deltas: List[str] = []
            with self._observation_scope(run_id, "stream"):
                record_content_reference(ContentKind.PROMPT, message)
                for event in self.runtime.stream(
                    messages=options.request_messages(history),
                    tools=options.tools,
                    hitl_context=self._build_hitl_context(run_id),
                    **options.runtime_kwargs,
                ):
                    self._observe_stream_event(event, deltas, user_turn)
                    yield event

        return observed_stream()

    async def astream(self, message: Any, **kwargs: Any) -> Any:
        """Asynchronously stream provider-neutral model events.

        History is updated as described for stream().
        """
        if not message:
            raise ValueError("Message cannot be empty")
        options = self._runtime_call_options(kwargs, entry_point="astream")
        user_turn, history = self._append_user_turn(message)
        run_id = str(uuid.uuid4())
        deltas: List[str] = []
        with self._observation_scope(run_id, "stream_async"):
            record_content_reference(ContentKind.PROMPT, message)
            async for event in self.runtime.astream(
                messages=options.request_messages(history),
                tools=options.tools,
                hitl_context=self._build_hitl_context(run_id),
                **options.runtime_kwargs,
            ):
                self._observe_stream_event(event, deltas, user_turn)
                yield event

    def _observe_stream_event(
        self, event: Any, deltas: List[str], user_turn: Dict[str, Any]
    ) -> None:
        """Collect text deltas and commit the answer on the ``final`` event."""
        event_type = getattr(event, "type", None)
        if event_type == "delta":
            deltas.append(str(getattr(event, "delta", "") or ""))
        elif event_type == "final":
            response = getattr(event, "response", None)
            content = response.content if response is not None else "".join(deltas)
            self._commit_answer(content, user_turn=user_turn)

    def configure_hitl(
        self,
        *,
        enabled: bool = True,
        db_path: Optional[str] = None,
    ) -> None:
        """
        Configure HITL behavior for this agent.

        Args:
            enabled: Whether HITL is enabled for this agent
            db_path: Optional SQLite path override for intervention storage
        """
        self._hitl_enabled = enabled
        if db_path is not None:
            self._hitl_db_path = db_path
            self._hitl_service = None

    def get_pending_interventions(
        self,
        run_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        """Get pending interventions filtered to this agent."""
        service = self._get_hitl_service()
        return service.get_pending_interventions(
            run_id=run_id,
            agent_name=self.name,
            limit=limit,
        )

    def approve_intervention(
        self,
        intervention_id: str,
        *,
        reviewer: str = "human",
        edited_args: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Approve or edit-approve an intervention for this agent."""
        service = self._get_hitl_service()
        intervention = service.get_intervention(intervention_id)
        if intervention is None:
            raise ValueError(f"Intervention '{intervention_id}' not found")
        if intervention.agent_name != self.name:
            raise ValueError(
                (
                    f"Intervention '{intervention_id}' does not belong to agent "
                    f"'{self.name}'"
                )
            )
        return service.approve_intervention(
            intervention_id,
            reviewer=reviewer,
            edited_args=edited_args,
        )

    def reject_intervention(
        self,
        intervention_id: str,
        *,
        reason: str,
        reviewer: str = "human",
    ) -> Any:
        """Reject an intervention for this agent."""
        service = self._get_hitl_service()
        intervention = service.get_intervention(intervention_id)
        if intervention is None:
            raise ValueError(f"Intervention '{intervention_id}' not found")
        if intervention.agent_name != self.name:
            raise ValueError(
                (
                    f"Intervention '{intervention_id}' does not belong to agent "
                    f"'{self.name}'"
                )
            )
        return service.reject_intervention(
            intervention_id,
            reviewer=reviewer,
            reason=reason,
        )

    def resume_run(self, run_id: str) -> str:
        """
        Resume a previously suspended HITL run after a decision.

        Args:
            run_id: Suspended run identifier

        Returns:
            Final model response for the resumed run
        """
        service, suspended, hitl_context = self._prepare_resume_run(run_id)

        try:
            if suspended.state.get("schema") == "model_runtime_tool_v1":
                resumed = self.runtime.resume_tool_flow(
                    suspended_state=suspended.state,
                    tools=list(self.tools.values()) if self.tools else None,
                    hitl_context=hitl_context,
                )
                response = resumed.content
            else:
                if not hasattr(self.provider, "resume_tool_flow"):
                    raise PravalError(
                        f"Provider '{self.provider_name}' does not support HITL resume"
                    )
                response = self.provider.resume_tool_flow(
                    suspended_state=suspended.state,
                    tools=list(self.tools.values()) if self.tools else None,
                    hitl_context=hitl_context,
                )
            return self._complete_resume_run(run_id, str(response), service)
        except BaseException:
            # A new intervention has already re-pended the run; otherwise the
            # run becomes resumable again, as it was before the claim.
            service.release_run(run_id)
            raise

    async def aresume_run(self, run_id: str) -> str:
        """Asynchronously resume a suspended run containing async-only tools."""
        service, suspended, hitl_context = self._prepare_resume_run(run_id)
        try:
            response = await self._aresume_claimed_run(suspended, hitl_context)
            return self._complete_resume_run(run_id, str(response), service)
        except BaseException:
            service.release_run(run_id)
            raise

    async def _aresume_claimed_run(
        self, suspended: Any, hitl_context: Dict[str, Any]
    ) -> Any:
        """Run the resume continuation of a claimed suspended run."""
        if suspended.state.get("schema") == "model_runtime_tool_v1":
            resumed = await self.runtime.resume_tool_flow_async(
                suspended_state=suspended.state,
                tools=list(self.tools.values()) if self.tools else None,
                hitl_context=hitl_context,
            )
            response = resumed.content
        else:
            resume = getattr(self.provider, "aresume_tool_flow", None)
            if callable(resume):
                response = resume(
                    suspended_state=suspended.state,
                    tools=list(self.tools.values()) if self.tools else None,
                    hitl_context=hitl_context,
                )
                if inspect.isawaitable(response):
                    response = await response
            else:
                resume = getattr(self.provider, "resume_tool_flow", None)
                if not callable(resume):
                    raise PravalError(
                        f"Provider '{self.provider_name}' does not support HITL resume"
                    )
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: resume(
                        suspended_state=suspended.state,
                        tools=list(self.tools.values()) if self.tools else None,
                        hitl_context=hitl_context,
                    ),
                )
        return response

    def _prepare_resume_run(self, run_id: str) -> Any:
        """Validate a suspended run and build its decided HITL context."""
        service = self._get_hitl_service()
        suspended = service.get_suspended_run(run_id)
        if suspended is None:
            raise ValueError(f"Suspended run '{run_id}' not found")
        if suspended.agent_name != self.name:
            raise ValueError(
                f"Suspended run '{run_id}' belongs to '{suspended.agent_name}', "
                f"not '{self.name}'"
            )
        if suspended.status != "pending":
            raise ValueError(
                f"Suspended run '{run_id}' is not pending (status={suspended.status})"
            )

        intervention_id = suspended.state.get("intervention_id")
        if not intervention_id:
            raise ValueError(f"Suspended run '{run_id}' has no linked intervention_id")

        intervention = service.get_intervention(intervention_id)
        if intervention is None:
            raise ValueError(
                f"Intervention '{intervention_id}' linked to run '{run_id}' not found"
            )
        if intervention.status.value == "PENDING":
            raise ValueError(
                f"Intervention '{intervention_id}' is still pending approval"
            )

        hitl_context = {
            **self._build_hitl_context(run_id),
            "resume_intervention": intervention.to_dict(),
        }
        # Claim last, so a validation error never leaves the run claimed. The
        # claim is one conditional UPDATE, so only one thread or process can
        # resume the run and execute the approved tool.
        if not service.claim_run(run_id):
            raise ValueError(f"Suspended run '{run_id}' is not pending")
        # Re-read under the claim: an earlier resume that ran the tool and then
        # failed may have stored its results after the first read.
        from ..hitl.models import SuspendedRunState

        claimed = service.store.get_suspended_run(run_id)
        if isinstance(claimed, SuspendedRunState):
            if claimed.state.get("intervention_id") != intervention_id:
                # Another resume moved the run on to a new intervention after
                # the first read; this decision no longer applies to it.
                service.release_run(run_id)
                raise ValueError(
                    f"Suspended run '{run_id}' now waits on intervention "
                    f"'{claimed.state.get('intervention_id')}'"
                )
            suspended = claimed
        return service, suspended, hitl_context

    def _complete_resume_run(self, run_id: str, response: str, service: Any) -> str:
        """Record a resumed response and mark its suspended run complete."""
        self._commit_answer(response)
        service.mark_run_completed(run_id, response)

        try:
            from ..observability.tracing import get_current_span

            span = get_current_span()
            if span:
                span.add_event(
                    "hitl.run.resumed",
                    {
                        "run_id": run_id,
                        "agent_name": self.name,
                        "provider_name": self.provider_name,
                    },
                )
        except Exception:
            pass

        return response

    def tool(self, func: Callable) -> Callable:
        """
        Decorator to register a function as a tool for the agent.

        Args:
            func: Function to register as a tool

        Returns:
            The original function (unchanged)

        Raises:
            ValueError: If function lacks proper type hints
        """
        # Validate function signature
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.annotation == inspect.Parameter.empty:
                raise ValueError(
                    "Tool functions must have type hints for all parameters"
                )

        if sig.return_annotation == inspect.Signature.empty:
            raise ValueError("Tool functions must have a return type hint")

        # Register tool on the agent
        tool_name = func.__name__
        self.tools[tool_name] = {
            "function": func,
            "description": func.__doc__ or "",
            "parameters": self._extract_parameters(sig),
            "requires_approval": False,
            "risk_level": "low",
            "approval_reason": "",
        }

        # Best-effort: also register in the global tool registry for discovery
        try:
            registry = get_tool_registry()
            existing = registry.get_tool(tool_name)
            if existing and existing.func is func:
                return func
            if existing and existing.func is not func:
                logger.debug(
                    "Tool name collision for '%s'; skipping registry registration.",
                    tool_name,
                )
                return func

            metadata = ToolMetadata(
                tool_name=tool_name,
                owned_by=self.name,
                description=func.__doc__ or "",
                category="general",
                shared=False,
                requires_approval=False,
                risk_level="low",
                approval_reason="",
            )
            registry.register_tool(Tool(func, metadata))
            self._registry_tools[tool_name] = func
        except ToolError as e:
            logger.debug("Tool registry registration failed for '%s': %s", tool_name, e)
        except Exception as e:
            logger.debug("Unexpected tool registry error for '%s': %s", tool_name, e)

        return func

    def add_tool_spec(
        self,
        spec: ToolSpec,
        handler: Callable[..., Any],
        *,
        async_only: bool = False,
    ) -> None:
        """Register an externally described JSON-schema tool on this agent.

        Args:
            spec: Provider-neutral tool declaration.
            handler: Callable invoked with the model-supplied keyword arguments.
            async_only: Whether the tool may only run through async Agent APIs.

        Raises:
            TypeError: If ``spec`` or ``handler`` has the wrong type.
            ValueError: If the name or schema is invalid or already registered.
        """
        if not isinstance(spec, ToolSpec):
            raise TypeError("spec must be a ToolSpec")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if not spec.name or not spec.name.strip():
            raise ValueError("ToolSpec name cannot be empty")
        if spec.name in self.tools:
            raise ValueError(f"Tool '{spec.name}' is already registered")
        self._validate_tool_schema(spec.parameters)
        if async_only and not inspect.iscoroutinefunction(handler):
            raise ValueError("async_only tools require an async handler")

        if async_only:

            async def registered_handler(**kwargs: Any) -> Any:
                return await handler(**kwargs)

        else:

            def registered_handler(**kwargs: Any) -> Any:
                return handler(**kwargs)

        registered_handler.__name__ = spec.name
        registered_handler.__doc__ = spec.description
        self.tools[spec.name] = {
            "name": spec.name,
            "function": registered_handler,
            "description": spec.description,
            "parameters": dict(spec.parameters),
            "strict": spec.strict,
            "requires_approval": spec.requires_approval,
            "risk_level": spec.risk_level,
            "approval_reason": spec.approval_reason,
            "metadata": dict(spec.metadata),
            "async_only": async_only,
        }

        try:
            metadata = ToolMetadata(
                tool_name=spec.name,
                owned_by=self.name,
                description=spec.description,
                category=str(spec.metadata.get("category", "external")),
                shared=False,
                requires_approval=spec.requires_approval,
                risk_level=spec.risk_level,
                approval_reason=spec.approval_reason,
            )
            get_tool_registry().register_tool(Tool(registered_handler, metadata))
            self._registry_tools[spec.name] = registered_handler
        except ToolError as e:
            logger.debug(
                "External tool registry registration failed for '%s': %s",
                spec.name,
                e,
            )

    @staticmethod
    def _validate_tool_schema(schema: Dict[str, Any]) -> None:
        """Validate the JSON Schema subset accepted for tool arguments."""
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError("Tool parameters must be a JSON Schema object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict):
            raise ValueError("Tool JSON Schema properties must be an object")
        if not isinstance(required, list) or not all(
            isinstance(name, str) for name in required
        ):
            raise ValueError("Tool JSON Schema required must be a list of names")
        try:
            json.dumps(schema)
        except (TypeError, ValueError) as exc:
            raise ValueError("Tool JSON Schema must be JSON serializable") from exc

    def _extract_parameters(self, signature: inspect.Signature) -> Dict[str, Any]:
        """Extract parameter information from function signature."""
        parameters = {}
        for name, param in signature.parameters.items():
            parameters[name] = {
                "type": (
                    param.annotation.__name__
                    if hasattr(param.annotation, "__name__")
                    else str(param.annotation)
                ),
                "required": param.default == inspect.Parameter.empty,
            }
        return parameters

    def _save_state(self) -> None:
        """Save current conversation state to storage."""
        if self._storage:
            self._storage.save(self.name, self.conversation_history)

    def _load_state(self) -> None:
        """Load conversation state from storage."""
        if self._storage:
            saved_state = self._storage.load(self.name)
            if saved_state:
                self.conversation_history = saved_state

    # ==========================================
    # REEF COMMUNICATION METHODS
    # ==========================================

    def send_knowledge(
        self, to_agent: str, knowledge: Dict[str, Any], channel: str = "main"
    ) -> str:
        """
        Send knowledge to another agent through the reef.

        Args:
            to_agent: Name of the target agent
            knowledge: Knowledge data to send
            channel: Reef channel to use (default: "main")

        Returns:
            Spore ID of the sent message
        """
        from .reef import get_reef

        return get_reef().send(
            from_agent=self.name,
            to_agent=to_agent,
            knowledge=knowledge,
            channel=channel,
        )

    def broadcast_knowledge(
        self, knowledge: Dict[str, Any], channel: str = "main"
    ) -> str:
        """
        Broadcast knowledge to all agents in the reef.

        Args:
            knowledge: Knowledge data to broadcast
            channel: Reef channel to use (default: "main")

        Returns:
            Spore ID of the broadcast message
        """
        from .reef import get_reef

        return get_reef().broadcast(
            from_agent=self.name, knowledge=knowledge, channel=channel
        )

    def request_knowledge(
        self, from_agent: str, request: Dict[str, Any], timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Request knowledge from another agent with timeout.

        Args:
            from_agent: Name of the agent to request from
            request: Request data
            timeout: Timeout in seconds

        Returns:
            Response data or None if timeout
        """
        from .reef import get_reef

        reef = get_reef()
        try:
            response = reef.request_and_wait(
                from_agent=self.name,
                to_agent=from_agent,
                request=request,
                expires_in_seconds=timeout,
                timeout=timeout,
            )
            return response.knowledge
        except TimeoutError:
            return None

    def on_spore_received(self, spore) -> None:
        """
        Handle received spores from the reef.

        This is a default implementation that can be overridden
        by subclasses for custom spore handling.

        Args:
            spore: The received Spore object
        """
        # Use custom handler if set, otherwise do nothing
        if hasattr(self, "_custom_spore_handler") and self._custom_spore_handler:
            result = self._custom_spore_handler(spore)
            if inspect.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    asyncio.run(result)
        # Default implementation does nothing
        # Subclasses can override for custom behavior

    def subscribe_to_channel(self, channel_name: str) -> None:
        """
        Subscribe this agent to a reef channel.

        Args:
            channel_name: Name of the channel to subscribe to
        """
        from .reef import get_reef

        reef = get_reef()
        # Create channel if it doesn't exist
        reef.create_channel(channel_name)
        reef.subscribe(self.name, self.on_spore_received, channel_name)

        # Track subscription for cleanup
        if channel_name not in self._subscribed_channels:
            self._subscribed_channels.append(channel_name)

    def unsubscribe_from_channel(self, channel_name: str) -> None:
        """
        Unsubscribe this agent from a reef channel.

        Args:
            channel_name: Name of the channel to unsubscribe from
        """
        from .reef import get_reef

        reef = get_reef()
        channel = reef.get_channel(channel_name)
        if channel:
            channel.unsubscribe(self.name, self.on_spore_received)

        # Remove from tracking
        if channel_name in self._subscribed_channels:
            self._subscribed_channels.remove(channel_name)

    @property
    def spore_handler(self) -> Optional[Callable]:
        """
        Get the current spore handler for this agent.

        Returns:
            The custom spore handler function, or None if not set
        """
        return getattr(self, "_custom_spore_handler", None)

    def set_spore_handler(self, handler: Callable) -> None:
        """
        Set a custom spore handler for this agent.

        Args:
            handler: Function that takes a Spore object and handles it
        """
        self._custom_spore_handler = handler

    # ==========================================
    # LIFECYCLE MANAGEMENT
    # ==========================================

    def close(self) -> None:
        """
        Release all resources held by the agent.

        This method:
        - Unsubscribes from all reef channels, and removes the channel an
          ``@agent`` owns (``<name>_channel``) once it has no other subscribers
        - Unregisters the tools this agent added to the global tool registry
        - Shuts down the memory system
        - Clears conversation history

        Safe to call multiple times. After calling close(), the agent
        should not be used for further operations.

        Example::

            agent = Agent("assistant")
            try:
                response = agent.chat("Hello")
            finally:
                agent.close()

            # Or use as context manager:
            with Agent("assistant") as agent:
                response = agent.chat("Hello")
        """
        if self._closed:
            return

        self._closed = True

        # Unsubscribe from reef channels
        try:
            from .reef import get_reef

            reef = get_reef()
            for channel_name in self._subscribed_channels[
                :
            ]:  # Copy to avoid mutation during iteration
                try:
                    channel = reef.get_channel(channel_name)
                    if channel:
                        channel.unsubscribe(self.name, self.on_spore_received)
                except Exception as e:
                    logger.warning(
                        f"Error unsubscribing {self.name} from {channel_name}: {e}"
                    )
            self._subscribed_channels.clear()
            for channel_name in self._owned_channels:
                reef.remove_channel_if_unused(channel_name)
            self._owned_channels.clear()
        except Exception as e:
            logger.warning(f"Error during reef cleanup for {self.name}: {e}")

        # Remove the tools this agent registered globally; a tool closure
        # that captures the agent would otherwise keep it alive.
        if self._registry_tools:
            try:
                registry = get_tool_registry()
                for tool_name, func in self._registry_tools.items():
                    registry.unregister_owned_tool(tool_name, func, self.name)
            except Exception as e:
                logger.warning(f"Error unregistering tools for {self.name}: {e}")
            self._registry_tools.clear()

        # Shutdown memory system
        if self.memory:
            try:
                if hasattr(self.memory, "shutdown"):
                    self.memory.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down memory for {self.name}: {e}")
            self.memory = None

        provider_close = getattr(self.provider, "close", None)
        if callable(provider_close):
            try:
                provider_close()
            except Exception as e:
                logger.warning(f"Error closing provider for {self.name}: {e}")

        # Clear conversation history
        self.conversation_history.clear()

        logger.debug(f"Agent {self.name} closed")

    def __enter__(self) -> "Agent":
        """Context manager entry - returns the agent."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    def __del__(self):
        """Destructor - attempt cleanup if not already done."""
        # Skip cleanup during Python shutdown
        # The import itself can fail during shutdown, so wrap everything
        try:
            import sys

            if sys.meta_path is None:
                return
            if not getattr(self, "_closed", True):
                self.close()
        except Exception:
            pass  # Suppress all errors during garbage collection

    @property
    def is_closed(self) -> bool:
        """Check if the agent has been closed."""
        return self._closed

    # ==========================================
    # MEMORY SYSTEM METHODS
    # ==========================================

    def _init_memory_system(self, memory_config: Optional[Dict[str, Any]] = None):
        """Initialize the memory system for this agent"""
        try:
            from ..memory import MemoryManager

            # Default memory configuration
            default_config = {
                "backend": "auto",
                "collection_name": f"praval_memories_{self.name}",
                "knowledge_base_path": self.knowledge_base,
            }

            # Merge with provided config
            if memory_config:
                default_config.update(memory_config)

            # Initialize memory manager
            self.memory = MemoryManager(agent_id=self.name, **default_config)

            logger.info(f"Memory system initialized for agent {self.name}")

        except ImportError as e:
            logger.warning(f"Memory system not available: {e}")
            self.memory = None
            self.memory_enabled = False
        except Exception as e:
            logger.warning(f"Failed to initialize memory system for {self.name}: {e}")
            self.memory = None
            self.memory_enabled = False

    def remember(
        self, content: str, importance: float = 0.5, memory_type: str = "short_term"
    ) -> Optional[str]:
        """
        Store a memory

        Args:
            content: The content to remember
            importance: Importance score (0.0 to 1.0)
            memory_type: Type of memory ("short_term", "semantic", "episodic")

        Returns:
            Memory ID if successful, None otherwise
        """
        if not self.memory:
            logger.debug(f"Memory not enabled for agent {self.name}")
            return None

        try:
            from ..memory import MemoryType

            # Map string to MemoryType enum
            type_mapping = {
                "short_term": MemoryType.SHORT_TERM,
                "semantic": MemoryType.SEMANTIC,
                "episodic": MemoryType.EPISODIC,
                "working": MemoryType.SHORT_TERM,
            }

            mem_type = type_mapping.get(memory_type, MemoryType.SHORT_TERM)

            return self.memory.store_memory(
                agent_id=self.name,
                content=content,
                memory_type=mem_type,
                importance=importance,
            )

        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")
            return None

    def recall(
        self, query: str, limit: int = 5, similarity_threshold: float = 0.1
    ) -> List:
        """
        Recall memories based on a query

        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score

        Returns:
            List of MemoryEntry objects
        """
        if not self.memory:
            logger.debug(f"Memory not enabled for agent {self.name}")
            return []

        try:
            from ..memory import MemoryQuery

            memory_query = MemoryQuery(
                query_text=query,
                agent_id=self.name,
                limit=limit,
                similarity_threshold=similarity_threshold,
            )

            results = self.memory.search_memories(memory_query)
            return results.entries

        except Exception as e:
            logger.warning(f"Failed to recall memories: {e}")
            return []

    def recall_by_id(self, memory_id: str) -> List:
        """Recall a specific memory by ID (for resolving spore references)"""
        if not self.memory:
            return []

        return self.memory.recall_by_id(memory_id)

    def get_conversation_context(self, turns: int = 10) -> List:
        """Get recent conversation context"""
        if not self.memory:
            return []

        return self.memory.get_conversation_context(self.name, turns)

    def create_knowledge_reference(
        self, content: str, importance: float = 0.8
    ) -> List[str]:
        """
        Create knowledge references for lightweight spores

        Args:
            content: Knowledge content to store and reference
            importance: Importance threshold

        Returns:
            List of knowledge reference IDs
        """
        if not self.memory:
            return []

        try:
            return self.memory.get_knowledge_references(content, importance)
        except Exception as e:
            logger.warning(f"Failed to create knowledge reference: {e}")
            return []

    def resolve_spore_knowledge(self, spore) -> Dict[str, Any]:
        """
        Resolve knowledge references in a spore

        Args:
            spore: Spore object with potential knowledge references

        Returns:
            Complete knowledge including resolved references
        """
        if not self.memory:
            return spore.knowledge

        try:
            from .reef import get_reef

            reef = get_reef()
            return reef.resolve_knowledge_references(spore, self.memory)
        except Exception as e:
            logger.warning(f"Failed to resolve spore knowledge: {e}")
            return spore.knowledge

    def send_lightweight_knowledge(
        self, to_agent: str, large_content: str, summary: str, channel: str = "main"
    ) -> str:
        """
        Send large knowledge as lightweight spore with references

        Args:
            to_agent: Target agent
            large_content: Large content to reference
            summary: Brief summary for the spore
            channel: Communication channel

        Returns:
            Spore ID
        """
        # Create knowledge reference
        refs = self.create_knowledge_reference(large_content)

        if not refs:
            # Fallback to direct send if referencing fails
            return self.send_knowledge(to_agent, {"content": large_content}, channel)

        # Send lightweight spore with reference
        from .reef import get_reef

        reef = get_reef()
        return reef.create_knowledge_reference_spore(
            from_agent=self.name,
            to_agent=to_agent,
            knowledge_summary=summary,
            knowledge_references=refs,
            channel=channel,
        )
