"""Implementation helpers for the stable ``praval eval`` command group."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
from pathlib import Path
from typing import Any

from praval.config import PravalConfig, load_config
from praval.core.registry import get_registry

from .dataset import load_jsonl_suite
from .errors import EvaluationExecutionError
from .gates import compare_evaluation_runs, promote_evaluation_baseline
from .judges import AgentJudge, ModelJudge
from .metrics import builtin_metrics
from .models import Gate, GateStatus
from .postgres import PostgresEvaluationStore
from .runner import EvalRunner, Judge, Metric
from .sqlite import SQLiteEvaluationStore
from .store import EvaluationStore
from .targets import AgentEvaluationTarget

EVAL_EXIT_OK = 0
EVAL_EXIT_GATE_FAILED = 1
EVAL_EXIT_ERROR = 2


def _project_root(config_path: str | None) -> Path:
    if config_path is None:
        return Path.cwd()
    return Path(config_path).expanduser().resolve().parent


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def _store(
    config: PravalConfig, *, root: Path, sqlite_path: str | None
) -> EvaluationStore:
    if sqlite_path is not None or config.eval.store == "sqlite":
        configured = sqlite_path or config.eval.stores.sqlite.path
        return SQLiteEvaluationStore(_resolve_path(root, configured))
    postgres = config.eval.stores.postgres
    if postgres is None:  # validated config should prevent this branch
        raise EvaluationExecutionError("PostgreSQL evaluation store is not configured")
    dsn = os.environ.get(postgres.dsn_env)
    if not dsn:
        raise EvaluationExecutionError(
            f"required evaluation database environment is unset: {postgres.dsn_env}"
        )
    return PostgresEvaluationStore(dsn)


def _gates(suite_name: str, suite: Any) -> tuple[Gate, ...]:
    gates = []
    for index, configured in enumerate(suite.gates, start=1):
        gates.append(
            Gate(
                gate_id=(
                    configured.gate_id or f"{suite_name}:{index}:{configured.metric}"
                ),
                metric=configured.metric,
                aggregation=configured.aggregation,
                operator=configured.operator,
                threshold=configured.threshold,
                required=configured.required,
                percentile=configured.percentile,
                baseline_max_regression=configured.baseline_max_regression,
            )
        )
    return tuple(gates)


async def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        suite_config = config.eval.suites[args.suite]
    except KeyError as exc:
        raise EvaluationExecutionError(
            f"unknown evaluation suite: {args.suite}"
        ) from exc
    available_metrics = builtin_metrics()
    unknown_metrics = sorted(set(suite_config.metrics) - set(available_metrics))
    if unknown_metrics:
        raise EvaluationExecutionError(f"unknown evaluation metrics: {unknown_metrics}")
    metrics: dict[str, Metric] = {
        name: available_metrics[name] for name in suite_config.metrics
    }
    for module_name in args.module:
        importlib.import_module(module_name)
    if not suite_config.target.startswith("agent:"):
        raise EvaluationExecutionError(
            "praval eval run currently requires an agent:<name> target"
        )
    target_name = suite_config.target.partition(":")[2]
    agent = get_registry().get_agent(target_name)
    if agent is None:
        raise EvaluationExecutionError(
            f"evaluation target agent is not registered: {target_name}"
        )
    root = _project_root(args.config)
    dataset = _resolve_path(root, suite_config.dataset)
    loaded = load_jsonl_suite(
        dataset,
        suite_id=args.suite,
        name=args.suite,
        target=suite_config.target,
        judges=suite_config.judges,
        metrics=suite_config.metrics,
        gates=_gates(args.suite, suite_config),
        case_ids=tuple(args.case_id) if args.case_id else None,
        include_tags=tuple(args.tag),
        limit=args.limit,
        seed=args.seed,
    )
    judges: dict[str, Judge] = {}
    for name in suite_config.judges:
        configured = config.eval.judges[name]
        if configured.model is not None:
            judges[name] = ModelJudge.from_config(
                name,
                config,
                rubric=configured.rubric,
                rubric_version=configured.rubric_version,
                judge_version=configured.judge_version,
            )
        else:
            judges[name] = AgentJudge.from_config(
                name,
                config,
                rubric=configured.rubric,
                rubric_version=configured.rubric_version,
                judge_version=configured.judge_version,
            )
    store = _store(config, root=root, sqlite_path=args.db)
    await store.migrate()
    try:
        runner = EvalRunner(
            store=store,
            target=AgentEvaluationTarget(agent),
            judges=judges,
            metrics=metrics,
            concurrency=config.eval.offline_concurrency,
        )
        result = await runner.run(loaded, evaluation_run_id=args.run_id)
        gate_results = await store.list_gate_results(
            evaluation_run_id=result.evaluation_run_id,
            limit=1000,
        )
    finally:
        await store.close()
    payload = {
        **result.model_dump(mode="json"),
        "gates": [gate.model_dump(mode="json") for gate in gate_results],
    }
    if args.json_output:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"Evaluation {result.evaluation_run_id}: "
            f"passed={result.passed_cases} failed={result.failed_cases} "
            f"errored={result.errored_cases}"
        )
        for gate in gate_results:
            print(
                f"  gate {gate.gate_id}: {gate.status.value} "
                f"observed={gate.observed_value} threshold={gate.threshold}"
            )
    if any(gate.status is not GateStatus.PASSED for gate in gate_results):
        return EVAL_EXIT_GATE_FAILED
    return EVAL_EXIT_OK


async def _compare(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    root = _project_root(args.config)
    store = _store(config, root=root, sqlite_path=args.db)
    await store.migrate()
    try:
        current_run_id = _exclusive_argument(
            args.current_run,
            args.current_run_option,
            positional="<run>",
            option="--current-run",
        )
        baseline_run_id = args.baseline_run
        if baseline_run_id is None:
            if args.suite is None:
                raise EvaluationExecutionError(
                    "--suite is required when --baseline-run is omitted"
                )
            baseline = await store.get_active_baseline(args.suite)
            if baseline is None:
                raise EvaluationExecutionError(
                    f"no active baseline exists for suite: {args.suite}"
                )
            baseline_run_id = baseline.source_evaluation_run_id
        comparison = await compare_evaluation_runs(
            store,
            current_run_id=current_run_id,
            baseline_run_id=baseline_run_id,
            max_regression=args.max_regression,
            direction=args.direction,
        )
    finally:
        await store.close()
    payload = {
        "current_run_id": comparison.current_run_id,
        "baseline_run_id": comparison.baseline_run_id,
        "max_regression": comparison.max_regression,
        "direction": comparison.direction,
        "regressed": comparison.regressed,
        "metrics": [metric.__dict__ for metric in comparison.metrics],
    }
    if args.json_output:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"Comparison {comparison.current_run_id} vs "
            f"{comparison.baseline_run_id}: "
            f"{'regressed' if comparison.regressed else 'passed'}"
        )
        for metric in comparison.metrics:
            print(
                f"  {metric.name}@{metric.version}: current={metric.current_value} "
                f"baseline={metric.baseline_value} delta={metric.delta}"
            )
    return EVAL_EXIT_GATE_FAILED if comparison.regressed else EVAL_EXIT_OK


async def _baseline_set(args: argparse.Namespace) -> int:
    suite_id = _exclusive_argument(
        args.suite,
        args.suite_option,
        positional="<suite>",
        option="--suite",
    )
    run_id = _exclusive_argument(
        args.run,
        args.run_option,
        positional="<run>",
        option="--run",
    )
    config = load_config(args.config)
    root = _project_root(args.config)
    store = _store(config, root=root, sqlite_path=args.db)
    await store.migrate()
    try:
        baseline = await promote_evaluation_baseline(
            store,
            suite_id=suite_id,
            evaluation_run_id=run_id,
            promoted_by=args.promoted_by,
        )
    finally:
        await store.close()
    payload = baseline.model_dump(mode="json")
    if args.json_output:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"Baseline {baseline.baseline_id} now points to "
            f"{baseline.source_evaluation_run_id}"
        )
    return EVAL_EXIT_OK


def _exclusive_argument(
    positional_value: str | None,
    option_value: str | None,
    *,
    positional: str,
    option: str,
) -> str:
    if positional_value and option_value:
        raise EvaluationExecutionError(f"use either {positional} or {option}, not both")
    value = positional_value or option_value
    if value is None:
        raise EvaluationExecutionError(f"required argument is missing: {positional}")
    return value


def run_eval_command(args: argparse.Namespace) -> int:
    """Execute an eval subcommand with stable CI exit codes."""
    try:
        if args.eval_command == "run":
            return asyncio.run(_run(args))
        if args.eval_command == "compare":
            return asyncio.run(_compare(args))
        if args.eval_command == "baseline" and args.baseline_command == "set":
            return asyncio.run(_baseline_set(args))
        raise EvaluationExecutionError("an evaluation subcommand is required")
    except (EvaluationExecutionError, ValueError, OSError) as exc:
        print(f"Evaluation error: {exc}")
        return EVAL_EXIT_ERROR
    except Exception as exc:  # defensive CLI boundary; never expose provider secrets
        print(f"Evaluation error: {type(exc).__name__}")
        return EVAL_EXIT_ERROR


__all__ = [
    "EVAL_EXIT_ERROR",
    "EVAL_EXIT_GATE_FAILED",
    "EVAL_EXIT_OK",
    "run_eval_command",
]
