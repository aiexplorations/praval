"""
Comprehensive tests for Praval SemanticMemory.

This module ensures the semantic memory system is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions, including knowledge storage, concept relationships, and validation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from praval.memory.semantic_memory import SemanticMemory
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestSemanticMemoryInitialization:
    """Test SemanticMemory initialization with comprehensive coverage."""
    
    def test_semantic_memory_initialization(self):
        """Test semantic memory initialization."""
        mock_long_term = Mock()
        
        memory = SemanticMemory(mock_long_term)
        
        assert memory.long_term_memory == mock_long_term


class TestSemanticMemoryFactStorage:
    """Test fact storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_store_fact_basic(self):
        """Test basic fact storage."""
        self.mock_long_term.store.return_value = "fact_id_123"
        
        result_id = self.memory.store_fact(
            agent_id="fact_agent",
            fact="The sky is blue during clear weather",
            domain="weather"
        )
        
        assert result_id == "fact_id_123"
        
        # Verify storage call
        self.mock_long_term.store.assert_called_once()
        call_args = self.mock_long_term.store.call_args[0][0]
        
        assert call_args.agent_id == "fact_agent"
        assert call_args.memory_type == MemoryType.SEMANTIC
        assert call_args.content == "The sky is blue during clear weather"
        assert call_args.metadata["type"] == "fact"
        assert call_args.metadata["domain"] == "weather"
        assert call_args.metadata["confidence"] == 1.0  # Default
        assert call_args.metadata["source"] is None  # Default
        assert call_args.metadata["related_concepts"] == []  # Default
        assert "importance" in call_args.metadata
    
    def test_store_fact_with_all_parameters(self):
        """Test fact storage with all parameters."""
        self.mock_long_term.store.return_value = "full_fact_123"
        
        result_id = self.memory.store_fact(
            agent_id="full_fact_agent",
            fact="Python is a high-level programming language",
            domain="programming",
            confidence=0.95,
            source="Python.org documentation",
            related_concepts=["programming", "high-level", "language"]
        )
        
        assert result_id == "full_fact_123"
        
        call_args = self.mock_long_term.store.call_args[0][0]
        assert call_args.metadata["confidence"] == 0.95
        assert call_args.metadata["source"] == "Python.org documentation"
        assert call_args.metadata["related_concepts"] == ["programming", "high-level", "language"]
    
    def test_store_fact_importance_calculation_base(self):
        """Test fact importance calculation with base confidence."""
        self.mock_long_term.store.return_value = "importance_test"
        
        self.memory.store_fact(
            agent_id="importance_agent",
            fact="Regular fact",
            domain="general",
            confidence=0.8
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should be based on confidence (0.8 * 0.6 = 0.48)
        assert importance == 0.48
    
    def test_store_fact_importance_calculation_important_domain(self):
        """Test fact importance calculation with important domain."""
        self.mock_long_term.store.return_value = "safety_fact"
        
        self.memory.store_fact(
            agent_id="safety_agent",
            fact="Safety procedures must be followed",
            domain="safety",
            confidence=0.5
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should get domain bonus (0.5 * 0.6 + 0.3 = 0.6)
        assert importance == 0.6
    
    def test_store_fact_importance_calculation_long_fact(self):
        """Test fact importance calculation with long fact."""
        self.mock_long_term.store.return_value = "long_fact"
        
        long_fact = "This is a very long fact that contains detailed information and goes on for quite a while, providing extensive context and multiple pieces of information that could be considered important due to its comprehensiveness and detail."
        
        self.memory.store_fact(
            agent_id="long_agent",
            fact=long_fact,
            domain="general",
            confidence=0.5
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should get length bonus (0.5 * 0.6 + 0.1 = 0.4)
        assert importance == 0.4
    
    def test_store_fact_importance_calculation_capped(self):
        """Test that fact importance is capped at 1.0."""
        self.mock_long_term.store.return_value = "capped_fact"
        
        long_fact = "This is an extremely long safety-critical fact " * 10
        
        self.memory.store_fact(
            agent_id="capped_agent",
            fact=long_fact,
            domain="safety",
            confidence=1.0
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]

        # Should be capped at 1.0 (use approx for floating point comparison)
        assert importance == pytest.approx(1.0)


class TestSemanticMemoryConceptStorage:
    """Test concept storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_store_concept_basic(self):
        """Test basic concept storage."""
        self.mock_long_term.store.return_value = "concept_id_123"
        
        result_id = self.memory.store_concept(
            agent_id="concept_agent",
            concept="Machine Learning",
            definition="A subset of AI that enables computers to learn without explicit programming",
            domain="artificial_intelligence"
        )
        
        assert result_id == "concept_id_123"
        
        # Verify storage call
        self.mock_long_term.store.assert_called_once()
        call_args = self.mock_long_term.store.call_args[0][0]
        
        assert call_args.agent_id == "concept_agent"
        assert call_args.memory_type == MemoryType.SEMANTIC
        assert "Concept: Machine Learning" in call_args.content
        assert "Definition: A subset of AI" in call_args.content
        assert call_args.metadata["type"] == "concept"
        assert call_args.metadata["concept"] == "Machine Learning"
        assert call_args.metadata["definition"] == "A subset of AI that enables computers to learn without explicit programming"
        assert call_args.metadata["domain"] == "artificial_intelligence"
        assert call_args.metadata["properties"] == {}  # Default
        assert call_args.metadata["relationships"] == {}  # Default
    
    def test_store_concept_with_properties_and_relationships(self):
        """Test concept storage with properties and relationships."""
        self.mock_long_term.store.return_value = "full_concept_123"
        
        properties = {
            "complexity": "high",
            "applications": ["classification", "regression", "clustering"]
        }
        
        relationships = {
            "is_a": ["artificial_intelligence", "computer_science"],
            "relates_to": ["neural_networks", "deep_learning", "statistics"],
            "uses": ["algorithms", "data", "mathematics"]
        }
        
        result_id = self.memory.store_concept(
            agent_id="full_concept_agent",
            concept="Deep Learning",
            definition="A subset of machine learning using neural networks with multiple layers",
            domain="ai",
            properties=properties,
            relationships=relationships
        )
        
        assert result_id == "full_concept_123"
        
        call_args = self.mock_long_term.store.call_args[0][0]
        assert call_args.metadata["properties"] == properties
        assert call_args.metadata["relationships"] == relationships
    
    def test_concept_importance_calculation_base(self):
        """Test concept importance calculation with base values."""
        self.mock_long_term.store.return_value = "base_concept"
        
        self.memory.store_concept(
            agent_id="base_agent",
            concept="Simple Concept",
            definition="A simple definition",
            domain="test"
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should be base importance (0.7)
        assert importance == 0.7
    
    def test_concept_importance_calculation_with_relationships(self):
        """Test concept importance calculation with relationships."""
        self.mock_long_term.store.return_value = "related_concept"
        
        relationships = {
            "is_a": ["category1", "category2"],
            "relates_to": ["concept1", "concept2", "concept3"],
            "uses": ["tool1"]
        }
        
        self.memory.store_concept(
            agent_id="related_agent",
            concept="Well Connected Concept",
            definition="A concept with many relationships",
            domain="test",
            relationships=relationships
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]
        
        # Should get relationship bonus (0.7 + (6 * 0.05) = 1.0)
        assert importance == 1.0
    
    def test_concept_importance_calculation_with_long_definition(self):
        """Test concept importance calculation with long definition."""
        self.mock_long_term.store.return_value = "long_def_concept"
        
        long_definition = "This is a very detailed and comprehensive definition that goes into great depth about the concept, explaining various aspects, nuances, and implications in considerable detail."
        
        self.memory.store_concept(
            agent_id="long_def_agent",
            concept="Detailed Concept",
            definition=long_definition,
            domain="test"
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        importance = call_args.metadata["importance"]

        # Should get length bonus (0.7 + 0.1 = 0.8) - use approx for floating point comparison
        assert importance == pytest.approx(0.8)


class TestSemanticMemoryRuleStorage:
    """Test rule storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_store_rule_basic(self):
        """Test basic rule storage."""
        self.mock_long_term.store.return_value = "rule_id_123"
        
        conditions = ["user asks for help", "task is within capability"]
        actions = ["provide assistance", "explain approach", "ask clarifying questions"]
        
        result_id = self.memory.store_rule(
            agent_id="rule_agent",
            rule_name="Help Request Rule",
            rule_description="How to respond to user help requests",
            conditions=conditions,
            actions=actions,
            domain="user_interaction"
        )
        
        assert result_id == "rule_id_123"
        
        # Verify storage call
        self.mock_long_term.store.assert_called_once()
        call_args = self.mock_long_term.store.call_args[0][0]
        
        assert call_args.agent_id == "rule_agent"
        assert call_args.memory_type == MemoryType.SEMANTIC
        assert "Rule: Help Request Rule" in call_args.content
        assert "How to respond to user help requests" in call_args.content
        assert call_args.metadata["type"] == "rule"
        assert call_args.metadata["rule_name"] == "Help Request Rule"
        assert call_args.metadata["rule_description"] == "How to respond to user help requests"
        assert call_args.metadata["conditions"] == conditions
        assert call_args.metadata["actions"] == actions
        assert call_args.metadata["domain"] == "user_interaction"
        assert call_args.metadata["confidence"] == 1.0  # Default
        assert call_args.metadata["importance"] == 0.8  # Rules are important
    
    def test_store_rule_with_custom_confidence(self):
        """Test rule storage with custom confidence."""
        self.mock_long_term.store.return_value = "confident_rule"
        
        result_id = self.memory.store_rule(
            agent_id="confident_agent",
            rule_name="Confident Rule",
            rule_description="A rule with custom confidence",
            conditions=["condition"],
            actions=["action"],
            domain="test",
            confidence=0.7
        )
        
        call_args = self.mock_long_term.store.call_args[0][0]
        assert call_args.metadata["confidence"] == 0.7


class TestSemanticMemoryKnowledgeRetrieval:
    """Test knowledge retrieval functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def create_semantic_memory(self, memory_id: str, agent_id: str, content: str, domain: str, memory_type: str = "fact"):
        """Helper to create semantic memory entry."""
        return MemoryEntry(
            id=memory_id,
            agent_id=agent_id,
            memory_type=MemoryType.SEMANTIC,
            content=content,
            metadata={
                "type": memory_type,
                "domain": domain,
                "confidence": 0.8
            }
        )
    
    def test_get_knowledge_in_domain_exact_match(self):
        """Test getting knowledge with exact domain match."""
        domain_memories = [
            self.create_semantic_memory("ai_1", "domain_agent", "AI is intelligence by machines", "artificial_intelligence"),
            self.create_semantic_memory("ai_2", "domain_agent", "Machine learning is a subset of AI", "artificial_intelligence"),
            self.create_semantic_memory("other", "domain_agent", "Python is a programming language", "programming")
        ]
        
        mock_search_result = MemorySearchResult(
            entries=domain_memories,
            scores=[0.9, 0.8, 0.3],
            query=Mock(),
            total_found=3
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_knowledge_in_domain(
            agent_id="domain_agent",
            domain="artificial_intelligence",
            limit=10
        )
        
        # Should return entries with exact domain match
        assert len(result) == 2
        assert all(entry.metadata["domain"] == "artificial_intelligence" for entry in result)
        
        # Verify search was called correctly
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == "artificial_intelligence"
        assert search_call_args.memory_types == [MemoryType.SEMANTIC]
        assert search_call_args.agent_id == "domain_agent"
        assert search_call_args.limit == 10
        assert search_call_args.similarity_threshold == 0.3
    
    def test_get_knowledge_in_domain_content_match(self):
        """Test getting knowledge with domain mentioned in content."""
        # Memory that doesn't have exact domain match but mentions domain in content
        content_match_memory = self.create_semantic_memory(
            "content_match", "content_agent", 
            "Artificial intelligence algorithms are used in robotics", "robotics"
        )
        
        mock_search_result = MemorySearchResult(
            entries=[content_match_memory],
            scores=[0.7],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_knowledge_in_domain(
            agent_id="content_agent",
            domain="artificial intelligence",  # Use space to match content substring
            limit=10
        )
        
        # Should return entries that mention domain in content
        assert len(result) == 1
        assert "artificial intelligence" in result[0].content.lower()
    
    def test_get_knowledge_in_domain_no_matches(self):
        """Test getting knowledge when no domain matches exist."""
        mock_search_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=Mock(),
            total_found=0
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.get_knowledge_in_domain(
            agent_id="empty_agent",
            domain="nonexistent_domain",
            limit=10
        )
        
        assert len(result) == 0


class TestSemanticMemoryConceptRelations:
    """Test concept relationship functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_find_related_concepts_basic(self):
        """Test finding related concepts."""
        related_memories = [
            MemoryEntry(
                id="concept_1",
                agent_id="concept_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Machine Learning is a subset of AI",
                metadata={"type": "concept", "domain": "ai"}
            ),
            MemoryEntry(
                id="fact_1",
                agent_id="concept_agent", 
                memory_type=MemoryType.SEMANTIC,
                content="Machine learning algorithms learn from data",
                metadata={"type": "fact", "domain": "ai"}
            ),
            MemoryEntry(
                id="rule_1",
                agent_id="concept_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Rule about machine learning",
                metadata={"type": "rule", "domain": "ai"}
            )
        ]
        
        mock_search_result = MemorySearchResult(
            entries=related_memories,
            scores=[0.9, 0.8, 0.7],
            query=Mock(),
            total_found=3
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.find_related_concepts(
            agent_id="concept_agent",
            concept="machine learning",
            limit=5
        )
        
        # Should only return concepts and facts (not rules)
        assert len(result.entries) == 2
        assert all(entry.metadata["type"] in ["concept", "fact"] for entry in result.entries)
        assert all("machine learning" in entry.content.lower() for entry in result.entries)
        
        # Scores should be recalculated for filtered results
        assert len(result.scores) == 2
        assert result.scores[0] == 0.9
        assert result.scores[1] == 0.8
        
        # Verify search parameters
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == "machine learning"
        assert search_call_args.limit == 10  # limit * 2
        assert search_call_args.similarity_threshold == 0.5
    
    def test_find_related_concepts_no_matches(self):
        """Test finding related concepts when none exist."""
        mock_search_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=Mock(),
            total_found=0
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.find_related_concepts(
            agent_id="no_concepts_agent",
            concept="nonexistent_concept",
            limit=5
        )
        
        assert len(result.entries) == 0
        assert len(result.scores) == 0
        assert result.total_found == 0
    
    def test_find_related_concepts_case_insensitive(self):
        """Test that concept matching is case-insensitive."""
        mixed_case_memory = MemoryEntry(
            id="mixed_case",
            agent_id="case_agent",
            memory_type=MemoryType.SEMANTIC,
            content="MACHINE LEARNING is powerful",
            metadata={"type": "fact", "domain": "ai"}
        )
        
        mock_search_result = MemorySearchResult(
            entries=[mixed_case_memory],
            scores=[0.8],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.find_related_concepts(
            agent_id="case_agent",
            concept="machine learning",  # lowercase
            limit=5
        )
        
        # Should match despite case differences
        assert len(result.entries) == 1
        assert result.entries[0].id == "mixed_case"


class TestSemanticMemoryKnowledgeValidation:
    """Test knowledge validation functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_validate_knowledge_supporting_evidence(self):
        """Test knowledge validation with supporting evidence."""
        supporting_memories = [
            MemoryEntry(
                id="support_1",
                agent_id="validate_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Python is a programming language",
                metadata={"type": "fact", "confidence": 0.9}
            ),
            MemoryEntry(
                id="support_2", 
                agent_id="validate_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Python programming language is widely used",
                metadata={"type": "fact", "confidence": 0.8}
            )
        ]
        
        mock_search_result = MemorySearchResult(
            entries=supporting_memories,
            scores=[0.9, 0.8],
            query=Mock(),
            total_found=2
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.validate_knowledge(
            agent_id="validate_agent",
            statement="Python is a programming language",
            threshold=0.8
        )
        
        assert result["is_consistent"] is True
        assert result["confidence"] == pytest.approx(0.85)  # Average of 0.9 and 0.8
        # Only memory 1 is supporting (exact substring match)
        # Memory 2 "Python programming language is widely used" does not contain
        # "Python is a programming language" as substring (missing "is a")
        assert len(result["supporting_evidence"]) == 1
        assert len(result["contradicting_evidence"]) == 0
        assert result["evidence_count"] == 2
        
        # Verify search parameters
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == "Python is a programming language"
        assert search_call_args.similarity_threshold == 0.8
    
    def test_validate_knowledge_contradicting_evidence(self):
        """Test knowledge validation with contradicting evidence."""
        contradicting_memory = MemoryEntry(
            id="contradict_1",
            agent_id="contradict_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Some unrelated high-confidence fact",
            metadata={"type": "fact", "confidence": 0.95}
        )
        
        mock_search_result = MemorySearchResult(
            entries=[contradicting_memory],
            scores=[0.7],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.validate_knowledge(
            agent_id="contradict_agent",
            statement="Some statement to validate",
            threshold=0.6
        )
        
        # High confidence facts that don't match are considered contradictory
        assert result["is_consistent"] is False
        assert result["confidence"] == 0.95
        assert len(result["supporting_evidence"]) == 0
        assert len(result["contradicting_evidence"]) == 1
    
    def test_validate_knowledge_no_evidence(self):
        """Test knowledge validation with no evidence."""
        mock_search_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=Mock(),
            total_found=0
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        result = self.memory.validate_knowledge(
            agent_id="no_evidence_agent",
            statement="Novel statement with no evidence",
            threshold=0.8
        )
        
        assert result["is_consistent"] is False  # No evidence means 0 > 0 = False in implementation
        assert result["confidence"] == 0.0
        assert len(result["supporting_evidence"]) == 0
        assert len(result["contradicting_evidence"]) == 0
        assert result["evidence_count"] == 0


class TestSemanticMemoryKnowledgeUpdate:
    """Test knowledge update functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_update_knowledge_existing_found(self):
        """Test updating existing knowledge."""
        # Mock finding existing knowledge
        existing_memory = MemoryEntry(
            id="existing_knowledge",
            agent_id="update_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Old knowledge statement",
            metadata={"type": "fact", "domain": "test_domain", "confidence": 0.8}
        )
        
        mock_search_result = MemorySearchResult(
            entries=[existing_memory],
            scores=[0.95],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        # Mock store calls for updating old and storing new
        self.mock_long_term.store.side_effect = ["updated_old", "new_knowledge_id"]
        
        result = self.memory.update_knowledge(
            agent_id="update_agent",
            old_knowledge="Old knowledge statement",
            new_knowledge="New updated knowledge statement",
            reason="Better information available"
        )
        
        assert result is True
        
        # Should store twice: once for updated old entry, once for new knowledge
        assert self.mock_long_term.store.call_count == 2
        
        # First call should update the old entry
        old_update_call = self.mock_long_term.store.call_args_list[0][0][0]
        assert old_update_call.metadata["outdated"] is True
        assert old_update_call.metadata["update_reason"] == "Better information available"
        assert old_update_call.importance == 0.1  # Reduced importance
        assert "updated_at" in old_update_call.metadata
        
        # Search should have been called to find existing knowledge
        self.mock_long_term.search.assert_called_once()
        search_call_args = self.mock_long_term.search.call_args[0][0]
        assert search_call_args.query_text == "Old knowledge statement"
        assert search_call_args.similarity_threshold == 0.9
    
    def test_update_knowledge_no_existing_found(self):
        """Test updating knowledge when no existing knowledge found."""
        # Mock no existing knowledge found
        mock_search_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=Mock(),
            total_found=0
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        # Mock store call for new knowledge
        self.mock_long_term.store.return_value = "new_fact_id"
        
        result = self.memory.update_knowledge(
            agent_id="no_existing_agent",
            old_knowledge="Non-existent knowledge",
            new_knowledge="Brand new knowledge",
            reason="First time learning"
        )
        
        assert result is True
        
        # Should only store once (new knowledge)
        assert self.mock_long_term.store.call_count == 1
    
    def test_update_knowledge_store_failure(self):
        """Test update knowledge when store fails."""
        # Mock finding existing knowledge
        existing_memory = MemoryEntry(
            id="fail_update",
            agent_id="fail_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Knowledge to update",
            metadata={"type": "fact", "domain": "test"}
        )
        
        mock_search_result = MemorySearchResult(
            entries=[existing_memory],
            scores=[0.95],
            query=Mock(),
            total_found=1
        )
        self.mock_long_term.search.return_value = mock_search_result
        
        # Mock store failure (returns None)
        self.mock_long_term.store.side_effect = ["old_updated", None]
        
        result = self.memory.update_knowledge(
            agent_id="fail_agent",
            old_knowledge="Knowledge to update",
            new_knowledge="Failed new knowledge"
        )
        
        assert result is False


class TestSemanticMemoryDomainExpertise:
    """Test domain expertise assessment functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_get_domain_expertise_level_novice(self):
        """Test expertise assessment for novice level."""
        # Mock get_knowledge_in_domain to return empty list
        with patch.object(self.memory, 'get_knowledge_in_domain', return_value=[]):
            result = self.memory.get_domain_expertise_level("novice_agent", "programming")
            
            assert result["expertise_level"] == "novice"
            assert result["knowledge_count"] == 0
            assert result["confidence_average"] == 0.0
            assert result["domains_covered"] == []
    
    def test_get_domain_expertise_level_intermediate(self):
        """Test expertise assessment for intermediate level."""
        # Create intermediate level knowledge (15 entries, 0.65 average confidence)
        intermediate_knowledge = []
        for i in range(15):
            memory = MemoryEntry(
                id=f"intermediate_{i}",
                agent_id="intermediate_agent",
                memory_type=MemoryType.SEMANTIC,
                content=f"Programming knowledge {i}",
                metadata={"domain": "programming", "confidence": 0.65}
            )
            intermediate_knowledge.append(memory)
        
        with patch.object(self.memory, 'get_knowledge_in_domain', return_value=intermediate_knowledge):
            result = self.memory.get_domain_expertise_level("intermediate_agent", "programming")
            
            assert result["expertise_level"] == "intermediate"
            assert result["knowledge_count"] == 15
            assert result["confidence_average"] == 0.65
            assert "programming" in result["domains_covered"]
    
    def test_get_domain_expertise_level_advanced(self):
        """Test expertise assessment for advanced level."""
        # Create advanced level knowledge (25 entries, 0.75 average confidence)
        advanced_knowledge = []
        for i in range(25):
            memory = MemoryEntry(
                id=f"advanced_{i}",
                agent_id="advanced_agent", 
                memory_type=MemoryType.SEMANTIC,
                content=f"Advanced programming knowledge {i}",
                metadata={"domain": "programming", "confidence": 0.75}
            )
            advanced_knowledge.append(memory)
        
        with patch.object(self.memory, 'get_knowledge_in_domain', return_value=advanced_knowledge):
            result = self.memory.get_domain_expertise_level("advanced_agent", "programming")
            
            assert result["expertise_level"] == "advanced"
            assert result["knowledge_count"] == 25
            assert result["confidence_average"] == 0.75
    
    def test_get_domain_expertise_level_expert(self):
        """Test expertise assessment for expert level."""
        # Create expert level knowledge (60 entries, 0.85 average confidence, multiple domains)
        expert_knowledge = []
        domains = ["programming", "algorithms", "data_structures"]
        
        for i in range(60):
            domain = domains[i % len(domains)]
            memory = MemoryEntry(
                id=f"expert_{i}",
                agent_id="expert_agent",
                memory_type=MemoryType.SEMANTIC,
                content=f"Expert {domain} knowledge {i}",
                metadata={"domain": domain, "confidence": 0.85}
            )
            expert_knowledge.append(memory)
        
        with patch.object(self.memory, 'get_knowledge_in_domain', return_value=expert_knowledge):
            result = self.memory.get_domain_expertise_level("expert_agent", "programming")
            
            assert result["expertise_level"] == "expert"
            assert result["knowledge_count"] == 60
            assert result["confidence_average"] == 0.85
            assert len(result["domains_covered"]) == 3
            assert "programming" in result["domains_covered"]
            assert "algorithms" in result["domains_covered"]
            assert "data_structures" in result["domains_covered"]
    
    def test_get_domain_expertise_level_mixed_confidence(self):
        """Test expertise assessment with mixed confidence levels."""
        # Create knowledge with varying confidence levels
        mixed_knowledge = []
        confidences = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]  # Average = 0.6
        
        for i, confidence in enumerate(confidences):
            memory = MemoryEntry(
                id=f"mixed_{i}",
                agent_id="mixed_agent",
                memory_type=MemoryType.SEMANTIC,
                content=f"Mixed confidence knowledge {i}",
                metadata={"domain": "mixed", "confidence": confidence}
            )
            mixed_knowledge.append(memory)
        
        with patch.object(self.memory, 'get_knowledge_in_domain', return_value=mixed_knowledge):
            result = self.memory.get_domain_expertise_level("mixed_agent", "mixed")
            
            # Should be novice due to low average confidence despite adequate count
            assert result["expertise_level"] == "novice"
            assert result["confidence_average"] == 0.6
    
    def test_get_domain_expertise_level_missing_domain_metadata(self):
        """Test expertise assessment when some entries lack domain metadata."""
        knowledge_with_missing_domain = []
        for i in range(15):
            # Some entries have domain, some don't
            metadata = {"confidence": 0.7}
            if i % 2 == 0:
                metadata["domain"] = "test_domain"
            
            memory = MemoryEntry(
                id=f"missing_domain_{i}",
                agent_id="missing_domain_agent",
                memory_type=MemoryType.SEMANTIC,
                content=f"Knowledge {i}",
                metadata=metadata
            )
            knowledge_with_missing_domain.append(memory)
        
        with patch.object(self.memory, 'get_knowledge_in_domain', return_value=knowledge_with_missing_domain):
            result = self.memory.get_domain_expertise_level("missing_domain_agent", "test_domain")
            
            # Should handle missing domain metadata gracefully
            assert result["expertise_level"] == "intermediate"  # 15 entries, 0.7 confidence
            assert "test_domain" in result["domains_covered"]


class TestSemanticMemoryStatistics:
    """Test semantic memory statistics functionality."""
    
    def test_get_stats_basic(self):
        """Test getting semantic memory statistics."""
        mock_long_term = Mock()
        memory = SemanticMemory(mock_long_term)
        
        stats = memory.get_stats()
        
        expected = {
            "backend": "long_term_memory",
            "supported_types": ["fact", "concept", "rule"],
            "features": ["domain_expertise", "knowledge_validation", "concept_relationships"]
        }
        
        assert stats == expected


class TestSemanticMemoryIntegration:
    """Test integration scenarios for SemanticMemory."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_long_term = Mock()
        self.memory = SemanticMemory(self.mock_long_term)
    
    def test_complete_knowledge_workflow(self):
        """Test complete workflow from storage to retrieval and validation."""
        # Store different types of knowledge
        self.mock_long_term.store.side_effect = ["fact_id", "concept_id", "rule_id"]
        
        # Store a fact
        fact_id = self.memory.store_fact(
            agent_id="workflow_agent",
            fact="Python supports object-oriented programming",
            domain="programming",
            confidence=0.9
        )
        
        # Store a concept
        concept_id = self.memory.store_concept(
            agent_id="workflow_agent",
            concept="Object-Oriented Programming",
            definition="Programming paradigm based on objects containing data and code",
            domain="programming"
        )
        
        # Store a rule
        rule_id = self.memory.store_rule(
            agent_id="workflow_agent",
            rule_name="OOP Best Practice",
            rule_description="Encapsulate data and behavior together",
            conditions=["designing classes"],
            actions=["group related data and methods", "hide implementation details"],
            domain="programming"
        )
        
        assert fact_id == "fact_id"
        assert concept_id == "concept_id"
        assert rule_id == "rule_id"
        
        # Verify all were stored in long-term memory
        assert self.mock_long_term.store.call_count == 3
        
        # Verify all stored entries have correct memory type
        for call in self.mock_long_term.store.call_args_list:
            memory_entry = call[0][0]
            assert memory_entry.memory_type == MemoryType.SEMANTIC
            assert memory_entry.agent_id == "workflow_agent"
    
    def test_knowledge_consistency_across_types(self):
        """Test that knowledge is consistently structured across different types."""
        self.mock_long_term.store.side_effect = ["test_fact", "test_concept", "test_rule"]
        
        # Store one of each type
        self.memory.store_fact("consistency_agent", "Test fact", "test")
        self.memory.store_concept("consistency_agent", "Test Concept", "Test definition", "test")
        self.memory.store_rule("consistency_agent", "Test Rule", "Test description", ["condition"], ["action"], "test")
        
        # All should have semantic memory type and proper structure
        for call_args in self.mock_long_term.store.call_args_list:
            memory_entry = call_args[0][0]
            assert memory_entry.memory_type == MemoryType.SEMANTIC
            assert "type" in memory_entry.metadata
            assert memory_entry.metadata["type"] in ["fact", "concept", "rule"]
            assert "importance" in memory_entry.metadata