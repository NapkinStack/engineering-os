# PDR-0009 — Say why a change may merge, and what that does not prove

- **Status**: Proposed (2026-09-20)
- **Date**: 2026-09-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: `nstack` (a new command), the skeleton's pull-request workflow and
  handbook

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

A change is allowed to merge because several things were true at once: it touched one module,
its boundaries held, the contract version it changed was proven compatible, its module's tests
passed, its test sheet was filled by a session that did not write it, and a human code owner
approved the head commit. Every one of those facts exists — in a CI log, in a pull request
body, in a commit trailer, in the forge's own rule evaluation.

**Nowhere are they in one place, and none of them survives.** Six months later, the question
*"why was this allowed in?"* is answered by re-reading logs that expire, a description anyone
can edit, and an approval the forge shows without saying what it covered. For a change written
by an agent, that is precisely the question a reviewer, an auditor or the next team asks
first.

**And nobody else answers it.** Verified on 2026-09-20 across the field: GitHub's rule suites
API is the only native record, and it is per-ref, unsigned, and reports a required check as one
opaque pass or fail; SLSA's Source Track defines two-party review at L4 but leaves the review
attestation format *"undefined and up to the SCSs"*, and no forge implements it; the in-toto
predicate catalogue has provenance, SBOMs and test results but **no predicate for review or
approval**; gittuf models review approvals and is in beta; Kosli records that a pull request
existed, and gates deployments rather than merges. The one project whose stated purpose is
this — *"Pull requests earn their merge with evidence, not claims"* — has one star.

Meanwhile the requirements are being written down elsewhere: the OpenSSF's OSPS Baseline asks
for *"at least one non-author human approval"* before a merge, and SLSA Source L4 for two
trusted reviewers. Both say **what must be true**. Neither says how a project shows it.

## Goal

Every change carries, on its own head commit, a record of why it was allowed to merge — built
from the checks themselves, readable by a machine and by a person, and explicit about what it
does not prove.

## Out of scope

- **Signing the record**, or turning it into an attestation chain. The shape is chosen so that
  signing is possible later; doing it now would be machinery before a reader.
- **A score, a grade or a badge.** A number invites optimisation of the number.
- **Judging anything new.** The record reports the verdicts the rules already produce; it adds
  no rule and changes none.
- **A service, a dashboard, or storage outside the repository and its forge.**
- **Claiming quality.** The record says which barriers held, not that the change is good.

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/docs/os/06-decisions.md` §2)

**How is this problem solved elsewhere?**

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [SLSA Verification Summary Attestation](https://slsa.dev/spec/v1.1/verification_summary) | A verdict with `verifier`, the `policy` it was judged against, `verificationResult` and `verifiedLevels` | **The shape.** Who judged, against what, with what result — and nothing about the thing being good |
| [in-toto attestations](https://github.com/in-toto/attestation/tree/main/spec/predicates) | A predicate catalogue: provenance, SBOM, vulnerabilities, **test results** (*"that all tests were in fact run, and that all required tests passed"*) | **The precedent for a typed record**, and the gap: no predicate names a reviewer who is not the author |
| [GitHub rule suites](https://docs.github.com/en/rest/repos/rule-suites) | `rule_evaluations` with *"rule source, enforcement status, result, rule type"* and outcomes of pass, fail **or bypass** | **That a bypass is part of the record.** A rule that was stepped around must appear, not vanish |
| [Kosli](https://docs.kosli.com/) | An *"immutable, append-only audit trail"* of attestations, and `kosli assert artifact` exiting non-zero on non-compliance | **The ambition**, and its limit: it gates deployments, and its pull-request attestation records that a pull request existed |
| [Pact `can-i-deploy`](https://docs.pact.io/pact_broker/can_i_deploy) | A question asked of recorded evidence — *"is the version you're about to deploy compatible with the versions that already exist"* — answered 0 or 1 | **That a verdict is worth more when it names the evidence it read** |

**The convention the user already knows:** a receipt. It lists what was paid for, by whom, and
when — and nobody mistakes it for a statement that the purchase was wise.

**Why depart from it:** every reference above describes an **artifact** — a build, a release,
a deployment. The unit here is a **change**, and the interesting facts about a change are
social as much as technical: who wrote it, who verified it, who approved which commit. That is
the predicate the field does not have, and the reason this record cannot simply be one of the
existing ones.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | The facts stay scattered and expire with the logs | 0 | No. The question outlives the logs |
| A. A human-readable summary comment on the pull request | A tidy comment; nothing machine-readable, nothing after the merge | Low | No, not alone. It is a rendering, not a record |
| **B. A record produced by the checks, machine-readable and rendered for people** | One command, one record per head commit, saying which rules held, on what evidence, and what is not proven | Medium | **Yes** |
| C. B, signed as an attestation from the first version | The record is verifiable away from the forge | High | Not now. The shape is kept compatible; signing waits for someone who needs it |
| D. A score out of ten | A number to show | Low | No. A score is optimised, a record is read |

## Decision

**Option B.** One record per change, assembled from what the rules already produce.

**It reports, it never judges.** Each line of the record is a verdict some rule already
reached — the scope, the boundaries, the contract comparison, the module's own checks, the
test sheet and its verifier, the hooks, the forge's approval state read read-only. The record
adds nothing and softens nothing: a rule that failed appears failed, a rule that was bypassed
appears bypassed, and a rule that did not apply says why.

**It is bound to one commit.** The record is produced for a head commit and names it. A new
push produces a different record, exactly as a new push dismisses an approval (G13): a record
that survived a force-push would be the same lie the framework refuses everywhere else.

**It names the state of the project it was produced in.** Guarded or unguarded (PDR-0006),
framed or unframed (PDR-0007), judged by a published framework or not (PDR-0005). A record
produced where nothing can refuse says so on its first line, because the same evidence means
something different in the two cases.

**And it ends with what it does not prove.** Not a disclaimer in small print — a section of the
record, as long as it needs to be: that the checks cover the rules and not the intent; that an
oracle proves what it asserts and nothing else; that a human's approval is attention, not a
guarantee; that whatever the plan could not enforce was not enforced. A record of barriers that
held is only honest if it says where there were none.

**It is readable twice.** One form for a machine — stable field names, one record per commit,
shaped so that it could later become a signed attestation without changing meaning — and one
rendering for a person, which is what appears where people already look.

---

## Expected behaviour

**Nominal journey.** A pull request's checks run as they do today. The record is produced for
the head commit, and it says: this change touched one module; the boundary rules held; the
contract version it changed was proven compatible by the project's own comparator, run from the
base; the module's tests passed; the test sheet's five scenarios were filled by a session that
authored none of the change's commits; a human code owner approved this very commit; the
repository is guarded and the project framed. Then: what this does not prove.

**Nominal journey, degraded.** The same change in an unguarded, unframed project produces the
same technical lines, plus: nothing here could have refused a merge, and no cycle bounds this
work. The record is still worth reading — it is the difference between the two states that it
exists to show.

**Edge cases and degraded states.** A rule that did not run — because a step before it failed —
appears as not run, never as passed. A check that was bypassed by an administrator appears as
bypassed, with who bypassed it if the forge says. A record asked for on a commit that no pull
request carries says so. A record asked for without a token reports the forge's part as not
verified, never as satisfied.

**Business rules.**

- Every line names the rule that produced it and the commit it was produced on.
- Nothing is summarised into a score.
- What did not run is never reported as passed.
- The record always carries what it does not prove.

**Permissions:** read-only. The record is produced from the repository and from what a
read-only token can read on the forge; producing it requires no right to change anything.

**Acceptance criteria** *(testable)*:

- [ ] Given a pull request whose checks all passed, when the record is produced, then it names
      each rule that held, the head commit, and the evidence each verdict came from.
- [ ] Given a pull request where a rule failed, when the record is produced, then that rule
      appears failed, and the record is still produced.
- [ ] Given a step that did not run, when the record is produced, then it appears as not run.
- [ ] Given an unguarded or unframed project, when the record is produced, then its first lines
      say so.
- [ ] Given any record, then it contains a section naming what it does not prove.
- [ ] Given a new push to the branch, when the record is produced again, then it names the new
      commit, and the previous record does not apply to it.
- [ ] Given no forge token, when the record is produced, then the forge's part is reported as
      not verified, never as satisfied.
- [ ] Given the machine-readable form, then every field name is stable and documented, and no
      field holds a score.

---

## Success criterion

> **Mandatory section.** Without a date nobody comes back to check, and the decision folder
> becomes a graveyard.

> We will consider this was the right call if, before **2027-06-30**, **over twenty merged
> pull requests of the pilot, the question "why was this allowed in?" is answered from the
> record alone** — without opening a CI log, and without asking the person who wrote it — and
> if at least one record shows something its reader had not noticed: a rule that did not apply,
> a step that did not run, or a bypass.

How it is observed: the twenty records, kept; and the first reading of them by someone who did
not write the changes, whose findings are logged as M9's and M10h's were.

If the criterion is not met: records nobody reads mean the facts were never actually wanted in
one place, and the command goes rather than growing features.

---

## Removal condition

> **Mandatory section.** A feature with no removal condition is permanent by default,
> including when nobody uses it.

This decision will be removed if the record is **used as a claim of quality** — quoted as
proof that a change is good rather than that named barriers held — and the wording cannot be
fixed to stop it; or if it drifts into judging, by acquiring a rule of its own. A record that
starts deciding has become a check, and it belongs with the other checks or nowhere.

---

## Impacts

- **Existing users**: none. Nothing depends on the record; it reports what already happens.
- **Modules and contracts**: none.
- **Decisions**: **PDR-0003** supplies the sheet and the verifier the record reports;
  **ADR-0004** the approval and the agent's identity; **PDR-0005**, **PDR-0006** and
  **PDR-0007** the three states it names. None of them changes.
- **Support and documentation**: the handbook gains a page on reading a record; the pull
  request template points at it; `PRODUCT.md` §2 gains one line, since this is the form the
  product's promise finally takes.
- **Data**: the record holds what the repository and the forge already show — commits,
  handles, session identifiers, verdicts. Nothing is collected beyond that, and nothing leaves
  the project.
