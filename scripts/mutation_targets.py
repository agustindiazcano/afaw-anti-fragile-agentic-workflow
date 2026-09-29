"""List which changed files must, or may, be mutation-tested in a PR.

Mutation testing runs only on new or modified source files (never on tests or docs). Files under
the project's critical folders (state/config.json: mutation_critical_paths) are required and must
reach mutation_min_score; every other changed source file is optional and left to the project.
The mutation engine itself is project-specific and is not part of this boilerplate: its CI job
calls this script to know what to mutate and which threshold to enforce.

Run in CI: python -m scripts.mutation_targets --base origin/main
Prints JSON: {"required": [...], "optional": [...], "min_score": 80.0}
Exit codes: 0 ok, 2 could not run (details on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.check_task_delta import changed_files
from scripts.project_config import ProjectConfig, load_config
from scripts.state_common import Json, StateError


def classify(changed: list[str], config: ProjectConfig) -> Json:
    """Split the changed files into required and optional mutation targets."""
    required = sorted(path for path in changed if config.is_critical(path))
    optional = sorted(
        path for path in changed if config.is_source(path) and not config.is_critical(path)
    )
    return {"required": required, "optional": optional, "min_score": config.mutation_min_score}


def main(argv: list[str] | None = None) -> int:
    """Print the mutation targets of the current branch as JSON."""
    parser = argparse.ArgumentParser(description="List the mutation-testing targets of a PR.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="git ref to compare with, e.g. origin/main")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        config = load_config(root)  # validate the config first: fail fast, before calling git
        result = classify(changed_files(args.base, root), config)
    except StateError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
