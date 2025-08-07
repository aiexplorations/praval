#!/usr/bin/env python3
"""
Test script for message type filtering in the knowledge graph miner.
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Add the project directory to the path
sys.path.insert(0, '/Users/rajesh/Github/praval/src')

from examples.knowledge_graph_miner import start_autonomous_mining, wait_for_completion, print_results, save_graph_results

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def test_message_filtering():
    """Test the message type filtering implementation."""
    print("🧪 Testing Message Type Filtering in Knowledge Graph Miner")
    print("=" * 60)
    
    # Test with a simple concept
    test_concept = "blockchain"
    max_nodes = 5
    
    print(f"🚀 Testing with concept: '{test_concept}' (max {max_nodes} nodes)")
    print()
    
    try:
        # Start autonomous mining
        start_autonomous_mining(test_concept, max_nodes)
        
        # Wait for completion with shorter timeout for testing
        print("⏳ Waiting for mining to complete...")
        final_stats = wait_for_completion(timeout=30)
        
        # Display results
        print_results()
        save_graph_results()
        
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logging.error(f"Test error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_message_filtering()
    sys.exit(0 if success else 1)