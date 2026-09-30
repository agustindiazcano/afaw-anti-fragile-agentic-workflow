"""Tests for scripts.project_config: per-project settings read from state/config.json."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.project_config import DEFAULT_CODE_PREFIXES, ProjectConfig, load_config
from scripts.state_common import StateError

if TYPE_CHECKING:
    from tests.tooling.conftest import Project


def test_defaults_apply_when_there_is_no_config_file(project: Project) -> None:
    config = load_config(project.root)
    assert config == ProjectConfig()
    assert config.code_prefixes == DEFAULT_CODE_PREFIXES
    assert config.mutation_critical_paths == ()
    assert config.mutation_min_score == 80.0


def test_values_are_read_from_the_config_file(project: Project) -> None:
    project.write(
        "state/config.json",
        {
            "code_prefixes": ["app/", "spec/"],
            "ignored_names": ["placeholder.txt"],
            "test_prefixes": ["spec/"],
            "mutation_critical_paths": ["app/payments/"],
            "mutation_min_score": 90.5,
        },
    )
    config = load_config(project.root)
    assert config.code_prefixes == ("app/", "spec/")
    assert config.ignored_names == frozenset({"placeholder.txt"})
    assert config.test_prefixes == ("spec/",)
    assert config.mutation_critical_paths == ("app/payments/",)
    assert config.mutation_min_score == 90.5


def test_missing_keys_fall_back_one_by_one(project: Project) -> None:
    project.write("state/config.json", {"mutation_min_score": 70})
    config = load_config(project.root)
    assert config.mutation_min_score == 70.0
    assert config.code_prefixes == DEFAULT_CODE_PREFIXES


def test_score_out_of_range_is_rejected(project: Project) -> None:
    project.write("state/config.json", {"mutation_min_score": 150})
    with pytest.raises(StateError, match="mutation_min_score"):
        load_config(project.root)


def test_critical_paths_must_be_a_list(project: Project) -> None:
    project.write("state/config.json", {"mutation_critical_paths": "src/"})
    with pytest.raises(StateError, match="mutation_critical_paths"):
        load_config(project.root)


def test_file_classification() -> None:
    config = ProjectConfig(
        code_prefixes=("src/", "tests/"),
        test_prefixes=("tests/",),
        mutation_critical_paths=("src/pay/",),
    )
    assert config.is_code("tests/test_a.py")
    assert not config.is_source("tests/test_a.py")
    assert config.is_source("src/util.py")
    assert not config.is_critical("src/util.py")
    assert config.is_critical("src/pay/charge.py")
    assert not config.is_code("docs/a.md")
    assert not config.is_code("src/.gitkeep")
    assert not config.is_critical("docs/pay/charge.py")
    assert not config.is_critical("tests/pay/test_charge.py")


def test_dashboard_settings_are_accepted(project: Project) -> None:
    project.write(
        "state/config.json",
        {
            "dashboard": {
                "stale_days": 3,
                "knowledge_budget": 40,
                "role_tags": {"backend": ["db"]},
                "reference_docs": ["README.md"],
            }
        },
    )
    assert load_config(project.root).code_prefixes == ("src/", "tests/", "scripts/")


def test_unknown_dashboard_setting_is_rejected(project: Project) -> None:
    project.write("state/config.json", {"dashboard": {"stale_dayz": 3}})
    with pytest.raises(StateError, match="stale_dayz"):
        load_config(project.root)
