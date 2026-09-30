from datetime import UTC, datetime

from scripts.afaw_state.render import bar_chart, fmt_age, fmt_num, fmt_seconds, pie_chart


def test_pie_skips_empty_slices_and_labels_every_status():
    svg = pie_chart({"done": 3, "in_progress": 1, "pending": 0, "backlog": 0, "cancelled": 0})
    assert svg.count("<path") == 2
    assert "Done: 3 (75%)" in svg and "In progress: 1 (25%)" in svg
    assert "Pending" not in svg


def test_pie_single_status_is_a_full_circle():
    svg = pie_chart({"done": 4, "in_progress": 0, "pending": 0, "backlog": 0, "cancelled": 0})
    assert "<circle" in svg and "<path" not in svg


def test_pie_with_no_tasks():
    assert "No tasks" in pie_chart(
        {"done": 0, "in_progress": 0, "pending": 0, "backlog": 0, "cancelled": 0}
    )


def test_bar_chart_has_one_bar_per_nonzero_day_with_tooltips():
    days = [
        {"date": "2026-09-27", "done": 2, "cumulative": 2},
        {"date": "2026-09-28", "done": 0, "cumulative": 2},
        {"date": "2026-09-29", "done": 1, "cumulative": 3},
    ]
    svg = bar_chart(days)
    assert svg.count('class="bar"') == 2
    assert "<title>2026-09-27: 2 merged, 2 in total</title>" in svg
    assert "<title>2026-09-28: 0 merged, 2 in total</title>" in svg


def test_bar_chart_labels_only_the_latest_peak():
    days = [
        {"date": f"2026-09-{d}", "done": 1, "cumulative": i + 1}
        for i, d in enumerate(("27", "28", "29"))
    ]
    svg = bar_chart(days)
    assert svg.count('class="val"') == 1
    assert svg.index('class="val"') > svg.index("2026-09-29: 1 merged")


def test_bar_chart_without_data():
    assert "No merged tasks yet" in bar_chart([])


def test_fmt_age():
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    assert fmt_age("2026-09-30T11:30:00Z", now) == "2026-09-30 (30 min ago)"
    assert fmt_age("2026-09-29T18:00:00Z", now) == "2026-09-29 (18 h ago)"
    assert fmt_age("2026-09-20T10:00:00Z", now) == "2026-09-20 (10 d ago)"
    assert fmt_age("2026-09-30T09:00:00-03:00", now) == "2026-09-30 (now)"
    assert fmt_age(None, now) == "unknown"


def test_fmt_seconds():
    assert fmt_seconds(None) == "–"
    assert fmt_seconds(45) == "45 s"
    assert fmt_seconds(90) == "1 min"
    assert fmt_seconds(3 * 3600 + 15 * 60) == "3 h 15 min"
    assert fmt_seconds(86400 + 7200) == "1 d 2 h"


def test_fmt_num():
    assert fmt_num(None) == "–"
    assert fmt_num(4) == "4"
    assert fmt_num(15.5) == "15.5"
    assert fmt_num(4.0) == "4"


def test_dashboard_css_braces_are_balanced() -> None:
    # A lost closing brace turns every later rule into part of the dark-mode media query,
    # and the light-mode page renders unstyled.
    from scripts.afaw_state.render import CSS, SERIES_CSS

    for css in (SERIES_CSS, CSS):
        depth = 0
        for ch in css:
            depth += {"{": 1, "}": -1}.get(ch, 0)
            assert depth >= 0
        assert depth == 0
