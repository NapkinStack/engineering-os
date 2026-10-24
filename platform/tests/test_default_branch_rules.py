"""D152: doctor reads the rules of the repository's default branch, where the checklist's ruleset
(`~DEFAULT_BRANCH`) applies — not of a branch named main. On a repository whose default branch
is not main, the rules read on `main` were none: G1 to G4 and G12 said missing however often the
ruleset was created, and each `nstack settings --apply` added one more.
"""

from __future__ import annotations

from napkinstack import doctor, settings

PULL = {"type": "pull_request", "ruleset_id": 3, "parameters": {
    "required_approving_review_count": 1, "require_code_owner_review": True,
    "dismiss_stale_reviews_on_push": True}}


class Forge:
    def __init__(self, default: str | None):
        self.default, self.read = default, []

    def get(self, path, missing=False):
        self.read.append(path)
        if path == "":
            return {"default_branch": self.default} if self.default else {}
        if path == f"/rules/branches/{self.default or 'main'}":
            return [PULL]
        if path.startswith("/rulesets/"):
            return {"id": 3, "bypass_actors": []}
        return []


def test_the_rules_read_are_the_default_branch_s():
    forge = Forge("master")
    assert doctor.CHECKS["G1"](forge) is True
    assert "/rules/branches/master" in forge.read and "/rules/branches/main" not in forge.read


def test_g12_reads_the_rulesets_of_the_default_branch():
    assert doctor.CHECKS["G12"](Forge("trunk")) is True


def test_a_default_branch_unread_falls_back_on_main():
    assert doctor.CHECKS["G1"](Forge(None)) is True


def test_a_default_branch_s_name_is_quoted_in_the_path():
    forge = Forge("release/2026")
    doctor.CHECKS["G1"](forge)
    assert "/rules/branches/release%2F2026" in forge.read


def test_the_ruleset_in_place_on_another_default_branch_is_not_planned_again():
    forge = Forge("master")
    missing = {rule for rule in ("G1", "G2", "G3") if not doctor.CHECKS[rule](forge)}
    assert not missing
    calls, _ = settings.plan(None, missing | {"G19"})
    assert [path for _, _, path, _ in calls] == ["/branches/<the default branch>/rename"]
