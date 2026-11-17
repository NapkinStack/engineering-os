"""D225 (#382): GitHub accepts as a code owner a user, or a team written organisation/team — never
an organisation by its bare name. A bare handle passes the syntax check whatever it names, so an
organisation's name became `owner_team`, and every CODEOWNERS line it wrote named no valid owner:
no path had one, against *a boundary is never orphaned*. Where an owner is written, GitHub is asked
what the handle names; `nstack doctor` reads the forge's own validation of the file (L10).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from napkinstack import cli, doctor, project

ANSWERS = ("_commit: v0.0.1\n_src_path: https://example.invalid/t.git\ngithub_repo: acme/demo\n"
           "owner_team: {owner}\nproject_name: Demo\n")


@pytest.fixture
def forge(monkeypatch):
    """A forge answering each path from a table: (status, JSON); every path asked is kept."""
    table: dict[str, tuple[int, object]] = {}
    asked: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — the standard library's name
            asked.append((self.path, self.headers.get("Authorization")))
            status, body = table.get(self.path, (404, {"message": "Not Found"}))
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("GITHUB_API_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    yield table, asked
    server.shutdown()


def _project(root: Path, owner: str, codeowners: str | None = None) -> None:
    (root / ".copier-answers.yml").write_text(ANSWERS.format(owner=owner), encoding="utf-8")
    (root / ".github").mkdir()
    (root / ".github" / "CODEOWNERS").write_text(codeowners or f"*  @{owner}\n", encoding="utf-8")


ORGANISATION = (200, {"login": "acme", "type": "Organization"})
USER = (200, {"login": "alice", "type": "User"})


def test_a_contract_owned_by_an_organisation_s_name_is_refused_before_anything_is_written(tmp_path, capsys, forge):
    table, _ = forge
    table["/users/acme"] = ORGANISATION
    _project(tmp_path, "acme")
    assert cli.main(["new-contract", "session-audio", "--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "'acme' is an organisation" in out and "acme/<team>" in out, out
    assert not (tmp_path / "contracts").exists()
    assert (tmp_path / ".github" / "CODEOWNERS").read_text(encoding="utf-8") == "*  @acme\n"


def test_a_module_owned_by_an_organisation_s_name_is_refused(tmp_path, capsys, forge):
    table, _ = forge
    table["/users/acme"] = ORGANISATION
    _project(tmp_path, "acme/platform")
    assert cli.main(["new-module", "billing", "acme", "standard", "--root", str(tmp_path)]) == 1
    assert "'acme' is an organisation" in capsys.readouterr().out
    assert not (tmp_path / "modules" / "billing").exists()


def test_a_user_and_a_team_are_owners_and_a_team_is_never_asked_about(tmp_path, capsys, forge):
    table, asked = forge
    table["/users/alice"] = USER
    _project(tmp_path, "acme/platform")
    assert cli.main(["new-module", "billing", "alice", "standard", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    assert cli.main(["new-contract", "session-audio", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    assert [path for path, _ in asked] == ["/users/alice"], "organisation/team is GitHub's form for a team"


def test_an_owner_github_cannot_be_asked_about_passes_with_a_note(tmp_path, capsys, forge):
    table, _ = forge
    table["/users/alice"] = (503, {})
    _project(tmp_path, "acme/platform")
    assert cli.main(["new-module", "billing", "alice", "standard", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "NOTE" in out and "nstack doctor" in out, out


def test_off_github_a_bare_handle_is_a_group_and_github_is_not_asked(tmp_path, capsys, forge):
    _, asked = forge
    _project(tmp_path, "acme")
    answers = tmp_path / ".copier-answers.yml"
    answers.write_text(answers.read_text(encoding="utf-8").replace("github_repo: acme/demo",
                                                                   "forge: gitlab\nrepository: acme/demo"),
                       encoding="utf-8")
    (tmp_path / ".gitlab").mkdir()
    (tmp_path / ".gitlab" / "CODEOWNERS").write_text("*  @acme\n", encoding="utf-8")
    assert cli.main(["new-module", "billing", "acme", "standard", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    assert asked == []


def test_init_refuses_an_organisation_s_name_as_the_foundation_s_owner(tmp_path, capsys, forge):
    table, _ = forge
    table["/users/acme"] = ORGANISATION
    answers = {"project_name": "Demo", "github_repo": "acme/demo", "owner_team": "acme"}
    assert project.init(tmp_path / "demo", answers, "unused", "unused") == 1
    out = capsys.readouterr().out
    assert "'acme' is an organisation" in out and "--owner-team acme/<team>" in out, out
    assert not (tmp_path / "demo").exists()


def test_a_contract_beside_others_writes_no_owner_and_asks_nothing(tmp_path, capsys, forge):
    """The owner is written once, with the contracts module: a project that already holds it is
    not refused for an answer it no longer reads."""
    table, asked = forge
    table["/users/alice"] = USER
    _project(tmp_path, "alice")
    assert cli.main(["new-contract", "session-audio", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    answers = tmp_path / ".copier-answers.yml"
    answers.write_text(answers.read_text(encoding="utf-8").replace("owner_team: alice", "owner_team: acme"),
                       encoding="utf-8")
    table["/users/acme"] = ORGANISATION
    asked.clear()
    assert cli.main(["new-contract", "billing-events", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    assert asked == []


def test_init_asks_github_only_when_the_forge_is_given_as_github(tmp_path, capsys, forge):
    """A forge left to Copier's prompt may be one where a bare group is an owner: doctor reads it."""
    table, asked = forge
    table["/users/acme"] = ORGANISATION
    project.init(tmp_path / "demo", {"project_name": "Demo", "owner_team": "acme"}, "unused", "unused")
    assert asked == [] and "is an organisation" not in capsys.readouterr().out


def test_a_handle_github_does_not_know_is_said_as_such(tmp_path, capsys, forge):
    _project(tmp_path, "acme/platform")
    assert cli.main(["new-module", "billing", "alcie", "standard", "--root", str(tmp_path)]) == 0
    assert "GitHub knows no user or organisation 'alcie'" in capsys.readouterr().out


def _l10(root: Path) -> tuple[str, str]:
    said = {rule: (status, detail) for rule, _, status, detail in
            doctor._workstation(root, project._answers(root))}
    return said["L10"]


ERRORS = "/repos/acme/demo/codeowners/errors"


def test_doctor_says_each_owner_github_does_not_know_as_a_gap(tmp_path, forge, monkeypatch):
    table, asked = forge
    monkeypatch.setenv("GH_TOKEN", "t0ken")
    table[ERRORS] = (200, {"errors": [
        {"line": 1, "column": 4, "kind": "Unknown owner", "source": "*  @acme\n", "path": ".github/CODEOWNERS",
         "message": "Unknown owner on line 1: make sure @acme exists and has write access to the repository"},
        {"line": 7, "column": 33, "kind": "Unknown owner", "source": "/docs/  @acme\n", "path": ".github/CODEOWNERS",
         "message": "..."}]})
    _project(tmp_path, "acme")
    status, detail = _l10(tmp_path)
    assert status == doctor.GAP, detail
    assert "line 1: Unknown owner — *  @acme" in detail and "line 7" in detail, detail
    assert "organisation/team" in detail and "Action:" in detail, detail
    assert (ERRORS, "Bearer t0ken") in asked, "a private repository is read with the token"


def test_doctor_is_compliant_when_github_knows_every_owner(tmp_path, forge):
    table, _ = forge
    table[ERRORS] = (200, {"errors": []})
    _project(tmp_path, "acme/platform")
    assert _l10(tmp_path) == (doctor.OK, "")


def test_doctor_says_an_unread_validation_without_counting_it(tmp_path, forge, capsys):
    _project(tmp_path, "acme/platform")
    status, detail = _l10(tmp_path)  # the table is empty: 404, a private repository out of reach
    assert status == doctor.NOT_READ and "Contents: read" in detail, detail
    assert status not in (doctor.GAP, doctor.UNKNOWN), "unread is said, never a gap nor a 'not verified' exit"


def test_off_github_doctor_does_not_ask_github(tmp_path, forge):
    _, asked = forge
    root = tmp_path
    _project(root, "acme")
    answers = root / ".copier-answers.yml"
    answers.write_text(answers.read_text(encoding="utf-8").replace("github_repo: acme/demo", "forge: none"),
                       encoding="utf-8")
    said = {rule for rule, *_ in doctor._workstation(root, project._answers(root))}
    assert "L10" not in said and not [path for path, _ in asked if "codeowners" in path]
