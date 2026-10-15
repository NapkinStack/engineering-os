"""
What a change must verify (D53): the modules with a changed file, and both sides of a contract
version it touches — the producer and the declared consumers (.nstack/handbook/03-contracts.md §5).
Run by platform/tests/run.sh.
"""

from __future__ import annotations

from napkinstack import modules
from test_compat import change, project


def folders(root, base, sides=False) -> list[str]:
    return [module["folder"] for module in modules.listing(root, base, sides)]


def test_a_contract_change_lists_both_sides(tmp_path):
    """D53: the producer's change never ran the consumer's checks. The declared graph says who
    must run, so no broker is needed inside one repository."""
    base = project(tmp_path)
    change(tmp_path)
    assert folders(tmp_path, base) == ["contracts"]
    assert folders(tmp_path, base, sides=True) == ["modules/billing", "modules/customers", "contracts"]


def test_a_module_change_lists_that_module_alone(tmp_path):
    """The neighbour: asking for the contract's sides adds nobody when no contract moved."""
    base = project(tmp_path)
    change(tmp_path, "modules/customers/src/app.py", "x\n")
    assert folders(tmp_path, base, sides=True) == ["modules/customers"]


def test_run_passes_what_follows_the_module_to_its_command(tmp_path, capfd):
    """D102: a module's `run` that takes an input — a folder to render into — is given it."""
    import yaml

    from napkinstack import cli

    folder = tmp_path / "modules" / "bench"
    folder.mkdir(parents=True)
    (folder / "bench.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    manifest = {"module": {"name": "bench"}, "commands": {"check": "true", "test": "true",
                                                         "run": "printf '[%s]' "}}
    (folder / "MANIFEST.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    assert cli.main(["run", "--root", str(tmp_path), "bench", "a folder", "6", "v2"]) == 0
    assert "[a folder][6][v2]" in capfd.readouterr().out
    # `--root` written after the module, as the other verbs take it, is still the root.
    assert cli.main(["run", "bench", "a folder", "--root", str(tmp_path)]) == 0
    assert "[a folder]" in capfd.readouterr().out


def test_clean_runs_the_declared_command_and_is_optional(tmp_path, capfd):
    """D106: a module removes what its commands left in its folder, when it declares how; a
    module that leaves nothing declares nothing."""
    import yaml

    from napkinstack import cli

    for name, commands in (("engine", {"clean": "rm -rf target"}), ("pages", {})):
        folder = tmp_path / "modules" / name
        (folder / "target").mkdir(parents=True)
        (folder / "target" / "build.o").write_bytes(b"\0")
        manifest = {"module": {"name": name}, "commands": {"check": "true", "test": "true", **commands}}
        (folder / "MANIFEST.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    assert cli.main(["clean", "--root", str(tmp_path)]) == 0
    assert not (tmp_path / "modules/engine/target").exists()
    assert (tmp_path / "modules/pages/target").exists()
    assert "pages: clean not declared, nothing to clean" in capfd.readouterr().out


def test_a_module_holds_no_register_of_its_own(tmp_path, capsys):
    """One register of decisions per project, at its root (PDR-0012, clarified 2026-10-15): the
    scaffold wrote an empty docs/adr/ in every module, named in its manifest and its page."""
    import yaml

    from napkinstack import cli

    assert cli.main(["new-module", "billing", "acme/billing", "standard", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    folder = tmp_path / "modules" / "billing"
    assert not (folder / "docs" / "adr").exists(), "the scaffold creates a folder of decisions in the module"
    assert "adr" not in (yaml.safe_load((folder / "MANIFEST.yaml").read_text(encoding="utf-8"))["docs"] or {})
    page = (folder / "README.md").read_text(encoding="utf-8")
    assert "`Scope: module billing`" in page, page
    assert "Scope: module billing" in output and "the project's docs/adr/" in output, output
