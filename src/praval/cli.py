"""Praval command-line interface."""

import argparse
import importlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .core.registry import get_registry
from .hitl.service import HITLService

OPTIONAL_FEATURE_MODULES = {
    "mcp": ("mcp",),
    "pdf": ("pypdf",),
    "memory": ("chromadb", "sentence_transformers"),
    "secure_transport": ("aio_pika", "nacl", "msgpack"),
    "postgresql": ("asyncpg", "psycopg2"),
    "redis": ("redis",),
    "s3": ("boto3",),
    "qdrant": ("qdrant_client",),
    "notebooks": ("jupyterlab", "nbclient", "nbformat"),
}

PROVIDER_ENVIRONMENT = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "cohere": ("COHERE_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai_compatible": (
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
    ),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="praval", description="Praval CLI")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the installed Praval version and exit",
    )
    parser.add_argument(
        "--hitl-db-path",
        default=None,
        help="Override HITL SQLite database path",
    )

    subparsers = parser.add_subparsers(dest="command")
    doctor_parser = subparsers.add_parser(
        "doctor", help="Report installation and optional feature diagnostics"
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print a machine-readable report",
    )
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


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _installed_distribution() -> Any:
    try:
        return importlib.metadata.distribution("praval")
    except importlib.metadata.PackageNotFoundError:
        return None


def _installation_source(distribution: Any) -> str:
    if distribution is None:
        return "source-tree"
    direct_url_text = distribution.read_text("direct_url.json")
    if direct_url_text:
        try:
            direct_url = json.loads(direct_url_text)
        except json.JSONDecodeError:
            direct_url = {}
        if direct_url.get("dir_info", {}).get("editable"):
            return "editable"
        if str(direct_url.get("url", "")).lower().endswith(".whl"):
            return "wheel"
        if direct_url.get("url"):
            return "local-or-vcs"
    if distribution.read_text("WHEEL"):
        return "wheel"
    return "unknown"


def _diagnostic_report() -> Dict[str, Any]:
    distribution = _installed_distribution()
    package_path = str(Path(__file__).resolve().parent)
    if distribution is None:
        package_version = "0+unknown"
    else:
        package_version = distribution.version

    features: Dict[str, Any] = {}
    for feature, modules in OPTIONAL_FEATURE_MODULES.items():
        module_status = {name: _module_available(name) for name in modules}
        features[feature] = {
            "available": all(module_status.values()),
            "modules": module_status,
        }

    providers: Dict[str, Any] = {}
    for provider, variables in PROVIDER_ENVIRONMENT.items():
        presence = {name: bool(os.environ.get(name)) for name in variables}
        if provider == "gemini":
            configured = any(presence.values())
        elif provider == "openai_compatible":
            configured = presence["OPENAI_COMPATIBLE_BASE_URL"]
        else:
            configured = all(presence.values())
        providers[provider] = {
            "configured": configured,
            "environment": presence,
        }

    return {
        "schema_version": 1,
        "praval": {
            "version": package_version,
            "package_path": package_path,
            "installation_source": _installation_source(distribution),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": str(Path(sys.executable).resolve()),
        },
        "optional_features": features,
        "providers": providers,
    }


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = _diagnostic_report()
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print(f"Praval {report['praval']['version']}")
    print(
        f"Python {report['python']['version']} ({report['python']['implementation']})"
    )
    print(f"Package: {report['praval']['package_path']}")
    print(f"Installation: {report['praval']['installation_source']}")
    print("Optional features:")
    for name, details in report["optional_features"].items():
        status = "available" if details["available"] else "not installed"
        print(f"  {name}: {status}")
    print("Provider configuration:")
    for name, details in report["providers"].items():
        status = "configured" if details["configured"] else "not configured"
        print(f"  {name}: {status}")
    return 0


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

    if args.version:
        distribution = _installed_distribution()
        package_version = (
            distribution.version if distribution is not None else "0+unknown"
        )
        print(f"praval {package_version}")
        return 0

    if args.command == "doctor":
        return _cmd_doctor(args)

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
