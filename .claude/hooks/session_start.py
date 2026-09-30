#!/usr/bin/env python3
"""
session_start.py

SessionStart hook: builds the derived views from origin/main and injects the
generated LASTCONTEXT.md and the human's PENDING.md into the session, so the
agent starts from the current state without being told to read them.

The views are rebuilt at every session start; a stale copy is never injected.
If the build fails, the agent receives the error instead (fail loudly, AGENTS.md
section 13). The hook does not fetch: it reads origin/main as last fetched, and
says so.

AFAW_BUILD_COMMAND overrides the build command (used by the tests).

Matcher (see .claude/settings.json): SessionStart (no matcher, fires always)
No external dependencies; runs on any Python 3.11+.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

VIEW = Path("build/state/context/global/LASTCONTEXT.md")
BUILD_TIMEOUT_SECONDS = 60


def build(project: Path) -> str | None:
    """Rebuild the views; return an error message, or None on success."""
    override = os.environ.get("AFAW_BUILD_COMMAND")
    command = (
        shlex.split(override)
        if override
        else [sys.executable, "-m", "scripts.build_state", "--ref", "origin/main", "--out",
              "build/state"]
    )
    (project / VIEW).unlink(missing_ok=True)
    try:
        result = subprocess.run(
            command, cwd=project, capture_output=True, text=True, timeout=BUILD_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if result.returncode != 0:
        return (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
    return None


def main() -> None:
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    sections = []

    error = build(project)
    view = project / VIEW
    if error is None and view.is_file():
        sections.append(
            "## LASTCONTEXT.md (generated from origin/main)\n\n"
            "Built from origin/main as last fetched; run `git fetch` and "
            "`python -m scripts.build_state` for a newer state.\n\n"
            + view.read_text(encoding="utf-8").strip()
        )
    else:
        sections.append(
            "## LASTCONTEXT.md\n\nThe session could not build the derived views, so no "
            "last-context is shown. Fix the source state before relying on it:\n\n"
            + (error or "the build produced no LASTCONTEXT.md")
        )

    pending = project / "PENDING.md"
    if pending.is_file() and pending.read_text(encoding="utf-8").strip():
        sections.append("## PENDING.md\n\n" + pending.read_text(encoding="utf-8").strip())

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(sections),
        }
    }
    sys.stdout.write(json.dumps(output) + "\n")


if __name__ == "__main__":
    main()
