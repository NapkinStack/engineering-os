"""D175, PDR-0021: an agent may approve another's change, where the project says so. On
`approval: agent`, the code owners file keeps a human for what one must approve (L6), the forge
refuses the last pusher's approval (G21), and a new `standard` module gets no code owner line.
Every case proves its rule fails (P5) and names itself (P6).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from napkinstack import doctor, modules, settings

HUMAN_LINES = ("/AGENTS.md", "/CONTRIBUTING.md", "/.nstack/", "/.github/", "/.copier-answers.yml", "/docs/", "/.pre-commit-config.yaml",
               "/.yamllint.yaml", "/SECURITY.md")


def project(tmp_path: Path, approval: str | None, owners: str, criticalities: dict[str, str] = {}) -> Path:
    answers = {"project_name": "Demo", "forge": "github", "github_repo": "acme/demo", "owner_team": "acme/core"}
    if approval:
        answers["approval"] = approval
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".copier-answers.yml").write_text(yaml.safe_dump(answers), encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "CODEOWNERS").write_text(owners, encoding="utf-8")
    for name, criticality in criticalities.items():
        folder = tmp_path / ("contracts" if name == "contracts" else f"modules/{name}")
        folder.mkdir(parents=True)
        (folder / "MANIFEST.yaml").write_text(yaml.safe_dump({"module": {
            "name": name, "owner": "acme/core", "criticality": criticality}}), encoding="utf-8")
    return tmp_path


def owners(*paths: str, default: bool = False) -> str:
    return "".join(f"{path:<31}@acme/core\n" for path in (("*",) if default else ()) + paths)


def test_on_human_the_code_owners_file_still_starts_with_a_default_owner(tmp_path):
    assert doctor._default_owner(project(tmp_path / "a", None, owners(*HUMAN_LINES, default=True)))[0] == doctor.OK
    assert doctor._default_owner(project(tmp_path / "b", "human", owners(*HUMAN_LINES)))[0] == doctor.GAP


def test_on_agent_a_human_owns_the_project_s_rules_and_every_high_or_critical_module(tmp_path):
    criticalities = {"capture": "standard", "billing": "critical", "contracts": "high"}
    whole = owners(*HUMAN_LINES, "/modules/billing/", "/contracts/")
    assert doctor._default_owner(project(tmp_path / "a", "agent", whole, criticalities))[0] == doctor.OK
    for missing in (*HUMAN_LINES, "/modules/billing/", "/contracts/"):
        lines = owners(*(path for path in (*HUMAN_LINES, "/modules/billing/", "/contracts/") if path != missing))
        status, detail = doctor._default_owner(project(tmp_path / missing.strip("/"), "agent", lines, criticalities))
        assert status == doctor.GAP and f"`{missing.lstrip('/')}`" in detail, missing


def test_on_agent_a_default_owner_leaves_no_change_an_agent_may_approve(tmp_path):
    status, detail = doctor._default_owner(project(tmp_path, "agent", owners(*HUMAN_LINES, default=True)))
    assert status == doctor.GAP and "default owner" in detail


class PullRequestRule:
    def __init__(self, **parameters):
        self.parameters = parameters

    def get(self, path, missing=False):
        if path == "":
            return {"default_branch": "main"}
        return [{"type": "pull_request", "parameters": self.parameters}]


@pytest.mark.parametrize("last_push, compliant", [(True, True), (False, False), (None, False)])
def test_g21_reads_the_last_push_approval(last_push, compliant):
    parameters = {} if last_push is None else {"require_last_push_approval": last_push}
    assert doctor.CHECKS["G21"](PullRequestRule(**parameters)) is compliant


def test_g21_is_asked_on_agent_alone_and_blocks_there():
    assert doctor.unasked("G21", {"approval": "agent"}) is None
    assert "human" in doctor.unasked("G21", {})
    assert "human" in doctor.unasked("G21", {"approval": "human"})
    assert doctor.unasked("G2", {}) is None and "G21" in doctor.BLOCKING and "G21" in doctor.PRIVATE_PLAN


def test_the_ruleset_planned_asks_the_last_push_approval_only_when_g21_is_missing():
    def pull_request(missing):
        body = settings.ruleset(missing)
        return next(rule["parameters"] for rule in body["rules"] if rule["type"] == "pull_request")

    assert pull_request({"G2", "G21"})["require_last_push_approval"] is True
    assert pull_request({"G2"})["require_last_push_approval"] is False
    assert pull_request({"G21"})["require_code_owner_review"] is True


@pytest.mark.parametrize("approval, criticality, owned", [
    ("agent", "standard", False), ("agent", "prototype", False), ("agent", "high", True),
    ("agent", "critical", True), ("human", "standard", True), (None, "standard", True)])
def test_a_new_module_gets_a_code_owner_line_where_a_human_must_approve(tmp_path, approval, criticality, owned):
    root = project(tmp_path, approval, owners(*HUMAN_LINES))
    assert modules.create(root, "capture", "acme/core", criticality) == 0
    lines = (root / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
    assert any(line.split()[:1] == ["/modules/capture/"] for line in lines) is owned


@pytest.mark.parametrize("approval", ["agent", None])
def test_a_project_made_on_agent_starts_with_code_owners_doctor_accepts(tmp_path, monkeypatch, approval):
    from napkinstack import project as made

    for name in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(name, "test")
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(name, "test@example.invalid")
    answers = {"project_name": "Demo", "owner_team": "acme/core", "forge": "github", "github_repo": "acme/demo",
               **({"approval": approval} if approval else {})}
    root = tmp_path / "demo"
    assert made.init(root, answers, str(Path(__file__).resolve().parents[2]), "HEAD") == 0
    rules = [line.split()[0] for line in (root / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    assert ("*" in rules) is (approval is None) and ("/docs/" in rules) is (approval == "agent")
    assert yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))["approval"] == (approval or "human")
    assert doctor._default_owner(root)[0] == doctor.OK


@pytest.mark.parametrize("text, kept", [
    ("/docs/ @acme/core\n/docs/adr/\n", "docs/"),            # the last match names nobody
    ("/docs/ # @acme/core\n", "docs/"),                       # a comment is no owner
    ("/modules/billing @acme/core\n", None),                  # a folder named without its slash
    ("modules/billing/ @acme/core\n", None),                  # unanchored, it still covers it
    ("/modules/billing/** @acme/core\n", None)])
def test_a_path_is_kept_for_a_human_by_the_last_rule_matching_it(tmp_path, text, kept):
    from napkinstack import owners as who

    root = project(tmp_path, "agent", "", {"billing": "critical"})
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "adr" / "0001-x.md").write_text("x", encoding="utf-8")
    rest = owners(*(path for path in HUMAN_LINES if path != "/docs/"))
    case = ("/modules/billing/ @acme/core\n" + text) if kept == "docs/" else ("/docs/ @acme/core\n" + text)
    default, missing = who.unowned(root, rest + case)
    assert not default
    assert missing == ([kept] if kept else []), missing


@pytest.mark.parametrize("default", ["*", "/**", "**"])
def test_every_spelling_of_a_default_owner_is_one(tmp_path, default):
    from napkinstack import owners as who

    assert who.unowned(project(tmp_path, "agent", ""), f"{default} @acme/core\n" + owners(*HUMAN_LINES))[0]


def test_a_manifest_the_engine_cannot_read_is_kept_for_a_human(tmp_path):
    from napkinstack import owners as who

    root = project(tmp_path, "agent", owners(*HUMAN_LINES))
    (root / "modules" / "odd").mkdir(parents=True)
    (root / "modules" / "odd" / "MANIFEST.yaml").write_text("module: [unclosed\n", encoding="utf-8")
    assert "modules/odd/" in who.wanted(root)


def test_in_ci_a_raised_criticality_without_its_owner_line_is_refused(tmp_path, capsys):
    from napkinstack.fitness import manifests

    root = project(tmp_path, "agent", owners(*HUMAN_LINES), {"billing": "critical"})
    assert manifests.run(root) == 1
    assert "[M13] code owners" in capsys.readouterr().out
    (root / ".github" / "CODEOWNERS").write_text(owners(*HUMAN_LINES, "/modules/billing/"), encoding="utf-8")
    manifests.run(root)
    assert "M13" not in capsys.readouterr().out
    human = project(tmp_path / "human", "human", owners(*HUMAN_LINES), {"billing": "critical"})
    manifests.run(human)
    assert "M13" not in capsys.readouterr().out


def test_a_human_project_compliant_reads_guarded_with_g21_not_applicable(capsys):
    results = [(rule, "", doctor.OK, "") for rule in doctor.BLOCKING if rule != "G21"]
    doctor._state(results + [("G21", "", doctor.NOT_APPLICABLE, "")])
    assert "This repository: guarded" in capsys.readouterr().out


@pytest.mark.parametrize("approval, planned", [(None, False), ("agent", True)])
def test_settings_plans_g21_on_agent_alone_without_a_token(tmp_path, monkeypatch, capsys, approval, planned):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    root = project(tmp_path, approval, owners(*HUMAN_LINES))
    settings.run(root)
    assert ("require_last_push_approval\": true" in capsys.readouterr().out.replace("'", '"')) is planned


def committed(root: Path, *authors: str) -> None:
    import os
    import subprocess

    # The identity is each commit's own: an identity another test left in the environment wins over `-c`.
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))}
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, check=True)
    for index, author in enumerate(authors):
        (root / f"f{index}").write_text(str(index), encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", f"user.name={author}", "-c", f"user.email={author}@users.noreply.github.com",
                        "commit", "-q", "-m", str(index)], cwd=root, check=True, env=env)


@pytest.mark.parametrize("authors, said", [
    (("1+a-agent[bot]", "1+a-agent[bot]", "alice"), True),   # one agent identity: nobody else's agent
    (("1+a-agent[bot]", "2+b-agent[bot]"), False),            # two: another contributor's agent may approve
    (("alice",), True)])
def test_on_agent_doctor_says_when_no_second_agent_identity_can_approve(tmp_path, authors, said):
    root = project(tmp_path, "agent", owners(*HUMAN_LINES))
    committed(root, *authors)
    status, detail = doctor._default_owner(root)
    assert status == doctor.OK and ("identity of its own" in detail) is said, detail
