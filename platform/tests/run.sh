#!/usr/bin/env bash
# Tests of the fitness functions. The oracle of the guardrails themselves.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$(pwd)
# sed that edits a file where it is, on GNU and on BSD alike: `sed -i` alone is GNU's, and a
# Mac's sed takes the next word for a backup's suffix (D99).
in_place() { local file=${!#}; sed -i.bak "$@" && rm -f "$file.bak"; }

# Every repository this suite creates is thrown away within seconds, and git's automatic
# maintenance has no business running inside one: it writes into .git/objects/pack while a
# temporary clone is being removed. Seen once on CI as "[Errno 39] Directory not empty:
# 'pack'" during an update, never reproduced locally (D64). Disabled through the
# environment, so no machine configuration is touched — and justified on its own terms,
# whatever that failure turns out to have been.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=gc.auto GIT_CONFIG_VALUE_0=0

echo "-> nstack: the command responds and prints its version"
uv run nstack --version | grep -qE '^nstack [0-9]+\.[0-9]+' \
  || { echo "FAIL: nstack --version does not respond."; exit 1; }

echo "-> repository manifests compliant"
uv run nstack manifests --root .

echo "-> repository boundaries compliant"
uv run nstack boundaries --root .

echo "-> repository free of paths from one person's machine (H1)"
uv run nstack hygiene --root .

echo "-> rules M, B, S, P, H: every rule proves it fails and names itself (pytest, D4)"
pytest -q platform/tests

GIT_ID_RM=(-c user.name=test -c user.email=test@example.invalid)
echo "-> docs: a link to the handbook's old location (docs/NN-...) MUST fail (D6)"
dead_links() {  # $1 = root of a git repository; prints the dead links, true when there are any
  git -C "$1" grep -n -E '(^|[^/a-z])docs/[0-9][0-9]-' -- ':!docs/governance/'
}
RM=$(mktemp -d)
git "${GIT_ID_RM[@]}" init -q "$RM"
# Links assembled at run time: written literally, they would be detected in this file itself.
printf 'See `docs/%s-contracts.md` §4.\n' 03 > "$RM/rule.md"
printf 'See `docs/%s-measurement.md`.\n' 10 > "$RM/late.md"
git -C "$RM" add rule.md late.md
[ "$(dead_links "$RM" | wc -l)" -eq 2 ] \
  || { echo "FAIL: dead link not detected."; dead_links "$RM"; rm -rf "$RM"; exit 1; }
rm -rf "$RM"
if DEAD=$(dead_links .); then
  echo "FAIL: links to docs/NN-...; the handbook lives in .nstack/handbook/ (skeleton/.nstack/handbook/ at the root):"
  echo "$DEAD"; exit 1
fi

echo "-> kernel: over its 250-line budget MUST fail (P4)"
within_budget() { [ "$(wc -l < "$1")" -le 250 ]; }
KB=$(mktemp)
seq 251 > "$KB"
if within_budget "$KB"; then echo "FAIL: a 251-line kernel passed the budget."; rm -f "$KB"; exit 1; fi
rm -f "$KB"
within_budget skeleton/AGENTS.md \
  || { echo "FAIL: skeleton/AGENTS.md has $(wc -l < skeleton/AGENTS.md) lines, over 250 (P4). Move a rule to a playbook, or to CI."; exit 1; }

echo "-> changelog: every published version has its section (D62)"
MISSING=""
for tag in $(git tag -l 'v*'); do
  grep -qE "^## ${tag}( |$)" CHANGELOG.md || MISSING="$MISSING $tag"
done
[ -z "$MISSING" ] \
  || { echo "FAIL: no CHANGELOG section for:$MISSING. A published version nobody can read"; \
       echo "      before taking it is what D62 is about."; exit 1; }

echo "-> front page: every version it names is the one being published"
# The front page is the registry's page, frozen at the tag. v0.7.0 went out saying
# "Status: v0.6.2": the page was corrected in the pull request after the release.
names_only() { ! grep -oE "(Status: |engineering-os@)v[0-9]+\.[0-9]+\.[0-9]+" "$1" | grep -vE "v$2\$" | grep -q .; }
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
FP=$(mktemp)
sed "s/engineering-os@v$VERSION/engineering-os@v0.0.1/" README.md > "$FP"
if names_only "$FP" "$VERSION"; then echo "FAIL: a front page pinning another version passed."; rm -f "$FP"; exit 1; fi
rm -f "$FP"
grep -qE "Status: v$VERSION" README.md && names_only README.md "$VERSION" \
  || { echo "FAIL: README.md names another version than $VERSION, which pyproject.toml declares."; \
       echo "      Action: in the version pull request, align its status line and its install lines."; exit 1; }

echo "-> an invalid manifest MUST fail"
TMP=$(mktemp -d)
mkdir -p "$TMP/modules/broken"
printf 'module:\n  name: broken\n' > "$TMP/modules/broken/MANIFEST.yaml"
if OUT=$(cd / && uv run --project "$REPO" nstack manifests --root "$TMP" 2>&1); then
  echo "FAIL: an incomplete manifest went green."; rm -rf "$TMP"; exit 1
fi
echo "$OUT" | grep -qF "[M2] broken" \
  || { echo "FAIL: expected M2 message missing."; echo "$OUT"; rm -rf "$TMP"; exit 1; }
rm -rf "$TMP"

# Skills: every fixture is a throwaway copy, the real .claude/ is never touched.
SK=$(mktemp -d)
trap 'rm -rf "$SK"' EXIT
mkdir -p "$SK/.nstack"
cp skeleton/.nstack/skills.yaml "$SK/.nstack/"
cp -r skeleton/.nstack/playbooks "$SK/.nstack/"
nstack_sk() { (cd / && uv run --project "$REPO" nstack skills --root "$SK" "$@"); }

echo "-> skills: the given root is analysed, whatever the current folder (D21)"
nstack_sk --check >/dev/null || { echo "FAIL: the given root is not analysed."; exit 1; }

echo "-> skills: a root with neither playbooks nor a mapping is out of scope"
mkdir -p "$SK/empty"
if ! OUT=$(cd / && uv run --project "$REPO" nstack skills --check --root "$SK/empty" 2>&1); then
  echo "FAIL: a root without playbooks is refused."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Skills: not applicable" \
  || { echo "FAIL: out-of-scope root not stated as such."; echo "$OUT"; exit 1; }

echo "-> skills: playbooks without .nstack/skills.yaml MUST fail (S1)"
mkdir -p "$SK/empty/.nstack/playbooks"
printf '# orphan\n' > "$SK/empty/.nstack/playbooks/orphan.md"
if OUT=$(cd / && uv run --project "$REPO" nstack skills --check --root "$SK/empty" 2>&1); then
  echo "FAIL: playbooks without a mapping went green."; exit 1
fi
echo "$OUT" | grep -qF "[S1] .nstack/skills.yaml not found" \
  || { echo "FAIL: expected S1 message missing."; echo "$OUT"; exit 1; }

echo "-> skills: on a fresh clone, S3 is not applicable and the check passes"
if ! OUT=$(nstack_sk --check 2>&1); then
  echo "FAIL: --check fails although no skill was generated."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "S3 not applicable" \
  || { echo "FAIL: S3 skipped without saying so."; echo "$OUT"; exit 1; }

echo "-> skills: an out-of-sync skill MUST fail"
nstack_sk >/dev/null
echo "added" >> "$SK/.nstack/playbooks/tests.md"
if OUT=$(nstack_sk --check 2>&1); then
  echo "FAIL: an out-of-sync skill went green."; exit 1
fi
echo "$OUT" | grep -qF "[S3] skill 'tests' out of sync" \
  || { echo "FAIL: expected S3 message missing."; echo "$OUT"; exit 1; }

echo "-> skills: a deleted skill MUST fail"
nstack_sk >/dev/null
rm "$SK/.claude/skills/ux/SKILL.md"
if OUT=$(nstack_sk --check 2>&1); then
  echo "FAIL: a deleted skill went green."; exit 1
fi
echo "$OUT" | grep -qF "[S3] skill 'ux' missing" \
  || { echo "FAIL: expected S3 message missing."; echo "$OUT"; exit 1; }

echo "-> skills: the generated frontmatter is valid YAML and returns name and description"
cp skeleton/.nstack/playbooks/tests.md "$SK/.nstack/playbooks/"
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
        sys.exit(f"FAIL: frontmatter of '{name}' invalid: {exc}")
    if meta != {"name": name, "description": " ".join(entry["description"].split())}:
        sys.exit(f"FAIL: the frontmatter of '{name}' does not return name and description: {meta!r}")
EOF

# S4: the "tests" skill is renamed, or its description replaced, in a copy of
# skills.yaml. Without .claude/skills/, S3 does not apply: only S4 can fail.
modified_tests_skill() {  # $1 = name, $2 = description length (optional)
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

echo "-> skills: a name outside the Agent Skills specification MUST fail (S4)"
for name in Uppercase -leading trailing- double--hyphen under_score "${A64}a"; do
  modified_tests_skill "$name"
  if OUT=$(nstack_sk --check 2>&1); then
    echo "FAIL: invalid skill name accepted: '$name'."; exit 1
  fi
  echo "$OUT" | grep -qF "[S4] skill '$name'" \
    || { echo "FAIL: expected S4 message missing for '$name'."; echo "$OUT"; exit 1; }
done

echo "-> skills: a description longer than 1024 characters MUST fail (S4)"
modified_tests_skill tests 1025
if OUT=$(nstack_sk --check 2>&1); then
  echo "FAIL: a 1025-character description was accepted."; exit 1
fi
echo "$OUT" | grep -qF "[S4] skill 'tests'" \
  || { echo "FAIL: expected S4 message missing."; echo "$OUT"; exit 1; }

echo "-> skills: a 64-character name and a 1024-character description are accepted"
modified_tests_skill "$A64" 1024
nstack_sk --check >/dev/null \
  || { echo "FAIL: specification limits refused."; exit 1; }

# Scaffolding: throwaway copy, the real repository is never touched.
SC=$(mktemp -d)
trap 'rm -rf "$SK" "$SC"' EXIT

echo "-> scaffolding: module created without a Makefile, owner org/team in the manifest and CODEOWNERS (D19)"
mkdir -p "$SC/.github" "$SC/modules"
cp .github/CODEOWNERS "$SC/.github/"
uv run nstack new-module demo acme/demo-team standard --root "$SC" >/dev/null
python3 - "$SC/modules/demo/MANIFEST.yaml" <<'EOF' || exit 1
import sys, yaml
module = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["module"]
expected = {"name": "demo", "owner": "acme/demo-team", "criticality": "standard"}
if {k: module.get(k) for k in expected} != expected:
    sys.exit(f"FAIL: template substitutions incorrect: {module!r}")
EOF
[ ! -e "$SC/modules/demo/Makefile" ] || { echo "FAIL: the template still imposes a Makefile (D22)."; exit 1; }
grep -qE '^/modules/demo/ +@acme/demo-team$' "$SC/.github/CODEOWNERS" \
  || { echo "FAIL: module CODEOWNERS line missing or invalid."; exit 1; }
uv run nstack manifests --root "$SC" >/dev/null \
  || { echo "FAIL: the generated module does not pass nstack manifests."; exit 1; }

echo "-> scaffolding: an owner without an organisation or an invalid name MUST be refused (P6)"
for case in "demo2|team-|invalid owner 'team-'" "Demo|acme/team|invalid name 'Demo'"; do
  IFS='|' read -r name owner message <<<"$case"
  if OUT=$(uv run nstack new-module "$name" "$owner" standard --root "$SC" 2>&1); then
    echo "FAIL: new-module $name $owner accepted."; exit 1
  fi
  echo "$OUT" | grep -qF "FAIL [new-module] $message" \
    || { echo "FAIL: refusal without an explanatory message."; echo "$OUT"; exit 1; }
done

echo "-> verbs: a module holding only its description has nothing to check yet (D33)"
for verb in check test; do
  OUT=$(uv run nstack "$verb" demo --root "$SC" 2>&1) \
    && echo "$OUT" | grep -qF "demo: holds only its description, nothing to $verb yet" \
    || { echo "FAIL: nstack $verb on a new module is not green."; echo "$OUT"; exit 1; }
done

echo "-> verbs: a module holding code with no check declared MUST fail while naming it (P1, D22)"
printf 'code\n' > "$SC/modules/demo/src/app.txt"
if OUT=$(uv run nstack check demo --root "$SC" 2>&1); then
  echo "FAIL: a module holding code with no check went green."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "FAIL [check] module 'demo': commands.check not declared" \
  || { echo "FAIL: failure without the module or the command."; echo "$OUT"; exit 1; }

echo "-> verbs: the declared command runs from the module folder, whatever the stack"
python3 - "$SC/modules/demo/MANIFEST.yaml" <<'EOF'
import sys, yaml
path = sys.argv[1]
data = yaml.safe_load(open(path, encoding="utf-8"))
data["commands"] = {"check": "test -f MANIFEST.yaml && echo stack-free", "test": "true"}
yaml.safe_dump(data, open(path, "w", encoding="utf-8"), allow_unicode=True)
EOF
OUT=$(uv run nstack check demo --root "$SC" 2>&1) && echo "$OUT" | grep -qx "stack-free" \
  || { echo "FAIL: the declared command does not run from the module."; echo "$OUT"; exit 1; }

echo "-> verbs: with no module, all modules, first failure named"
uv run nstack new-module zeta acme/team-zeta standard --root "$SC" >/dev/null
printf 'code\n' > "$SC/modules/zeta/src/app.txt"
if OUT=$(uv run nstack check --root "$SC" 2>&1); then
  echo "FAIL: an undeclared module went green."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qx "stack-free" && echo "$OUT" | grep -qF "FAIL [check] module 'zeta'" \
  || { echo "FAIL: modules not walked, or failure not named."; echo "$OUT"; exit 1; }

echo "-> verbs: bootstrap, e2e and clean optional; an undeclared run and an unknown module MUST fail"
uv run nstack bootstrap demo --root "$SC" | grep -qF "nothing to prepare" \
  || { echo "FAIL: missing bootstrap mishandled."; exit 1; }
uv run nstack e2e demo --root "$SC" | grep -qF "no end-to-end scenario" \
  || { echo "FAIL: missing e2e mishandled."; exit 1; }
uv run nstack clean demo --root "$SC" | grep -qF "nothing to clean" \
  || { echo "FAIL: missing clean mishandled."; exit 1; }
for case in "run demo|commands.run not declared" "test unknown|module 'unknown' not found"; do
  IFS='|' read -r arguments message <<<"$case"
  # shellcheck disable=SC2086
  if OUT=$(uv run nstack $arguments --root "$SC" 2>&1); then
    echo "FAIL: nstack $arguments accepted."; exit 1
  fi
  echo "$OUT" | grep -qF "$message" || { echo "FAIL: message "$message" missing."; echo "$OUT"; exit 1; }
done

echo "-> CI engine: a published version from PyPI, anything else from the repository, announced (PDR-0005)"
EI=$(mktemp -d)
mkdir -p "$EI/bin" "$EI/project/.nstack"
cp skeleton/.nstack/install-engine.sh "$EI/project/.nstack/"
printf '#!/usr/bin/env python3\nimport sys, yaml\nprint(yaml.safe_load(open(sys.argv[2]))[sys.argv[1][1:]])\n' > "$EI/bin/yq"
printf '#!/usr/bin/env bash\necho "uv $*"; [ -z "${UV_FAILS:-}" ]\n' > "$EI/bin/uv"
chmod +x "$EI/bin/yq" "$EI/bin/uv"
engine() {  # $1 = _commit, $2 = _src_path; prints what CI would run
  printf '_commit: %s\n_src_path: %s\n' "$1" "$2" > "$EI/project/.copier-answers.yml"
  (cd "$EI/project" && PATH="$EI/bin:$PATH" bash .nstack/install-engine.sh 2>&1)
}
# The script reads the answers file itself: a runner holding another yq, or none, installs
# the right engine all the same (a runner with the wrong yq was told its source was a path).
! grep -qw yq skeleton/.nstack/install-engine.sh \
  || { echo "FAIL: install-engine.sh needs yq to read two lines of the answers file."; exit 1; }
rm "$EI/bin/yq"
URL=https://github.com/NapkinStack/engineering-os.git
printf "_commit: 'v0.4.0'\n_src_path: '%s'\n" "$URL" > "$EI/project/.copier-answers.yml"
(cd "$EI/project" && PATH="$EI/bin:$PATH" bash .nstack/install-engine.sh 2>&1) \
  | grep -qxF 'uv tool install napkinstack==0.4.0 --with-executables-from pre-commit' \
  || { echo "FAIL: a quoted answer is not read."; exit 1; }
engine v0.4.0 "$URL" | grep -qxF 'uv tool install napkinstack==0.4.0 --with-executables-from pre-commit' \
  || { echo "FAIL: a published version is not installed from PyPI."; engine v0.4.0 "$URL"; exit 1; }
OUT=$(engine v0.4.0-3-g1a2b3c4 "$URL")
echo "$OUT" | grep -qF "::warning::UNPUBLISHED NapkinStack: $URL@1a2b3c4" \
  && echo "$OUT" | grep -qF "uv tool install napkinstack @ git+$URL@1a2b3c4" \
  || { echo "FAIL: an unpublished commit is not installed from the repository, announced."; echo "$OUT"; exit 1; }
engine v0.4.0-3-g1a2b3c4 gh:NapkinStack/engineering-os | grep -qF "git+https://github.com/NapkinStack/engineering-os@1a2b3c4" \
  && engine v0.4.0-3-g1a2b3c4 git@github.com:NapkinStack/engineering-os.git \
     | grep -qF "git+ssh://git@github.com/NapkinStack/engineering-os.git@1a2b3c4" \
  || { echo "FAIL: Copier's short and scp-like sources not read as doctor L7 reads them."; exit 1; }
if OUT=$(engine v0.4.0-3-g1a2b3c4 /srv/checkouts/framework); then
  echo "FAIL: a source on one machine accepted in CI."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "is a path on one machine" || { echo "FAIL: no reason given."; echo "$OUT"; exit 1; }
if OUT=$(UV_FAILS=1 engine v0.4.0-3-g0000000 "$URL"); then
  echo "FAIL: a missing ref did not fail."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "framework ref '0000000' not found" && ! echo "$OUT" | grep -qF "napkinstack==" \
  || { echo "FAIL: a missing ref fell back, or was not named."; echo "$OUT"; exit 1; }
rm -rf "$EI"

echo "-> nstack fitness: fails when any of the three checks fails"
FT=$(mktemp -d)
mkdir -p "$FT/.nstack" "$FT/.nstack/playbooks"
printf 'skills: {}\n' > "$FT/.nstack/skills.yaml"
printf '# orphan\n' > "$FT/.nstack/playbooks/orphan.md"
if OUT=$(uv run nstack fitness --root "$FT" 2>&1); then
  echo "FAIL: a playbook without an entry went green."; rm -rf "$FT"; exit 1
fi
echo "$OUT" | grep -qF "[S1]" || { echo "FAIL: S1 expected."; echo "$OUT"; rm -rf "$FT"; exit 1; }
rm -rf "$FT"

echo "-> hygiene: a path from one person's machine in a tracked file MUST fail (H1)"
HY=$(mktemp -d)
git -C "$HY" init -q --initial-branch=main
# Assembled here for the reason the rule's tests give: written literally, the path would be
# a finding of H1 in this very file, which has no way to exempt itself.
printf 'The key lands in ~%s\n' "/Downloads/agent.private-key.pem" > "$HY/runbook.md"
git -C "$HY" add -A
git -C "$HY" "${GIT_ID_RM[@]}" commit -qm files
if OUT=$(uv run nstack hygiene --root "$HY" 2>&1); then
  echo "FAIL: a path from one person's machine went green."; rm -rf "$HY"; exit 1
fi
echo "$OUT" | grep -qF "[H1]" || { echo "FAIL: H1 expected."; echo "$OUT"; rm -rf "$HY"; exit 1; }
rm -rf "$HY"

echo "-> nstack pr-scope: responds on the given root"
uv run nstack pr-scope --root . --base HEAD | grep -qF "No file changed." \
  || { echo "FAIL: nstack pr-scope does not respond."; exit 1; }

echo "-> release: a tag different from the package version MUST block (ADR-0002)"
[ -f .github/workflows/release.yml ] || { echo "FAIL: .github/workflows/release.yml missing."; exit 1; }
TAG_CHECK=$(python3 - <<'EOF'
import yaml
jobs = yaml.safe_load(open(".github/workflows/release.yml", encoding="utf-8"))["jobs"]
print(next(step["run"] for step in jobs["build"]["steps"] if step.get("name") == "Tag and version identical"))
EOF
)
if OUT=$(GITHUB_REF_NAME=v9.9.9 bash -c "$TAG_CHECK" 2>&1); then
  echo "FAIL: tag v9.9.9 accepted for a different version."; exit 1
fi
echo "$OUT" | grep -qF "Tag v9.9.9 and version" \
  || { echo "FAIL: refusal without an explanatory message."; echo "$OUT"; exit 1; }
GITHUB_REF_NAME="v$(uv version --short)" bash -c "$TAG_CHECK" >/dev/null \
  || { echo "FAIL: matching tag refused."; exit 1; }

# Hooks: throwaway git repositories, fictional identity. The fake secrets are assembled at
# run time: written literally, they would trigger push protection.
command -v pre-commit >/dev/null \
  || { echo "FAIL: pre-commit required (https://pre-commit.com/#install)."; exit 1; }
HK=$(mktemp -d)
trap 'rm -rf "$SK" "$SC" "$HK"' EXIT
GIT_ID=(-c user.name=test -c user.email=test@example.invalid -c init.defaultBranch=main)

repo_with_hooks() {
  local d="$HK/$1"
  git "${GIT_ID[@]}" init -q "$d"
  [ -f .pre-commit-config.yaml ] && cp .pre-commit-config.yaml "$d/"
  [ -f .yamllint.yaml ] && cp .yamllint.yaml "$d/"
  git -C "$d" add -A
  git "${GIT_ID[@]}" -C "$d" commit -q --no-verify --allow-empty -m init
  (cd "$d" && pre-commit install >/dev/null)
}
fake_aws_token() {
  python3 -c 'import secrets, string; print("AK" + "IA" + "".join(secrets.choice(string.ascii_uppercase + "234567") for _ in range(16)))'
}

echo "-> hooks: a secret MUST block the commit"
repo_with_hooks secret
echo "aws_access_key_id = $(fake_aws_token)" > "$HK/secret/config.ini"
git -C "$HK/secret" add config.ini
if OUT=$(git "${GIT_ID[@]}" -C "$HK/secret" commit -m test 2>&1); then
  echo "FAIL: a secret was committed."; exit 1
fi
echo "$OUT" | grep -qE "Detect hardcoded secrets\.+Failed" \
  || { echo "FAIL: refusal without the gitleaks hook."; echo "$OUT"; exit 1; }

echo "-> hooks: a private key MUST block the commit"
repo_with_hooks key
printf -- '-----BEGIN %s PRIVATE KEY-----\nMIIEow\n-----END %s PRIVATE KEY-----\n' RSA RSA > "$HK/key/id"
git -C "$HK/key" add id
if OUT=$(git "${GIT_ID[@]}" -C "$HK/key" commit -m test 2>&1); then
  echo "FAIL: a private key was committed."; exit 1
fi
echo "$OUT" | grep -qiE "detect private key\.+Failed" \
  || { echo "FAIL: refusal without detect-private-key."; echo "$OUT"; exit 1; }

echo "-> hooks: a shebang script that is not executable MUST block the commit"
repo_with_hooks shebang
printf '#!/bin/sh\necho ok\n' > "$HK/shebang/tool.sh"
git -C "$HK/shebang" add tool.sh
if OUT=$(git "${GIT_ID[@]}" -C "$HK/shebang" commit -m test 2>&1); then
  echo "FAIL: a non-executable script was committed."; exit 1
fi
echo "$OUT" | grep -qiE "shebangs are executable\.+Failed" \
  || { echo "FAIL: refusal without the shebang check."; echo "$OUT"; exit 1; }

echo "-> CI: a secret committed by bypassing the hook MUST be found, without being printed"
repo_with_hooks history
TOKEN=$(fake_aws_token)
echo "aws_access_key_id = $TOKEN" > "$HK/history/config.ini"
git -C "$HK/history" add config.ini
git "${GIT_ID[@]}" -C "$HK/history" commit -q --no-verify -m bypass
if OUT=$(cd "$HK/history" && pre-commit run gitleaks-history --hook-stage manual --all-files 2>&1); then
  echo "FAIL: the history scan found nothing."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qi "leaks found" \
  || { echo "FAIL: failure without a gitleaks detection."; echo "$OUT"; exit 1; }
if echo "$OUT" | grep -qF "$TOKEN"; then
  echo "FAIL: the secret appears in clear text in the output (CI logs are public)."; exit 1
fi

echo "-> hooks: a link into a private assistant session MUST be refused, in a message and in a file (D92)"
# The address is assembled here so that this file does not hold one.
LINK="https://claude"".ai/code/session_0123456789"
repo_with_hooks session
echo "a line" > "$HK/session/notes.md"
git -C "$HK/session" add notes.md
if OUT=$(git "${GIT_ID[@]}" -C "$HK/session" commit -m "A change" -m "Session: $LINK" 2>&1); then
  echo "FAIL: a commit message holding a session link accepted."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "No link to a private assistant session" \
  || { echo "FAIL: refusal without the session-link hook."; echo "$OUT"; exit 1; }
git "${GIT_ID[@]}" -C "$HK/session" commit -q -m "A change" -m "Co-Authored-By: An Assistant <noreply@example.com>" \
  || { echo "FAIL: a message naming a co-author, without a link, refused."; exit 1; }
# Not every link to an assistant is one into a session: its site, its documentation pass.
echo "Written with https://claude"".ai/ and https://chatgpt"".com/overview" >> "$HK/session/notes.md"
git -C "$HK/session" add notes.md
git "${GIT_ID[@]}" -C "$HK/session" commit -q -m "A link to the assistant's site" \
  || { echo "FAIL: a link to an assistant's site, which is no session, refused."; exit 1; }
for other in "https://chatgpt"".com/c/0123-4567" "https://claude"".ai/chat/0123-4567" "https://chatgpt"".com/share/0123"; do
  echo "$other" > "$HK/session/said.txt"
  if (cd "$HK/session" && pre-commit run no-session-link --hook-stage commit-msg --commit-msg-filename said.txt >/dev/null 2>&1); then
    echo "FAIL: a conversation link accepted: $other"; exit 1
  fi
done
echo "See $LINK" >> "$HK/session/notes.md"
git -C "$HK/session" add notes.md
if OUT=$(git "${GIT_ID[@]}" -C "$HK/session" commit -m "A file" 2>&1); then
  echo "FAIL: a file holding a session link accepted."; echo "$OUT"; exit 1
fi
echo "$LINK" > "$HK/session/said.txt"
if OUT=$(cd "$HK/session" && pre-commit run no-session-link --hook-stage commit-msg --commit-msg-filename said.txt 2>&1); then
  echo "FAIL: CI's reading of the messages found nothing."; echo "$OUT"; exit 1
fi
for f in .github/workflows/governance.yml skeleton/.github/workflows/governance.yml; do
  grep -qF 'no-session-link --hook-stage commit-msg --commit-msg-filename "$said"' "$f" \
    && grep -qF 'git log --format=%B "$BASE..HEAD"' "$f" && grep -qF 'DESCRIPTION: ${{ github.event.pull_request.body }}' "$f" \
    || { echo "FAIL: $f does not read the commit messages and the description."; exit 1; }
done

echo "-> hooks: same gitleaks version at commit time and in the history scan"
V_HOOK=$(grep -A1 'repo: https://github.com/gitleaks/gitleaks' .pre-commit-config.yaml | grep -oE 'frozen: v[0-9.]+' | cut -d' ' -f2 || true)
V_HISTORY=$(grep -oE 'gitleaks/v8@v[0-9.]+' .pre-commit-config.yaml | cut -d@ -f2 || true)
[ -n "$V_HOOK" ] && [ "$V_HOOK" = "$V_HISTORY" ] \
  || { echo "FAIL: gitleaks versions diverge (hook: '$V_HOOK', history: '$V_HISTORY')."; exit 1; }

echo "-> workflows: injection, unpinned action, permissions and persisted token MUST fail"
repo_with_hooks zizmor
mkdir -p "$HK/zizmor/.github/workflows"
cat > "$HK/zizmor/.github/workflows/flaw.yml" <<'EOF'
name: flaw
on: pull_request
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "${{ github.event.pull_request.title }}"
EOF
git -C "$HK/zizmor" add .github
if OUT=$(cd "$HK/zizmor" && pre-commit run zizmor --files .github/workflows/flaw.yml 2>&1); then
  echo "FAIL: a vulnerable workflow went through."; exit 1
fi
for audit in template-injection unpinned-uses excessive-permissions artipacked; do
  echo "$OUT" | grep -qF "[$audit]" \
    || { echo "FAIL: zizmor does not report $audit."; echo "$OUT"; exit 1; }
done

echo "-> workflows: an invalid workflow MUST fail"
repo_with_hooks actionlint
mkdir -p "$HK/actionlint/.github/workflows"
printf 'on: push\njobs:\n  j:\n    steps:\n      - run: echo ok\n' > "$HK/actionlint/.github/workflows/invalid.yml"
git -C "$HK/actionlint" add .github
if OUT=$(cd "$HK/actionlint" && pre-commit run actionlint --files .github/workflows/invalid.yml 2>&1); then
  echo "FAIL: an invalid workflow went through."; exit 1
fi
echo "$OUT" | grep -qF '"runs-on" section is missing' \
  || { echo "FAIL: actionlint does not report the expected error."; echo "$OUT"; exit 1; }

echo "-> hooks: a conflict marker outside a git merge MUST block the commit"
# Copier (ADR-0001) writes its conflicts outside any git merge. Markers assembled
# at run time: written at the start of a line here, they would block this file itself.
repo_with_hooks conflict
printf 'intro\n%s before\nlocal\n%s\nfix\n%s after\n' '<<<<<<<' '=======' '>>>>>>>' > "$HK/conflict/rule.md"
git -C "$HK/conflict" add rule.md
if OUT=$(git "${GIT_ID[@]}" -C "$HK/conflict" commit -m test 2>&1); then
  echo "FAIL: a file containing conflict markers was committed."; exit 1
fi
echo "$OUT" | grep -qF "Merge conflict string" \
  || { echo "FAIL: refusal without check-merge-conflict."; echo "$OUT"; exit 1; }

echo "-> YAML: a duplicate key MUST fail (check-yaml)"
repo_with_hooks duplicate
printf 'module:\n  name: a\n  name: b\n' > "$HK/duplicate/duplicate.yaml"
git -C "$HK/duplicate" add duplicate.yaml
if OUT=$(cd "$HK/duplicate" && pre-commit run check-yaml --files duplicate.yaml 2>&1); then
  echo "FAIL: a duplicate key went through."; exit 1
fi
echo "$OUT" | grep -qF 'found duplicate key "name"' \
  || { echo "FAIL: check-yaml does not report the duplicate key."; echo "$OUT"; exit 1; }

echo "-> YAML: an unquoted placeholder MUST fail (check-yaml)"
repo_with_hooks template
printf 'module:\n  name: {{MODULE_NAME}}\n' > "$HK/template/template.yaml"
git -C "$HK/template" add template.yaml
if OUT=$(cd "$HK/template" && pre-commit run check-yaml --files template.yaml 2>&1); then
  echo "FAIL: an unquoted placeholder went through."; exit 1
fi
echo "$OUT" | grep -qF 'found unhashable key' \
  || { echo "FAIL: check-yaml does not report the placeholder."; echo "$OUT"; exit 1; }

echo "-> YAML: an ambiguous boolean value MUST fail (yamllint, repository configuration)"
repo_with_hooks truthy
printf 'active: yes\n' > "$HK/truthy/rule.yaml"
git -C "$HK/truthy" add rule.yaml
if OUT=$(cd "$HK/truthy" && pre-commit run yamllint --files rule.yaml 2>&1); then
  echo "FAIL: the value 'yes' went through."; exit 1
fi
# The message text, not "(truthy)": on GitHub Actions, yamllint switches to the annotations format.
echo "$OUT" | grep -qF 'truthy value should be one of' \
  || { echo "FAIL: yamllint does not report the truthy rule."; echo "$OUT"; exit 1; }

echo "-> GitHub: an invalid dependabot.yml, issue form and issue configuration MUST fail"
repo_with_hooks schemas
mkdir -p "$HK/schemas/.github/ISSUE_TEMPLATE"
printf 'version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n' > "$HK/schemas/.github/dependabot.yml"
printf 'name: x\ndescription: y\nbody:\n  - type: input\n' > "$HK/schemas/.github/ISSUE_TEMPLATE/formulaire.yml"
printf 'blank_issues_enabled: "non"\n' > "$HK/schemas/.github/ISSUE_TEMPLATE/config.yml"
git -C "$HK/schemas" add .github
for case in check-dependabot:.github/dependabot.yml \
           check-github-issue-forms:.github/ISSUE_TEMPLATE/formulaire.yml \
           check-github-issue-config:.github/ISSUE_TEMPLATE/config.yml; do
  hook=${case%%:*}; file=${case#*:}
  if OUT=$(cd "$HK/schemas" && pre-commit run "$hook" --files "$file" 2>&1); then
    echo "FAIL: invalid $file accepted by $hook."; exit 1
  fi
  echo "$OUT" | grep -qF "Schema validation errors" \
    || { echo "FAIL: $hook does not report a schema error."; echo "$OUT"; exit 1; }
done

# Skeleton, init and update: projects created from the working tree, uncommitted changes
# included, never from GitHub. nstack commits: fictional git identity.
GN=$(mktemp -d)
trap 'rm -rf "$SK" "$SC" "$HK" "$GN"' EXIT
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid
# Long name: Copier writes .copier-answers.yml with no line limit (name, template path).
# The fresh-clone replay showed it with a long path; the name makes the case deterministic.
LONG_NAME="Demo project $(printf 'long%.0s' {1..30})"
ANSWERS=(--project-name "$LONG_NAME" --github-repo acme/demo --owner-team acme/platform)
PROJECT="$GN/project"

echo "-> init: project created and committed on main, answers rendered, no template file left"
if ! OUT=$(nstack init "$PROJECT" --source "$REPO" --ref HEAD "${ANSWERS[@]}" 2>&1); then
  echo "FAIL: nstack init failed."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Project created in" \
  || { echo "FAIL: nstack init does not confirm the creation."; echo "$OUT"; exit 1; }
[ "$(git -C "$PROJECT" branch --show-current)" = main ] && [ -z "$(git -C "$PROJECT" status --porcelain)" ] \
  || { echo "FAIL: the project is not committed on main."; git -C "$PROJECT" status; exit 1; }
# The manual installs the way CI does: a project pinned to a commit (this one is) is not
# told to install a version that no installer accepts.
grep -qxF "bash .nstack/install-engine.sh" "$PROJECT/.nstack/handbook/INSTALL.md" \
  && ! grep -qE 'napkinstack==[0-9.]+-[0-9]+-g' "$PROJECT/.nstack/handbook/INSTALL.md" \
  || { echo "FAIL: the manual's first install line is not the script CI runs."; grep -n "napkinstack==" "$PROJECT/.nstack/handbook/INSTALL.md"; exit 1; }
LEFTOVERS=$(find "$PROJECT" -name '*.jinja')
[ -z "$LEFTOVERS" ] || { echo "FAIL: template files copied as is:"; echo "$LEFTOVERS"; exit 1; }
# D58: what an agent's runtime writes as it runs is ignored; what a team shares is not.
for ignored in .mcp.json .claude/launch.json .claude/routines/x.md .claude/.cc-writes/x; do
  git -C "$PROJECT" check-ignore -q "$ignored" \
    || { echo "FAIL: the project does not ignore $ignored, left by an agent's runtime (D58)."; exit 1; }
done
for tracked in .claude/settings.json .claude/hooks/check.sh; do
  git -C "$PROJECT" check-ignore -q "$tracked" \
    && { echo "FAIL: the project ignores $tracked, which a team shares on purpose (D58)."; exit 1; }
done
for expected in ".github/CODEOWNERS|@acme/platform" \
               ".github/ISSUE_TEMPLATE/config.yml|https://github.com/acme/demo/discussions" \
               "README.md|# Demo project" \
               "README.md|.nstack/handbook/INSTALL.md" \
               ".nstack/handbook/INSTALL.md|## To do once on GitHub" \
               ".nstack/handbook/INSTALL.md|uv tool install \"napkinstack==" \
               ".copier-answers.yml|owner_team: acme/platform"; do
  file=${expected%%|*}; text=${expected#*|}
  grep -qF -- "$text" "$PROJECT/$file" 2>/dev/null \
    || { echo "FAIL: $file does not contain '$text'."; exit 1; }
done

echo "-> init: the front page is the project's, the manual is one click away (PDR-0010)"
if grep -niP 'napkinstack|(?<![./])\bnstack\b' "$PROJECT/README.md"; then  # its name or its command, not a path into .nstack/
  echo "FAIL: the project's front page names the framework."; exit 1
fi
[ "$(wc -l < "$PROJECT/README.md")" -lt 40 ] \
  || { echo "FAIL: the project's front page is $(wc -l < "$PROJECT/README.md") lines of form."; exit 1; }

[ ! -e "$PROJECT/contracts" ] && ! grep -qF "/contracts/" "$PROJECT/.github/CODEOWNERS" \
  || { echo "FAIL: a project is born with a contracts module before it has a contract (PDR-0012)."; exit 1; }

echo "-> init: NapkinStack's own development context is never copied (R6)"
for absent in PRODUCT.md docs/governance platform src pyproject.toml uv.lock copier.yml skeleton; do
  [ ! -e "$PROJECT/$absent" ] \
    || { echo "FAIL: $absent copied into the generated project (PDR-0001 R6). Remove it from skeleton/."; exit 1; }
done

echo "-> init: a non-empty folder MUST be refused, without writing anything into it"
mkdir -p "$GN/occupied" && echo guard > "$GN/occupied/guard.txt"
if OUT=$(nstack init "$GN/occupied" --source "$REPO" --ref HEAD "${ANSWERS[@]}" 2>&1); then
  echo "FAIL: init into a non-empty folder accepted."; exit 1
fi
echo "$OUT" | grep -qF "is not empty" \
  || { echo "FAIL: refusal without an explanation."; echo "$OUT"; exit 1; }
[ "$(ls -A "$GN/occupied")" = guard.txt ] || { echo "FAIL: init wrote into the refused folder."; exit 1; }

echo "-> init: a repository without an organisation, or an invalid owner, MUST be refused (P6)"
for question in github_repo owner_team; do
  if [ "$question" = github_repo ]; then
    answers=(--project-name x --github-repo demo --owner-team acme/platform)
  else
    answers=(--project-name x --github-repo acme/demo --owner-team platform-)
  fi
  if OUT=$(nstack init "$GN/refused-$question" --source "$REPO" --ref HEAD "${answers[@]}" 2>&1); then
    echo "FAIL: $question '${answers[-1]}' accepted."; exit 1
  fi
  echo "$OUT" | grep -qF "FAIL [init] Answer rejected for $question" \
    || { echo "FAIL: refusal of $question without an explanatory message."; echo "$OUT"; exit 1; }
done

echo "-> init: a project without an organisation names a user as owner"
nstack init "$GN/solo" --source "$REPO" --ref HEAD --project-name Solo --github-repo alice/solo \
  --owner-team alice >/dev/null || { echo "FAIL: init with a user as owner."; exit 1; }
grep -qE '^/AGENTS\.md +@alice$' "$GN/solo/.github/CODEOWNERS" \
  || { echo "FAIL: CODEOWNERS does not name the user."; exit 1; }

echo "-> init: a template with an "unsafe" feature MUST be refused, creating nothing (ADR-0001)"
UNSAFE="$GN/template-unsafe"
mkdir -p "$UNSAFE" && cp -r copier.yml skeleton "$UNSAFE/"
printf '\n_tasks:\n  - "touch execute"\n' >> "$UNSAFE/copier.yml"
git "${GIT_ID[@]}" init -q "$UNSAFE"
git -C "$UNSAFE" add -A
git "${GIT_ID[@]}" -C "$UNSAFE" commit -q --no-verify -m unsafe
if OUT=$(nstack init "$GN/unsafe" --source "$UNSAFE" --ref HEAD "${ANSWERS[@]}" 2>&1); then
  echo "FAIL: unsafe template accepted."; exit 1
fi
echo "$OUT" | grep -qF "FAIL [init] Template $UNSAFE runs code" \
  || { echo "FAIL: unsafe refusal without an explanatory message."; echo "$OUT"; exit 1; }
[ ! -e "$GN/unsafe" ] || { echo "FAIL: the refused template created files."; exit 1; }

echo "-> init: a template version that cannot be found MUST be explained (P6)"
if OUT=$(nstack init "$GN/missing" --source "$REPO" --ref v9.9.9 "${ANSWERS[@]}" 2>&1); then
  echo "FAIL: unknown version accepted."; exit 1
fi
echo "$OUT" | grep -qF "FAIL [init] Template $REPO at version v9.9.9 unreachable" \
  || { echo "FAIL: unknown version without an explanatory message."; echo "$OUT"; exit 1; }

echo "-> skeleton: hooks and YAML rules identical to the repository's (P3)"
for f in .pre-commit-config.yaml .yamllint.yaml; do
  cmp -s "$f" "skeleton/$f" \
    || { echo "FAIL: skeleton/$f diverges from $f. Apply the same change to both copies."; exit 1; }
done

echo "-> init: on a fresh clone, the project passes its CI untouched (criterion 1)"
CLONE="$GN/clone"
git clone -q "$PROJECT" "$CLONE"
if ! OUT=$(cd "$CLONE" && nstack fitness --root . 2>&1); then
  echo "FAIL: the project does not pass nstack fitness."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Skills: S1, S2 and S4 compliant" \
  || { echo "FAIL: skills not checked in the project."; echo "$OUT"; exit 1; }
if ! OUT=$(cd "$CLONE" && SKIP=gitleaks pre-commit run --all-files 2>&1); then
  echo "FAIL: the project does not pass its hooks."; echo "$OUT"; exit 1
fi
for hook in "Lint GitHub Actions workflow files" "Validate Dependabot Config (v2)" \
            "Validate GitHub issue config" "Validate GitHub issue forms" "zizmor"; do
  echo "$OUT" | grep -F -- "$hook" | grep -qF "Passed" \
    || { echo "FAIL: hook "$hook" not run on the project."; echo "$OUT"; exit 1; }
done
if ! OUT=$(cd "$CLONE" && pre-commit run gitleaks-history --hook-stage manual --all-files 2>&1); then
  echo "FAIL: history scan failing on the project."; echo "$OUT"; exit 1
fi
(cd "$CLONE" && nstack pr-scope --root . --base HEAD) | grep -qF "No file changed." \
  || { echo "FAIL: nstack pr-scope does not respond in the project."; exit 1; }

echo "-> new-module: in the project, the module passes fitness and hooks with no imposed stack (criterion 3)"
nstack new-module demo acme/demo-team standard --root "$CLONE" >/dev/null
if ! OUT=$(nstack fitness --root "$CLONE" 2>&1); then
  echo "FAIL: the stack-free module does not pass the fitness functions."; echo "$OUT"; exit 1
fi
git -C "$CLONE" add -A
if ! OUT=$(cd "$CLONE" && SKIP=gitleaks pre-commit run 2>&1); then
  echo "FAIL: the generated module does not pass the project hooks."; echo "$OUT"; exit 1
fi

echo "-> pr-check: in the project, a user-facing change without a test sheet MUST fail (PDR-0003)"
git "${GIT_ID[@]}" -C "$CLONE" commit -q --no-verify -m "First module"
nstack new-module face acme/web standard --user-facing --root "$CLONE" >/dev/null
printf 'page\n' > "$CLONE/modules/face/src/page.html"  # an empty scaffold changes no behaviour (D24)
git -C "$CLONE" add -A && git "${GIT_ID[@]}" -C "$CLONE" commit -q --no-verify -m "User-facing module"
if OUT=$(cd "$CLONE" && PR_BODY="$(cat .github/pull_request_template.md)" nstack pr-check --root . --base HEAD~1 2>&1); then
  echo "FAIL: a user-facing change with the template's empty sheet went green."; echo "$OUT"; exit 1
fi
# PDR-0007, its first two criteria in one run: the project has no charter, so the cycle rules
# say nothing and the run names the stage — while another rule, the test sheet, still refuses.
echo "$OUT" | grep -qF "modules/face (criticality standard, user-facing)" \
  && echo "$OUT" | grep -qF "Project unframed — no accepted charter: the cycle rules (K1 to K3) do not apply" \
  || { echo "FAIL: T1 or the project's stage missing."; echo "$OUT"; exit 1; }
if echo "$OUT" | grep -qE "FAIL \[K[123]\]"; then
  echo "FAIL: a cycle rule fired in a project that has no cycle (PDR-0007)."; echo "$OUT"; exit 1
fi

echo "-> plan: a module holding code and a module map left as its form MUST fail (C8, PDR-0010)"
if OUT=$(cd "$CLONE" && nstack plan --root . 2>&1); then
  echo "FAIL: a project with code in a module and no module map went green."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "FAIL [C8] modules/README.md" && echo "$OUT" | grep -qF "(face)" \
  || { echo "FAIL: C8 does not name the map and the module."; echo "$OUT"; exit 1; }
in_place 's#^<A diagram of this project.*#One module, face: the page a visitor sees. No contract yet.#' "$CLONE/modules/README.md"

echo "-> plan: a new project is unframed, a stage and not a fault; its templates are not checked (PDR-0007)"
(cd "$CLONE" && nstack plan --root .) | grep -qF "the project is unframed, which is a stage and not a fault" \
  || { echo "FAIL: nstack plan does not report an unframed project."; exit 1; }

echo "-> discover: an idea starts a discovery, no model called (PDR-0002, extension)"
printf 'A place where neighbours lend each other tools.\n' > "$GN/idea.md"
(cd "$CLONE" && nstack discover "$GN/idea.md" --root .) | grep -qF "Follow .nstack/playbooks/discovery.md on docs/project/inputs/idea.md" \
  && grep -qF 'idea: "docs/project/inputs/idea.md"' "$CLONE/docs/project/discovery.md" \
  && (cd "$CLONE" && nstack plan --root .) >/dev/null \
  || { echo "FAIL: nstack discover did not start the discovery."; exit 1; }

# Updates: throwaway template with three versions, built from the working tree.
TPL="$GN/template"
mkdir -p "$TPL" && cp -r copier.yml skeleton "$TPL/"
git "${GIT_ID[@]}" init -q "$TPL"
template_version() {  # $1 = tag, the template changes having been made
  git -C "$TPL" add -A
  git "${GIT_ID[@]}" -C "$TPL" commit -q --no-verify -m "$1"
  git -C "$TPL" tag "$1"
}
template_version v90.1.0
printf '\nFix v90.2, at the end of the file.\n' >> "$TPL/skeleton/.nstack/playbooks/tests.md"
printf '\nFix v90.2.\n' >> "$TPL/skeleton/.nstack/forms/pdr.md"
printf '\nFix v90.2.\n' >> "$TPL/skeleton/.nstack/tooling-profile.md"
# A seat is the project's from its first commit: the template may rewrite it, no project
# that already exists receives a line of it (PDR-0010).
for seat in README.md.jinja SECURITY.md modules/README.md docs/adr/README.md docs/pdr/README.md; do
  printf '\nSeat rewritten in v90.2.\n' >> "$TPL/skeleton/$seat"
done
template_version v90.2.0
in_place '1s/.*/# Security - title v0.3/' "$TPL/skeleton/.nstack/playbooks/security.md"
template_version v90.3.0
project_v01() {
  nstack init "$1" --source "$TPL" --ref v90.1.0 "${ANSWERS[@]}" >/dev/null \
    || { echo "FAIL: nstack init from the throwaway template ($1)."; exit 1; }
}
commit_project() { git -C "$1" add -A && git "${GIT_ID[@]}" -C "$1" commit -q --no-verify -m "$2"; }

A="$GN/project-a"
project_v01 "$A"
in_place '1s/.*/# Tests — local adaptation/' "$A/.nstack/playbooks/tests.md"
rm "$A/.nstack/forms/pdr.md"
nstack new-module demo acme/demo-team standard --root "$A" >/dev/null
printf '\nNeighbours lend each other tools.\n' >> "$A/README.md"
rm "$A/docs/adr/README.md"
commit_project "$A" "Adaptations and first module"
SEATS_BEFORE=$(git -C "$A" rev-parse HEAD:README.md HEAD:SECURITY.md HEAD:modules/README.md HEAD:docs/pdr/README.md)
MODULE_BEFORE=$(git -C "$A" rev-parse HEAD:modules/demo)

echo "-> update: started from another branch, it MUST be refused and name both (D74)"
# The pilot ran it from cycle/03-framing: the update branch carried a foreign commit and was
# replanted by hand. Refused before anything is written, and the way back is a command.
git -C "$A" switch -q -c cycle/03-framing
if OUT=$(nstack update --root "$A" --ref v90.2.0 2>&1); then
  echo "FAIL: update accepted from a feature branch."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "cycle/03-framing" && echo "$OUT" | grep -qF "git switch main" \
  && [ -z "$(git -C "$A" status --porcelain)" ] \
  && ! git -C "$A" rev-parse --verify --quiet refs/heads/nstack/update-v90.2.0 >/dev/null \
  || { echo "FAIL: update from a feature branch badly refused."; echo "$OUT"; exit 1; }
git -C "$A" switch -q main && git -C "$A" branch -q -D cycle/03-framing

echo "-> update: fix and adaptation merged, committed on a branch (criterion 4)"
if ! OUT=$(nstack update --root "$A" --ref v90.2.0 2>&1); then
  echo "FAIL: nstack update failed."; echo "$OUT"; exit 1
fi
[ "$(git -C "$A" branch --show-current)" = nstack/update-v90.2.0 ] && [ -z "$(git -C "$A" status --porcelain)" ] \
  || { echo "FAIL: update not committed on nstack/update-v90.2.0."; git -C "$A" status; exit 1; }
[ "$(head -1 "$A/.nstack/playbooks/tests.md")" = "# Tests — local adaptation" ] \
  && grep -qF "Fix v90.2, at the end of the file." "$A/.nstack/playbooks/tests.md" \
  || { echo "FAIL: adaptation or fix lost in .nstack/playbooks/tests.md."; exit 1; }
grep -qF "_commit: v90.2.0" "$A/.copier-answers.yml" \
  || { echo "FAIL: project version not bumped."; exit 1; }
echo "$OUT" | grep -qF "git push -u origin nstack/update-v90.2.0" \
  || { echo "FAIL: next step missing."; echo "$OUT"; exit 1; }
# D66: the notes name the distance travelled, never the target alone — one update can cross
# several versions, and the change that conflicts may come from any of them.
echo "$OUT" | grep -qF "What v90.1.0 -> v90.2.0 changes, engine and project apart:" \
  && echo "$OUT" | grep -qF "every section above v90.1.0" \
  || { echo "FAIL: the notes do not name every version crossed (D66)."; echo "$OUT"; exit 1; }

echo "-> update: a file the team deleted is not recreated (criterion 6)"
[ ! -e "$A/.nstack/forms/pdr.md" ] || { echo "FAIL: deleted file recreated."; exit 1; }

echo "-> update: no module file changed, a method file beside them follows (criterion 7)"
[ "$(git -C "$A" rev-parse HEAD:modules/demo)" = "$MODULE_BEFORE" ] \
  || { echo "FAIL: modules/demo changed by the update (PDR-0001 R4)."; exit 1; }
grep -qF "Fix v90.2." "$A/.nstack/tooling-profile.md" \
  || { echo "FAIL: .nstack/tooling-profile.md did not follow the version."; exit 1; }

echo "-> update: a seat the template rewrote MUST stay as the project wrote it (PDR-0010)"
[ "$(git -C "$A" rev-parse HEAD:README.md HEAD:SECURITY.md HEAD:modules/README.md HEAD:docs/pdr/README.md)" = "$SEATS_BEFORE" ] \
  || { echo "FAIL: an update rewrote a file that belongs to the project."
       git -C "$A" diff --stat main HEAD -- README.md modules/README.md docs/pdr/README.md; exit 1; }
# Unlike a method file (criterion 6), a seat that is missing comes back, as its form: that is
# what Copier's _skip_if_exists means, and a project with no front page gets one to write.
grep -qF "Seat rewritten in v90.2." "$A/docs/adr/README.md" \
  || { echo "FAIL: a missing seat was not recreated from the version's form."; exit 1; }

# The team merges the update's pull request and comes back to main, as it would.
git -C "$A" switch -q main && git -C "$A" merge -q --ff-only nstack/update-v90.2.0

echo "-> update: a project already up to date creates no branch"
if ! OUT=$(nstack update --root "$A" --ref v90.2.0 2>&1); then
  echo "FAIL: up-to-date project refused."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "Already up to date" \
  && [ "$(git -C "$A" branch --list 'nstack/*' | wc -l)" -eq 1 ] \
  || { echo "FAIL: up-to-date project mishandled."; echo "$OUT"; exit 1; }

echo "-> update: an older version MUST be refused, without changing anything"
if OUT=$(nstack update --root "$A" --ref v90.1.0 2>&1); then
  echo "FAIL: downgrade accepted."; exit 1
fi
echo "$OUT" | grep -qF "older than the project version (90.2.0)" \
  && [ -z "$(git -C "$A" status --porcelain)" ] \
  || { echo "FAIL: downgrade badly refused."; echo "$OUT"; exit 1; }
# P6: the action is a command to run, not a description of one. Found in real use on
# 2026-09-20: the maintainer met this refusal, then tried `uv tool upgrade`, which does
# nothing on a pinned install.
echo "$OUT" | grep -qF 'uv tool install "napkinstack@latest"' \
  || { echo "FAIL: the refusal must name the command that moves the workstation forward."; echo "$OUT"; exit 1; }

echo "-> update: a modified working tree MUST be refused, without changing anything"
echo "local change" >> "$A/README.md"
if OUT=$(nstack update --root "$A" --ref v90.3.0 2>&1); then
  echo "FAIL: update accepted on a modified tree."; exit 1
fi
echo "$OUT" | grep -qF "FAIL [update] Working tree modified" \
  && [ "$(git -C "$A" diff --name-only)" = README.md ] \
  && ! git -C "$A" rev-parse --verify --quiet refs/heads/nstack/update-v90.3.0 >/dev/null \
  || { echo "FAIL: modified tree badly refused."; echo "$OUT"; exit 1; }
git -C "$A" checkout -q -- README.md

echo "-> update: a project created before the framework had one folder keeps what it adapted (PDR-0012, criterion 3)"
# Measured on the pilot before this test existed: it had added one line to docs/project/README.md,
# the update moved that page to .nstack/handbook/ and the line was gone, with no conflict and no word.
OLD="$GN/template-old-layout"
mkdir -p "$OLD" && cp -r copier.yml skeleton "$OLD/"
( cd "$OLD/skeleton" && mv .nstack/playbooks playbooks && mkdir -p docs/project/cycles docs/project/rules \
    && mv .nstack/handbook/project.md docs/project/README.md && mv .nstack/handbook docs/os \
    && mv .nstack/tooling-profile.md docs/tooling-profile.md \
    && mv .nstack/forms/adr.md docs/adr/_TEMPLATE.md && mv .nstack/forms/pdr.md docs/pdr/_TEMPLATE.md \
    && mv .nstack/forms/charter.md docs/project/_CHARTER_TEMPLATE.md \
    && mv .nstack/forms/discovery.md docs/project/_DISCOVERY_TEMPLATE.md \
    && mv .nstack/forms/cycle.md docs/project/cycles/_TEMPLATE.md \
    && mv .nstack/forms/rules.md docs/project/rules/_TEMPLATE.md && rmdir .nstack/forms \
    && cp -r "$REPO/src/napkinstack/templates/contracts" contracts \
    && sed 's/"{{OWNER}}"/{{ owner_team }}/; s/{{GITHUB_REPO}}/{{ github_repo }}/' contracts/MANIFEST.yaml > contracts/MANIFEST.yaml.jinja \
    && rm contracts/MANIFEST.yaml \
    && printf '\n# Contracts: the most critical boundary in the system, never orphaned.\n/contracts/                    @{{ owner_team }}\n' >> .github/CODEOWNERS.jinja )
git "${GIT_ID[@]}" init -q "$OLD"
git -C "$OLD" add -A && git "${GIT_ID[@]}" -C "$OLD" commit -q --no-verify -m v91.1.0 && git -C "$OLD" tag v91.1.0
rm -rf "$OLD/skeleton" && cp -r skeleton "$OLD/"
git -C "$OLD" add -A && git "${GIT_ID[@]}" -C "$OLD" commit -q --no-verify -m v91.2.0 && git -C "$OLD" tag v91.2.0
M="$GN/project-moved"
nstack init "$M" --source "$OLD" --ref v91.1.0 "${ANSWERS[@]}" >/dev/null \
  || { echo "FAIL: nstack init from the old-layout template."; exit 1; }
[ -f "$M/playbooks/tests.md" ] && [ -f "$M/docs/os/05-workflow.md" ] && [ ! -e "$M/.nstack/playbooks" ] \
  || { echo "FAIL: the old-layout fixture is not in the old layout."; exit 1; }
in_place '1s/.*/# Tests — the way this team does them/' "$M/playbooks/tests.md"
printf '| `handover.md` | Where the work stands after a break | The framer | — |\n' >> "$M/docs/project/README.md"
# And what the project wrote about the framework's pages, in files no update ever touches: its
# front page is a seat, its decision index another, a module's manifest is its owner's. Measured
# on the third project the day the move shipped: 41 old addresses left, two of them dead links
# on the front page and in the security policy.
printf '\nThe manual: [`docs/os/INSTALL.md`](docs/os/INSTALL.md).\n' >> "$M/README.md"
printf '\nHow a record is written: [the handbook](../os/06-decisions.md), from [its form](./_TEMPLATE.md).\n' >> "$M/docs/adr/README.md"
mkdir -p "$M/docs/project" && printf '# Notes\n\nFramed with `playbooks/framing.md`; the matrix is `docs/os/05-workflow.md` §7.\n' > "$M/docs/project/notes.md"
# A module's code is its owner's. Measured on a copy of the second project before v0.7.0: an
# old address rewritten in a comment of its code made the update's pull request a change of
# three modules — refused on P1, and owing a test sheet for a comment (D88).
nstack new-module demo acme/demo-team standard --root "$M" >/dev/null
git -C "$M" checkout -q .github/CODEOWNERS   # its owner line sits beside one the update removes: another case's subject
mkdir -p "$M/modules/demo/src" && printf '# The contract rules: docs/os/03-contracts.md
print("demo")
' > "$M/modules/demo/src/app.py"
printf '
How this module is judged: `docs/os/08-quality.md`.
' >> "$M/modules/demo/README.md"
commit_project "$M" "Two adaptations, in the old places"
if ! OUT=$(nstack update --root "$M" --ref v91.2.0 2>&1); then
  echo "FAIL: the update across the move failed."; echo "$OUT"; exit 1
fi
[ "$(head -1 "$M/.nstack/playbooks/tests.md")" = "# Tests — the way this team does them" ] \
  || { echo "FAIL: an adapted playbook lost its adaptation in the move."; head -2 "$M/.nstack/playbooks/tests.md"; exit 1; }
grep -qF "Where the work stands after a break" "$M/.nstack/handbook/project.md" \
  || { echo "FAIL: a line the project had added to a moved page is gone."; exit 1; }
for gone in playbooks docs/os docs/project/README.md docs/tooling-profile.md docs/adr/_TEMPLATE.md; do
  [ ! -e "$M/$gone" ] || { echo "FAIL: $gone is left in both places."; exit 1; }
done
echo "$OUT" | grep -qF "docs/project/README.md -> .nstack/handbook/project.md" \
  && echo "$OUT" | grep -qF "playbooks/tests.md -> .nstack/playbooks/tests.md" \
  || { echo "FAIL: the update does not name what it carried."; echo "$OUT"; exit 1; }
# The fixture's own pages already speak the new addresses: what is asserted is that the old
# ones the project wrote are gone, and that each became the right new one.
if grep -nF -e "docs/os/" -e "../os/" -e "_TEMPLATE.md" "$M/README.md" "$M/docs/adr/README.md"; then
  echo "FAIL: an old address is left in a file the project owns."; exit 1
fi
grep -qF 'The manual: [`.nstack/handbook/INSTALL.md`](.nstack/handbook/INSTALL.md).' "$M/README.md" \
  || { echo "FAIL: the front page still sends its reader to the manual's old address."; tail -2 "$M/README.md"; exit 1; }
grep -qF '(../../.nstack/handbook/06-decisions.md)' "$M/docs/adr/README.md" \
  && grep -qF '[its form](../../.nstack/forms/adr.md)' "$M/docs/adr/README.md" \
  || { echo "FAIL: a relative link of the project to a moved page is dead."; tail -2 "$M/docs/adr/README.md"; exit 1; }
grep -qF 'Framed with `.nstack/playbooks/framing.md`; the matrix is `.nstack/handbook/05-workflow.md` §7.' "$M/docs/project/notes.md" \
  || { echo "FAIL: an old address written in the project's own notes was left."; cat "$M/docs/project/notes.md"; exit 1; }
echo "$OUT" | grep -qF "old addresses rewritten" && echo "$OUT" | grep -qF "  - docs/project/notes.md" \
  || { echo "FAIL: the update does not say which of the project's files it rewrote."; echo "$OUT"; exit 1; }
grep -qF '# The contract rules: docs/os/03-contracts.md' "$M/modules/demo/src/app.py" \
  || { echo "FAIL: the update rewrote a module's code: its pull request now changes that module (D88)."; cat "$M/modules/demo/src/app.py"; exit 1; }
grep -qF 'How this module is judged: `.nstack/handbook/08-quality.md`.' "$M/modules/demo/README.md" \
  || { echo "FAIL: a module's description kept an old address."; tail -2 "$M/modules/demo/README.md"; exit 1; }
echo "$OUT" | grep -qF "left as written" && echo "$OUT" | grep -qF "  - modules/demo/src/app.py" \
  || { echo "FAIL: the update does not name the code it left with an old address."; echo "$OUT"; exit 1; }
(cd "$M" && nstack pr-scope --base main >/dev/null) \
  || { echo "FAIL: the update's own pull request is refused by the scope rule (D88)."; exit 1; }
[ -z "$(git -C "$M" status --porcelain)" ] || { echo "FAIL: the update across the move is not committed."; git -C "$M" status --short; exit 1; }
[ ! -e "$M/contracts" ] && ! grep -qF "/contracts/" "$M/.github/CODEOWNERS" \
  || { echo "FAIL: a project with no contract keeps the contracts module it was born with (PDR-0012)."; ls "$M/contracts"; exit 1; }

echo "-> update: a project that HAS a contract keeps the module that holds it (PDR-0012)"
# The other half, and the dangerous one: the scaffold left the skeleton, so the merge deletes
# it — manifest, owner and all — from under the contracts a project wrote.
K="$GN/project-with-contract"
nstack init "$K" --source "$OLD" --ref v91.1.0 "${ANSWERS[@]}" >/dev/null \
  || { echo "FAIL: nstack init from the old-layout template (contracts)."; exit 1; }
mkdir -p "$K/contracts/billing/v1" && printf '# billing v1\n' > "$K/contracts/billing/v1/README.md"
printf '# The rules a contract follows: docs/os/03-contracts.md\nopenapi: 3.1.0\n' > "$K/contracts/billing/v1/openapi.yaml"
commit_project "$K" "A first contract"
if ! OUT=$(nstack update --root "$K" --ref v91.2.0 2>&1); then
  echo "FAIL: the update of a project holding a contract failed."; echo "$OUT"; exit 1
fi
for kept in MANIFEST.yaml AGENTS.md README.md docs/runbook.md billing/v1/README.md; do
  [ -f "$K/contracts/$kept" ] || { echo "FAIL: contracts/$kept was taken from under a project's contract."; echo "$OUT"; exit 1; }
done
grep -qF "/contracts/" "$K/.github/CODEOWNERS" \
  || { echo "FAIL: the contracts module lost its owner in the update."; exit 1; }
grep -qF 'docs/os/03-contracts.md' "$K/contracts/billing/v1/openapi.yaml" \
  || { echo "FAIL: the update rewrote a contract's schema: its pull request now changes the contracts module (D88)."; echo "$OUT"; exit 1; }
# The schema served its case: with it, the module owes the standard verbs (M7), which this
# fixture's scaffold does not declare — another rule's subject.
git -C "$K" rm -q contracts/billing/v1/openapi.yaml && commit_project "$K" "The schema has served its case"
echo "$OUT" | grep -qF "contracts/ kept" \
  || { echo "FAIL: the update does not say it kept the contracts module."; echo "$OUT"; exit 1; }
(cd "$K" && nstack manifests --root . >/dev/null) || { echo "FAIL: the kept contracts module is not valid."; exit 1; }
[ -z "$(git -C "$K" status --porcelain)" ] || { echo "FAIL: the update of a project holding a contract is not committed."; exit 1; }

echo "-> update: outside a project, the command MUST explain it"
if OUT=$(nstack update --root "$GN/occupied" 2>&1); then
  echo "FAIL: update accepted outside a project."; exit 1
fi
echo "$OUT" | grep -qF "FAIL [update] .copier-answers.yml not found" \
  || { echo "FAIL: expected message missing."; echo "$OUT"; exit 1; }

B="$GN/project-b"
project_v01 "$B"
in_place '1s/.*/# Security - local adaptation/' "$B/.nstack/playbooks/security.md"
commit_project "$B" "Adaptation"

echo "-> update: versions skipped in one go, conflict marked and left to the team (criterion 5)"
if OUT=$(nstack update --root "$B" --ref v90.3.0 2>&1); then
  echo "FAIL: conflict passed over in silence."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "FAIL [update] NapkinStack v90.1.0 -> v90.3.0: conflicts" \
  && echo "$OUT" | grep -qF "  - .nstack/playbooks/security.md" \
  || { echo "FAIL: conflict without the list of files."; echo "$OUT"; exit 1; }
[ "$(git -C "$B" branch --show-current)" = nstack/update-v90.3.0 ] \
  && [ "$(git -C "$B" rev-parse HEAD)" = "$(git -C "$B" rev-parse main)" ] \
  && grep -qF "Fix v90.2, at the end of the file." "$B/.nstack/playbooks/tests.md" \
  || { echo "FAIL: branch, commit or skipped version incorrect."; exit 1; }

echo "-> update: the commit stays refused while a marker remains (criterion 5)"
(cd "$B" && pre-commit install >/dev/null)
git -C "$B" add -A
if OUT=$(git "${GIT_ID[@]}" -C "$B" commit -m "Update" 2>&1); then
  echo "FAIL: an update conflict was committed."; exit 1
fi
echo "$OUT" | grep -qF "Merge conflict string" \
  || { echo "FAIL: refusal without check-merge-conflict."; echo "$OUT"; exit 1; }

# Doctor: simulated GitHub API, never the real one. Responses copied from the NapkinStack
# repository's, then degraded: bare repository, token without the Administration permission.
API="$GN/api"
mkdir -p "$API"
python3 - "$API/routes.json" <<'EOF'
import json, sys
rules = [
    {"type": "deletion", "ruleset_id": 1}, {"type": "non_fast_forward", "ruleset_id": 1},  # G17, G18 (D78)
    {"type": "pull_request", "ruleset_id": 1, "parameters": {"required_approving_review_count": 1, "require_code_owner_review": True,
                                                             "dismiss_stale_reviews_on_push": True}},
    {"type": "required_status_checks", "ruleset_id": 1, "parameters": {"required_status_checks": [
        {"context": "Fitness functions"}, {"context": "PR scope and review budget"}, {"context": "Hooks and secrets"},
        {"context": "Test sheet and cycle"}, {"context": "Module checks"}]}},
]
labels = {"/labels/cross-module": {"name": "cross-module"}, "/labels/over-budget": {"name": "over-budget"},
          "/labels/out-of-cycle": {"name": "out-of-cycle"}}
ruleset = {"/rulesets/1?includes_parents=true": {"id": 1, "bypass_actors": []}}
active = {"status": "enabled"}
# G14 to G16: shaped as the rules want them. Readable without the Administration permission
# and settable on any plan, which is why they carry no PRIVATE_PLAN entry (D61).
merges_ok = {"allow_auto_merge": True, "allow_squash_merge": True, "allow_merge_commit": False,
             "allow_rebase_merge": False, "delete_branch_on_merge": True, "default_branch": "main"}
# GitHub's own defaults for a fresh repository: auto-merge off, three methods allowed, branches kept.
# G19: a default branch the workflows do not watch, as a repository created before "main" was.
merges_default = {"allow_auto_merge": False, "allow_squash_merge": True, "allow_merge_commit": True,
                  "allow_rebase_merge": True, "delete_branch_on_merge": False, "default_branch": "master"}
compliant = {
    "": {"security_and_analysis": {"secret_scanning": active, "secret_scanning_push_protection": active},
         **merges_ok},
    "/rules/branches/main": rules,
    "/private-vulnerability-reporting": {"enabled": True},
    "/actions/permissions": {"enabled": True, "allowed_actions": "selected", "sha_pinning_required": True},
    "/actions/permissions/selected-actions": {"github_owned_allowed": True, "patterns_allowed": ["astral-sh/setup-uv@*"]},
    "/actions/permissions/fork-pr-contributor-approval": {"approval_policy": "all_external_contributors"},
    "/actions/permissions/workflow": {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
    **labels, **ruleset,
}
inactive = {"status": "disabled"}
bare = {
    "": {"security_and_analysis": {"secret_scanning": inactive, "secret_scanning_push_protection": inactive},
         **merges_default},
    "/rules/branches/main": [],
    "/private-vulnerability-reporting": {"enabled": False},
    "/actions/permissions": {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False},
    "/actions/permissions/fork-pr-contributor-approval": {"approval_policy": "first_time_contributors"},
    "/actions/permissions/workflow": {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True},
}
restricted = {"": {}, "/rules/branches/main": rules, **labels}
compliant[""]["visibility"] = "public"
bare[""]["visibility"] = "public"
actions = {path: response for path, response in compliant.items() if path.startswith("/actions/")}
private = {
    "": {"visibility": "private", "security_and_analysis": {"secret_scanning": inactive, "secret_scanning_push_protection": inactive},
         **merges_ok},
    "/rules/branches/main": [],
    **actions, **labels,
}
private_team = {path: response for path, response in compliant.items() if path != "/private-vulnerability-reporting"}
private_team[""] = {**compliant[""], "visibility": "private"}
bypass = {**compliant, "/rulesets/1?includes_parents=true": {"id": 1, "bypass_actors": [
    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]}}
stale = {**compliant, "/rules/branches/main": [*rules[:2], {**rules[2], "parameters": {**rules[2]["parameters"],
          "dismiss_stale_reviews_on_push": False}}, rules[3]]}
# Stricter than the checklist asks: two approvals. The settings command must leave it alone (PDR-0008).
strict = {**compliant, "/rules/branches/main": [*rules[:2], {**rules[2], "parameters": {**rules[2]["parameters"],
          "required_approving_review_count": 2}}, rules[3]]}
# Only its own actions allowed: stricter than "selected", and missing the SHA pinning.
local_only = {**compliant, "/actions/permissions": {"enabled": True, "allowed_actions": "local_only",
                                                    "sha_pinning_required": False}}
json.dump({"acme/compliant": compliant, "acme/bare": bare, "acme/restricted": restricted,
           "acme/private": private, "acme/private-team": private_team, "acme/bypass": bypass,
           "acme/stale": stale, "acme/strict": strict, "acme/local-only": local_only}, open(sys.argv[1], "w"))
EOF
cat > "$API/server.py" <<'EOF'
import http.server, json, pathlib, sys
routes = json.loads(pathlib.Path(sys.argv[1]).read_text())
class API(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        status, body = 404, {"message": "Not Found"}
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            status, body = 401, {"message": "Requires authentication"}
        elif self.path.startswith("/repos/"):
            owner, name, *rest = self.path.removeprefix("/repos/").split("/")
            repo, path = f"{owner}/{name}", ("/" + "/".join(rest)) if rest else ""
            if path in routes.get(repo, {}):
                status, body = 200, routes[repo][path]
            elif repo == "acme/restricted" and not path.startswith("/labels/"):
                status, body = 403, {"message": "Resource not accessible by personal access token"}
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
    def write(self):
        # Nothing in this suite may ever write to the forge: every attempt is recorded, and
        # the settings command is judged on this file staying empty (PDR-0008, criterion 1).
        with open(sys.argv[3], "a") as seen:
            seen.write(f"{self.command} {self.path}\n")
        self.send_response(403)
        self.end_headers()
    do_POST = do_PUT = do_PATCH = do_DELETE = write
    def log_message(self, *args):
        pass
server = http.server.HTTPServer(("127.0.0.1", 0), API)
pathlib.Path(sys.argv[2]).write_text(str(server.server_port))
server.serve_forever()
EOF
: > "$API/writes"
python3 "$API/server.py" "$API/routes.json" "$API/port" "$API/writes" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null; rm -rf "$SK" "$SC" "$HK" "$GN"' EXIT
for _ in $(seq 50); do [ -s "$API/port" ] && break; sleep 0.1; done
export GITHUB_API_URL="http://127.0.0.1:$(cat "$API/port")"
# No run of the oracle asks the real registry; the newer-version line has its own case (D91).
export NSTACK_REGISTRY_URL="http://127.0.0.1:9"

V=$(nstack --version | cut -d' ' -f2)
# Tag of the engine version. The throwaway template uses v90.x so that its versions can
# never be mistaken for a real engine version: project A must stay behind the installed
# engine for the L1 gap to exist, and project C must match it exactly. The guard below
# keeps the suite working even then, should the engine ever reach v90.x.
if ! git -C "$TPL" rev-parse -q --verify "refs/tags/v$V" >/dev/null; then
  git "${GIT_ID[@]}" -C "$TPL" commit -q --allow-empty --no-verify -m "v$V"
  git -C "$TPL" tag "v$V"
fi
C="$GN/project-c"
INIT_OUT=$(nstack init "$C" --source "$TPL" --ref "v$V" --project-name "Project C" \
  --github-repo acme/compliant --owner-team acme/platform 2>&1) \
  || { echo "FAIL: nstack init of project C."; echo "$INIT_OUT"; exit 1; }
repo_c() { in_place "s#^github_repo: .*#github_repo: $1#" "$C/.copier-answers.yml"; }
# Project C as the published template would have made it: its source a repository (L7).
in_place "s#^_src_path: .*#_src_path: https://github.com/NapkinStack/engineering-os.git#" "$C/.copier-answers.yml"
# The engine under test as the registry installs it: no direct_url.json, so published. The
# engine this suite runs is a checkout, unpublished, and has its own test below (PDR-0005).
published() {
  python3 - "$@" <<'PY'
import sys
from napkinstack import __version__, cli, provenance
provenance.engine = lambda: (__version__, None)
sys.exit(cli.main(sys.argv[1:]))
PY
}

echo "-> init: GitHub checklist printed, identical to the foundation manual and to the CI jobs"
[ "$(echo "$INIT_OUT" | grep -cF -- '- [ ] ')" -eq 19 ] && echo "$INIT_OUT" | grep -qF "nstack doctor" \
  || { echo "FAIL: checklist missing from the init output."; echo "$INIT_OUT"; exit 1; }
echo "$INIT_OUT" | grep -F -- '- [ ] ' | sed 's/^ *//' | while IFS= read -r line; do
  grep -qF -- "$line" skeleton/.nstack/handbook/INSTALL.md.jinja \
    || { echo "FAIL: '$line' missing from the foundation manual (.nstack/handbook/INSTALL.md)."; exit 1; }
done
python3 - "$(echo "$INIT_OUT" | grep -F 'Required checks')" <<'EOF' || exit 1
import re, sys, yaml
jobs = {workflow: [job["name"] for job in yaml.safe_load(
            open(f"skeleton/.github/workflows/{workflow}", encoding="utf-8"))["jobs"].values()]
        for workflow in ("governance.yml", "pull-request.yml", "module-checks.yml")}
# Every job of the two rule workflows is required; of the module workflow, only the job that
# fails when any module failed: the matrix jobs carry names no ruleset knows in advance.
names = jobs["governance.yml"] + jobs["pull-request.yml"] + ["Module checks"]
absents = [name for name in names if f"`{name}`" not in sys.argv[1]]
if absents:
    sys.exit(f"FAIL: skeleton CI jobs missing from the checklist (G4): {absents}")
unknown = [name for name in re.findall(r"`([^`]+)`", sys.argv[1]) if name not in sum(jobs.values(), [])]
if unknown:
    sys.exit(f"FAIL: required checks no skeleton job produces (G4): {unknown}")
EOF

echo "-> module checks: one job runs every changed module; a failure stops neither the next module nor V1 (D46, ADR-0005)"
MC=$(mktemp -d)
mkdir -p "$MC/bin" "$MC/project/.nstack" "$MC/project/modules/a" "$MC/project/modules/b"
cp skeleton/.nstack/check-modules.sh "$MC/project/.nstack/"
printf 'module:\n  name: a\n  criticality: high\n' > "$MC/project/modules/a/MANIFEST.yaml"
printf 'module:\n  name: b\n  criticality: "standard"\n' > "$MC/project/modules/b/MANIFEST.yaml"
# A fake engine: it lists two modules, logs every verb, and fails the tests of module a.
printf '%s\n' '#!/usr/bin/env bash' \
  'if [ "$1" = modules ]; then printf "a\tmodules/a\nb\tmodules/b\n"; exit 0; fi' \
  'echo "$1 $2" >> "$CALLS"' \
  '[ "$1 $2" != "test a" ]' > "$MC/bin/nstack"
chmod +x "$MC/bin/nstack"
checks() {  # $1 = RUNNER_ENVIRONMENT; prints the script's output, its verbs logged in $MC/calls
  : > "$MC/calls"
  (cd "$MC/project" && CALLS="$MC/calls" RUNNER_ENVIRONMENT="$1" BASE=HEAD PATH="$MC/bin:$PATH" \
     bash .nstack/check-modules.sh 2>&1)
}
if OUT=$(checks github-hosted); then echo "FAIL: a module whose tests failed passed the job."; echo "$OUT"; exit 1; fi
CALLS=$(tr '\n' ',' < "$MC/calls")
[ "$CALLS" = "bootstrap a,check a,test a,compat a,bootstrap b,check b,test b,compat b,e2e b," ] \
  && echo "$OUT" | grep -qF "Criticality: high" && echo "$OUT" | grep -qF "Criticality: standard" \
  && echo "$OUT" | grep -qF "Module checks failed: a" \
  || { echo "FAIL: every module, V1 after a failure, e2e only when green — not what ran."; echo "$CALLS"; echo "$OUT"; exit 1; }
checks self-hosted >/dev/null || true
[ "$(grep -c '^clean ' "$MC/calls")" -eq 2 ] \
  || { echo "FAIL: a self-hosted runner kept what a module's job left (D106)."; cat "$MC/calls"; exit 1; }
rm -rf "$MC"

echo "-> module checks: a contract change verifies both sides (D53)"
grep -qF -- "--with-contract-sides" skeleton/.nstack/check-modules.sh \
  || { echo "FAIL: the module checks no longer ask for the contract's sides (D53)."; exit 1; }

echo "-> the record: the project receives it, read-only, and the engine knows its name (W1)"
python3 - "$C" <<'EOF' || exit 1
import pathlib, sys, yaml
from napkinstack import landed
project = pathlib.Path(sys.argv[1])
workflow = project / landed.RECORD
if not workflow.is_file():
    sys.exit(f"FAIL: a generated project does not carry the record at {landed.RECORD} (PDR-0006).")
data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
# Read only (G10): how each commit arrived, and the record's own last success (actions).
if data["permissions"] != {"contents": "read", "pull-requests": "read", "actions": "read"}:
    sys.exit(f"FAIL: the record must need no write access (G10): {data['permissions']}")
steps = [step for job in data["jobs"].values() for step in job["steps"]]
if not any("nstack landed" in str(step.get("run", "")) for step in steps):
    sys.exit("FAIL: the record's workflow does not run nstack landed.")
if not any(step.get("with", {}).get("fetch-depth") == 0 for step in steps):
    sys.exit("FAIL: the record needs the history to know what predates it (fetch-depth: 0).")
EOF

echo "-> doctor: workstation gaps listed with their action (L1, L3, L6, L7)"
# L1 compares the installed engine with the project version. The condition is built here
# rather than inherited from project A, whose version would otherwise have to differ from
# the engine's by luck: it did not, at v0.2.0, and the rule silently stopped being tested.
in_place 's#^_commit: .*#_commit: v0.0.1#' "$A/.copier-answers.yml"
in_place '/^\*/d' "$A/.github/CODEOWNERS"
echo "# What the product is" > "$A/PRODUCT.md"  # a product may write about itself under any name (D79)
if OUT=$(GH_TOKEN=fake-token nstack doctor --root "$A" 2>&1); then
  echo "FAIL: non-compliant workstation accepted."; echo "$OUT"; exit 1
fi
if echo "$OUT" | grep -qF "PRODUCT.md"; then
  echo "FAIL: doctor still judges a file named PRODUCT.md (L4 is retired)."; echo "$OUT"; exit 1
fi
rm "$A/PRODUCT.md"
for rule in L1 L3 L6 L7; do
  echo "$OUT" | grep -qE "FAIL +\[$rule\]" \
    || { echo "FAIL: gap $rule not reported."; echo "$OUT"; exit 1; }
done
echo "$OUT" | grep -qF "Action: pre-commit install" && echo "$OUT" | grep -qF 'make `*  @<owner>` its first rule' \
  || { echo "FAIL: L3 or L6 action missing."; echo "$OUT"; exit 1; }

echo "-> doctor: a newer published version is named, as information; a silent registry is said (D91)"
REG=$(mktemp -d); mkdir -p "$REG/pypi/napkinstack"
echo '{"info": {"version": "99.0.0"}}' > "$REG/pypi/napkinstack/json"
in_place "s#^_commit: .*#_commit: v$V#" "$A/.copier-answers.yml"
OUT=$(NSTACK_REGISTRY_URL="file://$REG" GH_TOKEN=fake-token nstack doctor --root "$A" 2>&1) || true
echo "$OUT" | grep -qF "NEWER VERSION  v99.0.0 is published; the project is on v$V — information, not a gap" \
  && echo "$OUT" | grep -qF 'uv tool install "napkinstack==99.0.0"' \
  || { echo "FAIL: doctor does not name a newer published version."; echo "$OUT"; exit 1; }
OUT=$(GH_TOKEN=fake-token nstack doctor --root "$A" 2>&1) || true
echo "$OUT" | grep -qF "NOT READ       the registry did not answer" \
  || { echo "FAIL: a registry that does not answer is not said."; echo "$OUT"; exit 1; }
rm -rf "$REG"

(cd "$C" && pre-commit install >/dev/null)
in_place 's#<One sentence: what this project does.>#Demo project.#' "$C/README.md"

echo "-> doctor: GitHub repository without settings, every gap listed with its action (criterion 2)"
repo_c acme/bare
if OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: repository without settings accepted."; echo "$OUT"; exit 1
fi
# PDR-0007, criterion 6: what framing buys, and the gesture that starts it — said by the
# diagnosis, in one place and once. The project is unframed; that is not one of its gaps.
[ "$(echo "$OUT" | grep -cF "Framing buys an appetite, an end date, a circuit breaker and a decider")" -eq 1 ] \
  && echo "$OUT" | grep -qF "To start: follow .nstack/playbooks/framing.md" \
  && echo "$OUT" | grep -qE "^  UNFRAMED +no accepted charter — a stage, not a gap" \
  || { echo "FAIL: doctor does not say once what framing buys."; echo "$OUT"; exit 1; }
for rule in G1 G2 G3 G4 G5 G6 G7 G8 G9 G10 G11 G12 G13 G14 G15 G16 G17 G18 G19; do
  echo "$OUT" | grep -qE "FAIL +\[$rule\]" \
    || { echo "FAIL: gap $rule not reported."; echo "$OUT"; exit 1; }
done
[ "$(echo "$OUT" | grep -cF 'Action: Settings')" -ge 13 ] && echo "$OUT" | grep -qE "OK +\[L1\]" \
  || { echo "FAIL: actions or workstation incorrect."; echo "$OUT"; exit 1; }
# P6: each of the three merge rules names the place to go, not just the rule it broke (D61).
[ "$(echo "$OUT" | grep -cF 'Action: Settings → General → Pull Requests')" -eq 3 ] \
  || { echo "FAIL: G14-G16 without their setting's location."; echo "$OUT"; exit 1; }
echo "$OUT" | grep -qF "This repository: unguarded" && echo "$OUT" | grep -qF "Not yet in place" \
  || { echo "FAIL: a public repository with no settings is unguarded, its gaps reachable (PDR-0006)."; echo "$OUT"; exit 1; }

echo "-> doctor: checklist applied, the command exits successfully (criterion 2)"
repo_c acme/compliant
if ! OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: compliant project refused."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "nstack doctor: compliant." && [ "$(echo "$OUT" | grep -cE '^  OK +\[')" -eq 24 ] \
  || { echo "FAIL: compliance badly reported."; echo "$OUT"; exit 1; }
echo "$OUT" | grep -qF "This repository: guarded" && ! echo "$OUT" | grep -qF "unguarded" \
  || { echo "FAIL: a repository whose barriers are in force must read guarded (PDR-0006)."; echo "$OUT"; exit 1; }

echo "-> doctor: no ruleset at all, G12 names the ruleset to create, not an actor to remove (D25)"
repo_c acme/bare
OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1) || true
echo "$OUT" | grep -A1 -E "FAIL +\[G12\]" | grep -qF "create the ruleset first (G1)" \
  && echo "$OUT" | grep -A2 -E "FAIL +\[G4\]" | grep -qF "only once it has run" \
  || { echo "FAIL: G12 or G4 action misleading without a ruleset."; echo "$OUT"; exit 1; }

echo "-> doctor: an approval that survives a push is a gap (G13, D31)"
repo_c acme/stale
if OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: stale approvals kept, reported compliant."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "FAIL +\[G13\]" && echo "$OUT" | grep -qE "OK +\[G2\]" \
  && echo "$OUT" | grep -qF "dismiss stale pull request approvals" \
  || { echo "FAIL: stale approvals badly reported."; echo "$OUT"; exit 1; }

echo "-> doctor: a bypass actor on the main branch's ruleset is a gap (G12, ADR-0004)"
repo_c acme/bypass
if OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: a bypassable ruleset accepted."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "FAIL +\[G12\]" && echo "$OUT" | grep -qE "OK +\[G1\]" \
  && echo "$OUT" | grep -qF "remove every bypass actor" \
  || { echo "FAIL: bypass actor badly reported."; echo "$OUT"; exit 1; }

echo "-> doctor: private repository on the Free plan is unguarded, and not at fault for it (PDR-0006)"
repo_c acme/private
if ! OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: a project that has done everything its plan allows must not be reported as faulty."
  echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "NOT APPLICABLE +\[G6\]" \
  && [ "$(echo "$OUT" | grep -cE '^  OUT OF REACH +\[')" -eq 9 ] \
  && echo "$OUT" | grep -qF "Secret Protection is a paid option" \
  && echo "$OUT" | grep -qE "OK +\[G7\]" \
  || { echo "FAIL: private repository on the Free plan badly reported."; echo "$OUT"; exit 1; }
echo "$OUT" | grep -qF "This repository: unguarded" \
  && echo "$OUT" | grep -qF "Out of reach on this plan" \
  && echo "$OUT" | grep -qF "make the repository public" \
  && ! echo "$OUT" | grep -qE "^FAIL +\[G1\]" \
  || { echo "FAIL: the unguarded state, its reason and its exits must be named (PDR-0006)."; echo "$OUT"; exit 1; }

echo "-> doctor: private repository under GitHub Team, compliant without private reporting"
repo_c acme/private-team
if ! OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: compliant private repository refused."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "nstack doctor: compliant" && echo "$OUT" | grep -qE "NOT APPLICABLE +\[G6\]" \
  && [ "$(echo "$OUT" | grep -cE '^  OK +\[')" -eq 23 ] \
  || { echo "FAIL: compliant private repository badly reported."; echo "$OUT"; exit 1; }

echo "-> doctor: without a token, the GitHub part is not verified, never compliant — and exits 2, not 1 (D77)"
RC=0; OUT=$(unset GH_TOKEN GITHUB_TOKEN; published doctor --root "$C" 2>&1) || RC=$?
[ "$RC" -eq 2 ] || { echo "FAIL: nothing read and nothing missing must exit 2, got $RC."; echo "$OUT"; exit 1; }
echo "$OUT" | grep -qE "NOT VERIFIED +\[G11\]" && ! echo "$OUT" | grep -qE "OK +\[G" \
  && echo "$OUT" | grep -qF "GH_TOKEN" \
  || { echo "FAIL: missing token mishandled."; echo "$OUT"; exit 1; }
echo "$OUT" | grep -qF "This repository: not verified" \
  || { echo "FAIL: what cannot be read is never guarded (PDR-0006)."; echo "$OUT"; exit 1; }

echo "-> doctor: token without the Administration permission, unreadable settings are not verified"
repo_c acme/restricted
if OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: compliant without the Administration permission."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "OK +\[G1\]" && echo "$OUT" | grep -qE "NOT VERIFIED +\[G5\]" \
  && echo "$OUT" | grep -qE "NOT VERIFIED +\[G8\]" && echo "$OUT" | grep -qF "Administration: read" \
  && echo "$OUT" | grep -qE "NOT VERIFIED +\[G12\]" \
  || { echo "FAIL: missing permission mishandled."; echo "$OUT"; exit 1; }

echo "-> doctor: API unreachable, nothing is declared compliant"
if OUT=$(GITHUB_API_URL=http://127.0.0.1:9 GH_TOKEN=fake-token published doctor --root "$C" 2>&1); then
  echo "FAIL: compliant without the API."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qE "NOT VERIFIED +\[G1\]" && echo "$OUT" | grep -qF "unreachable" \
  || { echo "FAIL: unreachable API mishandled."; echo "$OUT"; exit 1; }

echo "-> doctor: the engine of a checkout is unpublished, a gap and never compliance (L1, PDR-0005)"
repo_c acme/compliant
if OUT=$(GH_TOKEN=fake-token nstack doctor --root "$C" 2>&1); then
  echo "FAIL: an unpublished engine reported compliant."; echo "$OUT"; exit 1
fi
echo "$OUT" | head -1 | grep -qF "Judged by an UNPUBLISHED NapkinStack — a local checkout" \
  && echo "$OUT" | grep -qE "FAIL +\[L1\]" && echo "$OUT" | grep -qF "The nstack running is unpublished" \
  && echo "$OUT" | grep -qF "1 gap(s), 0 not verified" \
  || { echo "FAIL: unpublished engine badly reported."; echo "$OUT"; exit 1; }

echo "-> doctor: a gap exits 1 even when other settings were not read (D77)"
repo_c acme/bare
RC=0; OUT=$(GH_TOKEN=fake-token published doctor --root "$C" 2>&1) || RC=$?
[ "$RC" -eq 1 ] && echo "$OUT" | grep -qF "as calls to run yourself: nstack settings" \
  || { echo "FAIL: a gap must exit 1 and name the command that plans its closing, got $RC."; echo "$OUT"; exit 1; }

echo "-> settings: a bare repository gets the calls that close the distance, and nothing is written (PDR-0008, criterion 1)"
OUT=$(GH_TOKEN=fake-secret-token-value nstack settings --root "$C" 2>&1) \
  || { echo "FAIL: the plan of a readable repository must exit 0."; echo "$OUT"; exit 1; }
echo "$OUT" | grep -qF "gh api --method POST repos/acme/bare/rulesets" \
  && echo "$OUT" | grep -qF '"~DEFAULT_BRANCH"' && echo "$OUT" | grep -qF '"bypass_actors": []' \
  && echo "$OUT" | grep -qF '"type": "deletion"' && echo "$OUT" | grep -qF '"type": "non_fast_forward"' \
  && echo "$OUT" | grep -qF '"context": "Test sheet and cycle"' \
  && echo "$OUT" | grep -qF "gh api --method PATCH repos/acme/bare " \
  && echo "$OUT" | grep -qF '"allow_merge_commit": false' \
  && echo "$OUT" | grep -qF "gh api --method PUT repos/acme/bare/private-vulnerability-reporting" \
  && echo "$OUT" | grep -qF '"sha_pinning_required": true' \
  && echo "$OUT" | grep -qF '"name": "out-of-cycle"' \
  && echo "$OUT" | grep -qF "Nothing was changed" && echo "$OUT" | grep -qF "Then: nstack doctor" \
  || { echo "FAIL: the plan of a bare repository is incomplete."; echo "$OUT"; exit 1; }
[ ! -s "$API/writes" ] || { echo "FAIL: the settings command wrote to the forge:"; cat "$API/writes"; exit 1; }
if echo "$OUT" | grep -qF "fake-secret-token-value"; then
  echo "FAIL: the credential appears in the output (PDR-0008, criterion 8)."; exit 1
fi

echo "-> settings: a compliant repository gets no call (criterion 4)"
repo_c acme/compliant
OUT=$(GH_TOKEN=fake-token nstack settings --root "$C" 2>&1)
echo "$OUT" | grep -qF "nothing to change: the checklist is in place" && ! echo "$OUT" | grep -qF "gh api" \
  || { echo "FAIL: a compliant repository was given something to do."; echo "$OUT"; exit 1; }

echo "-> settings: what is stricter than the checklist is left alone, and said (criterion 5)"
repo_c acme/strict
OUT=$(GH_TOKEN=fake-token nstack settings --root "$C" 2>&1)
! echo "$OUT" | grep -qF "gh api" \
  || { echo "FAIL: two required approvals were planned down to the checklist's one."; echo "$OUT"; exit 1; }
repo_c acme/local-only
OUT=$(GH_TOKEN=fake-token nstack settings --root "$C" 2>&1)
echo "$OUT" | grep -qF '"allowed_actions": "local_only"' && echo "$OUT" | grep -qF "stricter than the checklist" \
  && ! echo "$OUT" | grep -qF "selected-actions" \
  || { echo "FAIL: a repository allowing only its own actions was planned open."; echo "$OUT"; exit 1; }

echo "-> settings: an existing bypass list is never emptied by a call, only named (PDR-0008: no ruleset rewritten)"
repo_c acme/bypass
OUT=$(GH_TOKEN=fake-token nstack settings --root "$C" 2>&1)
echo "$OUT" | grep -qF "G12 by hand" && ! echo "$OUT" | grep -qF "gh api" \
  || { echo "FAIL: a bypass list must be left to a human."; echo "$OUT"; exit 1; }

echo "-> settings: a private repository on a plan that enforces nothing is never called guarded (criterion 6)"
repo_c acme/private
OUT=$(GH_TOKEN=fake-token nstack settings --root "$C" 2>&1)
echo "$OUT" | grep -qF "Out of reach on this plan" && echo "$OUT" | grep -qF "stays UNGUARDED" \
  && echo "$OUT" | grep -qF "rulesets require the GitHub Team plan" && ! echo "$OUT" | grep -qF "rulesets --input" \
  && echo "$OUT" | grep -qF "nothing to change within what this plan allows" \
  || { echo "FAIL: a private repository on a free plan badly planned."; echo "$OUT"; exit 1; }

echo "-> settings: without a token the whole checklist is planned, and said to be unread"
repo_c acme/bare
OUT=$(unset GH_TOKEN GITHUB_TOKEN; nstack settings --root "$C" 2>&1)
echo "$OUT" | grep -qF "not read — no token" && echo "$OUT" | grep -qF "repos/acme/bare/rulesets" \
  && echo "$OUT" | grep -qF "On a private repository without a paid plan the forge refuses the ruleset" \
  && [ "$(echo "$OUT" | grep -c "^gh api ")" -ge 9 ] \
  || { echo "FAIL: the unread plan is incomplete."; echo "$OUT"; exit 1; }

echo "-> settings: a repository the token cannot read is said, never planned around"
if OUT=$(GITHUB_API_URL=http://127.0.0.1:9 GH_TOKEN=fake-token nstack settings --root "$C" 2>&1); then
  echo "FAIL: an unreachable repository was planned."; echo "$OUT"; exit 1
fi
echo "$OUT" | grep -qF "FAIL [settings] acme/bare cannot be read" \
  || { echo "FAIL: unreadable repository mishandled."; echo "$OUT"; exit 1; }
[ ! -s "$API/writes" ] || { echo "FAIL: something wrote to the forge during this suite:"; cat "$API/writes"; exit 1; }

echo "-> doctor: outside a project, the command MUST explain it"
if OUT=$(nstack doctor --root "$GN/occupied" 2>&1); then
  echo "FAIL: doctor accepted outside a project."; exit 1
fi
echo "$OUT" | grep -qF "FAIL [doctor] .copier-answers.yml not found" \
  || { echo "FAIL: expected message missing."; echo "$OUT"; exit 1; }

echo "Platform tests: OK"
