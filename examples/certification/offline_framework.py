"""Certify core Praval behavior without network or provider credentials."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import tempfile
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

os.environ["PRAVAL_OBSERVABILITY"] = "on"
if os.environ.get("PRAVAL_DEMO_REPORT_DIR"):
    Path(os.environ["PRAVAL_DEMO_REPORT_DIR"]).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(
        "PRAVAL_TRACES_PATH",
        str(Path(os.environ["PRAVAL_DEMO_REPORT_DIR"]) / "offline-traces.sqlite3"),
    )
    os.environ.setdefault(
        "PRAVAL_HITL_DB_PATH",
        str(Path(os.environ["PRAVAL_DEMO_REPORT_DIR"]) / "offline-hitl.sqlite3"),
    )

from support import (  # noqa: E402
    CertificationProvider,
    report_dir,
    write_json_artifact,
)

from praval import (  # noqa: E402
    Agent,
    ContentPart,
    EmbeddingRuntime,
    PravalApp,
    Spore,
    SporeType,
    ToolSpec,
    get_provider_registry,
)
from praval.core.reef import Reef  # noqa: E402
from praval.memory.embedded_store import EmbeddedVectorStore  # noqa: E402
from praval.memory.memory_manager import MemoryManager  # noqa: E402
from praval.memory.memory_types import MemoryQuery, MemoryType  # noqa: E402
from praval.models import ProviderProfile  # noqa: E402
from praval.observability import SQLiteTraceStore, Tracer  # noqa: E402
from praval.observability.export import ConsoleViewer  # noqa: E402
from praval.storage import FileSystemProvider  # noqa: E402


def register_provider() -> None:
    """Register the deterministic adapter through the public provider registry."""
    registry = get_provider_registry()
    registry.register_provider(
        "certification-fake",
        CertificationProvider,
        default_model="certification-model",
        capabilities=CertificationProvider.capabilities,
    )
    registry.register_profile(
        ProviderProfile(
            provider="certification-fake",
            model="certification-model",
            default=True,
            capabilities=CertificationProvider.capabilities,
        )
    )


async def certify_agent_runtime() -> dict:
    """Exercise direct/app agents, tools, structured output and both async APIs."""
    register_provider()
    # A direct Agent is the primary public construction path.  Keep this
    # separate from the app-owned agent below so lifecycle ownership is tested
    # for both APIs against the exact installed wheel.
    direct = Agent(
        "certification-direct-agent",
        provider="certification-fake",
        model="certification-model",
    )
    direct_provider = direct.provider
    assert direct.name == "certification-direct-agent"
    assert direct.generate("certify direct").content == "Praval certification response"
    direct.close()
    assert direct_provider.closed is True

    lifecycle_provider = None
    with PravalApp() as app:
        agent = app.create_agent(
            "certification-agent",
            provider="certification-fake",
            model="certification-model",
            config={"temperature": 0, "max_output_tokens": 64},
        )
        lifecycle_provider = agent.provider
        assert agent.chat("certify chat") == "Praval certification response"
        structured = agent.generate(
            "certify structure",
            response_schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        )
        assert json.loads(structured.content)["summary"]
        async_response = await agent.agenerate("certify async")
        assert async_response.content == "Praval certification response"
        sync_events = list(agent.stream("certify sync stream"))
        async_events = [event async for event in agent.astream("certify async stream")]
        for events in (sync_events, async_events):
            assert any(event.type == "delta" for event in events)
            assert events[-1].type == "final"

        tool_spec = ToolSpec(
            name="double",
            description="Double an integer",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        )
        agent.add_tool_spec(tool_spec, lambda value: value * 2)
        tool_response = agent.generate("Use the double tool")
        assert tool_response.content == "tool-result:4"

        async_agent = app.create_agent(
            "async-tool-agent",
            provider="certification-fake",
            model="certification-model",
        )

        async def async_double(value: int) -> int:
            return value * 2

        async_agent.add_tool_spec(tool_spec, async_double, async_only=True)
        async_tool_response = await async_agent.agenerate("Use the async double tool")
        assert async_tool_response.content == "tool-result:4"
    assert lifecycle_provider is not None and lifecycle_provider.closed is True
    return {
        "direct_agent": True,
        "chat": True,
        "generate": True,
        "agenerate": True,
        "stream": True,
        "astream": True,
        "sync_tool": True,
        "async_tool": True,
        "lifecycle_cleanup": True,
    }


def certify_reef_and_spores() -> dict:
    """Exercise direct, broadcast, request/reply, async handlers and Spore V2."""
    reef = Reef()
    received = []

    async def async_handler(spore: Spore) -> None:
        await asyncio.sleep(0)
        received.append(spore)

    reef.subscribe("receiver", async_handler)
    direct_id = reef.send("sender", "receiver", {"kind": "direct"})
    broadcast_id = reef.broadcast("sender", {"kind": "broadcast"})
    request_id = reef.request("sender", "receiver", {"question": "ready"})
    reply_id = reef.reply("receiver", "sender", {"answer": "yes"}, request_id)
    assert reef.wait_for_completion(timeout=5)
    assert direct_id and broadcast_id and request_id and reply_id
    assert any(item.knowledge.get("kind") == "direct" for item in received)

    spore = Spore(
        id="certification-spore-v2",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="sender",
        to_agent="receiver",
        knowledge={"summary": "multimodal reference"},
        created_at=datetime.now(),
        schema_version="2.0",
        content_parts=[ContentPart.text_part("portable content")],
        data_references=["filesystem://file_system/certification.json"],
        correlation_id="certification-correlation",
    )
    restored = Spore.from_json(spore.to_json())
    assert restored.content_parts[0]["text"] == "portable content"
    assert restored.data_references == spore.data_references
    assert reef.shutdown(timeout=5)
    return {
        "direct": True,
        "broadcast": True,
        "request_reply": True,
        "async_handler": True,
        "spore_v2": True,
    }


async def certify_storage_memory_pdf_observability() -> dict:
    """Exercise memory paths, filesystem, fixture PDF extraction, and tracing."""
    output = report_dir()
    with tempfile.TemporaryDirectory(prefix="praval-certification-") as temporary:
        root = Path(temporary)
        filesystem = FileSystemProvider("certification-files", {"base_path": str(root)})
        stored = await filesystem.store("state/value.json", {"status": "ready"})
        restored = await filesystem.retrieve("state/value.json")
        assert stored.success and restored.success
        assert restored.data == {"status": "ready"}
        await filesystem.disconnect()

        embedding = EmbeddingRuntime(provider="local", dimensions=32).embed(
            ["coral agents", "reef coordination"]
        )
        assert len(embedding.embeddings) == 2
        assert embedding.dimensions and embedding.dimensions > 0
        assert all(
            len(vector) == embedding.dimensions for vector in embedding.embeddings
        )
        assert all(
            any(value != 0 for value in vector) for vector in embedding.embeddings
        )

        # Use the committed fixture rather than generating a PDF at runtime.
        # This keeps the release certificate tied to a reviewable, hashed input.
        pdf_fixture = Path(__file__).with_name("assets") / "knowledge_input.pdf.base64"
        pdf_bytes = base64.b64decode(pdf_fixture.read_text(encoding="ascii"))
        assert hashlib.sha256(pdf_bytes).hexdigest() == (
            "3cf3456c1f585f203aa2c853249a04fb1c431c57053eedf80f9a5fa23e831501"
        )
        pdf_path = root / "knowledge.pdf"
        pdf_path.write_bytes(pdf_bytes)
        vector_store = object.__new__(EmbeddedVectorStore)
        extracted = vector_store._extract_pdf_text(pdf_path)
        assert "Praval Reef" in extracted

        # Exercise the memory-only fallback, including episodic and semantic
        # paths.  This does not require Chroma/Qdrant and therefore remains a
        # deterministic offline certificate while still validating public
        # MemoryManager behavior.
        manager = MemoryManager(agent_id="memory-cert", backend="memory")
        conversation_id = manager.store_conversation_turn(
            "memory-cert", "How does Reef coordinate agents?", "Reef uses spores."
        )
        knowledge_id = manager.store_knowledge(
            "memory-cert", "reef", domain="reef", confidence=1.0
        )
        assert manager.retrieve_memory(conversation_id) is not None
        assert manager.retrieve_memory(knowledge_id) is not None
        context = manager.get_conversation_context("memory-cert", turns=2)
        assert any(item.memory_type is MemoryType.EPISODIC for item in context)
        domain_knowledge = manager.get_domain_knowledge("memory-cert", "reef")
        assert any(item.memory_type is MemoryType.SEMANTIC for item in domain_knowledge)
        search = manager.search_memories(
            MemoryQuery(
                query_text="reef",
                agent_id="memory-cert",
                memory_types=[MemoryType.SEMANTIC],
                similarity_threshold=0.0,
            )
        )
        assert search.total_found >= 1

        trace_path = output / "offline-traces.sqlite3"
        tracer = Tracer("certification")
        with tracer.start_as_current_span(
            "certification.offline", attributes={"mode": "offline"}
        ) as span:
            span.add_event("framework-certified")
            trace_id = span.trace_id
        store = SQLiteTraceStore(str(trace_path))
        spans = store.get_trace(trace_id)
        assert len(spans) == 1
        assert spans[0]["end_time"] is not None
        assert spans[0]["events"][0]["name"] == "framework-certified"

        # Console export is intentionally exercised through the public viewer
        # instead of asserting implementation details of the SQLite store.
        console = io.StringIO()
        with redirect_stdout(console):
            ConsoleViewer(use_colors=False).display_trace(trace_id, spans)
        assert "certification.offline" in console.getvalue()

    return {
        "filesystem": True,
        "local_embeddings": True,
        "real_pdf_extraction": True,
        "memory_manager": True,
        "sqlite_observability": True,
        "console_observability": True,
    }


async def main() -> None:
    """Run the complete offline certificate and write structured evidence."""
    evidence = {
        "agent_runtime": await certify_agent_runtime(),
        "reef_and_spores": certify_reef_and_spores(),
        "storage_memory_pdf_observability": (
            await certify_storage_memory_pdf_observability()
        ),
    }
    write_json_artifact("offline-framework.json", evidence)
    print("CERTIFIED: offline framework behavior")


if __name__ == "__main__":
    asyncio.run(main())
