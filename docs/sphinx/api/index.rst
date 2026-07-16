.. _api-reference:

=============
API Reference
=============

The API reference is generated from source docstrings. The supported surface
is classified in ``docs/api-surface.toml``. That manifest maps every top-level
export to its stability class and canonical guide. Prefer top-level ``praval``
exports unless a guide explicitly documents a public submodule.

.. contents:: API Modules
   :local:
   :depth: 1

Core API
========

The :mod:`praval` package re-exports the supported convenience surface. The
pages below document the modules that define those objects, avoiding duplicate
entries for the same class or function.

.. autosummary::
   :toctree: generated

   praval.app
   praval.core.agent
   praval.core.reef
   praval.core.registry
   praval.core.exceptions

Model Runtime
=============

.. autosummary::
   :toctree: generated

   praval.models
   praval.model_runtime
   praval.providers.registry
   praval.embeddings

Decorators And Composition
==========================

.. autosummary::
   :toctree: generated

   praval.decorators
   praval.composition

Providers
=========

.. autosummary::
   :toctree: generated

   praval.providers.factory
   praval.providers.openai
   praval.providers.anthropic
   praval.providers.cohere
   praval.providers.gemini
   praval.providers.openai_compatible

Tool System
===========

.. autosummary::
   :toctree: generated

   praval.tools
   praval.core.tool_registry

Human-in-the-Loop And MCP
=========================

.. autosummary::
   :toctree: generated

   praval.hitl.models
   praval.hitl.policy
   praval.hitl.service
   praval.hitl.store
   praval.hitl.runtime
   praval.mcp.client

Memory System
=============

.. autosummary::
   :toctree: generated

   praval.memory.memory_manager
   praval.memory.short_term_memory
   praval.memory.long_term_memory
   praval.memory.episodic_memory
   praval.memory.semantic_memory
   praval.memory.memory_types

Storage System
==============

.. autosummary::
   :toctree: generated

   praval.storage.data_manager
   praval.storage.base_provider
   praval.storage.storage_registry
   praval.storage.decorators
   praval.storage.providers.filesystem
   praval.storage.providers.postgresql
   praval.storage.providers.qdrant_provider
   praval.storage.providers.redis_provider
   praval.storage.providers.s3_provider

Observability
=============

.. autosummary::
   :toctree: generated

   praval.observability.config
   praval.observability.tracing.context
   praval.observability.tracing.tracer
   praval.observability.storage.sqlite_store
   praval.observability.export.console_viewer
   praval.observability.export.otlp_exporter
   praval.observability.instrumentation.manager
