"""The three floor recipes, their estimands, and the CRN guarantee."""

from __future__ import annotations

import math

import numpy as np
import pytest

from kleinlib.metrology import (
    ESTIMANDS,
    RECIPE_ESTIMAND,
    RECIPES,
    FloorEstimate,
    paired_bootstrap,
    seed_sweep,
    split_lottery,
)


def test_every_recipe_declares_the_estimand_it_measures() -> None:
    assert set(RECIPE_ESTIMAND) == set(RECIPES)
    assert set(RECIPE_ESTIMAND.values()) <= set(ESTIMANDS)


def test_seed_sweep_measures_fit_noise_and_never_becomes_the_bar() -> None:
    values = {1: 0.50, 2: 0.52, 3: 0.48, 4: 0.51, 5: 0.49}
    floor = seed_sweep(lambda s: values[s], [1, 2, 3, 4, 5])

    assert (floor.recipe, floor.estimand) == ("seed-sweep", "fit-noise")
    assert floor.k == 5
    assert floor.values == (0.50, 0.52, 0.48, 0.51, 0.49)
    assert floor.seeds == (1, 2, 3, 4, 5)
    assert floor.mean == pytest.approx(0.50)
    assert floor.value_range == pytest.approx(0.04)
    # A seed-only spread is provenance about the fit, not the keep bar.
    assert floor.block_key == "fit_noise"


def test_split_lottery_measures_the_marginal_resplit_spread() -> None:
    floor = split_lottery(lambda s: 0.6 + 0.01 * (s % 3), [11, 12, 13, 14])
    assert (floor.recipe, floor.estimand) == ("split-lottery", "marginal-resplit")
    assert floor.block_key == "noise_floor"


def test_suggested_minimum_delta_is_the_schema_three_bar() -> None:
    # On the k a Phase 0 can afford (k <= 16) the 2*std term always binds.
    small = split_lottery(lambda s: {1: 0.0, 2: 0.0, 3: 0.0, 4: 1.0}[s], [1, 2, 3, 4])
    assert small.suggested_minimum_delta == pytest.approx(
        max(2 * small.std, small.value_range / 2)
    )
    assert small.suggested_minimum_delta == pytest.approx(2 * small.std)

    # A 20-draw lottery with one wild draw: the range takes over, and the bar
    # does not shrink just because 19 of 20 draws happened to agree.
    lottery = split_lottery(lambda s: 1.0 if s == 20 else 0.0, range(1, 21))
    assert lottery.suggested_minimum_delta == pytest.approx(lottery.value_range / 2)
    assert lottery.suggested_minimum_delta > 2 * lottery.std


def test_a_floor_needs_at_least_three_replicates() -> None:
    with pytest.raises(ValueError, match="k >= 3"):
        seed_sweep(lambda s: float(s), [1, 2])


def test_repeated_seeds_are_refused() -> None:
    with pytest.raises(ValueError, match="distinct"):
        seed_sweep(lambda s: float(s), [1, 1, 2])


def test_non_finite_replicate_is_refused() -> None:
    with pytest.raises(ValueError, match="finite"):
        seed_sweep(lambda s: math.nan if s == 2 else 1.0, [1, 2, 3])


def test_floor_estimate_refuses_an_unknown_recipe_or_estimand() -> None:
    with pytest.raises(ValueError, match="recipe"):
        FloorEstimate("grid-search", "fit-noise", 3, 0.0, 0.0, 0.0, (0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="estimand"):
        FloorEstimate("seed-sweep", "vibes", 3, 0.0, 0.0, 0.0, (0.0, 0.0, 0.0))


def test_as_noise_floor_round_trips_into_the_study_yaml_block() -> None:
    from kleinlib.noise_floor import yaml_block

    floor = split_lottery(lambda s: 0.1 * s, [1, 2, 3, 4])
    block = yaml_block("primary", floor.as_noise_floor(), source="sweeps/x.tsv")
    assert "minimum_delta:" in block
    assert f"{floor.std:.6g}" in block


# --------------------------------------------------------------------------
# paired_bootstrap: common random numbers by construction
# --------------------------------------------------------------------------


def test_paired_bootstrap_measures_the_paired_comparison_estimand() -> None:
    rng = np.random.default_rng(7)
    a = rng.normal(0.20, 0.05, size=400)
    b = a + 0.01  # a constant per-row gap: the difference has (almost) no spread
    floor = paired_bootstrap(a, b, n_boot=200, seed=3)
    assert (floor.recipe, floor.estimand) == ("paired-bootstrap", "paired-comparison")
    assert floor.k == 200
    assert floor.mean == pytest.approx(-0.01, abs=1e-12)
    assert floor.std == pytest.approx(0.0, abs=1e-12)
    assert floor.block_key == "noise_floor"


def test_common_random_numbers_are_structural_not_optional() -> None:
    """The paired floor must be far tighter than two independent resamples.

    Two heavily correlated candidates differ by very little row-to-row; an
    UNpaired bootstrap (two independent index draws) would inherit each
    series' own marginal spread and report a floor an order of magnitude too
    wide.  There is no argument that switches this off — one index vector is
    drawn per replicate and applied to both series.
    """
    rng = np.random.default_rng(11)
    a = rng.normal(0.30, 0.10, size=500)
    b = a + rng.normal(0.0, 0.002, size=500)

    paired = paired_bootstrap(a, b, n_boot=400, seed=5)

    unpaired_rng = np.random.default_rng(5)
    n = a.size
    unpaired = [
        float(a[unpaired_rng.integers(0, n, n)].mean() - b[unpaired_rng.integers(0, n, n)].mean())
        for _ in range(400)
    ]
    assert paired.std < float(np.std(unpaired, ddof=1)) / 10


def test_paired_bootstrap_is_deterministic_for_a_seed() -> None:
    a = np.linspace(0.0, 1.0, 50)
    b = np.linspace(0.1, 0.9, 50)
    first = paired_bootstrap(a, b, n_boot=64, seed=99)
    second = paired_bootstrap(a, b, n_boot=64, seed=99)
    assert first.values == second.values
    assert paired_bootstrap(a, b, n_boot=64, seed=100).values != first.values


def test_paired_bootstrap_accepts_a_non_mean_statistic_on_aligned_resamples() -> None:
    a = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    b = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    seen: list[tuple[int, int]] = []

    def statistic(left: np.ndarray, right: np.ndarray) -> float:
        seen.append((left.size, right.size))
        # Identical inputs: the SAME index vector reached both series.
        assert np.array_equal(left, right)
        return float(np.median(left) - np.median(right))

    floor = paired_bootstrap(a, b, n_boot=8, seed=1, statistic=statistic)
    assert len(seen) == 8
    assert floor.std == 0.0


def test_unpaired_lengths_are_refused_as_the_wrong_estimand() -> None:
    with pytest.raises(ValueError, match="SAME rows"):
        paired_bootstrap(np.zeros(10), np.zeros(9))


def test_paired_bootstrap_refuses_non_finite_rows() -> None:
    with pytest.raises(ValueError, match="finite"):
        paired_bootstrap(np.array([0.0, np.nan, 1.0]), np.zeros(3))
