---
status: promoted
date: 2026-09-30
promoted_to: .github/workflows/scripts-ci.yml
tags: [ci, github]
---
# A required check from a path-filtered workflow blocks documents-only pull requests

## Symptom
A pull request that changes only documents stays unmergeable: the required checks `lint`,
`typecheck` and `tests` show "Expected — Waiting for status to be reported" forever.

## What to do
Do not put `paths:` on the trigger of a workflow whose jobs are required checks: when the
workflow does not run, GitHub never receives a status. Run the workflow on every pull request
and let a first job decide whether any relevant file changed; skip the other jobs with an
`if:` condition. GitHub reports a job skipped by its condition as successful.

Promoted: `scripts-ci.yml` now works this way, so the trap cannot recur there. Apply the same
pattern to any new workflow that becomes a required check.
