# README and changelog learning design

## Purpose

The README should help a reader understand what Praval is, choose the right
entry point, run a useful example, and find the next learning resource without
first reading the reference manual. The 0.8 changelog should explain the
release in terms of user impact, compatibility, migration, and known limits.

## README structure

Use a layered structure so readers can stop after the information they need:

1. A concise statement of purpose and the two supported ways to build.
2. A small architecture diagram and plain definitions of the main concepts.
3. A path selector for direct agents, collaboration, tools, memory, MCP, HITL,
   voice, local models, and distributed execution.
4. Installation options and two tested quick starts.
5. A feature map that states supported behavior and important boundaries.
6. Learning paths through the 13 course notebooks, four capstones, runnable
   examples, videos, and reference documentation.
7. Development, validation, compatibility, and release information.

The README will link to maintained material rather than copy full tutorials or
API reference pages. It will not hard-code the current published version.

## Changelog structure

Keep all historical entries unchanged. Expand only the unreleased 0.8 entry:

1. Release overview and major themes.
2. User-facing highlights and links to deeper guides.
3. Detailed Added, Changed, Fixed, Compatibility, Migration, Learning
   Resources, Validation, and Deferred sections.
4. The OpenAI Responses tool-schema, voice fixture, and WAV evidence fixes
   found during live certification.

The changelog will not contain copied test counts, coverage values, artifact
hashes, or dates that belong in generated release evidence.

## Validation

- Compile every Python block in the README.
- Resolve repository-local learning and documentation links.
- Run documentation contract and release metadata tests.
- Run formatting and plain-writing review passes.
- Preserve the existing uncommitted live-certification changes.
