"""Persistent JSONL adapter for one pinned comparison framework."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

Runner = Callable[
    [Mapping[str, Any], str, str, str],
    Tuple[Mapping[str, Any], List[Mapping[str, Any]]],
]


def _call_proxy(
    *,
    proxy_url: str,
    token: str,
    item: Mapping[str, Any],
    stage: str,
    request_id: str,
    prior: Optional[Mapping[str, Any]] = None,
) -> Tuple[Mapping[str, Any], Mapping[str, Any]]:
    body = {
        "request_id": request_id,
        "question_id": item["id"],
        "question": item["question"],
        "context": item["context"],
        "stage": stage,
        "prior": prior,
    }
    request = urllib.request.Request(
        proxy_url.rstrip("/") + "/invoke",
        data=json.dumps(body, sort_keys=True).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value.get("output"), dict):
        raise RuntimeError("measurement proxy returned no structured output")
    if not isinstance(value.get("measurement"), dict):
        raise RuntimeError("measurement proxy returned no timing metadata")
    return value["output"], value["measurement"]


def _load_praval() -> Runner:
    from praval.core.reef import Reef

    reef = Reef(default_max_workers=2)
    done = threading.Event()
    active: Dict[str, Any] = {}

    def extract(spore: Any) -> None:
        del spore
        try:
            output, measurement = _call_proxy(
                proxy_url=active["proxy_url"],
                token=active["token"],
                item=active["item"],
                stage="extract",
                request_id=f"{active['request_id']}:extract",
            )
            active["measurements"].append(measurement)
            reef.send(
                "extractor",
                "answerer",
                {"stage": "answer", "extracted": dict(output)},
            )
        except BaseException as exc:
            active["failures"].append(exc)
            done.set()

    def answer(spore: Any) -> None:
        try:
            output, measurement = _call_proxy(
                proxy_url=active["proxy_url"],
                token=active["token"],
                item=active["item"],
                stage="answer",
                request_id=f"{active['request_id']}:answer",
                prior=spore.knowledge["extracted"],
            )
            active["measurements"].append(measurement)
            active["result"].update(output)
        except BaseException as exc:
            active["failures"].append(exc)
        finally:
            done.set()

    reef.subscribe("extractor", extract)
    reef.subscribe("answerer", answer)

    def run(
        item: Mapping[str, Any],
        proxy_url: str,
        token: str,
        request_id: str,
    ) -> Tuple[Mapping[str, Any], List[Mapping[str, Any]]]:
        done.clear()
        active.clear()
        active.update(
            {
                "item": item,
                "proxy_url": proxy_url,
                "token": token,
                "request_id": request_id,
                "measurements": [],
                "result": {},
                "failures": [],
            }
        )
        reef.send("controller", "extractor", {"stage": "extract"})
        if not done.wait(timeout=300):
            raise TimeoutError("Praval two-stage workflow did not finish")
        if active["failures"]:
            failure = active["failures"][0]
            raise RuntimeError(str(failure)) from failure
        if not reef.wait_for_completion(timeout=30):
            raise TimeoutError("Praval Reef did not reach completion")
        return active["result"], active["measurements"]

    setattr(run, "close", lambda: reef.shutdown(timeout=30))
    return run


def _load_langgraph() -> Runner:
    from langgraph.graph import END, START, StateGraph
    from typing_extensions import TypedDict

    class State(TypedDict, total=False):
        item: Mapping[str, Any]
        proxy_url: str
        token: str
        request_id: str
        extracted: Mapping[str, Any]
        final: Mapping[str, Any]
        measurements: List[Mapping[str, Any]]

    def extract(state: State) -> State:
        output, measurement = _call_proxy(
            proxy_url=state["proxy_url"],
            token=state["token"],
            item=state["item"],
            stage="extract",
            request_id=f"{state['request_id']}:extract",
        )
        return {
            "extracted": output,
            "measurements": [measurement],
        }

    def answer(state: State) -> State:
        output, measurement = _call_proxy(
            proxy_url=state["proxy_url"],
            token=state["token"],
            item=state["item"],
            stage="answer",
            request_id=f"{state['request_id']}:answer",
            prior=state["extracted"],
        )
        return {
            "final": output,
            "measurements": [*state["measurements"], measurement],
        }

    builder = StateGraph(State)
    builder.add_node("extract", extract)
    builder.add_node("answer", answer)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "answer")
    builder.add_edge("answer", END)
    graph = builder.compile()

    def run(
        item: Mapping[str, Any],
        proxy_url: str,
        token: str,
        request_id: str,
    ) -> Tuple[Mapping[str, Any], List[Mapping[str, Any]]]:
        final = graph.invoke(
            {
                "item": item,
                "proxy_url": proxy_url,
                "token": token,
                "request_id": request_id,
                "measurements": [],
            }
        )
        return final["final"], final["measurements"]

    return run


def _load_crewai() -> Runner:
    from crewai.flow.flow import Flow, listen, start

    active: Dict[str, Any] = {}

    class ComparisonFlow(Flow[dict]):
        @start()
        def extract(self) -> Mapping[str, Any]:
            output, measurement = _call_proxy(
                proxy_url=active["proxy_url"],
                token=active["token"],
                item=active["item"],
                stage="extract",
                request_id=f"{active['request_id']}:extract",
            )
            active["measurements"].append(measurement)
            return output

        @listen(extract)
        def answer(self, extracted: Mapping[str, Any]) -> Mapping[str, Any]:
            output, measurement = _call_proxy(
                proxy_url=active["proxy_url"],
                token=active["token"],
                item=active["item"],
                stage="answer",
                request_id=f"{active['request_id']}:answer",
                prior=extracted,
            )
            active["measurements"].append(measurement)
            return output

    def run(
        item: Mapping[str, Any],
        proxy_url: str,
        token: str,
        request_id: str,
    ) -> Tuple[Mapping[str, Any], List[Mapping[str, Any]]]:
        active.clear()
        active.update(
            {
                "item": item,
                "proxy_url": proxy_url,
                "token": token,
                "request_id": request_id,
                "measurements": [],
            }
        )
        flow = ComparisonFlow(
            suppress_flow_events=True,
            tracing=False,
        )
        final = flow.kickoff()
        if not isinstance(final, dict):
            raise RuntimeError("CrewAI flow returned no structured final output")
        return final, active["measurements"]

    return run


def _load_runner(framework: str) -> Runner:
    return {
        "praval": _load_praval,
        "langgraph": _load_langgraph,
        "crewai": _load_crewai,
    }[framework]()


def _usage_totals(measurements: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for measurement in measurements:
        usage = measurement.get("usage", {})
        if not isinstance(usage, dict):
            continue
        for key in totals:
            value = usage.get(key, 0)
            if isinstance(value, int):
                totals[key] += value
    return totals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--framework", choices=("praval", "langgraph", "crewai"), required=True
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    proxy_url = os.environ.get("PRAVAL_COMPARISON_PROXY_URL", "")
    token = os.environ.get("PRAVAL_COMPARISON_PROXY_TOKEN", "")
    if not proxy_url or not token:
        raise RuntimeError("comparison proxy URL and token are required")
    setup_started = time.perf_counter_ns()
    runner = _load_runner(args.framework)
    setup_seconds = (time.perf_counter_ns() - setup_started) / 1_000_000_000
    version = importlib.metadata.version(args.framework)
    print(
        json.dumps(
            {
                "event": "ready",
                "framework": args.framework,
                "version": version,
                "setup_seconds": setup_seconds,
                "python": sys.version.split()[0],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            message = json.loads(line)
            if message.get("action") == "shutdown":
                break
            request_id = str(message["request_id"])
            started = time.perf_counter_ns()
            try:
                output, measurements = runner(
                    message["item"], proxy_url, token, request_id
                )
                elapsed_seconds = (time.perf_counter_ns() - started) / 1_000_000_000
                response = {
                    "event": "result",
                    "status": "passed",
                    "request_id": request_id,
                    "framework": args.framework,
                    "elapsed_seconds": elapsed_seconds,
                    "model_seconds": sum(
                        float(value.get("model_seconds", 0.0)) for value in measurements
                    ),
                    "service_seconds": sum(
                        float(value.get("service_seconds", 0.0))
                        for value in measurements
                    ),
                    "model_calls": len(measurements),
                    "returned_models": [
                        value.get("returned_model") for value in measurements
                    ],
                    "usage": _usage_totals(measurements),
                    "output": output,
                }
            except Exception as exc:
                response = {
                    "event": "result",
                    "status": "failed",
                    "request_id": request_id,
                    "framework": args.framework,
                    "elapsed_seconds": (time.perf_counter_ns() - started)
                    / 1_000_000_000,
                    "failure": f"{type(exc).__name__}: {exc}",
                }
            print(json.dumps(response, sort_keys=True), flush=True)
    finally:
        close = getattr(runner, "close", None)
        if callable(close):
            close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
