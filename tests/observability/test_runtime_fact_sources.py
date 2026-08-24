"""Observation facts produced by lower-level runtime boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from praval.core.exceptions import InterventionRequired
from praval.embeddings import EmbeddingRuntime
from praval.hitl.models import InterventionDecision, InterventionStatus
from praval.hitl.runtime import HITLRuntime
from praval.mcp.client import MCPClient, MCPServerConfig
from praval.memory.memory_manager import MemoryManager
from praval.memory.memory_types import MemoryQuery
from praval.model_runtime import (
    execute_legacy_tool_call,
    execute_legacy_tool_call_async,
)
from praval.models.observation import (
    ContentKind,
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
)
from praval.runtime_observation import ObservationScope, use_observation_recorder
from praval.storage.base_provider import StorageResult
from praval.storage.data_manager import DataManager


class MemoryRecorder:
    def __init__(self) -> None:
        self.observations: list[ExecutionObservation] = []

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


def test_sync_tool_success_and_returned_error_are_aggregated_without_payloads() -> None:
    def echo(value: str) -> str:
        return f"secret-result:{value}"

    def fail() -> None:
        raise RuntimeError("secret tool failure")

    tools = [{"function": echo}, {"function": fail}]
    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="tool-agent"):
            assert (
                execute_legacy_tool_call(
                    hitl_context=None,
                    tool_call_id="call-ok",
                    function_name="echo",
                    raw_args={"value": "secret-argument"},
                    available_tools=tools,
                )
                == "secret-result:secret-argument"
            )
            assert execute_legacy_tool_call(
                hitl_context=None,
                tool_call_id="call-error",
                function_name="fail",
                raw_args={},
                available_tools=tools,
            ).startswith("Error:")

    observation = recorder.observations[0]
    assert [fact.status for fact in observation.tool_calls] == [
        ObservationFactStatus.OK,
        ObservationFactStatus.ERROR,
    ]
    assert [fact.tool_call_id for fact in observation.tool_calls] == [
        "call-ok",
        "call-error",
    ]
    serialized = observation.model_dump_json()
    assert "secret-argument" not in serialized
    assert "secret-result" not in serialized
    assert "secret tool failure" not in serialized


@pytest.mark.asyncio
async def test_async_tool_cancellation_propagates_and_is_aggregated() -> None:
    async def cancel() -> None:
        raise asyncio.CancelledError()

    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="async-tool"):
            with pytest.raises(asyncio.CancelledError):
                await execute_legacy_tool_call_async(
                    hitl_context=None,
                    tool_call_id="call-cancelled",
                    function_name="cancel",
                    raw_args={},
                    available_tools=[{"function": cancel}],
                )

    fact = recorder.observations[0].tool_calls[0]
    assert fact.status is ObservationFactStatus.CANCELLED
    assert fact.error_type == "CancelledError"


def test_hitl_requested_and_approved_decisions_are_aggregated(tmp_path: Path) -> None:
    def publish(value: str) -> str:
        return value.upper()

    tool = {
        "function": publish,
        "requires_approval": True,
        "risk_level": "high",
        "approval_reason": "external side effect",
    }
    runtime = HITLRuntime(
        run_id="run-hitl",
        agent_name="hitl-agent",
        provider_name="provider",
        hitl_enabled=True,
        db_path=str(tmp_path / "hitl.sqlite3"),
    )
    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="hitl-agent"):
            with pytest.raises(InterventionRequired) as interrupted:
                runtime.execute_or_interrupt(
                    tool_call_id="call-hitl",
                    function_name="publish",
                    raw_args={"value": "draft"},
                    available_tools=[tool],
                    continuation_state={"step": 1},
                )
            intervention = runtime.store.get_intervention(
                interrupted.value.intervention_id
            )
            assert intervention is not None
            intervention.status = InterventionStatus.APPROVED
            intervention.decision = InterventionDecision.APPROVE
            intervention.reviewer = "reviewer@example.test"
            assert (
                runtime.execute_with_decision(
                    intervention=intervention,
                    available_tools=[tool],
                )
                == "DRAFT"
            )

    decisions = recorder.observations[0].hitl_decisions
    assert [decision.decision for decision in decisions] == [
        "requested",
        "approved",
    ]
    assert decisions[1].reviewer_type == "human"
    assert "reviewer@example.test" not in recorder.observations[0].model_dump_json()


def _mcp_client(*, timeout: float = 0.1) -> MCPClient:
    client = MCPClient(
        MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="test-command",
            tool_timeout=timeout,
        )
    )
    client._tool_names = {"test-server__echo": "echo"}
    return client


@pytest.mark.asyncio
async def test_direct_mcp_success_and_timeout_emit_one_fact_each() -> None:
    class Session:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            if arguments.get("timeout"):
                await asyncio.sleep(0.05)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="secret MCP result")],
                isError=False,
            )

    recorder = MemoryRecorder()
    client = _mcp_client(timeout=0.001)
    client._session = Session()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="mcp-agent"):
            success = await client.call_tool("test-server__echo", {"value": "secret"})
            timeout = await client.call_tool("test-server__echo", {"timeout": True})

    assert success.is_error is False
    assert timeout.is_error is True
    facts = recorder.observations[0].tool_calls
    assert [fact.status for fact in facts] == [
        ObservationFactStatus.OK,
        ObservationFactStatus.ERROR,
    ]
    assert len(facts) == 2
    assert "secret MCP result" not in recorder.observations[0].model_dump_json()


def test_embedding_facts_join_agent_observation_but_standalone_does_not_emit() -> None:
    runtime = EmbeddingRuntime(provider="local", dimensions=8)
    runtime._sentence_model_loaded = True
    runtime._sentence_model = None
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        standalone = runtime.embed("standalone private input")
        assert recorder.observations == []
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="embedding-agent"):
            response = runtime.embed(["first private input", "second private input"])

    assert standalone.dimensions == 8
    assert len(response.embeddings) == 2
    observation = recorder.observations[0]
    assert observation.provider == "local"
    assert observation.model == runtime.model
    assert [item.kind for item in observation.content_references] == [
        ContentKind.CONTEXT,
        ContentKind.CONTEXT,
    ]
    assert "private input" not in observation.model_dump_json()


def test_memory_operations_add_safe_input_and_retrieval_references() -> None:
    manager = MemoryManager(agent_id="memory-agent", backend="memory")
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="memory-agent"):
            memory_id = manager.store_memory(
                "memory-agent", "private remembered fact", store_long_term=False
            )
            assert manager.retrieve_memory(memory_id) is not None
            manager.search_memories(MemoryQuery(query_text="private search"))

    observation = recorder.observations[0]
    kinds = [reference.kind for reference in observation.content_references]
    assert ContentKind.CONTEXT in kinds
    assert ContentKind.RETRIEVED_DOCUMENT in kinds
    assert "private remembered fact" not in observation.model_dump_json()
    assert "private search" not in observation.model_dump_json()


@pytest.mark.asyncio
async def test_storage_operations_add_safe_input_and_retrieval_references() -> None:
    class Provider:
        async def store(self, resource: str, data: Any, **kwargs: Any) -> StorageResult:
            return StorageResult(success=True, data={"stored": resource})

        async def retrieve(self, resource: str, **kwargs: Any) -> StorageResult:
            return StorageResult(success=True, data={"private": "stored value"})

        async def query(
            self, resource: str, query: Any, **kwargs: Any
        ) -> StorageResult:
            return StorageResult(success=True, data=[{"private": "query value"}])

        async def delete(self, resource: str, **kwargs: Any) -> StorageResult:
            return StorageResult(success=True)

    registry = Mock()
    registry.get_provider.return_value = Provider()
    manager = DataManager(registry=registry)
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="storage-agent"):
            await manager.store("fake", "private-resource", {"private": "input"})
            await manager.get("fake", "private-resource")
            await manager.query("fake", "private-resource", {"private": "query"})
            await manager.delete("fake", "private-resource")

    observation = recorder.observations[0]
    kinds = [reference.kind for reference in observation.content_references]
    assert kinds.count(ContentKind.RETRIEVED_DOCUMENT) == 2
    assert "private-resource" not in observation.model_dump_json()
    assert "stored value" not in observation.model_dump_json()
    assert "query value" not in observation.model_dump_json()
