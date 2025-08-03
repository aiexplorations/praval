#!/usr/bin/env python3
"""
Simple RAG Chatbot using Praval Framework
Demonstrates the promised 3-5 line usage for a sophisticated RAG system.
"""

from pathlib import Path
from typing import List

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import Praval from installed package
from praval import Agent

def extract_pdf_content(pdf_path: str) -> str:
    """Extract text content from PDF file."""
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except ImportError:
        # Fallback: try to read as text if PyPDF2 not available
        print("PyPDF2 not available. Please install with: pip install PyPDF2")
        return ""

def chunk_text(text: str, chunk_size: int = 1000) -> List[str]:
    """Simple text chunking by character count."""
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks

# Load and process the ESL book
pdf_path = "/Users/rajesh/Downloads/ESLII_print12_toc.pdf"
print("Loading ESL book content...")

try:
    book_content = extract_pdf_content(pdf_path)
    if not book_content:
        # Simple fallback content for demonstration
        book_content = """
        Elements of Statistical Learning (ESL) is a comprehensive book on statistical learning methods.
        It covers topics including linear regression, classification, model selection, regularization,
        tree-based methods, support vector machines, clustering, and neural networks.
        The book provides both theoretical foundations and practical applications.
        """
    
    # Chunk the content for retrieval
    chunks = chunk_text(book_content, chunk_size=800)
    print(f"Processed {len(chunks)} content chunks from the book.")
    
except Exception as e:
    print(f"Could not read PDF: {e}")
    # Use sample content for demonstration
    chunks = [
        "Elements of Statistical Learning covers supervised learning methods including linear regression and classification.",
        "The book discusses model selection techniques such as cross-validation and information criteria.",
        "Regularization methods like ridge regression and lasso are explained in detail.",
        "Tree-based methods including random forests and boosting are covered comprehensively.",
        "Support Vector Machines and kernel methods are explained with theoretical foundations.",
        "The book covers unsupervised learning including clustering and dimensionality reduction.",
        "Neural networks and deep learning fundamentals are introduced in later chapters."
    ]
    print("Using sample ESL content for demonstration.")

# ==========================================
# HERE'S THE PROMISED 3-5 LINE RAG CHATBOT:
# ==========================================

# Create RAG agent with retrieval tool
agent = Agent("esl_rag_bot", system_message="""You are an expert on statistical learning and machine learning, with deep knowledge of "The Elements of Statistical Learning" book. 

When answering questions:
1. First use the retrieve_content tool to find relevant information from the book
2. Analyze and synthesize the retrieved content 
3. Provide a clear, helpful response based on the retrieved information
4. Do not simply repeat or quote large sections verbatim
5. Summarize key concepts and explain them in an accessible way
6. If asked about topics covered in the book, organize and present them clearly

You should sound knowledgeable and educational, not just return raw text excerpts.""")

@agent.tool
def retrieve_content(query: str) -> str:
    """Retrieve relevant content from the ESL book based on the query."""
    # Simple keyword-based retrieval
    query_lower = query.lower()
    relevant_chunks = []
    
    for chunk in chunks:
        chunk_lower = chunk.lower()
        # Score chunks by keyword overlap
        score = sum(1 for word in query_lower.split() if word in chunk_lower)
        if score > 0:
            relevant_chunks.append((score, chunk))
    
    # Return top 3 most relevant chunks
    relevant_chunks.sort(reverse=True, key=lambda x: x[0])
    top_chunks = [chunk for score, chunk in relevant_chunks[:3]]
    
    return "\n\n".join(top_chunks) if top_chunks else "No relevant content found."

# That's it! The RAG chatbot is ready in 5 lines of Praval code.
# ===============================================================

def main():
    """Interactive RAG chatbot session."""
    print("\n🤖 ESL RAG Chatbot ready!")
    print("Ask questions about statistical learning and machine learning concepts.")
    print("Type 'quit' to exit.\n")
    
    while True:
        try:
            question = input("📚 Your question: ").strip()
            if question.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye! 👋")
                break
            
            if not question:
                continue
            
            print("🔍 Searching ESL book and generating response...")
            response = agent.chat(question)
            print(f"\n🤖 ESL Bot: {response}\n")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()