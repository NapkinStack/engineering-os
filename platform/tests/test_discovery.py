"""
Discovery (PDR-0002, extension of 2026-09-16): `nstack discover` and rule C7. Every rule
proves it fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import pytest

from napkinstack import cli
from napkinstack.fitness import plan
from test_plan import TODAY, framed, write

TEMPLATE = "---\ndecision: proposed\ndecider: \"@<github-handle>\"\ndecided_on:\nidea: \"<idea file>\"\n---\n\n# Discovery\n"


def project(root):
    """A generated project's docs/project/, with the discovery template only."""
    (root / "docs" / "project").mkdir(parents=True)
    (root / "docs" / "project" / "_DISCOVERY_TEMPLATE.md").write_text(TEMPLATE, encoding="utf-8")


def idea(root, name: str = "idea.md"):
    path = root.parent / f"{root.name}-{name}"
    path.write_text("A shop where neighbours lend each other tools.\n", encoding="utf-8")
    return path


def discover(root, source, capsys) -> tuple[int, str]:
    code = cli.main(["discover", str(source), "--root", str(root)])
    return code, capsys.readouterr().out


def test_discover_starts_a_discovery(tmp_path, capsys):
    project(tmp_path)
    source = idea(tmp_path)
    code, output = discover(tmp_path, source, capsys)
    assert code == 0, output
    kept = tmp_path / "docs" / "project" / "inputs" / source.name
    assert kept.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    document = (tmp_path / "docs" / "project" / "discovery.md").read_text(encoding="utf-8")
    assert f'idea: "docs/project/inputs/{source.name}"' in document and "decision: proposed" in document
    assert f"Follow playbooks/discovery.md on docs/project/inputs/{source.name}" in output
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


DISCOVER_REFUSALS = {
    "not a project": (lambda r: None, "idea.md", "_DISCOVERY_TEMPLATE.md not found"),
    "not a text file": (project, "idea.pdf", "a Markdown or text file expected"),
    "discovery already started": (lambda r: (project(r), (r / "docs" / "project" / "discovery.md").write_text("x")),
                                  "idea.md", "discovery.md already exists"),
}


@pytest.mark.parametrize(("prepare", "name", "expected"), DISCOVER_REFUSALS.values(), ids=DISCOVER_REFUSALS.keys())
def test_discover_refuses(tmp_path, capsys, prepare, name, expected):
    prepare(tmp_path)
    code, output = discover(tmp_path, idea(tmp_path, name), capsys)
    assert code == 1 and "FAIL [discover]" in output and expected in output, output


def decided(decision: str, **changes) -> dict:
    data = {"decision": decision, "decider": "@alice", "decided_on": TODAY.isoformat(),
            "challenger": "@bob", "idea": "docs/project/inputs/idea.md"}
    return {key: value for key, value in {**data, **changes}.items() if value is not None}


DISCOVERY_CASES = {
    "C7 unknown decision": (lambda r: write(r, "discovery.md", decided("maybe")), "C7", True),
    "C7 decided without a decider": (lambda r: write(r, "discovery.md", decided("kill", decider="")), "C7", True),
    "C7 decided without a date": (lambda r: write(r, "discovery.md", decided("clarify", decided_on=None)), "C7", True),
    "C7 charter accepted before a go": (lambda r: (write(r, "discovery.md", decided("clarify")), framed(r)), "C7", True),
    "C7 go without a challenger": (lambda r: write(r, "discovery.md", decided("go", challenger="")), "C7", True),
    "C7 decider not a person": (lambda r: write(r, "discovery.md", decided("go", decider="the team")), "C7", True),
    "C7 challenger left as the template's (D51)": (lambda r: write(
        r, "discovery.md", decided("go", challenger="@<github-handle>")), "C7", True),
    "C1 discovery without front matter": (lambda r: write(r, "discovery.md", "# Discovery"), "C1", True),
}


@pytest.mark.parametrize(("prepare", "rule", "fails"), DISCOVERY_CASES.values(), ids=DISCOVERY_CASES.keys())
def test_discovery_rules(tmp_path, capsys, prepare, rule, fails):
    prepare(tmp_path)
    code = plan.run(tmp_path)
    output = capsys.readouterr().out
    assert f"[{rule}]" in output, output
    assert code == (1 if fails else 0), output


def test_charter_after_a_go(tmp_path, capsys):
    write(tmp_path, "discovery.md", decided("go"))
    framed(tmp_path)
    assert plan.run(tmp_path) == 0, capsys.readouterr().out
