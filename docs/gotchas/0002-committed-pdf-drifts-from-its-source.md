---
status: promoted
date: 2026-09-30
promoted_to: .github/workflows/checks.yml
tags: [paper, docs]
---
# A committed PDF drifts from the LaTeX source it was built from

## Symptom
The published v1.0 PDF still said "ROL:" after the source was fixed to "ROLE:" in PR #2: the
`.tex` changed, the PDF was never rebuilt, and nothing noticed.

## What to do
Rebuild the PDF whenever its sources change (`docs/paper/README.md`) and commit it in the same
pull request.

Promoted: the "Paper PDF rebuilt with its sources" step in `checks.yml` fails a pull request that
changes `docs/paper/afaw.tex`, `AGENTS.md` (the appendix) or `docs/img/` without changing
`docs/paper/afaw.pdf`. It checks that the PDF changed, not that it matches the source.
