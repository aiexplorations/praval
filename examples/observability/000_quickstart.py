#!/usr/bin/env python3
"""Create and inspect one explicitly configured local trace."""

from __future__ import annotations

import argparse
from pathlib import Path

from praval.observability import (
    ObservabilityConfig,
    configure_observability,
    force_flush,
    get_trace_store,
    get_tracer,
    shutdown_observability,
)


def main() -> None:
    """Run the local diagnostic quickstart."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path(".praval/telemetry.db"))
    args = parser.parse_args()

    config = ObservabilityConfig(
        enabled=True,
        local={"enabled": True, "path": str(args.db)},
        otlp={"traces": True, "metrics": False, "logs": False},
    )
    configure_observability(config, service_name="praval-local-quickstart")
    try:
        with get_tracer().start_as_current_span("prepare-report") as span:
            span.set_attribute("report.kind", "example")
            trace_id = format(span.get_span_context().trace_id, "032x")

        if not force_flush(5_000):
            raise RuntimeError("local telemetry did not flush within five seconds")
        rows = get_trace_store().get_trace(trace_id)
        print(f"trace_id={trace_id} spans={len(rows)} db={args.db}")
    finally:
        shutdown_observability(5_000)


if __name__ == "__main__":
    main()
