"""
Comprehensive tests for secure spore implementation.

This module tests:
- Secure spore creation and serialization
- Cryptographic operations (encryption, signing, verification)
- Key management functionality
- Message integrity and authenticity
- Performance characteristics
"""

import json
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from praval.core.secure_spore import (
    SecureSpore, SporeKeyManager, SecureSporeFactory
)
from praval.core.reef import SporeType


class TestSecureSpore:
    """Test secure spore data structure and serialization."""
    
    def test_secure_spore_creation(self):
        """Test basic secure spore creation."""
        spore = SecureSpore(
            id="test-id",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            created_at=datetime.now(),
            encrypted_knowledge=b"encrypted_data",
            knowledge_signature=b"signature",
            sender_public_key=b"public_key",
            nonce=b"nonce"
        )
        
        assert spore.id == "test-id"
        assert spore.spore_type == SporeType.KNOWLEDGE
        assert spore.from_agent == "agent1"
        assert spore.to_agent == "agent2"
        assert spore.version == "1.0"
    
    def test_secure_spore_serialization(self):
        """Test secure spore serialization and deserialization."""
        original = SecureSpore(
            id="test-id",
            spore_type=SporeType.BROADCAST,
            from_agent="agent1",
            to_agent=None,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            priority=7,
            encrypted_knowledge=b"encrypted_test_data",
            knowledge_signature=b"test_signature",
            sender_public_key=b"test_public_key",
            nonce=b"test_nonce"
        )
        
        # Serialize to bytes
        serialized = original.to_bytes()
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0
        
        # Deserialize from bytes
        deserialized = SecureSpore.from_bytes(serialized)
        
        # Verify all fields
        assert deserialized.id == original.id
        assert deserialized.spore_type == original.spore_type
        assert deserialized.from_agent == original.from_agent
        assert deserialized.to_agent == original.to_agent
        assert abs((deserialized.created_at - original.created_at).total_seconds()) < 1
        assert abs((deserialized.expires_at - original.expires_at).total_seconds()) < 1
        assert deserialized.priority == original.priority
        assert deserialized.encrypted_knowledge == original.encrypted_knowledge
        assert deserialized.knowledge_signature == original.knowledge_signature
        assert deserialized.sender_public_key == original.sender_public_key
        assert deserialized.nonce == original.nonce
    
    def test_secure_spore_expiration(self):
        """Test spore expiration logic."""
        # Non-expiring spore
        spore1 = SecureSpore(
            id="test1",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            created_at=datetime.now()
        )
        assert not spore1.is_expired()
        
        # Expired spore
        spore2 = SecureSpore(
            id="test2",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            created_at=datetime.now(),
            expires_at=datetime.now() - timedelta(minutes=1)
        )
        assert spore2.is_expired()
        
        # Future expiring spore
        spore3 = SecureSpore(
            id="test3",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        assert not spore3.is_expired()
    
    def test_secure_spore_size_estimation(self):
        """Test spore size estimation."""
        spore = SecureSpore(
            id="test-id",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            created_at=datetime.now(),
            encrypted_knowledge=b"test_data" * 100,  # Larger payload
            knowledge_signature=b"signature",
            sender_public_key=b"public_key",
            nonce=b"nonce"
        )
        
        size = spore.get_size_estimate()
        assert size > 0
        assert isinstance(size, int)
        
        # Should be approximately the serialized size
        actual_size = len(spore.to_bytes())
        assert abs(size - actual_size) < 100  # Within 100 bytes


class TestSporeKeyManager:
    """Test cryptographic key management."""
    
    def test_key_manager_initialization(self):
        """Test key manager initialization."""
        km = SporeKeyManager("test_agent")
        
        assert km.agent_name == "test_agent"
        assert km.signing_key is not None
        assert km.box_key is not None
        assert km.verify_key is not None
        assert km.public_key is not None
    
    def test_public_key_generation(self):
        """Test public key generation and format."""
        km = SporeKeyManager("test_agent")
        public_keys = km.get_public_keys()
        
        assert isinstance(public_keys, dict)
        assert 'verify_key' in public_keys
        assert 'public_key' in public_keys
        assert 'agent_name' in public_keys
        assert public_keys['agent_name'] == "test_agent"
        
        # Keys should be bytes
        assert isinstance(public_keys['verify_key'], bytes)
        assert isinstance(public_keys['public_key'], bytes)
        assert len(public_keys['verify_key']) == 32  # Ed25519 verify key
        assert len(public_keys['public_key']) == 32  # Curve25519 public key
    
    def test_encryption_and_signing(self):
        """Test end-to-end encryption and signing."""
        # Create two key managers (sender and recipient)
        sender_km = SporeKeyManager("sender")
        recipient_km = SporeKeyManager("recipient")
        
        # Test data
        knowledge = {
            "message": "Hello, secure world!",
            "timestamp": time.time(),
            "data": [1, 2, 3, {"nested": "value"}]
        }
        
        # Sender encrypts and signs
        recipient_public_key = bytes(recipient_km.public_key)
        encrypted_data, nonce, signature = sender_km.encrypt_and_sign(
            knowledge, recipient_public_key
        )
        
        assert isinstance(encrypted_data, bytes)
        assert isinstance(nonce, bytes)
        assert isinstance(signature, bytes)
        assert len(encrypted_data) > 0
        assert len(nonce) == 24  # XSalsa20 nonce
        assert len(signature) == 64  # Ed25519 signature
    
    def test_decryption_and_verification(self):
        """Test decryption and signature verification."""
        # Create key managers
        sender_km = SporeKeyManager("sender")
        recipient_km = SporeKeyManager("recipient")
        
        # Test data
        original_knowledge = {
            "secret": "classified information",
            "level": "top_secret",
            "clearance": ["alpha", "beta", "gamma"]
        }
        
        # Encrypt and sign
        recipient_public_key = bytes(recipient_km.public_key)
        encrypted_data, nonce, signature = sender_km.encrypt_and_sign(
            original_knowledge, recipient_public_key
        )
        
        # Decrypt and verify
        sender_public_key = bytes(sender_km.public_key)
        sender_verify_key = bytes(sender_km.verify_key)
        decrypted_knowledge = recipient_km.decrypt_and_verify(
            encrypted_data, nonce, signature, 
            sender_public_key, sender_verify_key
        )
        
        assert decrypted_knowledge == original_knowledge
    
    def test_encryption_with_wrong_recipient_key(self):
        """Test that wrong recipient keys cause decryption failure."""
        sender_km = SporeKeyManager("sender")
        recipient_km = SporeKeyManager("recipient")
        wrong_km = SporeKeyManager("wrong_agent")
        
        knowledge = {"test": "data"}
        
        # Encrypt with recipient key
        encrypted_data, nonce, signature = sender_km.encrypt_and_sign(
            knowledge, bytes(recipient_km.public_key)
        )
        
        # Try to decrypt with wrong key manager
        sender_public_key = bytes(sender_km.public_key)
        sender_verify_key = bytes(sender_km.verify_key)
        
        with pytest.raises(ValueError, match="Cryptographic verification failed"):
            wrong_km.decrypt_and_verify(
                encrypted_data, nonce, signature,
                sender_public_key, sender_verify_key
            )
    
    def test_signature_tampering_detection(self):
        """Test that tampered signatures are detected."""
        sender_km = SporeKeyManager("sender")
        recipient_km = SporeKeyManager("recipient")
        
        knowledge = {"important": "data"}
        
        # Encrypt and sign
        encrypted_data, nonce, signature = sender_km.encrypt_and_sign(
            knowledge, bytes(recipient_km.public_key)
        )
        
        # Tamper with signature
        tampered_signature = bytearray(signature)
        tampered_signature[0] = (tampered_signature[0] + 1) % 256
        tampered_signature = bytes(tampered_signature)
        
        # Verify tampering is detected
        sender_public_key = bytes(sender_km.public_key)
        sender_verify_key = bytes(sender_km.verify_key)
        
        with pytest.raises(ValueError, match="Cryptographic verification failed"):
            recipient_km.decrypt_and_verify(
                encrypted_data, nonce, tampered_signature,
                sender_public_key, sender_verify_key
            )
    
    def test_key_rotation(self):
        """Test cryptographic key rotation."""
        km = SporeKeyManager("test_agent")
        
        # Get original keys
        original_public_keys = km.get_public_keys()
        
        # Rotate keys
        rotation_result = km.rotate_keys()
        
        # Get new keys
        new_public_keys = km.get_public_keys()
        
        # Verify keys changed
        assert new_public_keys['verify_key'] != original_public_keys['verify_key']
        assert new_public_keys['public_key'] != original_public_keys['public_key']
        
        # Verify rotation result contains old keys
        assert 'old_signing_key' in rotation_result
        assert 'old_box_key' in rotation_result
        assert 'new_verify_key' in rotation_result
        assert 'new_public_key' in rotation_result
    
    def test_key_export_import(self):
        """Test key export and import functionality."""
        original_km = SporeKeyManager("test_agent")
        
        # Export keys
        exported_keys = original_km.export_keys()
        
        assert isinstance(exported_keys, dict)
        assert exported_keys['agent_name'] == "test_agent"
        assert 'signing_key' in exported_keys
        assert 'box_key' in exported_keys
        assert 'verify_key' in exported_keys
        assert 'public_key' in exported_keys
        
        # Import keys
        imported_km = SporeKeyManager.import_keys("test_agent", exported_keys)
        
        # Verify imported keys match original
        original_public_keys = original_km.get_public_keys()
        imported_public_keys = imported_km.get_public_keys()
        
        assert original_public_keys == imported_public_keys
        
        # Test encryption/decryption works with imported keys
        knowledge = {"test": "import_export"}
        
        # Encrypt with original, decrypt with imported
        encrypted_data, nonce, signature = original_km.encrypt_and_sign(
            knowledge, imported_public_keys['public_key']
        )
        
        decrypted = imported_km.decrypt_and_verify(
            encrypted_data, nonce, signature,
            original_public_keys['public_key'],
            original_public_keys['verify_key']
        )
        
        assert decrypted == knowledge


class TestSecureSporeFactory:
    """Test secure spore factory functionality."""
    
    def test_factory_initialization(self):
        """Test factory initialization with key manager."""
        km = SporeKeyManager("test_agent")
        factory = SecureSporeFactory(km)
        
        assert factory.key_manager == km
    
    def test_secure_spore_creation_targeted(self):
        """Test creating secure spores for specific agents."""
        sender_km = SporeKeyManager("sender")
        recipient_km = SporeKeyManager("recipient")
        factory = SecureSporeFactory(sender_km)
        
        knowledge = {"message": "targeted spore"}
        recipient_keys = recipient_km.get_public_keys()
        
        secure_spore = factory.create_secure_spore(
            to_agent="recipient",
            knowledge=knowledge,
            spore_type=SporeType.REQUEST,
            priority=8,
            expires_in_seconds=300,
            recipient_public_keys=recipient_keys
        )
        
        assert secure_spore.from_agent == "sender"
        assert secure_spore.to_agent == "recipient"
        assert secure_spore.spore_type == SporeType.REQUEST
        assert secure_spore.priority == 8
        assert secure_spore.expires_at is not None
        assert len(secure_spore.encrypted_knowledge) > 0
        assert len(secure_spore.knowledge_signature) > 0
        assert len(secure_spore.nonce) > 0
    
    def test_secure_spore_creation_broadcast(self):
        """Test creating secure spores for broadcast."""
        km = SporeKeyManager("broadcaster")
        factory = SecureSporeFactory(km)
        
        knowledge = {"announcement": "system maintenance"}
        
        secure_spore = factory.create_secure_spore(
            to_agent=None,
            knowledge=knowledge,
            spore_type=SporeType.BROADCAST,
            priority=10
        )
        
        assert secure_spore.from_agent == "broadcaster"
        assert secure_spore.to_agent is None
        assert secure_spore.spore_type == SporeType.BROADCAST
        assert secure_spore.priority == 10
        assert secure_spore.expires_at is None
    
    def test_factory_missing_recipient_keys_error(self):
        """Test that missing recipient keys raise appropriate error."""
        km = SporeKeyManager("sender")
        factory = SecureSporeFactory(km)
        
        with pytest.raises(ValueError, match="Recipient public keys required"):
            factory.create_secure_spore(
                to_agent="recipient",
                knowledge={"test": "data"}
            )
    
    def test_factory_invalid_recipient_keys_error(self):
        """Test that invalid recipient keys raise appropriate error."""
        km = SporeKeyManager("sender")
        factory = SecureSporeFactory(km)
        
        # Invalid keys (missing public_key)
        invalid_keys = {"verify_key": b"test"}
        
        with pytest.raises(ValueError, match="No public key found for agent"):
            factory.create_secure_spore(
                to_agent="recipient",
                knowledge={"test": "data"},
                recipient_public_keys=invalid_keys
            )


class TestSecureSporePerformance:
    """Test performance characteristics of secure spore operations."""
    
    def test_encryption_performance(self):
        """Test encryption performance for various message sizes."""
        km = SporeKeyManager("test_agent")
        recipient_keys = SporeKeyManager("recipient").get_public_keys()
        
        # Test different message sizes
        sizes = [100, 1000, 10000, 100000]  # bytes
        
        for size in sizes:
            knowledge = {"data": "x" * size}
            
            start_time = time.time()
            encrypted_data, nonce, signature = km.encrypt_and_sign(
                knowledge, recipient_keys['public_key']
            )
            end_time = time.time()
            
            encryption_time = (end_time - start_time) * 1000  # ms
            
            # Encryption should be fast (< 100ms for reasonable sizes)
            if size <= 10000:
                assert encryption_time < 100, f"Encryption too slow for {size} bytes: {encryption_time}ms"
            
            assert len(encrypted_data) > 0
            assert len(nonce) == 24
            assert len(signature) == 64
    
    def test_serialization_performance(self):
        """Test serialization performance for various spore sizes."""
        import random
        
        # Create spore with varying encrypted data sizes
        for size in [1000, 10000, 100000]:
            spore = SecureSpore(
                id=f"perf-test-{size}",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="recipient",
                created_at=datetime.now(),
                encrypted_knowledge=bytes(random.getrandbits(8) for _ in range(size)),
                knowledge_signature=b"signature" * 8,  # 64 bytes
                sender_public_key=b"public_key" * 4,   # 32 bytes
                nonce=b"nonce" * 6                     # 24 bytes
            )
            
            # Test serialization speed
            start_time = time.time()
            serialized = spore.to_bytes()
            serialize_time = (time.time() - start_time) * 1000
            
            # Test deserialization speed
            start_time = time.time()
            deserialized = SecureSpore.from_bytes(serialized)
            deserialize_time = (time.time() - start_time) * 1000
            
            # Serialization should be fast (< 50ms for reasonable sizes)
            if size <= 10000:
                assert serialize_time < 50, f"Serialization too slow for {size} bytes: {serialize_time}ms"
                assert deserialize_time < 50, f"Deserialization too slow for {size} bytes: {deserialize_time}ms"
            
            assert deserialized.encrypted_knowledge == spore.encrypted_knowledge
    
    def test_memory_usage(self):
        """Test memory usage of secure spore operations."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        
        # Measure memory before
        initial_objects = len(gc.get_objects())
        
        # Create and process many spores
        km = SporeKeyManager("memory_test")
        recipient_keys = SporeKeyManager("recipient").get_public_keys()
        factory = SecureSporeFactory(km)
        
        spores = []
        for i in range(100):
            knowledge = {"iteration": i, "data": "x" * 1000}
            spore = factory.create_secure_spore(
                to_agent="recipient",
                knowledge=knowledge,
                recipient_public_keys=recipient_keys
            )
            spores.append(spore)
        
        # Clear references and force garbage collection
        del spores
        gc.collect()
        
        # Measure memory after
        final_objects = len(gc.get_objects())
        
        # Memory usage shouldn't grow excessively
        object_growth = final_objects - initial_objects
        assert object_growth < 1000, f"Excessive memory usage: {object_growth} new objects"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])