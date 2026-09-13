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

echo "Tests plateforme : OK"
