---
name: tests
description: Runs the local tier of verification (the tests being written and a lint of the diff); everything else runs in CI.
---

# `tests` Skill

Use this skill when the user asks to run tests, validate code, or uses `/tests`.
AGENTS.md section 11 splits verification in two tiers; this skill is the local one.

1. **Only what finishes in seconds and needs no external service:**
   - the test or test file you are writing: `python -m pytest path/to/test_file.py::test_name -x`
   - ruff on the changed Python files: `ruff check $(git diff --name-only --diff-filter=ACMR origin/main -- '*.py')`
2. **Do not run locally:** the full suite, integration or end-to-end tests, mutation testing,
   builds, load or chaos tests. They run in CI, in parallel, on every pull request.
3. A local red or green is a claim, not a measurement: CI's red-first check verifies that the
   new tests failed on the old code (AGENTS.md section 11).

If a local step fails, fix it (or say what failed) before `commit` or `ship`. Never report a
suite as passing from a local run: link the CI run in the pull request.
