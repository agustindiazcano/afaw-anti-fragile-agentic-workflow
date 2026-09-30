#!/usr/bin/env python3
"""CI check for project knowledge in markdown.

Rejects a pull request whose ADRs or gotchas (docs/adr/, docs/gotchas/) have an
invalid file name, front matter, status or date; lack a required section;
break the supersedes chain; or whose markdown under docs/ (plus README.md and
AGENTS.md) links to a file that does not exist.

It cannot tell whether a decision that should have been recorded is missing:
that is judgement, left to the human review.

Usage (from the repository root, on the pull request's checkout):
    python scripts/check_docs.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.afaw_state.knowledge import broken_links, check_knowledge, parse_doc

TOP_LEVEL_DOCS = ("README.md", "AGENTS.md", "CLAUDE.md")


def tracked_files(root: Path) -> set[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True
    ).stdout
    return set(out.splitlines())


def check(root: Path, existing: set[str]) -> list[str]:
    docs = [
        parse_doc(path, (root / path).read_text(encoding="utf-8"))
        for path in sorted(existing)
        if path.endswith(".md")
        and path.count("/") == 2
        and path.startswith(("docs/adr/", "docs/gotchas/"))
    ]
    errors = check_knowledge(docs)
    markdown = sorted(
        p for p in existing if p.endswith(".md") and (p.startswith("docs/") or p in TOP_LEVEL_DOCS)
    )
    for path in markdown:
        for target in broken_links(path, (root / path).read_text(encoding="utf-8"), existing):
            errors.append(f"{path}: broken link: {target}")
    return errors


def main() -> int:
    root = Path.cwd()
    errors = check(root, tracked_files(root))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
