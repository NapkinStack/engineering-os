#!/usr/bin/env bash
# Crée un nouveau module à partir du squelette, avec ses garde-fous actifs
# dès le premier commit (docs/os/09-plateforme.md §4).
#
# Usage : ./platform/scaffold/new-module.sh <nom> <owner> <criticite>
#   nom        : kebab-case, ex. billing
#   owner      : une ÉQUIPE, ex. team-revenue
#   criticite  : prototype | standard | eleve | critique

set -euo pipefail

NAME="${1:-}"; OWNER="${2:-}"; CRIT="${3:-standard}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$ROOT/modules/$NAME"

usage() { echo "Usage : $0 <nom> <owner> [prototype|standard|eleve|critique]"; exit 1; }

[ -z "$NAME" ] && usage
[ -z "$OWNER" ] && usage
echo "$NAME" | grep -qE '^[a-z][a-z0-9-]*$' || { echo "Nom invalide : kebab-case attendu."; exit 1; }
echo "$CRIT" | grep -qE '^(prototype|standard|eleve|critique)$' || usage
[ -d "$DEST" ] && { echo "Le module '$NAME' existe déjà."; exit 1; }

cp -r "$ROOT/platform/templates/module" "$DEST"

# Substitutions dans le squelette
find "$DEST" -type f -print0 | while IFS= read -r -d '' f; do
  sed -i.bak \
    -e "s/{{MODULE_NAME}}/$NAME/g" \
    -e "s/{{OWNER}}/$OWNER/g" \
    -e "s/{{CRITICALITY}}/$CRIT/g" \
    "$f" && rm -f "$f.bak"
done

# CODEOWNERS
CO="$ROOT/.github/CODEOWNERS"
if ! grep -q "^/modules/$NAME/" "$CO" 2>/dev/null; then
  echo "/modules/$NAME/                @$OWNER" >> "$CO"
fi

# Runbook obligatoire au-delà de standard
if [ "$CRIT" = "eleve" ] || [ "$CRIT" = "critique" ]; then
  mkdir -p "$DEST/docs"
  cat > "$DEST/docs/runbook.md" <<EOF
# Runbook — $NAME

> Obligatoire pour criticality=$CRIT (docs/os/08-qualite.md §7).
> Un runbook vide fait échouer la CI. À remplir avant la mise en production.

## Alertes et réponses
| Alerte | Signification | Première action |
|---|---|---|
| | | |

## Rollback
<Procédure testée, pas supposée.>

## Vérification post-déploiement
<Ce qu'on regarde, et pendant combien de temps.>

## Dépendances et dégradation
<Que se passe-t-il si chaque dépendance est indisponible ?>
EOF
  # Activer la ligne runbook du manifest
  sed -i.bak 's|^\( *\)# runbook:|\1runbook:|' "$DEST/MANIFEST.yaml" && rm -f "$DEST/MANIFEST.yaml.bak"
fi

echo "Module créé : modules/$NAME"
echo
echo "Actif dès maintenant :"
echo "  - MANIFEST.yaml pré-rempli (owner=$OWNER, criticality=$CRIT)"
echo "  - AGENTS.md local avec les sections attendues"
echo "  - verbes standards : make check / test / run"
echo "  - CODEOWNERS mis à jour"
echo "  - fitness functions actives sur ce module"
[ "$CRIT" != "prototype" ] && [ "$CRIT" != "standard" ] && echo "  - runbook créé (à remplir)"
echo
echo "Étapes suivantes :"
echo "  1. ADR de création dans docs/adr/ (capacité, frontière, alternatives)"
echo "  2. Remplir la responsabilité du MANIFEST — UNE phrase"
echo "  3. Remplir modules/$NAME/AGENTS.md avec le spécifique, jamais le kernel"
echo "  4. make fitness  → doit passer avant le premier commit"
