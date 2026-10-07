# Praval - AI Multi-Agent Framework

**The Pythonic Multi-Agent AI Framework for building intelligent, collaborative agent systems**

> *Praval (प्रवाल) - Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.*

`AGENTS.md` carries the same rules in short form for other coding agents. Keep the two in sync: a process change goes into both.

## IMPORTANT: Always Use the Virtual Environment

```bash
source venv/bin/activate  # Always run this first!
```

All `pytest`, `pip` and `python` commands run inside the activated `venv/`. Create it with `make setup` if it is missing.

## Project Overview

- **Version**: `pyproject.toml` is the only source of truth. `praval.__version__` comes from installed distribution metadata. Current release work and its plan live in `plans/` (see `plans/praval-roadmap.md`).
- **Python support**: 3.10 to 3.14 (`requires-python = ">=3.10,<3.15"`). CI tests every version; typing is checked for 3.13 (strict) and 3.10 (compatibility).
- **License**: MIT

## Repository Structure

```
praval/
├── src/praval/
│   ├── __init__.py            # Public API; every export is listed in docs/api-surface.toml
│   ├── decorators.py          # @agent, chat(), achat(), broadcast()
│   ├── composition.py         # start_agents and agent composition
│   ├── app.py                 # PravalApp application lifecycle
│   ├── config.py              # PravalConfig / AppConfig and PRAVAL_* environment mapping
│   ├── model_runtime.py       # ModelRuntime: requests, retries, tool loop, streaming, HITL resume
│   ├── models/                # Provider-neutral contracts (ModelRequest, ModelResponse, Usage, ToolSpec...)
│   ├── providers/             # openai.py, anthropic.py, gemini.py, cohere.py,
│   │                          # openai_compatible.py (local servers), registry.py (profiles, capabilities), factory.py
│   ├── tools.py               # @tool decorator
│   ├── embeddings.py          # Embedding runtime
│   ├── runtime_observation.py # ExecutionObservation (per-run aggregated facts)
│   ├── hitl/                  # Human-in-the-loop policy, store, service, runtime
│   ├── core/                  # Agent, Reef, Spore, registry, storage, secure reef/spore, transport
│   ├── memory/                # Memory manager and memory types
│   ├── storage/               # Storage providers (filesystem, PostgreSQL, Redis, S3, Qdrant)
│   ├── observability/         # Tracing, instrumentation, OTLP/console/SQLite export
│   ├── eval/                  # Evaluation: datasets, runner, metrics, judges, gates, stores, online eval
│   ├── mcp/                   # MCP client and server support
│   └── cli.py                 # praval CLI
├── tests/                     # Pytest suite; subfolders eval/, mcp/, observability/, storage/,
│                              # integration/ (needs services), performance/, validation/
├── examples/                  # Examples, notebooks, and examples/certification/ (wheel and live checks)
├── docs/                      # Markdown docs, Sphinx sources (docs/sphinx/), release notes (docs/releases/)
│                              # and documentation contracts (api-surface.toml, feature-claims.toml,
│                              # documentation-coverage.toml, observation-contract.toml)
├── plans/                     # Roadmap and release plans
├── scripts/                   # Build, release, typing, coverage, demo and smoke scripts
├── RELEASE.md                 # Release procedure (authoritative)
└── CONTRIBUTING.md            # Contribution workflow and PR checklist
```

## Core Patterns

### Single agent
```python
from praval import Agent

agent = Agent("assistant", system_message="You are a helpful assistant")
response = agent.chat("What is machine learning?")
```

`Agent` also exposes `generate`, `agenerate`, `stream` and `astream`, which return provider-neutral `ModelResponse` objects and `ModelEvent` streams.

### Multi-agent with @agent
```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_request"])
def researcher(spore):
    result = chat(f"Research: {spore.knowledge['topic']}")
    broadcast({"type": "research_complete", "findings": result})
    return {"status": "done"}

@agent("writer", responds_to=["research_complete"])
def writer(spore):
    article = chat(f"Write about: {spore.knowledge['findings']}")
    return {"article": article}

start_agents(researcher, writer,
    initial_data={"type": "research_request", "topic": "AI agents"})
```

### Key concepts

- **`responds_to`**: filters messages by `spore.knowledge["type"]`.
- **`broadcast()`**: sends to all agents on the default channel; every broadcast needs a `type`.
- **`chat()`**: calls the LLM in agent context; only works inside `@agent` functions.
- **Peer-to-peer**: agents coordinate through the Reef, never through a central orchestrator.
- **All model calls go through `ModelRuntime`**; provider adapters translate provider-neutral requests to each provider's wire format and back.

## Code Standards

- **Black** (line length 88) and **isort** (`--profile black`) over `src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py`.
- **flake8** with `--max-line-length=88 --extend-ignore=E203,W503`.
- **mypy** via `scripts/check_types.py`: strict for Python 3.13 and a 3.10 compatibility pass. Code must type-check on both (no 3.11+ only syntax in `src/`).
- Comprehensive type hints on every function; specific exception types; `logging`, never `print`, in library code.
- Match the surrounding code's naming, comment density and idioms.

## Testing

- Frameworks: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-timeout`.
- Markers: `unit`, `integration` (needs external services), `performance`, `edge_case`, `knowledge_base`.
- Test files are named `test_*.py`. Provider behaviour is tested with recorded fixtures or deterministic fake clients; unit tests never call the network.
- Existing homes for new tests: `test_model_runtime_contracts.py` / `test_model_runtime_edges.py` (runtime), `test_<provider>_provider_edges.py` (adapters), `test_provider_streaming.py`, `test_hitl_provider_parity.py`, `test_agent_*.py`, `test_decorator_edges.py`.
- Coverage: overall at least 90% (`--cov-fail-under=90`) plus per-file floors in `scripts/check_coverage_floors.py`.
- Three test files are excluded by both CI and the Makefile: `test_arxiv_downloader.py`, `test_message_filtering.py`, `test_venturelens_demo.py`.
- Live provider checks are not part of pytest. They live in `examples/certification/` (`live_provider_matrix.py`, `live_hitl.py`, `live_voice_roundtrip.py`), need real keys, and incur cost.

## Development Commands

```bash
source venv/bin/activate

make setup            # create venv/ and install .[dev]
make test             # test suite (CI exclusions applied)
make test-cov         # coverage with --cov-fail-under=90 and coverage floors
make format           # black + isort
make lint             # flake8
make type-check       # scripts/check_types.py (3.13 strict + 3.10)
make docs-html        # Sphinx HTML into docs/_build/html
make build            # scripts/build.sh (coverage-enforced build)

# What CI runs (match it before pushing)
pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py \
  --ignore=tests/test_venturelens_demo.py --timeout=60 --timeout-method=thread -q
black --check src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py
isort --check-only src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py --profile black
flake8 src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py --max-line-length=88 --extend-ignore=E203,W503
python scripts/check_types.py
PRAVAL_DOCS_OFFLINE=1 sphinx-build -b html -W --keep-going docs/sphinx docs/_build/html
python scripts/check_release_metadata.py
python scripts/check_api_surface.py
```

## Documentation Contracts

These are enforced by tests (`tests/test_documentation_contracts.py`) and `scripts/check_api_surface.py`:

- Every name in `praval.__all__` must appear in exactly one surface in `docs/api-surface.toml`, and that surface's Sphinx page must document it. A new public export needs both.
- Claims in `docs/feature-claims.toml` cite the tests that prove them; update evidence when tests move.
- Config models and fields listed in `docs/documentation-coverage.toml` must be documented in the named page.
- The Sphinx build runs with `-W`: any warning fails CI.
- User-facing changes go in `CHANGELOG.md` under `[Unreleased]` (Added / Changed / Fixed), and into the matching guide under `docs/sphinx/guide/`.

## Branches, Commits and CI

- Work on a branch from `main`, never on `main`. Earlier work used `codex/<topic>`; v0.8.4 uses `release/v0.8.4` with feature branches merged into it.
- Commit prefixes: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `build:`; `BREAKING CHANGE:` for incompatible changes. Keep commits focused by concern.
- CI (`.github/workflows/ci.yml`) runs on PRs and pushes: tests on 3.10 to 3.14; quality (coverage, floors, typing, formatting, lint, notebooks, warning-free docs, release metadata, API surface); MCP contracts; reproducible package build; exact-wheel docs; wheel and install smoke tests; offline and service demos against the built wheel.
- `live-demos.yml` is manually dispatched from trusted `main` with protected credentials.

## Release Process

`RELEASE.md` is authoritative; `CONTRIBUTING.md` holds the PR checklist. In short:

1. One reviewable PR updates the version in `pyproject.toml`, `CHANGELOG.md`, `docs/releases/RELEASE_NOTES_X.Y.Z.md`, examples and current docs. `python scripts/check_release_metadata.py` validates them.
2. Merge to `main`; `main` CI produces `praval-<commit>` (the sole wheel) and `praval-docs-<commit>` artifacts and runs the demo jobs.
3. Optional live certification via `live-demos.yml`.
4. Download the CI wheel into `dist/`, manifest and checksums into `evidence/`; verify with `shasum -c`, `twine check`, `scripts/validate_distribution.py`, `scripts/check_release_metadata.py --dist dist`.
5. Upload only the named wheel with Twine (never `dist/*`), verify with `scripts/verify_pypi_wheel.py`, then tag `vX.Y.Z` on that exact commit. The tag workflow verifies the PyPI hash and creates the GitHub release.
6. Prepare the `praval-ai` docs PR from the exact-wheel docs artifact; merge it only after PyPI serves the new version.

Never rebuild locally and upload a different artifact. Any source change after the CI build needs a new CI artifact.

### Version semantics
- **Major (X)**: breaking API changes
- **Minor (Y)**: new features, backward compatible
- **Patch (Z)**: fixes and documentation. In the 0.8 series, point releases (0.8.3, 0.8.4) also carry backward-compatible features.

## Environment Variables

```bash
# At least one LLM key
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...        # or GOOGLE_API_KEY
COHERE_API_KEY=...

PRAVAL_DEFAULT_PROVIDER=openai
PRAVAL_DEFAULT_MODEL=...
PRAVAL_CONFIG_FILE=...    # optional config file
PRAVAL_OBSERVABILITY=auto # auto | on | off
PRAVAL_OTLP_ENDPOINT=...
PRAVAL_SAMPLE_RATE=1.0
```

## Optional Dependencies

```bash
pip install praval[memory]         # ChromaDB, sentence-transformers
pip install praval[secure]         # RabbitMQ, encryption
pip install praval[storage]        # PostgreSQL, Redis, S3, Qdrant
pip install praval[pdf]            # PDF knowledge base
pip install praval[mcp]            # MCP client/server
pip install praval[observability]  # OpenTelemetry SDK and exporters
pip install praval[eval-ragas]     # RAGAS evaluation adapter
pip install praval[notebooks]      # Visual notebooks
pip install praval[docs]           # Sphinx documentation build
pip install praval[all]            # Everything
pip install praval[dev]            # Development tools
```

## Documentation

- Sphinx sources: `docs/sphinx/` (guides in `guide/`, API in `api/`, plus `observability/`, `evaluation/`, `tutorials/`).
- `make docs-html` builds locally; `make docs-serve` opens the built `index.html`.
- Published docs are staged into the `praval-ai` repo from the CI exact-wheel docs artifact (`make docs-deploy`, `scripts/stage_docs_artifact.py`), not from a local build.

## Related Repositories

- **Website**: https://pravalagents.com
- **praval-ai** (website and published docs): https://github.com/aiexplorations/praval-ai
- **PyPI**: https://pypi.org/project/praval/
- **GitHub**: https://github.com/aiexplorations/praval
- Downstream consumers: Praval Code (`~/Github/praval-code`) and PravalClaw (`~/Github/pravalclaw`).
