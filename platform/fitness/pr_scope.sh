#!/usr/bin/env bash
# Fitness function 3 — Périmètre et taille de la PR.
#
#   P1  une PR = un module            → BLOQUANT  (docs/os/02-modules.md §7)
#   P2  budget de revue respecté      → AVERTISSEMENT (docs/os/05-workflow.md §4)
#
# Le label `cross-module` lève P1. Le label `hors-budget` documente P2.
# Les deux sont volontairement visibles : ils rendent l'exception comptable
# (docs/os/10-mesure.md §3).
#
# Usage local :  ./platform/fitness/pr_scope.sh [base]     (base par défaut : origin/main)
# En CI      :   PR_LABELS="cross-module,bug" ./platform/fitness/pr_scope.sh "$BASE_SHA"

set -uo pipefail

BASE="${1:-origin/main}"
LABELS="${PR_LABELS:-}"
MAX_LINES="${MAX_LINES:-400}"
MAX_FILES="${MAX_FILES:-15}"

if ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  echo "Base '$BASE' introuvable — check ignoré."
  exit 0
fi

CHANGED=$(git diff --name-only "$BASE"...HEAD)
[ -z "$CHANGED" ] && { echo "Aucun fichier modifié."; exit 0; }

# Modules touchés (modules/, services/, apps/, packages/)
MODULES=$(echo "$CHANGED" \
  | grep -E '^(modules|services|apps|packages)/[^/]+/' \
  | cut -d/ -f1-2 | sort -u)
COUNT=$(echo "$MODULES" | grep -c . || true)

echo "Fichiers modifiés : $(echo "$CHANGED" | wc -l | tr -d ' ')"
echo "Modules touchés   : $COUNT"
[ "$COUNT" -gt 0 ] && echo "$MODULES" | sed 's/^/  - /'

STATUS=0

# --- P1 : une PR = un module ---------------------------------------------
if [ "$COUNT" -gt 1 ]; then
  if echo "$LABELS" | grep -q 'cross-module'; then
    echo
    echo "AVERTISSEMENT [P1] PR cross-module autorisée par label."
    echo "  Comptée comme exception. Un taux qui monte = frontière qui se dégrade."
  else
    echo
    echo "ÉCHEC [P1] Cette PR touche $COUNT modules."
    echo "  Une PR = un module (docs/os/02-modules.md §7)."
    echo "  Un changement de contrat se fait en séquence expand/contract,"
    echo "  jamais en une PR unique (docs/os/03-contrats.md §4)."
    echo "  Si l'exception est justifiée : ajouter le label 'cross-module'."
    STATUS=1
  fi
fi

# --- P2 : budget de revue ------------------------------------------------
STATS=$(git diff --numstat "$BASE"...HEAD \
  | grep -vE '(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|go\.sum|\.generated\.|/generated/)' \
  || true)
LINES=$(echo "$STATS" | awk '{ a += $1 + $2 } END { print a+0 }')
FILES=$(echo "$STATS" | grep -c . || true)

echo
echo "Budget de revue : ${LINES}/${MAX_LINES} lignes, ${FILES}/${MAX_FILES} fichiers"

if [ "$LINES" -gt "$MAX_LINES" ] || [ "$FILES" -gt "$MAX_FILES" ]; then
  if echo "$LABELS" | grep -q 'hors-budget'; then
    echo "AVERTISSEMENT [P2] Hors budget, justifié par label."
  else
    echo "AVERTISSEMENT [P2] Hors budget de revue."
    echo "  Le débit du projet est le débit de VÉRIFICATION, pas de génération."
    echo "  Redécouper, ou ajouter le label 'hors-budget' avec justification"
    echo "  (génération, migration mécanique, renommage massif)."
  fi
fi

exit $STATUS
