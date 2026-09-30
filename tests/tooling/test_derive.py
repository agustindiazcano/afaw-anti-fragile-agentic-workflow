import pytest

from scripts.afaw_state.derive import ci_cost, durations, light, parse_ts, summarize
from tests.tooling.helpers import make_task

FACTS = {
    "started_at": "2026-09-28T10:00:00Z",
    "first_green_at": "2026-09-28T12:30:00Z",
    "pr_opened_at": "2026-09-28T12:00:00Z",
    "merged_at": "2026-09-29T09:00:00Z",
    "last_activity_at": "2026-09-30T08:00:00Z",
    "ci_status": "success",
}


def run_light(task, facts, tasks=(), as_of=None, stale_days=3):
    from tests.tooling.helpers import AS_OF

    by_id = {t["id"]: t for t in (task, *tasks)}
    return light(task, facts, by_id, as_of or AS_OF, stale_days)


def test_parse_ts_requires_time_zone():
    with pytest.raises(ValueError):
        parse_ts("2026-09-30T10:00:00")
    assert parse_ts(None) is None


@pytest.mark.parametrize("status", ["done", "cancelled", "backlog"])
def test_no_light_for_closed_or_backlog(status):
    lamp, _ = run_light(make_task(status=status, branch="b"), FACTS)
    assert lamp is None


def test_unresolved_blocker_is_red():
    blocker = make_task("task_002", status="in_progress", branch="b")
    lamp, reason = run_light(make_task(blocked_by=["task_002"]), None, [blocker])
    assert (lamp, reason) == ("red", "blocked by task_002 (in_progress)")


def test_unknown_blocker_is_red():
    lamp, reason = run_light(make_task(blocked_by=["task_999"]), None)
    assert (lamp, reason) == ("red", "blocked by unknown task task_999")


def test_done_blocker_does_not_block():
    blocker = make_task("task_002", status="done", branch="b")
    assert run_light(make_task(blocked_by=["task_002"]), None, [blocker]) == ("green", "ready")


def test_in_progress_without_facts_is_unknown_not_green():
    assert run_light(make_task(status="in_progress", branch="b"), None) == (
        "unknown",
        "no measured data",
    )


def test_ci_failure_is_red():
    lamp, _ = run_light(
        make_task(status="in_progress", branch="b"), {**FACTS, "ci_status": "failure"}
    )
    assert lamp == "red"


def test_stale_is_yellow():
    facts = {**FACTS, "last_activity_at": "2026-09-26T11:00:00Z"}
    assert run_light(make_task(status="in_progress", branch="b"), facts) == (
        "yellow",
        "no activity for 4 days",
    )


def test_exactly_at_threshold_is_green():
    facts = {**FACTS, "last_activity_at": "2026-09-27T12:00:00Z"}
    assert run_light(make_task(status="in_progress", branch="b"), facts)[0] == "green"


def test_active_is_green():
    assert run_light(make_task(status="in_progress", branch="b"), FACTS) == ("green", "active")


def test_durations_are_three_distinct_spans():
    assert durations(FACTS) == {
        "agent_seconds": 9000,
        "review_seconds": 75600,
        "lead_seconds": 82800,
    }


def test_durations_missing_timestamps_are_none():
    assert durations({"started_at": FACTS["started_at"]}) == {
        "agent_seconds": None,
        "review_seconds": None,
        "lead_seconds": None,
    }
    assert durations(None)["lead_seconds"] is None


def test_negative_duration_fails_loudly():
    with pytest.raises(ValueError, match="inconsistent facts"):
        durations({"started_at": "2026-09-29T00:00:00Z", "merged_at": "2026-09-28T00:00:00Z"})


def test_ci_cost_requires_all_keys():
    assert ci_cost(None) is None
    full = {"runs": 3, "failed_runs": 1, "jobs": 9, "queue_seconds": 40, "job_minutes": 12}
    assert ci_cost({"ci": full}) == full
    with pytest.raises(ValueError, match="missing: job_minutes"):
        ci_cost({"ci": {k: 1 for k in full if k != "job_minutes"}})


def test_summarize_counts_missing_and_uses_quartiles():
    s = summarize([10, None, 20, 30, 40, None])
    assert s == {"n": 4, "missing": 2, "median": 25.0, "p25": 17.5, "p75": 32.5}


def test_summarize_edge_cases():
    assert summarize([None]) == {"n": 0, "missing": 1, "median": None, "p25": None, "p75": None}
    assert summarize([7]) == {"n": 1, "missing": 0, "median": 7, "p25": 7, "p75": 7}
