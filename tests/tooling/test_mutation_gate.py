"""Tests for scripts.mutation_gate: the score uses only equivalences the human accepted."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scripts import mutation_gate

if TYPE_CHECKING:
    from tests.tooling.conftest import Project

SOURCE = "def fee(amount):\n    return round(amount * 0.03, 2)\n"
FILE = "src/back/domain/fees.py"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def results(statuses: dict[str, str]) -> dict[str, Any]:
    return {"files": {FILE: {"mutants": [{"id": k, "status": v} for k, v in statuses.items()]}}}


def ten_mutants(survivors: int) -> dict[str, str]:
    return {f"m{i}": ("survived" if i < survivors else "killed") for i in range(10)}


def test_raw_and_gated_scores_without_equivalences() -> None:
    report = mutation_gate.score(results(ten_mutants(3))["files"][FILE]["mutants"], accepted=set())
    assert report == {"generated": 10, "killed": 7, "equivalent": 0, "raw": 70.0, "gated": 70.0}


def test_timeout_counts_as_killed() -> None:
    mutants = [{"id": "a", "status": "timeout"}, {"id": "b", "status": "survived"}]
    assert mutation_gate.score(mutants, accepted=set())["killed"] == 1


def test_only_accepted_survivors_leave_the_denominator() -> None:
    mutants = results(ten_mutants(3))["files"][FILE]["mutants"]
    report = mutation_gate.score(mutants, accepted={"m0", "m1", "m9"})  # m9 was killed
    assert report["equivalent"] == 2
    assert report["gated"] == pytest.approx(87.5)  # 7 / (10 - 2)
    assert report["raw"] == 70.0


def test_unknown_status_fails_loudly() -> None:
    with pytest.raises(ValueError, match="unknown mutant status"):
        mutation_gate.score([{"id": "a", "status": "maybe"}], accepted=set())


def _setup(project: Project, survivors: int, equivalents: list[dict[str, str]]) -> Path:
    (project.root / FILE).parent.mkdir(parents=True, exist_ok=True)
    (project.root / FILE).write_text(SOURCE, encoding="utf-8")
    project.write("state/config.json", {"mutation_critical_paths": ["src/back/domain/"]})
    project.write("state/equivalent_mutants.json", {"mutants": equivalents})
    path = project.root / "mutation.json"
    path.write_text(json.dumps(results(ten_mutants(survivors))), encoding="utf-8")
    return path


def test_gate_blocks_a_required_file_below_the_minimum(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _setup(project, survivors=3, equivalents=[])
    args = ["--root", str(project.root), "--results", str(path), "--required", FILE]
    assert mutation_gate.main(args) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["files"][FILE]["gated"] == 70.0 and out["passed"] is False


def test_equivalences_bound_to_the_current_file_count(project: Project) -> None:
    equivalents = [
        {"file": FILE, "mutant": "m0", "file_sha256": sha(SOURCE), "reason": "round 2 vs 3"},
        {"file": FILE, "mutant": "m1", "file_sha256": sha(SOURCE), "reason": "same output"},
    ]
    path = _setup(project, survivors=3, equivalents=equivalents)
    args = ["--root", str(project.root), "--results", str(path), "--required", FILE]
    assert mutation_gate.main(args) == 0  # 7 / 8 = 87.5 >= 80


def test_equivalences_expire_when_the_file_changes(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    stale = [{"file": FILE, "mutant": "m0", "file_sha256": sha("old"), "reason": "x"}]
    path = _setup(project, survivors=3, equivalents=stale)
    args = ["--root", str(project.root), "--results", str(path), "--required", FILE]
    assert mutation_gate.main(args) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["files"][FILE]["equivalent"] == 0
    assert out["stale_equivalences"] == [f"{FILE}#m0"]


def test_optional_files_are_reported_but_never_block(project: Project) -> None:
    path = _setup(project, survivors=9, equivalents=[])
    args = ["--root", str(project.root), "--results", str(path)]
    assert mutation_gate.main(args) == 0


def test_required_file_missing_from_the_results_blocks(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _setup(project, survivors=0, equivalents=[])
    args = [
        "--root",
        str(project.root),
        "--results",
        str(path),
        "--required",
        "src/back/domain/x.py",
    ]
    assert mutation_gate.main(args) == 1
    assert "no mutation results for required file" in capsys.readouterr().err


def test_invalid_equivalence_file_is_rejected(
    project: Project, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _setup(project, survivors=0, equivalents=[{"file": FILE}])  # type: ignore[list-item]
    assert mutation_gate.main(["--root", str(project.root), "--results", str(path)]) == 2
    assert "missing required field" in capsys.readouterr().err
