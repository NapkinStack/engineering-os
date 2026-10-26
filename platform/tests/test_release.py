"""
`nstack release` (D127): each module's `commands.release` makes its artefacts into its own
folder of the project's `dist/`, named to it by `NSTACK_DIST`, emptied first; a module that
assembles others' runs after them. Nothing assumed of the stack or the platform.
"""

from __future__ import annotations

import yaml

from napkinstack import cli


def module(root, name, release=None, assembles=None):
    folder = root / "modules" / name
    (folder / "tests").mkdir(parents=True)
    for file_ in ("AGENTS.md", "README.md"):
        (folder / file_).write_text("x\n", encoding="utf-8")
    (folder / "src.txt").write_text("code\n", encoding="utf-8")
    manifest = {"module": {"name": name, "responsibility": "Does one thing.", "owner": "acme/team",
                           "lifecycle": "active", "criticality": "standard", "user_facing": False},
                "provides": [], "consumes": [], "data": {"owns": [], "shared": []},
                "commands": {"check": "true", "test": "true", **({"release": release} if release else {})},
                "docs": {"readme": "README.md", "agents": "AGENTS.md"}}
    if assembles:
        manifest["assembles"] = assembles
    (folder / "MANIFEST.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")


def test_each_release_writes_into_its_own_artefacts_folder_assembled_ones_first(tmp_path, capsys):
    # "alpha" assembles "zeta": by name it would come first; it waits for what it assembles.
    module(tmp_path, "zeta", release='printf app > "$NSTACK_DIST/app.bin"')
    module(tmp_path, "alpha", release='cat "$NSTACK_DIST/../zeta/app.bin" > "$NSTACK_DIST/pack.bin"', assembles=["zeta"])
    module(tmp_path, "docs-only")
    (tmp_path / "dist" / "zeta").mkdir(parents=True)
    (tmp_path / "dist" / "zeta" / "stale.bin").write_text("old", encoding="utf-8")
    assert cli.main(["release", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    said = capsys.readouterr().out
    assert said.index("-> zeta") < said.index("-> alpha"), said
    assert "-> docs-only: release not declared" in said, said
    assert (tmp_path / "dist" / "alpha" / "pack.bin").read_text() == "app"
    assert not (tmp_path / "dist" / "zeta" / "stale.bin").exists(), "the folder was not emptied first"


def test_a_named_release_takes_what_follows_and_needs_its_command(tmp_path, capsys):
    module(tmp_path, "app", release='sh -c \'echo "$@" > "$NSTACK_DIST/asked"\' release')
    module(tmp_path, "bare")
    assert cli.main(["release", "app", "--target", "aarch64-apple-darwin", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    assert (tmp_path / "dist" / "app" / "asked").read_text().strip() == "--target aarch64-apple-darwin"
    capsys.readouterr()
    assert cli.main(["release", "bare", "--root", str(tmp_path)]) == 1
    said = capsys.readouterr().out
    assert "FAIL [release] module 'bare': commands.release not declared" in said and "Action:" in said, said


def test_an_artefacts_folder_that_is_a_link_is_refused_never_followed(tmp_path, capsys):
    module(tmp_path, "app", release='printf x > "$NSTACK_DIST/app.bin"')
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep").write_text("kept", encoding="utf-8")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "app").symlink_to(elsewhere)
    assert cli.main(["release", "app", "--root", str(tmp_path)]) == 1
    said = capsys.readouterr().out
    assert "FAIL [release]" in said and "Action:" in said, said
    assert (elsewhere / "keep").read_text() == "kept"


# --- D163: what a release empties is said (#276) ---------------------------------------------

def test_what_a_release_empties_is_said_by_name(tmp_path, capsys):
    module(tmp_path, "install", release='printf deb > "$NSTACK_DIST/app.deb"')
    (tmp_path / "dist" / "install" / "more").mkdir(parents=True)
    for name in ("app.rpm", "more/a", "more/b", "more/c", "more/d", "more/e"):
        (tmp_path / "dist" / "install" / name).write_text("old", encoding="utf-8")
    assert cli.main(["release", "install", "--root", str(tmp_path)]) == 0
    said = capsys.readouterr().out
    assert ("-> install: dist/install emptied first, 6 files: app.rpm, more/a, more/b, more/c, more/d, and 1 more"
            in said), said
    assert cli.main(["release", "install", "--root", str(tmp_path)]) == 0
    assert "dist/install emptied first, 1 file: app.deb" in capsys.readouterr().out
    (tmp_path / "dist" / "install" / "app.deb").unlink()
    assert cli.main(["release", "install", "--root", str(tmp_path)]) == 0
    assert "emptied" not in capsys.readouterr().out
