"""
Episodic memory for Praval agents - conversation history and experiences

This manages:
- Conversation turns and dialogue history
- Agent interaction sequences
- Temporal event chains
- Experience-based learning patterns
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult
from .long_term_memory import LongTermMemory
from .short_term_memory import ShortTermMemory


class EpisodicMemory:
    """
    Manages episodic memories - experiences and conversations over time
    
    Features:
    - Conversation turn tracking
    - Experience sequencing
    - Temporal relationship modeling
    - Context window management
    """
    
    def __init__(self, 
                 long_term_memory: LongTermMemory,
                 short_term_memory: ShortTermMemory,
                 conversation_window: int = 50,
                 episode_lifetime_days: int = 30):
        """
        Initialize episodic memory
        
        Args:
            long_term_memory: Long-term memory backend
            short_term_memory: Short-term memory backend
            conversation_window: Number of conversation turns to keep in context
            episode_lifetime_days: How long to keep episodes before archiving
        """
        self.long_term_memory = long_term_memory
        self.short_term_memory = short_term_memory
        self.conversation_window = conversation_window
        self.episode_lifetime_days = episode_lifetime_days
    
    def store_conversation_turn(self,
                              agent_id: str,
                              user_message: str,
                              agent_response: str,
                              context: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a conversation turn as an episodic memory
        
        Args:
            agent_id: The agent involved in the conversation
            user_message: The user's message
            agent_response: The agent's response
            context: Additional context information
            
        Returns:
            The memory ID
        """
        # Create episodic memory entry
        conversation_content = {
            "user_message": user_message,
            "agent_response": agent_response,
            "turn_timestamp": datetime.now().isoformat(),
            "context": context or {}
        }
        
        memory = MemoryEntry(
            id=None,  # Will be generated
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content=f"User: {user_message}\nAgent: {agent_response}",
            metadata={
                "type": "conversation_turn",
                "conversation_data": conversation_content,
                "importance": self._calculate_conversation_importance(user_message, agent_response)
            }
        )
        
        # Store in short-term memory for immediate access
        self.short_term_memory.store(memory)
        
        # Store in long-term memory for persistence
        return self.long_term_memory.store(memory)
    
    def store_experience(self,
                        agent_id: str,
                        experience_type: str,
                        experience_data: Dict[str, Any],
                        outcome: str,
                        success: bool = True) -> str:
        """
        Store an experience or learning episode
        
        Args:
            agent_id: The agent that had the experience
            experience_type: Type of experience (e.g., "task_completion", "problem_solving")
            experience_data: Data about the experience
            outcome: The result or outcome
            success: Whether the experience was successful
            
        Returns:
            The memory ID
        """
        experience_content = f"{experience_type}: {outcome}"
        
        memory = MemoryEntry(
            id=None,
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content=experience_content,
            metadata={
                "type": "experience",
                "experience_type": experience_type,
                "experience_data": experience_data,
                "outcome": outcome,
                "success": success,
                "importance": 0.8 if success else 0.6  # Successful experiences are more important
            }
        )
        
        # Store in both memory systems
        self.short_term_memory.store(memory)
        return self.long_term_memory.store(memory)
    
    def get_conversation_context(self,
                               agent_id: str,
                               turns: Optional[int] = None) -> List[MemoryEntry]:
        """
        Get recent conversation context for an agent
        
        Args:
            agent_id: The agent to get context for
            turns: Number of conversation turns (default: conversation_window)
            
        Returns:
            List of recent conversation memories
        """
        if turns is None:
            turns = self.conversation_window
        
        # Try short-term memory first for recent conversations
        recent_memories = self.short_term_memory.get_recent(agent_id=agent_id, limit=turns * 2)
        conversation_memories = [
            m for m in recent_memories 
            if m.memory_type == MemoryType.EPISODIC and 
               m.metadata.get("type") == "conversation_turn"
        ]
        
        if len(conversation_memories) >= turns:
            return conversation_memories[:turns]
        
        # Fallback to long-term memory if needed
        query = MemoryQuery(
            query_text="conversation",
            memory_types=[MemoryType.EPISODIC],
            agent_id=agent_id,
            limit=turns
        )
        
        search_result = self.long_term_memory.search(query)
        lt_conversations = [
            m for m in search_result.entries
            if m.metadata.get("type") == "conversation_turn"
        ]
        
        # Combine and deduplicate
        all_conversations = conversation_memories + lt_conversations
        seen_ids = set()
        unique_conversations = []
        
        for conv in all_conversations:
            if conv.id not in seen_ids:
                unique_conversations.append(conv)
                seen_ids.add(conv.id)
        
        # Sort by creation time (most recent first)
        unique_conversations.sort(key=lambda x: x.created_at, reverse=True)
        
        return unique_conversations[:turns]
    
    def get_similar_experiences(self,
                              agent_id: str,
                              experience_description: str,
                              limit: int = 5) -> MemorySearchResult:
        """
        Find similar past experiences for an agent
        
        Args:
            agent_id: The agent to search experiences for
            experience_description: Description of the current experience
            limit: Maximum number of similar experiences to return
            
        Returns:
            Search results with similar experiences
        """
        query = MemoryQuery(
            query_text=experience_description,
            memory_types=[MemoryType.EPISODIC],
            agent_id=agent_id,
            limit=limit,
            similarity_threshold=0.6
        )
        
        search_result = self.long_term_memory.search(query)
        
        # Filter for experiences only
        experience_entries = [
            entry for entry in search_result.entries
            if entry.metadata.get("type") == "experience"
        ]
        
        # Recalculate scores for filtered results
        experience_scores = [
            score for entry, score in zip(search_result.entries, search_result.scores)
            if entry.metadata.get("type") == "experience"
        ]
        
        return MemorySearchResult(
            entries=experience_entries,
            scores=experience_scores,
            query=query,
            total_found=len(experience_entries)
        )
    
    def get_episode_timeline(self,
                           agent_id: str,
                           start_time: datetime,
                           end_time: datetime) -> List[MemoryEntry]:
        """
        Get episodic memories within a time range
        
        Args:
            agent_id: The agent to get timeline for
            start_time: Start of the time range
            end_time: End of the time range
            
        Returns:
            List of episodic memories in chronological order
        """
        query = MemoryQuery(
            query_text="",  # Empty query to get all
            memory_types=[MemoryType.EPISODIC],
            agent_id=agent_id,
            limit=1000,  # Large limit to get all in range
            similarity_threshold=0.0,  # Include all
            temporal_filter={"after": start_time, "before": end_time}
        )
        
        search_result = self.long_term_memory.search(query)
        
        # Sort chronologically
        episodes = sorted(search_result.entries, key=lambda x: x.created_at)
        
        return episodes
    
    def archive_old_episodes(self, cutoff_days: Optional[int] = None):
        """
        Archive old episodic memories (implementation depends on requirements)
        
        Args:
            cutoff_days: Days after which to archive (default: episode_lifetime_days)
        """
        if cutoff_days is None:
            cutoff_days = self.episode_lifetime_days
        
        cutoff_date = datetime.now() - timedelta(days=cutoff_days)
        
        # For now, this is a placeholder
        # In a full implementation, you might:
        # 1. Export old episodes to cold storage
        # 2. Compress multiple episodes into summaries
        # 3. Update importance scores based on age
        
        # This would require additional Qdrant operations
        # and possibly integration with external storage
        pass
    
    def _calculate_conversation_importance(self, user_message: str, agent_response: str) -> float:
        """
        Calculate the importance score for a conversation turn
        
        Args:
            user_message: The user's message
            agent_response: The agent's response
            
        Returns:
            Importance score between 0.0 and 1.0
        """
        importance = 0.5  # Base importance
        
        # Longer conversations tend to be more important
        total_length = len(user_message) + len(agent_response)
        if total_length > 500:
            importance += 0.2
        elif total_length > 200:
            importance += 0.1
        
        # Look for keywords that might indicate important conversations
        important_keywords = [
            "problem", "error", "help", "learn", "remember", "important", 
            "critical", "urgent", "goal", "plan", "decision"
        ]
        
        combined_text = (user_message + " " + agent_response).lower()
        keyword_count = sum(1 for keyword in important_keywords if keyword in combined_text)
        importance += min(keyword_count * 0.1, 0.3)
        
        return min(importance, 1.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get episodic memory statistics"""
        # This would require custom queries to Qdrant
        # For now, return basic info
        return {
            "conversation_window": self.conversation_window,
            "episode_lifetime_days": self.episode_lifetime_days,
            "backend": "long_term_memory + short_term_memory"
        }