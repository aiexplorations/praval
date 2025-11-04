"""
OTLP (OpenTelemetry Protocol) HTTP exporter.

Sends traces to OTLP-compatible collectors like:
- Jaeger
- Zipkin
- Honeycomb
- DataDog
- New Relic
- etc.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OTLPExporter:
    """OTLP HTTP exporter for sending traces to collectors."""

    def __init__(self, endpoint: str, headers: Optional[Dict[str, str]] = None):
        """Initialize OTLP exporter.

        Args:
            endpoint: OTLP HTTP endpoint URL (e.g., "http://localhost:4318/v1/traces")
            headers: Optional HTTP headers (e.g., API keys)
        """
        self.endpoint = endpoint
        self.headers = headers or {}
        self.headers.setdefault("Content-Type", "application/json")

    def export_spans(self, spans: List[Dict[str, Any]]) -> bool:
        """Export a batch of spans to the OTLP endpoint.

        Args:
            spans: List of span dictionaries

        Returns:
            True if export successful, False otherwise
        """
        if not spans:
            return True

        try:
            import requests
        except ImportError:
            logger.warning(
                "requests library not installed. Install with: pip install requests"
            )
            return False

        # Convert spans to OTLP format
        otlp_payload = self._build_otlp_payload(spans)

        try:
            response = requests.post(
                self.endpoint, json=otlp_payload, headers=self.headers, timeout=10
            )

            if response.status_code in (200, 202):
                logger.debug(f"Exported {len(spans)} spans to {self.endpoint}")
                return True
            else:
                logger.error(
                    f"OTLP export failed: {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"OTLP export error: {e}")
            return False

    def _build_otlp_payload(self, spans: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build OTLP-compliant JSON payload.

        Args:
            spans: List of span dictionaries

        Returns:
            OTLP JSON payload
        """
        # Group spans by trace_id
        trace_groups: Dict[str, List[Dict]] = {}
        for span in spans:
            trace_id = span.get("trace_id")
            if trace_id:
                if trace_id not in trace_groups:
                    trace_groups[trace_id] = []
                trace_groups[trace_id].append(span)

        # Build resource spans
        resource_spans = []
        for trace_id, trace_spans in trace_groups.items():
            scope_spans = {
                "scope": {
                    "name": "praval",
                    "version": "0.8.0",
                },
                "spans": [self._span_to_otlp(s) for s in trace_spans],
            }

            resource_span = {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "praval"}},
                        {
                            "key": "telemetry.sdk.name",
                            "value": {"stringValue": "praval-observability"},
                        },
                        {
                            "key": "telemetry.sdk.version",
                            "value": {"stringValue": "0.8.0"},
                        },
                    ]
                },
                "scopeSpans": [scope_spans],
            }

            resource_spans.append(resource_span)

        return {"resourceSpans": resource_spans}

    def _span_to_otlp(self, span: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a span dictionary to OTLP format.

        Args:
            span: Span dictionary from storage

        Returns:
            OTLP-formatted span
        """
        # Convert timestamps to Unix nanoseconds
        start_time_nano = self._datetime_to_unix_nano(span.get("start_time"))
        end_time_nano = (
            self._datetime_to_unix_nano(span.get("end_time"))
            if span.get("end_time")
            else None
        )

        # Map span kind
        kind_map = {
            "INTERNAL": 1,
            "SERVER": 2,
            "CLIENT": 3,
            "PRODUCER": 4,
            "CONSUMER": 5,
        }
        kind = kind_map.get(span.get("kind", "INTERNAL"), 1)

        # Map status
        status_map = {"ok": 1, "error": 2}
        status_code = status_map.get(span.get("status", "ok"), 1)

        return {
            "traceId": self._hex_to_base64(span.get("trace_id", "")),
            "spanId": self._hex_to_base64(span.get("span_id", "")),
            "parentSpanId": self._hex_to_base64(span.get("parent_span_id", ""))
            if span.get("parent_span_id")
            else "",
            "name": span.get("name", "unknown"),
            "kind": kind,
            "startTimeUnixNano": start_time_nano,
            "endTimeUnixNano": end_time_nano,
            "attributes": self._attributes_to_otlp(span.get("attributes", {})),
            "events": self._events_to_otlp(span.get("events", [])),
            "status": {"code": status_code, "message": span.get("status_message", "")},
        }

    def _attributes_to_otlp(self, attributes: Dict[str, Any]) -> List[Dict]:
        """Convert attributes to OTLP format."""
        result = []
        for key, value in attributes.items():
            if isinstance(value, bool):
                result.append({"key": key, "value": {"boolValue": value}})
            elif isinstance(value, int):
                result.append({"key": key, "value": {"intValue": value}})
            elif isinstance(value, float):
                result.append({"key": key, "value": {"doubleValue": value}})
            else:
                result.append({"key": key, "value": {"stringValue": str(value)}})
        return result

    def _events_to_otlp(self, events: List[Dict]) -> List[Dict]:
        """Convert events to OTLP format."""
        result = []
        for event in events:
            otlp_event = {
                "name": event.get("name", "event"),
                "timeUnixNano": self._datetime_to_unix_nano(event.get("timestamp")),
                "attributes": self._attributes_to_otlp(event.get("attributes", {})),
            }
            result.append(otlp_event)
        return result

    def _datetime_to_unix_nano(self, dt: Any) -> int:
        """Convert datetime to Unix nanoseconds."""
        if isinstance(dt, (int, float)):
            # Already a timestamp
            return int(dt * 1e9)
        elif isinstance(dt, datetime):
            return int(dt.timestamp() * 1e9)
        elif isinstance(dt, str):
            try:
                dt_obj = datetime.fromisoformat(dt)
                return int(dt_obj.timestamp() * 1e9)
            except:
                return 0
        return 0

    def _hex_to_base64(self, hex_str: str) -> str:
        """Convert hex string to base64 for OTLP."""
        if not hex_str:
            return ""
        try:
            import base64

            bytes_data = bytes.fromhex(hex_str)
            return base64.b64encode(bytes_data).decode("ascii")
        except:
            return hex_str


def export_traces_to_otlp(
    endpoint: str,
    trace_ids: Optional[List[str]] = None,
    limit: int = 100,
    headers: Optional[Dict[str, str]] = None,
) -> bool:
    """Export traces from local storage to OTLP endpoint.

    Args:
        endpoint: OTLP HTTP endpoint URL
        trace_ids: Optional list of specific trace IDs to export (None = recent traces)
        limit: Maximum number of traces to export (default: 100)
        headers: Optional HTTP headers

    Returns:
        True if export successful, False otherwise
    """
    from ..storage import get_trace_store

    store = get_trace_store()
    exporter = OTLPExporter(endpoint, headers)

    # Get spans to export
    if trace_ids:
        spans = []
        for trace_id in trace_ids:
            spans.extend(store.get_trace(trace_id))
    else:
        spans = store.get_recent_traces(limit=limit)

    if not spans:
        logger.info("No spans to export")
        return True

    # Export in batches of 100
    batch_size = 100
    total_exported = 0

    for i in range(0, len(spans), batch_size):
        batch = spans[i : i + batch_size]
        if exporter.export_spans(batch):
            total_exported += len(batch)
        else:
            logger.error(f"Failed to export batch {i // batch_size + 1}")
            return False

    logger.info(f"Exported {total_exported} spans to {endpoint}")
    return True
