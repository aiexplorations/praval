"""Shared deterministic/live model proxy for the framework comparison."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

FACT_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {"type": "string"}},
        "numbers": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["facts", "numbers"],
    "additionalProperties": False,
}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "numbers": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["answer", "facts", "numbers"],
    "additionalProperties": False,
}


def load_dataset(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load and validate the shared JSONL fixture."""
    items: Dict[str, Dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        item = json.loads(line)
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"dataset line {line_number} has no id")
        if item_id in items:
            raise ValueError(f"duplicate dataset id: {item_id}")
        if not all(key in item for key in ("question", "context", "expected")):
            raise ValueError(f"dataset item {item_id} is incomplete")
        items[item_id] = item
    if len(items) != 12:
        raise ValueError(
            f"comparison dataset must contain 12 items, found {len(items)}"
        )
    return items


def _extract_output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    fragments = []
    for output in response.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    fragments.append(text)
    if not fragments:
        raise RuntimeError("OpenAI response contained no output text")
    return "".join(fragments)


def _live_response(
    *,
    item: Mapping[str, Any],
    stage: str,
    prior: Optional[Mapping[str, Any]],
    api_key: str,
    model: str,
    base_url: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if stage == "extract":
        prompt = (
            "Extract only the facts and numbers needed to answer the question. "
            "Do not use outside knowledge.\n\nCONTEXT:\n"
            f"{item['context']}\n\nQUESTION:\n{item['question']}"
        )
        schema = FACT_SCHEMA
    else:
        prompt = (
            "Answer the question from the supplied context and extracted facts. "
            "Use the shortest exact answer that preserves units. Return the facts "
            "and numbers used.\n\nCONTEXT:\n"
            f"{item['context']}\n\nQUESTION:\n{item['question']}\n\n"
            f"EXTRACTED:\n{json.dumps(prior, sort_keys=True)}"
        )
        schema = ANSWER_SCHEMA
    request_body = {
        "model": model,
        "input": prompt,
        "temperature": 0,
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": f"comparison_{stage}",
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter_ns()
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        safe_message = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"OpenAI proxy request failed with HTTP {exc.code}: {safe_message}"
        ) from exc
    model_seconds = (time.perf_counter_ns() - started) / 1_000_000_000
    output = json.loads(_extract_output_text(body))
    return output, {
        "model_seconds": model_seconds,
        "returned_model": body.get("model"),
        "usage": body.get("usage") or {},
        "response_id": body.get("id"),
    }


class ComparisonServer(ThreadingHTTPServer):
    """HTTP server carrying immutable fixture and mutable measurement state."""

    def __init__(
        self,
        address: Tuple[str, int],
        *,
        dataset: Mapping[str, Mapping[str, Any]],
        events_path: Path,
        mode: str,
        delay_seconds: float,
        token: str,
        openai_api_key: str,
        openai_model: str,
        openai_base_url: str,
    ) -> None:
        super().__init__(address, ComparisonHandler)
        self.dataset = dataset
        self.events_path = events_path
        self.mode = mode
        self.delay_seconds = delay_seconds
        self.token = token
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        self.openai_base_url = openai_base_url
        self.event_lock = threading.Lock()
        self.sequence = 0

    def record(self, value: Mapping[str, Any]) -> int:
        with self.event_lock:
            self.sequence += 1
            event = {"sequence": self.sequence, **value}
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
            return self.sequence


class ComparisonHandler(BaseHTTPRequestHandler):
    """Serve exactly one versioned comparison call contract."""

    server: ComparisonServer

    def log_message(self, format: str, *args: Any) -> None:
        del format, args

    def _send(self, status: int, value: Mapping[str, Any]) -> None:
        body = json.dumps(value, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ready", "mode": self.server.mode})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/invoke":
            self._send(404, {"error": "not found"})
            return
        if self.headers.get("Authorization") != f"Bearer {self.server.token}":
            self._send(401, {"error": "unauthorized"})
            return
        started = time.perf_counter_ns()
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            question_id = payload["question_id"]
            stage = payload["stage"]
            request_id = payload["request_id"]
            if stage not in {"extract", "answer"}:
                raise ValueError("stage must be extract or answer")
            item = self.server.dataset[question_id]
            if payload.get("question") != item["question"]:
                raise ValueError("question differs from the registered fixture")
            if payload.get("context") != item["context"]:
                raise ValueError("context differs from the registered fixture")
            prior = payload.get("prior")
            if stage == "answer" and not isinstance(prior, dict):
                raise ValueError("answer stage requires extracted evidence")
            if self.server.mode == "delayed":
                time.sleep(self.server.delay_seconds)
                expected = item["expected"]
                output = (
                    {
                        "facts": expected["facts"],
                        "numbers": expected["numbers"],
                    }
                    if stage == "extract"
                    else expected
                )
                measurement = {
                    "model_seconds": self.server.delay_seconds,
                    "returned_model": "deterministic-delayed-proxy-v1",
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                    "response_id": None,
                }
            else:
                output, measurement = _live_response(
                    item=item,
                    stage=stage,
                    prior=prior,
                    api_key=self.server.openai_api_key,
                    model=self.server.openai_model,
                    base_url=self.server.openai_base_url,
                )
            service_seconds = (time.perf_counter_ns() - started) / 1_000_000_000
            sequence = self.server.record(
                {
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "mode": self.server.mode,
                    "question_id": question_id,
                    "request_id": request_id,
                    "stage": stage,
                    "service_seconds": service_seconds,
                    "model_seconds": measurement["model_seconds"],
                    "returned_model": measurement["returned_model"],
                    "usage": measurement["usage"],
                }
            )
            self._send(
                200,
                {
                    "output": output,
                    "measurement": {
                        **measurement,
                        "service_seconds": service_seconds,
                        "sequence": sequence,
                    },
                },
            )
        except Exception as exc:
            self._send(400, {"error": f"{type(exc).__name__}: {exc}"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", choices=("delayed", "live"), required=True)
    parser.add_argument("--delay-seconds", type=float, default=0.05)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    token = os.environ.get("PRAVAL_COMPARISON_PROXY_TOKEN", "")
    if not token:
        raise RuntimeError("PRAVAL_COMPARISON_PROXY_TOKEN is required")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("PRAVAL_COMPARISON_OPENAI_MODEL", "")
    if args.mode == "live" and (not api_key or not model):
        raise RuntimeError("live proxy requires OpenAI key and model")
    server = ComparisonServer(
        ("127.0.0.1", args.port),
        dataset=load_dataset(args.dataset),
        events_path=args.events,
        mode=args.mode,
        delay_seconds=args.delay_seconds,
        token=token,
        openai_api_key=api_key,
        openai_model=model,
        openai_base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    args.ready_file.parent.mkdir(parents=True, exist_ok=True)
    args.ready_file.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": server.server_address[1],
                "mode": args.mode,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    try:
        server.serve_forever(poll_interval=0.05)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
