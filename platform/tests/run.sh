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

# Hooks : dépôts git jetables, identité fictive. Les faux secrets sont assemblés à
# l'exécution : écrits en dur, ils déclencheraient la protection au push.
command -v pre-commit >/dev/null \
  || { echo "ÉCHEC : pre-commit requis (https://pre-commit.com/#install)."; exit 1; }
HK=$(mktemp -d)
trap 'rm -rf "$SK" "$HK"' EXIT
GIT_ID=(-c user.name=test -c user.email=test@example.invalid -c init.defaultBranch=main)

depot_avec_hooks() {
  local d="$HK/$1"
  git "${GIT_ID[@]}" init -q "$d"
  [ -f .pre-commit-config.yaml ] && cp .pre-commit-config.yaml "$d/"
  git -C "$d" add -A
  git "${GIT_ID[@]}" -C "$d" commit -q --no-verify --allow-empty -m init
  (cd "$d" && pre-commit install >/dev/null)
}
faux_jeton_aws() {
  python3 -c 'import secrets, string; print("AK" + "IA" + "".join(secrets.choice(string.ascii_uppercase + "234567") for _ in range(16)))'
}

echo "→ hooks : un secret DOIT bloquer le commit"
depot_avec_hooks secret
echo "aws_access_key_id = $(faux_jeton_aws)" > "$HK/secret/config.ini"
git -C "$HK/secret" add config.ini
if OUT=$(git "${GIT_ID[@]}" -C "$HK/secret" commit -m test 2>&1); then
  echo "ÉCHEC : un secret a été commité."; exit 1
fi
echo "$OUT" | grep -qE "Detect hardcoded secrets\.+Failed" \
  || { echo "ÉCHEC : refus sans le hook gitleaks."; echo "$OUT"; exit 1; }

echo "→ hooks : une clé privée DOIT bloquer le commit"
depot_avec_hooks cle
printf -- '-----BEGIN %s PRIVATE KEY-----\nMIIEow\n-----END %s PRIVATE KEY-----\n' RSA RSA > "$HK/cle/id"
git -C "$HK/cle" add id
if OUT=$(git "${GIT_ID[@]}" -C "$HK/cle" commit -m test 2>&1); then
  echo "ÉCHEC : une clé privée a été commitée."; exit 1
fi
echo "$OUT" | grep -qiE "detect private key\.+Failed" \
  || { echo "ÉCHEC : refus sans detect-private-key."; echo "$OUT"; exit 1; }

echo "→ hooks : un script à shebang non exécutable DOIT bloquer le commit"
depot_avec_hooks shebang
printf '#!/bin/sh\necho ok\n' > "$HK/shebang/outil.sh"
git -C "$HK/shebang" add outil.sh
if OUT=$(git "${GIT_ID[@]}" -C "$HK/shebang" commit -m test 2>&1); then
  echo "ÉCHEC : un script non exécutable a été commité."; exit 1
fi
echo "$OUT" | grep -qiE "shebangs are executable\.+Failed" \
  || { echo "ÉCHEC : refus sans le contrôle de shebang."; echo "$OUT"; exit 1; }

echo "→ CI : un secret commité en contournant le hook DOIT être trouvé, sans être affiché"
depot_avec_hooks historique
JETON=$(faux_jeton_aws)
echo "aws_access_key_id = $JETON" > "$HK/historique/config.ini"
git -C "$HK/historique" add config.ini
git "${GIT_ID[@]}" -C "$HK/historique" commit -q --no-verify -m contournement
if OUT=$(cd "$HK/historique" && pre-commit run gitleaks-historique --hook-stage manual --all-files 2>&1); then
  echo "ÉCHEC : le scan d'historique n'a rien trouvé."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qi "leaks found" \
  || { echo "ÉCHEC : échec sans détection de gitleaks."; echo "$OUT"; exit 1; }
if echo "$OUT" | grep -qF "$JETON"; then
  echo "ÉCHEC : le secret apparaît en clair dans la sortie (logs de CI publics)."; exit 1
fi

echo "→ hooks : même version de gitleaks au commit et dans le scan d'historique"
V_HOOK=$(grep -A1 'repo: https://github.com/gitleaks/gitleaks' .pre-commit-config.yaml | grep -oE 'frozen: v[0-9.]+' | cut -d' ' -f2 || true)
V_HISTO=$(grep -oE 'gitleaks/v8@v[0-9.]+' .pre-commit-config.yaml | cut -d@ -f2 || true)
[ -n "$V_HOOK" ] && [ "$V_HOOK" = "$V_HISTO" ] \
  || { echo "ÉCHEC : versions de gitleaks divergentes (hook : '$V_HOOK', historique : '$V_HISTO')."; exit 1; }

echo "Tests plateforme : OK"
