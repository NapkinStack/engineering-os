# Runbook — platform

## A check is blocking the whole team

1. Check that the failure is real and not a false positive of the detection.
2. If it is a false positive: fix the pattern in `boundaries.py`, add a test case.
3. **Never disable the check** to unblock. Use the exception label provided, which
   leaves a counted trace.

## Rollback

The fitness functions are stateless: `git revert` is enough. Then check
`uv run nstack fitness` on the main branch.

## A recurring false positive

That is a platform defect, not a team one. Open an *Architecture* issue: a gate that is
systematically worked around is a badly designed gate.
