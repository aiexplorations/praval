"""Observations and evaluation consume real agent executions over fake SDKs."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import pytest
from _agent_system_support import ScriptedModel, answer_for, provider_patch
from _system_matrix_support import SHAPES, Recorder, make_worker, plan, tools

from praval.core.agent import Agent
from praval.core.exceptions import ProviderError
from praval.models import ContentKind, ObservationFactStatus, ObservationStatus
from praval.runtime_observation import use_observation_recorder


@pytest.mark.parametrize("entry", ["chat", "generate", "agenerate"])
@pytest.mark.parametrize(
    "shape,outcome",
    [
        (shape, outcome)
        for shape in SHAPES
        for outcome in ["ok", "tool-error", "provider-error"]
        if shape != "none" or outcome != "tool-error"
    ],
)
def test_agent_observation_matches_wire_execution_without_private_content(
    monkeypatch: pytest.MonkeyPatch, entry: str, shape: str, outcome: str
) -> None:
    worker, model, log, _ = make_worker(monkeypatch, "sync-chat", shape)
    current = worker._praval_agent
    recorder = Recorder()
    question = "private-question-8675309"
    if outcome == "tool-error":
        name = "label" if shape == "dependent" else "echo"

        def broken(value: str) -> str:
            log.append((name, value))
            raise LookupError("private-tool-error-8675309")

        broken.__name__ = name
        current.tools[name]["function"] = broken
    if outcome == "provider-error":

        def fail_last(question: str) -> None:
            if len(model.requests) == SHAPES.index(shape) + 1:
                raise ValueError("private-provider-error-8675309")

        model.on_request = fail_last

    def run() -> Any:
        if entry == "agenerate":
            return asyncio.run(current.agenerate(question))
        return getattr(current, entry)(question)

    try:
        with use_observation_recorder(recorder):
            if outcome == "provider-error":
                with pytest.raises(ProviderError):
                    run()
            else:
                run()
        assert len(recorder.observations) == 1
        observation = recorder.observations[0]
        assert observation.agent_name == "worker"
        assert observation.provider == "openai" and observation.model == "gpt-test"
        assert (
            observation.request_mode
            == {"chat": "chat", "generate": "generate", "agenerate": "generate_async"}[
                entry
            ]
        )
        assert observation.status is (
            ObservationStatus.ERROR
            if outcome == "provider-error"
            else ObservationStatus.OK
        )
        assert len(observation.tool_calls) == SHAPES.index(shape)
        assert [fact.name for fact in observation.tool_calls] == (
            []
            if shape == "none"
            else ["echo"] + (["label"] if shape == "dependent" else [])
        )
        if outcome == "tool-error":
            assert observation.tool_calls[-1].status is ObservationFactStatus.ERROR
            assert observation.tool_calls[-1].error_type == "ToolResultError"
        else:
            assert all(
                fact.status is ObservationFactStatus.OK
                for fact in observation.tool_calls
            )
        assert len(model.requests) == SHAPES.index(shape) + 1
        assert observation.model_calls == len(model.requests)
        assert current.usage.totals.calls == len(model.requests)
        assert current.usage.totals.failed_calls == int(outcome == "provider-error")
        assert [call.status for call in current.usage.calls] == (
            ["ok"] * (len(model.requests) - int(outcome == "provider-error"))
            + (["error"] if outcome == "provider-error" else [])
        )
        prompt = next(
            reference
            for reference in observation.content_references
            if reference.kind is ContentKind.PROMPT
        )
        assert prompt.sha256 == hashlib.sha256(question.encode()).hexdigest()
        assert prompt.size_bytes == len(question.encode())
        serialized = observation.model_dump_json()
        assert "8675309" not in serialized
        assert observation.privacy.content_captured is False
        assert observation.error_type == (
            "ProviderError" if outcome == "provider-error" else None
        )
    finally:
        current.close()


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("matched", [False, True], ids=["gate-fails", "gate-passes"])
@pytest.mark.parametrize("isolated", [False, True], ids=["retained", "isolated"])
def test_eval_runner_gates_and_metrics_use_real_agent_tool_observations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    shape: str,
    matched: bool,
    isolated: bool,
) -> None:
    from dataclasses import replace

    from praval.eval import (
        AgentEvaluationTarget,
        EvalRunner,
        ExactMatchMetric,
        Gate,
        GateAggregation,
        GateOperator,
        GateStatus,
        SQLiteEvaluationStore,
        ToolCallMatchMetric,
        load_jsonl_suite,
    )

    model = ScriptedModel(plan(shape))
    log = []
    with provider_patch(model, monkeypatch):
        current = Agent("evaluation-target", provider="openai", model="gpt-test")
    for function in tools(log) if shape != "none" else []:
        current.tool(function)
    expected_calls = (
        []
        if shape == "none"
        else ["echo"] + (["label"] if shape == "dependent" else [])
    )
    rows = []
    for index in range(3):
        question = f"case-{index}"
        results = (
            []
            if shape == "none"
            else [f"E:{question}"]
            + ([f"L:E:{question}"] if shape == "dependent" else [])
        )
        rows.append(
            {
                "id": question,
                "input": question,
                "expected_output": (
                    answer_for(question, results) if matched else "wrong answer"
                ),
                "expected_tool_calls": expected_calls,
            }
        )
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    loaded = load_jsonl_suite(
        path,
        suite_id="matrix",
        name="Matrix",
        target="evaluation-target",
        metrics=("exact_match", "tool_call_match"),
    )
    loaded = replace(
        loaded,
        suite=loaded.suite.model_copy(
            update={
                "gates": (
                    Gate(
                        gate_id="answers",
                        metric="exact_match",
                        aggregation=GateAggregation.MEAN,
                        operator=GateOperator.GREATER_THAN_OR_EQUAL,
                        threshold=1.0,
                    ),
                )
            }
        ),
    )
    original = list(current.conversation_history)

    async def evaluate() -> None:
        store = SQLiteEvaluationStore(tmp_path / "results.db")
        await store.migrate()
        try:
            runner = EvalRunner(
                store=store,
                target=AgentEvaluationTarget(current, isolate_conversation=isolated),
                judges={},
                metrics={
                    "exact_match": ExactMatchMetric(),
                    "tool_call_match": ToolCallMatchMetric(),
                },
                concurrency=3,
            )
            result = await runner.run(loaded, evaluation_run_id="eval-matrix")
            assert result.total_cases == 3
            assert result.passed_cases == (3 if matched else 0)
            assert result.failed_cases == (0 if matched else 3)
            subjects = await store.list_subjects(evaluation_run_id="eval-matrix")
            metrics = await store.list_metric_results(evaluation_run_id="eval-matrix")
            gates = await store.list_gate_results(evaluation_run_id="eval-matrix")
            assert len(subjects) == 3 and len(metrics) == 6 and len(gates) == 1
            assert gates[0].status is (
                GateStatus.PASSED if matched else GateStatus.FAILED
            )
            assert {metric.subject_id for metric in metrics} == {
                subject.subject_id for subject in subjects
            }
            assert all(subject.observation_id for subject in subjects)
            assert all(
                metric.score == (None if shape == "none" else 1.0)
                for metric in metrics
                if metric.metric == "tool_call_match"
            )
        finally:
            await store.close()

    try:
        asyncio.run(evaluate())
        assert len(model.requests) == 3 * (SHAPES.index(shape) + 1)
        assert (
            current.conversation_history == original
            if isolated
            else len(current.conversation_history) == len(original) + 6
        )
        assert len(log) == 3 * SHAPES.index(shape)
    finally:
        current.close()


@pytest.mark.parametrize("mode", ["sync-chat", "async-chat", "async-achat"])
@pytest.mark.parametrize("shape", ["none", "dependent"])
def test_reef_carrier_links_handler_model_and_tools_without_private_payloads(
    monkeypatch: pytest.MonkeyPatch, mode: str, shape: str
) -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from praval.core.reef import get_reef
    from praval.runtime_observation import configure_observation_recorder

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("matrix")
    monkeypatch.setattr(
        "praval.observability.lifecycle.get_tracer", lambda *args: tracer
    )
    worker, _, _, _ = make_worker(monkeypatch, mode, shape, channel="traced")
    recorder = Recorder()
    previous = configure_observation_recorder(recorder)
    try:
        with tracer.start_as_current_span("root") as root:
            root_id = root.get_span_context().trace_id
            get_reef().broadcast(
                "sender",
                {"type": "work", "question": "private-traced-question"},
                channel="traced",
            )
            assert get_reef().get_channel("traced").wait_for_completion(timeout=5)
        assert len(recorder.observations) == 1
        observation = recorder.observations[0]
        assert observation.trace_id == f"{root_id:032x}"
        assert len(observation.tool_calls) == (2 if shape == "dependent" else 0)
        spans = exporter.get_finished_spans()
        assert all(span.context.trace_id == root_id for span in spans)
        names = {span.name for span in spans}
        assert {
            "praval.reef.producer",
            "praval.reef.delivery",
            "praval.reef.consumer",
            "praval.agent.invoke",
            "provider.invoke",
        } <= names
        assert all(
            "private-traced-question" not in str(span.attributes) for span in spans
        )
        assert "private-traced-question" not in observation.model_dump_json()
        by_id = {span.context.span_id: span for span in spans}
        assert all(
            span.parent is None or span.parent.span_id in by_id for span in spans
        )
    finally:
        configure_observation_recorder(previous)
        worker._praval_agent.close()
        provider.shutdown()


@pytest.mark.parametrize("status", ["passed", "failed", "skipped"])
@pytest.mark.parametrize("shape", ["none", "one"])
def test_agent_judge_results_and_gate_share_persisted_execution_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, status: str, shape: str
) -> None:
    from dataclasses import replace

    from praval.eval import (
        AgentEvaluationTarget,
        AgentJudge,
        EvalRunner,
        Gate,
        GateAggregation,
        GateOperator,
        GateStatus,
        ResultStatus,
        SQLiteEvaluationStore,
        load_jsonl_suite,
    )

    target_model = ScriptedModel(plan(shape))
    with provider_patch(target_model, monkeypatch):
        target = Agent("subject", provider="openai", model="gpt-target")
    for function in tools([]) if shape == "one" else []:
        target.tool(function)
    judge_model = ScriptedModel()
    payload = json.dumps(
        {
            "status": status,
            "score": 0.9 if status == "passed" else 0.1 if status == "failed" else None,
            "label": status,
            "explanation": "private-judge-reason",
            "evidence": ["private-judge-evidence"],
        }
    )
    original_final = judge_model.final_turn
    monkeypatch.setattr(judge_model, "final_turn", lambda text: original_final(payload))
    with provider_patch(judge_model, monkeypatch):
        evaluator = Agent("judge", provider="openai", model="gpt-judge")
    judge = AgentJudge(
        agent=evaluator,
        name="quality",
        judge_version="1",
        rubric="Assess the answer",
        rubric_version="1",
        max_attempts=1,
    )
    path = tmp_path / "judge.jsonl"
    path.write_text(
        json.dumps({"id": "case", "input": "private-target-question"}) + "\n",
        encoding="utf-8",
    )
    loaded = load_jsonl_suite(
        path, suite_id="judges", name="Judges", target="subject", judges=("quality",)
    )
    loaded = replace(
        loaded,
        suite=loaded.suite.model_copy(
            update={
                "gates": (
                    Gate(
                        gate_id="quality",
                        metric="quality",
                        aggregation=GateAggregation.MEAN,
                        operator=GateOperator.GREATER_THAN_OR_EQUAL,
                        threshold=0.5,
                    ),
                )
            }
        ),
    )

    async def evaluate() -> None:
        store = SQLiteEvaluationStore(tmp_path / "judge.db")
        await store.migrate()
        try:
            runner = EvalRunner(
                store=store,
                target=AgentEvaluationTarget(target),
                judges={"quality": judge},
                concurrency=1,
            )
            await runner.run(loaded, evaluation_run_id="judged")
            subjects = await store.list_subjects(evaluation_run_id="judged")
            results = await store.list_judge_results(evaluation_run_id="judged")
            gates = await store.list_gate_results(evaluation_run_id="judged")
            assert len(subjects) == len(results) == len(gates) == 1
            assert results[0].subject_id == subjects[0].subject_id
            assert results[0].status is ResultStatus(status)
            assert gates[0].status is (
                GateStatus.PASSED
                if status == "passed"
                else (GateStatus.FAILED if status == "failed" else GateStatus.ERROR)
            )
            assert results[0].explanation is None
            assert (
                results[0].evidence
                and "private-judge" not in results[0].model_dump_json()
            )
            assert evaluator.conversation_history == []
            assert target.conversation_history == []
        finally:
            await store.close()

    try:
        asyncio.run(evaluate())
        assert len(target_model.requests) == (2 if shape == "one" else 1)
        assert len(judge_model.requests) == 1
        assert not judge_model.requests[0].get("tools")
    finally:
        target.close()
        evaluator.close()
