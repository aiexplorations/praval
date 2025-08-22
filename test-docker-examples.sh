#!/bin/bash

# Test script for Praval containerized examples
# =============================================

set -e

echo "🐳 Testing Praval Containerized Examples"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed" 
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Test Docker file syntax
test_docker_files() {
    print_status "Validating Docker files..."
    
    # Check memory agents example
    if [ -f "examples/docker-examples/005-memory-agents/docker-compose.yml" ]; then
        docker-compose -f examples/docker-examples/005-memory-agents/docker-compose.yml config > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "Memory agents docker-compose.yml is valid"
        else
            print_error "Memory agents docker-compose.yml has syntax errors"
            exit 1
        fi
    else
        print_error "Memory agents docker-compose.yml not found"
        exit 1
    fi
    
    # Check storage example
    if [ -f "examples/docker-examples/010-unified-storage/docker-compose.yml" ]; then
        docker-compose -f examples/docker-examples/010-unified-storage/docker-compose.yml config > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "Unified storage docker-compose.yml is valid"
        else
            print_error "Unified storage docker-compose.yml has syntax errors"
            exit 1
        fi
    else
        print_error "Unified storage docker-compose.yml not found"
        exit 1
    fi
}

# Test Python scripts
test_python_scripts() {
    print_status "Validating Python scripts..."
    
    # Memory agents script
    if [ -f "examples/docker-examples/005-memory-agents/memory_agents_containerized.py" ]; then
        python3 -m py_compile examples/docker-examples/005-memory-agents/memory_agents_containerized.py
        if [ $? -eq 0 ]; then
            print_success "Memory agents Python script compiles successfully"
        else
            print_error "Memory agents Python script has syntax errors"
            exit 1
        fi
    else
        print_error "Memory agents Python script not found"
        exit 1
    fi
    
    # Storage demo script
    if [ -f "examples/docker-examples/010-unified-storage/unified_storage_containerized.py" ]; then
        python3 -m py_compile examples/docker-examples/010-unified-storage/unified_storage_containerized.py
        if [ $? -eq 0 ]; then
            print_success "Unified storage Python script compiles successfully"
        else
            print_error "Unified storage Python script has syntax errors"
            exit 1
        fi
    else
        print_error "Unified storage Python script not found"
        exit 1
    fi
}

# Test shell scripts
test_shell_scripts() {
    print_status "Validating shell scripts..."
    
    # Memory agents run script
    if [ -f "examples/docker-examples/005-memory-agents/run-memory-demo.sh" ]; then
        bash -n examples/docker-examples/005-memory-agents/run-memory-demo.sh
        if [ $? -eq 0 ]; then
            print_success "Memory demo shell script is valid"
        else
            print_error "Memory demo shell script has syntax errors"
            exit 1
        fi
    fi
    
    # Storage demo run script
    if [ -f "examples/docker-examples/010-unified-storage/run-storage-demo.sh" ]; then
        bash -n examples/docker-examples/010-unified-storage/run-storage-demo.sh
        if [ $? -eq 0 ]; then
            print_success "Storage demo shell script is valid"
        else
            print_error "Storage demo shell script has syntax errors"
            exit 1
        fi
    fi
}

# Test environment templates
test_env_templates() {
    print_status "Validating environment templates..."
    
    # Check env templates exist
    examples=("005-memory-agents" "010-unified-storage")
    
    for example in "${examples[@]}"; do
        env_file="examples/docker-examples/$example/.env.example"
        if [ -f "$env_file" ]; then
            # Basic validation - check for required keys
            if grep -q "OPENAI_API_KEY" "$env_file"; then
                print_success "$example environment template is valid"
            else
                print_warning "$example environment template missing OPENAI_API_KEY"
            fi
        else
            print_error "$example environment template not found"
        fi
    done
}

# Show example structure
show_structure() {
    print_status "Docker examples structure:"
    echo ""
    tree examples/docker-examples/ 2>/dev/null || find examples/docker-examples/ -type f | sort
    echo ""
}

# Main test execution
main() {
    echo ""
    print_status "Starting containerized examples validation..."
    echo ""
    
    check_prerequisites
    echo ""
    
    test_docker_files
    echo ""
    
    test_python_scripts
    echo ""
    
    test_shell_scripts  
    echo ""
    
    test_env_templates
    echo ""
    
    show_structure
    
    echo ""
    print_success "All containerized examples validated successfully!"
    echo ""
    print_status "To run the examples:"
    echo "  1. cd examples/docker-examples/005-memory-agents"
    echo "  2. cp .env.example .env  # Add your API keys"
    echo "  3. docker-compose up"
    echo ""
    print_status "Or for unified storage:"
    echo "  1. cd examples/docker-examples/010-unified-storage" 
    echo "  2. cp .env.example .env  # Add your API keys"
    echo "  3. docker-compose up"
    echo ""
}

# Run main function
main "$@"