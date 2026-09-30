"""Red-first check: every test a pull request adds must fail on the code before the change.

A red step seen by the agent on its own machine is a claim (F3). This check measures it: it
takes the test functions the pull request adds, runs them against the merge base with the new
test files copied in, and requires each of them to fail. A new test that passes on the old code
did not drive the change.

Rules:
  - A parametrized test is red if at least one of its cases fails or errors.
  - A test file that cannot even be imported on the old code (the module under test does not
    exist yet) counts as red for all its added tests. This is why the check shows that a test
    fails, not that it fails for the right reason.
  - A skipped test is not red. A test absent from the report did not run: the check fails
    loudly (exit 2) instead of counting it as passing.
  - A test that documents behavior the code already has is declared with
    @pytest.mark.characterization(reason="..."); it is excluded and printed for the reviewer.
  - If a task file changed by the pull request declares type tests-only or refactor, the check
    is skipped and the declaration is printed, for the reviewer to see.

The reference implementation runs pytest; another stack replaces run_old().

Run in CI: python -m scripts.red_check --base origin/main
Exit codes: 0 ok or skipped, 1 an added test passed on the old code, 2 could not run
(including an added test that did not run).
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from scripts.project_config import load_config
from scripts.state_common import StateError

GIT_TIMEOUT_SECONDS = 60
PYTEST_TIMEOUT_SECONDS = 600
SKIP_TYPES = frozenset({"tests-only", "refactor"})


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise StateError(f"git {' '.join(args)} failed: {exc}") from exc
    return result.stdout


def test_ids(source: str) -> set[str]:
    """Top-level test functions and test methods of Test* classes, as pytest names them."""
    ids: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            ids.add(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    item.name.startswith("test")
                ):
                    ids.add(f"{node.name}::{item.name}")
    return ids


def added_tests(path: str, old_source: str | None, new_source: str) -> list[str]:
    """Node ids of the tests in ``new_source`` that ``old_source`` does not have."""
    old = test_ids(old_source) if old_source is not None else set()
    return sorted(f"{path}::{name}" for name in test_ids(new_source) - old)


def _junit_key(node_id: str) -> tuple[str, str]:
    """(classname, name) that pytest's JUnit report uses for a node id."""
    path, *rest = node_id.split("::")
    module = str(PurePosixPath(path).with_suffix("")).replace("/", ".")
    return ".".join([module, *rest[:-1]]), rest[-1]


def not_red(junit_xml: str, added: list[str]) -> tuple[list[str], list[str]]:
    """Added tests that ran on the old code without failing, and those absent from the report.

    Absence is not a verdict: a test missing from the report did not run, and the caller fails
    loudly rather than count it as passing.
    """
    seen: set[tuple[str, str]] = set()
    failed: set[tuple[str, str]] = set()
    broken_modules: set[str] = set()
    for case in ET.fromstring(junit_xml).iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        bad = case.find("failure") is not None or case.find("error") is not None
        if not classname:  # a collection error: the whole module could not be imported
            if bad:
                broken_modules.add(name)
            continue
        key = (classname, name.split("[", 1)[0])
        seen.add(key)
        if bad:
            failed.add(key)
    passing: list[str] = []
    missing: list[str] = []
    for node_id in added:
        key = _junit_key(node_id)
        module = _junit_key(node_id.split("::", 1)[0] + "::x")[0]
        if module in broken_modules or key in failed:
            continue
        (passing if key in seen else missing).append(node_id)
    return passing, missing


def _is_characterization(decorator: ast.expr) -> str | None:
    """The reason of a @pytest.mark.characterization decorator, or None if it is another one."""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if not (isinstance(target, ast.Attribute) and target.attr == "characterization"):
        return None
    if isinstance(decorator, ast.Call):
        values = [k.value for k in decorator.keywords if k.arg == "reason"] + decorator.args
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    return ""


def characterization(path: str, source: str) -> dict[str, str]:
    """Tests declared as characterization tests (they document behavior the code already has).

    They are excluded from the check and printed, so the reviewer sees each declaration.
    """
    declared: dict[str, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            for decorator in node.decorator_list:
                reason = _is_characterization(decorator)
                if reason is not None:
                    declared[f"{path}::{prefix}{node.name}"] = reason

    for node in ast.parse(source).body:
        visit(node, "")
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                visit(item, f"{node.name}::")
    return declared


def _is_test_file(path: str, test_prefixes: tuple[str, ...]) -> bool:
    name = PurePosixPath(path).name
    is_test = name.startswith("test_") or name.endswith("_test.py")
    return path.startswith(test_prefixes) and path.endswith(".py") and is_test


def skip_declaration(root: Path, base: str) -> str | None:
    """The first task type in the pull request that skips the check, as a message."""
    changed = _git(
        root, "diff", "--name-only", "--diff-filter=AM", base, "HEAD", "--", "state/tasks"
    )
    for path in sorted(changed.split()):
        try:
            task = json.loads(_git(root, "show", f"HEAD:{path}"))
        except json.JSONDecodeError:
            continue
        if isinstance(task, dict) and task.get("type") in SKIP_TYPES:
            return f"SKIPPED: {task.get('id', path)} declares type {task['type']}"
    return None


def run_old(root: Path, base: str, support: list[str], test_files: list[str]) -> str:
    """Run ``test_files`` on the code at ``base``, with the new versions of the ``support``
    files copied in; return the JUnit XML report.

    Whole files are run, not node ids, and collection errors do not stop the session: a node id
    inside a module that cannot be imported would otherwise abort the run with no results.
    """
    work = Path(tempfile.mkdtemp(prefix="red-check-"))
    tree = work / "tree"
    _git(root, "worktree", "add", "--detach", str(tree), base)
    try:
        for path in support:
            target = tree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_git(root, "show", f"HEAD:{path}"), encoding="utf-8")
        report = work / "report.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *test_files,
            "-q",
            "-p",
            "no:cacheprovider",
            "--continue-on-collection-errors",
        ]
        subprocess.run(
            [*command, f"--junitxml={report}"],
            cwd=tree,
            capture_output=True,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
            check=False,
        )
        if not report.exists():
            raise StateError("pytest produced no report on the old code")
        return report.read_text(encoding="utf-8")
    finally:
        _git(root, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """Check that the tests added since --base fail on the old code."""
    parser = argparse.ArgumentParser(description="Every added test must fail on the old code.")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--base", required=True, help="the branch the PR merges into")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        merge_base = _git(root, "merge-base", args.base, "HEAD").strip()
        declaration = skip_declaration(root, merge_base)
        if declaration:
            sys.stdout.write(declaration + "\n")
            return 0
        prefixes = load_config(root).test_prefixes
        diff = _git(root, "diff", "--name-only", "--diff-filter=AM", merge_base, "HEAD")
        test_files = [p for p in diff.split() if _is_test_file(p, prefixes)]
        added: list[str] = []
        declared: dict[str, str] = {}
        for path in test_files:
            try:
                old: str | None = _git(root, "show", f"{merge_base}:{path}")
            except StateError:
                old = None
            new = _git(root, "show", f"HEAD:{path}")
            added.extend(added_tests(path, old, new))
            declared.update(characterization(path, new))
        added = [node_id for node_id in added if node_id not in declared]
        for node_id, reason in sorted(declared.items()):
            sys.stdout.write(f"DECLARED characterization: {node_id}: {reason}\n")
        if not added:
            sys.stdout.write("OK: no added tests to check.\n")
            return 0
        support = [p for p in diff.split() if p.startswith(prefixes) and p.endswith(".py")]
        report = run_old(root, merge_base, sorted(set(support)), test_files)
        passing, missing = not_red(report, added)
    except StateError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    if missing:
        for node_id in missing:
            sys.stderr.write(f"ERROR: {node_id} did not run on the old code\n")
        return 2
    for node_id in passing:
        sys.stderr.write(
            f"PROBLEM: {node_id} passes on the old code; it did not drive the change\n"
        )
    if passing:
        return 1
    count = len(added)
    noun = "test" if count == 1 else "tests"
    sys.stdout.write(f"OK: {count} added {noun} failed on the old code.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
