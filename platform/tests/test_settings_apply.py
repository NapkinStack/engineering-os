"""D151, PDR-0008 (option 3, D150): `nstack settings --apply`, run by the person who holds
administration. It makes the planned calls under their credential, names each refusal with the
forge's own answer, reads the result back with `nstack doctor`, and says to revoke the credential.
Never in CI, never under an App's installation token. Against a forge of this test's own.
"""

from __future__ import annotations

import http.server
import json
import threading

import pytest

from napkinstack import doctor, settings

TOKEN = "github_pat_person-secret-value"


class Forge(http.server.BaseHTTPRequestHandler):
    routes: dict = {}
    answers: dict = {}
    writes: list = []

    def _path(self) -> str:
        return self.path.removeprefix("/repos/acme/demo")

    def do_GET(self):
        status, body = (200, self.routes[self._path()]) if self._path() in self.routes else (404, {"message": "Not Found"})
        self._send(status, body)

    def _write(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        self.writes.append((self.command, self._path(), body))
        answer = self.answers.get((self.command, self._path()))
        status, said = answer(body) if callable(answer) else (answer or (200, {}))
        self._send(status, said)

    do_POST = do_PUT = do_PATCH = _write

    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def forge(tmp_path, monkeypatch):
    Forge.routes = {"": {"default_branch": "main", "visibility": "public"}, "/rulesets": []}
    Forge.answers, Forge.writes = {}, []
    server = http.server.HTTPServer(("127.0.0.1", 0), Forge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.15.1\nforge: github\ngithub_repo: acme/demo\n",
                                                  encoding="utf-8")
    for name in ("GITHUB_ACTIONS", "CI", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_API_URL", f"http://127.0.0.1:{server.server_port}")
    read_back = []
    monkeypatch.setattr(doctor, "run", lambda root: read_back.append(root) or 0)
    yield tmp_path, read_back
    server.shutdown()


def missing(monkeypatch, *rules: str, unread: tuple[str, ...] = ()) -> None:
    def check(rule):
        def read(client):
            if rule in unread:
                raise doctor.NotVerified("read refused (HTTP 403)")
            return rule not in rules
        return read
    monkeypatch.setattr(doctor, "CHECKS", {rule: check(rule) for rule, _, _ in doctor.CHECKLIST})


def test_it_makes_the_planned_calls_reads_back_and_says_to_revoke(forge, monkeypatch, capsys):
    root, read_back = forge
    missing(monkeypatch, "G1", "G5", "G16")
    assert settings.run(root, apply=True) == 0
    out = capsys.readouterr().out
    assert [(method, path) for method, path, _ in Forge.writes] == [("POST", "/rulesets"), ("PATCH", ""), ("PATCH", "")]
    assert Forge.writes[0][2]["bypass_actors"] == [] and Forge.writes[0][2]["name"] == settings.RULESET_NAME
    assert "applied  G1: POST /rulesets (HTTP 200)" in out and "applied  G5: PATCH /" in out, out
    assert read_back == [root], "the result is read back by nstack doctor"
    assert "Revoke the credential" in out
    assert TOKEN not in out, "the credential appears in the output (criterion 8)"


@pytest.mark.parametrize(("variable", "value"), [("GITHUB_ACTIONS", "true"), ("CI", "true")])
def test_it_never_runs_in_ci(forge, monkeypatch, capsys, variable, value):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.setenv(variable, value)
    assert settings.run(root, apply=True) == 1
    assert "--apply does not run in CI" in capsys.readouterr().out and Forge.writes == []


def test_it_refuses_an_app_s_installation_token(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.setenv("GH_TOKEN", "ghs_an-installation-token")
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "installation token" in out and "never holds administration" in out and Forge.writes == []


def test_it_needs_a_credential(forge, monkeypatch, capsys):
    root, _ = forge
    monkeypatch.delenv("GH_TOKEN")
    assert settings.run(root, apply=True) == 1
    assert "--apply needs your own credential" in capsys.readouterr().out and Forge.writes == []


def test_it_never_writes_what_it_could_not_read(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1", unread=("G11",))
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "never writes what it could not read" in out and "G11" in out and Forge.writes == []


def test_a_compliant_repository_gets_no_call(forge, monkeypatch, capsys):
    root, read_back = forge
    missing(monkeypatch)
    assert settings.run(root, apply=True) == 0
    assert "nothing to change" in capsys.readouterr().out and Forge.writes == []


def test_a_refusal_is_named_with_the_forge_s_answer_and_the_rest_still_applied(forge, monkeypatch, capsys):
    root, read_back = forge
    missing(monkeypatch, "G5", "G10")
    Forge.answers[("PATCH", "")] = (422, {"message": "Secret scanning is not available for this repository."})
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "REFUSED  G5: PATCH / (HTTP 422: Secret scanning is not available for this repository.)" in out, out
    assert ("PUT", "/actions/permissions/workflow") in [(m, p) for m, p, _ in Forge.writes]
    assert read_back == [root] and "FAIL [settings] 1 call(s) refused" in out


def test_a_check_the_forge_has_not_seen_leaves_g4_the_one_step_remaining(forge, monkeypatch, capsys):
    """D26: the ruleset goes in without the required checks, and G4 is named with the forge's answer."""
    root, _ = forge
    missing(monkeypatch, "G1", "G4")
    Forge.answers[("POST", "/rulesets")] = lambda body: (
        (422, {"message": "Invalid rule 'required_status_checks'"})
        if any(rule["type"] == "required_status_checks" for rule in body["rules"]) else (201, {}))
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert len(Forge.writes) == 2 and all(r["type"] != "required_status_checks" for r in Forge.writes[1][2]["rules"])
    assert "applied  G1: POST /rulesets (HTTP 201); G4 refused (HTTP 422: Invalid rule" in out, out
    assert "open a first pull request" in out


def test_a_ruleset_name_already_taken_is_never_rewritten(forge, monkeypatch, capsys):
    root, _ = forge
    Forge.routes["/rulesets"] = [{"id": 7, "name": settings.RULESET_NAME}]
    missing(monkeypatch, "G4")
    assert settings.run(root, apply=True) == 0
    assert Forge.writes[0][:2] == ("POST", "/rulesets") and Forge.writes[0][2]["name"] == f"{settings.RULESET_NAME}-2"


def test_without_apply_nothing_is_written(forge, monkeypatch, capsys):
    root, read_back = forge
    missing(monkeypatch, "G1", "G5")
    assert settings.run(root) == 0
    assert Forge.writes == [] and read_back == [] and "Nothing was changed" in capsys.readouterr().out
