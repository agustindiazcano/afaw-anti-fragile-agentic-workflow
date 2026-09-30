---
status: proposed
date: 2026-09-30
tags: [tests, ci]
---
# Verification has a local tier and a CI tier, and CI measures the red step

## Context
Version 1.0 sent every check to CI, including single tests. Strict TDD needs a test run at
every red and green step; a push per step is too slow, so in practice the step would be
skipped, and a red step reported by the agent is an unmeasured claim.

## Decision
Locally, the agent runs only the tests it is writing, one test or one file at a time, within
seconds and without external services. Everything else runs in CI. `scripts/red_check.py`
runs the tests a pull request adds against the merge base and requires each to fail. A task
of type `tests-only` or `refactor` skips the check; a single test that documents existing
behavior is declared with `@pytest.mark.characterization(reason=...)`. Both declarations are
printed in the run. A test absent from the old run's report fails the check (exit 2): absence
is never counted as passing.

## Alternatives considered
- Everything in CI: slow feedback, and the red step is not verified anyway.
- Everything local: the local machine becomes the bottleneck, and a local run is a claim.

## Consequences
The red-first check shows that a test fails on the old code, not that it fails for the right
reason: an import error also counts as failing. A characterization marker is a declaration
the reviewer must judge. The local time limit is a rule an agent can exceed. On its first run,
against the pull request that introduced it, the check found a test that passed on the old code
for the wrong reason. The reference implementation runs pytest; another stack replaces one function.
