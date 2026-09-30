"""Mutation gate: score each file from the engine's results, counting only human-accepted
equivalent mutants, and block the pull request if a required file is below the minimum.

With N generated mutants, K killed (a timeout counts as killed) and E_h survivors that the
human recorded as equivalent in state/equivalent_mutants.json, the gated score is
K / (N - E_h) and the raw score is K / N. Both are reported. An agent cannot lower the
denominator: it may only propose an equivalence in the pull request, and a hook denies its
writes to that file. Each recorded equivalence names the file's SHA-256 and expires when the
file changes; expired entries are reported, not counted.

The mutation engine is project-specific. It writes a results file in this shape:
    {"files": {"<path>": {"mutants": [{"id": "<id>", "status": "killed|survived|timeout"}]}}}
Required files come from `python -m scripts.mutation_targets` (its "required" list).

Run in CI:
    python -m scripts.mutation_gate --results mutation.json --required src/a.py src/b.py
Prints a JSON report. Exit codes: 0 ok, 1 a required file is below the minimum or missing,
2 could not run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from scripts.project_config import load_config
from scripts.state_common import StateError, load_json, load_validated

EQUIVALENTS_PATH = "state/equivalent_mutants.json"
EQUIVALENTS_SCHEMA_PATH = "state/schemas/equivalent_mutants.schema.json"
KILLED = frozenset({"killed", "timeout"})
STATUSES = KILLED | {"survived"}


def score(mutants: Iterable[Mapping[str, Any]], accepted: set[str]) -> dict[str, Any]:
    """Raw and gated scores of one file; ``accepted`` holds its human-accepted mutant ids."""
    generated = killed = equivalent = 0
    for mutant in mutants:
        status = mutant["status"]
        if status not in STATUSES:
            raise ValueError(f"unknown mutant status: {status!r}")
        generated += 1
        if status in KILLED:
            killed += 1
        elif mutant["id"] in accepted:
            equivalent += 1
    denominator = generated - equivalent
    return {
        "generated": generated,
        "killed": killed,
        "equivalent": equivalent,
        "raw": round(100 * killed / generated, 2) if generated else None,
        "gated": round(100 * killed / denominator, 2) if denominator else None,
    }


def _file_sha(root: Path, path: str) -> str | None:
    target = root / path
    if not target.is_file():
        return None
    return hashlib.sha256(target.read_bytes()).hexdigest()


def accepted_equivalences(root: Path) -> tuple[dict[str, set[str]], list[str]]:
    """Current equivalences per file, and the expired ones as file#mutant."""
    path = root / EQUIVALENTS_PATH
    if not path.exists():
        return {}, []
    data = load_validated(path, load_json(root / EQUIVALENTS_SCHEMA_PATH))
    current: dict[str, set[str]] = {}
    stale: list[str] = []
    for entry in data["mutants"]:
        if _file_sha(root, entry["file"]) == entry["file_sha256"]:
            current.setdefault(entry["file"], set()).add(entry["mutant"])
        else:
            stale.append(f"{entry['file']}#{entry['mutant']}")
    return current, sorted(stale)


def main(argv: list[str] | None = None) -> int:
    """Score the engine's results and enforce the minimum on the required files."""
    parser = argparse.ArgumentParser(description="Mutation gate with human-only equivalences.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--results", required=True, help="the mutation engine's results JSON")
    parser.add_argument("--required", nargs="*", default=[], help="files that must pass")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        config = load_config(root)
        accepted, stale = accepted_equivalences(root)
        files = load_json(Path(args.results))["files"]
        report = {
            path: score(entry["mutants"], accepted.get(path, set()))
            for path, entry in sorted(files.items())
        }
    except (StateError, KeyError, ValueError, TypeError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    failures = []
    for path in args.required:
        if path not in report:
            failures.append(f"no mutation results for required file {path}")
            continue
        gated = report[path]["gated"]
        if gated is None or gated < config.mutation_min_score:
            failures.append(f"{path}: gated score {gated} is below {config.mutation_min_score}")
    for failure in failures:
        sys.stderr.write(f"PROBLEM: {failure}\n")
    output = {
        "min_score": config.mutation_min_score,
        "required": sorted(args.required),
        "files": report,
        "stale_equivalences": stale,
        "passed": not failures,
    }
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
