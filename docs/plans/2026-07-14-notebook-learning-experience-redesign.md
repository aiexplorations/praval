# Praval Notebook Learning Experience Redesign

## Goal

Turn the Praval notebook collection into a two-tier learning experience. The
thirteen course notebooks teach the framework explicitly from first principles.
The four case studies assume those foundations and demonstrate larger systems
without explaining every line of Python.

The redesign preserves the existing YouTube mappings, exact-wheel execution,
real-service checks, and protected live-provider certification. It adds no public
Praval API and no framework runtime dependency.

## Course teaching contract

Every course notebook follows the same learning sequence:

1. What the learner will build.
2. Prerequisites, estimated time, and execution requirements.
3. Concrete learning goals.
4. A plain-language mental model.
5. An architecture or message-flow diagram.
6. Small concept-and-code steps.
7. Inspection and interpretation after important execution.
8. A practical explanation of why the behavior matters.
9. A guided exercise with an answer scaffold.
10. A common mistake and its correction.
11. An optional, collapsed under-the-hood explanation.
12. A recap, next lesson, and explicit cleanup.

The course progresses from the Agent/Reef/Spore mental model through agent
lifecycle, communication, coordination, tools, memory, services, ModelRuntime,
HITL, MCP, and request-based voice and multimodal execution. Foundational lessons
use especially small code cells. Later lessons assume vocabulary established by
earlier notebooks while retaining optional deeper explanations.

## Case-study teaching contract

Case studies are concise capstones. Each presents a problem, prerequisite course
lessons, architecture, important decisions, implementation by subsystem, one
complete run, runtime inspection, tradeoffs, and extension ideas. They do not
repeat foundational definitions or narrate routine imports and fixture creation.

- Building an agent team is an offline collaboration capstone.
- Conversational memory is an offline memory and personalization capstone.
- Student analytics is an offline deterministic data-pipeline capstone.
- AI-powered student analytics is a protected live OpenAI capstone contrasting
  deterministic code with model reasoning.

All four become maintained certification notebooks rather than reference-only
material.

## Presentation model

A small internal support module owns notebook styling, diagrams, timelines, Spore
cards, prerequisite checks, lifecycle-provider setup, and certification plumbing.
Meaningful Praval operations remain visible in notebook cells.

The visual system uses a restrained, accessible palette for agents, Reef, Spores,
tools, memory, humans, and providers. Notebooks use short callouts, actual runtime
data, self-contained diagrams, and collapsed advanced sections. They avoid remote
assets, excessive emoji, promotional prose, and screenshots of essential content.

## Catalog and certification

Notebook manifest schema version 2 adds prerequisite notebook IDs, estimated time,
and learning level. Prerequisites must resolve, and course prerequisites must refer
to earlier lessons. The three deterministic case studies run in offline CI. The AI
analytics case study runs only in protected live certification.

All seventeen notebooks remain output-free in Git, compile cell by cell, execute
outside the repository against the exact wheel, and produce sanitized evidence.
Normal CI covers ten offline notebooks and two service notebooks. Protected live
certification covers the five provider-backed notebooks.

## Acceptance criteria

- A new Python developer can complete lessons 00 through 02 without external
  Praval documentation.
- Terms are explained before later notebooks rely on them.
- Important operations expose the resulting Praval state, not only final prose.
- Advanced readers can skip introductory text and open under-the-hood sections.
- Case studies feel like real projects instead of duplicated course chapters.
- Every notebook is certified in its declared execution mode without silent skips.
- Existing video links, package limits, and release gates remain intact.
