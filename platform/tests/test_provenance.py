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


VCS = {"url": "https://github.com/NapkinStack/engineering-os.git",
       "vcs_info": {"vcs": "git", "commit_id": "1a2b3c4d5e6f7a8b9c0d"}}
JUDGED = {
    "published engine, published project": (None, "v0.4.0",
                                             "Judged by NapkinStack 0.4.0, published, project recorded at v0.4.0."),
    "an engine from the repository": (VCS, "v0.4.0", "UNPUBLISHED NapkinStack — "
                                      "https://github.com/NapkinStack/engineering-os.git@1a2b3c4d5e6f"),
    "a project pinned to a commit": (None, "v0.4.0-3-g1a2b3c4", "project pinned to v0.4.0-3-g1a2b3c4"),
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
