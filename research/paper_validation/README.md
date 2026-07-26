# Praval 0.8.1 paper validation

This folder is the evidence boundary for the Praval technical report. It tests
the published `praval-0.8.1-py3-none-any.whl`, whose SHA-256 is:

```text
70b0220a2ced6c0bd066423566c4e1811caa9015b128604d2bc5b3c8d57379c5
```

The wheel is associated with tag commit
`fa20513e7cc982fd8d94b81c19e55a9427a6f48c`. The runner rejects another
wheel, another version, a mismatched local tag, and imports from `src/praval`.

## Commands

Run commands from the Praval repository root:

```bash
python -m research.paper_validation audit
python -m research.paper_validation validate
python -m research.paper_validation run --tier offline
python -m research.paper_validation run --tier services
python -m research.paper_validation run --tier comparative
python -m research.paper_validation run --tier live
python -m research.paper_validation analyze --run-dir <run-directory>
python -m research.paper_validation export-paper --run-dir <run-directory>
python -m research.paper_validation curate --run-dir <canonical-run>
python -m research.paper_validation analyze --run-dir <offline-run> \
  --run-dir <services-run> --run-dir <comparative-run> \
  --output-dir <evidence-directory>
python -m research.paper_validation paper-validate \
  --paper-root ../praval_paper
python -m research.paper_validation build-paper \
  --paper-root ../praval_paper --output-dir <build-directory>
```

Use `--quick` only for harness development. Quick runs are marked
`canonical = false`; their claim statuses are `provisional_smoke_result`, never
`validated`.

## Evidence layout

- `features.toml` records the 0.8.1 implementation inventory.
- `claims.toml` states the wording that evidence may permit.
- `experiments.toml` freezes the experiment and artifact contract.
- `references.toml` is the versioned citation registry and BibTeX source.
- `comparative/locks/` freezes every comparison dependency.
- `baseline/` records hashes and the citation state of the paper before edits.
- `results/runs/` is ignored transient output.
- `results/canonical/` is reserved for sanitized, reviewed evidence selected
  for the paper.

Each run retains its environment, dependency list, raw JSONL samples, failures,
derived JSON, Markdown, and LaTeX. A failed experiment remains in the run. The
harness never converts missing services, credentials, or artifacts into a
passing result.

Combined analysis rejects duplicate experiment ownership across selected runs.
It emits the claim ledger, dimension-preserving statistics, RQ tables, 300-dpi
PNG figures, SVG figures, and a digest manifest. The paper build expands only
registered, hash-pinned fragments under the paper repository's `generated/`
folder.

## Secret handling

Only manifest-declared environment names enter service or live workers.
Credential values and authorization headers are redacted from captured output.
Do not commit private provider output, audio generated from private material,
service databases, or credential-bearing URLs. Archive large private evidence
separately and retain only its digest when needed.

## Interpretation

Passing deterministic fake-provider tests establishes the shared Praval
contract, not universal live-provider behavior. Passing Secure Spore behavior
tests establishes round-trip and tamper behavior, not a cryptographic proof.
Service and performance results apply only to their recorded environments.
