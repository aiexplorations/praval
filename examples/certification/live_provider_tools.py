"""Run a dependent-tool certificate independently for one configured provider."""

import argparse

from live_provider_matrix import certify_tool_rounds
from support import live_entrypoint, require_environment, write_json_artifact


def main() -> None:
    """Require real tool execution and reconciled per-request usage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        default="all",
        choices=("all", "ollama", "gemini", "anthropic", "openrouter"),
    )
    args = parser.parse_args()
    providers = (
        ("ollama", "gemini", "anthropic", "openrouter")
        if args.provider == "all"
        else (args.provider,)
    )
    evidence = {}
    for provider in providers:
        model_env = "PRAVAL_" + provider.upper() + "_MODEL"
        model = require_environment(model_env)[model_env]
        evidence[provider] = certify_tool_rounds(
            provider,
            model=model,
            max_output_tokens=1024 if provider == "ollama" else 4096,
        )
    write_json_artifact("live-provider-tools.json", evidence)
    print("CERTIFIED: configured provider dependent tools and usage")


if __name__ == "__main__":
    live_entrypoint(main)
