# Praval paper evolutionary rewrite design

## Purpose

Rewrite the Praval technical paper as one continuous account of the framework's
development. The paper will cover the framework from its first releases through
0.8.1, explain why each major change was made, and evaluate the current release
with the existing version-pinned evidence.

The paper will not cite, name, or describe the earlier unpublished manuscript.
Useful technical explanations from that draft may be rewritten into the current
paper because they are part of the same author's work. Unsupported claims and
old benchmark values will not be carried forward.

## Central argument

Praval began as a Python framework for message-driven coordination among
specialist agents. The 0.5 and 0.6 series added memory, data, transport, and
security-related facilities. The 0.7 series made the coordination layer more
operational through tools, observability, completion tracking, distributed Reef
support, and durable human intervention. Version 0.8.1 retained that
coordination foundation and added a provider-neutral execution plane centered on
`ModelRuntime`.

The paper will distinguish two claims:

1. Reef and Spores define how agents exchange work and results.
2. `ModelRuntime` defines how an agent invokes a supported model and receives a
   normalized result.

This separation is an implementation boundary. The paper will not present it as
a proof of formal independence or as evidence of universal decentralization.

## Source and evidence policy

The canonical editorial source is
`praval_paper/report/praval_technical_report.md`. The current introductory
language supplied by the author will be preserved unless a later author request
changes it.

Historical statements will use the following evidence, in order:

1. Tagged source and package metadata.
2. Release notes and the changelog.
3. Source and tests retained at the relevant tag.
4. Current exact-wheel experiments when they evaluate 0.8.1 behavior.

The earlier unpublished manuscript is editorial source material only. It will
not appear in the bibliography or prose. It cannot serve as independent
evidence.

Every release state will be recorded as one of:

- `development`
- `tagged_release`
- `documented_release`
- `withdrawn`
- `supported`
- `excluded_transient_state`

The distinction is needed because the repository contains untagged documented
versions, a withdrawn 0.8.0 package, and a reverted internal 1.0.0 version state.

## Historical structure

The main text will group releases into technical eras. A compact appendix will
list individual versions and their status.

### Initial coordination model

The first releases introduced agents, Reef, Spores, and message-driven
coordination. The paper will define each term before relying on it. Coral and
reef language will be treated as naming, not technical evidence.

### Operational expansion in 0.5 and 0.6

This era added the application and data facilities needed around coordination,
including memory, storage, `DataReference`, optional secure Spores, external
transports, and container or service integration. Each optional capability will
be stated with its dependency and configuration boundary.

### Coordination maturity in 0.7

The 0.7 series added registered tools, optional dependency groups,
observability, RabbitMQ-backed Reef delivery, distributed lifecycle support,
immutable Spore behavior, completion tracking, authorization and rate limits,
and durable human intervention. Version 0.7.22 will be identified as the last
stable 0.7 release. Its historical boundary is agent-gated approval, editing,
rejection, SQLite-backed suspension, restart, and resume.

### Execution transition in 0.8.1

The paper will explain the limitation that motivated the new execution plane.
The earlier `Agent.chat()` path coupled model invocation to agent behavior and
did not provide one capability-aware contract across providers. Version 0.8.1
added `ModelRuntime`, `EmbeddingRuntime`, provider profiles, fail-fast
capability checks, normalized requests and responses, streaming, structured
output, reasoning controls, multimodal requests, MCP tool consumption, Spore
V2, and `PravalApp` lifecycle ownership.

Version 0.8.0 will be recorded as withdrawn. The paper's tested release is the
published 0.8.1 wheel.

## Research questions

- **RQ1:** How did Praval's released capabilities develop from its first
  coordination model through 0.8.1, and which historical design claims remain
  supported by source and release evidence?
- **RQ2:** Does Praval 0.8.1 provide a consistent execution contract across
  supported providers and capabilities?
- **RQ3:** Under what workload topologies does Reef choreography shorten the
  critical path, and how does the tested implementation scale?
- **RQ4:** How do human approval, MCP, lifecycle, observability, storage, and
  failure boundaries behave under interruption and adverse conditions?
- **RQ5:** How does Praval compare with pinned LangGraph and CrewAI
  implementations when model work, task semantics, and correctness are
  controlled?

The existing experimental results for RQ1 through RQ4 will be relabeled as RQ2
through RQ5. The new RQ1 is answered by the version ledger and historical claim
audit, not by a performance benchmark.

## Paper structure

1. Introduction and research questions.
2. Origins and development of Praval.
3. Related work.
4. The coordination architecture before 0.8.
5. Why model execution changed.
6. The 0.8.1 two-plane architecture.
7. Governance, interoperability, data, operations, and bounded security.
8. Experimental method and artifact provenance.
9. Results for the five research questions.
10. Discussion of what changed, why it changed, and what the evidence supports.
11. Limitations and threats to validity.
12. Conclusion.
13. Appendices for version history and minimal usage patterns.

## Claim controls

The rewrite will remove or qualify these earlier claims unless current evidence
supports the narrower wording:

- the 3.23, 5.47, and 33.56 second comparison values;
- 90 percent and 41 percent latency reductions;
- formal Actor Model conformance;
- an absolute claim that there is no central controller;
- universal emergence or self-organization;
- persistent or replayable Spore history;
- horizontal scaling without operational qualification;
- perfect forward secrecy or production key rotation;
- unverified case studies; and
- unconditional production readiness.

The phrase "no application-level workflow orchestrator" may be used only for
message topologies that actually have that property.

## Conclusion design

The conclusion will contain four parts:

1. The framework's development and the reason for the 0.8.1 execution plane.
2. Direct answers to the five research questions.
3. The behavior that remains unproven or environment-dependent.
4. A practical statement of when the architecture is useful.

It will not praise the validation process, call the paper a narrative, repeat a
list of every experiment, or claim more than the reported evidence permits.

## Validation harness changes

Add a structured history manifest and parser under
`research/paper_validation/`. Each entry will record the version, status, date,
tag or commit, evidence paths, capability summary, motivation, and successor
relationship.

Extend the claim manifest with historical claims for the major eras. Validation
will reject duplicate versions, unsupported status values, missing local
evidence, impossible chronology, stale research-question labels, unpublished
manuscript citations, and historical claims without registered evidence.

Generate a Markdown and LaTeX version table from the history manifest. Keep the
individual patch ledger in the appendix and use the grouped eras in the main
text.

## Editorial rules

Use standard grammar, sentence-case headings, and the Oxford comma for genuine
series. Prefer direct technical statements. Define terms before using them.
Avoid sales language, rhetorical questions, and metaphors presented as
architecture.

Create `/tmp/revision-praval-paper-evolution.html` for sentence-level editorial
review.

## Build and review

After editing the canonical Markdown:

1. Validate claims, references, local links, generated values, and experiment
   identifiers.
2. Generate the canonical BibTeX, arXiv LaTeX, and PDF from the Markdown.
3. Render every PDF page to images.
4. Inspect the title page, contents, figures, tables, code, references, and final
   page for clipping, overlap, missing glyphs, or poor breaks.
5. Run focused validation tests and the complete paper validation commands.

## Acceptance

The rewrite is complete when:

- the paper reads as one continuous work and does not refer to an earlier
  manuscript;
- every released or documented version is represented in the version ledger;
- the main text explains the technical eras, the reasons for change, and the
  0.8.1 contribution;
- the author's current introductory edits remain present;
- every substantive claim has implementation evidence, experimental evidence,
  a citation, or an explicit limitation;
- no unsupported benchmark, security, scaling, persistence, or production claim
  remains;
- the conclusion answers the research questions and states the limits of the
  evidence;
- Markdown, BibTeX, LaTeX, and PDF outputs build without unresolved references
  or stale result labels; and
- the rendered PDF is readable on every page.

No public Praval runtime API changes are part of this work. The archived book is
outside this rewrite except where shared generated evidence must remain
consistent.
