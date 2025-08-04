#!/usr/bin/env python3
"""
Simple RAG Chatbot using Praval Framework
Demonstrates the promised 3-5 line usage for a sophisticated RAG system.
"""

from pathlib import Path
from typing import List, Optional
import time
import signal
import sys
import threading
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging to prevent massive log files
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Import Praval from installed package
from praval import Agent

# ==========================================
# TIMEOUT AND SAFETY MECHANISMS
# ==========================================

class ProcessMonitor:
    """Monitor process activity and enforce timeouts to prevent runaway execution."""
    
    def __init__(self, max_runtime_minutes: int = 5, max_inactivity_minutes: int = 5):
        self.start_time = time.time()
        self.last_activity = time.time()
        self.max_runtime = max_runtime_minutes * 60
        self.max_inactivity = max_inactivity_minutes * 60
        self.is_active = True
        self.interaction_count = 0
        
    def reset_activity(self):
        """Reset the activity timer."""
        self.last_activity = time.time()
        self.interaction_count += 1
        
    def check_should_continue(self) -> bool:
        """Check if process should continue running."""
        current_time = time.time()
        
        # Check total runtime
        if current_time - self.start_time > self.max_runtime:
            logging.warning(f"Process exceeded maximum runtime of {self.max_runtime/60:.1f} minutes")
            return False
            
        # Check inactivity timeout (only after first interaction)
        if self.interaction_count > 0 and current_time - self.last_activity > self.max_inactivity:
            logging.warning(f"Process inactive for {self.max_inactivity/60:.1f} minutes")
            return False
            
        return True

def safe_input_with_timeout(prompt: str, monitor: ProcessMonitor, timeout_seconds: int = 30) -> Optional[str]:
    """Get user input with timeout to prevent infinite waiting."""
    
    def input_thread(result_container):
        try:
            result = input(prompt)
            result_container.append(result)
        except (EOFError, KeyboardInterrupt):
            result_container.append(None)
    
    result_container = []
    thread = threading.Thread(target=input_thread, args=(result_container,))
    thread.daemon = True
    thread.start()
    
    # Wait for input with timeout
    start_time = time.time()
    while thread.is_alive() and (time.time() - start_time) < timeout_seconds:
        if not monitor.check_should_continue():
            logging.info("Process timeout detected during input - shutting down")
            return None
        time.sleep(0.1)
    
    if thread.is_alive():
        logging.warning(f"Input timeout after {timeout_seconds} seconds - assuming automated execution")
        return None
        
    monitor.reset_activity()
    return result_container[0] if result_container else None

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    logging.info("Received termination signal - shutting down gracefully")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ==========================================
# RAG SYSTEM IMPLEMENTATION
# ==========================================

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
    """Interactive RAG chatbot session with timeout protection."""
    print("\n🤖 ESL RAG Chatbot ready!")
    print("Ask questions about statistical learning and machine learning concepts.")
    print("⏰ Auto-shutdown after 5 minutes of inactivity or 5 minutes total runtime")
    print("Type 'quit' to exit.\n")
    
    # Initialize process monitor
    monitor = ProcessMonitor(max_runtime_minutes=5, max_inactivity_minutes=5)
    logging.info("Starting RAG chatbot with timeout protection")
    
    interaction_count = 0
    max_interactions = 20  # Limit total interactions to prevent runaway processes
    
    while monitor.check_should_continue() and interaction_count < max_interactions:
        try:
            # Get user input with timeout
            question = safe_input_with_timeout("📚 Your question: ", monitor, timeout_seconds=30)
            
            if question is None:
                # Input timeout or process timeout
                if not monitor.check_should_continue():
                    print("\n⏰ Process timeout - shutting down to prevent runaway execution")
                else:
                    print("\n⏰ Input timeout - assuming automated execution, exiting")
                break
                
            question = question.strip()
            if question.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye! 👋")
                break
            
            if not question:
                continue
                
            interaction_count += 1
            
            # Check timeout before expensive operation
            if not monitor.check_should_continue():
                print("⏰ Process timeout - cannot continue with query processing")
                break
            
            print("🔍 Searching ESL book and generating response...")
            logging.info(f"Processing question {interaction_count}: {question[:50]}...")
            
            response = agent.chat(question)
            monitor.reset_activity()  # Reset after successful response
            
            print(f"\n🤖 ESL Bot: {response}\n")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            print(f"Error: {e}")
    
    if interaction_count >= max_interactions:
        print(f"\n⏰ Reached maximum interactions ({max_interactions}) - shutting down")
    
    logging.info(f"RAG chatbot completed after {interaction_count} interactions")

if __name__ == "__main__":
    main()