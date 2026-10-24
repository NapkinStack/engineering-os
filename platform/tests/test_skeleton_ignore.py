"""The skeleton's .gitignore: it keeps secret files out, and never a project's source code.

macOS's file system ignores case, and git there ignores it too (core.ignorecase): a pattern
meant for secrets.json also matched Secrets.swift, a Keychain wrapper, which git then left out
of every commit without a word (D143).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IGNORE = ROOT / "skeleton/.gitignore"

SECRETS = ["secrets.env", "secrets.json", "secrets.yaml", "secrets.yml", "secrets.toml",
           "secrets.ini", "secrets.txt", ".envrc", "server.pem", "server.key", "id_ed25519"]
SOURCE = ["Secrets.swift", "secrets.py", "Secrets.kt", "secrets.ts", "Secrets.java", "secrets.go",
          "secrets.rs", "secrets.rb", "secrets.md"]


def ignored(tmp_path: Path, names: list[str]) -> set[str]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "core.ignorecase", "true"], check=True)
    shutil.copy(IGNORE, tmp_path / ".gitignore")
    for name in names:
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    found = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", *names],
                           capture_output=True, text=True)
    return set(found.stdout.split())


@pytest.mark.parametrize("name", SECRETS)
def test_a_secret_file_is_ignored(tmp_path, name):
    assert ignored(tmp_path, [name]) == {name}, f"{name} would be committed"


@pytest.mark.parametrize("name", SOURCE)
def test_source_code_named_secrets_is_never_ignored(tmp_path, name):
    assert ignored(tmp_path, [name]) == set(), (
        f"{name} is a source file: ignoring it leaves it out of every commit, silently (D143)")
