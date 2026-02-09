# Repository Guidelines

## Project Structure & Module Organization
- `src/praval/`: Core framework code (agents, reef communication, memory, storage, observability, providers).
- `tests/`: Pytest suite, including `storage/` and `observability/` subfolders.
- `examples/`: Runnable examples (start with `examples/simple_multi_agent.py`).
- `docs/` and `docs/sphinx/`: Documentation sources and Sphinx build output.
- `scripts/`: Build and release scripts used by `make build`.

## Build, Test, and Development Commands
- `make setup`: Create `venv/` and install dev dependencies.
- `source venv/bin/activate`: Required before running `python`, `pip`, or `pytest` commands.
- `make test`: Run the default test suite (some tests are ignored via Makefile).
- `make test-cov`: Run tests with coverage reports.
- `make format`: Run Black and isort formatting.
- `make lint`: Run flake8 linting.
- `make type-check`: Run mypy type checks.
- `make build`: Build the package (enforces 80% coverage).
- `make docs-html`: Build Sphinx docs into `docs/_build/html/`.

## Coding Style & Naming Conventions
- Python style: PEP 8 with Black formatting (line length 88) and isort (`profile = black`).
- Linting: flake8 with `--max-line-length=88` and ignores `E203,W503`.
- Typing: mypy is configured with `disallow_untyped_defs = true`.
- Tests: name files `test_*.py` or `*_test.py`; use descriptive test function names.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`, `pytest-cov`.
- Markers: `unit`, `integration`, `performance`, `edge_case`, `knowledge_base`.
- Examples:
  - `pytest tests/ -v`
  - `pytest tests/ -m unit`
  - `pytest tests/test_decorators.py -v`
- Coverage: repo targets `>= 80%` (enforced in `make build`).

## Commit & Pull Request Guidelines
- Commit prefixes drive versioning (see `docs/CONTRIBUTING.md`):
  - Major: `BREAKING CHANGE: ...`, `major: ...`, `api change: ...`
  - Minor: `feat: ...`, `add: ...`, `enhance: ...`
  - Patch: `fix: ...`, `docs: ...`, `test: ...`, `refactor: ...`
- Recent history uses concise prefixes like `fix:` and `docs:`.
- PRs: include a clear summary, rationale, and linked issues; update docs/examples/tests as needed; ensure CI passes.

## Configuration & Dependencies
- Python 3.9+ required.
- Optional extras: `.[memory]`, `.[storage]`, `.[secure]`, `.[pdf]`, or `.[all]` for full features.
