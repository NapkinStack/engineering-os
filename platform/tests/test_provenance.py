"""
Which framework judges a project (PDR-0005): every judging run says it, and an unpublished
framework is never reported as compliance. Run by platform/tests/run.sh.
"""

from __future__ import annotations

import json

import pytest
import yaml

from napkinstack import cli, doctor, provenance


class Distribution:
    """What importlib.metadata returns for the installed engine; `record` is direct_url.json."""

    def __init__(self, record: dict | None) -> None:
        self.version, self.record = "0.4.0", record

    def read_text(self, name: str) -> str | None:
        return json.dumps(self.record) if self.record and name == "direct_url.json" else None


def installed(monkeypatch, record: dict | None) -> None:
    monkeypatch.setattr(provenance.importlib.metadata, "distribution", lambda name: Distribution(record))


def project(root, commit="v0.4.0", source="https://github.com/NapkinStack/engineering-os.git"):
    answers = {"_commit": commit, "_src_path": source, "github_repo": "acme/demo"}
    (root / ".copier-answers.yml").write_text(yaml.safe_dump(answers), encoding="utf-8")


ARCHIVE = {"url": "file:///somewhere/napkinstack-0.4.0-py3-none-any.whl", "archive_info": {}}
VCS = {"url": "https://github.com/NapkinStack/engineering-os.git",
       "vcs_info": {"vcs": "git", "commit_id": "1a2b3c4d5e6f7a8b9c0d"}}
# uv records the ref it was asked for beside the commit (PEP 610); measured on 2026-09-20.
VCS_TAG = {"url": "https://github.com/NapkinStack/engineering-os.git",
           "vcs_info": {"vcs": "git", "commit_id": "1a2b3c4d5e6f7a8b9c0d",
                        "requested_revision": "v0.4.0"}}
JUDGED = {
    "published engine, published project": (None, "v0.4.0",
                                             "Judged by NapkinStack 0.4.0, published, project recorded at v0.4.0."),
    "an engine from the repository": (VCS, "v0.4.0", "UNPUBLISHED NapkinStack — "
                                      "https://github.com/NapkinStack/engineering-os.git@1a2b3c4d5e6f"),
    "a project pinned to a commit": (None, "v0.4.0-3-g1a2b3c4", "project pinned to v0.4.0-3-g1a2b3c4"),
    "an engine from an archive (D40)": (ARCHIVE, "v0.4.0", "UNPUBLISHED NapkinStack — an archive, not the registry"),
    "an engine from the repository at a tag (ADR-0002)": (
        VCS_TAG, "v0.4.0", "UNPUBLISHED NapkinStack — https://github.com/NapkinStack/engineering-os.git "
        "at v0.4.0 (commit 1a2b3c4d5e6f)"),
}


@pytest.mark.parametrize(("record", "commit", "expected"), JUDGED.values(), ids=JUDGED.keys())
def test_every_judging_run_names_its_framework(tmp_path, capsys, monkeypatch, record, commit, expected):
    installed(monkeypatch, record)
    project(tmp_path, commit)
    cli.main(["plan", "--root", str(tmp_path)])
    first = capsys.readouterr().out.splitlines()[0]
    assert expected in first, first


def test_a_listing_for_ci_stays_machine_readable(tmp_path, capsys, monkeypatch):
    installed(monkeypatch, VCS)
    cli.main(["modules", "--root", str(tmp_path), "--json"])
    assert json.loads(capsys.readouterr().out) == []


DOCTOR = {
    "L1 a project pinned to an unpublished framework": (None, "v0.4.0-3-g1a2b3c4", "https://github.com/x/y.git",
                                                         "L1", "pinned to an unpublished framework"),
    "L1 an engine from the repository": (VCS, "v0.4.0", "https://github.com/x/y.git",
                                         "L1", "The nstack running is unpublished"),
    "L1 a pre-release, which CI installs from the repository (D40)": (None, "v0.5.0rc1", "https://github.com/x/y.git",
                                                                     "L1", "pinned to an unpublished framework"),
    "L7 a template source on one machine": (None, "v0.4.0", "/srv/checkouts/framework",
                                            "L7", "a path on one machine"),
}


@pytest.mark.parametrize(("record", "commit", "source", "rule", "expected"), DOCTOR.values(), ids=DOCTOR.keys())
def test_doctor_never_calls_an_unpublished_framework_compliant(tmp_path, capsys, monkeypatch, record, commit,
                                                              source, rule, expected):
    installed(monkeypatch, record)
    monkeypatch.setattr(doctor, "__version__", "0.4.0")
    project(tmp_path, commit, source)
    assert doctor.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert any(line.split()[:2] == ["FAIL", f"[{rule}]"] for line in output.splitlines()), output
    assert expected in output, output


SOURCES = {"https://github.com/x/y.git": "OK", "gh:x/y": "OK", "gl:x/y": "OK", "git@github.com:x/y.git": "OK",
           "ssh://git@github.com/x/y.git": "OK", "git://github.com/x/y.git": "FAIL", "../framework": "FAIL"}


@pytest.mark.parametrize(("source", "status"), SOURCES.items(), ids=SOURCES.keys())
def test_l7_reads_a_source_as_ci_does(tmp_path, capsys, monkeypatch, source, status):
    """L7 and .nstack/install-engine.sh accept the same remote forms."""
    installed(monkeypatch, None)
    project(tmp_path, source=source)
    doctor.run(tmp_path)
    assert any(line.split()[:2] == [status, "[L7]"] for line in capsys.readouterr().out.splitlines())


def test_doctor_published_and_remote(tmp_path, capsys, monkeypatch):
    installed(monkeypatch, None)
    monkeypatch.setattr(doctor, "__version__", "0.4.0")
    project(tmp_path)
    doctor.run(tmp_path)
    output = capsys.readouterr().out
    assert "OK             [L1]" in output and "OK             [L7]" in output, output


# --- An engine older than its project says so, on every command (D90) ---
# Measured on 2026-10-12: a project updated to a new version, a workstation left on the one
# before. The manual named a command; the engine answered "invalid choice", and nothing else.

def test_an_engine_behind_its_project_says_so_before_refusing_an_unknown_command(tmp_path, monkeypatch, capsys):
    installed(monkeypatch, None)
    project(tmp_path, commit="v0.5.0")
    with pytest.raises(SystemExit):
        cli.main(["a-command-of-the-next-version", "--root", str(tmp_path)])
    said = capsys.readouterr().err
    assert said.index("nstack 0.4.0; the project is on v0.5.0") < said.index("invalid choice"), said
    assert 'uv tool install "napkinstack==0.5.0" --with-executables-from pre-commit' in said


def test_an_engine_behind_its_project_says_so_on_a_command_that_runs(tmp_path, monkeypatch, capsys):
    installed(monkeypatch, None)
    project(tmp_path, commit="v0.4.1")
    cli.main(["modules", f"--root={tmp_path}"])
    out, err = capsys.readouterr()
    assert "the project is on v0.4.1" in err and "the project is on" not in out, (out, err)


@pytest.mark.parametrize("commit", ["v0.4.0", "v0.3.9", "v0.4.0-3-g1a2b3c4", None])
def test_an_engine_level_with_its_project_or_ahead_says_nothing(tmp_path, monkeypatch, commit):
    installed(monkeypatch, None)
    if commit:
        project(tmp_path, commit=commit)
    assert provenance.behind(tmp_path) is None


# --- A project learns of a newer version from doctor, and from nowhere else (D91) ---
# Measured on 2026-10-12: nothing told a project that a version had been published. The one
# command that already reads the network says it, as information; no other opens a connection.

def registry(root, monkeypatch, version) -> None:
    page = root / "registry" / "pypi" / "napkinstack"
    page.mkdir(parents=True)
    (page / "json").write_text(json.dumps({"info": {"version": version}}), encoding="utf-8")
    monkeypatch.setenv("NSTACK_REGISTRY_URL", (root / "registry").as_uri())


def doctor_says(tmp_path, monkeypatch, capsys, version=None, commit="v0.4.0") -> tuple[int, str]:
    installed(monkeypatch, None)
    monkeypatch.setattr(doctor, "__version__", "0.4.0")
    project(tmp_path, commit=commit)
    if version:
        registry(tmp_path, monkeypatch, version)
    before = doctor.run(tmp_path)
    return before, capsys.readouterr().out


def test_doctor_names_a_newer_published_version_with_its_notes_and_the_way_to_take_it(tmp_path, monkeypatch, capsys):
    _, output = doctor_says(tmp_path, monkeypatch, capsys, "0.5.1")
    assert "NEWER VERSION  v0.5.1 is published; the project is on v0.4.0 — information, not a gap" in output, output
    assert "blob/v0.5.1/CHANGELOG.md — every section above v0.4.0" in output, output
    assert 'uv tool install "napkinstack==0.5.1" --with-executables-from pre-commit, then nstack update' in output


def test_a_newer_version_changes_no_verdict(tmp_path, monkeypatch, capsys):
    newer, said = doctor_says(tmp_path, monkeypatch, capsys, "0.5.1")
    (tmp_path / "registry" / "pypi" / "napkinstack" / "json").write_text(
        json.dumps({"info": {"version": "0.4.0"}}), encoding="utf-8")
    level = doctor.run(tmp_path)
    same = capsys.readouterr().out
    assert newer == level, "a newer version changed the exit code"
    assert "LATEST         the project is on v0.4.0" in same and "NEWER VERSION" not in same, same
    assert not any(line.lstrip().startswith("FAIL") and "published" in line for line in said.splitlines()), said


@pytest.mark.parametrize("version", ["0.3.9", "not-a-version"])
def test_an_older_or_unreadable_answer_is_never_a_newer_version(tmp_path, monkeypatch, capsys, version):
    _, output = doctor_says(tmp_path, monkeypatch, capsys, version)
    assert "NEWER VERSION" not in output, output


def test_a_registry_that_does_not_answer_is_said(tmp_path, monkeypatch, capsys):
    _, output = doctor_says(tmp_path, monkeypatch, capsys)
    assert "NOT READ       the registry did not answer" in output, output


def test_a_project_on_no_published_version_is_not_compared(tmp_path, monkeypatch, capsys):
    _, output = doctor_says(tmp_path, monkeypatch, capsys, "0.5.1", commit="v0.4.0-3-g1a2b3c4")
    assert "NEWER VERSION" not in output and "\nNapkinStack\n" not in output, output


def test_no_other_command_asks_the_registry(tmp_path, monkeypatch):
    installed(monkeypatch, None)
    project(tmp_path)
    monkeypatch.setattr(doctor.urllib.request, "urlopen", lambda *a, **k: pytest.fail("a connection was opened"))
    for command in ("fitness", "manifests", "modules", "plan"):
        cli.main([command, "--root", str(tmp_path)])


# --- A pin taken while a fix was reviewed, and the squash that left it behind ---
# Measured on 2026-10-15: a project pinned the head of a fix's pull request while it was
# reviewed, as the contributor's guide allows; the squash gave the default branch another commit,
# and the diagnosis said "unpublished" and nothing about where the pin now stood.

def forge(monkeypatch, status: str | None) -> None:
    """The framework's repository as the forge answers about it, without a network: None when
    it does not answer."""
    pages = {"/repos/NapkinStack/engineering-os": {"default_branch": "main"},
             "/repos/NapkinStack/engineering-os/compare/main...1a2b3c4": {"status": status}}
    monkeypatch.setattr(doctor, "_forge", lambda path: pages.get(path) if status else None)


PINS = {
    "a commit the default branch no longer leads to": ("diverged", "a commit the framework's main does not hold"),
    "a commit only a pull request holds": ("ahead", "a commit the framework's main does not hold"),
    "a commit of the default branch": ("behind", "once the change it waits for is released"),
    "the forge did not answer": (None, "once the change it waits for is released"),
}


@pytest.mark.parametrize(("status", "expected"), PINS.values(), ids=PINS.keys())
def test_l1_says_where_an_unpublished_pin_stands(tmp_path, capsys, monkeypatch, status, expected):
    installed(monkeypatch, None)
    project(tmp_path, "v0.4.0-3-g1a2b3c4")
    forge(monkeypatch, status)
    assert doctor.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert any(line.split()[:2] == ["FAIL", "[L1]"] for line in output.splitlines()), output
    assert expected in output, output
    if status in ("diverged", "ahead"):
        assert "nstack update --ref" in output and "a release that carries it" in output, output
        # Measured on 2026-10-15 rehearsing v0.7.7: a commit still in review was said "left behind
        # by its squash" before any squash. What the forge answers is where the commit stands.
        assert "left behind" not in output and "once it is merged" in output, output


def test_no_action_names_a_version_no_installer_accepts(tmp_path, capsys, monkeypatch):
    installed(monkeypatch, None)
    project(tmp_path, "v0.4.0-3-g1a2b3c4")
    monkeypatch.setattr(doctor.shutil, "which", lambda tool: None)
    doctor.run(tmp_path)
    output = capsys.readouterr().out
    assert "napkinstack==0.4.0-3-g" not in output, output
    assert "bash .nstack/install-engine.sh" in output, output


def test_the_version_says_an_unpublished_engine(capsys, monkeypatch):
    installed(monkeypatch, VCS)
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    said = capsys.readouterr().out
    assert said.startswith("nstack 0.4.0") and "UNPUBLISHED" in said and "1a2b3c4d5e6f" in said, said


def test_l2_fails_without_git_or_pre_commit(tmp_path, capsys, monkeypatch):
    """P5: L2 had no case proving it fails."""
    installed(monkeypatch, None)
    monkeypatch.setattr(doctor, "__version__", "0.4.0")
    project(tmp_path)
    monkeypatch.setattr(doctor.shutil, "which", lambda tool: None if tool == "pre-commit" else "/usr/bin/" + tool)
    assert doctor.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert any(line.split()[:2] == ["FAIL", "[L2]"] for line in output.splitlines()), output
    assert "Missing: pre-commit." in output and 'uv tool install "napkinstack==0.4.0"' in output, output


def test_an_editable_engine_says_the_version_its_source_is_at(tmp_path, monkeypatch):
    # D122: an editable install's metadata is written once, at install; the checkout moves on.
    # Measured on 2026-10-18: a checkout at v0.9.3 installed at 0.9.2 was told it was behind.
    source = tmp_path / "checkout"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\nname = "napkinstack"\nversion = "0.4.1"\n', encoding="utf-8")
    installed(monkeypatch, {"url": source.as_uri(), "dir_info": {"editable": True}})
    project(tmp_path, commit="v0.4.1")
    assert provenance.version() == "0.4.1"
    assert provenance.behind(tmp_path) is None
