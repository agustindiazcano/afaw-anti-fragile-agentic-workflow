from scripts.afaw_state.facts import Git, GitHub, ci_facts, collect, combine, pr_facts
from tests.tooling.helpers import make_task


def run(run_id, sha, created, updated, conclusion="success", status="completed"):
    return {
        "id": run_id,
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "created_at": created,
        "updated_at": updated,
    }


def job(created, started, completed):
    return {"created_at": created, "started_at": started, "completed_at": completed}


def commit(date):
    return {"commit": {"committer": {"date": date}}}


def test_pr_facts():
    pr = {
        "html_url": "https://github.com/o/r/pull/7",
        "created_at": "2026-09-28T12:00:00Z",
        "merged_at": "2026-09-29T09:00:00Z",
    }
    commits = [commit("2026-09-28T11:00:00Z"), commit("2026-09-28T09:30:00-03:00")]
    assert pr_facts(pr, commits) == {
        "pr_url": "https://github.com/o/r/pull/7",
        "pr_opened_at": "2026-09-28T12:00:00Z",
        "merged_at": "2026-09-29T09:00:00Z",
        "started_at": "2026-09-28T11:00:00Z",
        "last_commit_at": "2026-09-28T09:30:00-03:00",
    }
    assert pr_facts(None, []) == {}


def test_first_green_needs_every_run_of_a_commit_green():
    runs = [
        run(1, "aaa", "2026-09-28T10:00:00Z", "2026-09-28T10:05:00Z", "failure"),
        run(2, "aaa", "2026-09-28T10:00:00Z", "2026-09-28T10:06:00Z"),
        run(3, "bbb", "2026-09-28T11:00:00Z", "2026-09-28T11:04:00Z"),
        run(4, "bbb", "2026-09-28T11:00:00Z", "2026-09-28T11:09:00Z", "skipped"),
    ]
    facts = ci_facts(runs, {})
    assert facts["first_green_at"] == "2026-09-28T11:09:00Z"
    assert facts["ci_status"] == "success"
    assert facts["ci"]["runs"] == 4
    assert facts["ci"]["failed_runs"] == 1


def test_status_of_latest_commit():
    older_green = run(1, "aaa", "2026-09-28T10:00:00Z", "2026-09-28T10:05:00Z")
    failing = run(2, "bbb", "2026-09-28T11:00:00Z", "2026-09-28T11:05:00Z", "failure")
    running = run(3, "ccc", "2026-09-28T12:00:00Z", "2026-09-28T12:01:00Z", None, "in_progress")
    assert ci_facts([older_green, failing], {})["ci_status"] == "failure"
    assert ci_facts([older_green, failing, running], {})["ci_status"] == "pending"


def test_queue_and_job_minutes():
    runs = [run(1, "aaa", "2026-09-28T10:00:00Z", "2026-09-28T10:10:00Z")]
    jobs = {
        1: [
            job(
                "2026-09-28T10:00:00Z", "2026-09-28T10:00:40Z", "2026-09-28T10:02:01Z"
            ),  # 40 s queue, 81 s -> 2 min
            job(
                "2026-09-28T10:00:00Z", "2026-09-28T10:01:00Z", "2026-09-28T10:01:00Z"
            ),  # 60 s queue, 0 s -> 0 min
            job("2026-09-28T10:00:00Z", None, None),  # never started
        ]
    }
    ci = ci_facts(runs, jobs)["ci"]
    assert ci == {"runs": 1, "failed_runs": 0, "jobs": 3, "queue_seconds": 100, "job_minutes": 2}


def test_no_runs_gives_no_ci_facts():
    assert ci_facts([], {}) == {}


def test_combine_takes_latest_activity():
    facts = combine(
        "2026-09-20T00:00:00Z",
        "2026-09-28T10:00:00Z",
        {"started_at": "2026-09-27T00:00:00Z", "last_commit_at": "2026-09-28T09:00:00Z"},
        {"ci_status": "success", "last_run_at": "2026-09-28T10:30:00Z", "ci": {}},
    )
    assert facts["last_activity_at"] == "2026-09-28T10:30:00Z"
    assert "last_commit_at" not in facts and "last_run_at" not in facts


class FakeGit(Git):
    def __init__(self):
        super().__init__(run=lambda args: "")

    def file_added_at(self, ref, path):
        return "2026-09-20T00:00:00Z"

    def branch_commit_at(self, branch):
        return None


def test_collect_uses_api_and_reuses_cache_for_merged_tasks():
    calls = []

    def get_json(url):
        calls.append(url)
        if "/pulls?" in url:
            return [
                {
                    "number": 3,
                    "html_url": "u",
                    "created_at": "2026-09-28T12:00:00Z",
                    "merged_at": None,
                }
            ]
        if "/pulls/3/commits" in url:
            return [commit("2026-09-28T10:00:00Z")]
        if "actions/runs?" in url:
            return {
                "workflow_runs": [run(9, "aaa", "2026-09-28T12:00:00Z", "2026-09-28T12:05:00Z")]
            }
        if "actions/runs/9/jobs" in url:
            return {
                "jobs": [
                    job("2026-09-28T12:00:00Z", "2026-09-28T12:00:30Z", "2026-09-28T12:03:00Z")
                ]
            }
        raise AssertionError(url)

    tasks = [
        make_task("task_001", status="done", branch="feat/a"),
        make_task("task_002", status="in_progress", branch="feat/b"),
        make_task("task_003", status="backlog"),
    ]
    cache = {"task_001": {"merged_at": "2026-09-21T00:00:00Z", "ci": {"runs": 1}}}
    facts = collect(tasks, "origin/main", FakeGit(), GitHub("o/r", None, get_json), cache)

    assert facts["task_001"] == cache["task_001"]
    assert not any("feat%2Fa" in c for c in calls)
    assert facts["task_002"]["started_at"] == "2026-09-28T10:00:00Z"
    assert facts["task_002"]["ci"]["job_minutes"] == 3
    assert facts["task_002"]["ci"]["queue_seconds"] == 30
    assert facts["task_003"] == {"created_at": "2026-09-20T00:00:00Z"}


def test_git_file_added_at_takes_first_addition():
    outputs = {"log": "2026-09-25T00:00:00Z\n2026-09-20T00:00:00Z\n"}
    git = Git(run=lambda args: outputs[args[0]])
    assert git.file_added_at("origin/main", "state/tasks/task_001.json") == "2026-09-20T00:00:00Z"
