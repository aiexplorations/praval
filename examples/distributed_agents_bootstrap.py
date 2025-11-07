#!/usr/bin/env python
"""
Fixed Example: Distributed Agents Bootstrap with Proper Async Lifecycle

This example demonstrates the CORRECT way to run distributed agents with RabbitMQ.

KEY FIX (v0.7.14):
=================
In v0.7.13 and earlier, distributed agents didn't consume messages from RabbitMQ
because there was no event loop running. This example shows the proper solution
using AgentRunner and run_agents().

The Problem:
- Agent decorator subscribes at import time (synchronous)
- RabbitMQ backend requires async event loop to consume messages
- Without AgentRunner, the loop never runs → agents never consume messages

The Solution:
- Use AgentRunner to manage async event loop lifecycle
- Use run_agents() convenience function for simple setup
- AgentRunner handles initialization, signal handling, and shutdown

Example Flow:
┌──────────────────────────┐
│   Your Code              │
│  run_agents(...)         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   AgentRunner            │
│  - Create event loop     │
│  - Initialize backend    │
│  - Keep loop alive       │
│  - Handle signals        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   RabbitMQ Backend       │
│  - Connect to broker     │
│  - Subscribe to queues   │
│  - Consume messages      │
│  - Route to agents       │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   Agents                 │
│  - Receive spores        │
│  - Process messages      │
│  - Send responses        │
└──────────────────────────┘

Prerequisites:
- RabbitMQ running: docker run -d -p 5672:5672 rabbitmq:latest
- aio-pika installed: pip install aio-pika

Quick Start:
1. Start RabbitMQ:
   docker run -d -p 5672:5672 rabbitmq:latest

2. Run this script:
   python examples/distributed_agents_bootstrap.py

3. In another terminal, send a test message (optional):
   python -c "
   import asyncio
   from praval.core.reef import get_reef

   async def send_message():
       reef = get_reef()
       await reef.initialize_backend({
           'url': 'amqp://guest:guest@localhost:5672/',
           'exchange_name': 'praval.agents'
       })
       await reef.send(
           from_agent='test_client',
           to_agent='processor',
           knowledge={'data': 'hello world'}
       )

   asyncio.run(send_message())
   "
"""

import logging
from datetime import datetime

from praval import agent
from praval.composition import run_agents

# Configure logging to see agent activity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# AGENT DEFINITIONS
# ============================================================================

@agent("processor", responds_to=["request", "process"])
def processor_agent(spore):
    """
    Process incoming requests.

    Receives data and performs basic processing.
    Forwards results to the analyzer agent.
    """
    logger.info(f"Processor: Received from {spore.from_agent}")

    # Extract incoming data
    data = spore.knowledge.get('data', '')
    request_id = spore.knowledge.get('request_id', 'unknown')

    if not data:
        logger.warning("Processor: No data in request")
        return {'status': 'error', 'reason': 'no_data'}

    # Process the data
    processed = {
        'original': data,
        'processed': data.upper() if isinstance(data, str) else str(data),
        'length': len(str(data)),
        'processor_timestamp': datetime.now().isoformat(),
        'request_id': request_id
    }

    logger.info(f"Processor: Processed data, length={len(str(data))}")

    # Return result (will be broadcast by default)
    return {
        'type': 'processing_complete',
        'processed_data': processed,
        'original_request_id': request_id
    }


@agent("analyzer", responds_to=["processing_complete", "analyze"])
def analyzer_agent(spore):
    """
    Analyze processed data.

    Receives processed data and performs analysis.
    """
    logger.info(f"Analyzer: Received from {spore.from_agent}")

    # Extract data
    processed_data = spore.knowledge.get('processed_data', {})
    if not processed_data:
        logger.warning("Analyzer: No processed data received")
        return {'status': 'error', 'reason': 'no_data'}

    # Perform analysis
    analysis = {
        'length': processed_data.get('length', 0),
        'has_uppercase': any(
            c.isupper() for c in str(processed_data.get('processed', ''))
        ),
        'char_count': len(str(processed_data.get('original', ''))),
        'analyzer_timestamp': datetime.now().isoformat()
    }

    logger.info(f"Analyzer: Analysis complete - {analysis}")

    # Return analysis results
    return {
        'type': 'analysis_complete',
        'analysis': analysis,
        'source_request': spore.knowledge.get('original_request_id')
    }


@agent("reporter")
def reporter_agent(spore):
    """
    Report final results.

    Receives all messages and logs them.
    Could also send to external systems (logging, monitoring, etc.)
    """
    msg_type = spore.knowledge.get('type', 'unknown')
    logger.info(f"Reporter: Received {msg_type} from {spore.from_agent}")

    # Log results
    if msg_type == 'analysis_complete':
        analysis = spore.knowledge.get('analysis', {})
        logger.info(f"Reporter: Final results - {analysis}")

    return {'type': 'reported'}


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    import sys

    print("\n" + "=" * 70)
    print("DISTRIBUTED AGENTS BOOTSTRAP - PRAVAL v0.7.14")
    print("Fixed RabbitMQ Message Consumption")
    print("=" * 70 + "\n")

    # RabbitMQ configuration
    RABBITMQ_CONFIG = {
        'url': 'amqp://guest:guest@localhost:5672/',
        'exchange_name': 'praval.agents',
        'verify_tls': False  # False for development, True for production
    }

    print("Configuration:")
    print(f"  RabbitMQ URL: {RABBITMQ_CONFIG['url']}")
    print(f"  Exchange: {RABBITMQ_CONFIG['exchange_name']}")
    print("\nStarting distributed agents...")
    print("Agents running:")
    print("  ✓ Processor - Handles 'process' messages")
    print("  ✓ Analyzer  - Handles 'processing_complete' messages")
    print("  ✓ Reporter  - Logs all messages")
    print("\nPress Ctrl+C to shutdown\n")

    try:
        # THE KEY FIX: Use run_agents() to properly initialize async lifecycle
        # This function:
        # 1. Creates an event loop
        # 2. Initializes RabbitMQ backend
        # 3. Subscribes agents to message queues
        # 4. Keeps the loop running until shutdown
        # 5. Handles graceful shutdown on SIGTERM/SIGINT

        run_agents(
            processor_agent,
            analyzer_agent,
            reporter_agent,
            backend_config=RABBITMQ_CONFIG
        )

    except ConnectionError as e:
        print("\n" + "=" * 70)
        print("ERROR: Could not connect to RabbitMQ")
        print("=" * 70)
        print(f"\nDetails: {e}")
        print("\nTo fix, make sure RabbitMQ is running:")
        print("  docker run -d -p 5672:5672 rabbitmq:latest")
        print("\nOr test locally with InMemory backend:")
        print("  python examples/002_agent_communication.py")
        print("=" * 70 + "\n")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("Shutdown complete")
        print("=" * 70 + "\n")


# ============================================================================
# TESTING (Optional)
# ============================================================================

def test_locally():
    """Test the agents locally with InMemoryBackend (no RabbitMQ needed)."""
    print("Testing agents locally with InMemoryBackend...")

    from praval.composition import start_agents

    # This broadcasts a test message to all agents
    start_agents(
        processor_agent,
        analyzer_agent,
        reporter_agent,
        initial_data={
            'type': 'process',
            'data': 'test message',
            'request_id': 'test_123'
        }
    )

    print("✓ Local test completed")


if __name__ == '__main__':
    # Uncomment to run local test
    # test_locally()
    pass
