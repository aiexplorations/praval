"""Fresh-process probes used by paper-validation scenarios."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import resource
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _max_rss_kib(
    raw_value: Optional[float] = None, platform_name: Optional[str] = None
) -> float:
    """Normalize ``ru_maxrss`` to KiB on Linux and macOS."""
    observed = (
        float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if raw_value is None
        else float(raw_value)
    )
    current_platform = platform_name or sys.platform
    return observed / 1024.0 if current_platform == "darwin" else observed


def _hitl_suspend(args: argparse.Namespace) -> Dict[str, Any]:
    from praval.core.exceptions import InterventionRequired
    from praval.hitl.runtime import HITLRuntime

    def double(value: int) -> int:
        with args.execution_log.open("a", encoding="utf-8") as handle:
            handle.write(f"{value}\n")
        return value * 2

    runtime = HITLRuntime(
        run_id=args.run_id,
        agent_name="paper-agent",
        provider_name="paper-provider",
        hitl_enabled=True,
        db_path=str(args.db),
    )
    interrupted = False
    intervention_id = ""
    try:
        runtime.execute_or_interrupt(
            tool_call_id=f"call-{args.run_id}",
            function_name="double",
            raw_args={"value": 2},
            available_tools=[
                {
                    "function": double,
                    "requires_approval": True,
                    "risk_level": "high",
                    "approval_reason": "Paper validation",
                }
            ],
            continuation_state={"step": "tool", "run_id": args.run_id},
        )
    except InterventionRequired as exc:
        interrupted = True
        intervention_id = exc.intervention_id
    return {
        "interrupted": interrupted,
        "intervention_id": intervention_id,
        "execution_count": (
            len(args.execution_log.read_text(encoding="utf-8").splitlines())
            if args.execution_log.is_file()
            else 0
        ),
    }


def _hitl_decide(args: argparse.Namespace) -> Dict[str, Any]:
    from praval.hitl.runtime import HITLRuntime
    from praval.hitl.service import HITLService

    service = HITLService(db_path=str(args.db))
    pending = service.get_pending_interventions(run_id=args.run_id)
    if len(pending) != 1:
        raise RuntimeError(f"expected one pending intervention, found {len(pending)}")
    intervention = pending[0]
    if args.decision == "approve":
        decided = service.approve_intervention(
            intervention.id, reviewer="paper-validator"
        )
    elif args.decision == "edit":
        decided = service.approve_intervention(
            intervention.id,
            reviewer="paper-validator",
            edited_args={"value": 7},
        )
    else:
        decided = service.reject_intervention(
            intervention.id,
            reviewer="paper-validator",
            reason="negative control",
        )

    def double(value: int) -> int:
        with args.execution_log.open("a", encoding="utf-8") as handle:
            handle.write(f"{value}\n")
        return value * 2

    runtime = HITLRuntime(
        run_id=args.run_id,
        agent_name="paper-agent",
        provider_name="paper-provider",
        hitl_enabled=True,
        db_path=str(args.db),
    )
    result = runtime.execute_with_decision(
        intervention=decided,
        available_tools=[{"function": double, "requires_approval": True}],
    )
    return {
        "decision": decided.decision.value if decided.decision else None,
        "original_args": decided.original_args,
        "edited_args": decided.edited_args,
        "result": result,
        "execution_count": (
            len(args.execution_log.read_text(encoding="utf-8").splitlines())
            if args.execution_log.is_file()
            else 0
        ),
    }


def _reef_scale(args: argparse.Namespace) -> Dict[str, Any]:
    from praval.core.reef import Reef

    reef = Reef(default_max_workers=max(4, args.agents))
    latencies: List[float] = []
    failures = 0

    def receive(spore: Any) -> None:
        sent_ns = int(spore.knowledge["sent_ns"])
        latencies.append((time.perf_counter_ns() - sent_ns) / 1_000_000_000)

    for index in range(args.agents):
        reef.subscribe(f"agent-{index}", receive)
    padding = "x" * max(1, args.payload_bytes - 100)
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    for index in range(args.deliveries):
        try:
            reef.send(
                "sender",
                f"agent-{index % args.agents}",
                {"sent_ns": time.perf_counter_ns(), "padding": padding},
            )
        except Exception:
            failures += 1
    completed = reef.wait_for_completion(timeout=120)
    cpu_seconds = (time.process_time_ns() - start_cpu) / 1_000_000_000
    wall_seconds = (time.perf_counter_ns() - start_wall) / 1_000_000_000
    channel = reef.get_channel("main")
    queue_depth = len(channel.spores) if channel is not None else -1
    delivered = len(latencies)
    shutdown = reef.shutdown(timeout=10)
    return {
        "agents": args.agents,
        "payload_bytes": args.payload_bytes,
        "requested_deliveries": args.deliveries,
        "delivered": delivered,
        "failures": failures,
        "completion": completed,
        "shutdown": shutdown,
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "throughput_deliveries_per_second": (
            delivered / wall_seconds if wall_seconds else 0.0
        ),
        "latencies_seconds": latencies,
        "final_queue_depth": queue_depth,
        "max_rss_kib": _max_rss_kib(),
    }


async def _rabbit_scale_async(args: argparse.Namespace) -> Dict[str, Any]:
    from praval.core.reef import Spore, SporeType
    from praval.core.reef_backend import RabbitMQBackend

    backend = RabbitMQBackend()
    latencies: List[float] = []
    delivered = asyncio.Event()
    expected = args.deliveries
    queue_depths: List[int] = []
    sampling_done = asyncio.Event()

    async def receive(spore: Any) -> None:
        if args.consumer_delay > 0:
            await asyncio.sleep(args.consumer_delay)
        latencies.append(
            (time.perf_counter_ns() - int(spore.knowledge["sent_ns"])) / 1_000_000_000
        )
        if len(latencies) >= expected:
            delivered.set()

    def fetch_queue_depth() -> int:
        if not args.management_url:
            return 0
        request = urllib.request.Request(
            args.management_url.rstrip("/") + "/api/queues"
        )
        token = base64.b64encode(
            f"{args.management_user}:{args.management_password}".encode("utf-8")
        ).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(request, timeout=2) as response:
            queues = json.loads(response.read().decode("utf-8"))
        return sum(int(queue.get("messages", 0)) for queue in queues)

    async def sample_queue_depth() -> None:
        while not sampling_done.is_set():
            try:
                queue_depths.append(await asyncio.to_thread(fetch_queue_depth))
            except Exception:
                pass
            await asyncio.sleep(0.02)

    exchange = f"praval.paper.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    failures = 0
    try:
        await backend.initialize(
            {
                "url": args.url,
                "exchange_name": exchange,
                "prefetch_count": args.prefetch_count,
            }
        )
        for index in range(args.agents):
            await backend.subscribe(f"agent.agent-{index}", receive)
        await asyncio.sleep(0.2)
        sampler = asyncio.create_task(sample_queue_depth())
        padding = "x" * max(1, args.payload_bytes - 100)
        start_wall = time.perf_counter_ns()
        start_cpu = time.process_time_ns()
        for index in range(args.deliveries):
            spore = Spore(
                id=f"{os.getpid()}-{index}",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent=f"agent-{index % args.agents}",
                knowledge={
                    "sent_ns": time.perf_counter_ns(),
                    "padding": padding,
                },
                created_at=datetime.now(),
                schema_version="2.0",
            )
            try:
                await backend.send(spore, f"agent.agent-{index % args.agents}")
            except Exception:
                failures += 1
        await asyncio.wait_for(delivered.wait(), timeout=180)
        sampling_done.set()
        await sampler
        wall_seconds = (time.perf_counter_ns() - start_wall) / 1_000_000_000
        cpu_seconds = (time.process_time_ns() - start_cpu) / 1_000_000_000
    finally:
        await backend.shutdown()
    return {
        "agents": args.agents,
        "payload_bytes": args.payload_bytes,
        "requested_deliveries": args.deliveries,
        "delivered": len(latencies),
        "failures": failures,
        "completion": len(latencies) == args.deliveries,
        "shutdown": not backend.connected,
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "throughput_deliveries_per_second": (
            len(latencies) / wall_seconds if wall_seconds else 0.0
        ),
        "latencies_seconds": latencies,
        "max_queue_depth": max(queue_depths) if queue_depths else None,
        "max_rss_kib": _max_rss_kib(),
        "exchange": exchange,
    }


def _rabbit_scale(args: argparse.Namespace) -> Dict[str, Any]:
    return asyncio.run(_rabbit_scale_async(args))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError("MCP HTTP probe server did not start")


async def _mcp_samples(
    repository_root: Path, repetitions: int, warmups: int
) -> List[Dict[str, Any]]:
    from praval.mcp import MCPClient, MCPServerConfig

    server = repository_root / "examples" / "certification" / "mcp_server.py"
    samples: List[Dict[str, Any]] = []

    def direct(message: str) -> str:
        return f"echo:{message}"

    for _ in range(warmups):
        direct("paper")
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        direct("paper")
        samples.append(
            {
                "metric": "direct_function_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )

    stdio = MCPServerConfig(
        name="stdio-overhead",
        transport="stdio",
        command=sys.executable,
        args=[str(server)],
        require_approval=False,
    )
    async with MCPClient(stdio) as client:
        for _ in range(warmups):
            await client.call_tool("stdio-overhead__echo", {"message": "paper"})
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            await client.call_tool("stdio-overhead__echo", {"message": "paper"})
            samples.append(
                {
                    "metric": "mcp_stdio_seconds",
                    "value": (time.perf_counter_ns() - start) / 1_000_000_000,
                }
            )

    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, str(server), "http", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(port)
        http = MCPServerConfig(
            name="http-overhead",
            transport="streamable_http",
            url=f"http://127.0.0.1:{port}/mcp",
            require_approval=False,
        )
        async with MCPClient(http) as client:
            for _ in range(warmups):
                await client.call_tool("http-overhead__echo", {"message": "paper"})
            for _ in range(repetitions):
                start = time.perf_counter_ns()
                await client.call_tool("http-overhead__echo", {"message": "paper"})
                samples.append(
                    {
                        "metric": "mcp_http_seconds",
                        "value": (time.perf_counter_ns() - start) / 1_000_000_000,
                    }
                )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return samples


def _overhead(args: argparse.Namespace) -> Dict[str, Any]:
    from praval.core.agent import AgentConfig
    from praval.core.reef import Spore, SporeType
    from praval.core.secure_spore import SecureSpore, SporeKeyManager
    from praval.model_runtime import ModelRuntime
    from praval.models import ModelResponse, ProviderCapabilities
    from praval.observability.config import reset_config
    from praval.observability.storage.sqlite_store import reset_trace_store
    from praval.observability.tracing.tracer import Tracer

    class Provider:
        capabilities = ProviderCapabilities(text=True)

        def invoke(self, request: Any) -> ModelResponse:
            return ModelResponse(content=request.messages[0].content)

    provider = Provider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="paper-fake",
        config=AgentConfig(provider="paper-fake", model="paper-model"),
    )
    request = runtime._build_request(
        messages=[{"role": "user", "content": "paper"}],
        tools=None,
        hitl_context=None,
        response_schema=None,
        reasoning=None,
        provider_options=None,
        timeout=None,
        metadata=None,
        stream_options=None,
    )
    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    samples: List[Dict[str, Any]] = []
    for _ in range(args.warmups):
        provider.invoke(request)
        runtime.invoke(messages=[{"role": "user", "content": "paper"}])
    for index in range(args.repetitions):
        start = time.perf_counter_ns()
        provider.invoke(request)
        samples.append(
            {
                "metric": "direct_adapter_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )
        start = time.perf_counter_ns()
        runtime.invoke(messages=[{"role": "user", "content": "paper"}])
        samples.append(
            {
                "metric": "model_runtime_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )
        knowledge = {"index": index, "payload": "x" * 256}
        plain = Spore(
            id=f"plain-{index}",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="recipient",
            knowledge=knowledge,
            created_at=datetime.now(),
        )
        start = time.perf_counter_ns()
        plain.to_json()
        samples.append(
            {
                "metric": "plain_spore_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )
        start = time.perf_counter_ns()
        encrypted, nonce, signature = sender.encrypt_and_sign(
            knowledge, bytes(recipient.public_key)
        )
        secure = SecureSpore(
            id=f"secure-{index}",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="recipient",
            created_at=datetime.now(),
            encrypted_knowledge=encrypted,
            knowledge_signature=signature,
            sender_public_key=bytes(sender.public_key),
            nonce=nonce,
        )
        secure.to_bytes()
        samples.append(
            {
                "metric": "secure_spore_seconds",
                "value": (time.perf_counter_ns() - start) / 1_000_000_000,
            }
        )

    for mode in ("off", "on"):
        os.environ["PRAVAL_OBSERVABILITY"] = mode
        os.environ["PRAVAL_TRACES_PATH"] = str(
            args.output_dir / f"traces-{mode}.sqlite3"
        )
        reset_config()
        reset_trace_store()
        tracer = Tracer(f"overhead-{mode}")
        for _ in range(args.warmups):
            with tracer.start_as_current_span("paper.overhead"):
                pass
        for _ in range(args.repetitions):
            start = time.perf_counter_ns()
            with tracer.start_as_current_span("paper.overhead"):
                pass
            samples.append(
                {
                    "metric": f"observability_{mode}_seconds",
                    "value": (time.perf_counter_ns() - start) / 1_000_000_000,
                }
            )

    samples.extend(
        asyncio.run(_mcp_samples(args.repository_root, args.repetitions, args.warmups))
    )
    return {"samples": samples}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    suspend = subparsers.add_parser("hitl-suspend")
    suspend.add_argument("--db", type=Path, required=True)
    suspend.add_argument("--run-id", required=True)
    suspend.add_argument("--execution-log", type=Path, required=True)

    decide = subparsers.add_parser("hitl-decide")
    decide.add_argument("--db", type=Path, required=True)
    decide.add_argument("--run-id", required=True)
    decide.add_argument("--execution-log", type=Path, required=True)
    decide.add_argument(
        "--decision", choices=("approve", "edit", "reject"), required=True
    )

    reef = subparsers.add_parser("reef-scale")
    reef.add_argument("--agents", type=int, required=True)
    reef.add_argument("--payload-bytes", type=int, required=True)
    reef.add_argument("--deliveries", type=int, required=True)

    rabbit = subparsers.add_parser("rabbit-scale")
    rabbit.add_argument("--url", required=True)
    rabbit.add_argument("--agents", type=int, required=True)
    rabbit.add_argument("--payload-bytes", type=int, required=True)
    rabbit.add_argument("--deliveries", type=int, required=True)
    rabbit.add_argument("--consumer-delay", type=float, default=0.0)
    rabbit.add_argument("--prefetch-count", type=int, default=100)
    rabbit.add_argument("--management-url", default="")
    rabbit.add_argument("--management-user", default="guest")
    rabbit.add_argument("--management-password", default="guest")

    overhead = subparsers.add_parser("overhead")
    overhead.add_argument("--repetitions", type=int, required=True)
    overhead.add_argument("--warmups", type=int, required=True)
    overhead.add_argument("--repository-root", type=Path, required=True)
    overhead.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "hitl-suspend":
        result = _hitl_suspend(args)
    elif args.command == "hitl-decide":
        result = _hitl_decide(args)
    elif args.command == "reef-scale":
        result = _reef_scale(args)
    elif args.command == "rabbit-scale":
        result = _rabbit_scale(args)
    elif args.command == "overhead":
        result = _overhead(args)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
