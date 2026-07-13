"""Analyze a Gemini Files API reference with Praval.

Upload the input with Gemini's Files API first, then pass the returned file URI
to this example. Praval serializes the reference as Gemini ``fileData``; it does
not upload local files in 0.8.0.
"""

import argparse
import os
from typing import Optional, Sequence

from praval import Agent, ContentPart


def build_parser() -> argparse.ArgumentParser:
    """Build the example command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "file_uri",
        nargs="?",
        help="URI returned by the Gemini Files API",
    )
    parser.add_argument(
        "--mime-type",
        default="application/pdf",
        help="Media MIME type, such as application/pdf or video/mp4",
    )
    parser.add_argument(
        "--prompt",
        default="Summarize this file and list its three most important points.",
        help="Instruction sent with the file reference",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run Gemini generation with a remote file reference."""
    args = build_parser().parse_args(argv)
    if not args.file_uri:
        print("Pass a Gemini Files API URI to run this example.")
        return 0
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY to run this example.")
        return 0

    with Agent(
        "gemini-file-analyst",
        provider="gemini",
        model="gemini-3.5-flash",
    ) as agent:
        response = agent.generate(
            [
                ContentPart.text_part(args.prompt),
                ContentPart.file_url(args.file_uri, args.mime_type),
            ]
        )

    print(response.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
