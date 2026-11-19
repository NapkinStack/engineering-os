

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


def test_a_folder_git_would_track_is_said(tmp_path, capsys):
    """A project whose .gitignore predates D245 would commit .agents/skills/: said, with the line to add."""
    import subprocess

    from napkinstack import skills

    _project(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".claude/skills/\n", encoding="utf-8")
    assert skills.run(tmp_path) == 0
    out = capsys.readouterr().out
    assert "WARNING: .agents/skills/ is not ignored by git" in out and ".claude/skills/ is not" not in out, out
    (tmp_path / ".gitignore").write_text(".claude/skills/\n.agents/skills/\n", encoding="utf-8")
    assert skills.run(tmp_path) == 0
    assert "is not ignored" not in capsys.readouterr().out


def test_an_update_says_a_skill_folder_git_would_track(tmp_path):
    """The regeneration after an update says the warning, never "not committed" over it."""
    import subprocess

    from napkinstack import project

    _project(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".claude/skills/\n", encoding="utf-8")
    (tmp_path / ".agents" / "skills").mkdir(parents=True)  # only the open layout generated so far
    said = project._refresh_skills(tmp_path)
    assert said and "WARNING: .agents/skills/ is not ignored by git" in said and "not committed" not in said, said
