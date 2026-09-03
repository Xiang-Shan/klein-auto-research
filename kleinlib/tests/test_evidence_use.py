"""E9 / D14 — the 2026 failure modes as arithmetic on the receipt.

Three absences no other check catches, because each is a thing that is NOT
there: evidence the study produced and never mentioned again, a refutation with
no recorded decision, a confirmation resting on one kind of look.

Pinned here: the three numbers, the citation rules behind them, the schema
posture (enforcing on 3, silent on 2 unless asked, advisory when asked), and
`klein status` printing the summary line.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_registered_mode import amend
from test_workflow_v3 import commit_all

from kleinlib.evidence_use import EvidenceUse, decided_prediction_ids, evidence_use
from kleinlib.workflow import load_contract, load_state, status_summary, verify_study


def _manifests(*rows: tuple[str, str]) -> list[dict]:
    return [{"experiment": name, "disposition": disposition} for name, disposition in rows]


def _write(study: Path, name: str, text: str) -> None:
    (study / name).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. ignored evidence
# ---------------------------------------------------------------------------


def test_every_non_keep_disposition_counts_and_keeps_do_not(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _write(study, "program.md", "we ran things\n")
    _write(study, "findings.md", "# Findings\n")
    usage = evidence_use(
        study,
        {},
        {},
        _manifests(
            ("E0001", "keep"),
            ("E0002", "discard"),
            ("E0003", "crash"),
            ("E0004", "measured"),
        ),
    )
    # the incumbent chain reports itself; the rest is the record nobody has to read
    assert usage.evidence == ("E0002", "E0003", "E0004")
    assert usage.uncited == ("E0002", "E0003", "E0004")
    assert usage.rate == 0.0


def test_a_citation_in_either_document_counts(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _write(study, "program.md", "E0002 told us the encoder was the problem.\n")
    _write(study, "findings.md", "The crash E0003 is reported in §③.\n")
    usage = evidence_use(
        study, {}, {}, _manifests(("E0002", "discard"), ("E0003", "crash"), ("E0004", "measured"))
    )
    assert usage.cited == ("E0002", "E0003")
    assert usage.uncited == ("E0004",)
    assert usage.rate == pytest.approx(2 / 3)


def test_a_registered_sweep_is_evidence_that_must_be_cited(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _write(study, "program.md", "nothing to see\n")
    state = {"sweeps": {"floor": {"sidecar": "s.tsv"}, "arena": {"sidecar": "a.tsv"}}}
    usage = evidence_use(study, {}, state, [])
    assert usage.evidence == ("sweep:arena", "sweep:floor")
    _write(study, "findings.md", "the ladder comes from sweep:arena.\n")
    usage = evidence_use(study, {}, state, [])
    assert usage.cited == ("sweep:arena",)
    assert usage.uncited == ("sweep:floor",)


def test_a_run_id_is_matched_whole_never_as_a_prefix(tmp_path: Path) -> None:
    """`E0001` must not be "cited" by a table cell reading `E00010.029442`."""
    study = tmp_path / "10-demo"
    study.mkdir()
    _write(study, "findings.md", "E00010.029442 keep\n")
    usage = evidence_use(study, {}, {}, _manifests(("E0001", "discard")))
    assert usage.uncited == ("E0001",)


def test_an_empty_ledger_has_nothing_to_ignore(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    assert evidence_use(study, {}, {}, []).rate == 1.0


# ---------------------------------------------------------------------------
# 2. refutation without revision
# ---------------------------------------------------------------------------


def test_a_dated_decision_line_naming_the_id_is_what_counts() -> None:
    program = (
        "## adaptive-2 — 2026-09-03\n"
        "\n"
        "- **Decision:** P3 is refuted; the spline lever is retired.\n"
    )
    assert decided_prediction_ids(program) == {"P3"}


def test_an_undated_decision_line_does_not_count() -> None:
    assert decided_prediction_ids("- Decision: P3 is refuted.\n") == set()


def test_a_date_far_above_the_decision_does_not_reach_it() -> None:
    program = "# 2026-09-03\n" + "\n" * 12 + "- Decision: P3 is refuted.\n"
    assert decided_prediction_ids(program) == set()


def test_a_decision_that_names_no_prediction_decides_nothing() -> None:
    assert decided_prediction_ids("2026-09-03 Decision: stop the phase.\n") == set()


def test_a_refuted_prediction_without_a_decision_is_reported(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _write(study, "program.md", "no decisions here\n")
    contract = {
        "predictions": [
            {"id": "P1", "statement": "a"},
            {"id": "P2", "statement": "b"},
        ]
    }
    state = {
        "predictions": {
            "P1": {"verdict": "refuted"},
            "P2": {"verdict": "supported"},
        }
    }
    usage = evidence_use(study, contract, state, [])
    assert usage.refuted == ("P1",)
    assert usage.undecided_refutations == ("P1",)

    _write(study, "program.md", "## 2026-09-03\n- Decision: P1 refuted, lever retired.\n")
    assert evidence_use(study, contract, state, []).undecided_refutations == ()


# ---------------------------------------------------------------------------
# 3. single-source confirmation
# ---------------------------------------------------------------------------


def _lock(study: Path, evidence: list[str], *, strength: str = "confirmed") -> None:
    (study / "claims.lock").write_text(
        json.dumps(
            {
                "lock_schema": 2,
                "claims": {"C1": {"strength": strength, "evidence": evidence}},
            }
        ),
        encoding="utf-8",
    )


def _run(study: Path, name: str, *, sealed: bool) -> None:
    directory = study / "runs" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        json.dumps({"experiment": name, "evaluation_kind": "final_test" if sealed else "development"}),
        encoding="utf-8",
    )


def test_a_development_run_alone_is_a_single_source(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _run(study, "E0001", sealed=False)
    _run(study, "E0002", sealed=False)
    _lock(study, ["E0001", "E0002"])
    usage = evidence_use(study, {}, {}, [])
    assert usage.claim_kinds["C1"] == ("run",)
    assert usage.single_source_claims == ("C1",)


@pytest.mark.parametrize(
    "second, kind",
    [
        ("E0002", "sealed"),
        ("rep:E0001@20260903T101500Z", "replication"),
        ("verify:E0001@20260903T101500Z", "verification"),
    ],
)
def test_two_kinds_clear_the_convergence_bar(tmp_path: Path, second: str, kind: str) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _run(study, "E0001", sealed=False)
    _run(study, "E0002", sealed=True)
    _lock(study, ["E0001", second])
    usage = evidence_use(study, {}, {}, [])
    assert usage.claim_kinds["C1"] == ("run", kind)
    assert usage.single_source_claims == ()


def test_an_exploratory_claim_is_never_asked_for_convergence(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _run(study, "E0001", sealed=False)
    _lock(study, ["E0001"], strength="exploratory")
    assert evidence_use(study, {}, {}, []).claim_kinds == {}


def test_a_lone_sealed_look_is_also_single_source(tmp_path: Path) -> None:
    study = tmp_path / "10-demo"
    study.mkdir()
    _run(study, "E0009", sealed=True)
    _lock(study, ["E0009"])
    usage = evidence_use(study, {}, {}, [])
    assert usage.claim_kinds["C1"] == ("sealed",)
    assert usage.single_source_claims == ("C1",)


# ---------------------------------------------------------------------------
# 4. the summary line
# ---------------------------------------------------------------------------


def test_the_summary_names_all_three_numbers() -> None:
    line = EvidenceUse(
        evidence=("E0002", "E0003"),
        cited=("E0002",),
        uncited=("E0003",),
        undecided_refutations=("P1",),
        refuted=("P1",),
        single_source_claims=("C1",),
    ).summary()
    assert "evidence use: 0.50 (1/2 cited)" in line
    assert "1 refutation(s) without a recorded decision" in line
    assert "1 single-source confirmed claim(s)" in line


# ---------------------------------------------------------------------------
# 5. verify and status, on a real schema-3 study
# ---------------------------------------------------------------------------


@pytest.fixture
def uncited_study(ready_study_v3):
    """A schema-3 study with one registered sweep nothing ever mentions."""
    repo, study = ready_study_v3
    state_path = study / "study_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["sweeps"] = {
        "floor": {
            "sidecar": "sweeps/floor.sidecar.tsv",
            "sidecar_sha256": "0" * 64,
            "script": "sweeps/floor.py",
            "script_sha256": "0" * 64,
        }
    }
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (study / "findings.md").write_text("# Findings\n\nexploratory.\n", encoding="utf-8")
    commit_all(repo, "a sweep nobody cites")
    return repo, study


def _named(checks, name):
    return [check for check in checks if check.name == name]


def test_schema_3_verify_reports_the_uncited_sweep_as_a_warning(uncited_study) -> None:
    _repo, study = uncited_study
    checks = _named(verify_study(study, receipt=False), "evidence use")
    assert len(checks) == 1
    assert checks[0].ok is True
    assert "[WARN] evidence_use_rate 0.00" in checks[0].message
    assert "sweep:floor" in checks[0].message


def test_strict_turns_the_shortfall_into_a_failure(uncited_study) -> None:
    _repo, study = uncited_study
    checks = _named(verify_study(study, receipt=False, strict=True), "evidence use")
    assert checks[0].ok is False


def test_citing_it_clears_the_check(uncited_study) -> None:
    repo, study = uncited_study
    (study / "program.md").write_text(
        (study / "program.md").read_text(encoding="utf-8")
        + "\nThe floor comes from sweep:floor.\n",
        encoding="utf-8",
    )
    commit_all(repo, "cite the sweep")
    checks = _named(verify_study(study, receipt=False, strict=True), "evidence use")
    assert checks[0].ok is True
    assert "evidence_use_rate 1.00" in checks[0].message


def test_schema_2_is_silent_by_default_and_advisory_when_asked(ready_study) -> None:
    repo, study = ready_study
    state_path = study / "study_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["sweeps"] = {"floor": {"sidecar": "sweeps/floor.sidecar.tsv"}}
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    commit_all(repo, "a schema-2 sweep")

    assert _named(verify_study(study), "evidence use") == []
    asked = _named(verify_study(study, evidence=True, strict=True), "evidence use")
    assert len(asked) == 1
    # never retro-fails: schema 2 gets the finding, not the failure
    assert asked[0].ok is True
    assert "advisory on schema 2" in asked[0].message


def test_status_prints_the_three_numbers_on_schema_3(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    printed = status_summary(study)
    assert "evidence use: 1.00" in printed
    assert "refutation(s) without a recorded decision" in printed
    assert "single-source confirmed claim(s)" in printed


def test_status_on_schema_2_is_unchanged(ready_study) -> None:
    _repo, study = ready_study
    assert "evidence use:" not in status_summary(study)


def test_a_refuted_prediction_without_a_decision_fails_verify(ready_study_v3) -> None:
    repo, study = ready_study_v3
    amend(
        study,
        lambda c: c.update(
            predictions=[{"id": "P1", "statement": "the frontier clears 0.6"}]
        ),
        note="one manual prediction",
    )
    state_path = study / "study_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["predictions"] = {"P1": {"verdict": "refuted", "evidence": ["E0001"]}}
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    commit_all(repo, "P1 refuted, nothing decided")

    checks = _named(verify_study(study, receipt=False), "belief revision")
    assert len(checks) == 1 and checks[0].ok is False
    assert "P1 is refuted" in checks[0].message

    program = study / "program.md"
    program.write_text(
        program.read_text(encoding="utf-8")
        + "\n## adaptive-1 — 2026-09-03\n\n- **Decision:** P1 refuted; lever retired.\n",
        encoding="utf-8",
    )
    commit_all(repo, "the decision is on the record")
    assert _named(verify_study(study, receipt=False), "belief revision")[0].ok is True


def test_the_ledger_and_the_state_agree_on_what_refuted_means(ready_study_v3) -> None:
    """`evidence_use` reads the ledger Package B builds, not its own copy."""
    _repo, study = ready_study_v3
    contract = load_contract(study)
    state = load_state(study, contract)
    assert evidence_use(study, contract, state, []).refuted == ()
