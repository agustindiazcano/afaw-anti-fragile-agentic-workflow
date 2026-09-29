"""Tests for scripts.check_task_delta: a PR that changes code must carry a valid context delta."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scripts import check_task_delta
from scripts.state_common import StateError

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

DELTA = "context/tasks/task_001_context.json"


def test_docs_only_change_needs_no_delta(project: Project) -> None:
    assert check_task_delta.find_problems(["docs/guide.md", "README.md"], project.root) == []


def test_gitkeep_files_do_not_count_as_code(project: Project) -> None:
    assert check_task_delta.find_problems(["src/back/.gitkeep"], project.root) == []


def test_code_without_delta_is_reported(project: Project) -> None:
    problems = check_task_delta.find_problems(["src/back/health.py"], project.root)
    assert len(problems) == 1
    assert "no context delta" in problems[0]


def test_valid_delta_covering_the_code_passes(project: Project) -> None:
    project.add_task("task_001", status="in_progress")
    project.add_delta("task_001", files_touched=["src/back/health.py", "tests/back/test_health.py"])
    changed = ["src/back/health.py", "tests/back/test_health.py", DELTA]
    assert check_task_delta.find_problems(changed, project.root) == []


def test_code_file_missing_from_files_touched_is_reported(project: Project) -> None:
    project.add_task("task_001", status="in_progress")
    project.add_delta("task_001", files_touched=["src/back/health.py"])
    changed = ["src/back/health.py", "src/back/other.py", DELTA]
    problems = check_task_delta.find_problems(changed, project.root)
    assert len(problems) == 1
    assert "src/back/other.py" in problems[0]


def test_invalid_delta_is_reported(project: Project) -> None:
    project.write(DELTA, {"task_id": "task_001"})
    problems = check_task_delta.find_problems(["src/back/health.py", DELTA], project.root)
    assert any("missing required field" in problem for problem in problems)


def test_delta_task_id_must_match_its_file_name(project: Project) -> None:
    project.add_task("task_001")
    project.add_task("task_002")
    project.add_delta("task_002", files_touched=["src/back/health.py"])
    (project.root / "context/tasks/task_002_context.json").rename(project.root / DELTA)
    problems = check_task_delta.find_problems(["src/back/health.py", DELTA], project.root)
    assert any("task_002" in problem and "task_001" in problem for problem in problems)


def test_delta_needs_its_task_state_file(project: Project) -> None:
    project.add_delta("task_001", files_touched=["src/back/health.py"])
    problems = check_task_delta.find_problems(["src/back/health.py", DELTA], project.root)
    assert any("state/tasks/task_001.json" in problem for problem in problems)


def test_code_folders_come_from_the_project_config(project: Project) -> None:
    project.write("state/config.json", {"code_prefixes": ["app/"]})
    assert check_task_delta.find_problems(["src/a.py"], project.root) == []
    problems = check_task_delta.find_problems(["app/a.py"], project.root)
    assert len(problems) == 1
    assert "no context delta" in problems[0]


def test_ignored_names_come_from_the_project_config(project: Project) -> None:
    project.write("state/config.json", {"ignored_names": ["placeholder.txt"]})
    assert check_task_delta.find_problems(["src/placeholder.txt"], project.root) == []
    assert check_task_delta.find_problems(["src/.gitkeep"], project.root) != []


def test_invalid_config_is_rejected(project: Project) -> None:
    project.write("state/config.json", {"code_prefixes": "src/"})
    with pytest.raises(StateError, match="code_prefixes"):
        check_task_delta.find_problems(["docs/a.md"], project.root)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()


def test_changed_files_lists_what_changed_since_the_base(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "base.txt").write_text("base", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "change")

    assert check_task_delta.changed_files(base, tmp_path) == ["src/x.py"]


def test_changed_files_fails_loudly_on_a_bad_base(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    with pytest.raises(StateError, match="could not list changed files"):
        check_task_delta.changed_files("does-not-exist", tmp_path)


def test_main_returns_1_when_problems_exist(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_task_delta, "changed_files", lambda base, root: ["src/a.py"])
    assert check_task_delta.main(["--root", str(project.root), "--base", "origin/main"]) == 1
    assert "no context delta" in capsys.readouterr().err


def test_main_returns_0_when_everything_is_in_order(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_task_delta, "changed_files", lambda base, root: ["docs/a.md"])
    assert check_task_delta.main(["--root", str(project.root), "--base", "origin/main"]) == 0
