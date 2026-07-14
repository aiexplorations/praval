"""Presentation and certification helpers for Praval learning notebooks.

This module deliberately contains no agent workflow logic. Learners should see
every meaningful Praval operation in the notebook that teaches it.
"""

from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from IPython.display import HTML, display

from praval import get_provider_registry
from praval.models import ModelResponse, ProviderCapabilities

_EVENTS: List[Dict[str, Any]] = []
_STARTED = time.perf_counter()

_COLORS = {
    "agent": ("#eaf2ff", "#1d4ed8"),
    "reef": ("#ecfeff", "#0e7490"),
    "spore": ("#f5f3ff", "#6d28d9"),
    "tool": ("#fff7ed", "#c2410c"),
    "memory": ("#ecfdf5", "#047857"),
    "human": ("#fdf2f8", "#be185d"),
    "provider": ("#f8fafc", "#475569"),
    "default": ("#f8fafc", "#334155"),
}


class NotebookLifecycleProvider:
    """Credential-free adapter for handlers that never call a model."""

    provider_name = "notebook-lifecycle"
    capabilities = ProviderCapabilities(text=True)

    def __init__(self, config: Any):
        self.config = config

    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        return ModelResponse(
            content="Notebook lifecycle response",
            provider=self.provider_name,
            model=request.model,
        )

    def close(self) -> None:
        """Close the stateless adapter."""


def setup_notebook(number: int, title: str, *, total: int = 13) -> None:
    """Initialize deterministic notebook state and show course progress."""
    _setup_environment()
    show_progress(number, title, total=total)


def setup_case_study(title: str) -> None:
    """Initialize deterministic state and render a capstone banner."""
    _setup_environment()
    display(
        HTML(
            '<div style="border:1px solid #cbd5e1;border-radius:12px;'
            'padding:14px 16px;background:#fff;margin:8px 0 18px">'
            '<div style="color:#475569;font-size:12px">PRAVAL CASE STUDY</div>'
            f'<div style="font-size:20px;font-weight:650;color:#0f172a">'
            f"{html.escape(title)}</div>"
            '<div style="height:5px;background:#0e7490;border-radius:4px;'
            'margin-top:10px"></div></div>'
        )
    )


def _setup_environment() -> None:
    """Reset shared presentation state and configure keyless lifecycle defaults."""
    global _STARTED
    _EVENTS.clear()
    _STARTED = time.perf_counter()

    registry = get_provider_registry()
    registry.register_provider(
        "notebook-lifecycle",
        NotebookLifecycleProvider,
        default_model="notebook-lifecycle-model",
        capabilities=NotebookLifecycleProvider.capabilities,
    )
    os.environ.setdefault("PRAVAL_DEFAULT_PROVIDER", "notebook-lifecycle")
    os.environ.setdefault("PRAVAL_DEFAULT_MODEL", "notebook-lifecycle-model")
    os.environ.setdefault("PRAVAL_OBSERVABILITY", "off")


def show_progress(number: int, title: str, *, total: int = 13) -> None:
    """Render a compact course progress banner."""
    progress = max(0, min(100, round(((number + 1) / total) * 100)))
    display(
        HTML(
            '<div style="border:1px solid #cbd5e1;border-radius:12px;'
            'padding:14px 16px;background:#fff;margin:8px 0 18px">'
            f'<div style="color:#475569;font-size:12px">PRAVAL COURSE '
            f"{number:02d} OF {total - 1:02d}</div>"
            f'<div style="font-size:20px;font-weight:650;color:#0f172a">'
            f"{html.escape(title)}</div>"
            '<div style="height:5px;background:#e2e8f0;border-radius:4px;'
            'margin-top:10px"><div style="height:5px;background:#2563eb;'
            f'border-radius:4px;width:{progress}%"></div></div></div>'
        )
    )


def show_callout(title: str, body: str, *, role: str = "default") -> None:
    """Render a restrained semantic callout."""
    background, accent = _COLORS.get(role, _COLORS["default"])
    display(
        HTML(
            f'<div style="border-left:4px solid {accent};background:{background};'
            'padding:12px 14px;border-radius:8px;margin:10px 0">'
            f'<strong style="color:{accent}">{html.escape(title)}</strong>'
            f'<div style="color:#1e293b;margin-top:4px">'
            f"{html.escape(body)}</div></div>"
        )
    )


def show_flow(*steps: Tuple[str, str, str]) -> None:
    """Render a left-to-right architecture or message-flow diagram."""
    cards = []
    for index, step in enumerate(steps):
        name, detail = step[:2]
        role = step[2] if len(step) > 2 else "default"
        background, accent = _COLORS.get(role, _COLORS["default"])
        if index:
            cards.append('<div style="font-size:22px;color:#64748b">→</div>')
        cards.append(
            f'<div style="padding:12px 15px;border:1px solid {accent};'
            f'border-radius:10px;background:{background};min-width:130px">'
            f'<strong style="color:{accent}">{html.escape(name)}</strong><br>'
            f'<span style="color:#475569;font-size:12px">'
            f"{html.escape(detail)}</span></div>"
        )
    display(
        HTML(
            '<div style="display:flex;gap:9px;align-items:center;flex-wrap:wrap;'
            'margin:12px 0">' + "".join(cards) + "</div>"
        )
    )


def show_roles(rows: Sequence[Tuple[str, str, str]]) -> None:
    """Render agent or component responsibilities as a compact table."""
    rendered = []
    for name, responsibility, role in rows:
        _, accent = _COLORS.get(role, _COLORS["default"])
        rendered.append(
            "<tr>"
            f'<td><strong style="color:{accent}">{html.escape(name)}</strong></td>'
            f"<td>{html.escape(responsibility)}</td>"
            f"<td><code>{html.escape(role)}</code></td>"
            "</tr>"
        )
    display(
        HTML(
            '<table style="border-collapse:collapse;width:100%;margin:10px 0">'
            "<thead><tr><th>Component</th><th>Responsibility</th><th>Role</th>"
            "</tr></thead><tbody>" + "".join(rendered) + "</tbody></table>"
        )
    )


def stage(actor: str, action: str, detail: str = "", spore: Any = None) -> None:
    """Record one observable execution stage."""
    _EVENTS.append(
        {
            "ms": round((time.perf_counter() - _STARTED) * 1000, 1),
            "actor": actor,
            "action": action,
            "detail": detail,
            "spore_id": getattr(spore, "id", "") if spore else "",
        }
    )


def get_events() -> List[Dict[str, Any]]:
    """Return a safe copy of captured notebook events."""
    return [dict(event) for event in _EVENTS]


def show_timeline(events: Iterable[Mapping[str, Any]] | None = None) -> None:
    """Render recorded execution stages in chronological order."""
    selected = list(_EVENTS if events is None else events)
    rows = []
    for item in selected:
        rows.append(
            "<tr>"
            f"<td>{float(item['ms']):.1f}</td>"
            f"<td><strong>{html.escape(str(item['actor']))}</strong></td>"
            f"<td>{html.escape(str(item['action']))}</td>"
            f"<td>{html.escape(str(item['detail']))}</td>"
            f"<td><code>{html.escape(str(item['spore_id'])[:12])}</code></td>"
            "</tr>"
        )
    display(
        HTML(
            '<table style="border-collapse:collapse;width:100%;margin:10px 0">'
            "<thead><tr><th>ms</th><th>Actor</th><th>Stage</th>"
            "<th>Detail</th><th>Spore</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    )


def show_json(value: Any, label: str = "Runtime state", *, role: str = "reef") -> None:
    """Render JSON-safe runtime state."""
    background, accent = _COLORS.get(role, _COLORS["default"])
    rendered = html.escape(json.dumps(value, indent=2, sort_keys=True, default=str))
    display(
        HTML(
            f'<div style="border-left:4px solid {accent};background:{background};'
            'padding:10px 14px;border-radius:8px;margin:10px 0">'
            f'<strong style="color:{accent}">{html.escape(label)}</strong>'
            f'<pre style="white-space:pre-wrap;margin-bottom:0">{rendered}</pre>'
            "</div>"
        )
    )


def show_spore(spore: Any, label: str = "Spore on the Reef") -> None:
    """Render a Spore's actual serialized wire-safe fields."""
    show_json(json.loads(spore.to_json()), label, role="spore")


def require_env(*names: str) -> Dict[str, str]:
    """Return required environment values or fail with a useful action message."""
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required notebook configuration: {joined}. "
            "Set these values before running this live or service lesson."
        )
    return {name: os.environ[name] for name in names}


def find_example_asset(relative: str | Path) -> Path:
    """Find a copied certification asset in local or exact-wheel execution."""
    requested = Path(relative)
    for root in (Path.cwd(), *Path.cwd().parents):
        for candidate in (root / requested, root / "examples" / requested):
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"Could not locate example asset: {requested}")


__all__ = [
    "find_example_asset",
    "get_events",
    "require_env",
    "setup_case_study",
    "setup_notebook",
    "show_callout",
    "show_flow",
    "show_json",
    "show_roles",
    "show_spore",
    "show_timeline",
    "stage",
]
