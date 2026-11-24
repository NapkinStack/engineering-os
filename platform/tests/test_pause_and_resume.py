"""Pause and resume (D282): a session ends without warning, and the next one must find where to
continue without re-reading the history. The state is the repository's — commits, pull requests,
holds —; a short note per clone, never committed, points into it.
"""

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
PLAYBOOK = (SKELETON / ".nstack/playbooks/pause-and-resume.md").read_text(encoding="utf-8")
NOTE = ".nstack/local/resume.md"


def _ignored(tmp_path: Path, paths: list[str]) -> set[str]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copy(SKELETON / ".gitignore", tmp_path / ".gitignore")
    for path in paths:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("x\n", encoding="utf-8")
    found = subprocess.run(["git", "-C", str(tmp_path), "check-ignore", *paths], capture_output=True, text=True)
    return set(found.stdout.split())


def test_the_resume_note_is_never_committed_and_the_framework_s_files_are(tmp_path):
    framework = [".nstack/playbooks/pause-and-resume.md", ".nstack/skills.yaml", ".nstack/handbook/project.md"]
    assert _ignored(tmp_path, [NOTE, *framework]) == {NOTE}, "the note must be ignored, and only it"


def test_a_skill_is_generated_from_the_playbook(tmp_path):
    from napkinstack import skills

    shutil.copytree(SKELETON / ".nstack", tmp_path / ".nstack")
    assert skills.run(tmp_path) == 0
    for folder in (".claude/skills", ".agents/skills"):
        text = (tmp_path / folder / "pause-and-resume/SKILL.md").read_text(encoding="utf-8")
        assert "name: pause-and-resume" in text and "renews its holds" in " ".join(text.split()), text[:600]
    assert skills.run(tmp_path, check_only=True) == 0


def test_the_playbook_s_note_holds_within_its_own_cap():
    """The example is what agents copy: over fifteen lines, the cap it states is already broken."""
    assert "Fifteen lines at most" in PLAYBOOK
    example = re.search(r"```markdown\n(.*?)```", PLAYBOOK, re.S)
    assert example and len(example.group(1).splitlines()) <= 15


def test_a_resume_reads_the_note_renews_holds_and_plans_once():
    resume = PLAYBOOK[PLAYBOOK.index("## Resume"):]
    steps = ["Read the note, and only the note", "nstack claim <id> --person <person> --session <this session>",
             "`nstack plan`, once", "Continue at the noted gesture"]
    positions = [resume.find(step) for step in steps]
    assert -1 not in positions and positions == sorted(positions), dict(zip(steps, positions))
    assert "--take-over" in resume, "outside nstack agent run a renewal is a take-over (D271): said"


def test_a_stop_leaves_nothing_only_in_the_tree_and_never_skips_a_hook():
    stop = PLAYBOOK[PLAYBOOK.index("## Stop"): PLAYBOOK.index("## The note")]
    for said in ("Commit", "push", "No background job", "worktrees", "Holds stay", "never `--no-verify`"):
        assert said in stop, said


def test_tool_memories_are_extras_never_the_source():
    assert "The source is the repository and the forge." in PLAYBOOK
