"""The sign-flip max-t selection guard, checked against study 09's shipped numbers.

`kleinlib.metrology.family_maxt` is a port of the frozen study-08 reference
(`studies/08-iris-rematch/sweeps/rematch_analysis.py`, re-used verbatim by
study 09's `sweeps/analysis.py`).  The port is only worth having if it
reproduces what those studies published, so the anchor test rebuilds study 09's
42-cell permission map from its committed arena sidecars and compares every
adjusted score with `sweeps/arena_verdicts.tsv` — and the headline
`0/42` recorded in `claims.lock` under the `guard` alias.

Nothing here writes to `studies/`.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np
import pytest

from kleinlib.metrology import family_maxt

REPO = Path(__file__).resolve().parents[2]
STUDY09 = REPO / "studies" / "09-iris-first-lesson"
SWEEPS = STUDY09 / "sweeps"

#: Study 09's registered guard: repeat-level units, full enumeration of 2**10.
REPEATS = 10
FOLDS = 4
ANCHOR = "anchor_lda4"
#: `alpha = 0.05` lands between 51/1024 and 52/1024 on the enumeration grid.
ALPHA = 0.05

pytestmark = pytest.mark.skipif(
    not (SWEEPS / "arena_verdicts.tsv").is_file(),
    reason="study 09 evidence is not present in this checkout",
)


def _sidecar_cells(name: str) -> dict[tuple[str, int, int, int], float]:
    """(family, rung, repeat, fold) -> primary_metric for the ok rows."""
    import csv

    out: dict[tuple[str, int, int, int], float] = {}
    with (SWEEPS / name).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if row["status"] != "ok" or row["primary_metric"] in ("", "NA"):
                continue
            params = json.loads(row["params_json"])
            key = (
                params["family"],
                int(params["rung"]),
                int(params["repeat"]),
                int(params["fold"]),
            )
            out[key] = float(row["primary_metric"])
    return out


def _recorded_verdicts() -> list[dict[str, str]]:
    import csv

    with (SWEEPS / "arena_verdicts.tsv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def _study09_family() -> tuple[dict[str, np.ndarray], list[dict[str, str]]]:
    """Rebuild the guard's input: one repeat-level mean paired delta per unit."""
    anchor = _sidecar_cells("arena_anchor.sidecar.tsv")
    challengers = _sidecar_cells("arena.sidecar.tsv")
    verdicts = _recorded_verdicts()
    deltas: dict[str, np.ndarray] = {}
    for row in verdicts:
        family, rung = row["family"], int(row["rung"])
        units = []
        for repeat in range(1, REPEATS + 1):
            # Positive = the challenger improved on the anchor's Brier.
            paired = [
                anchor[(ANCHOR, rung, repeat, fold)] - challengers[(family, rung, repeat, fold)]
                for fold in range(FOLDS)
                if (ANCHOR, rung, repeat, fold) in anchor
                and (family, rung, repeat, fold) in challengers
            ]
            units.append(statistics.fmean(paired) if paired else float("nan"))
        deltas[f"{family}@{rung}"] = np.array(units)
    return deltas, verdicts


def test_reproduces_every_adjusted_score_study_09_published() -> None:
    deltas, verdicts = _study09_family()
    assert len(deltas) == 42, "study 09's registered family is 7 challengers x 6 rungs"

    adjusted = family_maxt(deltas, n_perm=1024, seed=0)

    mismatches = [
        (row["family"], row["rung"], row["p_guard"], adjusted[f"{row['family']}@{row['rung']}"])
        for row in verdicts
        if round(adjusted[f"{row['family']}@{row['rung']}"], 4) != float(row["p_guard"])
    ]
    assert not mismatches, f"adjusted scores drifted from the shipped table: {mismatches}"


def test_reproduces_the_zero_of_forty_two_recorded_in_the_claims_lock() -> None:
    lock = json.loads((STUDY09 / "claims.lock").read_text(encoding="utf-8"))
    recorded = lock["claims"]["guard"]["value"]["bar1_cleared"]

    deltas, _ = _study09_family()
    adjusted = family_maxt(deltas, n_perm=1024, seed=0)
    cleared = [cell for cell, p in adjusted.items() if p <= ALPHA]

    assert f"{len(cleared)}/{len(adjusted)}" == recorded == "0/42"


def test_full_enumeration_is_exact_and_ignores_the_seed() -> None:
    rng = np.random.default_rng(4)
    deltas = {f"c{i}": rng.normal(0.0, 1.0, size=8) for i in range(5)}
    assert family_maxt(deltas, n_perm=256, seed=0) == family_maxt(
        deltas, n_perm=256, seed=999
    )


def test_monte_carlo_is_used_above_the_enumeration_grid_and_is_seed_stable() -> None:
    rng = np.random.default_rng(5)
    deltas = {f"c{i}": rng.normal(0.0, 1.0, size=20) for i in range(4)}
    first = family_maxt(deltas, n_perm=500, seed=17)
    assert first == family_maxt(deltas, n_perm=500, seed=17)
    assert first != family_maxt(deltas, n_perm=500, seed=18)


def test_a_lone_strong_cell_clears_and_a_lone_weak_one_does_not() -> None:
    strong = np.full(10, 0.5)
    strong[0] = 0.4  # a non-zero spread so t is finite
    weak = np.array([0.01, -0.02, 0.03, -0.01, 0.0, 0.02, -0.03, 0.01, -0.01, 0.0])
    adjusted = family_maxt({"strong": strong, "weak": weak}, n_perm=1024)
    assert adjusted["strong"] <= 0.05
    assert adjusted["weak"] > 0.05


def test_the_family_is_fixed_so_adding_cells_can_only_raise_adjusted_scores() -> None:
    """The multiplicity correction is the whole point: a bigger family is harder."""
    rng = np.random.default_rng(9)
    target = rng.normal(0.4, 0.3, size=10)
    alone = family_maxt({"target": target}, n_perm=1024)["target"]
    crowd = {"target": target}
    crowd.update({f"noise{i}": rng.normal(0.0, 0.3, size=10) for i in range(20)})
    assert family_maxt(crowd, n_perm=1024)["target"] >= alone


def test_a_never_firing_placeholder_keeps_its_slot_and_scores_one() -> None:
    """A cell with too little data stays in the family; it is never dropped."""
    live = np.array([0.3, 0.2, 0.4, 0.1, 0.35, 0.25, 0.3, 0.2, 0.4, 0.15])
    dead = np.full(10, np.nan)
    dead[0] = 0.9  # a single finite unit cannot form a t
    adjusted = family_maxt({"live": live, "dead": dead}, n_perm=1024)
    assert adjusted["dead"] == 1.0
    assert set(adjusted) == {"live", "dead"}


def test_a_family_of_only_placeholders_fires_nothing() -> None:
    adjusted = family_maxt({"a": np.full(4, np.nan), "b": np.full(4, np.nan)}, n_perm=16)
    assert adjusted == {"a": 1.0, "b": 1.0}


def test_mixed_unit_counts_are_refused_because_one_sign_vector_is_shared() -> None:
    with pytest.raises(ValueError, match="same number of units"):
        family_maxt({"a": np.zeros(10), "b": np.zeros(8)}, n_perm=16)


def test_empty_family_is_empty() -> None:
    assert family_maxt({}) == {}
