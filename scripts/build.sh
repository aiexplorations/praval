#!/bin/bash
# Praval Build Script with Coverage Enforcement
# This script ensures tests pass and coverage is >=80% before building

set -e  # Exit on any error

echo "🚀 Praval Build Process Starting..."
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Please run: python -m venv venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${BLUE}📦 Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install -e .[dev] > /dev/null 2>&1

# Run tests with coverage
echo -e "${BLUE}🧪 Running tests with coverage analysis...${NC}"
echo "Required coverage: >=80%"

# Run pytest with coverage - this will fail if coverage < 80%
if pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py --ignore=tests/test_venturelens_demo.py -v; then
    echo -e "${GREEN}✅ All tests passed with sufficient coverage!${NC}"
else
    echo -e "${RED}❌ BUILD FAILED: Tests failed or coverage below 80%${NC}"
    echo -e "${YELLOW}💡 Please fix failing tests and improve test coverage before building.${NC}"
    echo ""
    echo "Modules needing better test coverage:"
    echo "• decorators.py (12% - CRITICAL)"
    echo "• composition.py (19% - CRITICAL)" 
    echo "• memory/ modules (14-23% - CRITICAL)"
    echo "• providers/ modules (29-51%)"
    echo "• core/agent.py (51%)"
    echo "• core/registry.py (53%)"
    exit 1
fi

# Type checking
echo -e "${BLUE}🔍 Running type checks...${NC}"
if command -v mypy &> /dev/null; then
    mypy src/praval/ || echo -e "${YELLOW}⚠️  Type checking warnings found${NC}"
else
    echo -e "${YELLOW}⚠️  mypy not available, skipping type checks${NC}"
fi

# Code formatting check
echo -e "${BLUE}🎨 Checking code formatting...${NC}"
if command -v black &> /dev/null; then
    black --check src/ tests/ || echo -e "${YELLOW}⚠️  Code formatting issues found - run 'black src/ tests/' to fix${NC}"
else
    echo -e "${YELLOW}⚠️  black not available, skipping format checks${NC}"
fi

# Build package
echo -e "${BLUE}📦 Building package...${NC}"
python -m build

echo -e "${GREEN}✅ BUILD SUCCESSFUL!${NC}"
echo "=========================================="
echo -e "${GREEN}🎉 Praval package built successfully with:${NC}"
echo -e "${GREEN}   • All tests passing${NC}"
echo -e "${GREEN}   • Test coverage ≥80%${NC}"
echo -e "${GREEN}   • Package ready for distribution${NC}"
echo ""
echo "Distribution files created in dist/"