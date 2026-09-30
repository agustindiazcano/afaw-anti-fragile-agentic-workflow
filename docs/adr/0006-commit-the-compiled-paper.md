---
status: proposed
date: 2026-09-30
tags: [paper, docs]
---
# The compiled paper is committed next to its source

## Context
v1.1 stopped committing the paper's PDF, because a committed build output drifts from its
source (gotcha 0002). Readers of the repository, and links from ResearchGate and the README,
need the PDF in the repository itself, without building LaTeX.

## Decision
`docs/paper/afaw.pdf` is committed and linked from the README. A CI step fails a pull request
that changes the paper's sources (`docs/paper/afaw.tex`, `AGENTS.md`, `docs/img/`) without
changing the PDF. The appendix source `appendix_rules.tex` stays generated and ignored.

## Alternatives considered
- Build the PDF only in CI and attach it to a GitHub Release: always in step, but the file is
  not in the repository tree, which is what readers expect.
- Commit the PDF with no check: reproduces the v1.0 drift.

## Consequences
Each paper change costs a local LaTeX build. The check proves the PDF changed, not that it was
built from the committed source; a stale or wrong PDF committed alongside still passes. PDF
bytes are not reproducible (they embed a build date), so a byte comparison is not used.
