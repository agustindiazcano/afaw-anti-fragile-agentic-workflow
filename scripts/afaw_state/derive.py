"""Traffic light, durations and CI cost, derived from task files and measured facts.

Every function here is pure: the same task files, facts and ``as_of`` give the
same result (principle P2). ``as_of`` is an input, never the wall clock.

Facts for one task (produced by ``collect_facts.py``; any key may be missing)::

    {
      "created_at":       ISO 8601, commit that added the task file to main (git)
      "started_at":       ISO 8601, earliest commit of the task's pull request
      "pr_opened_at":     ISO 8601, pull request creation (GitHub API)
      "pr_url":           str
      "first_green_at":   ISO 8601, completion of the first commit whose runs all passed
      "merged_at":        ISO 8601, pull request merge (GitHub API)
      "last_activity_at": ISO 8601, latest commit or CI run on the branch
      "ci_status":        "success" | "failure" | "pending", runs on the latest commit
      "ci": {"runs", "failed_runs", "jobs", "queue_seconds", "job_minutes"}
    }
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .model import CLOSED_STATUSES

LIGHTS = ("red", "yellow", "green", "unknown")
CI_KEYS = ("runs", "failed_runs", "jobs", "queue_seconds", "job_minutes")


def parse_ts(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp that carries a time zone."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without time zone: {value!r}")
    return parsed


def require_ts(value: str) -> datetime:
    """Parse a timestamp that must be present."""
    parsed = parse_ts(value)
    if parsed is None:
        raise ValueError("missing timestamp")
    return parsed


def light(
    task: Mapping[str, Any],
    facts: Mapping[str, Any] | None,
    tasks_by_id: Mapping[str, Mapping[str, Any]],
    as_of: datetime,
    stale_days: int,
) -> tuple[str | None, str]:
    """Return (light, reason) for one task.

    Rules, checked in this order:
      closed or backlog      -> no light
      unresolved blocker     -> red
      in_progress, no facts  -> unknown (never a silent green, principle P6)
      CI failing             -> red
      no activity for more than ``stale_days`` -> yellow
      otherwise              -> green
    """
    status = task["status"]
    if status in CLOSED_STATUSES:
        return None, status
    if status == "backlog":
        return None, "backlog"

    for blocker_id in task.get("blocked_by", []):
        blocker = tasks_by_id.get(blocker_id)
        if blocker is None:
            return "red", f"blocked by unknown task {blocker_id}"
        if blocker["status"] != "done":
            return "red", f"blocked by {blocker_id} ({blocker['status']})"

    if status == "pending":
        return "green", "ready"

    # in_progress
    if not facts:
        return "unknown", "no measured data"
    if facts.get("ci_status") == "failure":
        return "red", "CI failing on the latest commit"
    last = parse_ts(facts.get("last_activity_at"))
    if last is None:
        return "unknown", "no recorded activity"
    idle_days = (as_of - last).total_seconds() / 86400
    if idle_days > stale_days:
        return "yellow", f"no activity for {math.floor(idle_days)} days"
    return "green", "active"


def _span(facts: Mapping[str, Any], start: str, end: str) -> int | None:
    t0, t1 = parse_ts(facts.get(start)), parse_ts(facts.get(end))
    if t0 is None or t1 is None:
        return None
    seconds = int((t1 - t0).total_seconds())
    if seconds < 0:
        raise ValueError(f"inconsistent facts: {end} is before {start}")
    return seconds


def durations(facts: Mapping[str, Any] | None) -> dict[str, int | None]:
    """Wall-clock durations in seconds; None where a timestamp is missing.

    agent_seconds:  started_at -> first_green_at  (work until CI is green)
    review_seconds: pr_opened_at -> merged_at     (human latency, not agent time)
    lead_seconds:   started_at -> merged_at       (total)
    """
    facts = facts or {}
    return {
        "agent_seconds": _span(facts, "started_at", "first_green_at"),
        "review_seconds": _span(facts, "pr_opened_at", "merged_at"),
        "lead_seconds": _span(facts, "started_at", "merged_at"),
    }


def ci_cost(facts: Mapping[str, Any] | None) -> dict[str, int] | None:
    """CI usage for one task, or None if it was not measured."""
    ci = (facts or {}).get("ci")
    if ci is None:
        return None
    missing = [k for k in CI_KEYS if k not in ci]
    if missing:
        raise ValueError(f"incomplete CI facts, missing: {', '.join(missing)}")
    return {k: int(ci[k]) for k in CI_KEYS}


def summarize(values: list[int | None]) -> dict[str, float | int | None]:
    """Median and quartiles of the measured values; missing values are counted, not guessed."""
    measured = sorted(v for v in values if v is not None)
    missing = len(values) - len(measured)
    if not measured:
        return {"n": 0, "missing": missing, "median": None, "p25": None, "p75": None}
    if len(measured) == 1:
        only = measured[0]
        return {"n": 1, "missing": missing, "median": only, "p25": only, "p75": only}
    p25, p50, p75 = statistics.quantiles(measured, n=4, method="inclusive")
    return {"n": len(measured), "missing": missing, "median": p50, "p25": p25, "p75": p75}
