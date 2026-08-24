"""Deterministic built-in metric contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from praval.eval import (
    EvalCase,
    EvaluationSubject,
    ExactMatchMetric,
    JudgeContext,
    LoadedEvalCase,
    ResultStatus,
    TargetResult,
    TerminalSuccessMetric,
    ToolCallMatchMetric,
    builtin_metrics,
)
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ToolCallObservation,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _reference(kind: ContentKind) -> ContentReference:
    return ContentReference(kind=kind, sha256="a" * 64, size_bytes=1)


def _context(
    *,
    output='{"answer":"ok"}',
    expected=None,
    expected_tools: tuple[str, ...] = ("lookup",),
    observed_tools: tuple[str, ...] = ("lookup",),
    status: ObservationStatus = ObservationStatus.OK,
) -> JudgeContext:
    case = LoadedEvalCase(
        case=EvalCase(
            case_id="case-1",
            name="Case",
            input=_reference(ContentKind.PROMPT),
            expected_output=(
                _reference(ContentKind.RESPONSE) if expected is not None else None
            ),
            expected_tool_calls=expected_tools,
        ),
        input={"question": "hello"},
        expected_output=expected,
        reference_contexts=(),
    )
    observation = ExecutionObservation(
        observation_id="observation-1",
        run_id="execution-1",
        kind=ObservationKind.AGENT,
        agent_name="target",
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=1),
        duration_ms=1,
        status=status,
        error_type="TargetError" if status is ObservationStatus.ERROR else None,
        tool_calls=tuple(
            ToolCallObservation(
                tool_call_id=f"call-{index}",
                name=name,
                status=ObservationFactStatus.OK,
                duration_ms=1,
            )
            for index, name in enumerate(observed_tools)
        ),
    )
    subject = EvaluationSubject.from_observation(
        evaluation_run_id="evaluation-1",
        case_id="case-1",
        observation=observation,
    )
    return JudgeContext(
        evaluation_run_id="evaluation-1",
        case=case,
        subject=subject,
        target_result=TargetResult(observation=observation, output=output),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output", "expected", "status", "score"),
    [
        ('{"answer":"ok"}', {"answer": "ok"}, ResultStatus.PASSED, 1.0),
        ({"answer": "wrong"}, {"answer": "ok"}, ResultStatus.FAILED, 0.0),
        ("actual", "expected", ResultStatus.FAILED, 0.0),
        ({"score": float("nan")}, {"score": 1}, ResultStatus.ERROR, None),
        ("anything", None, ResultStatus.SKIPPED, None),
    ],
)
async def test_exact_match_normalizes_json_and_handles_missing_reference(
    output, expected, status: ResultStatus, score: float | None
) -> None:
    result = await ExactMatchMetric(clock=lambda: NOW).evaluate(
        _context(output=output, expected=expected)
    )

    assert result.status is status
    assert result.score == score
    assert result.metric == "exact_match"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected", "observed", "status"),
    [
        (("lookup",), ("lookup",), ResultStatus.PASSED),
        (("lookup",), ("search",), ResultStatus.FAILED),
        ((), ("lookup",), ResultStatus.SKIPPED),
    ],
)
async def test_tool_call_match_is_ordered_and_skips_unspecified_expectations(
    expected: tuple[str, ...],
    observed: tuple[str, ...],
    status: ResultStatus,
) -> None:
    result = await ToolCallMatchMetric(clock=lambda: NOW).evaluate(
        _context(expected_tools=expected, observed_tools=observed)
    )

    assert result.status is status
    assert result.score == (
        1.0
        if status is ResultStatus.PASSED
        else 0.0 if status is ResultStatus.FAILED else None
    )


@pytest.mark.asyncio
async def test_terminal_success_maps_observation_status_without_raw_content() -> None:
    passed = await TerminalSuccessMetric(clock=lambda: NOW).evaluate(_context())
    failed = await TerminalSuccessMetric(clock=lambda: NOW).evaluate(
        _context(status=ObservationStatus.ERROR)
    )

    assert passed.status is ResultStatus.PASSED and passed.score == 1.0
    assert failed.status is ResultStatus.FAILED and failed.score == 0.0
    assert failed.error_type is None
    assert set(builtin_metrics()) == {
        "exact_match",
        "terminal_success",
        "tool_call_match",
    }
