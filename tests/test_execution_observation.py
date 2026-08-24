"""Contract tests for the provider-neutral execution observation spine."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from praval.models import (
    NOOP_OBSERVATION_RECORDER,
    ContentKind,
    ContentReference,
    ExecutionObservation,
    HITLDecisionObservation,
    NoOpObservationRecorder,
    ObservationFactStatus,
    ObservationKind,
    ObservationPrivacy,
    ObservationRecorder,
    ObservationStatus,
    PrivacyMode,
    ReefHandoffObservation,
    RetryObservation,
    TokenUsageObservation,
    ToolCallObservation,
)


def _observation(**overrides: object) -> ExecutionObservation:
    started_at = datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc)
    values: dict[str, object] = {
        "observation_id": "obs-01",
        "run_id": "run-01",
        "kind": ObservationKind.AGENT,
        "conversation_id": "conversation-01",
        "response_id": "response-01",
        "agent_id": "agent-01",
        "agent_name": "researcher",
        "workflow_id": "workflow-01",
        "workflow_name": "research-flow",
        "started_at": started_at,
        "ended_at": started_at + timedelta(milliseconds=125),
        "duration_ms": 125.0,
        "status": ObservationStatus.OK,
        "terminal_outcome": "answer_returned",
        "provider": "openai",
        "model": "gpt-test",
        "request_mode": "async",
        "usage": TokenUsageObservation(
            input_tokens=10,
            output_tokens=5,
            reasoning_tokens=2,
            total_tokens=15,
        ),
        "tool_calls": (
            ToolCallObservation(
                tool_call_id="call-01",
                name="search_docs",
                status=ObservationFactStatus.OK,
                duration_ms=12.5,
            ),
        ),
        "retries": (
            RetryObservation(
                attempt=2,
                operation="model.invoke",
                reason_type="RateLimitError",
                backoff_ms=100,
            ),
        ),
        "hitl_decisions": (
            HITLDecisionObservation(
                decision_id="decision-01",
                decision="approved",
                tool_name="search_docs",
                reviewer_type="human",
            ),
        ),
        "handoffs": (
            ReefHandoffObservation(
                handoff_id="handoff-01",
                source_agent_id="agent-01",
                target_agent_id="agent-02",
                spore_id="spore-01",
                channel="research",
                status=ObservationFactStatus.OK,
                duration_ms=3.5,
            ),
        ),
        "content_references": (
            ContentReference(
                kind=ContentKind.RESPONSE,
                sha256="a" * 64,
                size_bytes=42,
                reference="store://responses/response-01",
                media_type="text/plain",
            ),
        ),
        "trace_id": "1" * 32,
        "span_id": "2" * 16,
    }
    values.update(overrides)
    return ExecutionObservation.model_validate(values)


def test_complete_observation_round_trips_through_versioned_json() -> None:
    observation = _observation()

    serialized = observation.model_dump_json()
    restored = ExecutionObservation.model_validate_json(serialized)

    assert restored == observation
    assert restored.schema_version == 1
    assert restored.started_at.tzinfo == timezone.utc
    assert restored.tool_calls[0].name == "search_docs"
    assert restored.content_references[0].sha256 == "a" * 64


def test_schema_freezes_required_identity_timing_status_and_privacy_fields() -> None:
    schema = ExecutionObservation.model_json_schema()

    assert set(schema["required"]) == {
        "observation_id",
        "run_id",
        "kind",
        "started_at",
        "ended_at",
        "duration_ms",
        "status",
    }
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert "privacy" in schema["properties"]
    assert "content" not in schema["properties"]


def test_observation_is_immutable_and_rejects_unknown_or_future_fields() -> None:
    observation = _observation()

    with pytest.raises(ValidationError, match="frozen"):
        observation.status = ObservationStatus.ERROR
    with pytest.raises(ValidationError, match="Extra inputs"):
        _observation(raw_response="secret")
    with pytest.raises(ValidationError, match="Input should be 1"):
        _observation(schema_version=2)


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"started_at": datetime(2026, 8, 24)}, "timezone-aware"),
        (
            {
                "started_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
                "ended_at": datetime(2026, 8, 24, tzinfo=timezone.utc),
            },
            "ended_at cannot be earlier",
        ),
        ({"agent_id": None, "agent_name": None}, "agent_id or agent_name"),
        (
            {
                "kind": ObservationKind.WORKFLOW,
                "workflow_id": None,
                "workflow_name": None,
            },
            "workflow_id or workflow_name",
        ),
        ({"span_id": None}, "must be supplied together"),
        ({"status": ObservationStatus.ERROR}, "require error_type"),
        ({"error_type": "ValueError"}, "only valid for non-ok"),
    ],
)
def test_observation_cross_field_invariants(
    overrides: dict[str, object], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        _observation(**overrides)


def test_error_observation_keeps_only_structured_error_type() -> None:
    observation = _observation(
        status=ObservationStatus.ERROR,
        error_type="ProviderTimeoutError",
        terminal_outcome="provider_failed",
    )

    serialized = observation.model_dump(mode="json")

    assert serialized["error_type"] == "ProviderTimeoutError"
    assert "error_message" not in serialized
    assert "stacktrace" not in serialized


@pytest.mark.parametrize(
    "status,error_type",
    [
        (ObservationStatus.CANCELLED, "CancelledError"),
        (ObservationStatus.TIMEOUT, "ProviderTimeoutError"),
    ],
)
def test_non_ok_terminal_status_can_carry_structured_error_type(
    status: ObservationStatus, error_type: str
) -> None:
    observation = _observation(status=status, error_type=error_type)

    assert observation.error_type == error_type


def test_nested_facts_and_content_references_are_bounded() -> None:
    too_many_retries = tuple(
        RetryObservation(attempt=index + 1, operation="model.invoke")
        for index in range(33)
    )

    with pytest.raises(ValidationError, match="at most 32"):
        _observation(retries=too_many_retries)
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        ContentReference(kind=ContentKind.PROMPT, sha256="unsafe", size_bytes=1)


def test_privacy_defaults_to_metadata_only_and_rejects_implicit_capture() -> None:
    observation = _observation(content_references=())

    assert observation.privacy == ObservationPrivacy()
    assert observation.privacy.mode is PrivacyMode.METADATA_ONLY
    assert observation.privacy.content_captured is False
    with pytest.raises(ValidationError, match="metadata_only"):
        ObservationPrivacy(content_captured=True, byte_limit=100)
    with pytest.raises(ValidationError, match="positive byte_limit"):
        ObservationPrivacy(mode=PrivacyMode.FULL, content_captured=True)


def test_noop_recorder_implements_protocol_and_has_no_side_effects() -> None:
    observation = _observation()

    assert isinstance(NOOP_OBSERVATION_RECORDER, NoOpObservationRecorder)
    assert isinstance(NOOP_OBSERVATION_RECORDER, ObservationRecorder)
    assert NOOP_OBSERVATION_RECORDER.record(observation) is None
    assert observation == _observation()


def test_observation_contract_has_no_otel_sdk_or_eval_dependency() -> None:
    import praval.models.observation as observation_module

    source = Path(observation_module.__file__).read_text(encoding="utf-8")
    imported_modules = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(name.startswith("opentelemetry") for name in imported_modules)
    assert not any(name.startswith("praval.eval") for name in imported_modules)


def test_frozen_observation_manifest_matches_the_runtime_exactly() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads(
        (root / "docs" / "observation-contract.toml").read_text(encoding="utf-8")
    )

    assert manifest["schema_version"] == 1
    assert manifest["execution_observation_fields"] == list(
        ExecutionObservation.model_fields
    )
    assert set(manifest["required_fields"]) == set(
        ExecutionObservation.model_json_schema()["required"]
    )
    assert manifest["observation_kinds"] == [value.value for value in ObservationKind]
    assert manifest["observation_statuses"] == [
        value.value for value in ObservationStatus
    ]
    assert manifest["fact_statuses"] == [value.value for value in ObservationFactStatus]
    assert manifest["privacy_modes"] == [value.value for value in PrivacyMode]
    assert manifest["content_kinds"] == [value.value for value in ContentKind]
    for field, maximum in manifest["bounds"].items():
        metadata = ExecutionObservation.model_fields[field].metadata
        assert any(getattr(item, "max_length", None) == maximum for item in metadata)
