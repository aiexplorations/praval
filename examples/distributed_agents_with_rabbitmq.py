"""
Example: Distributed Agents Using RabbitMQ Backend

Demonstrates how agents can work across distributed processes/containers
using RabbitMQ as the communication backend. The agent code is identical
to local communication - only the backend changes.

Key Concepts:
1. Same agent decorator works locally or distributed
2. RabbitMQ backend handles all distributed communication
3. Native Spore AMQP format for efficient transport
4. Automatic message routing and delivery

Example Flow:
┌─────────────────────────────────────────────────────┐
│ Client Process                                      │
│ - Sends initial request to "processor"              │
└─────────────────┬───────────────────────────────────┘
                  │ amqp://rabbitmq:5672
                  ▼
        ┌─────────────────────┐
        │  RabbitMQ Broker    │
        │  (agent.processor)  │
        │  (agent.analyzer)   │
        │  (broadcast.*)      │
        └─────────────────────┘
        ▲         │
        │         ▼
        │  ┌──────────────────┐
        │  │ Processor Agent  │
        │  │ (separate proc)  │
        │  └──────────────────┘
        │
        └──────────────────┐
                           ▼
                    ┌──────────────────┐
                    │ Analyzer Agent   │
                    │ (separate proc)  │
                    └──────────────────┘

Prerequisites:
- RabbitMQ running on rabbitmq:5672 (or configure URL)
- aio-pika installed (pip install aio-pika)
- asyncio event loop
"""

import asyncio
import logging
from datetime import datetime

from praval.core.reef import Reef, Spore, SporeType, get_reef
from praval.core.reef_backend import RabbitMQBackend
from praval.decorators import agent, broadcast, start_agents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

RABBITMQ_CONFIG = {
    'url': 'amqp://guest:guest@localhost:5672/',
    'exchange_name': 'praval.agents',
    'verify_tls': False  # Use False for development, True for production
}


# ============================================================================
# AGENT DEFINITIONS (Same as local, different backend!)
# ============================================================================

@agent("processor")
async def processor_agent(spore):
    """
    Process incoming requests from the client.

    The agent receives Spore objects directly (not raw bytes).
    It can work unchanged whether using InMemoryBackend or RabbitMQBackend.
    """
    logger.info(f"Processor received request: {spore.knowledge}")

    # Extract request data
    request_data = spore.knowledge.get("data")
    user_input = spore.knowledge.get("user_query")

    if not request_data:
        logger.warning("No data in request")
        return

    # Process the data (mock processing)
    processed = {
        "original": request_data,
        "processed_at": datetime.now().isoformat(),
        "query": user_input,
        "status": "ready_for_analysis"
    }

    logger.info(f"Processor: Data processed, sending to analyzer")

    # Send to analyzer for next stage
    reef = get_reef()
    analyzer_request = {
        "processed_data": processed,
        "original_request_id": spore.id
    }

    await reef.send(
        from_agent="processor",
        to_agent="analyzer",
        knowledge=analyzer_request,
        spore_type=SporeType.REQUEST,
        reply_to=spore.id
    )


@agent("analyzer")
async def analyzer_agent(spore):
    """
    Analyze processed data and broadcast results.
    """
    logger.info(f"Analyzer received data from {spore.from_agent}")

    # Extract processed data
    processed_data = spore.knowledge.get("processed_data", {})
    query = processed_data.get("query", "unknown")

    # Perform analysis (mock)
    analysis_result = {
        "query": query,
        "analysis": "This would be real analysis results",
        "confidence": 0.95,
        "analyzed_at": datetime.now().isoformat(),
        "tags": ["important", "processed"]
    }

    logger.info(f"Analyzer: Analysis complete, broadcasting results")

    # Broadcast results to all listening agents
    reef = get_reef()
    await reef.broadcast(
        from_agent="analyzer",
        knowledge={
            "analysis": analysis_result,
            "status": "analysis_complete",
            "source_request": spore.knowledge.get("original_request_id")
        }
    )


# ============================================================================
# CLIENT FUNCTION (Sends initial request)
# ============================================================================

async def client_process():
    """
    Client process that initiates a request through the distributed system.
    """
    logger.info("=" * 70)
    logger.info("CLIENT: Starting distributed agent workflow")
    logger.info("=" * 70)

    # Give agents time to start and subscribe
    await asyncio.sleep(2)

    # Get the global reef
    reef = get_reef()

    # Send request to processor
    request = {
        "data": {
            "text": "This is sample data for processing",
            "timestamp": datetime.now().isoformat()
        },
        "user_query": "Analyze this data for me"
    }

    request_id = await reef.send(
        from_agent="client",
        to_agent="processor",
        knowledge=request,
        spore_type=SporeType.REQUEST
    )

    logger.info(f"CLIENT: Sent request with ID {request_id}")
    logger.info(f"CLIENT: Waiting for results...")

    # In a real scenario, you'd subscribe to results or poll them
    # For this example, just wait for processing to complete
    await asyncio.sleep(3)

    # Print network statistics
    stats = reef.get_network_stats()
    logger.info("=" * 70)
    logger.info("NETWORK STATISTICS:")
    logger.info(f"  Backend: {stats['backend']}")
    logger.info(f"  Backend Stats: {stats['backend_stats']}")
    logger.info(f"  Channels: {stats['total_channels']}")
    logger.info("=" * 70)


# ============================================================================
# MAIN SETUP AND EXECUTION
# ============================================================================

async def setup_distributed_system():
    """
    Initialize the distributed agent system with RabbitMQ backend.

    This setup allows agents to run in separate processes/containers
    while communicating through RabbitMQ.
    """
    logger.info("Setting up distributed agent system with RabbitMQ backend...")

    # Create RabbitMQ backend
    backend = RabbitMQBackend()

    # Create Reef with RabbitMQ backend (instead of default InMemory)
    reef = Reef(backend=backend)

    # Initialize the backend (async operation for distributed transports)
    try:
        await reef.initialize_backend(RABBITMQ_CONFIG)
        logger.info("✓ Distributed system initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize distributed system: {e}")
        logger.error("  Make sure RabbitMQ is running at: " + RABBITMQ_CONFIG['url'])
        raise

    return reef


async def run_distributed_demo():
    """
    Run the complete distributed agent workflow.
    """
    # Setup distributed system
    reef = await setup_distributed_system()

    try:
        # Run the client process which triggers the workflow
        await client_process()

    except Exception as e:
        logger.error(f"Error during demo: {e}", exc_info=True)

    finally:
        # Cleanup: Close backend connection
        logger.info("Shutting down distributed system...")
        await reef.close_backend()
        reef.shutdown()
        logger.info("✓ Shutdown complete")


# ============================================================================
# EXAMPLE 2: SIMPLIFIED VERSION (For single-process testing)
# ============================================================================

async def run_local_test():
    """
    Test the same agents locally with InMemoryBackend.

    This shows that the same agent code works with both backends!
    """
    from praval.core.reef_backend import InMemoryBackend

    logger.info("=" * 70)
    logger.info("TESTING WITH LOCAL INMEMORY BACKEND")
    logger.info("(Same agent code, different backend!)")
    logger.info("=" * 70)

    # Use InMemoryBackend instead of RabbitMQ
    backend = InMemoryBackend()
    reef = Reef(backend=backend)

    # Initialize (no-op for in-memory)
    await reef.initialize_backend()

    try:
        # The agent code and workflow is identical!
        await client_process()

    finally:
        await reef.close_backend()
        reef.shutdown()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    print("\n" + "=" * 70)
    print("DISTRIBUTED AGENTS WITH RABBITMQ - PRAVAL v0.7.13")
    print("=" * 70 + "\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        # Run with local InMemory backend for testing
        print("Mode: LOCAL (InMemoryBackend)")
        print("\nThis demonstrates that the same agent code works with")
        print("both InMemoryBackend (local) and RabbitMQBackend (distributed)\n")
        asyncio.run(run_local_test())

    else:
        # Run distributed version with RabbitMQ
        print("Mode: DISTRIBUTED (RabbitMQBackend)")
        print("\nThis demonstrates agents running with RabbitMQ communication.")
        print("Ensure RabbitMQ is running at: " + RABBITMQ_CONFIG['url'])
        print("\nTo test with local backend instead, run:")
        print("  python distributed_agents_with_rabbitmq.py --local\n")

        try:
            asyncio.run(run_distributed_demo())
        except ConnectionError as e:
            logger.error("\n" + "=" * 70)
            logger.error("CONNECTION ERROR: Could not connect to RabbitMQ")
            logger.error("=" * 70)
            logger.error("\nTo fix:")
            logger.error("1. Install RabbitMQ: docker run -d -p 5672:5672 rabbitmq:latest")
            logger.error("2. Or test with local backend: python " + sys.argv[0] + " --local")
            logger.error("=" * 70 + "\n")
            sys.exit(1)
