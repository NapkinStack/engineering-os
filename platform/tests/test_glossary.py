"""D131, PDR-0014: a person finds what the framework's words mean, and the glossary stays true.

The terms a person must find are read from where the framework defines them — the postures'
table, the states the forms allow, the values a manifest accepts, the labels the checklist asks
for — never listed by hand; each must be a glossary entry. And a glossary term no file of the
framework uses any more is reported. Run by platform/tests/run.sh.
"""

from __future__ import annotations

import re
from pathlib import Path

from napkinstack import doctor

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
GLOSSARY = SKELETON / ".nstack/handbook/glossary.md"


def entries() -> str:
    """The glossary's first column, lower case: every term and state it defines."""
    rows = [line.split("|")[1] for line in GLOSSARY.read_text(encoding="utf-8").splitlines()
            if line.startswith("| **")]
    return " ".join(rows).lower()


def postures() -> set[str]:
    text = (SKELETON / ".nstack/handbook/05-workflow.md").read_text(encoding="utf-8")
    section = text[text.index("## 10. Postures"):]
    return {name.rstrip("s").lower() for name in re.findall(r"^\| \*\*(\w+)\*\* \|", section, re.M)}


def allowed(form: str, key: str) -> set[str]:
    """The values a form's front matter allows for a key: its comment `a | b | c`."""
    text = (SKELETON / ".nstack/forms" / form).read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if re.match(rf"\s*{key}:", line))
    return {re.sub(r"\s*\(.*", "", value).strip().lower() for value in line.split("#", 1)[1].split("—")[0].split("|")}


def manifest_values(key: str) -> set[str]:
    text = (ROOT / "src/napkinstack/templates/module/MANIFEST.yaml").read_text(encoding="utf-8")
    lines = text.splitlines()
    at = next(n for n, line in enumerate(lines) if re.match(rf"\s*{key}:", line))
    comment = next(line for line in reversed(lines[:at]) if "|" in line and line.strip().startswith("#"))
    return {re.sub(r"\s*\(.*", "", value).strip(" #").lower() for value in comment.split("|")}


def required() -> set[str]:
    return (postures() | allowed("cycle.md", "state") | allowed("cycle.md", "status")
            | allowed("discovery.md", "decision") | manifest_values("criticality")
            | manifest_values("lifecycle") | set(doctor.LABELS) - set(doctor.ISSUES))


def test_the_sources_name_the_terms_the_test_expects():
    assert {"decider", "verifier", "ready", "in-progress", "kill", "critical", "deprecated", "over-budget"} <= required()


def test_every_term_a_person_meets_has_an_entry():
    defined = entries()
    missing = sorted(term for term in required() if term not in defined)
    assert not missing, f"no glossary entry for: {missing}"


def test_every_term_of_the_glossary_is_still_used_by_the_framework():
    corpus = " ".join(path.read_text(encoding="utf-8", errors="ignore").lower()
                      for base in (SKELETON, ROOT / "src/napkinstack")
                      for path in base.rglob("*") if path.is_file() and path != GLOSSARY
                      and path.suffix in {".md", ".py", ".yml", ".yaml", ".jinja", ".sh"})
    terms = [term.strip() for row in entries().split("**") for term in re.split(r"[·/]", row)
             if term.strip() and not term.strip().startswith(("|", "("))]
    unused = sorted(term for term in terms if term not in corpus)
    assert not unused, f"in the glossary, used nowhere: {unused}"


def test_the_kernel_and_every_form_point_to_it():
    assert "glossary.md" in (SKELETON / "AGENTS.md").read_text(encoding="utf-8")
    for form in sorted((SKELETON / ".nstack/forms").glob("*.md")):
        if form.name == "rules.md":  # the project's own rules: it names no framework file (test_levels)
            continue
        assert "glossary.md" in form.read_text(encoding="utf-8"), form.name


def test_a_judging_command_that_fails_says_where_its_codes_and_words_are_explained(tmp_path, capsys):
    from napkinstack import cli

    (tmp_path / "body.md").write_text("A change.\n", encoding="utf-8")
    code = cli.main(["pr-check", "--root", str(tmp_path), "--base", "no-such-base", "--body-file", str(tmp_path / "body.md")])
    out = capsys.readouterr().out
    assert code == 1 and ".nstack/handbook/RULES.md" in out and ".nstack/handbook/glossary.md" in out, out
