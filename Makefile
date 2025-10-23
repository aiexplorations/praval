# Praval Development Makefile

.PHONY: help setup test test-cov build clean format lint type-check dev-install release

# Default target
help:
	@echo "Praval Development Commands:"
	@echo ""
	@echo "🛠️  Development:"
	@echo "  setup        - Set up development environment"
	@echo "  dev-install  - Install in development mode"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage report"
	@echo ""
	@echo "✨ Code Quality:"
	@echo "  format       - Format code with black and isort"
	@echo "  lint         - Run flake8 linting"
	@echo "  type-check   - Run mypy type checking"
	@echo ""
	@echo "📦 Build & Release:"
	@echo "  build        - Build package (requires 80% test coverage)"
	@echo "  release      - Interactive release wizard (patch/minor/major)"
	@echo "  clean        - Clean build artifacts"
	@echo ""
	@echo "📚 Documentation: See RELEASE.md for manual release process"

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

# Release target - interactive version bump and release
release:
	@echo "🚀 Praval Release Wizard"
	@echo ""
	@echo "Select version bump type:"
	@echo "  1) patch (0.7.7 → 0.7.8) - Bug fixes"
	@echo "  2) minor (0.7.7 → 0.8.0) - New features"
	@echo "  3) major (0.7.7 → 1.0.0) - Breaking changes"
	@echo ""
	@read -p "Enter choice (1/2/3): " choice; \
	case $$choice in \
		1) bump_type="patch";; \
		2) bump_type="minor";; \
		3) bump_type="major";; \
		*) echo "❌ Invalid choice"; exit 1;; \
	esac; \
	echo ""; \
	echo "📝 Bumping $$bump_type version..."; \
	./venv/bin/bump2version $$bump_type; \
	echo ""; \
	echo "✏️  Please update CHANGELOG.md with release notes"; \
	read -p "Press Enter when done..."; \
	echo ""; \
	echo "🔨 Building packages..."; \
	$(MAKE) clean; \
	./venv/bin/python -m build; \
	./venv/bin/twine check dist/*; \
	echo ""; \
	echo "📤 Ready to publish!"; \
	echo "Run: git push --follow-tags"; \
	echo "Then: twine upload dist/*"; \
	echo ""; \
	echo "📚 See RELEASE.md for detailed process"