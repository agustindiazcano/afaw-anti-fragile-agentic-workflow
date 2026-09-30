"""Static, self-contained HTML dashboard. No scripts, no external requests."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from typing import Any

from .derive import parse_ts

COLUMNS = (("in_progress", "In progress"), ("pending", "Pending"), ("backlog", "Backlog"))
LIGHT_LABEL = {"red": "Red", "yellow": "Yellow", "green": "Green", "unknown": "No data"}

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e2e2dc;--red:#c8372d;
  --yellow:#b98900;--green:#2f8a4c;--unknown:#8a8a84}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--card:#21211f;--ink:#ecece8;
  --muted:#a3a39c;--line:#34342f;--red:#ec6a5e;--yellow:#e3b53c;--green:#5cc27b;
  --unknown:#8a8a84}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1200px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:32px 0 12px}
.meta{color:var(--muted);margin:0 0 20px}
.warn{border:1px solid var(--yellow);border-radius:8px;padding:10px 12px;margin:0 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.tile b{display:block;font-size:22px}
.tile span{color:var(--muted)}
.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.col{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.col h3{font-size:14px;margin:0 0 10px}
.col h3 small{color:var(--muted);font-weight:400}
.task{border-top:1px solid var(--line);padding:10px 0}
.task:first-of-type{border-top:0}
.task .id{color:var(--muted);font-size:12px}
.task .t{font-weight:600}
.task .f{color:var(--muted);font-size:12px}
.lamp{display:inline-flex;align-items:center;gap:6px;font-size:12px}
.lamp i{width:10px;height:10px;border-radius:50%;display:inline-block}
.red i{background:var(--red)}
.yellow i{background:var(--yellow)}
.green i{background:var(--green)}
.unknown i{background:var(--unknown)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);
  border-radius:8px}
th,td{text-align:left;padding:8px 10px;border-top:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600;border-top:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:inherit}
.empty{color:var(--muted)}
.nw{white-space:nowrap}
.progress{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:14px 16px;margin:0 0 12px}
.progress .pct{font-size:30px;font-weight:700;line-height:1.1}
.progress .note{color:var(--muted)}
.meter{height:10px;border-radius:5px;background:var(--track);margin:10px 0 4px;overflow:hidden}
.meter span{display:block;height:100%;background:var(--series-1);border-radius:5px}
.charts{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0 0}
details.chart{background:var(--card);border:1px solid var(--line);border-radius:8px;
  flex:1 1 320px}
details.chart summary{cursor:pointer;padding:10px 14px;font-weight:600;list-style:none}
details.chart summary::-webkit-details-marker{display:none}
details.chart summary::before{content:"\\25B8  ";color:var(--muted)}
details.chart[open] summary::before{content:"\\25BE  "}
details.chart .body{padding:0 14px 14px}
.pie{display:flex;flex-wrap:wrap;align-items:center;gap:16px}
.pie svg{width:180px;height:180px;flex:none}
.legend{list-style:none;margin:0;padding:0}
.legend li{display:flex;align-items:center;gap:8px;margin:4px 0}
.legend i{width:12px;height:12px;border-radius:3px;display:inline-block;flex:none}
.s-done{fill:var(--series-1);background:var(--series-1)}
.s-in_progress{fill:var(--series-2);background:var(--series-2)}
.s-pending{fill:var(--series-3);background:var(--series-3)}
.s-backlog{fill:var(--series-4);background:var(--series-4)}
.s-cancelled{fill:var(--series-5);background:var(--series-5)}
.slice{stroke:var(--card);stroke-width:2}
.bars svg{width:100%;height:auto;display:block}
.bars .grid{stroke:var(--line);stroke-width:1}
.bars .axis{fill:var(--muted);font-size:10px}
.bars .bar{fill:var(--series-1)}
.bars .val{fill:var(--ink);font-size:10px;font-weight:600}
.bars .hit{fill:transparent}
.bars .col:hover .hit{fill:var(--line);fill-opacity:.5}
.chart .note{color:var(--muted);font-size:12px;margin:6px 0 0}
"""

SERIES_CSS = """
:root{--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--series-4:#eda100;
  --series-5:#e87ba4;--track:#cde2fb}
@media (prefers-color-scheme:dark){:root{--series-1:#3987e5;--series-2:#d95926;
  --series-3:#199e70;--series-4:#c98500;--series-5:#d55181;--track:#184f95}}
"""

STATUS_LABELS = (
    ("done", "Done"),
    ("in_progress", "In progress"),
    ("pending", "Pending"),
    ("backlog", "Backlog"),
    ("cancelled", "Cancelled"),
)


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%"


def pie_chart(counts: Mapping[str, int]) -> str:
    """Pie of tasks by status, with a legend that carries every value in text."""
    total = sum(counts.values())
    if total == 0:
        return '<p class="empty">No tasks.</p>'
    cx = cy = 90.0
    r = 86.0
    shapes, legend = [], []
    present = [(key, label, counts[key]) for key, label in STATUS_LABELS if counts.get(key)]
    angle = -math.pi / 2
    for key, label, n in present:
        text = f"{label}: {n} ({_pct(n, total)})"
        legend.append(f'<li><i class="s-{key}"></i>{escape(text)}</li>')
        if n == total:
            shapes.append(
                f'<circle class="slice s-{key}" cx="{cx}" cy="{cy}" r="{r}"><title>'
                f'{text}</title></circle>'
            )
            continue
        sweep = 2 * math.pi * n / total
        x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        angle += sweep
        x2, y2 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        shapes.append(
            f'<path class="slice s-{key}" d="M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 '
            f'{large} 1 {x2:.2f},{y2:.2f} Z">'
            f"<title>{text}</title></path>"
        )
    svg = (
        '<svg viewBox="0 0 180 180" role="img" aria-label="Tasks by status">'
        + "".join(shapes)
        + "</svg>"
    )
    return (
        f'<div class="pie">{svg}<ul class="legend">{"".join(legend)}</ul></div>'
        f'<p class="note">Share of all {total} tasks, cancelled included; progress above '
        'excludes them.</p>'
    )


def _bar_path(x: float, y: float, w: float, h: float) -> str:
    """Bar anchored to the baseline with rounded top corners."""
    r = min(4.0, w / 2, h)
    return (
        f"M{x:.2f},{y + h:.2f} L{x:.2f},{y + r:.2f} Q{x:.2f},{y:.2f} {x + r:.2f},{y:.2f} "
        f"L{x + w - r:.2f},{y:.2f} Q{x + w:.2f},{y:.2f} {x + w:.2f},{y + r:.2f} "
        f"L{x + w:.2f},{y + h:.2f} Z"
    )


def bar_chart(days: Sequence[Mapping[str, Any]]) -> str:
    """Tasks merged per UTC day. Native SVG tooltips; no scripts."""
    if not days or not any(d["done"] for d in days):
        return '<p class="empty">No merged tasks yet.</p>'
    n = len(days)
    left, right, top, bottom = 28.0, 8.0, 16.0, 24.0
    step = 20.0
    width = left + right + step * n
    height = 180.0
    plot_h = height - top - bottom
    peak = int(max(d["done"] for d in days))
    tick = max(1, math.ceil(peak / 4))
    y_max = tick * math.ceil(peak / tick)

    def y_of(v: float) -> float:
        return top + plot_h * (1 - v / y_max)

    parts = []
    for v in range(0, y_max + 1, tick):
        y = y_of(v)
        parts.append(
            f'<line class="grid" x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}"/>'
        )
        parts.append(
            f'<text class="axis" x="{left - 6}" y="{y + 3:.2f}" text-anchor="end">{v}</text>'
        )

    label_every = max(1, math.ceil(n / 8))
    bw = step * 0.62
    # One direct label only: the most recent day at the peak.
    peak_index = max(i for i, d in enumerate(days) if d["done"] == peak)
    for i, d in enumerate(days):
        x0 = left + step * i
        title = f"{d['date']}: {d['done']} merged, {d['cumulative']} in total"
        col = [
            f'<g class="col"><title>{title}</title>',
            f'<rect class="hit" x="{x0:.2f}" y="{top}" width="{step}" height="{plot_h}"/>',
        ]
        if d["done"]:
            y = y_of(d["done"])
            path = _bar_path(x0 + (step - bw) / 2, y, bw, top + plot_h - y)
            col.append(f'<path class="bar" d="{path}"/>')
            if i == peak_index:
                col.append(
                    f'<text class="val" x="{x0 + step / 2:.2f}" y="{y - 4:.2f}" '
                    f'text-anchor="middle">{d["done"]}</text>'
                )
        col.append("</g>")
        parts.append("".join(col))
        if i % label_every == 0 or i == n - 1:
            parts.append(
                f'<text class="axis" x="{x0 + step / 2:.2f}" y="{height - 8}" '
                f'text-anchor="middle">{d["date"][5:]}</text>'
            )
    total = days[-1]["cumulative"]
    svg = (
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="Tasks merged per day">'
        + "".join(parts)
        + "</svg>"
    )
    return (
        f'<div class="bars">{svg}<p class="note">Last {n} days, UTC. '
        f"{total} tasks merged in total. Hover a day for its count.</p></div>"
    )


def _progress(metrics: Mapping[str, Any]) -> str:
    p = metrics["progress"]
    if p["percent"] is None:
        return (
            '<section class="progress"><div class="pct">–</div>'
            '<div class="note">No tasks in scope.</div></section>'
        )
    return (
        f'<section class="progress"><div class="pct">{p["percent"]:g}%</div>'
        f'<div class="meter" role="img" aria-label="{p["percent"]:g}% done"><span '
        f'style="width:{p["percent"]}%"></span></div>'
        f'<div class="note">{p["done"]} of {p["scope"]} tasks done. Cancelled tasks are excluded; '
        "every task counts the same, whatever its size.</div></section>"
    )


def _charts(metrics: Mapping[str, Any]) -> str:
    return (
        '<div class="charts">'
        f'<details class="chart"><summary>Tasks by status (pie)</summary><div class="body">'
        f"{pie_chart(metrics['tasks_by_status'])}</div></details>"
        f'<details class="chart"><summary>Tasks merged per day (bars)</summary><div class="body">'
        f"{bar_chart(metrics['done_per_day'])}</div></details>"
        "</div>"
    )


def fmt_seconds(value: float | int | None) -> str:
    if value is None:
        return "–"
    seconds = int(round(value))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        return f"{seconds // 3600} h {seconds % 3600 // 60} min"
    return f"{seconds // 86400} d {seconds % 86400 // 3600} h"


def fmt_num(value: float | int | None) -> str:
    if value is None:
        return "–"
    return f"{value:g}" if isinstance(value, float) else str(value)


def fmt_age(ts: str | None, as_of: datetime) -> str:
    """UTC date plus age relative to ``as_of`` (never the wall clock)."""
    parsed = parse_ts(ts)
    if parsed is None:
        return "unknown"
    date = parsed.astimezone(UTC).date().isoformat()
    seconds = int((as_of - parsed).total_seconds())
    if seconds < 60:
        return f"{date} (now)"
    if seconds < 3600:
        return f"{date} ({seconds // 60} min ago)"
    if seconds < 86400:
        return f"{date} ({seconds // 3600} h ago)"
    return f"{date} ({seconds // 86400} d ago)"


def _lamp(light: str | None, reason: str) -> str:
    if light is None:
        return ""
    return (
        f'<span class="lamp {light}" title="{escape(reason)}"><i></i>'
        f"{LIGHT_LABEL[light]} · {escape(reason)}</span>"
    )


def _card(row: Mapping[str, Any], as_of: datetime) -> str:
    blockers = ", ".join(row["blocked_by"])
    dates = f'<span class="nw">Created {fmt_age(row["created_at"], as_of)}</span>'
    if row["status"] == "in_progress":
        dates += f' · <span class="nw">Started {fmt_age(row["started_at"], as_of)}</span>'
    parts = [
        f'<div class="task"><div class="id">{escape(row["id"])} · {escape(row["role"])} · '
        f'{escape(row["type"])}'
        + (" · human" if row["owner"] == "human" else "")
        + "</div>",
        f'<div class="t">{escape(row["title"])}</div>',
        f'<div class="f">Priority {row["priority"]} · Difficulty '
        f'{row["difficulty_estimate"]} (estimate)'
        + (f" · Blocked by {escape(blockers)}" if blockers else "")
        + "</div>",
        f'<div class="f">{dates}</div>',
        _lamp(row["light"], row["light_reason"]),
        "</div>",
    ]
    return "".join(parts)


def _board(open_rows: Sequence[Mapping[str, Any]], as_of: datetime) -> str:
    cols = []
    for status, label in COLUMNS:
        items = [r for r in open_rows if r["status"] == status]
        body = "".join(_card(r, as_of) for r in items) or '<p class="empty">Nothing here.</p>'
        cols.append(
            f'<section class="col"><h3>{label} <small>{len(items)}</small></h3>{body}</section>'
        )
    return f'<div class="board">{"".join(cols)}</div>'


def _history(done_rows: Sequence[Mapping[str, Any]]) -> str:
    if not done_rows:
        return '<p class="empty">No merged tasks yet.</p>'
    head = (
        "<tr><th>Task</th><th>Title</th><th>Role</th><th>Merged</th>"
        '<th class="num">Agent</th><th class="num">Review</th><th class="num">Lead</th>'
        '<th class="num">CI runs</th><th class="num">Queue</th><th class="num">Job min</th>'
        '<th>PR</th></tr>'
    )
    body = []
    for r in reversed(done_rows):
        d, ci = r["durations"], r["ci"] or {}
        pr = f'<a href="{escape(r["pr_url"])}">link</a>' if r["pr_url"] else "–"
        body.append(
            f"<tr><td>{escape(r['id'])}</td><td>{escape(r['title'])}</td><td>{escape(r['role'])}</td>"
            f"<td>{escape(r['merged_at'] or '–')}</td>"
            f'<td class="num">{fmt_seconds(d["agent_seconds"])}</td>'
            f'<td class="num">{fmt_seconds(d["review_seconds"])}</td>'
            f'<td class="num">{fmt_seconds(d["lead_seconds"])}</td>'
            f'<td class="num">{fmt_num(ci.get("runs"))}</td>'
            f'<td class="num">{fmt_seconds(ci.get("queue_seconds"))}</td>'
            f'<td class="num">{fmt_num(ci.get("job_minutes"))}</td><td>{pr}</td></tr>'
        )
    return f'<div class="scroll"><table>{head}{"".join(body)}</table></div>'


def _summary_table(metrics: Mapping[str, Any]) -> str:
    rows = []
    labels = {
        "agent_seconds": "Agent time (start → first green CI)",
        "review_seconds": "Review latency (PR opened → merged)",
        "lead_seconds": "Lead time (start → merged)",
    }
    for key, label in labels.items():
        s = metrics["durations_seconds"][key]
        rows.append(
            f'<tr><td>{label}</td><td class="num">{s["n"]}</td><td class="num">{s["missing"]}</td>'
            f'<td class="num">{fmt_seconds(s["p25"])}</td><td class="num">'
            f'{fmt_seconds(s["median"])}</td>'
            f'<td class="num">{fmt_seconds(s["p75"])}</td></tr>'
        )
    ci_labels = {
        "runs": ("CI runs", fmt_num),
        "failed_runs": ("Failed CI runs", fmt_num),
        "queue_seconds": ("CI queue time", fmt_seconds),
        "job_minutes": ("CI job minutes (rounded up per job)", fmt_num),
    }
    for key, (label, fmt) in ci_labels.items():
        s = metrics["ci_per_done_task"][key]
        rows.append(
            f'<tr><td>{label}</td><td class="num">{s["n"]}</td><td class="num">{s["missing"]}</td>'
            f'<td class="num">{fmt(s["p25"])}</td><td class="num">{fmt(s["median"])}</td>'
            f'<td class="num">{fmt(s["p75"])}</td></tr>'
        )
    head = (
        '<tr><th>Per merged task</th><th class="num">n</th><th class="num">Missing</th>'
        '<th class="num">P25</th><th class="num">Median</th><th class="num">P75</th></tr>'
    )
    return f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>'


def dashboard(
    open_rows: Sequence[Mapping[str, Any]],
    done_rows: Sequence[Mapping[str, Any]],
    all_rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    has_facts: bool,
) -> str:
    counts = metrics["tasks_by_status"]
    lights = metrics["lights"]
    totals = metrics["ci_totals_all_tasks"]
    tiles = [
        (counts["in_progress"], "In progress"),
        (counts["pending"], "Pending"),
        (counts["backlog"], "Backlog"),
        (counts["done"], "Done"),
        (lights["red"], "Red"),
        (lights["yellow"], "Yellow"),
        (totals["runs"], "CI runs, all tasks"),
        (totals["job_minutes"], "CI job minutes, all tasks"),
    ]
    tiles_html = "".join(
        f'<div class="tile"><b>{v}</b><span>{label}</span></div>' for v, label in tiles
    )
    k = metrics["knowledge"]
    knowledge = (
        f'<p class="warn">Knowledge review due: {k["active_items"]} active decisions and gotchas, '
        f"budget {k['budget']}. Promote, resolve or supersede items in a pull request.</p>"
        if k["review_due"]
        else f'<p class="meta">Knowledge: {k["decisions_in_force"]} decisions in force, '
        f"{k['decisions_proposed']} proposed, {k['gotchas_active']} active gotchas "
        f"(budget {k['budget']}).</p>"
    )
    warn = (
        ""
        if has_facts
        else '<p class="warn">No measured facts were supplied. Lights for tasks in progress show '
        '"No data", and durations and CI cost are empty.</p>'
    )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Project Status</title><style>{SERIES_CSS}{CSS}</style></head><body><main>"
        "<h1>Project status</h1>"
        f'<p class="meta">Derived from origin/main as of {escape(metrics["as_of"])}. '
        f"{len(all_rows)} tasks; CI measured for {metrics['ci_measured_tasks']}.</p>"
        f'{warn}{knowledge}{_progress(metrics)}<div class="tiles">{tiles_html}</div>'
        f'{_charts(metrics)}'
        f"<h2>Board</h2>{_board(open_rows, datetime.fromisoformat(metrics['as_of']))}"
        f"<h2>Timing and CI cost</h2>{_summary_table(metrics)}"
        f"<h2>Done</h2>{_history(done_rows)}"
        "</main></body></html>\n"
    )
