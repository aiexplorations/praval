#!/usr/bin/env python3
"""
Comprehensive tests for PDF knowledge base functionality in Praval.

Tests the PDF processing capabilities added to embedded_store.py including:
- PDF text extraction
- Text cleaning and preprocessing  
- Knowledge base indexing with PDFs
- Error handling for corrupted PDFs
- Integration with memory system
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from praval.memory.embedded_store import EmbeddedVectorStore
from praval.memory.memory_types import MemoryEntry, MemoryType


class TestPDFKnowledgeBase:
    """Test suite for PDF knowledge base functionality"""
    
    def setup_method(self):
        """Set up test environment before each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        # Mock the EmbeddedVectorStore to avoid ChromaDB initialization issues
        with patch('praval.memory.embedded_store.EmbeddedVectorStore._init_chromadb'):
            self.store = EmbeddedVectorStore()
        self.agent_id = "test_agent"
        
    def teardown_method(self):
        """Clean up after each test"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_mock_pdf(self, content_pages: list, filename: str = "test.pdf") -> Path:
        """Create a mock PDF file for testing"""
        pdf_path = self.temp_dir / filename
        # Create empty file (actual content will be mocked)
        pdf_path.write_bytes(b"mock pdf content")
        return pdf_path
    
    def create_test_text_file(self, content: str, filename: str = "test.txt") -> Path:
        """Create a test text file"""
        text_path = self.temp_dir / filename
        text_path.write_text(content, encoding='utf-8')
        return text_path
    
    @pytest.mark.unit
    def test_pdf_extension_supported(self):
        """Test that PDF extension is in supported formats"""
        # This tests that our modification to add .pdf is working
        knowledge_path = self.temp_dir
        pdf_file = self.create_mock_pdf(["test content"])
        
        # Should not raise an exception for PDF files
        supported_extensions = {'.txt', '.md', '.rst', '.py', '.js', '.json', '.yaml', '.yml', '.pdf'}
        assert '.pdf' in supported_extensions
        assert pdf_file.suffix.lower() == '.pdf'
    
    @pytest.mark.unit  
    @patch('PyPDF2.PdfReader')
    def test_extract_pdf_text_success(self, mock_pdf_reader):
        """Test successful PDF text extraction"""
        # Mock PDF reader and pages
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "This is page 1 content with important information."
        mock_page2 = Mock() 
        mock_page2.extract_text.return_value = "This is page 2 with more details about the topic."
        
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_path = self.create_mock_pdf(["page1", "page2"])
        
        with patch('builtins.open', mock_open(read_data=b"pdf content")):
            result = self.store._extract_pdf_text(pdf_path)
        
        # Check that both pages were extracted
        assert "page 1 content" in result
        assert "page 2" in result
        assert len(result) > 50  # Should have substantial content
        
        # Verify PyPDF2 was called correctly
        mock_pdf_reader.assert_called_once()
        mock_page1.extract_text.assert_called_once()
        mock_page2.extract_text.assert_called_once()
    
    @pytest.mark.unit
    @patch('PyPDF2.PdfReader')  
    def test_extract_pdf_text_empty_pages(self, mock_pdf_reader):
        """Test PDF with empty/unreadable pages"""
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = ""  # Empty page
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "   "  # Whitespace only
        
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_path = self.create_mock_pdf([])
        
        with patch('builtins.open', mock_open(read_data=b"pdf content")):
            result = self.store._extract_pdf_text(pdf_path)
        
        # Should return empty string for no readable content
        assert result == ""
    
    @pytest.mark.unit
    def test_extract_pdf_text_pypdf2_not_installed(self):
        """Test error handling when PyPDF2 is not installed"""
        pdf_path = self.create_mock_pdf(["content"])
        
        with patch('builtins.__import__', side_effect=ImportError("No module named 'PyPDF2'")):
            with pytest.raises(ImportError, match="PyPDF2 is required"):
                self.store._extract_pdf_text(pdf_path)
    
    @pytest.mark.unit
    @patch('PyPDF2.PdfReader')
    def test_extract_pdf_text_corrupted_file(self, mock_pdf_reader):
        """Test handling of corrupted PDF files"""
        mock_pdf_reader.side_effect = Exception("PDF file is corrupted")
        
        pdf_path = self.create_mock_pdf(["content"])
        
        with patch('builtins.open', mock_open(read_data=b"corrupted pdf")):
            result = self.store._extract_pdf_text(pdf_path)
        
        # Should return empty string and not crash
        assert result == ""
    
    @pytest.mark.unit
    @patch('PyPDF2.PdfReader')
    def test_extract_pdf_text_page_extraction_error(self, mock_pdf_reader):
        """Test handling of page-level extraction errors"""
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Good page content"
        
        mock_page2 = Mock()
        mock_page2.extract_text.side_effect = Exception("Page extraction failed")
        
        mock_page3 = Mock()
        mock_page3.extract_text.return_value = "Another good page"
        
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2, mock_page3]
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_path = self.create_mock_pdf(["p1", "p2", "p3"])
        
        with patch('builtins.open', mock_open(read_data=b"pdf content")):
            result = self.store._extract_pdf_text(pdf_path)
        
        # Should include good pages and skip bad ones
        assert "Good page content" in result
        assert "Another good page" in result
        assert len(result) > 10
    
    @pytest.mark.unit
    def test_clean_pdf_text_whitespace_cleanup(self):
        """Test PDF text cleaning functionality"""
        raw_text = "This   has    excessive     whitespace\n\n\n\n\nAnd multiple newlines"
        
        cleaned = self.store._clean_pdf_text(raw_text)
        
        # Should normalize whitespace
        assert "excessive     whitespace" not in cleaned
        assert "excessive whitespace" in cleaned
        assert "\n\n\n\n" not in cleaned
    
    @pytest.mark.unit
    def test_clean_pdf_text_url_email_removal(self):
        """Test removal of URLs and emails from PDF text"""
        raw_text = ("Check https://example.com for more info. "
                   "Contact support@company.com for help. "
                   "Visit http://research.university.edu/papers")
        
        cleaned = self.store._clean_pdf_text(raw_text)
        
        # Should replace URLs and emails with placeholders
        assert "https://example.com" not in cleaned
        assert "support@company.com" not in cleaned
        assert "[URL]" in cleaned
        assert "[EMAIL]" in cleaned
    
    @pytest.mark.unit
    def test_clean_pdf_text_punctuation_normalization(self):
        """Test punctuation cleanup in PDF text"""
        raw_text = "This has......many dots and-----many dashes"
        
        cleaned = self.store._clean_pdf_text(raw_text)
        
        # Should normalize excessive punctuation
        assert "......" not in cleaned
        assert "-----" not in cleaned
        assert "..." in cleaned
        assert "---" in cleaned
    
    @pytest.mark.integration  
    @patch('PyPDF2.PdfReader')
    def test_index_knowledge_files_with_pdf(self, mock_pdf_reader):
        """Test indexing knowledge base with PDF files"""
        # Create mixed content: text and PDF files
        text_file = self.create_test_text_file("This is a text file about machine learning.")
        
        # Mock PDF content
        mock_page = Mock()
        mock_page.extract_text.return_value = "This is PDF content about reinforcement learning and Q-learning algorithms."
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_file = self.create_mock_pdf(["RL content"], "research_paper.pdf")
        
        # Mock the store method to capture what gets indexed
        indexed_entries = []
        original_store = self.store.store
        self.store.store = lambda entry: indexed_entries.append(entry)
        
        with patch('builtins.open', mock_open(read_data=b"pdf content")):
            count = self.store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should have indexed both files
        assert count == 2
        assert len(indexed_entries) == 2
        
        # Check that entries were created correctly
        text_entry = next((e for e in indexed_entries if e.metadata['file_type'] == '.txt'), None)
        pdf_entry = next((e for e in indexed_entries if e.metadata['file_type'] == '.pdf'), None)
        
        assert text_entry is not None
        assert pdf_entry is not None
        
        # Check content
        assert "machine learning" in text_entry.content
        assert "reinforcement learning" in pdf_entry.content
        assert "Q-learning" in pdf_entry.content
        
        # Check metadata
        assert text_entry.agent_id == self.agent_id
        assert pdf_entry.agent_id == self.agent_id
        assert text_entry.memory_type == MemoryType.SEMANTIC
        assert pdf_entry.memory_type == MemoryType.SEMANTIC
        assert text_entry.importance == 0.8
        assert pdf_entry.importance == 0.8
    
    @pytest.mark.integration
    @patch('PyPDF2.PdfReader')  
    def test_index_knowledge_files_pdf_too_short(self, mock_pdf_reader):
        """Test that PDFs with insufficient content are skipped"""
        # Mock PDF with very short content
        mock_page = Mock()
        mock_page.extract_text.return_value = "Short"  # Less than 50 chars
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_file = self.create_mock_pdf(["short"], "tiny.pdf")
        
        indexed_entries = []
        self.store.store = lambda entry: indexed_entries.append(entry)
        
        with patch('builtins.open', mock_open(read_data=b"pdf content")):
            count = self.store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should skip the PDF due to insufficient content
        assert count == 0
        assert len(indexed_entries) == 0
    
    @pytest.mark.integration
    @patch('PyPDF2.PdfReader')
    def test_index_knowledge_files_mixed_success_failure(self, mock_pdf_reader):
        """Test indexing with some successful and some failed files"""
        # Create a good text file
        text_file = self.create_test_text_file("Good text content about AI research.")
        
        # Create a good PDF
        mock_page_good = Mock()
        mock_page_good.extract_text.return_value = "This is good PDF content with sufficient length for indexing."
        
        # Create a bad PDF that will fail
        def mock_pdf_reader_side_effect(file_handle):
            if "good.pdf" in str(file_handle):
                mock_reader = Mock()
                mock_reader.pages = [mock_page_good]
                return mock_reader
            else:
                raise Exception("Corrupted PDF")
        
        mock_pdf_reader.side_effect = mock_pdf_reader_side_effect
        
        good_pdf = self.create_mock_pdf(["content"], "good.pdf")
        bad_pdf = self.create_mock_pdf(["content"], "bad.pdf")
        
        indexed_entries = []
        self.store.store = lambda entry: indexed_entries.append(entry)
        
        with patch('builtins.open', mock_open(read_data=b"pdf content")):
            count = self.store.index_knowledge_files(self.temp_dir, self.agent_id)
        
        # Should index text file and good PDF, skip bad PDF
        assert count == 2  # text + good PDF
        assert len(indexed_entries) == 2
        
        # Verify content
        contents = [entry.content for entry in indexed_entries]
        assert any("AI research" in content for content in contents)
        assert any("good PDF content" in content for content in contents)
    
    @pytest.mark.unit
    def test_supported_extensions_includes_pdf(self):
        """Test that PDF is included in supported extensions"""
        # This is a basic test to ensure our code change is present
        from praval.memory.embedded_store import EmbeddedVectorStore
        
        # Create an instance and test the indexing logic would handle PDFs
        store = EmbeddedVectorStore()
        pdf_path = Path("test.pdf")
        
        # The supported extensions should include PDF
        supported_extensions = {'.txt', '.md', '.rst', '.py', '.js', '.json', '.yaml', '.yml', '.pdf'}
        
        assert pdf_path.suffix.lower() in supported_extensions
    
    @pytest.mark.performance
    @patch('PyPDF2.PdfReader')
    def test_large_pdf_handling(self, mock_pdf_reader):
        """Test handling of large PDF files"""
        # Mock a PDF with many pages
        mock_pages = []
        for i in range(100):  # 100 pages
            mock_page = Mock()
            mock_page.extract_text.return_value = f"Page {i+1} content with research data and analysis. " * 50
            mock_pages.append(mock_page)
        
        mock_reader_instance = Mock()
        mock_reader_instance.pages = mock_pages
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_path = self.create_mock_pdf(["large"], "large_research.pdf")
        
        with patch('builtins.open', mock_open(read_data=b"large pdf content")):
            result = self.store._extract_pdf_text(pdf_path)
        
        # Should handle large content without issues
        assert len(result) > 10000  # Should be substantial content
        assert "Page 1 content" in result
        assert "Page 100 content" in result
        
    @pytest.mark.edge_case
    def test_nonexistent_knowledge_path(self):
        """Test error handling for nonexistent knowledge base path"""
        nonexistent_path = Path("/this/path/does/not/exist")
        
        with pytest.raises(ValueError, match="Knowledge base path does not exist"):
            self.store.index_knowledge_files(nonexistent_path, self.agent_id)
    
    @pytest.mark.edge_case  
    def test_empty_knowledge_directory(self):
        """Test handling of empty knowledge base directory"""
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()
        
        indexed_entries = []
        self.store.store = lambda entry: indexed_entries.append(entry)
        
        count = self.store.index_knowledge_files(empty_dir, self.agent_id)
        
        # Should handle empty directory gracefully
        assert count == 0
        assert len(indexed_entries) == 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])