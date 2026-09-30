---
status: proposed
date: 2026-09-30
tags: [knowledge, method]
---
# Decisions are recorded as ADRs in markdown, and LASTCONTEXT.md only indexes them

## Context
Version 1.0 kept decisions as one-line entries (`architecture_decisions`) inside a generated
`lastcontext.json`. One line says what was decided, not which problem it solves or which
alternatives were rejected, so a later agent or person is likely to reverse it. A hand-kept
`LASTCONTEXT.md` in a real project grew until it needed manual snapshots, and the same rule
appeared in three of its sections.

## Decision
Every decision that constrains later work is an architecture decision record in
`docs/adr/NNNN-slug.md` with Context, Decision, Alternatives considered and Consequences, and
a small front matter (status, date, supersedes, tags). The generated `LASTCONTEXT.md` lists
the accepted and proposed ADRs as one line and a path each. Operational traps are gotchas in
`docs/gotchas/`. A record leaves the index only when superseded, deprecated, resolved or
promoted, never because of its age.

## Alternatives considered
- Decisions as JSON records in the delta: machine-readable, but they carry no reasoning, and
  keeping a prose copy elsewhere duplicates them.
- A hand-kept `LASTCONTEXT.md` with periodic snapshots: grows without bound, mixes items with
  different life cycles, and cleaning a shared file while other agents write to it conflicts.
- Summarizing old context with a model: the summary is an unmeasured claim and can drop the
  detail that mattered.

## Consequences
Decisions are reviewable in the pull request that introduces them. `check_docs.py` verifies
the structure of records, not that a decision was recorded: a missing ADR is left to the
reviewer. The number of active records is measured against a budget, and the human prunes.
