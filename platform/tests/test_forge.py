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


# --- off GitHub, what the engine says (ADR-0010 §4-§9) -----------------------------------------

def _all_ok(monkeypatch):
    from napkinstack import doctor

    real = doctor._workstation

    def workstation(root, answers):  # the engine's own rules, every other one compliant
        return [(rule, setting, doctor.OK if rule != "L8" else status, detail if rule == "L8" else "")
                for rule, setting, status, detail in real(root, answers)]

    monkeypatch.setattr(doctor, "_workstation", workstation)
    monkeypatch.setattr(doctor, "_newer", lambda answers: None)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def test_doctor_off_github_reads_no_github_setting_and_says_unguarded(created, monkeypatch, capsys):
    from napkinstack import doctor

    _all_ok(monkeypatch)
    assert doctor.run(created["gitlab"]) == 0  # the workstation's rules alone: no token is not "not verified"
    out = capsys.readouterr().out
    assert "[G" not in out and "GitHub:" not in out and "token" not in out
    assert "unguarded" in out and "gitlab" in out
    for protection in doctor.PROTECTIONS:
        assert protection in out
    assert "nstack landed" in out and "does not run" in out


def test_doctor_on_github_still_reads_its_settings(created, monkeypatch, capsys):
    from napkinstack import doctor

    _all_ok(monkeypatch)
    assert doctor.run(created["github"]) == 2
    assert "[G1]" in capsys.readouterr().out


def test_checks_forge_off_github_is_a_contradiction(created):
    from napkinstack import doctor

    root = created["forgejo"]
    answers = yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))
    said = {rule: (status, detail) for rule, _, status, detail in doctor._workstation(root, {**answers, "checks": "forge"})}
    assert said["L8"][0] == doctor.GAP and "attested" in said["L8"][1]
    said = {rule: status for rule, _, status, _ in doctor._workstation(root, answers)}
    assert said["L8"] == doctor.OK


def test_l8_is_not_said_on_github(created):
    from napkinstack import doctor

    answers = yaml.safe_load((created["github"] / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert "L8" not in {rule for rule, *_ in doctor._workstation(created["github"], answers)}


@pytest.mark.parametrize("forge, said", [("forgejo", "not read by"), ("gitea", "not read by"), ("none", "No forge reads")])
def test_l6_says_when_no_forge_reads_the_ownership_file(created, forge, said):
    from napkinstack import doctor

    status, detail = doctor._default_owner(created[forge])
    assert status == doctor.OK and said in detail


@pytest.mark.parametrize("forge", [forge for forge in EXPECTED if forge != "github"])
def test_install_lists_the_forge_neutral_protections_off_github(created, forge):
    from napkinstack import doctor

    manual = (created[forge] / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")
    for protection in doctor.PROTECTIONS:
        assert f"- [ ] {protection}" in manual, f"{forge}: '{protection}' not in INSTALL.md"
    assert "Settings → Rules" not in manual


def test_install_on_github_keeps_its_checklist(created):
    from napkinstack import doctor

    manual = (created["github"] / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")
    assert all(f"- [ ] {setting}" in manual for rule, setting, _ in doctor.CHECKLIST)


def test_settings_off_github_has_nothing_to_apply(created, capsys, monkeypatch):
    from napkinstack import settings

    monkeypatch.setenv("GH_TOKEN", "a-token-never-used")
    assert settings.run(created["gitlab"]) == 0
    out = capsys.readouterr().out
    assert "nothing to apply" in out and "gitlab" in out and "--method" not in out


def _remote(root: Path, url: str) -> None:
    import subprocess

    subprocess.run(["git", "remote", "remove", "origin"], cwd=root, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", url], cwd=root, check=True)


def test_the_displays_off_github_are_not_shown_and_say_the_forge(created, monkeypatch):
    from napkinstack import hold

    root = created["gitlab"]
    _remote(root, "https://github.com/acme/demo.git")  # even a GitHub remote: the answer says gitlab
    monkeypatch.setenv("GH_TOKEN", "a-token-never-used")
    assert hold._forge(root, "origin") is None
    assert hold.unshown(root) == "not shown — forge gitlab"


def test_github_enterprise_server_is_github(created, monkeypatch):
    from napkinstack import hold

    root = created["github"]
    _remote(root, "https://git.example.corp/acme/demo.git")
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setenv("GITHUB_API_URL", "https://git.example.corp/api/v3")
    assert hold._forge(root, "origin") == ("https://git.example.corp/api/v3", "acme/demo", "t")
    _remote(root, "../clone-of-demo")  # a clone of a checkout: never the project's forge
    assert hold._forge(root, "origin") is None


def test_the_board_off_github_says_the_forge(created, monkeypatch, capsys):
    from napkinstack import board

    monkeypatch.setattr(board, "desired", lambda root, *args, **kwargs: ([object()], []))
    assert board.run(created["gitlab"]) == 0
    assert "not shown — forge gitlab" in capsys.readouterr().out


def test_attest_s_display_off_github_says_the_forge(created, monkeypatch):
    from napkinstack import attest

    monkeypatch.setenv("GH_TOKEN", "a-token-never-used")
    assert attest._show(created["forgejo"], "0" * 40, 5, 5) == "not shown — forge forgejo"


@pytest.mark.parametrize("forge, checks, said, unsaid", [
    ("github", "forge", "CI validates it", "nstack attest"),
    ("github", "attested", "nstack attest", "CI validates it"),
    ("gitlab", "attested", "nstack attest", "CI validates it"),
    ("none", "attested", "nstack attest", "open the pull request"),
])
def test_update_s_next_step_says_who_checks(tmp_path, forge, checks, said, unsaid):
    (tmp_path / ".copier-answers.yml").write_text(f"_commit: v0.15.0\nforge: {forge}\nchecks: {checks}\n", encoding="utf-8")
    step = project.next_step(tmp_path, "nstack/update-v0.15.0")
    assert said in step and unsaid not in step


# --- pr-check off GitHub -------------------------------------------------------------------------

def _off(root: Path, forge: str) -> None:
    (root / ".copier-answers.yml").write_text(f"_commit: v0.15.0\nforge: {forge}\nchecks: forge\n", encoding="utf-8")


def test_pr_check_off_github_says_how_the_verifier_was_compared(tmp_path, capsys, monkeypatch):
    from test_pull_request import PASSED, USER_FACING, change, check, sheet

    base, head = change(tmp_path, USER_FACING)
    _off(tmp_path, "gitlab")
    check(tmp_path, base, head, sheet(PASSED), monkeypatch)
    assert "no person is recognised as an author off GitHub" in capsys.readouterr().out
    (tmp_path / ".copier-answers.yml").unlink()
    check(tmp_path, base, head, sheet(PASSED), monkeypatch)
    assert "off GitHub" not in capsys.readouterr().out


def test_with_no_forge_and_no_sheet_the_test_rules_say_no_carrier(tmp_path, capsys, monkeypatch):
    from test_pull_request import USER_FACING, change, check

    base, head = change(tmp_path, USER_FACING)
    _off(tmp_path, "none")  # attest with no --body-file passes an empty description
    check(tmp_path, base, head, "", monkeypatch, deliverable_line=None)
    out = capsys.readouterr().out
    assert "no carrier" in out and "[T1]" not in out
    check(tmp_path, base, head, "", monkeypatch)  # a description passed: its sheet is judged
    assert "[T1]" in capsys.readouterr().out
    _off(tmp_path, "gitlab")  # a forge with pull requests: a missing sheet stays a failure
    check(tmp_path, base, head, "", monkeypatch, deliverable_line=None)
    assert "[T1]" in capsys.readouterr().out
