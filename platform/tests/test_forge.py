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


def create(tmp_path: Path, forge: str, source: Path = ROOT, **more) -> Path:
    answers = {"project_name": "Demo", "owner_team": "acme/platform", "forge": forge,
               **({"github_repo": "acme/demo"} if forge == "github" else {}),
               **({"repository": "acme/sub/demo"} if forge in ("gitlab", "forgejo", "gitea", "other") else {}), **more}
    destination = tmp_path / forge
    assert project.init(destination, answers, str(source), "HEAD") == 0
    return destination


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory) -> Path:
    """The working tree, committed: a project made from a tree with changes records a commit
    Copier made for the copy, which a later render at the project's own version cannot find."""
    import shutil
    import subprocess

    destination = tmp_path_factory.mktemp("source") / "engineering-os"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(destination)], check=True)
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.split("\0")
    for name in filter(None, listed):
        if (ROOT / name).is_file():
            (destination / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination / name)
        elif (destination / name).is_file():
            (destination / name).unlink()
    subprocess.run(["git", "add", "-A"], cwd=destination, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "the working tree"], cwd=destination, check=True)
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


def test_a_github_project_s_update_keeps_its_own_lines_in_the_github_folder(tmp_path, capsys):
    """Copier excludes, from the copy it diffs against, what the new template's `_exclude` names,
    rendered with the old answers: with no `forge` there, `/.github` left that copy and every line
    a project had added under it came back as a conflict. Found rehearsing v0.15.0 on the third
    project, whose CODEOWNERS lists its modules."""
    import subprocess

    old = tmp_path / "old"
    answers = {"project_name": "Demo", "github_repo": "acme/demo", "owner_team": "acme/platform"}
    assert project.init(old, answers, str(ROOT), "v0.14.0") == 0
    owners = old / ".github" / "CODEOWNERS"
    owners.write_text(owners.read_text(encoding="utf-8") + "/modules/billing/              @acme/platform\n",
                      encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "a module"], cwd=old, check=True)
    assert project.update(old, "HEAD") == 0, capsys.readouterr().out
    text = owners.read_text(encoding="utf-8")
    assert "<<<<<<<" not in text and "/modules/billing/" in text


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
    ("github", "forge", "CI validates it", "run nstack attest"),
    ("github", "attested", "run nstack attest", "CI validates it"),
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


# --- what the verifier of part 2 found ---------------------------------------------------------

@pytest.mark.parametrize("url", ["../ghq/github.com/acme/demo", "../acme/demo", "file:///srv/git/acme/demo",
                                 "https://git.corp/x/acme/demo", "https://gitlab.com/acme/demo.git"])
def test_a_path_or_another_host_is_never_the_project_s_github(created, monkeypatch, url):
    from napkinstack import hold

    root = created["github"]
    _remote(root, url)
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setenv("GITHUB_API_URL", "https://git.example.corp/api/v3")
    assert hold._forge(root, "origin") is None


def test_a_server_of_its_own_needs_its_api_and_matches_without_case(created, monkeypatch):
    from napkinstack import hold

    root = created["github"]
    _remote(root, "git@git.example.corp:ACME/Demo.git")
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert hold._forge(root, "origin") is None  # no API named: never api.github.com for another host
    monkeypatch.setenv("GITHUB_API_URL", "https://git.example.corp/api/v3")
    assert hold._forge(root, "origin") == ("https://git.example.corp/api/v3", "acme/demo", "t")


def test_an_alias_rewritten_to_github_is_github(created, monkeypatch):
    import subprocess

    from napkinstack import hold

    root = created["github"]
    _remote(root, "work:demo")
    subprocess.run(["git", "config", "url.https://github.com/acme/.insteadOf", "work:"], cwd=root, check=True)
    monkeypatch.setenv("GH_TOKEN", "t")
    try:
        assert hold._forge(root, "origin")[1] == "acme/demo"
    finally:
        subprocess.run(["git", "config", "--unset", "url.https://github.com/acme/.insteadOf"], cwd=root)


@pytest.mark.parametrize("text", ["foo: [", "- a\n", "just text\n"])
def test_a_malformed_answers_file_is_github_never_a_traceback(tmp_path, text):
    (tmp_path / ".copier-answers.yml").write_text(text, encoding="utf-8")
    assert project.answer(tmp_path, "forge") is None and project.forge(tmp_path) == "github"


def test_landed_off_github_says_it_does_not_run(created, capsys, monkeypatch):
    from napkinstack import landed

    monkeypatch.setenv("GH_TOKEN", "t")
    assert landed.run(created["gitlab"], "HEAD~1..HEAD", landed.from_environment(created["gitlab"])) == 0
    assert "not run — forge gitlab" in capsys.readouterr().out


def test_doctor_with_no_forge_says_nothing_refuses(created, monkeypatch, capsys):
    from napkinstack import doctor

    _all_ok(monkeypatch)
    doctor.run(created["none"])
    out = capsys.readouterr().out
    assert "unguarded — no forge" in out and "forge's protections" not in out


def test_install_names_the_forge_as_people_do(created):
    assert "on GitLab" in (created["gitlab"] / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")
    assert "on your forge" in (created["other"] / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")


def test_the_no_carrier_line_names_the_description_s_file(tmp_path, capsys, monkeypatch):
    from test_pull_request import USER_FACING, change, check

    base, head = change(tmp_path, USER_FACING)
    _off(tmp_path, "none")
    check(tmp_path, base, head, "", monkeypatch, deliverable_line=None)
    assert "nstack attest --body-file" in capsys.readouterr().out
# --- changing forge (ADR-0010 §3) ----------------------------------------------------------------

def _git(root: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _adapted(root: Path) -> None:
    """A project that lived: a module, its own ownership line, a line added to its form."""
    from napkinstack import modules

    assert modules.create(root, "billing", "acme/billing", "standard", False) == 0
    owners = project.ownership(root)
    owners.write_text(owners.read_text(encoding="utf-8") + "/docs/legal/  @acme/legal\n", encoding="utf-8")
    form = next(path for path in (root / ".github/pull_request_template.md",
                                  root / ".gitlab/merge_request_templates/Default.md") if path.is_file())
    form.write_text(form.read_text(encoding="utf-8") + "\nOur own reminder: say the ticket.\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "the project's own lines")


def _answers(root: Path) -> dict:
    return yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))


def test_a_forge_change_moves_the_files_and_carries_the_project_s_lines(tmp_path, snapshot, capsys):
    root = create(tmp_path, "github", snapshot)
    _adapted(root)
    assert project.change_forge(root, "gitlab", repository="acme/sub/demo") == 0
    out = capsys.readouterr().out
    assert _git(root, "branch", "--show-current") == "nstack/forge-gitlab"
    assert not _git(root, "status", "--porcelain"), "the change is committed on its branch"
    assert not (root / ".github").exists()
    owners = (root / "CODEOWNERS").read_text(encoding="utf-8")
    assert "/modules/billing/" in owners and "/docs/legal/  @acme/legal" in owners and "<<<<<<<" not in owners
    assert "Our own reminder" in (root / ".gitlab/merge_request_templates/Default.md").read_text(encoding="utf-8")
    answers = _answers(root)
    assert answers["forge"] == "gitlab" and answers["repository"] == "acme/sub/demo"
    assert "github_repo" not in answers and answers["checks"] == "attested"
    assert "checks: attested" in out and "nstack attest" in out


def test_a_forge_change_rewrites_the_security_policy_and_keeps_the_project_s_lines(tmp_path, snapshot, capsys):
    root = create(tmp_path, "github", snapshot)
    policy = root / "SECURITY.md"
    policy.write_text(policy.read_text(encoding="utf-8") + "\nOur own: the on-call rota answers within a day.\n",
                      encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "the project's own policy line")
    assert project.change_forge(root, "gitlab", repository="acme/sub/demo") == 0
    text = policy.read_text(encoding="utf-8")
    assert "confidential issue" in text and "**Security** tab" not in text and ".github/" not in text, (
        "SECURITY.md is a seat Copier never rewrites: the forge change must, or it names GitHub's tab (#249)")
    assert "Our own: the on-call rota" in text and "<<<<<<<" not in text
    assert "SECURITY.md" in capsys.readouterr().out


def test_a_forge_change_back_to_github(tmp_path, snapshot):
    root = create(tmp_path, "gitlab", snapshot)
    _adapted(root)
    assert project.change_forge(root, "github", github_repo="acme/demo") == 0
    owners = (root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    assert "/modules/billing/" in owners and "/docs/legal/  @acme/legal" in owners
    assert not (root / "CODEOWNERS").exists() and (root / ".github/workflows").is_dir()
    assert "Our own reminder" in (root / ".github/pull_request_template.md").read_text(encoding="utf-8")
    answers = _answers(root)
    assert answers["github_repo"] == "acme/demo" and "repository" not in answers
    assert answers["checks"] == "attested"  # the decider's answer: CI runs once they say so


@pytest.mark.parametrize("forge, flags, said", [
    ("gitlab", {}, "--repository"),
    ("github", {}, "--github-repo"),
    ("none", {"repository": "acme/demo"}, "--repository"),
    ("gitlab", {"github_repo": "acme/demo"}, "github_repo"),
])
def test_a_forge_change_refuses_what_the_forge_does_not_take(tmp_path, capsys, forge, flags, said):
    root = create(tmp_path, "github" if forge != "github" else "gitlab")  # a gitlab project knows no GitHub repository
    assert project.change_forge(root, forge, **flags) == 1
    assert said in capsys.readouterr().out
    assert _git(root, "branch", "--show-current") == "main"


def test_the_same_forge_is_no_change(tmp_path, capsys):
    root = create(tmp_path, "gitlab")
    assert project.change_forge(root, "gitlab") == 0
    assert "already" in capsys.readouterr().out
    assert _git(root, "branch", "--show-current") == "main"


def _by_hand(root: Path, forge: str) -> None:
    answers = root / ".copier-answers.yml"
    text = answers.read_text(encoding="utf-8")
    answers.write_text(text.replace("forge: github", f"forge: {forge}"), encoding="utf-8")
    _git(root, "commit", "-qam", "forge changed by hand")


def test_a_forge_changed_by_hand_is_said_with_the_command(tmp_path, capsys):
    from napkinstack import doctor

    root = create(tmp_path, "github")
    _by_hand(root, "gitlab")
    assert project.update(root, "v99.0.0") == 1
    out = capsys.readouterr().out
    assert "forge: github" in out and "nstack update --forge gitlab" in out
    said = {rule: (status, detail) for rule, _, status, detail in doctor._workstation(root, _answers(root))}
    assert said["L9"][0] == doctor.GAP and "nstack update --forge gitlab" in said["L9"][1]
    assert project.change_forge(root, "forgejo", repository="acme/demo") == 1


def test_l9_is_compliant_where_the_files_are_the_forge_s(created):
    from napkinstack import doctor

    for forge in EXPECTED:
        said = {rule: status for rule, _, status, _ in doctor._workstation(created[forge], _answers(created[forge]))}
        assert said["L9"] == doctor.OK, forge


def test_a_remote_at_another_known_forge_is_said(tmp_path):
    from napkinstack import doctor

    root = create(tmp_path, "gitlab")
    _remote(root, "git@github.com:acme/demo.git")
    said = {rule: (status, detail) for rule, _, status, detail in doctor._workstation(root, _answers(root))}
    assert said["L9"][0] == doctor.OK and "github.com" in said["L9"][1] and "nstack update --forge github" in said["L9"][1]
    _remote(root, "https://gitlab.com/acme/sub/demo.git")
    said = {rule: (status, detail) for rule, _, status, detail in doctor._workstation(root, _answers(root))}
    assert said["L9"] == (doctor.OK, "")


def test_the_contracts_line_is_kept_where_the_forge_reads_ownership(tmp_path):
    from napkinstack import modules

    root = create(tmp_path, "gitlab")
    assert modules.create_contract(root, "orders", None) == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "a contract")
    base = _git(root, "rev-parse", "HEAD")
    owners = root / "CODEOWNERS"
    owners.write_text("".join(line for line in owners.read_text(encoding="utf-8").splitlines(keepends=True)
                              if not line.startswith("/contracts/")), encoding="utf-8")
    assert project._keep_contracts(root, base)
    assert any(line.startswith("/contracts/") for line in owners.read_text(encoding="utf-8").splitlines())


def test_update_takes_a_forge_on_the_command_line(tmp_path, monkeypatch):
    from napkinstack import cli

    seen = {}
    monkeypatch.setattr(project, "change_forge", lambda root, forge, **flags: seen.update(forge=forge, **flags) or 0)
    assert cli.main(["update", "--root", str(tmp_path), "--forge", "gitlab", "--repository", "acme/demo"]) == 0
    assert seen == {"forge": "gitlab", "github_repo": None, "repository": "acme/demo", "session": None}


# --- what the verifier of part 3 found -----------------------------------------------------------

def test_a_version_that_does_not_know_the_forge_refuses_the_change_and_leaves_nothing(tmp_path, snapshot, capsys):
    root = tmp_path / "old"
    assert project.init(root, {"project_name": "Demo", "github_repo": "acme/demo", "owner_team": "acme/platform"},
                        str(snapshot), "v0.14.0") == 0
    head = _git(root, "rev-parse", "HEAD")
    assert project.change_forge(root, "gitlab", repository="acme/demo") == 1
    out = capsys.readouterr().out
    assert "v0.14.0" in out and "nstack update" in out
    assert _git(root, "rev-parse", "HEAD") == head and not _git(root, "status", "--porcelain")
    assert _git(root, "branch", "--show-current") == "main"


def _conflicted(root: Path, path: str, old: str, new: str) -> None:
    file = root / path
    file.write_text(file.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    _git(root, "commit", "-qam", f"the project's own {path}")


@pytest.mark.parametrize("path, old, new", [
    (".nstack/handbook/INSTALL.md", "- [ ] At least 1 approving review", "- [ ] At least 2 approving reviews"),
    (".github/CODEOWNERS", "/.github/", "/.github/ @acme/infra #"),
])
def test_a_conflict_is_never_committed(tmp_path, snapshot, capsys, path, old, new):
    root = create(tmp_path, "github", snapshot)
    _conflicted(root, path, old, new)
    head = _git(root, "rev-parse", "HEAD")
    assert project.change_forge(root, "gitlab", repository="acme/demo") == 1
    out = capsys.readouterr().out
    assert "FAIL [update]" in out and "<<<<<<<" in out and "git add --all && git commit" in out
    assert _git(root, "rev-parse", "HEAD") == head, "nothing committed"


def test_a_contract_s_contact_follows_the_forge(tmp_path, snapshot, capsys):
    from napkinstack import modules

    root = create(tmp_path, "github", snapshot)
    assert modules.create_contract(root, "orders", "acme/contracts") == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "a contract")
    assert project.change_forge(root, "gitlab", repository="acme/demo") == 0
    manifest = (root / "contracts/MANIFEST.yaml").read_text(encoding="utf-8")
    assert "github.com" not in manifest and "@acme/contracts" in manifest


def test_the_same_form_does_not_hide_a_hand_edit(tmp_path, snapshot, capsys):
    root = create(tmp_path, "other", snapshot)
    answers = root / ".copier-answers.yml"
    answers.write_text(answers.read_text(encoding="utf-8").replace("forge: other", "forge: none"), encoding="utf-8")
    _git(root, "commit", "-qam", "by hand")
    assert project.written_for(root) == "other"
    root = create(tmp_path, "none")
    answers = root / ".copier-answers.yml"
    answers.write_text(answers.read_text(encoding="utf-8").replace("forge: none", "forge: other"), encoding="utf-8")
    assert project.written_for(root) == "none"


def test_a_hand_edit_is_l9_alone_and_the_refusal_names_the_forge_asked(tmp_path, capsys):
    from napkinstack import doctor

    root = create(tmp_path, "github")
    _by_hand(root, "gitlab")
    said = {rule for rule, _, status, _ in doctor._workstation(root, _answers(root)) if status == doctor.GAP}
    assert "L9" in said and "L8" not in said
    assert project.change_forge(root, "forgejo", repository="acme/demo") == 1
    assert "nstack update --forge forgejo" in capsys.readouterr().out


def test_flags_are_judged_before_the_same_forge(tmp_path, capsys):
    root = create(tmp_path, "github")
    assert project.change_forge(root, "github", repository="acme/demo") == 1
    assert "--repository" in capsys.readouterr().out


def test_a_version_with_a_forge_change_is_refused(tmp_path, capsys):
    from napkinstack import cli

    assert cli.main(["update", "--root", str(tmp_path), "--forge", "gitlab", "--repository", "a/b", "--ref", "v1.0.0"]) == 1
    assert "--ref" in capsys.readouterr().out


def test_back_on_github_the_way_to_ci_is_said(tmp_path, snapshot, capsys):
    root = create(tmp_path, "gitlab", snapshot)
    assert project.change_forge(root, "github", github_repo="acme/demo") == 0
    assert "checks: forge" in capsys.readouterr().out


# --- the pages, per forge (ADR-0010, consequences) ------------------------------------------------

OFF = [forge for forge in EXPECTED if forge != "github"]


@pytest.mark.parametrize("forge", OFF)
def test_off_github_the_pages_a_project_reads_name_no_github_file(created, forge):
    for page in ("CONTRIBUTING.md", "SECURITY.md", ".nstack/handbook/INSTALL.md"):
        text = (created[forge] / page).read_text(encoding="utf-8")
        assert ".github/" not in text, f"{forge}: {page} names .github/"
    install = (created[forge] / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")
    for said in ("GitHub repository", "hosted Ubuntu", "variable set NSTACK_RUNS_ON", "shown on GitHub as milestones"):
        assert said not in install, f"{forge}: INSTALL.md says '{said}'"
    assert "GitHub push" not in (created[forge] / "CONTRIBUTING.md").read_text(encoding="utf-8")


def test_on_github_the_pages_keep_github_s_words(created):
    root = created["github"]
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "`.github/CODEOWNERS`" in contributing and "GitHub push<br/>protection" in contributing
    assert "CI 'Hooks and secrets'" in contributing and "{%" not in contributing
    assert "**Security** tab" in (root / "SECURITY.md").read_text(encoding="utf-8")
    install = (root / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")
    assert "GitHub repository" in install and "NSTACK_RUNS_ON" in install and "| `.github/` |" in install


def test_security_off_github_names_a_private_channel(created):
    assert "confidential issue" in (created["gitlab"] / "SECURITY.md").read_text(encoding="utf-8")
    for forge in OFF:
        assert "`CODEOWNERS`" in (created[forge] / "SECURITY.md").read_text(encoding="utf-8")


def test_the_kernel_and_the_handbook_name_the_identity_and_the_ownership_file_of_any_forge():
    skeleton = ROOT / "skeleton"
    assert "your own GitHub identity" not in (skeleton / "AGENTS.md").read_text(encoding="utf-8")
    said = {"05-workflow.md": "elsewhere an issue of the forge", "07-governance.md": "**Off GitHub**",
            "09-platform.md": "elsewhere CODEOWNERS at the root", "README.md": "elsewhere CODEOWNERS at the root"}
    for page, words in said.items():
        text = " ".join((skeleton / ".nstack/handbook" / page).read_text(encoding="utf-8").split())
        assert words in text, f"{page}: says GitHub's place only, not where another forge keeps it"


# Words true of GitHub alone: a page off GitHub saying one of them describes a CI or a stop it does not have.
GITHUB_ONLY = {"CONTRIBUTING.md": ["CI 'Hooks and secrets'", "Merge impossible", "red: a stop.", "caught by CI"],
               ".nstack/handbook/INSTALL.md": ["CI decides", "<br/>CI:", "as CI installs it", "validated by CI",
                                               "hook and CI reject", "CI installs that commit", "(runs in CI)",
                                               "fails CI", "checks stay in CI"]}


@pytest.mark.parametrize("forge", OFF)
def test_off_github_no_page_claims_a_ci_or_a_merge_refused(created, forge):
    for page, words in GITHUB_ONLY.items():
        text = (created[forge] / page).read_text(encoding="utf-8")
        for said in words:
            assert said not in text, f"{forge}: {page} says '{said}'"


def test_on_github_the_ci_words_stay(created):
    for page, words in GITHUB_ONLY.items():
        text = (created["github"] / page).read_text(encoding="utf-8")
        for said in words:
            assert said in text, f"github: {page} lost '{said}'"


def test_with_no_forge_the_pages_say_there_is_none(created):
    contributing = (created["none"] / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "invites you on the forge" not in contributing and "The change, on its branch" in contributing
    install = (created["none"] / ".nstack/handbook/INSTALL.md").read_text(encoding="utf-8")
    assert "No forge<br/>hooks and records" in install and "Work in branches" in install
    assert "| `CODEOWNERS` | Who approves each path | People: no forge reads it |" in install
    assert "git push -u origin nstack/update" not in install


def test_the_glossary_defines_the_forge():
    glossary = (ROOT / "skeleton/.nstack/handbook/glossary.md").read_text(encoding="utf-8")
    assert "| **Forge" in glossary and "unguarded" in glossary.split("| **Forge", 1)[1].split("\n", 1)[0]
