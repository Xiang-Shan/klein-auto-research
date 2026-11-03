"""``klein next`` / ``klein status --json`` — read-only guidance from the records."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from test_workflow_v3 import _fill, commit_all, git

from kleinlib.cli import main
from kleinlib.next_step import next_step, sealed_tracks, status_data
from kleinlib.scaffold import scaffold_study
from kleinlib.state import record_gate

ROOT = Path(__file__).resolve().parents[2]


def _fresh(tmp_path: Path) -> tuple[Path, Path]:
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
    return repo, study


def _tree_state(repo: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_fresh_scaffold_asks_for_the_contract(tmp_path: Path) -> None:
    _, study = _fresh(tmp_path)
    result = next_step(study)
    assert result["next"]["stage"] == "CONSULT"
    assert "placeholder" in result["next"]["action"]
    assert result["done"] == []


def test_filled_contract_asks_for_the_consult_ack(tmp_path: Path) -> None:
    _, study = _fresh(tmp_path)
    _fill(study)
    result = next_step(study)
    assert result["next"]["stage"] == "CONSULT"
    assert "klein gate record consult" in result["next"]["command"]


def test_walks_data_then_method_then_branch_then_floor(tmp_path: Path) -> None:
    repo, study = _fresh(tmp_path)
    _fill(study)
    record_gate(study, "consult", acknowledged_by="tester")
    step = next_step(study)["next"]
    assert step["stage"] == "DATA"
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    assert "data_card.md" in next_step(study)["next"]["action"]
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    assert "klein gate record data" in next_step(study)["next"]["command"]
    record_gate(study, "data", acknowledged_by="tester")
    assert next_step(study)["next"]["stage"] == "METHOD"
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "gates")
    step = next_step(study)["next"]
    assert "experiments/03-demo" in step["action"]
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    step = next_step(study)["next"]
    assert step["stage"].startswith("EXPERIMENT")
    assert "noise floor" in step["action"]
    assert "klein noise-floor" in step["command"]


def test_next_never_writes(ready_study_v3: tuple[Path, Path]) -> None:
    repo, study = ready_study_v3
    before = _tree_state(repo)
    events_before = (study / "events.jsonl").read_bytes()
    next_step(study)
    status_data(study)
    assert _tree_state(repo) == before
    assert (study / "events.jsonl").read_bytes() == events_before
    assert not (study / ".klein.lock").exists()


def test_shipped_closed_study_reports_closed() -> None:
    result = next_step(ROOT / "studies" / "00-known-truth-quickstart")
    assert result["next"]["stage"] == "closed"
    assert any("finalized" in item for item in result["done"])


def test_status_json_matches_the_ledger() -> None:
    data = status_data(ROOT / "studies" / "12-insurance-claims-frequency")
    assert data["schema"] == 3
    assert data["experiments"]["total"] == 5
    assert data["tracks"]["primary"]["sealed"]["experiment"] == "E0005"
    assert data["predictions"]["open"] == 0
    assert data["next"]["stage"] == "closed"


def test_cli_next_and_status_json(capsys) -> None:
    study = (ROOT / "studies" / "00-known-truth-quickstart").as_posix()
    assert main(["next", "--study", study, "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["next"]["stage"] == "closed"
    assert main(["next", "--study", study]) == 0
    assert "stage: closed" in capsys.readouterr().out
    assert main(["status", "--study", study, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["study"] == "00-known-truth-quickstart"


def test_sealed_tracks_skip_a_track_that_closes_on_replication() -> None:
    contract = {"kind": "estimate", "schema_version": 3}
    tracks = {
        "primary": {"confirmation": {"require": ["sealed", "replicate"]}},
        "exponent": {"confirmation": {"require": ["replicate"]}},
        "default": {},
    }
    assert sealed_tracks(tracks, contract) == ["primary", "default"]
