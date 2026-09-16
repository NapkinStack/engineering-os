"""
Read-only diagnosis of a project: the workstation and the GitHub settings (PDR-0001).

Workflows inform; it is the GitHub settings that block, and they are not copied with the
project. CHECKLIST is printed by nstack init, checked here, and repeated word for word in
the skeleton README (a test verifies it).

GitHub is read with a token supplied by a human (GH_TOKEN, otherwise GITHUB_TOKEN):
fine-grained, limited to the repository, Administration: read permission. Without a token,
or when the API refuses a read, the setting is "not verified", never compliant. No write.

Rules:
  L1  nstack installed at the project version (_commit in .copier-answers.yml)
  L2  git and pre-commit available
  L3  pre-commit hooks installed
  L4  PRODUCT.md absent: that is NapkinStack's own development context (R6)
  L5  README personalised: the presentation sentence is written
  G1-G11  the GitHub settings of CHECKLIST; G6 is not applicable outside a public
          repository, and on a private one G1-G5 name the GitHub plan or option required

Usage :  nstack doctor [--root ROOT]
Output:  0 when everything is verified and compliant, 1 otherwise.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import yaml

from napkinstack import __version__
from napkinstack.project import ANSWERS

OK, GAP, UNKNOWN, NOT_APPLICABLE = "OK", "FAIL", "NOT VERIFIED", "NOT APPLICABLE"
API_VERSION = "2026-03-10"
PLACEHOLDER = "<One sentence: what this project does.>"
JOBS = ("Fitness functions", "Périmètre et budget de revue", "Hooks et secrets")
THIRD_PARTY_ACTIONS = ("astral-sh/setup-uv",)  # non-GitHub actions of the skeleton workflows
LABELS = ("cross-module", "hors-budget")
PUBLISHED = re.compile(r"v\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?")

RULESET = "Settings → Rules → Rulesets, main branch"
SECURITY = "Settings → Advanced Security"
ACTIONS = "Settings → Actions → General"

CHECKLIST = [  # (rule, setting, action)
    ("G1", "Pull request required: no direct push to main",
     f"{RULESET}: require a pull request before merging"),
    ("G2", "At least 1 approving review", f"{RULESET}: at least 1 approval required"),
    ("G3", "Code owner review required", f"{RULESET}: require Code Owners review"),
    ("G4", "Required checks: " + ", ".join(f"`{job}`" for job in JOBS),
     f"{RULESET}: require these status checks"),
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
    ("G11", "Labels " + " and ".join(f"`{label}`" for label in LABELS),
     "Issues → Labels: create " + " and ".join(LABELS)),
]

# Settings specific to public repositories, and settings a private one pays for
# (GitHub documentation, 2026-09-15).
PUBLIC_ONLY = {"G6": "private vulnerability reporting only exists for a public repository; "
                     "state an internal channel in SECURITY.md"}
PRIVATE_PLAN = dict.fromkeys(("G1", "G2", "G3", "G4"),
                             "Private repository: rulesets require the GitHub Team plan (organisation) "
                             "or Pro (personal account); without it, nothing blocks the merge.")
PRIVATE_PLAN["G5"] = ("Private repository: Secret Protection is a paid option; without it, only the "
                      "hooks and CI look for secrets.")


class NotVerified(Exception):
    """Setting unreadable: token, permission or network."""


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


def _rule(client: GitHub, kind: str) -> dict | None:
    return next((rule for rule in client.get("/rules/branches/main") if rule.get("type") == kind), None)


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
}


def _workstation(root: Path, answers: dict) -> list[tuple[str, str, str, str]]:
    commit = str(answers.get("_commit") or "")
    project = commit.removeprefix("v")
    install = f'uv tool install "napkinstack=={project}" --with-executables-from pre-commit'
    results = []

    if not PUBLISHED.fullmatch(commit):
        l1 = (UNKNOWN, f"Reason: the project comes from an unpublished version ({commit or 'unknown'}).")
    elif project != __version__:
        l1 = (GAP, f"nstack {__version__} installed, project on {project} (PDR-0001 R3).\nAction: {install}")
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

    product = (root / "PRODUCT.md").exists()
    results.append(("L4", "PRODUCT.md absent", GAP if product else OK,
                    "PRODUCT.md describes the development of NapkinStack itself (PDR-0001 R6).\n"
                    "Action: delete it." if product else ""))

    readme = root / "README.md"
    untouched = readme.is_file() and PLACEHOLDER in readme.read_text(encoding="utf-8", errors="replace")
    results.append(("L5", "README personalised", GAP if untouched else OK,
                    f'README.md still contains "{PLACEHOLDER}".\n'
                    "Action: write the sentence that presents the project." if untouched else ""))
    return results


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
        if client is None:
            status, detail = UNKNOWN, ""
        elif private and rule in PUBLIC_ONLY:
            status, detail = NOT_APPLICABLE, f"Reason: {PUBLIC_ONLY[rule]}."
        else:
            try:
                status, detail = (OK, "") if CHECKS[rule](client) else (GAP, f"Action: {action}")
            except NotVerified as reason:
                status, detail = UNKNOWN, f"Reason: {reason}"
            if private and status != OK and rule in PRIVATE_PLAN:
                detail += f"\n{PRIVATE_PLAN[rule]}"
        results.append((rule, setting, status, detail))
        _display(rule, setting, status, detail)

    gaps = sum(status == GAP for _, _, status, _ in results)
    unknown = sum(status == UNKNOWN for _, _, status, _ in results)
    skipped = sum(status == NOT_APPLICABLE for _, _, status, _ in results)
    suffix = f", {skipped} not applicable" if skipped else ""
    if not gaps and not unknown:
        print(f"\nnstack doctor: compliant{suffix}.")
        return 0
    print(f"\nnstack doctor: {gaps} gap(s), {unknown} not verified{suffix}.\nWorkflows inform; "
          "it is the GitHub settings that block, and they are not copied with the project.")
    return 1
