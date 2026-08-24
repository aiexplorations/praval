"""Tests for deterministic, privacy-aware JSONL evaluation datasets."""

from __future__ import annotations

import json

import pytest

from praval.eval import EvalDatasetError, Gate, GateAggregation, GateOperator
from praval.eval.dataset import load_jsonl_suite
from praval.models import ContentKind


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_loader_separates_ephemeral_material_from_persisted_case(tmp_path) -> None:
    dataset = tmp_path / "cases.jsonl"
    _write_jsonl(
        dataset,
        [
            {
                "id": "case-1",
                "name": "Grounded answer",
                "input": {"question": "What is Praval?"},
                "expected_output": "An agent framework",
                "reference_contexts": ["Praval documentation"],
                "expected_tool_calls": ["search"],
                "metadata": {"difficulty": "smoke", "priority": 1},
                "tags": ["docs", "smoke"],
            }
        ],
    )

    loaded = load_jsonl_suite(
        dataset,
        suite_id="suite-1",
        name="Documentation quality",
        target="researcher",
        judges=("quality-judge",),
        metrics=("correctness",),
    )

    assert loaded.suite.case_ids == ("case-1",)
    assert loaded.cases[0].input == {"question": "What is Praval?"}
    assert loaded.cases[0].expected_output == "An agent framework"
    assert loaded.cases[0].reference_contexts == ("Praval documentation",)
    case = loaded.cases[0].case
    assert case.input.kind is ContentKind.PROMPT
    assert case.expected_output is not None
    assert case.expected_output.kind is ContentKind.RESPONSE
    assert case.reference_contexts[0].kind is ContentKind.CONTEXT
    assert [(item.key, item.value) for item in case.metadata] == [
        ("difficulty", "smoke"),
        ("priority", 1),
    ]
    persisted = case.model_dump_json()
    assert "What is Praval?" not in persisted
    assert "An agent framework" not in persisted
    assert "Praval documentation" not in persisted


def test_hashes_are_canonical_for_equivalent_json_values(tmp_path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(first, [{"id": "case", "input": {"b": 2, "a": 1}}])
    second.write_text('{"input":{"a":1,"b":2},"id":"case"}\n', encoding="utf-8")

    first_loaded = load_jsonl_suite(
        first, suite_id="suite", name="Suite", target="agent"
    )
    second_loaded = load_jsonl_suite(
        second, suite_id="suite", name="Suite", target="agent"
    )

    assert first_loaded.cases[0].case.input.sha256 == (
        second_loaded.cases[0].case.input.sha256
    )
    assert first_loaded.cases[0].case.input.size_bytes == (
        second_loaded.cases[0].case.input.size_bytes
    )


def test_selection_is_deterministic_and_independent_of_file_order(tmp_path) -> None:
    rows = [
        {"id": f"case-{index}", "input": f"question-{index}", "tags": ["smoke"]}
        for index in range(10)
    ]
    forward = tmp_path / "forward.jsonl"
    reverse = tmp_path / "reverse.jsonl"
    _write_jsonl(forward, rows)
    _write_jsonl(reverse, list(reversed(rows)))

    first = load_jsonl_suite(
        forward,
        suite_id="suite",
        name="Suite",
        target="agent",
        include_tags=("smoke",),
        limit=4,
        seed=42,
    )
    repeated = load_jsonl_suite(
        forward,
        suite_id="suite",
        name="Suite",
        target="agent",
        include_tags=("smoke",),
        limit=4,
        seed=42,
    )
    reordered = load_jsonl_suite(
        reverse,
        suite_id="suite",
        name="Suite",
        target="agent",
        include_tags=("smoke",),
        limit=4,
        seed=42,
    )
    different_seed = load_jsonl_suite(
        forward,
        suite_id="suite",
        name="Suite",
        target="agent",
        include_tags=("smoke",),
        limit=4,
        seed=7,
    )

    assert first.suite.case_ids == repeated.suite.case_ids
    assert first.suite.case_ids == reordered.suite.case_ids
    assert first.suite.case_ids != different_seed.suite.case_ids


def test_case_id_filter_preserves_requested_identity_set(tmp_path) -> None:
    dataset = tmp_path / "cases.jsonl"
    _write_jsonl(
        dataset,
        [
            {"id": "a", "input": "A"},
            {"id": "b", "input": "B"},
            {"id": "c", "input": "C"},
        ],
    )

    loaded = load_jsonl_suite(
        dataset,
        suite_id="suite",
        name="Suite",
        target="agent",
        case_ids=("c", "a"),
    )

    assert loaded.suite.case_ids == ("a", "c")


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ('{"id":"case","input":"ok"}\nnot-json\n', "line 2"),
        ('{"id":"case"}\n', "input"),
        (
            '{"id":"same","input":"one"}\n' '{"id":"same","input":"two"}\n',
            "duplicate case id",
        ),
        ('["not", "an", "object"]\n', "JSON object"),
        ('{"id":"case","input":NaN}\n', "finite JSON"),
        ('{"id":"case","input":"ok","metadata":{"nested":{}}}\n', "scalar"),
        ('{"id":"case","input":"ok","metadata":[]}\n', "JSON object"),
        ('{"id":"case","input":"ok","metadata":{"score":NaN}}\n', "finite"),
        ('{"id":"case","input":"ok","metadata":{"bad key":1}}\n', "invalid metadata"),
        ('{"id":"case","input":"ok","tags":"smoke"}\n', "array of strings"),
        ('{"id":3,"input":"ok"}\n', "non-empty string"),
        ('{"id":"case","input":"ok","reference_contexts":"bad"}\n', "array"),
        ('{"id":"case","name":"","input":"ok"}\n', "invalid case"),
    ],
)
def test_loader_reports_invalid_rows_with_line_context(
    tmp_path, contents: str, message: str
) -> None:
    dataset = tmp_path / "invalid.jsonl"
    dataset.write_text(contents, encoding="utf-8")

    with pytest.raises(EvalDatasetError, match=message):
        load_jsonl_suite(dataset, suite_id="suite", name="Suite", target="agent")


def test_loader_rejects_missing_selection_and_resource_overflow(tmp_path) -> None:
    dataset = tmp_path / "cases.jsonl"
    _write_jsonl(dataset, [{"id": "case", "input": "x" * 20}])

    with pytest.raises(EvalDatasetError, match="unknown case ids"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            case_ids=("missing",),
        )
    with pytest.raises(EvalDatasetError, match="content limit"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            max_content_bytes=10,
        )
    with pytest.raises(EvalDatasetError, match="contains no cases"):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("\n", encoding="utf-8")
        load_jsonl_suite(empty, suite_id="suite", name="Suite", target="agent")
    with pytest.raises(EvalDatasetError, match="case selection contains no cases"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            include_tags=("missing",),
        )


def test_loader_enforces_file_line_case_and_argument_bounds(tmp_path) -> None:
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(EvalDatasetError, match="unable to read"):
        load_jsonl_suite(missing, suite_id="suite", name="Suite", target="agent")

    dataset = tmp_path / "cases.jsonl"
    _write_jsonl(
        dataset,
        [{"id": "a", "input": "A"}, {"id": "b", "input": "B"}],
    )
    with pytest.raises(EvalDatasetError, match="line exceeds"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            max_line_bytes=5,
        )
    with pytest.raises(EvalDatasetError, match="case limit"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            max_cases=1,
        )
    with pytest.raises(ValueError, match="resource limits"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            max_cases=0,
        )
    with pytest.raises(ValueError, match="limit must be positive"):
        load_jsonl_suite(
            dataset,
            suite_id="suite",
            name="Suite",
            target="agent",
            limit=0,
        )


def test_loader_carries_versioned_gates_into_suite(tmp_path) -> None:
    dataset = tmp_path / "cases.jsonl"
    _write_jsonl(dataset, [{"id": "case", "input": "question"}])
    gate = Gate(
        gate_id="quality",
        metric="correctness",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
    )

    loaded = load_jsonl_suite(
        dataset,
        suite_id="suite",
        name="Suite",
        target="agent",
        gates=(gate,),
    )

    assert loaded.suite.gates == (gate,)
