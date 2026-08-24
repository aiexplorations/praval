"""Evaluation-call context used to prevent recursive online sampling."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_EVALUATION_DEPTH: ContextVar[int] = ContextVar("praval_evaluation_depth", default=0)


def is_evaluation_call() -> bool:
    """Return whether the current sync or async context is evaluation work."""
    return _EVALUATION_DEPTH.get() > 0


@contextmanager
def evaluation_call_scope() -> Iterator[None]:
    """Mark model, tool, and agent calls as evaluation work for this context."""
    token = _EVALUATION_DEPTH.set(_EVALUATION_DEPTH.get() + 1)
    try:
        yield
    finally:
        _EVALUATION_DEPTH.reset(token)


__all__ = ["evaluation_call_scope", "is_evaluation_call"]
