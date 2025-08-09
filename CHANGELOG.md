# Changelog

All notable changes to the Praval project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2025-08-09

### Added
- 🧠 Comprehensive multi-layered memory system
  - Short-term memory for working context
  - Long-term memory with ChromaDB vector storage
  - Episodic memory for conversation history
  - Semantic memory for knowledge and facts
- 📊 Production-ready testing suite
  - 99% test coverage on decorators module
  - 100% test coverage on composition workflows
  - 4,750+ lines of comprehensive memory system tests
- ✨ Enhanced agent capabilities
  - Memory-enabled agents with persistent knowledge
  - Dynamic knowledge reference creation and resolution
  - Advanced agent communication patterns
  - Knowledge base integration for document indexing
- 📚 Complete documentation overhaul
  - Updated README.md with v0.5.0 features
  - Enhanced praval.md with comprehensive documentation
  - 1.5MB complete manual PDF
  - 9 progressive learning examples (001-009)
- 🏗️ Production infrastructure
  - Docker support with development environment
  - Modern Python packaging with pyproject.toml
  - Pre-commit hooks and CI/CD configuration
  - Repository reorganization with proper structure

### Changed
- Updated version numbering to follow semantic versioning
- Reorganized repository structure for better maintainability
- Enhanced error handling and resilience throughout framework

### Removed
- Legacy example files that were replaced with new progressive series
- Deprecated API patterns in favor of cleaner decorator approach

## Version Bump Keywords

Use these keywords in commit messages to trigger automatic version bumps:

### Major Version (Breaking Changes)
- `BREAKING CHANGE:` or `breaking change:`
- `major:` - Major version bump
- `api change:` - API breaking changes
- `breaking:` - Breaking functionality changes

### Minor Version (New Features)
- `feat:` or `feature:` - New features
- `add:` or `new:` - New functionality
- `enhance:` - Enhancements to existing features
- `memory system:` - Memory system changes
- `agent capability:` - New agent capabilities
- Changes to `decorators.py`, `core/agent.py`, or `core/reef.py`

### Patch Version (Bug Fixes)
- `fix:` or `patch:` - Bug fixes
- `bug:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test improvements
- `refactor:` - Code refactoring
- `style:` - Code style changes
- `chore:` - Maintenance tasks

[Unreleased]: https://github.com/aiexplorations/praval/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/aiexplorations/praval/releases/tag/v0.5.0