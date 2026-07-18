"""Tests for installation and provider diagnostics in the Praval CLI."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from praval.cli import _diagnostic_report, _installation_source, main


def test_cli_version_reports_installed_distribution(capsys):
    distribution = SimpleNamespace(version="0.8.1")
    with patch("praval.cli._installed_distribution", return_value=distribution):
        assert main(["--version"]) == 0

    assert capsys.readouterr().out == "praval 0.8.1\n"


def test_doctor_json_has_stable_shape_and_never_prints_secrets(monkeypatch, capsys):
    secrets = {
        "OPENAI_API_KEY": "openai-secret-value",
        "ANTHROPIC_API_KEY": "anthropic-secret-value",
        "COHERE_API_KEY": "cohere-secret-value",
        "GEMINI_API_KEY": "gemini-secret-value",
        "OPENAI_COMPATIBLE_BASE_URL": "https://models.example.invalid/v1",
        "OPENAI_COMPATIBLE_API_KEY": "compatible-secret-value",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)

    assert main(["doctor", "--json"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)

    assert report["schema_version"] == 1
    assert set(report) == {
        "schema_version",
        "praval",
        "python",
        "optional_features",
        "providers",
    }
    assert report["providers"]["openai"]["configured"] is True
    assert report["providers"]["gemini"]["configured"] is True
    assert report["providers"]["openai_compatible"]["configured"] is True
    assert report["providers"]["openai"]["environment"] == {"OPENAI_API_KEY": True}
    for value in secrets.values():
        assert value not in output


def test_doctor_text_reports_status_without_treating_missing_keys_as_errors(
    monkeypatch, capsys
):
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "COHERE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "Praval " in output
    assert "Optional features:" in output
    assert "Provider configuration:" in output
    assert "openai: not configured" in output
    assert "gemini: not configured" in output


def test_diagnostic_report_handles_feature_presence_and_gemini_alias(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret-value")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch(
        "praval.cli._module_available", side_effect=lambda name: name == "pypdf"
    ):
        report = _diagnostic_report()

    assert report["providers"]["gemini"]["configured"] is True
    assert report["optional_features"]["pdf"]["available"] is True
    assert report["optional_features"]["mcp"]["available"] is False


def test_installation_source_classifies_wheel_editable_and_unknown():
    wheel = SimpleNamespace(
        read_text=lambda name: (
            '{"url":"file:///tmp/praval-0.8.1-py3-none-any.whl"}'
            if name == "direct_url.json"
            else None
        )
    )
    editable = SimpleNamespace(
        read_text=lambda name: (
            '{"url":"file:///src/praval","dir_info":{"editable":true}}'
            if name == "direct_url.json"
            else None
        )
    )
    unknown = SimpleNamespace(read_text=lambda _name: None)

    assert _installation_source(wheel) == "wheel"
    assert _installation_source(editable) == "editable"
    assert _installation_source(unknown) == "unknown"
    assert _installation_source(None) == "source-tree"
