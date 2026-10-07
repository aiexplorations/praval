# Repository Guidelines

Short form of `CLAUDE.md`, which has the full detail. Keep the two in sync: a process change goes into both.

## Project Structure
- `src/praval/`: framework code. `model_runtime.py` (requests, retries, tool loop, streaming, HITL resume), `models/` (provider-neutral contracts), `providers/` (OpenAI, Anthropic, Gemini, Cohere, OpenAI-compatible local servers, registry), `core/` (Agent, Reef, Spore), `decorators.py` (`@agent`, `chat`, `broadcast`), `hitl/`, `memory/`, `storage/`, `observability/`, `eval/`, `mcp/`.
- `tests/`: pytest suite, with `eval/`, `mcp/`, `observability/`, `storage/`, `integration/` (needs services), `performance/`, `validation/`.
- `examples/`: examples and notebooks; `examples/certification/` holds exact-wheel and live provider checks.
- `docs/`: Markdown docs, Sphinx sources (`docs/sphinx/`), release notes (`docs/releases/`), documentation contracts (`api-surface.toml`, `feature-claims.toml`, `documentation-coverage.toml`).
- `plans/`: roadmap and release plans. `scripts/`: build, release, typing, coverage and smoke scripts.

## Environment
- Python 3.10 to 3.14. Always `source venv/bin/activate` before `python`, `pip` or `pytest`; `make setup` creates it.
- Version: `pyproject.toml` only; `praval.__version__` comes from distribution metadata.

## Build, Test, and Development Commands
- `make test`: test suite with the CI exclusions (`test_arxiv_downloader.py`, `test_message_filtering.py`, `test_venturelens_demo.py`).
- `make test-cov`: coverage, `--cov-fail-under=90`, plus per-file floors (`scripts/check_coverage_floors.py`).
- `make format` (Black + isort), `make lint` (flake8), `make type-check` (`scripts/check_types.py`: strict 3.13 and 3.10 compatibility).
- `make docs-html`: Sphinx build. CI builds with `-W`, so any warning fails.
- Before pushing, run what CI runs: tests with `--timeout=60 --timeout-method=thread`; `black --check` and `isort --check-only --profile black` and `flake8` over `src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py`; `scripts/check_types.py`; `scripts/check_release_metadata.py`; `scripts/check_api_surface.py`.

## Coding Style
- PEP 8, Black (88), isort (`profile = black`), flake8 ignoring `E203,W503`.
- Full type hints; code must type-check on Python 3.10 as well as 3.13.
- Specific exception types; `logging`, not `print`, in library code. Match surrounding code.

## Testing
- `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-timeout`. Markers: `unit`, `integration`, `performance`, `edge_case`, `knowledge_base`.
- Unit tests never call the network; provider behaviour uses recorded fixtures or deterministic fake clients.
- Live provider checks are in `examples/certification/` (for example `live_provider_matrix.py`), need real keys, and cost money.

## Documentation Contracts
- Every `praval.__all__` export is listed once in `docs/api-surface.toml` and documented on that surface's Sphinx page.
- `docs/feature-claims.toml` claims cite their test evidence.
- User-facing changes go in `CHANGELOG.md` under `[Unreleased]` and the matching guide in `docs/sphinx/guide/`.

## Commits, Branches and Pull Requests
- Branch from `main`; never commit to `main` directly. Earlier work used `codex/<topic>`; v0.8.4 uses `release/v0.8.4` with feature branches merged into it.
- Prefixes: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `build:`; `BREAKING CHANGE:` for incompatible changes.
- PRs: summary, risk notes, test evidence, migration notes for behaviour changes; checklist in `CONTRIBUTING.md`.

## Release
- `RELEASE.md` is authoritative. The only artifact released is the wheel built by `main` CI: download it, verify it, upload that named wheel with Twine, verify it on PyPI, then tag the exact commit. Never rebuild or upload a different local artifact.

## Optional Dependencies
- Extras: `memory`, `secure`, `storage`, `pdf`, `mcp`, `observability`, `eval-ragas`, `notebooks`, `docs`, `all`, `dev`.
