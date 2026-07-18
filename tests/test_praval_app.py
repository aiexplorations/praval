"""Tests for explicit Praval application ownership."""

from unittest.mock import Mock, patch

from praval.app import PravalApp, get_default_app, reset_default_app


def test_praval_app_create_agent_tracks_owned_agent():
    reef = Mock()
    registry = Mock()
    created_agent = Mock()
    created_agent.name = "planner"

    with patch("praval.app.Agent", return_value=created_agent) as mock_agent:
        app = PravalApp(reef=reef, provider_registry=registry)
        agent = app.create_agent("planner", provider="openai")

    mock_agent.assert_called_once_with("planner", provider="openai")
    assert agent is created_agent
    assert app._agents["planner"] is created_agent


def test_praval_app_register_agent_tracks_external_agent():
    app = PravalApp(reef=Mock(), provider_registry=Mock())
    agent = Mock()
    agent.name = "external"

    returned = app.register_agent(agent)

    assert returned is agent
    assert app._agents["external"] is agent


def test_praval_app_close_closes_agents_and_reef_once():
    reef = Mock()
    app = PravalApp(reef=reef, provider_registry=Mock())
    agent = Mock()
    agent.name = "owned"
    app.register_agent(agent)

    app.close()
    app.close()

    agent.close.assert_called_once()
    reef.shutdown.assert_called_once()
    assert app._agents == {}


def test_praval_app_rejects_agent_changes_after_close():
    app = PravalApp(reef=Mock(), provider_registry=Mock())
    app.close()

    try:
        app.register_agent(Mock(name="late"))
    except RuntimeError as exc:
        assert str(exc) == "PravalApp is closed"
    else:
        raise AssertionError("register_agent should fail after close")


def test_praval_app_context_manager_closes_on_exit():
    reef = Mock()
    agent = Mock()
    agent.name = "managed"

    with PravalApp(reef=reef, provider_registry=Mock()) as app:
        app.register_agent(agent)

    agent.close.assert_called_once()
    reef.shutdown.assert_called_once()


def test_praval_app_ignores_reef_shutdown_errors():
    reef = Mock()
    reef.shutdown.side_effect = RuntimeError("already stopped")
    app = PravalApp(reef=reef, provider_registry=Mock())

    app.close()

    reef.shutdown.assert_called_once()


def test_default_app_reset_replaces_previous_instance():
    first = reset_default_app()
    second = get_default_app()

    assert first is second

    replacement = reset_default_app()

    assert replacement is not first
    assert first.is_closed if hasattr(first, "is_closed") else first._closed
