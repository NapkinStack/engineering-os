"""D239 (#430): two pull requests of one deliverable, each attested green on its own base, merged
green one after the other — and together B1 failed on main: the consumer read a contract version its
manifest did not consume, a rule that fires only once the producer provides it. No check ever
judged the two together. From then on the pre-push hook refused every push, of every contributor,
for forty minutes. The checks judge what will land only when a branch is up to date with main
before it merges: G22, a gap where the ruleset does not ask it, and asked by `nstack settings`."""

from __future__ import annotations

import pytest

from napkinstack import doctor, settings


class StatusChecksRule:
    def __init__(self, queue=False, **parameters):
        self.parameters, self.queue = parameters, queue

    def get(self, path, missing=False):
        if path == "":
            return {"default_branch": "main"}
        return [{"type": "required_status_checks", "parameters": self.parameters},
                *([{"type": "merge_queue", "parameters": {}}] if self.queue else [])]


@pytest.mark.parametrize("strict, compliant", [(True, True), (False, False), (None, False)])
def test_g22_reads_whether_a_branch_must_be_up_to_date(strict, compliant):
    parameters = {"required_status_checks": [{"context": job} for job in doctor.JOBS]}
    if strict is not None:
        parameters["strict_required_status_checks_policy"] = strict
    assert doctor.CHECKS["G22"](StatusChecksRule(**parameters)) is compliant


def test_g22_blocks_and_names_its_setting():
    assert "G22" in doctor.BLOCKING and "G22" in doctor.PRIVATE_PLAN
    [(rule, setting, action)] = [line for line in doctor.CHECKLIST if line[0] == "G22"]
    assert "up to date before merging" in setting and "require branches to be up to date before merging" in action


@pytest.mark.parametrize("missing", [{"G22"}, {"G4"}, {"G4", "G22"}])
def test_the_ruleset_planned_asks_branches_up_to_date(missing):
    body = settings.ruleset(missing)
    [rule] = [rule for rule in body["rules"] if rule["type"] == "required_status_checks"]
    assert rule["parameters"]["strict_required_status_checks_policy"] is True
    assert {check["context"] for check in rule["parameters"]["required_status_checks"]} == set(doctor.JOBS)


def test_a_merge_queue_also_checks_what_will_land():
    assert doctor.CHECKS["G22"](StatusChecksRule(queue=True, strict_required_status_checks_policy=False)) is True


def test_g4_and_g22_read_every_ruleset_layered_on_the_branch():
    """The verifier's: a project's first ruleset asked the checks not up to date; the second, from
    nstack settings, asks them up to date. GitHub applies the strictest; read alone, the first said
    a gap that was not one."""
    class Layered:
        def get(self, path, missing=False):
            if path == "":
                return {"default_branch": "main"}
            return [{"type": "required_status_checks", "ruleset_id": 1, "parameters": {
                        "required_status_checks": [{"context": job} for job in doctor.JOBS[:2]],
                        "strict_required_status_checks_policy": False}},
                    {"type": "required_status_checks", "ruleset_id": 2, "parameters": {
                        "required_status_checks": [{"context": job} for job in doctor.JOBS[2:]],
                        "strict_required_status_checks_policy": True}}]
    assert doctor.CHECKS["G22"](Layered()) is True and doctor.CHECKS["G4"](Layered()) is True
