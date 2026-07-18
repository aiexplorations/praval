"""Request-based voice agent example for Praval 0.8.

This example transcribes a local audio file, sends the text through an agent,
and writes the synthesized reply to disk. It intentionally does not implement
realtime audio streaming.
"""

import argparse
import os
from pathlib import Path
from typing import Optional, Sequence

from praval import Agent


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", nargs="?", type=Path, help="Input audio file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reply.mp3"),
        help="Path for synthesized speech",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the request-based voice flow."""
    args = build_parser().parse_args(argv)
    if args.audio is None:
        print("Pass an audio file to run the voice example.")
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run the voice example.")
        return 0
    if not args.audio.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {args.audio}")

    with Agent(
        "voice-assistant",
        provider="openai",
        model="gpt-5.4-mini",
    ) as agent:
        transcript = agent.transcribe(
            args.audio,
            model="gpt-4o-transcribe",
        )
        reply = agent.chat(transcript)
        speech = agent.speak(
            reply,
            model="tts-1",
            voice="alloy",
            response_format="mp3",
        )

    args.output.write_bytes(speech)
    print(f"Transcript: {transcript}")
    print(f"Reply written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
