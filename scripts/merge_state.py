"""Consolidate per-task state and context deltas into the generated files.

Reads state/tasks/*.json and context/tasks/*_context.json and writes:
  - state/pending.json
  - context/global/lastcontext.json
  - context/roles/<role>/lastcontext.json

Pure code, no LLM. The same input always gives the same output (no wall-clock timestamps).
Agents never edit the generated files; CI regenerates them and opens a PR for a human.

Run: python -m scripts.merge_state [--root .] [--check]
  --check writes nothing and exits 1 if any generated file is out of date.
Exit codes: 0 ok, 1 stale (--check only), 2 invalid state (details on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from scripts.state_common import Json, StateError, load_json, load_validated

GENERATED_BY = "scripts/merge_state.py (CI)"
STATUSES = ("pending", "in_progress", "blocked", "completed")
MAX_RECENT_DECISIONS = 20
MAX_MERGED_TASKS = 10
PENDING_PATH = "state/pending.json"
GLOBAL_PATH = "context/global/lastcontext.json"
TASK_SCHEMA_PATH = "state/schemas/task.schema.json"
DELTA_SCHEMA_PATH = "state/schemas/context_delta.schema.json"


def _parse_time(value: str) -> datetime:
    """Parse an ISO 8601 timestamp; raise StateError if it is not valid."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise StateError(f"invalid ISO timestamp {value!r}: {exc}") from exc


def _latest(timestamps: Iterable[str]) -> str | None:
    """Return the most recent timestamp (as written), or None if there are none."""
    values = list(timestamps)
    return max(values, key=_parse_time) if values else None


def _dedupe(items: Iterable[str]) -> list[str]:
    """Remove duplicates while keeping the first occurrence order."""
    return list(dict.fromkeys(items))


def load_tasks(root: Path) -> dict[str, Json]:
    """Load and validate state/tasks/task_*.json, keyed by task id in file-name order."""
    schema = load_json(root / TASK_SCHEMA_PATH)
    tasks: dict[str, Json] = {}
    for path in sorted((root / "state" / "tasks").glob("task_*.json")):
        task = load_validated(path, schema)
        if task["id"] != path.stem:
            raise StateError(f"{path}: id {task['id']!r} does not match the file name")
        tasks[task["id"]] = task
    return tasks


def load_deltas(root: Path) -> list[Json]:
    """Load and validate context/tasks/task_*_context.json, oldest first."""
    schema = load_json(root / DELTA_SCHEMA_PATH)
    deltas: list[Json] = []
    for path in sorted((root / "context" / "tasks").glob("task_*_context.json")):
        delta = load_validated(path, schema)
        if path.name != f"{delta['task_id']}_context.json":
            raise StateError(f"{path}: task_id {delta['task_id']!r} does not match the file name")
        deltas.append(delta)
    return sorted(deltas, key=lambda d: (_parse_time(d["written_at"]), d["task_id"]))


def check_invariants(tasks: dict[str, Json], deltas: list[Json]) -> None:
    """Fail loudly on unknown references or a file locked by two in-progress tasks."""
    for task in tasks.values():
        for blocker in task["blocked_by"]:
            if blocker not in tasks:
                raise StateError(f"{task['id']}: blocked_by references unknown task {blocker!r}")
    owners: dict[str, str] = {}
    for task in tasks.values():
        if task["status"] != "in_progress":
            continue
        for locked in task["locked_files"]:
            if locked in owners:
                raise StateError(
                    f"LOCK CONFLICT: {locked} is locked by both {owners[locked]} and {task['id']}"
                )
            owners[locked] = task["id"]
    for delta in deltas:
        if delta["task_id"] not in tasks:
            raise StateError(f"context delta for unknown task {delta['task_id']!r}")


def _status_counts(tasks: dict[str, Json]) -> dict[str, int]:
    """Count tasks per status, always listing every status."""
    return {status: sum(1 for t in tasks.values() if t["status"] == status) for status in STATUSES}


def build_pending(tasks: dict[str, Json]) -> Json:
    """Build state/pending.json: the read-only consolidated view of all tasks."""
    return {
        "generated": True,
        "generated_by": GENERATED_BY,
        "generated_at": _latest(t["updated_at"] for t in tasks.values() if "updated_at" in t),
        "note": "Do not edit by hand. Source of truth is state/tasks/*.json, one file per task.",
        "tasks": {
            task_id: {key: task[key] for key in ("status", "owner", "blocked_by", "locked_files")}
            for task_id, task in tasks.items()
        },
        "summary": _status_counts(tasks),
    }


def build_role_context(role: str, tasks: dict[str, Json], deltas: list[Json]) -> Json:
    """Build context/roles/<role>/lastcontext.json from that role's tasks and deltas."""
    role_tasks = [t for t in tasks.values() if t["role"] == role]
    role_deltas = [d for d in deltas if d["role"] == role]
    active = [d for d in role_deltas if tasks[d["task_id"]]["status"] != "completed"]
    focus = [f"{t['id']}: {t['title']}" for t in role_tasks if t["status"] == "in_progress"]
    decisions = [{"task_id": d["task_id"], **item} for d in role_deltas for item in d["decisions"]]
    stamps = [t["updated_at"] for t in role_tasks if "updated_at" in t]
    stamps += [d["written_at"] for d in role_deltas]
    return {
        "generated": True,
        "generated_by": GENERATED_BY,
        "role": role,
        "updated_at": _latest(stamps),
        "last_agent_session": role_deltas[-1]["agent"] if role_deltas else None,
        "current_focus": "; ".join(focus) or "Idle.",
        "recent_decisions": decisions[-MAX_RECENT_DECISIONS:],
        "open_questions": _dedupe(q for d in active for q in d.get("blocked_by_lock", [])),
        "next_steps": _dedupe(step for d in active for step in d.get("remaining_work", [])),
    }


def build_global(existing: Json, tasks: dict[str, Json], deltas: list[Json]) -> Json:
    """Build context/global/lastcontext.json, keeping decisions and dependencies already there."""
    decisions = list(existing.get("architecture_decisions", []))
    known = {decision["id"] for decision in decisions}
    for delta in deltas:
        for index, item in enumerate(delta["decisions"], start=1):
            decision_id = f"dec_{delta['task_id']}_{index}"
            if decision_id in known:
                continue
            known.add(decision_id)
            decisions.append(
                {
                    "id": decision_id,
                    "date": delta["written_at"][:10],
                    "decision": item["decision"],
                    "source_task": delta["task_id"],
                }
            )
    previous = existing.get("dependencies", {})
    role_names = {t["role"] for t in tasks.values()} | {d["role"] for d in deltas}
    roles = sorted(role_names | set(previous))
    dependencies = {
        role: sorted(
            set(previous.get(role, []))
            | {dep for d in deltas if d["role"] == role for dep in d.get("dependencies_added", [])}
        )
        for role in roles
    }
    counts = _status_counts(tasks)
    completed = sorted(task_id for task_id, t in tasks.items() if t["status"] == "completed")
    stamps = [t["updated_at"] for t in tasks.values() if "updated_at" in t]
    stamps += [d["written_at"] for d in deltas]
    return {
        "project": existing.get("project", "unnamed-project"),
        "generated": True,
        "generated_by": GENERATED_BY,
        "updated_at": _latest(stamps),
        "summary": (
            f"{counts['completed']} of {len(tasks)} tasks completed; "
            f"{counts['in_progress']} in progress; {counts['pending']} pending; "
            f"{counts['blocked']} blocked."
        ),
        "architecture_decisions": decisions,
        "dependencies": dependencies,
        "last_merged_tasks": completed[-MAX_MERGED_TASKS:],
    }


def build_outputs(root: Path) -> dict[str, Json]:
    """Compute every generated file as {relative path: content}; nothing is written."""
    tasks = load_tasks(root)
    deltas = load_deltas(root)
    check_invariants(tasks, deltas)
    global_path = root / GLOBAL_PATH
    existing = load_json(global_path) if global_path.exists() else {}
    if not isinstance(existing, dict):
        raise StateError(f"{global_path}: expected a JSON object")
    outputs: dict[str, Json] = {
        PENDING_PATH: build_pending(tasks),
        GLOBAL_PATH: build_global(existing, tasks, deltas),
    }
    for role in sorted({t["role"] for t in tasks.values()} | {d["role"] for d in deltas}):
        outputs[f"context/roles/{role}/lastcontext.json"] = build_role_context(role, tasks, deltas)
    return outputs


def render(data: Json) -> str:
    """Serialize a generated file the same way every time."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def find_stale(root: Path, outputs: dict[str, Json]) -> list[str]:
    """Return the generated files that are missing or differ from what the sources produce."""
    return [
        relative
        for relative, data in outputs.items()
        if not (root / relative).exists()
        or (root / relative).read_text(encoding="utf-8") != render(data)
    ]


def main(argv: list[str] | None = None) -> int:
    """Regenerate the consolidated files (or only check them with --check)."""
    parser = argparse.ArgumentParser(description="Consolidate task state and context deltas.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--check", action="store_true", help="exit 1 if files are out of date")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        outputs = build_outputs(root)
    except StateError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    stale = find_stale(root, outputs)
    if args.check:
        for relative in stale:
            sys.stdout.write(f"STALE: {relative}\n")
        return 1 if stale else 0
    for relative in stale:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(outputs[relative]), encoding="utf-8")
        sys.stdout.write(f"WROTE: {relative}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
