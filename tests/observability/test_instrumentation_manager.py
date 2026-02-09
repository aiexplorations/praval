import os
import importlib

import pytest


def test_initialize_instrumentation_disabled(monkeypatch):
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "off")
    from praval.observability.config import reset_config
    reset_config()

    from praval.observability.instrumentation.manager import initialize_instrumentation, reset_instrumentation

    reset_instrumentation()
    assert initialize_instrumentation() is False


def test_initialize_and_reset_instrumentation(monkeypatch):
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "on")
    from praval.observability.config import reset_config
    reset_config()

    from praval.observability.instrumentation import manager
    manager.reset_instrumentation()

    from praval import decorators
    original = decorators.agent

    assert manager.initialize_instrumentation() is True
    assert decorators.agent is not original

    manager.reset_instrumentation()
    assert decorators.agent is original
