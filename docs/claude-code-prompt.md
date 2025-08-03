# Claude Code Prompt: Build Praval Phase 1

## Project Overview

Build Praval, a pure Python framework for LLM-based agents inspired by coral ecosystems. Just as corals are simple organisms that create complex structures through collaboration, Praval enables simple agents to work together for sophisticated behaviors.

**Core Philosophy**: Extreme simplicity and composability. A functional agent in 5 lines of code or less.

## Development Approach
W
### Mandatory Practices

1. **Test-Driven Development (TDD)**
   - Write the test FIRST, then implement the feature
   - Every public method must have tests
   - Aim for >90% test coverage
   - Use pytest for all testing

2. **Real Implementations Only**
   - NO mock implementations or placeholder code
   - NO "TODO" or "implement later" comments
   - Every feature must be fully functional
   - If you can't implement it fully, don't include it

3. **Python Best Practices**
   - Type hints on all public APIs
   - Docstrings in Google style for all public methods
   - Follow PEP 8 strictly
   - Use dataclasses for data structures
   - Proper error handling with custom exceptions