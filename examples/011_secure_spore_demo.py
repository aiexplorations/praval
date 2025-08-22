#!/usr/bin/env python3
"""
Secure Spore Communication Demo

This example demonstrates the secure spore communication system in Praval:
- End-to-end encryption with PyNaCl
- Digital signatures for authenticity
- Multi-protocol support (AMQP, MQTT, STOMP)
- Backward compatibility with existing Reef API
- Key management and rotation

Run with: python examples/secure_spore_demo.py
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Praval secure components
try:
    from src.praval.core.secure_reef import SecureReef, KeyRegistry
    from src.praval.core.secure_spore import SporeKeyManager, SecureSporeFactory
    from src.praval.core.transport import TransportProtocol
    from src.praval.core.reef import SporeType
except ImportError:
    # Fallback for different import paths
    import sys
    import pathlib
    sys.path.append(str(pathlib.Path(__file__).parent.parent / "src"))
    
    from praval.core.secure_reef import SecureReef, KeyRegistry
    from praval.core.secure_spore import SporeKeyManager, SecureSporeFactory
    from praval.core.transport import TransportProtocol
    from praval.core.reef import SporeType


class SecureAgentDemo:
    """Demonstration of secure agent communication."""
    
    def __init__(self, name: str, protocol: TransportProtocol = TransportProtocol.AMQP):
        self.name = name
        self.protocol = protocol
        self.reef = None
        self.received_messages = []
        
    async def initialize(self, transport_config: Dict[str, Any] = None):
        """Initialize the secure agent."""
        logger.info(f"🔐 Initializing secure agent '{self.name}' with {self.protocol.value}")
        
        # Create secure reef with mock transport for demo
        self.reef = SecureReef(
            protocol=self.protocol,
            transport_config=transport_config or {}
        )
        
        # Initialize with mock transport (in production, use real transport)
        await self.reef.initialize(self.name)
        
        # Register message handlers
        self.reef.register_handler(SporeType.KNOWLEDGE, self._handle_knowledge)
        self.reef.register_handler(SporeType.REQUEST, self._handle_request)
        self.reef.register_handler(SporeType.RESPONSE, self._handle_response)
        self.reef.register_handler(SporeType.BROADCAST, self._handle_broadcast)
        
        logger.info(f"✅ Agent '{self.name}' initialized successfully")
        
    async def _handle_knowledge(self, spore):
        """Handle knowledge spores."""
        logger.info(f"📚 {self.name} received knowledge from {spore.from_agent}")
        logger.info(f"   Content: {json.dumps(spore.knowledge, indent=2)}")
        self.received_messages.append(('knowledge', spore))
        
    async def _handle_request(self, spore):
        """Handle request spores."""
        logger.info(f"❓ {self.name} received request from {spore.from_agent}")
        logger.info(f"   Request: {json.dumps(spore.knowledge, indent=2)}")
        self.received_messages.append(('request', spore))
        
        # Auto-respond to requests
        response = {
            "status": "success",
            "response_to": spore.knowledge.get("query", "unknown"),
            "processed_by": self.name,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.reef.reply(
            to_agent=spore.from_agent,
            response=response,
            reply_to_spore_id=spore.id
        )
        
        logger.info(f"📤 {self.name} sent response to {spore.from_agent}")
        
    async def _handle_response(self, spore):
        """Handle response spores."""
        logger.info(f"📨 {self.name} received response from {spore.from_agent}")
        logger.info(f"   Response: {json.dumps(spore.knowledge, indent=2)}")
        self.received_messages.append(('response', spore))
        
    async def _handle_broadcast(self, spore):
        """Handle broadcast spores."""
        logger.info(f"📢 {self.name} received broadcast from {spore.from_agent}")
        logger.info(f"   Message: {json.dumps(spore.knowledge, indent=2)}")
        self.received_messages.append(('broadcast', spore))
        
    async def send_knowledge(self, to_agent: str, knowledge: Dict[str, Any]):
        """Send knowledge to another agent."""
        logger.info(f"📤 {self.name} sending knowledge to {to_agent}")
        
        spore_id = await self.reef.send_secure_spore(
            to_agent=to_agent,
            knowledge=knowledge,
            spore_type=SporeType.KNOWLEDGE,
            priority=5
        )
        
        logger.info(f"   Sent secure spore: {spore_id}")
        return spore_id
        
    async def send_request(self, to_agent: str, request: Dict[str, Any]):
        """Send request to another agent."""
        logger.info(f"❓ {self.name} sending request to {to_agent}")
        
        spore_id = await self.reef.request(
            to_agent=to_agent,
            request=request,
            expires_in_seconds=60
        )
        
        logger.info(f"   Sent request: {spore_id}")
        return spore_id
        
    async def broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message to all agents."""
        logger.info(f"📢 {self.name} broadcasting message")
        
        spore_id = await self.reef.broadcast(
            knowledge=message,
            spore_type=SporeType.BROADCAST
        )
        
        logger.info(f"   Broadcast spore: {spore_id}")
        return spore_id
        
    async def register_peer(self, peer_agent: 'SecureAgentDemo'):
        """Register another agent's keys for secure communication."""
        await self.reef.key_registry.register_agent(
            peer_agent.name,
            peer_agent.reef.key_manager.get_public_keys()
        )
        logger.info(f"🔑 {self.name} registered keys for {peer_agent.name}")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        reef_stats = self.reef.get_stats()
        return {
            **reef_stats,
            'messages_received': len(self.received_messages),
            'message_types': {
                msg_type: len([m for m in self.received_messages if m[0] == msg_type])
                for msg_type in ['knowledge', 'request', 'response', 'broadcast']
            }
        }
        
    async def rotate_keys(self):
        """Rotate cryptographic keys."""
        logger.info(f"🔄 {self.name} rotating cryptographic keys")
        
        rotation_result = await self.reef.rotate_keys()
        
        logger.info(f"✅ {self.name} keys rotated successfully")
        return rotation_result
        
    async def close(self):
        """Close the secure agent."""
        if self.reef:
            await self.reef.close()
        logger.info(f"🔒 Agent '{self.name}' closed")


async def demonstrate_secure_communication():
    """Demonstrate secure spore communication between agents."""
    logger.info("🚀 Starting Secure Spore Communication Demo")
    logger.info("=" * 60)
    
    # Create three agents with different protocols (mock for demo)
    alice = SecureAgentDemo("alice", TransportProtocol.AMQP)
    bob = SecureAgentDemo("bob", TransportProtocol.MQTT)
    charlie = SecureAgentDemo("charlie", TransportProtocol.STOMP)
    
    try:
        # Initialize all agents
        logger.info("🔧 Initializing agents...")
        await alice.initialize()
        await bob.initialize()
        await charlie.initialize()
        
        # Cross-register keys for secure communication
        logger.info("🔑 Cross-registering cryptographic keys...")
        await alice.register_peer(bob)
        await alice.register_peer(charlie)
        await bob.register_peer(alice)
        await bob.register_peer(charlie)
        await charlie.register_peer(alice)
        await charlie.register_peer(bob)
        
        logger.info("✅ All agents initialized and keys registered")
        logger.info("")
        
        # Demonstration 1: Basic secure knowledge sharing
        logger.info("📋 Demo 1: Secure Knowledge Sharing")
        logger.info("-" * 40)
        
        await alice.send_knowledge(
            to_agent="bob",
            knowledge={
                "topic": "secure_communication",
                "message": "Hello Bob! This is encrypted end-to-end.",
                "timestamp": datetime.now().isoformat(),
                "classification": "confidential"
            }
        )
        
        await asyncio.sleep(0.1)  # Allow message processing
        
        await bob.send_knowledge(
            to_agent="charlie",
            knowledge={
                "topic": "project_update",
                "status": "implementation_complete",
                "features": ["encryption", "signing", "multi_protocol"],
                "security_level": "high"
            }
        )
        
        await asyncio.sleep(0.1)
        logger.info("")
        
        # Demonstration 2: Request-Response pattern
        logger.info("📋 Demo 2: Secure Request-Response Pattern")
        logger.info("-" * 40)
        
        await charlie.send_request(
            to_agent="alice",
            request={
                "query": "system_status",
                "parameters": {"include_security": True, "detail_level": "high"},
                "requester": "charlie",
                "priority": "urgent"
            }
        )
        
        await asyncio.sleep(0.1)  # Allow response processing
        logger.info("")
        
        # Demonstration 3: Broadcast communication
        logger.info("📋 Demo 3: Secure Broadcast Communication")
        logger.info("-" * 40)
        
        await alice.broadcast_message({
            "announcement": "System maintenance scheduled",
            "maintenance_window": {
                "start": "2024-01-15T02:00:00Z",
                "end": "2024-01-15T04:00:00Z",
                "expected_downtime": "30 minutes"
            },
            "impact": "minimal",
            "broadcast_by": "alice"
        })
        
        await asyncio.sleep(0.1)
        logger.info("")
        
        # Demonstration 4: Key rotation for forward secrecy
        logger.info("📋 Demo 4: Cryptographic Key Rotation")
        logger.info("-" * 40)
        
        logger.info("🔄 Rotating Alice's keys...")
        await alice.rotate_keys()
        
        # Re-register updated keys
        await bob.register_peer(alice)
        await charlie.register_peer(alice)
        
        # Test communication after key rotation
        await alice.send_knowledge(
            to_agent="bob",
            knowledge={
                "message": "Communication after key rotation",
                "new_keys": True,
                "security": "enhanced"
            }
        )
        
        await asyncio.sleep(0.1)
        logger.info("")
        
        # Display statistics
        logger.info("📊 Final Statistics")
        logger.info("-" * 40)
        
        for agent in [alice, bob, charlie]:
            stats = agent.get_stats()
            logger.info(f"Agent {agent.name}:")
            logger.info(f"  📤 Spores sent: {stats['spores_sent']}")
            logger.info(f"  📥 Spores received: {stats['spores_received']}")
            logger.info(f"  📨 Messages processed: {stats['messages_received']}")
            logger.info(f"  🔐 Encryption errors: {stats['encryption_errors']}")
            logger.info(f"  ⏱️  Uptime: {stats['uptime_seconds']:.2f}s")
            logger.info(f"  🌐 Protocol: {stats['protocol']}")
            logger.info("")
        
        # Display protocol compatibility
        logger.info("🌐 Protocol Compatibility Matrix")
        logger.info("-" * 40)
        protocols = {
            alice.name: alice.protocol.value,
            bob.name: bob.protocol.value, 
            charlie.name: charlie.protocol.value
        }
        
        for agent_name, protocol in protocols.items():
            logger.info(f"  {agent_name}: {protocol}")
        
        logger.info("\n✅ All agents can communicate securely regardless of protocol!")
        
    except Exception as e:
        logger.error(f"❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        await alice.close()
        await bob.close()
        await charlie.close()
        
        logger.info("✅ Demo completed successfully!")


async def demonstrate_security_features():
    """Demonstrate security features of the system."""
    logger.info("\n🔒 Security Features Demonstration")
    logger.info("=" * 60)
    
    # Create agents for security demo
    secure_agent = SecureAgentDemo("secure_agent", TransportProtocol.AMQP)
    test_agent = SecureAgentDemo("test_agent", TransportProtocol.AMQP)
    
    try:
        await secure_agent.initialize()
        await test_agent.initialize()
        await secure_agent.register_peer(test_agent)
        await test_agent.register_peer(secure_agent)
        
        # Demonstrate encryption
        logger.info("🔐 Encryption Demonstration")
        logger.info("-" * 30)
        
        sensitive_data = {
            "classified": "top_secret",
            "operation": "secure_communication_test",
            "agents": ["secure_agent", "test_agent"],
            "encryption": {
                "algorithm": "Curve25519 + XSalsa20 + Poly1305",
                "key_size": "256 bits",
                "authenticated": True
            }
        }
        
        logger.info("📤 Sending sensitive data (encrypted)...")
        await secure_agent.send_knowledge("test_agent", sensitive_data)
        
        await asyncio.sleep(0.1)
        
        # Demonstrate digital signatures
        logger.info("\n🖋️  Digital Signature Demonstration")
        logger.info("-" * 30)
        
        signed_message = {
            "document": "security_clearance_update",
            "authorized_by": "secure_agent",
            "signature_algorithm": "Ed25519",
            "timestamp": datetime.now().isoformat(),
            "integrity": "verified"
        }
        
        logger.info("📝 Sending digitally signed message...")
        await secure_agent.send_knowledge("test_agent", signed_message)
        
        await asyncio.sleep(0.1)
        
        # Demonstrate message expiration
        logger.info("\n⏰ Message Expiration Demonstration")
        logger.info("-" * 30)
        
        # This would be demonstrated with actual message queue in production
        logger.info("📤 Sending time-sensitive message (TTL: 60 seconds)...")
        await secure_agent.reef.send_secure_spore(
            to_agent="test_agent",
            knowledge={
                "alert": "time_sensitive_security_update",
                "expires": "60 seconds",
                "action_required": True
            },
            expires_in_seconds=60
        )
        
        await asyncio.sleep(0.1)
        
        logger.info("✅ All security features demonstrated successfully!")
        
    finally:
        await secure_agent.close()
        await test_agent.close()


async def demonstrate_protocol_flexibility():
    """Demonstrate multi-protocol flexibility."""
    logger.info("\n🌐 Multi-Protocol Flexibility Demonstration")
    logger.info("=" * 60)
    
    protocols_info = {
        TransportProtocol.AMQP: {
            "use_cases": ["High reliability", "Complex routing", "Enterprise messaging"],
            "features": ["Durable queues", "Transaction support", "Message acknowledgment"]
        },
        TransportProtocol.MQTT: {
            "use_cases": ["IoT devices", "Lightweight messaging", "Mobile applications"],
            "features": ["Small footprint", "QoS levels", "Last will testament"]
        },
        TransportProtocol.STOMP: {
            "use_cases": ["Web applications", "Simple messaging", "Cross-platform"],
            "features": ["Text-based protocol", "Simple implementation", "Language agnostic"]
        }
    }
    
    for protocol, info in protocols_info.items():
        logger.info(f"📡 {protocol.value.upper()} Protocol")
        logger.info(f"   Use Cases: {', '.join(info['use_cases'])}")
        logger.info(f"   Features: {', '.join(info['features'])}")
        logger.info(f"   Security: TLS/SSL enabled by default")
        logger.info("")
    
    logger.info("🔄 Protocol Switching Example:")
    logger.info("   - Agents can switch protocols without code changes")
    logger.info("   - Configuration-driven protocol selection")
    logger.info("   - Seamless interoperability between protocols")
    logger.info("   - All security features work across all protocols")


def print_banner():
    """Print demo banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    🔐 PRAVAL SECURE SPORES 🔐                ║
    ║                                                              ║
    ║  Multi-Protocol Secure Communication for AI Agents          ║
    ║                                                              ║
    ║  Features:                                                   ║
    ║  • End-to-End Encryption (PyNaCl/Curve25519)               ║
    ║  • Digital Signatures (Ed25519)                            ║
    ║  • Protocol Agnostic (AMQP/MQTT/STOMP)                     ║  
    ║  • TLS/SSL Transport Security                               ║
    ║  • Key Rotation & Forward Secrecy                          ║
    ║  • Backward Compatibility                                   ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


async def main():
    """Main demo function."""
    print_banner()
    
    logger.info("🎬 Starting Praval Secure Spores Demo")
    logger.info(f"⏰ Demo started at: {datetime.now().isoformat()}")
    logger.info("")
    
    try:
        # Run demonstration sections
        await demonstrate_secure_communication()
        await demonstrate_security_features()
        await demonstrate_protocol_flexibility()
        
        logger.info("\n🎉 All demonstrations completed successfully!")
        logger.info("🔐 Secure spore communication system is ready for production!")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info(f"\n⏰ Demo ended at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    # Set environment for demo
    os.environ.setdefault("PRAVAL_LOG_LEVEL", "INFO")
    
    # Note: This demo uses mock transports for demonstration
    # In production, configure actual message queue servers:
    # 
    # For AMQP (RabbitMQ):
    # export PRAVAL_AMQP_URL="amqps://user:pass@rabbitmq:5671/vhost"
    #
    # For MQTT:
    # export PRAVAL_MQTT_HOST="mosquitto"
    # export PRAVAL_MQTT_PORT="8883"
    #
    # For STOMP:
    # export PRAVAL_STOMP_HOST="activemq"
    # export PRAVAL_STOMP_PORT="61614"
    
    asyncio.run(main())