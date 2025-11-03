"""
OpenTelemetry-compatible Span implementation.
"""

import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SpanKind(Enum):
    """OpenTelemetry Span Kind."""

    INTERNAL = "INTERNAL"
    CLIENT = "CLIENT"
    SERVER = "SERVER"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class SpanStatus(Enum):
    """OpenTelemetry Span Status."""

    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


@dataclass
class SpanEvent:
    """Event within a span."""

    name: str
    timestamp: int  # nanoseconds since epoch
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "attributes": self.attributes
        }


@dataclass
class Span:
    """OpenTelemetry-compatible Span.

    Represents a single operation in a distributed trace.

    Attributes:
        name: Span name (e.g., "agent.researcher.execute")
        trace_id: Trace identifier (32-char hex)
        span_id: Span identifier (16-char hex)
        parent_span_id: Parent span identifier (optional)
        kind: Span kind (INTERNAL, CLIENT, etc.)
        start_time: Start time in nanoseconds since epoch
        end_time: End time in nanoseconds since epoch (optional)
        attributes: Key-value attributes
        events: List of events within the span
        status: Span status (UNSET, OK, ERROR)
        status_message: Status description (optional)
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    kind: SpanKind = SpanKind.INTERNAL
    start_time: int = field(default_factory=lambda: time.time_ns())
    end_time: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    status: SpanStatus = SpanStatus.UNSET
    status_message: str = ""

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute.

        Args:
            key: Attribute key
            value: Attribute value
        """
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span.

        Args:
            name: Event name
            attributes: Event attributes (optional)
        """
        event = SpanEvent(
            name=name,
            timestamp=time.time_ns(),
            attributes=attributes or {}
        )
        self.events.append(event)

    def record_exception(self, exception: Exception) -> None:
        """Record an exception as a span event.

        Args:
            exception: Exception to record
        """
        self.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
            "exception.stacktrace": traceback.format_exc()
        })

    def set_status(self, status: str, message: str = "") -> None:
        """Set span status.

        Args:
            status: Status code ("ok", "error", "unset")
            message: Status message (optional)
        """
        status_upper = status.upper()
        if status_upper == "OK":
            self.status = SpanStatus.OK
        elif status_upper == "ERROR":
            self.status = SpanStatus.ERROR
        else:
            self.status = SpanStatus.UNSET

        self.status_message = message

    def end(self, end_time: Optional[int] = None) -> None:
        """End the span.

        Args:
            end_time: End time in nanoseconds (default: current time)
        """
        self.end_time = end_time or time.time_ns()

    def duration_ms(self) -> float:
        """Get span duration in milliseconds.

        Returns:
            Duration in milliseconds, or 0.0 if span not ended
        """
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time) / 1_000_000

    def is_recording(self) -> bool:
        """Check if span is still recording.

        Returns:
            True if span is recording (not ended)
        """
        return self.end_time is None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            # Record exception
            self.record_exception(exc_val)
            self.set_status("error", str(exc_val))

        # End the span
        if self.is_recording():
            self.end()

        return False  # Don't suppress exceptions

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary format.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms(),
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "status": self.status.value,
            "status_message": self.status_message
        }

    def to_otlp(self) -> Dict[str, Any]:
        """Convert to OpenTelemetry Protocol format.

        Returns:
            OTLP-compatible dictionary
        """
        return {
            "name": self.name,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id,
            "kind": self.kind.value,
            "startTimeUnixNano": str(self.start_time),
            "endTimeUnixNano": str(self.end_time) if self.end_time else None,
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)}}
                for k, v in self.attributes.items()
            ],
            "events": [
                {
                    "name": e.name,
                    "timeUnixNano": str(e.timestamp),
                    "attributes": [
                        {"key": k, "value": {"stringValue": str(v)}}
                        for k, v in e.attributes.items()
                    ]
                }
                for e in self.events
            ],
            "status": {
                "code": self.status.value,
                "message": self.status_message
            }
        }


class NoOpSpan:
    """No-op span for when observability is disabled.

    Provides the same interface as Span but does nothing.
    """

    def set_attribute(self, key: str, value: Any) -> None:
        """No-op set attribute."""
        pass

    def add_event(self, name: str, attributes: Optional[Dict] = None) -> None:
        """No-op add event."""
        pass

    def record_exception(self, exception: Exception) -> None:
        """No-op record exception."""
        pass

    def set_status(self, status: str, message: str = "") -> None:
        """No-op set status."""
        pass

    def end(self, end_time: Optional[int] = None) -> None:
        """No-op end."""
        pass

    def is_recording(self) -> bool:
        """Always returns False."""
        return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return False
