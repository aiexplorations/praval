"""Streaming events example.

Requires provider credentials unless you adapt it to a local provider.
"""

import os

from praval import Agent


def main() -> None:
    if os.getenv("PRAVAL_RUN_LIVE_EXAMPLES") != "1":
        print("SKIP: Set PRAVAL_RUN_LIVE_EXAMPLES=1 for live streaming.")
        return
    agent = Agent("assistant", provider="openai", model="gpt-5.4-mini")

    for event in agent.stream(
        "Write one sentence about streaming.",
        stream_options={"include_usage": True},
    ):
        if event.type == "delta":
            print(event.delta, end="")
        elif event.type == "usage" and event.usage:
            print(f"\nusage={event.usage.total_tokens}")
        elif event.type == "final":
            print("\ncomplete")


if __name__ == "__main__":
    main()
