"""The ``design`` capability (WP-09): say what the evidence is FOR, first.

Test names carry their requirement id (R-DES-1, R-DES-2).  The spine's fixtures
are reused verbatim — a generation-enabled study with one extra capability
declared — so what these tests exercise is the REGISTRATION path plus the two
requirements the artifact exists for:

R-DES-1  ``evidence_design.yaml`` is validated and locked BEFORE the DATA gate,
         and an acquisition claim costs a custody chain and an attestor.
R-DES-2  every validity condition names a registered prediction whose rule can
         actually fire it — an ``inconclusive_if`` rule or a combinator, never a
         plain leaf comparison and never prose.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_generation_spine import _gen, _receipt, _scaffold
from test_workflow_v3 import commit_all, git

from kleinlib.generation import capabilities
from kleinlib.generation import design as gd
from kleinlib.generation import manifest as gm
from kleinlib.workflow import record_gate

PREDICTIONS = """
predictions:
  - id: P1
    track: primary
    statement: "the candidate beats the incumbent on the printed metric"
    rule: {key: primary_metric, op: ">=", value: 0.0}
    inconclusive_if: {key: primary_metric, op: "abs_lt", value: 0.001}
  - id: P2
    track: primary
    statement: "the candidate finishes inside the per-run budget"
    rule: {key: wall_seconds, op: "<", value: 5.0}
  - id: P3
    track: primary
    statement: "the candidate wins and finishes inside the budget"
    rule:
      all_of:
        - {key: primary_metric, op: ">=", value: 0.0}
        - {key: wall_seconds, op: "<", value: 5.0}
"""


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _register_predictions(repo: Path, study: Path) -> None:
    """P1 carries an executable `inconclusive_if`; P2 is a plain leaf; P3 an all_of."""
    path = study / "study.yaml"
    path.write_text(path.read_text(encoding="utf-8") + PREDICTIONS, encoding="utf-8")
    commit_all(repo, "predictions registered")


def _document(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = copy.deepcopy(
        {
            "type": "evidence-design",
            "study": "03-demo",
            "question": {
                "estimand": "the discriminative power of the candidate signal",
                "population": "the rows of the fixture table",
                "units": "row",
                "measurement_process": "the evaluator prints primary_metric per run",
                "identification_assumptions": [
                    "the development rows and the sealed rows come from one population"
                ],
                "intended_generalization": "this fixture only; nothing travels off it",
            },
            "prediction": {
                "uncertainty_method": "the measured noise floor at the row level",
                "validity_conditions": [
                    {
                        "condition": "the run printed a metric indistinguishable from zero",
                        "rule_ref": "P1",
                    }
                ],
                "practical_threshold": "0.05 on the printed metric would change the choice",
                "provenance": "the incumbent recipe's published number",
            },
            "evidence": {
                "representations": ["data/prepared/fixture.csv", "the split index"],
                "dependency_hierarchy": "rows are independent; there is no nesting",
                "permitted_reuse": "development rows re-read freely; the seal spent once",
                "seal": {"holder": "the study itself", "mechanism": "run-one's seal accounting"},
                "acquisition": [],
            },
            "claim": {"warrant": "prediction", "supporting_evidence": ["P1"]},
            "decision": {"continuation": "continue", "predecessor": None, "successor": None},
        }
    )
    doc.update(copy.deepcopy(overrides))
    return doc


def _write_design(repo: Path, study: Path, doc: dict[str, Any] | None = None) -> None:
    (study / gd.DESIGN_NAME).write_text(
        yaml.safe_dump(doc if doc is not None else _document(), sort_keys=True),
        encoding="utf-8",
    )
    commit_all(repo, "evidence design drafted")


def _consult(repo: Path, study: Path) -> None:
    record_gate(study, "consult", acknowledged_by="tester")
    commit_all(repo, "consult gate recorded")


def _remaining_gates(repo: Path, study: Path) -> None:
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "data and method gates recorded")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")


@pytest.fixture
def declared_study(tmp_path: Path) -> tuple[Path, Path]:
    """A study that declared `design`, past CONSULT, with the DATA gate still open."""
    repo, study = _scaffold(tmp_path)
    _register_predictions(repo, study)
    assert _gen("init", "--study", str(study), "--capability", "design") == 0
    _consult(repo, study)
    return repo, study


@pytest.fixture
def locked_study(declared_study) -> tuple[Path, Path]:
    """The happy path: a design locked before the DATA gate, then the gates."""
    repo, study = declared_study
    _write_design(repo, study)
    assert _gen("design", "lock", "--study", str(study), "--actor", "tester") == 0
    _remaining_gates(repo, study)
    return repo, study


def _events(study: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _locks(study: Path) -> list[tuple[Any, dict[str, Any]]]:
    return gd.locks(study, _events(study))


def _lock_object(study: Path) -> dict[str, Any]:
    return _locks(study)[-1][1]


def _statuses(study: Path, name: str) -> list[str]:
    return [check["status"] for check in _receipt(study)["checks"] if check["name"] == name]


def _details(study: Path, name: str) -> str:
    return " ".join(
        check["detail"] for check in _receipt(study)["checks"] if check["name"] == name
    )


# --------------------------------------------------------------------------
# R-DES-1 — the valid control, and the anchor order
# --------------------------------------------------------------------------


def test_r_des_1_valid_control_a_design_locked_before_the_data_gate(locked_study) -> None:
    """R-DES-1: lock before the DATA gate → every design check PASSes, outcome `locked`."""
    _repo, study = locked_study

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert receipt["capabilities"]["design"] == {
        "integrity": "PASS",
        "outcome": "locked",
        "validity_conditions": 1,
    }
    for name in ("design lock", "design document", "design acquisition", "design conditions"):
        assert _statuses(study, name) == ["PASS"], name
    assert receipt["summary"]["failed"] == 0

    # the lock carries the document VERBATIM, so verify re-validates rather than
    # trusting a recorded verdict
    locked = _lock_object(study)
    assert locked["document"]["question"]["estimand"] == _document()["question"]["estimand"]
    assert locked["late"] is False


def test_r_des_1_the_lock_commit_touches_only_the_design_and_the_ledger(declared_study) -> None:
    """Write ownership: the design is a study-root artifact; nothing else moves."""
    repo, study = declared_study
    _write_design(repo, study)
    assert _gen("design", "lock", "--study", str(study)) == 0
    touched = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert touched, "the lock filed no commit"
    for path in touched:
        assert path.endswith(gd.DESIGN_NAME) or "/generation/" in path, path


def test_r_des_1_a_lock_after_the_data_gate_is_refused(declared_study) -> None:
    """R-DES-1 invalid control: once DATA is recorded the design describes, not commits."""
    repo, study = declared_study
    _write_design(repo, study)
    _remaining_gates(repo, study)

    assert _gen("design", "lock", "--study", str(study)) == 2
    assert _locks(study) == []
    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "design lock") == ["FAIL"]
    assert "is not locked" in _details(study, "design lock")


def test_r_des_1_allow_late_records_the_lock_and_fails_forever(declared_study) -> None:
    """`--allow-late` is lawful and permanently labelled — the same shape as the spine's."""
    repo, study = declared_study
    _write_design(repo, study)
    _remaining_gates(repo, study)

    assert _gen("design", "lock", "--study", str(study), "--allow-late") == 0
    assert _lock_object(study)["late"] is True
    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "design lock") == ["FAIL"]
    assert "--allow-late" in _details(study, "design lock")
    assert _receipt(study)["capabilities"]["design"]["integrity"] == "FAIL"
    # the outcome still says what the record HOLDS; integrity says whether to trust it
    assert _receipt(study)["capabilities"]["design"]["outcome"] == "locked"


def test_r_des_1_a_declared_but_unlocked_design_is_a_fail(declared_study) -> None:
    """Declaring the capability is a promise; `unlocked` is how the receipt says it is open."""
    _repo, study = declared_study
    assert _gen("verify", "--study", str(study)) == 2
    assert _receipt(study)["capabilities"]["design"] == {
        "integrity": "FAIL",
        "outcome": "unlocked",
        "validity_conditions": 0,
    }


def test_r_des_1_an_edited_design_fails_verification(locked_study) -> None:
    """The lock is the bytes, not the intent: an in-place edit is detected."""
    repo, study = locked_study
    path = study / gd.DESIGN_NAME
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["question"]["intended_generalization"] = "every insurer in Europe"
    path.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    commit_all(repo, "widen the generalization after the fact")

    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "design lock") == ["FAIL"]
    assert "does not match the lock" in _details(study, "design lock")


def test_r_des_1_a_second_lock_is_refused(locked_study) -> None:
    """One design, one lock: a change of estimand is a successor study."""
    _repo, study = locked_study
    assert _gen("design", "lock", "--study", str(study)) == 1


def test_a_study_that_did_not_declare_design_cannot_lock(tmp_path: Path) -> None:
    """The opt-in is immutable, so the fix is a manifest, not a flag."""
    repo, study = _scaffold(tmp_path)
    _register_predictions(repo, study)
    assert _gen("init", "--study", str(study)) == 0
    _consult(repo, study)
    _write_design(repo, study)
    assert _gen("design", "lock", "--study", str(study)) == 1


# --------------------------------------------------------------------------
# R-DES-1 — acquisition custody (import chronology ≠ acquisition chronology)
# --------------------------------------------------------------------------


def _with_acquisition(**entry: Any) -> dict[str, Any]:
    doc = _document()
    doc["evidence"]["acquisition"] = [entry]
    return doc


def test_r_des_1_an_acquisition_without_custody_is_refused(declared_study) -> None:
    """A claim about when a measurement was TAKEN costs a chain and an attestor."""
    repo, study = declared_study
    _write_design(
        repo,
        study,
        _with_acquisition(
            source="the vendor extract",
            kind="acquisition",
            acquired_at="2026-08-01",
            attested_by="the data steward",
        ),
    )
    assert _gen("design", "lock", "--study", str(study)) == 2

    _write_design(
        repo,
        study,
        _with_acquisition(
            source="the vendor extract",
            kind="acquisition",
            acquired_at="2026-08-01",
            custody="held by the vendor, then by the study",
        ),
    )
    assert _gen("design", "lock", "--study", str(study)) == 2


def test_r_des_1_an_import_needs_no_custody_and_an_acquisition_with_one_locks(
    declared_study,
) -> None:
    """An import records arrival; only an acquisition claims the measurement's date."""
    repo, study = declared_study
    _write_design(
        repo,
        study,
        _with_acquisition(
            source="a colleague's table", kind="import", acquired_at="2026-09-01"
        ),
    )
    assert _gen("design", "lock", "--study", str(study)) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(study, "design acquisition") == ["PASS"]
    assert "1 attested acquisition" not in _details(study, "design acquisition")


def test_r_des_1_an_attested_acquisition_is_reported_as_attested(declared_study) -> None:
    repo, study = declared_study
    _write_design(
        repo,
        study,
        _with_acquisition(
            source="the wet-lab run",
            kind="acquisition",
            acquired_at="2026-08-01",
            custody="held by the lab, couriered to the study",
            attested_by="the principal investigator",
        ),
    )
    assert _gen("design", "lock", "--study", str(study)) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert "1 attested acquisition" in _details(study, "design acquisition")


def test_an_unknown_acquisition_kind_is_refused(declared_study) -> None:
    repo, study = declared_study
    _write_design(
        repo,
        study,
        _with_acquisition(source="somewhere", kind="borrowed", acquired_at="2026-08-01"),
    )
    assert _gen("design", "lock", "--study", str(study)) == 2


# --------------------------------------------------------------------------
# R-DES-2 — a validity condition is executable, or it is decoration
# --------------------------------------------------------------------------


def _with_ref(ref: str) -> dict[str, Any]:
    doc = _document()
    doc["prediction"]["validity_conditions"] = [
        {"condition": "the run could not answer the question", "rule_ref": ref}
    ]
    return doc


def test_r_des_2_a_rule_ref_to_a_plain_leaf_rule_is_refused(declared_study) -> None:
    """R-DES-2 invalid control: a leaf comparison encodes no validity condition."""
    repo, study = declared_study
    _write_design(repo, study, _with_ref("P2"))
    assert _gen("design", "lock", "--study", str(study)) == 2
    assert _locks(study) == []


def test_r_des_2_a_rule_ref_to_an_unregistered_prediction_is_refused(declared_study) -> None:
    repo, study = declared_study
    _write_design(repo, study, _with_ref("P9"))
    assert _gen("design", "lock", "--study", str(study)) == 2


def test_r_des_2_a_combinator_rule_satisfies_the_condition(declared_study) -> None:
    """R-DES-2 valid control (second shape): an all_of rule carries its own conjuncts."""
    repo, study = declared_study
    _write_design(repo, study, _with_ref("P3"))
    assert _gen("design", "lock", "--study", str(study)) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(study, "design conditions") == ["PASS"]


def test_r_des_2_a_prose_inconclusive_if_is_not_executable() -> None:
    """The unit of the rule, so the reason is legible without a fixture."""
    assert gd.encodes_a_condition({"inconclusive_if": {"key": "m", "op": "lt", "value": 1}})
    assert gd.encodes_a_condition({"rule": {"any_of": [{"key": "m", "op": "lt", "value": 1}]}})
    assert not gd.encodes_a_condition(
        {"rule": {"key": "m", "op": "lt", "value": 1}, "inconclusive_if": "the run crashes"}
    )
    assert not gd.encodes_a_condition({"manual": True})


def test_r_des_2_dropping_the_inconclusive_if_afterwards_fails_verification(
    locked_study,
) -> None:
    """The design is frozen; study.yaml is not. Drift in the CONTRACT is caught."""
    repo, study = locked_study
    path = study / "study.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '    inconclusive_if: {key: primary_metric, op: "abs_lt", value: 0.001}\n', ""
        ),
        encoding="utf-8",
    )
    commit_all(repo, "drop P1's inconclusive_if")

    assert _gen("verify", "--study", str(study)) == 2
    assert _statuses(study, "design conditions") == ["FAIL"]
    assert "cannot express a validity condition" in _details(study, "design conditions")


# --------------------------------------------------------------------------
# admission: a cell measures something, and the design says what
# --------------------------------------------------------------------------


def test_a_cell_admission_is_refused_until_the_design_is_locked(declared_study) -> None:
    repo, study = declared_study
    _remaining_gates(repo, study)
    assert _gen("check", "--study", str(study), "--action", "cell", "--track", "primary") == 2

    sha = _events(study)[-1]["payload_sha256"]
    receipt = json.loads(
        (study / "generation" / "objects" / f"{sha}.json").read_text(encoding="utf-8")
    )
    assert receipt["verdict"] == "refused"
    assert any("evidence design is not locked" in reason for reason in receipt["reasons"])


def test_a_cell_admission_is_granted_once_the_design_is_locked(locked_study) -> None:
    _repo, study = locked_study
    assert _gen("check", "--study", str(study), "--action", "cell", "--track", "primary") == 0


def test_an_ordinary_run_admission_is_unaffected_by_the_design(declared_study) -> None:
    """The rule is scoped to cells: WP-09 blocks nothing else."""
    repo, study = declared_study
    _remaining_gates(repo, study)
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0


# --------------------------------------------------------------------------
# registration
# --------------------------------------------------------------------------


def test_design_is_registered_in_both_lists() -> None:
    """The two registries have to agree; forgetting one is a defect in this package."""
    assert "design" in gm.SUPPORTED_CAPABILITIES
    assert "design" in gm.KNOWN_CAPABILITIES
    loaded = capabilities.load()
    assert loaded["design"].name == gd.CAPABILITY_NAME
    assert loaded["design"].verify_family is not None


def test_surprise_still_depends_on_design() -> None:
    """The dependency table was encoded at the spine; `design` now satisfies it."""
    assert gm.CAPABILITY_DEPENDENCIES["surprise"] == ("design",)
    assert gm.capability_problems(["design"]) == []
