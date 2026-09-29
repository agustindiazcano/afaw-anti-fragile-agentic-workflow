"""Tests for the JSON loading and schema validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.state_common import StateError, load_json, load_validated, validate

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "n"],
    "properties": {
        "id": {"type": "string", "pattern": "^t_[0-9]+$"},
        "n": {"type": "integer", "minimum": 1, "maximum": 5},
        "tags": {"type": "array", "items": {"type": "string"}},
        "kind": {"enum": ["a", "b"]},
        "owner": {"type": ["string", "null"]},
    },
}


def test_valid_instance_has_no_errors() -> None:
    instance = {"id": "t_1", "n": 3, "tags": ["x"], "kind": "a", "owner": None}
    assert validate(instance, SCHEMA) == []


def test_missing_required_field_is_reported() -> None:
    assert validate({"id": "t_1"}, SCHEMA) == ["$: missing required field 'n'"]


def test_wrong_type_is_reported() -> None:
    assert validate({"id": "t_1", "n": "3"}, SCHEMA) == ["$.n: expected integer, got str"]


def test_boolean_is_not_an_integer() -> None:
    assert validate({"id": "t_1", "n": True}, SCHEMA) == ["$.n: expected integer, got bool"]


def test_range_pattern_and_enum_are_enforced() -> None:
    errors = validate({"id": "x", "n": 9, "kind": "z"}, SCHEMA)
    assert any("$.id" in error and "pattern" in error for error in errors)
    assert any("$.n" in error and "maximum" in error for error in errors)
    assert any("$.kind" in error for error in errors)
    assert validate({"id": "t_1", "n": 0}, SCHEMA) == ["$.n: 0 is less than the minimum 1"]


def test_unexpected_field_is_reported() -> None:
    assert validate({"id": "t_1", "n": 1, "extra": 1}, SCHEMA) == ["$: unexpected field 'extra'"]


def test_array_items_are_validated_with_their_index() -> None:
    assert validate({"id": "t_1", "n": 1, "tags": ["ok", 2]}, SCHEMA) == [
        "$.tags[1]: expected string, got int"
    ]


def test_union_types_accept_null() -> None:
    assert validate({"id": "t_1", "n": 1, "owner": None}, SCHEMA) == []
    assert validate({"id": "t_1", "n": 1, "owner": 5}, SCHEMA) != []


def test_load_json_reports_the_path_on_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    with pytest.raises(StateError, match="bad.json"):
        load_json(bad)


def test_load_json_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(StateError, match="missing.json"):
        load_json(tmp_path / "missing.json")


def test_load_validated_raises_with_every_error(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text('{"id": "x", "extra": 1}', encoding="utf-8")
    with pytest.raises(StateError) as info:
        load_validated(path, SCHEMA)
    message = str(info.value)
    assert "t.json" in message
    assert "missing required field 'n'" in message
    assert "unexpected field 'extra'" in message
