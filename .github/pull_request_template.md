## Description
What changed and why. Name the task: `task_NNN`.

## CI run
Link to the run (checks, scripts CI). Do not paste local output.

## Checklist
- [ ] **Delta**: `summary` and `next` written; `files_touched` filled with `python -m scripts.check_task_delta --base origin/main --write task_NNN`.
- [ ] **Tests**: each added test failed before the change (the red-first check measures it), or the task declares `tests-only` / `refactor`.
- [ ] **Decisions**: any decision that constrains later work is an ADR in `docs/adr/` (status `proposed`).
- [ ] **Equivalent mutants**: proposed here with their reason, never written to `state/equivalent_mutants.json`.
- [ ] **Docs**: README or docs updated if a measured number or the architecture changed.
