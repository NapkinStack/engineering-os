"""D151, PDR-0008 (option 3, D150): `nstack settings --apply`, run by the person who holds
administration. It makes the planned calls under their credential, names each refusal with the
forge's own answer, reads the result back with `nstack doctor`, and says to revoke the credential.
Never in CI, never under an App's installation token. Against a forge of this test's own.
"""

from __future__ import annotations

import http.server
import json
import os
import threading

import pytest

from napkinstack import doctor, settings

TOKEN = "github_pat_person-secret-value"
REAL_GH_TOKEN = settings._gh_token  # before conftest stubs it for every test


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
        status, said, *more = answer(body) if callable(answer) else (answer or (200, {}))
        self._send(status, said, *more)

    do_POST = do_PUT = do_PATCH = _write

    def _send(self, status, body, headers=None):
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def forge(tmp_path, monkeypatch):
    Forge.routes = {"": {"default_branch": "main", "visibility": "public"}, "/rulesets?per_page=100": []}
    Forge.answers, Forge.writes = {}, []
    server = http.server.HTTPServer(("127.0.0.1", 0), Forge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.15.1\nforge: github\ngithub_repo: acme/demo\n",
                                                  encoding="utf-8")
    for name in ("GITHUB_ACTIONS", "CI", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_API_URL", f"http://127.0.0.1:{server.server_port}")
    Forge.routes["/user"] = {"login": "alice"}
    monkeypatch.setattr(settings, "_interactive", lambda: True)
    monkeypatch.setattr(settings, "_ask", lambda prompt: "y")
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
    assert "GitHub App's" in out and "never holds administration" in out and Forge.writes == []
    assert "ghs_an-installation-token" not in out


def test_it_needs_a_credential(forge, monkeypatch, capsys):
    root, _ = forge
    monkeypatch.delenv("GH_TOKEN")
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "--apply needs your own credential" in out and Forge.writes == []
    assert "gh auth login" in out and "target_name=acme&expires_in=1&administration=write&issues=write" in out, out


def test_it_never_writes_what_it_could_not_read_and_writes_what_it_read(forge, monkeypatch, capsys):
    """#523: one rule it could not read held back every rule it had; the reason — a ruleset or a label
    added twice — is the unread rule's alone. Its calls are left out, named, and the run fails."""
    root, _ = forge
    missing(monkeypatch, "G1", "G10", unread=("G11",))
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert [(m, p) for m, p, _ in Forge.writes] == [("POST", "/rulesets"), ("PUT", "/actions/permissions/workflow")], out
    assert "/labels" not in str(Forge.writes)
    assert "FAIL [settings] not read with this token, so not written: G11" in out, out


def test_a_ruleset_closing_an_unread_rule_is_never_written(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1", "G10", unread=("G2",))
    assert settings.run(root, apply=True) == 1
    assert [(m, p) for m, p, _ in Forge.writes] == [("PUT", "/actions/permissions/workflow")], capsys.readouterr().out


def test_on_a_private_repository_g9_is_not_asked_and_the_labels_are_made(forge, monkeypatch, capsys):
    """#523: on a private repository the forge has no contributor approval to read — HTTP 422 under an
    administrator's token —; private forks run under another setting. G9 is not judged there, as G6."""
    root, _ = forge
    Forge.routes[""] = {"default_branch": "main", "visibility": "private"}
    missing(monkeypatch, "G11", unread=("G9",))
    assert settings.run(root, apply=True) == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    assert [p for m, p, _ in Forge.writes] == ["/labels"] * len(doctor.LABELS), out
    assert "G9" not in out, out
    assert "G9" in doctor.PUBLIC_ONLY


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
    Forge.routes["/rulesets?per_page=100"] = [{"id": 7, "name": settings.RULESET_NAME}]
    missing(monkeypatch, "G4")
    assert settings.run(root, apply=True) == 0
    assert Forge.writes[0][:2] == ("POST", "/rulesets") and Forge.writes[0][2]["name"] == f"{settings.RULESET_NAME}-2"


def test_without_apply_nothing_is_written(forge, monkeypatch, capsys):
    root, read_back = forge
    missing(monkeypatch, "G1", "G5")
    assert settings.run(root) == 0
    assert Forge.writes == [] and read_back == [] and "Nothing was changed" in capsys.readouterr().out


# --- what the independent verifier found -----------------------------------------------------

@pytest.mark.parametrize(("variable", "token"), [("GITHUB_TOKEN", "ghs_from-actions"), ("GH_TOKEN", "ghu_user-to-server")])
def test_every_app_token_is_refused_wherever_it_is_given(forge, monkeypatch, capsys, variable, token):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setenv(variable, token)
    assert settings.run(root, apply=True) == 1
    assert "GitHub App's" in capsys.readouterr().out and Forge.writes == []


def test_a_private_repository_gets_what_its_plan_allows(forge, monkeypatch, capsys):
    """The rules the plan cannot have are unreadable there (the forge's 403): out of reach, never a
    reason to refuse the rest."""
    root, _ = forge
    Forge.routes[""] = {"default_branch": "main", "visibility": "private"}
    missing(monkeypatch, "G10", unread=("G1", "G2", "G3", "G4"))
    assert settings.run(root, apply=True) == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    assert [(m, p) for m, p, _ in Forge.writes] == [("PUT", "/actions/permissions/workflow")]
    assert "never writes what it could not read" not in out


def test_a_redirected_write_is_refused_never_reported_applied(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    Forge.answers[("POST", "/rulesets")] = (301, {}, {"Location": "/repositories/1/rulesets"})
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "REFUSED  G1: POST /rulesets (HTTP 301" in out and "applied  G1" not in out, out
    assert [(m, p) for m, p, _ in Forge.writes] == [("POST", "/rulesets")], "the redirect was followed"


def test_disabled_actions_are_never_turned_on(forge, monkeypatch, capsys):
    root, _ = forge
    Forge.routes["/actions/permissions"] = {"enabled": False}
    missing(monkeypatch, "G7", "G8", "G10")
    settings.run(root, apply=True)
    out = capsys.readouterr().out
    assert not [p for _, p, _ in Forge.writes if p.startswith("/actions/permissions") and p != "/actions/permissions/workflow"]
    assert "Actions are disabled on this repository" in out


def test_the_read_back_s_verdict_is_the_run_s(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G10")
    monkeypatch.setattr(doctor, "run", lambda root: 2)
    assert settings.run(root, apply=True) == 2


def test_the_holds_ruleset_takes_a_free_name_too(forge, monkeypatch, capsys):
    root, _ = forge
    Forge.routes["/rulesets?per_page=100"] = [{"id": 8, "name": settings.HOLDS_RULESET}]
    missing(monkeypatch, "G20")
    settings.run(root, apply=True)
    assert Forge.writes[0][2]["name"] == f"{settings.HOLDS_RULESET}-2"


def test_a_ruleset_refused_with_and_without_its_checks_says_both_answers(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1", "G4")
    Forge.answers[("POST", "/rulesets")] = (422, {"message": "Name must be unique"})
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "(HTTP 422: Name must be unique; without the required checks: HTTP 422: Name must be unique)" in out, out


# --- D244: the person's gh login, or GH_TOKEN; confirmed at the keyboard ---------------------

GH_LOGIN = "gho_the-person-s-gh-login"


def _never(*args):
    raise AssertionError("the gh login was asked for")


def test_without_gh_token_the_gh_login_s_token_is_used_and_kept_nowhere(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setattr(settings, "_gh_token", lambda: GH_LOGIN)
    seen = []
    monkeypatch.setattr(doctor, "run", lambda root: seen.append(os.environ.get("GH_TOKEN")) or 0)
    assert settings.run(root, apply=True) == 0
    out = capsys.readouterr().out
    assert [(method, path) for method, path, _ in Forge.writes] == [("POST", "/rulesets")]
    assert "acme/demo as @alice, with your gh login's token" in out, out
    assert seen == [GH_LOGIN], "doctor reads the result back with the same credential"
    assert "GH_TOKEN" not in os.environ, "the gh login's token is left in no variable after the run"
    assert "Revoke the credential" not in out and "your gh login stays as it was" in out
    assert GH_LOGIN not in out


def test_gh_token_given_comes_first_and_gh_is_never_asked(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.setattr(settings, "_gh_token", _never)
    assert settings.run(root, apply=True) == 0
    assert "with the token in GH_TOKEN" in capsys.readouterr().out


@pytest.mark.parametrize(("variable", "value"), [("GITHUB_ACTIONS", "true"), ("NSTACK_AGENT", "scout")])
def test_neither_ci_nor_an_agent_s_session_reaches_the_gh_login(forge, monkeypatch, capsys, variable, value):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setenv(variable, value)
    monkeypatch.setattr(settings, "_gh_token", _never)
    assert settings.run(root, apply=True) == 1
    assert Forge.writes == []


def test_an_agent_s_session_is_refused_whatever_token_it_holds(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.setenv("NSTACK_AGENT", "scout")
    assert settings.run(root, apply=True) == 1
    assert "an agent's session" in capsys.readouterr().out and Forge.writes == []


def test_without_a_terminal_nothing_is_applied(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.setattr(settings, "_interactive", lambda: False)
    monkeypatch.setattr(settings, "_ask", _never)
    assert settings.run(root, apply=True) == 1
    out = capsys.readouterr().out
    assert "confirmed at the keyboard" in out and Forge.writes == []
    assert "G1: POST /rulesets" in out, "the plan is shown, even when it is not applied"


@pytest.mark.parametrize("answer", ["", "n", "no", "yes please"])
def test_anything_but_yes_applies_nothing(forge, monkeypatch, capsys, answer):
    root, read_back = forge
    missing(monkeypatch, "G1")
    monkeypatch.setattr(settings, "_ask", lambda prompt: answer)
    assert settings.run(root, apply=True) == 1
    assert Forge.writes == [] and read_back == [] and "Nothing was changed" in capsys.readouterr().out


def test_the_plan_alone_never_asks_the_gh_login(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setattr(settings, "_gh_token", _never)
    assert settings.run(root) == 0 and Forge.writes == []


def test_a_ruleset_the_forge_took_with_its_checks_leaves_nothing_by_hand(forge, monkeypatch, capsys):
    """Measured 2026-11-19 (D244): the rulesets API takes a required check it never saw run."""
    root, _ = forge
    missing(monkeypatch, "G1", "G4")
    Forge.answers[("POST", "/rulesets")] = (201, {})
    assert settings.run(root, apply=True) == 0
    out = capsys.readouterr().out
    assert "applied  G1, G4: POST /rulesets (HTTP 201)" in out and "Left to do by hand" not in out, out


@pytest.mark.parametrize("before", [None, ""])
def test_the_read_back_reads_with_the_gh_login_and_puts_back_what_was_there(forge, monkeypatch, capsys, before):
    """An empty GH_TOKEN is no credential: the gh login is used, and doctor reads with it too."""
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.delenv("GH_TOKEN")
    if before is not None:
        monkeypatch.setenv("GH_TOKEN", before)
    monkeypatch.setattr(settings, "_gh_token", lambda: GH_LOGIN)
    seen = []
    monkeypatch.setattr(doctor, "run", lambda root: seen.append(os.environ.get("GH_TOKEN")) or 0)
    assert settings.run(root, apply=True) == 0
    assert seen == [GH_LOGIN] and os.environ.get("GH_TOKEN") == before


def test_github_token_is_named_as_the_credential_it_is(forge, monkeypatch, capsys):
    root, _ = forge
    missing(monkeypatch, "G1")
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    assert settings.run(root, apply=True) == 0
    assert "with the token in GITHUB_TOKEN" in capsys.readouterr().out


@pytest.mark.parametrize(("api", "host"), [("https://api.github.com", "github.com"),
                                           ("https://ghe.example/api/v3", "ghe.example")])
def test_the_gh_login_asked_is_the_one_for_the_api_s_host(monkeypatch, api, host):
    asked = []

    class Done:
        returncode, stdout = 0, "gho_x\n"

    monkeypatch.setattr(settings.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(settings.subprocess, "run", lambda argv, **kw: asked.append(argv) or Done())
    monkeypatch.setenv("GITHUB_API_URL", api)
    assert REAL_GH_TOKEN() == "gho_x"  # the real one, gh itself stubbed
    assert asked == [["/usr/bin/gh", "auth", "token", "--hostname", host]]
