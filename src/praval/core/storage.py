"""
State storage functionality for persistent agent conversations.

Provides simple file-based storage for conversation history with automatic
directory management and JSON serialization.
"""

import contextlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .exceptions import StateError


def _json_default(value: Any) -> Any:
    """Serialise pydantic models (such as ContentPart) stored in history."""
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(exclude_none=True)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class StateStorage:
    """
    Simple file-based storage for agent conversation state.

    Stores conversation history as JSON files in a local directory,
    with one file per agent identified by agent name.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize state storage.

        Args:
            storage_dir: Directory to store state files. Defaults to ~/.praval/state
        """
        if storage_dir is None:
            storage_dir = os.path.expanduser("~/.praval/state")

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, agent_name: str, conversation_history: List[Dict[str, str]]) -> None:
        """
        Save conversation history for an agent.

        Args:
            agent_name: Unique identifier for the agent
            conversation_history: List of conversation messages

        Raises:
            StateError: If saving fails
        """
        try:
            # Serialise before opening: a failure must not truncate the
            # previous state. Multimodal turns hold ContentPart models.
            payload = json.dumps(
                conversation_history,
                indent=2,
                ensure_ascii=False,
                default=_json_default,
            )
            file_path = self.storage_dir / f"{agent_name}.json"
            # Write a private temporary file and rename it over the state
            # file, so a concurrent reader or writer never sees a partial file.
            temp_path = file_path.with_name(f".{file_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                with open(temp_path, "x", encoding="utf-8") as f:
                    f.write(payload)
                os.replace(temp_path, file_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    temp_path.unlink()
                raise
        except Exception as e:
            raise StateError(
                f"Failed to save state for agent '{agent_name}': {str(e)}"
            ) from e

    def load(self, agent_name: str) -> Optional[List[Dict[str, str]]]:
        """
        Load conversation history for an agent.

        Args:
            agent_name: Unique identifier for the agent

        Returns:
            Conversation history if found, None otherwise

        Raises:
            StateError: If loading fails due to file corruption
        """
        try:
            file_path = self.storage_dir / f"{agent_name}.json"
            if not file_path.exists():
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                return cast(Optional[List[Dict[str, str]]], json.load(f))
        except json.JSONDecodeError as e:
            raise StateError(
                f"Corrupted state file for agent '{agent_name}': {str(e)}"
            ) from e
        except Exception as e:
            raise StateError(
                f"Failed to load state for agent '{agent_name}': {str(e)}"
            ) from e

    def delete(self, agent_name: str) -> bool:
        """
        Delete stored state for an agent.

        Args:
            agent_name: Unique identifier for the agent

        Returns:
            True if state was deleted, False if no state existed

        Raises:
            StateError: If deletion fails
        """
        try:
            file_path = self.storage_dir / f"{agent_name}.json"
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            raise StateError(
                f"Failed to delete state for agent '{agent_name}': {str(e)}"
            ) from e

    def list_agents(self) -> List[str]:
        """
        List all agents with stored state.

        Returns:
            List of agent names with stored state
        """
        try:
            return [f.stem for f in self.storage_dir.glob("*.json") if f.is_file()]
        except Exception as e:
            raise StateError(f"Failed to list stored agents: {str(e)}") from e
