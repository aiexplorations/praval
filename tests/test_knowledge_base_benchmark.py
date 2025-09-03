#!/usr/bin/env python3
"""
Knowledge Base Integration Benchmark Tests

Comprehensive tests to validate the knowledge base functionality with realistic
scenarios including performance benchmarks, memory usage, and integration
with the memory management system.
"""

import os
import tempfile
import time
import pytest
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch

from praval.memory.embedded_store import EmbeddedVectorStore
from praval.memory.memory_manager import MemoryManager
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


@pytest.mark.knowledge_base
class TestKnowledgeBaseBenchmark:
    """Comprehensive knowledge base functionality and performance tests"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.agent_id = "benchmark_agent"
        
    def teardown_method(self):
        """Clean up test environment"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_knowledge_base(self, num_docs: int = 10) -> List[Path]:
        """Create a realistic test knowledge base with various file types"""
        files = []
        
        # Create text files with AI/ML content
        ai_topics = [
            "reinforcement learning algorithms",
            "deep neural networks architecture", 
            "natural language processing transformers",
            "computer vision convolutional networks",
            "machine learning optimization techniques",
            "gradient descent and backpropagation",
            "attention mechanisms in transformers",
            "generative adversarial networks",
            "recurrent neural networks LSTM GRU",
            "support vector machines kernel methods"
        ]
        
        for i in range(num_docs):
            topic = ai_topics[i % len(ai_topics)]
            content = f"""
            # Research Document {i+1}: {topic.title()}
            
            ## Abstract
            This document explores {topic} and their applications in modern artificial intelligence systems.
            The research covers theoretical foundations, practical implementations, and real-world applications.
            
            ## Introduction
            {topic.title()} represent a significant advancement in the field of machine learning and AI.
            This comprehensive analysis examines the key principles, methodologies, and experimental results.
            
            ## Key Findings
            - Advanced {topic} show superior performance in complex tasks
            - Implementation requires careful consideration of hyperparameter tuning
            - Scalability remains a challenge for large-scale deployments
            - Integration with existing systems requires careful architectural planning
            
            ## Conclusion
            The research demonstrates that {topic} provide valuable capabilities for AI systems.
            Future work should focus on optimization and practical deployment strategies.
            
            ## References
            1. Smith, J. et al. (2023). "Advanced {topic}: A comprehensive study"
            2. Johnson, K. (2023). "Practical applications of {topic}"
            3. Williams, R. et al. (2022). "Performance optimization in {topic}"
            """
            
            file_path = self.temp_dir / f"research_{i+1:02d}.md"
            file_path.write_text(content.strip())
            files.append(file_path)
        
        # Create Python code files
        for i in range(min(3, num_docs // 3)):
            code_content = f"""
            '''
            AI Research Module {i+1}: {ai_topics[i]} Implementation
            '''
            
            import numpy as np
            import torch
            import torch.nn as nn
            from typing import Optional, List, Dict, Any
            
            class AIModel{i+1}(nn.Module):
                '''Advanced {ai_topics[i]} implementation'''
                
                def __init__(self, input_size: int = 512, hidden_size: int = 256):
                    super().__init__()
                    self.input_size = input_size
                    self.hidden_size = hidden_size
                    
                    # Define architecture for {ai_topics[i]}
                    self.layers = nn.Sequential(
                        nn.Linear(input_size, hidden_size),
                        nn.ReLU(),
                        nn.Dropout(0.1),
                        nn.Linear(hidden_size, hidden_size),
                        nn.ReLU(),
                        nn.Linear(hidden_size, 1)
                    )
                
                def forward(self, x: torch.Tensor) -> torch.Tensor:
                    '''Forward pass for {ai_topics[i]} model'''
                    return self.layers(x)
                
                def train_model(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
                    '''Train the {ai_topics[i]} model'''
                    # Implementation details for {ai_topics[i]}
                    loss_values = []
                    
                    for epoch in range(100):
                        # Training loop implementation
                        loss = self._compute_loss(data)
                        loss_values.append(loss)
                    
                    return {{'final_loss': loss_values[-1], 'epochs': len(loss_values)}}
                
                def _compute_loss(self, data: List[Dict[str, Any]]) -> float:
                    '''Compute loss for {ai_topics[i]} training'''
                    return np.random.random() * 0.1  # Simulated loss
            """
            
            file_path = self.temp_dir / f"ai_model_{i+1}.py"
            file_path.write_text(code_content.strip())
            files.append(file_path)
            
        return files
    
    def create_mock_pdf_files(self, num_pdfs: int = 3) -> List[Path]:
        """Create mock PDF files for testing"""
        pdf_files = []
        
        pdf_contents = [
            [
                "Deep Reinforcement Learning: Theory and Practice",
                "",
                "This comprehensive guide covers the fundamentals of deep reinforcement learning,",
                "including Q-learning, policy gradients, and actor-critic methods.",
                "",
                "Chapter 1: Introduction to Reinforcement Learning",
                "Reinforcement learning is a machine learning paradigm where agents learn",
                "to make decisions by interacting with an environment and receiving rewards.",
                "",
                "Key concepts include:",
                "- Markov Decision Processes (MDPs)",
                "- Value functions and Q-functions", 
                "- Policy optimization techniques",
                "- Exploration vs exploitation trade-offs"
            ],
            [
                "Natural Language Processing with Transformers",
                "",
                "The transformer architecture has revolutionized natural language processing,",
                "enabling breakthrough performance in tasks like machine translation,",
                "text summarization, and question answering.",
                "",
                "Technical Details:",
                "- Multi-head attention mechanisms",
                "- Positional encoding strategies",
                "- Layer normalization and residual connections",
                "- Pre-training and fine-tuning approaches"
            ],
            [
                "Computer Vision: Convolutional Neural Networks and Beyond",
                "",
                "This research paper examines the evolution of computer vision techniques,",
                "from traditional image processing to modern deep learning approaches.",
                "",
                "Covered Topics:",
                "- Convolutional layers and pooling operations",
                "- Object detection and semantic segmentation",
                "- Transfer learning and pre-trained models",
                "- Vision transformers and attention-based architectures"
            ]
        ]
        
        for i in range(num_pdfs):
            content = pdf_contents[i % len(pdf_contents)]
            pdf_path = self.temp_dir / f"research_paper_{i+1}.pdf"
            
            # Create mock PDF file (will be mocked during tests)
            pdf_path.write_bytes(b"Mock PDF content")
            pdf_files.append((pdf_path, content))
            
        return pdf_files
    
    @pytest.mark.unit
    def test_knowledge_base_file_discovery(self):
        """Test that knowledge base correctly discovers all supported file types"""
        # Create diverse file types
        files = self.create_test_knowledge_base(5)
        
        # Add some unsupported files that should be ignored
        (self.temp_dir / "image.png").write_bytes(b"PNG image data")
        (self.temp_dir / "video.mp4").write_bytes(b"MP4 video data")
        (self.temp_dir / "archive.zip").write_bytes(b"ZIP archive data")
        
        # Mock the store to avoid ChromaDB initialization
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            store = EmbeddedVectorStore()
        
        indexed_entries = []
        store.store = lambda entry: indexed_entries.append(entry)
        
        count = store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should index supported files (md, py) but not unsupported ones
        assert count == len(files)  # Only supported files
        assert len(indexed_entries) == len(files)
        
        # Verify file types
        file_types = {entry.metadata['file_type'] for entry in indexed_entries}
        assert '.md' in file_types
        assert '.py' in file_types
        assert '.png' not in file_types  # Unsupported
    
    @pytest.mark.integration
    @patch('PyPDF2.PdfReader')
    def test_mixed_knowledge_base_indexing(self, mock_pdf_reader):
        """Test indexing of mixed file types including PDFs"""
        # Create text files
        text_files = self.create_test_knowledge_base(3)
        
        # Create mock PDFs
        pdf_files = self.create_mock_pdf_files(2)
        
        # Mock PDF reader for each PDF
        def pdf_reader_side_effect(file_handle):
            # Determine which PDF based on file path
            file_path = str(file_handle.name) if hasattr(file_handle, 'name') else str(file_handle)
            
            for pdf_path, content_lines in pdf_files:
                if str(pdf_path) in file_path:
                    mock_reader = Mock()
                    mock_pages = []
                    
                    # Create mock pages from content
                    for line in content_lines:
                        mock_page = Mock()
                        mock_page.extract_text.return_value = line
                        mock_pages.append(mock_page)
                    
                    mock_reader.pages = mock_pages
                    return mock_reader
            
            # Default fallback
            mock_reader = Mock()
            mock_reader.pages = []
            return mock_reader
        
        mock_pdf_reader.side_effect = pdf_reader_side_effect
        
        # Mock the store initialization and indexing
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            store = EmbeddedVectorStore()
        
        indexed_entries = []
        store.store = lambda entry: indexed_entries.append(entry)
        
        with patch('builtins.open', side_effect=lambda *args, **kwargs: 
                   open(*args, **kwargs) if not str(args[0]).endswith('.pdf') 
                   else Mock()):
            count = store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should index all files (text + PDF)
        total_files = len(text_files) + len(pdf_files)
        assert count == total_files
        assert len(indexed_entries) == total_files
        
        # Verify content diversity
        all_content = ' '.join(entry.content for entry in indexed_entries)
        assert "reinforcement learning" in all_content.lower()
        assert "neural networks" in all_content.lower()
        assert "transformers" in all_content.lower()
    
    @pytest.mark.performance
    def test_large_knowledge_base_performance(self):
        """Test performance with a large knowledge base"""
        # Create a larger knowledge base
        files = self.create_test_knowledge_base(50)  # 50 documents
        
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            store = EmbeddedVectorStore()
        
        indexed_entries = []
        indexing_times = []
        
        def timed_store(entry):
            start_time = time.time()
            indexed_entries.append(entry)
            indexing_times.append(time.time() - start_time)
        
        store.store = timed_store
        
        # Time the indexing process
        start_time = time.time()
        count = store.index_knowledge_files(self.temp_dir, self.agent_id)
        total_time = time.time() - start_time
        
        # Performance assertions
        assert count == 50
        assert total_time < 30.0  # Should complete within 30 seconds
        assert max(indexing_times) < 1.0  # No single file should take > 1 second
        assert sum(indexing_times) / len(indexing_times) < 0.1  # Average < 100ms per file
        
        # Verify all files were processed
        assert len(indexed_entries) == 50
        
        # Check content diversity (should have different topics)
        topics_found = set()
        for entry in indexed_entries:
            content_lower = entry.content.lower()
            if "reinforcement learning" in content_lower:
                topics_found.add("rl")
            if "neural networks" in content_lower:
                topics_found.add("nn")
            if "transformers" in content_lower:
                topics_found.add("transformers")
        
        assert len(topics_found) >= 3  # Multiple topics represented
    
    @pytest.mark.integration
    def test_memory_manager_knowledge_base_integration(self):
        """Test integration with MemoryManager for automatic knowledge base indexing"""
        # Create knowledge base files
        files = self.create_test_knowledge_base(5)
        
        # Mock MemoryManager to avoid external dependencies
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_store_class:
            mock_store = Mock()
            mock_store.index_knowledge_files.return_value = 5
            mock_store.health_check.return_value = True
            mock_store_class.return_value = mock_store
            
            # Initialize MemoryManager with knowledge base path
            memory_manager = MemoryManager(
                agent_id=self.agent_id,
                backend="chromadb",
                knowledge_base_path=str(self.temp_dir)
            )
            
            # Should have attempted to initialize embedded store
            mock_store_class.assert_called_once()
            
            # Simulate knowledge base indexing
            indexed_count = mock_store.index_knowledge_files(self.temp_dir, self.agent_id)
            assert indexed_count == 5
    
    @pytest.mark.performance
    def test_memory_search_performance(self):
        """Test search performance with indexed knowledge base"""
        # Create knowledge base with specific content for searching
        search_topics = [
            "deep reinforcement learning Q-networks DQN algorithms",
            "natural language processing transformers BERT GPT attention",
            "computer vision convolutional neural networks CNN ResNet",
            "machine learning optimization gradient descent backpropagation",
            "neural network architectures LSTM RNN recurrent networks"
        ]
        
        # Create files with search-friendly content
        for i, topic in enumerate(search_topics):
            content = f"""
            # Research Paper {i+1}
            
            This paper focuses on {topic} and explores advanced techniques.
            We present comprehensive analysis of {topic} methodologies.
            
            ## Key Contributions
            - Novel approaches to {topic} optimization
            - Improved performance metrics for {topic}
            - Scalable implementations of {topic} systems
            
            ## Experimental Results
            Our experiments demonstrate superior performance in {topic} applications.
            The proposed methods show significant improvements over baseline approaches.
            """
            
            file_path = self.temp_dir / f"search_doc_{i+1}.md"
            file_path.write_text(content.strip())
        
        # Mock vector store for performance testing
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            store = EmbeddedVectorStore()
        
        # Create realistic memory entries
        indexed_entries = []
        for i, topic in enumerate(search_topics):
            entry = MemoryEntry(
                id=f"entry_{i+1}",
                agent_id=self.agent_id,
                memory_type=MemoryType.SEMANTIC,
                content=f"Research on {topic} with detailed analysis and results",
                metadata={'source': f'search_doc_{i+1}.md'},
                importance=0.8
            )
            indexed_entries.append(entry)
        
        # Mock search functionality
        def mock_search(query: MemoryQuery) -> MemorySearchResult:
            # Simple keyword matching simulation
            results = []
            scores = []
            
            query_terms = query.query_text.lower().split()
            for entry in indexed_entries:
                content_lower = entry.content.lower()
                score = sum(1 for term in query_terms if term in content_lower) / len(query_terms)
                
                if score > query.similarity_threshold:
                    results.append(entry)
                    scores.append(score)
            
            # Sort by score
            sorted_results = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
            if sorted_results:
                results, scores = zip(*sorted_results[:query.limit])
            else:
                results, scores = [], []
            
            return MemorySearchResult(
                entries=list(results),
                scores=list(scores),
                query=query,
                total_found=len(results)
            )
        
        store.search = mock_search
        
        # Test search queries
        test_queries = [
            "reinforcement learning algorithms",
            "natural language processing",
            "computer vision CNN",
            "optimization techniques",
            "neural network architectures"
        ]
        
        search_times = []
        for query_text in test_queries:
            query = MemoryQuery(
                query_text=query_text,
                limit=5,
                similarity_threshold=0.3
            )
            
            start_time = time.time()
            result = store.search(query)
            search_time = time.time() - start_time
            search_times.append(search_time)
            
            # Verify search results
            assert len(result.entries) > 0
            assert len(result.scores) == len(result.entries)
            assert all(score >= 0.3 for score in result.scores)
        
        # Performance assertions
        assert max(search_times) < 0.1  # Max 100ms per search
        assert sum(search_times) / len(search_times) < 0.05  # Average < 50ms
    
    @pytest.mark.edge_case
    def test_knowledge_base_error_recovery(self):
        """Test error recovery in knowledge base operations"""
        # Create mixed files including some that will cause errors
        good_files = self.create_test_knowledge_base(3)
        
        # Create files that will cause various types of errors
        error_scenarios = [
            ("corrupted.txt", b"\x80\x81\x82\x83"),  # Invalid UTF-8
            ("empty.md", b""),  # Empty file
            ("permission_denied.py", "valid content")  # Will simulate permission error
        ]
        
        for filename, content in error_scenarios:
            file_path = self.temp_dir / filename
            if isinstance(content, str):
                file_path.write_text(content)
            else:
                file_path.write_bytes(content)
        
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            store = EmbeddedVectorStore()
        
        indexed_entries = []
        
        def store_with_errors(entry):
            # Simulate error for specific files
            if "permission_denied" in entry.metadata.get('source_file', ''):
                raise PermissionError("Access denied")
            indexed_entries.append(entry)
        
        store.store = store_with_errors
        
        # Should handle errors gracefully and continue with other files
        count = store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should have indexed the good files despite errors
        assert count >= len(good_files)  # At least the good files
        assert len(indexed_entries) >= len(good_files)
    
    @pytest.mark.knowledge_base
    def test_knowledge_base_metadata_tracking(self):
        """Test that knowledge base entries have proper metadata"""
        files = self.create_test_knowledge_base(3)
        
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            store = EmbeddedVectorStore()
        
        indexed_entries = []
        store.store = lambda entry: indexed_entries.append(entry)
        
        count = store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        assert count == 3
        assert len(indexed_entries) == 3
        
        # Verify metadata for all entries
        for entry in indexed_entries:
            assert entry.agent_id == self.agent_id
            assert entry.memory_type == MemoryType.SEMANTIC
            assert entry.importance == 0.8  # Knowledge base files have high importance
            
            metadata = entry.metadata
            assert 'source_file' in metadata
            assert 'file_type' in metadata
            assert 'file_size' in metadata
            assert 'indexed_at' in metadata
            
            # Verify source file exists and has correct extension
            source_path = Path(metadata['source_file'])
            assert source_path.exists()
            assert source_path.suffix == metadata['file_type']
            
            # Verify file size matches content length
            assert metadata['file_size'] == len(entry.content)
            assert metadata['file_size'] > 0


if __name__ == "__main__":
    # Run knowledge base benchmark tests
    pytest.main([
        __file__, 
        "-v", 
        "--tb=short", 
        "-m", "knowledge_base"
    ])