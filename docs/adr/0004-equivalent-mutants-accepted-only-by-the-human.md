---
status: proposed
date: 2026-09-30
tags: [mutation, tests]
---
# Only the human accepts an equivalent mutant, and the acceptance expires with the file

## Context
The mutation score is K / (N − E). Whether a mutant is equivalent is undecidable in general,
so an agent that marks survivors as equivalent can lower the denominator until the gate
passes: an unmeasured claim in the one place meant to measure test strength.

## Decision
The agent may propose an equivalence, with its reason, in the pull request. Only the human
records it, in `state/equivalent_mutants.json`, validated by its schema; a hook denies agent
writes and CI prints every change to the file in the run summary. Each entry names the file,
the mutant and the file's SHA-256, and expires when the file changes. `scripts/mutation_gate.py`
gates on K / (N − E_human) and reports the raw K / N next to it.

## Alternatives considered
- Gate on the raw score only: honest, but a file with a real equivalent mutant can never pass
  a high threshold, which pushes agents to write artificial tests.
- Let the agent mark equivalences and review them later: the gate would already have passed.

## Consequences
The human reviews each equivalence once per version of the file. The hook is a best-effort
filter; the CI summary is what makes an agent's write visible. Accepting an equivalence is a
judgement and can be wrong.
