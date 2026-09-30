"""Tests for the Claude Code hooks: the safety guard and the session-start context."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / ".claude" / "hooks" / "safety_guard.py"
SESSION = REPO_ROOT / ".claude" / "hooks" / "session_start.py"


def guard(tool: str, **tool_input: str) -> tuple[str, str]:
    """Run the guard on one tool call and return (decision, reason)."""
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, timeout=30
    )
    out = json.loads(result.stdout)
    if not out:
        return "allow", ""
    decision = out["hookSpecificOutput"]
    return decision["permissionDecision"], decision["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        "rm PENDING.md",
        "git rm PENDING.md",
        "echo '' > PENDING.md",
        "git push origin main",
        "git push origin HEAD:main",
        "git push -u origin main",
        "echo '{}' > state/equivalent_mutants.json",
        "rm build/state/context/global/LASTCONTEXT.md",
    ],
)
def test_hard_denied_commands(command: str) -> None:
    assert guard("Bash", command=command)[0] == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "DELETE FROM orders",
        "psql -c 'DROP TABLE orders'",
        "git push --force origin feat/x",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git restore .",
        "gh pr merge 12",
        "docker compose down -v",
    ],
)
def test_destructive_commands_ask(command: str) -> None:
    assert guard("Bash", command=command)[0] == "ask"


@pytest.mark.characterization(
    reason="the v1.0 guard already allowed ordinary commands; kept as a regression test"
)
@pytest.mark.parametrize(
    "command",
    [
        "git push -u origin feat/maintenance-page",
        "git status",
        "python -m pytest tests/tooling/test_model.py::test_invalid_owner",
        "cat PENDING.md",
        "DELETE FROM orders WHERE id = 3",
    ],
)
def test_ordinary_commands_allowed(command: str) -> None:
    assert guard("Bash", command=command)[0] == "allow"


@pytest.mark.parametrize(
    "path",
    ["state/equivalent_mutants.json", "/repo/build/state/pending.json", "build/facts.json"],
)
def test_agent_cannot_write_human_or_generated_files(path: str) -> None:
    assert guard("Write", file_path=path)[0] == "deny"


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "config/.env.prod",
        "migrations/0003_drop.py",
        "alembic/versions/a1.py",
        ".github/workflows/checks.yml",
        "state/config.json",
        "CODEOWNERS",
    ],
)
def test_protected_files_ask(path: str) -> None:
    assert guard("Edit", file_path=path)[0] == "ask"


@pytest.mark.characterization(
    reason="the v1.0 guard already allowed ordinary files; kept as a regression test"
)
def test_ordinary_file_allowed() -> None:
    assert guard("Edit", file_path="src/back/orders.py")[0] == "allow"


@pytest.mark.characterization(
    reason="the v1.0 guard already ignored invalid payloads; kept as a regression test"
)
def test_unparseable_payload_is_allowed_silently() -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, timeout=30
    )
    assert result.stdout.strip() == "{}"


def _session(project: Path, runner: str) -> dict[str, str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), "AFAW_BUILD_COMMAND": runner}
    result = subprocess.run(
        [sys.executable, str(SESSION)], capture_output=True, text=True, timeout=60, env=env
    )
    context: str = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    return {"context": context}


def test_session_start_injects_generated_lastcontext_and_pending(tmp_path: Path) -> None:
    (tmp_path / "PENDING.md").write_text("# Roadmap\n- ship v1.1\n", encoding="utf-8")
    view = tmp_path / "build/state/context/global/LASTCONTEXT.md"
    runner = (
        f"{sys.executable} -c \"import pathlib; p = pathlib.Path(r'{view}'); "
        "p.parent.mkdir(parents=True, exist_ok=True); p.write_text('# Last context\\nok\\n')\""
    )
    context = _session(tmp_path, runner)["context"]
    assert "## LASTCONTEXT.md (generated from origin/main)" in context
    assert "# Last context\nok" in context
    assert "## PENDING.md" in context and "ship v1.1" in context


def test_session_start_reports_a_failed_build_instead_of_stale_context(tmp_path: Path) -> None:
    stale = tmp_path / "build/state/context/global/LASTCONTEXT.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("# Last context\nSTALE\n", encoding="utf-8")
    runner = f"{sys.executable} -c \"import sys; sys.stderr.write('bad task file'); sys.exit(1)\""
    context = _session(tmp_path, runner)["context"]
    assert "could not build the derived views" in context
    assert "bad task file" in context
    assert "STALE" not in context
