#!/usr/bin/env python3
"""
safety_guard.py

PreToolUse hook: gates destructive or high-risk tool calls before Claude Code
executes them. Reads the hook payload from stdin and writes a
hookSpecificOutput permission decision to stdout.

Matcher (see .claude/settings.json): Bash|PowerShell|Write|Edit

Decisions:
  allow  - proceed (prints {})
  ask    - the human confirms first
  deny   - hard block; the tool never runs

This is a best-effort filter, not a security boundary: a command can be phrased
so that no pattern matches. Branch protection on main is the barrier that does
not depend on the agent (AGENTS.md, section 18).

No external dependencies; runs on any Python 3.11+.
"""

import json
import re
import sys

# ---------------------------------------------------------------------------
# Hard-blocked: never executed.
#   PENDING.md is the human's roadmap: it may be edited, never deleted or emptied.
#   main only changes through a reviewed pull request.
#   state/equivalent_mutants.json is written by the human only (AGENTS.md, section 12).
#   build/ holds generated views; they are rebuilt, never edited.
# ---------------------------------------------------------------------------
DENY_COMMAND_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\b(rm|del|erase)\b[^|&;\n]*PENDING\.md", "Deleting PENDING.md is not allowed."),
    (r"(?i)Remove-Item[^|&;\n]*PENDING\.md", "Deleting PENDING.md is not allowed."),
    (r"(?i)git\s+rm[^|&;\n]*PENDING\.md", "Deleting PENDING.md (even via git rm) is not allowed."),
    (r"(?<!>)>\s*PENDING\.md\b", "Truncating PENDING.md via shell redirection is not allowed."),
    (
        r"git\s+push\b[^|&;\n]*\s(\S*:)?(refs/heads/)?main\b",
        "Pushing to main is not allowed: open a pull request from a task branch.",
    ),
    (
        r"equivalent_mutants\.json",
        "Only the human records equivalent mutants (state/equivalent_mutants.json).",
    ),
    (
        r"(?i)\b(rm|del|mv|cp|tee|sed\s+-i)\b[^|&;\n]*\bbuild/|>\s*\S*\bbuild/",
        "Files under build/ are generated: rebuild them with python -m scripts.build_state.",
    ),
]

# ---------------------------------------------------------------------------
# Destructive intent in a shell command: the human confirms first.
# ---------------------------------------------------------------------------
DESTRUCTIVE_COMMAND_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\b(DELETE|UPDATE)\b(?!.*\bWHERE\b)", "Destructive SQL without a WHERE clause"),
    (r"(?i)\bDROP\s+(TABLE|COLUMN|DATABASE|SCHEMA|INDEX|EXTENSION)\b", "Schema-dropping SQL"),
    (r"alembic\s+downgrade", "Database migration downgrade (potential data loss)"),
    (r"rm\s+(-rf?|--recursive)\s+/", "Recursive deletion from filesystem root"),
    (r"Remove-Item.*-Recurse.*-Force", "Recursive forced deletion (PowerShell)"),
    (r"git\s+push[^|&;]*--force", "Force push to a remote"),
    (r"git\s+reset\s+--hard", "Hard reset (discards uncommitted work)"),
    (r"git\s+clean\s+.*-[a-z]*f", "git clean -f (permanently deletes untracked files)"),
    (r"git\s+restore\s+\.", "git restore . (discards all uncommitted tracked changes)"),
    (r"gh\s+pr\s+merge", "Merging a pull request needs an explicit human directive"),
    (
        r"(echo|printf|Set-Content|Out-File|Add-Content)[^|&;]*\.(env|secrets)\b",
        "Writing to a secrets file",
    ),
    (r"docker\s+compose\s+down\s+.*-v\b", "docker compose down -v (deletes named volumes)"),
]

# ---------------------------------------------------------------------------
# Write/Edit targets.
# ---------------------------------------------------------------------------
DENY_FILE_PATTERNS: list[tuple[str, str]] = [
    (
        r"(^|[/\\])state[/\\]equivalent_mutants\.json$",
        "Only the human records equivalent mutants (AGENTS.md, section 12).",
    ),
    (
        r"(^|[/\\])build[/\\]",
        "Files under build/ are generated: rebuild them with python -m scripts.build_state.",
    ),
]

PROTECTED_FILE_PATTERNS: list[tuple[str, str]] = [
    (r"(^|[/\\])\.env(\.\w+)?$", "Environment/secrets file"),
    (r"(^|[/\\])(migrations|alembic[/\\]versions)[/\\]", "Database migration"),
    (r"(^|[/\\])\.github[/\\]workflows[/\\]", "CI workflow: it decides what is verified"),
    (r"(^|[/\\])state[/\\]config\.json$", "Project thresholds and critical paths"),
    (r"(^|[/\\])CODEOWNERS$", "Review ownership"),
    (r"docker-compose.*\.ya?ml$", "Container orchestration file"),
]


def check_command(command_line: str) -> tuple[str, str]:
    """Decision for a shell command."""
    for pattern, label in DENY_COMMAND_PATTERNS:
        if re.search(pattern, command_line):
            return "deny", label
    for pattern, label in DESTRUCTIVE_COMMAND_PATTERNS:
        if re.search(pattern, command_line):
            return "ask", f"Potentially destructive operation: {label}. Confirm before allowing."
    return "allow", ""


def check_file_write(target_file: str) -> tuple[str, str]:
    """Decision for a Write or Edit on ``target_file``."""
    for pattern, label in DENY_FILE_PATTERNS:
        if re.search(pattern, target_file):
            return "deny", label
    for pattern, label in PROTECTED_FILE_PATTERNS:
        if re.search(pattern, target_file):
            return "ask", f"Protected file targeted: {label}."
    return "allow", ""


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdout.write("{}\n")
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    decision, reason = "allow", ""
    if tool_name in ("Bash", "PowerShell"):
        decision, reason = check_command(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit"):
        decision, reason = check_file_write(tool_input.get("file_path", ""))

    if decision == "allow":
        sys.stdout.write("{}\n")
        return
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(output) + "\n")


if __name__ == "__main__":
    main()
