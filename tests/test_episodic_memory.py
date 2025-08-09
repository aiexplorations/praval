"""
Comprehensive tests for Praval EpisodicMemory.

This module ensures the episodic memory system is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions, including conversation tracking and experience storage.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from praval.memory.episodic_memory import EpisodicMemory
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestEpisodicMemoryInitialization:
    """Test EpisodicMemory initialization with comprehensive coverage."""
    
    def test_episodic_memory_default_initialization(self):
        """Test episodic memory with default parameters."""
        mock_long_term = Mock()
        mock_short_term = Mock()
        
        memory = EpisodicMemory(mock_long_term, mock_short_term)
        
        assert memory.long_term_memory == mock_long_term
        assert memory.short_term_memory == mock_short_term
        assert memory.conversation_window == 50
        assert memory.episode_lifetime_days == 30
    
    def test_episodic_memory_custom_initialization(self):
        """Test episodic memory with custom parameters."""
        mock_long_term = Mock()
        mock_short_term = Mock()
        
        memory = EpisodicMemory(
            mock_long_term, 
            mock_short_term,
            conversation_window=25,
            episode_lifetime_days=14
        )
        
        assert memory.conversation_window == 25
        assert memory.episode_lifetime_days == 14


class TestEpisodicMemoryConversationStorage:
    """Test conversation turn storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def test_store_conversation_turn_basic(self):
        """Test basic conversation turn storage."""
        self.mock_long_term.store.return_value = "conversation_id_123"
        
        result_id = self.memory.store_conversation_turn(
            agent_id="conversation_agent",
            user_message="Hello, how are you?",
            agent_response="I'm doing well, thank you!"
        )
        
        assert result_id == "conversation_id_123"
        
        # Verify short-term memory storage
        self.mock_short_term.store.assert_called_once()
        st_call_args = self.mock_short_term.store.call_args[0][0]
        assert st_call_args.agent_id == "conversation_agent"
        assert st_call_args.memory_type == MemoryType.EPISODIC
        assert "Hello, how are you?" in st_call_args.content
        assert "I'm doing well, thank you!" in st_call_args.content
        assert st_call_args.metadata["type"] == "conversation_turn"
        
        # Verify long-term memory storage
        self.mock_long_term.store.assert_called_once()
        lt_call_args = self.mock_long_term.store.call_args[0][0]
        assert lt_call_args.agent_id == "conversation_agent"
        assert lt_call_args.memory_type == MemoryType.EPISODIC
    
    def test_store_conversation_turn_with_context(self):
        """Test conversation turn storage with context."""
        self.mock_long_term.store.return_value = "context_conversation_123"
        
        context = {
            "session_id": "session_456",
            "channel": "web_chat",
            "user_id": "user_789"
        }
        
        result_id = self.memory.store_conversation_turn(
            agent_id="context_agent",
            user_message="What's the weather like?",
            agent_response="I don't have access to weather data.",
            context=context
        )
        
        assert result_id == "context_conversation_123"
        
        # Verify context is stored in metadata
        call_args = self.mock_long_term.store.call_args[0][0]
        conversation_data = call_args.metadata["conversation_data"]
        assert conversation_data["context"] == context
        assert conversation_data["user_message"] == "What's the weather like?"
        assert conversation_data["agent_response"] == "I don't have access to weather data."
        assert "turn_timestamp" in conversation_data
    
    def test_store_conversation_turn_without_context(self):
        """Test conversation turn storage without context."""
        self.mock_long_term.store.return_value = "no_context_123"
        
        self.memory.store_conversation_turn(
            agent_id="no_context_agent",
            user_message="Simple message",
            agent_response="Simple response"
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        conversation_data = call_args.metadata["conversation_data"]
        assert conversation_data["context"] == {}
    
    def test_conversation_importance_calculation_basic(self):
        """Test conversation importance calculation with basic messages."""
        self.mock_long_term.store.return_value = "importance_test"
        
        # Short, simple conversation
        self.memory.store_conversation_turn(
            agent_id="importance_agent",
            user_message="Hi",
            agent_response="Hello"
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should be base importance (0.5) with no modifiers
        assert importance == 0.5
    
    def test_conversation_importance_calculation_length_bonus(self):
        """Test conversation importance calculation with length bonus."""
        self.mock_long_term.store.return_value = "length_test"
        
        # Long conversation should get importance bonus
        long_user_message = "This is a very long user message that contains detailed information and goes on for quite a while, providing extensive context and multiple questions that require thoughtful responses from the AI assistant."
        long_agent_response = "Thank you for your detailed question. I'll do my best to provide a comprehensive response that addresses all of your concerns. Let me break this down into several parts to ensure I cover everything thoroughly..."
        
        self.memory.store_conversation_turn(
            agent_id="length_agent",
            user_message=long_user_message,
            agent_response=long_agent_response
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should have length bonus (0.5 + 0.2 = 0.7)
        assert importance == 0.7
    
    def test_conversation_importance_calculation_keyword_bonus(self):
        """Test conversation importance calculation with keyword bonus."""
        self.mock_long_term.store.return_value = "keyword_test"
        
        # Conversation with important keywords
        self.memory.store_conversation_turn(
            agent_id="keyword_agent",
            user_message="I have a critical problem with my code that's urgent",
            agent_response="I'll help you learn to solve this important error"
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should have keyword bonus (0.5 + keyword bonuses)
        assert importance > 0.5
        assert importance <= 1.0
    
    def test_conversation_importance_calculation_max_capped(self):
        """Test that conversation importance is capped at 1.0."""
        self.mock_long_term.store.return_value = "capped_test"
        
        # Very long conversation with many keywords
        very_long_message = ("This is an extremely long message " * 50) + " with critical urgent important problem error help learn remember goal plan decision"
        very_long_response = ("This is an extremely long response " * 50) + " addressing critical urgent important problem error help learn remember goal plan decision"
        
        self.memory.store_conversation_turn(
            agent_id="capped_agent",
            user_message=very_long_message,
            agent_response=very_long_response
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should be capped at 1.0
        assert importance == 1.0


class TestEpisodicMemoryExperienceStorage:
    """Test experience storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def test_store_experience_successful(self):
        """Test storing a successful experience."""
        self.mock_long_term.store.return_value = "success_experience_123"
        
        experience_data = {
            "task": "code_generation",
            "input": "Create a sorting function",
            "approach": "quicksort_implementation"
        }
        
        result_id = self.memory.store_experience(
            agent_id="experience_agent",
            experience_type="task_completion",
            experience_data=experience_data,
            outcome="Successfully generated and tested sorting function",
            success=True
        )
        
        assert result_id == "success_experience_123"
        
        # Verify short-term memory storage
        self.mock_short_term.store.assert_called_once()
        st_call_args = self.mock_short_term.store.call_args[0][0]
        assert st_call_args.memory_type == MemoryType.EPISODIC
        assert st_call_args.metadata["type"] == "experience"
        assert st_call_args.metadata["success"] is True
        assert st_call_args.metadata["importance"] == 0.8  # Successful experience
        
        # Verify long-term memory storage
        self.mock_long_term.store.assert_called_once()
        lt_call_args = self.mock_long_term.store.call_args[0][0]
        assert lt_call_args.content == "task_completion: Successfully generated and tested sorting function"
        assert lt_call_args.metadata["experience_type"] == "task_completion"
        assert lt_call_args.metadata["experience_data"] == experience_data
        assert lt_call_args.metadata["outcome"] == "Successfully generated and tested sorting function"
    
    def test_store_experience_failed(self):
        """Test storing a failed experience."""
        self.mock_long_term.store.return_value = "failed_experience_123"
        
        experience_data = {
            "task": "api_call",
            "endpoint": "/users/create",
            "error": "validation_failed"
        }
        
        result_id = self.memory.store_experience(
            agent_id="fail_agent",
            experience_type="api_interaction",
            experience_data=experience_data,
            outcome="Request failed due to validation errors",
            success=False
        )
        
        assert result_id == "failed_experience_123"
        
        # Verify importance is lower for failed experiences
        call_args = self.mock_long_term.store.call_args[0][0]
        assert call_args.metadata["success"] is False
        assert call_args.metadata["importance"] == 0.6  # Failed experience
    
    def test_store_experience_default_success(self):
        """Test storing experience with default success value."""
        self.mock_long_term.store.return_value = "default_success_123"
        
        self.memory.store_experience(
            agent_id="default_agent",
            experience_type="learning",
            experience_data={"concept": "machine_learning"},
            outcome="Learned about neural networks"
            # success parameter not provided, should default to True
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        assert call_args.metadata["success"] is True
        assert call_args.metadata["importance"] == 0.8


class TestEpisodicMemoryConversationContext:
    """Test conversation context retrieval."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def create_conversation_memory(self, memory_id: str, agent_id: str, user_msg: str, agent_msg: str):
        """Helper to create conversation memory entry."""
        return MemoryEntry(
            id=memory_id,
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content=f"User: {user_msg}\nAgent: {agent_msg}",
            metadata={
                "type": "conversation_turn",
                "conversation_data": {
                    "user_message": user_msg,
                    "agent_response": agent_msg,
                    "turn_timestamp": datetime.now().isoformat(),
                    "context": {}
                }
            }
        )
    
    def test_get_conversation_context_from_short_term(self):
        """Test getting conversation context from short-term memory."""
        # Mock short-term memory to return conversation memories
        conv_memories = [
            self.create_conversation_memory("conv_3", "context_agent", "How are you?", "I'm fine"),
            self.create_conversation_memory("conv_2", "context_agent", "What's up?", "Not much"),
            self.create_conversation_memory("conv_1", "context_agent", "Hello", "Hi there"),
        ]
        
        # Add some non-conversation memories to test filtering
        non_conv_memory = MemoryEntry(
            id="non_conv",
            agent_id="context_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Some semantic content",
            metadata={"type": "knowledge"}
        )
        
        all_memories = conv_memories + [non_conv_memory]
        self.mock_short_term.get_recent.return_value = all_memories
        
        result = self.memory.get_conversation_context("context_agent", turns=2)
        
        # Should return only conversation memories, limited to requested turns
        assert len(result) == 2
        assert all(m.metadata.get("type") == "conversation_turn" for m in result)
        assert result[0].id == "conv_3"
        assert result[1].id == "conv_2"
        
        # Verify short-term memory was queried correctly
        self.mock_short_term.get_recent.assert_called_once_with(agent_id="context_agent", limit=4)  # turns * 2
    
    def test_get_conversation_context_fallback_to_long_term(self):
        """Test fallback to long-term memory when short-term doesn't have enough."""
        # Short-term has only 1 conversation
        short_term_conv = [
            self.create_conversation_memory("st_conv_1", "fallback_agent", "Recent msg", "Recent response")
        ]
        self.mock_short_term.get_recent.return_value = short_term_conv
        
        # Long-term has additional conversations
        long_term_conversations = [
            self.create_conversation_memory("lt_conv_2", "fallback_agent", "Old msg 2", "Old response 2"),
            self.create_conversation_memory("lt_conv_1", "fallback_agent", "Old msg 1", "Old response 1"),
        ]
        
        mock_search_result = MemorySearchResult(
            entries=long_term_conversations,
            scores=[0.9, 0.8],
            query=Mock(),
            total_found=2
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_conversation_context("fallback_agent", turns=3)
        
        # Should combine short-term and long-term results
        assert len(result) <= 3
        assert "st_conv_1" in [m.id for m in result]
        
        # Verify long-term search was called
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == "conversation"
        assert search_call_args.memory_types == [MemoryType.EPISODIC]
        assert search_call_args.agent_id == "fallback_agent"
    
    def test_get_conversation_context_deduplication(self):
        """Test that duplicate conversations are deduplicated."""
        # Same conversation in both short-term and long-term
        duplicate_conv = self.create_conversation_memory("dup_conv", "dup_agent", "Duplicate", "Response")
        
        self.mock_short_term.get_recent.return_value = [duplicate_conv]
        
        mock_search_result = MemorySearchResult(
            entries=[duplicate_conv],  # Same conversation
            scores=[0.9],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_conversation_context("dup_agent", turns=5)
        
        # Should only return one instance of the duplicate conversation
        assert len(result) == 1
        assert result[0].id == "dup_conv"
    
    def test_get_conversation_context_chronological_ordering(self):
        """Test that conversations are ordered chronologically (most recent first)."""
        # Create conversations with different timestamps
        old_time = datetime.now() - timedelta(hours=2)
        recent_time = datetime.now() - timedelta(minutes=30)
        
        old_conv = self.create_conversation_memory("old_conv", "chrono_agent", "Old", "Old response")
        old_conv.created_at = old_time
        
        recent_conv = self.create_conversation_memory("recent_conv", "chrono_agent", "Recent", "Recent response")
        recent_conv.created_at = recent_time
        
        # Return in wrong order from memory
        self.mock_short_term.get_recent.return_value = [old_conv, recent_conv]
        
        result = self.memory.get_conversation_context("chrono_agent", turns=2)
        
        # Should be sorted with most recent first
        assert result[0].id == "recent_conv"
        assert result[1].id == "old_conv"
    
    def test_get_conversation_context_default_window(self):
        """Test getting conversation context with default window size."""
        self.mock_short_term.get_recent.return_value = []
        self.mock_long_term.search.return_value = MemorySearchResult(entries=[], scores=[], query=Mock(), total_found=0)
        
        self.memory.get_conversation_context("default_agent")
        
        # Should use conversation_window as default (50 turns)
        self.mock_short_term.get_recent.assert_called_once_with(agent_id="default_agent", limit=100)  # 50 * 2


class TestEpisodicMemoryExperienceRetrieval:
    """Test experience retrieval functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def create_experience_memory(self, memory_id: str, agent_id: str, exp_type: str, outcome: str):
        """Helper to create experience memory entry."""
        return MemoryEntry(
            id=memory_id,
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content=f"{exp_type}: {outcome}",
            metadata={
                "type": "experience",
                "experience_type": exp_type,
                "outcome": outcome,
                "success": True
            }
        )
    
    def test_get_similar_experiences_basic(self):
        """Test getting similar experiences."""
        # Mock search results with mixed experience and conversation memories
        experience_memories = [
            self.create_experience_memory("exp_1", "exp_agent", "problem_solving", "Solved algorithm issue"),
            self.create_experience_memory("exp_2", "exp_agent", "code_review", "Found performance bug"),
        ]
        
        # Add a conversation memory that should be filtered out
        conversation_memory = MemoryEntry(
            id="conv_1",
            agent_id="exp_agent",
            memory_type=MemoryType.EPISODIC,
            content="User: Hello\nAgent: Hi",
            metadata={"type": "conversation_turn"}
        )
        
        all_memories = experience_memories + [conversation_memory]
        
        mock_search_result = MemorySearchResult(
            entries=all_memories,
            scores=[0.9, 0.8, 0.7],
            query=Mock(),
            total_found=3
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_similar_experiences(
            agent_id="exp_agent",
            experience_description="debugging algorithm problem",
            limit=5
        )
        
        # Should only return experience memories
        assert len(result.entries) == 2
        assert all(entry.metadata.get("type") == "experience" for entry in result.entries)
        assert result.entries[0].id == "exp_1"
        assert result.entries[1].id == "exp_2"
        
        # Scores should be recalculated for filtered results
        assert len(result.scores) == 2
        assert result.scores[0] == 0.9
        assert result.scores[1] == 0.8
        
        # Verify search was called correctly
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == "debugging algorithm problem"
        assert search_call_args.memory_types == [MemoryType.EPISODIC]
        assert search_call_args.agent_id == "exp_agent"
        assert search_call_args.limit == 5
        assert search_call_args.similarity_threshold == 0.6
    
    def test_get_similar_experiences_no_experiences_found(self):
        """Test getting similar experiences when none are found."""
        # Only conversation memories in results
        conversation_memory = MemoryEntry(
            id="conv_only",
            agent_id="no_exp_agent",
            memory_type=MemoryType.EPISODIC,
            content="User: Hello\nAgent: Hi",
            metadata={"type": "conversation_turn"}
        )
        
        mock_search_result = MemorySearchResult(
            entries=[conversation_memory],
            scores=[0.8],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_similar_experiences(
            agent_id="no_exp_agent",
            experience_description="looking for experiences",
            limit=3
        )
        
        # Should return empty results
        assert len(result.entries) == 0
        assert len(result.scores) == 0
        assert result.total_found == 0
    
    def test_get_similar_experiences_empty_search_results(self):
        """Test getting similar experiences when search returns nothing."""
        mock_search_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=Mock(),
            total_found=0
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_similar_experiences(
            agent_id="empty_agent",
            experience_description="no similar experiences",
            limit=3
        )
        
        assert len(result.entries) == 0
        assert len(result.scores) == 0
        assert result.total_found == 0


class TestEpisodicMemoryTimelineRetrieval:
    """Test timeline-based memory retrieval."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def test_get_episode_timeline_basic(self):
        """Test getting episodic timeline for a time range."""
        start_time = datetime(2023, 1, 1, 9, 0, 0)
        end_time = datetime(2023, 1, 1, 17, 0, 0)
        
        # Create memories with different timestamps (not in chronological order)
        late_memory = MemoryEntry(
            id="late_episode",
            agent_id="timeline_agent",
            memory_type=MemoryType.EPISODIC,
            content="Late episode",
            metadata={},
            created_at=datetime(2023, 1, 1, 15, 0, 0)
        )
        
        early_memory = MemoryEntry(
            id="early_episode",
            agent_id="timeline_agent",
            memory_type=MemoryType.EPISODIC,
            content="Early episode",
            metadata={},
            created_at=datetime(2023, 1, 1, 10, 0, 0)
        )
        
        middle_memory = MemoryEntry(
            id="middle_episode",
            agent_id="timeline_agent",
            memory_type=MemoryType.EPISODIC,
            content="Middle episode",
            metadata={},
            created_at=datetime(2023, 1, 1, 12, 30, 0)
        )
        
        # Return memories in random order
        mock_search_result = MemorySearchResult(
            entries=[late_memory, early_memory, middle_memory],
            scores=[0.9, 0.8, 0.7],
            query=Mock(),
            total_found=3
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_episode_timeline(
            agent_id="timeline_agent",
            start_time=start_time,
            end_time=end_time
        )
        
        # Should return memories in chronological order
        assert len(result) == 3
        assert result[0].id == "early_episode"
        assert result[1].id == "middle_episode"
        assert result[2].id == "late_episode"
        
        # Verify search was called with correct parameters
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == ""
        assert search_call_args.memory_types == [MemoryType.EPISODIC]
        assert search_call_args.agent_id == "timeline_agent"
        assert search_call_args.limit == 1000
        assert search_call_args.similarity_threshold == 0.0
        assert search_call_args.temporal_filter == {"after": start_time, "before": end_time}
    
    def test_get_episode_timeline_empty_results(self):
        """Test getting timeline when no episodes exist in range."""
        start_time = datetime(2023, 1, 1, 9, 0, 0)
        end_time = datetime(2023, 1, 1, 17, 0, 0)
        
        mock_search_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=Mock(),
            total_found=0
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_episode_timeline(
            agent_id="empty_timeline_agent",
            start_time=start_time,
            end_time=end_time
        )
        
        assert len(result) == 0


class TestEpisodicMemoryArchiving:
    """Test memory archiving functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def test_archive_old_episodes_default_cutoff(self):
        """Test archiving with default cutoff days."""
        # This is currently a placeholder implementation
        # Test should pass without errors
        self.memory.archive_old_episodes()
        
        # No assertions needed as implementation is placeholder
        # In future, would verify archival operations
    
    def test_archive_old_episodes_custom_cutoff(self):
        """Test archiving with custom cutoff days."""
        # This is currently a placeholder implementation
        # Test should pass without errors
        self.memory.archive_old_episodes(cutoff_days=7)
        
        # No assertions needed as implementation is placeholder


class TestEpisodicMemoryStatistics:
    """Test memory statistics functionality."""
    
    def test_get_stats_basic(self):
        """Test getting episodic memory statistics."""
        mock_long_term = Mock()
        mock_short_term = Mock()
        
        memory = EpisodicMemory(
            mock_long_term, 
            mock_short_term,
            conversation_window=25,
            episode_lifetime_days=14
        )
        
        stats = memory.get_stats()
        
        expected = {
            "conversation_window": 25,
            "episode_lifetime_days": 14,
            "backend": "long_term_memory + short_term_memory"
        }
        
        assert stats == expected


class TestEpisodicMemoryIntegration:
    """Test integration scenarios for EpisodicMemory."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.mock_short_term = Mock()
        self.memory = EpisodicMemory(self.mock_long_term, self.mock_short_term)
    
    def test_conversation_and_experience_workflow(self):
        """Test complete workflow with conversations and experiences."""
        # Store conversation
        self.mock_long_term.store.return_value = "workflow_conv_123"
        conv_id = self.memory.store_conversation_turn(
            agent_id="workflow_agent",
            user_message="Can you help me debug this code?",
            agent_response="Sure, I'll help you find the issue."
        )
        
        # Store related experience
        self.mock_long_term.store.return_value = "workflow_exp_456"
        exp_id = self.memory.store_experience(
            agent_id="workflow_agent",
            experience_type="debugging_session",
            experience_data={"language": "python", "issue_type": "syntax_error"},
            outcome="Successfully identified and fixed syntax error",
            success=True
        )
        
        assert conv_id == "workflow_conv_123"
        assert exp_id == "workflow_exp_456"
        
        # Verify both were stored in short-term and long-term memory
        assert self.mock_short_term.store.call_count == 2
        assert self.mock_long_term.store.call_count == 2
    
    def test_importance_calculation_edge_cases(self):
        """Test importance calculation edge cases."""
        # Test with empty messages
        self.mock_long_term.store.return_value = "empty_test"
        
        self.memory.store_conversation_turn(
            agent_id="empty_agent",
            user_message="",
            agent_response=""
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should still have base importance
        assert importance == 0.5
    
    def test_memory_type_consistency(self):
        """Test that all episodic memories have correct type."""
        self.mock_long_term.store.return_value = "type_test"
        
        # Store conversation
        self.memory.store_conversation_turn(
            agent_id="type_agent",
            user_message="Test message",
            agent_response="Test response"
        )
        
        # Store experience
        self.memory.store_experience(
            agent_id="type_agent",
            experience_type="test_experience",
            experience_data={"test": True},
            outcome="Test outcome"
        )
        
        # Verify all stored memories are episodic type
        for call in self.mock_long_term.store.call_args_list:
            memory_entry = call[0][0]
            assert memory_entry.memory_type == MemoryType.EPISODIC
    
    def test_agent_id_consistency(self):
        """Test that agent IDs are preserved correctly."""
        self.mock_long_term.store.return_value = "agent_test"
        
        test_agent_id = "consistency_agent_123"
        
        self.memory.store_conversation_turn(
            agent_id=test_agent_id,
            user_message="Agent ID test",
            agent_response="Testing agent ID"
        )
        
        self.memory.store_experience(
            agent_id=test_agent_id,
            experience_type="id_test",
            experience_data={},
            outcome="Agent ID preserved"
        )
        
        # Verify agent ID is preserved in all calls
        for call in self.mock_long_term.store.call_args_list:
            memory_entry = call[0][0]
            assert memory_entry.agent_id == test_agent_id