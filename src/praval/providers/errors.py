"""Map provider SDK and HTTP failures to typed ``ProviderError`` subclasses.

The helpers here duck-type the exceptions raised by the OpenAI, Anthropic and
Cohere SDKs (``status_code``, ``response.headers``, ``body``) and by
``urllib`` (``HTTPError``), so they need no SDK imports. Adapters call
:func:`map_provider_exception` from their ``except`` blocks and from their
``map_provider_error`` hook, which the model runtime uses for exceptions that
reach it unmapped.
"""

from __future__ import annotations

import copy
import json
import math
import time
import urllib.error
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, Mapping, Optional, Type

from ..core.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransportError,
    ProviderUnavailableError,
)

MAX_ERROR_BODY_CHARS = 2000
# Error bodies are untrusted: read at most this much before decoding.
MAX_ERROR_BODY_BYTES = 64 * 1024
QUOTA_ERROR_CODES = {"insufficient_quota", "billing_hard_limit_reached"}
UNAVAILABLE_ERROR_CODES = {"overloaded_error", "api_error", "server_error"}
RATE_LIMIT_ERROR_CODES = {"rate_limit_error", "rate_limit_exceeded"}
TRANSPORT_EXCEPTION_NAMES = {"APIConnectionError", "TransportError"}


def sdk_max_retries(config: Any) -> int:
    """Return the SDK-internal retry count: 0 unless explicitly configured.

    Praval retries provider requests itself, so SDK clients are built with
    ``max_retries=0``. ``config.max_retries`` or
    ``config.provider_options["max_retries"]`` overrides that.
    """
    value = getattr(config, "max_retries", None)
    if value is None:
        options = getattr(config, "provider_options", None)
        if isinstance(options, Mapping):
            value = options.get("max_retries")
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProviderError("max_retries must be a non-negative integer")
    return int(value)


def header_value(headers: Any, *names: str) -> Optional[str]:
    """Return the first present header among ``names`` (case-insensitive)."""
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    for name in names:
        for candidate in (name, name.lower(), name.title()):
            value = getter(candidate)
            if value is not None:
                return str(value)
    return None


def parse_retry_after(headers: Any) -> Optional[float]:
    """Parse ``retry-after-ms`` or ``retry-after`` (seconds or HTTP-date)."""
    milliseconds = header_value(headers, "retry-after-ms")
    if milliseconds is not None:
        try:
            value = float(milliseconds) / 1000.0
        except ValueError:
            value = -1.0
        if math.isfinite(value) and value >= 0:
            return value
    raw = header_value(headers, "retry-after")
    if raw is None:
        return None
    raw = raw.strip()
    try:
        seconds = float(raw)
    except ValueError:
        try:
            moment = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
        if moment is None:
            return None
        seconds = moment.timestamp() - time.time()
    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


def _should_retry_header(headers: Any) -> Optional[bool]:
    value = header_value(headers, "x-should-retry")
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _error_object(body: Any) -> Dict[str, Any]:
    """Return the provider's ``error`` object from a decoded error body."""
    if isinstance(body, Mapping):
        nested = body.get("error")
        if isinstance(nested, Mapping):
            return dict(nested)
        return dict(body)
    return {}


def _error_code_from(exc: BaseException, body: Any) -> Optional[str]:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    error = _error_object(body)
    for key in ("code", "type", "status"):
        value = error.get(key)
        if isinstance(value, str) and value:
            return value
    sdk_type = getattr(exc, "type", None)
    if isinstance(sdk_type, str) and sdk_type:
        return sdk_type
    return None


def error_class_for_status(
    status_code: Optional[int],
    *,
    error_code: Optional[str] = None,
) -> Type[ProviderError]:
    """Choose the ``ProviderError`` subclass for an HTTP status and error code."""
    code = (error_code or "").lower()
    if code in QUOTA_ERROR_CODES:
        return ProviderQuotaError
    if status_code is None:
        if code in RATE_LIMIT_ERROR_CODES:
            return ProviderRateLimitError
        if code in UNAVAILABLE_ERROR_CODES:
            return ProviderUnavailableError
        return ProviderError
    if status_code in (401, 403):
        return ProviderAuthenticationError
    if status_code == 402:
        return ProviderQuotaError
    if status_code == 408:
        return ProviderTransportError
    if status_code == 409:
        # OpenAI documents 409 as a transient lock conflict; its SDK retries it.
        return ProviderUnavailableError
    if status_code == 429:
        return ProviderRateLimitError
    if status_code >= 500:
        return ProviderUnavailableError
    if 400 <= status_code < 500:
        return ProviderInvalidRequestError
    return ProviderError


def is_transport_exception(exc: BaseException) -> bool:
    """Return whether ``exc`` is a connection failure or timeout."""
    if isinstance(exc, urllib.error.HTTPError):
        return False
    if isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError)):
        return True
    return any(cls.__name__ in TRANSPORT_EXCEPTION_NAMES for cls in type(exc).__mro__)


def _status_code_of(exc: BaseException) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if status is None and isinstance(exc, urllib.error.HTTPError):
        status = exc.code
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _headers_of(exc: BaseException) -> Any:
    headers = getattr(exc, "headers", None)
    if headers is not None:
        return headers
    response = getattr(exc, "response", None)
    return getattr(response, "headers", None)


def map_provider_exception(
    exc: BaseException,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    message: Optional[str] = None,
    redact: Optional[Callable[[str], str]] = None,
) -> ProviderError:
    """Return a typed ``ProviderError`` describing ``exc``.

    A ``ProviderError`` is returned unchanged apart from filling missing
    ``provider``/``model``/``operation``. HTTP status errors map by status
    code and error code; connection failures and timeouts become
    ``ProviderTransportError``. Anything unrecognised becomes a plain,
    non-retryable ``ProviderError``. ``message`` replaces the default text,
    which is ``str(exc)`` passed through ``redact`` and then truncated, so an
    oversized provider error body never becomes an oversized message.
    """
    text = message if message is not None else str(exc)
    if redact is not None:
        text = redact(text)
    text = _truncate_message(text)
    if isinstance(exc, ProviderError):
        if message is not None:
            # Same type and fields, re-worded by the adapter's except block.
            exc = copy.copy(exc)
            exc.message = text
            exc.args = (text,)
        return fill_provider_error_fields(
            exc, provider=provider, model=model, operation=operation
        )

    status_code = _status_code_of(exc)
    body = getattr(exc, "body", None)
    headers = _headers_of(exc)
    error_code = _error_code_from(exc, body)
    request_id = getattr(exc, "request_id", None)
    if not isinstance(request_id, str):
        request_id = header_value(headers, "x-request-id", "request-id")

    if status_code is None and is_transport_exception(exc):
        error_class: Type[ProviderError] = ProviderTransportError
    elif status_code is None and error_code is None:
        error_class = ProviderError
    else:
        error_class = error_class_for_status(status_code, error_code=error_code)

    retryable: Optional[bool] = None
    should_retry = _should_retry_header(headers)
    if should_retry is not None and error_class is not ProviderQuotaError:
        retryable = should_retry
    return error_class(
        text,
        provider=provider,
        model=model,
        operation=operation,
        status_code=status_code,
        error_code=error_code,
        request_id=request_id,
        retryable=retryable,
        retry_after_seconds=parse_retry_after(headers),
    )


def _truncate_message(text: str) -> str:
    if len(text) <= MAX_ERROR_BODY_CHARS:
        return text
    return text[:MAX_ERROR_BODY_CHARS] + "... [truncated]"


def fill_provider_error_fields(
    error: ProviderError,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
) -> ProviderError:
    """Set ``provider``/``model``/``operation`` where the error left them empty."""
    if error.provider is None:
        error.provider = provider
    if error.model is None:
        error.model = model
    if error.operation is None:
        error.operation = operation
    return error


def _gemini_quota_exhausted(error: Mapping[str, Any]) -> bool:
    """Separate exhausted quota from per-minute throttling in a Gemini 429.

    Gemini reports both as ``RESOURCE_EXHAUSTED`` with a ``QuotaFailure``
    detail. Per-minute limits also carry ``RetryInfo`` with a retry delay;
    daily or credit limits do not, or name a per-day quota.
    """
    details = error.get("details")
    if not isinstance(details, list):
        return False
    has_quota_failure = False
    has_retry_info = False
    per_day = False
    for detail in details:
        if not isinstance(detail, Mapping):
            continue
        detail_type = str(detail.get("@type", ""))
        if detail_type.endswith("google.rpc.QuotaFailure"):
            has_quota_failure = True
            for violation in detail.get("violations") or []:
                if not isinstance(violation, Mapping):
                    continue
                quota_id = str(violation.get("quotaId", ""))
                quota_metric = str(violation.get("quotaMetric", ""))
                if "PerDay" in quota_id or "per_day" in quota_metric.lower():
                    per_day = True
        elif detail_type.endswith("google.rpc.RetryInfo"):
            has_retry_info = True
    return has_quota_failure and (per_day or not has_retry_info)


def _gemini_retry_delay(error: Mapping[str, Any]) -> Optional[float]:
    for detail in error.get("details") or []:
        if not isinstance(detail, Mapping):
            continue
        if str(detail.get("@type", "")).endswith("google.rpc.RetryInfo"):
            delay = str(detail.get("retryDelay", "")).strip()
            if delay.endswith("s"):
                try:
                    seconds = float(delay[:-1])
                except ValueError:
                    return None
                return max(0.0, seconds) if math.isfinite(seconds) else None
    return None


def map_gemini_http_error(
    exc: urllib.error.HTTPError,
    *,
    prefix: str,
    model: Optional[str],
    redact: Callable[[str], str],
) -> ProviderError:
    """Map a Gemini REST ``HTTPError``, keeping its redacted error body.

    The body is read once here. Its ``error.status`` becomes ``error_code``
    and ``error.message`` is appended to the exception message; the request
    URL, which carries the API key, is never copied.
    """
    try:
        raw_body = exc.read(MAX_ERROR_BODY_BYTES).decode("utf-8", errors="replace")
    except Exception:
        raw_body = ""
    try:
        decoded = json.loads(raw_body) if raw_body else None
    except json.JSONDecodeError:
        decoded = None
    error = _error_object(decoded)
    status_text = error.get("status")
    error_code = status_text if isinstance(status_text, str) else None
    detail_message = error.get("message")
    if not isinstance(detail_message, str) or not detail_message:
        detail_message = raw_body.strip()
    detail_message = redact(detail_message)[:MAX_ERROR_BODY_CHARS]

    status_code = int(exc.code)
    parts = [f"HTTP {status_code}"]
    if error_code:
        parts.append(error_code)
    summary = " ".join(parts)
    text = f"{prefix}: {summary}"
    if detail_message:
        text = f"{text}: {detail_message}"
    if status_code == 404:
        text += (
            f". Model '{redact(model or 'unknown')}' is not available on this "
            "endpoint or key; choose an available model from the provider's "
            "model catalogue."
        )

    if status_code == 429 and _gemini_quota_exhausted(error):
        error_class: Type[ProviderError] = ProviderQuotaError
    else:
        error_class = error_class_for_status(status_code)
    retry_after = parse_retry_after(exc.headers)
    if retry_after is None:
        retry_after = _gemini_retry_delay(error)
    return error_class(
        text,
        provider="gemini",
        model=model,
        status_code=status_code,
        error_code=error_code,
        request_id=header_value(exc.headers, "x-request-id"),
        retry_after_seconds=retry_after,
    )
