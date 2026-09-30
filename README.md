# AFAW (Anti-Fragile Agentic Workflow)

**A deterministic, multi-agent methodology for AI-assisted software development.**

Moving from a single AI assistant in your IDE to several autonomous agents working on the same repository tends to create operational chaos: branch collisions, tests that pass by accident (vacuous tests), overwritten context and hallucinated results.

AFAW is a methodological framework and a repository-level boilerplate for governing that chaos. It lets several agents write code in parallel while constraining them with deterministic validation gates.

*Reference rules target a Python backend and can be adapted to other stacks.*

---

## Index

1. **[The Problem](#the-problem)**: Predictable failure modes of multi-agent development.
2. **[Core Principle](#core-principle-the-ai-decides-the-engine-measures)**: The AI proposes, the engine measures.
3. **[Pillars](#pillars)**: Isolation, state as code, TDD, CI verification, mutation testing, human authority.
4. **[Who It Is For](#who-it-is-for)**
5. **[System Overview](#system-overview)**: Multi-agent topology, branch isolation, cloud CI, human sign-off.
6. **[How It Works](#how-it-works)**:
   - 6.1 Isolated state per task
   - 6.2 One task, one branch, atomic commits
   - 6.3 Strict TDD
   - 6.4 Validation in CI, in parallel
   - 6.5 Mutation testing on the diff
   - 6.6 Human in the loop
   - 6.7 Roles
7. **[The Life of a Task](#the-life-of-a-task)**: 12-step lifecycle from `ROL:` consultation to merge and branch deletion.
8. **[Directory Structure](#directory-structure)**: Repository layout, agent skills, state definitions, tooling.
9. **[Getting Started](#getting-started)**: One-time setup for a new repository.
10. **[Daily Workflow](#daily-workflow)**: How to work with the agents once set up.
11. **[Scope and Limits](#scope-and-limits)**
12. **[Rebuilding the Diagrams](#rebuilding-the-diagrams)**
13. **[Citation](#citation)**, **[Author](#author)**, **[License](#license)**

---

## The Problem

Working with several agents on one repo tends to fail in predictable ways:

- Agents start coding on whatever branch is checked out and collide with each other.
- Two agents update the same shared context file (`LASTCONTEXT`, `PENDING`) and produce merge conflicts.
- Agents claim results they never measured, or write tests that pass no matter what.
- Heavy test suites run on the local machine and block the workflow.
- Nothing prevents a push to `main`.

These rules come from real mistakes observed while working with agents.

---

## Core Principle: "The AI decides, the engine measures"

Probabilistic models (LLMs) are not sources of truth. In AFAW the AI proposes and writes code, but its own assessment is never trusted. Every metric (tests, types, coverage, mutation score) comes from deterministic tools run in CI.

---

## Pillars

- **Strict per-task isolation:** one agent, one task, one isolated branch, in its own terminal. Agents do not work on `main` and do not share a working directory.
- **State as code:** global and per-role context is stored in versioned `.json` files. Each agent writes only its own delta and its task file. Aggregated state (`state/pending.json`, `context/**/lastcontext.json`) is never edited manually; CI regenerates it after each merge, which avoids conflicts.
- **Strict TDD:** the failing test comes first, then the minimum code. A bug starts with a test that reproduces it.
- **Deterministic verification in CI:** fast checks (linters, type checks, diff tests) run in seconds locally; heavy suites (AST mutation, full integration, load) run in parallel in the cloud with path filters. With branch protection and required checks, a failing CI blocks the PR.
- **Mutation testing on the diff:** to stop the AI from writing complacent tests that pass without checking anything, the engine injects mutations only into modified files. In critical modules (money, security, concurrency, public contracts), a file below the minimum score blocks the PR; elsewhere it is optional and each project decides.
- **Strict layer isolation:** clear separation between adapters, services, domain logic and external tool execution.
- **Human authority:** the agent creates branches, writes code and proposes Pull Requests. A human approves every PR and decides every merge. These rules are also enforced outside the prompt (branch protection, hooks and CI), because prompt instructions are advice, not guarantees.

---

## Who It Is For

Engineers and teams that want to scale development with several AI agents (Claude Code, Cursor, etc.) with greater verifiability and traceability.

---

## System Overview

![AFAW overview: the human opens one isolated terminal per agent, each agent works on its own branch, CI validates in the cloud, and the human approves every PR before it reaches main. CI also regenerates the shared state through its own PR.](docs/img/01-overview.svg)

*Colors in all diagrams: blue = agent action, amber = human, green = CI or deterministic check, purple = state files, red = blocked.*

---

## How It Works

### 1. Isolated state per task

Agents never edit shared state files. Each agent writes only its own delta (`context/tasks/task_NNN_context.json`) and its task file (`state/tasks/task_NNN.json`). `state/pending.json` and the global/role `lastcontext.json` files are regenerated by CI (`scripts/merge_state.py`), which opens a PR for human approval. CI rejects code changes that come without a valid delta (`scripts/check_task_delta.py`).

![State and context: the agent writes only its delta and task file; CI checks the delta, regenerates the shared state after the merge and opens a state PR that the human approves.](docs/img/03-state-and-context.svg)

### 2. One task, one branch, atomic commits

Before touching any file the agent checks `git status` and `git branch` and creates a new branch named after the task. Conventional Commits, one feature per commit, documentation in its own commit.

### 3. Strict TDD

Test first, confirm it fails, then write the minimum code. Bugs start with a failing reproduction test.

### 4. Validation runs in CI, in parallel

Tests, linters, type checks and builds run in the cloud with path filters, so each job runs only when its files change. Document-only changes trigger nothing.

![CI pipeline: path filters route a push to back-end, front-end and mutation jobs that run in parallel, document-only changes run nothing, and load and chaos tests are separate manual or scheduled workflows.](docs/img/04-ci-pipeline.svg)

### 5. Mutation testing on the diff

Modified files are mutated (AST-based) and the suite is re-run. Surviving mutants are fixed by improving tests. The baseline must pass before mutating, and equivalent mutants are reported instead of covered with artificial tests. It is mandatory in critical modules (money, security, concurrency, public contracts); which paths and what minimum score are defined per project in `state/config.json`.

![Mutation testing flow: validate the baseline, generate mutants in parallel, re-run the tests, fix surviving mutants by improving tests, and block the PR when a mandatory file is below the minimum score.](docs/img/05-mutation-testing.svg)

### 6. Human in the loop

No commits or pushes to `main`, no merges without an explicit human directive, and the human approves every PR. These rules should also be enforced outside the prompt (GitHub branch protection and hooks), since prompt instructions alone are advice, not guarantees.

![Control layers: AGENTS.md is advice, hooks intercept commands, CI checks block failing PRs, branch protection makes the server reject direct pushes to main, and the human approves the PR.](docs/img/06-control-layers.svg)

### 7. Roles

At session start the agent asks for its `ROL:` and reads that role's `LASTCONTEXT` (or the global one if none exists).

---

## The Life of a Task

Each task progresses through an isolated branch workflow with deterministic checks and explicit sign-offs:

![Life of a task in 12 steps: ask for a ROL, read the context, check git status and branch, create a branch, TDD, atomic commit, push and wait for CI, write the delta, ask about the PR, open it with the CI link, human approval, delete the branch.](docs/img/02-task-lifecycle.svg)

---

## Directory Structure

```text
afaw-anti-fragile-agentic-workflow/
├── .agents/                      # Agent skill definitions and instructions
│   └── skills/                   # Modular skills (add-mcp-tool, db-migration, tests, etc.)
├── .claude/                      # Claude Code skill configurations and references
│   └── skills/                   # Claude-compatible skills and eval references
├── .github/                      # CI/CD workflows
│   └── workflows/
│       ├── consolidate-state.yml # Regenerates pending.json and lastcontext.json after merges to main
│       ├── scripts-ci.yml        # Runs linting, type checks, and tests on CI
│       └── task-delta-check.yml  # Enforces context deltas for any PR touching code
├── context/                      # Agent and project context system
│   ├── global/
│   │   └── lastcontext.json      # Aggregated global project context (CI generated)
│   ├── roles/                    # Role-specific contexts
│   │   ├── backend/              # Backend agent context
│   │   └── frontend/             # Frontend agent context
│   └── tasks/                    # Task-level delta contexts produced by agents
│       └── task_001_context.json
├── dashboard/                    # Monitoring, metrics, and dashboard assets
├── docs/                         # Architecture documentation and guides
│   ├── diagrams/                 # Graphviz .dot diagram sources
│   ├── img/                      # Rendered diagrams (.svg for this README, .png elsewhere)
│   └── diagrams.md               # Diagram index and markdown references
├── scripts/                      # Workflow and CI automation scripts
│   ├── build_diagrams.mjs        # Renders docs/diagrams/*.dot into docs/img/
│   ├── check_task_delta.py       # Validates task deltas against the code diff
│   ├── merge_state.py            # Regenerates pending.json and lastcontext.json
│   ├── mutation_targets.py       # Identifies targets for mutation testing
│   ├── project_config.py         # Project configuration loader
│   ├── setup_protection.sh       # Applies branch protection and required checks via gh CLI
│   └── state_common.py           # JSON schema validation and state utilities
├── src/                          # Application source code
│   ├── back/                     # Backend services, routers, and logic
│   └── front/                    # Frontend UI and components
├── state/                        # State machines and task status definitions
│   ├── schemas/                  # JSON Schemas for validating state and deltas
│   │   ├── config.schema.json    # Schema for state/config.json
│   │   ├── context_delta.schema.json # Schema for task context deltas
│   │   └── task.schema.json      # Schema for individual task definitions
│   ├── tasks/                    # Atomic task files (source of truth)
│   │   ├── task_001.json
│   │   ├── task_002.json
│   │   └── task_003.json
│   ├── config.json               # Code boundary prefixes, mutation_critical_paths, mutation_min_score
│   └── pending.json              # Aggregated task summary (CI generated)
├── tests/                        # Automated test suites
│   ├── back/                     # Backend tests
│   ├── front/                    # Frontend tests
│   └── tooling/                  # Tests for workflow automation scripts
├── .env.example                  # Template for local credentials
├── AGENTS.md                     # Universal agent instructions and engineering rules
├── CLAUDE.md                     # Claude agent instructions (kept identical to AGENTS.md, or a symlink)
├── LICENSE                       # Project license
├── package.json                  # Dependencies for the diagram build
├── pyproject.toml                # Tooling config (ruff, mypy, pytest)
└── README.md                     # This file
```

---

## Getting Started

When you create a new repository from this template, GitHub does **not** copy branch protection rules, required checks, or repository secrets. You must configure them in your new repo.

1. **Use the template**: GitHub → **Use this template**, or clone it and re-initialize git.
2. **Configure state limits**: edit `state/config.json` to define your project's code folders, `mutation_critical_paths` and `mutation_min_score`.
3. **Set secrets**: copy `.env.example` to `.env` and set your credentials. Add the required secrets to your GitHub repository settings.
4. **Enforce branch protection**: run `bash scripts/setup_protection.sh` (requires `gh` CLI logged in) to require the CI checks (`lint`, `typecheck`, `tests`, `task-delta`) and block direct pushes to `main`.
5. **Verify CI**: open a test pull request to confirm the automated checks run and pass.
6. **Start working**: open a terminal, invoke your agent, and answer the initial `ROL:` prompt.

---

## Daily Workflow

1. Open one isolated terminal per agent. Start the agent and answer its first question with a `ROL:`.
2. The agent creates its branch, works task by task with TDD, pushes, and reads the CI result.
3. It writes its delta and task file, and asks before opening a PR.
4. You review and approve. CI regenerates the shared state through its own PR.
5. Ask for status at any time: the agent reads only `state/pending.json` from `origin/main` and answers with a table (task, status, difficulty, priority).

---

## Scope and Limits

- The reference rules assume a Python backend (async, `pytest`, `mypy --strict`, Postgres, Terraform). For other stacks, adapt sections 4, 5, 8 and 16 of `AGENTS.md`.
- AFAW has not been validated in a controlled study and makes no claim about speed, cost or defect-rate improvements. Measure your own (time per task, tokens spent, broken tests, escaped bugs) and add them.
- Mutation score measures how well the tests detect changes, not whether the code meets business requirements.
- CI minutes are limited on private repositories.

---

## Rebuilding the Diagrams

The diagrams are generated from the `.dot` files in `docs/diagrams/`. To change one, edit its source and run:

```bash
npm install
node scripts/build_diagrams.mjs
```

This rewrites `docs/img/*.svg` and `docs/img/*.png`.

---

## Citation

**Official DOI:** [10.5281/zenodo.23050310](https://doi.org/10.5281/zenodo.23050310)

## Author

Agustin Diaz-Cano, MS Candidate, Information Systems Engineering (UTN)

## License

MIT