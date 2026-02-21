"""Praval command-line interface."""

import argparse
import importlib
import json
from typing import Any, Dict, Optional

from .core.registry import get_registry
from .hitl.service import HITLService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="praval", description="Praval CLI")
    parser.add_argument(
        "--hitl-db-path",
        default=None,
        help="Override HITL SQLite database path",
    )

    subparsers = parser.add_subparsers(dest="command")
    hitl_parser = subparsers.add_parser("hitl", help="Human-in-the-loop operations")
    hitl_subparsers = hitl_parser.add_subparsers(dest="hitl_command")

    pending_parser = hitl_subparsers.add_parser(
        "pending", help="List pending interventions"
    )
    pending_parser.add_argument("--agent", default=None, help="Filter by agent name")
    pending_parser.add_argument("--run-id", default=None, help="Filter by run id")
    pending_parser.add_argument("--limit", type=int, default=100)

    show_parser = hitl_subparsers.add_parser("show", help="Show an intervention")
    show_parser.add_argument("intervention_id")

    approve_parser = hitl_subparsers.add_parser(
        "approve", help="Approve/edit an intervention"
    )
    approve_parser.add_argument("intervention_id")
    approve_parser.add_argument("--reviewer", default="human")
    approve_parser.add_argument(
        "--edited-args-json",
        default=None,
        help="JSON object to override tool call args",
    )

    reject_parser = hitl_subparsers.add_parser("reject", help="Reject an intervention")
    reject_parser.add_argument("intervention_id")
    reject_parser.add_argument("--reason", required=True)
    reject_parser.add_argument("--reviewer", default="human")

    resume_parser = hitl_subparsers.add_parser("resume", help="Resume a suspended run")
    resume_parser.add_argument("run_id")
    resume_parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Import module(s) before resolving agent from registry",
    )

    return parser


def _service(db_path: Optional[str]) -> HITLService:
    return HITLService(db_path=db_path)


def _print_intervention_row(intervention) -> None:
    print(
        f"{intervention.id} | run={intervention.run_id} | "
        f"agent={intervention.agent_name} | tool={intervention.tool_name} | "
        f"status={intervention.status.value}"
    )


def _cmd_pending(args: argparse.Namespace) -> int:
    service = _service(args.hitl_db_path)
    pending = service.get_pending_interventions(
        run_id=args.run_id,
        agent_name=args.agent,
        limit=args.limit,
    )
    if not pending:
        print("No pending interventions")
        return 0
    for intervention in pending:
        _print_intervention_row(intervention)
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    service = _service(args.hitl_db_path)
    intervention = service.get_intervention(args.intervention_id)
    if intervention is None:
        print(f"Intervention '{args.intervention_id}' not found")
        return 1
    print(json.dumps(intervention.to_dict(), indent=2, sort_keys=True))
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    service = _service(args.hitl_db_path)
    edited_args: Optional[Dict[str, Any]] = None
    if args.edited_args_json:
        try:
            parsed = json.loads(args.edited_args_json)
        except json.JSONDecodeError as exc:
            print(f"Invalid --edited-args-json: {exc}")
            return 1
        if not isinstance(parsed, dict):
            print("--edited-args-json must be a JSON object")
            return 1
        edited_args = parsed

    intervention = service.approve_intervention(
        args.intervention_id,
        reviewer=args.reviewer,
        edited_args=edited_args,
    )
    print(
        f"Intervention {intervention.id} marked {intervention.status.value} "
        f"(decision={intervention.decision.value if intervention.decision else 'N/A'})"
    )
    return 0


def _cmd_reject(args: argparse.Namespace) -> int:
    service = _service(args.hitl_db_path)
    intervention = service.reject_intervention(
        args.intervention_id,
        reviewer=args.reviewer,
        reason=args.reason,
    )
    print(
        f"Intervention {intervention.id} marked {intervention.status.value} "
        f"(decision={intervention.decision.value if intervention.decision else 'N/A'})"
    )
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    service = _service(args.hitl_db_path)
    suspended = service.get_suspended_run(args.run_id)
    if suspended is None:
        print(f"Suspended run '{args.run_id}' not found")
        return 1

    for module_name in args.module:
        importlib.import_module(module_name)

    registry = get_registry()
    agent = registry.get_agent(suspended.agent_name)
    if agent is None:
        print(
            f"Agent '{suspended.agent_name}' is not registered in this process. "
            f"Import the module defining the agent and retry with --module."
        )
        return 1

    response = agent.resume_run(args.run_id)
    print(response)
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "hitl":
        parser.print_help()
        return 1

    if args.hitl_command == "pending":
        return _cmd_pending(args)
    if args.hitl_command == "show":
        return _cmd_show(args)
    if args.hitl_command == "approve":
        return _cmd_approve(args)
    if args.hitl_command == "reject":
        return _cmd_reject(args)
    if args.hitl_command == "resume":
        return _cmd_resume(args)

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
