# Praval paper novelty and visual revision design

## Purpose

Revise the Praval technical report so that its technical contribution is clear
within the first two pages, its history provides context without dominating the
argument, and its architecture can be understood from a small set of precise
figures. The report will remain comprehensive, but it will move detailed
version evidence, public development accounts, and repeated qualifications out
of the main argument where possible.

The canonical editorial source remains
`praval_paper/report/praval_technical_report.md`. The exact published Praval
0.8.1 wheel remains the evaluated implementation boundary. No Praval runtime
API changes are part of this work.

## Contribution and novelty position

The report will make a bounded engineering contribution claim. It will not
claim that Praval invented agent coordination, provider adapters, capability
profiles, publish-subscribe messaging, or human approval. It will state that
Praval 0.8.1 combines these elements behind an explicit compositional boundary:

1. Agent, Reef, and Spore own message-driven coordination among specialist
   handlers.
2. `ModelRuntime`, provider profiles, normalized contracts, and adapters own
   model execution.
3. An application can vary the coordination topology and model execution
   configuration separately within the supported contract.
4. Capability checks reject known unsupported requests at the execution
   boundary before provider invocation.

The report will distinguish architectural novelty from primitive novelty. Its
contribution is the separation, its concrete interfaces, its compatibility
with the existing Reef model, and the evidence that tests the boundary. The
report will not claim that the separation is the first such idea in the field.

## Editorial structure

The abstract and introduction will lead with the engineering problem, the
two-plane design, the tested contribution, and the result scope. The
introduction will retain one concise paragraph on the author's earlier work and
the framework's intellectual influences. It will retain one concise paragraph
on the capability path through 0.7.22 and the change in 0.8.1.

The origins section will become a compact design-provenance section. It will
connect dynamical systems, population-based optimization, swarm intelligence,
stigmergy, and coral reef systems to specific Praval decisions. It will avoid
repeating the same chronology or biological qualifications in later sections.

Detailed version material will remain in the generated appendix ledger.
First-party development posts will remain in the bibliography and evidence
ledger, but their enumeration will move out of the main technical narrative.

The related-work section will end with a short subsection that states the
design gap and novelty scope. It will compare responsibilities and boundaries,
not marketing claims. Any characterization of another framework will use its
pinned source, official documentation, or the controlled comparison artifact.

The architecture, results, discussion, and conclusion will each have one job:

- Architecture defines the components, boundaries, and flows.
- Results report observed behavior.
- Discussion explains what the design changes for an application.
- Conclusion states the contribution, evidence, and remaining limits.

## Figures

The report will use three source-controlled architecture figures. Mermaid
source will be committed beside vector SVG and PDF derivatives. Text and line
weights must remain readable in the single-column report and in arXiv output.

### Figure 1: Two-plane architecture

This figure will show the application and Agent API at the top, then the two
planes side by side.

- The coordination plane contains Agent handlers, Reef, Spore, completion,
  correlation, and the in-memory or RabbitMQ delivery boundary.
- The execution plane contains `ModelRequest`, capability resolution,
  `ModelRuntime`, provider adapters, normalized responses and events, tools,
  and `EmbeddingRuntime`.
- Shared operational facilities contain tracing, memory, storage, and
  lifecycle ownership.
- Arrows will identify which component owns topology, provider choice,
  capability validation, and normalized results.

The prose will explain that the planes interact through an Agent call path but
do not own each other's decisions.

### Figure 2: Reef coordination patterns

This figure will combine pipeline, independent fan-out and fan-in, and
request-reply patterns. It will label dependency, correlation, and completion
points. It will show that fan-out shortens the critical path only when branches
can run concurrently, and that request-reply still has a waiting caller.

### Figure 3: Model execution, tools, and recovery

This figure will follow one request through profile resolution, capability
preflight, adapter translation, provider execution, normalized events, and the
tool loop. The protected-tool branch will show durable suspension, a persisted
intervention, restart, approval or rejection, and continuation. Unsupported
requests and provider failures will end at distinct labeled boundaries.

## Application impact

The discussion will explain the practical effect of the 0.8.1 changes without
claiming unmeasured productivity gains. It will state which responsibilities an
application can delegate to Praval and which responsibilities remain with the
application.

Supported consequences include:

- A Reef topology does not need to encode provider request shapes.
- Direct Agents and message-driven handlers can use the same execution
  contract.
- Capability errors can be found before a remote provider call when the active
  profile declares the limitation.
- Normalized responses, events, usage, tools, and error categories reduce the
  number of provider-specific branches needed at the application boundary.
- Durable human intervention can preserve a protected tool decision across a
  process restart.
- Existing `Agent.chat()` users have a compatibility path while richer callers
  can use the normalized generation interfaces.

The report will also state the limits. Provider neutrality does not imply
identical provider behavior or output quality. Message-driven coordination does
not imply automatic scaling, delivery guarantees, or useful emergence.
Architectural separation does not prove lower development cost without a user
study.

## Evidence changes

The claim ledger will gain a scoped claim for the compositional boundary and
its application consequences. Existing runtime-contract and capability
experiments will supply behavioral evidence. A static exact-wheel boundary
audit will check imports and ownership relationships where that check is
stable and meaningful.

If the existing experiment artifacts do not show that topology is preserved
when execution profiles change, add a deterministic offline scenario. It will
hold one Reef topology constant while changing supported runtime profiles. It
will verify normalized success for supported requests and fail-fast behavior
for unsupported requests before adapter execution.

The controlled framework comparison will remain a performance and correctness
comparison. It will not serve as proof that Praval's architecture is unique.

## Alternatives considered

### Claim fundamental novelty

This would make the strongest headline, but the current evidence does not
support a field-wide first-of-kind claim. It would require a systematic review
and comparable architectural implementations across a broader set of
frameworks.

### Add diagrams without restructuring

This would improve navigation but would leave the contribution buried under
repeated history. Figures cannot correct an unclear argument by themselves.

### Bounded contribution with compact history

This is the selected approach. It matches the implementation evidence, keeps
the intellectual lineage, and gives the report a defensible technical center.

## Validation

The revision is complete when:

- the abstract and introduction state the problem, contribution, evidence, and
  limits without a long version narrative;
- the main historical material is materially shorter and is not repeated in
  the results;
- each architecture figure has committed source, vector output, a clear
  caption, and an explanation in the text;
- each application-impact statement is linked to implementation evidence, an
  experiment, or an explicit limitation;
- the novelty language does not claim field-wide priority;
- Markdown, citations, generated LaTeX, and PDF pass the paper validator;
- every PDF page is rendered and inspected for clipping, overlap, poor breaks,
  missing glyphs, and unreadable figure text; and
- a sentence-level revision review is available in `/tmp`.

