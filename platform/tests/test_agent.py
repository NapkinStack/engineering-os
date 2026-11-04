"""D196, PDR-0022 §8, ADR-0004: `nstack agent add` gives an agent its identity in one command and
the forge's two clicks — the App created from a manifest, then installed. Its key stays in a folder
of the agent's own; git and gh in its clone get the App's tokens, minted per call, and nothing of
the person's. Against a forge of this test's own; the test plays the person's browser.
"""

from __future__ import annotations

import html
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from napkinstack import agent

REMOTE = agent.remote  # the real one: the fixture puts a bare repository in its place
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption()).decode()
PUBLIC = KEY.public_key()


class Forge(http.server.BaseHTTPRequestHandler):
    installed = True
    owner_type = "Organization"
    calls: list = []
    token_bodies: list = []
    git_auth: list = []

    def log_message(self, *args):
        pass

    def _send(self, status: int, body) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _app_jwt(self) -> bool:
        auth = self.headers.get("Authorization", "")
        try:
            claims = jwt.decode(auth.removeprefix("Bearer "), PUBLIC, algorithms=["RS256"])
        except jwt.PyJWTError:
            return False
        return claims.get("iss") == "4242" and claims["exp"] - claims["iat"] <= 600  # the forge's limit

    def do_GET(self):
        Forge.calls.append(("GET", self.path))
        if self.path.startswith("/acme/demo.git/"):  # git over HTTP: every credential it is handed, refused
            Forge.git_auth.append(self.headers.get("Authorization"))
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="GitHub"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if self.path == "/users/acme":
            return self._send(200, {"login": "acme", "type": self.owner_type})
        if self.path == "/users/demo-scout%5Bbot%5D":
            return self._send(200, {"login": "demo-scout[bot]", "id": 9001})
        if self.path == "/repos/acme/demo/installation":
            if not self._app_jwt():
                return self._send(401, {"message": "Bad credentials"})
            return self._send(200, {"id": 77}) if self.installed else self._send(404, {"message": "Not Found"})
        self._send(404, {"message": "Not Found"})

    def do_POST(self):
        Forge.calls.append(("POST", self.path))
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/app-manifests/the-code/conversions":
            return self._send(201, {"id": 4242, "slug": "demo-scout", "pem": PEM, "owner": {"login": "acme"},
                                    "client_secret": "x", "webhook_secret": None})
        if self.path == "/app/installations/77/access_tokens":
            if not self._app_jwt():
                return self._send(401, {"message": "Bad credentials"})
            Forge.token_bodies.append(body)
            return self._send(201, {"token": "ghs_installation-token", "expires_at": "2099-01-01T00:00:00Z"})
        self._send(404, {"message": "Not Found"})


@pytest.fixture
def forge(monkeypatch, tmp_path):
    Forge.installed, Forge.owner_type, Forge.calls, Forge.token_bodies, Forge.git_auth = True, "Organization", [], [], []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Forge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("GITHUB_API_URL", url)
    monkeypatch.setenv("GITHUB_SERVER_URL", url)
    monkeypatch.setenv("NSTACK_AGENTS_HOME", str(tmp_path / "agents"))
    monkeypatch.delenv("NSTACK_AGENT", raising=False)
    monkeypatch.setattr(agent, "POLL", 0.05)
    yield url
    server.shutdown()


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project whose remote is a bare repository standing in for the forge's."""
    bare = tmp_path / "remote.git"
    _git("init", "-q", "--bare", "-b", "main", str(bare))
    root = tmp_path / "demo"
    _git("init", "-q", "-b", "main", str(root))
    (root / ".copier-answers.yml").write_text("forge: github\ngithub_repo: acme/demo\n", encoding="utf-8")
    _git("-c", "user.name=P", "-c", "user.email=p@example.com", "add", ".", cwd=root)
    _git("-c", "user.name=P", "-c", "user.email=p@example.com", "commit", "-qm", "start", cwd=root)
    _git("push", "-q", str(bare), "main", cwd=root)
    monkeypatch.setattr(agent, "remote", lambda repo: str(bare))
    return root


class Browser:
    """The person's browser: opens the local page, submits its form to the forge as the person's click
    would, and the forge sends it back with a code. Then it is sent to the installation page."""

    def __init__(self, state: str | None = None, code: str = "the-code"):
        self.opened: list[str] = []
        self.forms: list[tuple[str, dict]] = []
        self.state, self.code = state, code

    def __call__(self, url: str) -> bool:
        self.opened.append(url)
        if urllib.parse.urlsplit(url).path == "/":
            threading.Thread(target=self._click, args=(url,), daemon=True).start()
        return True

    def _click(self, url: str) -> None:
        page = urllib.request.urlopen(url, timeout=5).read().decode()
        action = html.unescape(re.search(r'action="([^"]+)"', page)[1])
        manifest = json.loads(html.unescape(re.search(r'name="manifest" value="([^"]+)"', page)[1]))
        self.forms.append((action, manifest))
        state = self.state or urllib.parse.parse_qs(urllib.parse.urlsplit(action).query)["state"][0]
        redirect = manifest["redirect_url"]

        class Stay(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        try:
            urllib.request.build_opener(Stay).open(f"{redirect}?code={self.code}&state={state}", timeout=5)
        except urllib.error.HTTPError:
            pass


def test_one_command_makes_the_app_installs_it_and_configures_an_isolated_clone(forge, project, capsys):
    browser = Browser()
    code = agent.add(project, "scout", browser=browser)
    out = capsys.readouterr().out
    assert code == 0, out
    action, manifest = browser.forms[0]
    assert action.startswith(f"{forge}/organizations/acme/settings/apps/new?state=")
    assert manifest["public"] is False
    assert manifest["default_permissions"] == {"contents": "write", "pull_requests": "write", "issues": "write",
                                               "actions": "read", "checks": "read", "metadata": "read"}
    assert "administration" not in manifest["default_permissions"]
    assert manifest["hook_attributes"]["active"] is False
    assert browser.opened[-1] == f"{forge}/apps/demo-scout/installations/new"
    home = Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout"
    assert (home / "key.pem").read_text() == PEM
    if os.name == "posix":
        assert (home / "key.pem").stat().st_mode & 0o777 == 0o600
    assert json.loads((home / "app.json").read_text())["repo"] == "acme/demo"
    clone = project.parent / "demo-scout"
    assert _git("config", "--local", "user.name", cwd=clone) == "demo-scout[bot]"
    assert _git("config", "--local", "user.email", cwd=clone) == "9001+demo-scout[bot]@users.noreply.github.com"
    helpers = subprocess.run(["git", "config", "--local", "--get-all", "credential.helper"], cwd=clone,
                             capture_output=True, text=True, check=True).stdout.splitlines()
    assert helpers[0] == "" and "agent credential scout" in helpers[1]
    assert "nstack agent run scout --" in out
    assert "PEM" not in out and "ghs_" not in out


def test_the_minted_token_reaches_only_this_repository_and_serves_git(forge, project, tmp_path):
    assert agent.add(project, "scout", browser=Browser()) == 0
    assert agent.mint("scout") == "ghs_installation-token"
    assert Forge.token_bodies[-1] == {"repositories": ["demo"]}
    host = urllib.parse.urlsplit(forge).netloc
    answer = subprocess.run([sys.executable, "-m", "napkinstack", "agent", "credential", "scout", "get"],
                            input=f"protocol=https\nhost={host}\n\n", capture_output=True, text=True,
                            env={**os.environ}, check=True).stdout
    assert answer == "username=x-access-token\npassword=ghs_installation-token\n"
    other = subprocess.run([sys.executable, "-m", "napkinstack", "agent", "credential", "scout", "get"],
                           input="protocol=https\nhost=elsewhere.example\n\n", capture_output=True, text=True,
                           env={**os.environ}, check=True).stdout
    assert other == ""


def test_an_owner_who_is_a_person_gets_the_personal_page(forge, project):
    Forge.owner_type = "User"
    browser = Browser()
    assert agent.add(project, "scout", browser=browser) == 0
    assert browser.forms[0][0].startswith(f"{forge}/settings/apps/new?state=")


def test_mine_makes_a_public_app_on_the_person_s_account(forge, project):
    browser = Browser()
    assert agent.add(project, "scout", mine=True, browser=browser) == 0
    action, manifest = browser.forms[0]
    assert action.startswith(f"{forge}/settings/apps/new?state=") and manifest["public"] is True


def test_workflows_write_is_asked_for_only_when_named(forge, project):
    browser = Browser()
    assert agent.add(project, "scout", workflows=True, browser=browser) == 0
    assert browser.forms[0][1]["default_permissions"]["workflows"] == "write"


def test_a_wrong_state_is_refused_and_nothing_is_kept(forge, project, capsys):
    code = agent.add(project, "scout", browser=Browser(state="forged"), wait=1)
    assert code == 1
    assert "FAIL [agent]" in capsys.readouterr().out
    assert not (Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout" / "key.pem").exists()
    assert ("POST", "/app-manifests/the-code/conversions") not in Forge.calls


def test_not_installed_in_time_is_said_and_a_second_run_resumes_without_a_new_app(forge, project, capsys):
    Forge.installed = False
    assert agent.add(project, "scout", browser=Browser(), wait=0.3) == 1
    out = capsys.readouterr().out
    assert "not installed" in out and "nstack agent add scout" in out
    Forge.installed = True
    browser = Browser()
    assert agent.add(project, "scout", browser=browser) == 0
    assert not browser.forms, "the App made before is reused"
    assert sum(1 for call in Forge.calls if call[1].startswith("/app-manifests/")) == 1


HOOKS = """\
default_install_hook_types: [pre-commit, commit-msg, pre-push]
repos:
  - repo: local
    hooks:
      - id: no-secret
        name: no secret
        language: fail
        entry: a secret is committed
        files: ^secret$
"""


def _with_hooks(project: Path, config: str = HOOKS) -> None:
    """The project's hooks, committed and pushed to the bare repository standing for the forge."""
    (project / ".pre-commit-config.yaml").write_text(config, encoding="utf-8")
    _git("-c", "user.name=P", "-c", "user.email=p@example.com", "add", ".", cwd=project)
    _git("-c", "user.name=P", "-c", "user.email=p@example.com", "commit", "-qm", "hooks", cwd=project)
    _git("push", "-q", str(project.parent / "remote.git"), "main", cwd=project)


def _commit_as_the_agent(clone: Path, name: str) -> subprocess.CompletedProcess:
    (clone / name).write_text("x\n")
    env = agent._environment("scout")
    subprocess.run(["git", "add", name], cwd=clone, env=env, check=True)
    return subprocess.run(["git", "commit", "-qm", f"add {name}"], cwd=clone, env=env, capture_output=True, text=True)


def test_the_agent_s_commits_pass_the_project_s_hooks(forge, project, tmp_path, monkeypatch, capsys):
    """D198: the clone gets the project's hooks — gitleaks among them in a project nstack made —
    installed by the engine's own pre-commit, whatever the person's git configuration says."""
    _with_hooks(project)
    person = tmp_path / "person.gitconfig"
    person.write_text(f"[core]\n\thooksPath = {tmp_path / 'person-hooks'}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(person))  # pre-commit refuses to install under it
    monkeypatch.setenv("PRE_COMMIT_HOME", str(tmp_path / "pre-commit-cache"))
    assert agent.add(project, "scout", browser=Browser()) == 0, capsys.readouterr().out
    assert "hooks: the project's, run on every commit" in capsys.readouterr().out
    clone = project.parent / "demo-scout"
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        assert "generated by pre-commit" in (clone / ".git" / "hooks" / hook).read_text()
    refused = _commit_as_the_agent(clone, "secret")
    assert refused.returncode != 0 and "a secret is committed" in refused.stdout + refused.stderr
    _git("rm", "-q", "--cached", "secret", cwd=clone)
    assert _commit_as_the_agent(clone, "notes").returncode == 0


def test_a_second_run_puts_back_the_hooks_of_a_clone_made_before(forge, project, capsys):
    _with_hooks(project)
    assert agent.add(project, "scout", browser=Browser()) == 0
    hook = project.parent / "demo-scout" / ".git" / "hooks" / "pre-commit"
    hook.unlink()
    assert agent.add(project, "scout", browser=Browser()) == 0
    assert "generated by pre-commit" in hook.read_text()


def test_a_second_run_proves_the_identity_without_judging_the_agent_s_work(forge, project, capsys):
    """The dry-run push proves who pushes, not what: a pre-push hook refusing the agent's unpushed
    work must not turn into "the clone cannot push as the App"."""
    _with_hooks(project, "default_install_hook_types: [pre-commit, pre-push]\nrepos:\n  - repo: local\n"
                "    hooks:\n      - id: refuse-push\n        name: refuse push\n        language: fail\n"
                "        entry: not yet\n        stages: [pre-push]\n")
    assert agent.add(project, "scout", browser=Browser()) == 0
    assert _commit_as_the_agent(project.parent / "demo-scout", "notes").returncode == 0
    capsys.readouterr()
    assert agent.add(project, "scout", browser=Browser()) == 0, capsys.readouterr().out


def test_a_project_without_hooks_is_said_and_its_agent_still_commits(forge, project, capsys):
    """pre-commit installed without a configuration refuses every commit: nothing is installed,
    and the summary says the project has no hooks."""
    assert agent.add(project, "scout", browser=Browser()) == 0
    assert "hooks: none, the project has no .pre-commit-config.yaml" in capsys.readouterr().out
    clone = project.parent / "demo-scout"
    assert not (clone / ".git" / "hooks" / "pre-commit").exists()
    assert _commit_as_the_agent(clone, "notes").returncode == 0


def test_hooks_that_cannot_be_installed_stop_it(forge, project, capsys):
    _with_hooks(project)
    assert agent.add(project, "scout", browser=Browser()) == 0
    clone = project.parent / "demo-scout"
    _git("config", "--local", "core.hooksPath", "elsewhere", cwd=clone)
    capsys.readouterr()
    assert agent.add(project, "scout", browser=Browser()) == 1
    out = capsys.readouterr().out
    assert "FAIL [agent] the project's hooks could not be installed" in out and "core.hooksPath" in out


def test_an_agent_session_cannot_run_it(forge, project, monkeypatch, capsys):
    monkeypatch.setenv("NSTACK_AGENT", "scout")
    assert agent.add(project, "other", browser=Browser()) == 1
    assert "a person runs it" in capsys.readouterr().out


def test_run_hands_the_agent_none_of_the_person_s_credentials(forge, project, monkeypatch):
    assert agent.add(project, "scout", browser=Browser()) == 0
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "GH_ENTERPRISE_TOKEN"):
        monkeypatch.setenv(name, "the-person-s")
    probe = ("import json, os; print(json.dumps({k: os.environ.get(k) for k in "
             "['GH_TOKEN', 'GITHUB_TOKEN', 'SSH_AUTH_SOCK', 'GH_ENTERPRISE_TOKEN', 'GIT_CONFIG_GLOBAL', "
             "'GIT_CONFIG_NOSYSTEM', 'GH_CONFIG_DIR', 'NSTACK_AGENT']}), os.getcwd())")
    out = subprocess.run([sys.executable, "-m", "napkinstack", "agent", "run", "scout", "--",
                          sys.executable, "-c", probe], capture_output=True, text=True, check=True).stdout
    seen, cwd = out.rsplit("}", 1)
    seen = json.loads(seen + "}")
    home = Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout"
    assert seen == {"GH_TOKEN": None, "GITHUB_TOKEN": None, "SSH_AUTH_SOCK": None, "GH_ENTERPRISE_TOKEN": None,
                    "GIT_CONFIG_GLOBAL": str(home / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
                    "GH_CONFIG_DIR": str(home / "gh"), "NSTACK_AGENT": "scout"}
    assert Path(cwd.strip()).resolve() == (project.parent / "demo-scout").resolve()


def test_an_unknown_agent_is_named(forge, capsys):
    assert agent.mint("nobody") is None
    assert "nstack agent add nobody" in capsys.readouterr().out


@pytest.mark.skipif(os.name != "posix", reason="the POSIX shim; Windows gets gh.cmd")
def test_gh_in_the_agent_s_environment_is_the_app_and_refuses_a_login(forge, project, tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    fake = tools / "gh"
    fake.write_text('#!/bin/sh\necho "token=$GH_TOKEN config=$GH_CONFIG_DIR github=${GITHUB_TOKEN:-none} args=$*"\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GITHUB_TOKEN", "the-person-s")
    assert agent.add(project, "scout", browser=Browser()) == 0
    home = Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout"
    said = subprocess.run([sys.executable, "-m", "napkinstack", "agent", "run", "scout", "--", "gh", "pr", "list"],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert said == f"token=ghs_installation-token config={home / 'gh'} github=none args=pr list"
    login = subprocess.run([sys.executable, "-m", "napkinstack", "agent", "run", "scout", "--", "gh", "auth", "login"],
                           capture_output=True, text=True)
    assert login.returncode == 2 and "auth login refused" in login.stderr
    status = subprocess.run([sys.executable, "-m", "napkinstack", "agent", "run", "scout", "--", "gh", "auth", "status"],
                            capture_output=True, text=True, check=True).stdout
    assert "args=auth status" in status, "reading the login is not keeping one"


def _person(tmp_path, monkeypatch, netrc: str) -> None:
    person = tmp_path / "person"
    person.mkdir()
    (person / ".netrc").write_text(netrc)
    (person / ".netrc").chmod(0o600)
    monkeypatch.setenv("HOME", str(person))


def _ls_remote() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "napkinstack", "agent", "run", "scout", "--", "git", "ls-remote",
                           "origin"], capture_output=True, text=True, timeout=60)


def test_git_over_https_hands_the_app_s_token_never_the_config_the_person_s_shell_injects(
        forge, project, tmp_path, monkeypatch):
    import base64

    assert agent.add(project, "scout", browser=Browser()) == 0
    _git("remote", "set-url", "origin", REMOTE("acme/demo"), cwd=project.parent / "demo-scout")
    _person(tmp_path, monkeypatch, "machine elsewhere.example login person password PERSONSECRET\n")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "http.extraHeader")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "Authorization: Basic cGVyc29uOklOSkVDVEVE")
    _ls_remote()
    handed = [base64.b64decode(auth.split()[1]).decode() for auth in Forge.git_auth if auth]
    assert "x-access-token:ghs_installation-token" in handed, handed
    assert all(one.startswith("x-access-token:") and "PERSONSECRET" not in one for one in handed), handed
    assert not any("cGVyc29uOklOSkVDVEVE" in (auth or "") for auth in Forge.git_auth), "the injected header went out"


@pytest.mark.parametrize("entry", ["machine 127.0.0.1 login person password PERSONSECRET\n",
                                   "default login person password PERSONSECRET\n"])
def test_a_netrc_login_for_the_forge_stops_the_agent_before_git_can_hand_it_over(
        forge, project, tmp_path, monkeypatch, entry, capsys):
    """libcurl reads ~/.netrc whatever git's configuration; some versions send its password under the
    address's own user (seen on CI). Nothing in the clone can stop it: the agent does not start."""
    assert agent.add(project, "scout", browser=Browser()) == 0
    _git("remote", "set-url", "origin", REMOTE("acme/demo"), cwd=project.parent / "demo-scout")
    _person(tmp_path, monkeypatch, entry)
    refused = _ls_remote()
    assert refused.returncode == 1 and ".netrc holds a login for 127.0.0.1" in refused.stdout, refused.stdout
    assert not Forge.git_auth, "git never ran"
    assert agent.add(project, "scout", browser=Browser()) == 1
    assert ".netrc holds a login" in capsys.readouterr().out


def test_the_helper_calls_the_engine_that_made_it_not_another_on_the_path(forge, project):
    assert agent.add(project, "scout", browser=Browser()) == 0
    helper = _git("config", "--local", "--get-all", "credential.helper", cwd=project.parent / "demo-scout")
    assert Path(sys.executable).as_posix() in helper and "-m napkinstack agent credential scout" in helper


def test_a_folder_that_is_not_this_agent_s_clone_is_refused(forge, project, capsys):
    (project.parent / "demo-scout").mkdir()
    assert agent.add(project, "scout", browser=Browser()) == 1
    assert "is not this agent's clone" in capsys.readouterr().out


def test_an_agent_already_on_another_repository_is_refused(forge, project, capsys):
    assert agent.add(project, "scout", browser=Browser()) == 0
    (project / ".copier-answers.yml").write_text("forge: github\ngithub_repo: acme/other\n", encoding="utf-8")
    assert agent.add(project, "scout", browser=Browser()) == 1
    assert "already works on acme/demo" in capsys.readouterr().out


def test_a_push_the_forge_would_refuse_fails_the_command(forge, project, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(agent, "remote", lambda repo: str(tmp_path / "no-such-remote.git"))
    clone = project.parent / "demo-scout"
    _git("clone", "-q", str(tmp_path / "remote.git"), str(clone))
    _git("config", "nstack.agent", "scout", cwd=clone)
    _git("remote", "set-url", "origin", str(tmp_path / "no-such-remote.git"), cwd=clone)
    assert agent.add(project, "scout", browser=Browser()) == 1
    assert "cannot push as the App" in capsys.readouterr().out


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
def test_the_agent_s_folder_is_the_person_s_alone(forge, project):
    assert agent.add(project, "scout", browser=Browser()) == 0
    assert (Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout").stat().st_mode & 0o777 == 0o700


# D199: an agent knows what it is, and its tool works from the first run.

def _run(*args: str, env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "napkinstack", "agent", *args], capture_output=True, text=True,
                          env=env, cwd=cwd)


def _checkout(tmp_path, name: str, email: str) -> Path:
    """A checkout whose own git configuration names who commits there."""
    root = tmp_path / "checkout"
    root.mkdir()
    _git("init", "-q", cwd=root)
    _git("config", "--local", "user.name", name, cwd=root)
    _git("config", "--local", "user.email", email, cwd=root)
    return root


def _claude_stand_in(tmp_path, monkeypatch) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "claude").write_text('#!/bin/sh\nfor a in "$@"; do echo "arg=$a"; done\n')
    (tools / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")


def test_run_says_what_the_agent_gets_and_what_it_keeps_of_the_person(forge, project):
    assert agent.add(project, "scout", browser=Browser()) == 0
    done = _run("run", "scout", "--", sys.executable, "-c", "print('the agent speaks')")
    assert done.returncode == 0 and done.stdout == "the agent speaks\n", "the agent's own output is untouched"
    said = done.stderr
    assert "Agent scout: demo-scout[bot] on acme/demo" in said
    assert "removed: your tokens, SSH agent and git configuration" in said
    assert "kept: your agent tool's own configuration" in said and "nstack agent status" in said


@pytest.mark.skipif(os.name != "posix", reason="a POSIX stand-in for claude")
def test_claude_gets_settings_of_the_agent_s_own_that_keep_the_sandbox(forge, project, tmp_path, monkeypatch):
    _claude_stand_in(tmp_path, monkeypatch)
    assert agent.add(project, "scout", browser=Browser()) == 0
    done = _run("run", "scout", "--", "claude", "-p", "review #1")
    assert done.returncode == 0, done.stderr
    args = [line[4:] for line in done.stdout.splitlines()]
    home = Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout"
    assert args == ["--settings", str(home / "claude-settings.json"), "-p", "review #1"]
    settings = json.loads((home / "claude-settings.json").read_text())
    host = urllib.parse.urlsplit(forge).hostname  # the test's forge serves web and API on one host
    assert settings == {"sandbox": {"network": {"allowedDomains": [host]},
                                    "filesystem": {"allowWrite": [str(home / "gh")]}},
                        "env": {"GIT_HTTP_PROXY_AUTHMETHOD": "basic"}}, \
        "the forge's hosts and the agent's gh folder, nothing more; the sandbox never switched"
    assert "--settings" in done.stderr and "sandbox" in done.stderr


def test_on_github_com_the_agent_s_settings_also_open_the_ci_logs_host(forge, project, monkeypatch):
    assert agent.add(project, "scout", browser=Browser()) == 0
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com")
    settings = json.loads(agent._claude_settings("scout").read_text())
    # `gh run view --log` is redirected there by the API (seen 2026-11-03); a job's own log goes to
    # Azure blob storage, left closed: opening it would open every Azure account
    assert settings["sandbox"]["network"]["allowedDomains"] == [
        "api.github.com", "github.com", "results-receiver.actions.githubusercontent.com"]


@pytest.mark.skipif(os.name != "posix", reason="a POSIX stand-in for claude")
def test_settings_the_person_gives_claude_are_kept_and_said(forge, project, tmp_path, monkeypatch):
    _claude_stand_in(tmp_path, monkeypatch)
    assert agent.add(project, "scout", browser=Browser()) == 0
    for given in (["--settings", "mine.json"], ["--settings=mine.json"]):
        done = _run("run", "scout", "--", "claude", *given)
        assert [line[4:] for line in done.stdout.splitlines()] == given
        assert "your --settings is kept" in done.stderr
        assert f"allowedDomains needs {urllib.parse.urlsplit(forge).hostname}." in done.stderr, \
            "the person is told the hosts their own settings must open"


def test_the_agent_s_environment_names_its_gh_for_a_guard_hook(forge, project):
    """A person's hook against a bare gh lets the agent's through by this one comparison (07 §7):
    it holds wherever the agents' folder is — NSTACK_AGENTS_HOME, XDG_CONFIG_HOME or APPDATA."""
    assert agent.add(project, "scout", browser=Browser()) == 0
    env = agent._environment("scout")
    assert Path(env["GH_CONFIG_DIR"]).parent / "bin" / "gh" == Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout" / "bin" / "gh"


@pytest.mark.skipif(os.name != "posix", reason="a POSIX stand-in for gh")
def test_status_says_whether_gh_here_is_the_agent_s(forge, project, tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "gh").write_text("#!/bin/sh\n")
    (tools / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")
    assert agent.add(project, "scout", browser=Browser()) == 0
    shim = Path(os.environ["NSTACK_AGENTS_HOME"]) / "scout" / "bin" / "gh"
    assert f"gh: as the App ({shim})" in _run("status", env=dict(agent._environment("scout"))).stdout
    person = {k: v for k, v in os.environ.items() if k != "NSTACK_AGENT"}
    assert "gh here is not the agent" in _run("status", "scout", env=person).stdout


def test_status_tells_an_agent_who_it_is(forge, project):
    assert agent.add(project, "scout", browser=Browser()) == 0
    done = _run("status", env=dict(agent._environment("scout")))
    assert done.returncode == 0, done.stdout
    out = done.stdout
    assert "You are agent scout: demo-scout[bot], on acme/demo" in out
    assert str((project.parent / "demo-scout").resolve()) in out
    assert "hooks: none" in out  # the test project has no .pre-commit-config.yaml
    assert "this session: the agent's" in out


def test_status_lists_the_agents_for_a_person(forge, project, tmp_path):
    assert agent.add(project, "scout", browser=Browser()) == 0
    done = _run("status", env={k: v for k, v in os.environ.items() if k != "NSTACK_AGENT"},
                cwd=_checkout(tmp_path, "P", "p@example.com"))
    assert done.returncode == 0
    assert "scout" in done.stdout and "demo-scout[bot]" in done.stdout and "acme/demo" in done.stdout
    assert "this session: yours, not an agent's" in done.stdout


# D202 (#352): a session under an App made by hand commits as a bot, NSTACK_AGENT unset; it was
# told "yours, not an agent's", and an agent that believes it acts for the person may approve.
@pytest.mark.parametrize("name, email, said", [
    ("napkinstack-agent[bot]", "1+napkinstack-agent[bot]@users.noreply.github.com",
     "this session: commits as napkinstack-agent[bot], an App not made by nstack agent add"),
    ("Someone", "2+other[bot]@users.noreply.github.com",
     "this session: commits as 2+other[bot]@users.noreply.github.com, an App not made by nstack agent add"),
    ("demo-scout[bot]", "3+demo-scout[bot]@users.noreply.github.com",
     "this session: commits as demo-scout[bot], agent scout's App, without nstack agent run"),
], ids=["a hand-made App", "named by its email", "an agent's clone, not started as it"])
def test_a_session_that_commits_as_an_app_is_never_called_the_person_s(forge, project, tmp_path, name, email, said):
    assert agent.add(project, "scout", browser=Browser()) == 0
    done = _run("status", env={k: v for k, v in os.environ.items() if k != "NSTACK_AGENT"},
                cwd=_checkout(tmp_path, name, email))
    assert done.returncode == 0, done.stdout
    assert said in done.stdout and "yours, not an agent's" not in done.stdout, done.stdout


def test_status_of_an_agent_read_from_a_person_s_session_says_so(forge, project):
    assert agent.add(project, "scout", browser=Browser()) == 0
    done = _run("status", "scout", env={k: v for k, v in os.environ.items() if k != "NSTACK_AGENT"})
    assert done.returncode == 0
    assert "this session: not the agent's: start it with nstack agent run scout" in done.stdout


def test_status_of_an_unknown_agent_says_how_to_make_it(forge):
    done = _run("status", "nobody")
    assert done.returncode == 1 and "nstack agent add nobody" in done.stdout
