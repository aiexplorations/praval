# v0.8.3 E3 workflow-evaluation and regression-gates handoff

E3 implements deterministic metrics, agent and workflow subject execution,
quality gates, explicit baselines, run comparison, and the stable evaluation
CLI. It does not authorize a v0.8.3 release. E4 through E6, the documentation
site work, and all combined release gates remain required.

## Delivered contracts

### Deterministic evaluation

- `AgentEvaluationTarget` runs an ordinary registered `Agent`, isolates its
  transient history, and returns exactly one immutable observation per case.
- `EvalRunner` executes configured deterministic metrics alongside judges,
  validates every result identity, persists metric records, and folds metric
  and judge outcomes into the terminal case status.
- Built-in `exact_match`, `tool_call_match`, and `terminal_success` metrics are
  provider-free, versioned, and normalize invalid inputs into bounded errors.
- Fixed workflow fixtures prove that one workflow observation retains its
  terminal outcome, tool calls, and Reef handoffs as aggregated facts and can
  pass a quality gate without producing observations for individual facts.

### Gates and baselines

- Gates support mean, minimum, maximum, interpolated percentile, count, and
  pass-rate aggregation with all documented comparison operators.
- Required missing or errored results produce explicit gate errors. Optional
  unavailable gates are omitted rather than treated as successful.
- Baseline-relative gates apply a direction-aware maximum regression and reject
  comparisons between incompatible metric or judge identities and versions.
- Run comparison keeps metrics and judges with the same name separate, reports
  added and removed results deterministically, and never mutates a baseline.
- Baseline promotion is explicit and accepts only a completed terminal run from
  the selected suite. No successful run is promoted automatically.

### CLI and configuration

- `praval eval run <suite>` supports deterministic selection by case ID, tag,
  limit, and seed, plus registered-module loading and JSON output.
- `praval eval compare <run> --baseline <baseline>` compares immutable completed
  runs. Omitting `--baseline` uses only an explicitly promoted suite baseline.
- `praval eval baseline set <suite> <run>` performs explicit promotion and
  records the actor. The earlier named-option forms remain accepted as aliases.
- Exit code `0` means success, `1` means a quality or regression gate failed,
  and `2` means configuration or evaluation execution failed.
- Unexpected provider and plugin exceptions stop at the CLI boundary without
  exposing exception text that could contain credentials or candidate content.
- `praval.toml` now configures the evaluation store, judge versions and rubrics,
  suite metrics, gate aggregations, missing-result policy, and regression bounds.

## Public API added in E3

`praval.eval` now exports:

- `AgentEvaluationTarget`, `EvaluationExecutionError`
- `ExactMatchMetric`, `TerminalSuccessMetric`, `ToolCallMatchMetric`
- `GateEvaluationError`, `MetricComparison`, `RunComparison`
- `evaluate_gate`, `compare_evaluation_runs`, `promote_evaluation_baseline`

## Checkpoint evidence

Local results on 2026-08-25:

- Complete evaluation and configuration selection without the separately run
  Docker fixture: 163 passed.
- Complete evaluation suite under coverage: 139 passed; total `praval.eval`
  coverage is 92.41 percent, with the new CLI at 98 percent, gates at 97
  percent, metrics at 100 percent, runner at 97 percent, and targets at 100
  percent.
- Real PostgreSQL 15 evaluation-store contract: 7 of 7 passed through the
  Docker-backed fixture.
- Black, isort, focused flake8 at the repository's 88-character policy, and
  strict mypy checks pass.
- The exact `praval-0.8.3-py3-none-any.whl` passes distribution validation,
  clean-environment public evaluation imports, `praval eval --help`, the
  metadata-only no-SDK observability check, and the fake-provider runtime smoke.

## Commands

```bash
pytest -q tests/eval --ignore=tests/eval/test_postgres_store.py \
  tests/test_praval_config.py tests/test_praval_config_edges.py
pytest -q tests/eval/test_postgres_store.py
pytest -q tests/eval --ignore=tests/eval/test_postgres_store.py \
  --cov=praval.eval --cov-report=term-missing --cov-fail-under=90
mypy --cache-dir=/tmp/praval-mypy-e3-recheck \
  src/praval/eval src/praval/config.py
python -m build --wheel --no-isolation --outdir /tmp/praval-e3-dist-final
python scripts/validate_distribution.py /tmp/praval-e3-dist-final
python scripts/smoke_install.py /tmp/praval-e3-dist-final
```

## E4 starting boundary

E4 may add the public metric-plugin contract and discovery, the optional RAGAS
adapter, Praval model and embedding bridges, required-field validation, and a
small reference custom metric. It must preserve base-package operation without
RAGAS, immutable result identities, bounded errors, metadata-only defaults,
ordinary Praval runtime composition, explicit baselines, and the stable CLI
exit-code contract. RAGAS, LangChain, and datasets types must not leak into the
core public API.
