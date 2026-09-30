import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.tooling.helpers import make_task

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}


def run_module(repo: Path, module: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a scripts.* module with this interpreter, from inside the temporary repository."""
    return subprocess.run(
        [sys.executable, "-m", module, *args], cwd=repo, capture_output=True, text=True, env=ENV
    )


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "state/tasks").mkdir(parents=True)
    (tmp_path / "context/tasks").mkdir(parents=True)
    (tmp_path / "state/config.json").write_text(json.dumps({"dashboard": {"stale_days": 2}}))
    (tmp_path / "state/tasks/task_001.json").write_text(
        json.dumps(make_task(status="done", branch="feat/a"))
    )
    (tmp_path / "state/tasks/task_002.json").write_text(json.dumps(make_task("task_002")))
    (tmp_path / "context/tasks/task_001_context.json").write_text(
        json.dumps({"files_touched": ["src/a.py"]})
    )
    git(tmp_path, "add", ".")
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
        env={
            "GIT_COMMITTER_DATE": "2026-09-30T12:00:00+00:00",
            "GIT_AUTHOR_DATE": "2026-09-30T12:00:00+00:00",
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
        },
    )
    return tmp_path


def build(repo, *extra):
    return run_module(repo, "scripts.build_state", "--ref", "main", "--out", "build/state", *extra)


def test_builds_from_ref_not_working_tree(repo):
    # An uncommitted edit on the working tree must not reach the views.
    (repo / "state/tasks/task_002.json").write_text(
        json.dumps(make_task("task_002", title="LOCAL EDIT"))
    )
    result = build(repo)
    assert result.returncode == 0, result.stderr
    out = repo / "build/state"
    pending = json.loads((out / "pending.json").read_text())
    assert [r["title"] for r in pending] == ["Add endpoint"]
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["as_of"] == "2026-09-30T12:00:00+00:00"
    assert (out / "dashboard.html").read_text().startswith("<!doctype html>")
    assert (out / "context/global/LASTCONTEXT.md").read_text().startswith("# Last context\n")
    assert "task_001 · Add endpoint" in (out / "context/roles/backend/LASTCONTEXT.md").read_text()


def test_rebuild_is_byte_identical(repo):
    assert build(repo).returncode == 0
    first = {p: p.read_bytes() for p in (repo / "build/state").rglob("*") if p.is_file()}
    assert build(repo).returncode == 0
    second = {p: p.read_bytes() for p in (repo / "build/state").rglob("*") if p.is_file()}
    assert first == second


def test_as_of_can_be_given_explicitly(repo):
    result = build(repo, "--as-of", "2026-10-02T08:00:00Z")
    assert result.returncode == 0, result.stderr
    metrics = json.loads((repo / "build/state/metrics.json").read_text())
    assert metrics["as_of"] == "2026-10-02T08:00:00+00:00"


def test_as_of_without_time_zone_is_rejected(repo):
    result = build(repo, "--as-of", "2026-10-02T08:00:00")
    assert result.returncode != 0
    assert "time zone" in result.stderr


def test_refuses_foreign_output_directory(repo):
    (repo / "build/state").mkdir(parents=True)
    (repo / "build/state/keep.txt").write_text("mine")
    result = build(repo)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert (repo / "build/state/keep.txt").exists()


def test_invalid_state_fails_loudly(repo):
    (repo / "state/tasks/task_003.json").write_text(
        json.dumps(make_task("task_003", light="green"))
    )
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "bad")
    result = build(repo)
    assert result.returncode == 1
    assert "derived field must not be declared: light" in result.stderr
    assert not (repo / "build/state").exists()


ADR_TEXT = """---
status: accepted
date: 2026-09-24
tags: [db]
---
# Money in cents

## Context
c
## Decision
d
## Alternatives considered
a
## Consequences
e
"""


def test_knowledge_is_read_from_the_ref(repo):
    (repo / "docs/adr").mkdir(parents=True)
    (repo / "docs/adr/0001-money-in-cents.md").write_text(ADR_TEXT)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "adr")
    result = build(repo)
    assert result.returncode == 0, result.stderr
    md = (repo / "build/state/context/global/LASTCONTEXT.md").read_text()
    assert "- ADR 0001 · Money in cents — `docs/adr/0001-money-in-cents.md` (db)" in md


def test_check_docs_cli(repo):
    (repo / "docs/adr").mkdir(parents=True)
    (repo / "docs/adr/0001-money-in-cents.md").write_text(
        ADR_TEXT + "\nSee [overview](../architecture/overview.md).\n"
    )
    git(repo, "add", ".")
    result = run_module(repo, "scripts.check_docs")
    assert result.returncode == 1
    assert (
        "docs/adr/0001-money-in-cents.md: broken link: ../architecture/overview.md" in result.stderr
    )
    (repo / "docs/architecture").mkdir()
    (repo / "docs/architecture/overview.md").write_text("# Overview\n")
    git(repo, "add", ".")
    result = run_module(repo, "scripts.check_docs")
    assert result.returncode == 0, result.stderr
