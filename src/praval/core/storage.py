"""
State storage functionality for persistent agent conversations.

Provides simple file-based storage for conversation history with automatic
directory management and JSON serialization.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from .exceptions import StateError


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
            file_path = self.storage_dir / f"{agent_name}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(conversation_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise StateError(f"Failed to save state for agent '{agent_name}': {str(e)}") from e
    
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
                
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise StateError(f"Corrupted state file for agent '{agent_name}': {str(e)}") from e
        except Exception as e:
            raise StateError(f"Failed to load state for agent '{agent_name}': {str(e)}") from e
    
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
            raise StateError(f"Failed to delete state for agent '{agent_name}': {str(e)}") from e
    
    def list_agents(self) -> List[str]:
        """
        List all agents with stored state.
        
        Returns:
            List of agent names with stored state
        """
        try:
            return [
                f.stem for f in self.storage_dir.glob("*.json")
                if f.is_file()
            ]
        except Exception as e:
            raise StateError(f"Failed to list stored agents: {str(e)}") from e