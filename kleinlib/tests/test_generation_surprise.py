"""The ``surprise`` capability (WP-06): register the search space, keep the nulls.

Test names carry their requirement id.  The spine's and WP-09's fixtures are
reused verbatim — a generation-enabled study that declared ``design`` and
``surprise`` — so what these exercise is the REGISTRATION path plus the four
requirements the capability exists for:

R-SUR-1  ``discovery_cells.yaml`` is registered before its evidence; adapters
         live outside the mutable surface and are hashed.
R-SUR-2  the table carries every eligible segment, ``minimum_n`` makes a sparse
         slice inconclusive, and the multiplicity rule is declared — a measured
         effect floor is not one (RF-13).
R-SUR-3  ``<study>#Sn`` receipts come from the pinned table, may stay
         ``unresolved``, and are ALWAYS fully qualified (RF-02: a bare ``S3``
         is a scouting-ledger entry).
R-SUR-4  verify recomputes the summaries and verdicts, and a ``confirmed`` claim
         resting on a discovery table FAILs (R-INV-6).

The fixture is A3 §3's smallest exercise: two habitats plus a positive control
segment, a null control and a sparse slice, measured by all three templates.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_generation_spine import _gen, _receipt, _scaffold
from test_workflow_v3 import commit_all, git

from kleinlib.decision import METRIC_LINE_RE
from kleinlib.generation import surprise as gs
from kleinlib.generation import templates as gt
from kleinlib.workflow import record_gate, run_one

PREDICTIONS = """
predictions:
  - id: P1
    track: primary
    statement: "the candidate beats the incumbent on the printed metric"
    rule: {key: primary_metric, op: ">=", value: 0.0}
    inconclusive_if: {key: primary_metric, op: "abs_lt", value: 0.001}
  - id: P4
    track: primary
    statement: "no registered segment deviates from its expectation by more than 0.5"
    rule: {key: cell_max_abs_deviation, op: "<", value: 0.5}
"""

DESIGN = {
    "type": "evidence-design",
    "study": "03-demo",
    "question": {
        "estimand": "the per-habitat bias of the expectation model",
        "population": "the observations of the fixture table",
        "units": "observation",
        "measurement_process": "the adapter subtracts the model's expectation from the observation",
        "identification_assumptions": ["the observations within a habitat are exchangeable"],
        "intended_generalization": "this fixture only; nothing travels off it",
    },
    "prediction": {
        "uncertainty_method": "a sign-flip max-t over the registered segment family",
        "validity_conditions": [
            {"condition": "the run printed a metric indistinguishable from zero", "rule_ref": "P1"}
        ],
        "practical_threshold": "a deviation of 0.5 would change where the next study looks",
        "provenance": "the expectation model published with the fixture",
    },
    "evidence": {
        "representations": ["data/prepared/observations.csv"],
        "dependency_hierarchy": "observations are independent within a habitat",
        "permitted_reuse": "development rows re-read freely; the seal is never screened",
        "seal": {"holder": "the study itself", "mechanism": "run-one's seal accounting"},
        "acquisition": [],
    },
    "claim": {"warrant": "exploratory-structure", "supporting_evidence": ["P4"]},
    "decision": {"continuation": "continue", "predecessor": None, "successor": None},
}

ADAPTER = '''"""The discovery adapter: field measurements → the template contract."""

from __future__ import annotations

import csv
from pathlib import Path


def observations(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
'''

RUNNER = '''"""A discovery cell's entrypoint: adapter → template → pinned table → block."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True  # the study tree stays clean for the notary
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.generation import templates  # noqa: E402
from lib.habitat import observations  # noqa: E402

CELL, TEMPLATE = sys.argv[1], sys.argv[2]
ROWS = observations(Path("data/prepared/observations.csv"))
if TEMPLATE == "residual_by_segment":
    UNITS = templates.residual_by_segment(
        ROWS,
        segment_column="segment",
        observed_column="observed",
        expected_column="expected",
        unit_column="unit",
    )
    STATISTIC = "mean_signed_residual"
elif TEMPLATE == "error_slices":
    UNITS = templates.error_slices(
        ROWS, segment_column="segment", loss_column="loss", unit_column="unit"
    )
    STATISTIC = "mean_loss"
else:
    UNITS = templates.family_disagreement(
        ROWS,
        segment_column="segment",
        left_column="model_a",
        right_column="model_b",
        unit_column="unit",
    )
    STATISTIC = "distance"

if len(sys.argv) > 3 and sys.argv[3] == "drop-a-segment":
    UNITS = [row for row in UNITS if row["segment"] != "dry"]

TABLE = Path("tables") / f"{CELL}.tsv"
TABLE.parent.mkdir(parents=True, exist_ok=True)
TABLE.write_text(templates.render_table(UNITS), encoding="utf-8")

print("primary_metric:    0.5")
print("metric_name:       val_auc")
print("metric_goal:       higher")
print(f"artifact:          {TABLE.as_posix()}")
for KEY, VALUE in sorted(templates.printed_summary(UNITS, statistic=STATISTIC).items()):
    print(f"{KEY}: {VALUE}")
'''

#: Two habitats (`wet`, `dry`) that behave, one positive control (`burned`) and
#: one slice too sparse to answer — A3 §3's smallest exercise.
WET = [0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.0, 0.0]
DRY = [0.02, -0.02, 0.01, -0.01, 0.0, 0.0, 0.01, -0.01]
BURNED = [2.0, 2.1, 1.9, 2.05, 1.95, 2.0, 2.1, 1.9]
SPARSE = [0.5]

LOSS = {"wet": 1.0, "dry": 1.1, "burned": 5.0, "sparse": 1.0}
DISAGREEMENT = {"wet": 0.0, "dry": 0.0, "burned": 1.5, "sparse": 0.0}

CELL_A = "cell_residual_by_habitat"
CELL_B = "cell_loss_by_habitat"
CELL_C = "cell_family_disagreement"


# --------------------------------------------------------------------------
# the fixture study
# --------------------------------------------------------------------------


def _observations() -> str:
    lines = ["segment,unit,observed,expected,loss,model_a,model_b"]
    for segment, residuals in (("wet", WET), ("dry", DRY), ("burned", BURNED), ("sparse", SPARSE)):
        for index, residual in enumerate(residuals, start=1):
            wobble = 0.3 * ((index % 3) - 1)
            lines.append(
                ",".join(
                    (
                        segment,
                        f"{segment}-{index}",
                        f"{10.0 + residual:.6g}",
                        "10",
                        f"{LOSS[segment] + wobble:.6g}",
                        f"{DISAGREEMENT[segment] + wobble:.6g}",
                        f"{wobble:.6g}",
                    )
                )
            )
    return "\n".join(lines) + "\n"


def _cell(
    cell_id: str,
    *,
    template: str,
    statistic: str,
    rule: dict[str, Any],
    partition: str = "development",
    adapter: str = "lib/habitat.py",
    segments: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "cell_id": cell_id,
        "track": "primary",
        "expectation_P": "P4",
        "template": template,
        "statistic": statistic,
        "input_refs": [{"path": "data/prepared/observations.csv"}],
        "adapter": adapter,
        "partition": partition,
        "unit_policy": "one row per observation",
        "group_policy": None,
        "segments": {"column": "segment", "values": segments or ["wet", "dry", "burned", "sparse"]},
        "units": "millimetres",
        "floor_ref": "minimum_delta",
        "minimum_n": 2,
        "multiplicity_rule": rule,
        "output_columns": list(gt.TABLE_COLUMNS),
        "post_observation": False,
    }


def _registry(cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "type": "discovery-cells",
        "study": "03-demo",
        "adapters": [{"path": "lib/habitat.py"}],
        "cells": cells
        if cells is not None
        else [
            _cell(
                CELL_A,
                template="residual_by_segment",
                statistic="mean_signed_residual",
                rule={"method": "family_maxt", "n_perm": 1024, "seed": 0, "alpha": 0.05},
            ),
            _cell(
                CELL_B,
                template="error_slices",
                statistic="mean_loss",
                rule={"method": "bonferroni", "alpha": 0.05},
            ),
            _cell(
                CELL_C,
                template="family_disagreement",
                statistic="distance",
                rule={"method": "declared", "sweep": "null_disagreement", "threshold": 4.0},
            ),
        ],
    }


def _write_registry(study: Path, payload: dict[str, Any] | None = None) -> None:
    (study / gs.CELLS_NAME).write_text(
        yaml.safe_dump(payload if payload is not None else _registry(), sort_keys=False),
        encoding="utf-8",
    )


def _register_sweep(study: Path) -> None:
    """The null sweep a `declared` multiplicity rule cites, registered as state."""
    from kleinlib.cli_sweep import register_sweep
    from kleinlib.sweep import SIDECAR_COLUMNS

    sweeps = study / "sweeps"
    sweeps.mkdir(exist_ok=True)
    header = "\t".join(SIDECAR_COLUMNS)
    rows = [header]
    for index in range(3):
        row = dict.fromkeys(SIDECAR_COLUMNS, "")
        row["trial"] = str(index + 1)
        row["status"] = "ok"
        row["metric"] = "0.1"
        rows.append("\t".join(row[column] for column in SIDECAR_COLUMNS))
    (sweeps / "null_disagreement.sidecar.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (sweeps / "null_disagreement.py").write_text("# the null sweep\n", encoding="utf-8")
    register_sweep(
        study,
        "null_disagreement",
        sidecar=Path("sweeps/null_disagreement.sidecar.tsv"),
        script=Path("sweeps/null_disagreement.py"),
    )


@pytest.fixture
def registered_study(tmp_path: Path) -> tuple[Path, Path]:
    """Past all three gates, design locked, adapters committed, cells registered."""
    repo, study = _scaffold(tmp_path)
    path = study / "study.yaml"
    path.write_text(path.read_text(encoding="utf-8") + PREDICTIONS, encoding="utf-8")

    (study / "lib").mkdir(exist_ok=True)
    (study / "lib" / "habitat.py").write_text(ADAPTER, encoding="utf-8")
    (study / "cell_runner.py").write_text(RUNNER, encoding="utf-8")
    (study / "data" / "prepared" / "observations.csv").write_text(
        _observations(), encoding="utf-8"
    )
    (study / "evidence_design.yaml").write_text(yaml.safe_dump(DESIGN, sort_keys=True), "utf-8")
    commit_all(repo, "predictions, adapter, observations and the evidence design")

    assert _gen(
        "init", "--study", str(study), "--capability", "design", "--capability", "surprise"
    ) == 0
    record_gate(study, "consult", acknowledged_by="tester")
    commit_all(repo, "consult gate recorded")
    assert _gen("design", "lock", "--study", str(study)) == 0
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "data and method gates recorded")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")

    _register_sweep(study)
    _write_registry(study)
    assert _gen("surprise", "register", "--study", str(study), "--actor", "tester") == 0
    return repo, study


def _bump(study: Path, marker: str) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\nCANDIDATE = {marker!r}\n", "utf-8")


def _run_cell(
    study: Path, cell_id: str, template: str, *, extra: str | None = None, marker: str = "one"
) -> str:
    """Admit one cell, run it, and return the run id."""
    import sys

    _bump(study, marker)
    assert (
        _gen(
            "check",
            "--study",
            str(study),
            "--action",
            "cell",
            "--track",
            "primary",
            "--cell",
            cell_id,
            "--tests",
            "P4",
        )
        == 0
    )
    command = [sys.executable, str(study / "cell_runner.py"), cell_id, template]
    if extra:
        command.append(extra)
    manifest = run_one(study, command=command, tests=["P4"], echo=False)
    return str(manifest["experiment"])


def _events(study: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _record(study: Path, run: str) -> dict[str, Any]:
    for entry in gs.records(study, _events(study)):
        if entry["object"]["run"] == run:
            return entry["object"]
    raise AssertionError(f"no record for {run}")


def _verdicts(record: dict[str, Any]) -> dict[str, str]:
    return {row["segment"]: row["verdict"] for row in record["segments"]}


def _statuses(study: Path, name: str) -> list[str]:
    return [check["status"] for check in _receipt(study)["checks"] if check["name"] == name]


def _details(study: Path, name: str) -> str:
    return " ".join(
        check["detail"] for check in _receipt(study)["checks"] if check["name"] == name
    )


# --------------------------------------------------------------------------
# the templates, on tiny tables
# --------------------------------------------------------------------------


def test_residual_by_segment_subtracts_and_keeps_every_unit() -> None:
    rows = [
        {"habitat": "wet", "id": "a", "y": "3.0", "yhat": "2.5"},
        {"habitat": "dry", "id": "b", "y": "1.0", "yhat": "1.25"},
    ]
    units = gt.residual_by_segment(
        rows,
        segment_column="habitat",
        observed_column="y",
        expected_column="yhat",
        unit_column="id",
    )
    assert units == [
        {"segment": "wet", "unit": "a", "value": 0.5},
        {"segment": "dry", "unit": "b", "value": -0.25},
    ]


def test_error_slices_expectation_is_the_pooled_mean() -> None:
    units = gt.error_slices(
        [
            {"s": "a", "loss": "1.0"},
            {"s": "a", "loss": "3.0"},
            {"s": "b", "loss": "2.0"},
            {"s": "b", "loss": "2.0"},
        ],
        segment_column="s",
        loss_column="loss",
    )
    printed = gt.printed_summary(units, statistic="mean_loss")
    assert printed["cell_expected"] == 2.0
    assert printed["cell_deviation_a"] == 0.0
    assert printed["cell_deviation_b"] == 0.0


def test_family_disagreement_is_signed() -> None:
    units = gt.family_disagreement(
        [{"s": "a", "left": "1.0", "right": "3.0"}],
        segment_column="s",
        left_column="left",
        right_column="right",
    )
    assert units[0]["value"] == -2.0


def test_a_table_round_trips_and_a_non_finite_unit_is_refused() -> None:
    units = gt.residual_by_segment(
        [{"s": "wet meadow", "y": "1.5", "e": "1.0"}],
        segment_column="s",
        observed_column="y",
        expected_column="e",
    )
    assert gt.parse_table(gt.render_table(units)) == units
    with pytest.raises(ValueError, match="not finite"):
        gt.residual_by_segment(
            [{"s": "a", "y": "nan", "e": "1.0"}],
            segment_column="s",
            observed_column="y",
            expected_column="e",
        )


def test_printed_summary_keys_are_legal_printed_keys() -> None:
    """A segment name is the driver's vocabulary; a printed key is not."""
    units = gt.error_slices(
        [{"s": "38.5 °C / wet", "loss": "1.0"}, {"s": "38.5 °C / wet", "loss": "2.0"}],
        segment_column="s",
        loss_column="loss",
    )
    printed = gt.printed_summary(units, statistic="mean_loss")
    for key in printed:
        assert METRIC_LINE_RE.match(f"{key}: 0"), key


# --------------------------------------------------------------------------
# R-SUR-2 — the arithmetic: controls, sparse slices, and the declared family
# --------------------------------------------------------------------------


def _units(**segments: list[float]) -> list[dict[str, Any]]:
    return [
        {"segment": name, "unit": f"{name}-{index}", "value": value}
        for name, values in segments.items()
        for index, value in enumerate(values, start=1)
    ]


def _decide(units: list[dict[str, Any]], rule: dict[str, Any], inventory: list[str]) -> dict[str, str]:
    cell = _cell(
        CELL_A,
        template="residual_by_segment",
        statistic="mean_signed_residual",
        rule=rule,
        segments=inventory,
    )
    record = gs.build_record(run="E0001", cell=cell, units=units, table_sha256="0" * 64)
    return _verdicts(record)


def test_r_sur_2_max_t_flags_the_positive_control_and_spares_the_null_control() -> None:
    verdicts = _decide(
        _units(wet=WET, dry=DRY, burned=BURNED, sparse=SPARSE),
        {"method": "family_maxt", "n_perm": 1024, "seed": 0, "alpha": 0.05},
        ["wet", "dry", "burned", "sparse"],
    )
    assert verdicts == {
        "burned": "violation",
        "wet": "null",
        "dry": "null",
        "sparse": "inconclusive",
    }


def test_r_sur_2_a_sparse_slice_is_inconclusive_and_stays_in_the_family() -> None:
    """`minimum_n` first: a slice that could not answer is never reported as null."""
    cell = _cell(
        CELL_A,
        template="residual_by_segment",
        statistic="mean_signed_residual",
        rule={"method": "family_maxt", "n_perm": 1024, "seed": 0},
    )
    record = gs.build_record(
        run="E0001",
        cell=cell,
        units=_units(wet=WET, dry=DRY, burned=BURNED, sparse=SPARSE),
        table_sha256="0" * 64,
    )
    assert record["family_size"] == 4
    sparse = [row for row in record["segments"] if row["segment"] == "sparse"][0]
    assert (sparse["n"], sparse["verdict"]) == (1, "inconclusive")
    assert sparse["t"] is None


def test_r_sur_2_bonferroni_scales_by_the_frozen_family_size() -> None:
    """The denominator is the registered inventory, not the segments that fired."""
    units = _units(wet=WET, burned=BURNED)
    small = gs.build_record(
        run="E0001",
        cell=_cell(
            CELL_A,
            template="residual_by_segment",
            statistic="mean_signed_residual",
            rule={"method": "bonferroni", "alpha": 0.05},
            segments=["wet", "burned"],
        ),
        units=units,
        table_sha256="0" * 64,
    )
    wide = gs.build_record(
        run="E0001",
        cell=_cell(
            CELL_A,
            template="residual_by_segment",
            statistic="mean_signed_residual",
            rule={"method": "bonferroni", "alpha": 0.05},
            segments=["wet", "burned", "a", "b", "c", "d"],
        ),
        units=units,
        table_sha256="0" * 64,
    )
    burned_small = [r for r in small["segments"] if r["segment"] == "burned"][0]
    burned_wide = [r for r in wide["segments"] if r["segment"] == "burned"][0]
    assert burned_wide["adjusted_p"] == pytest.approx(3 * burned_small["adjusted_p"])
    assert (small["family_size"], wide["family_size"]) == (2, 6)


def test_r_sur_2_a_declared_rule_compares_against_the_registered_threshold() -> None:
    units = _units(wet=WET, burned=BURNED)
    inventory = ["wet", "burned"]
    strict = _decide(
        units, {"method": "declared", "sweep": "null", "threshold": 4.0}, inventory
    )
    lax = _decide(
        units, {"method": "declared", "sweep": "null", "threshold": 1000.0}, inventory
    )
    assert strict["burned"] == "violation" and strict["wet"] == "null"
    assert lax["burned"] == "null"


def test_the_family_is_recomputed_bit_for_bit_from_the_same_table() -> None:
    """R-SUR-4's precondition: the record is a pure function of the pinned bytes."""
    units = _units(wet=WET, dry=DRY, burned=BURNED, sparse=SPARSE)
    cell = _cell(
        CELL_A,
        template="residual_by_segment",
        statistic="mean_signed_residual",
        rule={"method": "family_maxt", "n_perm": 1024, "seed": 0},
    )
    first = gs.build_record(run="E0001", cell=cell, units=units, table_sha256="0" * 64)
    again = gs.build_record(
        run="E0001", cell=cell, units=gt.parse_table(gt.render_table(units)), table_sha256="0" * 64
    )
    assert first == again


# --------------------------------------------------------------------------
# R-SUR-1 — registration refusals
# --------------------------------------------------------------------------


def _refused_registry(study: Path, payload: dict[str, Any]) -> int:
    _write_registry(study, payload)
    return _gen("surprise", "register", "--study", str(study))


def test_r_sur_2_a_cell_without_a_multiplicity_rule_is_refused(tmp_path: Path) -> None:
    """RF-13: a screening family without a declared correction is not registrable."""
    _repo, study = _unregistered(tmp_path)
    payload = _registry()
    del payload["cells"][0]["multiplicity_rule"]
    assert _refused_registry(study, payload) == 2
    assert gs.registrations(study, _events(study)) == []


def test_r_sur_2_a_measured_floor_is_not_a_multiplicity_rule(tmp_path: Path) -> None:
    _repo, study = _unregistered(tmp_path)
    payload = _registry()
    payload["cells"][0]["multiplicity_rule"] = {"method": "minimum_delta"}
    assert _refused_registry(study, payload) == 2


def test_r_sur_1_an_adapter_inside_the_mutable_surface_is_refused(tmp_path: Path) -> None:
    _repo, study = _unregistered(tmp_path)
    payload = _registry()
    payload["adapters"] = [{"path": "train.py"}]
    for cell in payload["cells"]:
        cell["adapter"] = "train.py"
    assert _refused_registry(study, payload) == 2


def test_r_sur_1_a_cell_on_the_sealed_partition_is_refused(tmp_path: Path) -> None:
    _repo, study = _unregistered(tmp_path)
    payload = _registry()
    payload["cells"][0]["partition"] = "sealed"
    assert _refused_registry(study, payload) == 2


def test_a_cell_whose_expectation_is_unregistered_is_refused(tmp_path: Path) -> None:
    _repo, study = _unregistered(tmp_path)
    payload = _registry()
    payload["cells"][0]["expectation_P"] = "P9"
    assert _refused_registry(study, payload) == 2


def test_a_template_and_statistic_that_disagree_are_refused(tmp_path: Path) -> None:
    _repo, study = _unregistered(tmp_path)
    payload = _registry()
    payload["cells"][0]["statistic"] = "mean_loss"
    assert _refused_registry(study, payload) == 2


def test_a_study_that_did_not_declare_surprise_cannot_register(tmp_path: Path) -> None:
    _repo, study = _unregistered(tmp_path, capabilities=("design",))
    _write_registry(study)
    assert _gen("surprise", "register", "--study", str(study)) == 1


def _unregistered(
    tmp_path: Path, capabilities: tuple[str, ...] = ("design", "surprise")
) -> tuple[Path, Path]:
    """Everything the registered fixture does, stopping before `surprise register`."""
    repo, study = _scaffold(tmp_path)
    path = study / "study.yaml"
    path.write_text(path.read_text(encoding="utf-8") + PREDICTIONS, encoding="utf-8")
    (study / "lib").mkdir(exist_ok=True)
    (study / "lib" / "habitat.py").write_text(ADAPTER, encoding="utf-8")
    (study / "cell_runner.py").write_text(RUNNER, encoding="utf-8")
    (study / "data" / "prepared" / "observations.csv").write_text(_observations(), "utf-8")
    (study / "evidence_design.yaml").write_text(yaml.safe_dump(DESIGN, sort_keys=True), "utf-8")
    commit_all(repo, "predictions, adapter, observations and the evidence design")

    argv = ["init", "--study", str(study)]
    for name in capabilities:
        argv += ["--capability", name]
    assert _gen(*argv) == 0
    record_gate(study, "consult", acknowledged_by="tester")
    commit_all(repo, "consult gate recorded")
    if "design" in capabilities:
        assert _gen("design", "lock", "--study", str(study)) == 0
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "data and method gates recorded")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    _register_sweep(study)
    return repo, study


# --------------------------------------------------------------------------
# R-SUR-1/3/4 — the valid control, end to end
# --------------------------------------------------------------------------


def test_r_sur_1_valid_control_three_templates_two_habitats_and_a_clean_receipt(
    registered_study,
) -> None:
    """The whole loop: register → admit → run → record → verify, on all three templates."""
    repo, study = registered_study
    runs = {
        CELL_A: _run_cell(study, CELL_A, "residual_by_segment", marker="a"),
        CELL_B: _run_cell(study, CELL_B, "error_slices", marker="b"),
        CELL_C: _run_cell(study, CELL_C, "family_disagreement", marker="c"),
    }
    for run in runs.values():
        assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0

    # the residual cell: the positive control fires, the null controls do not,
    # and the slice that could not answer says so
    assert _verdicts(_record(study, runs[CELL_A])) == {
        "burned": "violation",
        "wet": "null",
        "dry": "null",
        "sparse": "inconclusive",
    }
    # every template retains the COMPLETE inventory, however it decided
    for run in runs.values():
        record = _record(study, run)
        assert record["family_size"] == 4
        assert len(record["segments"]) == 4
        assert record["missing_segments"] == [] and record["outcome"] == "complete"
    assert _verdicts(_record(study, runs[CELL_C]))["burned"] == "violation"

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert receipt["summary"]["failed"] == 0
    capability = receipt["capabilities"]["surprise"]
    assert capability["integrity"] == "PASS"
    assert (capability["outcome"], capability["cells"], capability["runs"]) == ("registered", 3, 3)
    assert capability["violations"] == capability["unresolved"] >= 3
    for name in ("surprise cells", "surprise records", "surprise receipts", "surprise claims"):
        assert _statuses(study, name) == ["PASS"], name

    # a second verify at the same HEAD is byte-identical (the spine's determinism)
    before = (study / "generation" / "verify_receipt.json").read_bytes()
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("verify", "--study", str(study)) == 0
    assert (study / "generation" / "verify_receipt.json").read_bytes() == before
    assert git(repo, "rev-parse", "HEAD") == head


def test_r_sur_3_receipts_are_fully_qualified_pinned_and_unresolved(registered_study) -> None:
    """RF-02 and A2: an S id is never bare, and an unexplained anomaly stays unexplained."""
    _repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0

    issued = [entry["object"] for entry in gs.receipts(study, _events(study))]
    assert [obj["id"] for obj in issued] == ["03-demo#S1"]
    receipt = issued[0]
    assert receipt["segment"] == "burned"
    assert receipt["explanation"] == "unresolved"
    assert receipt["label"] == "preregistered"
    assert receipt["table_sha256"] == _record(study, run)["table_sha256"]
    assert receipt["family_size"] == 4
    assert receipt["exposure"][0] == "development"


def test_r_sur_3_an_explanation_is_testimony_the_driver_typed(registered_study) -> None:
    _repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert (
        _gen(
            "surprise",
            "record",
            "--study",
            str(study),
            "--run",
            run,
            "--explain",
            "burned=the 2019 fire removed the canopy",
        )
        == 0
    )
    issued = [entry["object"] for entry in gs.receipts(study, _events(study))]
    assert issued[0]["explanation"] == "the 2019 fire removed the canopy"
    assert _gen("verify", "--study", str(study)) == 0
    assert _receipt(study)["capabilities"]["surprise"]["unresolved"] == 0


def test_the_record_commit_touches_only_generation_paths(registered_study) -> None:
    """Write ownership: the capability writes under generation/ and nowhere else."""
    repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0
    for path in git(repo, "show", "--name-only", "--format=", "HEAD").split():
        assert "/generation/" in path, path


def test_the_registration_commit_files_the_registry_and_the_ledger(tmp_path: Path) -> None:
    repo, study = _unregistered(tmp_path)
    _write_registry(study)
    assert _gen("surprise", "register", "--study", str(study)) == 0
    for path in git(repo, "show", "--name-only", "--format=", "HEAD").split():
        assert path.endswith(gs.CELLS_NAME) or "/generation/" in path, path
    # the registration pinned the hashes the author did not have to compute
    document = yaml.safe_load((study / gs.CELLS_NAME).read_text(encoding="utf-8"))
    assert len(document["adapters"][0]["sha256"]) == 64
    assert len(document["cells"][0]["input_refs"][0]["sha256"]) == 64


# --------------------------------------------------------------------------
# admission
# --------------------------------------------------------------------------


def test_an_unregistered_cell_is_refused_at_admission(registered_study) -> None:
    _repo, study = registered_study
    _bump(study, "x")
    assert (
        _gen(
            "check", "--study", str(study), "--action", "cell", "--track", "primary",
            "--cell", "cell_invented_after_the_fact", "--tests", "P4",
        )
        == 2
    )


def test_an_admission_whose_tests_omit_the_expectation_is_refused(registered_study) -> None:
    """Without the notary, the cell's expectation would be decided by prose afterwards."""
    _repo, study = registered_study
    _bump(study, "x")
    assert (
        _gen(
            "check", "--study", str(study), "--action", "cell", "--track", "primary",
            "--cell", CELL_A,
        )
        == 2
    )


def test_an_admission_after_the_adapter_changed_is_refused(registered_study) -> None:
    """R-INV-3: the adapter is frozen at registration, and the hash is the freeze."""
    repo, study = registered_study
    (study / "lib" / "habitat.py").write_text(ADAPTER + "\n# a late edit\n", encoding="utf-8")
    commit_all(repo, "edit the adapter after registration")
    _bump(study, "x")
    assert (
        _gen(
            "check", "--study", str(study), "--action", "cell", "--track", "primary",
            "--cell", CELL_A, "--tests", "P4",
        )
        == 2
    )
    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "surprise cells") == ["FAIL"]


def test_the_receipt_pins_the_cells_registration_and_the_locked_design(registered_study) -> None:
    """`inputs.cells` and `inputs.design` say WHICH commitments the action was taken under."""
    _repo, study = registered_study
    _bump(study, "x")
    assert (
        _gen(
            "check", "--study", str(study), "--action", "cell", "--track", "primary",
            "--cell", CELL_A, "--tests", "P4",
        )
        == 0
    )
    from kleinlib.generation.ledger import read_object

    events = _events(study)
    admission = [e for e in events if e["type"] == "admission_checked"][-1]
    inputs = read_object(study, admission["payload_sha256"])["inputs"]
    registration = gs.registrations(study, events)[-1]
    locks = [e for e in events if e["type"] == "design_locked"]
    assert inputs["cells"] == registration["sha"]
    assert inputs["design"] == locks[0]["payload_sha256"]


# --------------------------------------------------------------------------
# R-SUR-2/4 — the failure modes verify exists to catch
# --------------------------------------------------------------------------


def test_r_sur_2_an_omitted_eligible_segment_fails(registered_study) -> None:
    """The complete inventory IS the denominator; a dropped slice is not a rounding."""
    _repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment", extra="drop-a-segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 2

    record = _record(study, run)
    assert record["missing_segments"] == ["dry"]
    assert record["outcome"] == "defective"
    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "surprise records") == ["FAIL"]
    assert "missing" in _details(study, "surprise records")


def test_a_cell_that_ran_and_was_never_recorded_fails(registered_study) -> None:
    _repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "surprise records") == ["FAIL"]
    assert f"{run} ran cell {CELL_A}" in _details(study, "surprise records")


def test_an_edited_registry_fails_verification(registered_study) -> None:
    """A registered search space is not edited in place."""
    repo, study = registered_study
    path = study / gs.CELLS_NAME
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["cells"][0]["segments"]["values"] = ["wet", "burned"]
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    commit_all(repo, "quietly drop two segments")

    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "surprise cells") == ["FAIL"]
    assert "not edited in place" in _details(study, "surprise cells")


def test_an_edited_table_fails_verification(registered_study) -> None:
    """The record hashed the table; verify re-reads the bytes, not the summary."""
    repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0
    table = study / gs.table_relpath(CELL_A)
    table.write_text(table.read_text(encoding="utf-8").replace("burned-1\t2", "burned-1\t9"), "utf-8")
    commit_all(repo, "improve a residual")

    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "surprise records") == ["FAIL"]


def test_r_sur_4_a_confirmed_claim_citing_the_cell_table_fails(registered_study) -> None:
    """R-INV-6: a screen selects what to look at; it cannot also confirm it."""
    repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0
    lock = {
        "lock_schema": 2,
        "study_id": "03-demo",
        "artifacts": {
            "surprise_table": {"path": gs.table_relpath(CELL_A), "sha256": "0" * 64}
        },
        "claims": {
            "C1": {
                "claim": "burned plots are biased high",
                "class": "empirical-description",
                "strength": "confirmed",
                "evidence": ["art:surprise_table", run],
                "numbers": [],
            }
        },
        "numbers": {},
        "errata": [],
    }
    (study / "claims.lock").write_text(json.dumps(lock, indent=1), encoding="utf-8")
    commit_all(repo, "a claims lock that confirms a screen")

    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "surprise claims") == ["FAIL"]
    assert "cannot also confirm" in _details(study, "surprise claims")

    # the same claim, exploratory, is exactly what a discovery study may say
    lock["claims"]["C1"]["strength"] = "exploratory"
    (study / "claims.lock").write_text(json.dumps(lock, indent=1), encoding="utf-8")
    commit_all(repo, "downgrade the claim to exploratory")
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(study, "surprise claims") == ["PASS"]


def test_rf_02_a_bare_s_id_in_findings_warns(registered_study) -> None:
    """A bare `S3` is a scouting entry; the numbers scan already exempts it as one."""
    repo, study = registered_study
    (study / "findings.md").write_text(
        "# Findings\n\n## ③ Surprises and why\n\nS3 was the burned plot.\n", encoding="utf-8"
    )
    commit_all(repo, "findings with a bare S id")

    assert _gen("verify", "--study", str(study)) in (0, 2)
    assert "WARN" in _statuses(study, "surprise findings")
    assert "S3" in _details(study, "surprise findings")

    (study / "findings.md").write_text(
        "# Findings\n\n## ③ Surprises and why\n\n03-demo#S3 was the burned plot.\n", "utf-8"
    )
    commit_all(repo, "qualify the id")
    _gen("verify", "--study", str(study))
    assert _statuses(study, "surprise findings") == ["PASS"]


def test_a_cell_added_after_evidence_is_forced_post_observation(registered_study) -> None:
    """Adaptive slices are lawful and labelled; they never acquire preregistration."""
    _repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0

    document = yaml.safe_load((study / gs.CELLS_NAME).read_text(encoding="utf-8"))
    document["cells"].append(
        _cell(
            "cell_added_after_looking",
            template="residual_by_segment",
            statistic="mean_signed_residual",
            rule={"method": "family_maxt", "n_perm": 1024, "seed": 0},
        )
    )
    _write_registry(study, document)
    assert _gen("surprise", "register", "--study", str(study)) == 0

    registered = gs.registered_cells(study, _events(study))
    assert registered["cell_added_after_looking"]["post_observation"] is True
    assert registered[CELL_A]["post_observation"] is False
    assert _gen("verify", "--study", str(study)) == 0


def test_a_registered_cell_cannot_be_restated(registered_study) -> None:
    _repo, study = registered_study
    document = yaml.safe_load((study / gs.CELLS_NAME).read_text(encoding="utf-8"))
    document["cells"][0]["minimum_n"] = 5
    _write_registry(study, document)
    assert _gen("surprise", "register", "--study", str(study)) == 2
    assert len(gs.registrations(study, _events(study))) == 1


def test_recording_a_run_that_was_never_admitted_as_a_cell_is_refused(registered_study) -> None:
    """The record rests on an admitted cell, never on a run that merely wrote a table."""
    import sys

    _repo, study = registered_study
    _bump(study, "unadmitted")
    manifest = run_one(
        study,
        command=[sys.executable, str(study / "cell_runner.py"), CELL_A, "residual_by_segment"],
        tests=["P4"],
        echo=False,
    )
    assert (
        _gen("surprise", "record", "--study", str(study), "--run", str(manifest["experiment"]))
        == 1
    )


def test_the_capability_is_registered_in_both_registries() -> None:
    from kleinlib.generation import capabilities
    from kleinlib.generation.manifest import CAPABILITY_DEPENDENCIES, SUPPORTED_CAPABILITIES

    assert "surprise" in SUPPORTED_CAPABILITIES
    assert capabilities.load()["surprise"] is gs.CAPABILITY
    assert CAPABILITY_DEPENDENCIES["surprise"] == ("design",)


def test_surprise_without_design_is_refused_at_init(tmp_path: Path) -> None:
    """`surprise ⇒ design`: a cell measures something, and the design says what."""
    _repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "surprise") == 1
    assert not (study / "generation" / "manifest.yaml").is_file()


def test_the_module_proposes_nothing() -> None:
    """R-SLA-6's neighbour: the capability records and computes; it never selects."""
    source = (Path(__file__).resolve().parents[1] / "generation" / "surprise.py").read_text("utf-8")
    for word in ("random.", "rank(", "propose", "suggest", "recommend"):
        assert word not in source, word


def test_infinite_t_survives_the_ledger_round_trip() -> None:
    """A zero-spread segment is extreme, not missing — and the record says so."""
    units = _units(flat=[2.0, 2.0, 2.0], wide=WET)
    record = gs.build_record(
        run="E0001",
        cell=_cell(
            CELL_A,
            template="residual_by_segment",
            statistic="mean_signed_residual",
            rule={"method": "bonferroni", "alpha": 0.05},
            segments=["flat", "wide"],
        ),
        units=units,
        table_sha256="0" * 64,
    )
    flat = [row for row in record["segments"] if row["segment"] == "flat"][0]
    assert math.isinf(flat["t"]) and flat["adjusted_p"] == 0.0
    assert json.loads(json.dumps(record))["segments"][0]["t"] == flat["t"]


def test_the_summary_table_is_derived_and_deterministic(registered_study) -> None:
    _repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0
    path = gs.summary_table_path(study, CELL_A)
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "\t".join(gs.SUMMARY_COLUMNS)
    assert text == gs.summary_table_text(_record(study, run))
    assert len(text.splitlines()) == 5  # the header and every frozen segment


def test_show_reads_and_writes_nothing(registered_study) -> None:
    repo, study = registered_study
    run = _run_cell(study, CELL_A, "residual_by_segment")
    assert _gen("surprise", "record", "--study", str(study), "--run", run) == 0
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("surprise", "show", "--study", str(study)) == 0
    assert git(repo, "rev-parse", "HEAD") == head
