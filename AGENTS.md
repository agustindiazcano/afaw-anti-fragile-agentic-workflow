# Instructions for coding agents

Rules reusable in any project. `AGENTS.md` is the single source; `CLAUDE.md` imports it.

## 0. Language: always English
> **ALWAYS RESPOND IN ENGLISH.** Every reply, explanation, commit message, PR title/description and code comment is written in English, regardless of the language the user writes in.

## 1. Session start, tasks and context
1. **In the first message, always ask the human for `ROLE:`** (which role this agent has in the project).
2. At session start the hook builds the derived views from `origin/main` and injects `LASTCONTEXT.md` and `PENDING.md`. Without the hook, run `git fetch` and `python -m scripts.build_state --ref origin/main`, then read, in order: `README.md`, the reference documents listed in `LASTCONTEXT.md`, `build/state/context/global/LASTCONTEXT.md`, `build/state/context/roles/<role>/LASTCONTEXT.md`, and the ADRs and gotchas the task needs.
3. **An agent writes only two state files:** its task file `state/tasks/task_NNN.json` (declared values: id, title, role, type, status, owner, priority, difficulty, blocked_by, branch) and its delta `context/tasks/task_NNN_context.json` (`summary`, `next`, `files_touched`). Timestamps, CI results and the traffic light are measured, never declared; CI rejects a task file that contains them.
4. **Status lifecycle:** `backlog`, `pending`, `in_progress`, `done`, `cancelled`. Any open status may reach `done` in one pull request; `done` and `cancelled` are final. Task files are never deleted: set `cancelled`. A new task takes the next free id; CI rejects an id that already exists on `origin/main`.
5. **Owner:** `agent` by default; `human` for actions only the human can take (approve a PR, rotate a key, change a repository setting). A human task needs no branch. A pull request never changes both the owner and the status of a task.
6. **When finishing a task:** write `summary` (what was done) and `next` (what is left) in the delta; fill `files_touched` with `python -m scripts.check_task_delta --base origin/main --write task_NNN`, never by hand; update the affected documentation; record any decision as an ADR (section 20). Commit these documents in a separate `docs(scope): ...` commit, documents only, so it does not launch tests (section 11).
7. **Generated files are never edited:** everything under `build/` (the `LASTCONTEXT.md` files, pending, history, metrics, the dashboard) is rebuilt by `scripts/build_state.py` and never committed.

## 2. Role and way of working
1. Act as a senior engineer and QA specialist: SOLID, Clean Architecture, small, modular, typed, testable, production-ready code.
2. **Never claim a result that was not measured.**
3. **Strict TDD (Red → Green → Refactor):** write the test first and confirm it fails; then the minimum code to make it pass; refactor with the test green.
4. Never present a function or endpoint as finished without its test.
5. For a bug, first write a test that reproduces it (it must fail) and only then fix it.
6. Tests for detectors or estimators use synthetic sequences with known noise and a known change point.
7. **Parsimony:** implement the simplest model or detector that solves the problem; use a heavier one only with evidence that the simple one fails.
8. Do not add opaque components (e.g. a trained classifier) that then have to be monitored.
9. Consult the current documentation of a library before implementing with it; do not do it from memory.

## 3. Project status report
When the project status is requested, build the views from `origin/main` (`git fetch`, then `python -m scripts.build_state --ref origin/main`) and answer from `build/state/pending.json`, never from the working branch or by reading `state/tasks/` one by one. Answer with a table of open tasks:

| Task | Status | Light | Difficulty (1-5, estimate) | Priority (1-5) |
|---|---|---|---|---|
| Example: migrate the worker to async | in_progress | 🟡 no activity for 4 days | 3 | 1 |

1. **The light is derived by rules, never judged by the agent:** 🔴 a blocker is not done, or CI fails on the latest commit of the task's branch · 🟡 in progress with no commit or CI run for more than `stale_days` · 🟢 otherwise · no data when nothing was measured. Copy the light and its reason from the view.
2. **Priority:** 1 = most urgent, 5 = least urgent. Sort by ascending priority.
3. **Difficulty** is an estimate and is labelled as one.
4. One row per task; no paragraphs inside the table. For a 🔴 task, give on a separate line the blocker and what is needed to unblock it.
5. Only real tasks; do not invent tasks to fill the table.

## 4. Code standards
1. Type hints on every public function, with a short docstring (what it measures/does and which file it writes).
2. `mypy --strict`; no `Any` unless justified in an inline comment.
3. Every function that performs I/O is `async`, and there is never blocking I/O inside `async` (use `asyncio.sleep`, `httpx.AsyncClient`, async drivers).
4. Every blocking subprocess call has a timeout; long-running processes are terminated or awaited; temporary working directories are deleted.
5. Configuration from environment variables with `pydantic-settings`; never hardcode secrets or connection strings.
6. Structured logging (`structlog`); never `print()`.
7. PEP 8 with a maximum line length of 100 characters.
8. No `from module import *`.
9. Do not use a generic `except Exception` without logging or re-raising the specific error.
10. No `TODO` comments: implement it or ask.
11. Do not add new dependencies without justifying them; prefer the standard library.
12. Single-purpose functions; one file, one responsibility; split a file before it exceeds ~600 lines.
13. Every module has its own test file (`pytest` + `pytest-asyncio`).
14. Tests run against their own database whose name ends in `_test`; the suite refuses to start otherwise.
15. All code lives in `src/` with absolute imports, so it works the same locally, in tests and in Docker.
16. Sample or demo data is loaded with separate scripts or jobs, never inside a migration.

## 5. Architecture
1. **The AI decides, the engine measures:** every number (coverage, metrics, risk) comes from a deterministic function, never from an estimate, rounding or extrapolation.
2. **Determinism:** same input, same numbers. Two identical runs that differ are a bug.
3. **Layer separation:** never mix database, routing and AI logic in the same file. The core has no web/CLI/protocol code; the adapters (CLI, server, MCP) are thin and delegate.
4. Repositories only access the database; external HTTP calls go in services or agents.
5. **The AI layer never imports models, repositories or database connections:** all data access goes through tools (MCP).
6. **Mandatory idempotency:** every request carries a unique `request_id`; it is checked before invoking the LLM and, if it exists, the cached result is returned.
7. **Retries with exponential backoff** and a configurable limit on every external call; when exhausted, NACK to requeue or send to dead-letter.
8. **LLM provider factory:** switch provider with an environment variable, without touching business logic. A `mock` provider for all roles avoids spending in tests and load runs.
9. Scoring/rule modules are pure functions of their inputs, with no access to the database or tools, so that every firing is reproducible and auditable.
10. Log every rule firing (id, inputs, belief degree, final verdict): it is what makes the layer auditable, and it is not omitted to save writes.
11. Observability and drift detection never block or take part in the critical path: they consume already persisted logs and their failure does not affect transactions.
12. Explicitly define each component as fail-open or fail-closed: guards and judges fail closed; context retrieval and tracing fail open. A missing configuration value in a security check fails closed.
13. **Outputs as a contract:** functions return a dict and write JSON to an output folder; subagents communicate through files, not shared memory.
14. **Compact responses:** summaries by default, full data only on request (everything stays in the agent's context and is resent every turn).
15. Do not print to stdout in stdio servers: it is the protocol channel; use stderr or return values.
16. A read-only internal frontend consumes only GET endpoints and never connects directly to the database or to internal services.
17. Choose the transport deliberately and document it; a global change of transport is discussed first, and an alternative is added as an additional option.
18. **The source code is the reference:** when writing tests only `tests/` is edited. If a new test fails against the original code, the test is wrong unless there is evidence of a real bug; in that case `xfail(reason="possible bug: ...")`, never fix the source code to make it pass.
19. Work on temporary copies, never in place, when the target repo is the basis of the documented metrics.

## 6. Agents and LLMs
1. **The LLM never executes tools with side effects:** only deterministic code does, and every write tool is idempotent by `request_id`.
2. **Never trust the LLM's output:** revalidate it on the server with strict Pydantic schemas (`extra="forbid"`) and business limits.
3. The user-facing agent has minimum privilege: no access to the database, the knowledge table or the tool server. It only proposes a structured intent and, if it cannot map the message, asks instead of guessing a field.
4. A prompt injection/jailbreak filter before the message reaches the agent, which fails fast.
5. Feedback to the user exposes an objective, auditable verdict, never a judge's raw justification, which could leak internal reasoning or business rules. The agent words it but never reinterprets or overrides it.
6. Catch any exception in an agent's tool dispatch and return it to the model as an error result: one bad call must not bring down the whole process.

## 7. Security
1. Authenticate every tool call with a bearer token: the server stores only its SHA-256 hash, compares it in constant time and derives `client_id` from the token, never from a client header.
2. Per-tool authorization with a server-side allowlist; nothing in the prompt or in retrieved documents can widen access.
3. Rate limiting per client and tool, computed from the audit table so it holds across replicas without Redis.
4. Audit log of every invocation, including denied ones, with PII masked; if the audit write fails, the tool is not executed.
5. Mask PII in trace exports (pseudonymize user ids, redact emails and long numbers); every new PII field is added with its test before being traced.
6. One service account per service, with access per secret and never at project level.
7. Values that Terraform does not generate are loaded by hand, not through Terraform variables, so they do not end up in the state.
8. Normalize secrets (`.strip()`) on both sides of a comparison; beware of newlines in secrets.
9. Document exposure analyses (e.g. abuse of a public API) and do not implement a defense without the user's approval.
10. Persistence is opt-in and never public on routes that accept arbitrary input; do not store rounded numbers.

## 8. Concurrency and messaging
1. Pessimistic locking (`SELECT ... FOR UPDATE`) plus a `UniqueConstraint` on the id to prevent double processing.
2. A recovery sweeper (`FOR UPDATE SKIP LOCKED`) requeues what a crashed worker left half done.
3. Publish messages as persistent on durable queues: a transient message is lost when the broker restarts.
4. Safe ack/nack (log and continue if the channel closed) and reconnection with retry, instead of dying.
5. Long-lived consumers use `restart: unless-stopped` and wait for the broker themselves; normal services use a bounded restart as a defense.
6. Close the database transaction before long external calls (MCP, LLM).
7. Use `clock_timestamp()` and not `now()` for audit timestamps: `now()` reflects the start of a long transaction and distorts latencies.
8. In clients with a timeout, open a new session per attempt and do not reuse it across retries.
9. **In-memory state + multiple instances = bug:** locks and rate limiters must be durable (database) if the service scales horizontally.

## 9. Observability and traces
1. One trace per transaction, with an id derived from the `request_id`, and typed, nested observations.
2. Observation names are an API: stable, verb first, low cardinality; ids and models go in metadata. Renaming is a breaking change.
3. Tracing is fail-safe: it turns off without keys and its failures are logged without changing the result or the ACK/NACK.
4. Tests never send traces: tracing is disabled in the suite and an in-memory exporter is used when asserting on spans. If the test depends on callbacks, use real fake models and not `AsyncMock`.
5. Verify against a real trace after changing the instrumentation.

## 10. Evaluating models and judges
1. Evaluate the production code, never a pasted copy of the prompt.
2. The labels of the cases are decided by the user: new cases stay pending until the user reviews them.
3. Report false approvals first: they are the dangerous error and accuracy alone hides them.
4. Keep context retrieval fixed in evaluations.
5. Real runs cost money and time: use the mock provider to test the flow and pass up-to-date prices with a date.
6. Asymmetric judges from different model families; the tie-break uses a different model from the first judge's to give an independent opinion.
7. LLM verdicts vary between runs: do not repeat the vote to "correct", and cover that gap with deterministic checks.

## 11. Code tests
1. **Two tiers.** Locally, run only the test being written, one test or one test file at a time, to see red and green; this tier finishes in seconds and needs no external service. Everything else runs in CI: the full suite, integration and end-to-end tests, linters, type-check, mutation testing and builds.
2. **A local red is a claim; CI measures it:** the red-first check (`python -m scripts.red_check --base origin/main`) runs the tests a pull request adds against the code before the change and requires each to fail. A task of type `tests-only` or `refactor` skips it; a single test that documents behavior the code already has is declared with `@pytest.mark.characterization(reason="...")`. Both declarations are printed for the reviewer. A test that did not run on the old code fails the check; it never counts as passing.
3. CI jobs are parallelized whenever possible; they are not queued.
4. Changes in the back end launch only the back-end tests; changes in the front end, only the front-end ones.
5. Document changes do not launch tests: only what contains code.
6. Use path filters (`paths`/`paths-ignore`) in the workflows so that each job runs only when its files change.
7. Load and chaos tests (Locust, killing workers, restarting the broker) run in the cloud (manual or scheduled workflow), never locally, and do not run on every PR because of their cost and duration.

## 12. Code fragility and coverage (mutation testing with AST)
1. To measure fragility, **AST** mutation is used: the code is intentionally altered (mutants) and the tests are launched again. If the tests still pass, no assertion depends on that line.
2. Surviving mutants are fixed by writing or improving tests, and mutation is launched again, in a loop, until the required score is met.
3. **Mutation runs only on new or modified files**, never on files that did not change, **in parallel in CI**.
4. Validate the baseline before mutating: the suite must pass without modifying the code, or every mutant would count as "killed" and a false 100% would result.
5. **Equivalent mutants are accepted only by the human.** The agent may propose a survivor as equivalent, with its reason, in the pull request; it never writes `state/equivalent_mutants.json` (a hook denies it) and never covers the survivor with an artificial test. Each accepted entry is bound to the file's SHA-256 and expires when the file changes.
6. **Mandatory in critical modules** (money, security, concurrency, public contracts). In the rest it is optional and each project decides. A mandatory file below the minimum score blocks the PR. The gate uses K / (N − E_human) and reports the raw score K / N next to it: `python -m scripts.mutation_gate --results <engine output> --required <files>`.
7. The critical folders and the minimum score are defined in `state/config.json` (`mutation_critical_paths`, `mutation_min_score`). `python -m scripts.mutation_targets --base origin/main` lists the mandatory and optional files among the modified ones. The mutation engine and its CI job are specific to each project; they call these two scripts.

## 13. Verification
1. Verify after any engine change against documented baseline values, in CI.
2. **A script that says PASS does not prove it measured the right thing:** combine internal consistency (two runs agree) with a known external value.
3. **Fail loudly, do not fabricate:** if a check could not run (missing dependency, credentials), return a real error and never an empty result that looks like a pass.
4. **Fail fast:** validate credentials and configuration before spending minutes of compute.
5. Never leave fixtures or verification reference files inside the project after using them.
6. Validate with real end-to-end cases in the deployed environment, not only with tests.

## 14. Debugging, load and chaos
1. On a failure between containers, isolate the transport from the application: write the minimal script that exercises only that connection and run it with `docker exec` inside the failing container.
2. If the script passes, the bug is in the app's control flow or exception handling, not in Docker, DNS or the network.
3. **A missing dependency ≠ a missing config:** both look like an opaque `500`; check the server traceback before assuming.
4. Document postmortems.
5. Validate with real load (Locust) and with chaos: kill workers, restart the broker and verify invariants in SQL (zero duplicates, zero lost, nothing stuck).
6. Measure scaling by pausing the workers (`docker pause`), not with `stop`/`start`.
7. Watch out for heavy healthchecks: they can keep an idle broker at high CPU.

## 15. Environment and dependencies
1. **Never call `subprocess.run(["pytest", ...])` with a "bare" command name:** use `[sys.executable, "-m", ...]` to pin the interpreter and not depend on the ambient PATH.
2. Parallel checkouts/worktrees: a script installed in editable mode may point to another checkout; verify with `pip show` before trusting a run.
3. Pin exact versions of coupled packages (e.g. fastapi/starlette) and reinstall clean if they get out of sync.
4. Document environment variables in a table with description and default value.

## 16. Infrastructure and deployment
1. One Docker image per service, with production dependencies only and a non-root user.
2. Tag images with the commit, never with `latest`.
3. All infrastructure as code (Terraform) with versioned state.
4. Scripts to turn the demo environment off and on, to control costs.
5. Update the infrastructure documentation in the same PR as any infrastructure change.
6. Do not change broker or provider without confirming, and record each decision as an ADR (section 20).

## 17. When to pause and confirm
1. Confirm with the user before touching:
   - DELETE or UPDATE without WHERE.
   - Migrations that drop columns or tables.
   - The ACK/NACK logic.
   - Public tools (renaming or removing) or write guards.
   - Thresholds of a security guard (lowering them) or measurement operators/thresholds without re-measuring and updating the docs in the same change.
   - Fixtures that affect all documented numbers.
   - `.env` and secrets.
   - Model, router or tool-registry files (list the impact before deleting or moving).
   - Published numbers without a real measurement behind them.
2. Before a migration, verify the current revision (`alembic current`) and confirm the target with the user; this applies equally to the cloud database.
3. Hard-deny hooks protect what only the human may change: `PENDING.md` can be edited but never deleted or emptied; `state/equivalent_mutants.json` is never written by an agent; nothing under `build/` is edited; nothing is pushed to `main`.
4. When refusing an action, always state the correct alternative in the same reply.

## 18. Linters, branches, commits and PRs
### Linters
1. Linters and type-check (`ruff`, `mypy`, and the front-end ones) may run locally on the diff for feedback in seconds; CI runs them again and its result is the one that counts.
2. They are launched only on what was modified (the diff), and only the linter for the side that changed (back end or front end).
3. They do not run on document-only changes.

### Branches and commits
4. GitHub Flow: an always-deployable `main` and short branches. **Step 0, always:** before modifying any file, check the branch and the working tree (`git status` and `git branch`), because multiple agents are working on the project. Never start working on the current branch by default: first create a new, isolated branch for the task.
5. **The branch name represents the task** (`feat/`, `fix/`, `chore/` + a clear description, e.g. `feat/fuzzy-scoring-layer`).
6. **Atomic task system:** one feature = one commit with a representative name.
7. Conventional Commits: `type(scope): description`.

### Pull requests
8. **Never commit or push to `main`.**
9. **Never merge without an explicit human directive.**
10. **The human always approves the PR manually.**
11. **The agent asks whether to create the PR, unless the human already asked for it in the instruction.**
12. When creating a PR, deliver the title and a comment with the description in the reply, and also write them in the PR if the environment allows it.
13. The checks run in CI (`checks.yml`: task files, delta, red-first, ADRs and links, derived views; `scripts-ci.yml`: lint, types, tests); paste the link to the run in the PR, not a local output.
14. If a PR changes a measured number, update README/docs in the same PR.
15. After the merge that the human decides, delete the branch.

## 19. Token budget
1. Short replies: tables and lists, without repeating tool output.
2. Do not read output JSON, images or fixtures unless the task requires it; read only the part of a file that is needed and do not re-read what was just written.
3. At most 3 subagents per round, passing each one only its file and its data, not the conversation history.

## 20. Project knowledge: decisions and gotchas
1. **State files say what; prose says why.** Knowledge is recorded once, as markdown, never duplicated in JSON.
2. **A decision that constrains later work is an ADR** in `docs/adr/NNNN-slug.md` (template: `docs/templates/adr.md`): Context, Decision, Alternatives considered, Consequences. Record it in the same pull request that introduces it, with `status: proposed`; the human sets `accepted`.
3. **A trap others will hit is a gotcha** in `docs/gotchas/NNNN-slug.md` (template: `docs/templates/gotcha.md`): Symptom, What to do.
4. **Prefer a mechanism to a gotcha.** If a script, a configuration default, a test or a hook can prevent the trap, propose that mechanism and mark the gotcha `promoted` with `promoted_to`. A rule enforced by a mechanism no longer depends on being read.
5. A record leaves `LASTCONTEXT.md` only for an explicit reason, never for its age: an ADR is `superseded` (by one that lists it in `supersedes`) or `deprecated`; a gotcha is `resolved` (with `resolved_by`) or `promoted`. Never delete a record.
6. When the active records exceed `knowledge_budget` (in `state/config.json`), the dashboard and `LASTCONTEXT.md` say a review is due. The human prunes in a pull request; an agent never summarizes or deletes records on its own.
