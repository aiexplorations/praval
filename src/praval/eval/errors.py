"""Shared evaluation execution errors without orchestration import cycles."""


class EvaluationExecutionError(RuntimeError):
    """An evaluation cannot produce a valid persisted result."""


__all__ = ["EvaluationExecutionError"]
