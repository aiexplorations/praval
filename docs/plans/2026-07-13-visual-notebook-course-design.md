# Praval 0.8 Visual Notebook Course Design

## Goal

Make the Praval repository the canonical home for an executable visual course that
shows how agents, Reef channels, and Spores behave at runtime. Preserve the existing
YouTube course mapping while updating all code and lifecycle behavior for Praval
0.8.0.

## Source material

The course ports the nine notebooks in `aiexplorations/praval-tutorials` at commit
`7ae1c04`. Their numbering and corresponding Praval AI YouTube video URLs remain
stable. The four notebooks already in `examples/` become registered case studies
instead of remaining uncatalogued top-level files.

This is a curated port, not a Git subtree or an unrelated-history merge. Praval owns
the maintained copies. The original tutorial repository can remain available as a
read-only redirect so external links do not break.

## Information architecture

The maintained material lives under `examples/notebooks/`:

- `course/00` through `course/08` modernize the existing video course.
- `course/09` through `course/12` cover the 0.8 ModelRuntime, HITL, MCP, and
  request-based voice/multimodal APIs.
- `case_studies/` contains the existing building-agents, conversational-memory, and
  student-analytics notebooks.
- `manifest.toml` records execution mode, extras, services, timeout, and video URL.
- `README.md` is the human-facing course index and setup guide.

## Teaching and visual model

Every maintained course notebook follows the same progression:

1. State the observable learning objective and prerequisites.
2. Show a compact architecture or routing diagram.
3. Run the real framework path in small executable cells.
4. Capture timestamped stage events and actual Spore metadata.
5. Render a timeline, routing summary, or state transition table.
6. Assert the structural result so execution failures are unambiguous.
7. Shut down agents, sessions, Reef channels, clients, and services cleanly.

Lightweight HTML and SVG helpers provide consistent agent cards, Spore cards,
execution timelines, and routing diagrams without adding visualization libraries to
Praval's runtime dependencies.

## Execution modes

- `offline`: No credentials or external services. It still uses real Agent, Reef,
  Spore, tool, and runtime code. Deterministic local handlers provide observable
  behavior; they are demonstrations rather than live-provider certification.
- `services`: Uses real ephemeral Qdrant, RabbitMQ, MCP, or OTLP infrastructure.
- `live`: Uses real model, embedding, STT, TTS, and multimodal provider APIs. A mock
  cannot satisfy a live notebook.

Missing prerequisites fail the selected execution mode with a clear sanitized
message. Paid live notebooks are never triggered by a push or pull request.

## Execution and release integration

`scripts/run_notebooks.py` mirrors the exact-wheel demo contract. It creates an
isolated environment, installs the supplied wheel and notebook dependencies, copies
the selected notebooks outside the source tree, clears `PYTHONPATH`, executes them,
and writes a machine-readable report containing commit, wheel hash, mode, duration,
and results.

Normal CI executes offline notebooks against the exact wheel. Service notebooks run
only where their ephemeral dependencies are present. The protected manual live-demo
workflow executes live notebooks using the same previously built artifact. The wheel
is never rebuilt for notebook certification.

## Quality rules

- Every `.ipynb` under `examples/notebooks/` is registered.
- Stored outputs are stripped from committed notebooks.
- Notebooks contain no credentials, local absolute paths, or successful skip exits.
- Offline notebooks execute top to bottom in CI with zero errors or skipped cells.
- Live and service notebooks have explicit prerequisite checks and bounded timeouts.
- The sdist includes notebooks, the manifest, helpers, and course index.
- Distribution validation checks that the notebook catalog is present.

## YouTube compatibility

Notebooks `00` through `08` retain their exact existing video IDs and display a note
that the recording demonstrates the earlier course while the executable code is
maintained for 0.8. New videos can replace or supplement URLs through manifest-only
metadata changes. The course index links both directions between code and video.

