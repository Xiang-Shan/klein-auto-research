"""``klein demo``: a real study, run live, whose records the engine itself re-verifies."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kleinlib import cli
from kleinlib.demo import ACKNOWLEDGED_BY, run_demo
from kleinlib.next_step import next_step
from kleinlib.probe import probe_chain_problems, read_probes
from kleinlib.workflow import verify_study


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return run_demo(tmp_path_factory.mktemp("klein-demo") / "run", echo=False)


def _state(demo: dict) -> dict:
    return json.loads((Path(demo["study"]) / "study_state.json").read_text(encoding="utf-8"))


def test_summary_shape(demo: dict) -> None:
    assert set(demo) >= {
        "study", "repo", "seconds", "gates", "floor", "runs", "predictions", "probes", "next"
    }
    assert Path(demo["study"]) == Path(demo["repo"]) / "studies" / "01-demo"
    assert demo["seconds"] < 90


def test_three_gates_recorded_by_the_automated_acknowledger(demo: dict) -> None:
    assert set(demo["gates"]) == {"consult", "data", "method"}
    for name, gate in _state(demo)["gates"].items():
        if name in demo["gates"]:
            assert gate["status"] == "recorded"
            assert gate["acknowledged_by"] == ACKNOWLEDGED_BY
            assert "automated" in gate["acknowledged_by"]


def test_noise_floor_measured_and_in_the_contract(demo: dict) -> None:
    assert demo["floor"]["minimum_delta"] > 0
    assert demo["floor"]["estimand"] == "marginal-resplit"
    contract = (Path(demo["study"]) / "study.yaml").read_text(encoding="utf-8")
    assert f"minimum_delta: {demo['floor']['minimum_delta']:g}" in contract
    assert "noise_floor:" in contract
    assert "split_lottery" in _state(demo)["sweeps"]


def test_keep_keep_discard(demo: dict) -> None:
    assert [(r["experiment"], r["disposition"]) for r in demo["runs"]] == [
        ("E0001", "keep"),
        ("E0002", "keep"),
        ("E0003", "discard"),
    ]
    assert demo["runs"][1]["primary_metric"] > demo["runs"][0]["primary_metric"]


def test_p1_supported_p2_refuted(demo: dict) -> None:
    assert demo["predictions"] == {"P1": "supported", "P2": "refuted"}


def test_probe_before_gate_zero_is_on_the_record(demo: dict) -> None:
    study = Path(demo["study"])
    assert demo["probes"] == 1
    assert len(read_probes(study)) == 1
    assert probe_chain_problems(study) == []
    assert _state(demo)["gates"]["consult"]["probes"]["count"] == 1


def test_repo_clean_on_the_experiment_branch(demo: dict) -> None:
    repo = Path(demo["repo"])
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "symbolic-ref", "--short", "HEAD") == "experiments/01-demo"


def test_sealed_partition_untouched_and_nothing_finalized(demo: dict) -> None:
    study = Path(demo["study"])
    assert _state(demo)["final_holdout_access"]["primary"]["count"] == 0
    for name in ("findings.md", "claims.lock", "referee_report.md"):
        assert not (study / name).exists()


def test_verify_has_no_failing_check(demo: dict) -> None:
    checks = verify_study(Path(demo["study"]), receipt=False)
    assert [c.name for c in checks if not c.ok] == []


def test_next_action_is_the_experiment_stage(demo: dict) -> None:
    # Three of the phase's four runs are spent; the engine says so rather than
    # pretending the lifecycle is over.
    nxt = next_step(demo["study"])["next"]
    assert nxt["stage_id"] == "experiment"
    assert demo["next"]["stage_id"] == "experiment"


def test_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("mine", encoding="utf-8")
    assert cli.main(["demo", "--dir", str(tmp_path)]) == 2
    assert (tmp_path / "keep.txt").read_text(encoding="utf-8") == "mine"
    assert not (tmp_path / ".git").exists()


def test_nested_in_another_repository_never_touches_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init", "-q")
    (outer / "README.md").write_text("outer\n", encoding="utf-8")
    _git(outer, "add", "-A")
    _git(
        outer, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
        "commit", "-q", "-m", "outer",
    )
    head, branches = _git(outer, "rev-parse", "HEAD"), _git(outer, "branch", "--list")

    assert cli.main(["demo", "--dir", str(outer / "klein-demo"), "--json"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["verb"] == "demo" and envelope["ok"] is True
    assert envelope["data"]["predictions"] == {"P1": "supported", "P2": "refuted"}

    assert _git(outer, "status", "--porcelain") == "?? klein-demo/"
    assert _git(outer, "branch", "--list") == branches
    assert _git(outer, "rev-parse", "HEAD") == head
    inner = outer / "klein-demo"
    # git prints forward slashes on Windows; compare paths, not strings.
    assert Path(_git(inner, "rev-parse", "--show-toplevel")).resolve() == inner.resolve()
    assert _git(inner, "symbolic-ref", "--short", "HEAD") == "experiments/01-demo"
