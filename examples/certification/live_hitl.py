"""Certify real model-originated HITL decisions and cross-process resume."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from support import (
    live_entrypoint,
    report_dir,
    require_environment,
    write_json_artifact,
)

from praval import Agent, InterventionRequired, ToolSpec
from praval.hitl import HITLService

DECISIONS = ("approve", "edit", "reject")


def paths() -> Dict[str, Path]:
    """Return runner-owned persistent paths shared across child processes."""
    output = report_dir()
    return {
        "database": output / "live-hitl.sqlite3",
        "executions": output / "live-hitl-executions.json",
    }


def build_agent(decision: str) -> Agent:
    """Build the same real OpenAI agent in creation and resume processes."""
    values = require_environment("OPENAI_API_KEY", "PRAVAL_OPENAI_MODEL")
    agent = Agent(
        f"live-hitl-{decision}",
        provider="openai",
        model=values["PRAVAL_OPENAI_MODEL"],
        hitl_enabled=True,
        hitl_db_path=str(paths()["database"]),
        # A reasoning-capable model needs room for both the tool call and the
        # post-approval continuation. Keep the budget bounded, but large enough
        # that a successful tool execution can produce an auditable final reply.
        config={"temperature": 0, "max_output_tokens": 512, "timeout": 60},
    )

    def guarded_multiply(a: int, b: int) -> int:
        execution_path = paths()["executions"]
        entries: List[Dict[str, Any]] = []
        if execution_path.exists():
            entries = json.loads(execution_path.read_text(encoding="utf-8"))
        entries.append({"decision": decision, "a": a, "b": b, "result": a * b})
        execution_path.write_text(
            json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return a * b

    agent.add_tool_spec(
        ToolSpec(
            name="guarded_multiply",
            description=(
                "Multiply two integers. This is the required tool for multiplication."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
            strict=True,
            requires_approval=True,
            risk_level="high",
            approval_reason="Live certification requires an explicit human decision.",
        ),
        guarded_multiply,
    )
    return agent


def create_intervention(decision: str, state_path: Path) -> None:
    """Ask a real model to create and persist a pending tool intervention."""
    with build_agent(decision) as agent:
        try:
            agent.generate(
                "You must call guarded_multiply with a=2 and b=3. Do not calculate "
                "the answer yourself and do not ask a question."
            )
        except InterventionRequired as interruption:
            state = {
                "decision": decision,
                "agent_name": interruption.agent_name,
                "intervention_id": interruption.intervention_id,
                "run_id": interruption.run_id,
                "tool_name": interruption.tool_name,
            }
            state_path.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return
    raise AssertionError("real model did not produce the required HITL tool call")


def resume_intervention(decision: str, state_path: Path, result_path: Path) -> None:
    """Decide and resume the persisted run in a separate Python process."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    with build_agent(decision) as agent:
        if decision == "approve":
            intervention = agent.approve_intervention(
                state["intervention_id"], reviewer="live-certification"
            )
        elif decision == "edit":
            intervention = agent.approve_intervention(
                state["intervention_id"],
                reviewer="live-certification",
                edited_args={"a": 7, "b": 8},
            )
        else:
            intervention = agent.reject_intervention(
                state["intervention_id"],
                reviewer="live-certification",
                reason="Certification rejection path",
            )
        response = agent.resume_run(state["run_id"])
        assert (
            isinstance(response, str) and response.strip()
        ), "resumed provider continuation returned no final text"

    suspended = HITLService(db_path=str(paths()["database"])).get_suspended_run(
        state["run_id"]
    )
    assert suspended is not None, "resumed HITL run was not persisted"
    assert (
        suspended.status == "completed"
    ), f"resumed HITL run ended with status {suspended.status!r}"
    result_path.write_text(
        json.dumps(
            {
                "decision": decision,
                "intervention": intervention.to_dict(),
                "run_id": state["run_id"],
                "run_status": suspended.status,
                "response_chars": len(response),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def run_child(*arguments: str) -> None:
    """Run one phase with a hard timeout and propagate sanitized failure text."""
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *arguments],
        cwd=report_dir(),
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"HITL child phase failed ({completed.returncode}): "
            f"{completed.stdout}\n{completed.stderr}"
        )


def main() -> None:
    """Run create/resume phases and verify approve, edit, and reject semantics."""
    require_environment("OPENAI_API_KEY", "PRAVAL_OPENAI_MODEL")
    output = report_dir()
    for decision in DECISIONS:
        state_path = output / f"live-hitl-{decision}-state.json"
        result_path = output / f"live-hitl-{decision}-result.json"
        run_child("--create", decision, str(state_path))
        run_child("--resume", decision, str(state_path), str(result_path))

    execution_path = paths()["executions"]
    executions = (
        json.loads(execution_path.read_text(encoding="utf-8"))
        if execution_path.exists()
        else []
    )
    by_decision = {entry["decision"]: entry for entry in executions}
    assert by_decision["approve"]["result"] == 6
    assert by_decision["edit"] == {
        "decision": "edit",
        "a": 7,
        "b": 8,
        "result": 56,
    }
    assert "reject" not in by_decision

    results = {
        decision: json.loads(
            (output / f"live-hitl-{decision}-result.json").read_text(encoding="utf-8")
        )
        for decision in DECISIONS
    }
    write_json_artifact(
        "live-hitl.json",
        {
            "cross_process_resume": True,
            "decisions": results,
            "tool_executions": executions,
        },
    )
    print("CERTIFIED: real model HITL approve/edit/reject and cross-process resume")


def dispatch() -> None:
    """Dispatch parent and child modes without bypassing live error semantics."""
    if len(sys.argv) > 1 and sys.argv[1] == "--create":
        live_entrypoint(lambda: create_intervention(sys.argv[2], Path(sys.argv[3])))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--resume":
        live_entrypoint(
            lambda: resume_intervention(
                sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
            )
        )
        return
    live_entrypoint(main)


if __name__ == "__main__":
    dispatch()
