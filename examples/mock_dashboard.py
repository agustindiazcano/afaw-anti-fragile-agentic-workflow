#!/usr/bin/env python3
"""Build the public demo (dashboard and LASTCONTEXT.md) from mock data.

Usage (from the repository root):
    python -m examples.mock_dashboard [output directory]
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.afaw_state.knowledge import parse_doc
from scripts.afaw_state.views import build

AS_OF = datetime(2026, 9, 30, 3, 45, tzinfo=UTC)


def task(i, title, role, typ, status, priority, difficulty, blocked=(), branch=None):
    # Mock values are written as urgency (5 = most urgent); the task file uses 1 = most urgent.
    t = {
        "id": f"task_{i:03d}",
        "title": title,
        "role": role,
        "type": typ,
        "status": status,
        "priority": 6 - priority,
        "difficulty": difficulty,
        "blocked_by": list(blocked),
    }
    if branch:
        t["branch"] = branch
    return t


TASKS = [
    task(
        1,
        "Project skeleton and CI pipeline",
        "infra",
        "chore",
        "done",
        5,
        2,
        branch="chore/skeleton",
    ),
    task(
        2,
        "Order model and migrations",
        "backend",
        "feature",
        "done",
        5,
        3,
        branch="feat/order-model",
    ),
    task(
        3, "Create order endpoint", "backend", "feature", "done", 4, 3, branch="feat/create-order"
    ),
    task(
        4,
        "Fix rounding in tax calculation",
        "backend",
        "fix",
        "done",
        5,
        2,
        branch="fix/tax-rounding",
    ),
    task(5, "Order list page", "frontend", "feature", "done", 3, 3, branch="feat/order-list"),
    task(
        6,
        "Tests for payment adapter",
        "backend",
        "tests-only",
        "done",
        4,
        2,
        branch="chore/payment-tests",
    ),
    task(
        7,
        "Order cancellation endpoint",
        "backend",
        "feature",
        "in_progress",
        5,
        4,
        branch="feat/cancel-order",
    ),
    task(8, "Refund flow", "backend", "feature", "in_progress", 4, 5, branch="feat/refunds"),
    task(
        9,
        "Order detail page",
        "frontend",
        "feature",
        "in_progress",
        3,
        3,
        branch="feat/order-detail",
    ),
    task(
        10,
        "Terraform for staging",
        "infra",
        "chore",
        "in_progress",
        3,
        3,
        branch="chore/tf-staging",
    ),
    task(
        11,
        "Cancellation button in UI",
        "frontend",
        "feature",
        "pending",
        4,
        2,
        blocked=["task_007"],
    ),
    task(12, "Refund notifications", "backend", "feature", "pending", 3, 3, blocked=["task_008"]),
    task(13, "Rate limiting on public API", "backend", "feature", "pending", 3, 3),
    task(14, "Extract pricing service", "backend", "refactor", "pending", 2, 4),
    task(15, "Load test for checkout", "qa", "chore", "backlog", 2, 3),
    task(16, "Dark mode", "frontend", "feature", "backlog", 1, 2),
    task(17, "Legacy CSV export", "backend", "feature", "cancelled", 1, 2),
    {
        **task(18, "Branch protection on main, requiring CI", "infra", "chore", "pending", 5, 1),
        "owner": "human",
    },
    {
        **task(19, "Decide the public API protection", "backend", "chore", "pending", 3, 2),
        "owner": "human",
    },
]

DELTAS = {
    "task_006": {
        "files_touched": ["tests/test_payment_adapter.py"],
        "summary": "Adapter covered, including timeouts and partial refunds.",
    },
    "task_007": {
        "files_touched": ["src/orders/cancel.py"],
        "summary": "Endpoint and validation done; refund of the paid amount not wired yet.",
        "next": ["Call the refund service", "Idempotency key on retries"],
    },
    "task_009": {
        "files_touched": ["web/orders/detail.tsx"],
        "summary": "Layout done, data loading pending.",
    },
}


def _doc(path, status, day, tags, title, sections, extra=""):
    body = "\n\n".join(f"## {name}\n{text}" for name, text in sections)
    return parse_doc(
        path,
        f"---\nstatus: {status}\ndate: 2026-09-{day}\n{extra}tags: [{', '.join(tags)}]\n---\n"
        f"# {title}\n\n{body}\n",
    )


ADR_SECTIONS = [
    ("Context", "c"),
    ("Decision", "d"),
    ("Alternatives considered", "a"),
    ("Consequences", "e"),
]
GOTCHA_SECTIONS = [("Symptom", "s"), ("What to do", "w")]

KNOWLEDGE = [
    _doc(
        "docs/adr/0001-both-judges-gemini.md",
        "superseded",
        "10",
        ["llm"],
        "Both judges on Gemini",
        ADR_SECTIONS,
    ),
    _doc(
        "docs/adr/0002-vertex-via-langchain-genai.md",
        "accepted",
        "12",
        ["llm", "gcp"],
        "Vertex through langchain-google-genai, ADC only",
        ADR_SECTIONS,
    ),
    _doc(
        "docs/adr/0003-asymmetric-judges.md",
        "accepted",
        "18",
        ["llm"],
        "Judges stay asymmetric: Gemini and GPT-OSS",
        ADR_SECTIONS,
        "supersedes: [0001]\n",
    ),
    _doc(
        "docs/adr/0004-gcp-demo-only.md",
        "accepted",
        "20",
        ["infra", "gcp"],
        "Google Cloud is demo-only, switched off after each demo",
        ADR_SECTIONS,
    ),
    _doc(
        "docs/adr/0005-high-value-court.md",
        "proposed",
        "24",
        ["llm", "domain"],
        "Refunds of $1,000-$5,000 need four judges from four families",
        ADR_SECTIONS,
    ),
    _doc(
        "docs/gotchas/0001-terraform-429.md",
        "active",
        "21",
        ["infra", "terraform"],
        "terraform plan hangs silently on a Cloud Billing 429",
        GOTCHA_SECTIONS,
    ),
    _doc(
        "docs/gotchas/0002-gemini-global-endpoint.md",
        "active",
        "22",
        ["llm", "gcp"],
        "Gemini 3.x returns 404 on regional Vertex endpoints",
        GOTCHA_SECTIONS,
    ),
    _doc(
        "docs/gotchas/0003-demo-up-false.md",
        "promoted",
        "23",
        ["infra", "terraform"],
        "Every plan must pass demo_up=false while the demo is down",
        GOTCHA_SECTIONS,
        "promoted_to: infra/plan.sh\n",
    ),
    _doc(
        "docs/gotchas/0004-clock-timestamp.md",
        "active",
        "23",
        ["db"],
        "updated_at uses clock_timestamp() because the worker holds a transaction",
        GOTCHA_SECTIONS,
    ),
]

CONFIG = {
    "banner": "Demo with mock data: a fictional project, every task and number is invented.",
    "stale_days": 3,
    "role_tags": {"backend": ["llm", "db", "domain"], "infra": ["infra", "gcp", "terraform"]},
    "reference_docs": [
        "README.md",
        "docs/architecture/overview.md",
        "docs/infrastructure/gcp_infrastructure.md",
    ],
}


def merged(n, created, start, green, opened, merged_at, runs, failed, queue, minutes):
    return {
        "created_at": created,
        "started_at": start,
        "first_green_at": green,
        "pr_opened_at": opened,
        "merged_at": merged_at,
        "pr_url": f"https://github.com/example/shop/pull/{n}",
        "ci": {
            "runs": runs,
            "failed_runs": failed,
            "jobs": runs * 4,
            "queue_seconds": queue,
            "job_minutes": minutes,
        },
    }


FACTS = {
    "task_001": merged(
        1,
        "2026-09-12T15:00:00Z",
        "2026-09-14T13:00:00Z",
        "2026-09-14T14:10:00Z",
        "2026-09-14T14:05:00Z",
        "2026-09-14T18:30:00Z",
        3,
        1,
        140,
        11,
    ),
    "task_002": merged(
        2,
        "2026-09-12T15:00:00Z",
        "2026-09-15T12:00:00Z",
        "2026-09-15T15:40:00Z",
        "2026-09-15T15:20:00Z",
        "2026-09-16T11:00:00Z",
        5,
        2,
        260,
        24,
    ),
    "task_003": merged(
        3,
        "2026-09-12T15:00:00Z",
        "2026-09-16T13:00:00Z",
        "2026-09-16T17:05:00Z",
        "2026-09-16T16:45:00Z",
        "2026-09-17T12:10:00Z",
        4,
        1,
        210,
        19,
    ),
    "task_004": merged(
        4,
        "2026-09-17T20:00:00Z",
        "2026-09-18T14:00:00Z",
        "2026-09-18T14:50:00Z",
        "2026-09-18T14:40:00Z",
        "2026-09-18T16:00:00Z",
        2,
        0,
        75,
        8,
    ),
    "task_005": merged(
        5,
        "2026-09-15T14:00:00Z",
        "2026-09-21T12:30:00Z",
        "2026-09-21T18:20:00Z",
        "2026-09-21T17:55:00Z",
        "2026-09-23T13:00:00Z",
        6,
        3,
        390,
        31,
    ),
    "task_006": merged(
        6,
        "2026-09-19T13:00:00Z",
        "2026-09-24T13:00:00Z",
        "2026-09-24T15:00:00Z",
        "2026-09-24T14:50:00Z",
        "2026-09-25T10:00:00Z",
        3,
        1,
        160,
        14,
    ),
    # CI failing on the latest commit -> red
    "task_007": {
        "created_at": "2026-09-22T14:00:00Z",
        "started_at": "2026-09-29T12:00:00Z",
        "last_activity_at": "2026-09-30T02:40:00Z",
        "ci_status": "failure",
        "pr_url": "https://github.com/example/shop/pull/7",
        "ci": {"runs": 3, "failed_runs": 2, "jobs": 12, "queue_seconds": 150, "job_minutes": 13},
    },
    # No activity for more than stale_days -> yellow
    "task_008": {
        "created_at": "2026-09-19T13:00:00Z",
        "started_at": "2026-09-25T12:00:00Z",
        "last_activity_at": "2026-09-26T19:00:00Z",
        "ci_status": "success",
        "ci": {"runs": 2, "failed_runs": 0, "jobs": 8, "queue_seconds": 90, "job_minutes": 9},
    },
    "task_009": {
        "created_at": "2026-09-23T16:00:00Z",
        "started_at": "2026-09-29T15:00:00Z",
        "last_activity_at": "2026-09-30T03:10:00Z",
        "ci_status": "pending",
        "ci": {"runs": 1, "failed_runs": 0, "jobs": 4, "queue_seconds": 45, "job_minutes": 4},
    },
    # Only the creation date is known -> no data
    "task_010": {"created_at": "2026-09-26T12:00:00Z"},
    "task_011": {"created_at": "2026-09-22T14:05:00Z"},
    "task_012": {"created_at": "2026-09-25T18:00:00Z"},
    "task_013": {"created_at": "2026-09-27T13:00:00Z"},
    "task_014": {"created_at": "2026-09-29T22:30:00Z"},
    "task_015": {"created_at": "2026-09-12T15:00:00Z"},
    "task_016": {"created_at": "2026-09-18T11:00:00Z"},
    "task_017": {"created_at": "2026-09-12T15:00:00Z"},
    "task_018": {"created_at": "2026-09-25T14:00:00Z"},
    "task_019": {"created_at": "2026-09-24T19:00:00Z"},
}


def build_demo(out: Path) -> list[Path]:
    """Write the public demo: index.html (the dashboard) and two sample LASTCONTEXT.md files."""
    out.mkdir(parents=True, exist_ok=True)
    views = build(TASKS, DELTAS, FACTS, CONFIG, AS_OF, KNOWLEDGE)
    files = {
        "index.html": views["dashboard.html"],
        "LASTCONTEXT.md": views["context/global/LASTCONTEXT.md"],
        "LASTCONTEXT-backend.md": views["context/roles/backend/LASTCONTEXT.md"],
    }
    written = []
    for name, content in files.items():
        path = out / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "mock-output")
    written = build_demo(out)
    sys.stdout.write(f"wrote {len(written)} demo files to {out}\n")


if __name__ == "__main__":
    main()
