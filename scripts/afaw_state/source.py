"""Read the source state (task files, deltas, config) from a git ref, not from the working tree."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .knowledge import parse_doc

Runner = Callable[[list[str]], str]


def git_runner(args: list[str]) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _load(run: Runner, ref: str, path: str) -> Any:
    text = run(["show", f"{ref}:{path}"])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} at {ref} is not valid JSON: {exc}") from exc


def list_files(run: Runner, ref: str, folder: str, suffix: str = ".json") -> list[str]:
    out = run(["ls-tree", "-r", "--name-only", ref, "--", folder])
    return sorted(p for p in out.splitlines() if p.endswith(suffix))


def read_source(ref: str, run: Runner = git_runner) -> dict[str, Any]:
    """Task files, context deltas, ADRs and gotchas, config and the commit time of ``ref``."""
    tasks = [_load(run, ref, p) for p in list_files(run, ref, "state/tasks")]
    deltas = {}
    for path in list_files(run, ref, "context/tasks"):
        name = path.rsplit("/", 1)[-1]
        if name.endswith("_context.json"):
            deltas[name[: -len("_context.json")]] = _load(run, ref, path)
    config_files = list_files(run, ref, "state/config.json")
    config = _load(run, ref, "state/config.json") if config_files else {}
    knowledge = [
        parse_doc(p, run(["show", f"{ref}:{p}"]))
        for folder in ("docs/adr", "docs/gotchas")
        for p in list_files(run, ref, folder, ".md")
        if p.count("/") == 2  # files directly in the folder
    ]
    as_of = datetime.fromisoformat(run(["log", "-1", "--format=%cI", ref]).strip())
    return {
        "tasks": tasks,
        "deltas": deltas,
        "knowledge": knowledge,
        "config": config.get("dashboard", {}),
        "as_of": as_of,
    }
