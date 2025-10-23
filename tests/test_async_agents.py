#!/usr/bin/env python3
"""
Test async agent execution with concurrent LLM calls.
This demonstrates the performance improvement from threading.
"""

import os
import sys
import time
import asyncio
import logging
import pytest
from unittest.mock import patch, MagicMock

# Mock the provider detection to avoid requiring API keys in tests
os.environ["OPENAI_API_KEY"] = "test_key_for_testing"

from praval import agent, chat, achat, broadcast, start_agents

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(threadName)s] %(message)s')

# Test data
results = {"sync": [], "async": [], "concurrent": []}

# ==========================================
# SYNC AGENT TEST 
# ==========================================

@agent("sync_processor", channel="sync_test", responds_to=["sync_task"])
def sync_agent(spore):
    """Synchronous agent - will block during LLM calls."""
    task_id = spore.knowledge.get("task_id")
    concept = spore.knowledge.get("concept")
    
    start_time = time.time()
    logging.info(f"🔄 Sync agent {task_id} starting: {concept}")
    
    # Simulate LLM work - this blocks
    response = chat(f"Generate 3 words related to '{concept}'. Reply with only the words, comma-separated.")
    
    elapsed = time.time() - start_time
    logging.info(f"✅ Sync agent {task_id} completed in {elapsed:.2f}s")
    
    results["sync"].append(elapsed)
    return {"type": "sync_complete", "task_id": task_id, "response": response}

# ==========================================
# ASYNC AGENT TEST
# ==========================================

@agent("async_processor", channel="async_test", responds_to=["async_task"])
async def async_agent(spore):
    """Async agent - can run concurrently with other async agents."""
    task_id = spore.knowledge.get("task_id")
    concept = spore.knowledge.get("concept")
    
    start_time = time.time()
    logging.info(f"🔄 Async agent {task_id} starting: {concept}")
    
    # Simulate async LLM work - this doesn't block other agents
    response = await achat(f"Generate 3 words related to '{concept}'. Reply with only the words, comma-separated.")
    
    elapsed = time.time() - start_time
    logging.info(f"✅ Async agent {task_id} completed in {elapsed:.2f}s")
    
    results["async"].append(elapsed)
    return {"type": "async_complete", "task_id": task_id, "response": response}

# ==========================================
# CONCURRENT PROCESSING AGENT
# ==========================================

@agent("concurrent_processor", channel="concurrent_test", responds_to=["concurrent_task"])
def concurrent_agent(spore):
    """Regular agent that will be executed in parallel by thread pool."""
    task_id = spore.knowledge.get("task_id")
    concept = spore.knowledge.get("concept")
    
    start_time = time.time()
    logging.info(f"🔄 Concurrent agent {task_id} starting: {concept}")
    
    # Regular sync chat - but reef will run multiple in parallel
    response = chat(f"Generate 3 words related to '{concept}'. Reply with only the words, comma-separated.")
    
    elapsed = time.time() - start_time
    logging.info(f"✅ Concurrent agent {task_id} completed in {elapsed:.2f}s")
    
    results["concurrent"].append(elapsed)
    return {"type": "concurrent_complete", "task_id": task_id, "response": response}

# ==========================================
# TEST RUNNERS
# ==========================================

def test_sync_execution():
    """Test synchronous execution (should be slow - blocking)."""
    print("\n🐌 Testing Synchronous Execution (blocking)")
    print("=" * 50)
    
    start_agents(sync_agent, channel="sync_test")
    
    concepts = ["machine learning", "quantum physics", "biology", "economics"]
    start_time = time.time()
    
    for i, concept in enumerate(concepts):
        broadcast({
            "type": "sync_task",
            "task_id": f"sync_{i}",
            "concept": concept
        })
        time.sleep(0.1)  # Small delay between broadcasts
    
    # Wait for completion
    time.sleep(15)  # Should be enough for 4 sequential calls
    
    total_time = time.time() - start_time
    print(f"📊 Sync total time: {total_time:.2f}s")
    if results["sync"]:
        avg_time = sum(results["sync"]) / len(results["sync"])
        print(f"📊 Sync average per task: {avg_time:.2f}s")

def test_concurrent_execution():
    """Test concurrent execution with ThreadPool (should be fast)."""
    print("\n⚡ Testing Concurrent Execution (ThreadPool)")
    print("=" * 50)
    
    start_agents(concurrent_agent, channel="concurrent_test")
    
    concepts = ["chemistry", "mathematics", "psychology", "linguistics"]
    start_time = time.time()
    
    # Send all tasks at once - they should run in parallel
    for i, concept in enumerate(concepts):
        broadcast({
            "type": "concurrent_task",
            "task_id": f"concurrent_{i}",
            "concept": concept
        })
    
    # Wait for completion
    time.sleep(10)  # Should be much faster than sync version
    
    total_time = time.time() - start_time
    print(f"📊 Concurrent total time: {total_time:.2f}s")
    if results["concurrent"]:
        avg_time = sum(results["concurrent"]) / len(results["concurrent"])
        print(f"📊 Concurrent average per task: {avg_time:.2f}s")

def main():
    """Compare sync vs concurrent agent execution."""
    print("🧪 Async Agent Execution Test")
    print("Testing the performance difference between sync and concurrent agents")
    print("=" * 70)
    
    try:
        # Test synchronous execution
        test_sync_execution()
        
        # Clear results and test concurrent
        time.sleep(2)  # Brief pause between tests
        test_concurrent_execution()
        
        # Summary
        print("\n📊 Performance Summary")
        print("=" * 30)
        
        if results["sync"]:
            sync_total = sum(results["sync"])
            print(f"🐌 Sync execution: {sync_total:.2f}s total")
        
        if results["concurrent"]:
            concurrent_total = sum(results["concurrent"])
            print(f"⚡ Concurrent execution: {concurrent_total:.2f}s total")
            
            if results["sync"]:
                speedup = sync_total / concurrent_total
                print(f"🚀 Speedup: {speedup:.1f}x faster with threading!")
        
        print("\n✅ Async agent testing completed!")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logging.error(f"Test error: {e}")

if __name__ == "__main__":
    main()