"""Certify GPT-6 Luna parameters, endpoint selection and dependent tool rounds."""

from live_provider_matrix import certify_tool_rounds
from support import live_entrypoint, require_environment, write_json_artifact


def main() -> None:
    """Run bounded two-tool checks with the caller's OpenAI credential."""
    require_environment("OPENAI_API_KEY")
    evidence = {}
    for name, endpoint, reasoning in (
        ("automatic", None, None),
        ("automatic_low", None, "low"),
        ("responses", "responses", None),
        ("responses_low", "responses", "low"),
        ("chat_none", "chat.completions", "none"),
    ):
        evidence[name] = certify_tool_rounds(
            "openai",
            model="gpt-6-luna",
            endpoint=endpoint,
            reasoning=reasoning,
            max_output_tokens=4096,
        )
        assert evidence[name]["resolved_endpoint"] == (endpoint or "responses")
    write_json_artifact("live-openai-gpt6.json", evidence)
    print("CERTIFIED: GPT-6 Luna dependent tools, reasoning and usage")


if __name__ == "__main__":
    live_entrypoint(main)
