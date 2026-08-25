# v0.8.3 E4 RAGAS and metric-plugins handoff

E4 adds a public metric-extension contract and an optional RAGAS 0.4 adapter
without making RAGAS part of the base evaluation API. It does not authorize a
v0.8.3 release. E5 sampled online evaluation, E6 documentation and
certification, the documentation-site publication, and all combined release
gates remain required.

## Delivered contracts

### Metric plugins

- Installed extensions use the `praval.eval.metrics` entry-point group.
- A metric exposes bounded `name` and `version` strings and an asynchronous
  `evaluate(JudgeContext) -> MetricResult` method.
- Discovery is deterministic, rejects duplicates, rejects synchronous or
  malformed metrics, prevents built-in shadowing, and reports bounded load
  errors without exposing plugin exception content.
- The installed `reference.word_overlap` metric proves both factory discovery
  and evaluation through the public immutable context contract.

### Optional RAGAS adapter

- `praval[eval-ragas]` installs the tested RAGAS 0.4 line. The base package
  neither installs nor imports RAGAS.
- `PravalRagasLLM` sends RAGAS structured prompts through a configured
  provider-neutral `ModelRuntime`, with strict response schemas, zero retries,
  a bounded timeout, and the standard evaluation-call marker.
- `PravalRagasEmbeddings` sends embeddings through a configured
  `EmbeddingRuntime` with the same evaluation-call marker.
- The adapter never silently chooses a provider, model, embedding model, or
  credential. Model and embedding profile references are validated in typed
  `PravalConfig` before execution.
- Required case fields are validated before any paid judge call. Missing input,
  timeout, invalid score, invalid structured response, and provider failure are
  normalized into bounded `MetricResult` errors without raw content.
- Supported metric names are faithfulness, response relevancy, context
  precision, context recall, factual correctness, semantic similarity, topic
  adherence, agent-goal accuracy, tool-call accuracy, and tool-call F1.
- RAGAS, LangChain, and datasets types remain confined to the optional
  `praval.eval.ragas` module and do not appear in `praval.eval` exports.

### Dependency compatibility

The tested extra is `ragas>=0.4.3,<0.5` with
`langchain-community>=0.3.27,<0.4`. RAGAS 0.4.3 currently permits an
incompatible LangChain Community 0.4 resolution that no longer contains a
module imported by RAGAS. The explicit bound makes a clean installation
repeatable and is included in the `eval-ragas`, `all`, and `dev` extras.

## Checkpoint evidence

Local results on 2026-08-25:

- Complete sandboxed evaluation suite under coverage: 147 passed and 2
  dependency-tracing skips; total `praval.eval` coverage is 92.29 percent.
- Direct non-traced evaluation and configuration selection: 182 passed before
  the separately run database fixture.
- Real PostgreSQL 15 evaluation-store contract: 7 of 7 passed through the
  Docker-backed fixture.
- Black, isort, focused flake8, and strict mypy checks pass across the evaluation
  package and typed configuration.
- The wheel-only `praval-0.8.3-py3-none-any.whl` passes distribution validation.
- A clean base-wheel environment proves evaluation imports and runs while
  RAGAS, the MCP SDK, and the OpenTelemetry SDK are absent.
- A clean `eval-ragas` exact-wheel environment discovers the installed
  reference plugin and passes real RAGAS faithfulness, semantic-similarity,
  and tool-call-accuracy scoring through deterministic Praval runtime seams.

The RAGAS test module is intentionally skipped while Python tracing is active
because the current third-party datasets/PyArrow stack can register the same
extension type twice under coverage. The adapter is instead tested directly
without tracing and from the exact installed wheel; it is omitted from the
base-package coverage denominator.

## Commands

```bash
pytest -q tests/eval --ignore=tests/eval/test_postgres_store.py \
  tests/test_praval_config.py tests/test_praval_config_edges.py
pytest -q tests/eval/test_postgres_store.py
pytest -q tests/eval --ignore=tests/eval/test_postgres_store.py \
  --cov=praval.eval --cov-report=term-missing --cov-fail-under=90
mypy --strict src/praval/eval src/praval/config.py
python -m build --wheel --outdir /tmp/praval-e4-wheel-final
python scripts/validate_distribution.py /tmp/praval-e4-wheel-final
python scripts/smoke_install.py /tmp/praval-e4-wheel-final
python scripts/smoke_install.py /tmp/praval-e4-wheel-final --extra eval-ragas
```

## E5 starting boundary

E5 may add deterministic trace-based sampling, bounded subject capture, durable
PostgreSQL evaluation jobs, leases, retries, idempotent delivery, a worker
lifecycle, and post-hoc evaluation telemetry. Online evaluation must remain
disabled by default, no judge network call may occur on a user request path,
and the E1 through E4 immutable identities, one-observation subject contract,
privacy defaults, bounded errors, stable CLI, and optional-dependency boundaries
must remain unchanged.
