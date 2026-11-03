"""Seed arrays, usage records, usage budgets and the noise-floor policy (Klein 2.3)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml
from test_workflow_v3 import _fill, commit_all, git

from kleinlib.contract import load_contract, seed_array, validate_contract
from kleinlib.decision import parse_seed_array_log
from kleinlib.errors import WorkflowError
from kleinlib.scaffold import scaffold_study
from kleinlib.state import record_gate
from kleinlib.workflow import run_one


def _study(tmp_path: Path, *, entry_extra: str = "", phase_extra: str = "", policy: str = "") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies", "03-demo", goal="g", domain="d", target="y", task_type="classification",
        method_depth="brief", family="f", metric_name="val_auc", metric_goal="higher",
        data_source="csv:fixture.csv", data_path="data/prepared/fixture.csv", max_run_seconds=20,
        schema_version=3, kind="predict", modality="tabular", profile="generic", audience="tests",
    )
    _fill(study)
    path = study / "study.yaml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(\n  mutable: [^\n]*\n)", r"\1  printed: block\n" + entry_extra, text, count=1)
    if phase_extra:
        text = text.replace("    max_experiments: 4\n", "    max_experiments: 4\n" + phase_extra, 1)
    if policy:
        text = text.replace("\nmax_run_seconds:", "\n" + policy + "max_run_seconds:", 1)
    path.write_text(text, encoding="utf-8")
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    for gate in ("consult", "data", "method"):
        record_gate(study, gate, acknowledged_by="tester")
    commit_all(repo, "ready")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    return study


def _seeded_command(*, usage: dict | None = None, fail_seed: int | None = None) -> list[str]:
    usage_line = ""
    if usage:
        usage_line = f"from kleinlib.dl import report_usage; report_usage(**{usage!r}); "
    fail = f"assert seed != {fail_seed}, 'boom'; " if fail_seed is not None else ""
    body = (
        "import os; seed = int(os.environ['KLEIN_SEED']); " + fail + usage_line
        + "print('loss: nan'); print('---'); "
        "print('primary_metric: ' + str(0.70 + 0.01 * seed)); "
        "print('metric_name: val_auc'); print('metric_goal: higher'); "
        "print('wall_seconds: 0.1')"
    )
    return [sys.executable, "-c", body]


def _touch(study: Path, n: int) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\nCANDIDATE = {n}\n", encoding="utf-8")


def test_seeds_contract_rules(tmp_path: Path) -> None:
    study = _study(tmp_path, entry_extra="  seeds: [0, 1, 2]\n")
    contract = load_contract(study)
    assert seed_array(contract) == [0, 1, 2]
    assert validate_contract(contract, study) == []
    bad = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    bad["entrypoint"]["seeds"] = [1, 1]
    assert any("entrypoint.seeds" in p for p in validate_contract(bad, study))
    bad["entrypoint"]["seeds"] = [0, 1]
    bad["entrypoint"]["printed"] = "log"
    assert any("requires entrypoint.printed: block" in p for p in validate_contract(bad, study))


def test_a_seed_array_is_one_transaction_decided_on_the_mean(tmp_path: Path) -> None:
    study = _study(tmp_path, entry_extra="  seeds: [0, 1, 2]\n")
    _touch(study, 1)
    manifest = run_one(study, command=_seeded_command(usage={"steps": 100}), echo=False)
    assert manifest["disposition"] == "keep", manifest["decision_reason"]
    assert manifest["seeds"] == [0, 1, 2]
    assert manifest["primary_metric"] == pytest.approx(0.71)
    assert manifest["metrics"]["primary_metric_std"] == pytest.approx(0.01)
    assert manifest["metrics"]["seeds_n"] == 3
    seeds_rel = "runs/E0001/seeds.tsv"
    assert manifest["artifacts"][seeds_rel]["role"] == "seeds"
    assert (study / seeds_rel).read_text().startswith("seed\t")
    # usage accumulates across the seeds of the array and carries the hardware
    assert manifest["usage"]["steps"] == 300
    assert "hardware" in manifest["execution"]
    rows = parse_seed_array_log(study / "runs" / "E0001" / "run.log", [0, 1, 2])[4]
    assert [r["seed"] for r in rows] == [0, 1, 2]


def test_a_failing_seed_crashes_the_array_and_usage_is_still_recorded(tmp_path: Path) -> None:
    study = _study(tmp_path, entry_extra="  seeds: [0, 1, 2]\n")
    _touch(study, 1)
    manifest = run_one(study, command=_seeded_command(usage={"steps": 5}, fail_seed=1), echo=False)
    assert manifest["disposition"] == "crash"
    assert manifest["usage"]["steps"] == 5  # seed 0 reported before seed 1 failed


def test_usage_budget_refuses_the_next_run(tmp_path: Path) -> None:
    study = _study(tmp_path, entry_extra="", phase_extra="    budget_usd: 1.0\n")
    _touch(study, 1)
    first = run_one(study, command=[sys.executable, "-c", (
        "from kleinlib.dl import report_usage; report_usage(usd=1.5); "
        "print('---'); print('primary_metric: 0.7'); print('metric_name: val_auc'); "
        "print('metric_goal: higher')")], echo=False)
    assert first["usage"]["usd"] == 1.5
    _touch(study, 2)
    with pytest.raises(WorkflowError, match="exhausted budget_usd"):
        run_one(study, command=_seeded_command(), echo=False)


def test_noise_floor_policy_blocks_frontier_runs_after_phase_one(tmp_path: Path) -> None:
    middle = (
        "  - id: adaptive-2\n"
        "    description: \"second adaptive phase\"\n"
        "    budget_seconds: 3600\n"
        "    max_experiments: 4\n"
    )
    study = _study(tmp_path, phase_extra=middle, policy="policy:\n  noise_floor: required\n\n")
    # Phase 1 runs are allowed: that is where the floor is measured.
    _touch(study, 1)
    assert run_one(study, command=_seeded_command_single(), echo=False)["disposition"] != "crash"
    state_path = study / "study_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_phase"] = "adaptive-2"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    commit_all(study.parents[1], "phase boundary (simulated)")
    _touch(study, 2)
    with pytest.raises(WorkflowError, match="policy.noise_floor"):
        run_one(study, command=_seeded_command_single(), echo=False)


def _seeded_command_single() -> list[str]:
    return [sys.executable, "-c", (
        "print('---'); print('primary_metric: 0.7'); print('metric_name: val_auc'); "
        "print('metric_goal: higher')")]


def test_a_seed_array_replicates_as_a_seed_array(tmp_path: Path) -> None:
    from kleinlib.replicate import replicate_run

    study = _study(tmp_path, entry_extra="  seeds: [0, 1, 2]\n")
    _touch(study, 1)
    run_one(study, command=_seeded_command(), echo=False)
    record = replicate_run(study, "E0001", echo=False)
    assert record["reproduced"] is True, record.get("failure_reason")
    assert record["replicate_block"]["seeds_n"] == 3


def test_aux_metrics_hold_the_array_not_the_last_seed(tmp_path: Path) -> None:
    """Study 22's instrument found it: each seed's evaluator replaced the previous
    seed's aux rows, so aux_metrics.tsv held the LAST seed. The notary writes the
    seed means it decided on, plus their spread."""
    import csv

    study = _study(tmp_path, entry_extra="  seeds: [0, 1, 2]\n")
    _touch(study, 1)
    body = (
        "import os, time; from kleinlib.eval import evaluate_scalar; seed = int(os.environ['KLEIN_SEED']); "
        "print('---'); "
        "evaluate_scalar(0.70 + 0.01 * seed, exp_id=os.environ['KLEIN_EXPERIMENT_ID'], metric_name='val_auc', "
        "metric_goal='higher', extra={'val_extra': float(seed)}, study_dir='.', t0=time.time())"
    )
    manifest = run_one(study, command=[sys.executable, "-c", body], echo=False)
    assert manifest["disposition"] == "keep", manifest["decision_reason"]
    with (study / "aux_metrics.tsv").open(encoding="utf-8") as stream:
        rows = {r["metric"]: float(r["value"]) for r in csv.DictReader(stream, delimiter="\t") if r["experiment"] == "E0001"}
    assert rows["val_extra"] == pytest.approx(1.0)  # the mean of seeds 0, 1, 2 — not seed 2's 2.0
    assert rows["primary_metric_std"] == pytest.approx(0.01)
    assert rows["seeds_n"] == 3
