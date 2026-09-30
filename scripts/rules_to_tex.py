"""Convert AGENTS.md into the LaTeX appendix of the paper, so the rules exist only once.

Handles the subset of markdown the rules use: section and subsection headings, numbered lists
(keeping their numbers), nested bullets, block quotes, one table, and inline code, bold and
italics. Two edits are made for typesetting: the traffic-light emoji become the words green,
yellow and red, and the file's opening heading is omitted.

Run: python -m scripts.rules_to_tex AGENTS.md docs/paper/appendix_rules.tex
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EMOJI = {"🟢": "green", "🟡": "yellow", "🔴": "red"}
SPECIAL = {
    "\\": "\\textbackslash{}",
    "&": "\\&",
    "%": "\\%",
    "$": "\\$",
    "#": "\\#",
    "_": "\\_",
    "{": "\\{",
    "}": "\\}",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}",
}
NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
NESTED = re.compile(r"^\s{2,}[-*]\s+(.*)$")


def escape(text: str) -> str:
    """Escape LaTeX special characters."""
    return "".join(SPECIAL.get(ch, ch) for ch in text)


def _code(text: str) -> str:
    escaped = escape(text)
    # Let long paths and identifiers break after / and _.
    escaped = escaped.replace("/", "/\\allowbreak ").replace("\\_", "\\_\\allowbreak ")
    return f"\\texttt{{{escaped}}}"


def inline(text: str) -> str:
    """Inline markdown (code, bold, italics, emoji) to LaTeX."""
    for emoji, word in EMOJI.items():
        text = text.replace(emoji, word)
    # Protect code spans first, so bold or italics may contain them.
    codes: list[str] = []

    def stash(match: re.Match[str]) -> str:
        codes.append(_code(match.group(1)))
        return f"\x00{len(codes) - 1}\x00"

    piece = escape(re.sub(r"`([^`]+)`", stash, text))
    piece = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", piece)
    piece = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\emph{\1}", piece)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], piece)


def _table(rows: list[str]) -> list[str]:
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    header, body = cells[0], [r for r in cells[1:] if not all(set(c) <= set("-: ") for c in r)]
    lines = [
        "\\begin{center}\\small",
        # Y is a ragged-right X column; the paper defines it.
        f"\\begin{{tabularx}}{{\\linewidth}}{{@{{}}{'Y' * len(header)}@{{}}}}",
        "\\toprule",
        " & ".join(f"\\textbf{{{inline(c)}}}" for c in header) + " \\\\",
        "\\midrule",
    ]
    lines += [" & ".join(inline(c) for c in row) + " \\\\" for row in body]
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{center}"]
    return lines


def convert(markdown: str) -> str:
    """The LaTeX body of the appendix."""
    lines = markdown.splitlines()
    out: list[str] = []
    in_enum = in_items = False
    table: list[str] = []

    def close_items() -> None:
        nonlocal in_items
        if in_items:
            out.append("\\end{itemize}")
            in_items = False

    def close_enum() -> None:
        nonlocal in_enum
        close_items()
        if in_enum:
            out.append("\\end{enumerate}")
            in_enum = False

    for index, line in enumerate(lines):
        if index == 0 and line.startswith("# "):
            continue
        if line.startswith("|"):
            close_enum()
            table.append(line)
            continue
        if table:
            out += _table(table)
            table = []
        numbered = NUMBERED.match(line)
        nested = NESTED.match(line)
        if line.startswith("## "):
            close_enum()
            out.append(f"\\subsection*{{{inline(line[3:].strip())}}}")
        elif line.startswith("### "):
            close_enum()
            out.append(f"\\paragraph*{{{inline(line[4:].strip())}}}")
        elif numbered:
            close_items()
            if not in_enum:
                out.append(f"\\begin{{enumerate}}[start={numbered.group(1)}]")
                in_enum = True
            out.append(f"\\item {inline(numbered.group(2))}")
        elif nested:
            if not in_items:
                out.append("\\begin{itemize}")
                in_items = True
            out.append(f"\\item {inline(nested.group(1))}")
        elif line.startswith("> "):
            close_enum()
            out.append(f"\\begin{{quote}}{inline(line[2:])}\\end{{quote}}")
        elif not line.strip():
            continue
        else:
            close_enum()
            out.append(inline(line) + "\n")
    if table:
        out += _table(table)
    close_enum()
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the appendix generated from the rules file."""
    parser = argparse.ArgumentParser(description="Generate the paper's rules appendix.")
    parser.add_argument("source", help="the rules file, e.g. AGENTS.md")
    parser.add_argument("output", help="the LaTeX file to write")
    args = parser.parse_args(argv)
    source = Path(args.source)
    body = convert(source.read_text(encoding="utf-8"))
    header = f"% Generated from {source.name} by scripts/rules_to_tex.py. Do not edit.\n"
    Path(args.output).write_text(header + body, encoding="utf-8")
    sys.stdout.write(f"OK: wrote {args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
