"""
Secure Reef Implementation with Multi-Protocol Message Queue Support.

This module provides the secure communication layer for Praval agents with:
- End-to-end encryption using PyNaCl
- Protocol-agnostic transport (AMQP, MQTT, STOMP)
- Backward compatibility with existing Reef API
- Key management and distribution
- Message authenticity and integrity
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta

from .secure_spore import SecureSpore, SporeKeyManager, SecureSporeFactory
from .transport import MessageTransport, TransportFactory, TransportProtocol
from .reef import Spore, SporeType

logger = logging.getLogger(__name__)


class KeyRegistry:
    """
    Distributed key registry for agent public key management.
    
    In production, this would be backed by Redis, database, or another
    message queue for distributed key storage and retrieval.
    """
    
    def __init__(self):
        self._keys: Dict[str, Dict[str, bytes]] = {}
        self._lock = asyncio.Lock()
    
    async def register_agent(self, agent_name: str, public_keys: Dict[str, bytes]):
        """Register an agent's public keys."""
        async with self._lock:
            self._keys[agent_name] = public_keys
            logger.debug(f"Registered public keys for agent: {agent_name}")
    
    async def get_agent_keys(self, agent_name: str) -> Optional[Dict[str, bytes]]:
        """Retrieve an agent's public keys."""
        async with self._lock:
            return self._keys.get(agent_name)
    
    async def remove_agent(self, agent_name: str):
        """Remove an agent's public keys."""
        async with self._lock:
            self._keys.pop(agent_name, None)
            logger.debug(f"Removed public keys for agent: {agent_name}")
    
    async def list_agents(self) -> List[str]:
        """List all registered agents."""
        async with self._lock:
            return list(self._keys.keys())


class SecureReef:
    """
    Multi-protocol secure reef communication system with pluggable transports.
    
    Features:
    - End-to-end encryption with PyNaCl
    - Protocol-agnostic (AMQP, MQTT, STOMP)
    - Automatic key management
    - Backward compatibility
    - Message authenticity verification
    """
    
    def __init__(self, 
                 protocol: TransportProtocol = TransportProtocol.AMQP,
                 transport_config: Optional[Dict[str, Any]] = None,
                 key_registry: Optional[KeyRegistry] = None):
        self.protocol = protocol
        self.transport_config = transport_config or {}
        self.transport = TransportFactory.create_transport(protocol)
        
        self.key_manager: Optional[SporeKeyManager] = None
        self.spore_factory: Optional[SecureSporeFactory] = None
        self.key_registry = key_registry or KeyRegistry()
        
        self.agent_name: Optional[str] = None
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.connected = False
        
        # Statistics
        self.stats = {
            'spores_sent': 0,
            'spores_received': 0,
            'encryption_errors': 0,
            'started_at': datetime.now()
        }
    
    async def initialize(self, agent_name: str):
        """Initialize secure reef with cryptographic keys and transport."""
        self.agent_name = agent_name
        
        # Initialize cryptographic components
        self.key_manager = SporeKeyManager(agent_name)
        self.spore_factory = SecureSporeFactory(self.key_manager)
        
        # Register our public keys
        await self.key_registry.register_agent(
            agent_name, 
            self.key_manager.get_public_keys()
        )
        
        # Initialize transport layer
        try:
            await self.transport.initialize(self.transport_config)
            self.connected = True
            
            # Setup protocol-specific message patterns
            await self._setup_subscriptions()
            
            logger.info(f"Secure reef initialized for agent '{agent_name}' using {self.protocol.value}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize secure reef: {e}")
    
    async def _setup_subscriptions(self):
        """Setup protocol-specific subscriptions for incoming messages."""
        if self.protocol == TransportProtocol.AMQP:
            # Subscribe to agent-specific routing keys
            await self.transport.subscribe(
                f"agent.{self.agent_name}.*",
                self._handle_incoming_message
            )
            # Subscribe to broadcasts
            await self.transport.subscribe(
                "broadcast.*",
                self._handle_incoming_message
            )
            
        elif self.protocol == TransportProtocol.MQTT:
            # Subscribe to agent-specific topics
            await self.transport.subscribe(
                f"agent/{self.agent_name}/+",
                self._handle_incoming_message
            )
            # Subscribe to broadcasts
            await self.transport.subscribe(
                "broadcast/+",
                self._handle_incoming_message
            )
            
        elif self.protocol == TransportProtocol.STOMP:
            # Subscribe to agent-specific destinations
            await self.transport.subscribe(
                f"agent.{self.agent_name}",
                self._handle_incoming_message
            )
            # Subscribe to broadcasts
            await self.transport.subscribe(
                "broadcast",
                self._handle_incoming_message
            )
    
    async def send_secure_spore(self,
                               to_agent: Optional[str],
                               knowledge: Dict[str, Any],
                               spore_type: SporeType = SporeType.KNOWLEDGE,
                               priority: int = 5,
                               expires_in_seconds: Optional[int] = None) -> str:
        """Send a cryptographically secure spore."""
        if not self.connected:
            raise ConnectionError("Secure reef not connected")
        
        try:
            # Get recipient public keys for encryption
            recipient_keys = None
            if to_agent:
                recipient_keys = await self.key_registry.get_agent_keys(to_agent)
                if not recipient_keys:
                    raise ValueError(f"No public keys found for agent: {to_agent}")
            
            # Create secure spore
            secure_spore = self.spore_factory.create_secure_spore(
                to_agent=to_agent,
                knowledge=knowledge,
                spore_type=spore_type,
                priority=priority,
                expires_in_seconds=expires_in_seconds,
                recipient_public_keys=recipient_keys
            )
            
            # Generate protocol-specific topic
            topic = self._generate_topic(to_agent, spore_type.value)
            
            # Send via transport
            await self.transport.publish(
                topic=topic,
                message=secure_spore.to_bytes(),
                priority=priority,
                ttl=expires_in_seconds
            )
            
            self.stats['spores_sent'] += 1
            logger.debug(f"Sent secure spore {secure_spore.id} to {to_agent or 'broadcast'}")
            
            return secure_spore.id
            
        except Exception as e:
            logger.error(f"Failed to send secure spore: {e}")
            raise
    
    def _generate_topic(self, recipient: Optional[str], message_type: str) -> str:
        """Generate protocol-appropriate topic/routing key."""
        if self.protocol == TransportProtocol.AMQP:
            return f'agent.{recipient}.{message_type}' if recipient else f'broadcast.{message_type}'
        elif self.protocol == TransportProtocol.MQTT:
            return f'agent/{recipient}/{message_type}' if recipient else f'broadcast/{message_type}'
        elif self.protocol == TransportProtocol.STOMP:
            return f'agent.{recipient}.{message_type}' if recipient else f'broadcast.{message_type}'
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
    
    async def _handle_incoming_message(self, message_data: bytes):
        """Handle incoming secure spore messages."""
        try:
            # Deserialize secure spore
            secure_spore = SecureSpore.from_bytes(message_data)
            
            # Skip expired messages
            if secure_spore.is_expired():
                logger.debug(f"Skipping expired secure spore: {secure_spore.id}")
                return
            
            # Skip our own messages
            if secure_spore.from_agent == self.agent_name:
                return
            
            # Decrypt and verify
            decrypted_knowledge = await self._decrypt_spore(secure_spore)
            
            # Create traditional spore for backward compatibility
            traditional_spore = Spore(
                id=secure_spore.id,
                spore_type=secure_spore.spore_type,
                from_agent=secure_spore.from_agent,
                to_agent=secure_spore.to_agent,
                knowledge=decrypted_knowledge,
                created_at=secure_spore.created_at,
                expires_at=secure_spore.expires_at,
                priority=secure_spore.priority
            )
            
            # Notify handlers
            await self._notify_handlers(traditional_spore)
            self.stats['spores_received'] += 1
            
        except Exception as e:
            logger.error(f"Failed to process incoming secure spore: {e}")
            self.stats['encryption_errors'] += 1
    
    async def _decrypt_spore(self, secure_spore: SecureSpore) -> Dict[str, Any]:
        """Decrypt and verify a secure spore."""
        # For broadcast messages without encryption, handle plaintext
        if not secure_spore.nonce and not secure_spore.knowledge_signature:
            return json.loads(secure_spore.encrypted_knowledge.decode('utf-8'))
        
        # Get sender's public keys
        sender_keys = await self.key_registry.get_agent_keys(secure_spore.from_agent)
        if not sender_keys:
            raise ValueError(f"No public keys found for sender: {secure_spore.from_agent}")
        
        # Decrypt and verify
        return self.key_manager.decrypt_and_verify(
            secure_spore.encrypted_knowledge,
            secure_spore.nonce,
            secure_spore.knowledge_signature,
            sender_keys['public_key'],
            sender_keys['verify_key']
        )
    
    async def _notify_handlers(self, spore: Spore):
        """Notify registered spore handlers."""
        handler_key = spore.spore_type.value
        handlers = self.message_handlers.get(handler_key, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(spore)
                else:
                    handler(spore)
            except Exception as e:
                logger.error(f"Handler error for spore {spore.id}: {e}")
    
    def register_handler(self, spore_type: SporeType, handler: Callable):
        """Register a handler for specific spore types."""
        handler_key = spore_type.value
        if handler_key not in self.message_handlers:
            self.message_handlers[handler_key] = []
        
        self.message_handlers[handler_key].append(handler)
        logger.debug(f"Registered handler for spore type: {spore_type.value}")
    
    def unregister_handler(self, spore_type: SporeType, handler: Callable):
        """Unregister a handler for specific spore types."""
        handler_key = spore_type.value
        if handler_key in self.message_handlers:
            try:
                self.message_handlers[handler_key].remove(handler)
            except ValueError:
                pass
    
    # Backward compatibility methods
    
    async def send(self,
                  from_agent: str,
                  to_agent: Optional[str],
                  knowledge: Dict[str, Any],
                  spore_type: SporeType = SporeType.KNOWLEDGE,
                  priority: int = 5,
                  expires_in_seconds: Optional[int] = None,
                  **kwargs) -> str:
        """Backward compatible send method."""
        return await self.send_secure_spore(
            to_agent=to_agent,
            knowledge=knowledge,
            spore_type=spore_type,
            priority=priority,
            expires_in_seconds=expires_in_seconds
        )
    
    async def broadcast(self,
                       knowledge: Dict[str, Any],
                       spore_type: SporeType = SporeType.BROADCAST) -> str:
        """Broadcast knowledge to all agents."""
        return await self.send_secure_spore(
            to_agent=None,
            knowledge=knowledge,
            spore_type=spore_type
        )
    
    async def request(self,
                     to_agent: str,
                     request: Dict[str, Any],
                     expires_in_seconds: int = 300) -> str:
        """Send a request to another agent."""
        return await self.send_secure_spore(
            to_agent=to_agent,
            knowledge=request,
            spore_type=SporeType.REQUEST,
            expires_in_seconds=expires_in_seconds
        )
    
    async def reply(self,
                   to_agent: str,
                   response: Dict[str, Any],
                   reply_to_spore_id: str) -> str:
        """Reply to a request."""
        response_data = {
            **response,
            'reply_to': reply_to_spore_id
        }
        
        return await self.send_secure_spore(
            to_agent=to_agent,
            knowledge=response_data,
            spore_type=SporeType.RESPONSE
        )
    
    # Key management methods
    
    async def rotate_keys(self):
        """Rotate cryptographic keys."""
        if not self.key_manager:
            raise ValueError("Key manager not initialized")
        
        old_keys = self.key_manager.get_public_keys()
        rotation_result = self.key_manager.rotate_keys()
        
        # Update key registry
        await self.key_registry.register_agent(
            self.agent_name,
            self.key_manager.get_public_keys()
        )
        
        logger.info(f"Rotated keys for agent: {self.agent_name}")
        return rotation_result
    
    def export_keys(self, passphrase: Optional[str] = None) -> Dict[str, str]:
        """Export keys for backup."""
        if not self.key_manager:
            raise ValueError("Key manager not initialized")
        return self.key_manager.export_keys(passphrase)
    
    # Statistics and monitoring
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reef statistics."""
        uptime = datetime.now() - self.stats['started_at']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'agent_name': self.agent_name,
            'protocol': self.protocol.value,
            'connected': self.connected,
            'registered_agents': len(self.key_registry._keys) if self.key_registry else 0
        }
    
    async def close(self):
        """Close the secure reef connection."""
        if self.connected:
            await self.transport.close()
            self.connected = False
            
            if self.agent_name:
                await self.key_registry.remove_agent(self.agent_name)
            
            logger.info(f"Closed secure reef for agent: {self.agent_name}")


# Global secure reef instance
_global_secure_reef: Optional[SecureReef] = None


async def get_secure_reef(protocol: TransportProtocol = TransportProtocol.AMQP,
                         transport_config: Optional[Dict[str, Any]] = None) -> SecureReef:
    """Get or create the global secure reef instance."""
    global _global_secure_reef
    
    if _global_secure_reef is None:
        _global_secure_reef = SecureReef(protocol, transport_config)
    
    return _global_secure_reef


async def initialize_secure_reef(agent_name: str,
                                protocol: TransportProtocol = TransportProtocol.AMQP,
                                transport_config: Optional[Dict[str, Any]] = None) -> SecureReef:
    """Initialize the global secure reef for an agent."""
    secure_reef = await get_secure_reef(protocol, transport_config)
    await secure_reef.initialize(agent_name)
    return secure_reef


class SecureReefAdapter:
    """
    Adapter to maintain backward compatibility with existing Reef API.
    
    This allows existing code to work with secure spores transparently.
    """
    
    def __init__(self, secure_reef: SecureReef):
        self.secure_reef = secure_reef
        self._legacy_mode = False
    
    def send(self, from_agent: str, to_agent: str, knowledge: Dict, **kwargs) -> str:
        """Synchronous wrapper for send."""
        return asyncio.run(self.secure_reef.send(
            from_agent, to_agent, knowledge, **kwargs
        ))
    
    def broadcast(self, from_agent: str, knowledge: Dict, **kwargs) -> str:
        """Synchronous wrapper for broadcast."""
        return asyncio.run(self.secure_reef.broadcast(knowledge, **kwargs))
    
    def subscribe(self, agent_name: str, handler: Callable, **kwargs):
        """Register handler for spore types."""
        # This would need to be adapted based on how handlers are registered
        # in the original system
        pass