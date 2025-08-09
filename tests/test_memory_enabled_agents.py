"""
Test memory-enabled agents with embedded vector stores

Following Praval's test-driven development philosophy
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from praval import agent, start_agents
from praval.memory import MemoryType


class TestMemoryEnabledAgents:
    """Test agents with memory capabilities"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)
    
    def test_agent_with_default_memory(self):
        """Test agent created with default memory configuration"""
        
        @agent("memory_agent", memory=True)
        def test_agent(spore):
            """Agent with default memory enabled"""
            return {"status": "remembered"}
        
        # Agent should have memory manager
        assert hasattr(test_agent, 'memory')
        assert test_agent.memory is not None
    
    def test_agent_with_custom_memory_config(self):
        """Test agent with custom memory configuration"""
        
        @agent("custom_memory_agent", 
               memory={
                   "backend": "chromadb",
                   "storage_path": str(self.temp_path),
                   "collection_name": "test_memories"
               })
        def test_agent(spore):
            """Agent with custom memory config"""
            return {"status": "configured"}
        
        # Agent should have memory with custom settings
        assert hasattr(test_agent, 'memory')
        assert test_agent.memory.backend == "chromadb"
        assert test_agent.memory.collection_name == "test_memories"
    
    def test_agent_memory_store_and_recall(self):
        """Test agent can store and recall memories"""
        
        @agent("recall_agent", memory=True)
        def test_agent(spore):
            """Agent that can remember things"""
            query = spore.knowledge.get("query")
            
            if query == "remember":
                # Store a memory
                memory_id = test_agent.remember("Important information about coral reefs")
                return {"memory_id": memory_id}
            elif query == "recall":
                # Recall memories
                memories = test_agent.recall("coral reefs")
                return {"memories": [m.content for m in memories]}
        
        # Test storing memory
        result = start_agents(
            test_agent,
            initial_data={"type": "test", "query": "remember"}
        )
        assert "memory_id" in result
        
        # Test recalling memory
        result = start_agents(
            test_agent, 
            initial_data={"type": "test", "query": "recall"}
        )
        assert "memories" in result
        assert len(result["memories"]) > 0
        assert "coral reefs" in result["memories"][0]
    
    def test_agent_with_knowledge_base(self):
        """Test agent with pre-loaded knowledge base"""
        
        # Create test knowledge files
        kb_dir = self.temp_path / "knowledge"
        kb_dir.mkdir()
        
        (kb_dir / "facts.txt").write_text("Coral reefs are marine ecosystems.")
        (kb_dir / "concepts.md").write_text("# Symbiosis\nMutual benefit relationships.")
        
        @agent("kb_agent", 
               memory=True,
               knowledge_base=str(kb_dir))
        def test_agent(spore):
            """Agent with knowledge base"""
            query = spore.knowledge.get("query")
            memories = test_agent.recall(query)
            return {"relevant_knowledge": [m.content for m in memories]}
        
        # Test querying knowledge base
        result = start_agents(
            test_agent,
            initial_data={"type": "test", "query": "coral"}
        )
        
        assert "relevant_knowledge" in result
        assert len(result["relevant_knowledge"]) > 0
    
    def test_agent_without_memory(self):
        """Test agent explicitly created without memory"""
        
        @agent("no_memory_agent", memory=False)
        def test_agent(spore):
            """Agent without memory"""
            return {"status": "stateless"}
        
        # Agent should not have memory
        assert not hasattr(test_agent, 'memory') or test_agent.memory is None
    
    def test_multiple_agents_shared_memory(self):
        """Test multiple agents sharing memory space"""
        
        memory_config = {
            "backend": "chromadb",
            "storage_path": str(self.temp_path),
            "collection_name": "shared_memories"
        }
        
        @agent("writer_agent", memory=memory_config)
        def writer_agent(spore):
            """Agent that writes memories"""
            message = spore.knowledge.get("message")
            memory_id = writer_agent.remember(message, importance=0.8)
            return {"stored": memory_id}
        
        @agent("reader_agent", memory=memory_config) 
        def reader_agent(spore):
            """Agent that reads memories"""
            query = spore.knowledge.get("query")
            memories = reader_agent.recall(query)
            return {"found": [m.content for m in memories]}
        
        # Writer stores memory
        start_agents(
            writer_agent,
            initial_data={"type": "store", "message": "Shared knowledge about agents"}
        )
        
        # Reader recalls memory
        result = start_agents(
            reader_agent,
            initial_data={"type": "recall", "query": "agents"}
        )
        
        assert "found" in result
        assert len(result["found"]) > 0
        assert "agents" in result["found"][0]
    
    def test_memory_persistence(self):
        """Test memory persists across agent recreations"""
        
        memory_config = {
            "backend": "chromadb", 
            "storage_path": str(self.temp_path),
            "collection_name": "persistent_memories"
        }
        
        # First agent instance
        @agent("persistent_agent_1", memory=memory_config)
        def agent_v1(spore):
            memory_id = agent_v1.remember("Persistent data")
            return {"stored": memory_id}
        
        # Store data
        start_agents(agent_v1, initial_data={"type": "store"})
        
        # Second agent instance (simulating restart)
        @agent("persistent_agent_2", memory=memory_config)
        def agent_v2(spore):
            memories = agent_v2.recall("Persistent")
            return {"recalled": [m.content for m in memories]}
        
        # Recall data
        result = start_agents(agent_v2, initial_data={"type": "recall"})
        
        assert "recalled" in result
        assert len(result["recalled"]) > 0
        assert "Persistent data" in result["recalled"][0]
    
    @pytest.mark.parametrize("backend", ["chromadb", "memory"])
    def test_different_memory_backends(self, backend):
        """Test agents work with different memory backends"""
        
        memory_config = {"backend": backend}
        if backend == "chromadb":
            memory_config["storage_path"] = str(self.temp_path)
        
        @agent("backend_test_agent", memory=memory_config)
        def test_agent(spore):
            test_agent.remember("Backend test data")
            memories = test_agent.recall("Backend test")
            return {
                "backend": backend,
                "memories_found": len(memories)
            }
        
        result = start_agents(
            test_agent,
            initial_data={"type": "test"}
        )
        
        assert result["backend"] == backend
        assert result["memories_found"] >= 1


class TestLightweightSpores:
    """Test lightweight spore references to knowledge"""
    
    def test_spore_with_knowledge_reference(self):
        """Test spores carry references instead of full knowledge"""
        
        @agent("sender", memory=True)
        def sender_agent(spore):
            # Store knowledge and get reference
            knowledge_id = sender_agent.remember("Large dataset about marine biology", importance=0.9)
            
            # Send lightweight reference
            from praval import broadcast
            broadcast({
                "type": "knowledge_reference",
                "knowledge_id": knowledge_id,
                "summary": "Marine biology data available"
            })
            
            return {"sent_reference": knowledge_id}
        
        @agent("receiver", responds_to=["knowledge_reference"], memory=True)
        def receiver_agent(spore):
            knowledge_id = spore.knowledge.get("knowledge_id")
            summary = spore.knowledge.get("summary")
            
            # Retrieve full knowledge using reference
            memories = receiver_agent.recall_by_id(knowledge_id)
            
            return {
                "received_summary": summary,
                "retrieved_knowledge": memories[0].content if memories else None
            }
        
        # Test the communication
        results = start_agents(
            sender_agent,
            receiver_agent,
            initial_data={"type": "test"}
        )
        
        # Verify lightweight communication worked
        assert "sent_reference" in results
        assert "received_summary" in results
        assert results["received_summary"] == "Marine biology data available"
        assert results["retrieved_knowledge"] is not None
    
    def test_spore_size_optimization(self):
        """Test spores remain lightweight with knowledge references"""
        
        @agent("size_test_agent", memory=True)
        def test_agent(spore):
            # Store large content
            large_content = "Very large content " * 1000  # Simulate large data
            knowledge_id = test_agent.remember(large_content, importance=0.8)
            
            # Create spore with reference
            spore_data = {
                "type": "large_data_reference",
                "knowledge_id": knowledge_id,
                "content_size": len(large_content),
                "preview": large_content[:100] + "..."
            }
            
            return spore_data
        
        result = start_agents(
            test_agent,
            initial_data={"type": "test"}
        )
        
        # Verify spore is small but references large content
        assert "knowledge_id" in result
        assert result["content_size"] > 10000  # Large content was stored
        assert len(result["preview"]) < 200  # But spore carries only preview


class TestKnowledgeBaseIndexing:
    """Test automatic knowledge base indexing"""
    
    def setup_method(self):
        """Setup test knowledge base"""
        self.temp_dir = tempfile.mkdtemp()
        self.kb_path = Path(self.temp_dir) / "knowledge_base"
        self.kb_path.mkdir(parents=True)
        
        # Create test files
        (self.kb_path / "coral_facts.txt").write_text(
            "Coral reefs are built by coral polyps.\n"
            "They provide habitat for marine life.\n"
            "Coral bleaching occurs due to temperature changes."
        )
        
        (self.kb_path / "symbiosis.md").write_text(
            "# Symbiosis in Marine Ecosystems\n\n"
            "Coral polyps have symbiotic relationships with zooxanthellae.\n"
            "This relationship provides mutual benefits."
        )
        
        # Create subdirectory
        sub_dir = self.kb_path / "marine_life"
        sub_dir.mkdir()
        (sub_dir / "fish_species.txt").write_text(
            "Clownfish live in sea anemones.\n"
            "They have protective mucus coating."
        )
    
    def teardown_method(self):
        """Cleanup test environment"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_automatic_knowledge_indexing(self):
        """Test knowledge base files are automatically indexed"""
        
        @agent("kb_indexer", 
               memory=True,
               knowledge_base=str(self.kb_path))
        def test_agent(spore):
            # Search for indexed knowledge
            coral_memories = test_agent.recall("coral polyps")
            symbiosis_memories = test_agent.recall("symbiosis")
            
            return {
                "coral_results": len(coral_memories),
                "symbiosis_results": len(symbiosis_memories),
                "sample_content": coral_memories[0].content if coral_memories else None
            }
        
        result = start_agents(
            test_agent,
            initial_data={"type": "search"}
        )
        
        assert result["coral_results"] > 0
        assert result["symbiosis_results"] > 0
        assert "polyps" in result["sample_content"]
    
    def test_knowledge_base_file_types(self):
        """Test different file types are indexed correctly"""
        
        @agent("file_type_tester",
               memory=True, 
               knowledge_base=str(self.kb_path))
        def test_agent(spore):
            txt_results = test_agent.recall("coral facts")
            md_results = test_agent.recall("Marine Ecosystems")
            fish_results = test_agent.recall("clownfish")
            
            return {
                "txt_indexed": len(txt_results) > 0,
                "md_indexed": len(md_results) > 0,
                "subdirectory_indexed": len(fish_results) > 0
            }
        
        result = start_agents(
            test_agent,
            initial_data={"type": "file_test"}
        )
        
        assert result["txt_indexed"]
        assert result["md_indexed"] 
        assert result["subdirectory_indexed"]
    
    @patch.dict('os.environ', {'PRAVAL_KNOWLEDGE_BASE': '/test/kb/path'})
    def test_knowledge_base_from_env(self):
        """Test knowledge base path from environment variable"""
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('pathlib.Path.glob') as mock_glob:
            
            mock_glob.return_value = [Path('/test/kb/path/test.txt')]
            
            @agent("env_kb_agent", memory=True)  # No explicit knowledge_base
            def test_agent(spore):
                return {"kb_configured": hasattr(test_agent, 'knowledge_base')}
            
            result = start_agents(
                test_agent,
                initial_data={"type": "env_test"}
            )
            
            # Agent should have configured knowledge base from env
            assert result["kb_configured"]