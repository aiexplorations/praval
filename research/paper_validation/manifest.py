"""Load and validate paper claims and experiment manifests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.9 compatibility
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


SCHEMA_VERSION = 1
CLAIM_CATEGORIES = {
    "architectural",
    "behavioral",
    "performance",
    "security",
    "compatibility",
    "case_study",
}
CLAIM_STATUSES = {
    "proposed",
    "validated",
    "validated_with_scope",
    "descriptive_only",
    "unsupported",
    "contradicted",
    "future_work",
}
EXPERIMENT_TIERS = {"offline", "services", "live", "comparative"}
FEATURE_CLASSIFICATIONS = {
    "stable",
    "optional",
    "experimental",
    "compatibility",
    "unsupported",
}
HISTORY_STATUSES = {
    "development",
    "tagged_release",
    "documented_release",
    "withdrawn",
    "supported",
    "excluded_transient_state",
}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class ManifestError(ValueError):
    """Raised when paper validation metadata is incomplete or unsafe."""


@dataclass(frozen=True)
class Claim:
    """One paper claim and its evidence contract."""

    id: str
    statement: str
    category: str
    scope: str
    paper_sections: Tuple[str, ...]
    book_sections: Tuple[str, ...]
    status: str
    implementation_evidence: Tuple[str, ...]
    citations: Tuple[str, ...]
    experiments: Tuple[str, ...]
    acceptance_rule: str
    permitted_wording: str
    limitations: Tuple[str, ...]


@dataclass(frozen=True)
class Experiment:
    """One registered experiment and its execution requirements."""

    id: str
    title: str
    tier: str
    scenario: str
    claim_ids: Tuple[str, ...]
    repetitions: int
    warmups: int
    timeout_seconds: int
    fixtures: Tuple[str, ...]
    services: Tuple[str, ...]
    required_secrets: Tuple[str, ...]
    optional_secrets: Tuple[str, ...]
    expected_artifacts: Tuple[str, ...]
    validity_checks: Tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    """Linked paper claims and experiments."""

    claims: Mapping[str, Claim]
    experiments: Mapping[str, Experiment]


@dataclass(frozen=True)
class Feature:
    """One implementation capability in the Praval 0.8.1 inventory."""

    id: str
    classification: str
    statement: str
    source: Tuple[str, ...]
    evidence: Tuple[str, ...]
    documentation: Tuple[str, ...]
    notes: Tuple[str, ...]


@dataclass(frozen=True)
class HistoryEntry:
    """One source-backed state in Praval's version history."""

    version: str
    status: str
    date: date
    commit: str
    tag: str
    era: str
    summary: str
    motivation: str
    evidence: Tuple[str, ...]
    successor: str
    notes: Tuple[str, ...]


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"manifest does not exist: {path}")
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    return value


def _require_string(item: Mapping[str, Any], field: str, owner: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{owner}: {field} must be a non-empty string")
    return value.strip()


def _optional_string(item: Mapping[str, Any], field: str, owner: str) -> str:
    value = item.get(field, "")
    if not isinstance(value, str):
        raise ManifestError(f"{owner}: {field} must be a string")
    return value.strip()


def _string_tuple(item: Mapping[str, Any], field: str, owner: str) -> Tuple[str, ...]:
    value = item.get(field)
    if not isinstance(value, list) or not all(
        isinstance(entry, str) and entry.strip() for entry in value
    ):
        raise ManifestError(f"{owner}: {field} must be an array of non-empty strings")
    return tuple(entry.strip() for entry in value)


def _unique(values: Sequence[str], field: str, owner: str) -> None:
    if len(values) != len(set(values)):
        raise ManifestError(f"{owner}: {field} must contain unique values")


def _safe_repository_path(
    value: str,
    *,
    repository_root: Path,
    field: str,
    owner: str,
    must_exist: bool,
) -> None:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestError(
            f"{owner}: {field} must stay inside the repository: {value}"
        )
    root = repository_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ManifestError(
            f"{owner}: {field} must stay inside the repository: {value}"
        )
    if must_exist and not resolved.exists():
        raise ManifestError(f"{owner}: {field} does not exist: {value}")


def _raw_tables(
    raw: Mapping[str, Any], name: str, path: Path
) -> Iterable[Dict[str, Any]]:
    values = raw.get(name)
    if not isinstance(values, list) or not values:
        raise ManifestError(f"{path}: at least one [[{name}]] table is required")
    for value in values:
        if not isinstance(value, dict):
            raise ManifestError(f"{path}: every [[{name}]] entry must be a table")
        yield value


def _load_claims(path: Path, repository_root: Path) -> Dict[str, Claim]:
    raw = _load_toml(path)
    claims: Dict[str, Claim] = {}
    for item in _raw_tables(raw, "claim", path):
        claim_id = _require_string(item, "id", str(path))
        if claim_id in claims:
            raise ManifestError(f"duplicate claim id: {claim_id}")
        category = _require_string(item, "category", claim_id)
        status = _require_string(item, "status", claim_id)
        if category not in CLAIM_CATEGORIES:
            raise ManifestError(
                f"{claim_id}: category must use {sorted(CLAIM_CATEGORIES)}"
            )
        if status not in CLAIM_STATUSES:
            raise ManifestError(f"{claim_id}: status must use {sorted(CLAIM_STATUSES)}")
        evidence = _string_tuple(item, "implementation_evidence", claim_id)
        citations = _string_tuple(item, "citations", claim_id)
        experiments = _string_tuple(item, "experiments", claim_id)
        sections = _string_tuple(item, "paper_sections", claim_id)
        book_sections = tuple(
            _string_tuple(item, "book_sections", claim_id)
            if "book_sections" in item
            else ()
        )
        limitations = _string_tuple(item, "limitations", claim_id)
        for field, values in (
            ("implementation_evidence", evidence),
            ("citations", citations),
            ("experiments", experiments),
            ("paper_sections", sections),
            ("book_sections", book_sections),
            ("limitations", limitations),
        ):
            _unique(values, field, claim_id)
        for evidence_path in evidence:
            _safe_repository_path(
                evidence_path,
                repository_root=repository_root,
                field="implementation_evidence",
                owner=claim_id,
                must_exist=True,
            )
        if category in {"performance", "security"} and not experiments:
            raise ManifestError(f"{claim_id}: {category} claims require experiments")
        if not citations and not experiments:
            raise ManifestError(
                f"{claim_id}: claim requires at least one citation or experiment"
            )
        claims[claim_id] = Claim(
            id=claim_id,
            statement=_require_string(item, "statement", claim_id),
            category=category,
            scope=_require_string(item, "scope", claim_id),
            paper_sections=sections,
            book_sections=book_sections,
            status=status,
            implementation_evidence=evidence,
            citations=citations,
            experiments=experiments,
            acceptance_rule=_require_string(item, "acceptance_rule", claim_id),
            permitted_wording=_require_string(item, "permitted_wording", claim_id),
            limitations=limitations,
        )
    return claims


def _load_experiments(path: Path, repository_root: Path) -> Dict[str, Experiment]:
    raw = _load_toml(path)
    experiments: Dict[str, Experiment] = {}
    for item in _raw_tables(raw, "experiment", path):
        experiment_id = _require_string(item, "id", str(path))
        if experiment_id in experiments:
            raise ManifestError(f"duplicate experiment id: {experiment_id}")
        tier = _require_string(item, "tier", experiment_id)
        if tier not in EXPERIMENT_TIERS:
            raise ManifestError(
                f"{experiment_id}: tier must use {sorted(EXPERIMENT_TIERS)}"
            )
        repetitions = item.get("repetitions")
        warmups = item.get("warmups")
        timeout_seconds = item.get("timeout_seconds")
        if not isinstance(repetitions, int) or repetitions <= 0:
            raise ManifestError(f"{experiment_id}: repetitions must be positive")
        if not isinstance(warmups, int) or warmups < 0:
            raise ManifestError(f"{experiment_id}: warmups must be non-negative")
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise ManifestError(f"{experiment_id}: timeout_seconds must be positive")
        claim_ids = _string_tuple(item, "claim_ids", experiment_id)
        fixtures = _string_tuple(item, "fixtures", experiment_id)
        services = _string_tuple(item, "services", experiment_id)
        secrets = _string_tuple(item, "required_secrets", experiment_id)
        optional_secrets = tuple(
            _string_tuple(item, "optional_secrets", experiment_id)
            if "optional_secrets" in item
            else ()
        )
        artifacts = _string_tuple(item, "expected_artifacts", experiment_id)
        checks = _string_tuple(item, "validity_checks", experiment_id)
        if not claim_ids:
            raise ManifestError(f"{experiment_id}: claim_ids must not be empty")
        if not artifacts:
            raise ManifestError(
                f"{experiment_id}: expected_artifacts must not be empty"
            )
        if not checks:
            raise ManifestError(f"{experiment_id}: validity_checks must not be empty")
        for field, values in (
            ("claim_ids", claim_ids),
            ("fixtures", fixtures),
            ("services", services),
            ("required_secrets", secrets),
            ("optional_secrets", optional_secrets),
            ("expected_artifacts", artifacts),
            ("validity_checks", checks),
        ):
            _unique(values, field, experiment_id)
        for fixture in fixtures:
            _safe_repository_path(
                fixture,
                repository_root=repository_root,
                field="fixtures",
                owner=experiment_id,
                must_exist=True,
            )
        for artifact in artifacts:
            _safe_repository_path(
                artifact,
                repository_root=repository_root,
                field="expected_artifacts",
                owner=experiment_id,
                must_exist=False,
            )
        experiments[experiment_id] = Experiment(
            id=experiment_id,
            title=_require_string(item, "title", experiment_id),
            tier=tier,
            scenario=_require_string(item, "scenario", experiment_id),
            claim_ids=claim_ids,
            repetitions=repetitions,
            warmups=warmups,
            timeout_seconds=timeout_seconds,
            fixtures=fixtures,
            services=services,
            required_secrets=secrets,
            optional_secrets=optional_secrets,
            expected_artifacts=artifacts,
            validity_checks=checks,
        )
    return experiments


def load_registry(
    claims_path: Path,
    experiments_path: Path,
    *,
    repository_root: Path,
) -> Registry:
    """Load, validate, and cross-link paper claims and experiments."""
    claims = _load_claims(claims_path, repository_root)
    experiments = _load_experiments(experiments_path, repository_root)
    for claim in claims.values():
        for experiment_id in claim.experiments:
            experiment = experiments.get(experiment_id)
            if experiment is None:
                raise ManifestError(f"{claim.id}: unknown experiment: {experiment_id}")
            if claim.id not in experiment.claim_ids:
                raise ManifestError(
                    f"{claim.id}: experiment {experiment_id} does not link back"
                )
    for experiment in experiments.values():
        for claim_id in experiment.claim_ids:
            linked_claim = claims.get(claim_id)
            if linked_claim is None:
                raise ManifestError(f"{experiment.id}: unknown claim: {claim_id}")
            if experiment.id not in linked_claim.experiments:
                raise ManifestError(
                    f"{experiment.id}: claim {claim_id} does not link back"
                )
    return Registry(claims=claims, experiments=experiments)


def load_feature_inventory(
    path: Path, *, repository_root: Path
) -> Mapping[str, Feature]:
    """Load the versioned Praval 0.8.1 capability inventory."""
    raw = _load_toml(path)
    features: Dict[str, Feature] = {}
    for item in _raw_tables(raw, "feature", path):
        feature_id = _require_string(item, "id", str(path))
        if feature_id in features:
            raise ManifestError(f"duplicate feature id: {feature_id}")
        classification = _require_string(item, "classification", feature_id)
        if classification not in FEATURE_CLASSIFICATIONS:
            raise ManifestError(
                f"{feature_id}: classification must use "
                f"{sorted(FEATURE_CLASSIFICATIONS)}"
            )
        source = _string_tuple(item, "source", feature_id)
        evidence = _string_tuple(item, "evidence", feature_id)
        documentation = _string_tuple(item, "documentation", feature_id)
        notes = _string_tuple(item, "notes", feature_id)
        if not source:
            raise ManifestError(f"{feature_id}: source must not be empty")
        if classification != "unsupported" and not evidence:
            raise ManifestError(
                f"{feature_id}: supported features require executable evidence"
            )
        for field, values in (
            ("source", source),
            ("evidence", evidence),
            ("documentation", documentation),
            ("notes", notes),
        ):
            _unique(values, field, feature_id)
        for field, paths in (
            ("source", source),
            ("evidence", evidence),
            ("documentation", documentation),
        ):
            for value in paths:
                _safe_repository_path(
                    value,
                    repository_root=repository_root,
                    field=field,
                    owner=feature_id,
                    must_exist=True,
                )
        features[feature_id] = Feature(
            id=feature_id,
            classification=classification,
            statement=_require_string(item, "statement", feature_id),
            source=source,
            evidence=evidence,
            documentation=documentation,
            notes=notes,
        )
    return features


def load_history(path: Path, *, repository_root: Path) -> Mapping[str, HistoryEntry]:
    """Load Praval's release and development history in chronological order."""
    raw = _load_toml(path)
    entries: Dict[str, HistoryEntry] = {}
    tags: set[str] = set()
    previous_date: date | None = None
    ordered_versions: list[str] = []
    for item in _raw_tables(raw, "version", path):
        version = _require_string(item, "version", str(path))
        if version in entries:
            raise ManifestError(f"duplicate history version: {version}")
        status = _require_string(item, "status", version)
        if status not in HISTORY_STATUSES:
            raise ManifestError(
                f"{version}: status must use {sorted(HISTORY_STATUSES)}"
            )
        raw_date = _require_string(item, "date", version)
        try:
            released_on = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ManifestError(f"{version}: date must use YYYY-MM-DD") from exc
        if previous_date is not None and released_on < previous_date:
            raise ManifestError(
                f"{version}: history dates must be in chronological order"
            )
        previous_date = released_on
        commit = _require_string(item, "commit", version)
        if not COMMIT_RE.fullmatch(commit):
            raise ManifestError(f"{version}: commit must be a full Git object id")
        tag = _optional_string(item, "tag", version)
        if status in {"tagged_release", "supported"} and not tag:
            raise ManifestError(f"{version}: {status} entries require a tag")
        if tag:
            if tag in tags:
                raise ManifestError(f"duplicate history tag: {tag}")
            tags.add(tag)
        evidence = _string_tuple(item, "evidence", version)
        notes = _string_tuple(item, "notes", version)
        if not evidence:
            raise ManifestError(f"{version}: evidence must not be empty")
        _unique(evidence, "evidence", version)
        _unique(notes, "notes", version)
        for evidence_path in evidence:
            _safe_repository_path(
                evidence_path,
                repository_root=repository_root,
                field="evidence",
                owner=version,
                must_exist=True,
            )
        entries[version] = HistoryEntry(
            version=version,
            status=status,
            date=released_on,
            commit=commit,
            tag=tag,
            era=_require_string(item, "era", version),
            summary=_require_string(item, "summary", version),
            motivation=_require_string(item, "motivation", version),
            evidence=evidence,
            successor=_optional_string(item, "successor", version),
            notes=notes,
        )
        ordered_versions.append(version)
    for index, version in enumerate(ordered_versions):
        successor = entries[version].successor
        if not successor:
            continue
        if successor not in entries:
            raise ManifestError(f"{version}: unknown successor: {successor}")
        if ordered_versions.index(successor) <= index:
            raise ManifestError(f"{version}: successor must occur later in history")
    supported = [
        entry.version for entry in entries.values() if entry.status == "supported"
    ]
    if len(supported) != 1:
        raise ManifestError(
            "history must identify exactly one supported release, found "
            + str(supported)
        )
    return entries
