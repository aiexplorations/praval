"""Tests for Spore V2 compatibility fields."""

from datetime import datetime

import pytest

from praval.core.reef import Spore, SporeType, SporeValidationError
from praval.models import ContentPart


def test_spore_payload_mirrors_knowledge_for_compatibility():
    spore = Spore(
        id="spore-1",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="a",
        to_agent=None,
        knowledge={"type": "note"},
        created_at=datetime.now(),
        correlation_id="corr-1",
        trace_id="trace-1",
    )

    assert spore.payload == {"type": "note"}
    restored = Spore.from_json(spore.to_json())
    assert restored.knowledge == {"type": "note"}
    assert restored.payload == {"type": "note"}
    assert restored.correlation_id == "corr-1"
    assert restored.trace_id == "trace-1"


def test_spore_payload_populates_knowledge_when_knowledge_missing():
    spore = Spore(
        id="spore-2",
        spore_type=SporeType.REQUEST,
        from_agent="a",
        to_agent="b",
        knowledge=None,
        payload={"query": "hello"},
        created_at=datetime.now(),
    )

    assert spore.knowledge == {"query": "hello"}


def test_spore_normalizes_and_round_trips_multimodal_content_and_references():
    spore = Spore(
        id="spore-multimodal",
        spore_type=SporeType.REQUEST,
        from_agent="vision-agent",
        to_agent="reviewer",
        knowledge=None,
        created_at=datetime.now(),
        content_parts=[
            ContentPart.text_part("Review the recording"),
            ContentPart.audio_url("s3://bucket/recording.mp3", "audio/mpeg"),
        ],
        data_references=["s3://bucket/recording.mp3"],
    )

    assert spore.content_parts == [
        {"type": "text", "text": "Review the recording", "metadata": {}},
        {
            "type": "audio_url",
            "url": "s3://bucket/recording.mp3",
            "mime_type": "audio/mpeg",
            "metadata": {},
        },
    ]
    restored = Spore.from_json(spore.to_json())
    assert restored.content_parts == spore.content_parts
    assert restored.data_references == ["s3://bucket/recording.mp3"]


def test_spore_rejects_raw_binary_content_parts():
    with pytest.raises(SporeValidationError, match="content_parts"):
        Spore(
            id="spore-binary",
            spore_type=SporeType.REQUEST,
            from_agent="voice-agent",
            to_agent="reviewer",
            knowledge=None,
            created_at=datetime.now(),
            content_parts=[{"type": "audio_base64", "data": b"raw-audio"}],
        )
