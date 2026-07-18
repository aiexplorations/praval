"""Multimodal input example.

Requires a provider and model profile with image input support.
"""

import os

from praval import Agent, ContentPart


def main() -> None:
    if os.getenv("PRAVAL_RUN_LIVE_EXAMPLES") != "1":
        print("SKIP: Set PRAVAL_RUN_LIVE_EXAMPLES=1 for live multimodal input.")
        return
    agent = Agent("vision", provider="openai", model="gpt-5.4-mini")
    response = agent.generate(
        [
            ContentPart.text_part("Describe this image in one sentence."),
            ContentPart.image_url("https://example.com/image.png"),
        ]
    )
    print(response.content)


if __name__ == "__main__":
    main()
