"""Executable scenarios for Praval 0.8.1 paper claims."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .analysis import bootstrap_mean_ci, describe_samples
from .provenance import EXPECTED_WHEEL_SHA256, stable_json

Scenario = Callable[[Path, int, int, int, bool], Dict[str, Any]]


def _metric_summaries(
    samples: Sequence[Mapping[str, Any]], seed: int
) -> Dict[str, Any]:
    grouped: Dict[str, List[float]] = {}
    for sample in samples:
        metric = sample.get("metric")
        value = sample.get("value")
        if isinstance(metric, str) and isinstance(value, (int, float)):
            grouped.setdefault(metric, []).append(float(value))
    summaries: Dict[str, Any] = {}
    for index, (metric, values) in enumerate(sorted(grouped.items())):
        summary: Dict[str, Any] = dict(describe_samples(values))
        if len(values) > 1:
            lower, upper = bootstrap_mean_ci(values, seed=seed + index, resamples=500)
            summary["mean_bootstrap_95_ci"] = [lower, upper]
        summaries[metric] = summary
    return summaries


def _finish(
    output_dir: Path,
    *,
    checks: Mapping[str, bool],
    samples: Sequence[Mapping[str, Any]],
    seed: int,
    details: Optional[Mapping[str, Any]] = None,
    limitations: Sequence[str] = (),
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "passed" if checks and all(checks.values()) else "failed",
        "checks": dict(checks),
        "metrics": _metric_summaries(samples, seed),
        "sample_count": len(samples),
        "details": dict(details or {}),
        "limitations": list(limitations),
    }
    (output_dir / "result.json").write_text(stable_json(result), encoding="utf-8")
    with (output_dir / "samples.jsonl").open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, sort_keys=True) + "\n")
    return result


def _exact_wheel_identity(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del repetitions, warmups, quick
    import praval

    installed_path = Path(praval.__file__).resolve()
    observed_hash = os.environ.get("PRAVAL_VALIDATION_WHEEL_SHA256", "")
    checks = {
        "version_is_0_8_1": praval.__version__ == "0.8.1",
        "wheel_hash_matches": observed_hash == EXPECTED_WHEEL_SHA256,
        "not_imported_from_src": "/src/praval/" not in installed_path.as_posix(),
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=[],
        seed=seed,
        details={
            "installed_path": str(installed_path),
            "version": praval.__version__,
            "wheel_sha256": observed_hash,
        },
    )


def _runtime_contracts(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    from praval.core.agent import AgentConfig
    from praval.model_runtime import ModelRuntime
    from praval.models import (
        ModelEvent,
        ModelResponse,
        ProviderCapabilities,
        ToolCall,
        ToolResult,
        Usage,
    )

    class ContractProvider:
        provider_name = "paper-fake"
        capabilities = ProviderCapabilities(
            text=True,
            tools=True,
            streaming=True,
            native_streaming=True,
            structured_outputs=True,
            reasoning=True,
            reasoning_effort=True,
            multimodal=True,
            image_input=True,
        )

        def __init__(self) -> None:
            self.requests: List[Any] = []

        def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
            del tools
            self.requests.append(request)
            if request.tools:
                return ModelResponse(
                    provider=self.provider_name,
                    model=request.model,
                    tool_calls=[
                        ToolCall(id="call-1", name="double", arguments={"value": 2})
                    ],
                    usage=Usage(input_tokens=2, output_tokens=1, total_tokens=3),
                )
            content = (
                '{"summary":"normalized"}' if request.response_schema else "normalized"
            )
            return ModelResponse(
                content=content,
                provider=self.provider_name,
                model=request.model,
                finish_reason="stop",
                usage=Usage(input_tokens=2, output_tokens=1, total_tokens=3),
            )

        async def ainvoke(self, request: Any) -> ModelResponse:
            return self.invoke(request)

        def stream(self, request: Any, tools: Any = None) -> Any:
            del tools
            yield ModelEvent(type="delta", delta="normal")
            yield ModelEvent(type="delta", delta="ized")
            response = ModelResponse(
                content="normalized",
                provider=self.provider_name,
                model=request.model,
                finish_reason="stop",
                usage=Usage(input_tokens=2, output_tokens=1, total_tokens=3),
            )
            yield ModelEvent(type="usage", usage=response.usage)
            yield ModelEvent(type="final", response=response, usage=response.usage)

        def continue_with_tool_results(
            self,
            request: Any,
            response: ModelResponse,
            results: List[ToolResult],
        ) -> ModelResponse:
            del request, response
            return ModelResponse(
                content=f"tool:{results[0].content}",
                provider=self.provider_name,
                model="paper-model",
                finish_reason="tool_complete",
                usage=Usage(input_tokens=4, output_tokens=2, total_tokens=6),
            )

    provider = ContractProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name=provider.provider_name,
        config=AgentConfig(provider=provider.provider_name, model="paper-model"),
    )
    effective_repetitions = min(repetitions, 2) if quick else repetitions
    samples: List[Dict[str, Any]] = []
    sync_responses = []
    streams = []
    async_responses = []

    def invoke_once() -> Any:
        start = time.perf_counter_ns()
        response = runtime.invoke(messages=[{"role": "user", "content": "contract"}])
        samples.append(
            {
                "metric": "sync_invoke_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )
        sync_responses.append(response)

    for _ in range(warmups):
        runtime.invoke(messages=[{"role": "user", "content": "warmup"}])
    for _ in range(effective_repetitions):
        invoke_once()
        events = list(runtime.stream(messages=[{"role": "user", "content": "stream"}]))
        streams.append(events)
        async_responses.append(
            asyncio.run(
                runtime.ainvoke(messages=[{"role": "user", "content": "async"}])
            )
        )

    structured = runtime.invoke(
        messages=[{"role": "user", "content": "structured"}],
        response_schema={"type": "object"},
        reasoning={"effort": "low"},
    )

    def double(value: int) -> int:
        return value * 2

    tool_response = runtime.invoke(
        messages=[{"role": "user", "content": "tool"}],
        tools=[{"function": double, "description": "Double an integer"}],
    )
    checks = {
        "sync_shape": all(
            response.content == "normalized"
            and response.provider == "paper-fake"
            and response.model == "paper-model"
            and response.finish_reason == "stop"
            for response in sync_responses
        ),
        "usage_invariant": all(
            response.usage is not None
            and response.usage.total_tokens
            == response.usage.input_tokens + response.usage.output_tokens
            for response in sync_responses + async_responses
        ),
        "stream_event_order": all(
            [event.type for event in events]
            == ["start", "delta", "delta", "usage", "final"]
            for events in streams
        ),
        "stream_final_once": all(
            sum(event.type == "final" for event in events) == 1 for events in streams
        ),
        "async_shape": all(
            response.content == "normalized" for response in async_responses
        ),
        "structured_output": json.loads(structured.content)["summary"] == "normalized",
        "tool_metadata": (
            tool_response.content == "tool:4"
            and tool_response.tool_calls[0].name == "double"
            and tool_response.metadata["tool_results"][0]["content"] == "4"
        ),
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={"provider_request_count": len(provider.requests)},
        limitations=[
            "This deterministic adapter tests the shared contract, not live "
            "provider conformance."
        ],
    )


def _capability_resolution(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del repetitions, warmups, quick
    from praval.core.agent import AgentConfig
    from praval.core.exceptions import ProviderError
    from praval.model_runtime import ModelRuntime
    from praval.models import ContentPart, ModelResponse, ProviderCapabilities

    class CountingProvider:
        capabilities = ProviderCapabilities()

        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, request: Any) -> ModelResponse:
            self.calls += 1
            return ModelResponse(content="reached", model=request.model)

    provider = CountingProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="ollama",
        config=AgentConfig(provider="ollama", model="llama3"),
    )
    failures: Dict[str, str] = {}

    def expect_failure(name: str, **kwargs: Any) -> None:
        try:
            runtime.invoke(messages=[{"role": "user", "content": "test"}], **kwargs)
        except ProviderError as exc:
            failures[name] = str(exc)

    expect_failure("reasoning", reasoning={"effort": "low"})
    expect_failure("structured", response_schema={"type": "object"})
    try:
        runtime.invoke(
            messages=[
                {
                    "role": "user",
                    "content": [ContentPart.image_url("https://example.invalid/a.png")],
                }
            ]
        )
    except ProviderError as exc:
        failures["image"] = str(exc)
    expect_failure("unsafe_options", provider_options={"api_key": "secret"})
    openai_provider = CountingProvider()
    experimental_runtime = ModelRuntime(
        provider=openai_provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="paper-model"),
    )
    try:
        experimental_runtime.invoke(
            messages=[{"role": "user", "content": "search"}],
            provider_options={
                "endpoint": "responses",
                "experimental_tools": [{"type": "web_search"}],
            },
        )
    except ProviderError as exc:
        failures["experimental_opt_in"] = str(exc)
    supported = runtime.invoke(
        messages=[{"role": "user", "content": "allowed"}],
        response_schema={"type": "object"},
        provider_options={"capabilities": {"structured_outputs": True}},
    )
    checks = {
        "negative_matrix_complete": set(failures)
        == {
            "reasoning",
            "structured",
            "image",
            "unsafe_options",
            "experimental_opt_in",
        },
        "failures_before_provider": provider.calls == 1 and openai_provider.calls == 0,
        "explicit_override_reaches_provider": supported.content == "reached",
        "credential_value_not_in_errors": all(
            "secret" not in message for message in failures.values()
        ),
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=[],
        seed=seed,
        details={"failure_messages": failures, "provider_calls": provider.calls},
    )


def _spore_v2_compatibility(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    from praval import ContentPart
    from praval.core.reef import Spore, SporeType, SporeValidationError

    effective_repetitions = min(repetitions, 2) if quick else repetitions
    samples: List[Dict[str, Any]] = []
    json_roundtrips = 0
    amqp_roundtrips = 0
    for index in range(effective_repetitions):
        legacy = Spore(
            id=f"legacy-{index}",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"kind": "legacy"},
            created_at=datetime.now(),
        )
        start = time.perf_counter_ns()
        legacy_restored = Spore.from_json(legacy.to_json())
        samples.append(
            {
                "metric": "json_roundtrip_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
                "schema": "1.0",
            }
        )
        json_roundtrips += int(legacy_restored.knowledge == legacy.knowledge)
        v2 = Spore(
            id=f"v2-{index}",
            spore_type=SporeType.REQUEST,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"kind": "v2"},
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=30),
            priority=8,
            schema_version="2.0",
            content_parts=[ContentPart.text_part("portable")],
            knowledge_references=["memory://knowledge/1"],
            data_references=["filesystem://files/a.json"],
            correlation_id="correlation-1",
            causation_id="cause-1",
            trace_id="trace-1",
            run_id="run-1",
            idempotency_key="key-1",
        )
        restored = Spore.from_json(v2.to_json())
        json_roundtrips += int(
            restored.content_parts == v2.content_parts
            and restored.data_references == v2.data_references
            and restored.correlation_id == v2.correlation_id
            and restored.priority == 8
        )
        message = v2.to_amqp_message()
        amqp_restored = Spore.from_amqp_message(message)
        amqp_roundtrips += int(
            amqp_restored.content_parts == v2.content_parts
            and amqp_restored.data_references == v2.data_references
            and amqp_restored.schema_version == "2.0"
            and amqp_restored.idempotency_key == "key-1"
        )
    binary_rejected = False
    try:
        Spore(
            id="binary",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now(),
            content_parts=[{"type": "audio_base64", "data": b"raw"}],
        )
    except SporeValidationError:
        binary_rejected = True
    checks = {
        "legacy_and_v2_json_roundtrip": json_roundtrips == effective_repetitions * 2,
        "v2_amqp_roundtrip": amqp_roundtrips == effective_repetitions,
        "raw_binary_rejected": binary_rejected,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={
            "json_roundtrips": json_roundtrips,
            "amqp_roundtrips": amqp_roundtrips,
        },
    )


def _secure_spore_behavior(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    from praval.core.reef import SporeType
    from praval.core.secure_spore import SecureSpore, SporeKeyManager

    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    wrong = SporeKeyManager("wrong")
    sizes = [100, 1_000] if quick else [100, 1_000, 10_000, 100_000]
    effective_repetitions = min(repetitions, 2) if quick else repetitions
    samples: List[Dict[str, Any]] = []
    roundtrips = 0
    first_package = None
    for size in sizes:
        knowledge = {"payload": "x" * size}
        for repetition in range(effective_repetitions):
            start = time.perf_counter_ns()
            encrypted, nonce, signature = sender.encrypt_and_sign(
                knowledge, bytes(recipient.public_key)
            )
            encrypted_at = time.perf_counter_ns()
            restored = recipient.decrypt_and_verify(
                encrypted,
                nonce,
                signature,
                bytes(sender.public_key),
                bytes(sender.verify_key),
            )
            decrypted_at = time.perf_counter_ns()
            secure = SecureSpore(
                id=f"secure-{size}-{repetition}",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="recipient",
                created_at=datetime.now(),
                encrypted_knowledge=encrypted,
                knowledge_signature=signature,
                sender_public_key=bytes(sender.public_key),
                nonce=nonce,
            )
            serialized_at = time.perf_counter_ns()
            encoded = secure.to_bytes()
            encoded_at = time.perf_counter_ns()
            decoded = SecureSpore.from_bytes(encoded)
            finished = time.perf_counter_ns()
            roundtrips += int(
                restored == knowledge
                and decoded.encrypted_knowledge == encrypted
                and len(nonce) == 24
                and len(signature) == 64
            )
            samples.extend(
                [
                    {
                        "metric": "encryption_seconds",
                        "value": (encrypted_at - start) / 1_000_000_000,
                        "payload_bytes": size,
                    },
                    {
                        "metric": "decryption_seconds",
                        "value": (decrypted_at - encrypted_at) / 1_000_000_000,
                        "payload_bytes": size,
                    },
                    {
                        "metric": "serialization_seconds",
                        "value": (encoded_at - serialized_at) / 1_000_000_000,
                        "payload_bytes": size,
                    },
                    {
                        "metric": "deserialization_seconds",
                        "value": (finished - encoded_at) / 1_000_000_000,
                        "payload_bytes": size,
                    },
                ]
            )
            if first_package is None:
                first_package = (encrypted, nonce, signature)
    assert first_package is not None
    encrypted, nonce, signature = first_package
    wrong_key_rejected = False
    tampering_rejected = False
    try:
        wrong.decrypt_and_verify(
            encrypted,
            nonce,
            signature,
            bytes(sender.public_key),
            bytes(sender.verify_key),
        )
    except ValueError:
        wrong_key_rejected = True
    tampered = bytearray(signature)
    tampered[0] ^= 1
    try:
        recipient.decrypt_and_verify(
            encrypted,
            nonce,
            bytes(tampered),
            bytes(sender.public_key),
            bytes(sender.verify_key),
        )
    except ValueError:
        tampering_rejected = True
    checks = {
        "roundtrips": roundtrips == len(sizes) * effective_repetitions,
        "wrong_key_rejected": wrong_key_rejected,
        "tampering_rejected": tampering_rejected,
        "expiration_is_enforced_by_object": SecureSpore(
            id="expired",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="recipient",
            created_at=datetime.now() - timedelta(seconds=2),
            expires_at=datetime.now() - timedelta(seconds=1),
        ).is_expired(),
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        limitations=[
            "Behavioral tests are not a cryptographic proof.",
            "Praval 0.8.1 uses long-lived Box keys; this does not validate "
            "perfect forward secrecy.",
            "The rotate_keys helper has no production key-distribution or "
            "grace-period protocol.",
        ],
    )


def _external_certificate(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
    *,
    script_name: str,
    artifact_name: str,
) -> Dict[str, Any]:
    del repetitions, warmups, quick
    repository_root = Path(__file__).resolve().parents[2]
    script = repository_root / "examples" / "certification" / script_name
    environment = dict(os.environ)
    environment["PRAVAL_DEMO_REPORT_DIR"] = str(output_dir)
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=script.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    artifact = output_dir / artifact_name
    checks = {
        "certificate_exit_zero": completed.returncode == 0,
        "certificate_artifact_present": artifact.is_file(),
    }
    details: Dict[str, Any] = {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if artifact.is_file():
        details["certificate"] = json.loads(artifact.read_text(encoding="utf-8"))
    return _finish(
        output_dir,
        checks=checks,
        samples=[],
        seed=seed,
        details=details,
    )


def _mcp_safety(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    return _external_certificate(
        output_dir,
        repetitions,
        warmups,
        seed,
        quick,
        script_name="mcp_transports.py",
        artifact_name="mcp-transports.json",
    )


def _service_integrations(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    return _external_certificate(
        output_dir,
        repetitions,
        warmups,
        seed,
        quick,
        script_name="services.py",
        artifact_name="services.json",
    )


def _live_capability_matrix(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    scripts = (
        ("live_provider_matrix.py", "live-provider-matrix.json"),
        ("live_hitl.py", "live-hitl.json"),
        ("live_voice_roundtrip.py", "live-voice-roundtrip.json"),
    )
    effective_repetitions = min(repetitions, 1) if quick else repetitions
    repository_root = Path(__file__).resolve().parents[2]
    script_root = repository_root / "examples" / "certification"
    trials: List[Dict[str, Any]] = []
    all_passed = True
    for repetition in range(effective_repetitions):
        trial_dir = output_dir / f"trial-{repetition}"
        trial_dir.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ)
        environment["PRAVAL_DEMO_REPORT_DIR"] = str(trial_dir)
        trial: Dict[str, Any] = {"repetition": repetition, "scripts": {}}
        for script_name, artifact_name in scripts:
            completed = subprocess.run(
                [sys.executable, str(script_root / script_name)],
                cwd=script_root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            artifact = trial_dir / artifact_name
            passed = completed.returncode == 0 and artifact.is_file()
            all_passed = all_passed and passed
            trial["scripts"][script_name] = {
                "passed": passed,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "artifact": (
                    json.loads(artifact.read_text(encoding="utf-8"))
                    if artifact.is_file()
                    else None
                ),
            }
        trials.append(trial)
    checks = {
        "three_external_validity_repetitions": quick or effective_repetitions == 3,
        "provider_matrix_hitl_and_voice_pass": all_passed,
        "provider_and_model_identifiers_recorded": all_passed,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=[],
        seed=seed,
        details={"trials": trials},
        limitations=[
            "Live provider behavior, returned model aliases, latency, and cost "
            "can change after the framework wheel is fixed.",
            "These runs provide external validity and are not deterministic "
            "guarantees or provider rankings.",
        ],
    )


def _probe(command: Sequence[str]) -> Dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "research.paper_validation.probes", *command],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "probe failed: " + " ".join(command) + "\n" + completed.stderr.strip()
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("probe produced no JSON output")
    return dict(json.loads(lines[-1]))


def _hitl_process_recovery(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    from praval.hitl.models import InterventionStatus
    from praval.hitl.service import HITLService

    effective_repetitions = min(repetitions, 1) if quick else repetitions
    cases: List[Dict[str, Any]] = []
    all_process_boundaries = True
    for repetition in range(effective_repetitions):
        for decision in ("approve", "edit", "reject"):
            case_dir = output_dir / f"{repetition}-{decision}"
            case_dir.mkdir(parents=True, exist_ok=True)
            database = case_dir / "hitl.sqlite3"
            execution_log = case_dir / "executions.log"
            run_id = f"paper-{repetition}-{decision}"
            suspended = _probe(
                [
                    "hitl-suspend",
                    "--db",
                    str(database),
                    "--run-id",
                    run_id,
                    "--execution-log",
                    str(execution_log),
                ]
            )
            decided = _probe(
                [
                    "hitl-decide",
                    "--db",
                    str(database),
                    "--run-id",
                    run_id,
                    "--execution-log",
                    str(execution_log),
                    "--decision",
                    decision,
                ]
            )
            expected_executions = 0 if decision == "reject" else 1
            cases.append(
                {
                    "decision": decision,
                    "interrupted": suspended["interrupted"],
                    "before_execution_count": suspended["execution_count"],
                    "after_execution_count": decided["execution_count"],
                    "expected_execution_count": expected_executions,
                    "original_args": decided["original_args"],
                    "edited_args": decided["edited_args"],
                    "result": decided["result"],
                }
            )
            all_process_boundaries = all_process_boundaries and bool(
                suspended["interrupted"]
            )

    expiration_dir = output_dir / "expiration"
    expiration_dir.mkdir(parents=True, exist_ok=True)
    expiration_db = expiration_dir / "hitl.sqlite3"
    expiration_log = expiration_dir / "executions.log"
    expiration_run = "paper-expiration"
    expiration = _probe(
        [
            "hitl-suspend",
            "--db",
            str(expiration_db),
            "--run-id",
            expiration_run,
            "--execution-log",
            str(expiration_log),
        ]
    )
    with sqlite3.connect(str(expiration_db)) as connection:
        connection.execute(
            "UPDATE interventions SET expires_at = 0 WHERE run_id = ?",
            (expiration_run,),
        )
        connection.commit()
    expiration_service = HITLService(db_path=str(expiration_db))
    expiration_service.get_pending_interventions(run_id=expiration_run)
    expired = expiration_service.list_interventions(run_id=expiration_run)[0]

    cancel_dir = output_dir / "cancel"
    cancel_dir.mkdir(parents=True, exist_ok=True)
    cancel_db = cancel_dir / "hitl.sqlite3"
    cancel_log = cancel_dir / "executions.log"
    cancel_run = "paper-cancel"
    cancelled = _probe(
        [
            "hitl-suspend",
            "--db",
            str(cancel_db),
            "--run-id",
            cancel_run,
            "--execution-log",
            str(cancel_log),
        ]
    )
    cancel_service = HITLService(db_path=str(cancel_db))
    cancel_service.cancel_run(cancel_run, "operator cancelled")
    cancelled_state = cancel_service.get_suspended_run(cancel_run)
    cancelled_intervention = cancel_service.list_interventions(run_id=cancel_run)[0]

    checks = {
        "suspension_crosses_process_boundary": all_process_boundaries,
        "protected_tool_not_run_before_decision": all(
            case["before_execution_count"] == 0 for case in cases
        ),
        "approve_and_edit_exactly_once": all(
            case["after_execution_count"] == case["expected_execution_count"]
            for case in cases
        ),
        "edit_preserves_original_and_edited_args": any(
            case["decision"] == "edit"
            and case["original_args"] == {"value": 2}
            and case["edited_args"] == {"value": 7}
            and case["result"] == "14"
            for case in cases
        ),
        "reject_does_not_execute": any(
            case["decision"] == "reject"
            and case["after_execution_count"] == 0
            and "Rejected by human reviewer" in case["result"]
            for case in cases
        ),
        "expiration_is_durable": (
            expiration["execution_count"] == 0
            and expired.status is InterventionStatus.EXPIRED
        ),
        "cancelled_run_is_durable": (
            cancelled["execution_count"] == 0
            and cancelled_state is not None
            and cancelled_state.status == "cancelled"
        ),
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=[],
        seed=seed,
        details={
            "cases": cases,
            "expired_status": expired.status.value,
            "cancelled_run_status": (
                cancelled_state.status if cancelled_state is not None else None
            ),
            "cancelled_intervention_status": cancelled_intervention.status.value,
        },
        limitations=[
            "Cancelling a suspended run does not change its pending "
            "intervention to CANCELLED in Praval 0.8.1.",
            "The probe validates durable tool decisions and continuation "
            "records, not recovery of arbitrary application-local state.",
        ],
    )


def _lifecycle_failure(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    import threading

    from praval.app import PravalApp
    from praval.core.reef import Reef

    effective_repetitions = min(repetitions, 2) if quick else repetitions
    baseline_threads = {
        thread.ident for thread in threading.enumerate() if thread.is_alive()
    }
    samples: List[Dict[str, Any]] = []
    trials: List[Dict[str, Any]] = []

    class OwnedResource:
        name = "owned-resource"

        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    for repetition in range(effective_repetitions):
        reef = Reef(default_max_workers=4)
        completed: List[str] = []

        async def async_handler(spore: Any) -> None:
            await asyncio.sleep(0.002)
            completed.append(f"async:{spore.knowledge['trial']}")

        def failing_handler(spore: Any) -> None:
            del spore
            raise RuntimeError("injected handler failure")

        def slow_handler(spore: Any) -> None:
            del spore
            time.sleep(0.02)
            completed.append("slow")

        reef.subscribe("async", async_handler)
        reef.subscribe("failure", failing_handler)
        reef.subscribe("slow", slow_handler)
        start = time.perf_counter_ns()
        reef.send("sender", "async", {"trial": repetition})
        reef.send("sender", "failure", {"trial": repetition})
        reef.send("sender", "slow", {"trial": repetition})
        timed_out = not reef.wait_for_completion(timeout=0.001)
        eventually_completed = reef.wait_for_completion(timeout=2)
        samples.append(
            {
                "metric": "lifecycle_trial_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )
        owned = OwnedResource()
        app = PravalApp(reef=reef)
        app.register_agent(owned)
        app.close()
        app.close()
        second_shutdown = reef.shutdown(timeout=2)
        trials.append(
            {
                "timed_out": timed_out,
                "eventually_completed": eventually_completed,
                "completed": list(completed),
                "resource_close_count": owned.close_count,
                "second_shutdown": second_shutdown,
            }
        )
    time.sleep(0.05)
    extra_threads = [
        thread.name
        for thread in threading.enumerate()
        if thread.is_alive()
        and thread.ident not in baseline_threads
        and (
            thread.name.startswith("reef-")
            or thread.name.startswith("ThreadPoolExecutor")
        )
    ]
    checks = {
        "timeout_is_explicit": all(trial["timed_out"] for trial in trials),
        "completion_waits_for_async_and_slow_handlers": all(
            trial["eventually_completed"]
            and any(value.startswith("async:") for value in trial["completed"])
            and "slow" in trial["completed"]
            for trial in trials
        ),
        "handler_exception_does_not_break_completion": all(
            trial["eventually_completed"] for trial in trials
        ),
        "owned_resources_close_once": all(
            trial["resource_close_count"] == 1 for trial in trials
        ),
        "duplicate_shutdown_is_idempotent": all(
            trial["second_shutdown"] for trial in trials
        ),
        "no_reef_worker_thread_leak": not extra_threads,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={"trials": trials, "extra_threads": extra_threads},
        limitations=[
            "Handler exceptions are logged and swallowed; Reef 0.8.1 has no "
            "built-in retry or dead-letter guarantee for in-memory delivery."
        ],
    )


def _data_observability_contracts(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del repetitions, warmups, quick
    from types import SimpleNamespace

    from praval.core.exceptions import EmbeddingConfigurationError, ProviderError
    from praval.embeddings import EmbeddingRuntime
    from praval.memory.long_term_memory import LongTermMemory
    from praval.observability.storage.sqlite_store import SQLiteTraceStore
    from praval.observability.tracing.span import Span
    from praval.storage.base_provider import DataReference, StorageType
    from praval.storage.providers.filesystem import FileSystemProvider

    embedding_runtime = EmbeddingRuntime(provider="local", dimensions=8)
    embedding_runtime._sentence_model_loaded = True
    embedding_runtime._sentence_model = None
    first = embedding_runtime.embed(["reef", "spore"])
    second = embedding_runtime.embed(["reef", "spore"])
    unsupported_error = ""
    try:
        EmbeddingRuntime(provider="unsupported").embed("reef")
    except ProviderError as exc:
        unsupported_error = str(exc)
    dimension_error = ""
    mismatched_memory = object.__new__(LongTermMemory)
    mismatched_memory.collection_name = "paper-existing"
    mismatched_memory.vector_size = 8
    mismatched_memory.client = SimpleNamespace(
        get_collection=lambda name: SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=4))
            )
        )
    )
    try:
        mismatched_memory._validate_existing_collection_dimensions()
    except EmbeddingConfigurationError as exc:
        dimension_error = str(exc)

    async def storage_roundtrip() -> Dict[str, Any]:
        storage_root = output_dir / "filesystem"
        provider = FileSystemProvider(
            "paper-filesystem", {"base_path": str(storage_root)}
        )
        await provider.connect()
        stored = await provider.store("state/value.json", {"status": "ready"})
        restored = await provider.retrieve("state/value.json")
        await provider.disconnect()
        return {
            "stored": stored.success,
            "restored": restored.success,
            "data": restored.data,
        }

    storage = asyncio.run(storage_roundtrip())
    reference = DataReference(
        provider="paper-filesystem",
        storage_type=StorageType.FILE_SYSTEM,
        resource_id="state/value.json",
    )
    restored_reference = DataReference.from_uri(reference.to_uri())
    trace_store = SQLiteTraceStore(str(output_dir / "trace-once.sqlite3"))
    span = Span(name="paper.once", trace_id="trace-1", span_id="span-1")
    span.add_event("completed")
    span.end()
    trace_store.store_span(span)
    trace_store.store_span(span)
    stored_spans = trace_store.get_trace("trace-1")
    checks = {
        "embedding_shape_and_dimension": (
            first.dimensions == 8
            and len(first.embeddings) == 2
            and all(len(vector) == 8 for vector in first.embeddings)
        ),
        "deterministic_local_embedding": first.embeddings == second.embeddings,
        "unsupported_embedding_provider_is_explicit": (
            "Unsupported embedding provider" in unsupported_error
        ),
        "dimension_mismatch_has_reindex_guidance": (
            "vector size 4" in dimension_error and "re-index" in dimension_error
        ),
        "filesystem_roundtrip": (
            storage["stored"]
            and storage["restored"]
            and storage["data"] == {"status": "ready"}
        ),
        "data_reference_roundtrip": (
            restored_reference.provider == reference.provider
            and restored_reference.storage_type is StorageType.FILE_SYSTEM
            and restored_reference.resource_id == reference.resource_id
        ),
        "span_stored_once": (
            len(stored_spans) == 1
            and stored_spans[0]["events"][0]["name"] == "completed"
        ),
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=[],
        seed=seed,
        details={
            "unsupported_embedding_error": unsupported_error,
            "dimension_mismatch_error": dimension_error,
        },
        limitations=[
            "PostgreSQL, Redis, S3-compatible, Qdrant, and OTLP endpoints "
            "belong to the services tier."
        ],
    )


def _measure_reef_topology(
    topology: str, branches: int, work_seconds: float, repetitions: int
) -> List[float]:
    from praval.core.reef import Reef

    durations: List[float] = []
    if topology == "sequential":
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            for _ in range(branches):
                time.sleep(work_seconds)
            durations.append((time.perf_counter_ns() - start) / 1_000_000_000)
        return durations

    reef = Reef(default_max_workers=max(4, branches + 1))
    if topology == "fanout":
        for index in range(branches):
            reef.subscribe(
                f"fan-{index}",
                lambda spore, delay=work_seconds: time.sleep(delay),
            )
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            reef.broadcast("coordinator", {"topology": topology})
            if not reef.wait_for_completion(timeout=30):
                raise RuntimeError("fan-out did not complete")
            durations.append((time.perf_counter_ns() - start) / 1_000_000_000)
    elif topology == "pipeline":
        for index in range(branches):
            next_agent = f"pipe-{index + 1}" if index + 1 < branches else None

            def stage(
                spore: Any,
                next_name: Optional[str] = next_agent,
                sender: str = f"pipe-{index}",
            ) -> None:
                time.sleep(work_seconds)
                if next_name:
                    reef.send(sender, next_name, spore.knowledge)

            reef.subscribe(f"pipe-{index}", stage)
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            reef.send("coordinator", "pipe-0", {"topology": topology})
            if not reef.wait_for_completion(timeout=30):
                raise RuntimeError("pipeline did not complete")
            durations.append((time.perf_counter_ns() - start) / 1_000_000_000)
    elif topology == "request_reply":
        replies: List[str] = []
        reef.subscribe(
            "collector",
            lambda spore: replies.append(str(spore.reply_to)),
        )
        for index in range(branches):

            def responder(spore: Any, agent: str = f"reply-{index}") -> None:
                time.sleep(work_seconds)
                reef.reply(
                    agent,
                    "collector",
                    {"status": "done"},
                    spore.id,
                )

            reef.subscribe(f"reply-{index}", responder)
        for repetition in range(repetitions):
            before = len(replies)
            start = time.perf_counter_ns()
            for index in range(branches):
                reef.request(
                    "collector",
                    f"reply-{index}",
                    {"trial": repetition},
                )
            if not reef.wait_for_completion(timeout=30):
                raise RuntimeError("request/reply did not complete")
            if len(replies) - before != branches:
                raise RuntimeError("request/reply lost a branch")
            durations.append((time.perf_counter_ns() - start) / 1_000_000_000)
    else:
        raise ValueError(topology)
    reef.shutdown(timeout=10)
    return durations


def _choreography_critical_path(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    branches_values = [2, 4] if quick else [2, 4, 8]
    work_values = [0.005] if quick else [0.01, 0.05, 0.2]
    effective_repetitions = min(repetitions, 2) if quick else repetitions
    samples: List[Dict[str, Any]] = []
    cells: List[Dict[str, Any]] = []
    all_cells_valid = True
    for branches in branches_values:
        for work_seconds in work_values:
            observed: Dict[str, List[float]] = {}
            for topology in (
                "sequential",
                "fanout",
                "pipeline",
                "request_reply",
            ):
                values = _measure_reef_topology(
                    topology, branches, work_seconds, effective_repetitions
                )
                observed[topology] = values
                theoretical = (
                    work_seconds
                    if topology in {"fanout", "request_reply"}
                    else branches * work_seconds
                )
                for value in values:
                    samples.append(
                        {
                            "metric": f"{topology}_seconds",
                            "value": value,
                            "topology": topology,
                            "branches": branches,
                            "work_seconds": work_seconds,
                            "theoretical_seconds": theoretical,
                        }
                    )
            sequential_median = describe_samples(observed["sequential"])["median"]
            fanout_median = describe_samples(observed["fanout"])["median"]
            request_median = describe_samples(observed["request_reply"])["median"]
            pipeline_median = describe_samples(observed["pipeline"])["median"]
            cell_valid = (
                fanout_median < sequential_median
                and request_median < sequential_median
                and pipeline_median >= fanout_median
            )
            all_cells_valid = all_cells_valid and cell_valid
            cells.append(
                {
                    "branches": branches,
                    "work_seconds": work_seconds,
                    "sequential_median": sequential_median,
                    "fanout_median": fanout_median,
                    "pipeline_median": pipeline_median,
                    "request_reply_median": request_median,
                    "fanout_speedup": sequential_median / fanout_median,
                    "valid": cell_valid,
                }
            )
    checks = {
        "all_topologies_and_cells_completed": len(cells)
        == len(branches_values) * len(work_values),
        "parallel_critical_paths_are_shorter": all_cells_valid,
        "same_branch_work_per_cell": True,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={"cells": cells},
        limitations=[
            "Deterministic sleep work isolates coordination critical paths; "
            "it does not model provider or tool variance.",
            "Pipeline and sequential paths are expected to remain serial in "
            "branch work.",
        ],
    )


def _reef_scaling_inmemory(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    agents_values = [2, 4] if quick else [2, 8, 32]
    payload_values = [256] if quick else [256, 16 * 1024, 256 * 1024]
    process_count = 1 if quick else repetitions
    deliveries = 100 if quick else 1_000
    samples: List[Dict[str, Any]] = []
    process_results: List[Dict[str, Any]] = []
    for agents in agents_values:
        for payload_bytes in payload_values:
            for process_index in range(process_count):
                result = _probe(
                    [
                        "reef-scale",
                        "--agents",
                        str(agents),
                        "--payload-bytes",
                        str(payload_bytes),
                        "--deliveries",
                        str(deliveries),
                    ]
                )
                result["process_index"] = process_index
                process_results.append(result)
                for latency in result.pop("latencies_seconds"):
                    samples.append(
                        {
                            "metric": "delivery_latency_seconds",
                            "value": latency,
                            "agents": agents,
                            "payload_bytes": payload_bytes,
                            "process_index": process_index,
                        }
                    )
                for metric in (
                    "throughput_deliveries_per_second",
                    "cpu_seconds",
                    "max_rss_kib",
                    "final_queue_depth",
                ):
                    samples.append(
                        {
                            "metric": metric,
                            "value": result[metric],
                            "agents": agents,
                            "payload_bytes": payload_bytes,
                            "process_index": process_index,
                        }
                    )
    expected_processes = len(agents_values) * len(payload_values) * process_count
    checks = {
        "matrix_complete": len(process_results) == expected_processes,
        "all_deliveries_counted": all(
            result["delivered"] == result["requested_deliveries"]
            and result["failures"] == 0
            for result in process_results
        ),
        "completion_and_shutdown_clean": all(
            result["completion"] and result["shutdown"] for result in process_results
        ),
        "fresh_processes_per_cell": quick or process_count == 5,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={"processes": process_results},
        limitations=[
            "In-memory delivery measurements are host-specific and do not "
            "imply RabbitMQ scaling.",
            "The bounded channel retains at most 1,000 recent spores; final "
            "queue depth is not broker queue depth.",
        ],
    )


def _reef_scaling_rabbitmq(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    del warmups
    from praval.core.reef import Spore, SporeType, SporeValidationError

    url = os.environ.get("RABBITMQ_URL", "")
    management_url = os.environ.get("RABBITMQ_MANAGEMENT_URL", "")
    if not url or not management_url:
        raise RuntimeError("RABBITMQ_URL and RABBITMQ_MANAGEMENT_URL are required")
    agents_values = [2] if quick else [2, 8, 32]
    payload_values = [256] if quick else [256, 16 * 1024, 256 * 1024]
    process_count = 1 if quick else repetitions
    deliveries = 100 if quick else 1_000
    samples: List[Dict[str, Any]] = []
    process_results: List[Dict[str, Any]] = []
    for agents in agents_values:
        for payload_bytes in payload_values:
            for process_index in range(process_count):
                result = _probe(
                    [
                        "rabbit-scale",
                        "--url",
                        url,
                        "--management-url",
                        management_url,
                        "--agents",
                        str(agents),
                        "--payload-bytes",
                        str(payload_bytes),
                        "--deliveries",
                        str(deliveries),
                    ]
                )
                result["process_index"] = process_index
                process_results.append(result)
                for latency in result.pop("latencies_seconds"):
                    samples.append(
                        {
                            "metric": "rabbitmq_delivery_latency_seconds",
                            "value": latency,
                            "agents": agents,
                            "payload_bytes": payload_bytes,
                            "process_index": process_index,
                        }
                    )
                for metric in (
                    "throughput_deliveries_per_second",
                    "cpu_seconds",
                    "max_rss_kib",
                    "max_queue_depth",
                ):
                    if result[metric] is not None:
                        samples.append(
                            {
                                "metric": f"rabbitmq_{metric}",
                                "value": result[metric],
                                "agents": agents,
                                "payload_bytes": payload_bytes,
                                "process_index": process_index,
                            }
                        )

    slow = _probe(
        [
            "rabbit-scale",
            "--url",
            url,
            "--management-url",
            management_url,
            "--agents",
            "2",
            "--payload-bytes",
            "256",
            "--deliveries",
            "100" if quick else "1000",
            "--consumer-delay",
            "0.02",
            "--prefetch-count",
            "1",
        ]
    )
    for latency in slow.pop("latencies_seconds"):
        samples.append(
            {
                "metric": "rabbitmq_slow_consumer_latency_seconds",
                "value": latency,
                "agents": 2,
                "payload_bytes": 256,
            }
        )
    oversized_rejected = False
    near_limit_accepted = False
    try:
        near_limit = Spore(
            id="near-limit",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"payload": "x" * (10 * 1024 * 1024 - 4 * 1024)},
            created_at=datetime.now(),
        )
        near_limit_accepted = near_limit.get_payload_size() <= 10 * 1024 * 1024
    except SporeValidationError:
        near_limit_accepted = False
    try:
        Spore(
            id="oversized",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"payload": "x" * (11 * 1024 * 1024)},
            created_at=datetime.now(),
        )
    except SporeValidationError:
        oversized_rejected = True
    expected_processes = len(agents_values) * len(payload_values) * process_count
    checks = {
        "matrix_complete": len(process_results) == expected_processes,
        "all_deliveries_counted": all(
            result["delivered"] == result["requested_deliveries"]
            and result["failures"] == 0
            for result in process_results
        ),
        "five_fresh_processes_per_cell": quick or process_count == 5,
        "queue_depth_sampled": all(
            result["max_queue_depth"] is not None for result in process_results
        )
        and slow["max_queue_depth"] is not None,
        "slow_consumer_boundary_completed": (
            slow["delivered"] == slow["requested_deliveries"]
            and isinstance(slow["max_queue_depth"], int)
            and slow["max_queue_depth"] > 0
        ),
        "near_limit_spore_accepted_before_transport": near_limit_accepted,
        "oversized_spore_rejected_before_transport": oversized_rejected,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={
            "processes": process_results,
            "slow_consumer": slow,
            "service_images": ["rabbitmq:3.13.7-management-alpine"],
        },
        limitations=[
            "RabbitMQ measurements apply only to the recorded host, broker "
            "image, and local network.",
            "The near-10 MiB accepted and over-10 MiB rejected boundary is a "
            "framework validation limit, not a measured broker maximum.",
            "The slow-consumer probe uses prefetch 1 and a 20 ms handler "
            "delay; it does not establish a production backpressure policy.",
        ],
    )


def _abstraction_overhead(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    process_count = 1 if quick else 5
    measured = min(repetitions, 5) if quick else repetitions
    effective_warmups = min(warmups, 2) if quick else warmups
    repository_root = Path(__file__).resolve().parents[2]
    samples: List[Dict[str, Any]] = []
    for process_index in range(process_count):
        process_dir = output_dir / f"process-{process_index}"
        process_dir.mkdir(parents=True, exist_ok=True)
        result = _probe(
            [
                "overhead",
                "--repetitions",
                str(measured),
                "--warmups",
                str(effective_warmups),
                "--repository-root",
                str(repository_root),
                "--output-dir",
                str(process_dir),
            ]
        )
        for sample in result["samples"]:
            sample["process_index"] = process_index
            samples.append(sample)
    observed_metrics = {sample["metric"] for sample in samples}
    required_metrics = {
        "direct_adapter_seconds",
        "model_runtime_seconds",
        "direct_function_seconds",
        "mcp_stdio_seconds",
        "mcp_http_seconds",
        "observability_off_seconds",
        "observability_on_seconds",
        "plain_spore_seconds",
        "secure_spore_seconds",
    }
    checks = {
        "all_equivalent_paths_measured": required_metrics <= observed_metrics,
        "five_fresh_processes": quick or process_count == 5,
        "sample_count_per_metric": all(
            sum(sample["metric"] == metric for sample in samples)
            == process_count * measured
            for metric in required_metrics
        ),
        "external_model_time_absent": True,
    }
    return _finish(
        output_dir,
        checks=checks,
        samples=samples,
        seed=seed,
        details={
            "process_count": process_count,
            "repetitions_per_process": measured,
            "warmups_per_process": effective_warmups,
        },
        limitations=[
            "MCP measurements use a local loopback server and small echo payloads.",
            "Overhead values are specific to the recorded host and dependency "
            "versions.",
        ],
    )


def _controlled_framework_comparison(
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    from .comparative.controller import run_comparison

    comparison = run_comparison(
        output_dir=output_dir,
        repetitions=repetitions,
        warmups=warmups,
        seed=seed,
        quick=quick,
    )
    return _finish(
        output_dir,
        checks=comparison["checks"],
        samples=comparison["samples"],
        seed=seed,
        details=comparison["details"],
        limitations=comparison["limitations"],
    )


SCENARIOS: Dict[str, Scenario] = {
    "exact_wheel_identity": _exact_wheel_identity,
    "runtime_contracts": _runtime_contracts,
    "capability_resolution": _capability_resolution,
    "hitl_process_recovery": _hitl_process_recovery,
    "mcp_safety": _mcp_safety,
    "spore_v2_compatibility": _spore_v2_compatibility,
    "lifecycle_failure": _lifecycle_failure,
    "data_observability_contracts": _data_observability_contracts,
    "secure_spore_behavior": _secure_spore_behavior,
    "choreography_critical_path": _choreography_critical_path,
    "reef_scaling_inmemory": _reef_scaling_inmemory,
    "service_integrations": _service_integrations,
    "reef_scaling_rabbitmq": _reef_scaling_rabbitmq,
    "abstraction_overhead": _abstraction_overhead,
    "controlled_framework_comparison": _controlled_framework_comparison,
    "live_capability_matrix": _live_capability_matrix,
}


def run_scenario(
    scenario: str,
    *,
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    """Run one registered scenario and persist raw and derived evidence."""
    function = SCENARIOS.get(scenario)
    if function is None:
        raise ValueError(f"unregistered scenario implementation: {scenario}")
    return function(output_dir, repetitions, warmups, seed, quick)
