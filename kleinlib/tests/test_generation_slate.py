"""Hypothesis slates and forecast calibration (WP-02).

Three layers, tested separately on purpose:

1. **The arithmetic** (``kleinlib.generation.calibration``) on hand-computed
   lists — Brier, the Murphy decomposition and its exact identity, coverage, and
   the best/worst bounds the censored rows allow.
2. **The bookkeeping** (``kleinlib.generation.slate``) on a real fixture study —
   V-11's four-row slate (supported / refuted / crash / never-run) scored to
   coverage 0.75 and `conditional`, then completed to 1.0 and `complete`; V-12's
   size, duplicate and id rules; the admission rule that binds a run to the
   hypothesis it was admitted for.
3. **The boundary** — a source scan asserting that nothing in either module
   produces, ranks or selects a candidate (R-SLA-6). The 1–3 axis scores are
   authored in the file and copied; they are never compared.

The fixtures reuse ``test_generation_spine``'s scaffolding, so a slate study is
an ordinary schema-3 generation study that declared one capability.
"""

from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest
import yaml
from test_generation_spine import _bump, _gates, _gen, _receipt, _scaffold, _statuses
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib import cli
from kleinlib.generation import calibration, slate
from kleinlib.workflow import record_gate, run_one

STUDY = "03-demo"
PHASE = "adaptive-1"
GENERATION_PKG = Path(__file__).resolve().parents[1] / "generation"

#: Four ruled predictions on the fixture's one track — one per V-11 slate row.
PREDICTIONS = [
    {
        "id": "P1",
        "track": "primary",
        "statement": "the metric clears 0.6",
        "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
    },
    {
        "id": "P2",
        "track": "primary",
        "statement": "the metric clears 0.9",
        "rule": {"key": "primary_metric", "op": ">", "value": 0.9},
    },
    {
        "id": "P3",
        "track": "primary",
        "statement": "the third lever clears 0.6",
        "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
    },
    {
        "id": "P4",
        "track": "primary",
        "statement": "the fourth lever clears 0.5",
        "rule": {"key": "primary_metric", "op": ">", "value": 0.5},
    },
    {
        "id": "P5",
        "track": "primary",
        "statement": "the referee finds the table readable",
        "manual": True,
    },
]


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _amend_contract(study: Path, transform) -> None:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    transform(contract)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


@pytest.fixture
def slate_study(tmp_path: Path) -> tuple[Path, Path]:
    """A generation study that DECLARED ``slates``, with P1…P5 registered.

    The predictions land before the consult gate — they are pre-registration, and
    a slate row may only name one the notary can decide.
    """
    repo, study = _scaffold(tmp_path)
    _amend_contract(study, lambda c: c.update(predictions=[dict(p) for p in PREDICTIONS]))
    commit_all(repo, "five registered predictions")
    assert _gen("init", "--study", str(study), "--capability", "slates") == 0
    _gates(repo, study)
    return repo, study


@pytest.fixture
def two_track_study(tmp_path: Path) -> tuple[Path, Path]:
    """The same, with a second declared track — so "wrong track" is testable."""
    repo, study = _scaffold(tmp_path)

    def _two(contract: dict) -> None:
        contract["predictions"] = [
            *[dict(p) for p in PREDICTIONS],
            {
                "id": "P6",
                "track": "secondary",
                "statement": "the second track's metric clears 0.6",
                "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
            },
        ]
        contract["tracks"]["secondary"] = copy.deepcopy(contract["tracks"]["primary"])
        contract["phases"][-1]["max_experiments"] = 2

    _amend_contract(study, _two)
    commit_all(repo, "two tracks")
    assert _gen("init", "--study", str(study), "--capability", "slates") == 0
    _gates(repo, study)
    return repo, study


def _row(
    index: int,
    *,
    p: float,
    success: tuple[str, ...] = ("P1",),
    provenance: str = "unscouted",
    track: str = "primary",
    kind: str = "diff",
    statement: str | None = None,
    **extra: object,
) -> dict[str, object]:
    """One authored slate row — every field the schema requires, nothing clever."""
    row: dict[str, object] = {
        "kind": kind,
        "track": track,
        "lever_family": f"lever-{index}",
        "statement": statement or f"candidate {index} moves val_auc",
        "source_ids": ["playbook", "method_card §4"],
        "provenance": provenance,
        "p_success": p,
        "success_P": list(success),
        "expected_effect": 0.01 * index,
        "units": "val_auc",
        "floor_ref": "minimum_delta",
        "cost_budget": "1 run",
        "novelty": 3,
        "testability": 3,
        "information": 2,
    }
    row.update(extra)
    return row


def _write_slate(
    study: Path, rows: list[dict[str, object]], *, phase: str = PHASE, base_rate: float = 0.5, **extra
) -> Path:
    payload = {
        "type": "slate",
        "study": STUDY,
        "phase": phase,
        "cohort_window": {"closes": "phase-end"},
        "base_rate_forecast": base_rate,
        **extra,
        "rows": rows,
    }
    path = study / "slates" / f"{phase}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


V11_ROWS = [
    _row(1, p=0.8, success=("P1",)),
    _row(2, p=0.3, success=("P2",)),
    _row(3, p=0.6, success=("P3",)),
    _row(4, p=0.5, success=("P4",)),
]


def _lock(study: Path, rows: list[dict[str, object]], *, phase: str = PHASE) -> int:
    _write_slate(study, rows, phase=phase)
    return _gen("slate", "lock", "--study", str(study), "--phase", phase)


def _check(study: Path, hypothesis: str, *tests: str, track: str = "primary") -> int:
    argv = ["check", "--study", str(study), "--action", "run", "--track", track,
            "--hypothesis", hypothesis]
    if tests:
        argv += ["--tests", *tests]
    return _gen(*argv)


def _run(study: Path, marker: str, value: float, *, tests: str) -> dict:
    _bump(study, marker)
    return run_one(study, command=metric_command(value), tests=tests, echo=False)


CRASH = [sys.executable, "-c", "raise SystemExit(3)"]


def _slate_object(study: Path, index: int = -1) -> dict:
    from kleinlib.generation.ledger import read_events

    return slate.slate_versions(study, read_events(study), PHASE)[index]["object"]


def _score_object(study: Path, index: int = -1) -> tuple[str, dict]:
    from kleinlib.generation.ledger import read_events

    entry = slate.score_events(study, read_events(study), PHASE)[index]
    return entry["sha"], entry["object"]


def _write_object(study: Path, sha: str, obj: dict) -> None:
    """Rewrite an object's BYTES in place — the tamper the family must catch."""
    (study / "generation" / "objects" / f"{sha}.json").write_text(
        json.dumps(obj, indent=2) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------
# 1. the arithmetic, hand-computed
# --------------------------------------------------------------------------


def test_brier_and_the_base_rate_are_the_textbook_means() -> None:
    pairs = [(0.8, 1), (0.3, 0), (0.6, 0)]
    assert calibration.brier(pairs) == pytest.approx((0.04 + 0.09 + 0.36) / 3)
    assert calibration.base_rate_brier(0.5, pairs) == pytest.approx(0.25)
    assert calibration.skill(0.163333333333333, 0.25) == pytest.approx(1 - 0.6533333333, rel=1e-6)
    assert calibration.brier([]) is None
    assert calibration.skill(0.1, 0.0) is None, "dividing by a perfect base rate invents infinity"


def test_the_murphy_identity_closes_exactly_on_the_binned_brier() -> None:
    """`binned_brier == reliability − resolution + uncertainty`, to 1e-12."""
    for pairs in (
        [(0.8, 1), (0.3, 0), (0.6, 0)],
        [(0.9, 1), (0.9, 0), (0.1, 0), (0.5, 1), (0.5, 0), (0.25, 1)],
        [(0.7, 1)],
    ):
        reliability, resolution, uncertainty = calibration.murphy(pairs)
        assert calibration.binned_brier(pairs) == pytest.approx(
            reliability - resolution + uncertainty, abs=1e-12
        )
    assert calibration.murphy([]) == (None, None, None)


def test_the_bins_are_five_equal_width_and_empty_ones_are_reported() -> None:
    rows = calibration.bins([(0.05, 0), (0.15, 1), (0.95, 1)])
    assert [row["n"] for row in rows] == [2, 0, 0, 0, 1]
    assert rows[0]["lo"] == 0.0 and rows[0]["hi"] == 0.2
    assert rows[0]["mean_p"] == pytest.approx(0.1) and rows[0]["mean_y"] == pytest.approx(0.5)
    assert rows[1]["mean_p"] is None and rows[1]["mean_y"] is None
    assert calibration.bin_index(0.2) == 1 and calibration.bin_index(1.0) == 4


def test_the_bounds_score_the_censored_rows_both_ways() -> None:
    pairs = [(0.8, 1)]
    best, worst = calibration.bounds(pairs, [0.9, 0.1])
    # best: the 0.9 row resolves 1 and the 0.1 row resolves 0
    assert best == pytest.approx((0.04 + 0.01 + 0.01) / 3)
    # worst: the other way round
    assert worst == pytest.approx((0.04 + 0.81 + 0.81) / 3)
    assert calibration.bounds(pairs, []) == (
        pytest.approx(0.04),
        pytest.approx(0.04),
    )
    assert calibration.bounds([], []) == (None, None)


def test_coverage_keeps_the_denominator_frozen() -> None:
    assert calibration.coverage(3, 4) == 0.75
    assert calibration.coverage(4, 4) == 1.0
    assert calibration.coverage(0, 0) is None


def test_numbers_agree_reports_the_first_disagreement_it_meets() -> None:
    left = {"a": 1.0, "b": [1, 2], "c": "x"}
    assert calibration.numbers_agree(left, {"a": 1.0 + 1e-15, "b": [1, 2], "c": "x"}) == []
    assert calibration.numbers_agree(left, {"a": 1.1, "b": [1, 2], "c": "x"})
    assert calibration.numbers_agree(left, {"a": 1.0, "b": [1], "c": "x"})
    assert calibration.numbers_agree(left, {"a": 1.0, "b": [1, 2], "c": "y"})


# --------------------------------------------------------------------------
# 2. V-11 — the A3 §2 smallest exercise
# --------------------------------------------------------------------------


def _run_the_first_three(study: Path) -> None:
    """Row 1 supported, row 2 refuted, row 3 crashed — the V-11 trajectory."""
    _bump(study, "h1")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    assert run_one(study, command=metric_command(0.7), tests="P1", echo=False)["predictions"] == {
        "P1": {"verdict": "supported", "explanation": "primary_metric 0.7 > 0.6 → supported"}
    }
    _bump(study, "h2")
    assert _check(study, f"{STUDY}#H2", "P2") == 0
    assert (
        run_one(study, command=metric_command(0.7), tests="P2", echo=False)["predictions"]["P2"][
            "verdict"
        ]
        == "refuted"
    )
    _bump(study, "h3")
    assert _check(study, f"{STUDY}#H3", "P3") == 0
    assert run_one(study, command=CRASH, tests="P3", echo=False)["disposition"] == "crash"


def test_v11_four_rows_score_over_three_at_coverage_three_quarters(slate_study) -> None:
    """V-11: supported / refuted / crash / never-run → Brier over 3, `conditional`."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    locked = _slate_object(study)
    assert [row["id"] for row in locked["rows"]] == [f"{STUDY}#H{n}" for n in (1, 2, 3, 4)]
    assert locked["version"] == 1 and locked["late"] is False

    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)

    assert score["coverage"] == 0.75
    assert score["outcome"] == "conditional"
    statuses = {row["id"]: (row["status"], row["y"]) for row in score["cohort"]}
    assert statuses == {
        f"{STUDY}#H1": ("resolved", 1),
        f"{STUDY}#H2": ("resolved", 0),
        f"{STUDY}#H3": ("resolved", 0),  # a crash is a resolved failure, not a gap
        f"{STUDY}#H4": ("censored", None),
    }
    assert "crashed" in next(r["reason"] for r in score["cohort"] if r["id"] == f"{STUDY}#H3")

    panel = score["panels"]["unscouted"]
    assert panel["n"] == 3
    assert panel["brier"] == pytest.approx((0.04 + 0.09 + 0.36) / 3)
    assert panel["base_rate_brier"] == pytest.approx(0.25)
    assert panel["skill"] == pytest.approx(1 - ((0.49 / 3) / 0.25))
    assert score["panels"]["derived"]["n"] == 0
    assert score["panels"]["revisions"]["n"] == 0

    table = (study / "generation" / "tables" / f"slate_calibration_{PHASE}.tsv").read_text(
        encoding="utf-8"
    )
    assert table.splitlines()[0].split("\t") == list(slate.TABLE_COLUMNS)
    assert len(table.splitlines()) == 5
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(_receipt(study), "generation slate") == ["PASS", "WARN"]
    reported = _receipt(study)["capabilities"]["slates"]
    assert reported["integrity"] == "PASS" and reported["outcome"] == "conditional"
    assert reported["phases"][PHASE]["coverage"] == 0.75
    assert reported["phases"][PHASE]["n"] == 3


def test_v11_completing_the_deferred_row_rescores_to_complete(slate_study) -> None:
    """Coverage 1.0 and `complete` — and only through `--rescore --reason`."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0

    _bump(study, "h4")
    assert _check(study, f"{STUDY}#H4", "P4") == 0
    run_one(study, command=metric_command(0.7), tests="P4", echo=False)

    # a second score without --rescore is refused; --rescore without a reason too
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 1
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE, "--rescore") == 1
    assert (
        _gen(
            "slate", "score", "--study", str(study), "--phase", PHASE,
            "--rescore", "--reason", "H4 resolved after the first score",
        )
        == 0
    )
    _sha, score = _score_object(study)
    assert score["coverage"] == 1.0
    assert score["outcome"] == "complete"
    assert score["panels"]["unscouted"]["n"] == 4
    # the new score names the old one as its parent; both objects survive
    from kleinlib.generation.ledger import read_events

    scores = slate.score_events(study, read_events(study), PHASE)
    assert len(scores) == 2
    assert scores[1]["event"]["parent_ids"] == [scores[0]["event"]["id"]]
    assert scores[1]["event"]["reason"] == "H4 resolved after the first score"

    assert _gen("verify", "--study", str(study)) == 0
    assert _receipt(study)["capabilities"]["slates"]["outcome"] == "complete"


def test_v11_invalid_control_editing_a_locked_forecast_fails_verification(slate_study) -> None:
    """R-SLA-4: the prior is immutable, and the file's sha is what says so."""
    repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    assert _gen("verify", "--study", str(study)) == 0

    path = study / "slates" / f"{PHASE}.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["rows"][1]["p_success"] = 0.95  # the refuted row, forecast up after the fact
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    commit_all(repo, "quietly raise a locked forecast")

    assert _gen("verify", "--study", str(study)) == 2
    detail = " ".join(
        c["detail"] for c in _receipt(study)["checks"] if c["name"] == "generation slate"
    )
    assert "immutable" in detail
    assert _receipt(study)["capabilities"]["slates"]["integrity"] == "FAIL"


def test_v11_a_tampered_score_object_fails_the_recomputation(slate_study) -> None:
    """R-SLA-5: verify recomputes every number from the receipts and manifests."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    assert _gen("verify", "--study", str(study)) == 0

    sha, score = _score_object(study)
    score["panels"]["unscouted"]["brier"] = 0.01
    _write_object(study, sha, score)
    assert _gen("verify", "--study", str(study)) == 2
    detail = " ".join(
        c["detail"] for c in _receipt(study)["checks"] if c["name"] == "generation slate"
    )
    assert "panels.unscouted.brier" in detail


def test_v11_a_tampered_calibration_table_fails_its_hash(slate_study) -> None:
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0

    path = study / "generation" / "tables" / f"slate_calibration_{PHASE}.tsv"
    path.write_text(path.read_text(encoding="utf-8").replace("resolved", "RESOLVED"), "utf-8")
    assert _gen("verify", "--study", str(study)) == 2
    detail = " ".join(
        c["detail"] for c in _receipt(study)["checks"] if c["name"] == "generation slate"
    )
    assert "is not the table the score hashed" in detail


# --------------------------------------------------------------------------
# 3. V-12 — slate size, duplicates, ids
# --------------------------------------------------------------------------


def test_v12_three_rows_and_seven_rows_are_both_refused(slate_study) -> None:
    _repo, study = slate_study
    from kleinlib.generation.ledger import read_events

    assert _lock(study, V11_ROWS[:3]) == 2
    assert _lock(study, [_row(n, p=0.5) for n in range(1, 8)]) == 2
    assert slate.latest_version(study, read_events(study), PHASE) is None, "nothing was recorded"


def test_v12_two_rows_with_one_statement_are_one_hypothesis_with_two_ids(slate_study) -> None:
    _repo, study = slate_study
    rows = [
        _row(1, p=0.8, statement="log1p the three right-skewed numerics"),
        _row(2, p=0.3, statement="log1p the three right-skewed numerics"),
        _row(3, p=0.6),
        _row(4, p=0.5),
    ]
    assert _lock(study, rows) == 2


def test_v12_an_amendment_withdraws_a_row_without_shrinking_the_cohort(slate_study) -> None:
    """RF-05: the denominator is frozen at lock; withdrawal is censoring."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    locked = _slate_object(study)
    carried = [dict(row) for row in locked["rows"][:3]]
    _write_slate(study, [*carried, _row(5, p=0.4, success=("P4",))])
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0

    amended = _slate_object(study)
    assert amended["version"] == 2
    assert amended["parent_ids"] == ["G0002"]
    assert [row["id"] for row in amended["rows"]] == [
        f"{STUDY}#H{n}" for n in (1, 2, 3, 5)
    ], "the new row gets a FRESH id; H4 is gone from the file, never from the cohort"

    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)
    withdrawn = next(row for row in score["cohort"] if row["id"] == f"{STUDY}#H4")
    assert withdrawn["status"] == "withdrawn" and "version 2" in withdrawn["reason"]
    assert len(score["cohort"]) == 5
    assert score["coverage"] == 0.0 and score["outcome"] == "conditional"


def test_v12_an_amendment_may_not_revive_a_freed_id(slate_study) -> None:
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    carried = [dict(row) for row in _slate_object(study)["rows"][:3]]
    _write_slate(study, [*carried, _row(5, p=0.4, success=("P4",))])
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0

    revived = dict(V11_ROWS[3], id=f"{STUDY}#H4")
    _write_slate(study, [*carried, revived])
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 2
    assert _slate_object(study)["version"] == 2, "the refused amendment recorded nothing"


def test_v12_a_carried_id_may_not_change_what_it_names(slate_study) -> None:
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    rows = [dict(row) for row in _slate_object(study)["rows"]]
    rows[0]["statement"] = "an entirely different idea"
    _write_slate(study, rows)
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 2


def test_v12_a_revised_forecast_is_scored_in_its_own_panel(slate_study) -> None:
    """R-SLA-4: the primary panels keep `p_first`; the revision panel gets `p_latest`."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    rows = [dict(row) for row in _slate_object(study)["rows"]]
    rows[0]["p_success"] = 0.55
    _write_slate(study, rows)
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0
    assert _slate_object(study)["rows"][0]["revision_of"] == 1

    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)
    first = next(row for row in score["cohort"] if row["id"] == f"{STUDY}#H1")
    assert (first["p_first"], first["p_latest"]) == (0.8, 0.55)
    assert score["panels"]["unscouted"]["brier"] == pytest.approx((0.04 + 0.09 + 0.36) / 3)
    assert score["panels"]["revisions"]["n"] == 1
    assert score["panels"]["revisions"]["brier"] == pytest.approx((0.55 - 1) ** 2)


def test_v12_a_revision_stays_a_revision_across_a_later_amendment(slate_study) -> None:
    """B-8: `revision_of` is carried forward, so the row cannot drift back.

    The revisions panel selects on `revision_of`, and the primary panels score
    `p_first`.  Clearing the marker on the next amendment that happens not to
    touch the row would move the revised forecast back into the primary panel and
    score it against the number it replaced.
    """
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    rows = [dict(row) for row in _slate_object(study)["rows"]]
    rows[0]["p_success"] = 0.55
    _write_slate(study, rows)
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0
    assert _slate_object(study)["rows"][0]["revision_of"] == 1

    # v3 touches a DIFFERENT row; H1's forecast is untouched and stays revised
    rows = [dict(row) for row in _slate_object(study)["rows"]]
    rows[1]["p_success"] = 0.35
    _write_slate(study, rows)
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0
    third = _slate_object(study)
    assert third["version"] == 3
    assert third["rows"][0]["revision_of"] == 1, "H1 was revised in v2 and still is"
    assert third["rows"][1]["revision_of"] == 2
    assert third["rows"][2]["revision_of"] is None, "a row nobody ever revised"

    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)
    assert score["panels"]["revisions"]["n"] == 2
    assert _gen("verify", "--study", str(study)) == 0


def test_v12_a_first_lock_can_never_be_late_and_an_amendment_may_be(slate_study) -> None:
    """B-12: `late` on version 1 was an unreachable FAIL, and this is why.

    `is_late` asks whether a receipt already named an id THIS phase allocated —
    and before a phase's first lock there are no ids to name, so version 1 is
    `late: false` by construction.  The rule that actually catches a hypothesis
    admitted before the slate in force is the admission-order check, which reads
    the receipts against the versions locked before each one.
    """
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    assert _slate_object(study, 0)["late"] is False

    _bump(study, "h1")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    run_one(study, command=metric_command(0.7), tests="P1", echo=False)

    rows = [dict(row) for row in _slate_object(study)["rows"]]
    _write_slate(study, rows)
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0
    assert _slate_object(study)["late"] is True, "informational on an amendment, not a FAIL"
    assert _gen("verify", "--study", str(study)) == 0
    assert _receipt(study)["capabilities"]["slates"]["integrity"] == "PASS"


def test_v12_a_parent_id_must_name_a_hypothesis_this_study_locked(slate_study, capsys) -> None:
    """B-13: lineage that ends nowhere still looks like provenance."""
    _repo, study = slate_study
    invented = [dict(V11_ROWS[0], parent_ids=[f"{STUDY}#H99"]), *V11_ROWS[1:]]
    assert _lock(study, invented) == 2
    assert "no locked slate in this study ever allocated" in capsys.readouterr().out

    malformed = [dict(V11_ROWS[0], parent_ids=[7]), *V11_ROWS[1:]]
    assert _lock(study, malformed) == 2
    assert "is not a hypothesis id" in capsys.readouterr().out

    # a real ancestor is accepted, and an empty list always was
    assert _lock(study, V11_ROWS) == 0
    carried = [dict(row) for row in _slate_object(study)["rows"][:3]]
    descendant = _row(5, p=0.4, success=("P4",), parent_ids=[f"{STUDY}#H1"])
    _write_slate(study, [*carried, descendant])
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0
    assert _slate_object(study)["rows"][3]["parent_ids"] == [f"{STUDY}#H1"]


def test_the_base_rate_forecast_is_frozen_at_the_first_lock(slate_study) -> None:
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    rows = [dict(row) for row in _slate_object(study)["rows"]]
    _write_slate(study, rows, base_rate=0.2)
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 2


# --------------------------------------------------------------------------
# 4. admission
# --------------------------------------------------------------------------


def _last_reasons(study: Path) -> list[str]:
    lines = (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    sha = json.loads(lines[-1])["payload_sha256"]
    obj = json.loads((study / "generation" / "objects" / f"{sha}.json").read_text("utf-8"))
    return obj["reasons"]


def test_a_hypothesis_before_the_lock_is_refused(slate_study) -> None:
    _repo, study = slate_study
    _bump(study, "early")
    assert _check(study, f"{STUDY}#H1", "P1") == 2
    assert any("no slate is locked" in reason for reason in _last_reasons(study))


def test_the_notary_must_be_asked_to_adjudicate_every_success_p(slate_study) -> None:
    """Without `--tests`, the row's y could never resolve — so the check says no."""
    _repo, study = slate_study
    assert _lock(study, [_row(1, p=0.8, success=("P1", "P4")), *V11_ROWS[1:]]) == 0
    _bump(study, "partial")
    assert _check(study, f"{STUDY}#H1", "P1") == 2
    assert any("missing P4" in reason for reason in _last_reasons(study))
    assert _check(study, f"{STUDY}#H1", "P1", "P4") == 0


def test_a_hypothesis_on_another_track_is_refused(two_track_study) -> None:
    _repo, study = two_track_study
    rows = [_row(1, p=0.8, track="secondary", success=("P6",)), *V11_ROWS[1:]]
    assert _lock(study, rows) == 0
    _bump(study, "wrong-track")
    assert _check(study, f"{STUDY}#H1", "P6", track="primary") == 2
    assert any("not 'primary'" in reason for reason in _last_reasons(study))


def test_a_withdrawn_row_never_runs_again(slate_study) -> None:
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    carried = [dict(row) for row in _slate_object(study)["rows"][:3]]
    _write_slate(study, [*carried, _row(5, p=0.4, success=("P4",))])
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 0
    _bump(study, "withdrawn")
    assert _check(study, f"{STUDY}#H4", "P4") == 2
    assert any("was withdrawn" in reason for reason in _last_reasons(study))


def test_an_enabled_study_runs_hypotheses_and_names_its_exemptions(slate_study) -> None:
    """`--action run` without an H is refused; the typed obligations are not."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _bump(study, "nameless")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2
    assert _last_reasons(study) == [
        "an enabled study runs hypotheses; use --hypothesis, or "
        "--action calibration|baseline|repair"
    ]
    assert (
        _gen("check", "--study", str(study), "--action", "calibration", "--track", "primary") == 0
    )


def test_the_receipt_pins_the_lock_it_was_taken_under(slate_study) -> None:
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _bump(study, "pinned")
    assert _check(study, f"{STUDY}#H1", "P1") == 0

    from kleinlib.generation.ledger import read_events

    events = read_events(study)
    sha = events[-1]["payload_sha256"]
    receipt = json.loads(
        (study / "generation" / "objects" / f"{sha}.json").read_text(encoding="utf-8")
    )
    assert receipt["inputs"]["slate"] == slate.latest_version(study, events, PHASE)["sha"]
    assert receipt["intended_action"]["hypothesis_id"] == f"{STUDY}#H1"
    # The key set is the SPINE's, not this capability's: a capability may fill a
    # slot and may never add one, so the receipt's shape is read from the
    # constant rather than restated here (restating it would only break the day
    # a later package legitimately declares a new slot).
    from kleinlib.generation.admission import RECEIPT_INPUT_SLOTS

    assert set(receipt["inputs"]) == {"manifest", *RECEIPT_INPUT_SLOTS}


def test_a_hypothesis_scores_on_its_first_resolution(slate_study) -> None:
    """B-7: `y` comes from the FIRST admitted run, and the retry is counted.

    A forecast is about what happens when the idea is tried.  Reading the LAST
    admitted run would let a row that resolved `y = 0` be run again — knowing the
    outcome this time — until it resolved `y = 1`, which scores the forecast
    against a retry rather than against a prediction.  The second run stays on
    the ledger, is counted in `n_bound_runs`, and earns a WARN.
    """
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0

    _bump(study, "h1 first try")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    first = run_one(study, command=metric_command(0.5), tests="P1", echo=False)
    assert first["predictions"]["P1"]["verdict"] == "refuted"

    _bump(study, "h1 again, now that the answer is known")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    second = run_one(study, command=metric_command(0.7), tests="P1", echo=False)
    assert second["predictions"]["P1"]["verdict"] == "supported"

    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)
    row = next(entry for entry in score["cohort"] if entry["id"] == f"{STUDY}#H1")
    assert (row["y"], row["run"]) == (0, first["experiment"]), "the FIRST resolution scores"
    assert row["n_bound_runs"] == 2
    assert score["panels"]["unscouted"]["brier"] == pytest.approx((0.8 - 0) ** 2)

    table = (study / "generation" / "tables" / f"slate_calibration_{PHASE}.tsv").read_text("utf-8")
    header = table.splitlines()[0].split("\t")
    assert header == list(slate.TABLE_COLUMNS) and "n_bound_runs" in header
    assert table.splitlines()[1].split("\t")[-1] == "2"

    assert _gen("verify", "--study", str(study)) == 0, "a re-run is a WARN, not a broken record"
    detail = " ".join(
        c["detail"] for c in _receipt(study)["checks"] if c["name"] == "generation slate"
    )
    assert f"{STUDY}#H1 bound more than one admitted run" in detail
    assert _receipt(study)["capabilities"]["slates"]["integrity"] == "PASS"


def test_one_admitted_run_per_row_counts_one_and_warns_about_nothing(slate_study) -> None:
    """The valid control for B-7: the ordinary trajectory is unchanged."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)
    counts = {row["id"]: row["n_bound_runs"] for row in score["cohort"]}
    assert counts == {
        f"{STUDY}#H1": 1,
        f"{STUDY}#H2": 1,
        f"{STUDY}#H3": 1,
        f"{STUDY}#H4": 0,
    }
    assert _gen("verify", "--study", str(study)) == 0
    detail = " ".join(
        c["detail"] for c in _receipt(study)["checks"] if c["name"] == "generation slate"
    )
    assert "bound more than one admitted run" not in detail


def test_an_unadmitted_hypothesis_run_censors_rather_than_resolving(slate_study) -> None:
    """A row is bound only through an ADMITTED receipt — never by prose."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    _bump(study, "unadmitted")
    run_one(study, command=metric_command(0.7), tests="P1", echo=False)

    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)
    assert {row["status"] for row in score["cohort"]} == {"censored"}
    assert score["coverage"] == 0.0


# --------------------------------------------------------------------------
# 5. scouted provenance and phase closure
# --------------------------------------------------------------------------


def test_a_scouted_row_is_descriptive_and_never_calibration(slate_study) -> None:
    """consult-protocol.md: a value the ledger already saw is not a forecast."""
    _repo, study = slate_study
    rows = [
        _row(1, p=0.8, success=("P1",), provenance="scouted"),
        _row(2, p=0.3, success=("P2",), provenance="derived"),
        _row(3, p=0.6, success=("P3",)),
        _row(4, p=0.5, success=("P4",)),
    ]
    assert _lock(study, rows) == 0
    _run_the_first_three(study)
    assert _gen("slate", "score", "--study", str(study), "--phase", PHASE) == 0
    _sha, score = _score_object(study)

    assert score["panels"]["scouted_descriptive"]["n"] == 1
    assert score["panels"]["scouted_descriptive"]["brier"] == pytest.approx(0.04)
    assert score["panels"]["derived"]["n"] == 1
    assert score["panels"]["unscouted"]["n"] == 1
    assert score["panels"]["unscouted"]["brier"] == pytest.approx(0.36)
    table = (study / "generation" / "tables" / f"slate_calibration_{PHASE}.tsv").read_text("utf-8")
    assert f"{STUDY}#H1\tscouted_descriptive" in table


def test_a_phase_acknowledged_without_a_score_is_a_warning(slate_study) -> None:
    repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    record_gate(study, "phase", acknowledged_by="tester", phase=PHASE)
    commit_all(repo, "phase acknowledged")
    assert _gen("verify", "--study", str(study)) == 0
    detail = " ".join(
        c["detail"] for c in _receipt(study)["checks"] if c["name"] == "generation slate"
    )
    assert "was acknowledged without a" in detail
    assert _receipt(study)["capabilities"]["slates"]["outcome"] == "unscored"


def test_declaring_slates_without_locking_one_is_honest_not_broken(slate_study) -> None:
    _repo, study = slate_study
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(_receipt(study), "generation slate") == ["WARN"]
    assert _receipt(study)["capabilities"]["slates"] == {
        "integrity": "PASS",
        "outcome": "unscored",
        "phases": {},
    }
    assert _gen("slate", "show", "--study", str(study)) == 0


# --------------------------------------------------------------------------
# 6. contract validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        ({"p_success": 0}, "certainties, not forecasts"),
        ({"p_success": 1.5}, "strictly inside"),
        ({"provenance": "guessed"}, "provenance is"),
        ({"novelty": 4}, "novelty is 4"),
        ({"kind": "experiment"}, "kind is"),
        ({"track": "ghost"}, "is not declared in study.yaml"),
        ({"success_P": ["P9"]}, "does not register"),
        ({"success_P": ["P5"]}, "is manual (no rule)"),
        ({"success_P": []}, "non-empty list of registered prediction ids"),
        ({"floor_ref": "guessed"}, "expected 'minimum_delta'"),
        ({"floor_ref": "sweep:nope"}, "is not registered in study_state.json"),
        ({"source_ids": []}, "source_ids must be a non-empty list"),
        ({"units": ""}, "units is required"),
        ({"expected_effect": "a lot"}, "expected_effect must be a number"),
    ],
)
def test_one_bad_row_field_refuses_the_whole_lock(slate_study, mutation, needle, capsys) -> None:
    _repo, study = slate_study
    rows = [dict(V11_ROWS[0], **mutation), *[dict(row) for row in V11_ROWS[1:]]]
    assert _lock(study, rows) == 2
    assert needle in capsys.readouterr().out


def test_the_cohort_window_and_the_phase_id_are_both_checked(slate_study, capsys) -> None:
    _repo, study = slate_study
    _write_slate(study, [dict(row) for row in V11_ROWS], base_rate=0.5)
    path = study / "slates" / f"{PHASE}.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["cohort_window"] = {"closes": "never"}
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    assert _gen("slate", "lock", "--study", str(study), "--phase", PHASE) == 2
    assert "cohort_window" in capsys.readouterr().out

    assert _gen("slate", "lock", "--study", str(study), "--phase", "no-such-phase") == 1


def test_a_study_that_did_not_declare_slates_cannot_lock_one(tmp_path: Path) -> None:
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study)) == 0
    _gates(repo, study)
    _write_slate(study, [dict(row) for row in V11_ROWS])
    assert _gen("slate", "lock", "--study", str(study), "--phase", PHASE) == 1


def test_locking_twice_is_refused_and_amending_nothing_is_too(slate_study) -> None:
    """A locked forecast is immutable: the second version is an amendment or nothing."""
    _repo, study = slate_study
    assert _gen("slate", "amend", "--study", str(study), "--phase", PHASE) == 1
    assert _lock(study, V11_ROWS) == 0
    assert _lock(study, V11_ROWS) == 1
    assert _slate_object(study)["version"] == 1


# --------------------------------------------------------------------------
# 7. write ownership and R-SLA-6
# --------------------------------------------------------------------------


def test_a_slate_commit_files_the_slate_and_the_ledger_and_nothing_else(slate_study) -> None:
    repo, study = slate_study
    _bump(study, "operator edit that must survive")
    assert _lock(study, V11_ROWS) == 0
    names = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(Path(name).name for name in names) == sorted(
        [f"{PHASE}.yaml", "events.jsonl", *[Path(n).name for n in names if n.endswith(".json")]]
    )
    assert all(
        "/slates/" in f"/{name}" or "/generation/" in f"/{name}" for name in names
    ), names
    assert "train.py" in git(repo, "status", "--porcelain"), "the candidate stayed the operator's"


BANNED_FUNCTION_PREFIXES = (
    "propose",
    "generate",
    "rank",
    "select",
    "suggest",
    "choose",
    "recommend",
    "invent",
)

#: The authored fields a ranking would have to touch.  They may be VALIDATED and
#: COPIED; they may never key a sort or feed a comparison.
JUDGMENT_FIELDS = ("novelty", "testability", "information", "p_success")


def _module_source(name: str) -> tuple[str, ast.Module]:
    text = (GENERATION_PKG / f"{name}.py").read_text(encoding="utf-8")
    return text, ast.parse(text)


@pytest.mark.parametrize("module", ["slate", "calibration"])
def test_r_sla_6_nothing_here_proposes_ranks_or_selects(module: str) -> None:
    """R-SLA-6: the mechanism records and computes; the judgment stays authored."""
    _text, tree = _module_source(module)
    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.lstrip("_").startswith(BANNED_FUNCTION_PREFIXES)
    ]
    assert not offenders, f"{module}.py defines {offenders} — the layer never generates"

    sorts: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in ("sorted", "sort", "max", "min"):
            continue
        rendered = ast.dump(node)
        for field in JUDGMENT_FIELDS:
            if repr(field) in rendered:
                sorts.append(f"{name}(… {field} …)")
    assert not sorts, f"{module}.py orders rows by an authored score: {sorts}"


def test_r_sla_6_the_axis_scores_are_only_ever_validated(slate_study) -> None:
    """The 1–3 scores reach the record verbatim and reach no comparison at all."""
    _repo, study = slate_study
    rows = [dict(row, novelty=1, testability=2, information=3) for row in V11_ROWS]
    assert _lock(study, rows) == 0
    locked = _slate_object(study)
    assert [(r["novelty"], r["testability"], r["information"]) for r in locked["rows"]] == [
        (1, 2, 3)
    ] * 4
    # the row order is the AUTHOR's, unchanged by any score
    assert [row["statement"] for row in locked["rows"]] == [
        str(row["statement"]) for row in V11_ROWS
    ]


def test_the_slate_modules_reach_no_network_and_call_no_runner() -> None:
    for module in ("slate", "calibration"):
        text, _tree = _module_source(module)
        for banned in ("run_one", "subprocess", "requests", "httpx", "urllib", "socket"):
            assert f"import {banned}" not in text and f"from {banned}" not in text, module
        assert "run_one(" not in text, f"{module}.py must never drive the notary"


def test_core_verify_still_never_mentions_the_word_generation(slate_study) -> None:
    """R-INV-8, re-checked with a capability declared."""
    _repo, study = slate_study
    assert _lock(study, V11_ROWS) == 0
    assert cli.main(["verify", "--study", str(study)]) == 0
    receipt = json.loads((study / "verify_receipt.json").read_text(encoding="utf-8"))
    assert not [c for c in receipt["checks"] if "generation" in c["name"]]
    assert not [c for c in receipt["checks"] if "slate" in c["name"]]
