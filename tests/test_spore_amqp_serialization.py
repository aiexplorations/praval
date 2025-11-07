"""
Unit tests for Spore AMQP serialization (native wire format).

Tests the to_amqp_message() and from_amqp_message() methods that make
Spore the native AMQP message format, eliminating intermediate conversions.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from praval.core.reef import Spore, SporeType


class TestSporeToAmqpMessage:
    """Tests for Spore.to_amqp_message() conversion."""

    def test_to_amqp_basic_knowledge_spore(self):
        """Test basic conversion of knowledge spore to AMQP message."""
        spore = Spore(
            id="test-id-123",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"data": "test_value", "count": 42},
            created_at=datetime(2025, 11, 7, 12, 0, 0),
            priority=7
        )

        amqp_msg = spore.to_amqp_message()

        # Verify basic properties
        assert amqp_msg.message_id == "test-id-123"
        assert amqp_msg.priority == 7
        assert amqp_msg.content_type == "application/json"
        assert amqp_msg.delivery_mode.name == "PERSISTENT"

    def test_to_amqp_headers_preserved(self):
        """Test that all spore metadata is preserved in AMQP headers."""
        spore = Spore(
            id="spore-xyz",
            spore_type=SporeType.REQUEST,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"request": "data"},
            created_at=datetime(2025, 11, 7, 12, 30, 0),
            priority=9,
            reply_to="original-request-id"
        )

        amqp_msg = spore.to_amqp_message()
        headers = amqp_msg.headers

        # Verify all metadata in headers
        assert headers['spore_id'] == "spore-xyz"
        assert headers['spore_type'] == "request"
        assert headers['from_agent'] == "sender"
        assert headers['to_agent'] == "receiver"
        assert headers['priority'] == "9"
        assert headers['reply_to'] == "original-request-id"
        assert headers['version'] == "1.0"

    def test_to_amqp_knowledge_in_body(self):
        """Test that knowledge is properly serialized in message body."""
        knowledge_dict = {"key1": "value1", "nested": {"key2": "value2"}}
        spore = Spore(
            id="test-id",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge=knowledge_dict,
            created_at=datetime.now()
        )

        amqp_msg = spore.to_amqp_message()

        # Body should be JSON-encoded knowledge
        body_dict = json.loads(amqp_msg.body.decode('utf-8'))
        assert body_dict == knowledge_dict

    def test_to_amqp_broadcast_spore(self):
        """Test broadcast spore (to_agent = None)."""
        spore = Spore(
            id="broadcast-123",
            spore_type=SporeType.BROADCAST,
            from_agent="broadcaster",
            to_agent=None,  # Broadcast
            knowledge={"message": "to all"},
            created_at=datetime.now()
        )

        amqp_msg = spore.to_amqp_message()
        headers = amqp_msg.headers

        assert headers['spore_type'] == "broadcast"
        assert headers['to_agent'] == ""  # None serialized as empty string

    def test_to_amqp_with_expiration(self):
        """Test TTL conversion from expires_at to AMQP expiration."""
        now = datetime.now()
        expires_at = now + timedelta(seconds=300)  # 5 minutes from now

        spore = Spore(
            id="expiring-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"data": "value"},
            created_at=now,
            expires_at=expires_at
        )

        amqp_msg = spore.to_amqp_message()

        # Expiration should be in milliseconds
        assert amqp_msg.expiration is not None
        assert 290000 <= amqp_msg.expiration <= 310000  # ~300 seconds in ms

    def test_to_amqp_expired_spore(self):
        """Test that expired spore still converts but with past expiration."""
        now = datetime.now()
        expires_at = now - timedelta(seconds=10)  # Already expired

        spore = Spore(
            id="expired-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"data": "value"},
            created_at=now - timedelta(seconds=20),
            expires_at=expires_at
        )

        amqp_msg = spore.to_amqp_message()

        # Should have no expiration (negative TTL)
        assert amqp_msg.expiration is None

    def test_to_amqp_priority_clamping(self):
        """Test that priority is clamped to AMQP range (0-255)."""
        # Test high priority (1-10 scale -> AMQP 0-255)
        spore = Spore(
            id="high-priority",
            spore_type=SporeType.REQUEST,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={},
            created_at=datetime.now(),
            priority=10
        )

        amqp_msg = spore.to_amqp_message()
        assert amqp_msg.priority == 10  # Should be clamped to 255 range

    def test_to_amqp_response_spore(self):
        """Test response spore with reply_to metadata."""
        spore = Spore(
            id="response-spore-456",
            spore_type=SporeType.RESPONSE,
            from_agent="responder",
            to_agent="requester",
            knowledge={"answer": "42"},
            created_at=datetime.now(),
            reply_to="original-request-789"
        )

        amqp_msg = spore.to_amqp_message()
        headers = amqp_msg.headers

        assert headers['spore_type'] == "response"
        assert headers['reply_to'] == "original-request-789"

    def test_to_amqp_notification_spore(self):
        """Test notification spore type."""
        spore = Spore(
            id="notification-123",
            spore_type=SporeType.NOTIFICATION,
            from_agent="system",
            to_agent="agent1",
            knowledge={"event": "system_updated"},
            created_at=datetime.now()
        )

        amqp_msg = spore.to_amqp_message()

        assert amqp_msg.headers['spore_type'] == "notification"

    def test_to_amqp_empty_knowledge(self):
        """Test spore with empty knowledge dict."""
        spore = Spore(
            id="empty-spore",
            spore_type=SporeType.BROADCAST,
            from_agent="agent1",
            to_agent=None,
            knowledge={},
            created_at=datetime.now()
        )

        amqp_msg = spore.to_amqp_message()

        # Should still serialize correctly
        body_dict = json.loads(amqp_msg.body.decode('utf-8'))
        assert body_dict == {}

    def test_to_amqp_complex_knowledge(self):
        """Test spore with nested complex knowledge structure."""
        complex_knowledge = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ],
            "metadata": {
                "version": "1.0",
                "timestamp": "2025-11-07T12:00:00",
                "nested": {
                    "deep": {
                        "value": "found"
                    }
                }
            }
        }

        spore = Spore(
            id="complex-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="system",
            to_agent="analyzer",
            knowledge=complex_knowledge,
            created_at=datetime.now()
        )

        amqp_msg = spore.to_amqp_message()
        body_dict = json.loads(amqp_msg.body.decode('utf-8'))

        assert body_dict == complex_knowledge


class TestSporeFromAmqpMessage:
    """Tests for Spore.from_amqp_message() conversion."""

    def test_from_amqp_basic_conversion(self):
        """Test basic conversion from AMQP message to Spore."""
        # Create a test spore, convert to AMQP, then back
        original = Spore(
            id="roundtrip-id",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"key": "value"},
            created_at=datetime(2025, 11, 7, 12, 0, 0),
            priority=5
        )

        amqp_msg = original.to_amqp_message()
        restored = Spore.from_amqp_message(amqp_msg)

        assert restored.id == original.id
        assert restored.spore_type == original.spore_type
        assert restored.from_agent == original.from_agent
        assert restored.to_agent == original.to_agent
        assert restored.knowledge == original.knowledge
        assert restored.priority == original.priority

    def test_from_amqp_all_fields_preserved(self):
        """Test that all spore fields survive roundtrip conversion."""
        now = datetime(2025, 11, 7, 12, 30, 45)
        expires_at = now + timedelta(hours=1)

        original = Spore(
            id="full-spore",
            spore_type=SporeType.REQUEST,
            from_agent="requester",
            to_agent="responder",
            knowledge={"request": "data"},
            created_at=now,
            expires_at=expires_at,
            priority=8,
            reply_to="some-id"
        )

        amqp_msg = original.to_amqp_message()
        restored = Spore.from_amqp_message(amqp_msg)

        # Check all fields
        assert restored.id == original.id
        assert restored.spore_type == original.spore_type
        assert restored.from_agent == original.from_agent
        assert restored.to_agent == original.to_agent
        assert restored.knowledge == original.knowledge
        assert restored.priority == original.priority
        assert restored.reply_to == original.reply_to
        # Timestamps should be close (within microseconds)
        assert abs((restored.created_at - original.created_at).total_seconds()) < 0.001

    def test_from_amqp_broadcast_spore(self):
        """Test conversion of broadcast spore (to_agent = None)."""
        original = Spore(
            id="broadcast-restore",
            spore_type=SporeType.BROADCAST,
            from_agent="broadcaster",
            to_agent=None,
            knowledge={"message": "broadcast"},
            created_at=datetime.now()
        )

        amqp_msg = original.to_amqp_message()
        restored = Spore.from_amqp_message(amqp_msg)

        assert restored.spore_type == SporeType.BROADCAST
        assert restored.to_agent is None

    def test_from_amqp_missing_headers(self):
        """Test deserialization when some headers are missing."""
        # Mock AMQP message with minimal headers
        mock_msg = Mock()
        mock_msg.headers = {
            'spore_id': 'minimal-id',
            'from_agent': 'minimal-sender'
        }
        mock_msg.body = json.dumps({"data": "value"}).encode('utf-8')
        mock_msg.message_id = 'minimal-id'
        mock_msg.timestamp = datetime.now()

        restored = Spore.from_amqp_message(mock_msg)

        # Should use defaults for missing headers
        assert restored.id == 'minimal-id'
        assert restored.from_agent == 'minimal-sender'
        assert restored.spore_type == SporeType.KNOWLEDGE  # Default
        assert restored.to_agent is None  # Default (empty string -> None)
        assert restored.priority == 5  # Default

    def test_from_amqp_invalid_json_body(self):
        """Test deserialization when body is not valid JSON."""
        mock_msg = Mock()
        mock_msg.headers = {
            'spore_id': 'invalid-json-id',
            'from_agent': 'sender'
        }
        mock_msg.body = b"Not valid JSON"
        mock_msg.message_id = 'invalid-json-id'
        mock_msg.timestamp = datetime.now()

        restored = Spore.from_amqp_message(mock_msg)

        # Should fallback to raw_content
        assert 'raw_content' in restored.knowledge
        assert restored.knowledge['raw_content'] == "Not valid JSON"

    def test_from_amqp_invalid_timestamp(self):
        """Test deserialization with invalid timestamp in headers."""
        mock_msg = Mock()
        mock_msg.headers = {
            'spore_id': 'invalid-ts-id',
            'from_agent': 'sender',
            'created_at': 'not-a-valid-datetime'
        }
        mock_msg.body = json.dumps({}).encode('utf-8')
        mock_msg.message_id = 'invalid-ts-id'
        mock_msg.timestamp = None

        restored = Spore.from_amqp_message(mock_msg)

        # Should use current time as fallback
        assert restored.created_at is not None

    def test_from_amqp_with_expiration(self):
        """Test that expiration timestamp is restored correctly."""
        now = datetime(2025, 11, 7, 15, 0, 0)
        expires_at = now + timedelta(days=1)

        original = Spore(
            id="expire-test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"data": "value"},
            created_at=now,
            expires_at=expires_at
        )

        amqp_msg = original.to_amqp_message()
        restored = Spore.from_amqp_message(amqp_msg)

        assert restored.expires_at is not None
        # Should be close to original (may lose milliseconds)
        assert abs((restored.expires_at - original.expires_at).total_seconds()) < 1

    def test_from_amqp_response_spore(self):
        """Test conversion of response spore."""
        original = Spore(
            id="response-id",
            spore_type=SporeType.RESPONSE,
            from_agent="responder",
            to_agent="requester",
            knowledge={"answer": 42},
            created_at=datetime.now(),
            reply_to="original-request-id"
        )

        amqp_msg = original.to_amqp_message()
        restored = Spore.from_amqp_message(amqp_msg)

        assert restored.spore_type == SporeType.RESPONSE
        assert restored.reply_to == "original-request-id"

    def test_from_amqp_all_spore_types(self):
        """Test conversion works for all SporeType values."""
        for spore_type in SporeType:
            original = Spore(
                id=f"{spore_type.value}-id",
                spore_type=spore_type,
                from_agent="sender",
                to_agent="receiver" if spore_type != SporeType.BROADCAST else None,
                knowledge={"type": spore_type.value},
                created_at=datetime.now()
            )

            amqp_msg = original.to_amqp_message()
            restored = Spore.from_amqp_message(amqp_msg)

            assert restored.spore_type == spore_type

    def test_from_amqp_complex_knowledge_restored(self):
        """Test that complex nested knowledge is fully preserved."""
        complex_knowledge = {
            "level1": {
                "level2": {
                    "level3": [1, 2, 3],
                    "mixed": {"a": 1, "b": [4, 5, 6]}
                }
            },
            "array": [{"id": 1}, {"id": 2}]
        }

        original = Spore(
            id="complex-id",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="system",
            to_agent="processor",
            knowledge=complex_knowledge,
            created_at=datetime.now()
        )

        amqp_msg = original.to_amqp_message()
        restored = Spore.from_amqp_message(amqp_msg)

        assert restored.knowledge == complex_knowledge


class TestSporeAmqpRoundtrip:
    """Integration tests for Spore <-> AMQP roundtrip conversions."""

    def test_roundtrip_preserves_all_data(self):
        """Test that data is fully preserved in a roundtrip conversion."""
        test_cases = [
            {
                "name": "basic_knowledge",
                "spore": Spore(
                    id="id1",
                    spore_type=SporeType.KNOWLEDGE,
                    from_agent="a1",
                    to_agent="a2",
                    knowledge={"x": 1},
                    created_at=datetime(2025, 11, 7, 10, 0, 0)
                )
            },
            {
                "name": "broadcast",
                "spore": Spore(
                    id="id2",
                    spore_type=SporeType.BROADCAST,
                    from_agent="broadcaster",
                    to_agent=None,
                    knowledge={"msg": "all"},
                    created_at=datetime(2025, 11, 7, 10, 0, 0)
                )
            },
            {
                "name": "request_response",
                "spore": Spore(
                    id="id3",
                    spore_type=SporeType.REQUEST,
                    from_agent="requester",
                    to_agent="responder",
                    knowledge={"q": "answer?"},
                    created_at=datetime(2025, 11, 7, 10, 0, 0),
                    reply_to="original-123"
                )
            }
        ]

        for test_case in test_cases:
            original = test_case["spore"]
            amqp_msg = original.to_amqp_message()
            restored = Spore.from_amqp_message(amqp_msg)

            # Check all fields match
            assert restored.id == original.id, f"ID mismatch in {test_case['name']}"
            assert restored.spore_type == original.spore_type, f"Type mismatch in {test_case['name']}"
            assert restored.from_agent == original.from_agent, f"From agent mismatch in {test_case['name']}"
            assert restored.to_agent == original.to_agent, f"To agent mismatch in {test_case['name']}"
            assert restored.knowledge == original.knowledge, f"Knowledge mismatch in {test_case['name']}"
            assert restored.priority == original.priority, f"Priority mismatch in {test_case['name']}"

    def test_multiple_roundtrips_stable(self):
        """Test that spore remains stable across multiple roundtrip conversions."""
        original = Spore(
            id="stable-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"data": "value"},
            created_at=datetime(2025, 11, 7, 12, 0, 0)
        )

        # Do multiple roundtrips
        current = original
        for i in range(3):
            amqp_msg = current.to_amqp_message()
            current = Spore.from_amqp_message(amqp_msg)

        # Should still match original
        assert current.id == original.id
        assert current.knowledge == original.knowledge
        assert current.spore_type == original.spore_type

    def test_roundtrip_with_various_priorities(self):
        """Test roundtrip with different priority values."""
        for priority in [1, 5, 10]:
            original = Spore(
                id=f"priority-{priority}",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="receiver",
                knowledge={"priority": priority},
                created_at=datetime.now(),
                priority=priority
            )

            amqp_msg = original.to_amqp_message()
            restored = Spore.from_amqp_message(amqp_msg)

            assert restored.priority == priority, f"Priority {priority} not preserved"
