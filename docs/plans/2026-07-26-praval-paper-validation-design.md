# Praval 0.8.1 paper validation design

## Purpose

The Praval paper contains architectural, behavioral, performance, and security
claims that predate Praval 0.8.1. This project will validate those claims
against the exact 0.8.1 wheel before the paper is revised.

The revised paper will use one central thesis:

> Praval separates decentralized agent coordination through Reef and Spores
> from provider-neutral model execution through `ModelRuntime`.

The project will describe the released implementation. It will not change the
framework to make a paper claim pass. A failed or narrow result will change the
wording of the paper or become a documented limitation.

## Evidence model

The research harness will live under `research/paper_validation/`. It will
maintain three linked records:

1. A feature inventory derived from the 0.8.1 release, public API, source,
   tests, examples, and release certification.
2. A claim registry that records the proposed wording, scope, implementation
   evidence, citations, experiments, and acceptance rule for each paper claim.
3. An experiment registry that records the tier, scenario, repetitions,
   prerequisites, expected artifacts, and validity checks.

The validator will reject duplicate identifiers, unsafe paths, missing
evidence, unknown experiment links, unstated secrets, and performance or
security claims without experiments.

## Execution tiers

- Offline experiments use deterministic providers, in-memory services, fixed
  fixtures, and fault injection. They must run in normal CI.
- Service experiments use pinned containers such as RabbitMQ, PostgreSQL,
  Redis, MinIO, Qdrant, and an OTLP collector.
- Live experiments use configured model providers. They are manual and record
  the provider and model identifiers returned during the run.
- Comparative experiments isolate Praval, LangGraph, and CrewAI in separate
  environments and use one controller, fixture set, and scoring protocol.

Every canonical run will verify the exact wheel hash, package version, import
path, source commit, environment, and dependency versions. Reports will keep
raw samples separate from summaries. Reports will redact credentials and
authorization data.

## Experiment families

The initial offline suite will cover runtime contracts, capability rejection,
Spore V2 compatibility, Reef topology timing, lifecycle behavior, Secure
Spore integrity, and abstraction overhead. Service and live suites will extend
the same claim registry instead of creating separate claims.

Performance experiments will use monotonic clocks, warmups, repeated fresh
processes where needed, raw samples, percentiles, and bootstrap confidence
intervals. The controlled framework comparison will separate deterministic
framework overhead from live model time and correctness.

## Paper workflow

The Markdown technical report remains the editorial source. The bibliography
will use stable citation keys. Experiment analysis will generate Markdown,
LaTeX, and figure artifacts so that numeric results are not typed into the
paper by hand.

The paper audit will identify unsupported absolute language, stale benchmark
figures, and security statements that exceed the implementation. The abstract,
contributions, results, limitations, future work, and conclusion will be
rewritten only after the claim report is available.

## Acceptance

The work is complete when every substantive paper claim has implementation
evidence, an experiment, a citation, or an explicit limitation. Offline
evidence must pass against the exact 0.8.1 wheel. Service and live results must
state their environment and limits. The paper and bibliography must build
without unresolved references, stale experiment identifiers, or numeric
values that disagree with generated evidence.
