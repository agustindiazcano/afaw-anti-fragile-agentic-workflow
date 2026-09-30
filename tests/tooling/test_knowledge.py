import pytest

from scripts.afaw_state.knowledge import broken_links, check_knowledge, parse_doc

ADR = """---
status: accepted
date: 2026-09-24
supersedes: [0003]
tags: [llm, judges]
---
# Judges stay asymmetric

## Context
Two judges from the same family share blind spots.

## Decision
Judge 1 on Gemini, judge 2 on GPT-OSS.

## Alternatives considered
Two Gemini judges: rejected, correlated errors.

## Consequences
Two providers to operate.
"""

OLD = """---
status: superseded
date: 2026-09-10
tags: [llm]
---
# Both judges on Gemini

## Context
x
## Decision
x
## Alternatives considered
x
## Consequences
x
"""

GOTCHA = """---
status: active
date: 2026-09-23
tags: [infra, terraform]
---
# Terraform plan hangs silently

## Symptom
`terraform plan` prints nothing for minutes.

## What to do
Wait a minute and re-run.
"""


def test_parse_adr():
    doc = parse_doc("docs/adr/0007-judges-asymmetric.md", ADR)
    assert doc["id"] == "0007"
    assert doc["kind"] == "adr"
    assert doc["title"] == "Judges stay asymmetric"
    assert doc["meta"] == {
        "status": "accepted",
        "date": "2026-09-24",
        "supersedes": ["0003"],
        "tags": ["llm", "judges"],
    }
    assert doc["sections"] == ["context", "decision", "alternatives considered", "consequences"]


def test_parse_gotcha():
    doc = parse_doc("docs/gotchas/0002-terraform-429.md", GOTCHA)
    assert (doc["kind"], doc["id"], doc["title"]) == (
        "gotcha",
        "0002",
        "Terraform plan hangs silently",
    )


def test_parse_rejects_unknown_location():
    with pytest.raises(ValueError):
        parse_doc("docs/notes/0001-x.md", ADR)


def docs(*pairs):
    return [parse_doc(p, t) for p, t in pairs]


def test_valid_set_has_no_errors():
    assert (
        check_knowledge(
            docs(
                ("docs/adr/0003-both-gemini.md", OLD),
                ("docs/adr/0007-judges-asymmetric.md", ADR),
                ("docs/gotchas/0002-terraform-429.md", GOTCHA),
            )
        )
        == []
    )


def test_bad_file_name():
    errors = check_knowledge(
        docs(("docs/adr/7-Judges.md", ADR.replace("supersedes: [0003]\n", "")))
    )
    assert any("file name must be NNNN-slug.md" in e for e in errors)


def test_missing_front_matter_and_sections():
    errors = check_knowledge(docs(("docs/adr/0001-x.md", "# Title only\n\nSome text.\n")))
    assert any("missing front matter" in e for e in errors)
    assert any("missing section: Alternatives considered" in e for e in errors)


def test_invalid_status_and_date():
    text = ADR.replace("status: accepted", "status: maybe").replace("2026-09-24", "24/09/2026")
    errors = check_knowledge(
        docs(("docs/adr/0003-both-gemini.md", OLD), ("docs/adr/0007-a.md", text))
    )
    assert any("invalid status: 'maybe'" in e for e in errors)
    assert any("invalid date" in e for e in errors)


def test_supersedes_must_exist_and_target_must_be_superseded():
    errors = check_knowledge(docs(("docs/adr/0007-a.md", ADR)))
    assert any("supersedes unknown ADR 0003" in e for e in errors)
    errors = check_knowledge(
        docs(
            ("docs/adr/0003-both-gemini.md", OLD.replace("status: superseded", "status: accepted")),
            ("docs/adr/0007-a.md", ADR),
        )
    )
    assert any("0003 is superseded by 0007 but its status is accepted" in e for e in errors)


def test_superseded_without_successor():
    errors = check_knowledge(docs(("docs/adr/0003-both-gemini.md", OLD)))
    assert any("status superseded but no ADR supersedes it" in e for e in errors)


def test_duplicate_ids():
    errors = check_knowledge(
        docs(
            ("docs/gotchas/0002-a.md", GOTCHA),
            ("docs/gotchas/0002-b.md", GOTCHA),
        )
    )
    assert any("duplicate gotcha id 0002" in e for e in errors)


@pytest.mark.parametrize("status,field", [("resolved", "resolved_by"), ("promoted", "promoted_to")])
def test_closed_gotcha_needs_its_reference(status, field):
    text = GOTCHA.replace("status: active", f"status: {status}")
    errors = check_knowledge(docs(("docs/gotchas/0002-a.md", text)))
    assert any(f"status {status} requires {field}" in e for e in errors)
    fixed = text.replace("tags:", f"{field}: task_031\ntags:")
    assert check_knowledge(docs(("docs/gotchas/0002-a.md", fixed))) == []


def test_unknown_front_matter_key():
    errors = check_knowledge(
        docs(("docs/gotchas/0002-a.md", GOTCHA.replace("tags:", "owner: me\ntags:")))
    )
    assert any("unknown front matter key: owner" in e for e in errors)


def test_broken_links():
    text = (
        "See [ADR](../adr/0007-a.md), [anchor](#top), [web](https://x.org), "
        "[missing](../architecture/nope.md#part) and ![img](img/a.png).\n"
    )
    existing = {"docs/adr/0007-a.md", "docs/gotchas/img/a.png"}
    assert broken_links("docs/gotchas/0002-a.md", text, existing) == ["../architecture/nope.md"]


def test_links_inside_code_are_not_checked():
    text = (
        "Real [link](missing.md).\n\n"
        "```markdown\n![snippet](docs/img/a.svg)\n```\n\n"
        "Inline `[not a link](x.md)` too.\n"
    )
    assert broken_links("docs/guide.md", text, set()) == ["missing.md"]
