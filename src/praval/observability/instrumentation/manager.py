"""
Instrumentation manager.

Coordinates all instrumentation of Praval components.
"""

import logging
from typing import Optional

from ..config import get_config

logger = logging.getLogger(__name__)

# Global flag to track if instrumentation is initialized
_instrumentation_initialized = False


def initialize_instrumentation() -> bool:
    """Initialize automatic instrumentation of Praval framework.

    This should be called once when the observability module is imported.

    Returns:
        True if instrumentation was initialized, False if disabled or already initialized
    """
    global _instrumentation_initialized

    # Check if already initialized
    if _instrumentation_initialized:
        return True

    # Check if observability is enabled
    config = get_config()
    if not config.is_enabled():
        logger.debug("Observability disabled, skipping instrumentation")
        return False

    try:
        # Instrument components
        # Note: Actual instrumentation will be added in subsequent implementations
        # For now, just mark as initialized
        _instrumentation_initialized = True
        logger.info("Praval observability instrumentation initialized")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize instrumentation: {e}")
        return False


def is_instrumented() -> bool:
    """Check if instrumentation is initialized.

    Returns:
        True if instrumentation is active
    """
    return _instrumentation_initialized
