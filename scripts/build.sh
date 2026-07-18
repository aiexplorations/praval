#!/usr/bin/env bash
# Build and validate a Praval release candidate from the current source tree.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Keep the documented local build reproducible without requiring callers to
# duplicate the CI setup. An explicit epoch still wins for controlled rebuilds.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct HEAD)}"

if [[ ! -d venv ]]; then
    echo "Virtual environment not found. Run 'make setup' first." >&2
    exit 1
fi

source venv/bin/activate

echo "Installing development and documentation dependencies"
python -m pip install -e ".[dev,docs,mcp]"

echo "Running complete test suite and coverage gates"
pytest tests/ \
    --ignore=tests/test_arxiv_downloader.py \
    --ignore=tests/test_message_filtering.py \
    --ignore=tests/test_venturelens_demo.py \
    --cov=src/praval \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=json:coverage.json \
    --cov-fail-under=90
python scripts/check_coverage_floors.py coverage.json

echo "Running static quality gates"
python scripts/check_types.py
black --check src/ tests/ scripts/
isort --check-only src/ tests/ scripts/ --profile black
flake8 src/ tests/ scripts/ --max-line-length=88 --extend-ignore=E203,W503

echo "Building documentation with warnings treated as errors"
python scripts/check_release_metadata.py
python scripts/check_api_surface.py --report evidence/api-coverage.json
sphinx-build -b html -W --keep-going docs/sphinx docs/_build/html

echo "Building distribution artifacts"
rm -rf build dist
python -m build
python scripts/normalize_sdist.py dist/praval-*.tar.gz
twine check dist/*.whl dist/*.tar.gz
python scripts/validate_distribution.py dist
python scripts/write_build_manifest.py dist --evidence-dir evidence
python scripts/check_release_metadata.py --dist dist

echo "Praval release candidate passed all local build gates"
