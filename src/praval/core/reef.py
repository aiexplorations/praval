"""
Reef Communication System for Praval Framework.

Like coral reefs facilitate communication between polyps through chemical and biological
signals,
this system enables knowledge-first communication between agents through structured JSON
message queues.

Components:
- Spores: JSON messages containing knowledge, data, or requests
- ReefChannel: Named message channels within the reef
- Reef: The message queue network connecting all agents
"""

import asyncio
import inspect
import json
import logging
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Deque, Dict, List, Optional

from ..models import ContentPart

if TYPE_CHECKING:
    import aio_pika

logger = logging.getLogger(__name__)

# Default maximum spore payload size (10MB)
MAX_SPORE_SIZE_BYTES = 10 * 1024 * 1024


def _estimate_payload_size_bytes(payload: Any) -> int:
    """Estimate payload size without stringifying the entire payload."""
    try:
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except Exception:
        # Fallback to conservative estimate if payload isn't JSON-serializable
        return MAX_SPORE_SIZE_BYTES + 1


def _contains_binary(value: Any) -> bool:
    """Return whether a nested value contains raw binary data."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return True
    if isinstance(value, Mapping):
        return any(_contains_binary(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_binary(item) for item in value)
    return False


class SporeValidationError(Exception):
    """Raised when spore validation fails."""

    pass


class ReefLifecycleError(RuntimeError):
    """Raised when an active Reef operation is interrupted by its lifecycle."""


class SporeType(Enum):
    """Types of spores that can flow through the reef."""

    KNOWLEDGE = "knowledge"  # Pure knowledge/data sharing
    REQUEST = "request"  # Request for information or action
    RESPONSE = "response"  # Response to a request
    BROADCAST = "broadcast"  # Message to all agents
    NOTIFICATION = "notification"  # Event notification


@dataclass
class Spore:
    """
    A spore is a knowledge-carrying message that flows through the reef.

    Spores are immutable. To add references, use
    add_knowledge_reference()/add_data_reference(),
    which return new Spore instances.

    Like biological spores, each carries:
    - Genetic material (knowledge/data)
    - Identification markers (metadata)
    - Survival instructions (processing hints)

    Spores can carry either direct knowledge or lightweight references to
    knowledge stored in vector memory, following the principle that
    "light spores travel far."
    """

    id: str
    spore_type: SporeType
    from_agent: str
    to_agent: Optional[str]  # None for broadcasts
    knowledge: Optional[Dict[str, Any]]  # The actual data payload
    created_at: datetime
    expires_at: Optional[datetime] = None
    priority: int = 5  # 1-10, higher = more urgent
    reply_to: Optional[str] = None  # For request-response patterns
    metadata: Optional[Dict[str, Any]] = None
    knowledge_references: List[str] = None  # References to stored knowledge
    data_references: List[str] = None  # References to storage system data
    schema_version: str = "1.0"
    payload: Optional[Dict[str, Any]] = None
    content_parts: List[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    trace_id: Optional[str] = None
    run_id: Optional[str] = None
    idempotency_key: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.knowledge_references is None:
            self.knowledge_references = []
        if self.data_references is None:
            self.data_references = []
        if self.content_parts is None:
            self.content_parts = []
        self.content_parts = self._normalize_content_parts(self.content_parts)
        if self.payload is None and self.knowledge is not None:
            self.payload = self.knowledge
        if self.knowledge is None and self.payload is not None:
            self.knowledge = self.payload

        # Validate the spore
        self.validate()

    @staticmethod
    def _normalize_content_parts(content_parts: List[Any]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in content_parts:
            if isinstance(item, ContentPart):
                part = item
            elif isinstance(item, Mapping):
                if _contains_binary(item):
                    raise SporeValidationError(
                        "content_parts must use base64 strings or data references, "
                        "not raw binary values"
                    )
                try:
                    part = ContentPart.model_validate(dict(item))
                except Exception as exc:
                    raise SporeValidationError(
                        f"invalid content_parts entry: {exc}"
                    ) from exc
            else:
                raise SporeValidationError(
                    "content_parts entries must be ContentPart instances or mappings"
                )
            dumped = part.model_dump(exclude_none=True)
            if _contains_binary(dumped):
                raise SporeValidationError(
                    "content_parts must use base64 strings or data references, "
                    "not raw binary values"
                )
            normalized.append(dumped)
        return normalized

    def validate(self, max_size: int = None) -> None:
        """
        Validate the spore payload.

        Args:
            max_size: Maximum allowed payload size in bytes (default:
            MAX_SPORE_SIZE_BYTES)

        Raises:
            SporeValidationError: If validation fails
        """
        if max_size is None:
            max_size = MAX_SPORE_SIZE_BYTES

        # Validate knowledge type
        if self.knowledge is not None and not isinstance(self.knowledge, Mapping):
            raise SporeValidationError(
                f"knowledge must be a dict, got {type(self.knowledge).__name__}"
            )

        if not isinstance(self.data_references, list) or not all(
            isinstance(reference, str) for reference in self.data_references
        ):
            raise SporeValidationError("data_references must be a list of strings")
        if not isinstance(self.knowledge_references, list) or not all(
            isinstance(reference, str) for reference in self.knowledge_references
        ):
            raise SporeValidationError("knowledge_references must be a list of strings")

        try:
            encoded = json.dumps(self._transport_body_payload(), ensure_ascii=False)
        except (TypeError, ValueError):
            raise SporeValidationError("spore content is not JSON-serializable")

        # Validate payload size
        payload_size = len(encoded.encode("utf-8"))
        if payload_size > max_size:
            raise SporeValidationError(
                f"Spore payload too large: {payload_size} bytes "
                f"(max: {max_size} bytes = {max_size / 1024 / 1024:.1f}MB). "
                f"Consider using knowledge_references for large data."
            )

    def _transport_body_payload(self) -> Any:
        """Build the backward-compatible JSON body used for size and AMQP wire data."""
        if not (
            self.metadata
            or self.content_parts
            or self.data_references
            or self.knowledge_references
            or self.payload != self.knowledge
        ):
            return self.knowledge if self.knowledge is not None else None
        return {
            "_praval_spore_envelope": "2.0",
            "knowledge": self.knowledge,
            "payload": self.payload,
            "metadata": dict(self.metadata),
            "content_parts": list(self.content_parts),
            "knowledge_references": list(self.knowledge_references),
            "data_references": list(self.data_references),
        }

    def get_payload_size(self) -> int:
        """Get the size of the knowledge payload in bytes."""
        if self.knowledge is None:
            return 0
        try:
            return len(json.dumps(self.knowledge, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError):
            return 0

    def to_json(self) -> str:
        """Serialize spore to JSON for transmission."""
        data = {
            "id": self.id,
            "spore_type": self.spore_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "knowledge": (self.knowledge if self.knowledge is not None else None),
            "created_at": self.created_at.isoformat(),
            "expires_at": (self.expires_at.isoformat() if self.expires_at else None),
            "priority": self.priority,
            "reply_to": self.reply_to,
            "metadata": (self.metadata if self.metadata is not None else {}),
            "knowledge_references": list(self.knowledge_references),
            "data_references": list(self.data_references),
            "schema_version": self.schema_version,
            "payload": (self.payload if self.payload is not None else None),
            "content_parts": list(self.content_parts),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "idempotency_key": self.idempotency_key,
        }
        # Handle datetime serialization
        data["created_at"] = self.created_at.isoformat()
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        data["spore_type"] = self.spore_type.value
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Spore":
        """Deserialize spore from JSON."""
        data = json.loads(json_str)
        # Handle datetime deserialization
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        data["spore_type"] = SporeType(data["spore_type"])
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if spore has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    def add_knowledge_reference(self, reference_id: str) -> "Spore":
        """Return a new spore with an added knowledge reference."""
        if reference_id in self.knowledge_references:
            return self
        return Spore(
            id=self.id,
            spore_type=self.spore_type,
            from_agent=self.from_agent,
            to_agent=self.to_agent,
            knowledge=(self.knowledge if self.knowledge is not None else None),
            created_at=self.created_at,
            expires_at=self.expires_at,
            priority=self.priority,
            reply_to=self.reply_to,
            metadata=(self.metadata if self.metadata is not None else {}),
            knowledge_references=list(self.knowledge_references) + [reference_id],
            data_references=list(self.data_references),
            schema_version=self.schema_version,
            payload=(self.payload if self.payload is not None else None),
            content_parts=list(self.content_parts),
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            run_id=self.run_id,
            idempotency_key=self.idempotency_key,
        )

    def add_data_reference(self, reference_uri: str) -> "Spore":
        """Return a new spore with an added data reference."""
        if reference_uri in self.data_references:
            return self
        return Spore(
            id=self.id,
            spore_type=self.spore_type,
            from_agent=self.from_agent,
            to_agent=self.to_agent,
            knowledge=(self.knowledge if self.knowledge is not None else None),
            created_at=self.created_at,
            expires_at=self.expires_at,
            priority=self.priority,
            reply_to=self.reply_to,
            metadata=(self.metadata if self.metadata is not None else {}),
            knowledge_references=list(self.knowledge_references),
            data_references=list(self.data_references) + [reference_uri],
            schema_version=self.schema_version,
            payload=(self.payload if self.payload is not None else None),
            content_parts=list(self.content_parts),
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            run_id=self.run_id,
            idempotency_key=self.idempotency_key,
        )

    def has_knowledge_references(self) -> bool:
        """Check if spore has knowledge references"""
        return len(self.knowledge_references) > 0

    def has_data_references(self) -> bool:
        """Check if spore has data references"""
        return len(self.data_references) > 0

    def has_any_references(self) -> bool:
        """Check if spore has any kind of references"""
        return self.has_knowledge_references() or self.has_data_references()

    def get_spore_size_estimate(self) -> int:
        """Estimate spore size for lightweight transmission"""
        try:
            knowledge_size = _estimate_payload_size_bytes(self.knowledge or {})
            metadata_size = _estimate_payload_size_bytes(self.metadata or {})
            refs_size = _estimate_payload_size_bytes(
                list(self.knowledge_references or []) + list(self.data_references or [])
            )
            content_size = _estimate_payload_size_bytes(self.content_parts or [])
            overhead = 500
            return knowledge_size + metadata_size + refs_size + content_size + overhead
        except Exception:
            return len(self.to_json())

    def to_amqp_message(self) -> "aio_pika.Message":
        """
        Convert Spore to AMQP message with metadata in headers.

        Design:
        - Body: Knowledge payload (JSON serialized)
        - Headers: Spore metadata (spore_id, type, from_agent, etc.)
        - Properties: AMQP message properties (priority, TTL, etc.)

        This makes Spore the native AMQP format, eliminating intermediate conversions.

        Returns:
            aio_pika.Message: AMQP message ready for publication

        Raises:
            ImportError: If aio-pika is not installed
        """
        try:
            import aio_pika
        except ImportError:
            raise ImportError("aio-pika package required for AMQP serialization")

        knowledge_bytes = json.dumps(self._transport_body_payload()).encode("utf-8")

        # Build AMQP headers with spore metadata
        headers = {
            "spore_id": self.id,
            "spore_type": self.spore_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent or "",
            "created_at": self.created_at.isoformat(),
            "expires_at": (self.expires_at.isoformat() if self.expires_at else ""),
            "priority": str(self.priority),
            "reply_to": (self.reply_to or ""),
            "version": self.schema_version,
            "correlation_id": self.correlation_id or "",
            "causation_id": self.causation_id or "",
            "trace_id": self.trace_id or "",
            "run_id": self.run_id or "",
            "idempotency_key": self.idempotency_key or "",
        }

        # Calculate TTL in milliseconds (if expires_at is set)
        expiration_ms = None
        if self.expires_at:
            ttl_seconds = (self.expires_at - datetime.now()).total_seconds()
            if ttl_seconds > 0:
                expiration_ms = int(ttl_seconds * 1000)

        # Create AMQP message with properties
        return aio_pika.Message(
            body=knowledge_bytes,
            headers=headers,
            message_id=self.id,
            timestamp=self.created_at,
            priority=min(max(self.priority, 0), 255),  # AMQP priority range 0-255
            expiration=expiration_ms,  # TTL in milliseconds
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )

    @classmethod
    def from_amqp_message(cls, amqp_msg: "aio_pika.Message") -> "Spore":
        """
        Create Spore directly from AMQP message.

        Reconstructs a Spore object from AMQP message headers and body,
        with zero intermediate conversions (AMQP message directly becomes Spore).

        Args:
            amqp_msg: aio_pika.Message from AMQP broker

        Returns:
            Spore: Reconstructed spore object with all metadata

        Raises:
            ImportError: If aio-pika is not installed
            ValueError: If required spore headers are missing
        """
        try:
            __import__("aio_pika")
        except ImportError:
            raise ImportError("aio-pika package required for AMQP deserialization")

        headers = amqp_msg.headers or {}

        # Parse knowledge from message body
        try:
            decoded_body = json.loads(amqp_msg.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fallback if body is not valid JSON
            decoded_body = {
                "raw_content": amqp_msg.body.decode("utf-8", errors="replace")
            }

        is_envelope = (
            isinstance(decoded_body, dict)
            and decoded_body.get("_praval_spore_envelope") == "2.0"
        )
        if is_envelope:
            knowledge = decoded_body.get("knowledge")
            payload = decoded_body.get("payload")
            metadata = decoded_body.get("metadata") or {}
            content_parts = decoded_body.get("content_parts") or []
            knowledge_references = decoded_body.get("knowledge_references") or []
            data_references = decoded_body.get("data_references") or []
        else:
            knowledge = decoded_body
            payload = knowledge if isinstance(knowledge, dict) else None
            metadata = {}
            content_parts = []
            knowledge_references = []
            data_references = []

        # Parse expires_at timestamp
        expires_at = None
        if headers.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(headers["expires_at"])
            except (ValueError, TypeError):
                expires_at = None

        # Parse created_at timestamp
        created_at = datetime.now()
        if headers.get("created_at"):
            try:
                created_at = datetime.fromisoformat(headers["created_at"])
            except (ValueError, TypeError):
                created_at = datetime.now()
        elif amqp_msg.timestamp:
            created_at = amqp_msg.timestamp

        # Reconstruct Spore from headers
        return cls(
            id=headers.get("spore_id", amqp_msg.message_id or str(uuid.uuid4())),
            spore_type=SporeType(headers.get("spore_type", "knowledge")),
            from_agent=headers.get("from_agent", "unknown"),
            to_agent=(headers.get("to_agent") or None),
            knowledge=knowledge,
            created_at=created_at,
            expires_at=expires_at,
            priority=int(headers.get("priority", 5)),
            reply_to=(headers.get("reply_to") or None),
            metadata=metadata,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=headers.get("version", "1.0"),
            payload=payload,
            content_parts=content_parts,
            correlation_id=(headers.get("correlation_id") or None),
            causation_id=(headers.get("causation_id") or None),
            trace_id=(headers.get("trace_id") or None),
            run_id=(headers.get("run_id") or None),
            idempotency_key=(headers.get("idempotency_key") or None),
        )


class _ResponseWaiter:
    """Thread-safe state shared by synchronous and asynchronous response waits."""

    def __init__(
        self,
        request: Spore,
        channel: str,
        handler: Callable[[Spore], None],
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.request = request
        self.channel = channel
        self.handler = handler
        self.messages: Deque[Spore] = deque()
        self.condition = threading.Condition()
        self.error: Optional[BaseException] = None
        self.active = True
        self.backend_handle: Any = None
        self.loop = loop
        self.async_event = asyncio.Event() if loop is not None else None

    def deliver(self, spore: Spore) -> None:
        """Queue a matched spore and wake the owning waiter."""
        with self.condition:
            if not self.active:
                return
            self.messages.append(spore)
            self.condition.notify_all()
        self._wake_async()

    def fail(self, error: BaseException) -> None:
        """Wake the waiter with an error."""
        with self.condition:
            if not self.active:
                return
            self.error = error
            self.condition.notify_all()
        self._wake_async()

    def close(self) -> None:
        """Prevent any later delivery to this waiter."""
        with self.condition:
            self.active = False
            self.condition.notify_all()
        self._wake_async()

    def _wake_async(self) -> None:
        if (
            self.loop is not None
            and self.async_event is not None
            and not self.loop.is_closed()
        ):
            self.loop.call_soon_threadsafe(self.async_event.set)


class SubscriptionManager:
    """Manage subscriber handlers for a channel."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()

    def set_handler(self, agent_name: str, handler: Callable) -> None:
        with self._lock:
            self._subscribers[agent_name] = [handler]

    def add_handler(self, agent_name: str, handler: Callable) -> None:
        with self._lock:
            self._subscribers[agent_name].append(handler)

    def remove_agent(self, agent_name: str) -> None:
        with self._lock:
            if agent_name in self._subscribers:
                del self._subscribers[agent_name]

    def remove_handler(self, agent_name: str, handler: Callable) -> None:
        """Remove one handler without disturbing the agent's other subscribers."""
        with self._lock:
            handlers = self._subscribers.get(agent_name)
            if not handlers:
                return
            self._subscribers[agent_name] = [
                existing for existing in handlers if existing is not handler
            ]
            if not self._subscribers[agent_name]:
                del self._subscribers[agent_name]

    def get_handlers(self, agent_name: str) -> List[Callable]:
        with self._lock:
            return list(self._subscribers.get(agent_name, []))

    def iter_broadcast(self, exclude_agent: Optional[str] = None):
        with self._lock:
            subscribers = [
                (agent_name, list(handlers))
                for agent_name, handlers in self._subscribers.items()
                if not exclude_agent or agent_name != exclude_agent
            ]
        yield from subscribers

    def counts(self) -> Dict[str, int]:
        with self._lock:
            return {name: len(handlers) for name, handlers in self._subscribers.items()}


class ReefChannel:
    _shared_async_loop = None
    _shared_async_thread = None
    _shared_async_loop_ready = threading.Event()
    _shared_async_lock = threading.Lock()
    _shared_async_users = 0

    """
    A message channel within the reef.

    Like channels in a coral reef, they:
    - Have directional flow patterns
    - Can carry multiple spores simultaneously
    - Have capacity limits (to prevent overwhelming)
    - Can experience turbulence (message loss/delays)
    """

    def __init__(
        self,
        name: str,
        max_capacity: int = 1000,
        max_workers: int = 4,
        executor: Optional[ThreadPoolExecutor] = None,
        batch_size: int = 1,
    ):
        self.name = name
        self.max_capacity = max_capacity
        self.spores: deque = deque(maxlen=max_capacity)
        self._subscriptions = SubscriptionManager()
        # Backward-compat alias for direct access
        self.subscribers = self._subscriptions._subscribers
        self.lock = threading.RLock()
        self.executor = executor or ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=f"reef-{name}"
        )
        self._owns_executor = executor is None
        self._shutdown = False
        self._shutdown_result: Optional[bool] = None
        self._active_futures: List[Future] = []  # Track active handler executions
        self._futures_lock = threading.Lock()
        self._async_loop = None
        self._async_thread = None
        self._async_loop_ready = threading.Event()
        self._uses_shared_async_loop = True
        self._shared_async_registered = False
        self.batch_size = max(1, batch_size)
        self.stats = {
            "spores_carried": 0,
            "spores_delivered": 0,
            "spores_expired": 0,
            "created_at": datetime.now(),
        }

    def _ensure_async_handler_loop(self) -> None:
        if self._uses_shared_async_loop:
            if (
                ReefChannel._shared_async_loop
                and ReefChannel._shared_async_loop.is_running()
            ):
                self._async_loop = ReefChannel._shared_async_loop
                if not self._shared_async_registered:
                    ReefChannel._shared_async_users += 1
                    self._shared_async_registered = True
                return

            with ReefChannel._shared_async_lock:
                if (
                    ReefChannel._shared_async_loop
                    and ReefChannel._shared_async_loop.is_running()
                ):
                    self._async_loop = ReefChannel._shared_async_loop
                else:

                    def _run_loop():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        ReefChannel._shared_async_loop = loop
                        ReefChannel._shared_async_loop_ready.set()
                        loop.run_forever()
                        loop.close()

                    ReefChannel._shared_async_loop_ready.clear()
                    ReefChannel._shared_async_thread = threading.Thread(
                        target=_run_loop, daemon=True
                    )
                    ReefChannel._shared_async_thread.start()
                    ReefChannel._shared_async_loop_ready.wait(timeout=5)
                    self._async_loop = ReefChannel._shared_async_loop

            if not self._shared_async_registered:
                ReefChannel._shared_async_users += 1
                self._shared_async_registered = True
            return

        if self._async_loop and self._async_loop.is_running():
            return

        def _run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._async_loop = loop
            self._async_loop_ready.set()
            loop.run_forever()
            loop.close()

        self._async_loop_ready.clear()
        self._async_thread = threading.Thread(target=_run_loop, daemon=True)
        self._async_thread.start()
        self._async_loop_ready.wait(timeout=5)

    @classmethod
    def _shutdown_shared_async_loop(cls) -> None:
        if cls._shared_async_loop and cls._shared_async_loop.is_running():
            cls._shared_async_loop.call_soon_threadsafe(cls._shared_async_loop.stop)
            if cls._shared_async_thread and cls._shared_async_thread.is_alive():
                cls._shared_async_thread.join(timeout=5.0)
        cls._shared_async_loop = None
        cls._shared_async_thread = None
        cls._shared_async_loop_ready = threading.Event()
        cls._shared_async_users = 0

    def send_spore(self, spore: Spore) -> bool:
        """Send a spore through this channel."""
        with self.lock:
            if len(self.spores) >= self.max_capacity:
                # Channel at capacity - oldest spores drift away
                self.spores.popleft()

            self.spores.append(spore)
            self.stats["spores_carried"] += 1

            # Immediately try to deliver to subscribers
            self._deliver_spore(spore)
            return True

    def _deliver_spore(self, spore: Spore) -> List[Future]:
        """Deliver spore to subscribed agents asynchronously."""
        if spore.is_expired():
            self.stats["spores_expired"] += 1
            return []

        if self._shutdown:
            return []

        futures = []

        # Deliver to specific agent if targeted
        if spore.to_agent:
            handlers = self._subscriptions.get_handlers(spore.to_agent)
            if handlers:
                if self.batch_size > 1:
                    for i in range(0, len(handlers), self.batch_size):
                        future = self._execute_handlers_batch(
                            handlers[i : i + self.batch_size], spore
                        )
                        if future:
                            futures.append(future)
                else:
                    for handler in handlers:
                        future = self._execute_handler_async(handler, spore)
                        if future:
                            futures.append(future)

        # Deliver broadcasts to all subscribers except sender
        elif spore.spore_type == SporeType.BROADCAST:
            for agent_name, handlers in self._subscriptions.iter_broadcast(
                exclude_agent=spore.from_agent
            ):
                handler_list = list(handlers)
                if self.batch_size > 1:
                    for i in range(0, len(handler_list), self.batch_size):
                        future = self._execute_handlers_batch(
                            handler_list[i : i + self.batch_size], spore
                        )
                        if future:
                            futures.append(future)
                else:
                    for handler in handler_list:
                        future = self._execute_handler_async(handler, spore)
                        if future:
                            futures.append(future)

        return futures

    def _execute_handlers_batch(
        self, handlers: List[Callable], spore: Spore
    ) -> Optional[Future]:
        if self._shutdown:
            return None

        def batch_wrapper():
            for handler in handlers:
                try:
                    if inspect.iscoroutinefunction(handler):
                        self._ensure_async_handler_loop()
                        if not self._async_loop or not self._async_loop.is_running():
                            raise RuntimeError("Async handler loop not available")
                        future = asyncio.run_coroutine_threadsafe(
                            handler(spore), self._async_loop
                        )
                        future.result()
                    else:
                        handler(spore)
                    self.stats["spores_delivered"] += 1
                except Exception as e:
                    logger.warning(f"Agent handler error in channel {self.name}: {e}")
            return None

        future = self.executor.submit(batch_wrapper)
        with self._futures_lock:
            self._active_futures.append(future)
        return future

    def _execute_handler_async(
        self, handler: Callable, spore: Spore
    ) -> Optional[Future]:
        """Execute handler asynchronously, supporting both sync and async handlers."""
        if self._shutdown:
            return None
        if getattr(handler, "_praval_response_waiter", False):
            future: Future = Future()
            try:
                future.set_result(handler(spore))
                self.stats["spores_delivered"] += 1
            except BaseException as exc:
                future.set_exception(exc)
            return future

        def safe_handler_wrapper():
            try:
                # Check if handler is async
                if inspect.iscoroutinefunction(handler):
                    # Run async handler on a shared loop
                    self._ensure_async_handler_loop()
                    if not self._async_loop or not self._async_loop.is_running():
                        raise RuntimeError("Async handler loop not available")
                    future = asyncio.run_coroutine_threadsafe(
                        handler(spore), self._async_loop
                    )
                    result = future.result()
                    self.stats["spores_delivered"] += 1
                    return result
                else:
                    # Run sync handler directly
                    result = handler(spore)
                    self.stats["spores_delivered"] += 1
                    return result
            except Exception as e:
                # Log errors but don't break the system
                logger.warning(f"Agent handler error in channel {self.name}: {e}")
                return None

        future = self.executor.submit(safe_handler_wrapper)

        # Track the future for wait_for_completion()
        with self._futures_lock:
            self._active_futures.append(future)

        return future

    def subscribe(
        self, agent_name: str, handler: Callable[[Spore], None], replace: bool = True
    ) -> None:
        """
        Subscribe an agent to receive spores from this channel.

        Args:
            agent_name: Name of the agent subscribing
            handler: Callback function to handle received spores
            replace: If True (default), replaces existing handlers for this agent.
                    If False, adds handler to the list (useful for multiple handlers).

        Note:
            Default behavior (replace=True) ensures that re-registering an agent
            in interactive environments (like Jupyter notebooks) doesn't create
            duplicate subscriptions. Set replace=False if you intentionally want
            multiple handlers for the same agent.
        """
        if replace:
            self._subscriptions.set_handler(agent_name, handler)
        else:
            self._subscriptions.add_handler(agent_name, handler)

    def unsubscribe(
        self, agent_name: str, handler: Optional[Callable[[Spore], None]] = None
    ) -> None:
        """Unsubscribe an agent or one specific handler from this channel."""
        if handler is None:
            self._subscriptions.remove_agent(agent_name)
        else:
            self._subscriptions.remove_handler(agent_name, handler)

    def get_spores_for_agent(self, agent_name: str, limit: int = 10) -> List[Spore]:
        """Get recent spores for a specific agent (polling interface)."""
        with self.lock:
            relevant_spores = []
            for spore in reversed(self.spores):  # Most recent first
                if len(relevant_spores) >= limit:
                    break

                if spore.is_expired():
                    continue

                # Include if targeted to this agent or is a broadcast
                if spore.to_agent == agent_name or (
                    spore.spore_type == SporeType.BROADCAST
                    and spore.from_agent != agent_name
                ):
                    relevant_spores.append(spore)

            return relevant_spores

    def cleanup_expired(self) -> int:
        """Remove expired spores from the channel."""
        with self.lock:
            initial_count = len(self.spores)
            self.spores = deque(
                [s for s in self.spores if not s.is_expired()], maxlen=self.max_capacity
            )
            expired_count = initial_count - len(self.spores)
            self.stats["spores_expired"] += expired_count
            return expired_count

    def get_stats(self) -> Dict[str, Any]:
        """Get channel statistics."""
        with self.lock:
            return {
                "name": self.name,
                "spores_in_channel": len(self.spores),
                "max_capacity": self.max_capacity,
                "subscriber_count": sum(self._subscriptions.counts().values()),
                "active_threads": (
                    len(self.executor._threads)
                    if hasattr(self.executor, "_threads")
                    else 0
                ),
                "shutdown": self._shutdown,
                **self.stats,
            }

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all active handler executions to complete.

        This method blocks until all currently running and pending handlers finish,
        including handlers that spawn new handlers (cascading messages).

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if all handlers completed, False if timeout occurred.
        """
        from concurrent.futures import ALL_COMPLETED
        from concurrent.futures import wait as futures_wait

        start_time = time.time()

        while True:
            # Get current active futures
            with self._futures_lock:
                # Clean up completed futures
                self._active_futures = [f for f in self._active_futures if not f.done()]
                pending = list(self._active_futures)

            if not pending:
                return True

            # Calculate remaining timeout
            remaining_timeout = None
            if timeout is not None:
                elapsed = time.time() - start_time
                remaining_timeout = max(0, timeout - elapsed)
                if remaining_timeout <= 0:
                    return False

            # Wait for at least one future to complete
            try:
                futures_wait(
                    pending, timeout=remaining_timeout, return_when=ALL_COMPLETED
                )
            except Exception:
                pass

            # Check if we've timed out
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False

    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> bool:
        """
        Shutdown the channel's thread pool.

        Args:
            wait: Whether to wait for pending handlers to complete
            timeout: Maximum seconds to wait (only if wait=True)

        Returns:
            True if shutdown completed cleanly, False if timeout occurred
        """
        if self._shutdown:
            return bool(self._shutdown_result)

        self._shutdown = True

        if not wait:
            if self._owns_executor:
                self.executor.shutdown(wait=False)
            # Stop async handler loop
            if self._uses_shared_async_loop:
                if self._shared_async_registered:
                    ReefChannel._shared_async_users -= 1
                    self._shared_async_registered = False
                    if ReefChannel._shared_async_users <= 0:
                        ReefChannel._shutdown_shared_async_loop()
            else:
                if self._async_loop and self._async_loop.is_running():
                    self._async_loop.call_soon_threadsafe(self._async_loop.stop)
                    if self._async_thread and self._async_thread.is_alive():
                        self._async_thread.join(timeout=min(5.0, timeout))
            self._shutdown_result = True
            return self._shutdown_result

        # Cancel pending futures
        with self._futures_lock:
            for future in self._active_futures:
                if not future.done():
                    future.cancel()

        # Shutdown executor if owned
        if self._owns_executor:
            if sys.version_info >= (3, 9):
                self.executor.shutdown(wait=True, cancel_futures=True)
            else:
                self.executor.shutdown(wait=True)

        # Verify all futures completed within timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._futures_lock:
                pending = [f for f in self._active_futures if not f.done()]
            if not pending:
                # Stop async handler loop
                if self._uses_shared_async_loop:
                    if self._shared_async_registered:
                        ReefChannel._shared_async_users -= 1
                        self._shared_async_registered = False
                        if ReefChannel._shared_async_users <= 0:
                            ReefChannel._shutdown_shared_async_loop()
                else:
                    if self._async_loop and self._async_loop.is_running():
                        self._async_loop.call_soon_threadsafe(self._async_loop.stop)
                        if self._async_thread and self._async_thread.is_alive():
                            self._async_thread.join(timeout=min(5.0, timeout))
                self._shutdown_result = True
                return self._shutdown_result
            time.sleep(0.1)

        with self._futures_lock:
            pending = [f for f in self._active_futures if not f.done()]
        if pending:
            logger.warning(
                (
                    f"Channel {self.name} shutdown timed out with {len(pending)} "
                    f"pending handlers"
                )
            )
            # Stop async handler loop
            if self._async_loop and self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(self._async_loop.stop)
                if self._async_thread and self._async_thread.is_alive():
                    self._async_thread.join(timeout=min(5.0, timeout))
            self._shutdown_result = False
            return self._shutdown_result

        # Stop async handler loop
        if self._async_loop and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            if self._async_thread and self._async_thread.is_alive():
                self._async_thread.join(timeout=min(5.0, timeout))

        self._shutdown_result = True
        return self._shutdown_result


class ReefCore:
    """
    Core Reef implementation (transport and channel management).

    The Reef manages all communication channels and facilitates agent communication.

    Like a coral reef ecosystem, it:
    - Maintains multiple communication channels
    - Enables knowledge flow between polyps (agents)
    - Supports both direct and broadcast communication
    - Provides network health monitoring

    The Reef uses pluggable backends for transport:
    - InMemoryBackend: Local agent communication (default)
    - RabbitMQBackend: Distributed agent communication
    - Future: HTTP, gRPC, Kafka, etc.

    Agents work unchanged regardless of backend choice.

    Message Routing:
    - When using InMemoryBackend: Messages routed through local ReefChannel
    - When using RabbitMQBackend (or other distributed): Messages routed through backend
    """

    def __init__(
        self,
        default_max_workers: int = 4,
        backend=None,
        use_shared_pool: bool = True,
        auth_provider: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ):
        """
        Initialize Reef with optional backend.

        Args:
            default_max_workers: Thread workers per channel (InMemory only)
            backend: ReefBackend instance (defaults to InMemoryBackend)
            use_shared_pool: Share a single thread pool across channels
            auth_provider: Optional authorization callback (action, context) -> bool
        """
        self.channels: Dict[str, ReefChannel] = {}
        self.default_channel = "main"
        self.default_max_workers = default_max_workers
        self.use_shared_pool = use_shared_pool
        self._shared_executor = None
        self.broadcast_rate_limit_per_sec = None
        self._broadcast_counters = defaultdict(deque)
        self._broadcast_window_seconds = 1.0
        self.lock = threading.RLock()
        self._shutdown = False
        self._shutdown_result: Optional[bool] = None
        self.auth_provider = auth_provider
        self._response_waiters: Dict[str, _ResponseWaiter] = {}
        self._response_waiters_lock = threading.RLock()

        # Async loop for running backend coroutines from sync context
        self._async_loop = None
        self._async_thread = None
        self._async_loop_ready = threading.Event()
        self._uses_shared_async_loop = True
        self._shared_async_registered = False

        # Set backend (default to InMemory for backward compatibility)
        if backend is None:
            from .reef_backend import InMemoryBackend

            backend = InMemoryBackend()

        self.backend = backend
        self._backend_initialized = False

        if self.use_shared_pool:
            self._shared_executor = ThreadPoolExecutor(
                max_workers=self.default_max_workers
            )

        # Create default channel
        self.create_channel(self.default_channel)

        # Start background cleanup
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

    def _shutdown_async_loop(self) -> None:
        if self._async_loop and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            if self._async_thread and self._async_thread.is_alive():
                self._async_thread.join(timeout=5.0)
        self._async_loop = None
        self._async_thread = None

    def _authorize(self, action: str, context: Dict[str, Any]) -> None:
        if not self.auth_provider:
            return
        try:
            allowed = self.auth_provider(action, context)
        except Exception as e:
            raise PermissionError(f"Authorization error: {e}") from e
        if not allowed:
            raise PermissionError(f"Unauthorized action '{action}'")

    def _ensure_async_loop(self) -> None:
        if self._async_loop and self._async_loop.is_running():
            return

        def _run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._async_loop = loop
            self._async_loop_ready.set()
            loop.run_forever()
            loop.close()

        self._async_loop_ready.clear()
        self._async_thread = threading.Thread(target=_run_loop, daemon=True)
        self._async_thread.start()
        self._async_loop_ready.wait(timeout=5)

    def _is_distributed_backend(self) -> bool:
        """
        Check if the current backend is distributed (requires async message routing).

        Returns:
            True if using RabbitMQ or other distributed backend, False for InMemory.
        """
        from .reef_backend import InMemoryBackend

        return (
            not isinstance(self.backend, InMemoryBackend) and self._backend_initialized
        )

    def _run_async(self, coro):
        """
        Run an async coroutine from sync context.

        Handles the async/sync boundary for backends that require async operations.
        """
        try:
            _ = asyncio.get_running_loop()
            # We're already in an async context, create a task
            return asyncio.ensure_future(coro)
        except RuntimeError:
            # No running loop, use a persistent background loop
            self._ensure_async_loop()
            if not self._async_loop or not self._async_loop.is_running():
                raise RuntimeError("Async loop not available")
            future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
            return future.result()

    def create_channel(
        self,
        name: str,
        max_capacity: int = 1000,
        max_workers: Optional[int] = None,
        batch_size: int = 1,
    ) -> ReefChannel:
        """Create a new reef channel."""
        with self.lock:
            if name in self.channels:
                return self.channels[name]

            workers = max_workers or self.default_max_workers
            executor = self._shared_executor if self.use_shared_pool else None
            channel = ReefChannel(
                name, max_capacity, workers, executor=executor, batch_size=batch_size
            )
            self.channels[name] = channel
            return channel

    def get_channel(self, name: str) -> Optional[ReefChannel]:
        """Get a reef channel by name."""
        return self.channels.get(name)

    async def initialize_backend(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Reef backend (async operation for distributed backends).

        Call this method to set up distributed backends like RabbitMQ.
        InMemoryBackend initializes immediately, so this is optional for local usage.

        Args:
            config: Backend-specific configuration (passed to backend.initialize())
        """
        if not self._backend_initialized:
            await self.backend.initialize(config or {})
            self._backend_initialized = True
            logger.info(f"Reef backend initialized: {self.backend.__class__.__name__}")

    async def close_backend(self) -> None:
        """Shutdown the backend (async operation for distributed backends)."""
        if self._backend_initialized:
            await self.backend.shutdown()
            self._backend_initialized = False
            logger.info(f"Reef backend shutdown: {self.backend.__class__.__name__}")

    @staticmethod
    def _expiration_time(
        expires_in_seconds: Optional[float],
        expires_at: Optional[datetime],
    ) -> Optional[datetime]:
        if expires_at is not None:
            return expires_at
        if not expires_in_seconds:
            return None
        return datetime.now() + timedelta(seconds=expires_in_seconds)

    def _create_spore(
        self,
        from_agent: str,
        to_agent: Optional[str],
        knowledge: Optional[Dict[str, Any]],
        spore_type: SporeType,
        *,
        priority: int = 5,
        expires_in_seconds: Optional[float] = None,
        expires_at: Optional[datetime] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: str = "1.0",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Spore:
        return Spore(
            id=str(uuid.uuid4()),
            spore_type=spore_type,
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge=knowledge,
            created_at=datetime.now(),
            expires_at=self._expiration_time(expires_in_seconds, expires_at),
            priority=priority,
            reply_to=reply_to,
            metadata=metadata,
            knowledge_references=list(knowledge_references or []),
            data_references=list(data_references or []),
            schema_version=schema_version,
            payload=payload,
            content_parts=list(content_parts or []),
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )

    def send_spore(self, spore: Spore, channel: str = None) -> str:
        """Route an existing spore through authorization and the active backend."""
        if spore.is_expired():
            raise ValueError(f"Spore '{spore.id}' is already expired")

        if channel is None:
            channel = self.default_channel

        self._authorize(
            "send",
            {
                "from_agent": spore.from_agent,
                "to_agent": spore.to_agent,
                "channel": channel,
                "spore_type": spore.spore_type.value,
            },
        )

        reef_channel = self.get_channel(channel)
        if not reef_channel:
            raise ValueError(f"Reef channel '{channel}' not found")

        if self._is_distributed_backend():
            logger.debug(
                (
                    f"Routing spore {spore.id} through distributed backend to "
                    f"channel: {channel}"
                )
            )
            self._run_async(self.backend.send(spore, channel))
        else:
            reef_channel.send_spore(spore)
        return spore.id

    def send(
        self,
        from_agent: str,
        to_agent: Optional[str],
        knowledge: Dict[str, Any],
        spore_type: SporeType = SporeType.KNOWLEDGE,
        channel: str = None,
        priority: int = 5,
        expires_in_seconds: Optional[int] = None,
        reply_to: Optional[str] = None,
        knowledge_references: Optional[List[str]] = None,
        auto_reference_large_knowledge: bool = True,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: str = "1.0",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> str:
        """Send a spore through the reef."""

        if channel is None:
            channel = self.default_channel

        # Auto-reference large knowledge if enabled
        if auto_reference_large_knowledge and knowledge:
            knowledge_size = _estimate_payload_size_bytes(knowledge)
            if knowledge_size > 1000:  # Threshold for large knowledge
                # TODO: Store knowledge and replace with reference
                # This would require access to a memory manager
                logger.debug(
                    (
                        f"Large knowledge detected ({knowledge_size} bytes) - "
                        f"consider using references"
                    )
                )

        spore = self._create_spore(
            from_agent,
            to_agent,
            knowledge,
            spore_type,
            priority=priority,
            expires_in_seconds=expires_in_seconds,
            expires_at=expires_at,
            reply_to=reply_to,
            metadata=metadata,
            payload=payload,
            content_parts=content_parts,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=schema_version,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        return self.send_spore(spore, channel)

    def _check_broadcast_rate_limit(self, from_agent: str) -> None:
        if not self.broadcast_rate_limit_per_sec:
            return

        now = time.time()
        window_start = now - self._broadcast_window_seconds
        counter = self._broadcast_counters[from_agent]
        while counter and counter[0] < window_start:
            counter.popleft()

        if len(counter) >= self.broadcast_rate_limit_per_sec:
            raise RuntimeError(
                f"Broadcast rate limit exceeded for {from_agent}: "
                f"{self.broadcast_rate_limit_per_sec}/sec"
            )

        counter.append(now)

    def broadcast(
        self, from_agent: str, knowledge: Dict[str, Any], channel: str = None
    ) -> str:
        """Broadcast knowledge to all agents in the reef."""
        self._check_broadcast_rate_limit(from_agent)
        self._authorize("broadcast", {"from_agent": from_agent, "channel": channel})
        return self.send(
            from_agent=from_agent,
            to_agent=None,
            knowledge=knowledge,
            spore_type=SporeType.BROADCAST,
            channel=channel,
        )

    def system_broadcast(self, knowledge: Dict[str, Any], channel: str = None) -> str:
        """Broadcast system-level messages to all agents in a channel."""
        return self.broadcast(from_agent="system", knowledge=knowledge, channel=channel)

    def request(
        self,
        from_agent: str,
        to_agent: str,
        request: Dict[str, Any],
        channel: str = None,
        expires_in_seconds: int = 300,
        *,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: str = "1.0",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> str:
        """Send a knowledge request to another agent."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge=request,
            spore_type=SporeType.REQUEST,
            channel=channel,
            priority=priority,
            expires_in_seconds=expires_in_seconds,
            metadata=metadata,
            payload=payload,
            content_parts=content_parts,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=schema_version,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )

    def reply(
        self,
        from_agent: str,
        to_agent: str,
        response: Dict[str, Any],
        reply_to_spore_id: str,
        channel: str = None,
        *,
        priority: int = 5,
        expires_in_seconds: Optional[float] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: str = "1.0",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Reply to a knowledge request."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge=response,
            spore_type=SporeType.RESPONSE,
            channel=channel,
            priority=priority,
            expires_in_seconds=expires_in_seconds,
            expires_at=expires_at,
            reply_to=reply_to_spore_id,
            metadata=metadata,
            payload=payload,
            content_parts=content_parts,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=schema_version,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _response_matches(request: Spore, candidate: Spore) -> bool:
        if request.is_expired() or candidate.is_expired():
            return False
        if candidate.spore_type not in (
            SporeType.RESPONSE,
            SporeType.NOTIFICATION,
        ):
            return False
        if candidate.reply_to != request.id:
            return False
        if candidate.from_agent != request.to_agent:
            return False
        if candidate.to_agent != request.from_agent:
            return False
        exact_fields = (
            "correlation_id",
            "trace_id",
            "run_id",
            "idempotency_key",
        )
        if any(
            getattr(candidate, field) != getattr(request, field)
            for field in exact_fields
        ):
            return False
        return candidate.causation_id in (None, request.id)

    def _new_response_waiter(
        self,
        request: Spore,
        channel: str,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> _ResponseWaiter:
        waiter: _ResponseWaiter

        def response_handler(candidate: Spore) -> None:
            with self._response_waiters_lock:
                is_active = self._response_waiters.get(request.id) is waiter
            if is_active and self._response_matches(request, candidate):
                waiter.deliver(candidate)

        response_handler._praval_response_waiter = True  # type: ignore[attr-defined]
        waiter = _ResponseWaiter(request, channel, response_handler, loop=loop)
        with self._response_waiters_lock:
            self._response_waiters[request.id] = waiter
        return waiter

    def _register_response_waiter(self, waiter: _ResponseWaiter) -> None:
        self._authorize(
            "subscribe",
            {"agent_name": waiter.request.from_agent, "channel": waiter.channel},
        )
        try:
            if self._is_distributed_backend():
                subscribe_handler = getattr(self.backend, "subscribe_handler", None)
                if subscribe_handler is None:
                    raise RuntimeError(
                        "The configured Reef backend does not support precise "
                        "response subscriptions required by request_and_wait()"
                    )
                waiter.backend_handle = self._run_async(
                    subscribe_handler(
                        f"agent.{waiter.request.from_agent}", waiter.handler
                    )
                )
            else:
                reef_channel = self.get_channel(waiter.channel)
                if not reef_channel:
                    raise ValueError(f"Reef channel '{waiter.channel}' not found")
                reef_channel.subscribe(
                    waiter.request.from_agent, waiter.handler, replace=False
                )
        except BaseException:
            self._discard_response_waiter(waiter)
            raise

    async def _aregister_response_waiter(self, waiter: _ResponseWaiter) -> None:
        self._authorize(
            "subscribe",
            {"agent_name": waiter.request.from_agent, "channel": waiter.channel},
        )
        try:
            if self._is_distributed_backend():
                subscribe_handler = getattr(self.backend, "subscribe_handler", None)
                if subscribe_handler is None:
                    raise RuntimeError(
                        "The configured Reef backend does not support precise "
                        "response subscriptions required by arequest_and_wait()"
                    )
                waiter.backend_handle = await subscribe_handler(
                    f"agent.{waiter.request.from_agent}", waiter.handler
                )
            else:
                reef_channel = self.get_channel(waiter.channel)
                if not reef_channel:
                    raise ValueError(f"Reef channel '{waiter.channel}' not found")
                reef_channel.subscribe(
                    waiter.request.from_agent, waiter.handler, replace=False
                )
        except BaseException:
            await self._adiscard_response_waiter(waiter)
            raise

    def _discard_response_waiter(self, waiter: _ResponseWaiter) -> None:
        with self._response_waiters_lock:
            if self._response_waiters.get(waiter.request.id) is waiter:
                del self._response_waiters[waiter.request.id]
        waiter.close()
        if waiter.backend_handle is not None:
            unsubscribe_handler = getattr(self.backend, "unsubscribe_handler", None)
            if unsubscribe_handler is not None:
                self._run_async(unsubscribe_handler(waiter.backend_handle))
        else:
            reef_channel = self.get_channel(waiter.channel)
            if reef_channel:
                reef_channel.unsubscribe(waiter.request.from_agent, waiter.handler)

    async def _adiscard_response_waiter(self, waiter: _ResponseWaiter) -> None:
        with self._response_waiters_lock:
            if self._response_waiters.get(waiter.request.id) is waiter:
                del self._response_waiters[waiter.request.id]
        waiter.close()
        if waiter.backend_handle is not None:
            unsubscribe_handler = getattr(self.backend, "unsubscribe_handler", None)
            if unsubscribe_handler is not None:
                await unsubscribe_handler(waiter.backend_handle)
        else:
            reef_channel = self.get_channel(waiter.channel)
            if reef_channel:
                reef_channel.unsubscribe(waiter.request.from_agent, waiter.handler)

    def _waiter_next(self, waiter: _ResponseWaiter, deadline: Optional[float]) -> Spore:
        with waiter.condition:
            while not waiter.messages:
                if waiter.error is not None:
                    raise waiter.error
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                if remaining == 0.0:
                    raise TimeoutError(f"Reef request {waiter.request.id} timed out")
                waiter.condition.wait(remaining)
            return waiter.messages.popleft()

    async def _await_waiter_next(
        self, waiter: _ResponseWaiter, deadline: Optional[float]
    ) -> Spore:
        if waiter.async_event is None:
            raise RuntimeError("Async waiter event is not available")
        while True:
            with waiter.condition:
                if waiter.messages:
                    return waiter.messages.popleft()
                if waiter.error is not None:
                    raise waiter.error
                waiter.async_event.clear()
            remaining = (
                None if deadline is None else max(0.0, deadline - time.monotonic())
            )
            if remaining == 0.0:
                raise TimeoutError(f"Reef request {waiter.request.id} timed out")
            try:
                if remaining is None:
                    await waiter.async_event.wait()
                else:
                    await asyncio.wait_for(waiter.async_event.wait(), remaining)
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"Reef request {waiter.request.id} timed out"
                ) from exc

    @staticmethod
    def _wait_deadline(timeout: Optional[float], request: Spore) -> Optional[float]:
        durations: List[float] = []
        if timeout is not None:
            durations.append(max(0.0, timeout))
        if request.expires_at is not None:
            durations.append(
                max(0.0, (request.expires_at - datetime.now()).total_seconds())
            )
        if not durations:
            return None
        return time.monotonic() + min(durations)

    def request_and_wait(
        self,
        from_agent: str,
        to_agent: str,
        request: Dict[str, Any],
        channel: str = None,
        expires_in_seconds: int = 300,
        timeout: Optional[float] = 30.0,
        *,
        on_notification: Optional[Callable[[Spore], Any]] = None,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: str = "1.0",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Spore:
        """Send a request and block for its strictly matched final response."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "request_and_wait() cannot run inside an active event loop; "
                "use arequest_and_wait() instead"
            )

        channel = channel or self.default_channel
        request_spore = self._create_spore(
            from_agent,
            to_agent,
            request,
            SporeType.REQUEST,
            priority=priority,
            expires_in_seconds=expires_in_seconds,
            expires_at=expires_at,
            metadata=metadata,
            payload=payload,
            content_parts=content_parts,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=schema_version,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        waiter = self._new_response_waiter(request_spore, channel)
        try:
            self._register_response_waiter(waiter)
            self.send_spore(request_spore, channel)
            deadline = self._wait_deadline(timeout, request_spore)
            while True:
                candidate = self._waiter_next(waiter, deadline)
                if candidate.spore_type is SporeType.NOTIFICATION:
                    if on_notification is not None:
                        result = on_notification(candidate)
                        if inspect.isawaitable(result):
                            self._run_async(result)
                    continue
                return candidate
        finally:
            self._discard_response_waiter(waiter)

    async def arequest_and_wait(
        self,
        from_agent: str,
        to_agent: str,
        request: Dict[str, Any],
        channel: str = None,
        expires_in_seconds: int = 300,
        timeout: Optional[float] = 30.0,
        *,
        on_notification: Optional[Callable[[Spore], Any]] = None,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: str = "1.0",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Spore:
        """Asynchronously send a request and await its matched final response."""
        channel = channel or self.default_channel
        request_spore = self._create_spore(
            from_agent,
            to_agent,
            request,
            SporeType.REQUEST,
            priority=priority,
            expires_in_seconds=expires_in_seconds,
            expires_at=expires_at,
            metadata=metadata,
            payload=payload,
            content_parts=content_parts,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=schema_version,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        loop = asyncio.get_running_loop()
        waiter = self._new_response_waiter(request_spore, channel, loop=loop)
        try:
            await self._aregister_response_waiter(waiter)
            if self._is_distributed_backend():
                if request_spore.is_expired():
                    raise ValueError(f"Spore '{request_spore.id}' is already expired")
                self._authorize(
                    "send",
                    {
                        "from_agent": request_spore.from_agent,
                        "to_agent": request_spore.to_agent,
                        "channel": channel,
                        "spore_type": request_spore.spore_type.value,
                    },
                )
                await self.backend.send(request_spore, channel)
            else:
                self.send_spore(request_spore, channel)
            deadline = self._wait_deadline(timeout, request_spore)
            while True:
                candidate = await self._await_waiter_next(waiter, deadline)
                if candidate.spore_type is SporeType.NOTIFICATION:
                    if on_notification is not None:
                        result = on_notification(candidate)
                        if inspect.isawaitable(result):
                            await result
                    continue
                return candidate
        finally:
            await self._adiscard_response_waiter(waiter)

    @staticmethod
    def _bounded_expiry(
        request: Spore,
        expires_in_seconds: Optional[float] = None,
        expires_at: Optional[datetime] = None,
    ) -> Optional[datetime]:
        candidate = expires_at
        if candidate is None and expires_in_seconds is not None:
            candidate = datetime.now() + timedelta(seconds=expires_in_seconds)
        if request.expires_at is None:
            return candidate
        if candidate is None:
            return request.expires_at
        return min(candidate, request.expires_at)

    def _send_derived_response(
        self,
        request_spore: Spore,
        knowledge: Dict[str, Any],
        spore_type: SporeType,
        *,
        channel: str = None,
        priority: Optional[int] = None,
        expires_in_seconds: Optional[float] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: Optional[str] = None,
    ) -> str:
        if request_spore.to_agent is None:
            raise ValueError("Cannot derive a direct response from a broadcast")
        response_spore = self._create_spore(
            request_spore.to_agent,
            request_spore.from_agent,
            knowledge,
            spore_type,
            priority=request_spore.priority if priority is None else priority,
            expires_at=self._bounded_expiry(
                request_spore, expires_in_seconds, expires_at
            ),
            reply_to=request_spore.id,
            metadata=metadata,
            payload=payload,
            content_parts=content_parts,
            knowledge_references=knowledge_references,
            data_references=data_references,
            schema_version=schema_version or request_spore.schema_version,
            correlation_id=request_spore.correlation_id,
            causation_id=request_spore.id,
            trace_id=request_spore.trace_id,
            run_id=request_spore.run_id,
            idempotency_key=request_spore.idempotency_key,
        )
        return self.send_spore(response_spore, channel)

    def reply_to_request(
        self,
        request_spore: Spore,
        response: Dict[str, Any],
        **options: Any,
    ) -> str:
        """Reply with lifecycle fields derived from the originating request."""
        return self._send_derived_response(
            request_spore, response, SporeType.RESPONSE, **options
        )

    def notify_request(
        self,
        request_spore: Spore,
        notification: Dict[str, Any],
        **options: Any,
    ) -> str:
        """Send a correlated progress notification for an active request."""
        return self._send_derived_response(
            request_spore, notification, SporeType.NOTIFICATION, **options
        )

    def forward_request(
        self,
        request_spore: Spore,
        to_agent: str,
        request: Optional[Dict[str, Any]] = None,
        *,
        channel: str = None,
        priority: Optional[int] = None,
        expires_in_seconds: Optional[float] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_parts: Optional[List[Dict[str, Any]]] = None,
        knowledge_references: Optional[List[str]] = None,
        data_references: Optional[List[str]] = None,
        schema_version: Optional[str] = None,
    ) -> str:
        """Forward a request without extending its lifecycle."""
        if request_spore.to_agent is None:
            raise ValueError("Cannot forward a broadcast request")
        forwarded = self._create_spore(
            request_spore.to_agent,
            to_agent,
            request_spore.knowledge if request is None else request,
            SporeType.REQUEST,
            priority=request_spore.priority if priority is None else priority,
            expires_at=self._bounded_expiry(
                request_spore, expires_in_seconds, expires_at
            ),
            metadata=request_spore.metadata if metadata is None else metadata,
            payload=request_spore.payload if payload is None else payload,
            content_parts=(
                request_spore.content_parts if content_parts is None else content_parts
            ),
            knowledge_references=(
                request_spore.knowledge_references
                if knowledge_references is None
                else knowledge_references
            ),
            data_references=(
                request_spore.data_references
                if data_references is None
                else data_references
            ),
            schema_version=schema_version or request_spore.schema_version,
            correlation_id=request_spore.correlation_id,
            causation_id=request_spore.id,
            trace_id=request_spore.trace_id,
            run_id=request_spore.run_id,
            idempotency_key=request_spore.idempotency_key,
        )
        return self.send_spore(forwarded, channel)

    def subscribe(
        self,
        agent_name: str,
        handler: Callable[[Spore], None],
        channel: str = None,
        replace: bool = True,
    ) -> None:
        """
        Subscribe an agent to receive spores from a channel.

        Args:
            agent_name: Name of the agent subscribing
            handler: Callback function to handle received spores
            channel: Channel name (uses default if None)
            replace: If True (default), replaces existing handlers for this agent.
                    If False, adds handler to the list.

        Note:
            For distributed backends (RabbitMQ, etc.), this also subscribes to
            the backend's message broker, enabling cross-process communication.
        """
        if channel is None:
            channel = self.default_channel

        self._authorize("subscribe", {"agent_name": agent_name, "channel": channel})

        reef_channel = self.get_channel(channel)
        if reef_channel:
            # Always register locally (needed for local message tracking)
            reef_channel.subscribe(agent_name, handler, replace=replace)

        # Also subscribe through distributed backend if active
        if self._is_distributed_backend():
            logger.debug(
                (
                    f"Subscribing agent '{agent_name}' to distributed backend "
                    f"channel: {channel}"
                )
            )
            self._run_async(self.backend.subscribe(channel, handler))

    def get_network_stats(self) -> Dict[str, Any]:
        """Get statistics about the reef network."""
        with self.lock:
            stats = {
                "total_channels": len(self.channels),
                "backend": self.backend.__class__.__name__,
                "backend_stats": self.backend.get_stats(),
                "channel_stats": {},
            }

            for name, channel in self.channels.items():
                stats["channel_stats"][name] = {
                    "active_spores": len(channel.spores),
                    "subscribers": len(channel.subscribers),
                    **channel.stats,
                }

            return stats

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all active agent handlers to complete across all channels.

        This method blocks until all currently running handlers finish,
        including cascading handlers triggered by broadcast() calls within agents.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if all handlers completed, False if timeout occurred.

        Example:
            start_agents(researcher, summarizer, initial_data={...})
            get_reef().wait_for_completion()  # Block until all agents done
            get_reef().shutdown()
        """
        start_time = time.time()

        for channel in self.channels.values():
            # Calculate remaining timeout for this channel
            remaining_timeout = None
            if timeout is not None:
                elapsed = time.time() - start_time
                remaining_timeout = max(0, timeout - elapsed)
                if remaining_timeout <= 0:
                    return False

            if not channel.wait_for_completion(timeout=remaining_timeout):
                return False

        return True

    def _cancel_response_waiters(self, reason: str) -> None:
        """Wake and remove all active response waiters."""
        with self._response_waiters_lock:
            waiters = list(self._response_waiters.values())
        for waiter in waiters:
            waiter.fail(ReefLifecycleError(reason))
            try:
                self._discard_response_waiter(waiter)
            except Exception as exc:
                logger.warning(
                    f"Error cleaning response waiter {waiter.request.id}: {exc}"
                )

    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> bool:
        """
        Shutdown the reef and all its channels.

        Args:
            wait: Whether to wait for pending handlers
            timeout: Maximum total seconds to wait across all channels

        Returns:
            True if all channels shut down cleanly, False if timeout occurred
        """
        if self._shutdown:
            return bool(self._shutdown_result)

        self._shutdown = True
        self._cancel_response_waiters("Reef shut down while waiting for a response")

        all_clean = True
        remaining_timeout = timeout

        # Shutdown all channels, distributing timeout
        for channel in self.channels.values():
            start = time.time()
            if not channel.shutdown(wait=wait, timeout=remaining_timeout):
                all_clean = False
            elapsed = time.time() - start
            remaining_timeout = max(0.1, remaining_timeout - elapsed)

        # Close backend
        try:
            self._run_async(self.close_backend())
        except Exception as e:
            logger.warning(f"Error closing backend: {e}")
            all_clean = False

        # Shutdown shared executor if owned
        if self.use_shared_pool and self._shared_executor:
            try:
                if sys.version_info >= (3, 9):
                    self._shared_executor.shutdown(wait=wait, cancel_futures=True)
                else:
                    self._shared_executor.shutdown(wait=wait)
            except Exception as e:
                logger.warning(f"Error shutting down shared executor: {e}")
                all_clean = False
            self._shared_executor = None

        # Stop async loop for backend operations
        self._shutdown_async_loop()

        # Wait for cleanup thread to finish if requested
        if wait and self.cleanup_thread.is_alive():
            cleanup_timeout = min(5.0, remaining_timeout)
            self.cleanup_thread.join(timeout=cleanup_timeout)
            if self.cleanup_thread.is_alive():
                logger.warning("Cleanup thread did not stop within timeout")
                all_clean = False

        self._shutdown_result = all_clean
        return self._shutdown_result

    def __del__(self):
        try:
            self.shutdown(wait=False)
        except Exception:
            pass

    def create_knowledge_reference_spore(
        self,
        from_agent: str,
        to_agent: Optional[str],
        knowledge_summary: str,
        knowledge_references: List[str],
        spore_type: SporeType = SporeType.KNOWLEDGE,
        channel: str = None,
    ) -> str:
        """
        Create a lightweight spore with knowledge references

        This follows the reef principle: "light spores travel far"
        """
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge={
                "type": "knowledge_reference",
                "summary": knowledge_summary,
                "reference_count": len(knowledge_references),
            },
            spore_type=spore_type,
            channel=channel,
            knowledge_references=knowledge_references,
            auto_reference_large_knowledge=False,  # Already handled
        )

    def resolve_knowledge_references(
        self, spore: Spore, memory_manager
    ) -> Dict[str, Any]:
        """
        Resolve knowledge references in a spore to actual knowledge

        Args:
            spore: The spore with knowledge references
            memory_manager: Agent's memory manager to resolve references

        Returns:
            Combined knowledge from references
        """
        if not spore.has_knowledge_references():
            return spore.knowledge

        resolved_knowledge = dict(spore.knowledge) if spore.knowledge else {}
        resolved_knowledge["referenced_knowledge"] = []

        for ref_id in spore.knowledge_references:
            try:
                memories = memory_manager.recall_by_id(ref_id)
                if memories:
                    resolved_knowledge["referenced_knowledge"].append(
                        {
                            "reference_id": ref_id,
                            "content": memories[0].content,
                            "metadata": memories[0].metadata,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to resolve knowledge reference {ref_id}: {e}")

        return resolved_knowledge

    def _cleanup_loop(self) -> None:
        """
        Background thread to clean up expired spores.

        Runs every 60 seconds. Logs errors instead of silently ignoring them.
        Uses interruptible sleep to respond quickly to shutdown signals.
        """
        while not self._shutdown:
            try:
                # Use interruptible sleep - check shutdown flag every second
                for _ in range(60):
                    if self._shutdown:
                        break
                    time.sleep(1)

                if not self._shutdown:
                    for channel in self.channels.values():
                        try:
                            expired = channel.cleanup_expired()
                            if expired > 0:
                                logger.debug(
                                    f"Cleaned up {expired} expired spores from "
                                    f"{channel.name}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Error cleaning up channel {channel.name}: {e}"
                            )
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Don't exit the loop on error, but add backoff to prevent tight loop
                time.sleep(5)


class Reef(ReefCore):
    """Facade for backwards-compatible Reef API."""

    pass


# Global reef instance
_global_reef = Reef()


def get_reef() -> Reef:
    """Get the global reef instance."""
    return _global_reef


def reset_reef() -> None:
    """
    Reset the global reef instance to a clean state.

    This is primarily used for testing to ensure test isolation.
    Clears all channels and reinitializes with just the default channel.
    """
    global _global_reef

    old_reef = _global_reef
    old_reef._cancel_response_waiters("Reef reset while waiting for a response")
    old_reef.shutdown(wait=False)
    _global_reef = Reef()
