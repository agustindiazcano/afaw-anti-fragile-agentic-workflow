"""Per-project settings read from state/config.json.

Which folders are code, which hold tests and where mutation testing is mandatory depend on the
project's stack and risk, so they are configuration, not code. Any missing key (or a missing
file) falls back to the defaults below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.state_common import load_json, load_validated

CONFIG_PATH = "state/config.json"
CONFIG_SCHEMA_PATH = "state/schemas/config.schema.json"
DEFAULT_CODE_PREFIXES = ("src/", "tests/", "scripts/")
DEFAULT_IGNORED_NAMES = (".gitkeep",)
DEFAULT_TEST_PREFIXES = ("tests/",)
DEFAULT_MUTATION_MIN_SCORE = 80.0  # a starting value, not a measured one; set it per project


@dataclass(frozen=True)
class ProjectConfig:
    """The settings of one project."""

    code_prefixes: tuple[str, ...] = DEFAULT_CODE_PREFIXES
    ignored_names: frozenset[str] = frozenset(DEFAULT_IGNORED_NAMES)
    test_prefixes: tuple[str, ...] = DEFAULT_TEST_PREFIXES
    mutation_critical_paths: tuple[str, ...] = ()
    mutation_min_score: float = DEFAULT_MUTATION_MIN_SCORE

    def is_code(self, path: str) -> bool:
        """True if the file lives under a code folder and is not an ignored name."""
        return path.startswith(self.code_prefixes) and Path(path).name not in self.ignored_names

    def is_source(self, path: str) -> bool:
        """True if the file is code but not a test (the files mutation testing can mutate)."""
        return self.is_code(path) and not path.startswith(self.test_prefixes)

    def is_critical(self, path: str) -> bool:
        """True if the file is source code under a folder where mutation testing is mandatory."""
        return self.is_source(path) and path.startswith(self.mutation_critical_paths)


def load_config(root: Path) -> ProjectConfig:
    """Read state/config.json (validated against its schema) or return the defaults."""
    path = root / CONFIG_PATH
    if not path.exists():
        return ProjectConfig()
    data = load_validated(path, load_json(root / CONFIG_SCHEMA_PATH))
    defaults = ProjectConfig()
    return ProjectConfig(
        code_prefixes=tuple(data.get("code_prefixes", defaults.code_prefixes)),
        ignored_names=frozenset(data.get("ignored_names", defaults.ignored_names)),
        test_prefixes=tuple(data.get("test_prefixes", defaults.test_prefixes)),
        mutation_critical_paths=tuple(
            data.get("mutation_critical_paths", defaults.mutation_critical_paths)
        ),
        mutation_min_score=float(data.get("mutation_min_score", defaults.mutation_min_score)),
    )
