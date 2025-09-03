#!/usr/bin/env python3
"""
Integration tests for PDF knowledge base using actual PDF files.

This creates real PDFs and tests the complete pipeline:
1. PDF creation
2. Text extraction  
3. Knowledge base indexing
4. Memory search and retrieval
"""

import os
import tempfile
import pytest
from pathlib import Path

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from praval.memory.embedded_store import EmbeddedVectorStore
from praval.memory.memory_types import MemoryEntry, MemoryType


def create_test_pdf(content_lines: list, output_path: Path):
    """Create a real PDF file with given content for testing"""
    if not REPORTLAB_AVAILABLE:
        pytest.skip("ReportLab not available for PDF creation")
    
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    y_position = height - 50  # Start near top
    line_height = 20
    
    for line in content_lines:
        if y_position < 50:  # Start new page if needed
            c.showPage()
            y_position = height - 50
        
        c.drawString(50, y_position, line)
        y_position -= line_height
    
    c.save()


class TestPDFIntegration:
    """Integration tests using real PDF files"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.store = EmbeddedVectorStore()
        self.agent_id = "test_integration_agent"
        
    def teardown_method(self):
        """Clean up test environment"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="ReportLab not available")
    @pytest.mark.integration
    def test_create_and_index_real_pdf(self):
        """Test creating and indexing a real PDF file"""
        # Create PDF with reinforcement learning content
        pdf_content = [
            "Reinforcement Learning: An Introduction",
            "",
            "Deep Q-Networks (DQN) represent a significant advancement in reinforcement learning.",
            "The algorithm combines Q-learning with deep neural networks to handle complex state spaces.",
            "",
            "Key components of DQN include:",
            "1. Experience replay buffer for storing and sampling past experiences",
            "2. Target network for stable training",
            "3. Deep neural network for Q-value approximation",
            "",
            "The Rainbow algorithm further improves upon DQN by combining multiple enhancements:",
            "- Prioritized experience replay",
            "- Double Q-learning", 
            "- Dueling network architecture",
            "- Multi-step learning",
            "- Distributional reinforcement learning",
            "- Noisy networks",
            "",
            "These improvements lead to more sample-efficient and stable learning in various environments."
        ]
        
        pdf_path = self.temp_dir / "rl_research.pdf"
        create_test_pdf(pdf_content, pdf_path)
        
        # Verify PDF was created
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0
        
        # Test text extraction
        extracted_text = self.store._extract_pdf_text(pdf_path)
        
        assert len(extracted_text) > 100
        assert "Reinforcement Learning" in extracted_text
        assert "Deep Q-Networks" in extracted_text  
        assert "Rainbow algorithm" in extracted_text
        assert "experience replay" in extracted_text
        
    @pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="ReportLab not available")
    @pytest.mark.integration
    def test_knowledge_base_indexing_real_pdf(self):
        """Test complete knowledge base indexing with real PDF"""
        # Create multiple PDFs with different content
        dqn_content = [
            "Playing Atari with Deep Reinforcement Learning",
            "We present the first deep learning model to successfully learn control policies",
            "directly from high-dimensional sensory input using reinforcement learning.",
            "The model is a convolutional neural network, trained with a variant of Q-learning,",
            "whose input is raw pixels and whose output is a value function estimating future rewards."
        ]
        
        ppo_content = [
            "Proximal Policy Optimization Algorithms", 
            "We propose a new family of policy gradient methods for reinforcement learning,",
            "which alternate between sampling data through interaction with the environment",
            "and optimizing a surrogate objective function using stochastic gradient ascent.",
            "PPO strikes a balance between ease of implementation, sample complexity, and ease of tuning."
        ]
        
        # Create PDFs
        dqn_pdf = self.temp_dir / "dqn_paper.pdf"
        ppo_pdf = self.temp_dir / "ppo_paper.pdf"
        
        create_test_pdf(dqn_content, dqn_pdf)
        create_test_pdf(ppo_content, ppo_pdf)
        
        # Index the knowledge base
        indexed_entries = []
        original_store = self.store.store
        self.store.store = lambda entry: indexed_entries.append(entry)
        
        count = self.store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Verify indexing results
        assert count == 2
        assert len(indexed_entries) == 2
        
        # Check that content was properly extracted and indexed
        contents = [entry.content for entry in indexed_entries]
        
        assert any("Deep Reinforcement Learning" in content for content in contents)
        assert any("Proximal Policy Optimization" in content for content in contents)
        assert any("Q-learning" in content for content in contents)
        assert any("policy gradient" in content for content in contents)
        
        # Check metadata
        for entry in indexed_entries:
            assert entry.agent_id == self.agent_id
            assert entry.memory_type == MemoryType.SEMANTIC
            assert entry.importance == 0.8
            assert entry.metadata['file_type'] == '.pdf'
            assert 'source_file' in entry.metadata
            assert 'indexed_at' in entry.metadata
    
    @pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="ReportLab not available")
    @pytest.mark.integration 
    def test_mixed_file_types_knowledge_base(self):
        """Test knowledge base with mixed PDF and text files"""
        # Create a text file
        text_file = self.temp_dir / "notes.txt"
        text_file.write_text(
            "Research Notes on Reinforcement Learning\n\n"
            "Key algorithms include Q-learning, SARSA, and Actor-Critic methods.\n"
            "Modern deep RL uses neural networks to approximate value functions."
        )
        
        # Create a PDF file
        pdf_content = [
            "Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning",
            "Model-free deep reinforcement learning algorithms have been demonstrated",
            "on a range of challenging decision making and control tasks.",
            "However, these methods typically suffer from very high sample complexity."
        ]
        
        pdf_file = self.temp_dir / "sac_paper.pdf"
        create_test_pdf(pdf_content, pdf_file)
        
        # Index mixed knowledge base
        indexed_entries = []
        self.store.store = lambda entry: indexed_entries.append(entry)
        
        count = self.store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should index both file types
        assert count == 2
        assert len(indexed_entries) == 2
        
        # Verify different file types were processed
        file_types = [entry.metadata['file_type'] for entry in indexed_entries]
        assert '.txt' in file_types
        assert '.pdf' in file_types
        
        # Verify content from both sources
        all_content = ' '.join(entry.content for entry in indexed_entries)
        assert "Research Notes" in all_content  # From text file
        assert "Soft Actor-Critic" in all_content  # From PDF file
        assert "Q-learning" in all_content  # From text file
        assert "sample complexity" in all_content  # From PDF file
    
    @pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="ReportLab not available") 
    @pytest.mark.integration
    def test_pdf_text_cleaning_integration(self):
        """Test that PDF text cleaning works with real extracted content"""
        # Create PDF with content that needs cleaning
        messy_content = [
            "Paper Title: Advanced RL Methods",
            "",
            "Visit   https://example.com   for   more   info",
            "Contact  author@university.edu  for  questions", 
            "This...has...too...many...dots",
            "And-----too-----many-----dashes",
            "   Excessive   whitespace   everywhere   "
        ]
        
        pdf_path = self.temp_dir / "messy.pdf"
        create_test_pdf(messy_content, pdf_path)
        
        # Extract and clean text
        extracted_text = self.store._extract_pdf_text(pdf_path)
        
        # Verify cleaning worked
        assert "[URL]" in extracted_text
        assert "[EMAIL]" in extracted_text
        assert "https://example.com" not in extracted_text
        assert "author@university.edu" not in extracted_text
        assert "..." in extracted_text and "....." not in extracted_text
        assert "---" in extracted_text and "-----" not in extracted_text
        
        # Should still preserve actual content
        assert "Advanced RL Methods" in extracted_text
        assert "Paper Title" in extracted_text


@pytest.fixture(scope="session", autouse=True)
def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import PyPDF2
    except ImportError:
        pytest.skip("PyPDF2 not available", allow_module_level=True)


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])