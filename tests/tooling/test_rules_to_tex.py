"""Tests for scripts.rules_to_tex: the paper's appendix is generated from AGENTS.md."""

from __future__ import annotations

from pathlib import Path

from scripts import rules_to_tex

SAMPLE = """# Instructions for coding agents

Rules reusable in any project.

## 0. Language
> **ALWAYS RESPOND IN ENGLISH.** Every reply.

## 3. Status
Answer with a table:

| Task | Light |
|---|---|
| Migrate `worker_a` | 🟡 stale |

1. **Light:** 🔴 blocked · 🟢 otherwise.
2. Use `state/config.json` & 100% of *care*.
   - nested DELETE
   - nested $x_1$

### Pull requests
8. Never push to `main`.
9. Keep {braces} and ~tilde^.
"""


def test_title_is_omitted_and_sections_numbered_as_written() -> None:
    tex = rules_to_tex.convert(SAMPLE)
    assert "Instructions for coding agents" not in tex
    assert "\\subsection*{0. Language}" in tex
    assert "\\subsection*{3. Status}" in tex
    assert "\\paragraph*{Pull requests}" in tex


def test_lists_keep_their_numbers_and_nesting() -> None:
    tex = rules_to_tex.convert(SAMPLE)
    assert "\\begin{enumerate}[start=1]" in tex
    assert "\\begin{enumerate}[start=8]" in tex
    assert tex.count("\\begin{itemize}") == 1
    assert "\\item nested DELETE" in tex


def test_inline_markup_emoji_and_escaping() -> None:
    tex = rules_to_tex.convert(SAMPLE)
    assert "\\textbf{ALWAYS RESPOND IN ENGLISH.}" in tex
    assert "\\texttt{state/\\allowbreak config.json}" in tex
    assert "\\& 100\\% of \\emph{care}" in tex
    assert "red blocked · green otherwise" in tex
    assert "\\$x\\_1\\$" in tex
    assert "\\{braces\\} and \\textasciitilde{}tilde\\textasciicircum{}" in tex
    assert "\\begin{quote}" in tex


def test_table_becomes_tabular() -> None:
    tex = rules_to_tex.convert(SAMPLE)
    assert "\\begin{tabularx}{\\linewidth}{@{}YY@{}}" in tex
    assert "\\textbf{Task} & \\textbf{Light} \\\\" in tex
    assert "Migrate \\texttt{worker\\_\\allowbreak a} & yellow stale \\\\" in tex


def test_main_writes_the_appendix(tmp_path: Path) -> None:
    source = tmp_path / "AGENTS.md"
    source.write_text(SAMPLE, encoding="utf-8")
    out = tmp_path / "appendix_rules.tex"
    assert rules_to_tex.main([str(source), str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("% Generated from")


def test_the_real_agents_file_converts() -> None:
    root = Path(__file__).resolve().parents[2]
    tex = rules_to_tex.convert((root / "AGENTS.md").read_text(encoding="utf-8"))
    assert "\\subsection*{20. Project knowledge: decisions and gotchas}" in tex
    assert tex.count("\\begin{enumerate}") == tex.count("\\end{enumerate}")
    assert tex.count("\\begin{itemize}") == tex.count("\\end{itemize}")


def test_bold_spanning_a_code_span() -> None:
    tex = rules_to_tex.inline("**Always ask for `ROLE:`** first.")
    assert tex == "\\textbf{Always ask for \\texttt{ROLE:}} first."
