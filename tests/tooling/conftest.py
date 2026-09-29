"""Fixtures: a throwaway project root with the real schemas and helpers to add tasks/deltas."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


class Project:
    """A temporary project root laid out like the boilerplate."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def add_task(
        self,
        task_id: str,
        *,
        role: str = "backend",
        status: str = "pending",
        owner: str | None = None,
        blocked_by: list[str] | None = None,
        locked_files: list[str] | None = None,
        updated_at: str = "2026-09-29T15:00:00-03:00",
    ) -> dict[str, Any]:
        """Write state/tasks/<task_id>.json and return its content."""
        task: dict[str, Any] = {
            "id": task_id,
            "title": f"Title of {task_id}",
            "role": role,
            "status": status,
            "owner": owner,
            "branch": None,
            "priority": 2,
            "difficulty": 2,
            "blocked_by": blocked_by or [],
            "locked_files": locked_files or [],
            "pr": None,
            "created_at": "2026-09-29T15:00:00-03:00",
            "updated_at": updated_at,
        }
        self.write(f"state/tasks/{task_id}.json", task)
        return task

    def add_delta(
        self,
        task_id: str,
        *,
        role: str = "backend",
        agent: str = "agent_1",
        written_at: str = "2026-09-29T15:30:00-03:00",
        decisions: list[str] | None = None,
        files_touched: list[str] | None = None,
        dependencies_added: list[str] | None = None,
        blocked_by_lock: list[str] | None = None,
        remaining_work: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write context/tasks/<task_id>_context.json and return its content."""
        delta: dict[str, Any] = {
            "task_id": task_id,
            "role": role,
            "agent": agent,
            "branch": "feat/some-task",
            "written_at": written_at,
            "decisions": [{"decision": text} for text in decisions or []],
            "dependencies_added": dependencies_added or [],
            "files_touched": files_touched or [],
            "blocked_by_lock": blocked_by_lock or [],
            "remaining_work": remaining_work or [],
        }
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
    for name in ("task.schema.json", "context_delta.schema.json", "config.schema.json"):
        shutil.copy(REPO_ROOT / "state" / "schemas" / name, schemas / name)
    return Project(tmp_path)
