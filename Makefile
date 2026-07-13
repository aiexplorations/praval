# Praval Development Makefile

.PHONY: help setup test test-cov build package-check reproducible-build clean format lint type-check dev-install release docs-html docs-clean docs-serve docs-check pdf pdf-lualatex pdf-xelatex pdf-tectonic pdf-compare pdf-clean

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
	@echo "📚 Documentation:"
	@echo "  docs-html    - Build HTML documentation with Sphinx"
	@echo "  docs-clean   - Clean documentation build artifacts"
	@echo "  docs-serve   - Build and open documentation in browser"
	@echo "  docs-check   - Check documentation for errors"
	@echo "  docs-deploy  - Build and deploy docs to praval-ai website"
	@echo ""
	@echo "📄 PDF Manual:"
	@echo "  pdf          - Generate PDF with LuaLaTeX (recommended)"
	@echo "  pdf-lualatex - Generate PDF with LuaLaTeX engine"
	@echo "  pdf-xelatex  - Generate PDF with XeLaTeX engine"
	@echo "  pdf-tectonic - Generate PDF with Tectonic engine"
	@echo "  pdf-compare  - Generate PDFs with all engines for comparison"
	@echo "  pdf-clean    - Clean generated PDFs"
	@echo ""
	@echo "📦 Build & Release:"
	@echo "  build        - Build package (requires 90% test coverage)"
	@echo "  package-check - Validate existing wheel and sdist"
	@echo "  reproducible-build - Build twice and compare artifacts"
	@echo "  release      - Interactive release wizard (patch/minor/major)"
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
	./venv/bin/pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py --ignore=tests/test_venturelens_demo.py --cov=src/praval --cov-report=term-missing --cov-report=html --cov-report=json:coverage.json --cov-fail-under=90
	./venv/bin/python scripts/check_coverage_floors.py coverage.json

build:
	@echo "🚀 Building Praval with complete-package coverage enforcement..."
	./scripts/build.sh

package-check:
	./venv/bin/twine check dist/*
	./venv/bin/python scripts/validate_distribution.py dist

reproducible-build:
	./scripts/check_reproducible_build.sh

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
	./venv/bin/pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py --ignore=tests/test_venturelens_demo.py --cov=src/praval --cov-report=json:coverage.json --cov-fail-under=90
	./venv/bin/python scripts/check_coverage_floors.py coverage.json
	@echo "✅ Coverage requirement met!"

# Releases are produced and published by protected GitHub workflows.
release:
	@echo "Direct local publication is disabled."
	@echo "Run 'make build', validate the exact CI artifact in Praval Research,"
	@echo "then use the protected tag and trusted-publishing workflows."
	@exit 1

# Documentation targets
docs-html:
	@echo "📚 Building HTML documentation..."
	@if [ ! -d "venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Installing documentation dependencies..."
	./venv/bin/pip install -e ".[docs]" > /dev/null
	@echo "Running Sphinx build..."
	cd docs/sphinx && ../../venv/bin/sphinx-build -b html . ../_build/html
	@echo "✅ Documentation built successfully!"
	@echo "📖 Open: docs/_build/html/index.html"

docs-clean:
	@echo "🧹 Cleaning documentation build artifacts..."
	rm -rf docs/_build/
	rm -rf docs/sphinx/api/generated/
	@echo "✅ Documentation cleaned!"

docs-serve: docs-html
	@echo "🌐 Opening documentation in browser..."
	@if command -v open > /dev/null; then \
		open docs/_build/html/index.html; \
	elif command -v xdg-open > /dev/null; then \
		xdg-open docs/_build/html/index.html; \
	else \
		echo "📖 Please open: docs/_build/html/index.html"; \
	fi

docs-check:
	@echo "🔍 Checking documentation for errors..."
	@if [ ! -d "venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	./venv/bin/pip install -e ".[docs]" > /dev/null
	cd docs/sphinx && ../../venv/bin/sphinx-build -b html -W --keep-going . ../_build/html
	@echo "✅ Documentation check passed!"

docs-deploy: docs-html
	@echo "🚀 Deploying documentation to praval-ai website..."
	./scripts/deploy-docs.sh
	@echo "✅ Documentation deployed!"
	@echo ""
	@echo "📋 Next: cd ~/Github/praval-ai && git add docs/ && git commit && git push"

# PDF Manual Generation
PDF_DIR = docs/generated
MANUAL_SRC = docs/praval-manual.md
COMMON_OPTS = -V geometry:margin=1.2in \
              -V fontsize=11pt \
              -V linestretch=1.15 \
              -V linkcolor=blue \
              -V urlcolor=blue \
              --toc \
              --toc-depth=2 \
              --number-sections \
              --highlight-style=tango

$(PDF_DIR):
	mkdir -p $(PDF_DIR)

# LuaLaTeX (Recommended)
pdf-lualatex: $(PDF_DIR)
	@echo "📄 Generating PDF with LuaLaTeX..."
	pandoc $(MANUAL_SRC) -o $(PDF_DIR)/praval-manual.pdf \
		--pdf-engine=lualatex \
		-V documentclass=report \
		-V logo=docs/assets/logo.png \
		$(COMMON_OPTS) \
		--pdf-engine-opt=-shell-escape
	@echo "✅ Generated: $(PDF_DIR)/praval-manual.pdf"

# XeLaTeX (Current)
pdf-xelatex: $(PDF_DIR)
	@echo "📄 Generating PDF with XeLaTeX..."
	pandoc $(MANUAL_SRC) -o $(PDF_DIR)/praval-manual-xelatex.pdf \
		--pdf-engine=xelatex \
		$(COMMON_OPTS)
	@echo "✅ Generated: $(PDF_DIR)/praval-manual-xelatex.pdf"

# Tectonic (Modern, requires installation)
pdf-tectonic: $(PDF_DIR)
	@if command -v tectonic >/dev/null 2>&1; then \
		echo "📄 Generating PDF with Tectonic..."; \
		pandoc $(MANUAL_SRC) -o $(PDF_DIR)/praval-manual-tectonic.pdf \
			--pdf-engine=tectonic \
			$(COMMON_OPTS); \
		echo "✅ Generated: $(PDF_DIR)/praval-manual-tectonic.pdf"; \
	else \
		echo "❌ Tectonic not installed. Run: brew install tectonic"; \
		exit 1; \
	fi

# Generate all versions for comparison
pdf-compare: $(PDF_DIR)
	@echo "📊 Generating PDFs with all engines for comparison..."
	@echo ""
	@echo "1/3 - LuaLaTeX..."
	@$(MAKE) pdf-lualatex --no-print-directory
	@echo ""
	@echo "2/3 - XeLaTeX..."
	@$(MAKE) pdf-xelatex --no-print-directory
	@echo ""
	@echo "3/3 - Tectonic (if available)..."
	@$(MAKE) pdf-tectonic --no-print-directory || echo "   (skipped - not installed)"
	@echo ""
	@echo "✅ All PDFs generated in $(PDF_DIR)/"
	@echo ""
	@echo "File sizes:"
	@ls -lh $(PDF_DIR)/praval-manual*.pdf 2>/dev/null | awk '{print "  " $$9 " - " $$5}' || echo "  No PDFs found"

# Default PDF target (uses recommended engine)
pdf: pdf-lualatex

# Clean generated PDFs
pdf-clean:
	@echo "🧹 Cleaning generated PDFs..."
	rm -f $(PDF_DIR)/praval-manual*.pdf
	@echo "✅ PDFs cleaned"
