import json

from scripts.check_task_files import check
from tests.tooling.helpers import make_task


def fake(diff, base_files, head_files):
    def run(args):
        if args[0] == "diff":
            return diff
        if args[0] == "show":
            import subprocess

            path = args[1].split(":", 1)[1]
            if path not in base_files:
                raise subprocess.CalledProcessError(128, "git show")
            return json.dumps(base_files[path])
        raise AssertionError(args)

    return run, lambda path: json.dumps(head_files[path])


P1 = "state/tasks/task_001.json"


def test_valid_change_passes():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="in_progress", branch="feat/x")},
    )
    assert check("base", "feat/x", run, read) == []


def test_deletion_rejected():
    run, read = fake(f"D\t{P1}\n", {}, {})
    assert "never deleted" in check("base", None, run, read)[0]


def test_forbidden_transition_rejected():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="done", branch="feat/x")},
        {P1: make_task(status="in_progress", branch="feat/x")},
    )
    assert any(
        "status change not allowed: done -> in_progress" in e
        for e in check("base", "feat/x", run, read)
    )


def test_new_task_cannot_start_cancelled():
    run, read = fake(f"A\t{P1}\n", {}, {P1: make_task(status="cancelled")})
    assert any("cannot start as cancelled" in e for e in check("base", "feat/x", run, read))


def test_single_pull_request_task_goes_from_pending_to_done():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="done", branch="feat/x")},
    )
    assert check("base", "feat/x", run, read) == []


def test_derived_field_rejected():
    run, read = fake(f"A\t{P1}\n", {}, {P1: make_task(merged_at="2026-09-01T00:00:00Z")})
    assert any("derived field" in e for e in check("base", None, run, read))


def test_id_must_match_file_name():
    run, read = fake(f"A\t{P1}\n", {}, {P1: make_task("task_002")})
    assert any("does not match the file name" in e for e in check("base", None, run, read))


def test_branch_must_be_the_pull_request_branch():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="in_progress", branch="feat/other")},
    )
    assert any("is not this pull request's branch" in e for e in check("base", "feat/x", run, read))


def test_human_task_is_not_bound_to_the_branch():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending", owner="human")},
        {P1: make_task(status="done", owner="human")},
    )
    assert check("base", "feat/x", run, read) == []


def test_owner_and_status_cannot_change_together():
    run, read = fake(
        f"M\t{P1}\n",
        {P1: make_task(status="pending")},
        {P1: make_task(status="done", owner="human")},
    )
    assert any(
        "owner and status cannot change in the same pull request" in e
        for e in check("base", "feat/x", run, read)
    )


def test_new_task_id_must_not_exist_on_the_target_branch():
    # Two parallel branches may pick the same next id; the second one to merge must rename.
    base_run, read = fake(f"A\t{P1}\n", {}, {P1: make_task()})

    def run(args):
        if args[0] == "cat-file":
            return ""  # exists on origin/main
        return base_run(args)

    errors = check("base", None, run, read, target="origin/main")
    assert errors == [
        f"{P1}: task id task_001 already exists on origin/main; pick the next free id"
    ]
