"""Builders shared by the tests of the derived-state package."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

AS_OF = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def make_task(task_id: str = "task_001", **overrides: Any) -> dict[str, Any]:
    """A valid task file; keyword arguments replace or add fields."""
    task: dict[str, Any] = {
        "id": task_id,
        "title": "Add endpoint",
        "role": "backend",
        "type": "feature",
        "status": "pending",
        "priority": 3,
        "difficulty": 2,
        "blocked_by": [],
    }
    task.update(overrides)
    return task
