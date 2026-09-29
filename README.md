# Anti-Fragile Agentic Workflow (AFAW)

An anti-fragile, multi-agent workflow framework designed for resilient, adaptive AI-driven software engineering and automation.

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

## Core Principles

- **Deterministic Verification**: Every claim is measured. Tests, linters, and type checks run in CI.
- **Context & Task Atomic Deltas**: Code changes require task context deltas (`context/tasks/task_NNN_context.json`) listing all touched files.
- **Generated State Isolation**: Aggregated state (`state/pending.json` and `context/global/lastcontext.json`) is never modified by hand; it is compiled automatically by CI.
- **Strict Layer Isolation**: Clear boundaries between adaptors, services, domain logic, and external tool execution.
