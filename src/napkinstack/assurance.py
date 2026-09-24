"""
The machine half of the assurance matrix (`docs/os/05-workflow.md` §7).

`assurance` here is the word of DO-178C's *Design Assurance Level*, of ISO 26262, of the
OpenSSF Baseline's "advanced high assurance", and of plain *quality assurance*: how much
verification the cost of a failure buys. It is not `insurance`, and it is not the French
word it is spelled like.

That table is the single source of what a criticality value requires (D67). Its rows are marked
*machine* or *owed*: the machine ones are here, the owed ones belong to a human and this module
does not pretend to know them.

Before it, one threshold lived in four places — `pull_request.SHEET_CRITICALITIES`,
`modules.NEEDS_RUNBOOK`, `modules.NEEDS_SHEET` and a literal inside M8 — which is how a
framework comes to describe one fact three times in its documents and spend it as one in its
code. A rule that reads the matrix here cannot drift from the table that announces it;
`platform/tests/test_assurance_contract.py` guards the other direction.

One row of the table is deliberately absent: **e2e**. A check can read that a module
declares an `e2e` verb; it cannot read that the verb runs end-to-end scenarios rather than
the unit suite under another name. This repository's own `platform` module declares its
whole oracle as `test`, so the rule would have asked it to alias one command as two — and a
rule a one-line alias satisfies teaches the alias (P6). The row is owed to a human.
"""

from __future__ import annotations

# Ascending, so that "the value below" is the previous one. M3 validates a manifest against it.
CRITICALITIES = ("prototype", "standard", "high", "critical")

# What each value requires, machine rows only:
#   sheet            a test sheet run by a verifier who is not an author (T1)
#   runbook          a runbook declared in the manifest and present (M8)
#   rerun_at_head    every scenario re-run at the head; no confirmation stands in for a
#                    re-run, which is what the top value costs (T4)
# `"user_facing"` means: required only when the module declares a user-visible surface (M10).
MATRIX: dict[str, dict[str, bool | str]] = {
    "prototype": {"sheet": False, "runbook": False, "rerun_at_head": False},
    "standard": {"sheet": "user_facing", "runbook": False, "rerun_at_head": False},
    "high": {"sheet": True, "runbook": True, "rerun_at_head": False},
    "critical": {"sheet": True, "runbook": True, "rerun_at_head": True},
}


def requires(criticality: str | None, row: str, user_facing: bool = False) -> bool:
    """Does `criticality` require `row`? An unknown value reads as the strictest: M3 refuses it
    where a manifest is judged, and until a reader fixes that the safe reading is the expensive
    one — never the cheap one."""
    rule = MATRIX.get(criticality or "", MATRIX["critical"])[row]
    return bool(user_facing) if rule == "user_facing" else bool(rule)


def below(criticality: str | None) -> str | None:
    """The value one step down, or None at the bottom and for a value the engine does not know."""
    if criticality not in CRITICALITIES:
        return None
    index = CRITICALITIES.index(criticality)
    return CRITICALITIES[index - 1] if index else None


def relief(criticality: str | None, row: str, user_facing: bool = False) -> str:
    """What the value below would have required instead, as half a sentence, or "" when there is
    nothing below or nothing would change.

    P6 asks a refusal to name an action. On a threshold the action is not always "do the work":
    it can be "this module is not what you declared it to be". Saying what the neighbouring
    value costs lets a reader judge the declaration instead of only obeying it — which is the
    decision an agent took alone when nothing told it where to stop (D70)."""
    lower = below(criticality)
    if lower is None or requires(lower, row, user_facing):
        return ""
    if MATRIX[lower][row] == "user_facing":
        return f"at {lower} it would be required only for a module a user sees"
    return f"at {lower} it would not be required"
