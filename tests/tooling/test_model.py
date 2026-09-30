"""Tests for scripts.afaw_state.model: task files hold declared values and follow a lifecycle."""

from __future__ import annotations

import pytest

from scripts.afaw_state.model import check_transition, validate_task
from tests.tooling.helpers import make_task


def test_valid_task_has_no_errors() -> None:
    assert validate_task(make_task()) == []


def test_missing_fields_are_all_reported() -> None:
    errors = validate_task({"id": "task_001"})
    assert "$: missing required field 'title'" in errors
    assert "$: missing required field 'blocked_by'" in errors


@pytest.mark.parametrize("field", ["merged_at", "started_at", "light", "ci", "pr", "updated_at"])
def test_derived_fields_cannot_be_declared(field: str) -> None:
    errors = validate_task(make_task(**{field: "x"}))
    assert errors == [f"derived field must not be declared: {field}"]


def test_unknown_field_is_rejected() -> None:
    assert "$: unexpected field 'eta'" in validate_task(make_task(eta="tomorrow"))


@pytest.mark.parametrize("value", [0, 6, "3", True, 2.5])
def test_priority_must_be_integer_1_to_5(value: object) -> None:
    errors = validate_task(make_task(priority=value))
    assert len(errors) == 1 and errors[0].startswith("$.priority:")


@pytest.mark.parametrize("bad_id", ["task_1", "Task_001", "task-001", 7])
def test_invalid_id(bad_id: object) -> None:
    assert any(e.startswith("$.id:") for e in validate_task(make_task(bad_id)))  # type: ignore[arg-type]


@pytest.mark.parametrize("role", ["../x", "Back End", "", "a/b"])
def test_role_must_be_safe_for_paths(role: str) -> None:
    assert any(e.startswith("$.role:") for e in validate_task(make_task(role=role)))


def test_in_progress_requires_branch() -> None:
    assert "status in_progress requires a branch" in validate_task(make_task(status="in_progress"))
    assert validate_task(make_task(status="in_progress", branch="feat/x")) == []


def test_self_block_rejected() -> None:
    assert "a task cannot block itself" in validate_task(make_task(blocked_by=["task_001"]))


def test_non_object_rejected() -> None:
    assert validate_task([]) == ["task file must be a JSON object"]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (None, "backlog"),
        (None, "pending"),
        ("backlog", "pending"),
        ("pending", "in_progress"),
        ("in_progress", "done"),
        ("in_progress", "pending"),
        ("pending", "cancelled"),
        ("done", "done"),
        # A pull request sees only its endpoints: in_progress happens on the branch.
        ("pending", "done"),
        ("backlog", "done"),
        (None, "done"),
    ],
)
def test_allowed_transitions(old: str | None, new: str) -> None:
    assert check_transition(old, new) is None


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (None, "cancelled"),
        ("done", "in_progress"),
        ("done", "pending"),
        ("cancelled", "pending"),
        ("cancelled", "done"),
    ],
)
def test_forbidden_transitions(old: str | None, new: str) -> None:
    assert check_transition(old, new) is not None


def test_transition_to_invalid_status() -> None:
    assert check_transition("pending", "finished") == "invalid status: 'finished'"


@pytest.mark.parametrize("owner", ["agent", "human"])
def test_owner_values(owner: str) -> None:
    assert validate_task(make_task(owner=owner)) == []


def test_invalid_owner() -> None:
    assert "$.owner: 'team' is not one of ['agent', 'human']" in validate_task(
        make_task(owner="team")
    )


def test_human_task_in_progress_needs_no_branch() -> None:
    assert validate_task(make_task(owner="human", status="in_progress")) == []
    assert validate_task(make_task(owner="human", status="done")) == []


def test_done_and_cancelled_are_final() -> None:
    assert check_transition("done", "pending") is not None
    assert check_transition("cancelled", "done") is not None
