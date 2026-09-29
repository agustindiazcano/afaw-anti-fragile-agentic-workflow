"""Shared helpers for the state scripts: JSON loading and a small JSON Schema validator.

Stdlib only, so the scripts run in CI without installing anything.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

Json = Any  # JSON documents are untyped by nature.

_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


class StateError(Exception):
    """Raised when a state or context file is missing, unreadable or invalid."""


def _type_matches(value: Json, expected: str | list[str]) -> bool:
    """Return True if value has one of the expected JSON types (bool is not an integer)."""
    names = expected if isinstance(expected, list) else [expected]
    for name in names:
        if name in ("integer", "number") and isinstance(value, bool):
            continue
        if isinstance(value, _PY_TYPES[name]):
            return True
    return False


def _validate_scalar(instance: Json, schema: dict[str, Json], path: str) -> list[str]:
    """Check pattern, minLength, minimum and maximum for strings and numbers."""
    errors: list[str] = []
    if isinstance(instance, str):
        pattern = schema.get("pattern")
        if pattern is not None and not re.search(pattern, instance):
            errors.append(f"{path}: {instance!r} does not match pattern {pattern!r}")
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than {schema['minLength']} characters")
    elif isinstance(instance, int | float) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is less than the minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is greater than the maximum {schema['maximum']}")
    return errors


def _validate_object(
    instance: dict[str, Json], schema: dict[str, Json], path: str
) -> list[str]:
    """Check required, properties and additionalProperties=false for an object."""
    errors = [
        f"{path}: missing required field {key!r}"
        for key in schema.get("required", [])
        if key not in instance
    ]
    properties = schema.get("properties", {})
    for key, value in instance.items():
        if key in properties:
            errors.extend(validate(value, properties[key], f"{path}.{key}"))
        elif schema.get("additionalProperties") is False:
            errors.append(f"{path}: unexpected field {key!r}")
    return errors


def validate(instance: Json, schema: dict[str, Json], path: str = "$") -> list[str]:
    """Validate instance against a subset of JSON Schema and return the error messages.

    Supported keywords: type, enum, pattern, minLength, minimum, maximum, required,
    properties, additionalProperties (false only) and items. An empty list means valid.
    """
    if "type" in schema and not _type_matches(instance, schema["type"]):
        return [f"{path}: expected {schema['type']}, got {type(instance).__name__}"]
    errors: list[str] = []
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    errors.extend(_validate_scalar(instance, schema, path))
    if isinstance(instance, dict):
        errors.extend(_validate_object(instance, schema, path))
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    return errors


def load_json(path: Path) -> Json:
    """Read a JSON file; raise StateError naming the file if it is missing or malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"{path}: {exc}") from exc


def load_validated(path: Path, schema: dict[str, Json]) -> Json:
    """Read a JSON file and validate it against schema; raise StateError listing every error."""
    data = load_json(path)
    errors = validate(data, schema)
    if errors:
        raise StateError(f"{path}: " + "; ".join(errors))
    return data
