"""Explicit application ownership for Praval runtimes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .core.agent import Agent
from .core.reef import Reef, get_reef
from .providers.registry import ProviderRegistry, get_provider_registry


class PravalApp:
    """Owns the core runtime objects for an isolated Praval application."""

    def __init__(
        self,
        *,
        reef: Optional[Reef] = None,
        provider_registry: Optional[ProviderRegistry] = None,
        use_global_reef: bool = False,
    ) -> None:
        self.reef = reef or (get_reef() if use_global_reef else Reef())
        self.provider_registry = provider_registry or get_provider_registry()
        self._agents: Dict[str, Agent] = {}
        self._closed = False

    def create_agent(self, name: str, **kwargs: Any) -> Agent:
        """Create and retain an agent owned by this app."""
        if self._closed:
            raise RuntimeError("PravalApp is closed")
        agent = Agent(name, **kwargs)
        self._agents[name] = agent
        return agent

    def register_agent(self, agent: Agent) -> Agent:
        """Register an externally-created agent with this app."""
        if self._closed:
            raise RuntimeError("PravalApp is closed")
        self._agents[agent.name] = agent
        return agent

    def close(self) -> None:
        """Close all owned agents and the owned Reef when possible."""
        if self._closed:
            return
        self._closed = True
        for agent in list(self._agents.values()):
            agent.close()
        self._agents.clear()
        try:
            self.reef.shutdown()
        except Exception:
            pass

    def __enter__(self) -> "PravalApp":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


_default_app: Optional[PravalApp] = None


def get_default_app() -> PravalApp:
    """Return the default app that backs compatibility shims."""
    global _default_app
    if _default_app is None:
        _default_app = PravalApp(use_global_reef=True)
    return _default_app


def reset_default_app() -> PravalApp:
    """Reset the default app for tests."""
    global _default_app
    if _default_app is not None:
        _default_app.close()
    _default_app = PravalApp(use_global_reef=True)
    return _default_app
