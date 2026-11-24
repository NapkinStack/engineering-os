"""#529: the project's settings — a default each, the decider's to change with one command.

The review budget was set by environment only: CI's workflow and every workstation that attests had
to be kept in agreement by hand. It is now two answers of the project, read alike wherever pr-scope
runs, and `nstack config` lists, reads and changes every setting the decider owns — on a branch, for
a pull request a human approves, the files written from the answer following it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from napkinstack import config, project

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("NSTACK_AGENT", raising=False)
    for name in ("MAX_LINES", "MAX_FILES"):
        monkeypatch.delenv(name, raising=False)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def test_the_engine_s_settings_are_copier_s_questions():
    """One list in two places — the engine's table and copier.yml — held the same: a setting the engine
    offers that Copier does not ask would be rendered away; a default that differs would lie."""
    questions = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    types = {str: "str", int: "int", bool: "bool"}
    for name, setting in config.SETTINGS.items():
        question = questions[name]
        assert question["type"] == types[setting.kind], name
        assert tuple(question.get("choices", ())) == setting.choices, name
        if "{{" not in str(question["default"]):
            assert question["default"] == setting.default({"forge": "github"}), name
    assert config.SETTINGS["checks"].default({"forge": "github"}) == "forge"
    assert config.SETTINGS["checks"].default({"forge": "gitlab"}) == "attested"
    asked = {name for name in questions if not name.startswith("_")}
    assert asked == set(config.SETTINGS) | set(config.AT_INIT), "a question neither listed nor changeable"


def _scoped(tmp_path: Path, answers: str, lines: int) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    _git(root, "init", "-q", "--initial-branch=main")
    (root / ".copier-answers.yml").write_text(answers, encoding="utf-8")
    (root / "modules/a").mkdir(parents=True)
    (root / "modules/a/x.txt").write_text("0\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    (root / "modules/a/x.txt").write_text("".join(f"{n}\n" for n in range(lines)), encoding="utf-8")
    _git(root, "commit", "-qam", "change")
    return root


@pytest.mark.parametrize(("answers", "env", "said"), [
    ("_commit: v0.34.9\n", {}, "/400 lines, 1/15 files (review_budget_lines, by default; review_budget_files, by default)"),
    ("_commit: v0.34.9\nreview_budget_lines: 800\n", {}, "/800 lines, 1/15 files (review_budget_lines in .copier-answers.yml"),
    ("_commit: v0.34.9\nreview_budget_lines: 800\n", {"MAX_LINES": "5"}, "/5 lines, 1/15 files (MAX_LINES in the environment"),
])
def test_pr_scope_reads_the_project_s_budget_the_environment_first(tmp_path, monkeypatch, capsys, answers, env, said):
    from napkinstack.fitness import pr_scope

    root = _scoped(tmp_path, answers, 3)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    pr_scope.run(root, "HEAD~1")
    assert said in capsys.readouterr().out


def test_an_answer_that_is_no_budget_is_refused_naming_its_source(tmp_path, capsys):
    from napkinstack.fitness import pr_scope

    root = _scoped(tmp_path, "_commit: v0.34.9\nreview_budget_files: 0\n", 3)
    assert pr_scope.run(root, "HEAD~1") == 1
    out = capsys.readouterr().out
    assert "review_budget_files in .copier-answers.yml: '0' is not a whole number above 0" in out, out
    assert "nstack config review_budget_files" in out


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    """A project made from the working tree, committed: config renders it again at its own version."""
    import shutil

    os.environ.update(IDENTITY)
    source = tmp_path_factory.mktemp("source") / "engineering-os"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(source)], check=True)
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.split("\0")
    for name in filter(None, listed):
        if (ROOT / name).is_file():
            (source / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, source / name)
        elif (source / name).is_file():
            (source / name).unlink()
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "the working tree"], cwd=source, check=True)
    return source


def _project(tmp_path: Path, source: Path) -> Path:
    root = tmp_path / "demo"
    answers = {"project_name": "Demo", "owner_team": "acme/platform", "forge": "github", "github_repo": "acme/demo"}
    assert project.init(root, answers, str(source), "HEAD") == 0
    return root


def test_config_lists_every_setting_with_its_value_and_source(tmp_path, made, capsys):
    root = _project(tmp_path, made)
    capsys.readouterr()
    assert config.run(root) == 0
    out = capsys.readouterr().out
    for name in config.SETTINGS:
        assert name in out, name
    assert "review_budget_lines    400" not in out or "(default)" in out
    assert "github_repo" in out and "nstack update --forge" in out
    assert config.run(root, "approval") == 0 and "approval: human" in capsys.readouterr().out


def test_a_change_is_laid_on_a_branch_with_the_files_it_writes(tmp_path, made, capsys):
    root = _project(tmp_path, made)
    owners = (root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    capsys.readouterr()
    assert config.run(root, "approval", "agent", session="s-9") == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    assert _git(root, "branch", "--show-current") == "nstack/config-approval"
    assert not _git(root, "status", "--porcelain"), "the change is committed on its branch"
    assert yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))["approval"] == "agent"
    assert (root / ".github/CODEOWNERS").read_text(encoding="utf-8") != owners, "the code owners file follows"
    assert _git(root, "log", "-1", "--format=%(trailers:key=Agent-Session,valueonly)") == "s-9"
    assert "approval human -> agent" in out and "a pull request a human approves" in out
    _git(root, "switch", "-q", "main")
    assert config.run(root, "review_budget_lines", "800") == 0
    assert yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))["review_budget_lines"] == 800


@pytest.mark.parametrize(("name", "value", "said"), [
    ("review_budget_lines", "lots", "give a whole number above 0"),
    ("review_budget_lines", "0", "give a whole number above 0"),
    ("approval", "robots", "give human or agent"),
    ("agent_sockets", "maybe", "give true or false"),
    ("forge", "gitlab", "nstack update --forge"),
    ("colour", "blue", "no such setting"),
])
def test_a_value_or_a_setting_it_does_not_take_is_refused_before_anything_is_written(tmp_path, capsys, name, value, said):
    root = tmp_path / "p"
    root.mkdir()
    (root / ".copier-answers.yml").write_text("_commit: v0.34.9\nforge: github\n", encoding="utf-8")
    assert config.run(root, name, value) == 1
    assert said in capsys.readouterr().out


def test_an_agent_s_change_names_its_session(tmp_path, monkeypatch, capsys):
    root = tmp_path / "p"
    root.mkdir()
    (root / ".copier-answers.yml").write_text("_commit: v0.34.9\nforge: github\n", encoding="utf-8")
    monkeypatch.setenv("NSTACK_AGENT", "scout")
    assert config.run(root, "hold_days", "10") == 1
    assert "--session <this session>" in capsys.readouterr().out


# --- what a fresh verifier found: every guard of a change, and the values it writes ----------------

def _branches(root: Path) -> list[str]:
    return [line.strip("* ").strip() for line in _git(root, "branch").splitlines()]


@pytest.mark.parametrize(("said", "written"), [("true", True), ("false", None), ("yes", True)])
def test_a_bool_is_written_as_yaml_s_bool(tmp_path, made, said, written):
    root = _project(tmp_path, made)
    code = config.run(root, "agent_sockets", said)
    answers = yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8"))
    if written is None:  # false is the default, already written at init: nothing to change, no branch
        assert code == 0 and _branches(root) == ["main"] and answers["agent_sockets"] is False
    else:
        assert code == 0 and answers["agent_sockets"] is True


def test_an_agent_with_its_session_changes_a_setting(tmp_path, made, monkeypatch):
    root = _project(tmp_path, made)
    monkeypatch.setenv("NSTACK_AGENT", "scout")
    assert config.run(root, "hold_days", "10", session="s-1") == 0
    assert _git(root, "log", "-1", "--format=%(trailers:key=Agent-Session,valueonly)") == "s-1"


def test_a_version_that_does_not_ask_the_setting_is_refused_leaving_the_tree_as_it_was(tmp_path, capsys):
    root = tmp_path / "old"
    answers = {"project_name": "Demo", "owner_team": "acme/platform", "forge": "github", "github_repo": "acme/demo"}
    assert project.init(root, answers, str(ROOT), "v0.34.9") == 0
    head = _git(root, "rev-parse", "HEAD")
    capsys.readouterr()
    assert config.run(root, "review_budget_lines", "800") == 1
    assert "does not know the setting review_budget_lines" in capsys.readouterr().out
    assert _git(root, "rev-parse", "HEAD") == head and not _git(root, "status", "--porcelain", "--ignored")
    assert _branches(root) == ["main"]


@pytest.mark.parametrize("held", ["branch", "dirty", "elsewhere", "forge by hand"])
def test_a_change_is_refused_where_it_would_carry_or_lose_something(tmp_path, made, capsys, held):
    root = _project(tmp_path, made)
    if held == "branch":
        _git(root, "branch", "nstack/config-hold-days")
        said = "Branch nstack/config-hold-days already exists"
    elif held == "dirty":
        (root / "README.md").write_text("changed\n", encoding="utf-8")
        said = "Working tree modified"
    elif held == "elsewhere":
        _git(root, "switch", "-q", "-c", "feature")
        said = "feature is checked out, not main"
    else:
        answers = root / ".copier-answers.yml"
        answers.write_text(answers.read_text(encoding="utf-8").replace("forge: github", "forge: gitlab"), encoding="utf-8")
        _git(root, "commit", "-qam", "by hand")
        said = "the answer was changed by hand"
    capsys.readouterr()
    assert config.run(root, "hold_days", "10") == 1
    assert said in capsys.readouterr().out
    assert "nstack/config-hold-days" not in _branches(root) or held == "branch"


def test_a_conflict_is_laid_out_never_committed(tmp_path, made, capsys):
    root = _project(tmp_path, made)
    owners = root / ".github/CODEOWNERS"
    lines = owners.read_text(encoding="utf-8").splitlines()
    default = next(i for i, line in enumerate(lines) if line.startswith("*"))
    lines[default] = "*  @acme/platform @acme/leads"
    owners.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _git(root, "commit", "-qam", "the project's own default owners")
    head = _git(root, "rev-parse", "HEAD")
    capsys.readouterr()
    assert config.run(root, "approval", "agent", session="s-2") == 1
    out = capsys.readouterr().out
    assert ".github/CODEOWNERS" in out and "<<<<<<<" in owners.read_text(encoding="utf-8")
    assert '--trailer "Agent-Session: s-2"' in out, "the Action keeps the agent's session"
    assert _git(root, "rev-parse", "HEAD") == head, "nothing committed"


def test_checks_forge_is_refused_where_no_ci_is_shipped(tmp_path, capsys):
    root = tmp_path / "p"
    root.mkdir()
    (root / ".copier-answers.yml").write_text("_commit: v0.34.9\nforge: gitlab\nchecks: attested\n", encoding="utf-8")
    assert config.run(root, "checks", "forge") == 1
    assert "no CI is shipped off GitHub" in capsys.readouterr().out


def test_an_unreadable_answers_file_is_said_never_a_traceback(tmp_path, capsys):
    from napkinstack.fitness import pr_scope

    root = _scoped(tmp_path, "_commit: v0.34.9\nforge: [unclosed\n", 3)
    assert pr_scope.run(root, "HEAD~1") == 1 and "cannot be read" in capsys.readouterr().out
    assert config.run(root) == 1 and "fix the file's YAML" in capsys.readouterr().out


def test_a_setting_written_as_text_is_said(tmp_path, capsys):
    root = tmp_path / "p"
    root.mkdir()
    (root / ".copier-answers.yml").write_text('_commit: v0.34.9\nforge: github\nagent_sockets: "true"\n', encoding="utf-8")
    assert config.run(root, "agent_sockets") == 0
    assert "NOT a bool" in capsys.readouterr().out
