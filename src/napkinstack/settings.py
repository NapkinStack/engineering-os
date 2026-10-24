"""
The forge's settings as one gesture (PDR-0008): the plan, printed — or applied by the person.

`nstack doctor` says what is missing. This command says how to close the distance: it reads
the repository's settings with the same checks as doctor, and prints the smallest set of calls
that brings it to the checklist, in a form a person runs with their own credential. By default
it writes nothing, and sends nothing but reads.

With `--apply`, the person who holds administration has it make those calls under their own
credential, then reads the result back with `nstack doctor`. Never delegated: the forge allows
no credential that administers and cannot commit (D150), so the mode refuses an App's
installation token — an agent's identity, which holds no administration (ADR-0004) — and a run
in CI. It stores nothing, prints each change and the forge's own error for each refusal, and
ends by saying to revoke the credential.

What it never plans, so never prints nor applies:
  - a call that rewrites or deletes a ruleset: the missing rules go in a ruleset of their own,
    and rulesets layer — the strictest one wins, so adding never lowers;
  - a call that lowers a setting already stricter than the checklist;
  - a bypass actor. Emptying an existing bypass list (G12) is named as a step by hand: it
    edits a ruleset this command did not create.

What the repository's plan cannot enforce is not planned and not reported as a fault: it is
named, with its cost, in doctor's own words.

Usage :  nstack settings [--root ROOT] [--apply]
Output:  0 with the plan printed, or nothing to change; 1 when the repository cannot be read
         with the token given. With --apply: 1 when a call was refused or the mode is; else
         nstack doctor's own exit code.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from napkinstack import doctor, project
from napkinstack.project import ANSWERS

RULESET_NAME = "nstack-checklist"
HOLDS_RULESET = "nstack-holds"  # the holds of deliverables: never forced, never deleted (G20)
IN_RULESET = ("G1", "G2", "G3", "G4", "G13", "G17", "G18")
PULL_REQUEST = ("G1", "G2", "G3", "G13")
LABEL_COLOURS = {"cross-module": "d93f0b", "over-budget": "fbca04", "out-of-cycle": "5319e7",
                 "request": "0e8a16", "bug": "d73a4a", "architecture": "1d76db", "debt": "c5def5",
                 "acceptance": "bfdadc"}
# An issue label means what its template says: the same words, the template being the source.
LABEL_MEANING = {"cross-module": "A pull request touching several modules, with its justification",
                 "over-budget": "A pull request beyond the review budget, with its justification",
                 "out-of-cycle": "Work outside the current cycle, with its justification",
                 "request": "Something asked for that no cycle plans yet",
                 "bug": "Incorrect behaviour in production or in test",
                 "architecture": "Boundary, contract, coupling, structuring decision",
                 "debt": "Identified debt, with its cost and its trigger",
                 "acceptance": "A deliverable tried by a person — what to run, what was seen"}
Call = tuple[str, str, str, dict | None]  # (rules closed, method, path under the repository, body)


def ruleset(missing: set[str]) -> dict:
    """One ruleset holding the rules that are missing, on the default branch, with nobody on
    its bypass list. Never the ones in place: a rule is not written twice."""
    rules: list[dict] = []
    if "G17" in missing:
        rules.append({"type": "deletion"})
    if "G18" in missing:
        rules.append({"type": "non_fast_forward"})
    if missing & set(PULL_REQUEST):
        rules.append({"type": "pull_request", "parameters": {
            "required_approving_review_count": 1, "require_code_owner_review": True,
            "dismiss_stale_reviews_on_push": True, "require_last_push_approval": False,
            "required_review_thread_resolution": False}})
    if "G4" in missing:
        rules.append({"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": job} for job in doctor.JOBS],
            "strict_required_status_checks_policy": False}})
    return {"name": RULESET_NAME, "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [], "rules": rules}


def _actions(client: doctor.GitHub | None, missing: set[str]) -> tuple[list[Call], list[str]]:
    """G7 and G8 share one setting object. A repository that allows only its own actions is
    stricter than the checklist and is left alone; the patterns already allowed are kept."""
    calls: list[Call] = []
    notes: list[str] = []
    current: dict = {}
    selection: dict = {}
    if client is not None:
        try:
            current = client.get("/actions/permissions") or {}
            if current.get("allowed_actions") == "selected":
                selection = client.get("/actions/permissions/selected-actions") or {}
        except doctor.NotVerified:
            current, selection = {}, {}
    stricter = current.get("allowed_actions") == "local_only"
    if stricter and "G7" in missing:
        notes.append("G7  left as it is: this repository allows only its own actions, which is stricter than "
                     "the checklist. The skeleton's workflows use " + ", ".join(doctor.THIRD_PARTY_ACTIONS)
                     + ": they will not run until it is allowed.")
    allowed = current.get("allowed_actions") if stricter else "selected"
    if missing & {"G7", "G8"} and not (stricter and missing == {"G7"}):
        closed = ", ".join(sorted(missing & ({"G8"} if stricter else {"G7", "G8"})))
        calls.append((closed, "PUT", "/actions/permissions",
                      {"enabled": True, "allowed_actions": allowed, "sha_pinning_required": True}))
    if "G7" in missing and not stricter:
        wanted = [f"{action}@*" for action in doctor.THIRD_PARTY_ACTIONS]
        kept = [pattern for pattern in selection.get("patterns_allowed") or [] if pattern not in wanted]
        calls.append(("G7", "PUT", "/actions/permissions/selected-actions",
                      {"github_owned_allowed": True, "verified_allowed": bool(selection.get("verified_allowed")),
                       "patterns_allowed": kept + wanted}))
    return calls, notes


def plan(client: doctor.GitHub | None, missing: set[str]) -> tuple[list[Call], list[str]]:
    """The calls that close `missing`, and the steps that stay by hand."""
    calls: list[Call] = []
    notes: list[str] = []
    in_ruleset = missing & set(IN_RULESET)
    if in_ruleset:
        body = {**ruleset(in_ruleset), "name": _free(client, RULESET_NAME)}
        calls.append((", ".join(sorted(in_ruleset, key=_order)), "POST", "/rulesets", body))
        if "G4" in in_ruleset:
            notes.append("G4  the forge may refuse a check it has never seen run. If it does, open a first "
                         "pull request, let the checks run, then run this call again.")
    if "G12" in missing:
        notes.append("G12 by hand — " + doctor.RULESET + ": remove every bypass actor. This command never "
                     "rewrites a ruleset it did not create.")
    if "G20" in missing:
        calls.append(("G20", "POST", "/rulesets", {
            "name": _free(client, HOLDS_RULESET), "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/nstack/hold/**/*"], "exclude": []}},
            "bypass_actors": [], "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}))
    if "G5" in missing:
        calls.append(("G5", "PATCH", "", {"security_and_analysis": {
            "secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}))
    if "G6" in missing:
        calls.append(("G6", "PUT", "/private-vulnerability-reporting", None))
    more, said = _actions(client, missing)
    calls += more
    notes += said
    if "G9" in missing:
        calls.append(("G9", "PUT", "/actions/permissions/fork-pr-contributor-approval",
                      {"approval_policy": "all_external_contributors"}))
    if "G10" in missing:
        calls.append(("G10", "PUT", "/actions/permissions/workflow",
                      {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False}))
    if "G11" in missing:
        for label in doctor.LABELS:
            if client is None or _absent(client, label):
                calls.append(("G11", "POST", "/labels", {"name": label, "color": LABEL_COLOURS[label],
                                                         "description": LABEL_MEANING[label]}))
    merges: dict = {}
    if "G14" in missing:
        merges["allow_auto_merge"] = True
    if "G15" in missing:
        merges.update(allow_squash_merge=True, allow_merge_commit=False, allow_rebase_merge=False)
    if "G16" in missing:
        merges["delete_branch_on_merge"] = True
    if merges:
        calls.append((", ".join(rule for rule in ("G14", "G15", "G16") if rule in missing), "PATCH", "", merges))
    if "G19" in missing:
        current = "<the default branch>"
        if client is not None:
            try:
                current = str(client.get("").get("default_branch") or current)
            except doctor.NotVerified:
                pass
        calls.append(("G19", "POST", f"/branches/{current}/rename", {"new_name": "main"}))
    return calls, notes


def _order(rule: str) -> int:
    return int(rule[1:])


def _free(client: doctor.GitHub | None, name: str) -> str:
    """A ruleset's name the repository does not use yet: the forge refuses a second ruleset of the
    same name, and a ruleset of an earlier run, or one a person made, is never rewritten."""
    if client is None:
        return name
    try:
        taken = {str(found.get("name")) for found in client.get("/rulesets", missing=True) or []}
    except doctor.NotVerified:
        return name
    return next(f"{name}-{n}" if n > 1 else name for n in range(1, len(taken) + 2)
                if (f"{name}-{n}" if n > 1 else name) not in taken)


def _absent(client: doctor.GitHub, label: str) -> bool:
    try:
        return client.get(f"/labels/{label}", missing=True) is None
    except doctor.NotVerified:
        return True


def render(repo: str, call: Call) -> str:
    """One call as a command the person runs under their own credential: the forge's own
    command line, the body on standard input so that nothing has to be quoted."""
    closed, method, path, body = call
    head = f"# {closed}\ngh api --method {method} repos/{repo}{path}"
    if body is None:
        return head
    return f"{head} --input - <<'JSON'\n{json.dumps(body, indent=2)}\nJSON"


class Forge(doctor.GitHub):
    """doctor's reads, and the writes of the apply mode — the only place nstack writes to the
    forge's settings, under the person's own credential (PDR-0008, D150)."""

    def send(self, method: str, path: str, body: dict | None) -> tuple[bool, str]:
        """(done, the forge's answer): its HTTP status, and its own message when it refused."""
        request = urllib.request.Request(
            f"{self.api}/repos/{self.repo}{path}", method=method,
            data=None if body is None else json.dumps(body).encode("utf-8"), headers={
                "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": doctor.API_VERSION, "User-Agent": "nstack settings",
                **({} if body is None else {"Content-Type": "application/json"})})
        self.cache.clear()  # what was read before this write may no longer be true
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return True, f"HTTP {response.status}"
        except urllib.error.HTTPError as error:
            try:
                said = json.load(error).get("message") or ""
            except (ValueError, AttributeError):
                said = ""
            return False, f"HTTP {error.code}" + (f": {said}" if said else "")
        except OSError as error:
            return False, f"unreachable ({error.__class__.__name__})"


def _refused(token: str | None) -> str | None:
    """Why the apply mode does not run here, or None. It is the person's gesture: never in CI,
    never under an App's installation token — an agent's identity holds no administration."""
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() in ("true", "1"):
        return ("--apply does not run in CI: administering the repository is a person's gesture, under their "
                "own credential.\n      Action: run it on your workstation, or print the "
                "plan without --apply.")
    if not token:
        return ("--apply needs your own credential in GH_TOKEN: a fine-grained token limited to this "
                "repository, with Administration: write and Issues: write (the labels).\n"
                "      Action: set GH_TOKEN for this one run, then revoke the token.")
    if token.startswith("ghs_"):
        return ("the token is a GitHub App's installation token — an agent's identity, which never holds "
                "administration.\n      Action: run it yourself, under your own credential.")
    return None


def _apply(client: Forge, root: Path, calls: list[Call], notes: list[str]) -> int:
    print(f"\n{len(calls)} call(s) to close the distance to the checklist, under your credential:")
    failed = 0
    for closed, method, path, body in calls:
        done, answer = client.send(method, path, body)
        if not done and method == "POST" and path == "/rulesets" and body and any(
                rule["type"] == "required_status_checks" for rule in body["rules"]):
            # D26: the forge may refuse a check it has never seen run. The ruleset goes in without
            # them, and G4 is the one step that remains.
            rest = [rule for rule in body["rules"] if rule["type"] != "required_status_checks"]
            if rest:
                again, answer_again = client.send(method, path, {**body, "rules": rest})
                if again:
                    print(f"  applied  {closed.replace('G4, ', '').replace(', G4', '')}: {method} {path or '/'} "
                          f"({answer_again}); G4 refused ({answer}): open a first pull request, let the checks "
                          "run, then run nstack settings --apply again")
                    failed += 1
                    continue
        print(f"  {'applied ' if done else 'REFUSED '} {closed}: {method} {path or '/'} ({answer})")
        failed += not done
    if notes:
        print("\nLeft to do by hand:")
        for note in notes:
            print(f"  {note}")
    print("\nThe result, read back by nstack doctor — not by this command's account of itself:\n")
    code = doctor.run(root)
    print("\nRevoke the credential you gave this run now: nothing kept it, and nothing asks for it again.")
    if failed:
        print(f"FAIL [settings] {failed} call(s) refused by the forge, named above with its answer.\n"
              "      Action: fix what the forge said, then run nstack settings --apply again — what is in "
              "place is not applied twice.")
        return 1
    return code


def run(root: Path, apply: bool = False) -> int:
    if not (root / ANSWERS).is_file():
        print(f"FAIL [settings] {ANSWERS} not found in {root}: this folder is not a project "
              "created by nstack init.\n      Action: run the command at the project root, "
              "or pass --root.")
        return 1
    answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
    forge = project.forge(root)
    if forge != "github":
        print(f"Settings: nothing to apply — forge {forge}. This version writes GitHub's settings only; "
              "what the forge should refuse is listed by nstack doctor and in .nstack/handbook/INSTALL.md.")
        return 0
    repo = str(answers.get("github_repo"))
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if apply and (refusal := _refused(token)):
        print(f"FAIL [settings] {refusal}")
        return 1
    client = Forge(repo, token, os.environ.get("GITHUB_API_URL") or "https://api.github.com") if token else None

    missing: set[str] = set()
    unread: list[str] = []
    out_of_reach: list[tuple[str, str]] = []
    if client is None:
        # G12 is not planned blind: the ruleset planned below has nobody on its bypass list, and
        # an older one that has is a step by hand, which only a read can find.
        missing = {rule for rule, _, _ in doctor.CHECKLIST} - {"G12"}
        print(f"Settings of {repo}: not read — no token (GH_TOKEN or GITHUB_TOKEN). The whole checklist is "
              "planned below; a call for a setting already in place changes nothing, except a ruleset's: "
              f"skip it if a ruleset named {RULESET_NAME} exists, and the G20 one if {HOLDS_RULESET} does.\n"
              "Not read either: the repository's visibility and plan. On a private repository without a "
              "paid plan the forge refuses the ruleset and the secret scanning — out of reach there, not a "
              "fault; run again with a token to have them left out and named.")
    else:
        try:
            client.get("")  # the repository itself: unreadable, nothing below means anything
            private = doctor._private(client)
        except doctor.NotVerified as reason:
            print(f"FAIL [settings] {repo} cannot be read: {reason}.\n      Action: supply a token that can "
                  "read the repository — fine-grained, limited to it, Administration: read — or run without "
                  "a token to print the whole checklist.")
            return 1
        for rule, _, _ in doctor.CHECKLIST:
            if private and rule in doctor.PUBLIC_ONLY:
                continue
            try:
                compliant = doctor.CHECKS[rule](client)
            except doctor.NotVerified:
                unread.append(rule)
                compliant = False
            except doctor.Gap:
                # G12 with no ruleset at all: the ruleset planned for G1 closes it, with an
                # empty bypass list. Nothing to do by hand.
                continue
            if compliant:
                continue
            if private and rule in doctor.PRIVATE_PLAN:
                out_of_reach.append((rule, doctor.PRIVATE_PLAN[rule]))
            else:
                missing.add(rule)

    calls, notes = plan(client, missing)
    if out_of_reach:
        print("\nOut of reach on this plan — not planned, and not a fault:")
        for reason in dict.fromkeys(reason for _, reason in out_of_reach):
            rules = ", ".join(rule for rule, said in out_of_reach if said == reason)
            print(f"  {rules}: {reason}")
        if set(doctor.BLOCKING) & {rule for rule, _ in out_of_reach}:
            print("  This repository stays UNGUARDED whatever is applied below: nothing here refuses a merge.\n"
                  "  Two exits: make it public, or move it to a plan that enforces rulesets.")
    if unread and apply:
        print("\nFAIL [settings] not read with this token: " + ", ".join(unread) + ". --apply never writes "
              "what it could not read: it would add a ruleset or a label twice.\n      Action: give the token "
              "Administration: write and Issues: write, then run again.")
        return 1
    if unread:
        print("\nNot read with this token, planned as if missing: " + ", ".join(unread)
              + ". A call for a setting already in place changes nothing.")
    if apply and calls:
        return _apply(client, root, calls, notes)
    if not calls and not notes:
        if client is not None:
            print(f"Settings of {repo}: nothing to change"
                  + (" within what this plan allows." if out_of_reach else ": the checklist is in place."))
        return 0
    if calls:
        print(f"\n{len(calls)} call(s) would close the distance to the checklist. Nothing was changed: run "
              "them yourself, under a credential of your own.\n")
        print("\n\n".join(render(repo, call) for call in calls))
    if notes:
        print("\nLeft to do by hand:")
        for note in notes:
            print(f"  {note}")
    print("\nThen: nstack doctor — the read-only check is what establishes the result, not this plan.")
    return 0
