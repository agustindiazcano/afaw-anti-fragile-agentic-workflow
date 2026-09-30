"""Fixtures: a throwaway project root with the real schemas and helpers to add tasks/deltas."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.tooling.helpers import make_task

REPO_ROOT = Path(__file__).resolve().parents[2]


class Project:
    """A temporary project root laid out like the boilerplate."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def add_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Write state/tasks/<task_id>.json (a valid task, plus ``fields``) and return it."""
        if fields.get("status") in {"in_progress", "done"}:
            fields.setdefault("branch", "feat/some-task")
        task = make_task(task_id, **fields)
        self.write(f"state/tasks/{task_id}.json", task)
        return task

    def add_delta(
        self,
        task_id: str,
        *,
        files_touched: list[str] | None = None,
        summary: str | None = None,
        next_steps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write context/tasks/<task_id>_context.json and return its content."""
        delta: dict[str, Any] = {"task_id": task_id, "files_touched": files_touched or []}
        if summary is not None:
            delta["summary"] = summary
        if next_steps is not None:
            delta["next"] = next_steps
        self.write(f"context/tasks/{task_id}_context.json", delta)
        return delta

    def write(self, relative_path: str, data: Any) -> None:
        """Write a JSON file under the project root, creating folders as needed."""
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Project:
    """A temporary project root that already contains the real JSON schemas."""
    schemas = tmp_path / "state" / "schemas"
    schemas.mkdir(parents=True)
    for name in (
        "task.schema.json",
        "context_delta.schema.json",
        "config.schema.json",
        "equivalent_mutants.schema.json",
    ):
        shutil.copy(REPO_ROOT / "state" / "schemas" / name, schemas / name)
    return Project(tmp_path)
