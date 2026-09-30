"""Project knowledge written by people and agents as markdown: ADRs and gotchas.

A document carries a small front matter block for the fields a program needs
(status, date, links to other records) and prose for everything a reader
needs (context, the decision, rejected alternatives, consequences). The
markdown is the only source; indexes are derived from it and never written by
hand, so nothing is recorded twice.

    docs/adr/NNNN-slug.md       decisions (Nygard-style records)
    docs/gotchas/NNNN-slug.md   operational pitfalls that still bite

Front matter is a restricted ``key: value`` format (values may be ``[a, b]``
lists), parsed with the standard library.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

KINDS = {"docs/adr/": "adr", "docs/gotchas/": "gotcha"}

ADR_STATUSES = ("proposed", "accepted", "superseded", "deprecated")
GOTCHA_STATUSES = ("active", "resolved", "promoted")

ALLOWED_KEYS = {
    "adr": {"status", "date", "supersedes", "tags"},
    "gotcha": {"status", "date", "tags", "resolved_by", "promoted_to"},
}
REQUIRED_KEYS = {"adr": ("status", "date"), "gotcha": ("status", "date")}
REQUIRED_SECTIONS = {
    "adr": ("Context", "Decision", "Alternatives considered", "Consequences"),
    "gotcha": ("Symptom", "What to do"),
}
# A closed gotcha must say what closed it: the task that fixed the cause, or
# the mechanism (hook, script, config, test) that now enforces it.
CLOSING_FIELD = {"resolved": "resolved_by", "promoted": "promoted_to"}

FILE_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [item.strip().strip("'\"") for item in inner.split(",")] if inner else []
    return raw.strip("'\"")


def parse_doc(path: str, text: str) -> dict[str, Any]:
    """Parse one knowledge document. Structural problems are reported by ``check_knowledge``."""
    kind = next((k for prefix, k in KINDS.items() if path.startswith(prefix)), None)
    if kind is None:
        raise ValueError(f"not a knowledge document: {path}")
    name = path.rsplit("/", 1)[-1]
    match = FILE_NAME.match(name)
    doc: dict[str, Any] = {
        "path": path,
        "kind": kind,
        "id": match.group(1) if match else name.split("-", 1)[0].removesuffix(".md"),
        "valid_name": bool(match),
        "meta": {},
        "meta_errors": [],
        "has_front_matter": False,
        "title": None,
        "sections": [],
    }

    lines = text.splitlines()
    body_start = 0
    if lines and lines[0].strip() == "---":
        try:
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration:
            doc["meta_errors"].append("front matter is not closed with ---")
            end = None
        if end is not None:
            doc["has_front_matter"] = True
            for line in lines[1:end]:
                if not line.strip():
                    continue
                key, sep, raw = line.partition(":")
                if not sep:
                    doc["meta_errors"].append(f"front matter line is not key: value: {line!r}")
                    continue
                doc["meta"][key.strip()] = _value(raw)
            body_start = end + 1

    for line in lines[body_start:]:
        if line.startswith("# ") and doc["title"] is None:
            doc["title"] = line[2:].strip()
        elif line.startswith("## "):
            doc["sections"].append(line[3:].strip().lower())
    return doc


def _check_doc(doc: Mapping[str, Any]) -> list[str]:
    kind, meta = doc["kind"], doc["meta"]
    errors = list(doc["meta_errors"])
    if not doc["valid_name"]:
        errors.append("file name must be NNNN-slug.md (lowercase, hyphens)")
    if not doc["has_front_matter"]:
        errors.append("missing front matter")
    for key in sorted(meta):
        if key not in ALLOWED_KEYS[kind]:
            errors.append(f"unknown front matter key: {key}")
    for key in REQUIRED_KEYS[kind]:
        if doc["has_front_matter"] and key not in meta:
            errors.append(f"missing front matter key: {key}")

    statuses = ADR_STATUSES if kind == "adr" else GOTCHA_STATUSES
    status = meta.get("status")
    if status is not None and status not in statuses:
        errors.append(f"invalid status: {status!r}")
    if "date" in meta:
        try:
            date.fromisoformat(str(meta["date"]))
        except ValueError:
            errors.append(f"invalid date: {meta['date']!r} (expected YYYY-MM-DD)")
    for key in ("tags", "supersedes"):
        if key in meta and not isinstance(meta[key], list):
            errors.append(f"{key} must be a list: [a, b]")
    if kind == "gotcha" and status in CLOSING_FIELD and not meta.get(CLOSING_FIELD[status]):
        errors.append(f"status {status} requires {CLOSING_FIELD[status]}")

    if not doc["title"]:
        errors.append("missing title (a '# ' heading)")
    for section in REQUIRED_SECTIONS[kind]:
        if not any(s.startswith(section.lower()) for s in doc["sections"]):
            errors.append(f"missing section: {section}")
    return errors


def check_knowledge(docs: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every problem in the set of documents; an empty list means valid."""
    errors: list[str] = []
    seen: dict[tuple[str, str], str] = {}
    for doc in docs:
        errors.extend(f"{doc['path']}: {e}" for e in _check_doc(doc))
        key = (doc["kind"], doc["id"])
        if key in seen:
            errors.append(
                f"{doc['path']}: duplicate {doc['kind']} id {doc['id']} (also {seen[key]})"
            )
        seen[key] = doc["path"]

    adrs = {d["id"]: d for d in docs if d["kind"] == "adr"}
    superseded_by: dict[str, list[str]] = {}
    for adr in adrs.values():
        targets = adr["meta"].get("supersedes", [])
        for target in targets if isinstance(targets, list) else []:
            if target not in adrs:
                errors.append(f"{adr['path']}: supersedes unknown ADR {target}")
                continue
            superseded_by.setdefault(target, []).append(adr["id"])
            status = adrs[target]["meta"].get("status")
            if status != "superseded":
                errors.append(
                    f"{adrs[target]['path']}: {target} is superseded by {adr['id']} but its "
                    f"status is {status}"
                )
    for adr in adrs.values():
        if adr["meta"].get("status") == "superseded" and adr["id"] not in superseded_by:
            errors.append(f"{adr['path']}: status superseded but no ADR supersedes it")
    return errors


def broken_links(path: str, text: str, existing: set[str]) -> list[str]:
    """Relative links in ``text`` that do not resolve to a file in ``existing``."""
    base = posixpath.dirname(path)
    # Links inside fenced code blocks or inline code are examples, not links of the document.
    prose = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    broken = []
    for target in LINK.findall(prose):
        if target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        file_part = target.split("#", 1)[0]
        if not file_part:
            continue
        resolved = posixpath.normpath(posixpath.join(base, file_part))
        if resolved not in existing:
            broken.append(file_part)
    return broken
