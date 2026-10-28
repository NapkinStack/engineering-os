"""
Read-only diagnosis of a project: the workstation and the GitHub settings (PDR-0001).

Workflows inform; it is the GitHub settings that block, and they are not copied with the
project. CHECKLIST is printed by nstack init, checked here, and repeated word for word in
the foundation manual, skeleton/.nstack/handbook/INSTALL.md.jinja (a test verifies it).

The registry is asked one question, without a token: which version is the latest published
(NSTACK_REGISTRY_URL, otherwise https://pypi.org). An answer changes no exit code. For a project
pinned to an unpublished commit, the framework's repository is asked another, without a token
either: whether its default branch holds that commit (GITHUB_API_URL, otherwise
https://api.github.com). No answer leaves L1 as it is.

GitHub is read with a token supplied by a human (GH_TOKEN, otherwise GITHUB_TOKEN):
fine-grained, limited to the repository, Administration: read permission. Without a token,
or when the API refuses a read, the setting is "not verified", never compliant. No write.

Rules:
  L1  nstack installed at the project version (_commit in .copier-answers.yml), both
      published: an unpublished framework is a gap, never compliance (PDR-0005) — and a pinned
      commit the framework's default branch does not hold, a pull request's head, is said with
      the gesture that moves the pin once it is merged
  L2  git and pre-commit available
  L3  pre-commit hooks installed
  L4  retired (D79): it refused a file named PRODUCT.md, which a product may write. The
      number is not reused.
  L5  retired (PDR-0010): it reported the front page's unwritten sentence from a project's
      first minute. The plan check asks for it at the discovery's go (C8). Not reused.
  L6  the ownership file starts with a default owner: the code owner review covers every path;
      where no forge reads it — Forgejo and Gitea read another syntax, `none` has no forge — it
      is said
  L7  the template source reachable by anyone: a repository, not a path on one machine
  L8  off GitHub only: `checks: forge` names a CI this version ships only on GitHub — nothing
      would run the checks; the answer is `attested`
  L9  the `forge` answer is the one the project's files were written for — never changed by
      hand, which Copier would misread; `nstack update --forge` changes it. A remote on another
      known public forge is said, never judged: a mirror is a choice
  N1  information, never a gap (D91): a published version newer than the project's, read from
      the registry — the one place a project learns of it. No other command opens a connection
  G1-G21  the GitHub settings of CHECKLIST; G6 is not applicable outside a public
          repository, G21 outside `approval: agent`, and on a private one G1-G5, G12, G13, G17,
          G18, G20 and G21 name the GitHub plan or option required

Off GitHub (the project's `forge` answer, ADR-0010) no G rule is read: the forge-neutral
PROTECTIONS are said as information — the same list as INSTALL.md's, bound by a test — and the
repository is unguarded as far as this version knows. The exit is the workstation's alone.

Usage :  nstack doctor [--root ROOT]
Output:  0 when everything is verified and compliant; 1 when a setting is missing — a gap;
         2 when nothing read is missing and something could not be read — not verified
         (D77). The two are different things to whoever reads the code: one asks for a
         change, the other for a token.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

import yaml

from napkinstack import __version__, provenance
from napkinstack.fitness import plan
from napkinstack.project import ANSWERS

OK, GAP, UNKNOWN, NOT_APPLICABLE = "OK", "FAIL", "NOT VERIFIED", "NOT APPLICABLE"
SOURCES = "SOURCES"  # a contributor's checkout holding the project's version: said, not a gap (D136)
OUT_OF_REACH = "OUT OF REACH"      # the plan forbids it: a state, not a fault (PDR-0006)
# The settings that make the forge refuse a merge. A repository is guarded when they are
# all in force; the others matter and none of them stops a merge.
BLOCKING = ("G1", "G2", "G3", "G4", "G12", "G13", "G21")
API_VERSION = "2026-03-10"
JOBS = ("Fitness functions", "PR scope and review budget", "Hooks and secrets", "Test sheet and cycle",
        "Module checks")
THIRD_PARTY_ACTIONS = ("astral-sh/setup-uv",)  # non-GitHub actions of the skeleton workflows
# The pull requests' three exceptions, then what the shipped issue templates put on an issue: a
# label that does not exist is dropped by GitHub without a word (D128).
EXCEPTIONS = ("cross-module", "over-budget", "out-of-cycle")
ISSUES = ("request", "bug", "architecture", "debt", "acceptance")
LABELS = EXCEPTIONS + ISSUES
PUBLISHED = provenance.PUBLISHED  # a published version is a vX.Y.Z tag (ADR-0002), as CI installs it
REMOTE = re.compile(r"https://|ssh://|git@[^:/]+:|gh:|gl:")  # as .nstack/install-engine.sh reads them
ON_GITHUB = re.compile(r"(?:https://github\.com/|ssh://git@github\.com/|git@github\.com:|gh:)([^/]+/[^/]+?)(?:\.git)?/?$")

RULESET = "Settings → Rules → Rulesets, main branch"
SECURITY = "Settings → Advanced Security"
ACTIONS = "Settings → Actions → General"
MERGES = "Settings → General → Pull Requests"
CODEOWNERS = Path(".github") / "CODEOWNERS"
# Off GitHub, what a forge should refuse, in its own words; read by no version yet (ADR-0010 §5).
PROTECTIONS = (
    "A pull request required: no direct push to the main branch",
    "At least 1 approval",
    "The code owners' review required",
    "The main branch neither force-pushed nor deleted",
    "Squash the only merge method",
    "Secrets refused at push",
    "Hold branches `nstack/hold/…` neither force-pushed nor deleted",
)
UNREAD_OWNERSHIP = {"forgejo": "Forgejo", "gitea": "Gitea"}  # CODEOWNERS as regular expressions

CHECKLIST = [  # (rule, setting, action)
    ("G1", "Pull request required: no direct push to main",
     f"{RULESET}: require a pull request before merging"),
    ("G2", "At least 1 approving review", f"{RULESET}: at least 1 approval required"),
    ("G3", "Code owner review required", f"{RULESET}: require Code Owners review"),
    ("G4", "Required checks: " + ", ".join(f"`{job}`" for job in JOBS),
     f"{RULESET}: require these status checks. GitHub offers a check only once it has run: "
     "open a first pull request, then select them"),
    ("G5", "Secret Protection and push protection",
     f"{SECURITY}: enable Secret Protection and push protection"),
    ("G6", "Private vulnerability reporting, public repository (the `SECURITY.md` channel)",
     f"{SECURITY}: enable private vulnerability reporting"),
    ("G7", "Allowed actions: GitHub's own, plus " + ", ".join(f"`{a}`" for a in THIRD_PARTY_ACTIONS),
     f"{ACTIONS}: allow only GitHub's actions and " + ", ".join(f"{a}@*" for a in THIRD_PARTY_ACTIONS)),
    ("G8", "SHA-pinned actions required", f"{ACTIONS}: require actions to be pinned to a SHA"),
    ("G9", "Workflow approval for every outside contributor",
     f"{ACTIONS}: require approval for all external contributors"),
    ("G10", "Workflow token read-only; Actions neither creates nor approves pull requests",
     f"{ACTIONS}: workflow permissions read-only, with no pull request creation or approval"),
    ("G11", "Labels " + ", ".join(f"`{label}`" for label in LABELS[:-1]) + f" and `{LABELS[-1]}`",
     "Issues → Labels: create " + ", ".join(LABELS[:-1]) + f" and {LABELS[-1]}"),
    ("G12", "Bypass list empty: nobody merges around the rules, administrators included",
     f"{RULESET}: remove every bypass actor"),
    ("G13", "Stale approvals dismissed when new commits are pushed",
     f"{RULESET}: dismiss stale pull request approvals when new commits are pushed"),
    # G14 to G16 shape the merge; they never refuse one, so they are not in BLOCKING. Like G11,
    # they need neither the Administration permission nor a paid plan (D61).
    ("G14", "Auto-merge available: a pull request armed for it merges itself once approved and green",
     f"{MERGES}: allow auto-merge"),
    ("G15", "Squash the only merge method: one pull request, one commit on main",
     f"{MERGES}: allow squash merging, and turn off merge commits and rebase merging"),
    ("G16", "Head branch deleted on merge: a merged branch is history, not a place to work",
     f"{MERGES}: automatically delete head branches"),
    # G17 and G18 protect the branch itself (D78): the rules above say how a change reaches
    # main, and said nothing of main being deleted or rewritten under them.
    ("G17", "Main branch cannot be deleted", f"{RULESET}: restrict deletions"),
    ("G18", "Main branch history cannot be rewritten: no force push", f"{RULESET}: block force pushes"),
    # G19: every workflow and ruleset here watches `main`. A repository whose default branch is
    # another one triggers none of them, and its record of commits on main never runs.
    ("G19", "Default branch `main`: the branch every workflow and ruleset here watches",
     "Settings → General → Default branch: rename it main"),
    # G20: a hold of a deliverable is refused twice by the remote, unless forced (ADR-0007): its
    # branches are rewritten or deleted by nobody.
    ("G20", "Hold branches `nstack/hold/**/*` cannot be force-pushed nor deleted",
     "Settings → Rules → Rulesets, a ruleset on the branches nstack/hold/**/* — not nstack/hold/**, "
     "which stops at a slash — with nobody on its bypass list: block force pushes and restrict deletions"),
    # G21: where another contributor's agent approves (PDR-0021), the one who pushed last never
    # approves what they pushed — the author's own fix included.
    ("G21", "The most recent push approved by someone other than its pusher (approval: agent)",
     f"{RULESET}: require approval of the most recent reviewable push"),
]

# Asked of a project only on one of its answers: elsewhere not applicable, and said why.
ANSWERED = {"G21": ("approval", "agent", "the project's approval is human: a code owner approves every change")}


def unasked(rule: str, answers: dict) -> str | None:
    """Why a rule is not asked of this project, or None when it is."""
    if rule not in ANSWERED:
        return None
    key, value, reason = ANSWERED[rule]
    return None if answers.get(key) == value else reason


# Settings specific to public repositories, and settings a private one pays for
# (GitHub documentation, 2026-09-15).
PUBLIC_ONLY = {"G6": "private vulnerability reporting only exists for a public repository; "
                     "state an internal channel in SECURITY.md"}
PRIVATE_PLAN = dict.fromkeys(("G1", "G2", "G3", "G4", "G12", "G13", "G17", "G18", "G20", "G21"),
                             "Private repository: rulesets require the GitHub Team plan (organisation) "
                             "or Pro (personal account); without it, nothing blocks the merge.")
PRIVATE_PLAN["G5"] = ("Private repository: Secret Protection is a paid option; without it, only the "
                      "hooks and CI look for secrets.")


class NotVerified(Exception):
    """Setting unreadable: token, permission or network."""


class Gap(Exception):
    """Setting missing, with an action more precise than the checklist's."""


class GitHub:
    """Reads of the GitHub REST API, cached; never a write."""

    def __init__(self, repo: str, token: str, api: str) -> None:
        self.repo, self.token, self.api = repo, token, api.rstrip("/")
        self.cache: dict[str, tuple[int, object]] = {}

    def get(self, path: str, missing: bool = False):
        """JSON of /repos/<repo><path>; None when `missing` and 404; NotVerified otherwise."""
        if path not in self.cache:
            request = urllib.request.Request(f"{self.api}/repos/{self.repo}{path}", headers={
                "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION, "User-Agent": f"nstack/{__version__}"})
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    self.cache[path] = (response.status, json.load(response))
            except urllib.error.HTTPError as error:
                self.cache[path] = (error.code, None)
            except (OSError, ValueError):
                self.cache[path] = (0, None)
        status, data = self.cache[path]
        if status == 200:
            return data
        if status == 404 and missing:
            return None
        if status == 0:
            raise NotVerified(f"GitHub API unreachable ({self.api})")
        if status == 401:
            raise NotVerified("token refused (HTTP 401)")
        raise NotVerified(f"read refused (HTTP {status}): repository out of reach, or the token lacks "
                          "the Administration: read permission")


def _rules(client: GitHub) -> list[dict]:
    """The rules that apply to the default branch, where the checklist's ruleset applies
    (`~DEFAULT_BRANCH`): on a repository whose default branch is not yet main (G19), the rules of
    a branch named main are none (D152). An unread default branch is read as main."""
    try:
        default = str(client.get("").get("default_branch") or "main")
    except NotVerified:
        default = "main"
    return client.get(f"/rules/branches/{urllib.parse.quote(default, safe='')}")


def _rule(client: GitHub, kind: str) -> dict | None:
    return next((rule for rule in _rules(client) if rule.get("type") == kind), None)


# A name at a hold's depth, nstack/hold/<cycle>/<id>: GitHub answers for a branch that need not
# exist, and a ruleset's `**` stops at a slash (fnmatch, FNM_PATHNAME) — a probe one level up
# would read a pattern that covers no hold.
HOLD_PROBE = "nstack/hold/probe/probe"


def _holds_kept(client: GitHub) -> bool:
    """G20: the rules applying to a hold's branch refuse a forced push and a deletion, from
    rulesets nobody may bypass."""
    found = [rule for rule in client.get(f"/rules/branches/{HOLD_PROBE}")
             if rule.get("type") in ("non_fast_forward", "deletion")]
    if {rule.get("type") for rule in found} != {"non_fast_forward", "deletion"}:
        return False
    for ruleset in sorted({rule["ruleset_id"] for rule in found if rule.get("ruleset_id")}):
        actors = client.get(f"/rulesets/{ruleset}?includes_parents=true").get("bypass_actors")
        if actors is None:
            raise NotVerified("bypass list not visible: the token lacks the Administration: read permission")
        if actors:
            return False
    return True


def _parameters(client: GitHub, kind: str) -> dict:
    return (_rule(client, kind) or {}).get("parameters") or {}


def _security(client: GitHub) -> bool:
    analysis = client.get("").get("security_and_analysis")
    if analysis is None:
        raise NotVerified("security settings not visible: the token lacks the Administration: read "
                          "permission")
    return all((analysis.get(key) or {}).get("status") == "enabled"
               for key in ("secret_scanning", "secret_scanning_push_protection"))


def _allowed_actions(client: GitHub) -> bool:
    if client.get("/actions/permissions").get("allowed_actions") != "selected":
        return False
    selection = client.get("/actions/permissions/selected-actions")
    patterns = selection.get("patterns_allowed") or []
    return bool(selection.get("github_owned_allowed")) and all(
        any(fnmatch.fnmatch(f"{action}@0", pattern) for pattern in patterns)
        for action in THIRD_PARTY_ACTIONS)


def _workflows(client: GitHub) -> bool:
    permissions = client.get("/actions/permissions/workflow")
    return (permissions.get("default_workflow_permissions") == "read"
            and permissions.get("can_approve_pull_request_reviews") is False)


def _no_bypass(client: GitHub) -> bool:
    """G12: every ruleset applying to main has an empty bypass list (ADR-0004)."""
    rulesets = {rule["ruleset_id"] for rule in _rules(client) if rule.get("ruleset_id")}
    if not rulesets:
        raise Gap(f"no ruleset applies to main, so there is no bypass list to empty. {RULESET}: "
                  "create the ruleset first (G1)")
    for ruleset in sorted(rulesets):
        actors = client.get(f"/rulesets/{ruleset}?includes_parents=true").get("bypass_actors")
        if actors is None:
            raise NotVerified("bypass list not visible: the token lacks the Administration: read permission")
        if actors:
            return False
    return True


MERGE_SETTINGS = ("allow_auto_merge", "allow_squash_merge", "allow_merge_commit",
                  "allow_rebase_merge", "delete_branch_on_merge")


def _merges(client: GitHub, *keys: str) -> dict:
    """G14 to G16 read the repository object, which carries these fields in every answer and
    asks for no Administration permission (D61). Absent means a degraded read, never a setting
    that is off: the difference between "not verified" and "missing" is the whole point of this
    command (PDR-0005). Each rule names the fields it reads, and one of them absent is enough."""
    repo = client.get("")
    absent = [key for key in keys or MERGE_SETTINGS if key not in repo]
    if absent:
        raise NotVerified(f"{', '.join(absent)} not visible in the repository's own object")
    return repo


def _squash_only(client: GitHub) -> bool:
    """G15: squash alone, so that a workstream reaches main as one commit. A merge commit puts
    the branch's commits on main beside a merge of its own; a rebase puts them there without
    one. Measured on two repositories before the rule existed: 22 branches for 23 merged pull
    requests, and four commits on main for two workstreams (D61)."""
    repo = _merges(client, "allow_squash_merge", "allow_merge_commit", "allow_rebase_merge")
    return (repo.get("allow_squash_merge") is True
            and repo.get("allow_merge_commit") is False
            and repo.get("allow_rebase_merge") is False)


CHECKS: dict[str, Callable[[GitHub], bool]] = {
    "G1": lambda c: _rule(c, "pull_request") is not None,
    "G2": lambda c: _parameters(c, "pull_request").get("required_approving_review_count", 0) >= 1,
    "G3": lambda c: _parameters(c, "pull_request").get("require_code_owner_review") is True,
    "G4": lambda c: set(JOBS) <= {check.get("context") for check in _parameters(
        c, "required_status_checks").get("required_status_checks", [])},
    "G5": _security,
    "G6": lambda c: c.get("/private-vulnerability-reporting").get("enabled") is True,
    "G7": _allowed_actions,
    "G8": lambda c: c.get("/actions/permissions").get("sha_pinning_required") is True,
    "G9": lambda c: c.get("/actions/permissions/fork-pr-contributor-approval").get(
        "approval_policy") == "all_external_contributors",
    "G10": _workflows,
    "G11": lambda c: all(c.get(f"/labels/{label}", missing=True) is not None for label in LABELS),
    "G12": _no_bypass,
    "G13": lambda c: _parameters(c, "pull_request").get("dismiss_stale_reviews_on_push") is True,
    "G14": lambda c: _merges(c, "allow_auto_merge").get("allow_auto_merge") is True,
    "G15": _squash_only,
    "G16": lambda c: _merges(c, "delete_branch_on_merge").get("delete_branch_on_merge") is True,
    "G17": lambda c: _rule(c, "deletion") is not None,
    "G18": lambda c: _rule(c, "non_fast_forward") is not None,
    "G19": lambda c: _merges(c, "default_branch").get("default_branch") == "main",
    "G20": _holds_kept,
    "G21": lambda c: _parameters(c, "pull_request").get("require_last_push_approval") is True,
}


def _default_owner(root: Path) -> tuple[str, str]:
    """L6: `*` first, so that the code owner review covers every path (ADR-0004) — or, where
    another contributor's agent approves (PDR-0021), a human named for what one must approve and
    no default owner, so that the rest is the agents'."""
    from napkinstack.project import answer, forge, ownership

    path = ownership(root)  # where the project's forge reads it (ADR-0010)
    shown = path.relative_to(root).as_posix()
    agent = answer(root, "approval") == "agent"
    if not path.is_file():
        return GAP, f"{shown} missing.\nAction: create it" + ("." if agent else ", starting with `*  @<owner>`.")
    rules = [line.split() for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if agent:
        return _kept_for_a_human(root, shown, path.read_text(encoding="utf-8"))
    if rules and rules[0][0] == "*" and len(rules[0]) > 1:
        name = forge(root)
        if name in UNREAD_OWNERSHIP:
            return OK, (f"Written, not read by {UNREAD_OWNERSHIP[name]}: its code owners take another "
                        "syntax. The owners it names are for people to read.")
        if name == "none":
            return OK, "No forge reads it: the owners it names are for people to read."
        return OK, ""
    return GAP, (f"The first rule of {shown} is not a default owner.\nAction: make `*  @<owner>` "
                 "its first rule: the code owner review then covers every path (.nstack/handbook/07-governance.md §7).")


def _kept_for_a_human(root: Path, shown: str, text: str) -> tuple[str, str]:
    """L6 on `approval: agent`: no default owner, and every path a human must approve ends on a
    rule with an owner (`owners.py`; in CI, rule M13)."""
    from napkinstack import owners
    from napkinstack.project import forge

    default, missing = owners.unowned(root, text)
    if default:
        return GAP, (f"{shown} names a default owner: on approval agent, it leaves no change another "
                     "contributor's agent may approve.\nAction: remove the `*` rule; name a human for what "
                     "one must approve (.nstack/handbook/07-governance.md §7).")
    if missing:
        return GAP, (f"{shown} names no owner for " + ", ".join(f"`{path}`" for path in missing)
                     + ": on approval agent, a human approves them.\nAction: end each on a line "
                     "`/<path>  @<owner>`, the owner a team of people (.nstack/handbook/07-governance.md §7).")
    name = forge(root)
    if name in UNREAD_OWNERSHIP or name == "none":
        return OK, ("No forge reads it here: who approves what is for people to read, and nothing refuses "
                    "an agent's approval of the rest.")
    return OK, ""


def _forge(path: str) -> dict | None:
    """JSON of a public repository's page on the forge, read without a token; None when it does
    not answer."""
    api = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    request = urllib.request.Request(f"{api}{path}", headers={
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": f"nstack/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.load(response)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _left_behind(answers: dict) -> str | None:
    """The framework's default branch, when it does not hold the pinned commit; None when it
    does, or when the forge could not say. A fix may be pinned while it is reviewed; its squash
    then gives the default branch another commit, and leaves this one on no branch."""
    commit = str(answers.get("_commit") or "")
    repository = ON_GITHUB.match(str(answers.get("_src_path") or ""))
    if "-g" not in commit or not repository:
        return None
    sha, repo = commit.rsplit("-g", 1)[1], repository.group(1)
    branch = (_forge(f"/repos/{repo}") or {}).get("default_branch")
    status = (_forge(f"/repos/{repo}/compare/{branch}...{sha}") or {}).get("status") if branch else None
    return branch if status in ("ahead", "diverged") else None


def _workstation(root: Path, answers: dict) -> list[tuple[str, str, str, str]]:
    commit = str(answers.get("_commit") or "")
    project = commit.removeprefix("v")
    install = (f'uv tool install "napkinstack=={project}" --refresh-package napkinstack --with-executables-from pre-commit'
               if PUBLISHED.fullmatch(commit) else "bash .nstack/install-engine.sh")
    results = []

    _, origin = provenance.engine()
    if not PUBLISHED.fullmatch(commit):
        branch = _left_behind(answers)
        if branch:
            l1 = (GAP, f"The project is pinned to an unpublished framework ({commit}), a commit the "
                       f"framework's {branch} does not hold: a pull request's head, which its squash leaves "
                       f"on no branch.\nAction: once it is merged, nstack update --ref <the commit {branch} "
                       "received for that change>, or --ref vX.Y.Z, a release that carries it.")
        else:
            l1 = (GAP, f"The project is pinned to an unpublished framework ({commit or 'unknown'}): its "
                       "verdicts come from rules nobody has published.\nAction: once the change it "
                       "waits for is released, nstack update --ref vX.Y.Z.")
    elif origin is not None:
        folder = provenance.checkout()
        if folder is not None and provenance.holds(folder, commit):
            # A contributor running the framework's latest sources: ahead of the project, never behind.
            l1 = (SOURCES, f"nstack from a contributor's checkout ({origin}), which holds the project's "
                           f"{commit}: this workstation judges with rules ahead of CI's, which installs "
                           f"{commit}.\nTo judge as CI does: {install}")
        elif folder is not None:
            l1 = (GAP, f"The nstack running is a checkout ({origin}) that does not hold the project's "
                       f"{commit}: it is behind it, on another branch, or without its tags.\nAction: git "
                       f"-C {folder} pull --tags on the framework's main, or {install}")
        else:
            l1 = (GAP, f"The nstack running is unpublished ({origin}).\nAction: {install}")
    elif project != __version__:
        l1 = (GAP, f"nstack {__version__} installed, project on {project}: the engine and the project "
                   f"move together.\nAction: {install}")
    else:
        l1 = (OK, "")
    results.append(("L1", "nstack at the project version", *l1))

    missing = [tool for tool in ("git", "pre-commit") if shutil.which(tool) is None]
    results.append(("L2", "git and pre-commit available", GAP if missing else OK,
                    f"Missing: {', '.join(missing)}.\nAction: install git; pre-commit comes with "
                    f"{install}" if missing else ""))

    if "git" in missing:
        l3 = (UNKNOWN, "Reason: git missing.")
    else:
        hook = subprocess.run(["git", "rev-parse", "--git-path", "hooks/pre-commit"], cwd=root,
                              capture_output=True, text=True)
        path = root / hook.stdout.strip()
        installed = (hook.returncode == 0 and path.is_file()
                     and "generated by pre-commit" in path.read_text(errors="replace"))
        l3 = (OK, "") if installed else (GAP, "Action: pre-commit install")
    results.append(("L3", "pre-commit hooks installed", *l3))

    results.append(("L6", "CODEOWNERS names a human where one approves (approval: agent)"
                     if answers.get("approval") == "agent" else "CODEOWNERS starts with a default owner",
                     *_default_owner(root)))

    source = str(answers.get("_src_path") or "")
    local = not REMOTE.match(source)
    results.append(("L7", "Template source reachable by anyone", GAP if local else OK,
                    f"The project was generated from '{source}', a path on one machine: nobody else can "
                    "update it.\nAction: nstack update, from the published source." if local else ""))

    from napkinstack.project import forge, remote_forge, written_for

    name = forge(root)
    written, remote = written_for(root), remote_forge(root)
    if written is not None:
        l9 = (GAP, f"`forge: {name}`, and the project's files are written for {written}: the answer was changed "
                   f"by hand.\nAction: put back `forge: {written}` in {ANSWERS}, commit it, then nstack update "
                   f"--forge {name}, which moves the files and carries the project's lines.")
    elif remote is not None:
        flag = "--github-repo <owner/name>" if remote[1] == "github" else "--repository <group/name>"
        l9 = (OK, f"Said: the remote is on {remote[0]}, and the answer says {name}. A mirror stays as it is; "
                  f"a project that lives there: nstack update --forge {remote[1]} {flag}.")
    else:
        l9 = (OK, "")
    if name != "github" and written is None:  # a hand edit is L9's: the files are still the old forge's
        forced = answers.get("checks") == "forge"
        results.append(("L8", "Checks run where the project says", GAP if forced else OK,
                        f"`checks: forge`, and this version ships a CI only on GitHub: nothing runs the "
                        f"checks of a {name} project.\nAction: answer `checks: attested` in {ANSWERS}, in a "
                        "pull request; each change then carries its record, made by nstack attest."
                        if forced else ""))
    results.append(("L9", "The forge answered is the one the files are written for", *l9))
    return results


def _latest() -> str | None:
    """The latest version the registry publishes, or None when it did not answer."""
    registry = (os.environ.get("NSTACK_REGISTRY_URL") or "https://pypi.org").rstrip("/")
    request = urllib.request.Request(f"{registry}/pypi/napkinstack/json",
                                     headers={"Accept": "application/json", "User-Agent": f"nstack/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            version = str(json.load(response)["info"]["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return version if PUBLISHED.fullmatch(f"v{version}") else None


def _number(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _newer(answers: dict) -> None:
    """Says whether a version newer than the project's is published (N1). Information: taking
    a version is the team's decision, at a cycle's boundary, and nothing here counts it as a gap."""
    commit = str(answers.get("_commit") or "")
    if not PUBLISHED.fullmatch(commit):
        return  # L1 already says the project is on no published version
    print("\nNapkinStack")
    latest = _latest()
    if latest is None:
        print("  NOT READ       the registry did not answer: whether a newer version is published is not known")
        return
    if _number(latest) <= _number(commit.removeprefix("v")):
        print(f"  LATEST         the project is on {commit}, the latest published version")
        return
    from napkinstack.project import release_notes

    print(f"  NEWER VERSION  v{latest} is published; the project is on {commit} — information, not a gap\n"
          f"                 What it changes: {release_notes(str(answers.get('_src_path') or ''), commit, f'v{latest}')}\n"
          f"                 To take it, at a cycle's boundary: uv tool install \"napkinstack=={latest}\" "
          "--refresh-package napkinstack --with-executables-from pre-commit, then nstack update")


def _private(client: GitHub) -> bool:
    """Repository not public (private or internal); visibility unreadable: treated as public."""
    try:
        return (client.get("").get("visibility") or "public") != "public"
    except NotVerified:
        return False


def _display(rule: str, setting: str, status: str, detail: str) -> None:
    print(f"  {status:<14} [{rule}] {setting}")
    for line in detail.splitlines():
        print(f"                 {line}")


def _state(results: list[tuple[str, str, str, str]]) -> None:
    """Guarded when every setting that refuses a merge is in force; unguarded otherwise, with
    what a plan forbids kept apart from what is not yet done; never guarded on what could not
    be read (PDR-0006)."""
    status_of = {rule: status for rule, _, status, _ in results}
    blocking = [status_of.get(rule, UNKNOWN) for rule in BLOCKING]
    blocking = [status for status in blocking if status != NOT_APPLICABLE]  # G21 off `approval: agent`
    if any(status == UNKNOWN for status in blocking):
        print("\nThis repository: not verified — what cannot be read is never reported as guarded.")
        return
    if all(status == OK for status in blocking):
        print("\nThis repository: guarded — the forge refuses what the checklist asks it to refuse.")
        return
    groups = {name: [rule for rule, _, status, _ in results
                     if status == name and rule.startswith("G")]
              for name in (OK, GAP, OUT_OF_REACH)}
    print("\nThis repository: unguarded — nothing here refuses a merge.")
    for label, name in (("In force", OK), ("Not yet in place", GAP),
                        ("Out of reach on this plan", OUT_OF_REACH)):
        if groups[name]:
            print(f"  {label:<26}: {', '.join(groups[name])}")
    if groups[OUT_OF_REACH]:
        print("  What it would take        : make the repository public, where these work at no "
              "cost on any plan;\n                              or move the private repository to a "
              "plan that enforces rules;\n                              or keep working here, "
              "knowing that nothing refuses.")
    if groups[GAP]:
        print("  Each setting not yet in place carries its action above.")


def _off_github(name: str, answers: dict, results: list[tuple[str, str, str, str]]) -> int:
    """No G rule off GitHub (ADR-0010 §5): what the forge should refuse said as information, the
    repository unguarded as far as this version knows, and the exit the workstation's alone."""
    if name == "none":
        print("\nForge: none — no forge, so nothing refuses a change. Hosted on one, it should refuse:")
    else:
        print(f"\nForge: {name} — {answers.get('repository') or 'repository not named'}\n"
              "  This version reads no setting of this forge. Set there, as INSTALL.md lists them:")
    for protection in PROTECTIONS:
        print(f"    - {protection}")
    print("  The record of commits on the main branch (nstack landed) does not run: its workflow is "
          "written only on GitHub.")
    print("\nThis repository: unguarded — " + ("no forge, nothing refuses a change." if name == "none"
                                                else "this version does not read the forge's protections."))
    gaps = sum(status == GAP for _, _, status, _ in results)
    unknown = sum(status == UNKNOWN for _, _, status, _ in results)
    if not gaps and not unknown:
        print(f"\nnstack doctor: the workstation compliant; the forge's settings not read (forge {name}).")
        return 0
    print(f"\nnstack doctor: {gaps} gap(s), {unknown} not verified, on the workstation; the forge's "
          f"settings not read (forge {name}).")
    return 1 if gaps else 2


def run(root: Path) -> int:
    if not (root / ANSWERS).is_file():
        print(f"FAIL [doctor] {ANSWERS} not found in {root}: this folder is not a project "
              "created by nstack init.\n      Action: run the command at the project root, "
              "or pass --root.")
        return 1
    answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}

    results = _workstation(root, answers)
    print("Workstation")
    for result in results:
        _display(*result)

    _newer(answers)

    if plan.stage(root) == plan.UNFRAMED:
        # Said here and nowhere else, once: every other run names the stage in one line and
        # leaves it there. A stage is not a gap, and nothing below counts it as one.
        print("\nProject\n  UNFRAMED       no accepted charter — a stage, not a gap\n"
              "                 Framing buys an appetite, an end date, a circuit breaker and a decider.\n"
              "                 It is worth its price when there is something to bound: several people,\n"
              "                 a deadline, a decider who is not the one typing.\n"
              "                 To start: follow .nstack/playbooks/framing.md with your agent.")

    from napkinstack.project import forge

    name = forge(root)
    if name != "github":
        return _off_github(name, answers, results)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    print(f"\nGitHub: {answers.get('github_repo')}")
    if token:
        client = GitHub(str(answers.get("github_repo")), token,
                        os.environ.get("GITHUB_API_URL") or "https://api.github.com")
    else:
        client = None
        print("  No token (GH_TOKEN or GITHUB_TOKEN): no setting is read.\n"
              "  Action: supply a fine-grained token limited to the repository, "
              "Administration: read permission, then run again.")
    private = client is not None and _private(client)
    for rule, setting, action in CHECKLIST:
        if unasked(rule, answers):
            status, detail = NOT_APPLICABLE, f"Reason: {unasked(rule, answers)}."
        elif client is None:
            status, detail = UNKNOWN, ""
        elif private and rule in PUBLIC_ONLY:
            status, detail = NOT_APPLICABLE, f"Reason: {PUBLIC_ONLY[rule]}."
        else:
            try:
                status, detail = (OK, "") if CHECKS[rule](client) else (GAP, f"Action: {action}")
            except NotVerified as reason:
                status, detail = UNKNOWN, f"Reason: {reason}"
            except Gap as action:
                status, detail = GAP, f"Action: {action}"
            if private and status != OK and rule in PRIVATE_PLAN:
                status, detail = OUT_OF_REACH, f"Reason: {PRIVATE_PLAN[rule]}"
        results.append((rule, setting, status, detail))
        _display(rule, setting, status, detail)

    gaps = sum(status == GAP for _, _, status, _ in results)
    unknown = sum(status == UNKNOWN for _, _, status, _ in results)
    skipped = sum(status == NOT_APPLICABLE for _, _, status, _ in results)
    out_of_reach = sum(status == OUT_OF_REACH for _, _, status, _ in results)
    _state(results)
    suffix = f", {skipped} not applicable" if skipped else ""
    if not gaps and not unknown:
        reach = f"; {out_of_reach} setting(s) out of reach on this plan" if out_of_reach else ""
        print(f"\nnstack doctor: compliant{suffix}{reach}.")
        return 0
    print(f"\nnstack doctor: {gaps} gap(s), {unknown} not verified{suffix}.\nWorkflows inform; "
          "it is the GitHub settings that block, and they are not copied with the project.")
    if gaps:
        print("What would close the gaps, as calls to run yourself: nstack settings")
    return 1 if gaps else 2
