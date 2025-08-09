"""
Semantic memory for Praval agents - knowledge, facts, and concepts

This manages:
- Factual knowledge storage
- Concept relationships
- Domain expertise
- Learned information persistence
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import json

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult
from .long_term_memory import LongTermMemory


class SemanticMemory:
    """
    Manages semantic memories - facts, concepts, and knowledge
    
    Features:
    - Factual knowledge storage
    - Concept relationship tracking
    - Knowledge validation and updating
    - Domain expertise building
    """
    
    def __init__(self, long_term_memory: LongTermMemory):
        """
        Initialize semantic memory
        
        Args:
            long_term_memory: Long-term memory backend for persistence
        """
        self.long_term_memory = long_term_memory
    
    def store_fact(self,
                   agent_id: str,
                   fact: str,
                   domain: str,
                   confidence: float = 1.0,
                   source: Optional[str] = None,
                   related_concepts: Optional[List[str]] = None) -> str:
        """
        Store a factual piece of knowledge
        
        Args:
            agent_id: The agent learning this fact
            fact: The factual statement
            domain: Domain or category of knowledge
            confidence: Confidence in this fact (0.0 to 1.0)
            source: Source of this information
            related_concepts: Related concepts or topics
            
        Returns:
            The memory ID
        """
        memory = MemoryEntry(
            id=None,
            agent_id=agent_id,
            memory_type=MemoryType.SEMANTIC,
            content=fact,
            metadata={
                "type": "fact",
                "domain": domain,
                "confidence": confidence,
                "source": source,
                "related_concepts": related_concepts or [],
                "importance": self._calculate_fact_importance(fact, domain, confidence)
            }
        )
        
        return self.long_term_memory.store(memory)
    
    def store_concept(self,
                     agent_id: str,
                     concept: str,
                     definition: str,
                     domain: str,
                     properties: Optional[Dict[str, Any]] = None,
                     relationships: Optional[Dict[str, List[str]]] = None) -> str:
        """
        Store a concept with its definition and relationships
        
        Args:
            agent_id: The agent learning this concept
            concept: The concept name
            definition: Definition of the concept
            domain: Domain or field of the concept
            properties: Properties or attributes of the concept
            relationships: Relationships to other concepts (e.g., {"is_a": ["category"], "relates_to": ["other_concepts"]})
            
        Returns:
            The memory ID
        """
        content = f"Concept: {concept}\nDefinition: {definition}"
        
        memory = MemoryEntry(
            id=None,
            agent_id=agent_id,
            memory_type=MemoryType.SEMANTIC,
            content=content,
            metadata={
                "type": "concept",
                "concept": concept,
                "definition": definition,
                "domain": domain,
                "properties": properties or {},
                "relationships": relationships or {},
                "importance": self._calculate_concept_importance(concept, definition, relationships)
            }
        )
        
        return self.long_term_memory.store(memory)
    
    def store_rule(self,
                   agent_id: str,
                   rule_name: str,
                   rule_description: str,
                   conditions: List[str],
                   actions: List[str],
                   domain: str,
                   confidence: float = 1.0) -> str:
        """
        Store a procedural rule or pattern
        
        Args:
            agent_id: The agent learning this rule
            rule_name: Name of the rule
            rule_description: Description of what the rule does
            conditions: Conditions when the rule applies
            actions: Actions to take when conditions are met
            domain: Domain of application
            confidence: Confidence in this rule
            
        Returns:
            The memory ID
        """
        content = f"Rule: {rule_name}\n{rule_description}"
        
        memory = MemoryEntry(
            id=None,
            agent_id=agent_id,
            memory_type=MemoryType.SEMANTIC,
            content=content,
            metadata={
                "type": "rule",
                "rule_name": rule_name,
                "rule_description": rule_description,
                "conditions": conditions,
                "actions": actions,
                "domain": domain,
                "confidence": confidence,
                "importance": 0.8  # Rules are generally important
            }
        )
        
        return self.long_term_memory.store(memory)
    
    def get_knowledge_in_domain(self,
                              agent_id: str,
                              domain: str,
                              limit: int = 50) -> List[MemoryEntry]:
        """
        Get all knowledge in a specific domain
        
        Args:
            agent_id: The agent to get knowledge for
            domain: The domain to search in
            limit: Maximum number of entries to return
            
        Returns:
            List of semantic memories in the domain
        """
        query = MemoryQuery(
            query_text=domain,
            memory_types=[MemoryType.SEMANTIC],
            agent_id=agent_id,
            limit=limit,
            similarity_threshold=0.3
        )
        
        search_result = self.long_term_memory.search(query)
        
        # Filter for exact domain matches and high relevance
        domain_knowledge = [
            entry for entry in search_result.entries
            if entry.metadata.get("domain") == domain or domain.lower() in entry.content.lower()
        ]
        
        return domain_knowledge
    
    def find_related_concepts(self,
                            agent_id: str,
                            concept: str,
                            limit: int = 10) -> MemorySearchResult:
        """
        Find concepts related to a given concept
        
        Args:
            agent_id: The agent to search for
            concept: The concept to find relations for
            limit: Maximum number of related concepts
            
        Returns:
            Search results with related concepts
        """
        query = MemoryQuery(
            query_text=concept,
            memory_types=[MemoryType.SEMANTIC],
            agent_id=agent_id,
            limit=limit * 2,  # Get more to filter
            similarity_threshold=0.5
        )
        
        search_result = self.long_term_memory.search(query)
        
        # Filter for concepts and facts that mention this concept
        related_entries = []
        related_scores = []
        
        for entry, score in zip(search_result.entries, search_result.scores):
            if (entry.metadata.get("type") in ["concept", "fact"] and 
                concept.lower() in entry.content.lower()):
                related_entries.append(entry)
                related_scores.append(score)
        
        return MemorySearchResult(
            entries=related_entries[:limit],
            scores=related_scores[:limit],
            query=query,
            total_found=len(related_entries)
        )
    
    def validate_knowledge(self,
                          agent_id: str,
                          statement: str,
                          threshold: float = 0.8) -> Dict[str, Any]:
        """
        Check if a statement is consistent with stored knowledge
        
        Args:
            agent_id: The agent to check knowledge for
            statement: The statement to validate
            threshold: Similarity threshold for matching
            
        Returns:
            Validation result with confidence and supporting evidence
        """
        query = MemoryQuery(
            query_text=statement,
            memory_types=[MemoryType.SEMANTIC],
            agent_id=agent_id,
            limit=10,
            similarity_threshold=threshold
        )
        
        search_result = self.long_term_memory.search(query)
        
        # Analyze results for consistency
        supporting_facts = []
        contradicting_facts = []
        average_confidence = 0.0
        
        for entry in search_result.entries:
            fact_confidence = entry.metadata.get("confidence", 0.5)
            
            # Simple heuristic: if very similar, consider it supporting
            if entry.content.lower() in statement.lower() or statement.lower() in entry.content.lower():
                supporting_facts.append(entry)
            else:
                # More sophisticated contradiction detection would go here
                # For now, assume non-matching high-confidence facts might contradict
                if fact_confidence > 0.8:
                    contradicting_facts.append(entry)
            
            average_confidence += fact_confidence
        
        if search_result.entries:
            average_confidence /= len(search_result.entries)
        
        return {
            "is_consistent": len(supporting_facts) > len(contradicting_facts),
            "confidence": average_confidence,
            "supporting_evidence": [entry.content for entry in supporting_facts[:3]],
            "contradicting_evidence": [entry.content for entry in contradicting_facts[:3]],
            "evidence_count": len(search_result.entries)
        }
    
    def update_knowledge(self,
                        agent_id: str,
                        old_knowledge: str,
                        new_knowledge: str,
                        reason: str = "Updated information") -> bool:
        """
        Update existing knowledge with new information
        
        Args:
            agent_id: The agent updating knowledge
            old_knowledge: The knowledge to update
            new_knowledge: The new knowledge
            reason: Reason for the update
            
        Returns:
            True if update was successful
        """
        # Find existing knowledge
        query = MemoryQuery(
            query_text=old_knowledge,
            memory_types=[MemoryType.SEMANTIC],
            agent_id=agent_id,
            limit=5,
            similarity_threshold=0.9
        )
        
        search_result = self.long_term_memory.search(query)
        
        if not search_result.entries:
            # No existing knowledge found, store as new
            return self.store_fact(agent_id, new_knowledge, "updated_knowledge") is not None
        
        # Mark old knowledge as outdated and store new
        for old_entry in search_result.entries:
            # Update metadata to mark as outdated
            old_entry.metadata["outdated"] = True
            old_entry.metadata["updated_at"] = datetime.now().isoformat()
            old_entry.metadata["update_reason"] = reason
            old_entry.importance = 0.1  # Reduce importance
            
            # Store the updated entry
            self.long_term_memory.store(old_entry)
        
        # Store new knowledge
        domain = search_result.entries[0].metadata.get("domain", "general")
        return self.store_fact(agent_id, new_knowledge, domain, source=f"Update: {reason}") is not None
    
    def get_domain_expertise_level(self, agent_id: str, domain: str) -> Dict[str, Any]:
        """
        Assess the agent's expertise level in a domain
        
        Args:
            agent_id: The agent to assess
            domain: The domain to assess expertise in
            
        Returns:
            Expertise assessment with metrics
        """
        domain_knowledge = self.get_knowledge_in_domain(agent_id, domain, limit=200)
        
        if not domain_knowledge:
            return {
                "expertise_level": "novice",
                "knowledge_count": 0,
                "confidence_average": 0.0,
                "domains_covered": []
            }
        
        # Calculate metrics
        knowledge_count = len(domain_knowledge)
        confidence_scores = [
            entry.metadata.get("confidence", 0.5) 
            for entry in domain_knowledge
        ]
        average_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Determine expertise level
        if knowledge_count >= 50 and average_confidence >= 0.8:
            expertise_level = "expert"
        elif knowledge_count >= 20 and average_confidence >= 0.7:
            expertise_level = "advanced"
        elif knowledge_count >= 10 and average_confidence >= 0.6:
            expertise_level = "intermediate"
        else:
            expertise_level = "novice"
        
        # Find related domains
        all_domains = set()
        for entry in domain_knowledge:
            entry_domain = entry.metadata.get("domain")
            if entry_domain:
                all_domains.add(entry_domain)
        
        return {
            "expertise_level": expertise_level,
            "knowledge_count": knowledge_count,
            "confidence_average": average_confidence,
            "domains_covered": list(all_domains)
        }
    
    def _calculate_fact_importance(self, fact: str, domain: str, confidence: float) -> float:
        """Calculate importance score for a fact"""
        importance = confidence * 0.6  # Base on confidence
        
        # Domain-specific importance
        important_domains = ["safety", "security", "ethics", "legal", "health"]
        if domain.lower() in important_domains:
            importance += 0.3
        
        # Length and complexity can indicate importance
        if len(fact) > 200:
            importance += 0.1
        
        return min(importance, 1.0)
    
    def _calculate_concept_importance(self, 
                                   concept: str, 
                                   definition: str, 
                                   relationships: Optional[Dict[str, List[str]]]) -> float:
        """Calculate importance score for a concept"""
        importance = 0.7  # Base importance for concepts
        
        # Concepts with many relationships are more important
        if relationships:
            relationship_count = sum(len(rel_list) for rel_list in relationships.values())
            importance += min(relationship_count * 0.05, 0.3)
        
        # Longer definitions might indicate more important concepts
        if len(definition) > 100:
            importance += 0.1
        
        return min(importance, 1.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get semantic memory statistics"""
        return {
            "backend": "long_term_memory",
            "supported_types": ["fact", "concept", "rule"],
            "features": ["domain_expertise", "knowledge_validation", "concept_relationships"]
        }