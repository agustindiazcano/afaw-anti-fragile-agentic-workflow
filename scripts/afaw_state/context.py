"""LASTCONTEXT.md: the context an agent reads first, generated from sources.

Every section comes from a source with its own life cycle, so nothing needs a
manual snapshot or cleanup:

  Where things stand      open tasks, measured facts, the latest delta of each task
  Waiting on the human    open tasks with owner "human"
  Next, in order          pending agent tasks, most urgent (priority 1) first
  Decisions in force      ADRs with status accepted (index + path, never the text)
  Proposed decisions      ADRs with status proposed
  Active gotchas          gotchas with status active
  Reference documents     paths listed in the configuration

A decision or gotcha leaves the index only for an explicit reason: superseded,
deprecated, resolved, or promoted to a mechanism. Never because of its age.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

HEADER = (
    "Generated from origin/main as of {as_of}. Do not edit: it is rebuilt by "
    "`scripts/build_state.py`. Read order: README, then the reference documents below, then "
    "this file, "
    "then the ADRs and gotchas the task needs."
)


def _as_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return "; ".join(items) if items else None
    return None


def _tags(doc: Mapping[str, Any]) -> list[str]:
    tags = doc["meta"].get("tags", [])
    return tags if isinstance(tags, list) else []


def _doc_line(doc: Mapping[str, Any]) -> str:
    label = "ADR" if doc["kind"] == "adr" else "Gotcha"
    tags = _tags(doc)
    suffix = f" ({', '.join(tags)})" if tags else ""
    return f"- {label} {doc['id']} · {doc['title']} — `{doc['path']}`{suffix}"


def split_knowledge(docs: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    def by_id(items: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return sorted(items, key=lambda d: d["id"])

    adrs = [d for d in docs if d["kind"] == "adr"]
    gotchas = [d for d in docs if d["kind"] == "gotcha"]
    return {
        "in_force": by_id(d for d in adrs if d["meta"].get("status") == "accepted"),
        "proposed": by_id(d for d in adrs if d["meta"].get("status") == "proposed"),
        "gotchas": by_id(d for d in gotchas if d["meta"].get("status") == "active"),
    }


def knowledge_metrics(docs: Sequence[Mapping[str, Any]], budget: int) -> dict[str, Any]:
    parts = split_knowledge(docs)
    active = len(parts["in_force"]) + len(parts["proposed"]) + len(parts["gotchas"])
    return {
        "decisions_in_force": len(parts["in_force"]),
        "decisions_proposed": len(parts["proposed"]),
        "gotchas_active": len(parts["gotchas"]),
        "active_items": active,
        "budget": budget,
        "review_due": active > budget,
    }


def _filter(
    docs: Sequence[Mapping[str, Any]], tags: list[str] | None
) -> Sequence[Mapping[str, Any]]:
    if tags is None:
        return list(docs)
    wanted = set(tags)
    return [d for d in docs if wanted & set(_tags(d))]


def _task_block(row: Mapping[str, Any], delta: Mapping[str, Any] | None) -> list[str]:
    light = {"unknown": "no data", None: "no light"}.get(row["light"], row["light"])
    branch = f", `{row['branch']}`" if row["branch"] else ""
    lines = [
        f"- **{row['id']} · {row['title']}** ({row['role']}{branch}) — {light}: "
        f"{row['light_reason']}"
    ]
    summary = _as_text((delta or {}).get("summary"))
    nxt = _as_text((delta or {}).get("next"))
    if summary:
        lines.append(f"  - Summary: {summary}")
    if nxt:
        lines.append(f"  - Next: {nxt}")
    if row.get("pr_url"):
        lines.append(f"  - PR: {row['pr_url']}")
    return lines


def _queue(rows: Sequence[Mapping[str, Any]], size: int) -> list[str]:
    pending = sorted(
        (r for r in rows if r["status"] == "pending" and r["owner"] == "agent"),
        key=lambda r: (r["priority"], r["id"]),
    )[:size]
    lines = []
    for i, r in enumerate(pending, 1):
        blocked = f" — blocked by {', '.join(r['blocked_by'])}" if r["blocked_by"] else ""
        lines.append(f"{i}. {r['id']} · {r['title']} (P{r['priority']}, {r['role']}){blocked}")
    return lines or ["Nothing pending."]


def _section(title: str, lines: list[str], empty: str) -> list[str]:
    return ["", f"## {title}", *(lines or [empty])]


def global_lastcontext(
    rows: Sequence[Mapping[str, Any]],
    deltas: Mapping[str, Mapping[str, Any]],
    docs: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    cfg: Mapping[str, Any],
) -> str:
    parts = split_knowledge(docs)
    p = metrics["progress"]
    pct = f" ({p['percent']:g}%)" if p["percent"] is not None else ""
    k = metrics["knowledge"]

    state = [f"- Progress: {p['done']} of {p['scope']} tasks done{pct}."]
    if k["review_due"]:
        state.append(
            f"- Knowledge review due: {k['active_items']} active items, budget {k['budget']}."
        )
    in_progress = sorted(
        (r for r in rows if r["status"] == "in_progress" and r["owner"] == "agent"),
        key=lambda r: (r["priority"], r["id"]),
    )
    for r in in_progress:
        state.extend(_task_block(r, deltas.get(r["id"])))
    if not in_progress:
        state.append("- No agent task in progress on main.")

    waiting = []
    for r in sorted(
        (r for r in rows if r["owner"] == "human" and r["status"] in {"pending", "in_progress"}),
        key=lambda r: (r["priority"], r["id"]),
    ):
        since = f" — since {r['created_at'][:10]}" if r.get("created_at") else ""
        waiting.append(f"- {r['id']} · {r['title']} (P{r['priority']}){since}")

    refs = [f"- `{path}`" for path in cfg.get("reference_docs", [])]

    lines = ["# Last context", "", HEADER.format(as_of=metrics["as_of"])]
    lines += _section("Where things stand", state, "")
    lines += _section("Waiting on the human", waiting, "Nothing.")
    lines += _section("Next, in order", _queue(rows, cfg["next_size"]), "")
    lines += _section(
        "Decisions in force", [_doc_line(d) for d in parts["in_force"]], "None recorded."
    )
    lines += _section("Proposed decisions", [_doc_line(d) for d in parts["proposed"]], "None.")
    lines += _section("Active gotchas", [_doc_line(d) for d in parts["gotchas"]], "None.")
    lines += _section(
        "Reference documents", refs, "None configured (`reference_docs` in `state/config.json`)."
    )
    return "\n".join(lines) + "\n"


def role_lastcontext(
    role: str,
    rows: Sequence[Mapping[str, Any]],
    done_rows: Sequence[Mapping[str, Any]],
    deltas: Mapping[str, Mapping[str, Any]],
    docs: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    cfg: Mapping[str, Any],
) -> str:
    tags = cfg.get("role_tags", {}).get(role)
    parts = split_knowledge(_filter(docs, tags))
    mine = [r for r in rows if r["role"] == role]

    in_progress = []
    for r in sorted(
        (r for r in mine if r["status"] == "in_progress" and r["owner"] == "agent"),
        key=lambda r: (r["priority"], r["id"]),
    ):
        in_progress.extend(_task_block(r, deltas.get(r["id"])))

    recent = []
    for r in [r for r in reversed(done_rows) if r["role"] == role][: cfg["lastcontext_size"]]:
        merged = f" — merged {r['merged_at'][:10]}" if r.get("merged_at") else ""
        recent.append(f"- {r['id']} · {r['title']}{merged}")
        summary = _as_text(deltas.get(r["id"], {}).get("summary"))
        if summary:
            recent.append(f"  - Summary: {summary}")

    scope = (
        f"tags {', '.join(tags)}" if tags is not None else "all tags (no `role_tags` for this role)"
    )
    lines = [
        f"# Last context — role {role}",
        "",
        HEADER.format(as_of=metrics["as_of"]),
        "",
        f"Knowledge filtered to {scope}. The global file has everything.",
    ]
    lines += _section("In progress", in_progress, "Nothing in progress.")
    lines += _section("Next, in order", _queue(mine, cfg["next_size"]), "")
    lines += _section("Recently merged", recent, "Nothing merged yet.")
    lines += _section(
        "Decisions in force", [_doc_line(d) for d in parts["in_force"]], "None for this role."
    )
    lines += _section(
        "Active gotchas", [_doc_line(d) for d in parts["gotchas"]], "None for this role."
    )
    return "\n".join(lines) + "\n"
