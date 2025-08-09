# Praval Development Makefile

.PHONY: help setup test test-cov build clean format lint type-check dev-install

# Default target
help:
	@echo "Praval Development Commands:"
	@echo "  setup        - Set up development environment"
	@echo "  dev-install  - Install in development mode"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage report"
	@echo "  build        - Build package (requires 80% test coverage)"
	@echo "  format       - Format code with black and isort"
	@echo "  lint         - Run flake8 linting"
	@echo "  type-check   - Run mypy type checking"
	@echo "  clean        - Clean build artifacts"

setup:
	@echo "Setting up Praval development environment..."
	python -m venv venv
	./venv/bin/pip install -U pip setuptools wheel
	./venv/bin/pip install -e .[dev]
	@echo "✅ Development environment ready!"

dev-install:
	./venv/bin/pip install -e .[dev]

test:
	./venv/bin/pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py --ignore=tests/test_venturelens_demo.py -v

test-cov:
	./venv/bin/pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py --ignore=tests/test_venturelens_demo.py --cov=src/praval --cov-report=term-missing --cov-report=html

build:
	@echo "🚀 Building Praval with coverage enforcement..."
	./scripts/build.sh

format:
	./venv/bin/black src/ tests/
	./venv/bin/isort src/ tests/ --profile black

lint:
	./venv/bin/flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203,W503

type-check:
	./venv/bin/mypy src/praval/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Coverage enforcement target
coverage-check:
	@echo "Checking test coverage..."
	./venv/bin/pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py --ignore=tests/test_venturelens_demo.py --cov=src/praval --cov-fail-under=80
	@echo "✅ Coverage requirement met!"