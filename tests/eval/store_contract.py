"""Behavioral assertions shared by every evaluation-store implementation."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

from praval.eval import EvaluationBaseline, EvaluationConflictError, JobStatus


async def assert_all_records_round_trip(store: Any, records: dict[str, Any]) -> None:
    assert await store.put_case(records["case"]) == records["case"]
    assert await store.put_suite(records["suite"]) == records["suite"]
    assert await store.put_run(records["run"]) == records["run"]
    assert await store.put_subject(records["subject"]) == records["subject"]
    assert await store.put_metric_result(records["metric"]) == records["metric"]
    assert await store.put_judge_result(records["judge"]) == records["judge"]
    assert await store.put_gate_result(records["gate_result"]) == records["gate_result"]
    assert await store.put_evaluation_result(records["result"]) == records["result"]
    assert await store.promote_baseline(records["baseline"]) == records["baseline"]
    assert await store.put_job(records["job"]) == records["job"]
    assert await store.put_attempt(records["attempt"]) == records["attempt"]

    assert await store.get_case("case-1") == records["case"]
    assert await store.get_suite("suite-1") == records["suite"]
    assert await store.get_run("eval-run-1") == records["run"]
    assert await store.get_subject(records["subject"].subject_id) == records["subject"]
    assert await store.get_evaluation_result("eval-run-1") == records["result"]
    assert await store.get_active_baseline("suite-1") == records["baseline"]
    assert await store.get_job("job-1") == records["job"]


async def assert_query_filters(store: Any, records: dict[str, Any]) -> None:
    await store.put_case(records["case"])
    await store.put_suite(records["suite"])
    await store.put_run(records["run"])
    await store.put_subject(records["subject"])
    await store.put_metric_result(records["metric"])
    await store.put_judge_result(records["judge"])
    await store.put_gate_result(records["gate_result"])
    await store.put_job(records["job"])
    await store.put_attempt(records["attempt"])

    assert await store.list_runs(suite_id="suite-1") == [records["run"]]
    assert await store.list_runs(suite_id="missing") == []
    assert await store.list_subjects(evaluation_run_id="eval-run-1") == [
        records["subject"]
    ]
    assert await store.list_metric_results(
        evaluation_run_id="eval-run-1", metric="correctness"
    ) == [records["metric"]]
    assert await store.list_judge_results(evaluation_run_id="eval-run-1") == [
        records["judge"]
    ]
    assert await store.list_gate_results(evaluation_run_id="eval-run-1") == [
        records["gate_result"]
    ]
    assert await store.list_jobs(status=JobStatus.PENDING) == [records["job"]]
    assert await store.list_attempts(job_id="job-1") == [records["attempt"]]


async def assert_result_idempotency(store: Any, records: dict[str, Any]) -> None:
    metric = records["metric"]
    first, second = await asyncio.gather(
        store.put_metric_result(metric), store.put_metric_result(metric)
    )
    assert first == second == metric

    changed = metric.model_copy(update={"score": 0.1})
    with pytest.raises(EvaluationConflictError, match="metric result"):
        await store.put_metric_result(changed)


async def assert_concurrent_writes(store: Any, records: dict[str, Any]) -> None:
    base = records["case"]
    cases = [
        base.model_copy(update={"case_id": f"case-{index}", "name": f"Case {index}"})
        for index in range(25)
    ]
    await asyncio.gather(*(store.put_case(case) for case in cases))
    assert {case.case_id for case in await store.list_cases(limit=100)} == {
        case.case_id for case in cases
    }


async def assert_explicit_baseline_promotion(
    store: Any, records: dict[str, Any]
) -> None:
    first = records["baseline"]
    second = EvaluationBaseline.create(
        suite_id="suite-1",
        source_evaluation_run_id="eval-run-2",
        promoted_at=first.promoted_at + timedelta(seconds=1),
        promoted_by="maintainer",
    )
    await store.promote_baseline(first)
    assert await store.get_active_baseline("suite-1") == first
    await store.promote_baseline(second)
    assert await store.get_active_baseline("suite-1") == second
    baselines = await store.list_baselines(suite_id="suite-1")
    assert [baseline.active for baseline in baselines] == [True, False]


async def assert_attempt_idempotency(store: Any, records: dict[str, Any]) -> None:
    attempt = records["attempt"]
    await store.put_attempt(attempt)
    assert await store.put_attempt(attempt) == attempt

    conflicting = attempt.model_copy(update={"attempt_id": "different-id"})
    with pytest.raises(EvaluationConflictError, match="attempt number"):
        await store.put_attempt(conflicting)
