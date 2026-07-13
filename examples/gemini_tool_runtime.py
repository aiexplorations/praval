"""Gemini client-tool round trip through ModelRuntime.

Set GEMINI_API_KEY or GOOGLE_API_KEY before running this example.
"""

import os

from praval import Agent


def main() -> int:
    """Run a Gemini function-call round trip."""
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY to run this example.")
        return 0

    with Agent("gemini-tools", provider="gemini", model="gemini-3.5-flash") as agent:

        @agent.tool
        def weather(city: str) -> str:
            """Return illustrative weather data for a city."""
            return f"The illustrative forecast for {city} is sunny."

        response = agent.generate("Use the weather tool for Bengaluru.")

    print(response.content)
    print([call.name for call in response.tool_calls])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
