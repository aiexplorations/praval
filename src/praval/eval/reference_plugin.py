"""Small installed reference metric proving the public entry-point contract."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .models import MetricResult, ResultStatus
from .runner import JudgeContext


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


class ReferenceWordOverlapMetric:
    """Measure case-insensitive token overlap with an expected output."""

    name = "reference.word_overlap"
    version = "1"

    async def evaluate(self, context: JudgeContext) -> MetricResult:
        expected = context.case.expected_output
        if expected is None:
            status = ResultStatus.SKIPPED
            score = None
        else:
            expected_tokens = set(_text(expected).casefold().split())
            output_tokens = set(_text(context.target_result.output).casefold().split())
            union = expected_tokens | output_tokens
            score = len(expected_tokens & output_tokens) / len(union) if union else 1.0
            status = ResultStatus.PASSED
        return MetricResult.create(
            evaluation_run_id=context.evaluation_run_id,
            case_id=context.case.case.case_id,
            subject_id=context.subject.subject_id,
            metric=self.name,
            metric_version=self.version,
            status=status,
            score=score,
            label="measured" if score is not None else None,
            created_at=datetime.now(timezone.utc),
        )


def create_metric() -> ReferenceWordOverlapMetric:
    """Create the reference plugin through the standard zero-argument factory."""
    return ReferenceWordOverlapMetric()


__all__ = ["ReferenceWordOverlapMetric", "create_metric"]
