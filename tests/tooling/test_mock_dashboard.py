"""Tests for examples.mock_dashboard: the public demo is built from mock data, deterministically."""

from __future__ import annotations

from pathlib import Path

from examples import mock_dashboard


def test_demo_site_files(tmp_path: Path) -> None:
    written = mock_dashboard.build_demo(tmp_path)
    assert sorted(p.name for p in written) == [
        "LASTCONTEXT-backend.md",
        "LASTCONTEXT.md",
        "index.html",
    ]
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Demo with mock data" in html
    for light in ("Red · CI failing on the latest commit", "Yellow · no activity", "No data"):
        assert light in html


def test_demo_is_deterministic(tmp_path: Path) -> None:
    first = {p.name: p.read_bytes() for p in mock_dashboard.build_demo(tmp_path / "a")}
    second = {p.name: p.read_bytes() for p in mock_dashboard.build_demo(tmp_path / "b")}
    assert first == second
