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

echo "→ contrôles M, B, S, P : chaque règle prouve qu'elle échoue et se nomme (pytest, D4)"
pytest -q platform/tests

GIT_ID_RM=(-c user.name=test -c user.email=test@example.invalid)
echo "→ docs : un renvoi vers l'ancien emplacement du manuel (docs/0X-…) DOIT échouer (D6)"
renvois_morts() {  # $1 = racine d'un dépôt git ; affiche les renvois morts, vrai s'il y en a
  git -C "$1" grep -n -E '(^|[^/a-z])docs/0[0-9]-' -- ':!docs/governance/'
}
RM=$(mktemp -d)
git "${GIT_ID_RM[@]}" init -q "$RM"
# Renvoi assemblé à l'exécution : écrit en dur, il serait lui-même détecté dans ce fichier.
printf 'Voir `docs/%s-contrats.md` §4.\n' 03 > "$RM/regle.md"
git -C "$RM" add regle.md
renvois_morts "$RM" >/dev/null || { echo "ÉCHEC : renvoi mort non détecté."; rm -rf "$RM"; exit 1; }
rm -rf "$RM"
if MORTS=$(renvois_morts .); then
  echo "ÉCHEC : renvois vers docs/0X-… ; le manuel vit dans docs/os/ (skeleton/docs/os/ à la racine) :"
  echo "$MORTS"; exit 1
fi

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
mkdir -p "$SK/.nstack"
cp skeleton/.nstack/skills.yaml "$SK/.nstack/"
cp -r skeleton/playbooks "$SK/"
nstack_sk() { (cd / && uv run --project "$REPO" nstack skills --root "$SK" "$@"); }

echo "→ skills : la racine donnée est analysée, quel que soit le dossier courant (D21)"
nstack_sk --check >/dev/null || { echo "ÉCHEC : la racine donnée n'est pas analysée."; exit 1; }

echo "→ skills : une racine sans playbooks ni correspondance n'est pas concernée"
mkdir -p "$SK/vide"
if ! OUT=$(cd / && uv run --project "$REPO" nstack skills --check --root "$SK/vide" 2>&1); then
  echo "ÉCHEC : une racine sans playbooks est refusée."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Skills : non applicable" \
  || { echo "ÉCHEC : racine non concernée sans le dire."; echo "$OUT"; exit 1; }

echo "→ skills : des playbooks sans .nstack/skills.yaml DOIVENT échouer (S1)"
mkdir -p "$SK/vide/playbooks"
printf '# orphelin\n' > "$SK/vide/playbooks/orphelin.md"
if OUT=$(cd / && uv run --project "$REPO" nstack skills --check --root "$SK/vide" 2>&1); then
  echo "ÉCHEC : des playbooks sans correspondance sont passés au vert."; exit 1
fi
echo "$OUT" | grep -qF "[S1] .nstack/skills.yaml introuvable" \
  || { echo "ÉCHEC : message S1 attendu absent."; echo "$OUT"; exit 1; }

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
cp skeleton/playbooks/tests.md "$SK/playbooks/"
nstack_sk >/dev/null
python3 - "$SK" <<'EOF' || exit 1
import sys, yaml
from pathlib import Path
root = Path(sys.argv[1])
skills = yaml.safe_load((root / ".nstack/skills.yaml").read_text(encoding="utf-8"))["skills"]
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
  cp skeleton/.nstack/skills.yaml "$SK/.nstack/"
  python3 - "$SK/.nstack/skills.yaml" "$@" <<'EOF'
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

echo "→ scaffold : module créé sans Makefile, owner org/équipe dans le manifest et CODEOWNERS (D19)"
mkdir -p "$SC/.github" "$SC/modules"
cp .github/CODEOWNERS "$SC/.github/"
uv run nstack new-module demo acme/equipe-demo standard --root "$SC" >/dev/null
python3 - "$SC/modules/demo/MANIFEST.yaml" <<'EOF' || exit 1
import sys, yaml
module = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["module"]
attendu = {"name": "demo", "owner": "acme/equipe-demo", "criticality": "standard"}
if {k: module.get(k) for k in attendu} != attendu:
    sys.exit(f"ÉCHEC : substitutions du gabarit incorrectes : {module!r}")
EOF
[ ! -e "$SC/modules/demo/Makefile" ] || { echo "ÉCHEC : le gabarit impose encore un Makefile (D22)."; exit 1; }
grep -qE '^/modules/demo/ +@acme/equipe-demo$' "$SC/.github/CODEOWNERS" \
  || { echo "ÉCHEC : ligne CODEOWNERS du module absente ou invalide."; exit 1; }
uv run nstack manifests --root "$SC" >/dev/null \
  || { echo "ÉCHEC : le module généré ne passe pas nstack manifests."; exit 1; }

echo "→ scaffold : un owner sans organisation ou un nom invalide DOIVENT être refusés (P6)"
for cas in "demo2|equipe-demo|owner 'equipe-demo' invalide" "Demo|acme/equipe|nom 'Demo' invalide"; do
  IFS='|' read -r nom owner message <<<"$cas"
  if OUT=$(uv run nstack new-module "$nom" "$owner" standard --root "$SC" 2>&1); then
    echo "ÉCHEC : new-module $nom $owner accepté."; exit 1
  fi
  echo "$OUT" | grep -qF "ÉCHEC [new-module] $message" \
    || { echo "ÉCHEC : refus sans message explicatif."; echo "$OUT"; exit 1; }
done

echo "→ verbes : une commande à déclarer DOIT échouer en nommant le module (P1, D22)"
if OUT=$(uv run nstack check demo --root "$SC" 2>&1); then
  echo "ÉCHEC : une commande à déclarer est passée au vert."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "commands.check à déclarer" && echo "$OUT" | grep -qF "ÉCHEC [check] module 'demo'" \
  || { echo "ÉCHEC : échec sans le module ni la commande."; echo "$OUT"; exit 1; }

echo "→ verbes : la commande déclarée s'exécute depuis le dossier du module, quelle que soit la stack"
python3 - "$SC/modules/demo/MANIFEST.yaml" <<'EOF'
import sys, yaml
chemin = sys.argv[1]
data = yaml.safe_load(open(chemin, encoding="utf-8"))
data["commands"] = {"check": "test -f MANIFEST.yaml && echo stack-libre", "test": "true"}
yaml.safe_dump(data, open(chemin, "w", encoding="utf-8"), allow_unicode=True)
EOF
OUT=$(uv run nstack check demo --root "$SC" 2>&1) && echo "$OUT" | grep -qx "stack-libre" \
  || { echo "ÉCHEC : la commande déclarée ne s'exécute pas depuis le module."; echo "$OUT"; exit 1; }

echo "→ verbes : sans module, tous les modules, premier échec nommé"
uv run nstack new-module zeta acme/equipe-zeta standard --root "$SC" >/dev/null
if OUT=$(uv run nstack check --root "$SC" 2>&1); then
  echo "ÉCHEC : un module non déclaré est passé au vert."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qx "stack-libre" && echo "$OUT" | grep -qF "ÉCHEC [check] module 'zeta'" \
  || { echo "ÉCHEC : modules non parcourus ou échec non nommé."; echo "$OUT"; exit 1; }

echo "→ verbes : bootstrap facultatif ; run non déclaré et module inconnu DOIVENT échouer"
uv run nstack bootstrap demo --root "$SC" | grep -qF "rien à préparer" \
  || { echo "ÉCHEC : bootstrap absent mal traité."; exit 1; }
for cas in "run demo|commands.run non déclarée" "test inconnu|module 'inconnu' introuvable"; do
  IFS='|' read -r arguments message <<<"$cas"
  # shellcheck disable=SC2086
  if OUT=$(uv run nstack $arguments --root "$SC" 2>&1); then
    echo "ÉCHEC : nstack $arguments accepté."; exit 1
  fi
  echo "$OUT" | grep -qF "$message" || { echo "ÉCHEC : message « $message » absent."; echo "$OUT"; exit 1; }
done

echo "→ nstack fitness : échoue si l'un des trois contrôles échoue"
FT=$(mktemp -d)
mkdir -p "$FT/.nstack" "$FT/playbooks"
printf 'skills: {}\n' > "$FT/.nstack/skills.yaml"
printf '# orphelin\n' > "$FT/playbooks/orphelin.md"
if OUT=$(uv run nstack fitness --root "$FT" 2>&1); then
  echo "ÉCHEC : un playbook sans entrée est passé au vert."; rm -rf "$FT"; exit 1
fi
echo "$OUT" | grep -qF "[S1]" || { echo "ÉCHEC : S1 attendu."; echo "$OUT"; rm -rf "$FT"; exit 1; }
rm -rf "$FT"

echo "→ nstack pr-scope : répond sur la racine donnée"
uv run nstack pr-scope --root . --base HEAD | grep -qF "No file changed." \
  || { echo "ÉCHEC : nstack pr-scope ne répond pas."; exit 1; }

echo "→ publication : un tag différent de la version du paquet DOIT bloquer (ADR-0002)"
[ -f .github/workflows/release.yml ] || { echo "ÉCHEC : .github/workflows/release.yml absent."; exit 1; }
CONTROLE_TAG=$(python3 - <<'EOF'
import yaml
jobs = yaml.safe_load(open(".github/workflows/release.yml", encoding="utf-8"))["jobs"]
print(next(step["run"] for step in jobs["construction"]["steps"] if step.get("name") == "Tag et version identiques"))
EOF
)
if OUT=$(GITHUB_REF_NAME=v9.9.9 bash -c "$CONTROLE_TAG" 2>&1); then
  echo "ÉCHEC : tag v9.9.9 accepté pour une autre version."; exit 1
fi
echo "$OUT" | grep -qF "Tag v9.9.9 et version" \
  || { echo "ÉCHEC : refus sans message explicatif."; echo "$OUT"; exit 1; }
GITHUB_REF_NAME="v$(uv version --short)" bash -c "$CONTROLE_TAG" >/dev/null \
  || { echo "ÉCHEC : tag conforme refusé."; exit 1; }

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

# Squelette, init et update : projets créés depuis l'arbre de travail, modifications non
# commitées comprises, jamais depuis GitHub. nstack commite : identité git fictive.
GN=$(mktemp -d)
trap 'rm -rf "$SK" "$SC" "$HK" "$GN"' EXIT
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid
# Nom long : Copier écrit .copier-answers.yml sans limite de ligne (nom, chemin du gabarit).
# Le rejeu sur clone vierge l'a montré avec un chemin long ; le nom rend le cas déterministe.
NOM_LONG="Projet démo $(printf 'long%.0s' {1..30})"
REPONSES=(--project-name "$NOM_LONG" --github-repo acme/demo --owner-team acme/plateforme)
PROJET="$GN/projet"

echo "→ init : projet créé et commité sur main, réponses rendues, sans fichier de gabarit"
if ! OUT=$(nstack init "$PROJET" --source "$REPO" --ref HEAD "${REPONSES[@]}" 2>&1); then
  echo "ÉCHEC : nstack init a échoué."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Projet créé dans" \
  || { echo "ÉCHEC : nstack init ne confirme pas la création."; echo "$OUT"; exit 1; }
[ "$(git -C "$PROJET" branch --show-current)" = main ] && [ -z "$(git -C "$PROJET" status --porcelain)" ] \
  || { echo "ÉCHEC : le projet n'est pas commité sur main."; git -C "$PROJET" status; exit 1; }
RESIDUS=$(find "$PROJET" -name '*.jinja')
[ -z "$RESIDUS" ] || { echo "ÉCHEC : fichiers de gabarit copiés tels quels :"; echo "$RESIDUS"; exit 1; }
for attendu in ".github/CODEOWNERS|@acme/plateforme" \
               ".github/ISSUE_TEMPLATE/config.yml|https://github.com/acme/demo/discussions" \
               "contracts/MANIFEST.yaml|owner: acme/plateforme" \
               "README.md|# Projet démo" \
               ".copier-answers.yml|owner_team: acme/plateforme"; do
  fichier=${attendu%%|*}; texte=${attendu#*|}
  grep -qF -- "$texte" "$PROJET/$fichier" 2>/dev/null \
    || { echo "ÉCHEC : $fichier ne contient pas « $texte »."; exit 1; }
done

echo "→ init : le contexte de développement de NapkinStack n'est jamais copié (R6)"
for absent in PRODUCT.md docs/governance platform src pyproject.toml uv.lock copier.yml skeleton; do
  [ ! -e "$PROJET/$absent" ] \
    || { echo "ÉCHEC : $absent copié dans le projet généré (PDR-0001 R6). Le retirer de skeleton/."; exit 1; }
done

echo "→ init : un dossier non vide DOIT être refusé, sans rien y écrire"
mkdir -p "$GN/occupe" && echo garde > "$GN/occupe/garde.txt"
if OUT=$(nstack init "$GN/occupe" --source "$REPO" --ref HEAD "${REPONSES[@]}" 2>&1); then
  echo "ÉCHEC : init dans un dossier non vide accepté."; exit 1
fi
echo "$OUT" | grep -qF "n'est pas vide" \
  || { echo "ÉCHEC : refus sans explication."; echo "$OUT"; exit 1; }
[ "$(ls -A "$GN/occupe")" = garde.txt ] || { echo "ÉCHEC : init a écrit dans le dossier refusé."; exit 1; }

echo "→ init : un dépôt ou une équipe sans organisation DOIT être refusé (P6)"
for question in github_repo owner_team; do
  if [ "$question" = github_repo ]; then
    reponses=(--project-name x --github-repo demo --owner-team acme/plateforme)
  else
    reponses=(--project-name x --github-repo acme/demo --owner-team plateforme)
  fi
  if OUT=$(nstack init "$GN/refus-$question" --source "$REPO" --ref HEAD "${reponses[@]}" 2>&1); then
    echo "ÉCHEC : $question sans « / » accepté."; exit 1
  fi
  echo "$OUT" | grep -qF "ÉCHEC [init] Réponse refusée pour $question" \
    || { echo "ÉCHEC : refus de $question sans message explicatif."; echo "$OUT"; exit 1; }
done

echo "→ init : un gabarit à fonction « unsafe » DOIT être refusé, sans rien créer (ADR-0001)"
UNSAFE="$GN/gabarit-unsafe"
mkdir -p "$UNSAFE" && cp -r copier.yml skeleton "$UNSAFE/"
printf '\n_tasks:\n  - "touch execute"\n' >> "$UNSAFE/copier.yml"
git "${GIT_ID[@]}" init -q "$UNSAFE"
git -C "$UNSAFE" add -A
git "${GIT_ID[@]}" -C "$UNSAFE" commit -q --no-verify -m unsafe
if OUT=$(nstack init "$GN/unsafe" --source "$UNSAFE" --ref HEAD "${REPONSES[@]}" 2>&1); then
  echo "ÉCHEC : gabarit unsafe accepté."; exit 1
fi
echo "$OUT" | grep -qF "ÉCHEC [init] Le gabarit $UNSAFE exécute du code" \
  || { echo "ÉCHEC : refus unsafe sans message explicatif."; echo "$OUT"; exit 1; }
[ ! -e "$GN/unsafe" ] || { echo "ÉCHEC : le gabarit refusé a créé des fichiers."; exit 1; }

echo "→ init : une version de gabarit introuvable DOIT être expliquée (P6)"
if OUT=$(nstack init "$GN/absente" --source "$REPO" --ref v9.9.9 "${REPONSES[@]}" 2>&1); then
  echo "ÉCHEC : version introuvable acceptée."; exit 1
fi
echo "$OUT" | grep -qF "ÉCHEC [init] Gabarit $REPO en version v9.9.9 inaccessible" \
  || { echo "ÉCHEC : version introuvable sans message explicatif."; echo "$OUT"; exit 1; }

echo "→ squelette : hooks et règles YAML identiques à ceux du dépôt (P3)"
for f in .pre-commit-config.yaml .yamllint.yaml; do
  cmp -s "$f" "skeleton/$f" \
    || { echo "ÉCHEC : skeleton/$f diverge de $f. Appliquer le même changement aux deux copies."; exit 1; }
done

echo "→ init : sur clone vierge, le projet passe sa CI sans retouche (critère 1)"
CLONE="$GN/clone"
git clone -q "$PROJET" "$CLONE"
if ! OUT=$(cd "$CLONE" && nstack fitness --root . 2>&1); then
  echo "ÉCHEC : le projet ne passe pas nstack fitness."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Skills : S1, S2 et S4 conformes" \
  || { echo "ÉCHEC : skills non vérifiées dans le projet."; echo "$OUT"; exit 1; }
if ! OUT=$(cd "$CLONE" && SKIP=gitleaks pre-commit run --all-files 2>&1); then
  echo "ÉCHEC : le projet ne passe pas ses hooks."; echo "$OUT"; exit 1
fi
for hook in "Lint GitHub Actions workflow files" "Validate Dependabot Config (v2)" \
            "Validate GitHub issue config" "Validate GitHub issue forms" "zizmor"; do
  echo "$OUT" | grep -F -- "$hook" | grep -qF "Passed" \
    || { echo "ÉCHEC : hook « $hook » non exécuté sur le projet."; echo "$OUT"; exit 1; }
done
if ! OUT=$(cd "$CLONE" && pre-commit run gitleaks-historique --hook-stage manual --all-files 2>&1); then
  echo "ÉCHEC : scan d'historique en échec sur le projet."; echo "$OUT"; exit 1
fi
(cd "$CLONE" && nstack pr-scope --root . --base HEAD) | grep -qF "No file changed." \
  || { echo "ÉCHEC : nstack pr-scope ne répond pas dans le projet."; exit 1; }

echo "→ new-module : dans le projet, le module passe fitness et hooks sans stack imposée (critère 3)"
nstack new-module demo acme/equipe-demo standard --root "$CLONE" >/dev/null
if ! OUT=$(nstack fitness --root "$CLONE" 2>&1); then
  echo "ÉCHEC : le module sans stack ne passe pas les fitness functions."; echo "$OUT"; exit 1
fi
git -C "$CLONE" add -A
if ! OUT=$(cd "$CLONE" && SKIP=gitleaks pre-commit run 2>&1); then
  echo "ÉCHEC : le module généré ne passe pas les hooks du projet."; echo "$OUT"; exit 1
fi

# Mises à jour : gabarit jetable à trois versions, construit depuis l'arbre de travail.
TPL="$GN/gabarit"
mkdir -p "$TPL" && cp -r copier.yml skeleton "$TPL/"
git "${GIT_ID[@]}" init -q "$TPL"
version_gabarit() {  # $1 = tag, les modifications du gabarit étant faites
  git -C "$TPL" add -A
  git "${GIT_ID[@]}" -C "$TPL" commit -q --no-verify -m "$1"
  git -C "$TPL" tag "$1"
}
version_gabarit v0.1.0
printf '\nCorrectif v0.2, en fin de fichier.\n' >> "$TPL/skeleton/playbooks/tests.md"
printf '\nCorrectif v0.2.\n' >> "$TPL/skeleton/docs/pdr/_TEMPLATE.md"
printf '\nCorrectif v0.2.\n' >> "$TPL/skeleton/modules/README.md"
version_gabarit v0.2.0
sed -i '1s/.*/# Sécurité — titre v0.3/' "$TPL/skeleton/playbooks/securite.md"
version_gabarit v0.3.0
projet_v01() {
  nstack init "$1" --source "$TPL" --ref v0.1.0 "${REPONSES[@]}" >/dev/null \
    || { echo "ÉCHEC : nstack init depuis le gabarit jetable ($1)."; exit 1; }
}
commit_projet() { git -C "$1" add -A && git "${GIT_ID[@]}" -C "$1" commit -q --no-verify -m "$2"; }

A="$GN/projet-a"
projet_v01 "$A"
sed -i '1s/.*/# Tests — adaptation locale/' "$A/playbooks/tests.md"
rm "$A/docs/pdr/_TEMPLATE.md"
nstack new-module demo acme/equipe-demo standard --root "$A" >/dev/null
commit_projet "$A" "Adaptations et premier module"
MODULE_AVANT=$(git -C "$A" rev-parse HEAD:modules/demo)

echo "→ update : correctif et adaptation fusionnés, commités sur une branche (critère 4)"
if ! OUT=$(nstack update --root "$A" --ref v0.2.0 2>&1); then
  echo "ÉCHEC : nstack update a échoué."; echo "$OUT"; exit 1
fi
[ "$(git -C "$A" branch --show-current)" = nstack/update-v0.2.0 ] && [ -z "$(git -C "$A" status --porcelain)" ] \
  || { echo "ÉCHEC : mise à jour non commitée sur nstack/update-v0.2.0."; git -C "$A" status; exit 1; }
[ "$(head -1 "$A/playbooks/tests.md")" = "# Tests — adaptation locale" ] \
  && grep -qF "Correctif v0.2, en fin de fichier." "$A/playbooks/tests.md" \
  || { echo "ÉCHEC : adaptation ou correctif perdu dans playbooks/tests.md."; exit 1; }
grep -qF "_commit: v0.2.0" "$A/.copier-answers.yml" \
  || { echo "ÉCHEC : version du projet non montée."; exit 1; }
echo "$OUT" | grep -qF "git push -u origin nstack/update-v0.2.0" \
  || { echo "ÉCHEC : étape suivante absente."; echo "$OUT"; exit 1; }

echo "→ update : un fichier supprimé par l'équipe n'est pas recréé (critère 6)"
[ ! -e "$A/docs/pdr/_TEMPLATE.md" ] || { echo "ÉCHEC : fichier supprimé recréé."; exit 1; }

echo "→ update : aucun fichier de module modifié, le README du squelette suit (critère 7)"
[ "$(git -C "$A" rev-parse HEAD:modules/demo)" = "$MODULE_AVANT" ] \
  || { echo "ÉCHEC : modules/demo modifié par la mise à jour (PDR-0001 R4)."; exit 1; }
grep -qF "Correctif v0.2." "$A/modules/README.md" \
  || { echo "ÉCHEC : modules/README.md n'a pas suivi la version."; exit 1; }

echo "→ update : un projet déjà à jour ne crée pas de branche"
if ! OUT=$(nstack update --root "$A" --ref v0.2.0 2>&1); then
  echo "ÉCHEC : projet à jour refusé."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Déjà à jour" \
  && [ "$(git -C "$A" branch --list 'nstack/*' | wc -l)" -eq 1 ] \
  || { echo "ÉCHEC : projet à jour mal traité."; echo "$OUT"; exit 1; }

echo "→ update : une version antérieure DOIT être refusée, sans rien modifier"
if OUT=$(nstack update --root "$A" --ref v0.1.0 2>&1); then
  echo "ÉCHEC : retour arrière accepté."; exit 1
fi
echo "$OUT" | grep -qF "antérieure à celle du projet (0.2.0)" \
  && [ -z "$(git -C "$A" status --porcelain)" ] \
  || { echo "ÉCHEC : retour arrière mal refusé."; echo "$OUT"; exit 1; }

echo "→ update : un arbre de travail modifié DOIT être refusé, sans rien modifier"
echo "modification locale" >> "$A/README.md"
if OUT=$(nstack update --root "$A" --ref v0.3.0 2>&1); then
  echo "ÉCHEC : mise à jour acceptée sur un arbre modifié."; exit 1
fi
echo "$OUT" | grep -qF "ÉCHEC [update] Arbre de travail modifié" \
  && [ "$(git -C "$A" diff --name-only)" = README.md ] \
  && ! git -C "$A" rev-parse --verify --quiet refs/heads/nstack/update-v0.3.0 >/dev/null \
  || { echo "ÉCHEC : arbre modifié mal refusé."; echo "$OUT"; exit 1; }
git -C "$A" checkout -q -- README.md

echo "→ update : hors d'un projet, la commande DOIT l'expliquer"
if OUT=$(nstack update --root "$GN/occupe" 2>&1); then
  echo "ÉCHEC : update accepté hors d'un projet."; exit 1
fi
echo "$OUT" | grep -qF "ÉCHEC [update] .copier-answers.yml introuvable" \
  || { echo "ÉCHEC : message attendu absent."; echo "$OUT"; exit 1; }

B="$GN/projet-b"
projet_v01 "$B"
sed -i '1s/.*/# Sécurité — adaptation locale/' "$B/playbooks/securite.md"
commit_projet "$B" "Adaptation"

echo "→ update : versions sautées d'un coup, conflit marqué et laissé à l'équipe (critère 5)"
if OUT=$(nstack update --root "$B" --ref v0.3.0 2>&1); then
  echo "ÉCHEC : conflit passé sous silence."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "ÉCHEC [update] NapkinStack v0.1.0 → v0.3.0 : conflits" \
  && echo "$OUT" | grep -qF "  - playbooks/securite.md" \
  || { echo "ÉCHEC : conflit sans liste des fichiers."; echo "$OUT"; exit 1; }
[ "$(git -C "$B" branch --show-current)" = nstack/update-v0.3.0 ] \
  && [ "$(git -C "$B" rev-parse HEAD)" = "$(git -C "$B" rev-parse main)" ] \
  && grep -qF "Correctif v0.2, en fin de fichier." "$B/playbooks/tests.md" \
  || { echo "ÉCHEC : branche, commit ou version sautée incorrects."; exit 1; }

echo "→ update : le commit reste refusé tant qu'un marqueur subsiste (critère 5)"
(cd "$B" && pre-commit install >/dev/null)
git -C "$B" add -A
if OUT=$(git "${GIT_ID[@]}" -C "$B" commit -m "Mise à jour" 2>&1); then
  echo "ÉCHEC : un conflit de mise à jour a été commité."; exit 1
fi
echo "$OUT" | grep -qF "Merge conflict string" \
  || { echo "ÉCHEC : refus sans check-merge-conflict."; echo "$OUT"; exit 1; }

# Doctor : API GitHub simulée, jamais la vraie. Réponses recopiées de celles du dépôt
# NapkinStack, puis dégradées : dépôt nu, jeton sans permission Administration.
API="$GN/api"
mkdir -p "$API"
python3 - "$API/routes.json" <<'EOF'
import json, sys
regles = [
    {"type": "pull_request", "parameters": {"required_approving_review_count": 1, "require_code_owner_review": True}},
    {"type": "required_status_checks", "parameters": {"required_status_checks": [
        {"context": "Fitness functions"}, {"context": "Périmètre et budget de revue"}, {"context": "Hooks et secrets"}]}},
]
labels = {"/labels/cross-module": {"name": "cross-module"}, "/labels/hors-budget": {"name": "hors-budget"}}
active = {"status": "enabled"}
conforme = {
    "": {"security_and_analysis": {"secret_scanning": active, "secret_scanning_push_protection": active}},
    "/rules/branches/main": regles,
    "/private-vulnerability-reporting": {"enabled": True},
    "/actions/permissions": {"enabled": True, "allowed_actions": "selected", "sha_pinning_required": True},
    "/actions/permissions/selected-actions": {"github_owned_allowed": True, "patterns_allowed": ["astral-sh/setup-uv@*"]},
    "/actions/permissions/fork-pr-contributor-approval": {"approval_policy": "all_external_contributors"},
    "/actions/permissions/workflow": {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
    **labels,
}
inactive = {"status": "disabled"}
nu = {
    "": {"security_and_analysis": {"secret_scanning": inactive, "secret_scanning_push_protection": inactive}},
    "/rules/branches/main": [],
    "/private-vulnerability-reporting": {"enabled": False},
    "/actions/permissions": {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False},
    "/actions/permissions/fork-pr-contributor-approval": {"approval_policy": "first_time_contributors"},
    "/actions/permissions/workflow": {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True},
}
restreint = {"": {}, "/rules/branches/main": regles, **labels}
conforme[""]["visibility"] = "public"
nu[""]["visibility"] = "public"
actions = {chemin: reponse for chemin, reponse in conforme.items() if chemin.startswith("/actions/")}
prive = {
    "": {"visibility": "private", "security_and_analysis": {"secret_scanning": inactive, "secret_scanning_push_protection": inactive}},
    "/rules/branches/main": [],
    **actions, **labels,
}
prive_team = {chemin: reponse for chemin, reponse in conforme.items() if chemin != "/private-vulnerability-reporting"}
prive_team[""] = {**conforme[""], "visibility": "private"}
json.dump({"acme/conforme": conforme, "acme/nu": nu, "acme/restreint": restreint,
           "acme/prive": prive, "acme/prive-team": prive_team}, open(sys.argv[1], "w"))
EOF
cat > "$API/serveur.py" <<'EOF'
import http.server, json, pathlib, sys
routes = json.loads(pathlib.Path(sys.argv[1]).read_text())
class API(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        statut, corps = 404, {"message": "Not Found"}
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            statut, corps = 401, {"message": "Requires authentication"}
        elif self.path.startswith("/repos/"):
            owner, name, *reste = self.path.removeprefix("/repos/").split("/")
            depot, chemin = f"{owner}/{name}", ("/" + "/".join(reste)) if reste else ""
            if chemin in routes.get(depot, {}):
                statut, corps = 200, routes[depot][chemin]
            elif depot == "acme/restreint" and not chemin.startswith("/labels/"):
                statut, corps = 403, {"message": "Resource not accessible by personal access token"}
        self.send_response(statut)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(corps).encode())
    def log_message(self, *args):
        pass
serveur = http.server.HTTPServer(("127.0.0.1", 0), API)
pathlib.Path(sys.argv[2]).write_text(str(serveur.server_port))
serveur.serve_forever()
EOF
python3 "$API/serveur.py" "$API/routes.json" "$API/port" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null; rm -rf "$SK" "$SC" "$HK" "$GN"' EXIT
for _ in $(seq 50); do [ -s "$API/port" ] && break; sleep 0.1; done
export GITHUB_API_URL="http://127.0.0.1:$(cat "$API/port")"

V=$(nstack --version | cut -d' ' -f2)
# Tag de la version du moteur ; il existe déjà si elle coïncide avec une version du gabarit jetable.
if ! git -C "$TPL" rev-parse -q --verify "refs/tags/v$V" >/dev/null; then
  git "${GIT_ID[@]}" -C "$TPL" commit -q --allow-empty --no-verify -m "v$V"
  git -C "$TPL" tag "v$V"
fi
C="$GN/projet-c"
INIT_OUT=$(nstack init "$C" --source "$TPL" --ref "v$V" --project-name "Projet C" \
  --github-repo acme/conforme --owner-team acme/plateforme 2>&1) \
  || { echo "ÉCHEC : nstack init du projet C."; echo "$INIT_OUT"; exit 1; }
depot_c() { sed -i "s#^github_repo: .*#github_repo: $1#" "$C/.copier-answers.yml"; }

echo "→ init : checklist GitHub affichée, identique au README du squelette et aux jobs de la CI"
[ "$(echo "$INIT_OUT" | grep -cF -- '- [ ] ')" -eq 11 ] && echo "$INIT_OUT" | grep -qF "nstack doctor" \
  || { echo "ÉCHEC : checklist absente de la sortie d'init."; echo "$INIT_OUT"; exit 1; }
echo "$INIT_OUT" | grep -F -- '- [ ] ' | sed 's/^ *//' | while IFS= read -r ligne; do
  grep -qF -- "$ligne" skeleton/README.md.jinja \
    || { echo "ÉCHEC : « $ligne » absent du README du squelette."; exit 1; }
done
python3 - "$(echo "$INIT_OUT" | grep -F 'Checks obligatoires')" <<'EOF' || exit 1
import sys, yaml
jobs = yaml.safe_load(open("skeleton/.github/workflows/governance.yml", encoding="utf-8"))["jobs"]
absents = [job["name"] for job in jobs.values() if f"`{job['name']}`" not in sys.argv[1]]
if absents:
    sys.exit(f"ÉCHEC : jobs de la CI du squelette absents de la checklist (G4) : {absents}")
EOF

echo "→ doctor : écarts du poste listés avec leur action (L1, L3, L4, L5)"
echo "# Produit" > "$A/PRODUCT.md"
if OUT=$(GH_TOKEN=jeton-factice nstack doctor --root "$A" 2>&1); then
  echo "ÉCHEC : poste non conforme accepté."; echo "$OUT"; exit 1
fi
for regle in L1 L3 L4 L5; do
  echo "$OUT" | grep -qE "ÉCHEC +\[$regle\]" \
    || { echo "ÉCHEC : écart $regle non signalé."; echo "$OUT"; exit 1; }
done
echo "$OUT" | grep -qF "Action : pre-commit install" \
  || { echo "ÉCHEC : action de L3 absente."; echo "$OUT"; exit 1; }
rm "$A/PRODUCT.md"

(cd "$C" && pre-commit install >/dev/null)
sed -i 's#<Une phrase : ce que fait ce projet.>#Projet de démonstration.#' "$C/README.md"

echo "→ doctor : dépôt GitHub sans réglages, chaque écart listé avec son action (critère 2)"
depot_c acme/nu
if OUT=$(GH_TOKEN=jeton-factice nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : dépôt sans réglages accepté."; echo "$OUT"; exit 1
fi
for regle in G1 G2 G3 G4 G5 G6 G7 G8 G9 G10 G11; do
  echo "$OUT" | grep -qE "ÉCHEC +\[$regle\]" \
    || { echo "ÉCHEC : écart $regle non signalé."; echo "$OUT"; exit 1; }
done
[ "$(echo "$OUT" | grep -cF 'Action : Settings')" -ge 10 ] && echo "$OUT" | grep -qE "OK +\[L1\]" \
  || { echo "ÉCHEC : actions ou poste incorrects."; echo "$OUT"; exit 1; }

echo "→ doctor : checklist appliquée, la commande sort en succès (critère 2)"
depot_c acme/conforme
if ! OUT=$(GH_TOKEN=jeton-factice nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : projet conforme refusé."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "nstack doctor : conforme." && [ "$(echo "$OUT" | grep -cE '^  OK +\[')" -eq 16 ] \
  || { echo "ÉCHEC : conformité mal rapportée."; echo "$OUT"; exit 1; }

echo "→ doctor : dépôt privé sur l'offre Free, écarts nommant l'offre requise, signalement non applicable"
depot_c acme/prive
if OUT=$(GH_TOKEN=jeton-factice nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : dépôt privé sans barrière accepté."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "NON APPLICABLE +\[G6\]" \
  && [ "$(echo "$OUT" | grep -cF 'offre GitHub Team')" -eq 4 ] \
  && echo "$OUT" | grep -qF "Secret Protection est une option payante" \
  && echo "$OUT" | grep -qE "OK +\[G7\]" \
  || { echo "ÉCHEC : dépôt privé sur l'offre Free mal rapporté."; echo "$OUT"; exit 1; }

echo "→ doctor : dépôt privé sous GitHub Team, conforme sans signalement privé"
depot_c acme/prive-team
if ! OUT=$(GH_TOKEN=jeton-factice nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : dépôt privé conforme refusé."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "nstack doctor : conforme" && echo "$OUT" | grep -qE "NON APPLICABLE +\[G6\]" \
  && [ "$(echo "$OUT" | grep -cE '^  OK +\[')" -eq 15 ] \
  || { echo "ÉCHEC : dépôt privé conforme mal rapporté."; echo "$OUT"; exit 1; }

echo "→ doctor : sans jeton, la partie GitHub est non vérifiée, jamais conforme"
if OUT=$(env -u GH_TOKEN -u GITHUB_TOKEN nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : conforme sans jeton."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "NON VÉRIFIÉ +\[G11\]" && ! echo "$OUT" | grep -qE "OK +\[G" \
  && echo "$OUT" | grep -qF "GH_TOKEN" \
  || { echo "ÉCHEC : absence de jeton mal traitée."; echo "$OUT"; exit 1; }

echo "→ doctor : jeton sans permission Administration, les réglages illisibles sont non vérifiés"
depot_c acme/restreint
if OUT=$(GH_TOKEN=jeton-factice nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : conforme sans permission Administration."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "OK +\[G1\]" && echo "$OUT" | grep -qE "NON VÉRIFIÉ +\[G5\]" \
  && echo "$OUT" | grep -qE "NON VÉRIFIÉ +\[G8\]" && echo "$OUT" | grep -qF "Administration : lecture" \
  || { echo "ÉCHEC : permission manquante mal traitée."; echo "$OUT"; exit 1; }

echo "→ doctor : API injoignable, rien n'est déclaré conforme"
if OUT=$(GITHUB_API_URL=http://127.0.0.1:9 GH_TOKEN=jeton-factice nstack doctor --root "$C" 2>&1); then
  echo "ÉCHEC : conforme sans API."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "NON VÉRIFIÉ +\[G1\]" && echo "$OUT" | grep -qF "injoignable" \
  || { echo "ÉCHEC : API injoignable mal traitée."; echo "$OUT"; exit 1; }

echo "→ doctor : hors d'un projet, la commande DOIT l'expliquer"
if OUT=$(nstack doctor --root "$GN/occupe" 2>&1); then
  echo "ÉCHEC : doctor accepté hors d'un projet."; exit 1
fi
echo "$OUT" | grep -qF "ÉCHEC [doctor] .copier-answers.yml introuvable" \
  || { echo "ÉCHEC : message attendu absent."; echo "$OUT"; exit 1; }

echo "Tests plateforme : OK"
