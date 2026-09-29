# Anti-Fragile Agentic Workflow (AFAW)

An anti-fragile, multi-agent workflow framework designed for resilient, adaptive AI-driven software engineering and automation.

---

## Index

1. **[System Overview](#system-overview)**: High-level multi-agent topology, branch isolation, cloud CI, and human sign-off.
2. **[Directory Structure](#directory-structure)**: Repository layout, modular agent skills, state definitions, and tooling.
3. **[Core Principles](#core-principles)**: Deterministic verification, fast local feedback, atomic context deltas, and defense-in-depth.
4. **[Workflow & Architecture Diagrams](#workflow--architecture-diagrams)**:
   - 4.1 **[Task Lifecycle](#1-task-lifecycle)**: 12-step lifecycle from session start (`ROL:` consultation) to merge and branch deletion.
   - 4.2 **[State & Context Management](#2-state--context-management)**: Source of truth in atomic task files (`state/tasks/`), agent context deltas, and automated CI consolidation.
   - 4.3 **[CI/CD Pipeline](#3-cicd-pipeline)**: Path-filtered parallel jobs and docs-only fast-paths.
   - 4.4 **[Mutation Testing on Diffs](#4-mutation-testing-on-diffs)**: AST mutant injection, survivor elimination, and critical threshold enforcement.
   - 4.5 **[Control Layers](#5-control-layers)**: Defense-in-depth from guidelines to branch protection.

---

## System Overview

High-level multi-agent topology, branch isolation, cloud CI, and human sign-off:

![AFAW Overview](docs/img/01-overview.svg)

---

## Directory Structure

```text
afaw-anti-fragile-agentic-workflow/
├── .agents/                      # Agent skill definitions and instructions
│   └── skills/                   # Modular skills (add-mcp-tool, db-migration, tests, etc.)
├── .claude/                      # Claude Code skill configurations and references
│   └── skills/                   # Claude-compatible skills and eval references
├── .github/                      # CI/CD Workflows
│   └── workflows/
│       ├── consolidate-state.yml # Merges task deltas into pending.json on main
│       ├── scripts-ci.yml        # Runs linting, type checks, and tests on CI
│       └── task-delta-check.yml  # Enforces context deltas for any PR touching code
├── context/                      # Agent and project context system
│   ├── global/
│   │   └── lastcontext.json      # Aggregated global project context (CI generated)
│   ├── roles/                    # Role-specific contexts
│   │   ├── backend/              # Backend agent context
│   │   └── frontend/             # Frontend agent context
│   └── tasks/                    # Task-level delta contexts produced by agents
│       └── task_001_context.json # Context delta for specific task
├── dashboard/                    # Monitoring, metrics, and dashboard assets
├── docs/                         # Architecture documentation and guides
│   ├── diagrams/                 # Graphviz .dot diagram sources
│   ├── img/                      # Rendered diagram SVG and PNG assets
│   └── diagrams.md               # Diagram index and markdown references
├── scripts/                      # Core workflow and CI automation scripts
│   ├── check_task_delta.py       # Validates task deltas against code diff
│   ├── merge_state.py            # Regenerates pending.json and lastcontext.json
│   ├── mutation_targets.py       # Identifies targets for mutation testing
│   ├── project_config.py         # Project configuration loader
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
│   ├── config.json               # State configuration and code boundary prefixes
│   └── pending.json              # Aggregated task summary (CI generated)
├── tests/                        # Automated test suites
│   ├── back/                     # Backend tests
│   ├── front/                    # Frontend tests
│   └── tooling/                  # Tests for workflow automation scripts
├── AGENTS.md                     # Universal agent instructions and engineering rules
├── CLAUDE.md                     # Claude agent instructions (kept identical to AGENTS.md)
├── LICENSE                       # Project license
├── pyproject.toml                # Tooling config (ruff, mypy, pytest)
└── README.md                     # Project documentation and structure overview
```

---

## Core Principles

- **Deterministic Verification**: Every metric is measured, not estimated. Tests, linters, and type checks enforce standards.
- **Fast Local Feedback & CI Scaling**: Fast checks (linters, type checks, diff tests) run in seconds locally; heavy suites (AST mutation, full integration, load) run parallelized in CI.
- **Context & Task Atomic Deltas**: Code changes require task context deltas (`context/tasks/task_NNN_context.json`) listing all touched files.
- **Generated State Isolation**: Aggregated state (`state/pending.json` and `context/global/lastcontext.json`) is never modified manually; it is compiled automatically by CI.
- **Strict Layer Isolation**: Clear separation between adaptors, services, domain logic, and external tool execution.
- **Human-in-the-Loop**: PRs require explicit human review and approval before merging into `main`.

---

## Workflow & Architecture Diagrams

### 1. Task Lifecycle
Each task progresses through an isolated branch workflow with deterministic checks and explicit sign-offs:

![Life of a task](docs/img/02-task-lifecycle.svg)

### 2. State & Context Management
Agents write only atomic task files and context deltas. Shared state is generated deterministically by CI:

![State and Context](docs/img/03-state-and-context.svg)

### 3. CI/CD Pipeline
Path-based triggers route changes to parallel jobs, avoiding redundant runs for docs-only changes:

![CI Pipeline](docs/img/04-ci-pipeline.svg)

### 4. Mutation Testing on Diffs
Measures fragility by mutating modified code with AST to guarantee test suite coverage and efficacy:

![Mutation Testing](docs/img/05-mutation-testing.svg)

### 5. Control Layers
Defense in depth from prompt instructions down to branch protection rules:

![Control Layers](docs/img/06-control-layers.svg)
