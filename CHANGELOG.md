# Changelog

All notable changes to the Praval project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.11] - 2025-11-05

### Added
- 📊 **Built-in Observability Framework** - Comprehensive, zero-configuration distributed tracing for multi-agent systems
  - **Automatic Instrumentation**: All agents, reef communication, memory operations, storage I/O, and LLM calls automatically traced
  - **OpenTelemetry Export**: OTLP compliance with support for Jaeger, Zipkin, Honeycomb, DataDog, New Relic
  - **Console Viewer**: Rich terminal output with tree hierarchy, ANSI colors, timing, and statistics
  - **Local Storage**: SQLite backend with query interface and trace retrieval
  - **<5% Overhead**: Minimal performance impact with configurable sampling (0.0-1.0)

### Features
- **Zero Configuration**: Auto-detection based on environment (dev vs production)
- **Trace Context Propagation**: Automatic parent-child span relationships across agents via Spore metadata
- **Four Span Kinds**: SERVER (agent execution), CLIENT (LLM/storage), PRODUCER (reef comms), INTERNAL (memory ops)
- **Query Interface**: Find spans by name, status, duration, trace ID with built-in analytics

### Documentation
- **`docs/observability/README.md`**: Comprehensive usage guide
- **`docs/observability/quickstart.md`**: Quick start tutorial
- **4 Examples**: Quickstart, basic tracing, configuration, context propagation demos

### Statistics
- **~2,500 lines**: Core implementation
- **~1,300 lines**: Tests (78 tests, 94% passing)
- **~800 lines**: Documentation
- **33 new files**: 10 implementation, 7 test, 4 example, 2 docs

### Configuration
```bash
PRAVAL_OBSERVABILITY="on"  # on, off, or auto (default)
PRAVAL_OTLP_ENDPOINT="http://localhost:4318/v1/traces"
PRAVAL_SAMPLE_RATE="1.0"  # 0.0-1.0
```

### Breaking Changes
**None** - Fully backward compatible, opt-in feature

## [0.7.10] - 2025-10-28

### Fixed
- 🐛 **Jupyter Duplicate Execution** - Agents no longer execute multiple times when re-registering in notebooks
- 🔧 **Channel Subscription** - Added `replace` parameter to `subscribe()` to prevent handler accumulation

### Added
- 🎓 **Student Analytics AI Example** - Interactive notebook with 6 AI-powered agents analyzing student performance
- 🎨 **AI Code Generation** - Visualization agent dynamically generates matplotlib code (not templates!)
- 📚 **Documentation Infrastructure** - Sphinx setup with 5 new make targets (docs-html, docs-serve, docs-clean, docs-check, docs-deploy)
- 🧪 **Interactive Environment Tests** - Comprehensive test suite (165 lines) for notebook scenarios
- 📖 **Building Agents Tutorial** - Step-by-step Jupyter notebook for learning Praval

### Changed
- 🎯 **Default Subscribe Behavior** - Now replaces handlers by default (set `replace=False` for append behavior)

### Examples
- `student_analytics_ai.ipynb` - 6 AI agents with parallel execution and code generation (198KB)
- `student_analytics.py` - Python script version for CLI execution (16KB)
- `building_agents_tutorial.ipynb` - Interactive tutorial (82KB)

### Technical Details
- Modified: `src/praval/core/reef.py` (~40 lines)
- Added: `tests/test_duplicate_agent_registration.py` (165 lines)
- Enhanced: Makefile with documentation targets
- Updated: pyproject.toml with `[docs]` dependency group

### Benefits
- ✅ Seamless Jupyter notebook development
- ✅ Showcase of true multi-agent AI collaboration
- ✅ Demonstrates AI creativity through code generation
- ✅ Production-ready documentation infrastructure

## [0.7.9] - 2025-10-23

### Changed
- 🚀 **Flexible Installation Options** - Choose your installation size!
  - **Minimal** (`pip install praval`): ~50MB - Core agents and LLM providers only
  - **Memory** (`pip install praval[memory]`): ~500MB - Adds vector storage and embeddings
  - **Full** (`pip install praval[all]`): ~1.5GB - All features including enterprise messaging

- 📦 **Restructured Dependencies**:
  - Core: Only essential LLM providers and configuration (~50MB vs ~1.5GB)
  - Optional extras: `[memory]`, `[secure]`, `[pdf]`, `[storage]`, `[all]`
  - Faster installation for users who don't need all features
  - Reduced barrier to entry for new users

### Added
- 🔧 **New Installation Extras**:
  - `praval[memory]` - ChromaDB, sentence-transformers, scikit-learn
  - `praval[secure]` - Secure Spores with AMQP, MQTT, STOMP, encryption
  - `praval[pdf]` - PDF knowledge base support
  - `praval[storage]` - PostgreSQL, Redis, S3, Qdrant providers
  - `praval[all]` - Everything combined

### Documentation
- Updated README with clear installation options and size comparisons
- Updated requirements.txt with commented optional dependencies
- Added feature-to-dependency mapping

### Benefits
- ⚡ 30x faster minimal installation (~2min vs ~10min)
- 💾 30x smaller minimal package (~50MB vs ~1.5GB)
- 🎯 Users only install what they need
- 🚀 Lower barrier to entry for new users

## [0.7.8] - 2025-10-23

### Changed
- 🔒 **Distribution Strategy** - Now distributing wheel-only packages to PyPI
  - Source code, examples, and documentation remain private
  - Only compiled wheel (.whl) available on PyPI
  - Users can install via `pip install praval` but cannot access source
  - Full source available on GitHub when project is open-sourced

### Infrastructure
- Updated release process to upload wheels only
- Enhanced Makefile with interactive release wizard
- Improved documentation organization

### Note
This is a re-release to implement wheel-only distribution strategy.
Versions 0.7.6 and 0.7.7 have been removed from PyPI.

## [0.7.7] - 2025-10-23

### Added
- 📦 **Manual Release Process Documentation** - Comprehensive RELEASE.md guide
  - Step-by-step instructions for version bumping
  - PyPI publication workflow
  - Testing and verification procedures
  - Rollback and troubleshooting guides
- 🔧 **GitHub Actions Workflow** - Automated release infrastructure (disabled by default)
  - Automatic version detection from commit messages
  - PyPI upload automation
  - GitHub release creation
  - Can be enabled when ready for automated releases

### Changed
- 🎯 **Version Control Strategy** - Moved to manual deliberate version bumps
  - Auto-versioning workflow disabled for more control
  - Prevents accidental major version jumps
  - Ensures version 1.0.0 is a deliberate milestone decision
- 📚 **Repository Organization** - Comprehensive cleanup and documentation
  - Documentation organized in docs/ with archive/ subdirectory
  - Removed redundant files and build artifacts
  - Enhanced PyPI metadata with keywords and project URLs
  - Added UV installation support

### Fixed
- 🔒 **Security** - Removed exposed API keys from repository
  - Cleaned .env files from git history
  - Enhanced .gitignore patterns
  - Proper credential management documentation
- 🧪 **Test Suite** - Fixed import errors in test files
  - Corrected module paths (src.praval → praval)
  - Added test environment setup for CI/CD
  - All core tests now passing

### Infrastructure
- ✅ PyPI publication ready (v0.7.6 successfully published)
- ✅ UV package manager compatible
- ✅ GitHub Actions infrastructure configured
- ✅ Comprehensive release documentation

## [0.7.6] - 2024-12-03

### Added
- 🏗️ **Collection Separation Architecture** - Separate ChromaDB collections for knowledge base vs conversational memory
  - **Knowledge Collection**: Immutable storage for semantic memories (knowledge base files, facts)
  - **Memory Collection**: Mutable storage for episodic and conversational memories
  - **Smart Memory Routing**: Automatic routing based on memory type (semantic → knowledge, others → memory)
  - **Cross-Collection Operations**: Search, retrieve, and stats work seamlessly across both collections

### Enhanced
- 🛡️ **Data Integrity & Security**
  - Immutable knowledge base - knowledge cannot be deleted, providing data protection
  - Selective deletion policy - only conversational memory can be deleted
  - Safe memory clearing - `clear_agent_memories()` preserves knowledge base, only clears conversations
- 🔄 **Migration & Compatibility**
  - Automatic migration from legacy single collections to separated architecture
  - Zero-downtime migration - existing data is preserved and properly migrated
  - Backward compatibility - legacy single-collection mode still supported
- 📊 **Enhanced Features**
  - Detailed statistics with separate metrics for knowledge vs conversational memories
  - Health monitoring across both collections
  - Memory manager integration with separated collections enabled by default

### Fixed
- ChromaDB API compatibility issues with `get()` vs `query()` result structures
- Numpy array boolean evaluation errors in memory operations
- Collection migration edge cases and error handling
- Memory retrieval across separated collections

### Technical
- 17 comprehensive test cases covering initialization, storage, routing, migration
- Production-ready implementation with proper error handling and logging
- Enhanced documentation and code comments

## [0.7.5] - 2024-12-03

### Fixed
- ChromaDB collection initialization error when collections don't exist
- Knowledge base auto-indexing now works correctly with memory-only fallback scenarios
- Exception handling for ChromaDB NotFoundError instead of ValueError

### Improved
- More robust error handling during ChromaDB collection creation
- Better integration between @agent decorator and knowledge base functionality
- Automatic collection creation with proper metadata configuration

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