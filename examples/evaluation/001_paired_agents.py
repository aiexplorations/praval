"""Paired target and least-privilege evaluator agents with fake providers."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from praval import Agent, ProviderCapabilities, ToolSpec, get_provider_registry
from praval.eval import (
    AgentEvaluationTarget,
    AgentJudge,
    EvalRunner,
    SQLiteEvaluationStore,
    load_jsonl_suite,
)
from praval.models import ModelResponse, Usage


class FakeEvaluationProvider:
    """Return deterministic target or strict evaluator output by model name."""

    provider_name = "evaluation-fake"

    def __init__(self, config) -> None:
        self.config = config

    async def ainvoke(self, request, tools=None):
        if request.model == "target-model":
            content = json.dumps({"answer": "Paris"})
        else:
            content = json.dumps(
                {
                    "status": "passed",
                    "score": 1.0,
                    "label": "supported",
                    "explanation": "The answer matches the supplied reference.",
                }
            )
        return ModelResponse(
            content=content,
            provider=self.provider_name,
            model=request.model,
            usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
        )


def _agents() -> tuple[Agent, Agent]:
    registry = get_provider_registry()
    registry.register_provider(
        "evaluation-fake",
        FakeEvaluationProvider,
        capabilities=ProviderCapabilities(structured_outputs=True, tools=True),
    )
    target = Agent(
        "answerer",
        provider="evaluation-fake",
        model="target-model",
        persist_state=False,
        config={"temperature": 0, "retries": 0},
    )
    evaluator = Agent(
        "quality-evaluator",
        provider="evaluation-fake",
        model="judge-model",
        persist_state=False,
        config={"temperature": 0, "retries": 0},
    )
    evaluator.add_tool_spec(
        ToolSpec(
            name="policy_lookup",
            parameters={
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
            metadata={"read_only": True, "evaluation_safe": True},
        ),
        lambda topic: f"approved policy for {topic}",
    )
    return target, evaluator


async def run(db_path: Path) -> dict[str, object]:
    target_agent, evaluator_agent = _agents()
    dataset = Path(__file__).with_name("data") / "answers.jsonl"
    suite = load_jsonl_suite(
        dataset,
        suite_id="paired-agents-v1",
        name="Paired target and evaluator",
        target="agent:answerer",
        judges=("quality",),
    )
    judge = AgentJudge(
        name="quality",
        agent=evaluator_agent,
        judge_version="1",
        rubric="Pass only when the answer is supported by the reference.",
        rubric_version="facts-v1",
        allowed_tools=("policy_lookup",),
        tool_policy="read_only",
        timeout_seconds=5,
        max_attempts=1,
        max_input_tokens=1000,
        max_cost_usd=1,
    )
    store = SQLiteEvaluationStore(db_path)
    await store.migrate()
    try:
        result = await EvalRunner(
            store=store,
            target=AgentEvaluationTarget(target_agent),
            judges={"quality": judge},
        ).run(suite, evaluation_run_id=f"paired-{uuid.uuid4()}")
        subjects = await store.list_subjects(evaluation_run_id=result.evaluation_run_id)
        judge_results = await store.list_judge_results(
            evaluation_run_id=result.evaluation_run_id
        )
        return {
            "run_status": result.status.value,
            "passed_cases": result.passed_cases,
            "subject_count": len(subjects),
            "target_agent": subjects[0].observation.agent_name,
            "judge": judge_results[0].judge,
            "judge_status": judge_results[0].status.value,
            "allowed_tools": list(judge.allowed_tools),
        }
    finally:
        await store.close()
        target_agent.close()
        evaluator_agent.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.db)), sort_keys=True))


if __name__ == "__main__":
    main()
