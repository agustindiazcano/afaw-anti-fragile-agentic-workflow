"""Fail a PR that changes code without a valid context delta.

Rule (AGENTS.md, section 1): finishing a task means writing
context/tasks/task_NNN_context.json. The delta must be valid against its schema, its task must
exist in state/tasks/, and files_touched must equal the set of code files the PR changes: a
missing file and an extra file are both reported, so the field is measured, not declared.
A PR that changes no code (docs only) always passes.

Run in CI: python -m scripts.check_task_delta --base origin/main
Fill a delta: python -m scripts.check_task_delta --base origin/main --write task_NNN
Exit codes: 0 ok, 1 problems found (listed on stderr), 2 could not run (details on stderr).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from scripts.project_config import load_config
from scripts.state_common import StateError, load_json, load_validated

DELTA_PATTERN = re.compile(r"^context/tasks/(task_[0-9]{3,})_context\.json$")
DELTA_SCHEMA_PATH = "state/schemas/context_delta.schema.json"
GIT_TIMEOUT_SECONDS = 60


def changed_files(base: str, root: Path) -> list[str]:
    """List files added, copied, modified or renamed on HEAD since base (deletions excluded)."""
    command = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise StateError(f"could not list changed files against {base!r}: {exc}") from exc
    return [line for line in result.stdout.splitlines() if line]


def find_problems(changed: list[str], root: Path) -> list[str]:
    """Return what is wrong with the PR's context deltas; an empty list means it may pass."""
    config = load_config(root)
    code = [path for path in changed if config.is_code(path)]
    if not code:
        return []
    delta_paths = [path for path in changed if DELTA_PATTERN.match(path)]
    if not delta_paths:
        return [
            "Code changed but the PR has no context delta "
            "(context/tasks/task_NNN_context.json, see AGENTS.md section 1)."
        ]
    schema = load_json(root / DELTA_SCHEMA_PATH)
    problems: list[str] = []
    listed: set[str] = set()
    for relative in delta_paths:
        match = DELTA_PATTERN.match(relative)
        assert match is not None  # delta_paths only holds paths that matched
        task_id = match.group(1)
        try:
            delta = load_validated(root / relative, schema)
        except StateError as exc:
            problems.append(str(exc))
            continue
        if delta["task_id"] != task_id:
            problems.append(f"{relative}: task_id is {delta['task_id']!r}, file says {task_id!r}")
        if not (root / "state" / "tasks" / f"{task_id}.json").exists():
            problems.append(f"{relative}: state/tasks/{task_id}.json does not exist")
        listed.update(delta["files_touched"])
    missing = sorted(set(code) - listed)
    if missing:
        problems.append(
            "Changed code files not listed in any delta's files_touched: " + ", ".join(missing)
        )
    extra = sorted(listed - set(code))
    if extra:
        problems.append(
            "files_touched lists files not changed by this pull request: " + ", ".join(extra)
        )
    return problems


def write_files_touched(task_id: str, changed: list[str], root: Path) -> Path:
    """Set files_touched of the task's delta to the changed code files; create the delta if needed.

    The agent runs this instead of writing the list by hand, so the field is measured.
    Writes context/tasks/<task_id>_context.json and returns its path.
    """
    config = load_config(root)
    path = root / "context" / "tasks" / f"{task_id}_context.json"
    delta = load_json(path) if path.exists() else {"task_id": task_id}
    delta["files_touched"] = sorted(p for p in changed if config.is_code(p))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(delta, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """Check the current branch against --base, or fill a delta's files_touched with --write."""
    parser = argparse.ArgumentParser(description="Require a context delta when code changes.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="git ref to compare with, e.g. origin/main")
    parser.add_argument(
        "--write", metavar="TASK_ID", help="fill files_touched of this task's delta from the diff"
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        changed = changed_files(args.base, root)
        if args.write:
            path = write_files_touched(args.write, changed, root)
            sys.stdout.write(f"OK: wrote files_touched to {path}\n")
            return 0
        problems = find_problems(changed, root)
    except StateError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    for problem in problems:
        sys.stderr.write(f"PROBLEM: {problem}\n")
    if problems:
        return 1
    sys.stdout.write("OK: context delta check passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
