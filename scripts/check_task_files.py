"""CI check for the task files a pull request changes.

Rejects a pull request that:
  - writes an invalid task file, or declares a measured value (timestamp, CI result, light);
  - changes a task's status in a way the lifecycle does not allow;
  - changes both the owner and the status of a task (an agent could otherwise hand a task
    to the human to close it without branch work);
  - deletes a task file (the files of done tasks are the project history);
  - names a task file differently from its id, or adds an id that already exists on the
    target branch (two parallel branches picked the same next id);
  - moves an agent's task to in progress or done on a branch other than the pull request's.

Run in CI:
    python -m scripts.check_task_files --base "$(git merge-base origin/main HEAD)" \\
        --head-branch "$GITHUB_HEAD_REF" --target origin/main
Exit codes: 0 ok, 1 problems found (listed on stderr).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.afaw_state.model import check_transition, validate_task
from scripts.afaw_state.source import Runner, git_runner

PREFIX = "state/tasks/"


def _previous(run: Runner, base: str, path: str) -> tuple[str | None, str | None]:
    """Status and owner of a task file at ``base``, or (None, None) if unreadable."""
    try:
        old = json.loads(run(["show", f"{base}:{path}"]))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None, None
    if not isinstance(old, dict):
        return None, None
    return old.get("status"), old.get("owner", "agent")


def _exists_on(run: Runner, ref: str, path: str) -> bool:
    try:
        run(["cat-file", "-e", f"{ref}:{path}"])
    except subprocess.CalledProcessError:
        return False
    return True


def _check_changed(
    path: str,
    task: dict[str, Any],
    old: tuple[str | None, str | None],
    head_branch: str | None,
) -> list[str]:
    """Rules that compare the new task file with its previous version."""
    errors: list[str] = []
    old_status, old_owner = old
    new_status = task.get("status")
    owner = task.get("owner", "agent")
    if old_owner is not None and old_owner != owner and old_status != new_status:
        errors.append(f"{path}: owner and status cannot change in the same pull request")
    if isinstance(new_status, str):
        problem = check_transition(old_status, new_status)
        if problem:
            errors.append(f"{path}: {problem}")
    moved = new_status in {"in_progress", "done"} and new_status != old_status
    if owner == "agent" and head_branch and moved and task.get("branch") != head_branch:
        errors.append(
            f"{path}: branch {task.get('branch')!r} is not this pull request's branch "
            f"{head_branch!r}"
        )
    return errors


def check(
    base: str,
    head_branch: str | None,
    run: Runner,
    read_head: Callable[[str], str],
    target: str | None = None,
) -> list[str]:
    """Every problem in the task files changed between ``base`` and HEAD."""
    errors: list[str] = []
    diff = run(["diff", "--name-status", "--no-renames", base, "HEAD", "--", PREFIX])
    for line in diff.splitlines():
        status, path = line.split("\t", 1)
        if not path.endswith(".json"):
            continue
        if status == "D":
            errors.append(f"{path}: task files are never deleted; set the status to cancelled")
            continue
        try:
            task = json.loads(read_head(path))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: not valid JSON: {exc}")
            continue
        errors.extend(f"{path}: {problem}" for problem in validate_task(task))
        if not isinstance(task, dict):
            continue
        if task.get("id") != Path(path).stem:
            errors.append(f"{path}: id {task.get('id')!r} does not match the file name")
        if status == "A" and target and _exists_on(run, target, path):
            errors.append(
                f"{path}: task id {Path(path).stem} already exists on {target}; "
                "pick the next free id"
            )
        old = _previous(run, base, path) if status == "M" else (None, None)
        errors.extend(_check_changed(path, task, old, head_branch))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Check the task files of the current branch and report every problem."""
    parser = argparse.ArgumentParser(description="Check task files changed by a pull request.")
    parser.add_argument("--base", required=True, help="merge base with the target branch")
    parser.add_argument("--head-branch", help="the pull request's head branch")
    parser.add_argument("--target", help="the branch the PR merges into, e.g. origin/main")
    args = parser.parse_args(argv)
    errors = check(
        args.base,
        args.head_branch,
        git_runner,
        lambda p: Path(p).read_text(encoding="utf-8"),
        args.target,
    )
    for error in errors:
        sys.stderr.write(f"PROBLEM: {error}\n")
    if errors:
        return 1
    sys.stdout.write("OK: task file check passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
