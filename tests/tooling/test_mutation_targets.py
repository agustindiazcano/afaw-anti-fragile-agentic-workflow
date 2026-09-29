"""Tests for scripts.mutation_targets: which changed files must, or may, be mutation-tested."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scripts import mutation_targets
from scripts.project_config import load_config

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

CHANGED = [
    "src/pay/charge.py",
    "src/util.py",
    "tests/test_charge.py",
    "docs/a.md",
    "src/.gitkeep",
    "context/tasks/task_001_context.json",
]


def test_changed_files_are_split_into_required_and_optional(project: Project) -> None:
    project.write(
        "state/config.json", {"mutation_critical_paths": ["src/pay/"], "mutation_min_score": 85}
    )
    result = mutation_targets.classify(CHANGED, load_config(project.root))
    assert result == {
        "required": ["src/pay/charge.py"],
        "optional": ["src/util.py"],
        "min_score": 85.0,
    }


def test_tests_and_docs_are_never_mutation_targets(project: Project) -> None:
    result = mutation_targets.classify(
        ["tests/test_a.py", "docs/a.md"], load_config(project.root)
    )
    assert result["required"] == []
    assert result["optional"] == []


def test_without_critical_paths_nothing_is_required(project: Project) -> None:
    result = mutation_targets.classify(["src/a.py"], load_config(project.root))
    assert result["required"] == []
    assert result["optional"] == ["src/a.py"]


def test_main_prints_the_result_as_json(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {"mutation_critical_paths": ["src/pay/"]})
    monkeypatch.setattr(mutation_targets, "changed_files", lambda base, root: CHANGED)
    assert mutation_targets.main(["--root", str(project.root), "--base", "origin/main"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "required": ["src/pay/charge.py"],
        "optional": ["src/util.py"],
        "min_score": 80.0,
    }


def test_main_returns_2_on_an_invalid_config(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.write("state/config.json", {"mutation_min_score": -5})
    assert mutation_targets.main(["--root", str(project.root), "--base", "origin/main"]) == 2
    assert "mutation_min_score" in capsys.readouterr().err
