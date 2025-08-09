"""
Memory types and data structures for Praval agents
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid


class MemoryType(Enum):
    """Types of memory entries"""
    SHORT_TERM = "short_term"          # Working memory, temporary
    EPISODIC = "episodic"              # Conversation history, experiences
    SEMANTIC = "semantic"              # Knowledge, facts, concepts
    PROCEDURAL = "procedural"          # Skills, how-to knowledge
    EMOTIONAL = "emotional"            # Emotional context and associations


@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str
    agent_id: str
    memory_type: MemoryType
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime = None
    accessed_at: datetime = None
    access_count: int = 0
    importance: float = 0.5  # 0.0 to 1.0, for memory retention
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.accessed_at is None:
            self.accessed_at = self.created_at
            
    def mark_accessed(self):
        """Mark this memory as accessed"""
        self.accessed_at = datetime.now()
        self.access_count += 1
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'memory_type': self.memory_type.value,
            'content': self.content,
            'metadata': self.metadata,
            'embedding': self.embedding,
            'created_at': self.created_at.isoformat(),
            'accessed_at': self.accessed_at.isoformat(),
            'access_count': self.access_count,
            'importance': self.importance
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            agent_id=data['agent_id'],
            memory_type=MemoryType(data['memory_type']),
            content=data['content'],
            metadata=data['metadata'],
            embedding=data.get('embedding'),
            created_at=datetime.fromisoformat(data['created_at']),
            accessed_at=datetime.fromisoformat(data['accessed_at']),
            access_count=data.get('access_count', 0),
            importance=data.get('importance', 0.5)
        )


@dataclass 
class MemoryQuery:
    """A memory search query"""
    query_text: str
    memory_types: List[MemoryType] = None
    agent_id: Optional[str] = None
    limit: int = 10
    similarity_threshold: float = 0.7
    include_metadata: bool = True
    temporal_filter: Optional[Dict[str, datetime]] = None  # e.g., {"after": datetime, "before": datetime}
    
    def __post_init__(self):
        if self.memory_types is None:
            self.memory_types = list(MemoryType)


@dataclass
class MemorySearchResult:
    """Result of a memory search"""
    entries: List[MemoryEntry]
    scores: List[float]
    query: MemoryQuery
    total_found: int
    
    def get_best_match(self) -> Optional[MemoryEntry]:
        """Get the best matching memory entry"""
        if self.entries:
            return self.entries[0]
        return None
    
    def get_above_threshold(self, threshold: float = 0.8) -> List[MemoryEntry]:
        """Get entries above similarity threshold"""
        return [
            entry for entry, score in zip(self.entries, self.scores) 
            if score >= threshold
        ]