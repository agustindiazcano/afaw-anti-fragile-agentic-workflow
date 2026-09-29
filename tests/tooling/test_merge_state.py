"""Tests for scripts.merge_state: consolidation of task state and context deltas."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scripts import merge_state
from scripts.state_common import StateError

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

ROLE_BACKEND = "context/roles/backend/lastcontext.json"
ROLE_FRONTEND = "context/roles/frontend/lastcontext.json"


def test_pending_summarises_every_task(project: Project) -> None:
    project.add_task(
        "task_001",
        status="in_progress",
        owner="agent_1",
        locked_files=["src/a.py"],
        updated_at="2026-09-29T15:45:00-03:00",
    )
    project.add_task("task_002")
    project.add_task("task_003", status="blocked", blocked_by=["task_001"])

    pending = merge_state.build_outputs(project.root)[merge_state.PENDING_PATH]

    assert pending["summary"] == {"pending": 1, "in_progress": 1, "blocked": 1, "completed": 0}
    assert pending["tasks"]["task_001"] == {
        "status": "in_progress",
        "owner": "agent_1",
        "blocked_by": [],
        "locked_files": ["src/a.py"],
    }
    assert pending["generated_at"] == "2026-09-29T15:45:00-03:00"


def test_two_in_progress_tasks_cannot_lock_the_same_file(project: Project) -> None:
    project.add_task("task_001", status="in_progress", locked_files=["src/a.py"])
    project.add_task("task_002", status="in_progress", locked_files=["src/a.py", "src/b.py"])
    with pytest.raises(StateError, match=r"LOCK CONFLICT.*src/a\.py"):
        merge_state.build_outputs(project.root)


def test_a_pending_task_may_share_a_file_with_an_in_progress_task(project: Project) -> None:
    project.add_task("task_001", status="in_progress", locked_files=["src/a.py"])
    project.add_task("task_002", status="pending", locked_files=["src/a.py"])
    assert merge_state.build_outputs(project.root)


def test_unknown_blocker_is_rejected(project: Project) -> None:
    project.add_task("task_002", status="blocked", blocked_by=["task_404"])
    with pytest.raises(StateError, match="task_404"):
        merge_state.build_outputs(project.root)


def test_file_name_must_match_the_task_id(project: Project) -> None:
    project.add_task("task_001")
    (project.root / "state/tasks/task_001.json").rename(project.root / "state/tasks/task_009.json")
    with pytest.raises(StateError, match="does not match the file name"):
        merge_state.build_outputs(project.root)


def test_delta_for_an_unknown_task_is_rejected(project: Project) -> None:
    project.add_delta("task_007")
    with pytest.raises(StateError, match="unknown task"):
        merge_state.build_outputs(project.root)


def test_invalid_task_file_is_rejected(project: Project) -> None:
    task = project.add_task("task_001")
    task["status"] = "done"
    project.write("state/tasks/task_001.json", task)
    with pytest.raises(StateError, match="status"):
        merge_state.build_outputs(project.root)


def test_role_context_reports_focus_last_agent_and_open_work(project: Project) -> None:
    project.add_task("task_001", status="in_progress")
    project.add_delta(
        "task_001",
        agent="agent_backend_2",
        written_at="2026-09-29T16:00:00-03:00",
        decisions=["Use httpx"],
        remaining_work=["Add retries"],
        blocked_by_lock=["LOCKED_BY_TASK_9"],
    )

    role = merge_state.build_outputs(project.root)[ROLE_BACKEND]

    assert role["current_focus"] == "task_001: Title of task_001"
    assert role["last_agent_session"] == "agent_backend_2"
    assert role["recent_decisions"] == [{"task_id": "task_001", "decision": "Use httpx"}]
    assert role["next_steps"] == ["Add retries"]
    assert role["open_questions"] == ["LOCKED_BY_TASK_9"]
    assert role["updated_at"] == "2026-09-29T16:00:00-03:00"


def test_role_without_active_work_is_idle(project: Project) -> None:
    project.add_task("task_003", role="frontend")
    role = merge_state.build_outputs(project.root)[ROLE_FRONTEND]
    assert role["current_focus"] == "Idle."
    assert role["last_agent_session"] is None


def test_completed_tasks_leave_no_next_steps(project: Project) -> None:
    project.add_task("task_001", status="completed")
    project.add_delta("task_001", remaining_work=["Already handled"])
    assert merge_state.build_outputs(project.root)[ROLE_BACKEND]["next_steps"] == []


def test_recent_decisions_keep_only_the_newest(project: Project) -> None:
    project.add_task("task_001", status="in_progress")
    total = merge_state.MAX_RECENT_DECISIONS + 5
    project.add_delta("task_001", decisions=[f"decision {n}" for n in range(total)])
    decisions = merge_state.build_outputs(project.root)[ROLE_BACKEND]["recent_decisions"]
    assert len(decisions) == merge_state.MAX_RECENT_DECISIONS
    assert decisions[-1]["decision"] == f"decision {total - 1}"


def test_global_context_keeps_existing_decisions_and_adds_new_ones(project: Project) -> None:
    project.write(
        merge_state.GLOBAL_PATH,
        {
            "project": "demo",
            "architecture_decisions": [
                {"id": "dec_001", "date": "2026-09-29", "decision": "Keep", "source_task": None}
            ],
            "dependencies": {"backend": ["fastapi"]},
        },
    )
    project.add_task("task_001", status="completed")
    project.add_delta("task_001", decisions=["Use httpx"], dependencies_added=["httpx"])

    context = merge_state.build_outputs(project.root)[merge_state.GLOBAL_PATH]

    assert context["project"] == "demo"
    assert [d["id"] for d in context["architecture_decisions"]] == ["dec_001", "dec_task_001_1"]
    assert context["architecture_decisions"][1]["date"] == "2026-09-29"
    assert context["dependencies"]["backend"] == ["fastapi", "httpx"]
    assert context["last_merged_tasks"] == ["task_001"]
    assert context["summary"] == "1 of 1 tasks completed; 0 in progress; 0 pending; 0 blocked."


def test_main_writes_files_and_check_passes_afterwards(project: Project) -> None:
    project.add_task("task_001", status="in_progress")
    args = ["--root", str(project.root)]

    assert merge_state.main([*args, "--check"]) == 1
    assert not (project.root / merge_state.PENDING_PATH).exists()

    assert merge_state.main(args) == 0
    assert (project.root / merge_state.PENDING_PATH).exists()
    assert merge_state.main([*args, "--check"]) == 0


def test_output_is_deterministic(project: Project) -> None:
    project.add_task("task_001", status="in_progress")
    project.add_delta("task_001", decisions=["A"])
    args = ["--root", str(project.root)]

    merge_state.main(args)
    first = (project.root / merge_state.GLOBAL_PATH).read_text(encoding="utf-8")
    merge_state.main(args)
    second = (project.root / merge_state.GLOBAL_PATH).read_text(encoding="utf-8")

    assert first == second
    assert json.loads(first)["generated"] is True


def test_main_returns_2_and_names_the_broken_file(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    project.add_task("task_001")
    (project.root / "state/tasks/task_001.json").write_text("{oops", encoding="utf-8")

    assert merge_state.main(["--root", str(project.root)]) == 2
    assert "task_001.json" in capsys.readouterr().err
