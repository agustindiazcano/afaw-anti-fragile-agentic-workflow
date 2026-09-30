"""Task file model: what an agent may write, and how status may change.

The shape of a task file is defined once, in state/schemas/task.schema.json.
This module adds what a schema cannot express: explicit rejection of measured
values, rules that relate fields to each other, and the status lifecycle.
Measured values (timestamps, CI results, the traffic light) are derived
elsewhere, so an agent cannot declare them (principle P1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.state_common import Json, load_json, validate

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_SCHEMA_PATH = REPO_ROOT / "state" / "schemas" / "task.schema.json"

STATUSES = ("backlog", "pending", "in_progress", "done", "cancelled")
OPEN_STATUSES = frozenset({"backlog", "pending", "in_progress"})
CLOSED_STATUSES = frozenset({"done", "cancelled"})

# Allowed status changes between the base and the head of a pull request. A
# pull request sees only its two endpoints: a task that went pending ->
# in_progress -> done on its branch arrives as pending -> done. So any open
# status may reach done, and done and cancelled are final.
TRANSITIONS: dict[str, frozenset[str]] = {
    "backlog": frozenset({"pending", "in_progress", "done", "cancelled"}),
    "pending": frozenset({"backlog", "in_progress", "done", "cancelled"}),
    "in_progress": frozenset({"pending", "done", "cancelled"}),
    "done": frozenset(),
    "cancelled": frozenset(),
}

# Measured values. They come from git, the pull request API or the CI API,
# never from the task file.
DERIVED_FIELDS = frozenset(
    {
        "created_at",
        "updated_at",
        "started_at",
        "pr",
        "pr_url",
        "pr_opened_at",
        "first_green_at",
        "merged_at",
        "last_activity_at",
        "duration",
        "durations",
        "light",
        "ci",
        "ci_status",
        "queue_seconds",
        "job_minutes",
    }
)

_schema_cache: dict[str, Json] = {}


def task_schema() -> Json:
    """The task JSON Schema, read once from state/schemas/."""
    if "task" not in _schema_cache:
        _schema_cache["task"] = load_json(TASK_SCHEMA_PATH)
    return _schema_cache["task"]


def validate_task(task: Any) -> list[str]:
    """Return every problem found in a task file; an empty list means valid."""
    if not isinstance(task, dict):
        return ["task file must be a JSON object"]

    derived = sorted(key for key in task if key in DERIVED_FIELDS)
    errors = [f"derived field must not be declared: {key}" for key in derived]
    shape = validate({k: v for k, v in task.items() if k not in DERIVED_FIELDS}, task_schema())
    errors.extend(shape)

    blockers = task.get("blocked_by")
    if isinstance(blockers, list) and task.get("id") in blockers:
        errors.append("a task cannot block itself")

    # Work by an agent happens on a branch; an action by the human (rotate a
    # key, change a setting) may have none.
    status = task.get("status")
    if task.get("owner", "agent") == "agent" and status in {"in_progress", "done"}:
        if not task.get("branch"):
            errors.append(f"status {status} requires a branch")
    return errors


def check_transition(old: str | None, new: str) -> str | None:
    """Return an error if a status change is not allowed, else None.

    ``old`` is None for a task file created by the pull request; such a task may
    arrive already done (the pull request is its work), but not cancelled.
    """
    if new not in STATUSES:
        return f"invalid status: {new!r}"
    if old is None:
        if new == "cancelled":
            return "a new task cannot start as cancelled"
        return None
    if old == new:
        return None
    if old not in STATUSES:
        return f"invalid status: {old!r}"
    if new not in TRANSITIONS[old]:
        return f"status change not allowed: {old} -> {new}"
    return None
