"""Build every derived view from task files, context deltas and measured facts.

``build`` is a pure function. It returns a mapping from output path (relative to
the build directory) to file content, so the caller decides where to write and
tests can compare outputs byte for byte.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from . import context, derive, render
from .knowledge import check_knowledge
from .model import OPEN_STATUSES, STATUSES, validate_task

DEFAULT_CONFIG = {
    "stale_days": 3,
    "lastcontext_size": 5,
    "chart_days": 30,
    "next_size": 10,
    "knowledge_budget": 40,
}
STATUS_ORDER = {
    s: i for i, s in enumerate(("in_progress", "pending", "backlog", "done", "cancelled"))
}


class StateError(ValueError):
    """Raised when the source state is invalid. Views are never built from it."""


def _utc_date(ts: str) -> date:
    return derive.require_ts(ts).astimezone(UTC).date()


def progress(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Share of done tasks over every task not cancelled. A count, not a weighted estimate."""
    done = sum(1 for r in rows if r["status"] == "done")
    scope = sum(1 for r in rows if r["status"] != "cancelled")
    return {
        "done": done,
        "scope": scope,
        "percent": round(100 * done / scope, 1) if scope else None,
    }


def done_per_day(
    rows: Sequence[Mapping[str, Any]], as_of: datetime, window: int
) -> list[dict[str, Any]]:
    """Merged tasks per UTC day, from the first recorded date to ``as_of``, last ``window`` days."""
    merged = [_utc_date(r["merged_at"]) for r in rows if r["status"] == "done" and r["merged_at"]]
    known = merged + [_utc_date(r["created_at"]) for r in rows if r["created_at"]]
    if not known:
        return []
    end = as_of.astimezone(UTC).date()
    start = min(known)
    counts: dict[date, int] = {}
    for d in merged:
        counts[d] = counts.get(d, 0) + 1
    days, total, day = [], 0, start
    while day <= end:
        total += counts.get(day, 0)
        days.append({"date": day.isoformat(), "done": counts.get(day, 0), "cumulative": total})
        day += timedelta(days=1)
    return days[-window:]


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _merged_key(row: Mapping[str, Any]) -> tuple[str, str]:
    # Tasks without a merge time sort last; ties break on the id.
    return (row["merged_at"] or "￿", row["id"])


def build(
    tasks: Sequence[Mapping[str, Any]],
    deltas: Mapping[str, Mapping[str, Any]],
    facts: Mapping[str, Mapping[str, Any]] | None,
    config: Mapping[str, Any] | None,
    as_of: datetime,
    knowledge: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    facts = facts or {}
    docs = list(knowledge or [])

    errors: list[str] = []
    seen: set[Any] = set()
    for task in tasks:
        for problem in validate_task(task):
            errors.append(f"{task.get('id', '?')}: {problem}")
        task_id = task.get("id")
        if task_id in seen:
            errors.append(f"{task_id}: duplicate task id")
        seen.add(task_id)
    errors.extend(check_knowledge(docs))
    if errors:
        raise StateError("invalid source state:\n  " + "\n  ".join(errors))

    by_id = {t["id"]: t for t in tasks}
    rows: list[dict[str, Any]] = []
    for task in tasks:
        f = facts.get(task["id"])
        lamp, reason = derive.light(task, f, by_id, as_of, cfg["stale_days"])
        rows.append(
            {
                "id": task["id"],
                "title": task["title"],
                "role": task["role"],
                "type": task["type"],
                "owner": task.get("owner", "agent"),
                "status": task["status"],
                "priority": task["priority"],
                "difficulty_estimate": task["difficulty"],
                "blocked_by": list(task["blocked_by"]),
                "branch": task.get("branch"),
                "light": lamp,
                "light_reason": reason,
                "pr_url": (f or {}).get("pr_url"),
                "created_at": (f or {}).get("created_at"),
                "started_at": (f or {}).get("started_at"),
                "merged_at": (f or {}).get("merged_at"),
                "durations": derive.durations(f),
                "ci": derive.ci_cost(f),
            }
        )

    open_rows = sorted(
        (r for r in rows if r["status"] in OPEN_STATUSES),
        key=lambda r: (STATUS_ORDER[r["status"]], r["priority"], r["id"]),
    )
    done_rows = sorted((r for r in rows if r["status"] == "done"), key=_merged_key)

    metrics = {
        "as_of": as_of.isoformat(),
        "tasks_by_status": {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES},
        "lights": {name: sum(1 for r in open_rows if r["light"] == name) for name in derive.LIGHTS},
        "done_tasks": len(done_rows),
        "durations_seconds": {
            key: derive.summarize([r["durations"][key] for r in done_rows])
            for key in ("agent_seconds", "review_seconds", "lead_seconds")
        },
        "ci_per_done_task": {
            key: derive.summarize([r["ci"][key] if r["ci"] else None for r in done_rows])
            for key in derive.CI_KEYS
        },
        "ci_totals_all_tasks": {
            key: sum(r["ci"][key] for r in rows if r["ci"]) for key in derive.CI_KEYS
        },
        "ci_measured_tasks": sum(1 for r in rows if r["ci"]),
        "progress": progress(rows),
        "done_per_day": done_per_day(rows, as_of, cfg["chart_days"]),
        "knowledge": context.knowledge_metrics(docs, cfg["knowledge_budget"]),
    }

    outputs = {
        "pending.json": _dump(open_rows),
        "history.json": _dump(done_rows),
        "metrics.json": _dump(metrics),
        "context/global/LASTCONTEXT.md": context.global_lastcontext(
            rows, deltas, docs, metrics, cfg
        ),
        "dashboard.html": render.dashboard(
            open_rows, done_rows, rows, metrics, bool(facts), cfg.get("banner")
        ),
    }
    for role in sorted({r["role"] for r in rows}):
        outputs[f"context/roles/{role}/LASTCONTEXT.md"] = context.role_lastcontext(
            role, rows, done_rows, deltas, docs, metrics, cfg
        )
    return outputs
