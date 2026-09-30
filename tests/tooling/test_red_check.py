"""Tests for scripts.red_check: each test a pull request adds must fail on the old code."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import red_check

OLD_TESTS = """
def test_existing():
    assert True


class TestGroup:
    def test_kept(self):
        assert True
"""

NEW_TESTS = """
import pytest


def test_existing():
    assert True


def test_added():
    assert False


class TestGroup:
    def test_kept(self):
        assert True

    def test_added_in_class(self):
        assert False


@pytest.mark.parametrize("x", [1, 2])
def test_added_param(x):
    assert x == 2


def helper_not_a_test():
    pass
"""


def test_test_ids_lists_functions_and_methods() -> None:
    ids = red_check.test_ids(NEW_TESTS)
    assert ids == {
        "test_existing",
        "test_added",
        "TestGroup::test_kept",
        "TestGroup::test_added_in_class",
        "test_added_param",
    }


def test_added_tests_is_the_difference() -> None:
    added = red_check.added_tests("tests/test_x.py", OLD_TESTS, NEW_TESTS)
    assert added == [
        "tests/test_x.py::TestGroup::test_added_in_class",
        "tests/test_x.py::test_added",
        "tests/test_x.py::test_added_param",
    ]


def test_added_tests_of_a_new_file_are_all_its_tests() -> None:
    assert len(red_check.added_tests("tests/test_x.py", None, NEW_TESTS)) == 5


JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
  <testcase classname="tests.test_x" name="test_added"><failure message="x"/></testcase>
  <testcase classname="tests.test_x.TestGroup" name="test_added_in_class"/>
  <testcase classname="tests.test_x" name="test_added_param[1]"><failure message="x"/></testcase>
  <testcase classname="tests.test_x" name="test_added_param[2]"/>
  <testcase classname="tests.test_x" name="test_skipped"><skipped message="s"/></testcase>
</testsuite></testsuites>
"""


def test_passing_on_old_code_is_read_from_junit() -> None:
    added = [
        "tests/test_x.py::test_added",
        "tests/test_x.py::TestGroup::test_added_in_class",
        "tests/test_x.py::test_added_param",
        "tests/test_x.py::test_skipped",
    ]
    # A parametrized test is red if at least one case fails; a skip is not a failure.
    passing, missing = red_check.not_red(JUNIT, added)
    assert passing == [
        "tests/test_x.py::TestGroup::test_added_in_class",
        "tests/test_x.py::test_skipped",
    ]
    assert missing == []


def test_a_test_absent_from_the_report_is_missing_not_passing() -> None:
    # Absence is not a verdict: the test did not run (fail loudly, never a silent pass).
    assert red_check.not_red(JUNIT, ["tests/test_x.py::test_missing"]) == (
        [],
        ["tests/test_x.py::test_missing"],
    )


def test_a_module_that_cannot_be_imported_makes_its_tests_red() -> None:
    report = (
        '<testsuites><testsuite><testcase classname="" name="tests.test_y">'
        '<error message="ImportError"/></testcase></testsuite></testsuites>'
    )
    assert red_check.not_red(report, ["tests/test_y.py::test_new"]) == ([], [])


def test_characterization_tests_are_declared_not_checked() -> None:
    source = """
import pytest


@pytest.mark.characterization(reason="documents the existing guard")
def test_existing_behaviour():
    assert True


@pytest.mark.parametrize("x", [1])
def test_new(x):
    assert False
"""
    assert red_check.characterization("tests/test_z.py", source) == {
        "tests/test_z.py::test_existing_behaviour": "documents the existing guard"
    }


# ---------------------------------------------------------------- end to end

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "tests/test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\n', encoding="utf-8"
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    _git(tmp_path, "checkout", "-q", "-b", "feat/x")
    return tmp_path


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "scripts.red_check", "--base", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_end_to_end_test_driving_a_change_passes(repo: Path) -> None:
    (repo / "src/calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
        encoding="utf-8",
    )
    with (repo / "tests/test_calc.py").open("a", encoding="utf-8") as f:
        f.write("\n\ndef test_sub():\n    from src.calc import sub\n    assert sub(3, 1) == 2\n")
    _git(repo, "commit", "-qam", "feat: sub")
    result = _run(repo)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "1 added test failed on the old code" in result.stdout
    assert not list(repo.glob(".red-check-*")), "the temporary worktree must be removed"


def test_end_to_end_test_passing_on_old_code_is_rejected(repo: Path) -> None:
    with (repo / "tests/test_calc.py").open("a", encoding="utf-8") as f:
        f.write("\n\ndef test_add_zero():\n    assert add(0, 0) == 0\n")
    _git(repo, "commit", "-qam", "test: add zero")
    result = _run(repo)
    assert result.returncode == 1
    assert "tests/test_calc.py::test_add_zero" in result.stderr


def test_end_to_end_tests_only_task_is_skipped_and_declared(repo: Path) -> None:
    (repo / "state/tasks").mkdir(parents=True)
    task = {"id": "task_001", "type": "tests-only", "status": "done"}
    (repo / "state/tasks/task_001.json").write_text(json.dumps(task), encoding="utf-8")
    with (repo / "tests/test_calc.py").open("a", encoding="utf-8") as f:
        f.write("\n\ndef test_add_zero():\n    assert add(0, 0) == 0\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "test: add zero")
    result = _run(repo)
    assert result.returncode == 0
    assert "SKIPPED: task_001 declares type tests-only" in result.stdout


def test_end_to_end_no_added_tests(repo: Path) -> None:
    (repo / "src/calc.py").write_text("def add(a, b):\n    return b + a\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "refactor")
    result = _run(repo)
    assert result.returncode == 0
    assert "no added tests" in result.stdout
