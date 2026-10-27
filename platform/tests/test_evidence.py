"""D140, PDR-0017, ADR-0009: a change's runs show what their logs said. Every case proves its rule
fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from napkinstack import evidence, modules
from napkinstack.fitness import manifests

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


# --- the level of a line (§3) --------------------------------------------------------------

@pytest.mark.parametrize("line, level", [
    ('{"level":"WARN","message":"device slow"}', "warning"),
    ('{"levelname": "ERROR", "msg": "boom"}', "error"),
    ('{"severity":"CRITICAL"}', "error"),
    ('{"level":40,"msg":"x"}', "warning"),
    ('{"level":50}', "error"),
    ('{"level":60}', "error"),
    ('{"level":0.7,"event":"loudness"}', "below"),  # an audio level is no log level
    ('{"level":3}', "below"),
    ('{"level":"info","msg":"x"}', "below"),
    ("time=2026 level=warn msg=slow", "warning"),
    ("ERROR could not open device", "error"),
    ("[WARN] slow", "warning"),
    ("2026-10-21T10:00:00Z WARNING: slow", "warning"),
    ("2026-10-21 10:00:00,123 WARNING msg", "warning"),
    ("2026/10/21 10:00:00 ERROR: x", "error"),
    ("[2026-10-21T10:00:00Z WARN  wholeheard] slow", "warning"),
    ("\x1b[33m WARN\x1b[0m slow", "warning"),
    ("warning: deprecated call", "warning"),
    ("(wholeheard:123): Gtk-WARNING **: 10:00: theme", "warning"),
    ("(wholeheard:123): GLib-CRITICAL **: assertion", "error"),
    ("INFO started", "below"),
    ("Error rate: 0%", None),  # prose, not a level
    ("Warning count is 3", None),
    ("the shell started", None),
])
def test_a_line_s_level_is_recognised_in_the_common_forms(line, level):
    assert evidence.level_of(line) == level


def test_the_module_s_own_expression_is_tried_first():
    own = evidence.compile_levels(r"^(?P<level>\w+)\|")
    assert evidence.level_of("err|disk full", own) == "error"
    assert evidence.level_of("info|fine", own) == "below"


# --- the declaration (§4, M12) --------------------------------------------------------------

def module(root: Path, name="capture", criticality="standard", evidence_section=None, e2e=None):
    folder = root / "modules" / name
    (folder / "tests").mkdir(parents=True, exist_ok=True)
    data = {"module": {"name": name, "responsibility": "Records sound.", "owner": "acme/team",
                       "lifecycle": "active", "criticality": criticality, "user_facing": False},
            "commands": {"check": "true", "test": "true", **({"e2e": e2e} if e2e else {})}}
    if evidence_section is not None:
        data["evidence"] = evidence_section
    import yaml
    (folder / "MANIFEST.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    for page in ("AGENTS.md", "README.md"):
        (folder / page).write_text(f"# {name}\n", encoding="utf-8")
    (folder / "code.py").write_text("x = 1\n", encoding="utf-8")
    return folder


@pytest.mark.parametrize("section, said", [
    ({"provoke": []}, "unknown key 'provoke'"),
    ({"provoked": {"pattern": "x"}}, "a list"),
    ({"provoked": [{"pattern": "(", "level": "error", "scenario": "S1"}]}, "does not compile"),
    ({"provoked": [{"pattern": ".*", "level": "error", "scenario": "S1"}]}, "matches an empty line"),
    ({"provoked": [{"pattern": "x", "level": "info", "scenario": "S1"}]}, "level"),
    ({"provoked": [{"pattern": "x", "level": "error", "scenario": ""}]}, "scenario"),
    ({"provoked": [{"pattern": "x", "level": "error", "scenario": "S1", "why": "y"}]}, "exactly"),
    ({"levels": "^(\\w+)"}, "group named level"),
])
def test_m12_refuses_a_declaration_that_would_check_nothing(tmp_path, capsys, section, said):
    module(tmp_path, evidence_section=section)
    assert manifests.run(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[M12]" in out and said in out


def test_m12_accepts_a_well_formed_declaration(tmp_path, capsys):
    module(tmp_path, evidence_section={"provoked": [{"pattern": "key refused", "level": "warning", "scenario": "S3"}],
                                       "levels": r"^(?P<level>\w+)\|"})
    manifests.run(tmp_path)
    assert "[M12]" not in capsys.readouterr().out


# --- report first, judge next, read from the project (§6) ------------------------------------

def project(tmp_path, *versions):
    """A project whose answers recorded these versions, one commit each."""
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=tmp_path, check=True)
    for version in versions:
        (tmp_path / ".copier-answers.yml").write_text(f"_commit: {version}\nproject_name: p\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", version], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.parametrize("versions, step", [
    (("v0.13.0", "v0.14.0"), "report"),               # the version that brings it
    (("v0.13.0", "v0.14.0", "v0.15.0"), "judge"),     # the next minor
    (("v0.13.0", "v0.15.0"), "report"),               # skipped the reporting version: one minor of reports
    (("v0.13.0", "v0.15.0", "v0.16.0"), "judge"),
    (("v0.14.0", "v0.14.2"), "report"),               # a patch is no next minor
    (("v0.14.0", "v0.15.0-3-gabc1234"), "judge"),     # an unpublished commit beyond it
])
def test_the_step_is_read_from_the_project_s_history(tmp_path, monkeypatch, versions, step):
    monkeypatch.setattr(evidence, "FIRST", (0, 14))
    assert evidence.step(project(tmp_path, *versions)) == step


def test_without_history_the_audit_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "FIRST", (0, 14))
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.16.0\n", encoding="utf-8")
    assert evidence.step(tmp_path) == "report"


# --- the audit (§5, §6) ----------------------------------------------------------------------

def write_logs(folder: Path, name: str, *lines: str):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


DECLARED = [{"pattern": "key refused", "level": "warning", "scenario": "S3"}]


def test_an_undeclared_error_fails_when_judging_and_is_quoted(tmp_path):
    write_logs(tmp_path, "shell.jsonl", '{"level":"ERROR","message":"device lost 42"}',
               '{"level":"WARN","message":"key refused"}')
    found = evidence.audit(tmp_path, DECLARED, "standard", "judge")
    assert found["verdict"] == "failed"
    assert [(line["file"], line["line"], line["level"]) for line in found["undeclared"]] == [("shell.jsonl", 1, "error")]


def test_an_undeclared_warning_is_reported_below_high_and_fails_from_high(tmp_path):
    write_logs(tmp_path, "a.log", "WARNING slow start")
    assert evidence.audit(tmp_path, [], "standard", "judge")["verdict"] == "reported"
    assert evidence.audit(tmp_path, [], "high", "judge")["verdict"] == "failed"
    assert evidence.audit(tmp_path, [], None, "judge")["verdict"] == "failed"  # unknown: judged as critical


def test_the_reporting_step_never_fails(tmp_path):
    write_logs(tmp_path, "a.log", "ERROR boom")
    assert evidence.audit(tmp_path, [], "critical", "report")["verdict"] == "reported"


def test_a_declaration_nothing_matched_is_said_never_failed(tmp_path):
    write_logs(tmp_path, "a.log", "INFO fine")
    found = evidence.audit(tmp_path, DECLARED, "standard", "judge")
    assert found["verdict"] == "passed" and found["stale"] == ["key refused"]


def test_a_file_whose_lines_cannot_be_classified_is_not_read_and_passes(tmp_path):
    write_logs(tmp_path, "odd.log", "the shell started", "the window opened")
    found = evidence.audit(tmp_path, [], "critical", "judge")
    assert found["verdict"] == "passed" and found["not_read"] == ["odd.log"]


def test_the_suggested_declaration_matches_its_line_again(tmp_path):
    write_logs(tmp_path, "a.jsonl", '{"level":"ERROR","message":"device 3f9a2c7d1e lost after 42 ms"}')
    found = evidence.audit(tmp_path, [], "standard", "report")
    suggested = found["undeclared"][0]["suggest"]
    import re
    assert re.search(suggested, "device 0badc0ffee lost after 7 ms")
    assert "42" not in suggested


def test_links_output_and_other_files_are_not_read(tmp_path):
    write_logs(tmp_path, "output.txt", "ERROR from the runner")
    write_logs(tmp_path, "notes.md", "ERROR in prose")
    outside = tmp_path.parent / "outside.log"
    outside.write_text("ERROR outside\n", encoding="utf-8")
    (tmp_path / "linked.log").symlink_to(outside)
    assert evidence.audit(tmp_path, [], "critical", "judge")["verdict"] == "passed"


# --- the run: folder, output, audit, record (§1, §2, §7) --------------------------------------

def e2e_project(tmp_path, script: str, criticality="standard", section=None,
                versions=("v0.13.0", "v0.14.0", "v0.15.0")):
    root = project(tmp_path, *versions)
    (tmp_path / "e2e.py").write_text(script, encoding="utf-8")
    module(root, criticality=criticality, evidence_section=section, e2e=f"{sys.executable} ../../e2e.py")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "module"], cwd=root, check=True)
    return root


@pytest.fixture
def judging(monkeypatch):
    monkeypatch.setattr(evidence, "FIRST", (0, 14))


def test_the_run_gets_its_folder_keeps_its_output_and_fails_on_an_undeclared_error(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "import os, pathlib\n"
                                 "print('scenario S1', flush=True)\n"
                                 "pathlib.Path(os.environ['NSTACK_EVIDENCE'], 'shell.log').write_text('ERROR lost\\n')\n")
    assert modules.run_verb(root, "e2e", "capture") == 1
    folder = root / "modules/capture/.evidence/e2e"
    assert "scenario S1" in (folder / "output.txt").read_text(encoding="utf-8")
    audit = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "failed" and audit["commit"]
    out = capsys.readouterr().out
    assert "scenario S1" in out and "shell.log:1" in out and "ERROR lost" in out


def test_a_command_that_fails_is_still_audited_and_keeps_its_traceback(tmp_path, judging):
    root = e2e_project(tmp_path, "raise SystemExit('broke in S5')\n")
    assert modules.run_verb(root, "e2e", "capture") != 0
    folder = root / "modules/capture/.evidence/e2e"
    assert "broke in S5" in (folder / "output.txt").read_text(encoding="utf-8")
    assert (folder / "audit.json").is_file()


def test_the_folder_is_emptied_before_a_run(tmp_path, judging):
    root = e2e_project(tmp_path, "print('ok')\n")
    stale = root / "modules/capture/.evidence/e2e/old.log"
    stale.parent.mkdir(parents=True)
    stale.write_text("ERROR from yesterday\n", encoding="utf-8")
    assert modules.run_verb(root, "e2e", "capture") == 0
    assert not stale.exists()


def test_a_folder_that_is_a_link_is_refused_and_nothing_emptied_through_it(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "print('ok')\n")
    elsewhere = tmp_path.parent / f"{tmp_path.name}-kept"
    elsewhere.mkdir()
    (elsewhere / "precious.txt").write_text("keep\n", encoding="utf-8")
    (root / "modules/capture/.evidence").symlink_to(elsewhere)
    assert modules.run_verb(root, "e2e", "capture") == 1
    assert (elsewhere / "precious.txt").exists() and "link" in capsys.readouterr().out


def test_a_child_that_keeps_the_output_open_does_not_hang_the_run(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "import subprocess, sys\n"
                                 "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                                 "print('left a child behind', flush=True)\n")
    import time
    began = time.monotonic()
    modules.run_verb(root, "e2e", "capture")
    assert time.monotonic() - began < 15
    assert "still holds" in capsys.readouterr().out


def test_bytes_that_are_not_utf8_are_kept_as_they_are(tmp_path, judging):
    root = e2e_project(tmp_path, "import sys\nsys.stdout.buffer.write(b'raw \\xff\\xfe bytes\\n')\n")
    modules.run_verb(root, "e2e", "capture")
    assert b"\xff\xfe" in (root / "modules/capture/.evidence/e2e/output.txt").read_bytes()


def test_the_attested_record_carries_the_audit_with_a_relative_path(tmp_path, judging):
    from napkinstack import attest

    root = e2e_project(tmp_path, "import os, pathlib\n"
                                 "pathlib.Path(os.environ['NSTACK_EVIDENCE'], 'a.log').write_text('WARNING slow\\n')\n")
    modules.run_verb(root, "e2e", "capture")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    found = attest.evidence_of(root, commit)
    assert found and found[0]["module"] == "capture"
    assert found[0]["folder"] == "modules/capture/.evidence/e2e"
    assert found[0]["audit"]["verdict"] == "reported"
    assert str(tmp_path) not in json.dumps(found)


# --- what the verifier of the build found --------------------------------------------------

def test_the_printed_declaration_pastes_into_the_manifest_and_matches_again(tmp_path, judging, capsys):
    import yaml
    root = e2e_project(tmp_path, "import os, pathlib\n"
                                 "pathlib.Path(os.environ['NSTACK_EVIDENCE'], 'a.log').write_text("
                                 "'\\x1b[31mERROR\\x1b[0m device 0xDEADbeef lost, id 3f2504e0-4f89-11d3-9a0c-0305e82c3301\\n')\n")
    assert modules.run_verb(root, "e2e", "capture") == 1
    printed = next(line for line in capsys.readouterr().out.splitlines() if "declare it:" in line)
    entry = yaml.safe_load(printed.split("declare it:", 1)[1].strip().replace("<the scenario that provokes it>", "S1"))
    manifest = root / "modules/capture/MANIFEST.yaml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    data["evidence"] = {"provoked": entry}
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    script = tmp_path / "e2e.py"
    script.write_text(script.read_text(encoding="utf-8").replace("0xDEADbeef", "0xCAFEf00d")
                      .replace("3f2504e0-4f89-11d3-9a0c-0305e82c3301", "6ba7b810-9dad-11d1-80b4-00c04fd430c8"), encoding="utf-8")
    assert modules.run_verb(root, "e2e", "capture") == 0


@pytest.mark.parametrize("pattern", [5, ["x"]], ids=["a number", "a list"])
def test_m12_requires_a_pattern_to_be_text(tmp_path, capsys, pattern):
    module(tmp_path, evidence_section={"provoked": [{"pattern": pattern, "level": "error", "scenario": "S1"}]})
    assert manifests.run(tmp_path) == 1
    assert "[M12]" in capsys.readouterr().out


def test_a_declaration_that_breaks_the_audit_still_leaves_an_audit_and_no_running_mark(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "print('ok')\n", section={"provoked": [{"pattern": "(", "level": "error", "scenario": "S1"}]})
    assert modules.run_verb(root, "e2e", "capture") == 1
    folder = root / "modules/capture/.evidence/e2e"
    assert not (folder / ".running").exists()


@pytest.mark.parametrize("line, level", [
    ("INFO user set level=error", "below"),   # a leading word before a logfmt value in the message
    ("- error: x", None),
    ("1 error: x", None),
])
def test_a_leading_word_comes_first_and_a_timestamp_is_a_timestamp(line, level):
    assert evidence.level_of(line) == level


def test_a_huge_single_line_is_read_without_holding_it_whole(tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    with open(folder / "big.log", "w", encoding="utf-8") as out:
        out.write("ERROR " + "x" * (30 * 1024 * 1024) + "\nINFO fine\n")
    import resource
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    found = evidence.audit(folder, [], "standard", "report")
    grown_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before
    assert found["undeclared"][0]["line"] == 1 and len(found["undeclared"]) == 1
    assert grown_kib < 20 * 1024


def test_the_record_keeps_at_most_ten_lines_of_log_text(tmp_path, judging):
    from napkinstack import attest

    lines = "".join(f"ERROR failure {n}\\n" for n in range(30))
    root = e2e_project(tmp_path, f"import os, pathlib\npathlib.Path(os.environ['NSTACK_EVIDENCE'], 'a.log').write_text('{lines}')\n")
    modules.run_verb(root, "e2e", "capture")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    audit = attest.evidence_of(root, commit)[0]["audit"]
    assert len(audit["undeclared"]) == 10 and audit["undeclared_count"] == 30


def test_the_failure_says_whether_the_command_failed_or_its_logs(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "import os, pathlib\npathlib.Path(os.environ['NSTACK_EVIDENCE'], 'a.log').write_text('ERROR x\\n')\n")
    modules.run_verb(root, "e2e", "capture")
    out = capsys.readouterr().out
    assert "exited with" not in out and "logged what it does not declare" in out


# --- a run that wrote nothing where nstack reads, or did not run (D144, #246) -------------------

@pytest.mark.parametrize("logs", [None, ("odd.log", "the shell started")], ids=["no log file", "no line classified"])
def test_a_run_that_declares_lines_and_wrote_no_log_the_audit_reads_fails_when_judged(tmp_path, logs):
    if logs:
        write_logs(tmp_path, *logs)
    tmp_path.mkdir(exist_ok=True)
    judged = evidence.audit(tmp_path, DECLARED, "standard", "judge")
    assert judged["verdict"] == "failed" and judged["silent"], (
        "a module declaring provoked lines whose run wrote no log here was checked against nothing (D144)")
    assert evidence.audit(tmp_path, DECLARED, "standard", "report")["verdict"] == "reported"


def test_a_run_that_declares_nothing_and_wrote_no_log_passes_and_says_so(tmp_path):
    found = evidence.audit(tmp_path, [], "critical", "judge")
    assert found["verdict"] == "passed" and not found["silent"]


def test_the_run_that_logged_elsewhere_fails_and_says_where_nstack_reads(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "print('logged elsewhere')\n", section={"provoked": DECLARED},
                       versions=("v0.14.0", "v0.15.0", "v0.16.0"))
    assert modules.run_verb(root, "e2e", "capture") == 1
    out = capsys.readouterr().out
    assert "wrote no log where nstack reads them" in out and "$NSTACK_EVIDENCE" in out and "exit 77" in out
    assert "0 undeclared" not in out, "the head says what failed: no log read, not zero lines (D144)"
    assert "did not happen" not in out, "nothing was read: a declaration matched nothing for want of a log (D144)"


@pytest.mark.parametrize("versions", [("v0.13.0", "v0.14.0", "v0.15.0"), ("v0.14.0",)], ids=["judge", "report"])
def test_a_run_that_cannot_run_here_exits_77_and_is_said_not_run(tmp_path, judging, capsys, versions):
    root = e2e_project(tmp_path, "print('e2e: NOT RUN — no sound server here')\nraise SystemExit(77)\n",
                       section={"provoked": DECLARED})
    if versions != ("v0.13.0", "v0.14.0", "v0.15.0"):
        (root / ".copier-answers.yml").write_text(f"_commit: {versions[0]}\nproject_name: p\n", encoding="utf-8")
    assert modules.run_verb(root, "e2e", "capture") == 0, "exit 77 is the run's own 'not run here' (D144)"
    audit = json.loads((root / "modules/capture/.evidence/e2e/audit.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "not run" and audit["exit"] == 77
    out = capsys.readouterr().out
    assert "not run here (exit 77)" in out and "did not happen" not in out


def test_the_tests_playbook_says_an_asserted_provoked_line_is_declared_too():
    text = (ROOT / "skeleton/.nstack/playbooks/tests.md").read_text(encoding="utf-8")
    declare = " ".join(text.split("- **Declare**", 1)[1].split("\n\n", 1)[0].split())
    assert "never both" not in declare, "tests.md: the audit reads only the manifest (D144, #245)"
    assert "asserts it too" in declare and "exits 77" in declare, "tests.md: how a run says it did not run (D144)"


def test_in_the_version_that_brings_it_a_silent_run_is_reported_though_undeclared_lines_are_judged(
        tmp_path, judging, capsys):
    # v0.14 judged undeclared lines from v0.15; silence is new in v0.15: reported there, judged from v0.16.
    root = e2e_project(tmp_path, "print('ran, logged elsewhere')\n", section={"provoked": DECLARED})
    assert modules.run_verb(root, "e2e", "capture") == 0, "a silent run reported for one minor first (#250)"
    out = capsys.readouterr().out
    assert "1 declared line(s) checked against nothing" in out and "no log here was read for" in out


def test_a_run_that_says_not_run_still_fails_when_its_audit_cannot_be_read(tmp_path, judging):
    root = e2e_project(tmp_path, "raise SystemExit(77)\n",
                       section={"provoked": [{"pattern": "(", "level": "error", "scenario": "S1"}]})
    assert modules.run_verb(root, "e2e", "capture") == 1


def test_a_command_that_crashed_is_blamed_for_its_exit_never_for_its_logs(tmp_path, judging, capsys):
    root = e2e_project(tmp_path, "raise SystemExit(3)\n", section={"provoked": DECLARED},
                       versions=("v0.14.0", "v0.15.0", "v0.16.0"))
    assert modules.run_verb(root, "e2e", "capture") == 3
    out = capsys.readouterr().out
    assert "exited with 3" in out and "wrote no log where nstack reads them —" not in out


# --- one end-to-end run at a time on a machine (#287) ----------------------------------------

def test_a_second_e2e_waits_for_the_first_and_says_for_whom(tmp_path, monkeypatch, judging, capsys):
    """Another run holds the machine's lock — another project, another session: this one waits, says
    so, and starts once it ends. What the run starts inherits the lock instead of waiting on it."""
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv(evidence.HELD, raising=False)
    root = e2e_project(tmp_path, "import os, pathlib, time\n"
                                 "print('held by', os.environ.get('NSTACK_E2E_HELD'), 'at', time.time(), flush=True)\n")
    holder = subprocess.Popen([sys.executable, "-c",
                               "import fcntl, sys, time\n"
                               "lock = open(sys.argv[1], 'a+')\n"
                               "fcntl.flock(lock, fcntl.LOCK_EX)\n"
                               "lock.write('shell, in /elsewhere, process 1, since then\\n'); lock.flush()\n"
                               "print('held', flush=True)\n"
                               "time.sleep(1.5)\n"
                               "print(time.time(), flush=True)\n",
                               str(runtime / "nstack-e2e.lock")], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "held"
    assert modules.run_verb(root, "e2e", "capture") == 0
    released = float(holder.stdout.readline())
    holder.wait()
    said = capsys.readouterr().out
    assert ("-> capture: waits for the end-to-end run already on this machine — "
            "shell, in /elsewhere, process 1, since then") in said, said
    started = float(said.split("held by 1 at ", 1)[1].split()[0])
    assert started >= released, said
    assert (runtime / "nstack-e2e.lock").read_text(encoding="utf-8") == ""  # nobody holds it now


def test_an_e2e_started_by_an_e2e_does_not_wait_for_its_parent(tmp_path, monkeypatch, judging, capsys):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv(evidence.HELD, "1")
    root = e2e_project(tmp_path, "print('ok')\n")
    import fcntl
    with open(runtime / "nstack-e2e.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert modules.run_verb(root, "e2e", "capture") == 0
    assert "waits for" not in capsys.readouterr().out
