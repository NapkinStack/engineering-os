#!/usr/bin/env bash
# Tests des fitness functions. L'oracle des garde-fous eux-mêmes.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$(pwd)

echo "→ nstack : la commande répond et affiche sa version"
uv run nstack --version | grep -qE '^nstack [0-9]+\.[0-9]+' \
  || { echo "ÉCHEC : nstack --version ne répond pas."; exit 1; }

echo "→ manifests du dépôt conformes"
uv run nstack manifests --root .

echo "→ frontières du dépôt conformes"
uv run nstack boundaries --root .

echo "→ un manifest invalide DOIT échouer"
TMP=$(mktemp -d)
mkdir -p "$TMP/modules/cassé"
printf 'module:\n  name: cassé\n' > "$TMP/modules/cassé/MANIFEST.yaml"
if OUT=$(cd / && uv run --project "$REPO" nstack manifests --root "$TMP" 2>&1); then
  echo "ÉCHEC : un manifest incomplet est passé au vert."; rm -rf "$TMP"; exit 1
fi
echo "$OUT" | grep -qF "[M2] cassé" \
  || { echo "ÉCHEC : message M2 attendu absent."; echo "$OUT"; rm -rf "$TMP"; exit 1; }
rm -rf "$TMP"

# Skills : chaque fixture est une copie jetable, le vrai .claude/ n'est jamais touché.
SK=$(mktemp -d)
trap 'rm -rf "$SK"' EXIT
mkdir -p "$SK/platform"
cp platform/skills.yaml "$SK/platform/"
cp -r playbooks "$SK/"
nstack_sk() { (cd / && uv run --project "$REPO" nstack skills --root "$SK" "$@"); }

echo "→ skills : la racine donnée est analysée, quel que soit le dossier courant (D21)"
if (cd / && uv run --project "$REPO" nstack skills --check --root / >/dev/null 2>&1); then
  echo "ÉCHEC : racine sans skills.yaml acceptée."; exit 1
fi
nstack_sk --check >/dev/null || { echo "ÉCHEC : la racine donnée n'est pas analysée."; exit 1; }

echo "→ skills : sur un clone vierge, S3 est non applicable et le check passe"
if ! OUT=$(nstack_sk --check 2>&1); then
  echo "ÉCHEC : --check échoue alors qu'aucune skill n'a été générée."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "S3 non applicable" \
  || { echo "ÉCHEC : S3 ignoré sans le dire."; echo "$OUT"; exit 1; }

echo "→ skills : une skill désynchronisée DOIT échouer"
nstack_sk >/dev/null
echo "ajout" >> "$SK/playbooks/tests.md"
if OUT=$(nstack_sk --check 2>&1); then
  echo "ÉCHEC : une skill désynchronisée est passée au vert."; exit 1
fi
echo "$OUT" | grep -qF "[S3] skill 'tests' désynchronisée" \
  || { echo "ÉCHEC : message S3 attendu absent."; echo "$OUT"; exit 1; }

echo "→ skills : une skill supprimée DOIT échouer"
nstack_sk >/dev/null
rm "$SK/.claude/skills/ux/SKILL.md"
if OUT=$(nstack_sk --check 2>&1); then
  echo "ÉCHEC : une skill supprimée est passée au vert."; exit 1
fi
echo "$OUT" | grep -qF "[S3] skill 'ux' absente" \
  || { echo "ÉCHEC : message S3 attendu absent."; echo "$OUT"; exit 1; }

echo "→ skills : le frontmatter généré est du YAML valide et restitue nom et description"
cp playbooks/tests.md "$SK/playbooks/"
nstack_sk >/dev/null
python3 - "$SK" <<'EOF' || exit 1
import sys, yaml
from pathlib import Path
root = Path(sys.argv[1])
skills = yaml.safe_load((root / "platform/skills.yaml").read_text(encoding="utf-8"))["skills"]
for name, entry in skills.items():
    _, front, _ = (root / ".claude/skills" / name / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)
    try:
        meta = yaml.safe_load(front)
    except yaml.YAMLError as exc:
        sys.exit(f"ÉCHEC : frontmatter de '{name}' invalide : {exc}")
    if meta != {"name": name, "description": " ".join(entry["description"].split())}:
        sys.exit(f"ÉCHEC : le frontmatter de '{name}' ne restitue pas nom et description : {meta!r}")
EOF

# S4 : la skill « tests » est renommée, ou sa description remplacée, dans une copie de
# skills.yaml. Sans .claude/skills/, S3 ne s'applique pas : seul S4 peut échouer.
skill_tests_modifiee() {  # $1 = nom, $2 = longueur de description (facultatif)
  cp platform/skills.yaml "$SK/platform/"
  python3 - "$SK/platform/skills.yaml" "$@" <<'EOF'
import sys, yaml
path, name, *size = sys.argv[1:]
with open(path, encoding="utf-8") as f:
    data = yaml.safe_load(f)
entry = data["skills"].pop("tests")
if size:
    entry["description"] = "x" * int(size[0])
data["skills"][name] = entry
with open(path, "w", encoding="utf-8") as f:
    yaml.safe_dump(data, f, allow_unicode=True)
EOF
}
rm -rf "$SK/.claude"
A64=$(printf 'a%.0s' {1..64})

echo "→ skills : un nom hors spécification Agent Skills DOIT échouer (S4)"
for nom in Majuscule -debut fin- double--tiret nom_souligne "${A64}a"; do
  skill_tests_modifiee "$nom"
  if OUT=$(nstack_sk --check 2>&1); then
    echo "ÉCHEC : nom de skill invalide accepté : '$nom'."; exit 1
  fi
  echo "$OUT" | grep -qF "[S4] skill '$nom'" \
    || { echo "ÉCHEC : message S4 attendu absent pour '$nom'."; echo "$OUT"; exit 1; }
done

echo "→ skills : une description de plus de 1024 caractères DOIT échouer (S4)"
skill_tests_modifiee tests 1025
if OUT=$(nstack_sk --check 2>&1); then
  echo "ÉCHEC : description de 1025 caractères acceptée."; exit 1
fi
echo "$OUT" | grep -qF "[S4] skill 'tests'" \
  || { echo "ÉCHEC : message S4 attendu absent."; echo "$OUT"; exit 1; }

echo "→ skills : nom de 64 caractères et description de 1024 caractères acceptés"
skill_tests_modifiee "$A64" 1024
nstack_sk --check >/dev/null \
  || { echo "ÉCHEC : limites de la spécification refusées."; exit 1; }

# Scaffold : copie jetable, le vrai dépôt n'est jamais touché.
SC=$(mktemp -d)
trap 'rm -rf "$SK" "$SC"' EXIT

echo "→ scaffold : le module généré a un MANIFEST.yaml valide, aux valeurs substituées"
mkdir -p "$SC/.github" "$SC/modules"
cp .github/CODEOWNERS "$SC/.github/"
uv run nstack new-module demo equipe-demo standard --root "$SC" >/dev/null
python3 - "$SC/modules/demo/MANIFEST.yaml" <<'EOF' || exit 1
import sys, yaml
module = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["module"]
attendu = {"name": "demo", "owner": "equipe-demo", "criticality": "standard"}
if {k: module.get(k) for k in attendu} != attendu:
    sys.exit(f"ÉCHEC : substitutions du gabarit incorrectes : {module!r}")
EOF
uv run nstack manifests --root "$SC" >/dev/null \
  || { echo "ÉCHEC : le module généré ne passe pas nstack manifests."; exit 1; }

echo "→ nstack fitness : échoue si l'un des trois contrôles échoue"
FT=$(mktemp -d)
mkdir -p "$FT/platform" "$FT/playbooks"
printf 'skills: {}\n' > "$FT/platform/skills.yaml"
printf '# orphelin\n' > "$FT/playbooks/orphelin.md"
if OUT=$(uv run nstack fitness --root "$FT" 2>&1); then
  echo "ÉCHEC : un playbook sans entrée est passé au vert."; rm -rf "$FT"; exit 1
fi
echo "$OUT" | grep -qF "[S1]" || { echo "ÉCHEC : S1 attendu."; echo "$OUT"; rm -rf "$FT"; exit 1; }
rm -rf "$FT"

echo "→ nstack pr-scope : répond sur la racine donnée"
uv run nstack pr-scope --root . --base HEAD | grep -qF "Aucun fichier modifié" \
  || { echo "ÉCHEC : nstack pr-scope ne répond pas."; exit 1; }

# Hooks : dépôts git jetables, identité fictive. Les faux secrets sont assemblés à
# l'exécution : écrits en dur, ils déclencheraient la protection au push.
command -v pre-commit >/dev/null \
  || { echo "ÉCHEC : pre-commit requis (https://pre-commit.com/#install)."; exit 1; }
HK=$(mktemp -d)
trap 'rm -rf "$SK" "$SC" "$HK"' EXIT
GIT_ID=(-c user.name=test -c user.email=test@example.invalid -c init.defaultBranch=main)

depot_avec_hooks() {
  local d="$HK/$1"
  git "${GIT_ID[@]}" init -q "$d"
  [ -f .pre-commit-config.yaml ] && cp .pre-commit-config.yaml "$d/"
  [ -f .yamllint.yaml ] && cp .yamllint.yaml "$d/"
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

echo "→ workflows : injection, action non épinglée, permissions et token persistant DOIVENT échouer"
depot_avec_hooks zizmor
mkdir -p "$HK/zizmor/.github/workflows"
cat > "$HK/zizmor/.github/workflows/faille.yml" <<'EOF'
name: faille
on: pull_request
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "${{ github.event.pull_request.title }}"
EOF
git -C "$HK/zizmor" add .github
if OUT=$(cd "$HK/zizmor" && pre-commit run zizmor --files .github/workflows/faille.yml 2>&1); then
  echo "ÉCHEC : un workflow vulnérable est passé."; exit 1
fi
for audit in template-injection unpinned-uses excessive-permissions artipacked; do
  echo "$OUT" | grep -qF "[$audit]" \
    || { echo "ÉCHEC : zizmor ne signale pas $audit."; echo "$OUT"; exit 1; }
done

echo "→ workflows : un workflow invalide DOIT échouer"
depot_avec_hooks actionlint
mkdir -p "$HK/actionlint/.github/workflows"
printf 'on: push\njobs:\n  j:\n    steps:\n      - run: echo ok\n' > "$HK/actionlint/.github/workflows/invalide.yml"
git -C "$HK/actionlint" add .github
if OUT=$(cd "$HK/actionlint" && pre-commit run actionlint --files .github/workflows/invalide.yml 2>&1); then
  echo "ÉCHEC : un workflow invalide est passé."; exit 1
fi
echo "$OUT" | grep -qF '"runs-on" section is missing' \
  || { echo "ÉCHEC : actionlint ne signale pas l'erreur attendue."; echo "$OUT"; exit 1; }

echo "→ hooks : un marqueur de conflit hors merge git DOIT bloquer le commit"
# Copier (ADR-0001) écrit ses conflits en dehors de tout merge git. Marqueurs assemblés
# à l'exécution : écrits en début de ligne ici, ils bloqueraient ce fichier lui-même.
depot_avec_hooks conflit
printf 'intro\n%s avant\nlocal\n%s\ncorrectif\n%s après\n' '<<<<<<<' '=======' '>>>>>>>' > "$HK/conflit/regle.md"
git -C "$HK/conflit" add regle.md
if OUT=$(git "${GIT_ID[@]}" -C "$HK/conflit" commit -m test 2>&1); then
  echo "ÉCHEC : un fichier contenant des marqueurs de conflit a été commité."; exit 1
fi
echo "$OUT" | grep -qF "Merge conflict string" \
  || { echo "ÉCHEC : refus sans check-merge-conflict."; echo "$OUT"; exit 1; }

echo "→ YAML : une clé dupliquée DOIT échouer (check-yaml)"
depot_avec_hooks doublon
printf 'module:\n  name: a\n  name: b\n' > "$HK/doublon/doublon.yaml"
git -C "$HK/doublon" add doublon.yaml
if OUT=$(cd "$HK/doublon" && pre-commit run check-yaml --files doublon.yaml 2>&1); then
  echo "ÉCHEC : une clé dupliquée est passée."; exit 1
fi
echo "$OUT" | grep -qF 'found duplicate key "name"' \
  || { echo "ÉCHEC : check-yaml ne signale pas la clé dupliquée."; echo "$OUT"; exit 1; }

echo "→ YAML : un placeholder non quoté DOIT échouer (check-yaml)"
depot_avec_hooks gabarit
printf 'module:\n  name: {{MODULE_NAME}}\n' > "$HK/gabarit/gabarit.yaml"
git -C "$HK/gabarit" add gabarit.yaml
if OUT=$(cd "$HK/gabarit" && pre-commit run check-yaml --files gabarit.yaml 2>&1); then
  echo "ÉCHEC : un placeholder non quoté est passé."; exit 1
fi
echo "$OUT" | grep -qF 'found unhashable key' \
  || { echo "ÉCHEC : check-yaml ne signale pas le placeholder."; echo "$OUT"; exit 1; }

echo "→ YAML : une valeur booléenne ambiguë DOIT échouer (yamllint, configuration du dépôt)"
depot_avec_hooks truthy
printf 'actif: yes\n' > "$HK/truthy/regle.yaml"
git -C "$HK/truthy" add regle.yaml
if OUT=$(cd "$HK/truthy" && pre-commit run yamllint --files regle.yaml 2>&1); then
  echo "ÉCHEC : la valeur 'yes' est passée."; exit 1
fi
# Texte du message, pas « (truthy) » : sur GitHub Actions, yamllint passe au format d'annotations.
echo "$OUT" | grep -qF 'truthy value should be one of' \
  || { echo "ÉCHEC : yamllint ne signale pas la règle truthy."; echo "$OUT"; exit 1; }

echo "→ GitHub : dependabot.yml, formulaire et configuration d'issues invalides DOIVENT échouer"
depot_avec_hooks schemas
mkdir -p "$HK/schemas/.github/ISSUE_TEMPLATE"
printf 'version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n' > "$HK/schemas/.github/dependabot.yml"
printf 'name: x\ndescription: y\nbody:\n  - type: input\n' > "$HK/schemas/.github/ISSUE_TEMPLATE/formulaire.yml"
printf 'blank_issues_enabled: "non"\n' > "$HK/schemas/.github/ISSUE_TEMPLATE/config.yml"
git -C "$HK/schemas" add .github
for cas in check-dependabot:.github/dependabot.yml \
           check-github-issue-forms:.github/ISSUE_TEMPLATE/formulaire.yml \
           check-github-issue-config:.github/ISSUE_TEMPLATE/config.yml; do
  hook=${cas%%:*}; fichier=${cas#*:}
  if OUT=$(cd "$HK/schemas" && pre-commit run "$hook" --files "$fichier" 2>&1); then
    echo "ÉCHEC : $fichier invalide accepté par $hook."; exit 1
  fi
  echo "$OUT" | grep -qF "Schema validation errors" \
    || { echo "ÉCHEC : $hook ne signale pas d'erreur de schéma."; echo "$OUT"; exit 1; }
done

echo "Tests plateforme : OK"
