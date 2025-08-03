"""
Tests for state storage functionality.

Tests the conversation history persistence with file-based storage
including error handling and edge cases.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from praval.core.storage import StateStorage
from praval.core.exceptions import StateError


class TestStateStorage:
    """Test StateStorage class functionality."""
    
    def setup_method(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = StateStorage(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_storage_directory_creation(self):
        """Test that storage directory is created automatically."""
        new_temp_dir = Path(self.temp_dir) / "new_storage"
        storage = StateStorage(str(new_temp_dir))
        
        assert new_temp_dir.exists()
        assert new_temp_dir.is_dir()
    
    def test_default_storage_directory(self):
        """Test that default storage directory is set correctly."""
        storage = StateStorage()
        expected_path = Path.home() / ".praval" / "state"
        
        assert storage.storage_dir == expected_path
    
    def test_save_conversation_history(self):
        """Test saving conversation history to file."""
        agent_name = "test_agent"
        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        self.storage.save(agent_name, conversation)
        
        # Verify file was created
        file_path = Path(self.temp_dir) / f"{agent_name}.json"
        assert file_path.exists()
        
        # Verify content is correct
        with open(file_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data == conversation
    
    def test_load_conversation_history(self):
        """Test loading conversation history from file."""
        agent_name = "test_agent"
        conversation = [
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"}
        ]
        
        # Save first
        self.storage.save(agent_name, conversation)
        
        # Load and verify
        loaded_conversation = self.storage.load(agent_name)
        assert loaded_conversation == conversation
    
    def test_load_nonexistent_agent(self):
        """Test loading conversation for non-existent agent returns None."""
        result = self.storage.load("nonexistent_agent")
        assert result is None
    
    def test_save_overwrites_existing_file(self):
        """Test that saving overwrites existing conversation history."""
        agent_name = "test_agent"
        
        # Save first conversation
        first_conversation = [{"role": "user", "content": "First message"}]
        self.storage.save(agent_name, first_conversation)
        
        # Save second conversation
        second_conversation = [{"role": "user", "content": "Second message"}]
        self.storage.save(agent_name, second_conversation)
        
        # Verify only second conversation is stored
        loaded_conversation = self.storage.load(agent_name)
        assert loaded_conversation == second_conversation
        assert loaded_conversation != first_conversation
    
    def test_save_with_unicode_content(self):
        """Test saving conversation with unicode characters."""
        agent_name = "unicode_agent"
        conversation = [
            {"role": "user", "content": "こんにちは"},
            {"role": "assistant", "content": "Hello! 🌟 How can I help you?"}
        ]
        
        self.storage.save(agent_name, conversation)
        loaded_conversation = self.storage.load(agent_name)
        
        assert loaded_conversation == conversation
    
    def test_delete_agent_state(self):
        """Test deleting stored state for an agent."""
        agent_name = "test_agent"
        conversation = [{"role": "user", "content": "Test message"}]
        
        # Save conversation
        self.storage.save(agent_name, conversation)
        assert self.storage.load(agent_name) is not None
        
        # Delete state
        result = self.storage.delete(agent_name)
        assert result is True
        
        # Verify state is deleted
        assert self.storage.load(agent_name) is None
    
    def test_delete_nonexistent_agent(self):
        """Test deleting state for non-existent agent returns False."""
        result = self.storage.delete("nonexistent_agent")
        assert result is False
    
    def test_list_agents(self):
        """Test listing all agents with stored state."""
        # Save state for multiple agents
        agents_and_conversations = {
            "agent1": [{"role": "user", "content": "Message 1"}],
            "agent2": [{"role": "user", "content": "Message 2"}],
            "agent3": [{"role": "user", "content": "Message 3"}]
        }
        
        for agent_name, conversation in agents_and_conversations.items():
            self.storage.save(agent_name, conversation)
        
        # List agents
        agent_list = self.storage.list_agents()
        
        assert len(agent_list) == 3
        assert set(agent_list) == {"agent1", "agent2", "agent3"}
    
    def test_list_agents_empty_directory(self):
        """Test listing agents when no state files exist."""
        agent_list = self.storage.list_agents()
        assert agent_list == []
    
    def test_save_error_handling(self):
        """Test error handling when save operation fails."""
        # Create storage with invalid directory permissions
        invalid_dir = Path(self.temp_dir) / "invalid"
        invalid_dir.mkdir()
        invalid_dir.chmod(0o444)  # Read-only
        
        storage = StateStorage(str(invalid_dir))
        
        with pytest.raises(StateError, match="Failed to save state"):
            storage.save("test_agent", [{"role": "user", "content": "test"}])
    
    def test_load_corrupted_file_error_handling(self):
        """Test error handling when loading corrupted JSON file."""
        agent_name = "corrupted_agent"
        file_path = Path(self.temp_dir) / f"{agent_name}.json"
        
        # Create corrupted JSON file
        with open(file_path, 'w') as f:
            f.write("invalid json content {")
        
        with pytest.raises(StateError, match="Corrupted state file"):
            self.storage.load(agent_name)
    
    def test_empty_conversation_history(self):
        """Test saving and loading empty conversation history."""
        agent_name = "empty_agent"
        empty_conversation = []
        
        self.storage.save(agent_name, empty_conversation)
        loaded_conversation = self.storage.load(agent_name)
        
        assert loaded_conversation == empty_conversation
        assert loaded_conversation == []
    
    def test_large_conversation_history(self):
        """Test handling large conversation histories."""
        agent_name = "large_agent"
        
        # Create a large conversation history
        large_conversation = []
        for i in range(1000):
            large_conversation.extend([
                {"role": "user", "content": f"User message {i}"},
                {"role": "assistant", "content": f"Assistant response {i}"}
            ])
        
        self.storage.save(agent_name, large_conversation)
        loaded_conversation = self.storage.load(agent_name)
        
        assert len(loaded_conversation) == 2000
        assert loaded_conversation == large_conversation
    
    def test_agent_name_with_special_characters(self):
        """Test agent names with special characters."""
        # Note: We only test valid filename characters
        agent_name = "agent_with-special.chars_123"
        conversation = [{"role": "user", "content": "Test"}]
        
        self.storage.save(agent_name, conversation)
        loaded_conversation = self.storage.load(agent_name)
        
        assert loaded_conversation == conversation