"""Detached runs (Klein 2.3): detach -> job exec -> collect, and every refusal around it."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from test_workflow_v3 import _fill, commit_all, git

from kleinlib.checks import verify_study
from kleinlib.errors import WorkflowError
from kleinlib.job import exec_job
from kleinlib.manifest import load_manifests
from kleinlib.scaffold import scaffold_study
from kleinlib.state import record_gate
from kleinlib.workflow import abandon_detached, collect_detached, finalize, recover, run_one

ENTRY = (
    "import os, pathlib\n"
    "pathlib.Path('models').mkdir(exist_ok=True)\n"
    "pathlib.Path('models/weights.txt').write_text('w=' + os.environ['KLEIN_EXPERIMENT_ID'])\n"
    "print('epoch: 1')\n"
    "print('---')\n"
    "print('primary_metric: 0.75')\n"
    "print('metric_name: val_auc')\n"
    "print('metric_goal: higher')\n"
)


def _study(tmp_path: Path, *, execution: str = "  execution: [local, detached]\n") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies", "03-demo", goal="g", domain="d", target="y", task_type="classification",
        method_depth="brief", family="f", metric_name="val_auc", metric_goal="higher",
        data_source="csv:fixture.csv", data_path="data/prepared/fixture.csv", max_run_seconds=60,
        schema_version=3, kind="predict", modality="tabular", profile="generic", audience="tests",
    )
    _fill(study)
    path = study / "study.yaml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\n  command: [^\n]*\n", '\n  command: ["python", "-u", "train.py"]\n', text, count=1)
    text = re.sub(r"(\n  mutable: [^\n]*\n)", r"\1  printed: block\n" + execution, text, count=1)
    path.write_text(text, encoding="utf-8")
    (study / "train.py").write_text(ENTRY, encoding="utf-8")
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    for gate in ("consult", "data", "method"):
        record_gate(study, gate, acknowledged_by="tester")
    commit_all(repo, "ready")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    return repo, study


def _touch(study: Path, n: int) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\nCANDIDATE = {n}\n", encoding="utf-8")


def test_detach_exec_collect_round_trip(tmp_path: Path) -> None:
    repo, study = _study(tmp_path)
    _touch(study, 1)
    detached = run_one(study, detach=True, echo=False)
    assert detached["transaction"]["phase"] == "awaiting_collect"
    assert git(repo, "log", "-1", "--format=%s") == "detach E0001: awaiting collect"
    assert git(repo, "status", "--porcelain") == ""
    assert (study / ".klein-detached").read_text().strip() == "E0001"
    assert (study / "results.tsv").read_text().count("\n") == 1  # no row until collected
    # Frozen: another run and a state commit are refused.
    with pytest.raises(WorkflowError, match="detached run E0001 is open"):
        run_one(study, echo=False)
    # recover leaves a detached run alone instead of crashing it.
    assert recover(study) == []
    # verify names the open run and writes no receipt over it; finalize refuses.
    rows = {c.name: c for c in verify_study(study)}
    assert not rows["detached run"].ok and "E0001" in rows["detached run"].message
    assert "verify receipt" not in rows
    with pytest.raises(WorkflowError, match="detached run E0001 is open"):
        finalize(study)
    assert git(repo, "status", "--porcelain") == ""

    result = exec_job(study / "runs" / "E0001" / "job.json", executor="local", echo=False)
    receipt = json.loads((result / "receipt.json").read_text())
    assert receipt["exit_code"] == 0 and "models/weights.txt" in receipt["files"]
    assert not (study / "models" / "weights.txt").exists()  # ran in a worktree, not here

    manifest = collect_detached(study, "E0001", echo=False)
    assert manifest["disposition"] == "keep", manifest["decision_reason"]
    assert manifest["primary_metric"] == 0.75
    assert manifest["execution"]["mode"] == "detached"
    assert manifest["execution"]["observed_by_notary"] is False
    assert "models/weights.txt" in manifest["artifacts"]
    assert "runs/E0001/job_receipt.json" in manifest["artifacts"]
    assert not (study / ".klein-detached").exists()
    assert git(repo, "status", "--porcelain") == ""
    assert "E0001\tprimary\t0.75\tkeep" in (study / "results.tsv").read_text()
    # The study is open again.
    _touch(study, 2)
    assert run_one(study, echo=False)["experiment"] == "E0002"


def test_collect_refuses_a_tampered_result(tmp_path: Path) -> None:
    _, study = _study(tmp_path)
    _touch(study, 1)
    run_one(study, detach=True, echo=False)
    result = exec_job(study / "runs" / "E0001" / "job.json", executor="local", echo=False)
    log = result / "run.log"
    log.write_text(log.read_text().replace("0.75", "0.99"))
    with pytest.raises(WorkflowError, match="run.log is missing or does not match"):
        collect_detached(study, "E0001", echo=False)
    (result / "files" / "models" / "weights.txt").write_text("forged")
    with pytest.raises(WorkflowError, match="does not match the receipt"):
        collect_detached(study, "E0001", echo=False)


def test_collect_refuses_a_foreign_receipt_and_a_moved_head(tmp_path: Path) -> None:
    repo, study = _study(tmp_path)
    _touch(study, 1)
    run_one(study, detach=True, echo=False)
    result = exec_job(study / "runs" / "E0001" / "job.json", executor="local", echo=False)
    receipt = json.loads((result / "receipt.json").read_text())
    receipt["job_sha256"] = "0" * 64
    (result / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(WorkflowError, match="different job bundle"):
        collect_detached(study, "E0001", echo=False)
    (repo / "unrelated.txt").write_text("x")
    git(repo, "add", "unrelated.txt")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@x", "commit", "-q", "-m", "moved")
    with pytest.raises(WorkflowError, match="detach commit"):
        collect_detached(study, "E0001", echo=False)


def test_abandon_records_a_crash_and_reopens_the_study(tmp_path: Path) -> None:
    repo, study = _study(tmp_path)
    _touch(study, 1)
    run_one(study, detach=True, echo=False)
    with pytest.raises(WorkflowError, match="reason"):
        abandon_detached(study, "E0001", reason=" ")
    manifest = abandon_detached(study, "E0001", reason="the GPU node was preempted twice")
    assert manifest["disposition"] == "crash"
    assert "preempted" in manifest["decision_reason"]
    assert git(repo, "status", "--porcelain") == ""
    assert [m["disposition"] for m in load_manifests(study)] == ["crash"]
    assert "CANDIDATE = 1" not in (study / "train.py").read_text()  # surface restored


def test_detach_needs_the_contract_opt_in(tmp_path: Path) -> None:
    _, study = _study(tmp_path, execution="")
    _touch(study, 1)
    with pytest.raises(WorkflowError, match="entrypoint.execution"):
        run_one(study, detach=True, echo=False)
    assert load_manifests(study) == []  # refused before any id or commit


def test_foreground_runs_are_untouched_by_the_opt_in(tmp_path: Path) -> None:
    _, study = _study(tmp_path)
    _touch(study, 1)
    manifest = run_one(study, echo=False)
    assert manifest["disposition"] == "keep" and "execution" not in manifest
    assert sys.executable  # the foreground path runs the declared command in place
