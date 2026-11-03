"""An agent's identity in one command (PDR-0022 §8, ADR-0004).

`nstack agent add <name>`, run by a person in their own terminal, beside their browser:

1. creates the agent's GitHub App from a manifest — the forge asks the person for one click;
2. keeps the App's key in a folder of the agent's own, outside any repository;
3. sends the person to the App's installation page — their second click, on this repository;
4. clones the repository beside the project, configured to act as the App and as nothing else.

Then `nstack agent run <name> -- <the agent's command>` starts the agent in that clone, with none
of the person's credentials in its environment. Git and gh get the App's tokens, minted per call
for this repository alone and valid one hour, never written to disk.

What it cannot do: keep an agent that wants them away from the person's files. Removing the
credentials from its environment is not a sandbox (ADR-0004: a sandbox, a container or a
dedicated system user).
"""

from __future__ import annotations

import html
import http.server
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

import yaml

from napkinstack import __version__

POLL = 3.0  # seconds between two reads of the installation
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,24}$")
PERMISSIONS = {"contents": "write", "pull_requests": "write", "issues": "write",
               "actions": "read", "checks": "read", "metadata": "read"}
# What would let the agent's environment act as the person: their tokens, their SSH agent and
# commands, git configuration their shell injects, and the variables that point gh at another host.
PERSONAL = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST",
            "SSH_AUTH_SOCK", "GIT_ASKPASS", "SSH_ASKPASS", "GIT_SSH", "GIT_SSH_COMMAND", "GIT_PROXY_COMMAND",
            "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT")  # without the count, git reads no GIT_CONFIG_KEY_n
REFUSED_AUTH = {"login", "logout", "refresh", "setup-git", "switch"}  # what would keep or change a login
CI_LOGS = "results-receiver.actions.githubusercontent.com"  # where github.com serves a run's logs


def _api() -> str:
    return (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")


def _web() -> str:
    return (os.environ.get("GITHUB_SERVER_URL") or "https://github.com").rstrip("/")


def remote(repo: str) -> str:
    """Where the agent's clone is made from: HTTPS, where git asks the credential helper. The user
    is named in the address, so that git never takes one from the person's ~/.netrc."""
    web = urllib.parse.urlsplit(_web())
    return f"{web.scheme}://x-access-token@{web.netloc}{web.path}/{repo}.git"


def home() -> Path:
    """The agents' folders: the user's configuration, never a repository."""
    if given := os.environ.get("NSTACK_AGENTS_HOME"):
        return Path(given)
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "nstack" / "agents"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "nstack" / "agents"


def _say(message: str, out=None) -> None:
    print(message, file=out or sys.stdout, flush=True)


def _call(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": f"nstack/{__version__}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{_api()}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None
    except (OSError, ValueError):
        return 0, None


def _app_token(app: dict) -> str:
    """The App's own token, a JWT signed with its key: it reads the App's installations, nothing else."""
    import jwt

    now = int(time.time())
    key = (home() / app["name"] / "key.pem").read_text(encoding="utf-8")
    return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": str(app["id"])}, key, algorithm="RS256")


def _load(name: str) -> dict | None:
    path = home() / name / "app.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _save(app: dict) -> None:
    (home() / app["name"] / "app.json").write_text(json.dumps(app, indent=2) + "\n", encoding="utf-8")


def _installation(app: dict) -> tuple[int, int | None]:
    status, data = _call("GET", f"/repos/{app['repo']}/installation", _app_token(app))
    return status, (data or {}).get("id") if status == 200 and isinstance(data, dict) else None


def mint(name: str, out=None) -> str | None:
    """A token of the App's installation, for this repository alone, valid one hour."""
    app = _load(name)
    if app is None:
        _say(f"FAIL [agent] no agent named {name} on this workstation.\n"
             f"      Action: a person runs nstack agent add {name} at the project's root.", out)
        return None
    if not app.get("installation"):
        status, installation = _installation(app)
        if not installation:
            _say(f"FAIL [agent] the App {app['slug']} is not installed on {app['repo']} (HTTP {status}).\n"
                 f"      Action: a person runs nstack agent add {name} again, and installs it.", out)
            return None
        app["installation"] = installation
        _save(app)
    status, data = _call("POST", f"/app/installations/{app['installation']}/access_tokens", _app_token(app),
                         {"repositories": [app["repo"].split("/", 1)[1]]})
    if status != 201 or not isinstance(data, dict) or not data.get("token"):
        _say(f"FAIL [agent] the forge minted no token for {app['slug']} (HTTP {status}).\n"
             f"      Action: check the App is still installed on {app['repo']}: nstack agent add {name} says so.",
             out)
        return None
    return str(data["token"])


def credential(name: str, action: str) -> int:
    """git's credential helper: the App's token for the forge's host, nothing for any other."""
    if action != "get":
        return 0
    asked = dict(line.split("=", 1) for line in sys.stdin.read().splitlines() if "=" in line)
    if asked.get("host") != urllib.parse.urlsplit(_web()).netloc:
        return 0
    token = mint(name, out=sys.stderr)
    if token is None:
        return 1
    print(f"username=x-access-token\npassword={token}", flush=True)
    return 0


def token(name: str) -> int:
    """Prints a token, for a tool that takes one from its environment."""
    minted = mint(name, out=sys.stderr)
    if minted is None:
        return 1
    print(minted)
    return 0


def _engine() -> str:
    """How git and the shim call this engine back: the interpreter running it, by its absolute
    path — never the `nstack` the PATH finds, which may be another version."""
    return f'"{Path(sys.executable).as_posix()}" -m napkinstack'


def _netrc() -> str | None:
    """A ~/.netrc entry git would hand the forge in the agent's clone: libcurl reads it whatever
    git's configuration, and some versions send its password under the address's own user. None
    when there is none; else what to say."""
    host = urllib.parse.urlsplit(_web()).hostname or ""
    paths = [Path(os.environ["NETRC"])] if os.environ.get("NETRC") else []
    paths += [Path.home() / ".netrc", Path.home() / "_netrc"]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(rf"(^|\s)(machine\s+{re.escape(host)}|default)(\s|$)", text):
            return (f"FAIL [agent] {path} holds a login for {host}: git hands it to the forge in the agent's "
                    "clone, before the App's token and whatever the clone's configuration — the agent would "
                    "act as you.\n"
                    f"      Action: remove that entry from {path.name} (a credential helper of yours can replace "
                    "it), or run the agent in a sandbox with a home of its own.")
    return None


def _environment(name: str) -> dict[str, str]:
    """The agent's environment: none of the person's credentials, git without their configuration,
    gh with a folder of its own and a token minted per call."""
    folder = home() / name
    env = {key: value for key, value in os.environ.items() if key not in PERSONAL}
    env.update({"GIT_CONFIG_GLOBAL": str(folder / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
                "GH_CONFIG_DIR": str(folder / "gh"), "NSTACK_AGENT": name,
                "PATH": str(folder / "bin") + os.pathsep + env.get("PATH", "")})
    return env


def _shim(name: str) -> bool:
    """gh, as the App: a token minted per call, `gh auth` refused so no login is ever kept."""
    folder = home() / name
    real = shutil.which("gh", path=os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                                                    if Path(p) != folder / "bin"))
    if not real:
        return False
    (folder / "bin").mkdir(exist_ok=True)
    engine = _engine()
    if os.name == "nt":
        refuse = "".join(f'if "%1"=="auth" if "%2"=="{verb}" (echo gh: auth {verb} refused, this agent\'s token '
                         "is minted per call 1>&2 & exit /b 2)\r\n" for verb in sorted(REFUSED_AUTH))
        (folder / "bin" / "gh.cmd").write_text(
            "@echo off\r\nsetlocal\r\n" + refuse
            + f"for /f \"delims=\" %%t in ('{engine} agent token {name}') do set GH_TOKEN=%%t\r\n"
            f'set GITHUB_TOKEN=\r\nset GH_CONFIG_DIR={folder / "gh"}\r\n"{real}" %*\r\n', encoding="utf-8")
        return True
    import shlex

    shim = folder / "bin" / "gh"
    shim.write_text(
        "#!/bin/sh\n"
        f"# gh as the App of agent {name}: a token minted per call, never kept (nstack agent).\n"
        f'if [ "$1" = auth ]; then case "$2" in {"|".join(sorted(REFUSED_AUTH))})\n'
        '  echo "gh: auth $2 refused - this agent\'s token is minted per call" >&2; exit 2;; esac; fi\n'
        f"GH_TOKEN=\"$({engine} agent token {name})\" || exit 1\n"
        "unset GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN GH_HOST\n"
        f"GH_CONFIG_DIR={shlex.quote(str(folder / 'gh'))}\nexport GH_TOKEN GH_CONFIG_DIR\n"
        f"exec {shlex.quote(real)} \"$@\"\n", encoding="utf-8")
    shim.chmod(0o755)
    return True


def _create(owner: str, personal: bool, manifest: dict, browser, wait: float) -> tuple[dict | None, str]:
    """The manifest flow: a page on this machine posts the manifest to the forge, the person
    clicks, the forge comes back with a code this engine exchanges for the App and its key."""
    state = secrets.token_urlsafe(24)
    target = f"{_web()}/settings/apps/new" if personal else f"{_web()}/organizations/{owner}/settings/apps/new"
    result: dict = {}
    ignored: list[str] = []

    class Page(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _reply(self, status: int, text: str) -> None:
            body = text.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{port}":  # a page of another site, by DNS rebinding
                return self._reply(400, "Refused")
            url = urllib.parse.urlsplit(self.path)
            if url.path == "/":
                return self._reply(200, (
                    "<!DOCTYPE html><html><body>"
                    f'<form method="post" action="{html.escape(target + "?state=" + state)}">'
                    f'<input type="hidden" name="manifest" value="{html.escape(json.dumps(manifest))}">'
                    "<p>nstack: creating your agent's GitHub App.</p>"
                    '<button type="submit">Continue to GitHub</button></form>'
                    "<script>document.forms[0].submit()</script></body></html>"))
            if url.path != "/created":
                return self._reply(404, "Not found")
            query = urllib.parse.parse_qs(url.query)
            code = (query.get("code") or [""])[0]
            if not secrets.compare_digest((query.get("state") or [""])[0].encode(), state.encode()) or not code:
                ignored.append("an answer without this run's state came, and was ignored: a page of another run, or forged")
                return self._reply(400, "<p>Refused: not this run's answer. Nothing was kept.</p>")
            status, data = _call("POST", f"/app-manifests/{urllib.parse.quote(code, safe='')}/conversions")
            if status != 201 or not isinstance(data, dict) or not data.get("pem"):
                result["refused"] = f"the forge did not hand over the App (HTTP {status}); the code lasts one hour"
                return self._reply(502, "<p>The forge did not hand over the App. See the terminal.</p>")
            result["app"] = data
            self._reply(200, "<p>App created. Install it on the repository on the page that opens next; "
                             "this tab can be closed.</p>")

    server = http.server.HTTPServer(("127.0.0.1", 0), Page)
    server.timeout = 0.2
    port = server.server_address[1]
    manifest["redirect_url"] = f"http://127.0.0.1:{port}/created"
    page = f"http://127.0.0.1:{port}/"
    _say(f"Opening {page} — it sends you to GitHub. Check the App's name and permissions, then click "
         "Create GitHub App. (No browser here? Open that address on this machine.)")
    browser(page)
    deadline = time.monotonic() + wait
    try:
        while not result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "app" in result:
        return result["app"], ""
    return None, result.get("refused") or (ignored[-1] if ignored else f"no answer from the forge within {int(wait)} s")


def _git(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)


def _clone(app: dict, clone: Path, bot: dict) -> str | None:
    """Clones the repository, or takes the agent's clone made before; configures it to act as the
    App: its name, its address, its credential helper — and git's other helpers emptied first."""
    env = _environment(app["name"])
    helper = f"!{_engine()} agent credential {app['name']}"
    if clone.exists() and not clone.is_dir():
        return f"{clone} is a file"
    if clone.exists():
        if _git("config", "--local", "nstack.agent", cwd=clone).stdout.strip() != app["name"]:
            return f"{clone} exists and is not this agent's clone"
    else:
        made = _git("-c", "credential.helper=", "-c", f"credential.helper={helper}", "clone", "-q",
                    remote(app["repo"]), str(clone), env=env)
        if made.returncode:
            return f"git clone failed: {made.stderr.strip().splitlines()[-1] if made.stderr.strip() else made.returncode}"
    login = f"{app['slug']}[bot]"
    _git("config", "--local", "--unset-all", "credential.helper", cwd=clone)
    for args in (("user.name", login), ("user.email", f"{bot['id']}+{login}@users.noreply.github.com"),
                 ("nstack.agent", app["name"]), ("--add", "credential.helper", ""),
                 ("--add", "credential.helper", helper)):
        if _git("config", "--local", *args, cwd=clone).returncode:
            return f"git could not configure {clone}: {' '.join(args[:-1])}"
    if _git("remote", "set-url", "origin", remote(app["repo"]), cwd=clone).returncode:
        return f"{clone} has no remote origin to point at {app['repo']}"
    return None


def _hooks(name: str, clone: Path) -> str | None:
    """Installs the project's hooks in the clone (D198) — gitleaks among them in a project nstack
    made — with the engine's own pre-commit and the agent's environment: the person's git
    configuration, and a core.hooksPath in it, are not read. None when done; else why not."""
    done = subprocess.run([sys.executable, "-m", "pre_commit", "install"], cwd=clone, env=_environment(name),
                          capture_output=True, text=True)
    if done.returncode:
        said = (done.stdout + done.stderr).strip().splitlines()
        return " ".join(said[-2:]) if said else f"pre-commit exited with {done.returncode}"
    return None


def add(root: Path, name: str, mine: bool = False, workflows: bool = False, clone: Path | None = None,
        browser=webbrowser.open, wait: float = 900) -> int:
    """`nstack agent add`: the App, its key, its installation and its clone, in one command."""
    if os.environ.get("NSTACK_AGENT"):
        _say("FAIL [agent] this session is agent " + os.environ["NSTACK_AGENT"] + "'s: a person runs it, "
             "in their own terminal — the forge asks them to create and install the App.\n"
             f"      Action: give your person the command: nstack agent add {name}")
        return 1
    if not NAME.match(name):
        _say(f"FAIL [agent] {name!r} is not a name: lowercase letters, digits and dashes, 25 at most.\n"
             "      Action: nstack agent add scout")
        return 1
    if said := _netrc():
        _say(said)
        return 1
    answers_file = root / ".copier-answers.yml"
    answers = yaml.safe_load(answers_file.read_text(encoding="utf-8")) if answers_file.is_file() else None
    if not answers or answers.get("forge", "github") != "github" or not answers.get("github_repo"):
        _say("FAIL [agent] this is not a project on GitHub: the agent's identity is a GitHub App: .nstack/handbook/INSTALL.md says why.\n"
             "      Action: run it at the root of a project nstack init made for GitHub, or pass --root.")
        return 1
    repo = str(answers["github_repo"])
    owner = repo.split("/", 1)[0]
    folder = home() / name
    app = _load(name)
    if app and app["repo"] != repo:
        _say(f"FAIL [agent] agent {name} already works on {app['repo']} on this workstation.\n"
             f"      Action: another name for this project: nstack agent add {name}-{repo.split('/', 1)[1]}")
        return 1

    if app is None:
        status, account = _call("GET", f"/users/{urllib.parse.quote(owner)}")
        if status != 200 or not isinstance(account, dict):
            _say(f"FAIL [agent] could not read who owns {repo} (HTTP {status}).\n"
                 "      Action: check the network, then run it again.")
            return 1
        personal = mine or account.get("type") != "Organization"
        permissions = dict(PERMISSIONS, **({"workflows": "write"} if workflows else {}))
        manifest = {"name": f"{repo.split('/', 1)[1]}-{name}"[:34], "url": f"{_web()}/{repo}",
                    "public": bool(mine), "default_permissions": permissions, "default_events": [],
                    "hook_attributes": {"url": f"{_web()}/{repo}", "active": False}}
        made, why = _create(owner, personal, manifest, browser, wait)
        if made is None:
            _say(f"FAIL [agent] the App was not created: {why}. Nothing was kept.\n"
                 f"      Action: nstack agent add {name} again; an App half made at the forge is deleted there, "
                 "under Settings → Developer settings → GitHub Apps.")
            return 1
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            folder.chmod(0o700)
        key = folder / "key.pem"
        descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as written:
            written.write(str(made["pem"]))
        (folder / "gitconfig").touch()
        app = {"name": name, "repo": repo, "id": made["id"], "slug": made["slug"],
               "owner": (made.get("owner") or {}).get("login"), "public": bool(mine)}
        _save(app)
        _say(f"App {app['slug']} created; its key is in {key}" + (", readable by you alone." if os.name == "posix" else "."))
        install = f"{_web()}/apps/{app['slug']}/installations/new"
        _say(f"Opening {install} — choose Only select repositories, {repo}, then Install."
             + (" The organisation's owner approves the request: this waits for it." if mine else ""))
        browser(install)
    else:
        status, installation = _installation(app)
        if not installation:
            install = f"{_web()}/apps/{app['slug']}/installations/new"
            _say(f"App {app['slug']} exists; not installed on {repo} yet. Opening {install}.")
            browser(install)

    deadline = time.monotonic() + wait
    installation = None
    while True:
        status, installation = _installation(app)
        if installation or status not in (404, 200) or time.monotonic() >= deadline:
            break
        time.sleep(POLL)
    if not installation:
        _say(f"FAIL [agent] App {app['slug']} not installed on {repo} (HTTP {status}).\n"
             f"      Action: install it on {_web()}/apps/{app['slug']}/installations/new — or have the owner of "
             f"{owner} approve its request — then run nstack agent add {name} again: the App is kept.")
        return 1
    app["installation"] = installation
    _save(app)

    status, bot = _call("GET", f"/users/{urllib.parse.quote(app['slug'] + '[bot]', safe='')}")
    if status != 200 or not isinstance(bot, dict) or "id" not in bot:
        _say(f"FAIL [agent] could not read the App's account {app['slug']}[bot] (HTTP {status}).\n"
             f"      Action: run nstack agent add {name} again.")
        return 1
    target = (clone or Path(app.get("clone") or root.resolve().parent / f"{root.resolve().name}-{name}")).resolve()
    (folder / "gitconfig").touch()
    if refused := _clone(app, target, bot):
        _say(f"FAIL [agent] {refused}.\n      Action: name another folder: nstack agent add {name} --clone <path>")
        return 1
    app["clone"] = str(target)
    _save(app)
    hooked = (target / ".pre-commit-config.yaml").is_file()  # without it, pre-commit refuses every commit
    if hooked and (refused := _hooks(name, target)):
        _say(f"FAIL [agent] the project's hooks could not be installed in {target}: {refused}\n"
             "      Action: fix what pre-commit says in that clone, then run nstack agent add "
             f"{name} again — an agent does not commit without them.")
        return 1
    shim = _shim(name)
    # Who pushes, not what: --no-verify, or a pre-push hook judging the agent's unpushed work
    # would read as a refused identity.
    proof = _git("push", "--dry-run", "--no-verify", "-q", "origin", "HEAD:refs/heads/nstack-identity-check",
                 cwd=target, env=_environment(name))
    if proof.returncode:
        _say(f"FAIL [agent] the clone cannot push as the App: {proof.stderr.strip()}\n"
             f"      Action: check the App's installation on {repo} gives Contents: write.")
        return 1
    _say(f"Agent {name}: {app['slug']}[bot], on {repo}, in {target}.\n"
         "  - git: commits as the App, pushes with its token, minted per call; the person's git configuration "
         "and helpers are not read.\n"
         + ("  - hooks: the project's, run on every commit, installed by this engine's pre-commit.\n" if hooked else
            "  - hooks: none, the project has no .pre-commit-config.yaml.\n")
         + ("  - gh: as the App, from the agent's own folder; gh auth refused.\n" if shim else
            "  - gh: not found on this workstation; once installed, run this command again.\n")
         + "  - a push to the repository, tried without writing: accepted.\n"
         f"Start your agent there, always this way:\n  nstack agent run {name} -- <your agent's command>\n"
         "It removes your tokens and SSH agent from its environment; it is not a sandbox.")
    return 0


def _hosts() -> list[str]:
    """What the agent reaches: the forge's web and API hosts, and on github.com the host of a run's
    logs (D200) — the API sends `gh run view --log` there. A job's own log goes to Azure blob
    storage, left closed: opening it would open every Azure account to the agent."""
    hosts = {host for host in (urllib.parse.urlsplit(_web()).hostname, urllib.parse.urlsplit(_api()).hostname) if host}
    if "github.com" in hosts:
        hosts.add(CI_LOGS)
    return sorted(hosts)


def _claude_settings(name: str) -> Path:
    """Claude Code's settings of the agent's own, added to the person's (D199): their sandbox, when
    on, cuts the forge — the agent's git and gh go nowhere — and lets it write nowhere outside its
    clone, gh's folder included. This opens the agent's hosts and that folder; it never turns the
    sandbox off, nor touches a hook or a permission of theirs."""
    folder = home() / name
    settings = {"sandbox": {"network": {"allowedDomains": _hosts()}, "filesystem": {"allowWrite": [str(folder / "gh")]}},
                # git behind the sandbox's proxy fails "Proxy CONNECT aborted" without it
                "env": {"GIT_HTTP_PROXY_AUTHMETHOD": "basic"}}
    path = folder / "claude-settings.json"
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return path


def status(name: str | None) -> int:
    """`nstack agent status`: who the agent is, for the agent itself; the agents here, for a person."""
    session = os.environ.get("NSTACK_AGENT")
    name = name or session
    if not name:
        agents = sorted(path.parent.name for path in home().glob("*/app.json")) if home().is_dir() else []
        print("The agents on this workstation — this session: yours, not an agent's (NSTACK_AGENT is not set).")
        if not agents:
            print("No agent on this workstation.\n      Action: at a project's root, nstack agent add <name>")
        for one in agents:
            app = _load(one) or {}
            print(f"  {one}: {app.get('slug')}[bot] on {app.get('repo')}, clone {app.get('clone') or 'not made'}")
        if agents:
            print("Start one with: nstack agent run <name> -- <your agent's command>")
        return 0
    app = _load(name)
    if app is None:
        _say(f"FAIL [agent] no agent named {name} on this workstation.\n"
             f"      Action: a person runs nstack agent add {name} at the project's root.")
        return 1
    if not app.get("clone"):
        _say(f"FAIL [agent] agent {name}'s App {app.get('slug')} exists, its clone is not made: nstack agent add stopped before.\n"
             f"      Action: a person runs nstack agent add {name} again at the project's root: the App is kept.")
        return 1
    clone = Path(app["clone"])
    hook = clone / ".git" / "hooks" / "pre-commit"
    hooked = hook.is_file() and "generated by pre-commit" in hook.read_text(errors="replace")
    shim = home() / name / "bin" / ("gh.cmd" if os.name == "nt" else "gh")
    first = shutil.which("gh")
    this = "the agent's" if session == name else f"not the agent's: start it with nstack agent run {name} -- <command>"
    print(f"You are agent {name}: {app['slug']}[bot], on {app['repo']}, in {clone}.\n"
          f"  - this session: {this}.\n"
          "  - git: commits as the App and pushes with its token, minted per call — no login to make, none to keep.\n"
          + (f"  - gh: as the App ({shim}); gh auth is refused.\n" if first and Path(first) == shim else
             "  - gh: " + ("the App's shim is not first on PATH: gh here is not the agent." if shim.exists() else
                           "not installed for the agent: a person runs nstack agent add " + name + " again once gh is installed.") + "\n")
          + ("  - hooks: the project's, run on every commit.\n" if hooked else
             "  - hooks: none — the project has no .pre-commit-config.yaml, or they were removed: nstack agent add " + name + " puts them back.\n")
          + "  - a pull request you open is yours to deliver; another agent's or a person's approval merges it, as the project says.")
    return 0


def run(name: str, command: list[str]) -> int:
    """Starts the agent's command in its clone, with the agent's environment."""
    app = _load(name)
    if app is None or not app.get("clone"):
        _say(f"FAIL [agent] no agent named {name} on this workstation.\n"
             f"      Action: a person runs nstack agent add {name} at the project's root.")
        return 1
    if said := _netrc():
        _say(said)
        return 1
    command = command[1:] if command[:1] == ["--"] else command
    if not command:
        _say(f"FAIL [agent] no command to start.\n      Action: nstack agent run {name} -- claude")
        return 1
    _say(f"Agent {name}: {app['slug']}[bot] on {app['repo']}, in {app['clone']}.\n"
         "  - removed: your tokens, SSH agent and git configuration; git and gh act as the App.\n"
         "  - kept: your agent tool's own configuration (its sandbox, hooks and permissions), and your files: "
         "this is not a sandbox.\n"
         "  - the agent checks who it is with: nstack agent status", sys.stderr)
    if Path(command[0]).name.lower() in ("claude", "claude.exe", "claude.cmd"):
        if any(arg == "--settings" or arg.startswith("--settings=") for arg in command[1:]):
            _say(f"  - claude: your --settings is kept; if your sandbox is on, its sandbox.network.allowedDomains "
                 f"needs {', '.join(_hosts())}.", sys.stderr)
        else:
            command = [command[0], "--settings", str(_claude_settings(name)), *command[1:]]
            _say(f"  - claude: --settings {home() / name / 'claude-settings.json'}, added to yours: your sandbox, "
                 "if on, lets it reach the forge and write its gh folder, nothing more.", sys.stderr)
    try:
        return subprocess.run(command, cwd=app["clone"], env=_environment(name)).returncode
    except FileNotFoundError:
        _say(f"FAIL [agent] {command[0]} not found.\n      Action: install it, or name it by its path.")
        return 1
