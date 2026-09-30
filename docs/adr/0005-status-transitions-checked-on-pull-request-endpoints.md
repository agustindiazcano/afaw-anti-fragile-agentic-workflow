---
status: proposed
date: 2026-09-30
tags: [state, tasks]
---
# The status lifecycle is checked on the endpoints a pull request shows

## Context
A first version of `check_task_files.py` required every step of the lifecycle (pending, then
in_progress, then done). A pull request only shows the status at its base and at its head, so
the most common case, a task done in one pull request, arrived as pending to done and was
rejected.

## Decision
Any open status (`backlog`, `pending`, `in_progress`) may reach `done` in one pull request, a
new task may arrive already `done`, and `done` and `cancelled` are final. A task file is never
deleted. A pull request may not change both the owner and the status of a task, so an agent
cannot hand a task to the human to close it without branch work.

## Alternatives considered
- Check every intermediate step by reading each commit of the branch: squash merges and
  rebases rewrite those commits, so the check would depend on the merge strategy.
- Require a separate pull request to claim a task: doubles the pull requests per task.

## Consequences
The `in_progress` status is visible on `main` only for tasks that span several pull requests.
The dashboard's in-progress column shows those tasks and any task whose branch has activity.
