"""Metadata-first telemetry sanitization contracts."""

from praval.observability.privacy import TelemetrySanitizer


def test_default_policy_drops_content_and_redacts_credentials() -> None:
    sanitizer = TelemetrySanitizer(max_attribute_bytes=16, max_collection_items=2)

    attributes = sanitizer.sanitize_attributes(
        {
            "gen_ai.prompt": "private prompt",
            "tool.arguments": {"query": "private"},
            "authorization": "Bearer private-token",
            "safe.value": "api_key=private",
            "third.value": "not retained because the collection is bounded",
        }
    )

    assert "gen_ai.prompt" not in attributes
    assert "tool.arguments" not in attributes
    assert attributes == {}

    credentials = sanitizer.sanitize_attributes(
        {
            "authorization": "Bearer private-token",
            "safe.value": "api_key=private",
        }
    )
    assert credentials == {
        "authorization": "[REDACTED]",
        "safe.value": "[REDACTED]",
    }


def test_content_requires_both_opt_in_and_exact_allowlist() -> None:
    empty_allowlist = TelemetrySanitizer(capture_content=True)
    explicit = TelemetrySanitizer(
        capture_content=True,
        content_allowlist=("gen_ai.prompt",),
    )

    supplied = {
        "gen_ai.prompt": "allowed prompt",
        "gen_ai.response": "not allowed response",
    }
    assert empty_allowlist.sanitize_attributes(supplied) == {}
    assert explicit.sanitize_attributes(supplied) == {"gen_ai.prompt": "allowed prompt"}


def test_values_are_utf8_collection_and_type_bounded() -> None:
    sanitizer = TelemetrySanitizer(max_attribute_bytes=5, max_collection_items=2)

    attributes = sanitizer.sanitize_attributes(
        {
            "safe.text": "éééé",
            "safe.list": [1, 2, 3],
        }
    )

    assert len(attributes["safe.text"].encode("utf-8")) <= 5
    assert attributes["safe.list"] == [1, 2]
    assert sanitizer.sanitize_value(b"private bytes") == {
        "type": "bytes",
        "size_bytes": 13,
    }
    assert sanitizer.sanitize_value(object()) == "objec"
