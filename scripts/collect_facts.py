#!/usr/bin/env python3
"""Collect measured facts per task from git and the GitHub API.

Usage (GITHUB_REPOSITORY=owner/repo, GITHUB_TOKEN with read access to pulls and actions):
    python scripts/collect_facts.py --ref origin/main --out build/facts.json

Facts of merged tasks are final, so an existing output file is reused as a cache.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from scripts.afaw_state.facts import Git, GitHub, collect
from scripts.afaw_state.source import read_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--out", default="build/facts.json", type=Path)
    args = parser.parse_args(argv)

    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("GITHUB_REPOSITORY is not set (expected owner/repo)", file=sys.stderr)
        return 1

    source = read_source(args.ref)
    cache = json.loads(args.out.read_text()) if args.out.exists() else {}
    facts = collect(
        source["tasks"], args.ref, Git(), GitHub(repo, os.environ.get("GITHUB_TOKEN")), cache
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote facts for {len(facts)} tasks to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
