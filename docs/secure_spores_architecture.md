# Secure Spores with Multi-Protocol Message Queue Architecture

## Overview

This document outlines the architecture for implementing secure spore communication in Praval using a pluggable message queue backend that supports multiple protocols (AMQP, MQTT, STOMP, etc.) with PyNaCl for cryptographic operations.

## Design Goals

1. **Security by Default**: All spores are encrypted and signed by default
2. **Protocol Agnostic**: Support AMQP, MQTT, STOMP, and other protocols
3. **Performance**: Minimal overhead for cryptographic operations
4. **Compatibility**: Backward compatibility with existing reef API
5. **Scalability**: Distributed messaging with protocol-specific clustering
6. **Reliability**: Message durability and delivery guarantees
7. **Flexibility**: Support for both synchronous and asynchronous operations
8. **Transport Security**: TLS/SSL by default across all protocols

## Architecture Components

### 1. Secure Spore Structure

```python
@dataclass
class SecureSpore:
    """
    A cryptographically secure spore with encryption and digital signatures.
    """
    # Public metadata (not encrypted)
    id: str
    spore_type: SporeType
    from_agent: str
    to_agent: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    priority: int
    
    # Encrypted payload
    encrypted_knowledge: bytes  # PyNaCl Box encrypted
    knowledge_signature: bytes  # PyNaCl signing
    
    # Cryptographic metadata
    sender_public_key: bytes
    nonce: bytes  # For encryption
    
    # Knowledge references (encrypted separately)
    encrypted_references: Optional[bytes]
```

### 2. Cryptographic Key Management

```python
class SporeKeyManager:
    """
    Manages cryptographic keys for secure spore communication.
    Uses PyNaCl for high-performance cryptography.
    """
    
    def __init__(self, agent_name: str):
        # Each agent has dedicated key pairs
        self.agent_name = agent_name
        self.signing_key = nacl.signing.SigningKey.generate()
        self.box_key = nacl.public.PrivateKey.generate()
        
        # Public keys for verification/encryption
        self.verify_key = self.signing_key.verify_key
        self.public_key = self.box_key.public_key
    
    def encrypt_and_sign(self, knowledge: Dict, recipient_public_key: bytes) -> Tuple[bytes, bytes, bytes]:
        """Encrypt knowledge and sign the entire spore."""
        # Serialize knowledge
        knowledge_bytes = json.dumps(knowledge).encode('utf-8')
        
        # Create encryption box with recipient
        recipient_key = nacl.public.PublicKey(recipient_public_key)
        box = nacl.public.Box(self.box_key, recipient_key)
        
        # Encrypt knowledge
        encrypted = box.encrypt(knowledge_bytes)
        
        # Sign the encrypted data
        signature = self.signing_key.sign(encrypted.ciphertext + encrypted.nonce)
        
        return encrypted.ciphertext, encrypted.nonce, signature.signature
    
    def decrypt_and_verify(self, encrypted_data: bytes, nonce: bytes, 
                          signature: bytes, sender_public_key: bytes) -> Dict:
        """Decrypt knowledge and verify signature."""
        # Verify signature first
        sender_verify_key = nacl.signing.VerifyKey(sender_public_key)
        sender_verify_key.verify(encrypted_data + nonce, signature)
        
        # Create decryption box
        sender_key = nacl.public.PublicKey(sender_public_key)
        box = nacl.public.Box(self.box_key, sender_key)
        
        # Decrypt
        decrypted = box.decrypt(encrypted_data, nonce)
        return json.loads(decrypted.decode('utf-8'))
```

### 3. Transport Abstraction Layer

```python
from abc import ABC, abstractmethod
from enum import Enum

class TransportProtocol(Enum):
    AMQP = "amqp"
    MQTT = "mqtt"
    STOMP = "stomp"
    REDIS = "redis"
    NATS = "nats"

class MessageTransport(ABC):
    """Abstract base class for message queue transports."""
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the transport connection."""
        pass
    
    @abstractmethod
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish a message to a topic/queue."""
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic/queue with callback."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""
        pass

class AMQPTransport(MessageTransport):
    """AMQP transport implementation (RabbitMQ, ActiveMQ, etc.)"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize AMQP connection with TLS."""
        import aio_pika
        
        connection_params = {
            'url': config.get('url', 'amqps://localhost:5671/'),
            'ssl': True,
            'ssl_options': {
                'ca_certs': config.get('ca_cert', 'ca_certificate.pem'),
                'keyfile': config.get('client_key', 'client_key.pem'),
                'certfile': config.get('client_cert', 'client_certificate.pem'),
            }
        }
        
        self.connection = await aio_pika.connect_robust(**connection_params)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=100)
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish to AMQP exchange."""
        exchange = await self.channel.declare_exchange(
            'praval.spores', aio_pika.ExchangeType.TOPIC, durable=True
        )
        
        await exchange.publish(
            aio_pika.Message(
                message,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=priority,
                expiration=ttl * 1000 if ttl else None
            ),
            routing_key=topic
        )

class MQTTTransport(MessageTransport):
    """MQTT transport implementation with TLS."""
    
    def __init__(self):
        self.client = None
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize MQTT connection with TLS."""
        import asyncio_mqtt
        import ssl
        
        # Setup TLS context
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.check_hostname = False
        ssl_context.load_verify_locations(config.get('ca_cert', 'ca_certificate.pem'))
        ssl_context.load_cert_chain(
            config.get('client_cert', 'client_certificate.pem'),
            config.get('client_key', 'client_key.pem')
        )
        
        self.client = asyncio_mqtt.Client(
            hostname=config.get('host', 'localhost'),
            port=config.get('port', 8883),  # MQTT over TLS
            tls_context=ssl_context,
            client_id=config.get('client_id', f'praval-{uuid.uuid4().hex[:8]}')
        )
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish to MQTT topic."""
        qos_map = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 1, 8: 2, 9: 2, 10: 2}
        qos = qos_map.get(priority, 1)
        
        await self.client.publish(
            topic=f"praval/spores/{topic}",
            payload=message,
            qos=qos,
            retain=False
        )

class STOMPTransport(MessageTransport):
    """STOMP transport implementation with TLS."""
    
    def __init__(self):
        self.connection = None
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize STOMP connection with TLS."""
        import aiostomp
        import ssl
        
        ssl_context = ssl.create_default_context()
        ssl_context.load_cert_chain(
            config.get('client_cert', 'client_certificate.pem'),
            config.get('client_key', 'client_key.pem')
        )
        
        self.connection = aiostomp.AioStomp(
            config.get('host', 'localhost'),
            config.get('port', 61614),  # STOMP over TLS
            ssl_context=ssl_context
        )
        
        await self.connection.connect()
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish to STOMP destination."""
        headers = {
            'priority': str(priority),
            'persistent': 'true'
        }
        
        if ttl:
            headers['expires'] = str(int(time.time() * 1000) + (ttl * 1000))
        
        await self.connection.send(
            destination=f'/topic/praval.spores.{topic}',
            body=message.decode('utf-8'),
            headers=headers
        )

class SecureReefMQ:
    """
    Multi-protocol secure reef communication system with pluggable transports.
    """
    
    def __init__(self, protocol: TransportProtocol = TransportProtocol.AMQP, 
                 transport_config: Optional[Dict[str, Any]] = None):
        self.protocol = protocol
        self.transport_config = transport_config or {}
        self.transport = self._create_transport()
        self.key_manager = None
        self.agent_name = None
    
    def _create_transport(self) -> MessageTransport:
        """Factory method to create appropriate transport based on protocol."""
        transport_map = {
            TransportProtocol.AMQP: AMQPTransport,
            TransportProtocol.MQTT: MQTTTransport,
            TransportProtocol.STOMP: STOMPTransport,
            # TransportProtocol.REDIS: RedisTransport,  # Future implementation
            # TransportProtocol.NATS: NATSTransport,    # Future implementation
        }
        
        transport_class = transport_map.get(self.protocol)
        if not transport_class:
            raise ValueError(f"Unsupported transport protocol: {self.protocol}")
        
        return transport_class()
        
    async def initialize(self, agent_name: str):
        """Initialize connection and cryptographic keys."""
        self.agent_name = agent_name
        self.key_manager = SporeKeyManager(agent_name)
        
        # Initialize the transport layer with TLS configuration
        await self.transport.initialize(self.transport_config)
        
        # Setup protocol-specific messaging patterns
        await self._setup_messaging_patterns()
    
    async def _setup_messaging_patterns(self):
        """Setup protocol-specific messaging patterns."""
        if self.protocol == TransportProtocol.AMQP:
            await self._setup_amqp_patterns()
        elif self.protocol == TransportProtocol.MQTT:
            await self._setup_mqtt_patterns()
        elif self.protocol == TransportProtocol.STOMP:
            await self._setup_stomp_patterns()
    
    async def _setup_amqp_patterns(self):
        """Setup AMQP-specific exchanges and queues."""
        # AMQP patterns are handled within the AMQPTransport
        pass
    
    async def _setup_mqtt_patterns(self):
        """Setup MQTT-specific subscriptions."""
        # Subscribe to agent-specific topics
        await self.transport.subscribe(
            f"praval/spores/agent/{self.agent_name}/+",
            self._handle_incoming_spore
        )
        
        # Subscribe to broadcast topics
        await self.transport.subscribe(
            f"praval/spores/broadcast/+",
            self._handle_incoming_spore
        )
    
    async def _setup_stomp_patterns(self):
        """Setup STOMP-specific subscriptions."""
        # Subscribe to agent-specific destinations
        await self.transport.subscribe(
            f"/topic/praval.spores.agent.{self.agent_name}",
            self._handle_incoming_spore
        )
        
        # Subscribe to broadcast destinations
        await self.transport.subscribe(
            f"/topic/praval.spores.broadcast",
            self._handle_incoming_spore
        )
    
    async def send_secure_spore(self, spore_data: Dict, recipient: Optional[str] = None):
        """Send a cryptographically secure spore."""
        # Get recipient public key (from key registry)
        recipient_public_key = await self._get_agent_public_key(recipient)
        
        # Encrypt and sign
        encrypted_knowledge, nonce, signature = self.key_manager.encrypt_and_sign(
            spore_data['knowledge'], 
            recipient_public_key
        )
        
        # Create secure spore
        secure_spore = SecureSpore(
            id=str(uuid.uuid4()),
            spore_type=SporeType(spore_data.get('type', 'knowledge')),
            from_agent=self.agent_name,
            to_agent=recipient,
            created_at=datetime.now(),
            encrypted_knowledge=encrypted_knowledge,
            knowledge_signature=signature,
            sender_public_key=self.key_manager.public_key.encode(),
            nonce=nonce
        )
        
        # Generate protocol-specific topic/routing key
        topic = self._generate_topic(recipient, spore_data.get('type', 'knowledge'))
        
        # Publish using transport abstraction
        await self.transport.publish(
            topic=topic,
            message=secure_spore.to_bytes(),
            priority=spore_data.get('priority', 5),
            ttl=spore_data.get('ttl', 3600)
        )
    
    def _generate_topic(self, recipient: Optional[str], message_type: str) -> str:
        """Generate protocol-appropriate topic/routing key."""
        if self.protocol == TransportProtocol.AMQP:
            return f'agent.{recipient}.{message_type}' if recipient else f'broadcast.{message_type}'
        elif self.protocol == TransportProtocol.MQTT:
            return f'praval/spores/agent/{recipient}/{message_type}' if recipient else f'praval/spores/broadcast/{message_type}'
        elif self.protocol == TransportProtocol.STOMP:
            return f'/topic/praval.spores.agent.{recipient}.{message_type}' if recipient else f'/topic/praval.spores.broadcast.{message_type}'
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
    
    async def _handle_incoming_spore(self, message):
        """Handle incoming secure spore messages."""
        try:
            # Deserialize secure spore
            secure_spore = SecureSpore.from_bytes(message)
            
            # Decrypt and verify
            decrypted_knowledge = self.key_manager.decrypt_and_verify(
                secure_spore.encrypted_knowledge,
                secure_spore.nonce,
                secure_spore.knowledge_signature,
                secure_spore.sender_public_key
            )
            
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
            
            # Delegate to registered handlers
            await self._notify_handlers(traditional_spore)
            
        except Exception as e:
            logger.error(f"Failed to process incoming secure spore: {e}")
    
    async def _notify_handlers(self, spore: Spore):
        """Notify registered spore handlers."""
        # Implementation would integrate with existing agent handler system
        pass
    
    async def _get_agent_public_key(self, agent_name: str) -> bytes:
        """Retrieve agent public key from distributed key registry."""
        # This could be Redis, database, or another RabbitMQ queue
        # For now, implement simple in-memory registry
        return await self._fetch_from_key_registry(agent_name)
```

### 4. Backward Compatibility Layer

```python
class SecureReefAdapter:
    """
    Adapter to maintain backward compatibility with existing Reef API.
    """
    
    def __init__(self):
        self.secure_reef = SecureReefMQ()
        self._legacy_mode = False
    
    def send(self, from_agent: str, to_agent: str, knowledge: Dict, **kwargs) -> str:
        """Maintain compatibility with existing reef.send() API."""
        if self._legacy_mode:
            return self._send_legacy(from_agent, to_agent, knowledge, **kwargs)
        else:
            return asyncio.run(self._send_secure(from_agent, to_agent, knowledge, **kwargs))
    
    async def _send_secure(self, from_agent: str, to_agent: str, knowledge: Dict, **kwargs):
        """Send using secure spore protocol."""
        spore_data = {
            'knowledge': knowledge,
            'type': kwargs.get('spore_type', 'knowledge').value,
            'priority': kwargs.get('priority', 5),
            'ttl': kwargs.get('expires_in_seconds', 3600)
        }
        
        await self.secure_reef.send_secure_spore(spore_data, to_agent)
```

## Security Features

### 1. End-to-End Encryption
- All spore knowledge is encrypted using PyNaCl Box (Curve25519 + XSalsa20 + Poly1305)
- Each agent has unique key pairs for encryption/decryption
- Perfect forward secrecy through ephemeral keys

### 2. Digital Signatures
- Every spore is digitally signed using Ed25519
- Prevents tampering and ensures message authenticity
- Non-repudiation of messages

### 3. Transport Security
- RabbitMQ connections use TLS 1.3
- Client certificates for mutual authentication
- Message durability with encrypted persistence

### 4. Key Management
- Automatic key rotation policies
- Secure key distribution through separate channels
- Hardware security module (HSM) support for production

## Performance Considerations

### 1. Cryptographic Overhead
- PyNaCl operations: ~10-50μs per message
- Acceptable for most agent communication patterns
- Batch processing for high-throughput scenarios

### 2. Message Queue Performance
- RabbitMQ clustering for horizontal scaling
- Message batching and compression
- Lazy queue declarations to reduce memory usage

### 3. Memory Management
- Secure memory clearing after use
- Connection pooling and reuse
- Efficient serialization with MessagePack

## Implementation Timeline

### Phase 1: Core Cryptography (Week 1)
- [ ] Implement SporeKeyManager with PyNaCl
- [ ] Create SecureSpore data structure
- [ ] Add basic encryption/decryption tests

### Phase 2: RabbitMQ Integration (Week 2)
- [ ] Implement SecureReefMQ class
- [ ] Add connection management and topology setup
- [ ] Integrate with existing reef API

### Phase 3: Security Hardening (Week 3)
- [ ] Add key rotation mechanisms
- [ ] Implement secure key distribution
- [ ] Add comprehensive security tests

### Phase 4: Production Features (Week 4)
- [ ] Docker configuration with RabbitMQ cluster
- [ ] Monitoring and observability
- [ ] Documentation and examples

## Security Audit Requirements

Before production deployment:
1. Third-party cryptographic review
2. Penetration testing of message queue infrastructure
3. Key management audit
4. Performance benchmarking under load

## Conclusion

This architecture provides enterprise-grade security for Praval's spore communication while maintaining the simplicity and elegance of the existing API. The use of PyNaCl ensures modern cryptographic standards, while RabbitMQ provides reliable, scalable message queuing infrastructure.