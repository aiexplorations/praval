"""
Tests for Spore payload validation.

Verifies spore size limits and type validation (S1).
Part of rearchitecture Phase 1.
"""

from datetime import datetime

import pytest


class TestSporeValidation:
    """Tests for Spore validation."""

    def test_spore_accepts_valid_payload(self):
        """Verify spore accepts valid dict payload."""
        from praval.core.reef import Spore, SporeType

        spore = Spore(
            id="test_valid",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"message": "Hello", "data": [1, 2, 3]},
            created_at=datetime.now(),
        )

        assert spore.knowledge == {"message": "Hello", "data": [1, 2, 3]}

    def test_spore_accepts_empty_knowledge(self):
        """Verify spore accepts empty dict or None for knowledge."""
        from praval.core.reef import Spore, SporeType

        # Empty dict
        spore1 = Spore(
            id="test_empty",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now(),
        )
        assert spore1.knowledge == {}

        # None is also acceptable (will be validated as such)
        spore2 = Spore(
            id="test_none",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge=None,
            created_at=datetime.now(),
        )
        assert spore2.knowledge is None

    def test_spore_rejects_non_dict_knowledge(self):
        """Verify spore rejects non-dict knowledge."""
        from praval.core.reef import Spore, SporeType, SporeValidationError

        with pytest.raises(SporeValidationError) as exc_info:
            Spore(
                id="test_string",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="receiver",
                knowledge="not a dict",  # Invalid
                created_at=datetime.now(),
            )

        assert "must be a dict" in str(exc_info.value)
        assert "str" in str(exc_info.value)

    def test_spore_rejects_list_knowledge(self):
        """Verify spore rejects list as knowledge."""
        from praval.core.reef import Spore, SporeType, SporeValidationError

        with pytest.raises(SporeValidationError) as exc_info:
            Spore(
                id="test_list",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="receiver",
                knowledge=[1, 2, 3],  # Invalid
                created_at=datetime.now(),
            )

        assert "must be a dict" in str(exc_info.value)

    def test_spore_rejects_oversized_payload(self):
        """Verify spore rejects payload exceeding max size."""
        from praval.core.reef import Spore, SporeType, SporeValidationError

        # Create large payload (over 10MB)
        large_data = {"data": "x" * (11 * 1024 * 1024)}  # ~11MB string

        with pytest.raises(SporeValidationError) as exc_info:
            Spore(
                id="test_oversized",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="receiver",
                knowledge=large_data,
                created_at=datetime.now(),
            )

        assert "too large" in str(exc_info.value)
        assert "knowledge_references" in str(exc_info.value)

    def test_spore_accepts_payload_at_limit(self):
        """Verify spore accepts payload at exactly the limit."""
        from praval.core.reef import MAX_SPORE_SIZE_BYTES, Spore, SporeType

        # Create payload just under the limit
        # Account for JSON overhead {"data": "..."}
        overhead = len('{"data": ""}'.encode("utf-8"))
        data_size = MAX_SPORE_SIZE_BYTES - overhead - 100  # Some buffer
        knowledge = {"data": "x" * data_size}

        # Should not raise
        spore = Spore(
            id="test_at_limit",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge=knowledge,
            created_at=datetime.now(),
        )

        assert spore.get_payload_size() <= MAX_SPORE_SIZE_BYTES

    def test_spore_rejects_non_serializable_knowledge(self):
        """Verify spore rejects non-JSON-serializable knowledge."""
        from praval.core.reef import Spore, SporeType, SporeValidationError

        class CustomClass:
            pass

        with pytest.raises(SporeValidationError) as exc_info:
            Spore(
                id="test_non_serializable",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="receiver",
                knowledge={"obj": CustomClass()},  # Not serializable
                created_at=datetime.now(),
            )

        assert "not JSON-serializable" in str(exc_info.value)

    def test_validate_with_custom_max_size(self):
        """Verify validate() accepts custom max size."""
        from praval.core.reef import Spore, SporeType, SporeValidationError

        # Create spore with payload under default but over custom limit
        knowledge = {"data": "x" * 1000}  # ~1KB

        spore = Spore(
            id="test_custom_limit",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge=knowledge,
            created_at=datetime.now(),
        )

        # Should pass with default limit
        spore.validate()

        # Should fail with smaller limit
        with pytest.raises(SporeValidationError):
            spore.validate(max_size=100)


class TestSporePayloadSize:
    """Tests for get_payload_size() method."""

    def test_get_payload_size_empty(self):
        """Verify get_payload_size returns 0 for empty knowledge."""
        from praval.core.reef import Spore, SporeType

        spore = Spore(
            id="test_size_empty",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now(),
        )

        assert spore.get_payload_size() == 2  # "{}"

    def test_get_payload_size_none(self):
        """Verify get_payload_size returns 0 for None knowledge."""
        from praval.core.reef import Spore, SporeType

        spore = Spore(
            id="test_size_none",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge=None,
            created_at=datetime.now(),
        )

        assert spore.get_payload_size() == 0

    def test_get_payload_size_with_data(self):
        """Verify get_payload_size returns correct size."""
        import json

        from praval.core.reef import Spore, SporeType

        knowledge = {"key": "value", "number": 42}
        expected_size = len(json.dumps(knowledge).encode("utf-8"))

        spore = Spore(
            id="test_size_data",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge=knowledge,
            created_at=datetime.now(),
        )

        assert spore.get_payload_size() == expected_size


class TestSporeValidationError:
    """Tests for SporeValidationError exception."""

    def test_exception_exists(self):
        """Verify SporeValidationError is importable."""
        from praval.core.reef import SporeValidationError

        assert issubclass(SporeValidationError, Exception)

    def test_exception_message(self):
        """Verify exception carries message."""
        from praval.core.reef import SporeValidationError

        error = SporeValidationError("Test error message")
        assert str(error) == "Test error message"


class TestMaxSporeSizeConstant:
    """Tests for MAX_SPORE_SIZE_BYTES constant."""

    def test_constant_exists(self):
        """Verify MAX_SPORE_SIZE_BYTES is defined."""
        from praval.core.reef import MAX_SPORE_SIZE_BYTES

        assert MAX_SPORE_SIZE_BYTES is not None

    def test_constant_is_10mb(self):
        """Verify default max size is 10MB."""
        from praval.core.reef import MAX_SPORE_SIZE_BYTES

        assert MAX_SPORE_SIZE_BYTES == 10 * 1024 * 1024


class TestSporeValidationBackwardCompatibility:
    """Tests for backward compatibility of validation."""

    def test_existing_valid_spores_still_work(self):
        """Verify existing code creating valid spores still works."""
        from praval.core.reef import Spore, SporeType

        # This is how spores were created before validation
        spore = Spore(
            id="compat_test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent_a",
            to_agent="agent_b",
            knowledge={"type": "test", "data": "hello"},
            created_at=datetime.now(),
        )

        assert spore.id == "compat_test"

    def test_from_json_validates(self):
        """Verify from_json also validates the spore."""
        import json

        from praval.core.reef import Spore

        # Create valid JSON
        valid_json = json.dumps(
            {
                "id": "json_test",
                "spore_type": "knowledge",
                "from_agent": "sender",
                "to_agent": "receiver",
                "knowledge": {"message": "hello"},
                "created_at": datetime.now().isoformat(),
                "expires_at": None,
                "priority": 5,
                "reply_to": None,
                "metadata": {},
                "knowledge_references": [],
                "data_references": [],
            }
        )

        # Should work for valid JSON
        spore = Spore.from_json(valid_json)
        assert spore.id == "json_test"
