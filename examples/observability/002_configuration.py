#!/usr/bin/env python3
"""Load a complete, side-effect-free observability configuration."""

from praval import load_config


def main() -> None:
    """Show supported environment overrides without creating SDK resources."""
    config = load_config(
        environ={
            "PRAVAL_SERVICE_NAME": "configured-example",
            "PRAVAL_ENVIRONMENT": "development",
            "PRAVAL_OBSERVABILITY": "on",
            "PRAVAL_OTLP_ENDPOINT": "http://127.0.0.1:4318",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "PRAVAL_SAMPLE_RATE": "0.25",
            "PRAVAL_CAPTURE_CONTENT": "false",
        }
    )
    observability = config.observability
    print(
        "service={service} enabled={enabled} protocol={protocol} sample={sample}".format(
            service=config.app.service_name,
            enabled=observability.enabled,
            protocol=observability.otlp.protocol,
            sample=observability.sample_ratio,
        )
    )


if __name__ == "__main__":
    main()
