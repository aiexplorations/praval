"""Deterministic JSONL loading with an explicit content-persistence boundary."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from praval.models import ContentKind, ContentReference

from .models import EvalCase, EvalSuite, EvaluationMetadata, Gate


class EvalDatasetError(ValueError):
    """A JSONL evaluation dataset violates its bounded public schema."""


@dataclass(frozen=True)
class LoadedEvalCase:
    """Persistable case metadata paired with ephemeral execution material."""

    case: EvalCase
    input: Any
    expected_output: Any | None
    reference_contexts: tuple[Any, ...]


@dataclass(frozen=True)
class LoadedEvalSuite:
    """One selected suite and its ephemeral case material."""

    suite: EvalSuite
    cases: tuple[LoadedEvalCase, ...]


def _canonical_json(value: Any, *, line_number: int) -> bytes:
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise EvalDatasetError(
            f"line {line_number}: values must be finite JSON"
        ) from exc
    return rendered.encode("utf-8")


def _content_reference(
    value: Any,
    *,
    kind: ContentKind,
    dataset_id: str,
    case_id: str,
    field: str,
    line_number: int,
    max_content_bytes: int,
) -> ContentReference:
    encoded = _canonical_json(value, line_number=line_number)
    if len(encoded) > max_content_bytes:
        raise EvalDatasetError(
            f"line {line_number}: {field} exceeds the content limit "
            f"of {max_content_bytes} bytes"
        )
    return ContentReference(
        kind=kind,
        sha256=hashlib.sha256(encoded).hexdigest(),
        size_bytes=len(encoded),
        reference=f"jsonl://{dataset_id}/{case_id}/{field}",
        media_type="application/json",
    )


def _metadata(value: Any, *, line_number: int) -> tuple[EvaluationMetadata, ...]:
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise EvalDatasetError(f"line {line_number}: metadata must be a JSON object")
    items = []
    for key in sorted(value):
        item = value[key]
        if not isinstance(item, (str, int, float, bool)) and item is not None:
            raise EvalDatasetError(
                f"line {line_number}: metadata values must be scalar"
            )
        if isinstance(item, float) and not math.isfinite(item):
            raise EvalDatasetError(
                f"line {line_number}: metadata values must be finite"
            )
        try:
            items.append(EvaluationMetadata(key=key, value=item))
        except ValueError as exc:
            raise EvalDatasetError(
                f"line {line_number}: invalid metadata: {exc}"
            ) from exc
    return tuple(items)


def _string_tuple(value: Any, *, field: str, line_number: int) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise EvalDatasetError(
            f"line {line_number}: {field} must be an array of strings"
        )
    return tuple(value)


def _load_rows(
    path: Path,
    *,
    max_cases: int,
    max_line_bytes: int,
    max_content_bytes: int,
) -> list[LoadedEvalCase]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvalDatasetError(f"unable to read dataset {path}: {exc}") from exc
    dataset_id = hashlib.sha256(raw).hexdigest()
    loaded: list[LoadedEvalCase] = []
    identities: set[str] = set()
    for line_number, encoded_line in enumerate(raw.splitlines(), start=1):
        if not encoded_line.strip():
            continue
        if len(encoded_line) > max_line_bytes:
            raise EvalDatasetError(
                f"line {line_number}: line exceeds {max_line_bytes} bytes"
            )
        try:
            row = json.loads(encoded_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvalDatasetError(f"line {line_number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise EvalDatasetError(f"line {line_number}: row must be a JSON object")
        case_id = row.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise EvalDatasetError(f"line {line_number}: id must be a non-empty string")
        if case_id in identities:
            raise EvalDatasetError(f"line {line_number}: duplicate case id {case_id!r}")
        identities.add(case_id)
        if "input" not in row:
            raise EvalDatasetError(f"line {line_number}: input is required")
        input_value = row["input"]
        expected_value = row.get("expected_output")
        contexts_value = row.get("reference_contexts", [])
        if not isinstance(contexts_value, list):
            raise EvalDatasetError(
                f"line {line_number}: reference_contexts must be an array"
            )
        input_reference = _content_reference(
            input_value,
            kind=ContentKind.PROMPT,
            dataset_id=dataset_id,
            case_id=case_id,
            field="input",
            line_number=line_number,
            max_content_bytes=max_content_bytes,
        )
        expected_reference = (
            _content_reference(
                expected_value,
                kind=ContentKind.RESPONSE,
                dataset_id=dataset_id,
                case_id=case_id,
                field="expected_output",
                line_number=line_number,
                max_content_bytes=max_content_bytes,
            )
            if "expected_output" in row
            else None
        )
        context_references = tuple(
            _content_reference(
                context,
                kind=ContentKind.CONTEXT,
                dataset_id=dataset_id,
                case_id=case_id,
                field=f"reference_contexts/{index}",
                line_number=line_number,
                max_content_bytes=max_content_bytes,
            )
            for index, context in enumerate(contexts_value)
        )
        try:
            case = EvalCase(
                case_id=case_id,
                name=row.get("name", case_id),
                input=input_reference,
                expected_output=expected_reference,
                reference_contexts=context_references,
                expected_tool_calls=_string_tuple(
                    row.get("expected_tool_calls"),
                    field="expected_tool_calls",
                    line_number=line_number,
                ),
                metadata=_metadata(row.get("metadata"), line_number=line_number),
                tags=_string_tuple(
                    row.get("tags"), field="tags", line_number=line_number
                ),
            )
        except ValueError as exc:
            raise EvalDatasetError(f"line {line_number}: invalid case: {exc}") from exc
        loaded.append(
            LoadedEvalCase(
                case=case,
                input=input_value,
                expected_output=expected_value,
                reference_contexts=tuple(contexts_value),
            )
        )
        if len(loaded) > max_cases:
            raise EvalDatasetError(f"dataset exceeds the case limit of {max_cases}")
    if not loaded:
        raise EvalDatasetError("dataset contains no cases")
    return loaded


def load_jsonl_suite(
    path: str | Path,
    *,
    suite_id: str,
    name: str,
    target: str,
    judges: tuple[str, ...] = (),
    metrics: tuple[str, ...] = (),
    gates: tuple[Gate, ...] = (),
    tags: tuple[str, ...] = (),
    case_ids: tuple[str, ...] | None = None,
    include_tags: tuple[str, ...] = (),
    limit: int | None = None,
    seed: int = 0,
    max_cases: int = 100_000,
    max_line_bytes: int = 1_048_576,
    max_content_bytes: int = 262_144,
) -> LoadedEvalSuite:
    """Load, validate, and deterministically select a JSONL evaluation suite."""
    if max_cases <= 0 or max_line_bytes <= 0 or max_content_bytes <= 0:
        raise ValueError("dataset resource limits must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    loaded = _load_rows(
        Path(path),
        max_cases=max_cases,
        max_line_bytes=max_line_bytes,
        max_content_bytes=max_content_bytes,
    )
    by_id = {item.case.case_id: item for item in loaded}
    if case_ids is not None:
        unknown = sorted(set(case_ids) - set(by_id))
        if unknown:
            raise EvalDatasetError(f"unknown case ids: {unknown}")
        selected = [by_id[case_id] for case_id in sorted(set(case_ids))]
    else:
        required_tags = set(include_tags)
        selected = [
            item for item in loaded if required_tags.issubset(set(item.case.tags))
        ]
        selected.sort(key=lambda item: item.case.case_id)
    if not selected:
        raise EvalDatasetError("case selection contains no cases")
    if limit is not None and len(selected) > limit:
        selected.sort(
            key=lambda item: hashlib.sha256(
                f"{seed}\x1f{item.case.case_id}".encode("utf-8")
            ).digest()
        )
        selected = selected[:limit]
        selected.sort(key=lambda item: item.case.case_id)
    suite = EvalSuite(
        suite_id=suite_id,
        name=name,
        target=target,
        case_ids=tuple(item.case.case_id for item in selected),
        judges=judges,
        metrics=metrics,
        gates=gates,
        tags=tags,
    )
    return LoadedEvalSuite(suite=suite, cases=tuple(selected))


__all__ = [
    "EvalDatasetError",
    "LoadedEvalCase",
    "LoadedEvalSuite",
    "load_jsonl_suite",
]
