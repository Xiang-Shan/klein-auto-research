from __future__ import annotations

import json
from pathlib import Path

import pytest

from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import (
    StudyLock,
    WorkflowError,
    append_event,
    finalize,
    fingerprint_path,
    load_contract,
    migration_report,
    normalize_tracks,
    read_events,
    render_results,
    resolve_study,
    schema_version,
    status_summary,
    validate_contract,
    validate_manifest,
    verify_event_chain,
    verify_study,
)


def _contract(study_id: str = "03-quality") -> dict:
    return {
        "schema_version": 2,
        "study_id": study_id,
        "goal": "quality paths",
        "domain": "test",
        "target": "y",
        "task_type": "classification",
        "method_depth": "brief",
        "max_run_seconds": 10,
        "tracks": {
            "primary": {
                "metric": {"name": "val_auc", "goal": "higher", "minimum_delta": 0},
                "guardrails": {},
            }
        },
        "data": {
            "prepared_path": "data/prepared.csv",
            "split": {
                "kind": "stratified",
                "seed": 42,
                "development_size": 0.2,
                "test_size": 0.2,
            },
        },
        "phases": [
            {"id": "adaptive", "budget_seconds": 60, "max_experiments": 2},
            {"id": "confirmation", "budget_seconds": 30, "max_experiments": 1},
        ],
    }


def test_contract_validation_reports_independent_errors(tmp_path: Path) -> None:
    assert "invalid schema_version" in validate_contract({"schema_version": "nope"})[0]
    assert "schema_version must be 2" in validate_contract({"schema_version": 1})[0]

    bad = _contract("wrong-name")
    bad.update(
        method_depth="endless",
        task_type="ranking",
        max_run_seconds=0,
        note="{{UNRESOLVED}}",
        tracks=[
            {
                "id": "bad-track",
                "metric": {"name": "", "goal": "sideways", "minimum_delta": float("nan")},
                "guardrails": "not-a-mapping",
            }
        ],
        data={
            "prepared_path": "x",
            "split": {"kind": "leaky", "development_size": 0.8, "test_size": 0.5},
        },
        phases=[
            "not-a-phase",
            {"id": "dup", "budget_seconds": 0, "max_experiments": 0},
            {"id": "dup", "budget_seconds": "bad", "max_experiments": "bad"},
        ],
    )
    problems = validate_contract(bad, tmp_path / "03-quality")
    joined = "\n".join(problems)
    for expected in (
        "must equal directory name",
        "method_depth",
        "task_type",
        "max_run_seconds",
        "metric.name",
        "metric.goal",
        "metric.minimum_delta",
        "guardrails",
        "data.split.kind",
        "sum to < 1",
        "must be a mapping",
        "must be unique",
        "budget_seconds",
        "max_experiments",
        "unresolved placeholders",
    ):
        assert expected in joined


def test_contract_rejects_unsafe_guardrails_and_unusable_confirmation_phase() -> None:
    bad_guardrails = _contract()
    bad_guardrails["tracks"]["primary"]["guardrails"] = {
        "latency": {"max": float("nan")},
        "memory": {"min": 4, "max": 2},
        "drift": {"maximum_degradation": -0.1, "goal": "sideways"},
        "typo": {"maximum_degrade": 1},
    }
    joined = "\n".join(validate_contract(bad_guardrails))
    assert "latency" in joined and "max must be finite" in joined
    assert "min must be <= max" in joined
    assert "maximum_degradation must be finite and >= 0" in joined
    assert "goal must be higher or lower" in joined
    assert "unknown keys" in joined

    one_phase = _contract()
    one_phase["phases"] = one_phase["phases"][:1]
    assert "at least two phases" in "\n".join(validate_contract(one_phase))

    two_tracks = _contract()
    two_tracks["tracks"]["secondary"] = {
        "metric": {"name": "val_pr_auc", "goal": "higher", "minimum_delta": 0},
        "guardrails": {},
    }
    assert "number of tracks (2)" in "\n".join(validate_contract(two_tracks))


def test_track_normalization_and_schema_errors() -> None:
    tracks = normalize_tracks(
        {
            "tracks": [
                {
                    "id": "loss",
                    "metric_name": "rmse",
                    "metric_goal": "lower",
                    "minimum_delta": 0.1,
                }
            ]
        }
    )
    assert tracks["loss"]["metric"] == {
        "name": "rmse",
        "goal": "lower",
        "minimum_delta": 0.1,
    }
    assert tracks["loss"]["guardrails"] == {}
    with pytest.raises(WorkflowError, match="invalid schema_version"):
        schema_version({"schema_version": []})


def test_path_fingerprints_cover_file_tree_empty_missing_and_symlink(tmp_path: Path) -> None:
    prepared = tmp_path / "prepared.csv"
    prepared.write_text("x,y\n1,0\n", encoding="utf-8")
    first = fingerprint_path(prepared)
    prepared.write_text("x,y\n2,1\n", encoding="utf-8")
    assert fingerprint_path(prepared) != first

    tree = tmp_path / "tree"
    (tree / "nested").mkdir(parents=True)
    (tree / "nested" / "part.csv").write_text("x\n1\n", encoding="utf-8")
    assert len(fingerprint_path(tree)) == 64
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(WorkflowError, match="empty"):
        fingerprint_path(empty)
    with pytest.raises(WorkflowError, match="does not exist"):
        fingerprint_path(tmp_path / "missing")

    link = tmp_path / "link.csv"
    link.symlink_to(prepared)
    with pytest.raises(WorkflowError, match="symlink"):
        fingerprint_path(link)

    nested_link = tree / "nested" / "linked.csv"
    nested_link.symlink_to(prepared)
    with pytest.raises(WorkflowError, match="must not contain symlinks"):
        fingerprint_path(tree)


def test_resolve_load_lock_and_event_tamper_paths(tmp_path: Path) -> None:
    study = tmp_path / "03-quality"
    study.mkdir()
    config = study / "study.yaml"
    config.write_text("schema_version: 2\n", encoding="utf-8")
    assert resolve_study(config) == study
    assert load_contract(study) == {"schema_version": 2}
    with pytest.raises(WorkflowError, match="study directory not found"):
        resolve_study(tmp_path / "absent")

    with StudyLock(study):
        with pytest.raises(WorkflowError, match="another Klein operation"):
            with StudyLock(study):
                pass
    assert not (study / ".klein.lock").exists()

    append_event(study, "first", value=1)
    append_event(study, "second", value=2)
    assert len(read_events(study)) == 2
    assert verify_event_chain(study) == []
    events = read_events(study)
    events[1]["value"] = 999
    (study / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
    )
    assert any("event_hash" in item for item in verify_event_chain(study))
    (study / "events.jsonl").write_text("not-json\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="invalid JSON"):
        read_events(study)


def test_manifest_validation_and_derived_rendering() -> None:
    problems = "\n".join(validate_manifest({}))
    assert "experiment" in problems
    assert "track" in problems
    assert "disposition" in problems
    assert "fingerprints" in problems
    assert "artifacts" in problems

    malformed_artifact = {
        "experiment": "E0001",
        "track": "primary",
        "disposition": "crash",
        "base_commit": "a" * 40,
        "candidate_commit": "b" * 40,
        "code_patch_hash": "c" * 64,
        "primary_metric": None,
        "transaction": {"status": "pending"},
        "fingerprints": {"data": "d", "split": "s", "environment": "e"},
        "artifacts": {
            "models/a.joblib": {
                "availability": "somewhere",
                "sha256": "f" * 64,
                "bytes": 1,
                "committed": False,
            }
        },
    }
    assert "artifact availability is invalid" in "\n".join(
        validate_manifest(malformed_artifact)
    )

    manifests = [
        {
            "experiment": "E0001",
            "track": "primary",
            "primary_metric": 0.75,
            "disposition": "keep",
            "candidate_commit": "a" * 40,
            "description": "line one\nline two",
        },
        {
            "experiment": "E0002",
            "track": "primary",
            "primary_metric": None,
            "disposition": "crash",
            "candidate_commit": "b" * 40,
            "description": "broken",
        },
    ]
    result = render_results(manifests)
    assert "E0001\tprimary\t0.75\tkeep" in result
    assert "line one line two" in result
    assert "E0002\tprimary\tNA\tcrash" in result


def test_legacy_reports_and_v2_exploratory_finalize(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "study.yaml").write_text("goal: legacy\n", encoding="utf-8")
    (legacy / "results.tsv").write_text(
        "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n",
        encoding="utf-8",
    )
    assert "v1 (deprecated compatibility)" in status_summary(legacy)
    assert "deprecated v1 adapter" in migration_report(legacy)
    checks = verify_study(legacy)
    assert all(check.ok for check in checks)
    assert any("deprecated" in check.message for check in checks)

    study = scaffold_study(
        tmp_path,
        "03-finalize",
        goal="finish explicitly",
        domain="test",
        target="y",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
    )
    (study / "findings.md").write_text(
        "# Findings\n\nThis result remains exploratory.\n", encoding="utf-8"
    )
    with pytest.raises(WorkflowError, match="allow-exploratory"):
        finalize(study)
    assert finalize(study, allow_exploratory=True) == "exploratory"
    summary = status_summary(study)
    assert "status: finalized" in summary
    assert "pending transactions: none" in summary
