"""Static audits for the Praval paper and its bibliography."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set

PAPER_FILES = (
    "report/praval_technical_report.md",
    "arxiv/praval.tex",
    "arxiv/references.bib",
)
LEGACY_TOKENS = ("90%", "41%", "3.23s", "5.47s", "33.56s")
STRONG_CLAIMS = (
    "No central controller",
    "Actor Model",
    "Location Transparency",
    "persist in the Reef",
    "deterministic replay",
    "horizontal scaling",
    "10,000 msgs/sec",
    "p99",
    "Perfect Forward Secrecy",
    "key rotation",
)
BIB_KEY_RE = re.compile(r"(?m)^@\w+\s*\{\s*([^,\s]+)\s*,")
LATEX_CITE_RE = re.compile(r"\\cite(?!proc)[a-zA-Z*]*\s*\{([^}]+)\}")
PANDOC_LATEX_CITE_RE = re.compile(r"\\citeproc\s*\{\s*ref-([^}\s]+)\s*\}")
PANDOC_CITE_BLOCK_RE = re.compile(r"\[([^\]]*@[^\]]+)\]")
PANDOC_CITE_KEY_RE = re.compile(r"@([A-Za-z0-9_:.+\-/]+)")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LATEX_HEADING_RE = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`*_])")
MARKDOWN_DECORATION_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+|>\s+)+|[*_]{1,2}|`")
LATEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?")
LATEX_BRACE_RE = re.compile(r"[{}]")
CLAIM_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|has|have|provides?|supports?|implements?|"
    r"enables?|uses?|allows?|reduces?|eliminates?|preserves?|operates?|"
    r"executes?|requires?|introduces?|addresses?|ensures?|includes?|"
    r"coordinates?|demonstrates?|shows?|measures?|reports?|scales?)\b",
    re.IGNORECASE,
)
RESULT_EVIDENCE_RE = re.compile(
    r"PRAVAL_(?:RESULT|INCLUDE|VALUE):" r"(?P<evidence>[a-z0-9][a-z0-9_-]*)"
)


EVIDENCE_RULES = (
    (
        re.compile(r"\b(?:90%|41%|3\.23s|5\.47s|33\.56s)\b", re.IGNORECASE),
        "unsupported",
        ("historical-comparison-not-evidence",),
        "Historical figures came from an uncontrolled comparison.",
    ),
    (
        re.compile(
            r"perfect forward secrecy|key rotation is supported|rotate on a schedule",
            re.IGNORECASE,
        ),
        "contradicted",
        ("secure-spore-bounded-claim",),
        "Praval 0.8.1 uses long-lived Box keys and has no production "
        "rotation protocol.",
    ),
    (
        re.compile(
            r"persist(?:s|ent)? in the Reef|deterministic replay|"
            r"persistent message logs",
            re.IGNORECASE,
        ),
        "contradicted",
        ("spore-v2-compatibility", "reef-completion-lifecycle"),
        "The in-memory Reef retains bounded process-local history, not "
        "durable replay logs.",
    ),
    (
        re.compile(
            r"10,?000 msgs/sec|p99|~1gb/s|30% smaller|performance impact is minimal",
            re.IGNORECASE,
        ),
        "unsupported",
        ("reef-scaling-bounded", "secure-spore-bounded-claim"),
        "The baseline paper gives no reproducible run for this numeric claim.",
    ),
    (
        re.compile(r"\bno central (?:controller|coordinator)\b", re.IGNORECASE),
        "validated_with_scope",
        ("two-plane-architecture",),
        "The supported wording is no application-level workflow orchestrator.",
    ),
    (
        re.compile(r"\bactor model\b|location transparency", re.IGNORECASE),
        "validated_with_scope",
        ("two-plane-architecture", "reef-completion-lifecycle"),
        "Praval implements selected actor-like isolation and messaging "
        "properties, not formal conformance.",
    ),
    (
        re.compile(r"\bhorizontal scal(?:e|ing)\b", re.IGNORECASE),
        "unsupported",
        ("reef-scaling-bounded",),
        "Transport interoperability is implemented, but horizontal scaling "
        "needs bounded service evidence.",
    ),
    (
        re.compile(
            r"secure spores?|curve25519|ed25519|xsalsa20|poly1305|"
            r"authenticated encryption",
            re.IGNORECASE,
        ),
        "validated_with_scope",
        ("secure-spore-bounded-claim",),
        "Implementation and behavioral evidence support only bounded "
        "cryptographic claims.",
    ),
    (
        re.compile(r"open(?:telemetry| telemetry)|trace propagation", re.IGNORECASE),
        "validated_with_scope",
        ("observability-once",),
        "Offline and service experiments test trace storage/export boundaries.",
    ),
    (
        re.compile(
            r"rabbitmq|postgresql|redis|minio|qdrant|unified storage",
            re.IGNORECASE,
        ),
        "validated_with_scope",
        ("storage-service-roundtrips",),
        "Service interoperability applies only to pinned providers and the "
        "recorded environment.",
    ),
    (
        re.compile(r"\bspore\b|\breef\b|publish-subscribe|pub/sub", re.IGNORECASE),
        "validated_with_scope",
        ("two-plane-architecture", "spore-v2-compatibility"),
        "Implementation and exact-wheel behavior support a scoped "
        "coordination-plane description.",
    ),
    (
        re.compile(r"\bmemory\b|embedding|vector", re.IGNORECASE),
        "validated_with_scope",
        ("embedding-compatibility",),
        "The implementation supports registered memory and embedding paths "
        "with provider-specific limits.",
    ),
    (
        re.compile(r"\bmcp\b|human-in-the-loop|\bhitl\b", re.IGNORECASE),
        "validated_with_scope",
        ("mcp-tools-bounded-scope", "durable-hitl-resume"),
        "Registered behavioral experiments bound interoperability and recovery claims.",
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_findings(
    text: str, tokens: Sequence[str], *, path: str
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    lowered_tokens = [(token, token.casefold()) for token in tokens]
    for line_number, line in enumerate(text.splitlines(), 1):
        lowered = line.casefold()
        for token, folded in lowered_tokens:
            if folded in lowered:
                findings.append(
                    {
                        "path": path,
                        "line": line_number,
                        "token": token,
                        "text": line.strip(),
                    }
                )
    return findings


def _latex_citations(text: str) -> Set[str]:
    citations: Set[str] = set()
    for match in LATEX_CITE_RE.finditer(text):
        citations.update(
            value.strip()
            for value in match.group(1).split(",")
            if re.fullmatch(r"[A-Za-z0-9_:.+\-/]+", value.strip())
        )
    citations.update(match.group(1) for match in PANDOC_LATEX_CITE_RE.finditer(text))
    return citations


def _pandoc_citations(text: str) -> Set[str]:
    citations: Set[str] = set()
    for block in PANDOC_CITE_BLOCK_RE.finditer(text):
        citations.update(
            match.group(1) for match in PANDOC_CITE_KEY_RE.finditer(block.group(1))
        )
    return citations


def _duplicates(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    duplicates: Set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _split_sentences(value: str) -> List[str]:
    normalized = " ".join(value.split())
    return [
        sentence.strip()
        for sentence in SENTENCE_BOUNDARY_RE.split(normalized)
        if sentence.strip()
    ]


def _is_substantive(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", sentence)
    if len(words) < 8:
        return False
    if sentence.casefold().startswith(
        ("when to use", "example", "source:", "available:")
    ):
        return False
    return bool(CLAIM_VERB_RE.search(sentence))


def _claim_category(sentence: str, section: str) -> str:
    folded = f"{section} {sentence}".casefold()
    if "case stud" in folded:
        return "case_study"
    if any(
        token in folded
        for token in (
            "security",
            "cryptograph",
            "encrypt",
            "signature",
            "keypair",
            "tamper",
        )
    ):
        return "security"
    if any(
        token in folded
        for token in (
            "performance",
            "latency",
            "throughput",
            "p99",
            "faster",
            "overhead",
            "scaling",
            " msgs/sec",
        )
    ):
        return "performance"
    if any(
        token in folded
        for token in (
            "compatib",
            "wire format",
            "protocol",
            "transport",
            "serialization",
        )
    ):
        return "compatibility"
    if any(
        token in folded
        for token in (
            "architecture",
            "actor model",
            "coordination",
            "controller",
            "orchestrat",
            "reef",
            "spore",
        )
    ):
        return "architectural"
    return "behavioral"


def _classify_claim(sentence: str, section: str) -> tuple[str, Sequence[str], str]:
    if "future work" in section.casefold():
        return (
            "future_work",
            (),
            "The baseline paper explicitly presents this statement as future work.",
        )
    for pattern, status, claim_ids, reason in EVIDENCE_RULES:
        if pattern.search(sentence):
            return status, claim_ids, reason
    if "limitation" in section.casefold():
        return (
            "descriptive_only",
            (),
            "The statement records a limitation rather than a positive "
            "capability claim.",
        )
    if "case stud" in section.casefold() or "deployed" in sentence.casefold():
        return (
            "unsupported",
            (),
            "The application assertion requires versioned external "
            "case-study evidence.",
        )
    return (
        "descriptive_only",
        (),
        "The statement is descriptive and has not been promoted to an "
        "experimental claim.",
    )


def _support_required(sentence: str, category: str, section: str) -> bool:
    folded = f"{section} {sentence}".casefold()
    return category in {"performance", "security"} or any(
        name in folded
        for name in (
            "langgraph",
            "crewai",
            "autogen",
            "agno",
            "strands",
            "semantic kernel",
            "metagpt",
            "actor model",
            "publish-subscribe",
        )
    )


def _markdown_claims(text: str, path: str) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    section = "Front matter"
    in_code = False
    paragraph: List[str] = []
    paragraph_line = 1

    def flush() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        cleaned = " ".join(paragraph)
        evidence_experiments = sorted(
            {match.group("evidence") for match in RESULT_EVIDENCE_RE.finditer(cleaned)}
        )
        cleaned = re.sub(r"<!--.*?-->", "", cleaned)
        cleaned = re.sub(r"\{\{PRAVAL_[^}]+\}\}", "", cleaned)
        cleaned = MARKDOWN_DECORATION_RE.sub("", cleaned.strip())
        paragraph = []
        if not cleaned or cleaned.startswith("!["):
            return
        paragraph_citations = sorted(_pandoc_citations(cleaned))
        numeric_citations = sorted(set(re.findall(r"\[(\d+)\]", cleaned)), key=int)
        for sentence in _split_sentences(cleaned):
            if not _is_substantive(sentence):
                continue
            category = _claim_category(sentence, section)
            status, claim_ids, reason = _classify_claim(sentence, section)
            claims.append(
                {
                    "path": path,
                    "line": paragraph_line,
                    "section": section,
                    "text": sentence,
                    "category": category,
                    "status": status,
                    "reason": reason,
                    "claim_ids": list(claim_ids),
                    "citations": paragraph_citations,
                    "legacy_numeric_citations": numeric_citations,
                    "evidence_experiments": evidence_experiments,
                    "support_required": _support_required(sentence, category, section),
                }
            )

    for line_number, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        heading = MARKDOWN_HEADING_RE.match(line)
        if heading:
            flush()
            section = heading.group(2).strip()
            continue
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if re.match(r"^(?:[-*+]\s+|\d+\.\s+)", stripped) and paragraph:
            flush()
        if not paragraph:
            paragraph_line = line_number
        paragraph.append(stripped)
    flush()
    return claims


def _latex_claims(text: str, path: str) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    section = "Front matter"
    in_verbatim = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if re.search(r"\\begin\{(?:verbatim|lstlisting|minted)\}", line):
            in_verbatim = True
            continue
        if re.search(r"\\end\{(?:verbatim|lstlisting|minted)\}", line):
            in_verbatim = False
            continue
        if in_verbatim or line.lstrip().startswith("%"):
            continue
        heading = LATEX_HEADING_RE.search(line)
        if heading:
            section = heading.group(1).strip()
        citation_keys = sorted(_latex_citations(line))
        cleaned = LATEX_CITE_RE.sub("", line)
        cleaned = LATEX_COMMAND_RE.sub("", cleaned)
        cleaned = LATEX_BRACE_RE.sub("", cleaned)
        cleaned = cleaned.replace("~", " ").replace(r"\%", "%")
        for sentence in _split_sentences(cleaned):
            if not _is_substantive(sentence):
                continue
            category = _claim_category(sentence, section)
            status, claim_ids, reason = _classify_claim(sentence, section)
            claims.append(
                {
                    "path": path,
                    "line": line_number,
                    "section": section,
                    "text": sentence,
                    "category": category,
                    "status": status,
                    "reason": reason,
                    "claim_ids": list(claim_ids),
                    "citations": citation_keys,
                    "legacy_numeric_citations": [],
                    "evidence_experiments": [],
                    "support_required": _support_required(sentence, category, section),
                }
            )
    return claims


def audit_paper(paper_root: Path) -> Dict[str, Any]:
    """Audit paper hashes, citations, and claims that require revalidation."""
    root = paper_root.resolve()
    missing_files = [name for name in PAPER_FILES if not (root / name).is_file()]
    if missing_files:
        raise ValueError(
            "paper repository is missing required files: " + ", ".join(missing_files)
        )

    texts = {name: (root / name).read_text(encoding="utf-8") for name in PAPER_FILES}
    hashes = {name: _sha256(root / name) for name in PAPER_FILES}
    bibliography_keys_in_order = BIB_KEY_RE.findall(texts["arxiv/references.bib"])
    bibliography_keys = set(bibliography_keys_in_order)
    citations = _latex_citations(texts["arxiv/praval.tex"])
    citations.update(_pandoc_citations(texts["report/praval_technical_report.md"]))

    legacy_claims: List[Dict[str, Any]] = []
    strong_claims: List[Dict[str, Any]] = []
    for name in PAPER_FILES[:2]:
        legacy_claims.extend(_line_findings(texts[name], LEGACY_TOKENS, path=name))
        strong_claims.extend(_line_findings(texts[name], STRONG_CLAIMS, path=name))

    malformed: List[str] = []
    bibliography = texts["arxiv/references.bib"]
    if bibliography.count("{") != bibliography.count("}"):
        malformed.append("references.bib has unbalanced braces")

    claim_inventory = _markdown_claims(
        texts["report/praval_technical_report.md"],
        "report/praval_technical_report.md",
    )
    claim_inventory.extend(_latex_claims(texts["arxiv/praval.tex"], "arxiv/praval.tex"))
    latex_is_generated = (
        texts["arxiv/praval.tex"].startswith("% Options for packages loaded elsewhere")
        and r"\NewDocumentCommand\citeproc" in texts["arxiv/praval.tex"]
    )
    for index, claim in enumerate(claim_inventory, 1):
        claim["id"] = f"baseline-paper-claim-{index:04d}"
        claim["support_missing"] = bool(
            claim["support_required"]
            and not claim["citations"]
            and not claim["legacy_numeric_citations"]
            and not claim["claim_ids"]
            and not claim["evidence_experiments"]
        )
        if latex_is_generated and claim["path"] == "arxiv/praval.tex":
            claim["support_missing"] = False
            claim["evidence_inherited_from_markdown"] = True
    status_counts = Counter(claim["status"] for claim in claim_inventory)
    category_counts = Counter(claim["category"] for claim in claim_inventory)
    source_support_missing = sum(
        bool(claim["support_missing"])
        for claim in claim_inventory
        if claim["path"] == "report/praval_technical_report.md"
    )
    all_support_missing = sum(
        bool(claim["support_missing"]) for claim in claim_inventory
    )

    return {
        "schema_version": 1,
        "paper_root": str(root),
        "hashes": hashes,
        "citations": {
            "bibliography_records": len(bibliography_keys_in_order),
            "cited_records": len(citations & bibliography_keys),
            "keys": sorted(citations),
            "missing": sorted(citations - bibliography_keys),
            "uncited": sorted(bibliography_keys - citations),
            "duplicate_bibliography_keys": _duplicates(bibliography_keys_in_order),
            "malformed": malformed,
        },
        "legacy_claims": legacy_claims,
        "strong_claims": strong_claims,
        "claim_inventory": claim_inventory,
        "claim_inventory_summary": {
            "total": len(claim_inventory),
            "by_status": dict(sorted(status_counts.items())),
            "by_category": dict(sorted(category_counts.items())),
            "support_missing": source_support_missing,
            "all_sources_support_missing": all_support_missing,
            "generated_latex_inherits_source_evidence": latex_is_generated,
        },
    }


def audit_summary(result: Mapping[str, Any]) -> str:
    """Return a compact Markdown summary for a paper audit."""
    citations = result["citations"]
    lines = [
        "# Praval paper audit",
        "",
        f"- Bibliography records: {citations['bibliography_records']}",
        f"- Cited records: {citations['cited_records']}",
        f"- Missing citation keys: {len(citations['missing'])}",
        f"- Uncited records: {len(citations['uncited'])}",
        f"- Legacy result occurrences: {len(result['legacy_claims'])}",
        f"- Strong-claim occurrences: {len(result['strong_claims'])}",
        f"- Sentence-level claims: {result['claim_inventory_summary']['total']}",
        (
            "- Claims missing required support: "
            f"{result['claim_inventory_summary']['support_missing']}"
        ),
        "",
    ]
    return "\n".join(lines)
