#!/usr/bin/env bash
# Tests des fitness functions. L'oracle des garde-fous eux-mêmes.
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "→ les scripts compilent"
python3 -m py_compile platform/fitness/manifests.py platform/fitness/boundaries.py

echo "→ manifests du dépôt conformes"
python3 platform/fitness/manifests.py .

echo "→ frontières du dépôt conformes"
python3 platform/fitness/boundaries.py .

echo "→ un manifest invalide DOIT échouer"
TMP=$(mktemp -d)
mkdir -p "$TMP/modules/cassé"
printf 'module:\n  name: cassé\n' > "$TMP/modules/cassé/MANIFEST.yaml"
if python3 platform/fitness/manifests.py "$TMP" >/dev/null 2>&1; then
  echo "ÉCHEC : un manifest incomplet est passé au vert."; rm -rf "$TMP"; exit 1
fi
rm -rf "$TMP"

# Skills : chaque fixture est une copie jetable, le vrai .claude/ n'est jamais touché.
SK=$(mktemp -d)
trap 'rm -rf "$SK"' EXIT
mkdir -p "$SK/platform"
cp platform/sync_skills.py platform/skills.yaml "$SK/platform/"
cp -r playbooks "$SK/"

echo "→ skills : sur un clone vierge, S3 est non applicable et le check passe"
if ! OUT=$(python3 "$SK/platform/sync_skills.py" --check 2>&1); then
  echo "ÉCHEC : --check échoue alors qu'aucune skill n'a été générée."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "S3 non applicable" \
  || { echo "ÉCHEC : S3 ignoré sans le dire."; echo "$OUT"; exit 1; }

echo "→ skills : une skill désynchronisée DOIT échouer"
python3 "$SK/platform/sync_skills.py" >/dev/null
echo "ajout" >> "$SK/playbooks/tests.md"
if OUT=$(python3 "$SK/platform/sync_skills.py" --check 2>&1); then
  echo "ÉCHEC : une skill désynchronisée est passée au vert."; exit 1
fi
echo "$OUT" | grep -qF "[S3] skill 'tests' désynchronisée" \
  || { echo "ÉCHEC : message S3 attendu absent."; echo "$OUT"; exit 1; }

echo "→ skills : une skill supprimée DOIT échouer"
python3 "$SK/platform/sync_skills.py" >/dev/null
rm "$SK/.claude/skills/ux/SKILL.md"
if OUT=$(python3 "$SK/platform/sync_skills.py" --check 2>&1); then
  echo "ÉCHEC : une skill supprimée est passée au vert."; exit 1
fi
echo "$OUT" | grep -qF "[S3] skill 'ux' absente" \
  || { echo "ÉCHEC : message S3 attendu absent."; echo "$OUT"; exit 1; }

echo "Tests plateforme : OK"
