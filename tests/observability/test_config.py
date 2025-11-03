"""
Tests for observability configuration.
"""

import os
import pytest

from praval.observability.config import ObservabilityConfig, get_config, reset_config


class TestObservabilityConfig:
    """Tests for ObservabilityConfig."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()
        # Clear environment variables
        for key in ["PRAVAL_OBSERVABILITY", "PRAVAL_OTLP_ENDPOINT",
                    "PRAVAL_SAMPLE_RATE", "PRAVAL_TRACES_PATH", "ENVIRONMENT"]:
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_default_config(self):
        """Test default configuration."""
        config = ObservabilityConfig.from_env()

        assert config.enabled is True  # Default development environment
        assert config.sample_rate == 1.0
        assert config.otlp_endpoint is None
        assert "/.praval/traces.db" in config.storage_path

    def test_observability_off(self):
        """Test explicitly disabling observability."""
        os.environ["PRAVAL_OBSERVABILITY"] = "off"
        config = ObservabilityConfig.from_env()

        assert config.enabled is False
        assert config.is_enabled() is False

    def test_observability_on(self):
        """Test explicitly enabling observability."""
        os.environ["PRAVAL_OBSERVABILITY"] = "on"
        config = ObservabilityConfig.from_env()

        assert config.enabled is True
        assert config.is_enabled() is True

    def test_observability_auto_development(self):
        """Test auto mode in development."""
        os.environ["PRAVAL_OBSERVABILITY"] = "auto"
        os.environ["ENVIRONMENT"] = "development"
        config = ObservabilityConfig.from_env()

        assert config.enabled is True

    def test_observability_auto_production(self):
        """Test auto mode in production."""
        os.environ["PRAVAL_OBSERVABILITY"] = "auto"
        os.environ["ENVIRONMENT"] = "production"
        config = ObservabilityConfig.from_env()

        assert config.enabled is False

    def test_sample_rate(self):
        """Test sample rate configuration."""
        os.environ["PRAVAL_SAMPLE_RATE"] = "0.5"
        config = ObservabilityConfig.from_env()

        assert config.sample_rate == 0.5

    def test_otlp_endpoint(self):
        """Test OTLP endpoint configuration."""
        os.environ["PRAVAL_OTLP_ENDPOINT"] = "http://localhost:4318/v1/traces"
        config = ObservabilityConfig.from_env()

        assert config.otlp_endpoint == "http://localhost:4318/v1/traces"

    def test_custom_storage_path(self):
        """Test custom storage path."""
        os.environ["PRAVAL_TRACES_PATH"] = "/tmp/custom_traces.db"
        config = ObservabilityConfig.from_env()

        assert config.storage_path == "/tmp/custom_traces.db"

    def test_should_sample_always(self):
        """Test sampling with 100% rate."""
        config = ObservabilityConfig(sample_rate=1.0)

        # Should always sample
        for _ in range(10):
            assert config.should_sample() is True

    def test_should_sample_never(self):
        """Test sampling with 0% rate."""
        config = ObservabilityConfig(sample_rate=0.0)

        # Should never sample
        for _ in range(10):
            assert config.should_sample() is False

    def test_should_sample_probabilistic(self):
        """Test probabilistic sampling."""
        config = ObservabilityConfig(sample_rate=0.5)

        # Run many times and check distribution
        samples = sum(1 for _ in range(1000) if config.should_sample())

        # Should be around 500, allow some variance
        assert 400 < samples < 600

    def test_global_config(self):
        """Test global configuration instance."""
        os.environ["PRAVAL_OBSERVABILITY"] = "on"

        config1 = get_config()
        config2 = get_config()

        # Should return same instance
        assert config1 is config2
        assert config1.enabled is True
