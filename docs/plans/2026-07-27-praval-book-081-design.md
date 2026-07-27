# Praval 0.7.22 context and 0.8.1 book revision

## Purpose

This project will add the missing historical context to the Praval paper and
turn the archived book into a maintained Praval 0.8.1 reference. It will also
extend the existing paper validation harness so that claims and Python examples
in the book can be checked against the exact published wheel.

No public Praval runtime API will change.

## Editorial model

The paper will preserve the author's current opening sentences. A new passage
of 350 to 500 words will explain what Praval provided by version 0.7.22 and how
version 0.8.1 extended that foundation. The passage will separate coordination
features from the provider-neutral execution features introduced in the 0.8
series. Historical statements will cite the version 0.7.22 release, tag, code,
tests, or an explicit limitation.

The book will remain at `docs/archive/praval-book.md`. Its title page will
identify Praval 0.8.1 and Book Edition 1.1, July 2026. The revised chapters will
define Agent, Reef, Spore, and `ModelRuntime` before relying on those terms.
They will cover coordination, execution, tools, durable human intervention,
data services, operations, testing, and deployment limits. Optional features
will state their installation and configuration requirements.

The prose will use direct technical statements, standard grammar, sentence case
headings, and the Oxford comma for true series. It will remove invented
incidents, fabricated measurements, and unsupported absolute claims.

## Evidence and example model

Claims may name both `paper_sections` and `book_sections`. New historical claims
will cover the pre-0.8 coordination foundation, the version 0.7.22 durable HITL
boundary, and the version 0.8.1 execution-plane transition.

Every Python fence in the book will have an adjacent
`PRAVAL_BOOK_EXAMPLE` marker with a unique ID and one mode:

- `run` executes a complete offline example against the exact wheel.
- `compile` compiles a self-contained fragment without provider calls.
- `display` permits an intentionally partial example only when the marker
  includes a reason.

The validator will reject missing markers, duplicate IDs, unknown modes,
unsafe or obsolete imports, source-tree imports, unsupported version claims,
broken local links, unresolved citations, and strong claims that lack support.
Exact-wheel runs will verify package version, package path, and SHA-256 before
examples execute.

## Internal commands

The existing `research.paper_validation` command will gain three subcommands:

```text
python -m research.paper_validation book-audit \
  --book docs/archive/praval-book.md

python -m research.paper_validation book-validate \
  --book docs/archive/praval-book.md \
  --wheel dist/praval-0.8.1-py3-none-any.whl

python -m research.paper_validation build-book \
  --book docs/archive/praval-book.md \
  --output docs/archive/praval-book.pdf
```

The build will use Pandoc and XeLaTeX. It will generate the bibliography from
the evidence reference registry and keep temporary files outside the
repository.

## Validation and delivery

Unit tests will cover manifest compatibility, marker parsing, audit failures,
exact-wheel isolation, and CLI behavior. The completed work will run the
focused tests, the full Praval test suite, lint, type checking, paper
validation, book validation, citation checks, and both document builds.

Each final PDF will be rendered to images. The visual review will cover every
page, with focused checks on the title page, contents, code blocks, tables,
figures, references, and final page. Sentence-level HTML revision reports will
be written to `/tmp/revision-praval-paper-history.html` and
`/tmp/revision-praval-book-081.html`.

Commits will include only the design, validation tooling, manifests, paper,
book, bibliography output, and PDFs. Existing Sphinx output and browser files
will remain untouched.
