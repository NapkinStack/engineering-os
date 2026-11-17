"""#368: the labels `nstack attest` and `pr-check` judge were taken on the caller's word — a record
said "justified by label" of a label no pull request carried, and a run given none failed K3 on an
out-of-cycle pull request. Off the forge's own run, with a token and an open pull request at the
head, the labels are that pull request's; a label it does not carry is refused, never recorded."""

from __future__ import annotations

from pathlib import Path

import pytest

from napkinstack import hold, pull_request

HEAD = "a" * 40


def forge(monkeypatch, answer):
    asked = []

    def call(forge, method, path, body=None):
        asked.append((method, path))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(hold, "_forge", lambda root, name: ("https://api.example", "owner/p", "t"))
    monkeypatch.setattr(hold, "_call", call)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("NSTACK_ATTESTING", raising=False)
    return asked


def pull(number=7, labels=("out-of-cycle",), sha=HEAD, state="open"):
    return {"number": number, "state": state, "head": {"sha": sha}, "labels": [{"name": name} for name in labels]}


def test_with_none_given_the_pull_request_s_own_labels_are_read(tmp_path: Path, monkeypatch):
    asked = forge(monkeypatch, [pull()])
    labels, said, refused = pull_request.labels_for(tmp_path, HEAD, "")
    assert labels == {"out-of-cycle"} and refused is None
    assert said == "read from pull request #7"
    assert asked == [("GET", f"/commits/{HEAD}/pulls")]


def test_a_label_the_pull_request_does_not_carry_is_refused(tmp_path: Path, monkeypatch):
    forge(monkeypatch, [pull(labels=())])
    labels, _, refused = pull_request.labels_for(tmp_path, HEAD, "over-budget")
    assert refused and "pull request #7 carries no label over-budget" in refused, refused


def test_a_closed_pull_request_or_another_head_is_not_this_one(tmp_path: Path, monkeypatch):
    forge(monkeypatch, [pull(state="closed"), pull(number=8, sha="b" * 40)])
    labels, said, refused = pull_request.labels_for(tmp_path, HEAD, "cross-module")
    assert labels == {"cross-module"} and refused is None
    assert "given by the caller" in said and "no open pull request has this head" in said, said


def test_a_forge_that_refuses_leaves_the_caller_s_labels_and_says_why(tmp_path: Path, monkeypatch):
    forge(monkeypatch, hold.Refused("HTTP 403: Resource not accessible"))
    labels, said, refused = pull_request.labels_for(tmp_path, HEAD, "cross-module")
    assert labels == {"cross-module"} and refused is None and "HTTP 403" in said, said


@pytest.mark.parametrize("where", ["GITHUB_ACTIONS", "NSTACK_ATTESTING"])
def test_on_the_forge_s_run_and_under_attest_the_labels_given_are_the_pull_request_s(tmp_path, monkeypatch, where):
    asked = forge(monkeypatch, [pull(labels=())])
    monkeypatch.setenv(where, "true" if where == "GITHUB_ACTIONS" else HEAD)
    labels, _, refused = pull_request.labels_for(tmp_path, HEAD, "out-of-cycle")
    assert labels == {"out-of-cycle"} and refused is None and asked == []
