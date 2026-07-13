"""Certify request-based OpenAI STT and TTS with a real audio round trip."""

from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path

from support import (
    live_entrypoint,
    report_dir,
    require_environment,
    validate_wav,
    write_json_artifact,
)

from praval import Agent

PHRASE_PATH = Path(__file__).with_name("assets") / "voice_phrase.txt"
VOICE_FIXTURE_PATH = Path(__file__).with_name("assets") / "voice_input.wav.gz.base64"
VOICE_FIXTURE_SHA256 = (
    "041f5f356daec0d916580e31cc7913ba4837fc29a5fb3a0b2a3e8f5ac926648b"
)


def normalized_words(value: str) -> set[str]:
    """Return lowercase alphanumeric words for tolerant speech assertions."""
    cleaned = "".join(
        character.lower() if character.isalnum() else " " for character in value
    )
    return set(cleaned.split())


def require_words(value: str, required: set[str], label: str) -> None:
    """Require the semantic key words expected from speech recognition."""
    missing = required - normalized_words(value)
    assert not missing, f"{label} is missing recognized words: {sorted(missing)}"


def main() -> None:
    """Execute committed WAV -> STT -> agent -> TTS -> STT with OpenAI."""
    values = require_environment(
        "OPENAI_API_KEY",
        "PRAVAL_OPENAI_MODEL",
        "PRAVAL_OPENAI_TRANSCRIPTION_MODEL",
        "PRAVAL_OPENAI_TTS_MODEL",
        "PRAVAL_OPENAI_TTS_VOICE",
    )
    phrase = PHRASE_PATH.read_text(encoding="utf-8").strip()
    output = report_dir()
    input_path = output / "voice-input.wav"
    reply_path = output / "voice-reply.wav"
    seed_audio = gzip.decompress(
        base64.b64decode(VOICE_FIXTURE_PATH.read_text(encoding="ascii"))
    )
    assert hashlib.sha256(seed_audio).hexdigest() == VOICE_FIXTURE_SHA256
    input_metadata = validate_wav(seed_audio)
    input_path.write_bytes(seed_audio)

    with Agent(
        "live-voice-certification",
        provider="openai",
        model=values["PRAVAL_OPENAI_MODEL"],
        config={"temperature": 0, "max_output_tokens": 64, "timeout": 60},
    ) as agent:
        transcript = agent.transcribe(
            input_path,
            model=values["PRAVAL_OPENAI_TRANSCRIPTION_MODEL"],
            language="en",
            timeout=60,
        )
        require_words(
            transcript,
            {"praval", "speech", "transcription", "synthesis"},
            "transcript",
        )

        response = agent.generate(
            "The user said: "
            + transcript
            + " Reply with exactly: Praval voice round trip succeeded."
        )
        assert response.content.strip()
        require_words(response.content, {"praval", "voice", "succeeded"}, "agent reply")

        reply_audio = agent.speak(
            response.content,
            model=values["PRAVAL_OPENAI_TTS_MODEL"],
            voice=values["PRAVAL_OPENAI_TTS_VOICE"],
            response_format="wav",
            timeout=60,
        )
        reply_metadata = validate_wav(reply_audio)
        reply_path.write_bytes(reply_audio)
        roundtrip = agent.transcribe(
            reply_path,
            model=values["PRAVAL_OPENAI_TRANSCRIPTION_MODEL"],
            language="en",
            timeout=60,
        )
        require_words(roundtrip, {"praval", "voice", "succeeded"}, "round trip")

    evidence = {
        "phrase": phrase,
        "transcript": transcript,
        "agent_reply": response.content,
        "roundtrip_transcript": roundtrip,
        "models": {
            "agent": values["PRAVAL_OPENAI_MODEL"],
            "transcription": values["PRAVAL_OPENAI_TRANSCRIPTION_MODEL"],
            "tts": values["PRAVAL_OPENAI_TTS_MODEL"],
            "voice": values["PRAVAL_OPENAI_TTS_VOICE"],
        },
        "usage": response.usage.model_dump() if response.usage else None,
        "input_wav": input_metadata,
        "input_wav_sha256": VOICE_FIXTURE_SHA256,
        "reply_wav": reply_metadata,
    }
    write_json_artifact("live-voice-roundtrip.json", evidence)
    print("CERTIFIED: real STT and TTS round trip")


if __name__ == "__main__":
    live_entrypoint(main)
