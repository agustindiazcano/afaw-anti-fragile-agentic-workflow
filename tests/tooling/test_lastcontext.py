import json

import pytest

from scripts.afaw_state.knowledge import parse_doc
from scripts.afaw_state.views import StateError, build
from tests.tooling.helpers import AS_OF, make_task
from tests.tooling.test_knowledge import ADR, GOTCHA, OLD


def knowledge():
    promoted = (
        GOTCHA.replace("status: active", "status: promoted")
        .replace("tags:", "promoted_to: scripts/plan.sh\ntags:")
        .replace("# Terraform plan hangs silently", "# Plan needs demo_up=false")
    )
    db_gotcha = GOTCHA.replace("tags: [infra, terraform]", "tags: [db]").replace(
        "# Terraform plan hangs silently", "# updated_at uses clock_timestamp()"
    )
    return [
        parse_doc("docs/adr/0003-both-gemini.md", OLD),
        parse_doc("docs/adr/0007-judges-asymmetric.md", ADR),
        parse_doc(
            "docs/adr/0008-cents.md",
            ADR.replace("status: accepted", "status: proposed")
            .replace("supersedes: [0003]\n", "")
            .replace("# Judges stay asymmetric", "# Money in cents"),
        ),
        parse_doc("docs/gotchas/0002-terraform-429.md", GOTCHA),
        parse_doc("docs/gotchas/0004-demo-up.md", promoted),
        parse_doc("docs/gotchas/0005-clock.md", db_gotcha),
    ]


def sample():
    tasks = [
        make_task("task_001", status="done", branch="feat/a", title="Claim proposal model"),
        make_task(
            "task_002",
            status="in_progress",
            branch="feat/b",
            title="Wire proposer into worker",
            priority=5,
        ),
        make_task("task_003", status="pending", title="Promptfoo eval", priority=4),
        make_task(
            "task_004",
            status="pending",
            title="Open the PR for Phase 1.E",
            owner="human",
            priority=5,
        ),
        make_task(
            "task_005",
            status="pending",
            title="Branch protection on main",
            owner="human",
            priority=3,
            role="infra",
        ),
        make_task("task_006", status="backlog", title="Load test", role="infra"),
    ]
    deltas = {
        "task_001": {
            "files_touched": ["src/a.py"],
            "summary": "ClaimProposal with a strict schema.",
            "next": "Wire it into the worker.",
        },
        "task_002": {
            "files_touched": ["src/w.py"],
            "summary": "Steps 1-2 of 7 done.",
            "next": ["Server-side re-validation", "Self-correction loop"],
        },
    }
    facts = {
        "task_001": {
            "merged_at": "2026-09-28T10:00:00Z",
            "pr_url": "https://github.com/o/r/pull/1",
        },
        "task_002": {
            "last_activity_at": "2026-09-30T10:00:00Z",
            "ci_status": "success",
            "pr_url": "https://github.com/o/r/pull/2",
        },
        "task_004": {"created_at": "2026-09-25T12:00:00Z"},
    }
    return tasks, deltas, facts


def lastcontext(config=None):
    tasks, deltas, facts = sample()
    return build(tasks, deltas, facts, config, AS_OF, knowledge())


def test_global_lastcontext_sections_in_order():
    md = lastcontext()["context/global/LASTCONTEXT.md"]
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Where things stand",
        "## Waiting on the human",
        "## Next, in order",
        "## Decisions in force",
        "## Proposed decisions",
        "## Active gotchas",
        "## Reference documents",
    ]
    assert md.startswith("# Last context\n")
    assert "Generated from origin/main as of 2026-09-30T12:00:00+00:00. Do not edit" in md


def test_in_progress_task_carries_its_summary_and_next_steps():
    md = lastcontext()["context/global/LASTCONTEXT.md"]
    assert "- **task_002 · Wire proposer into worker** (backend, `feat/b`) — green: active" in md
    assert "  - Summary: Steps 1-2 of 7 done." in md
    assert "  - Next: Server-side re-validation; Self-correction loop" in md
    assert "  - PR: https://github.com/o/r/pull/2" in md


def test_human_tasks_are_separate_from_the_agent_queue():
    md = lastcontext()["context/global/LASTCONTEXT.md"]
    waiting = md.split("## Waiting on the human")[1].split("## ")[0]
    queue = md.split("## Next, in order")[1].split("## ")[0]
    assert "task_004 · Open the PR for Phase 1.E" in waiting
    assert "task_005 · Branch protection on main" in waiting
    assert "task_004" not in queue
    assert "1. task_003 · Promptfoo eval (P4, backend)" in queue
    assert "task_006" not in queue  # backlog is not the queue


def test_knowledge_index_links_documents_and_skips_closed_ones():
    md = lastcontext()["context/global/LASTCONTEXT.md"]
    assert (
        "- ADR 0007 · Judges stay asymmetric — `docs/adr/0007-judges-asymmetric.md` (llm, judges)"
        in md
    )
    assert "ADR 0003" not in md  # superseded
    assert (
        "- ADR 0008 · Money in cents — `docs/adr/0008-cents.md`"
        in md.split("## Proposed decisions")[1]
    )
    assert (
        "- Gotcha 0002 · Terraform plan hangs silently — "
        "`docs/gotchas/0002-terraform-429.md` (infra, terraform)"
        in md
    )
    assert "Plan needs demo_up=false" not in md  # promoted to a mechanism


def test_reference_documents_come_from_config():
    md = lastcontext({"reference_docs": ["docs/architecture/overview.md"]})[
        "context/global/LASTCONTEXT.md"
    ]
    assert "- `docs/architecture/overview.md`" in md


def test_role_lastcontext_filters_knowledge_by_role_tags():
    out = lastcontext({"role_tags": {"backend": ["llm", "db"]}})
    backend = out["context/roles/backend/LASTCONTEXT.md"]
    infra = out["context/roles/infra/LASTCONTEXT.md"]
    assert "ADR 0007" in backend and "Gotcha 0005" in backend
    assert "Gotcha 0002" not in backend  # infra/terraform only
    assert "Gotcha 0002" in infra  # no role_tags for infra: everything
    assert "task_001 · Claim proposal model" in backend.split("## Recently merged")[1]
    assert "ClaimProposal with a strict schema." in backend


def test_knowledge_budget_is_measured():
    metrics = json.loads(lastcontext({"knowledge_budget": 2})["metrics.json"])
    assert metrics["knowledge"] == {
        "decisions_in_force": 1,
        "decisions_proposed": 1,
        "gotchas_active": 2,
        "active_items": 4,
        "budget": 2,
        "review_due": True,
    }
    html = lastcontext({"knowledge_budget": 2})["dashboard.html"]
    assert "Knowledge review due" in html


def test_invalid_knowledge_fails_loudly():
    tasks, deltas, facts = sample()
    bad = [parse_doc("docs/adr/0007-a.md", ADR)]  # supersedes 0003, which does not exist
    with pytest.raises(StateError, match="supersedes unknown ADR 0003"):
        build(tasks, deltas, facts, None, AS_OF, bad)


def test_board_marks_human_tasks():
    html = lastcontext()["dashboard.html"]
    assert "task_004 · backend · feature · human" in html
