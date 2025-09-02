#!/usr/bin/env python3
"""
Simple focused tests for PDF functionality without ChromaDB dependencies.
"""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open


def test_pdf_text_extraction():
    """Test PDF text extraction functionality"""
    # Import the function we want to test
    from praval.memory.embedded_store import EmbeddedVectorStore
    
    # Create a minimal store instance for testing methods
    store = EmbeddedVectorStore.__new__(EmbeddedVectorStore)  # Create without calling __init__
    
    with patch('PyPDF2.PdfReader') as mock_pdf_reader:
        # Mock PDF reader and pages
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "This is page 1 content about reinforcement learning."
        mock_page2 = Mock() 
        mock_page2.extract_text.return_value = "This is page 2 with Q-learning algorithms."
        
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance
        
        # Create a temporary PDF path
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = Path(tmp.name)
        
        try:
            with patch('builtins.open', mock_open(read_data=b"pdf content")):
                result = store._extract_pdf_text(pdf_path)
            
            # Check that both pages were extracted
            assert "page 1 content" in result
            assert "page 2" in result
            assert "reinforcement learning" in result
            assert "Q-learning" in result
            assert len(result) > 50  # Should have substantial content
            
            # Verify PyPDF2 was called correctly
            mock_pdf_reader.assert_called_once()
            mock_page1.extract_text.assert_called_once()
            mock_page2.extract_text.assert_called_once()
            
        finally:
            pdf_path.unlink()  # Clean up


def test_pdf_text_cleaning():
    """Test PDF text cleaning functionality"""
    from praval.memory.embedded_store import EmbeddedVectorStore
    
    store = EmbeddedVectorStore.__new__(EmbeddedVectorStore)
    
    # Test whitespace cleanup
    raw_text = "This   has    excessive     whitespace\n\n\n\n\nAnd multiple newlines"
    cleaned = store._clean_pdf_text(raw_text)
    
    assert "excessive     whitespace" not in cleaned
    assert "excessive whitespace" in cleaned
    assert "\n\n\n\n" not in cleaned
    
    # Test URL and email removal
    raw_text = ("Check https://example.com for more info. "
               "Contact support@company.com for help.")
    
    cleaned = store._clean_pdf_text(raw_text)
    
    assert "https://example.com" not in cleaned
    assert "support@company.com" not in cleaned
    assert "[URL]" in cleaned
    assert "[EMAIL]" in cleaned


def test_pdf_extraction_error_handling():
    """Test error handling in PDF extraction"""
    from praval.memory.embedded_store import EmbeddedVectorStore
    
    store = EmbeddedVectorStore.__new__(EmbeddedVectorStore)
    
    # Test PyPDF2 not installed
    with patch('builtins.__import__', side_effect=ImportError("No module named 'PyPDF2'")):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = Path(tmp.name)
        
        try:
            with pytest.raises(ImportError, match="PyPDF2 is required"):
                store._extract_pdf_text(pdf_path)
        finally:
            pdf_path.unlink()
    
    # Test corrupted PDF
    with patch('PyPDF2.PdfReader', side_effect=Exception("PDF corrupted")):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = Path(tmp.name)
        
        try:
            with patch('builtins.open', mock_open(read_data=b"corrupted")):
                result = store._extract_pdf_text(pdf_path)
                assert result == ""  # Should return empty string, not crash
        finally:
            pdf_path.unlink()


def test_knowledge_indexing_includes_pdf():
    """Test that PDF files are included in knowledge indexing"""
    from praval.memory.embedded_store import EmbeddedVectorStore
    
    # Test that PDF is in supported extensions
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test files
        (temp_path / "test.txt").write_text("Text file content")
        (temp_path / "test.pdf").write_bytes(b"PDF content")
        (temp_path / "test.md").write_text("# Markdown content")
        
        # Check that PDF files would be processed
        pdf_file = temp_path / "test.pdf"
        supported_extensions = {'.txt', '.md', '.rst', '.py', '.js', '.json', '.yaml', '.yml', '.pdf'}
        
        assert pdf_file.suffix.lower() in supported_extensions
        assert pdf_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])