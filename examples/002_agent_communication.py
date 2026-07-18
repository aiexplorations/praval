#!/usr/bin/env python3
"""Example 002: bounded communication between two Praval agents.

Run with: python examples/002_agent_communication.py
"""

from typing import Dict, List

from praval import agent, broadcast, get_reef, start_agents

QUESTIONS = {
    "creativity": "What role does failure play in the creative process?",
    "learning": "How does feedback change what people retain?",
    "collaboration": "What helps specialists combine their knowledge?",
}

DIALOGUES: List[Dict[str, str]] = []


@agent("questioner", provider="ollama", responds_to=["start_dialogue"])
def curious_questioner(spore):
    """Turn one topic into one correlated question Spore."""
    topic = str(spore.knowledge["topic"])
    correlation_id = str(spore.knowledge["correlation_id"])
    question = QUESTIONS[topic]
    broadcast(
        {
            "type": "question_posed",
            "correlation_id": correlation_id,
            "topic": topic,
            "question": question,
        }
    )
    return {"question": question}


@agent("responder", provider="ollama", responds_to=["question_posed"])
def thoughtful_responder(spore):
    """Answer once and record a terminal result without another broadcast."""
    topic = str(spore.knowledge["topic"])
    answer = (
        f"For {topic}, progress improves when a team makes assumptions visible, "
        "tests them, and shares what it learns."
    )
    DIALOGUES.append(
        {
            "correlation_id": str(spore.knowledge["correlation_id"]),
            "topic": topic,
            "question": str(spore.knowledge["question"]),
            "answer": answer,
        }
    )
    return {"status": "complete", "answer": answer}


def main() -> int:
    """Run three bounded request and response exchanges."""
    DIALOGUES.clear()
    reef = get_reef()
    try:
        for index, topic in enumerate(QUESTIONS, 1):
            start_agents(
                curious_questioner,
                thoughtful_responder,
                initial_data={
                    "type": "start_dialogue",
                    "correlation_id": f"dialogue-{index}",
                    "topic": topic,
                },
            )
            if not reef.wait_for_completion(timeout=10):
                raise TimeoutError(f"dialogue did not complete: {topic}")
    finally:
        reef.shutdown()

    if len(DIALOGUES) != len(QUESTIONS):
        raise RuntimeError("not every dialogue produced a terminal response")

    print("Example 002: Agent Communication")
    for dialogue in DIALOGUES:
        print(f"\n[{dialogue['correlation_id']}] {dialogue['topic'].title()}")
        print(f"Questioner: {dialogue['question']}")
        print(f"Responder: {dialogue['answer']}")
    print("\nCompleted three correlated, bounded Reef exchanges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
