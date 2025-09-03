# Changelog

All notable changes to the Praval project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.4] - 2024-12-03

### Added
- Comprehensive knowledge base benchmark tests (`test_knowledge_base_benchmark.py`)
- Pytest custom markers for better test organization (unit, integration, performance, edge_case, knowledge_base)

### Fixed
- Version discrepancy in `__init__.py` docstring 
- Pytest marker warnings by adding proper marker configuration in `pyproject.toml`

### Improved
- Test coverage for knowledge base functionality with performance benchmarks
- Documentation accuracy for current version features

## [0.6.2] - 2025-08-21

### Added
- 🐳 **Containerized Examples Infrastructure** - Production-ready Docker deployments
  - **Memory Agents Container**: Complete setup for memory-enabled agent demonstrations
  - **Unified Storage Container**: Full-stack demo with PostgreSQL, Redis, MinIO, Qdrant
  - **Shell Script Orchestration**: End-to-end automation with service health monitoring
  - **Multi-Service Docker Compose**: Professional development and testing environments

### Fixed
- 🔧 **Qdrant Docker Health Check**: Updated to use `/readyz` endpoint with bash networking
- 📚 **Example Organization**: Properly renumbered examples and fixed import issues
- 🔑 **Environment Configuration**: Added `load_dotenv()` support to all examples
- 🧪 **Testing Infrastructure**: Comprehensive validation scripts for containerized examples

### Enhanced
- 🗄️ **Cross-Storage Operations**: Demonstrated filesystem + PostgreSQL integration
- 📊 **Production Logging**: Enhanced monitoring and result reporting
- 🚀 **Developer Experience**: One-command Docker setup with automatic cleanup

## [0.6.1] - 2025-08-20

### Added
- 🗄️ **Unified Data Storage & Retrieval System** - Enterprise-grade data ecosystem
  - **Base Provider Framework**: Abstract base class for consistent storage interfaces
  - **Storage Registry**: Centralized provider discovery with permissions and health monitoring
  - **Built-in Providers**: Production-ready PostgreSQL, Redis, S3, Qdrant, and FileSystem providers
  - **Storage Decorators**: `@storage_enabled()` and `@requires_storage()` for declarative access
  - **Data References**: Lightweight sharing of large datasets through spore communication
  - **Memory Integration**: Unified interface combining memory system with external storage
  - **Cross-Storage Operations**: Query and manage data across multiple storage backends
- 📊 **Enhanced Data Management**
  - Async connection pooling and health monitoring
  - Smart storage selection based on data characteristics
  - Batch operations for high-throughput scenarios
  - Security with permission-based access control per agent
  - Environment-based auto-registration of storage providers
- 📖 **Comprehensive Documentation**
  - Complete PART VI section in praval.md (800+ lines)
  - Production examples demonstrating multi-storage workflows
  - Integration patterns and best practices
  - Storage provider development guide

### Enhanced
- 🔄 **Spore Communication System**
  - Enhanced spore protocol to support data references
  - Added `data_references` field for lightweight large data sharing
  - Methods: `add_data_reference()`, `has_data_references()`, `has_any_references()`
- 🧠 **Memory System Integration**
  - Bridge between existing memory system and external storage
  - Unified memory-storage interface for agents
  - Cross-system data operations and retrieval
- 📦 **Framework Exports**
  - Added comprehensive storage system exports with graceful fallbacks
  - New exports: `BaseStorageProvider`, `StorageRegistry`, `DataManager`, all providers
  - `STORAGE_AVAILABLE` flag for optional dependency handling

### Examples
- 📊 **Unified Storage Demo** (`examples/unified_storage_demo.py`)
  - Multi-agent workflow demonstrating PostgreSQL, Redis, and S3 integration
  - Data collection, analysis, and reporting across storage backends
  - Production-ready patterns for enterprise deployments

### Changed
- Updated version to 0.6.1 across all configuration files
- Enhanced framework documentation to reflect new capabilities
- Improved error handling throughout storage system

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