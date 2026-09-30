#!/usr/bin/env python3
"""Build the derived views (pending, history, metrics, last-context, dashboard) from a git ref.

Usage:
    git fetch origin
    python scripts/build_state.py --ref origin/main --facts build/facts.json

Outputs go to a build directory that is listed in .gitignore and never committed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from scripts.afaw_state.source import read_source
from scripts.afaw_state.views import StateError, build

MARKER = ".afaw-build"


def prepare_out(out: Path) -> None:
    """Empty the build directory, refusing to touch a directory it did not create."""
    if out.exists():
        if not (out / MARKER).exists():
            raise SystemExit(f"refusing to overwrite {out}: it is not an AFAW build directory")
        for child in out.iterdir():
            if child.name == MARKER:
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    (out / MARKER).touch()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--out", default="build/state", type=Path)
    parser.add_argument("--facts", type=Path, help="facts.json from collect_facts.py (optional)")
    parser.add_argument(
        "--as-of",
        help="reference time, ISO 8601 with time zone (default: commit time of --ref). "
        "A scheduled run passes its own time so that inactivity is measured against now.",
    )
    args = parser.parse_args(argv)

    source = read_source(args.ref)
    as_of = source["as_of"]
    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of)
        if as_of.tzinfo is None:
            print(f"--as-of needs a time zone: {args.as_of!r}", file=sys.stderr)
            return 2
    facts = json.loads(args.facts.read_text()) if args.facts else None
    try:
        outputs = build(
            source["tasks"], source["deltas"], facts, source["config"], as_of, source["knowledge"]
        )
    except StateError as exc:
        print(exc, file=sys.stderr)
        return 1

    prepare_out(args.out)
    for rel, content in outputs.items():
        path = args.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"wrote {len(outputs)} views to {args.out} (as of {as_of.isoformat()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
