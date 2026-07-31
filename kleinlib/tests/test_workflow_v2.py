from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import kleinlib.workflow as workflow
from kleinlib import cli
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import (
    V2_RESULTS_COLUMNS,
    WorkflowError,
    choose_disposition,
    finalize,
    load_manifests,
    load_state,
    preflight_checks,
    record_gate,
    run_one,
    run_subprocess,
    status_summary,
    validate_contract,
    verify_event_chain,
    verify_study,
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain") == "":
        return  # gate records file their own state writes; nothing may remain
    git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )


@pytest.fixture
def ready_study(tmp_path: Path) -> tuple[Path, Path]:
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
    )
    for name in ("study.yaml", "program.md", "research_plan.md"):
        path = study / name
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace("{{RQ1_QUESTION}}", "does it improve?")
            .replace("{{RQ1_PRIOR}}", "no")
            .replace("{{LEVER_1}}", "candidate")
            .replace("{{DELTA_1}}", "+0.1 score"),
            encoding="utf-8",
        )
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text(
        "# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8"
    )
    (study / "method_card.md").write_text("# Method card\n\nBrief method.\n", encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "ready study")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    return repo, study


def metric_command(
    value: float,
    *,
    expected_kind: str | None = None,
    expected_experiment: str | None = None,
    expected_track: str | None = None,
) -> list[str]:
    check = ""
    if expected_kind:
        check = (
            "import os; "
            f"assert os.environ['KLEIN_EVALUATION_KIND'] == {expected_kind!r}; "
        )
    if expected_experiment:
        check += f"assert os.environ['KLEIN_EXPERIMENT_ID'] == {expected_experiment!r}; "
    if expected_track:
        check += f"assert os.environ['KLEIN_TRACK'] == {expected_track!r}; "
    return [
        sys.executable,
        "-c",
        check
        + f"print('primary_metric:    {value}'); "
        "print('metric_name:       val_auc'); print('metric_goal:       higher')",
    ]


def test_scaffold_is_v2_and_template_passes_eval_identity(tmp_path: Path) -> None:
    study = scaffold_study(
        tmp_path,
        "03-smoke",
        goal="g",
        domain="d",
        target="y",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:x",
    )
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["schema_version"] == 2
    assert contract["method_depth"] == "full"
    assert contract["data"]["split"]["development_size"] == 0.2
    assert (study / "results.tsv").read_text().splitlines()[0] == "\t".join(
        V2_RESULTS_COLUMNS
    )
    train = (study / "train.py").read_text(encoding="utf-8")
    assert "exp_id=EXPERIMENT_ID" in train
    assert 'study_dir="."' in train
    assert 'EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID")' in train
    assert 'os.environ.get("KLEIN_EVALUATION_KIND")' in train
    assert verify_event_chain(study) == []


def test_scaffold_and_contract_reject_metric_identity_drift(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown metric"):
        scaffold_study(
            tmp_path,
            "03-unknown-metric",
            task_type="classification",
            metric_name="score",
            metric_goal="higher",
        )
    with pytest.raises(ValueError, match="belongs to task"):
        scaffold_study(
            tmp_path,
            "03-wrong-task",
            task_type="regression",
            metric_name="val_auc",
            metric_goal="higher",
        )
    with pytest.raises(ValueError, match="canonical goal"):
        scaffold_study(
            tmp_path,
            "03-wrong-goal",
            task_type="classification",
            metric_name="val_auc",
            metric_goal="lower",
        )

    study = scaffold_study(
        tmp_path,
        "03-contract-metric",
        task_type="classification",
        metric_name="val_auc",
        metric_goal="higher",
    )
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    contract["tracks"]["primary"]["metric"]["goal"] = "lower"
    assert any("canonical goal" in problem for problem in validate_contract(contract, study))


def test_simulation_contract_accepts_custom_scalar_metric_and_kind_none(tmp_path: Path) -> None:
    """E-0: math/optimization labs are first-class — custom metric, split kind none."""
    study = scaffold_study(
        tmp_path,
        "03-noisy-rosenbrock",
        goal="do restarts beat plain NM?",
        domain="optimization",
        target="synthetic",
        task_type="simulation",
        family="simulation",
        metric_name="mean_final_gap",
        metric_goal="lower",
        data_source="synthetic:noisy_rosenbrock_v1",
        data_path="data/prepared/reference_cell.csv",
    )
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["task_type"] == "simulation"
    assert contract["data"]["split"]["kind"] == "none"
    assert "development_size" not in contract["data"]["split"]
    problems = [
        p
        for p in validate_contract(contract, study)
        if "unresolved placeholders" not in p
    ]
    assert problems == []

    # custom metric requires an explicit direction
    with pytest.raises(ValueError, match="requires metric_goal"):
        scaffold_study(
            tmp_path,
            "04-no-goal",
            task_type="simulation",
            metric_name="my_custom_gap",
        )
    # kind none is simulation-only
    classification = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    classification["task_type"] = "classification"
    classification["tracks"]["primary"]["metric"]["name"] = "val_auc"
    classification["tracks"]["primary"]["metric"]["goal"] = "higher"
    assert any(
        "none is valid only for simulation" in problem or "kind must be" in problem
        for problem in validate_contract(classification, study)
    )


def test_generated_train_executes_through_workflow_with_durable_identity(ready_study) -> None:
    _, study = ready_study
    train = study / "train.py"
    source = train.read_text(encoding="utf-8")
    source = source.replace(
        '    raise NotImplementedError("implement the fixed three-way split declared in study.yaml")',
        "    return (\n"
        "        [[0.0], [0.1], [0.2], [0.8], [0.9], [1.0]],\n"
        "        [[0.15], [0.25], [0.75], [0.85]],\n"
        "        [0, 0, 0, 1, 1, 1],\n"
        "        [0, 0, 1, 1],\n"
        "    )",
    )
    source = source.replace(
        '    raise NotImplementedError("build this candidate")',
        "    from sklearn.linear_model import LogisticRegression\n"
        "    return LogisticRegression(random_state=RANDOM_SEED)",
    )
    train.write_text(source, encoding="utf-8")

    manifest = run_one(
        study,
        description="generated scaffold smoke",
        command=[sys.executable, "-u", "train.py"],
        echo=False,
    )

    assert manifest["experiment"] == "E0001"
    assert manifest["disposition"] == "keep"
    assert manifest["metric_name"] == "val_auc"
    assert "primary_metric:    1.000000" in (
        study / "runs" / "E0001" / "run.log"
    ).read_text(encoding="utf-8")
    aux = (study / "aux_metrics.tsv").read_text(encoding="utf-8")
    assert "E0001\tval_auc\t" in aux
    assert "runs/E0001/run.log" in manifest["artifacts"]


def test_safe_runner_preserves_crash_timeout_and_environment(tmp_path: Path) -> None:
    crash_log = tmp_path / "crash.log"
    crashed = run_subprocess(
        [sys.executable, "-c", "import os,sys; print(os.environ['MARK']); sys.exit(7)"],
        cwd=tmp_path,
        log_path=crash_log,
        timeout_seconds=3,
        echo=False,
        env_overrides={"MARK": "visible"},
    )
    assert crashed.exit_code == 7
    assert not crashed.timed_out
    assert "visible" in crash_log.read_text(encoding="utf-8")

    timeout_log = tmp_path / "timeout.log"
    timed_out = run_subprocess(
        [sys.executable, "-c", "import time; print('before', flush=True); time.sleep(30)"],
        cwd=tmp_path,
        log_path=timeout_log,
        timeout_seconds=0.1,
        echo=False,
    )
    assert timed_out.exit_code == 124
    assert timed_out.timed_out
    assert "runner_status: timeout" in timeout_log.read_text(encoding="utf-8")


def test_run_transactions_keep_discard_crash_and_seal(ready_study) -> None:
    repo, study = ready_study
    train = study / "train.py"

    train.write_text(train.read_text() + "\nKEEP_CANDIDATE = True\n", encoding="utf-8")
    kept = run_one(
        study,
        description="baseline",
        command=metric_command(
            0.70,
            expected_kind="development",
            expected_experiment="E0001",
            expected_track="primary",
        ),
        echo=False,
    )
    assert kept["disposition"] == "keep"
    kept_train = train.read_text(encoding="utf-8")

    train.write_text(kept_train + "\nWEAKER_CANDIDATE = True\n", encoding="utf-8")
    discarded = run_one(
        study,
        description="weaker",
        command=metric_command(0.60, expected_kind="development"),
        echo=False,
    )
    assert discarded["disposition"] == "discard"
    assert train.read_text(encoding="utf-8") == kept_train

    train.write_text(kept_train + "\nCRASH_CANDIDATE = True\n", encoding="utf-8")
    crashed = run_one(
        study,
        description="broken",
        command=[sys.executable, "-c", "import sys; sys.exit(7)"],
        echo=False,
    )
    assert crashed["disposition"] == "crash"
    assert crashed["primary_metric"] is None
    assert train.read_text(encoding="utf-8") == kept_train

    record_gate(
        study,
        "phase",
        phase="adaptive-1",
        acknowledged_by="tester",
        note="adaptive phase reviewed",
    )
    commit_all(repo, "acknowledge adaptive phase")
    final = run_one(
        study,
        description="confirmation",
        final_test=True,
        command=metric_command(0.69, expected_kind="final_test"),
        echo=False,
    )
    assert final["evaluation_kind"] == "final_test"
    assert final["disposition"] == "discard"
    with pytest.raises(WorkflowError, match="already been accessed"):
        run_one(
            study,
            final_test=True,
            command=metric_command(0.69, expected_kind="final_test"),
            echo=False,
        )

    manifests = load_manifests(study)
    assert [m["disposition"] for m in manifests] == [
        "keep",
        "discard",
        "crash",
        "discard",
    ]
    for manifest in manifests:
        assert manifest["transaction"]["status"] == "complete"
        assert git(repo, "cat-file", "-t", manifest["candidate_commit"]) == "commit"
        assert git(repo, "cat-file", "-t", manifest["transaction"]["evidence_commit"]) == "commit"
    assert git(repo, "status", "--porcelain") == ""
    state = load_state(study, yaml.safe_load((study / "study.yaml").read_text()))
    assert state["final_holdout_access"]["primary"]["count"] == 1
    assert final["phase"] == "confirmation"
    assert final["phase_experiment_limit"] == 1
    lines = (study / "results.tsv").read_text().splitlines()
    assert lines[0] == "\t".join(V2_RESULTS_COLUMNS)
    assert lines[3].split("\t")[2:4] == ["NA", "crash"]


def test_phase_boundary_and_evaluation_kind_are_enforced(ready_study) -> None:
    repo, study = ready_study
    with pytest.raises(WorkflowError, match="only in final phase"):
        run_one(
            study,
            final_test=True,
            command=metric_command(0.7, expected_kind="final_test"),
            echo=False,
        )
    with pytest.raises(WorkflowError, match="only the current phase"):
        record_gate(
            study,
            "phase",
            phase="confirmation",
            acknowledged_by="tester",
        )
    with pytest.raises(WorkflowError, match="cannot be overridden"):
        record_gate(
            study,
            "phase",
            phase="adaptive-1",
            acknowledged_by="tester",
            override_reason="skip review",
        )

    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    with pytest.raises(WorkflowError, match="already been acknowledged"):
        record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "acknowledge adaptive phase")
    with pytest.raises(WorkflowError, match="development runs are forbidden"):
        run_one(
            study,
            command=metric_command(0.7, expected_kind="development"),
            echo=False,
        )


def test_confirmation_run_is_capped_by_remaining_phase_budget(ready_study) -> None:
    repo, study = ready_study
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    contract["phases"][-1]["budget_seconds"] = 0.05
    (study / "study.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    commit_all(repo, "enter bounded confirmation")

    result = run_one(
        study,
        final_test=True,
        command=[sys.executable, "-c", "import time; time.sleep(1)"],
        echo=False,
    )
    assert result["disposition"] == "crash"
    assert result["timed_out"]
    assert 0 < result["max_run_seconds"] <= 0.05
    assert result["phase"] == "confirmation"


def test_track_frontiers_and_lower_direction_are_independent() -> None:
    incumbent = {
        "track": "loss",
        "primary_metric": 5.0,
        "metrics": {"latency": 10.0},
        "disposition": "keep",
    }
    lower = {
        "metric": {"name": "rmse", "goal": "lower", "minimum_delta": 0.2},
        "guardrails": {"latency": {"max": 12}},
    }
    disposition, _ = choose_disposition(
        primary_metric=4.7,
        track_spec=lower,
        metrics={"latency": 11.0},
        incumbent=incumbent,
        final_test=False,
    )
    assert disposition == "keep"
    disposition, _ = choose_disposition(
        primary_metric=4.9,
        track_spec=lower,
        metrics={"latency": 11.0},
        incumbent=incumbent,
        final_test=False,
    )
    assert disposition == "discard"
    # A different track has no incumbent and starts its own frontier.
    disposition, _ = choose_disposition(
        primary_metric=100,
        track_spec={
            "metric": {"name": "profit", "goal": "higher", "minimum_delta": 1},
            "guardrails": {},
        },
        metrics={},
        incumbent=None,
        final_test=False,
    )
    assert disposition == "keep"


def test_preflight_requires_exact_branch_and_recorded_fingerprints(ready_study) -> None:
    repo, study = ready_study
    checks = preflight_checks(study)
    assert all(check.ok for check in checks), [(c.name, c.message) for c in checks if not c.ok]
    git(repo, "switch", "-q", "-c", "experiments/wrong")
    checks = preflight_checks(study)
    branch = next(check for check in checks if check.name == "git branch")
    assert not branch.ok
    assert "experiments/03-demo" in branch.message


def test_data_override_bypasses_only_go_and_still_fingerprints(ready_study) -> None:
    _, study = ready_study
    card = study / "data_card.md"
    card.write_text("# Data card\n\nDecision: NO-GO\n", encoding="utf-8")
    state = record_gate(
        study,
        "data",
        acknowledged_by="tester",
        override_reason="fixture is understood and explicitly accepted",
    )
    assert state["gates"]["data"]["status"] == "overridden"
    assert state["fingerprints"]["data"]
    assert state["prepared_data"]["sha256"] == state["fingerprints"]["data"]

    card.write_text("# Data card\n\nDecision: {{GO_OR_NO_GO}}\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="unresolved placeholder"):
        record_gate(
            study,
            "data",
            acknowledged_by="tester",
            override_reason="placeholder must not be bypassed",
        )
    card.unlink()
    with pytest.raises(WorkflowError, match="missing data_card.md"):
        record_gate(
            study,
            "data",
            acknowledged_by="tester",
            override_reason="missing evidence must not be bypassed",
        )


def test_gate_records_and_derived_views_do_not_block_the_loop(ready_study) -> None:
    repo, study = ready_study
    # A CLI verb's own state writes are filed automatically: re-recording a
    # gate leaves the tree clean instead of blocking the next run-one (A1).
    record_gate(study, "method", acknowledged_by="tester", note="re-record")
    assert git(repo, "status", "--porcelain") == ""
    assert "method gate recorded" in git(repo, "log", "-1", "--format=%s")
    # Derived views may be dirty at run time; the run proceeds and the next
    # state commit sweeps them (A2).
    (study / "results_summary.md").write_text("derived view\n", encoding="utf-8")
    (study / "progress.svg").write_text("<svg/>\n", encoding="utf-8")
    (study / "figures").mkdir(exist_ok=True)
    (study / "figures" / "x.png").write_bytes(b"png")
    manifest = run_one(
        study,
        description="derived views present",
        command=metric_command(0.9),
        echo=False,
    )
    assert manifest["disposition"] == "keep"
    record_gate(study, "consult", acknowledged_by="tester", note="sweep derived views")
    assert git(repo, "status", "--porcelain") == ""


def test_gate_records_sweep_measurement_sidecars(ready_study) -> None:
    repo, study = ready_study
    # A Phase-0 noise-floor sweep leaves sweeps/ untracked; the next gate
    # record must file it (the papercut: consult re-record used to strand it,
    # and the following run-one refused on a dirty tree).
    sweeps = study / "sweeps"
    sweeps.mkdir(exist_ok=True)
    (sweeps / "noise_floor.py").write_text("# measurement sweep\n", encoding="utf-8")
    (sweeps / "noise_floor.sidecar.tsv").write_text(
        "trial\tparams_json\tprimary_metric\twall_seconds\tstatus\terror\n",
        encoding="utf-8",
    )
    record_gate(study, "consult", acknowledged_by="tester", note="floor measured")
    assert git(repo, "status", "--porcelain") == ""
    tracked = git(repo, "ls-files", "studies/03-demo/sweeps")
    assert "studies/03-demo/sweeps/noise_floor.py" in tracked
    assert "studies/03-demo/sweeps/noise_floor.sidecar.tsv" in tracked


def test_playbook_is_scaffolded_wired_into_evidence_and_phase_acks(ready_study) -> None:
    repo, study = ready_study
    playbook = study / "playbook.md"
    text = playbook.read_text(encoding="utf-8")
    for heading in (
        "## Current best (per track)",
        "## Ruled out (evidence, not opinion)",
        "## Open hypotheses",
        "## Next-best candidates",
    ):
        assert heading in text
    # dirty playbook never blocks a run, and the evidence commit carries it
    playbook.write_text(text + "\n| primary | E0001 | 0.9 | baseline | now |\n", encoding="utf-8")
    manifest = run_one(
        study,
        description="playbook dirty at run time",
        command=metric_command(0.9),
        echo=False,
    )
    assert manifest["disposition"] == "keep"
    committed = git(
        repo, "show", f"{manifest['transaction']['evidence_commit']}:studies/03-demo/playbook.md"
    )
    assert "E0001" in committed
    # phase ack refuses a placeholder playbook, then records the hash
    playbook.write_text(text + "\n{{REFRESH_ME}}\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="unresolved placeholders"):
        record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    playbook.write_text(text + "\n| primary | E0001 | 0.9 | baseline | now |\n", encoding="utf-8")
    state = record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    ack = state["phase_acknowledgements"]["adaptive-1"]
    assert len(ack["playbook_sha256"]) == 64
    assert git(repo, "status", "--porcelain") == ""


def test_method_gate_enforces_declared_triad(ready_study) -> None:
    _, study = ready_study
    card = study / "method_card.md"
    card.write_text(
        "---\ntriad:\n  theory: true\n  papers: false\n  practice: true\n---\n"
        "# Method card\n\nBrief method.\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError, match="triad incomplete"):
        record_gate(study, "method", acknowledged_by="tester")
    # naming the missing leg in the note is an explicit, recorded acceptance
    record_gate(
        study,
        "method",
        acknowledged_by="tester",
        note="papers pending: preprint only, refs flagged UNVERIFIED",
    )
    # all legs true also passes
    card.write_text(
        "---\ntriad:\n  theory: true\n  papers: true\n  practice: true\n---\n"
        "# Method card\n\nBrief method.\n",
        encoding="utf-8",
    )
    record_gate(study, "method", acknowledged_by="tester", note="triad complete")


def test_noise_floor_contract_validation_and_preflight_honesty(ready_study) -> None:
    repo, study = ready_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]

    # malformed blocks are contract problems
    metric["noise_floor"] = {"k": 2, "std": -1.0, "range": 0.1, "bogus": 1}
    problems = " ".join(validate_contract(contract, study))
    assert "noise_floor.k" in problems
    assert "noise_floor.std" in problems
    assert "unknown keys" in problems

    # method: is optional provenance — accepted as a non-empty string, refused otherwise
    metric["noise_floor"] = {
        "k": 5, "std": 0.002, "range": 0.005, "method": "paired-bootstrap",
    }
    metric["minimum_delta"] = 0.004
    assert not any(
        "noise_floor" in p for p in validate_contract(contract, study)
    )
    metric["noise_floor"]["method"] = "  "
    assert any(
        "noise_floor.method" in p for p in validate_contract(contract, study)
    )

    # a declared floor with minimum_delta inside it fails preflight
    metric["noise_floor"] = {"k": 5, "std": 0.002, "range": 0.005, "mean": 0.67}
    metric["minimum_delta"] = 0.001
    (study / "study.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note="floor measured")
    floor_checks = [
        c for c in preflight_checks(study, require_clean=False, require_branch=False)
        if c.name == "noise floor"
    ]
    assert len(floor_checks) == 1 and not floor_checks[0].ok
    assert "dishonesty" in floor_checks[0].message

    # honest minimum_delta passes
    metric["minimum_delta"] = 0.004
    (study / "study.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note="delta from floor")
    floor_checks = [
        c for c in preflight_checks(study, require_clean=False, require_branch=False)
        if c.name == "noise floor"
    ]
    assert len(floor_checks) == 1 and floor_checks[0].ok


def test_journal_appends_do_not_invalidate_preflight(ready_study) -> None:
    """A19: program.md is the living lab notebook — appending to it after the
    consult ack must not fail the artifact-hash check (study.yaml still does)."""
    _, study = ready_study
    program = study / "program.md"
    program.write_text(
        program.read_text(encoding="utf-8") + "\n- log: tried X, keeping Y\n",
        encoding="utf-8",
    )
    hash_checks = [
        c for c in preflight_checks(study, require_clean=False, require_branch=False)
        if c.name == "gate artifact hashes"
    ]
    assert all(c.ok for c in hash_checks), [c.message for c in hash_checks]
    contract_path = study / "study.yaml"
    contract_path.write_text(
        contract_path.read_text(encoding="utf-8") + "# drifted\n", encoding="utf-8"
    )
    hash_checks = [
        c for c in preflight_checks(study, require_clean=False, require_branch=False)
        if c.name == "gate artifact hashes"
    ]
    assert any(not c.ok and "study.yaml" in c.message for c in hash_checks)


def test_phase_ladder_drift_is_caught_by_preflight(ready_study) -> None:
    """A20: phases inserted or renamed after initialization must fail preflight,
    not silently orphan — state's current_phase anchors at scaffold time."""
    _, study = ready_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    ladder = [c for c in preflight_checks(study, require_clean=False, require_branch=False)
              if c.name == "phase ladder"]
    assert len(ladder) == 1 and ladder[0].ok

    # insert a phase BEFORE the current one
    inserted = dict(contract)
    inserted["phases"] = [
        {"id": "phase0-inserted", "description": "retrofit", "budget_seconds": 60,
         "max_experiments": 1},
        *contract["phases"],
    ]
    (study / "study.yaml").write_text(yaml.safe_dump(inserted, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note="amend")
    ladder = [c for c in preflight_checks(study, require_clean=False, require_branch=False)
              if c.name == "phase ladder"]
    assert len(ladder) == 1 and not ladder[0].ok
    assert "phase0-inserted" in ladder[0].message

    # rename the current phase away entirely
    renamed = dict(contract)
    renamed["phases"] = [
        {**contract["phases"][0], "id": "renamed-phase"},
        *contract["phases"][1:],
    ]
    (study / "study.yaml").write_text(yaml.safe_dump(renamed, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note="rename")
    ladder = [c for c in preflight_checks(study, require_clean=False, require_branch=False)
              if c.name == "phase ladder"]
    assert len(ladder) == 1 and not ladder[0].ok
    assert "renamed" in ladder[0].message or "not in the contract" in ladder[0].message


def test_v1_verify_is_read_only_with_errata(tmp_path: Path) -> None:
    study = tmp_path / "legacy"
    study.mkdir()
    (study / "study.yaml").write_text("goal: legacy\n", encoding="utf-8")
    results = study / "results.tsv"
    results.write_text(
        "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n",
        encoding="utf-8",
    )
    before = results.read_bytes()
    checks = verify_study(study)
    assert checks[0].name == "legacy warning"
    assert "deprecated" in checks[0].message
    messages = " ".join(check.message for check in checks)
    assert "exact candidate commits were not retained" in messages
    assert "create a new v2 study" in messages
    assert all(check.ok for check in checks)
    assert results.read_bytes() == before
    assert "schema: v1 (deprecated compatibility)" in status_summary(study)


def test_v1_and_v2_cli_compatibility_round_trips(ready_study, tmp_path: Path, capsys) -> None:
    _, v2 = ready_study
    assert cli.main(["status", "--study", str(v2)]) == 0
    assert "schema: v2" in capsys.readouterr().out
    assert cli.main(["verify", "--study", str(v2)]) == 0
    assert "0 failed" in capsys.readouterr().out

    v1 = tmp_path / "legacy-cli"
    v1.mkdir()
    (v1 / "study.yaml").write_text("goal: legacy\n", encoding="utf-8")
    ledger = v1 / "results.tsv"
    ledger.write_text(
        "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()
    assert cli.main(["status", "--study", str(v1)]) == 0
    assert "v1 (deprecated compatibility)" in capsys.readouterr().out
    assert cli.main(["verify", "--study", str(v1)]) == 0
    out = capsys.readouterr().out
    assert "legacy warning" in out
    assert "no study evidence is rewritten" in out
    assert ledger.read_bytes() == before


def test_finalize_requires_explicit_exploratory_or_confirmed_label(ready_study, capsys) -> None:
    repo, study = ready_study
    (study / "findings.md").write_text(
        "# Findings\n\nThis study is exploratory.\n", encoding="utf-8"
    )
    with pytest.raises(WorkflowError, match="use --allow-exploratory"):
        finalize(study)
    (study / "findings.md").write_text(
        "# Findings\n\nThis exploratory study found a real effect.\n", encoding="utf-8"
    )
    assert finalize(study, allow_exploratory=True) == "exploratory"
    captured = capsys.readouterr()
    assert "without explicit uncertainty" in captured.err
    assert "status: finalized" in status_summary(study)
    assert verify_event_chain(study) == []

    # Finalization state is evidence the CLI files itself (A1): tree clean,
    # and the finalize commit is the receipt.
    assert git(repo, "status", "--porcelain") == ""
    assert "finalized exploratory" in git(repo, "log", "-1", "--format=%s")


def test_finalize_confirmed_after_one_sealed_run(ready_study) -> None:
    repo, study = ready_study
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "enter confirmation")
    run_one(
        study,
        final_test=True,
        command=metric_command(0.7, expected_kind="final_test"),
        echo=False,
    )
    (study / "findings.md").write_text(
        "# Findings\n\nThis study is confirmed, with uncertainty still stated.\n",
        encoding="utf-8",
    )
    assert finalize(study) == "confirmed"


def test_crashed_sealed_run_does_not_confirm_findings(ready_study) -> None:
    repo, study = ready_study
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "enter confirmation")
    crashed = run_one(
        study,
        final_test=True,
        command=[sys.executable, "-c", "import sys; sys.exit(7)"],
        echo=False,
    )
    assert crashed["disposition"] == "crash"
    (study / "findings.md").write_text(
        "# Findings\n\nThis study remains exploratory after confirmation crashed.\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError, match="successful sealed final-test"):
        finalize(study)
    assert finalize(study, allow_exploratory=True) == "exploratory"


def test_final_test_env_is_not_ambiently_inherited(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_EVALUATION_KIND", "development")
    log = tmp_path / "kind.log"
    run_subprocess(
        [sys.executable, "-c", "import os; print(os.environ['KLEIN_EVALUATION_KIND'])"],
        cwd=tmp_path,
        log_path=log,
        timeout_seconds=2,
        echo=False,
        env_overrides={"KLEIN_EVALUATION_KIND": "final_test"},
    )
    assert log.read_text(encoding="utf-8").splitlines()[0] == "final_test"


def test_manifest_integrity_resolves_commits_and_detects_hash_tampering(ready_study) -> None:
    repo, study = ready_study
    train = study / "train.py"
    train.write_text(train.read_text() + "\nCANDIDATE = True\n", encoding="utf-8")
    manifest = run_one(study, command=metric_command(0.7), echo=False)
    checks = verify_study(study)
    assert all(check.ok for check in checks), [check.message for check in checks if not check.ok]
    for commit in (
        manifest["base_commit"],
        manifest["candidate_commit"],
        manifest["transaction"]["evidence_commit"],
    ):
        assert git(repo, "cat-file", "-t", commit) == "commit"

    log = study / "runs" / "E0001" / "run.log"
    log.write_text(log.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    ledger = next(check for check in verify_study(study) if check.name == "ledger integrity")
    assert not ledger.ok
    assert "run-log hash mismatch" in ledger.message
    git(repo, "restore", "--", str(log.relative_to(repo)))

    manifest_path = study / "runs" / "E0001" / "manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    changed = json.loads(original)
    changed["code_patch_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger = next(check for check in verify_study(study) if check.name == "ledger integrity")
    assert "code_patch_hash does not match commits" in ledger.message

    manifest_path.write_text(original, encoding="utf-8")
    changed = json.loads(original)
    changed["base_commit"] = "f" * 40
    changed["transaction"]["evidence_commit"] = "e" * 40
    manifest_path.write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger = next(check for check in verify_study(study) if check.name == "ledger integrity")
    assert "base_commit does not resolve" in ledger.message
    assert "evidence_commit does not resolve" in ledger.message


@pytest.mark.parametrize("window", ["before_evidence", "after_evidence", "before_finalize"])
def test_recover_completes_each_transaction_window_idempotently(
    ready_study, monkeypatch, window: str
) -> None:
    repo, study = ready_study
    train = study / "train.py"
    train.write_text(train.read_text() + f"\nWINDOW = {window!r}\n", encoding="utf-8")
    original_complete = workflow._complete_evidence_transaction
    original_commit = workflow._git_commit

    if window == "before_evidence":
        def interrupt_complete(*_args, **_kwargs):
            raise RuntimeError("injected before evidence")

        monkeypatch.setattr(workflow, "_complete_evidence_transaction", interrupt_complete)
    else:
        def interrupt_commit(repo_path, message, **kwargs):
            if window == "before_finalize" and message.startswith("transaction "):
                raise RuntimeError("injected before finalization")
            result = original_commit(repo_path, message, **kwargs)
            if window == "after_evidence" and message.startswith("evidence "):
                raise RuntimeError("injected after evidence")
            return result

        monkeypatch.setattr(workflow, "_git_commit", interrupt_commit)

    with pytest.raises(RuntimeError, match="injected"):
        run_one(study, command=metric_command(0.7), echo=False)
    monkeypatch.setattr(workflow, "_complete_evidence_transaction", original_complete)
    monkeypatch.setattr(workflow, "_git_commit", original_commit)

    assert workflow.recover(study) == ["E0001"]
    assert workflow.recover(study) == []
    recovered = load_manifests(study)[0]
    assert recovered["transaction"]["status"] == "complete"
    assert recovered["transaction"]["recovered"] is (window != "before_finalize")
    assert git(repo, "cat-file", "-t", recovered["candidate_commit"]) == "commit"
    assert git(repo, "cat-file", "-t", recovered["transaction"]["evidence_commit"]) == "commit"
    assert git(repo, "status", "--porcelain") == ""
    assert all(check.ok for check in verify_study(study))


def test_recover_refuses_a_tampered_completed_manifest(ready_study) -> None:
    _, study = ready_study
    run_one(study, command=metric_command(0.7), echo=False)
    manifest_path = study / "runs" / "E0001" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = "tampered after the completed transaction"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(WorkflowError, match="refusing to recover modified complete manifest"):
        workflow.recover(study)

    ledger = next(
        check for check in verify_study(study) if check.name == "ledger integrity"
    )
    assert not ledger.ok
    assert "manifest differs from its HEAD blob" in ledger.message
