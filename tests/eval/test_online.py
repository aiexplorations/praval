"""Sampled online evaluation request-isolation and worker lifecycle tests."""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from praval.config import OnlineEvalConfig
from praval.eval import (
    EvalCase,
    EvalSuite,
    EvaluationJob,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSubject,
    ExactMatchMetric,
    JobStatus,
    JudgeContext,
    JudgeResult,
    LoadedEvalCase,
    MetricResult,
    OnlineSubjectEvaluator,
    ResultStatus,
    SQLiteEvaluationStore,
    TargetResult,
)
from praval.eval.context import evaluation_call_scope, is_evaluation_call
from praval.eval.online import OnlineEvaluationService, trace_sampled
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ObservationKind,
    ObservationStatus,
)
from praval.observability.evaluation import post_hoc_evaluation_links

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _observation(index: int = 1) -> ExecutionObservation:
    return ExecutionObservation(
        observation_id=f"observation-{index}",
        run_id=f"target-run-{index}",
        kind=ObservationKind.AGENT,
        agent_name="target",
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=1),
        duration_ms=1,
        status=ObservationStatus.OK,
        trace_id=f"{index:032x}",
        span_id=f"{index:016x}",
    )


def _config(**overrides) -> OnlineEvalConfig:
    values = {
        "enabled": True,
        "sample_ratio": 1.0,
        "queue_capacity": 16,
        "workers": 1,
        "max_attempts": 2,
        "max_enqueue_attempts": 2,
        "lease_seconds": 2,
        "job_timeout_seconds": 1,
        "poll_interval_seconds": 0.005,
        "retry_backoff_seconds": 0,
        "shutdown_timeout_seconds": 1,
        "max_subject_bytes": 262_144,
    }
    values.update(overrides)
    return OnlineEvalConfig.model_validate(values)


def _suite() -> EvalSuite:
    return EvalSuite(
        suite_id="online-quality",
        name="Online quality",
        target="agent:target",
        case_ids=("online-template",),
    )


def _job_subject_context():
    observation = _observation()
    run_id = "online-run-test"
    case_id = "online-case-test"
    subject = EvaluationSubject.from_observation(
        evaluation_run_id=run_id,
        case_id=case_id,
        observation=observation,
    )
    job = EvaluationJob.create(
        evaluation_run_id=run_id,
        suite_id=_suite().suite_id,
        case_id=case_id,
        subject_id=subject.subject_id,
        available_at=NOW,
        max_attempts=2,
        created_at=NOW,
        updated_at=NOW,
    )
    reference = ContentReference(kind=ContentKind.PROMPT, sha256="a" * 64, size_bytes=1)
    case = EvalCase(
        case_id=case_id,
        name="Resolved online case",
        input=reference,
        expected_output=reference.model_copy(update={"kind": ContentKind.RESPONSE}),
    )
    context = JudgeContext(
        evaluation_run_id=run_id,
        case=LoadedEvalCase(
            case=case,
            input="question",
            expected_output={"answer": "ok"},
            reference_contexts=(),
        ),
        subject=subject,
        target_result=TargetResult(
            observation=observation,
            output={"answer": "ok"},
        ),
    )
    return job, subject, context


async def _wait_until(predicate, *, timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        await asyncio.sleep(0.005)


@pytest.mark.parametrize(
    ("trace_id", "ratio", "expected"),
    [
        ("0" * 32, 0.0, False),
        ("f" * 32, 1.0, True),
        ("0" * 31 + "1", 0.5, True),
        ("f" * 32, 0.5, False),
        (None, 1.0, False),
    ],
)
def test_trace_sampling_is_deterministic(trace_id, ratio, expected) -> None:
    assert trace_sampled(trace_id, ratio) is expected
    assert trace_sampled(trace_id, ratio) is expected


def test_trace_sampling_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="sample_ratio"):
        trace_sampled("0" * 32, 1.1)
    with pytest.raises(ValueError, match="32 hexadecimal"):
        trace_sampled("not-a-trace", 1)
    with pytest.raises(ValueError, match="32 hexadecimal"):
        trace_sampled("g" * 32, 1)


def test_online_subject_evaluator_rejects_unknown_plugins(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "unknown.db")
    with pytest.raises(ValueError, match="unknown online judges"):
        OnlineSubjectEvaluator(
            store=store,
            suite=_suite().model_copy(update={"judges": ("missing",)}),
            context_loader=lambda job, subject: None,
            judges={},
            metrics={},
        )
    with pytest.raises(ValueError, match="unknown online metrics"):
        OnlineSubjectEvaluator(
            store=store,
            suite=_suite().model_copy(update={"metrics": ("missing",)}),
            context_loader=lambda job, subject: None,
            judges={},
            metrics={},
        )


def test_online_subject_evaluator_rejects_identity_drift() -> None:
    job, subject, context = _job_subject_context()
    other_observation = _observation(2)
    other_subject = EvaluationSubject.from_observation(
        evaluation_run_id=job.evaluation_run_id,
        case_id=job.case_id,
        observation=other_observation,
    )
    invalid_contexts = (
        replace(context, evaluation_run_id="other-run"),
        replace(
            context,
            case=replace(
                context.case,
                case=context.case.case.model_copy(update={"case_id": "other-case"}),
            ),
        ),
        replace(context, subject=other_subject),
        replace(
            context,
            target_result=TargetResult(
                observation=other_observation,
                output=context.target_result.output,
            ),
        ),
    )
    for invalid in invalid_contexts:
        with pytest.raises(ValueError, match="identity does not match"):
            OnlineSubjectEvaluator._validate_context(invalid, job, subject)


def test_online_subject_evaluator_rejects_result_identity_drift() -> None:
    job, subject, context = _job_subject_context()
    values = {
        "evaluation_run_id": job.evaluation_run_id,
        "case_id": job.case_id,
        "subject_id": subject.subject_id,
        "judge": "quality",
        "judge_version": "1",
        "prompt_sha256": "a" * 64,
        "rubric_version": "1",
        "status": ResultStatus.PASSED,
        "score": 1,
        "label": "pass",
        "created_at": NOW,
    }
    valid = JudgeResult.create(**values)
    for update in (
        {"evaluation_run_id": "other-run"},
        {"case_id": "other-case"},
        {"subject_id": "other-subject"},
        {"judge": "other-judge"},
    ):
        with pytest.raises(ValueError, match="identity does not match"):
            OnlineSubjectEvaluator._validate_result(
                valid.model_copy(update=update), "quality", context
            )
    metric = MetricResult.create(
        evaluation_run_id=job.evaluation_run_id,
        case_id=job.case_id,
        subject_id=subject.subject_id,
        metric="quality",
        metric_version="1",
        status=ResultStatus.PASSED,
        score=1,
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="metric identity"):
        OnlineSubjectEvaluator._validate_result(metric, "quality", context, "2")


@pytest.mark.asyncio
async def test_disabled_online_evaluation_starts_no_tasks(tmp_path) -> None:
    calls = []

    async def processor(job, subject):
        calls.append((job, subject))

    service = OnlineEvaluationService(
        store=SQLiteEvaluationStore(tmp_path / "disabled.db"),
        suite=_suite(),
        processor=processor,
        config=OnlineEvalConfig(),
    )

    await service.start()
    service.record(_observation())

    assert service.active is False
    assert calls == []
    assert service.stats().skipped == 1
    assert not (tmp_path / "disabled.db").exists()


@pytest.mark.asyncio
async def test_request_path_only_enqueues_and_worker_completes_durable_job(
    tmp_path,
) -> None:
    calls = []

    async def processor(job, subject):
        calls.append((job, subject, is_evaluation_call()))

    store = SQLiteEvaluationStore(tmp_path / "online.db")
    service = OnlineEvaluationService(
        store=store, suite=_suite(), processor=processor, config=_config()
    )
    await service.start()

    service.record(_observation())
    assert calls == []
    await _wait_until(lambda: service.stats().processed == 1)

    jobs = await store.list_jobs()
    attempts = await store.list_attempts(job_id=jobs[0].job_id)
    run = await store.get_run(jobs[0].evaluation_run_id)
    assert len(calls) == 1 and calls[0][2] is True
    assert jobs[0].status is JobStatus.COMPLETED
    assert len(attempts) == 1 and attempts[0].status.value == "succeeded"
    assert run is not None and run.status.value == "completed"
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_online_subject_evaluator_composes_public_metrics(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "subject-evaluator.db")
    suite = _suite().model_copy(update={"metrics": ("exact_match",)})

    async def context_loader(job, subject):
        reference = ContentReference(
            kind=ContentKind.PROMPT, sha256="a" * 64, size_bytes=1
        )
        case = EvalCase(
            case_id=job.case_id,
            name="Resolved online case",
            input=reference,
            expected_output=reference.model_copy(update={"kind": ContentKind.RESPONSE}),
        )
        return JudgeContext(
            evaluation_run_id=job.evaluation_run_id,
            case=LoadedEvalCase(
                case=case,
                input="question",
                expected_output={"answer": "ok"},
                reference_contexts=(),
            ),
            subject=subject,
            target_result=TargetResult(
                observation=subject.observation,
                output={"answer": "ok"},
            ),
        )

    evaluator = OnlineSubjectEvaluator(
        store=store,
        suite=suite,
        context_loader=context_loader,
        judges={},
        metrics={"exact_match": ExactMatchMetric(clock=lambda: NOW)},
        clock=lambda: NOW,
    )
    service = OnlineEvaluationService(
        store=store, suite=suite, processor=evaluator, config=_config()
    )
    await service.start()
    service.record(_observation())
    await _wait_until(
        lambda: service.stats().processed == 1
        or service.stats().processor_failures == 2
    )
    jobs = await store.list_jobs()
    attempts = await store.list_attempts(job_id=jobs[0].job_id)
    assert service.stats().processed == 1, (
        service.stats(),
        [attempt.error_type for attempt in attempts],
    )
    metrics = await store.list_metric_results(
        evaluation_run_id=jobs[0].evaluation_run_id
    )
    result = await store.get_evaluation_result(jobs[0].evaluation_run_id)
    assert len(metrics) == 1
    assert metrics[0].metric == "exact_match" and metrics[0].score == 1
    assert result is not None and result.passed_cases == 1
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_online_subject_evaluator_composes_judges_and_normalizes_metrics(
    tmp_path, monkeypatch
) -> None:
    store = SQLiteEvaluationStore(tmp_path / "judge-and-metric.db")
    suite = _suite().model_copy(
        update={"judges": ("quality",), "metrics": ("exploding",)}
    )

    class QualityJudge:
        name = "quality"

        async def evaluate(self, context):
            return JudgeResult.create(
                evaluation_run_id=context.evaluation_run_id,
                case_id=context.case.case.case_id,
                subject_id=context.subject.subject_id,
                judge=self.name,
                judge_version="1",
                prompt_sha256="a" * 64,
                rubric_version="1",
                status=ResultStatus.PASSED,
                score=1,
                label="pass",
                created_at=NOW,
            )

    class ExplodingMetric:
        name = "exploding"
        version = "1"

        async def evaluate(self, context):
            raise RuntimeError("unbounded provider details")

    async def context_loader(job, subject):
        _, _, template = _job_subject_context()
        case = template.case.case.model_copy(update={"case_id": job.case_id})
        return replace(
            template,
            evaluation_run_id=job.evaluation_run_id,
            case=replace(template.case, case=case),
            subject=subject,
            target_result=TargetResult(
                observation=subject.observation,
                output=template.target_result.output,
            ),
        )

    def broken_telemetry(result, subject):
        raise RuntimeError("exporter unavailable")

    monkeypatch.setattr("praval.eval.online.emit_evaluation_result", broken_telemetry)
    evaluator = OnlineSubjectEvaluator(
        store=store,
        suite=suite,
        context_loader=context_loader,
        judges={"quality": QualityJudge()},
        metrics={"exploding": ExplodingMetric()},
        clock=lambda: NOW,
    )
    service = OnlineEvaluationService(
        store=store, suite=suite, processor=evaluator, config=_config()
    )
    await service.start()
    service.record(_observation())
    await _wait_until(lambda: service.stats().processed == 1)

    jobs = await store.list_jobs()
    judges = await store.list_judge_results(evaluation_run_id=jobs[0].evaluation_run_id)
    metrics = await store.list_metric_results(
        evaluation_run_id=jobs[0].evaluation_run_id
    )
    result = await store.get_evaluation_result(jobs[0].evaluation_run_id)
    assert len(judges) == 1 and judges[0].status is ResultStatus.PASSED
    assert len(metrics) == 1 and metrics[0].status is ResultStatus.ERROR
    assert metrics[0].error_type == "RuntimeError"
    assert "provider details" not in metrics[0].model_dump_json()
    assert result is not None and result.errored_cases == 1
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_online_subject_evaluator_requires_aware_error_clock(tmp_path) -> None:
    job, subject, context = _job_subject_context()

    class ExplodingMetric:
        name = "exploding"
        version = "1"

        async def evaluate(self, loaded_context):
            raise RuntimeError("failed")

    async def context_loader(loaded_job, loaded_subject):
        return context

    evaluator = OnlineSubjectEvaluator(
        store=SQLiteEvaluationStore(tmp_path / "naive-evaluator-clock.db"),
        suite=_suite().model_copy(update={"metrics": ("exploding",)}),
        context_loader=context_loader,
        judges={},
        metrics={"exploding": ExplodingMetric()},
        clock=lambda: NOW.replace(tzinfo=None),
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        await evaluator(job, subject)


@pytest.mark.asyncio
async def test_recursive_evaluation_and_non_target_observations_are_skipped(
    tmp_path,
) -> None:
    async def processor(job, subject):
        raise AssertionError("processor must not run")

    service = OnlineEvaluationService(
        store=SQLiteEvaluationStore(tmp_path / "skip.db"),
        suite=_suite(),
        processor=processor,
        config=_config(),
    )
    await service.start()
    with evaluation_call_scope():
        service.record(_observation())
    service.record(_observation().model_copy(update={"agent_name": "other"}))
    await asyncio.sleep(0.02)

    assert service.stats().skipped == 2
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_sampling_target_and_lifecycle_skip_branches(tmp_path) -> None:
    async def processor(job, subject):
        raise AssertionError("processor must not run")

    service = OnlineEvaluationService(
        store=SQLiteEvaluationStore(tmp_path / "sampling-skips.db"),
        suite=_suite().model_copy(update={"target": "target"}),
        processor=processor,
        config=_config(sample_ratio=0),
    )
    assert await service.shutdown()
    await service.start()
    await service.start()
    service.record(_observation())
    invalid = _observation(2).model_copy(update={"trace_id": "g" * 32})
    service.record(invalid)
    workflow = _observation(3).model_copy(
        update={
            "kind": ObservationKind.WORKFLOW,
            "agent_name": None,
            "workflow_name": "target",
        }
    )
    service.record(workflow)

    assert service.stats().skipped == 2
    assert service.stats().dropped == 1
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_queue_saturation_is_visible_and_does_not_block_request(tmp_path) -> None:
    gate = asyncio.Event()
    backing = SQLiteEvaluationStore(tmp_path / "saturation.db")

    class BlockingStore:
        def __getattr__(self, name):
            return getattr(backing, name)

        async def get_job(self, job_id):
            await gate.wait()
            return await backing.get_job(job_id)

    async def processor(job, subject):
        return None

    service = OnlineEvaluationService(
        store=BlockingStore(),
        suite=_suite(),
        processor=processor,
        config=_config(queue_capacity=1),
    )
    await service.start()
    service.record(_observation(1))
    await _wait_until(lambda: service.queue_depth == 0)
    service.record(_observation(2))

    started = time.perf_counter()
    service.record(_observation(3))
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < 2
    assert service.stats().dropped == 1
    gate.set()
    await _wait_until(lambda: service.stats().persisted >= 1)
    await service.shutdown()


@pytest.mark.asyncio
async def test_processor_failures_retry_then_dead_letter(tmp_path) -> None:
    calls = []

    async def processor(job, subject):
        calls.append(job.attempt_count)
        raise RuntimeError("provider secret must remain bounded")

    store = SQLiteEvaluationStore(tmp_path / "retry.db")
    service = OnlineEvaluationService(
        store=store, suite=_suite(), processor=processor, config=_config()
    )
    await service.start()
    service.record(_observation())
    await _wait_until(lambda: service.stats().dead_lettered == 1, timeout=3)

    jobs = await store.list_jobs()
    attempts = await store.list_attempts(job_id=jobs[0].job_id)
    run = await store.get_run(jobs[0].evaluation_run_id)
    assert calls == [1, 2]
    assert jobs[0].status is JobStatus.DEAD_LETTER
    assert jobs[0].error_type == "RuntimeError"
    assert [attempt.error_type for attempt in attempts] == [
        "RuntimeError",
        "RuntimeError",
    ]
    assert run is not None and run.status.value == "failed"
    assert "provider secret" not in jobs[0].model_dump_json()
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_processor_timeout_is_recorded_and_dead_lettered(tmp_path) -> None:
    async def processor(job, subject):
        await asyncio.Event().wait()

    store = SQLiteEvaluationStore(tmp_path / "timeout.db")
    service = OnlineEvaluationService(
        store=store,
        suite=_suite(),
        processor=processor,
        config=_config(
            max_attempts=1,
            job_timeout_seconds=0.01,
            lease_seconds=0.02,
        ),
    )
    await service.start()
    service.record(_observation())
    await _wait_until(lambda: service.stats().dead_lettered == 1)

    jobs = await store.list_jobs()
    attempts = await store.list_attempts(job_id=jobs[0].job_id)
    assert jobs[0].status is JobStatus.DEAD_LETTER
    assert jobs[0].error_type == "ProcessorTimeout"
    assert len(attempts) == 1 and attempts[0].status.value == "timeout"
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_missing_subject_is_dead_lettered_without_calling_processor(
    tmp_path,
) -> None:
    async def processor(job, subject):
        raise AssertionError("processor must not run")

    store = SQLiteEvaluationStore(tmp_path / "missing-subject.db")
    await store.migrate()
    job, _, context = _job_subject_context()
    job = job.model_copy(
        update={
            "max_attempts": 1,
            "available_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
            "created_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
        }
    )
    await store.put_suite(_suite())
    await store.put_case(context.case.case)
    await store.put_run(
        EvaluationRun(
            evaluation_run_id=job.evaluation_run_id,
            suite_id=job.suite_id,
            target=_suite().target,
            status=EvaluationRunStatus.PENDING,
            started_at=NOW,
        )
    )
    await store.put_job(job)
    service = OnlineEvaluationService(
        store=store,
        suite=_suite(),
        processor=processor,
        config=_config(max_attempts=1),
    )
    await service.start()
    await _wait_until(lambda: service.stats().dead_lettered == 1)

    stored = await store.get_job(job.job_id)
    assert stored is not None and stored.error_type == "SubjectMissing"
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_duplicate_observation_delivery_processes_one_durable_job(
    tmp_path,
) -> None:
    calls = []

    async def processor(job, subject):
        calls.append(job.job_id)

    store = SQLiteEvaluationStore(tmp_path / "duplicate.db")
    service = OnlineEvaluationService(
        store=store, suite=_suite(), processor=processor, config=_config()
    )
    await service.start()
    service.record(_observation())
    service.record(_observation())
    await _wait_until(lambda: service.stats().processed == 1)
    await asyncio.sleep(0.02)

    assert len(calls) == 1
    assert len(await store.list_jobs()) == 1
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_worker_restart_resumes_durable_pending_job(tmp_path) -> None:
    entered = asyncio.Event()

    async def interrupted_processor(job, subject):
        entered.set()
        await asyncio.Event().wait()

    store = SQLiteEvaluationStore(tmp_path / "restart.db")
    first = OnlineEvaluationService(
        store=store,
        suite=_suite(),
        processor=interrupted_processor,
        config=_config(),
    )
    await first.start()
    first.record(_observation())
    await asyncio.wait_for(entered.wait(), timeout=1)
    assert await first.shutdown(timeout_seconds=0.02) is False

    resumed = []

    async def resumed_processor(job, subject):
        resumed.append(job.attempt_count)

    second = OnlineEvaluationService(
        store=store,
        suite=_suite(),
        processor=resumed_processor,
        config=_config(),
    )
    await second.start()
    await _wait_until(lambda: second.stats().processed == 1)

    jobs = await store.list_jobs()
    attempts = await store.list_attempts(job_id=jobs[0].job_id)
    assert resumed == [2]
    assert jobs[0].status is JobStatus.COMPLETED
    assert [attempt.status.value for attempt in attempts] == [
        "cancelled",
        "succeeded",
    ]
    assert await second.shutdown()


@pytest.mark.asyncio
async def test_store_downtime_retries_off_path_and_reports_job_loss(tmp_path) -> None:
    backing = SQLiteEvaluationStore(tmp_path / "store-down.db")

    class UnavailableStore:
        def __getattr__(self, name):
            return getattr(backing, name)

        async def get_job(self, job_id):
            raise ConnectionError("database credential must not be exposed")

    async def processor(job, subject):
        raise AssertionError("processor must not run")

    service = OnlineEvaluationService(
        store=UnavailableStore(),
        suite=_suite(),
        processor=processor,
        config=_config(max_enqueue_attempts=2),
    )
    await service.start()

    started = time.perf_counter()
    service.record(_observation())
    elapsed_ms = (time.perf_counter() - started) * 1000
    await _wait_until(lambda: service.stats().dropped == 1)

    assert elapsed_ms < 2
    assert service.stats().store_failures == 2
    assert service.stats().persisted == 0
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_worker_recovers_after_transient_lease_failure(tmp_path) -> None:
    backing = SQLiteEvaluationStore(tmp_path / "lease-recovery.db")

    class FlakyLeaseStore:
        def __init__(self):
            self.failed = False

        def __getattr__(self, name):
            return getattr(backing, name)

        async def lease_job(self, **values):
            if not self.failed:
                self.failed = True
                raise ConnectionError("database unavailable")
            return await backing.lease_job(**values)

    calls = []

    async def processor(job, subject):
        calls.append(job.job_id)

    service = OnlineEvaluationService(
        store=FlakyLeaseStore(),
        suite=_suite(),
        processor=processor,
        config=_config(),
    )
    await service.start()
    service.record(_observation())
    await _wait_until(lambda: service.stats().processed == 1)

    assert len(calls) == 1
    assert service.stats().store_failures == 1
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_post_hoc_span_link_uses_original_trace_and_span() -> None:
    links = post_hoc_evaluation_links(_observation(7))

    assert len(links) == 1
    assert links[0].context.trace_id == 7
    assert links[0].context.span_id == 7
    assert (
        post_hoc_evaluation_links(
            _observation().model_copy(update={"trace_id": None, "span_id": None})
        )
        == []
    )


@pytest.mark.asyncio
async def test_subject_size_bound_drops_before_persistence(tmp_path) -> None:
    async def processor(job, subject):
        raise AssertionError("processor must not run")

    service = OnlineEvaluationService(
        store=SQLiteEvaluationStore(tmp_path / "bounded.db"),
        suite=_suite(),
        processor=processor,
        config=_config(max_subject_bytes=1),
    )
    await service.start()
    service.record(_observation())

    assert service.stats().dropped == 1
    assert service.stats().persisted == 0
    assert await service.shutdown()


@pytest.mark.asyncio
async def test_shutdown_is_bounded_and_releases_cancelled_work(tmp_path) -> None:
    entered = asyncio.Event()

    async def processor(job, subject):
        entered.set()
        await asyncio.Event().wait()

    store = SQLiteEvaluationStore(tmp_path / "shutdown.db")
    service = OnlineEvaluationService(
        store=store, suite=_suite(), processor=processor, config=_config()
    )
    await service.start()
    service.record(_observation())
    await asyncio.wait_for(entered.wait(), timeout=1)

    started = time.perf_counter()
    clean = await service.shutdown(timeout_seconds=0.02)
    elapsed = time.perf_counter() - started

    assert clean is False
    assert elapsed < 0.5
    assert service.active is False
    jobs = await store.list_jobs()
    assert jobs[0].status in {JobStatus.PENDING, JobStatus.DEAD_LETTER}


@pytest.mark.asyncio
async def test_request_scheduling_p95_stays_below_two_milliseconds(tmp_path) -> None:
    gate = asyncio.Event()

    async def processor(job, subject):
        await gate.wait()

    service = OnlineEvaluationService(
        store=SQLiteEvaluationStore(tmp_path / "performance.db"),
        suite=_suite(),
        processor=processor,
        config=_config(queue_capacity=1000),
    )
    await service.start()

    durations = []
    for index in range(1, 301):
        started = time.perf_counter()
        service.record(_observation(index))
        durations.append((time.perf_counter() - started) * 1000)
    p95 = sorted(durations)[int(len(durations) * 0.95) - 1]

    assert p95 < 2
    assert service.stats().enqueued == 300
    gate.set()
    await service.shutdown(timeout_seconds=0.02)
