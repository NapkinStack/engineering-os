

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
