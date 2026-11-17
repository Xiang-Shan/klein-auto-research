"""The sign-flip max-t selection guard, checked against study 09's published numbers.

`kleinlib.metrology.family_maxt` is a port of the frozen study-08 reference
(`sweeps/rematch_analysis.py`, re-used verbatim by study 09's `sweeps/analysis.py`).
The port is only worth having if it reproduces what those studies published, so the
anchor test feeds it study 09's 42-cell family and compares every adjusted score with
the study's `sweeps/arena_verdicts.tsv` — and with the headline `0/42` its
`claims.lock` records under the `guard` alias.

Studies 08 and 09 are archived (`studies/ARCHIVE.md`).  `fixtures/study09_maxt.json`
freezes the guard's input — one repeat-level mean paired delta per unit, rebuilt from
the committed arena sidecars — together with the published scores and the sha256 of
every source file at the archive commit.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from kleinlib.metrology import family_maxt

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "study09_maxt.json").read_text(encoding="utf-8")
)


def _study09_family() -> dict[str, np.ndarray]:
    return {
        cell: np.array([np.nan if unit is None else unit for unit in units], dtype=float)
        for cell, units in FIXTURE["deltas"].items()
    }


def test_reproduces_every_adjusted_score_study_09_published() -> None:
    deltas = _study09_family()
    assert len(deltas) == 42, "study 09's registered family is 7 challengers x 6 rungs"

    adjusted = family_maxt(deltas, n_perm=FIXTURE["n_perm"], seed=FIXTURE["seed"])

    mismatches = [
        (cell, published, adjusted[cell])
        for cell, published in FIXTURE["p_guard"].items()
        if round(adjusted[cell], 4) != published
    ]
    assert not mismatches, f"adjusted scores drifted from the published table: {mismatches}"


def test_reproduces_the_zero_of_forty_two_recorded_in_the_claims_lock() -> None:
    adjusted = family_maxt(_study09_family(), n_perm=FIXTURE["n_perm"], seed=FIXTURE["seed"])
    cleared = [cell for cell, p in adjusted.items() if p <= FIXTURE["alpha"]]

    assert f"{len(cleared)}/{len(adjusted)}" == FIXTURE["bar1_cleared"] == "0/42"


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
