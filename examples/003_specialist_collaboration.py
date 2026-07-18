#!/usr/bin/env python3
"""Example 003: a four-stage specialist collaboration pipeline.

Run with: python examples/003_specialist_collaboration.py
"""

from typing import Any, Dict, List

from praval import agent, broadcast, get_reef, start_agents

PROBLEMS = (
    "How can we reduce food waste in urban areas?",
    "How can we help people form better habits?",
    "How can we make learning more engaging and effective?",
)

RESULTS: List[Dict[str, Any]] = []
MESSAGE_TRAIL: List[Dict[str, str]] = []


def record(correlation_id: str, producer: str, stage: str) -> None:
    """Keep a small visible trail of the Spores produced by the pipeline."""
    MESSAGE_TRAIL.append(
        {
            "correlation_id": correlation_id,
            "producer": producer,
            "stage": stage,
        }
    )


@agent("analyzer", provider="ollama", responds_to=["analyze_problem"])
def problem_analyzer(spore):
    """Identify the decision, stakeholders, and main constraint."""
    problem = str(spore.knowledge["problem"])
    correlation_id = str(spore.knowledge["correlation_id"])
    analysis = {
        "decision": problem,
        "stakeholders": ["people affected", "operators", "funders"],
        "constraint": "The solution must be measurable and practical to test.",
    }
    record(correlation_id, "analyzer", "analysis_complete")
    broadcast(
        {
            "type": "analysis_complete",
            "correlation_id": correlation_id,
            "problem": problem,
            "analysis": analysis,
        }
    )
    return analysis


@agent("creator", provider="ollama", responds_to=["analysis_complete"])
def creative_generator(spore):
    """Generate distinct choices from the shared analysis."""
    correlation_id = str(spore.knowledge["correlation_id"])
    solutions = [
        "Run a small behavior-focused pilot with a clear baseline.",
        "Pair the pilot with a community feedback and support loop.",
        "Use a simple dashboard to expose progress and failed assumptions.",
    ]
    record(correlation_id, "creator", "solutions_generated")
    broadcast(
        {
            "type": "solutions_generated",
            "correlation_id": correlation_id,
            "problem": spore.knowledge["problem"],
            "analysis": spore.knowledge["analysis"],
            "solutions": solutions,
        }
    )
    return {"solutions": solutions}


@agent("evaluator", provider="ollama", responds_to=["solutions_generated"])
def solution_evaluator(spore):
    """Choose a bounded experiment and state its tradeoff."""
    correlation_id = str(spore.knowledge["correlation_id"])
    evaluation = {
        "recommended": spore.knowledge["solutions"][0],
        "reason": "It creates evidence before the team commits to a large program.",
        "tradeoff": "A narrow pilot may miss effects that appear only at scale.",
    }
    record(correlation_id, "evaluator", "evaluation_complete")
    broadcast(
        {
            "type": "evaluation_complete",
            "correlation_id": correlation_id,
            "problem": spore.knowledge["problem"],
            "analysis": spore.knowledge["analysis"],
            "evaluation": evaluation,
        }
    )
    return evaluation


@agent("synthesizer", provider="ollama", responds_to=["evaluation_complete"])
def final_synthesizer(spore):
    """Create one terminal artifact for the correlated problem."""
    correlation_id = str(spore.knowledge["correlation_id"])
    result = {
        "correlation_id": correlation_id,
        "problem": str(spore.knowledge["problem"]),
        "recommendation": spore.knowledge["evaluation"]["recommended"],
        "why": spore.knowledge["evaluation"]["reason"],
        "tradeoff": spore.knowledge["evaluation"]["tradeoff"],
        "success_measure": "Compare the pilot outcome with its recorded baseline.",
    }
    RESULTS.append(result)
    record(correlation_id, "synthesizer", "complete")
    return result


def main() -> int:
    """Run each problem to completion, then print ordered final artifacts."""
    RESULTS.clear()
    MESSAGE_TRAIL.clear()
    reef = get_reef()
    try:
        for index, problem in enumerate(PROBLEMS, 1):
            start_agents(
                problem_analyzer,
                creative_generator,
                solution_evaluator,
                final_synthesizer,
                initial_data={
                    "type": "analyze_problem",
                    "correlation_id": f"problem-{index}",
                    "problem": problem,
                },
            )
            if not reef.wait_for_completion(timeout=10):
                raise TimeoutError(f"specialist pipeline did not complete: {problem}")
    finally:
        reef.shutdown()

    if len(RESULTS) != len(PROBLEMS):
        raise RuntimeError("not every problem produced a final artifact")
    if len(MESSAGE_TRAIL) != len(PROBLEMS) * 4:
        raise RuntimeError("the correlated message trail is incomplete")

    print("Example 003: Specialist Collaboration")
    for result in RESULTS:
        print(f"\n[{result['correlation_id']}] {result['problem']}")
        print(f"Recommendation: {result['recommendation']}")
        print(f"Why: {result['why']}")
        print(f"Tradeoff: {result['tradeoff']}")
        print(f"Success measure: {result['success_measure']}")
    print(f"\nRecorded {len(MESSAGE_TRAIL)} ordered specialist stages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
