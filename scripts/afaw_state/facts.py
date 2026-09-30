"""Measured facts per task, taken from git and from the GitHub REST API.

Nothing here is declared by an agent. The parsing functions are pure and are
tested on recorded API payloads; the I/O is at the edges (``Git``, ``GitHub``).
"""

from __future__ import annotations

import json
import math
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Any

from .derive import parse_ts, require_ts

GREEN_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})
FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat().replace("+00:00", "Z") if ts else None


def _latest(values: Iterable[str | None]) -> str | None:
    parsed = [require_ts(v) for v in values if v]
    return _iso(max(parsed)) if parsed else None


def pr_facts(pr: Mapping[str, Any] | None, commits: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Facts from one pull request and its commits."""
    if pr is None:
        return {}
    dates = [require_ts(c["commit"]["committer"]["date"]) for c in commits]
    return {
        "pr_url": pr["html_url"],
        "pr_opened_at": _iso(require_ts(pr["created_at"])),
        "merged_at": _iso(parse_ts(pr.get("merged_at"))),
        "started_at": _iso(min(dates)) if dates else None,
        "last_commit_at": _iso(max(dates)) if dates else None,
    }


def ci_facts(
    runs: list[Mapping[str, Any]], jobs_by_run: Mapping[int, list[Mapping[str, Any]]]
) -> dict[str, Any]:
    """Facts from the workflow runs of one branch and their jobs.

    first_green_at: the earliest time at which every run of one commit had
                    finished green (success, skipped or neutral).
    ci_status:      the state of the runs of the latest commit.
    ci.queue_seconds: sum over jobs of (started_at - created_at).
    ci.job_minutes:   sum over jobs of their duration rounded up to a whole
                      minute, the unit GitHub uses to bill standard runners.
                      Runner price multipliers are not applied; the billing
                      report remains the ground truth for cost.
    """
    if not runs:
        return {}

    by_sha: dict[str, list[Mapping[str, Any]]] = {}
    for run in runs:
        by_sha.setdefault(run["head_sha"], []).append(run)

    green_times = []
    for sha_runs in by_sha.values():
        if all(
            r["status"] == "completed" and r["conclusion"] in GREEN_CONCLUSIONS for r in sha_runs
        ):
            green_times.append(max(require_ts(r["updated_at"]) for r in sha_runs))

    latest_sha = max(by_sha, key=lambda s: max(require_ts(r["created_at"]) for r in by_sha[s]))
    latest = by_sha[latest_sha]
    if any(r.get("conclusion") in FAILED_CONCLUSIONS for r in latest):
        status = "failure"
    elif all(r["status"] == "completed" and r["conclusion"] in GREEN_CONCLUSIONS for r in latest):
        status = "success"
    else:
        status = "pending"

    jobs = [j for r in runs for j in jobs_by_run.get(r["id"], [])]
    queue = 0
    minutes = 0
    for job in jobs:
        created, started, completed = (
            parse_ts(job.get(k)) for k in ("created_at", "started_at", "completed_at")
        )
        if created and started:
            queue += max(0, int((started - created).total_seconds()))
        if started and completed:
            minutes += math.ceil(max(0.0, (completed - started).total_seconds()) / 60)

    return {
        "first_green_at": _iso(min(green_times)) if green_times else None,
        "ci_status": status,
        "last_run_at": _latest(r["updated_at"] for r in runs),
        "ci": {
            "runs": len(runs),
            "failed_runs": sum(1 for r in runs if r.get("conclusion") in FAILED_CONCLUSIONS),
            "jobs": len(jobs),
            "queue_seconds": queue,
            "job_minutes": minutes,
        },
    }


def combine(
    created_at: str | None,
    branch_commit_at: str | None,
    pr: Mapping[str, Any],
    ci: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge the facts of one task into the shape that ``derive`` reads."""
    facts: dict[str, Any] = {"created_at": created_at}
    facts.update({k: v for k, v in pr.items() if k != "last_commit_at"})
    facts.update({k: v for k, v in ci.items() if k != "last_run_at"})
    facts["last_activity_at"] = _latest(
        [branch_commit_at, pr.get("last_commit_at"), ci.get("last_run_at")]
    )
    return facts


# ---------------------------------------------------------------- I/O edges


class Git:
    def __init__(self, run: Callable[[list[str]], str] | None = None) -> None:
        self._run = run or (
            lambda args: (
                subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout
            )
        )

    def file_added_at(self, ref: str, path: str) -> str | None:
        out = self._run(["log", "--diff-filter=A", "--format=%cI", ref, "--", path]).split()
        return _iso(require_ts(out[-1])) if out else None

    def branch_commit_at(self, branch: str) -> str | None:
        try:
            out = self._run(["log", "-1", "--format=%cI", f"origin/{branch}"]).strip()
        except subprocess.CalledProcessError:
            return None  # branch deleted after merge; the PR commits cover it
        return _iso(require_ts(out)) if out else None


class GitHub:
    API = "https://api.github.com"

    def __init__(
        self, repo: str, token: str | None, get_json: Callable[[str], Any] | None = None
    ) -> None:
        self.repo = repo
        self.owner = repo.split("/")[0]
        self._token = token
        self._get_json = get_json or self._http_get

    def _http_get(self, url: str) -> Any:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    def _url(self, path: str, **params: Any) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.API}/repos/{self.repo}/{path}" + (f"?{query}" if query else "")

    def _pages(self, path: str, key: str | None, max_pages: int, **params: Any) -> list[Any]:
        items: list[Any] = []
        for page in range(1, max_pages + 1):
            data = self._get_json(self._url(path, per_page=100, page=page, **params))
            batch = data[key] if key else data
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def pull_request(self, branch: str) -> Mapping[str, Any] | None:
        pulls = self._get_json(
            self._url("pulls", head=f"{self.owner}:{branch}", state="all", per_page=100)
        )
        if not pulls:
            return None
        latest: Mapping[str, Any] = max(pulls, key=lambda p: require_ts(p["created_at"]))
        return latest

    def pr_commits(self, number: int) -> list[Mapping[str, Any]]:
        return self._pages(f"pulls/{number}/commits", None, 3)

    def runs(self, branch: str) -> list[Mapping[str, Any]]:
        return self._pages("actions/runs", "workflow_runs", 10, branch=branch)

    def jobs(self, run_id: int) -> list[Mapping[str, Any]]:
        return self._pages(f"actions/runs/{run_id}/jobs", "jobs", 5, filter="all")


def collect(
    tasks: list[Mapping[str, Any]],
    ref: str,
    git: Git,
    github: GitHub,
    cache: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Facts for every task that has a branch. Facts of merged tasks are final and reused "
    "from the cache."""
    cache = cache or {}
    facts: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = task["id"]
        cached = cache.get(task_id)
        if cached and cached.get("merged_at"):
            facts[task_id] = dict(cached)
            continue
        created = git.file_added_at(ref, f"state/tasks/{task_id}.json")
        branch = task.get("branch")
        if not branch:
            facts[task_id] = {"created_at": created}
            continue
        pr = github.pull_request(branch)
        pr_part = pr_facts(pr, github.pr_commits(pr["number"]) if pr else [])
        runs = github.runs(branch)
        ci_part = ci_facts(runs, {r["id"]: github.jobs(r["id"]) for r in runs})
        facts[task_id] = combine(created, git.branch_commit_at(branch), pr_part, ci_part)
    return facts
