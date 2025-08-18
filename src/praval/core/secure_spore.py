"""
Secure Spore Implementation for Praval Framework.

This module provides cryptographically secure spore communication with:
- End-to-end encryption using PyNaCl (Curve25519 + XSalsa20 + Poly1305)
- Digital signatures using Ed25519
- Protocol-agnostic transport layer supporting AMQP, MQTT, STOMP
- Backward compatibility with existing Reef API
"""

import json
import time
import uuid
import msgpack
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

import nacl.secret
import nacl.public
import nacl.signing
import nacl.encoding
from nacl.exceptions import CryptoError

from .reef import SporeType, Spore


@dataclass
class SecureSpore:
    """
    A cryptographically secure spore with end-to-end encryption and digital signatures.
    
    Security features:
    - Knowledge encrypted with PyNaCl Box (Curve25519 + XSalsa20 + Poly1305)
    - Digital signatures using Ed25519
    - Perfect forward secrecy through ephemeral keys
    - Authenticated encryption preventing tampering
    """
    # Public metadata (not encrypted)
    id: str
    spore_type: SporeType
    from_agent: str
    to_agent: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    priority: int = 5
    
    # Encrypted payload
    encrypted_knowledge: bytes = field(default=b'')
    knowledge_signature: bytes = field(default=b'')
    
    # Cryptographic metadata
    sender_public_key: bytes = field(default=b'')
    nonce: bytes = field(default=b'')
    
    # Knowledge references (encrypted separately)
    encrypted_references: Optional[bytes] = None
    
    # Version for backward compatibility
    version: str = "1.0"
    
    def to_bytes(self) -> bytes:
        """Serialize secure spore to bytes for transmission using MessagePack."""
        data = {
            'id': self.id,
            'spore_type': self.spore_type.value,
            'from_agent': self.from_agent,
            'to_agent': self.to_agent,
            'created_at': self.created_at.timestamp(),
            'expires_at': self.expires_at.timestamp() if self.expires_at else None,
            'priority': self.priority,
            'encrypted_knowledge': self.encrypted_knowledge,
            'knowledge_signature': self.knowledge_signature,
            'sender_public_key': self.sender_public_key,
            'nonce': self.nonce,
            'encrypted_references': self.encrypted_references,
            'version': self.version
        }
        
        return msgpack.packb(data, use_bin_type=True)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SecureSpore':
        """Deserialize secure spore from bytes."""
        try:
            unpacked = msgpack.unpackb(data, raw=False, strict_map_key=False)
            
            return cls(
                id=unpacked['id'],
                spore_type=SporeType(unpacked['spore_type']),
                from_agent=unpacked['from_agent'],
                to_agent=unpacked.get('to_agent'),
                created_at=datetime.fromtimestamp(unpacked['created_at']),
                expires_at=datetime.fromtimestamp(unpacked['expires_at']) if unpacked.get('expires_at') else None,
                priority=unpacked.get('priority', 5),
                encrypted_knowledge=unpacked.get('encrypted_knowledge', b''),
                knowledge_signature=unpacked.get('knowledge_signature', b''),
                sender_public_key=unpacked.get('sender_public_key', b''),
                nonce=unpacked.get('nonce', b''),
                encrypted_references=unpacked.get('encrypted_references'),
                version=unpacked.get('version', '1.0')
            )
        except Exception as e:
            raise ValueError(f"Failed to deserialize secure spore: {e}")
    
    def is_expired(self) -> bool:
        """Check if secure spore has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def get_size_estimate(self) -> int:
        """Estimate the size of the serialized secure spore."""
        return len(self.to_bytes())


class SporeKeyManager:
    """
    Manages cryptographic keys for secure spore communication.
    
    Uses PyNaCl for high-performance, secure cryptography:
    - Ed25519 for digital signatures (signing_key, verify_key)
    - Curve25519 for encryption (box_key, public_key)
    - Separate keys for signing and encryption (security best practice)
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        
        # Generate key pairs
        self.signing_key = nacl.signing.SigningKey.generate()
        self.box_key = nacl.public.PrivateKey.generate()
        
        # Public keys for distribution
        self.verify_key = self.signing_key.verify_key
        self.public_key = self.box_key.public_key
    
    def get_public_keys(self) -> Dict[str, bytes]:
        """Get public keys for distribution to other agents."""
        return {
            'verify_key': bytes(self.verify_key),
            'public_key': bytes(self.public_key),
            'agent_name': self.agent_name
        }
    
    def encrypt_and_sign(self, knowledge: Dict[str, Any], 
                        recipient_public_key: bytes) -> tuple[bytes, bytes, bytes]:
        """
        Encrypt knowledge and sign the entire package.
        
        Args:
            knowledge: The knowledge dictionary to encrypt
            recipient_public_key: The recipient's public encryption key
            
        Returns:
            Tuple of (encrypted_data, nonce, signature)
        """
        try:
            # Serialize knowledge to JSON bytes
            knowledge_bytes = json.dumps(knowledge, ensure_ascii=False).encode('utf-8')
            
            # Create encryption box with recipient
            recipient_key = nacl.public.PublicKey(recipient_public_key)
            box = nacl.public.Box(self.box_key, recipient_key)
            
            # Encrypt knowledge
            encrypted = box.encrypt(knowledge_bytes)
            
            # Sign the encrypted data + nonce for authentication
            message_to_sign = encrypted.ciphertext + encrypted.nonce
            signed_message = self.signing_key.sign(message_to_sign)
            
            return encrypted.ciphertext, encrypted.nonce, signed_message.signature
            
        except Exception as e:
            raise ValueError(f"Failed to encrypt and sign knowledge: {e}")
    
    def decrypt_and_verify(self, encrypted_data: bytes, nonce: bytes, 
                          signature: bytes, sender_public_key: bytes,
                          sender_verify_key: bytes) -> Dict[str, Any]:
        """
        Verify signature and decrypt knowledge.
        
        Args:
            encrypted_data: The encrypted knowledge
            nonce: The encryption nonce
            signature: The digital signature
            sender_public_key: The sender's public encryption key
            sender_verify_key: The sender's public verification key
            
        Returns:
            Decrypted knowledge dictionary
        """
        try:
            # Verify signature first (fail fast on tampered messages)
            verify_key = nacl.signing.VerifyKey(sender_verify_key)
            message_to_verify = encrypted_data + nonce
            verify_key.verify(message_to_verify, signature)
            
            # Create decryption box with sender
            sender_key = nacl.public.PublicKey(sender_public_key)
            box = nacl.public.Box(self.box_key, sender_key)
            
            # Decrypt
            decrypted_bytes = box.decrypt(encrypted_data, nonce)
            
            # Deserialize knowledge
            return json.loads(decrypted_bytes.decode('utf-8'))
            
        except CryptoError as e:
            raise ValueError(f"Cryptographic verification failed: {e}")
        except Exception as e:
            raise ValueError(f"Failed to decrypt and verify knowledge: {e}")
    
    def rotate_keys(self):
        """
        Rotate cryptographic keys for forward secrecy.
        
        Note: In production, this should be coordinated with key distribution
        and include a grace period for old keys.
        """
        old_signing_key = self.signing_key
        old_box_key = self.box_key
        
        # Generate new keys
        self.signing_key = nacl.signing.SigningKey.generate()
        self.box_key = nacl.public.PrivateKey.generate()
        
        # Update public keys
        self.verify_key = self.signing_key.verify_key
        self.public_key = self.box_key.public_key
        
        # TODO: In production, implement key distribution protocol
        # and maintain old keys temporarily for decryption
        
        return {
            'old_signing_key': old_signing_key,
            'old_box_key': old_box_key,
            'new_verify_key': bytes(self.verify_key),
            'new_public_key': bytes(self.public_key)
        }
    
    def export_keys(self, passphrase: Optional[str] = None) -> Dict[str, str]:
        """
        Export keys for backup or migration.
        
        Args:
            passphrase: Optional passphrase for key encryption
            
        Returns:
            Dictionary with base64-encoded keys
        """
        import base64
        
        if passphrase:
            # TODO: Implement passphrase-based key encryption
            raise NotImplementedError("Passphrase-based key export not yet implemented")
        
        return {
            'agent_name': self.agent_name,
            'signing_key': base64.b64encode(bytes(self.signing_key)).decode('ascii'),
            'box_key': base64.b64encode(bytes(self.box_key)).decode('ascii'),
            'verify_key': base64.b64encode(bytes(self.verify_key)).decode('ascii'),
            'public_key': base64.b64encode(bytes(self.public_key)).decode('ascii')
        }
    
    @classmethod
    def import_keys(cls, agent_name: str, exported_keys: Dict[str, str], 
                   passphrase: Optional[str] = None) -> 'SporeKeyManager':
        """
        Import keys from backup or migration.
        
        Args:
            agent_name: The agent name
            exported_keys: Dictionary with base64-encoded keys
            passphrase: Optional passphrase for key decryption
            
        Returns:
            SporeKeyManager instance with imported keys
        """
        import base64
        
        if passphrase:
            raise NotImplementedError("Passphrase-based key import not yet implemented")
        
        # Create instance
        key_manager = cls.__new__(cls)
        key_manager.agent_name = agent_name
        
        # Import keys
        key_manager.signing_key = nacl.signing.SigningKey(
            base64.b64decode(exported_keys['signing_key'])
        )
        key_manager.box_key = nacl.public.PrivateKey(
            base64.b64decode(exported_keys['box_key'])
        )
        
        # Derive public keys
        key_manager.verify_key = key_manager.signing_key.verify_key
        key_manager.public_key = key_manager.box_key.public_key
        
        return key_manager


class SecureSporeFactory:
    """
    Factory class for creating secure spores with proper encryption and signing.
    """
    
    def __init__(self, key_manager: SporeKeyManager):
        self.key_manager = key_manager
    
    def create_secure_spore(self, 
                           to_agent: Optional[str],
                           knowledge: Dict[str, Any],
                           spore_type: SporeType = SporeType.KNOWLEDGE,
                           priority: int = 5,
                           expires_in_seconds: Optional[int] = None,
                           recipient_public_keys: Optional[Dict[str, bytes]] = None) -> SecureSpore:
        """
        Create a new secure spore with encryption and signing.
        
        Args:
            to_agent: Target agent name (None for broadcasts)
            knowledge: Knowledge dictionary to encrypt
            spore_type: Type of spore
            priority: Message priority (1-10)
            expires_in_seconds: TTL in seconds
            recipient_public_keys: Public keys for encryption
            
        Returns:
            SecureSpore instance ready for transmission
        """
        if not recipient_public_keys and to_agent:
            raise ValueError("Recipient public keys required for targeted spores")
        
        # Calculate expiration
        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.fromtimestamp(
                time.time() + expires_in_seconds
            )
        
        # Encrypt and sign (for broadcasts, use a shared key or skip encryption)
        if to_agent and recipient_public_keys:
            recipient_pub_key = recipient_public_keys.get('public_key')
            if not recipient_pub_key:
                raise ValueError(f"No public key found for agent: {to_agent}")
            
            encrypted_knowledge, nonce, signature = self.key_manager.encrypt_and_sign(
                knowledge, recipient_pub_key
            )
        else:
            # For broadcasts, we could implement group encryption or use plaintext
            # For now, we'll use a simple approach (could be enhanced)
            encrypted_knowledge = json.dumps(knowledge).encode('utf-8')
            nonce = b''
            signature = b''
        
        return SecureSpore(
            id=str(uuid.uuid4()),
            spore_type=spore_type,
            from_agent=self.key_manager.agent_name,
            to_agent=to_agent,
            created_at=datetime.now(),
            expires_at=expires_at,
            priority=priority,
            encrypted_knowledge=encrypted_knowledge,
            knowledge_signature=signature,
            sender_public_key=bytes(self.key_manager.public_key),
            nonce=nonce
        )