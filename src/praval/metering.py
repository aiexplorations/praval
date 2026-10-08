"""Bounded, exact chat-model usage counters and caller-supplied cost estimates.

Records contain identities and usage only, never prompts or response content.
Provider requests are counted even when usage is unavailable.
"""

from __future__ import annotations

import logging
import math
import threading
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Dict, Iterator, Literal, Mapping, Optional, Tuple

from .models import Usage

logger = logging.getLogger(__name__)
_tracked: ContextVar[Tuple["UsageMeter", ...]] = ContextVar("praval_meters", default=())
_correlation: ContextVar[Optional[str]] = ContextVar(
    "praval_meter_correlation", default=None
)
_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "total_tokens",
)


@dataclass(frozen=True)
class ModelCall:
    """One actual provider request, including failed and interrupted attempts."""

    provider: str
    model: str
    operation: Literal["invoke", "stream", "continue", "resume"]
    round_index: Optional[int]
    attempt: int
    status: Literal["ok", "error"]
    usage: Optional[Usage]
    duration_ms: float
    started_at: datetime
    agent_name: Optional[str]
    call_id: str
    run_id: Optional[str]
    parent_run_id: Optional[str]
    correlation_id: Optional[str]
    response_id: Optional[str]


@dataclass(frozen=True)
class UsageTotals:
    """Exact totals, including records evicted from the bounded call history."""

    calls: int = 0
    failed_calls: int = 0
    unreported_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    complete: bool = True


@dataclass(frozen=True)
class Price:
    """Prices per million tokens; cache prices default to the input price."""

    input_per_million: float
    output_per_million: float
    cache_read_per_million: Optional[float] = None
    cache_write_per_million: Optional[float] = None
    currency: str = "USD"

    def __post_init__(self) -> None:
        for value in (
            self.input_per_million,
            self.output_per_million,
            self.cache_read_per_million,
            self.cache_write_per_million,
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("Token prices must be finite and non-negative")
        if not self.currency:
            raise ValueError("currency must not be empty")


class PriceTable:
    """Caller-owned prices indexed by ``(provider, model)`` in one currency."""

    def __init__(self, prices: Mapping[Tuple[str, str], Price]) -> None:
        self._prices = dict(prices)
        currencies = {price.currency for price in self._prices.values()}
        if len(currencies) > 1:
            raise ValueError("A price table cannot mix currencies")
        self.currency = next(iter(currencies), "USD")


@dataclass(frozen=True)
class CostEstimate:
    """Cost of reported usage, with explicit missing-price/usage accounting."""

    amount: float
    currency: str
    priced_calls: int
    unpriced_calls: int
    complete: bool


def _copy_call(call: ModelCall) -> ModelCall:
    return replace(
        call, usage=call.usage.model_copy(deep=True) if call.usage is not None else None
    )


def _add(totals: UsageTotals, call: ModelCall) -> UsageTotals:
    tokens = {name: getattr(totals, name) for name in _TOKEN_FIELDS}
    if call.usage is not None:
        for name in _TOKEN_FIELDS:
            tokens[name] += getattr(call.usage, name)
    return UsageTotals(
        calls=totals.calls + 1,
        failed_calls=totals.failed_calls + int(call.status == "error"),
        unreported_calls=totals.unreported_calls
        + int(call.status == "ok" and call.usage is None),
        complete=totals.complete and call.status == "ok" and call.usage is not None,
        **tokens,
    )


class UsageMeter:
    """Thread-safe counters with bounded records and isolated subscribers."""

    def __init__(self, max_records: int = 10_000) -> None:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        self._calls: deque[ModelCall] = deque(maxlen=max_records)
        self._totals = UsageTotals()
        self._models: Dict[Tuple[str, str], UsageTotals] = {}
        self._reported: Dict[Tuple[str, str], int] = {}
        self._subscribers: Dict[object, Callable[[ModelCall], None]] = {}
        self._lock = threading.RLock()

    def record(self, call: ModelCall) -> None:
        """Record a request; invoke subscribers without holding the meter lock."""
        owned = _copy_call(call)
        key = (owned.provider, owned.model)
        with self._lock:
            self._calls.append(owned)
            self._totals = _add(self._totals, owned)
            self._models[key] = _add(self._models.get(key, UsageTotals()), owned)
            self._reported[key] = self._reported.get(key, 0) + int(
                owned.usage is not None
            )
            subscribers = tuple(self._subscribers.items())
        for token, callback in subscribers:
            try:
                callback(_copy_call(owned))
            except Exception:
                # Callback messages may contain application secrets.
                logger.warning("Usage subscriber failed and was removed")
                with self._lock:
                    self._subscribers.pop(token, None)

    @property
    def totals(self) -> UsageTotals:
        """Return an immutable snapshot of all recorded usage."""
        with self._lock:
            return self._totals

    def totals_by_model(self) -> Dict[Tuple[str, str], UsageTotals]:
        """Return independent totals for each provider/model pair."""
        with self._lock:
            return dict(self._models)

    @property
    def calls(self) -> Tuple[ModelCall, ...]:
        """Return defensive snapshots of the most recent bounded records."""
        with self._lock:
            return tuple(_copy_call(call) for call in self._calls)

    def subscribe(self, callback: Callable[[ModelCall], None]) -> Callable[[], None]:
        """Subscribe to new requests; return an idempotent unsubscribe function."""
        token = object()
        with self._lock:
            self._subscribers[token] = callback

        def unsubscribe() -> None:
            with self._lock:
                self._subscribers.pop(token, None)

        return unsubscribe

    def cost(self, prices: PriceTable) -> CostEstimate:
        """Price exact lifetime totals, without charging cache/reasoning twice."""
        with self._lock:
            models, reported, totals = (
                dict(self._models),
                dict(self._reported),
                self._totals,
            )
        amount, priced_calls = 0.0, 0
        for key, usage in models.items():
            price = prices._prices.get(key)
            if price is None:
                continue
            priced_calls += reported[key]
            uncached = (
                usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
            )
            read_price = (
                price.input_per_million
                if price.cache_read_per_million is None
                else price.cache_read_per_million
            )
            write_price = (
                price.input_per_million
                if price.cache_write_per_million is None
                else price.cache_write_per_million
            )
            amount += (
                uncached * price.input_per_million
                + usage.cache_read_tokens * read_price
                + usage.cache_write_tokens * write_price
                + usage.output_tokens * price.output_per_million
            ) / 1_000_000
        unpriced = totals.calls - priced_calls
        return CostEstimate(
            amount,
            prices.currency,
            priced_calls,
            unpriced,
            totals.complete and unpriced == 0,
        )

    def reset(self) -> None:
        """Clear records and totals, keeping existing subscriptions."""
        with self._lock:
            self._calls.clear()
            self._totals = UsageTotals()
            self._models.clear()
            self._reported.clear()

    @contextmanager
    def track(self) -> Iterator[UsageMeter]:
        """Track calls from all agents/runtimes in this context, including workers."""
        current = _tracked.get()
        token = _tracked.set(current if self in current else (*current, self))
        try:
            yield self
        finally:
            _tracked.reset(token)


@contextmanager
def correlation(identifier: str) -> Iterator[None]:
    """Attach an application correlation ID to calls in the current context."""
    token = _correlation.set(identifier)
    try:
        yield
    finally:
        _correlation.reset(token)


__all__ = [
    "ModelCall",
    "UsageMeter",
    "UsageTotals",
    "Price",
    "PriceTable",
    "CostEstimate",
    "correlation",
]
