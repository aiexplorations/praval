"""
Agent Runner: Lifecycle management for distributed agents.

This module provides the AgentRunner class which properly manages the async
event loop and backend initialization for agents using distributed backends
like RabbitMQ.

The core issue it solves:
- The @agent decorator registers agents at import time (synchronous)
- RabbitMQ backend requires an async event loop to consume messages
- Without AgentRunner, distributed agents never consume messages from the broker

Usage:
    from praval.core.agent_runner import AgentRunner

    runner = AgentRunner(
        agents=[agent1, agent2, agent3],
        backend_config={'url': 'amqp://localhost:5672/'}
    )

    # This keeps the event loop running and agents consuming messages
    runner.run()
"""

import asyncio
import logging
import signal
import sys
from typing import List, Dict, Any, Optional, Callable
from contextlib import asynccontextmanager

from .reef import get_reef, Reef
from .reef_backend import RabbitMQBackend

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Manages the lifecycle of distributed agents with proper async event loop.

    This class solves the RabbitMQ message consumption problem by:
    1. Creating and managing an event loop
    2. Initializing the RabbitMQ backend asynchronously
    3. Ensuring agents are properly subscribed to channels
    4. Keeping the loop alive to consume messages
    5. Handling graceful shutdown on signals

    Example:
        @agent("processor")
        def process(spore):
            return {"result": "processed"}

        @agent("analyzer")
        def analyze(spore):
            return {"analysis": "done"}

        # Run distributed agents
        runner = AgentRunner(
            agents=[process, analyze],
            backend_config={
                'url': 'amqp://localhost:5672/',
                'exchange_name': 'praval.agents'
            }
        )
        runner.run()  # Blocks until shutdown signal
    """

    def __init__(
        self,
        agents: List[Callable],
        backend_config: Optional[Dict[str, Any]] = None,
        backend: Optional[Any] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        """
        Initialize the agent runner.

        Args:
            agents: List of agent functions decorated with @agent
            backend_config: Configuration dict for RabbitMQ backend
                {
                    'url': 'amqp://user:pass@host:5672/',
                    'exchange_name': 'praval.agents',
                    'verify_tls': True/False
                }
            backend: Optional pre-created RabbitMQBackend instance
            loop: Optional asyncio event loop (creates new one if None)
        """
        self.agents = agents
        self.backend_config = backend_config or {}
        self.backend = backend or self._create_backend()
        self.loop = loop
        self.reef: Optional[Reef] = None
        self._shutdown_event = asyncio.Event()
        self._running = False

        # Validate agents
        for agent in agents:
            if not hasattr(agent, '_praval_agent'):
                raise ValueError(
                    f"Agent {agent.__name__} is not decorated with @agent. "
                    "All agents must be decorated with the @agent decorator."
                )

    def _create_backend(self) -> Any:
        """Create RabbitMQ backend from config."""
        if self.backend_config:
            return RabbitMQBackend()
        else:
            # Use InMemory backend if no config provided
            from .reef_backend import InMemoryBackend
            return InMemoryBackend()

    async def initialize(self) -> None:
        """
        Initialize the backend and agents.

        This is called automatically by run(), but can be called separately
        for more control over startup sequence.
        """
        logger.info(f"Initializing {len(self.agents)} agents...")

        # Get or create the global reef with our backend
        self.reef = get_reef()
        if self.reef.backend != self.backend:
            # Replace with our backend if different
            self.reef.backend = self.backend

        # Initialize the backend (this is the critical step for RabbitMQ)
        try:
            await self.reef.initialize_backend(self.backend_config)
            logger.info(f"✓ Backend initialized: {self.reef.backend.__class__.__name__}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize backend: {e}")
            raise

        # Log agent registrations
        for agent in self.agents:
            agent_name = agent._praval_name
            agent_channel = agent._praval_channel
            logger.info(f"  ✓ Agent '{agent_name}' ready on channel '{agent_channel}'")

    async def run_async(self) -> None:
        """
        Run the agent event loop until shutdown.

        This is called by run() and can be called directly for async contexts.
        It blocks until shutdown signal or exception occurs.
        """
        if self._running:
            raise RuntimeError("Agent runner is already running")

        self._running = True
        logger.info("=" * 70)
        logger.info(f"Starting distributed agent system with {len(self.agents)} agents")
        logger.info("=" * 70)

        try:
            # Initialize backend and agents
            await self.initialize()

            # Keep the event loop alive
            logger.info("Agents ready and listening. Press Ctrl+C to shutdown...")

            # Wait for shutdown event (triggered by signal handler)
            await self._shutdown_event.wait()

        except KeyboardInterrupt:
            logger.info("\nKeyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in agent runner: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    def run(self) -> None:
        """
        Run the agent event loop (blocking call).

        This is the main entry point. It:
        1. Creates/uses event loop
        2. Sets up signal handlers for graceful shutdown
        3. Runs agents until shutdown signal
        4. Cleans up resources
        """
        # Use provided loop or create new one
        if self.loop is None:
            # Create new event loop for this runner
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            created_loop = True
        else:
            created_loop = False

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum: int, frame: Any) -> None:
            """Handle shutdown signals gracefully."""
            sig_name = signal.Signals(signum).name
            logger.info(f"\n{sig_name} received, shutting down gracefully...")
            self._shutdown_event.set()

        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        try:
            # Run the async event loop
            self.loop.run_until_complete(self.run_async())
        finally:
            if created_loop:
                # Clean up loop if we created it
                self.loop.close()
                self.loop = None

    async def shutdown(self) -> None:
        """
        Gracefully shutdown agents and backend.

        Called automatically by run_async() or can be called manually.
        """
        logger.info("Shutting down agent system...")

        try:
            if self.reef and hasattr(self.reef, 'close_backend'):
                await self.reef.close_backend()
                logger.info("✓ Backend closed")

            if self.reef:
                self.reef.shutdown(wait=True)
                logger.info("✓ Reef shutdown complete")

            logger.info("=" * 70)
            logger.info("Agent system shutdown complete")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            self._running = False

    @asynccontextmanager
    async def context(self):
        """
        Async context manager for using the runner in async code.

        Example:
            async with runner.context():
                # Agents are running and consuming messages
                await asyncio.sleep(10)
                # Shutdown happens automatically on exit
        """
        try:
            await self.initialize()
            yield self
        finally:
            await self.shutdown()

    def get_stats(self) -> Dict[str, Any]:
        """Get current runner statistics."""
        if not self.reef:
            return {
                'status': 'not_initialized',
                'agents': len(self.agents),
                'running': self._running
            }

        reef_stats = self.reef.get_network_stats()
        return {
            'status': 'running' if self._running else 'stopped',
            'agents': len(self.agents),
            'running': self._running,
            'backend': reef_stats.get('backend'),
            'channels': reef_stats.get('total_channels'),
            'backend_stats': reef_stats.get('backend_stats')
        }


def run_agents(
    *agents: Callable,
    backend_config: Optional[Dict[str, Any]] = None,
    backend: Optional[Any] = None
) -> None:
    """
    Convenience function to run distributed agents.

    This is the simplest way to start distributed agents with proper
    async lifecycle management.

    Args:
        *agents: Agent functions decorated with @agent
        backend_config: RabbitMQ configuration (required for distributed mode)
        backend: Optional pre-created backend instance

    Example:
        from praval import agent
        from praval.core.agent_runner import run_agents

        @agent("processor")
        def process_data(spore):
            return {"processed": True}

        @agent("analyzer")
        def analyze_results(spore):
            return {"analysis": "complete"}

        # Run with RabbitMQ
        run_agents(
            process_data,
            analyze_results,
            backend_config={
                'url': 'amqp://localhost:5672/',
                'exchange_name': 'praval.agents'
            }
        )
    """
    runner = AgentRunner(
        agents=list(agents),
        backend_config=backend_config,
        backend=backend
    )
    runner.run()
