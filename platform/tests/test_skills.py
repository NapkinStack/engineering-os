

def test_a_generated_skill_whose_playbook_is_gone_is_removed_never_a_person_s(tmp_path, capsys):
    """D220: a playbook an update removes left its skill loaded by the agent, said by no rule."""
    from napkinstack import skills

    playbooks = tmp_path / ".nstack" / "playbooks"
    playbooks.mkdir(parents=True)
    (playbooks / "kept.md").write_text("# Kept\n\nDo this.\n", encoding="utf-8")
    (tmp_path / ".nstack" / "skills.yaml").write_text(
        "skills:\n  kept:\n    source: .nstack/playbooks/kept.md\n    description: Use when keeping.\n", encoding="utf-8")
    gone = tmp_path / ".claude" / "skills" / "gone"
    gone.mkdir(parents=True)
    (gone / "SKILL.md").write_text("---\nname: gone\n---\n\n<!-- GENERATED from x by nstack skills - DO NOT EDIT.\n", encoding="utf-8")
    mine = tmp_path / ".claude" / "skills" / "mine"
    mine.mkdir()
    (mine / "SKILL.md").write_text("---\nname: mine\n---\n\nWritten by a person.\n", encoding="utf-8")
    assert skills.run(tmp_path) == 0
    assert not gone.exists() and (mine / "SKILL.md").is_file()
    assert "removed, their playbook gone: gone" in capsys.readouterr().out


def _project(root):
    playbooks = root / ".nstack" / "playbooks"
    playbooks.mkdir(parents=True)
    (playbooks / "kept.md").write_text("# Kept\n\nDo this.\n", encoding="utf-8")
    (root / ".nstack" / "skills.yaml").write_text(
        "skills:\n  kept:\n    source: .nstack/playbooks/kept.md\n    description: Use when keeping.\n", encoding="utf-8")


def test_the_skills_are_generated_for_every_agent_tool_the_same(tmp_path, capsys):
    """D245: Claude Code reads .claude/skills/; Codex and the Agent Skills tools read .agents/skills/.
    One playbook, one SKILL.md, in both."""
    from napkinstack import skills

    _project(tmp_path)
    assert skills.run(tmp_path) == 0
    claude = (tmp_path / ".claude/skills/kept/SKILL.md").read_text(encoding="utf-8")
    assert (tmp_path / ".agents/skills/kept/SKILL.md").read_text(encoding="utf-8") == claude
    out = capsys.readouterr().out
    assert ".claude/skills/" in out and ".agents/skills/" in out


def test_a_stale_skill_in_either_folder_fails_s3(tmp_path, capsys):
    from napkinstack import skills

    _project(tmp_path)
    assert skills.run(tmp_path) == 0
    (tmp_path / ".agents/skills/kept/SKILL.md").write_text("edited\n", encoding="utf-8")
    capsys.readouterr()
    assert skills.run(tmp_path, check_only=True) == 1
    assert "[S3] skill 'kept' out of sync with .nstack/playbooks/kept.md, in .agents/skills/" in capsys.readouterr().out


def test_s3_reads_only_the_folders_there_are(tmp_path, capsys):
    """A project that generated before D245 has .claude/skills/ alone: in sync, never failed for the other."""
    from napkinstack import skills

    _project(tmp_path)
    assert skills.run(tmp_path) == 0
    import shutil
    shutil.rmtree(tmp_path / ".agents")
    capsys.readouterr()
    assert skills.run(tmp_path, check_only=True) == 0, capsys.readouterr().out


def test_a_generated_skill_gone_is_removed_from_both_folders(tmp_path, capsys):
    from napkinstack import skills

    _project(tmp_path)
    for folder in (".claude", ".agents"):
        gone = tmp_path / folder / "skills" / "gone"
        gone.mkdir(parents=True)
        (gone / "SKILL.md").write_text("<!-- GENERATED from x by nstack skills - DO NOT EDIT.\n", encoding="utf-8")
    assert skills.run(tmp_path) == 0
    assert not (tmp_path / ".claude/skills/gone").exists() and not (tmp_path / ".agents/skills/gone").exists()


def test_a_skills_folder_git_ignores_is_said(tmp_path, capsys):
    """D252: the skills are committed; a .gitignore from before still leaving them out is said."""
    import subprocess

    from napkinstack import skills

    _project(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".claude/skills/\n", encoding="utf-8")
    assert skills.run(tmp_path) == 0
    out = capsys.readouterr().out
    assert "WARNING: .claude/skills/ is ignored by git" in out and ".agents/skills/ is ignored" not in out, out
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    assert skills.run(tmp_path) == 0
    assert "is ignored" not in capsys.readouterr().out


def test_an_update_regenerates_the_skills_where_the_project_declares_them(tmp_path):
    """D252: before the update's commit, so they travel in it; a project that never had them gets them."""
    from napkinstack import project

    _project(tmp_path)
    said = project._refresh_skills(tmp_path)
    assert said and "in the update's commit" in said, said
    assert (tmp_path / ".claude/skills/kept/SKILL.md").is_file() and (tmp_path / ".agents/skills/kept/SKILL.md").is_file()


def test_a_project_without_skills_is_not_given_any_by_an_update(tmp_path):
    from napkinstack import project

    assert project._refresh_skills(tmp_path) is None and not (tmp_path / ".claude").exists()


def test_the_review_budget_leaves_the_generated_skills_out():
    from napkinstack.fitness import pr_scope

    for path in (".claude/skills/tests/SKILL.md", ".agents/skills/tests/SKILL.md"):
        assert pr_scope.GENERATED.search(path), path
    assert not pr_scope.GENERATED.search(".claude/settings.json")
    assert not pr_scope.GENERATED.search("modules/billing/skills/x.py")


def test_the_skeleton_commits_the_skills_and_folds_them_in_review():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "skeleton"
    ignored = [line.strip() for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    assert not any("skills" in line for line in ignored), ignored
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert ".claude/skills/** linguist-generated=true" in attributes
    assert ".agents/skills/** linguist-generated=true" in attributes


def test_a_folder_holding_only_a_person_s_skills_is_not_read_by_s3(tmp_path, capsys):
    """D248: a project that keeps skills of its own in .agents/skills/, tracked, has that folder in a
    fresh clone with no generated skill in it: S3 does not ask for every playbook there."""
    from napkinstack import skills

    _project(tmp_path)
    mine = tmp_path / ".agents" / "skills" / "mine"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("---\nname: mine\n---\n\nWritten by a person.\n", encoding="utf-8")
    assert skills.run(tmp_path, check_only=True) == 0, capsys.readouterr().out
    assert skills.run(tmp_path) == 0  # generated there too, beside the person's
    assert (mine / "SKILL.md").read_text(encoding="utf-8").endswith("Written by a person.\n")
    capsys.readouterr()
    assert skills.run(tmp_path, check_only=True) == 0, "generated there, and in sync"


def test_a_folder_with_a_generated_skill_of_no_playbook_is_read(tmp_path, capsys):
    """The banner alone marks the folder as nstack's: a skill left from a playbook gone, beside a person's."""
    from napkinstack import skills

    _project(tmp_path)
    for name, text in (("gone", "<!-- GENERATED from x by nstack skills - DO NOT EDIT.\n"), ("mine", "Mine.\n")):
        (tmp_path / ".agents/skills" / name).mkdir(parents=True)
        (tmp_path / ".agents/skills" / name / "SKILL.md").write_text(text, encoding="utf-8")
    assert skills.run(tmp_path, check_only=True) == 1
    assert "[S3] skill 'kept' missing from .agents/skills/" in capsys.readouterr().out


def test_an_update_says_a_skills_folder_its_commit_left_out(tmp_path):
    """A .gitignore that still names a folder: the update says so, never "in the update's commit"."""
    import subprocess

    from napkinstack import project

    _project(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".claude/skills/\n.agents/skills/\n", encoding="utf-8")
    said = project._refresh_skills(tmp_path)
    assert said and "not all in the update's commit" in said and ".claude/skills/ is ignored by git" in said, said
