#!/usr/bin/env python3
"""
Example 002: Configuration Demo
================================

This example demonstrates the configuration system:
- Environment variable configuration
- Auto-detection of dev/prod environments
- Sampling configuration
- Enabling/disabling observability

Run: python examples/observability/002_configuration_demo.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from praval.observability import get_config, get_tracer
from praval.observability.config import reset_config


def show_config():
    """Display current configuration."""
    config = get_config()

    print("Current Configuration:")
    print(f"  Enabled: {config.enabled}")
    print(f"  Sample rate: {config.sample_rate * 100:.0f}%")
    print(f"  OTLP endpoint: {config.otlp_endpoint or 'None (local only)'}")
    print(f"  Storage path: {config.storage_path}")
    print()


def demo_default_config():
    """Demonstrate default configuration."""
    print("=" * 70)
    print("1. Default Configuration (No environment variables set)")
    print("=" * 70)
    print()

    # Clear any existing config
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print(f"  - Observability is {'ENABLED' if config.is_enabled() else 'DISABLED'}")
    print(f"  - In development: Auto-enabled")
    print(f"  - In production: Auto-disabled")
    print(f"  - Traces stored to: {config.storage_path}")
    print()


def demo_explicit_on():
    """Demonstrate explicitly enabling observability."""
    print("=" * 70)
    print("2. Explicitly Enabled (PRAVAL_OBSERVABILITY=on)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "on"
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Observability ENABLED regardless of environment")
    print("  - All operations traced")
    print("  - Useful for production debugging")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]


def demo_explicit_off():
    """Demonstrate explicitly disabling observability."""
    print("=" * 70)
    print("3. Explicitly Disabled (PRAVAL_OBSERVABILITY=off)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "off"
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Observability DISABLED regardless of environment")
    print("  - Zero overhead (no spans created)")
    print("  - Useful for performance-critical scenarios")
    print()

    # Test that spans are not created
    tracer = get_tracer()
    span = tracer.start_span("test")
    print(f"  - Span type when disabled: {type(span).__name__}")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]


def demo_production_auto():
    """Demonstrate auto-detection in production."""
    print("=" * 70)
    print("4. Auto-Detection in Production (ENVIRONMENT=production)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "auto"
    os.environ["ENVIRONMENT"] = "production"
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Auto-detected production environment")
    print("  - Observability DISABLED by default")
    print("  - Reduces overhead in production")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]
    del os.environ["ENVIRONMENT"]


def demo_sampling():
    """Demonstrate sampling configuration."""
    print("=" * 70)
    print("5. Sampling (PRAVAL_SAMPLE_RATE=0.1)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "on"
    os.environ["PRAVAL_SAMPLE_RATE"] = "0.1"  # 10% sampling
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Only 10% of operations are traced")
    print("  - Reduces storage and overhead")
    print("  - Useful for high-volume production")
    print()

    # Test sampling
    tracer = get_tracer()
    sampled_count = 0
    total_attempts = 100

    for _ in range(total_attempts):
        reset_config()  # Reset to get new sampling decisions
        if config.should_sample():
            sampled_count += 1

    print(f"  - Out of {total_attempts} attempts, {sampled_count} were sampled")
    print(f"  - Actual rate: {sampled_count/total_attempts * 100:.0f}%")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]
    del os.environ["PRAVAL_SAMPLE_RATE"]


def demo_custom_storage():
    """Demonstrate custom storage path."""
    print("=" * 70)
    print("6. Custom Storage Path (PRAVAL_TRACES_PATH)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "on"
    os.environ["PRAVAL_TRACES_PATH"] = "/tmp/my_custom_traces.db"
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Traces stored to custom location")
    print("  - Useful for separating different environments")
    print("  - Can use different paths for different applications")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]
    del os.environ["PRAVAL_TRACES_PATH"]


def demo_otlp_export():
    """Demonstrate OTLP endpoint configuration."""
    print("=" * 70)
    print("7. OTLP Export (PRAVAL_OTLP_ENDPOINT)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "on"
    os.environ["PRAVAL_OTLP_ENDPOINT"] = "http://localhost:4318/v1/traces"
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Traces exported to OTLP endpoint (when Phase 3 is complete)")
    print("  - Works with Jaeger, Zipkin, cloud collectors")
    print("  - Traces also stored locally in SQLite")
    print()

    print("Example OTLP-compatible tools:")
    print("  - Jaeger: docker run -p 4318:4318 -p 16686:16686 jaegertracing/all-in-one")
    print("  - Zipkin: docker run -p 4318:4318 -p 9411:9411 openzipkin/zipkin")
    print("  - OpenTelemetry Collector: docker run -p 4318:4318 otel/opentelemetry-collector")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]
    del os.environ["PRAVAL_OTLP_ENDPOINT"]


def demo_combined_config():
    """Demonstrate combining multiple configuration options."""
    print("=" * 70)
    print("8. Combined Configuration (Production with Sampling)")
    print("=" * 70)
    print()

    os.environ["PRAVAL_OBSERVABILITY"] = "on"  # Explicitly enable
    os.environ["PRAVAL_SAMPLE_RATE"] = "0.1"   # 10% sampling
    os.environ["PRAVAL_OTLP_ENDPOINT"] = "http://collector:4318/v1/traces"
    reset_config()

    config = get_config()
    show_config()

    print("Behavior:")
    print("  - Observability enabled in production")
    print("  - Only 10% of requests traced (low overhead)")
    print("  - Traces exported to centralized collector")
    print("  - Also stored locally for debugging")
    print()

    print("Use case:")
    print("  - Production monitoring with controlled overhead")
    print("  - Centralized trace collection for analysis")
    print("  - Local backup for troubleshooting")
    print()

    del os.environ["PRAVAL_OBSERVABILITY"]
    del os.environ["PRAVAL_SAMPLE_RATE"]
    del os.environ["PRAVAL_OTLP_ENDPOINT"]


def main():
    """Run the configuration demo."""
    print("\n" + "=" * 70)
    print("Praval Observability - Configuration Demo")
    print("=" * 70)
    print()
    print("This demo shows all 3 configuration options:")
    print("  1. PRAVAL_OBSERVABILITY (auto|on|off)")
    print("  2. PRAVAL_OTLP_ENDPOINT (optional)")
    print("  3. PRAVAL_SAMPLE_RATE (0.0-1.0)")
    print()

    demo_default_config()
    demo_explicit_on()
    demo_explicit_off()
    demo_production_auto()
    demo_sampling()
    demo_custom_storage()
    demo_otlp_export()
    demo_combined_config()

    print("=" * 70)
    print("Configuration Demo Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("✓ Only 3 environment variables for simple configuration")
    print("✓ Sensible defaults (auto-detect dev/prod)")
    print("✓ Sampling for performance control")
    print("✓ OTLP export for enterprise tools")
    print("✓ Local SQLite storage always available")
    print()


if __name__ == "__main__":
    main()
