import json

import pytest

from scripts.afaw_state.views import StateError, build
from tests.tooling.helpers import AS_OF, make_task

CI = {"runs": 3, "failed_runs": 1, "jobs": 6, "queue_seconds": 90, "job_minutes": 14}


def sample():
    tasks = [
        make_task("task_001", status="done", branch="feat/a", title="First"),
        make_task("task_002", status="done", branch="feat/b", role="frontend", title="Second"),
        make_task("task_003", status="in_progress", branch="feat/c", priority=5),
        make_task("task_004", status="pending", blocked_by=["task_003"], priority=4),
        make_task("task_005", status="backlog", title="<script>alert(1)</script>"),
    ]
    facts = {
        "task_001": {
            "started_at": "2026-09-20T10:00:00Z",
            "first_green_at": "2026-09-20T11:00:00Z",
            "pr_opened_at": "2026-09-20T11:00:00Z",
            "merged_at": "2026-09-21T10:00:00Z",
            "pr_url": "https://github.com/o/r/pull/1",
            "ci": CI,
        },
        "task_002": {
            "started_at": "2026-09-22T10:00:00Z",
            "first_green_at": "2026-09-22T14:00:00Z",
            "pr_opened_at": "2026-09-22T13:00:00Z",
            "merged_at": "2026-09-22T15:00:00Z",
            "ci": {**CI, "runs": 5, "job_minutes": 20},
        },
        "task_003": {"last_activity_at": "2026-09-30T09:00:00Z", "ci_status": "failure", "ci": CI},
    }
    deltas = {
        "task_001": {"files_touched": ["src/a.py"]},
        "task_002": {"files_touched": ["web/b.ts"]},
    }
    return tasks, deltas, facts


def test_outputs_and_order():
    tasks, deltas, facts = sample()
    out = build(tasks, deltas, facts, None, AS_OF)
    assert set(out) == {
        "pending.json",
        "history.json",
        "metrics.json",
        "dashboard.html",
        "context/global/LASTCONTEXT.md",
        "context/roles/backend/LASTCONTEXT.md",
        "context/roles/frontend/LASTCONTEXT.md",
    }
    pending = json.loads(out["pending.json"])
    assert [r["id"] for r in pending] == ["task_003", "task_004", "task_005"]
    assert pending[0]["light"] == "red"
    assert pending[1]["light_reason"] == "blocked by task_003 (in_progress)"
    history = json.loads(out["history.json"])
    assert [r["id"] for r in history] == ["task_001", "task_002"]


def test_metrics_cover_done_tasks_and_totals_cover_all():
    tasks, deltas, facts = sample()
    metrics = json.loads(build(tasks, deltas, facts, None, AS_OF)["metrics.json"])
    assert metrics["tasks_by_status"] == {
        "backlog": 1,
        "pending": 1,
        "in_progress": 1,
        "done": 2,
        "cancelled": 0,
    }
    assert metrics["durations_seconds"]["agent_seconds"]["median"] == 9000
    assert metrics["ci_per_done_task"]["runs"]["median"] == 4
    assert metrics["ci_totals_all_tasks"]["runs"] == 3 + 5 + 3
    assert metrics["ci_totals_all_tasks"]["job_minutes"] == 14 + 20 + 14
    assert metrics["ci_measured_tasks"] == 3


def test_build_is_deterministic_regardless_of_input_order():
    tasks, deltas, facts = sample()
    a = build(tasks, deltas, facts, None, AS_OF)
    b = build(list(reversed(tasks)), deltas, facts, None, AS_OF)
    assert a == b


def test_invalid_state_is_rejected_with_all_errors():
    tasks = [
        make_task(merged_at="2026-01-01T00:00:00Z"),
        make_task(),
        make_task("task_002", priority=9),
    ]
    with pytest.raises(StateError) as exc:
        build(tasks, {}, None, None, AS_OF)
    message = str(exc.value)
    assert "derived field must not be declared: merged_at" in message
    assert "task_001: duplicate task id" in message
    assert "task_002: $.priority: 9 is greater than the maximum 5" in message


def test_dashboard_escapes_and_labels_lights_in_text():
    tasks, deltas, facts = sample()
    html = build(tasks, deltas, facts, None, AS_OF)["dashboard.html"]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "Red · CI failing on the latest commit" in html
    assert "Difficulty 2 (estimate)" in html
    assert "<script" not in html.replace("&lt;script", "")


def test_dashboard_shows_creation_and_start_age():
    tasks = [
        make_task("task_001", status="pending"),
        make_task("task_002", status="in_progress", branch="feat/b"),
        make_task("task_003", status="backlog"),
    ]
    facts = {
        "task_001": {"created_at": "2026-09-20T10:00:00Z"},
        "task_002": {
            "created_at": "2026-09-25T12:00:00Z",
            "started_at": "2026-09-29T18:00:00Z",
            "last_activity_at": "2026-09-30T11:00:00Z",
        },
    }
    out = build(tasks, {}, facts, None, AS_OF)
    html = out["dashboard.html"]
    assert '<span class="nw">Created 2026-09-20 (10 d ago)</span>' in html
    assert (
        '<span class="nw">Created 2026-09-25 (5 d ago)</span> · '
        '<span class="nw">Started 2026-09-29 (18 h ago)</span>'
    ) in html
    assert "Created unknown" in html
    row = json.loads(out["pending.json"])[0]
    assert (
        row["created_at"] == "2026-09-25T12:00:00Z" and row["started_at"] == "2026-09-29T18:00:00Z"
    )


def test_progress_is_done_over_scope_excluding_cancelled():
    tasks = [
        make_task("task_001", status="done", branch="a"),
        make_task("task_002", status="done", branch="b"),
        make_task("task_003", status="in_progress", branch="c"),
        make_task("task_004", status="backlog"),
        make_task("task_005", status="cancelled"),
    ]
    metrics = json.loads(build(tasks, {}, None, None, AS_OF)["metrics.json"])
    assert metrics["progress"] == {"done": 2, "scope": 4, "percent": 50.0}


def test_progress_with_empty_scope_is_none():
    metrics = json.loads(
        build([make_task(status="cancelled")], {}, None, None, AS_OF)["metrics.json"]
    )
    assert metrics["progress"] == {"done": 0, "scope": 0, "percent": None}


def test_done_per_day_fills_gaps_and_accumulates():
    tasks = [
        make_task("task_001", status="done", branch="a"),
        make_task("task_002", status="done", branch="b"),
        make_task("task_003", status="done", branch="c"),
        make_task("task_004", status="pending"),
    ]
    facts = {
        "task_001": {"created_at": "2026-09-26T10:00:00Z", "merged_at": "2026-09-27T10:00:00Z"},
        "task_002": {"merged_at": "2026-09-27T23:30:00Z"},
        "task_003": {"merged_at": "2026-09-29T08:00:00Z"},
        "task_004": {"created_at": "2026-09-28T00:00:00Z"},
    }
    days = json.loads(build(tasks, {}, facts, None, AS_OF)["metrics.json"])["done_per_day"]
    assert days == [
        {"date": "2026-09-26", "done": 0, "cumulative": 0},
        {"date": "2026-09-27", "done": 2, "cumulative": 2},
        {"date": "2026-09-28", "done": 0, "cumulative": 2},
        {"date": "2026-09-29", "done": 1, "cumulative": 3},
        {"date": "2026-09-30", "done": 0, "cumulative": 3},
    ]


def test_done_per_day_keeps_only_the_last_window():
    tasks = [make_task("task_001", status="done", branch="a")]
    facts = {
        "task_001": {"created_at": "2026-01-01T00:00:00Z", "merged_at": "2026-01-02T00:00:00Z"}
    }
    days = json.loads(build(tasks, {}, facts, {"chart_days": 10}, AS_OF)["metrics.json"])[
        "done_per_day"
    ]
    assert len(days) == 10
    assert days[0] == {"date": "2026-09-21", "done": 0, "cumulative": 1}
    assert days[-1]["date"] == "2026-09-30"


def test_done_per_day_empty_without_dates():
    metrics = json.loads(build([make_task()], {}, None, None, AS_OF)["metrics.json"])
    assert metrics["done_per_day"] == []


def test_dashboard_has_progress_and_charts_without_scripts():
    tasks, deltas, facts = sample()
    html = build(tasks, deltas, facts, None, AS_OF)["dashboard.html"]
    assert "40%" in html  # 2 done of 5 open or done tasks; none cancelled
    assert '<details class="chart"><summary>Tasks by status (pie)</summary>' in html
    assert '<details class="chart"><summary>Tasks merged per day (bars)</summary>' in html
    assert "<svg" in html and "<script" not in html.replace("&lt;script", "")


def test_dashboard_warns_when_no_facts():
    tasks, deltas, _ = sample()
    html = build(tasks, deltas, None, None, AS_OF)["dashboard.html"]
    assert "No measured facts were supplied" in html
    assert "No data · no measured data" in html


def test_banner_is_shown_escaped_when_configured() -> None:
    tasks, deltas, facts = sample()
    html = build(tasks, deltas, facts, {"banner": "Demo <mock> data"}, AS_OF)["dashboard.html"]
    assert '<p class="banner">Demo &lt;mock&gt; data</p>' in html
    plain = build(tasks, deltas, facts, None, AS_OF)["dashboard.html"]
    assert 'class="banner"' not in plain
