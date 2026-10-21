"""D141, PDR-0018, ADR-0010: git is required; the forge is the project's choice. Projects are
created from the working tree, as platform/tests/run.sh does. Every case proves its rule fails (P5)
and names itself (P6).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from napkinstack import project

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
EXPECTED = {
    "github": {"present": [".github/workflows", ".github/CODEOWNERS", ".github/pull_request_template.md",
                           ".github/dependabot.yml", ".github/ISSUE_TEMPLATE"],
               "absent": ["CODEOWNERS", ".gitlab", ".gitea", "docs/pull_request_template.md"]},
    "gitlab": {"present": ["CODEOWNERS", ".gitlab/merge_request_templates/Default.md"],
               "absent": [".github", ".gitea", "docs/pull_request_template.md"]},
    "forgejo": {"present": ["CODEOWNERS", ".gitea/pull_request_template.md"],
                "absent": [".github", ".gitlab", "docs/pull_request_template.md"]},
    "gitea": {"present": ["CODEOWNERS", ".gitea/pull_request_template.md"],
              "absent": [".github", ".gitlab", "docs/pull_request_template.md"]},
    "other": {"present": ["CODEOWNERS", "docs/pull_request_template.md"], "absent": [".github", ".gitlab", ".gitea"]},
    "none": {"present": ["CODEOWNERS", "docs/pull_request_template.md"], "absent": [".github", ".gitlab", ".gitea"]},
}


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


def create(tmp_path: Path, forge: str, **more) -> Path:
    answers = {"project_name": "Demo", "owner_team": "acme/platform", "forge": forge,
               **({"github_repo": "acme/demo"} if forge == "github" else {}),
               **({"repository": "acme/sub/demo"} if forge in ("gitlab", "forgejo", "gitea", "other") else {}), **more}
    destination = tmp_path / forge
    assert project.init(destination, answers, str(ROOT), "HEAD") == 0
    return destination


@pytest.fixture(scope="module")
def created(tmp_path_factory):
    os.environ.update(IDENTITY)
    base = tmp_path_factory.mktemp("forges")
    return {forge: create(base, forge) for forge in EXPECTED}


@pytest.mark.parametrize("forge", list(EXPECTED))
def test_each_forge_gets_the_method_s_files_where_it_reads_them(created, forge):
    root = created[forge]
    for path in EXPECTED[forge]["present"]:
        assert (root / path).exists(), f"{forge}: {path} missing"
    for path in EXPECTED[forge]["absent"]:
        assert not (root / path).exists(), f"{forge}: {path} written"


@pytest.mark.parametrize("forge", list(EXPECTED))
def test_the_answers_say_the_forge_and_only_its_own_repository(created, forge):
    answers = yaml.safe_load((created[forge] / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert answers["forge"] == forge
    assert ("github_repo" in answers) is (forge == "github")
    assert answers["checks"] == ("forge" if forge == "github" else "attested")


@pytest.mark.parametrize("forge", [forge for forge in EXPECTED if forge != "github"])
def test_off_github_no_file_links_to_the_project_s_forge_on_github(created, forge):
    root = created[forge]
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.suffix in {".md", ".yml", ".yaml", ""}:
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "github.com/acme" not in text, f"{forge}: {path.relative_to(root)} links to the project on GitHub"


def test_the_ownership_file_and_the_pull_request_form_are_one_content(created):
    github, gitlab = created["github"], created["gitlab"]
    assert (gitlab / "CODEOWNERS").read_text(encoding="utf-8").split("\n# Foundation")[0] == \
        (github / ".github/CODEOWNERS").read_text(encoding="utf-8").split("\n# Foundation")[0]
    assert (gitlab / ".gitlab/merge_request_templates/Default.md").read_text(encoding="utf-8") == \
        (github / ".github/pull_request_template.md").read_text(encoding="utf-8")


def test_the_engine_reads_the_forge_and_its_ownership_file(created, tmp_path):
    assert project.forge(created["gitlab"]) == "gitlab"
    assert project.ownership(created["gitlab"]) == created["gitlab"] / "CODEOWNERS"
    assert project.ownership(created["github"]) == created["github"] / ".github/CODEOWNERS"
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.13.0\ngithub_repo: a/b\n", encoding="utf-8")
    assert project.forge(tmp_path) == "github"  # an answers file without the answer: GitHub, as it was


def test_new_module_writes_its_owner_where_the_forge_reads_ownership(created):
    from napkinstack import modules

    root = created["gitlab"]
    assert modules.create(root, "billing", "acme/billing", "standard", False) == 0
    assert "/modules/billing/" in (root / "CODEOWNERS").read_text(encoding="utf-8")


def test_init_s_next_steps_off_github_name_no_github_setting(tmp_path, capsys):
    create(tmp_path, "gitlab")
    out = capsys.readouterr().out
    assert "GitHub" not in out.split("Next steps:")[1]
    assert "nstack attest" in out and "unguarded" in out


def test_a_github_repository_is_refused_off_github(tmp_path, capsys):
    answers = {"project_name": "Demo", "owner_team": "acme/platform", "forge": "gitlab",
               "repository": "acme/demo", "github_repo": "acme/demo"}
    assert project.init(tmp_path / "x", answers, str(ROOT), "HEAD") == 1
    assert "github_repo" in capsys.readouterr().out


def test_a_github_project_s_update_writes_forge_github_and_changes_nothing_else(tmp_path, capsys):
    """A project made before the question: the update names its forge, and the files stay."""
    import subprocess

    old = tmp_path / "old"
    answers = {"project_name": "Demo", "github_repo": "acme/demo", "owner_team": "acme/platform"}
    assert project.init(old, answers, str(ROOT), "v0.14.0") == 0
    assert "forge" not in yaml.safe_load((old / ".copier-answers.yml").read_text(encoding="utf-8"))
    before = {path.relative_to(old).as_posix() for path in old.rglob("*") if path.is_file() and ".git" not in path.parts}
    assert project.update(old, "HEAD") == 0
    after = {path.relative_to(old).as_posix() for path in old.rglob("*") if path.is_file() and ".git" not in path.parts}
    updated = yaml.safe_load((old / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert updated["forge"] == "github" and updated["github_repo"] == "acme/demo"
    assert after == before, f"files added or removed: {sorted(after ^ before)}"


# --- what the verifier of part 1 found --------------------------------------------------------

def test_a_forge_chosen_interactively_still_gets_attested_checks(tmp_path):
    """Asked by Copier, the forge is unknown before the copy: the engine settles `checks` after it."""
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.15.0\nforge: gitlab\nchecks: forge\n", encoding="utf-8")
    project.settle_checks(tmp_path, given={})
    assert "checks: attested" in (tmp_path / ".copier-answers.yml").read_text(encoding="utf-8")
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.15.0\nforge: gitlab\nchecks: forge\n", encoding="utf-8")
    project.settle_checks(tmp_path, given={"checks": "forge"})  # the decider said it: kept
    assert "checks: forge" in (tmp_path / ".copier-answers.yml").read_text(encoding="utf-8")


def test_doctor_reads_the_ownership_file_where_the_forge_has_it(created):
    from napkinstack import doctor

    assert doctor._default_owner(created["gitlab"])[0] == doctor.OK


@pytest.mark.parametrize("forge, accepted", [("gitlab", True), ("github", False)])
def test_a_subgroup_owner_is_accepted_where_the_forge_has_subgroups(created, forge, accepted):
    from napkinstack import modules

    assert (modules.create(created[forge], f"pay-{forge}", "acme/sub/pay", "standard", False) == 0) is accepted


def test_a_contract_off_github_has_its_owner_as_contact_never_a_github_link(created):
    from napkinstack import modules

    root = created["gitlab"]
    assert modules.create_contract(root, "orders", None) == 0
    manifest = (root / "contracts/MANIFEST.yaml").read_text(encoding="utf-8")
    assert "github.com" not in manifest and "acme/platform" in manifest


@pytest.mark.parametrize("forge", ["github", "none"])
def test_a_repository_path_is_refused_where_the_forge_takes_none(tmp_path, capsys, forge):
    answers = {"project_name": "Demo", "owner_team": "acme/platform", "forge": forge, "repository": "acme/demo",
               **({"github_repo": "acme/demo"} if forge == "github" else {})}
    assert project.init(tmp_path / forge, answers, str(ROOT), "HEAD") == 1
    assert "repository" in capsys.readouterr().out


def test_a_description_file_that_does_not_exist_is_said_never_a_traceback(tmp_path, capsys):
    from napkinstack import pull_request

    assert pull_request.run(tmp_path, "HEAD", tmp_path / "missing.md") == 1
    assert "FAIL [pr-check]" in capsys.readouterr().out
