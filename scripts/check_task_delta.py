"""Fail a PR that changes code without a valid context delta.

Rule (CLAUDE.md, section 1): finishing a task means writing
context/tasks/task_NNN_context.json. The delta must be valid against its schema, its task must
exist in state/tasks/, and every changed code file must be listed in its files_touched.
A PR that changes no code (docs only) always passes.

Run in CI: python -m scripts.check_task_delta --base origin/main
Exit codes: 0 ok, 1 problems found (listed on stderr), 2 could not run (details on stderr).
"""

from __future__ import annotations

import argparse
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
            "(context/tasks/task_NNN_context.json, see CLAUDE.md section 1)."
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
    return problems


def main(argv: list[str] | None = None) -> int:
    """Check the current branch against --base and report every problem found."""
    parser = argparse.ArgumentParser(description="Require a context delta when code changes.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="git ref to compare with, e.g. origin/main")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        problems = find_problems(changed_files(args.base, root), root)
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
