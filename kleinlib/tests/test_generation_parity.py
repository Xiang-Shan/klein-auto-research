"""Expert parity and the contribution ledger (WP-04).

Test names carry their validation-plan id (V-14, V-15, V-16).  Four layers, kept
apart on purpose:

1. **The arithmetic** (:mod:`kleinlib.generation.stats`) on synthetic per-unit
   tables — determinism, the block structure, and the three ways a metric ends
   up with no bound at all.
2. **The decision rule** (:func:`kleinlib.generation.parity.decide`) on
   hand-written rows, including every boundary where two outcomes could
   otherwise both claim the same table.
3. **The bookkeeping** on a real fixture study — a registered comparison track
   whose sole sealed cell runs through ``run_one(final_test=True)``, assessed
   from its own pinned table and re-verified from the same bytes.
4. **The refusals** — a margin without a rationale, a prediction rule that does
   not test the locked margin, margins set by the actor under review, a sealed
   admission before the pipelines are frozen, and a scorer edited at the sealed
   candidate commit.

The fixtures compose ``test_generation_spine``'s scaffolding with
``test_generation_expert``'s domain card: parity requires expertise, so a parity
study is an expertise study that also locked ``parity.yaml``.
"""

from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from test_generation_expert import _reference, _set_experimenter, _write_card
from test_generation_slate import BANNED_FUNCTION_PREFIXES
from test_generation_spine import _bump, _gates, _gen, _receipt, _scaffold
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib.generation import contribution as gc
from kleinlib.generation import parity as gp
from kleinlib.generation import stats
from kleinlib.workflow import record_gate, run_one

STUDY = "03-demo"
EXPERIMENTER = "sonnet-experimenter"
REVIEWER = "an independent practitioner"
SCORER = "lib/parity_score.py"
AI_SNAPSHOT = "pipelines/ai.py"
EXPERT_SNAPSHOT = "pipelines/expert.py"

#: The three metrics of the A3 §6 smallest exercise: a ranking gain, a
#: calibration loss, and a ratio that a zero-loss bottom decile leaves undefined.
KEYS: tuple[str, ...] = ("gini", "calib", "ratio")

#: The contract's id grammar is ``P<number>``, so the lock's ``predictions`` map
#: is what ties a metric key to the prediction that adjudicates it.
PRED: dict[str, str] = {"gini": "P1", "calib": "P2", "ratio": "P3"}
DEV_PRED = "P4"
MARGIN = 0.01
FLOOR = 0.01
N_BOOT = 400


# --------------------------------------------------------------------------
# 1. the arithmetic
# --------------------------------------------------------------------------


def _spread(offset: float) -> np.ndarray:
    return np.array([0.06, 0.05, 0.055, 0.045, 0.058, 0.052, 0.049, 0.051]) + offset


BLOCKS = ["b1", "b1", "b2", "b2", "b3", "b3", "b4", "b4"]


def test_bounds_are_deterministic_and_straddle_the_mean() -> None:
    deltas = {"a": _spread(0.0), "b": _spread(-0.1)}
    first = stats.simultaneous_bounds(deltas, BLOCKS, n_boot=N_BOOT, seed=0)
    again = stats.simultaneous_bounds(deltas, BLOCKS, n_boot=N_BOOT, seed=0)
    assert first == again, "the same table and seed must give the same bounds everywhere"
    for key, values in deltas.items():
        low, high = first[key]
        assert low < float(values.mean()) < high


def test_iid_units_and_singleton_blocks_are_the_same_declaration() -> None:
    """`block_column: null` IS one unit per block — the sanity check for nesting."""
    deltas = {"a": _spread(0.0)}
    assert stats.simultaneous_bounds(deltas, None, n_boot=N_BOOT, seed=3) == (
        stats.simultaneous_bounds(deltas, list(range(8)), n_boot=N_BOOT, seed=3)
    )
    assert stats.block_count(None, 8) == 8
    assert stats.block_count(BLOCKS, 8) == 4


def test_a_zero_spread_metric_is_undefined_rather_than_certain() -> None:
    flat = np.full(8, 0.05)
    bounds = stats.simultaneous_bounds({"flat": flat, "real": _spread(0.0)}, BLOCKS, n_boot=N_BOOT)
    assert all(math.isnan(value) for value in bounds["flat"])
    assert all(math.isfinite(value) for value in bounds["real"])


def test_a_single_block_carries_no_bound_at_all() -> None:
    bounds = stats.simultaneous_bounds({"a": _spread(0.0)}, ["one"] * 8, n_boot=N_BOOT)
    assert all(math.isnan(value) for value in bounds["a"])


def test_a_nonfinite_metric_drops_out_and_the_rest_keep_their_bounds() -> None:
    broken = _spread(0.0).copy()
    broken[2] = float("nan")
    bounds = stats.simultaneous_bounds({"broken": broken, "ok": _spread(0.0)}, BLOCKS, n_boot=N_BOOT)
    assert all(math.isnan(value) for value in bounds["broken"])
    assert all(math.isfinite(value) for value in bounds["ok"])


def test_a_wider_family_never_gives_a_narrower_interval() -> None:
    """Simultaneity costs width — that is what makes the bounds joint."""
    alone = stats.simultaneous_bounds({"a": _spread(0.0)}, BLOCKS, n_boot=N_BOOT, seed=1)["a"]
    together = stats.simultaneous_bounds(
        {"a": _spread(0.0), "b": _spread(-0.1), "c": _spread(0.2)},
        BLOCKS,
        n_boot=N_BOOT,
        seed=1,
    )["a"]
    assert together[0] <= alone[0] + 1e-12 and together[1] + 1e-12 >= alone[1]


def test_an_unreproducible_replicate_count_is_refused() -> None:
    with pytest.raises(ValueError, match="n_boot"):
        stats.simultaneous_bounds({"a": _spread(0.0)}, BLOCKS, n_boot=stats.MIN_BOOT - 1)
    with pytest.raises(ValueError, match="alpha"):
        stats.simultaneous_bounds({"a": _spread(0.0)}, BLOCKS, n_boot=N_BOOT, alpha=1.0)
    with pytest.raises(ValueError, match="SAME sampling"):
        stats.simultaneous_bounds({"a": _spread(0.0), "b": np.zeros(3)}, None, n_boot=N_BOOT)


# --------------------------------------------------------------------------
# 2. the decision rule
# --------------------------------------------------------------------------


def _row(*, d: float, low: float, high: float, defined: bool = True) -> dict[str, Any]:
    return {
        "ai": 1.0,
        "expert": 1.0 - d,
        "d": d,
        "L": low,
        "U": high,
        "delta_floor": FLOOR,
        "margin": MARGIN,
        "defined": defined,
    }


def test_exceeds_needs_every_bound_above_zero_and_one_above_its_floor() -> None:
    verdict = gp.decide(
        {
            "gini": _row(d=0.05, low=0.02, high=0.08),
            "calib": _row(d=0.002, low=0.001, high=0.004),
        }
    )
    assert verdict["verdict"] == "exceeds"
    # every bound above zero but NONE above its floor is parity, not superiority
    assert (
        gp.decide(
            {
                "gini": _row(d=0.005, low=0.001, high=0.009),
                "calib": _row(d=0.002, low=0.001, high=0.004),
            }
        )["verdict"]
        == "parity"
    )


def test_parity_is_noninferiority_and_its_boundary_is_inclusive() -> None:
    assert gp.decide({"gini": _row(d=-0.005, low=-MARGIN, high=0.02)})["verdict"] == "parity"
    assert gp.decide({"gini": _row(d=-0.02, low=-0.011, high=0.02)})["verdict"] == "inconclusive"


def test_a_bound_entirely_below_the_margin_refutes() -> None:
    assert gp.decide({"gini": _row(d=-0.05, low=-0.08, high=-0.02)})["verdict"] == "refuted"
    # exactly AT -margin does not refute: the rule is strict
    assert gp.decide({"gini": _row(d=-0.05, low=-0.08, high=-MARGIN)})["verdict"] == "inconclusive"


def test_the_four_outcomes_cannot_both_hold(  ) -> None:
    """Refuted and parity contradict each other on the same metric, by construction."""
    for low, high in ((-0.005, 0.02), (-0.08, -0.02), (-0.011, 0.001), (0.02, 0.08)):
        verdict = gp.decide({"gini": _row(d=0.0, low=low, high=high)})["verdict"]
        assert verdict in gp.VERDICTS
        assert not (low >= -MARGIN and high < -MARGIN), "a lower bound above a refuting upper one"


def test_an_undefined_metric_can_never_pass() -> None:
    rows = {
        "gini": _row(d=0.05, low=0.02, high=0.08),
        "ratio": _row(d=float("nan"), low=float("nan"), high=float("nan"), defined=False),
    }
    decision = gp.decide(rows)
    assert decision["verdict"] == "inconclusive"
    assert decision["undefined_metrics"] == ["ratio"]
    rows["calib"] = _row(d=-0.05, low=-0.08, high=-0.02)
    assert gp.decide(rows)["verdict"] == "refuted", "another metric refuting still refutes"


def test_agreement_within_floor_is_reported_under_its_own_name_and_is_not_parity() -> None:
    """A4 §7's by-delta rule can hold while the conjunction is inconclusive."""
    decision = gp.decide({"gini": _row(d=0.004, low=-0.05, high=0.06)})
    assert decision["agreement_within_floor"] is True
    assert decision["verdict"] == "inconclusive"
    # and an undefined metric never agrees either
    undefined = gp.decide(
        {"ratio": _row(d=float("nan"), low=float("nan"), high=float("nan"), defined=False)}
    )
    assert undefined["agreement_within_floor"] is False


# --------------------------------------------------------------------------
# 3. the fixture study
# --------------------------------------------------------------------------


def _amend_contract(study: Path, transform) -> None:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    transform(contract)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


def _predictions() -> list[dict[str, Any]]:
    rows = [
        {
            "id": PRED[key],
            "track": "comparison",
            "statement": f"the AI pipeline is noninferior on {key}",
            "rule": {"key": f"L_{key}", "op": ">=", "value": -MARGIN},
        }
        for key in KEYS
    ]
    rows.append(
        {
            "id": DEV_PRED,
            "track": "primary",
            "statement": "the development metric clears 0.4",
            "rule": {"key": "primary_metric", "op": ">", "value": 0.4},
        }
    )
    return rows


def _two_tracks(contract: dict[str, Any]) -> None:
    contract["tracks"]["comparison"] = copy.deepcopy(contract["tracks"]["primary"])
    contract["tracks"]["comparison"]["mode"] = "registered"
    contract["tracks"]["comparison"]["metric"]["minimum_delta"] = 0.0
    contract["predictions"] = _predictions()
    contract["phases"][0]["max_experiments"] = 6
    contract["phases"][-1]["max_experiments"] = 2


def _parity_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "parity",
        "study": STUDY,
        "comparison_track": "comparison",
        "sampling_unit": "policy-year",
        "block_column": "block",
        "pipelines": {
            "ai": {
                "name": "candidate",
                "description": "the AI-built pipeline",
                "owner": EXPERIMENTER,
                "selection_rule": "the frontier incumbent at the phase boundary",
            },
            "expert": {
                "name": "control",
                "description": "the reproduced expert recipe",
                "owner": REVIEWER,
                "selection_rule": "the domain card's baseline, unchanged",
            },
        },
        "budget_rule": "one machine-hour and the same features for both pipelines",
        "metrics": [
            {
                "key": "gini",
                "name": "exposure-weighted ranking Gini",
                "direction": "higher",
                "units": "Gini points",
                "estimand": "paired per-policy-year contribution to the Gini",
                "floor_ref": "run:E0002",
                "margin": MARGIN,
                "margin_rationale": "underwriting accepts a 0.01 Gini give-back for a simpler rate plan",
                "undefined_handling": "cannot_pass",
            },
            {
                "key": "calib",
                "name": "calibration error",
                "direction": "lower",
                "units": "absolute loss ratio error",
                "estimand": "paired per-policy-year absolute calibration error",
                "floor_ref": "run:E0002",
                "margin": MARGIN,
                "margin_rationale": "a 0.01 calibration drift is inside the reserving tolerance",
                "undefined_handling": "cannot_pass",
            },
            {
                "key": "ratio",
                "name": "top-to-bottom decile ratio",
                "direction": "higher",
                "units": "ratio",
                "estimand": "paired per-policy-year decile contribution",
                "floor_ref": "run:E0002",
                "margin": MARGIN,
                "margin_rationale": "the ratio is a communication metric; a 0.01 move is not material",
                "undefined_handling": "cannot_pass",
            },
        ],
        "uncertainty": {
            "method": "block_bootstrap_maxt",
            "n_boot": N_BOOT,
            "seed": 0,
            "alpha": 0.05,
        },
        "aggregation": "conjunction",
        "scorer": {"path": SCORER},
        "margins_set_by": {"name": REVIEWER, "session_receipt": None},
        "scoring": {"masked": True, "scorer_name": REVIEWER},
        "predictions": dict(PRED),
        "ablation_study": None,
    }
    payload.update(overrides)
    return payload


def _write_parity(study: Path, payload: dict[str, Any] | None = None) -> Path:
    path = study / gp.PARITY_NAME
    path.write_text(
        yaml.safe_dump(payload if payload is not None else _parity_payload(), sort_keys=False),
        encoding="utf-8",
    )
    return path


def _write_pipeline_files(study: Path) -> None:
    for rel, text in (
        (SCORER, "# the study-local parity scorer\nSCORER = 1\n"),
        (AI_SNAPSHOT, "# the frozen AI pipeline\nPIPELINE = 'ai'\n"),
        (EXPERT_SNAPSHOT, "# the frozen expert pipeline\nPIPELINE = 'expert'\n"),
    ):
        path = study / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _enable(tmp_path: Path, *capabilities: str) -> tuple[Path, Path]:
    """A schema-3 study with a comparison track, opted in, gates NOT yet recorded."""
    repo, study = _scaffold(tmp_path)
    _amend_contract(study, _two_tracks)
    _write_pipeline_files(study)
    _set_experimenter(repo, study, EXPERIMENTER)
    commit_all(repo, "comparison track, pipelines and roster")
    argv = ["init", "--study", str(study)]
    for name in capabilities:
        argv += ["--capability", name]
    assert _gen(*argv) == 0
    return repo, study


@pytest.fixture
def parity_study(tmp_path: Path) -> tuple[Path, Path]:
    """Card and parity locked before the gates; baseline reproduced; floors measured."""
    repo, study = _enable(tmp_path, "expertise", "parity")
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study), "--actor", EXPERIMENTER) == 0
    _write_parity(study)
    assert _gen("parity", "lock", "--study", str(study), "--actor", EXPERIMENTER) == 0
    _gates(repo, study)

    _bump(study, "baseline")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, track="primary", command=metric_command(0.5), echo=False)[
        "experiment"
    ] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 0

    _bump(study, "floors")
    assert (
        _gen("check", "--study", str(study), "--action", "calibration", "--track", "comparison") == 0
    )
    floors = {f"floor_{key}": FLOOR for key in KEYS}
    assert run_one(
        study, track="comparison", command=metric_command(0.7, extra=floors), echo=False
    )["experiment"] == "E0002"
    return repo, study


@pytest.fixture
def bound_study(parity_study) -> tuple[Path, Path]:
    repo, study = parity_study
    assert (
        _gen(
            "parity",
            "bind",
            "--study",
            str(study),
            "--ai-snapshot",
            AI_SNAPSHOT,
            "--expert-snapshot",
            EXPERT_SNAPSHOT,
        )
        == 0
    )
    return repo, study


# --- the sealed comparison cell -------------------------------------------


def _units(*, calib_spread: float = 0.0, undefined: bool = True) -> dict[str, Any]:
    """One per-unit table plus the printed block a real scorer would emit.

    ``gini`` is a clear AI gain, ``calib`` a clear AI LOSS (direction ``lower``),
    and ``ratio`` is undefined on one unit — A4 §7's zero-loss bottom decile.
    """
    gain = _spread(0.0)
    loss = _spread(0.0) + calib_spread * np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
    columns = {
        "ai_gini": 0.30 + gain,
        "expert_gini": np.full(8, 0.30),
        "ai_calib": 0.10 + loss,
        "expert_calib": np.full(8, 0.10),
        "ai_ratio": np.array([2.0, 2.1, 2.2, 2.0, 2.1, 2.0, 2.2, 2.1]),
        "expert_ratio": np.full(8, 2.05),
    }
    if undefined:
        columns["ai_ratio"] = columns["ai_ratio"].copy()
        columns["ai_ratio"][3] = float("nan")

    deltas = {
        "gini": columns["ai_gini"] - columns["expert_gini"],
        "calib": -(columns["ai_calib"] - columns["expert_calib"]),
        "ratio": columns["ai_ratio"] - columns["expert_ratio"],
    }
    bounds = stats.simultaneous_bounds(deltas, BLOCKS, n_boot=N_BOOT, seed=0)

    header = ["unit", "block", *[f"{side}_{key}" for key in KEYS for side in ("ai", "expert")]]
    lines = ["\t".join(header)]
    for index in range(8):
        cells = [f"u{index + 1}", BLOCKS[index]]
        for key in KEYS:
            for side in ("ai", "expert"):
                cells.append(format(float(columns[f"{side}_{key}"][index]), ".12g"))
        lines.append("\t".join(cells))
    table = "\n".join(lines) + "\n"

    printed: dict[str, float] = {"n_units": 8.0, "n_blocks": 4.0}
    for key in KEYS:
        printed[f"ai_{key}"] = float(np.mean(columns[f"ai_{key}"]))
        printed[f"expert_{key}"] = float(np.mean(columns[f"expert_{key}"]))
        printed[f"d_{key}"] = float(np.mean(deltas[key]))
        printed[f"L_{key}"], printed[f"U_{key}"] = (float(value) for value in bounds[key])
        printed[f"defined_{key}"] = 0.0 if math.isnan(bounds[key][0]) else 1.0
    return {"table": table, "printed": printed, "bounds": bounds}


def _cell_command(table: str) -> list[str]:
    printed = {
        key: value
        for key, value in _CELL["printed"].items()
        if not (isinstance(value, float) and math.isnan(value))
    }
    command = metric_command(0.05, artifacts=[gp.UNITS_TABLE], extra=printed)
    prologue = (
        "import pathlib; "
        f"_p = pathlib.Path({gp.UNITS_TABLE!r}); "
        "_p.parent.mkdir(parents=True, exist_ok=True); "
        f"_p.write_bytes({table!r}.encode()); "
    )
    command[-1] = prologue + command[-1]
    return command


_CELL = _units()


def _seal(repo: Path, study: Path, *, track: str = "comparison") -> dict[str, Any]:
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "acknowledge the adaptive phase")
    _gen(
        "check",
        "--study",
        str(study),
        "--action",
        "sealed",
        "--track",
        track,
        "--tests",
        *PRED.values(),
    )
    return run_one(
        study,
        track=track,
        final_test=True,
        command=_cell_command(_CELL["table"]),
        tests=list(PRED.values()),
        echo=False,
    )


def _capability(study: Path, name: str) -> dict[str, Any]:
    return _receipt(study)["capabilities"][name]


def _statuses(study: Path, prefix: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for check in _receipt(study)["checks"]:
        if check["name"].startswith(prefix):
            out.setdefault(check["name"], []).append(check["status"])
    return out


def _detail(study: Path, name: str) -> str:
    return " ".join(
        check["detail"] for check in _receipt(study)["checks"] if check["name"] == name
    )


# --------------------------------------------------------------------------
# V-14 — the A3 §6 smallest exercise
# --------------------------------------------------------------------------


def test_v14_a_ranking_gain_with_a_calibration_loss_fails_the_conjunction(bound_study) -> None:
    """V-14: gini up, calib down beyond -epsilon, ratio undefined → not parity."""
    repo, study = bound_study
    manifest = _seal(repo, study)
    assert manifest["evaluation_kind"] == "final_test"
    assert manifest["experiment"] == "E0003"

    assert _gen("parity", "assess", "--study", str(study), "--run", "E0003") == 2
    assert _gen("verify", "--study", str(study)) == 0

    outcome = _capability(study, "parity")
    assert outcome["integrity"] == "PASS"
    assert outcome["outcome"] == "refuted"
    assert outcome["undefined_metrics"] == ["ratio"]
    assert outcome["agreement_within_floor"] is False
    assert outcome["review"] == "source-reconstructed"

    events = json.loads(
        (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert events["type"] == gp.ASSESS_TYPE and events["verdict"] == "refuted"

    # the notary reached the same inequality on the printed block
    assert manifest["predictions"][PRED["gini"]]["verdict"] == "supported"
    assert manifest["predictions"][PRED["calib"]]["verdict"] == "refuted"


def test_v14_the_by_delta_rule_is_reported_separately_and_never_reads_as_parity(
    bound_study,
) -> None:
    repo, study = bound_study
    _seal(repo, study)
    assert _gen("parity", "assess", "--study", str(study), "--run", "E0003") == 2
    obj = _assessment(study)
    assert obj["agreement_within_floor"] is False
    assert obj["verdict"] != "parity"
    # gini moved far more than its measured floor, so the two questions differ
    assert abs(obj["metrics"]["gini"]["d"]) > obj["metrics"]["gini"]["delta_floor"]


def test_v14_an_undefined_metric_is_named_in_the_record(bound_study) -> None:
    repo, study = bound_study
    _seal(repo, study)
    assert _gen("parity", "assess", "--study", str(study), "--run", "E0003") == 2
    obj = _assessment(study)
    assert obj["metrics"]["ratio"]["defined"] is False
    assert obj["metrics"]["ratio"]["L"] is None
    assert obj["undefined_metrics"] == ["ratio"]
    assert any("cannot pass" in reason for reason in obj["reasons"])


def _assessment(study: Path) -> dict[str, Any]:
    from kleinlib.generation.ledger import read_events

    return gp.joined(study, read_events(study), gp.ASSESS_TYPE)[-1][1]


# --------------------------------------------------------------------------
# V-15 — custody of sealed access
# --------------------------------------------------------------------------


def test_v15_a_sealed_admission_is_refused_until_the_pipelines_are_bound(parity_study) -> None:
    repo, study = parity_study
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "acknowledge the adaptive phase")
    assert (
        _gen("check", "--study", str(study), "--action", "sealed", "--track", "primary") == 2
    ), "a frontier seal before the bind puts the comparison out of reach"
    receipt = _last_receipt(study)
    assert receipt["verdict"] == "refused"
    assert any("parity bind" in reason for reason in receipt["reasons"])


def test_v15_a_frontier_seal_before_the_bind_fails_the_parity_family(parity_study) -> None:
    """The core still grants the look (D-2); the extension records that it was spent."""
    repo, study = parity_study
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "acknowledge the adaptive phase")
    assert _gen("check", "--study", str(study), "--action", "sealed", "--track", "primary") == 2
    run_one(
        study,
        track="primary",
        final_test=True,
        command=metric_command(0.6),
        echo=False,
    )
    assert (
        _gen(
            "parity",
            "bind",
            "--study",
            str(study),
            "--ai-snapshot",
            AI_SNAPSHOT,
            "--expert-snapshot",
            EXPERT_SNAPSHOT,
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "parity bind")["parity bind"] == ["FAIL"]
    assert "before the bind anchored" in _detail(study, "parity bind")
    assert _capability(study, "parity")["integrity"] == "FAIL"


def test_v15_a_scorer_edited_at_the_sealed_candidate_fails(bound_study) -> None:
    """R-INV-3: the checker is never the searcher, and the seal is where it shows."""
    repo, study = bound_study
    (study / SCORER).write_text("# the scorer, retuned\nSCORER = 2\n", encoding="utf-8")
    commit_all(repo, "retune the scorer after the bind")
    _seal(repo, study)
    assert _gen("verify", "--study", str(study)) == 2
    assert "is not the file the bind pinned" in _detail(study, "parity bind")
    assert _capability(study, "parity")["integrity"] == "FAIL"


def test_the_sealed_cell_is_the_comparison_tracks_sole_sealed_evaluation(bound_study) -> None:
    repo, study = bound_study
    _seal(repo, study)
    assert _gen("parity", "assess", "--study", str(study), "--run", "E0003") == 2
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(study, "parity cell")["parity cell"] == ["PASS"]
    assert "admitted as sealed" in _detail(study, "parity cell")


def test_a_tampered_assessment_does_not_recompute(bound_study) -> None:
    repo, study = bound_study
    _seal(repo, study)
    assert _gen("parity", "assess", "--study", str(study), "--run", "E0003") == 2
    obj = _assessment(study)
    sha = _assessment_sha(study)
    obj["verdict"] = "parity"
    (study / "generation" / "objects" / f"{sha}.json").write_text(
        json.dumps(obj, indent=2) + "\n", encoding="utf-8"
    )
    git(repo, "add", "-A", "--", str(study / "generation"))
    git(repo, "commit", "-q", "-m", "tamper")
    assert _gen("verify", "--study", str(study)) == 2
    assert "does not recompute" in _detail(study, "parity assessment")


def _assessment_sha(study: Path) -> str:
    from kleinlib.generation.ledger import read_events

    return str(gp.joined(study, read_events(study), gp.ASSESS_TYPE)[-1][0]["payload_sha256"])


def _last_receipt(study: Path) -> dict[str, Any]:
    from kleinlib.generation.admission import load_receipts
    from kleinlib.generation.ledger import read_events, read_object

    events = read_events(study)
    return read_object(study, load_receipts(study, events)[-1].sha)


# --------------------------------------------------------------------------
# the lock refusals
# --------------------------------------------------------------------------


@pytest.fixture
def locked_ready(tmp_path: Path) -> tuple[Path, Path]:
    """Opted in, card locked, gates NOT recorded — ready for one `parity lock`."""
    repo, study = _enable(tmp_path, "expertise", "parity")
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study)) == 0
    return repo, study


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda p: p["metrics"][0].pop("margin_rationale"), "margin_rationale is required"),
        (lambda p: p["metrics"][0].update(margin=0.02), "the locked margin for gini"),
        (lambda p: p["margins_set_by"].update(name=EXPERIMENTER), "roster experimenter"),
        (lambda p: p.update(comparison_track="primary"), "is a 'frontier' track"),
        (lambda p: p.update(aggregation="any_of"), "aggregation is 'any_of'"),
        (lambda p: p["metrics"][0].update(floor_ref="guessed"), "floor_ref is 'guessed'"),
        (lambda p: p["uncertainty"].update(method="normal"), "uncertainty.method"),
        (lambda p: p["metrics"][0].update(undefined_handling="drop"), "undefined_handling"),
        (lambda p: p["predictions"].pop("ratio"), "predictions.ratio is required"),
        (lambda p: p.pop("ablation_study"), "ablation_study is required"),
    ],
)
def test_the_lock_refuses_a_criterion_it_cannot_hold(locked_ready, mutate, needle) -> None:
    _repo, study = locked_ready
    payload = _parity_payload()
    mutate(payload)
    _write_parity(study, payload)
    assert _gen("parity", "lock", "--study", str(study)) == 2
    assert not gp.locks(study, _events(study))


def test_a_margin_the_actor_under_review_set_is_refused_by_name(locked_ready, capsys) -> None:
    _repo, study = locked_ready
    payload = _parity_payload()
    payload["margins_set_by"]["name"] = EXPERIMENTER
    _write_parity(study, payload)
    assert _gen("parity", "lock", "--study", str(study)) == 2
    assert "cannot set the bar it is measured against" in capsys.readouterr().out


def test_a_late_lock_is_refused_and_recorded_late_when_forced(tmp_path: Path) -> None:
    repo, study = _enable(tmp_path, "expertise", "parity")
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study)) == 0
    _gates(repo, study)
    _write_parity(study)
    assert _gen("parity", "lock", "--study", str(study)) == 2
    assert _gen("parity", "lock", "--study", str(study), "--allow-late") == 0
    assert gp.locks(study, _events(study))[0][1]["late"] is True
    assert _gen("verify", "--study", str(study)) == 2
    assert "locked after the consult gate" in _detail(study, "parity lock")


def test_an_amendment_may_not_move_a_margin(parity_study) -> None:
    _repo, study = parity_study
    payload = _parity_payload()
    payload["metrics"][0]["margin"] = 0.05
    payload["predictions"] = dict(payload["predictions"])
    _write_parity(study, payload)
    assert _gen("parity", "amend", "--study", str(study)) == 2
    payload = _parity_payload(ablation_study="14-frozen-baseline")
    _write_parity(study, payload)
    assert _gen("parity", "amend", "--study", str(study)) == 0
    versions = gp.locks(study, _events(study))
    assert [obj["version"] for _event, obj in versions] == [1, 2]


def test_a_bind_needs_a_reproduced_baseline_and_a_numeric_floor(tmp_path: Path) -> None:
    repo, study = _enable(tmp_path, "expertise", "parity")
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study)) == 0
    _write_parity(study)
    assert _gen("parity", "lock", "--study", str(study)) == 0
    _gates(repo, study)
    assert (
        _gen(
            "parity",
            "bind",
            "--study",
            str(study),
            "--ai-snapshot",
            AI_SNAPSHOT,
            "--expert-snapshot",
            EXPERT_SNAPSHOT,
        )
        == 2
    ), "the expertise obligation is still open"


def test_a_sweep_floor_reference_is_refused_with_the_reason(parity_study, capsys) -> None:
    """A registered sweep pins hashes, not a number — say so instead of inventing delta."""
    _repo, study = parity_study
    payload = _parity_payload()
    for row in payload["metrics"]:
        row["floor_ref"] = "sweep:parity_floor"
    _write_parity(study, payload)
    # the sweep must be registered for the lock to accept the reference at all
    assert _gen("parity", "amend", "--study", str(study)) == 0
    assert (
        _gen(
            "parity",
            "bind",
            "--study",
            str(study),
            "--ai-snapshot",
            AI_SNAPSHOT,
            "--expert-snapshot",
            EXPERT_SNAPSHOT,
        )
        == 2
    )
    assert "not a numeric floor" in capsys.readouterr().err


def _events(study: Path) -> list[dict[str, Any]]:
    from kleinlib.generation.ledger import read_events

    return read_events(study)


# --------------------------------------------------------------------------
# V-16 — the contribution ledger
# --------------------------------------------------------------------------

SLATE_PHASE = "adaptive-1"


def _slate_row(index: int) -> dict[str, Any]:
    return {
        "kind": "diff",
        "track": "primary",
        "lever_family": f"lever-{index}",
        "statement": f"candidate {index} moves val_auc",
        "source_ids": ["playbook"],
        "provenance": "unscouted",
        "p_success": 0.5,
        "success_P": [DEV_PRED],
        "expected_effect": 0.01 * index,
        "units": "val_auc",
        "floor_ref": "minimum_delta",
        "cost_budget": "1 run",
        "novelty": 2,
        "testability": 3,
        "information": 2,
    }


@pytest.fixture
def ledger_study(tmp_path: Path) -> tuple[Path, Path]:
    """A study declaring ``slates`` + ``contribution`` with a five-row slate."""
    repo, study = _enable(tmp_path, "slates", "contribution")
    _gates(repo, study)
    path = study / "slates" / f"{SLATE_PHASE}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "type": "slate",
                "study": STUDY,
                "phase": SLATE_PHASE,
                "cohort_window": {"closes": "phase-end"},
                "base_rate_forecast": 0.4,
                "rows": [_slate_row(index) for index in range(1, 6)],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert _gen("slate", "lock", "--study", str(study), "--phase", SLATE_PHASE) == 0
    return repo, study


def _record(study: Path, subject: str, **flags: str) -> int:
    argv = [
        "contribution",
        "record",
        "--study",
        str(study),
        "--kind",
        flags.pop("kind", "proposal"),
        "--subject",
        subject,
        "--origin",
        flags.pop("origin", "ai"),
        "--actor",
        flags.pop("actor", "sonnet"),
    ]
    for key, value in flags.items():
        argv += [f"--{key.replace('_', '-')}", value]
    return _gen(*argv)


def test_v16_a_ledger_that_misses_one_slate_row_fails_coverage(ledger_study) -> None:
    _repo, study = ledger_study
    for index in range(1, 5):
        assert _record(study, f"{STUDY}#H{index}") == 0
    assert _gen("verify", "--study", str(study)) == 2
    detail = _detail(study, "contribution coverage")
    assert f"{STUDY}#H5" in detail and "coverage 0.8" in detail
    assert _capability(study, "contribution")["integrity"] == "FAIL"

    assert _record(study, f"{STUDY}#H5", kind="rejection", decision="rejected") == 0
    assert _gen("verify", "--study", str(study)) == 0
    outcome = _capability(study, "contribution")
    assert (outcome["integrity"], outcome["coverage"]) == ("PASS", 1.0)


def test_v16_an_accepted_row_with_no_human_acceptor_stays_agent_accepted(ledger_study) -> None:
    _repo, study = ledger_study
    for index in range(1, 6):
        assert (
            _record(study, f"{STUDY}#H{index}", kind="decision", decision="accepted") == 0
        )
    assert _gen("verify", "--study", str(study)) == 0
    outcome = _capability(study, "contribution")
    assert outcome["outcome"] == "descriptive"
    assert outcome["agent_accepted"] == 5
    assert "agent-accepted" in _detail(study, "contribution ledger")


def test_a_human_acceptor_belongs_only_on_an_accepted_row(ledger_study) -> None:
    _repo, study = ledger_study
    assert (
        _record(
            study,
            f"{STUDY}#H1",
            kind="decision",
            decision="rejected",
            human_acceptor="the underwriter",
        )
        == 2
    )
    assert gc.read_lines(study) == []


def test_an_edited_ledger_line_fails_the_two_witnesses(ledger_study) -> None:
    repo, study = ledger_study
    for index in range(1, 6):
        assert _record(study, f"{STUDY}#H{index}") == 0
    path = gc.ledger_path(study)
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["outcome"] = "it worked beautifully"
    lines[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    commit_all(repo, "improve the record after the fact")
    assert _gen("verify", "--study", str(study)) == 2
    assert "append-only" in _detail(study, "contribution ledger")


def test_the_ledger_covers_a_hypothesis_admission_that_was_refused(ledger_study) -> None:
    """Coverage counts the work, not the wins: a refused admission still needs a line."""
    _repo, study = ledger_study
    assert (
        _gen(
            "check",
            "--study",
            str(study),
            "--action",
            "run",
            "--track",
            "primary",
            "--hypothesis",
            f"{STUDY}#H9",
            "--tests",
            DEV_PRED,
        )
        == 2
    ), "H9 is not a row of the locked slate"
    for index in range(1, 6):
        assert _record(study, f"{STUDY}#H{index}") == 0
    assert _gen("verify", "--study", str(study)) == 2
    assert f"{STUDY}#H9" in _detail(study, "contribution coverage")

    assert _record(study, f"{STUDY}#H9", kind="error", outcome="a typo in the hypothesis id") == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study, "contribution")["coverage"] == 1.0


def test_ablation_cited_needs_a_parity_lock_that_names_a_matched_arm(tmp_path: Path) -> None:
    repo, study = _enable(tmp_path, "expertise", "slates", "parity", "contribution")
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study)) == 0
    _write_parity(study)
    assert _gen("parity", "lock", "--study", str(study)) == 0
    _gates(repo, study)
    assert _record(study, "playbook.md", kind="proposal") == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study, "contribution")["outcome"] == "descriptive"
    assert _capability(study, "parity")["outcome"] == "unassessed"

    _write_parity(study, _parity_payload(ablation_study="14-frozen-baseline"))
    assert _gen("parity", "amend", "--study", str(study)) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study, "contribution")["outcome"] == "ablation-cited"


# --------------------------------------------------------------------------
# the boundary: nothing here proposes, ranks or selects
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module", ["parity", "contribution", "stats"])
def test_nothing_here_proposes_ranks_or_selects(module: str) -> None:
    """R-SLA-6's guard, applied to WP-04's modules (plan N-1, N-2).

    Prose may say "proposal" — the ledger records them.  What the modules may
    not do is DEFINE one: no function that proposes, ranks, selects or chooses.
    """
    package = Path(__file__).resolve().parents[1] / "generation"
    text = (package / f"{module}.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.lstrip("_").startswith(BANNED_FUNCTION_PREFIXES)
    ]
    assert not offenders, f"{module}.py defines {offenders} — the layer never generates"
    for banned in ("run_one", "subprocess", "requests", "httpx", "urllib", "socket"):
        assert f"import {banned}" not in text and f"from {banned}" not in text, module
    assert "run_one(" not in text, f"{module}.py must never drive the notary"
