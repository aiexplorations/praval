"""Structured output example.

Requires provider credentials.
"""

import os

from praval import Agent


def main() -> None:
    if os.getenv("PRAVAL_RUN_LIVE_EXAMPLES") != "1":
        print(
            "SKIP: Set PRAVAL_RUN_LIVE_EXAMPLES=1 for live structured-output "
            "example."
        )
        return
    agent = Agent("extractor", provider="openai", model="gpt-5.4-mini")
    response = agent.generate(
        "Extract the city and temperature from: Pune is 29 degrees.",
        response_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "temperature_c": {"type": "number"},
            },
            "required": ["city", "temperature_c"],
        },
    )
    print(response.content)


if __name__ == "__main__":
    main()
