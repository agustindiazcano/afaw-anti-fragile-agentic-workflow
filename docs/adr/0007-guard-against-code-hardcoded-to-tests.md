---
status: proposed
date: 2026-11-11
tags: [tests, agents, mutation]
---
# Agents never code to a test's values; property-based tests and review back the rule

## Context
Mutation testing finds tests that verify nothing. It does not find an implementation hardcoded
to a test (`if x == 3: return 9`), because the test kills every mutant on that branch, nor a test
that expects the wrong result, nor a case nobody thought of. The red-first check has the same
blind spot. A high score could therefore hide code that does not generalize.

## Decision
Add a rule (AGENTS.md sections 2.10, 11.8, 11.9, 12.7): the agent never hardcodes against a test
and never edits an existing test to make it pass. Back it with property-based tests for pure
logic (Hypothesis; inputs generated, properties derived from the specification, fixed seed in CI),
optional human-written held-out tests for critical requirements, and human review of the test
diff in every pull request. The README and the paper state that mutation testing does not cover
this failure.

## Alternatives considered
- Rely on the mutation gate alone: it promises more than the technique measures.
- A CI check that detects hardcoding: no deterministic detector is known, and a heuristic would
  add an opaque component to monitor.
- Held-out tests for everything: costly; kept optional for critical requirements.

## Consequences
The rule is advice to the agent (hooks cannot judge intent), so what catches a violation is the
generated inputs and the reviewer. Good properties are harder to write than examples, and an
agent that writes both code and properties can make them trivial. Revisit if the evaluation
protocol shows hardcoded implementations still reaching main.
