#!/usr/bin/env bash
# Fitness function 3 — Pull request scope and size.
#
#   P1  one PR = one module           → BLOCKING  (docs/os/02-modules.md §7)
#   P2  review budget respected       → WARNING   (docs/os/05-workflow.md §4)
#
# The `cross-module` label lifts P1. The `hors-budget` label documents P2.
# Both are deliberately visible: they make the exception countable
# (docs/os/10-mesure.md §3).
#
# Local usage :  nstack pr-scope [--base BASE] [--root ROOT]   (base defaults to origin/main)
# In CI       :  PR_LABELS="cross-module,bug" bash src/napkinstack/fitness/pr_scope.sh "$BASE_SHA"

set -uo pipefail

BASE="${1:-origin/main}"
LABELS="${PR_LABELS:-}"
MAX_LINES="${MAX_LINES:-400}"
MAX_FILES="${MAX_FILES:-15}"

if ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  echo "Base '$BASE' not found — check skipped."
  exit 0
fi

CHANGED=$(git diff --name-only "$BASE"...HEAD)
[ -z "$CHANGED" ] && { echo "No file changed."; exit 0; }

# Modules touched (modules/, services/, apps/, packages/)
MODULES=$(echo "$CHANGED" \
  | grep -E '^(modules|services|apps|packages)/[^/]+/' \
  | cut -d/ -f1-2 | sort -u)
COUNT=$(echo "$MODULES" | grep -c . || true)

echo "Files changed   : $(echo "$CHANGED" | wc -l | tr -d ' ')"
echo "Modules touched : $COUNT"
[ "$COUNT" -gt 0 ] && echo "$MODULES" | sed 's/^/  - /'

STATUS=0

# --- P1 : one PR = one module --------------------------------------------
if [ "$COUNT" -gt 1 ]; then
  if echo "$LABELS" | grep -q 'cross-module'; then
    echo
    echo "WARNING [P1] Cross-module PR allowed by label."
    echo "  Counted as an exception. A rising rate means a boundary is decaying."
  else
    echo
    echo "FAIL [P1] This PR touches $COUNT modules."
    echo "  One PR = one module (docs/os/02-modules.md §7)."
    echo "  A contract change goes through an expand/contract sequence,"
    echo "  never a single PR (docs/os/03-contrats.md §4)."
    echo "  If the exception is justified: add the 'cross-module' label."
    STATUS=1
  fi
fi

# --- P2 : review budget --------------------------------------------------
STATS=$(git diff --numstat "$BASE"...HEAD \
  | grep -vE '(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|go\.sum|uv\.lock|\.generated\.|/generated/)' \
  || true)
LINES=$(echo "$STATS" | awk '{ a += $1 + $2 } END { print a+0 }')
FILES=$(echo "$STATS" | grep -c . || true)

echo
echo "Review budget : ${LINES}/${MAX_LINES} lines, ${FILES}/${MAX_FILES} files"

if [ "$LINES" -gt "$MAX_LINES" ] || [ "$FILES" -gt "$MAX_FILES" ]; then
  if echo "$LABELS" | grep -q 'hors-budget'; then
    echo "WARNING [P2] Over budget, justified by label."
  else
    echo "WARNING [P2] Over the review budget."
    echo "  A project's throughput is its VERIFICATION throughput, not its generation rate."
    echo "  Split it up, or add the 'hors-budget' label with a justification"
    echo "  (generation, mechanical migration, mass rename)."
  fi
fi

exit $STATUS
