"""Tests for praval HITL CLI commands."""

from pathlib import Path
from unittest.mock import Mock, patch

from praval.cli import main
from praval.hitl.service import HITLService


def _seed(db_path: str):
    service = HITLService(db_path=db_path)
    intervention = service.store.create_intervention(
        run_id="run-cli-1",
        agent_name="agent-cli",
        provider_name="openai",
        tool_name="tool_cli",
        tool_call_id="call-cli-1",
        original_args={"x": 1},
    )
    service.store.upsert_suspended_run(
        run_id="run-cli-1",
        agent_name="agent-cli",
        provider_name="openai",
        state={"schema": "openai_tool_v1", "intervention_id": intervention.id},
    )
    return service, intervention


def test_cli_pending_and_show(tmp_path: Path, capsys):
    db_path = str(tmp_path / "hitl.db")
    _, intervention = _seed(db_path)

    rc_pending = main(["--hitl-db-path", db_path, "hitl", "pending"])
    assert rc_pending == 0
    pending_out = capsys.readouterr().out
    assert intervention.id in pending_out

    rc_show = main(
        [
            "--hitl-db-path",
            db_path,
            "hitl",
            "show",
            intervention.id,
        ]
    )
    assert rc_show == 0
    show_out = capsys.readouterr().out
    assert '"id"' in show_out
    assert intervention.id in show_out


def test_cli_approve_reject(tmp_path: Path, capsys):
    db_path = str(tmp_path / "hitl.db")
    service, intervention = _seed(db_path)

    rc_approve = main(
        [
            "--hitl-db-path",
            db_path,
            "hitl",
            "approve",
            intervention.id,
            "--reviewer",
            "qa",
            "--edited-args-json",
            '{"x": 5}',
        ]
    )
    assert rc_approve == 0
    approve_out = capsys.readouterr().out
    assert "APPROVED" in approve_out

    second = service.store.create_intervention(
        run_id="run-cli-2",
        agent_name="agent-cli",
        provider_name="openai",
        tool_name="tool_cli",
        tool_call_id="call-cli-2",
        original_args={},
    )
    rc_reject = main(
        [
            "--hitl-db-path",
            db_path,
            "hitl",
            "reject",
            second.id,
            "--reason",
            "unsafe",
            "--reviewer",
            "ops",
        ]
    )
    assert rc_reject == 0
    reject_out = capsys.readouterr().out
    assert "REJECTED" in reject_out


def test_cli_resume_uses_registered_agent(tmp_path: Path, capsys):
    db_path = str(tmp_path / "hitl.db")
    service, intervention = _seed(db_path)
    service.approve_intervention(intervention.id, reviewer="qa")

    fake_agent = Mock()
    fake_agent.resume_run.return_value = "resumed"

    fake_registry = Mock()
    fake_registry.get_agent.return_value = fake_agent

    with patch("praval.cli.get_registry", return_value=fake_registry):
        rc = main(
            [
                "--hitl-db-path",
                db_path,
                "hitl",
                "resume",
                "run-cli-1",
            ]
        )

    assert rc == 0
    out = capsys.readouterr().out
    assert "resumed" in out
    fake_agent.resume_run.assert_called_once_with("run-cli-1")
