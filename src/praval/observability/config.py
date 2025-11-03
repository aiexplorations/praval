"""
Observability Configuration.

Simple global configuration loaded from environment variables.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ObservabilityConfig:
    """Global observability configuration.

    Configuration is loaded from environment variables:
    - PRAVAL_OBSERVABILITY: "auto" | "on" | "off" (default: "auto")
    - PRAVAL_OTLP_ENDPOINT: OTLP endpoint URL (default: None)
    - PRAVAL_SAMPLE_RATE: 0.0-1.0 (default: 1.0)
    - PRAVAL_TRACES_PATH: SQLite database path (default: ~/.praval/traces.db)
    """

    enabled: bool = True
    sample_rate: float = 1.0
    otlp_endpoint: Optional[str] = None
    storage_path: str = "~/.praval/traces.db"

    @classmethod
    def from_env(cls) -> 'ObservabilityConfig':
        """Load configuration from environment variables.

        Returns:
            ObservabilityConfig instance
        """
        obs_mode = os.getenv("PRAVAL_OBSERVABILITY", "auto").lower()

        # Determine if observability should be enabled
        if obs_mode == "off":
            enabled = False
        elif obs_mode == "on":
            enabled = True
        else:  # auto
            # Enable in development, disable in production
            env = os.getenv("ENVIRONMENT", "development").lower()
            enabled = env not in ["production", "prod"]

        # Load other configuration
        sample_rate = float(os.getenv("PRAVAL_SAMPLE_RATE", "1.0"))
        otlp_endpoint = os.getenv("PRAVAL_OTLP_ENDPOINT")
        storage_path = os.getenv("PRAVAL_TRACES_PATH", "~/.praval/traces.db")

        # Expand storage path
        storage_path = str(Path(storage_path).expanduser())

        return cls(
            enabled=enabled,
            sample_rate=sample_rate,
            otlp_endpoint=otlp_endpoint,
            storage_path=storage_path
        )

    def is_enabled(self) -> bool:
        """Check if observability is enabled.

        Returns:
            True if observability is enabled
        """
        return self.enabled

    def should_sample(self) -> bool:
        """Check if current request should be sampled.

        Uses simple random sampling based on sample_rate.

        Returns:
            True if should sample this request
        """
        if self.sample_rate >= 1.0:
            return True

        import random
        return random.random() < self.sample_rate


# Global configuration instance
_global_config: Optional[ObservabilityConfig] = None


def get_config() -> ObservabilityConfig:
    """Get global observability configuration.

    Returns:
        ObservabilityConfig instance
    """
    global _global_config

    if _global_config is None:
        _global_config = ObservabilityConfig.from_env()

    return _global_config


def reset_config() -> None:
    """Reset global configuration (mainly for testing)."""
    global _global_config
    _global_config = None
