"""``entrypoint.printed: block`` — metrics come from the final canonical block only.

The legacy channel (every ``key: value`` line of the whole log) stays the default
and is frozen by ``test_legacy_parse_golden.py``; this file covers the opt-in
block scope: training chatter before the block can neither crash nor pollute a
run, the reserved evidence keys are still read from the whole log, the manifest
records the rule, and replication re-parses by the manifest.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml
from test_workflow_v3 import _fill, commit_all, git

from kleinlib.contract import load_contract, printed_scope, validate_contract
from kleinlib.decision import block_lines, parse_metric_log, printed_values
from kleinlib.errors import WorkflowError
from kleinlib.scaffold import scaffold_study
from kleinlib.state import record_gate
from kleinlib.workflow import run_one

NOISY_BLOCK = """\
epoch: 1
loss: nan
loss: 2.31
split_fingerprint: abc123
artifact: models/x.txt
---
primary_metric:    0.700000
metric_name:       val_auc
metric_goal:       higher
training_seconds:  NA
total_seconds:     0.1
train_rows:        NA
val_rows:          NA
status:            ok
--- aux_metrics ---
val_logloss:       0.5
wall_seconds:      0.1
runner_status: ok
runner_exit_code: 0
"""


def test_block_scope_ignores_chatter_and_keeps_aux(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(NOISY_BLOCK, encoding="utf-8")
    with pytest.raises(WorkflowError, match="non-finite"):
        parse_metric_log(log)  # the legacy channel still crashes on `loss: nan`
    primary, name, goal, metrics = parse_metric_log(log, scope="block")
    assert (primary, name, goal) == (0.7, "val_auc", "higher")
    assert "epoch" not in metrics and "loss" not in metrics
    assert metrics["val_logloss"] == 0.5 and metrics["wall_seconds"] == 0.1
    # Evidence keys are read from the whole log under either scope.
    assert printed_values(log, "split_fingerprint") == ["abc123"]
    assert printed_values(log, "artifact") == ["models/x.txt"]


def test_block_scope_reads_the_last_block_and_needs_an_opener(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text("---\nprimary_metric: 0.1\n---\nprimary_metric: 0.9\n", encoding="utf-8")
    assert parse_metric_log(log, scope="block")[0] == 0.9
    log.write_text("primary_metric: 0.9\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="no canonical block"):
        parse_metric_log(log, scope="block")
    assert block_lines(["a: 1", "--- aux_metrics ---"]) is None
    with pytest.raises(ValueError):
        parse_metric_log(log, scope="tail")


def _block_study(tmp_path: Path, *, printed: str = "block") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies",
        "03-demo",
        goal="compare a candidate",
        domain="test",
        target="y",
        task_type="classification",
        method_depth="brief",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
        data_path="data/prepared/fixture.csv",
        max_run_seconds=5,
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="the maintainers of this test suite",
    )
    _fill(study)
    contract_path = study / "study.yaml"
    text = contract_path.read_text(encoding="utf-8")
    text = re.sub(r"(\n  mutable: [^\n]*\n)", rf"\1  printed: {printed}\n", text, count=1)
    contract_path.write_text(text, encoding="utf-8")
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "ready")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    return repo, study


def _noisy_command(value: float) -> list[str]:
    body = NOISY_BLOCK.replace("0.700000", f"{value:.6f}")
    body = "\n".join(
        line for line in body.splitlines() if not line.startswith(("runner_", "split_", "artifact"))
    )
    return [sys.executable, "-c", f"print({body!r})"]


def test_contract_accepts_block_and_refuses_an_unknown_scope(tmp_path: Path) -> None:
    _, study = _block_study(tmp_path)
    contract = load_contract(study)
    assert printed_scope(contract) == "block"
    assert validate_contract(contract, study) == []
    bad = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    bad["entrypoint"]["printed"] = "tail"
    assert any("entrypoint.printed" in p for p in validate_contract(bad, study))
    bad["entrypoint"]["printed"] = "log"
    assert not any("entrypoint" in p for p in validate_contract(bad, study))


def test_block_scoped_run_survives_training_chatter(tmp_path: Path) -> None:
    _, study = _block_study(tmp_path)
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_noisy_command(0.7), echo=False)
    assert manifest["disposition"] == "keep", manifest["decision_reason"]
    assert manifest["printed_scope"] == "block"
    assert "loss" not in manifest["metrics"] and "epoch" not in manifest["metrics"]


def test_the_same_chatter_crashes_a_legacy_scoped_run(tmp_path: Path) -> None:
    _, study = _block_study(tmp_path, printed="log")
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_noisy_command(0.7), echo=False)
    assert manifest["disposition"] == "crash"
    assert "non-finite" in manifest["decision_reason"]
    assert "printed_scope" not in manifest


def test_replicate_reparses_by_the_manifest_scope(tmp_path: Path) -> None:
    """A block-scoped run replicates — the chatter would crash a whole-log parse."""
    from kleinlib.replicate import replicate_run

    _, study = _block_study(tmp_path)
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_noisy_command(0.7), echo=False)
    assert manifest["printed_scope"] == "block"
    record = replicate_run(study, "E0001", echo=False)
    assert record["reproduced"] is True, record.get("failure_reason")
    assert "loss" not in record["replicate_block"]
