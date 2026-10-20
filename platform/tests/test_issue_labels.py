"""D128: every label a shipped issue template declares is one the checklist asks for, and one
`nstack settings` creates.

The templates declared `request`, `architecture`, `debt` and `acceptance`; the checklist (G11)
and `settings` knew only the three pull-request exceptions. GitHub drops a label that does not
exist without a word, so an issue filed through such a template arrived unlabelled — on every
project set up by nstack (engineering-os #190).
"""

from pathlib import Path

import yaml

from napkinstack import doctor, settings

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = sorted((ROOT / "skeleton/.github/ISSUE_TEMPLATE").glob("*.yml"))


def declared() -> set[str]:
    """The labels the shipped issue templates put on an issue."""
    found: set[str] = set()
    for path in TEMPLATES:
        found.update(yaml.safe_load(path.read_text(encoding="utf-8")).get("labels") or [])
    return found


def test_the_skeleton_ships_issue_templates_with_labels():
    assert declared(), "no issue template with a label found in the skeleton"


def test_the_checklist_asks_for_every_label_a_template_declares():
    assert declared() <= set(doctor.LABELS), f"missing from G11: {sorted(declared() - set(doctor.LABELS))}"


def test_settings_creates_every_label_the_checklist_asks_for_with_its_colour_and_meaning():
    calls, _ = settings.plan(None, {"G11"})
    created = {body["name"]: body for rule, method, path, body in calls if rule == "G11"}
    assert set(created) == set(doctor.LABELS)
    for name, body in created.items():
        assert len(body["color"]) == 6 and body["description"], name
        # GitHub refuses a label description longer than 100 characters.
        assert len(body["description"]) <= 100, name


def test_an_issue_labels_meaning_is_its_templates_own_words():
    for path in TEMPLATES:
        template = yaml.safe_load(path.read_text(encoding="utf-8"))
        for label in template.get("labels") or []:
            assert settings.LABEL_MEANING[label] == template["description"], (label, path.name)
