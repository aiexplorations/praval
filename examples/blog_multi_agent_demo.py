"""
Blog multi-agent demo for Praval.

This script corresponds to the "Simple Agent Ecosystem" example in
`aiexplorations_blogposts/praval_post.md`. It defines three collaborating
agents and starts the agent ecosystem.

Run (from the `praval` project root) with a configured environment, e.g.:

    source ../praval_deep_research/.env
    export PRAVAL_DEFAULT_PROVIDER=openai
    export PRAVAL_DEFAULT_MODEL=gpt-4o-mini
    python -m examples.blog_multi_agent_demo
"""

import time

from praval import agent, chat, broadcast, start_agents, get_reef


@agent("researcher", responds_to=["query"])
def researcher(spore):
    """I research topics deeply."""
    findings = chat(f"Research: {spore.knowledge['topic']}")
    broadcast({"type": "analysis_request", "data": findings})


@agent("analyst", responds_to=["analysis_request"])
def analyst(spore):
    """I analyze data for insights."""
    insights = chat(f"Analyze: {spore.knowledge['data']}")
    broadcast({"type": "report_request", "insights": insights})


@agent("writer", responds_to=["report_request"])
def writer(spore):
    """I create polished reports."""
    report = chat(f"Write report: {spore.knowledge['insights']}")
    print(f"Report generated:\\n{report}")


def main() -> None:
    start_agents(
        researcher,
        analyst,
        writer,
        initial_data={"type": "query", "topic": "multi-agent AI systems"},
    )
    # Give agents some time to process messages and complete LLM calls
    time.sleep(5)
    # Gracefully shut down the reef so no new work is scheduled
    # during interpreter shutdown.
    get_reef().shutdown(wait=True)


if __name__ == "__main__":
    main()
