# Praval Agent-Team Showcase Capstones

## Goal

Replace the four small case-study notebooks with substantial showcases for
agent-heavy work in research, customer support, software delivery, and marketing.
The course continues to explain Praval step by step. The capstones assume that
knowledge and concentrate on team architecture, message contracts, failure
recovery, inspectable state, and useful final artifacts.

The catalog remains at seventeen notebooks. Research, support, and release
readiness are deterministic offline certifications. Marketing is a protected live
OpenAI certification. No Praval public API, top-level export, or runtime dependency
changes are part of this work.

## Shared capstone contract

Each capstone contains eighteen to twenty-four purposeful cells and at least six
agents, two registered tools, a correlated Spore trail, inspectable state, a
failure or revision path, and a substantial final artifact. Domain messages carry
a type, case identifier, correlation identifier, producer, stage, status, and
domain payload.

Meaningful Praval operations remain visible in notebook cells. The internal
notebook support module may render message graphs, scorecards, and artifacts, but
must not contain workflow logic. Committed notebooks contain no outputs,
credentials, absolute paths, or silent skip paths.

Small fixtures live under the notebook tree with provenance and SHA-256 hashes.
They are copied into exact-wheel execution workspaces and included in the source
distribution.

## Research Intelligence Desk

An eight-agent research desk evaluates a market-entry decision from customer
interviews, competitor claims, analyst notes, stale material, and contradictory
evidence. A director fans work out to market, customer, and competitor specialists.
An evidence auditor checks source lookup, freshness, and citation coverage. A
skeptical reviewer forces a bounded editorial revision before publication.

The final decision brief includes the recommendation, evidence table,
counterarguments, uncertainties, and validation experiments. Offline certification
requires all specialists to terminate explicitly, unsupported evidence to be
rejected, accepted claims to be fully cited, memory to contain evidence and
revision history, and the final artifact to satisfy its schema.

## Customer Support Resolution Center

An eight-agent support team handles a synthetic enterprise service regression and
service-credit request. Intake routes the case while customer-context, knowledge,
technical, and policy specialists work in parallel. A resolution coordinator
drafts the answer. A customer advocate rejects the first response because it uses
stale guidance and ignores remembered customer context. An explicit reviewer Spore
records the offline human escalation boundary.

The final case record contains diagnosis, evidence, policy rationale, approved
action, customer-facing response, state transitions, and escalation history.
Offline certification verifies routing, memory retrieval, tool execution, stale
article rejection, bounded revision, reviewer participation, and closure.

## Software Release Readiness Team

A nine-agent release team reviews a small committed Python candidate. The candidate
contains a real failing test plus security and documentation defects. Review agents
inspect changes, run tests without a shell, check security, validate packaging, and
review documentation. A remediation planner selects an allow-listed patch that is
applied only to a temporary copy. Verification reruns the checks before the final
gate decision.

The release dossier records findings, evidence, remediation, before-and-after
checks, residual risk, timing, and the final decision. Offline certification
requires an initial no-go, real test and security failures, bounded remediation,
passing verification, finalized local traces, a final go, and workspace cleanup.

## AI Marketing Studio

A ten-role marketing studio starts from an already-built product and solves the
remaining positioning and distribution problem. It uses a product brief, brand
guide, customer interviews, approved facts, a product screenshot, channel
constraints, and bounded early campaign signals. Audience and customer research
feed positioning, channel planning, and a multi-asset content studio. Claims and
creative reviewers force one bounded revision.

The protected live notebook uses real OpenAI calls through Agent and ModelRuntime,
structured outputs, real screenshot input, and a model-generated call to an
approval-protected claims tool. The intervention is persisted, inspected, edited
or approved, and resumed. A learning pass stores the winning message, failed
hypothesis, and next experiment. The final launch kit contains positioning,
message hierarchy, channel assets, approved claims, measurement, and the next
experiment.

## Certification and release

Manifest schema version 2 remains unchanged. The mode totals remain ten offline,
two services, and five live notebooks. Structural checks validate the renamed
catalog, prerequisites, cell pacing, fixture provenance, clean notebook state, and
support-module boundaries.

All deterministic capstones run against the exact wheel outside the source tree in
normal CI. Marketing runs only through protected manual live certification using
`OPENAI_API_KEY` and `PRAVAL_OPENAI_MODEL`. The complete package, coverage, typing,
formatting, lint, documentation, reproducibility, distribution, and rendering gates
remain release requirements.
