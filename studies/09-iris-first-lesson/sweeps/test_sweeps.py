"""tests_sweeps.py — the sweep machinery's own tests (study 09).

Run from the STUDY DIRECTORY::

    uv run --locked python -m pytest sweeps/tests_sweeps.py -q

These tests exercise the FROZEN machinery, not the study's results: the selection
guard's arithmetic, the quota scan's nesting and twins discipline, the exact-pairing
guarantee, the floor reduction against `kleinlib.noise_floor`, `ceil3dp`'s
boundaries, every seed's domain, and the RQ4 ceiling-share arithmetic.

They import the sweep modules, which import `families` — so they run against
WHATEVER roster is installed. Assertions that depend on the registered roster size
(7 challengers) SKIP with a named reason when a stand-in roster is loaded, so the
same file is valid both in the study and against a smoke harness.

OUT OF SCOPE, deliberately: the simulation lane's decomposition/identity tests
(irreducible + bias^2 + variance) belong to the separate simulation workstream and
are NOT duplicated here.
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

STUDY_DIR = Path(__file__).resolve().parent.parent
SWEEPS_DIR = Path(__file__).resolve().parent
for _p in (str(STUDY_DIR), str(SWEEPS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import analysis  # noqa: E402
import arena  # noqa: E402
import candidate_floors  # noqa: E402
import families  # noqa: E402
import kseed_floor  # noqa: E402
import metrology_paired  # noqa: E402
import rq0_headroom  # noqa: E402

from kleinlib.noise_floor import summarize_noise  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

SEED_DOMAIN = 2**32
REGISTERED_CHALLENGERS = 7
REGISTERED_RUNGS = (60, 45, 30, 20, 12, 8)
TWINS = "twins102-143"
#: Fixture seed. A test fixture, not a registered study seed — but still in domain.
FIXTURE_SEED = 12345


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _synthetic_pool(n_per_class: int = 40) -> pd.DataFrame:
    """A grouped frame shaped like the hard pair: one 2-row TWIN group, rest singletons."""
    rng = np.random.default_rng(FIXTURE_SEED)
    rows = []
    for cls in (0, 1):
        centre = 1.0 if cls == 0 else 2.0
        for i in range(n_per_class):
            rows.append(
                {
                    "sepal_length_cm": float(centre + rng.normal(0, 0.3)),
                    "sepal_width_cm": float(centre + rng.normal(0, 0.3)),
                    "petal_length_cm": float(centre + rng.normal(0, 0.3)),
                    "petal_width_cm": float(centre + rng.normal(0, 0.3)),
                    arena.TARGET: cls,
                    arena.GROUP: f"row{cls}{i:03d}",
                }
            )
    frame = pd.DataFrame(rows)
    # Pin a 2-row TWIN group inside the virginica class: identical measurements,
    # one shared group id — exactly the hard pair's rows 102/143.
    twin_positions = [len(frame) - 2, len(frame) - 1]
    frame.loc[twin_positions, arena.GROUP] = TWINS
    frame.loc[twin_positions[1], frame.columns[:4]] = frame.loc[
        twin_positions[0], frame.columns[:4]
    ].to_numpy()
    frame = frame.reset_index(drop=True)
    frame["_row"] = frame.index
    return frame


@pytest.fixture(scope="module")
def pool() -> pd.DataFrame:
    return _synthetic_pool()


@pytest.fixture(scope="module")
def geometry(pool: pd.DataFrame):
    """Two repeats of the real geometry over the synthetic pool — all six rungs."""
    declared_dev_rows = set(pool["_row"].iloc[:10])
    return arena.build_geometry(pool, declared_dev_rows, repeats=2, rungs=arena.RUNGS)


# ---------------------------------------------------------------------------
# 1. the selection guard
# ---------------------------------------------------------------------------

def test_flip_enumeration_is_exactly_1024():
    flips = analysis.enumerate_flips(analysis.REPEATS)
    assert analysis.REPEATS == 10
    assert len(flips) == 1024
    assert len(set(flips)) == 1024, "the enumeration must be free of duplicates"
    assert all(len(e) == 10 and set(e) <= {1, -1} for e in flips)


def test_placebo_anchor_vs_anchor_never_fires():
    """Anchor vs anchor gives d == 0 for every repeat; the guard must NOT fire."""
    placebo = {j: 0.0 for j in range(1, 11)}
    assert analysis.t_stat(placebo) == 0.0
    flips = analysis.enumerate_flips()
    live = {("placebo", 60): placebo}
    t_obs = {("placebo", 60): analysis.t_stat(placebo)}
    p = analysis.sign_flip_guard(live, t_obs, flips)
    assert p[("placebo", 60)] == 1.0
    assert not (p[("placebo", 60)] <= analysis.ALPHA)


def test_negating_d_flips_the_t_sign():
    dbar = {j: v for j, v in enumerate([0.02, -0.01, 0.03, 0.05, 0.0, 0.01,
                                        -0.02, 0.04, 0.02, 0.01], start=1)}
    neg = {j: -v for j, v in dbar.items()}
    assert math.isclose(analysis.t_stat(neg), -analysis.t_stat(dbar), rel_tol=1e-12)


def test_zero_sd_t_is_signed_infinity():
    assert analysis.t_stat({j: 0.05 for j in range(1, 11)}) == float("inf")
    assert analysis.t_stat({j: -0.05 for j in range(1, 11)}) == analysis.NEVER
    assert analysis.t_stat({1: 0.05}) == analysis.NEVER  # < 2 repeats


def test_placeholder_cells_never_fire():
    """A -inf placeholder occupies its guard slot and scores 1.0 — it cannot clear."""
    flips = analysis.enumerate_flips()
    live = {("live", 60): {j: 0.02 * j for j in range(1, 11)}}
    t_obs = {("live", 60): analysis.t_stat(live[("live", 60)]),
             ("dead", 8): analysis.NEVER}
    p = analysis.sign_flip_guard(live, t_obs, flips)
    assert p[("dead", 8)] == 1.0
    assert not (p[("dead", 8)] <= analysis.ALPHA)
    # ... and it is still a MEMBER of the family, not a dropped cell.
    assert set(p) == {("live", 60), ("dead", 8)}


def test_guard_family_is_the_fixed_full_grid():
    cells = analysis.guard_cells()
    assert len(cells) == len(families.CHALLENGERS) * len(arena.RUNGS)
    assert len(set(cells)) == len(cells)
    if len(families.CHALLENGERS) != REGISTERED_CHALLENGERS:
        pytest.skip(
            f"stand-in roster ({len(families.CHALLENGERS)} challengers); the "
            "registered 7 x 6 = 42 assertion runs against the installed roster"
        )
    assert len(cells) == 42


# ---------------------------------------------------------------------------
# 2. nesting + the twins discipline
# ---------------------------------------------------------------------------

def test_quota_subsets_are_nested_across_rungs(geometry):
    partitions, _ = geometry
    rungs = sorted(arena.RUNGS)  # ascending
    for (j, k), part in partitions.items():
        for small, big in zip(rungs, rungs[1:], strict=False):
            s = set(part["subsets"][small]["_row"])
            b = set(part["subsets"][big]["_row"])
            assert s <= b, f"rung {small} not nested inside {big} at repeat {j} fold {k}"


def test_twins_never_split_by_a_fold(geometry):
    partitions, _ = geometry
    for (j, k), part in partitions.items():
        dev_twins = set(part["dev"].loc[part["dev"][arena.GROUP] == TWINS, "_row"])
        assert len(dev_twins) in (0, 2), (
            f"twins straddle the fold boundary at repeat {j} fold {k}"
        )


def test_twins_never_split_by_a_quota_subset(geometry):
    partitions, _ = geometry
    for (j, k), part in partitions.items():
        for n, sub in part["subsets"].items():
            got = set(sub.loc[sub[arena.GROUP] == TWINS, "_row"])
            assert len(got) in (0, 2), (
                f"twins straddle the subset boundary at repeat {j} fold {k} rung {n}"
            )


def test_twins_never_split_by_a_metrology_redraw(pool):
    for draw in range(1, metrology_paired.DRAWS + 1):
        seed = metrology_paired.DRAW_SEED_BASE + draw
        train, evaluation = metrology_paired.draw_partitions(pool, seed)
        in_train = set(train.loc[train[arena.GROUP] == TWINS, "_row"])
        in_eval = set(evaluation.loc[evaluation[arena.GROUP] == TWINS, "_row"])
        assert not (in_train and in_eval), f"twins straddle metrology draw {draw}"
        assert len(in_train) in (0, 2) and len(in_eval) in (0, 2)


def test_quota_subset_takes_whole_groups_only(geometry, pool):
    partitions, _ = geometry
    sizes = pool.groupby(arena.GROUP).size().to_dict()
    for (_j, _k), part in partitions.items():
        for _n, sub in part["subsets"].items():
            for gid, count in sub.groupby(arena.GROUP).size().items():
                assert count == sizes[gid], f"group {gid} was split by the quota scan"


def test_realized_n_never_exceeds_the_nominal_rung(geometry):
    _partitions, table = geometry
    for _, row in table.iterrows():
        assert int(row["n_actual"]) <= int(row["rung"]), (
            "the nominal-rung qualifier exists because n_actual <= nominal; a "
            "realized subset larger than its rung would break the claim wording"
        )


# ---------------------------------------------------------------------------
# 3. exact pairing
# ---------------------------------------------------------------------------

def test_every_family_is_served_byte_identical_rows(geometry):
    """The (train, eval) lookup ignores the family — pairing is by construction."""
    partitions, table = geometry
    roster = [families.ANCHOR, *families.CHALLENGERS, *families.CONTROLS]
    by_cell = {
        (int(r["repeat"]), int(r["fold"]), int(r["rung"])): str(r["rows_sha256"])
        for _, r in table.iterrows()
    }
    for (j, k), part in partitions.items():
        for n, sub in part["subsets"].items():
            hashes = set()
            dev_hashes = set()
            for _family in roster:
                # the exact lookup make_trial_fn performs, once per family
                train = partitions[(j, k)]["subsets"][n]
                dev = partitions[(j, k)]["dev"]
                hashes.add(families.positions_sha256(sorted(int(r) for r in train["_row"])))
                dev_hashes.add(families.positions_sha256(sorted(int(r) for r in dev["_row"])))
            assert len(hashes) == 1, f"train rows differ by family at {(j, k, n)}"
            assert len(dev_hashes) == 1, f"eval rows differ by family at {(j, k, n)}"
            assert hashes.pop() == by_cell[(j, k, n)] == families.positions_sha256(
                sorted(int(r) for r in sub["_row"])
            )


def test_positions_sha256_of_empty_is_the_empty_string_hash():
    """08's convention; the coda manifest depends on it in BOTH branches."""
    assert families.positions_sha256([]) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


# ---------------------------------------------------------------------------
# 4. floor math
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "values",
    [
        [0.01, 0.02, 0.03, 0.04, 0.05],
        [-0.004, 0.011, 0.0, 0.031, -0.012, 0.008],
        [0.02] * 5,
        [0.000112, 0.030589, 0.001, 0.0044, 0.019],
    ],
)
def test_paired_stats_matches_kleinlib_summarize_noise(values):
    mine = candidate_floors.paired_stats(values)
    theirs = summarize_noise(values)
    assert mine["k"] == theirs.k
    assert mine["std"] == theirs.std                       # both statistics.stdev, ddof=1
    assert mine["range"] == theirs.value_range             # both max - min
    assert mine["mean"] == theirs.mean
    assert mine["floor"] == theirs.suggested_minimum_delta  # max(2*std, range/2)
    # and the study's own restatement of the rule agrees
    assert mine["floor"] == max(2.0 * statistics.stdev(values), (max(values) - min(values)) / 2.0)


def test_floor_is_location_invariant(_shift=0.37):
    """The blindness clause in arithmetic: shifting every d leaves floor_c unchanged."""
    values = [-0.004, 0.011, 0.0, 0.031, -0.012, 0.008]
    shifted = [v + _shift for v in values]
    assert math.isclose(
        candidate_floors.paired_stats(values)["floor"],
        candidate_floors.paired_stats(shifted)["floor"],
        rel_tol=1e-12,
    )


def test_cross_check_refuses_on_disagreement(monkeypatch):
    values = [0.01, 0.02, 0.03]
    mine = dict(candidate_floors.paired_stats(values))
    mine["std"] += 1.0
    with pytest.raises(SystemExit, match="REFUSING TO WRITE"):
        candidate_floors.cross_check(values, mine)


def _write_floor_table(path: Path, floor_value: float) -> None:
    rows = [{
        "family": families.ANCHOR, "role": "anchor", "stat_kind": "marginal-resplit",
        "k": 20, "mean_d": repr(0.0465253333333333), "std_d": repr(0.02897131468078957),
        "range_d": repr(0.057006), "floor_c": repr(0.05794262936157914),
        "floor_rule": "2*std (MARGINAL)",
    }]
    rows += [{
        "family": f, "role": "challenger", "stat_kind": "paired-comparison",
        "k": 20, "mean_d": repr(-0.006764666666666666),
        "std_d": repr(0.005922261420549868), "range_d": repr(0.011525),
        "floor_c": repr(floor_value), "floor_rule": "max(2*std, range/2)",
    } for f in families.CHALLENGERS]
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)


def test_full_precision_floor_survives_the_analysis_reader(tmp_path, monkeypatch):
    """Bar-2 compares mean_gain to floor_c — the read must be ROUND-TRIP exact.

    pandas' DEFAULT csv float parser is not: 0.011844522841099736 comes back as
    0.0118445228410997 (1-2 ULP off). Every reader of a table this pipeline wrote
    pins `float_precision="round_trip"`; this test is what keeps that pin in place.
    """
    value = 0.011844522841099736
    _write_floor_table(tmp_path / "candidate_floors.tsv", value)
    monkeypatch.setattr(analysis, "SWEEPS_DIR", tmp_path)
    floors = analysis.load_candidate_floors()
    for fam in families.CHALLENGERS:
        assert floors[fam] == value, "floor_c lost precision on the way into Bar-2"
    assert analysis.FLOAT_PRECISION == "round_trip"


def test_full_precision_floor_survives_the_rq0_reader(tmp_path):
    value = 0.011844522841099736
    _write_floor_table(tmp_path / "candidate_floors.tsv", value)
    df = rq0_headroom.load_floors(tmp_path / "candidate_floors.tsv")
    got = df[df["role"] == "challenger"]["floor_c"].astype(float).iloc[0]
    assert float(got) == value
    assert rq0_headroom.FLOAT_PRECISION == "round_trip"
    assert candidate_floors.FLOAT_PRECISION == "round_trip"


# ---------------------------------------------------------------------------
# 5. ceil3dp
# ---------------------------------------------------------------------------

CEIL_IMPLS = (
    ("arena", arena.ceil_3dp),
    ("candidate_floors", candidate_floors.ceil_3dp),
    ("rq0_headroom", rq0_headroom.ceil_3dp),
)


@pytest.mark.parametrize("name,fn", CEIL_IMPLS)
@pytest.mark.parametrize(
    "exact", [0.0, 0.001, 0.005, 0.007, 0.032, 0.046, 0.062, 0.147, 0.252, 0.5, 0.999]
)
def test_ceil3dp_leaves_exact_boundaries_alone(name, fn, exact):
    """An exact 3dp value must NOT be bumped up — that is what the 1e-12 slack buys."""
    assert fn(exact) == pytest.approx(exact, abs=1e-15), name


@pytest.mark.parametrize("name,fn", CEIL_IMPLS)
def test_ceil3dp_rounds_up_off_boundary(name, fn):
    assert fn(0.0320001) == pytest.approx(0.033, abs=1e-15), name
    assert fn(0.0001) == pytest.approx(0.001, abs=1e-15), name
    assert fn(0.03201) == pytest.approx(0.033, abs=1e-15), name
    assert fn(0.1234) == pytest.approx(0.124, abs=1e-15), name


def test_all_ceil3dp_implementations_agree():
    probes = [0.0, 1e-9, 0.0005, 0.001, 0.005, 0.0321, 0.032, 0.06, 0.147, 0.2519, 1.0]
    for x in probes:
        got = {fn(x) for _n, fn in CEIL_IMPLS}
        assert len(got) == 1, f"ceil_3dp copies disagree at {x}: {got}"


# ---------------------------------------------------------------------------
# 6. seed domains (claim 08#C11 — the 2**32-1 trap bit BOTH prior studies)
# ---------------------------------------------------------------------------

def test_every_literal_seed_is_in_domain():
    literals = {
        "metrology DRAW_SEED_BASE": metrology_paired.DRAW_SEED_BASE,
        "arena REPEAT_SEED_BASE": arena.REPEAT_SEED_BASE,
        "arena SUBSET_SEED_BASE": arena.SUBSET_SEED_BASE,
        "analysis SENS_SEED": analysis.SENS_SEED,
    }
    for name, seed in literals.items():
        assert 0 <= seed < SEED_DOMAIN, name
    for seed in kseed_floor.SEEDS:
        assert 0 <= seed < SEED_DOMAIN


def test_every_derived_seed_is_in_domain():
    for draw in range(1, metrology_paired.DRAWS + 1):
        assert 0 <= metrology_paired.DRAW_SEED_BASE + draw < SEED_DOMAIN
    for j in range(1, arena.REPEATS + 1):
        assert 0 <= arena.REPEAT_SEED_BASE + j < SEED_DOMAIN
        for k in range(arena.FOLDS):
            assert 0 <= arena.SUBSET_SEED_BASE + 100 * j + k < SEED_DOMAIN
    # the rung never enters a seed formula — assert that, so a future edit that
    # makes a seed rung-dependent has to face this test.
    for n in arena.RUNGS:
        assert n < SEED_DOMAIN
    assert (
        arena.SUBSET_SEED_BASE + 100 * arena.REPEATS + arena.FOLDS - 1
    ) == 2026100303, "the registered maximum derived subset seed"


def test_registered_seed_literals_are_the_09_namespace():
    assert metrology_paired.DRAW_SEED_BASE + 1 == 2026099101
    assert metrology_paired.DRAW_SEED_BASE + metrology_paired.DRAWS == 2026099120
    assert arena.REPEAT_SEED_BASE + 1 == 2026099201
    assert arena.REPEAT_SEED_BASE + arena.REPEATS == 2026099210
    assert arena.SUBSET_SEED_BASE == 2026099300
    assert analysis.SENS_SEED == 2026101500
    assert kseed_floor.SEEDS == (0, 1, 2, 3, 4)


def test_declared_split_seed_is_in_domain_and_registered():
    contract = load_contract(STUDY_DIR)
    split = contract["data"]["split"]
    assert 0 <= int(split["seed"]) < SEED_DOMAIN
    assert split["kind"] == "group"
    if int(split["seed"]) != 20260912:
        pytest.skip(f"stand-in contract (split seed {split['seed']})")
    assert float(split["development_size"]) == 0.20
    assert float(split["test_size"]) == 0.20


def test_sensitivity_seed_is_disjoint_from_every_arena_seed():
    """SENS_SEED was RE-REGISTERED to 2026101500 pre-consult after the drafted
    value collided with the subset seed at (j=2, k=0). This test now pins the
    fix: the seed is outside every subset and repeat seed, and the docstring
    keeps the near-miss auditable."""
    subset_seeds = {arena.SUBSET_SEED_BASE + 100 * j + k for j in range(1, 11) for k in range(0, 10)}
    repeat_seeds = {arena.REPEAT_SEED_BASE + j for j in range(1, 11)}
    assert analysis.SENS_SEED == 2026101500
    assert analysis.SENS_SEED not in subset_seeds
    assert analysis.SENS_SEED not in repeat_seeds
    assert "2026101500" in analysis.__doc__ and "2026099500" in analysis.__doc__


# ---------------------------------------------------------------------------
# 7. RQ4 ceiling-share arithmetic
# ---------------------------------------------------------------------------

def _aux_frame(records: list[tuple[str, int, int, int, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [dict(zip(arena.AUX_COLUMNS, (*r, ""), strict=True)) for r in records]
    )


def test_rq4_ceiling_share_arithmetic():
    #  fam A: 2 of 3 defined val_auc at the ceiling, one NA (OUT of the denominator).
    #  The two near-1 values straddle CEILING_TOL on purpose: 1-1e-15 counts,
    #  1-1e-11 does not.
    #  fam B: 0 of 2 at the ceiling.
    records = [
        ("famA", 60, 1, 0, "val_auc", "1.0"),
        ("famA", 60, 1, 1, "val_auc", "0.999999999999999"),
        ("famA", 60, 1, 2, "val_auc", "0.99999999999"),
        ("famA", 60, 1, 3, "val_auc", "NA"),
        ("famB", 60, 1, 0, "val_auc", "0.8"),
        ("famB", 60, 1, 1, "val_auc", "0.75"),
        ("famA", 60, 1, 0, "val_logloss", "0.10"),
        ("famA", 60, 1, 1, "val_logloss", "0.20"),
        ("famB", 60, 1, 0, "val_logloss", "0.50"),
    ]
    aux = _aux_frame(records)
    brier = {
        ("famA", 60, 1, 0): 0.01, ("famA", 60, 1, 1): 0.03,
        ("famB", 60, 1, 0): 0.20, ("famB", 60, 1, 1): 0.30,
    }
    sat = analysis.rq4_saturation(aux, brier, rungs=(60,), metrics=("val_auc",))
    a = sat[(sat["family"] == "famA") & (sat["metric"] == "val_auc")].iloc[0]
    assert int(a["n_evals"]) == 3 and int(a["n_na"]) == 1
    assert int(a["n_ceiling"]) == 2          # 1-1e-11 is NOT within CEILING_TOL
    assert float(a["ceiling_share"]) == pytest.approx(2 / 3)
    assert float(a["mean_val_brier"]) == pytest.approx(0.02)
    assert float(a["mean_val_logloss"]) == pytest.approx(0.15)

    b = sat[(sat["family"] == "famB") & (sat["metric"] == "val_auc")].iloc[0]
    assert int(b["n_ceiling"]) == 0 and float(b["ceiling_share"]) == 0.0

    pooled = sat[sat["scope"] == "pooled"].iloc[0]
    assert int(pooled["n_evals"]) == 5 and int(pooled["n_na"]) == 1
    assert float(pooled["ceiling_share"]) == pytest.approx(2 / 5)


def test_rq4_all_na_leaves_the_share_undefined_not_zero():
    aux = _aux_frame([("famA", 8, 1, 0, "val_auc", "NA"),
                      ("famA", 8, 1, 1, "val_auc", "NA")])
    sat = analysis.rq4_saturation(aux, {}, rungs=(8,), metrics=("val_auc",))
    row = sat[sat["scope"] == "family"].iloc[0]
    assert int(row["n_evals"]) == 0 and int(row["n_na"]) == 2
    assert row["ceiling_share"] == "", "an undefined share is blank, never 0.0"


def test_rq4_empty_aux_is_an_empty_table_not_a_crash():
    sat = analysis.rq4_saturation(pd.DataFrame(columns=list(arena.AUX_COLUMNS)), {})
    assert sat.empty


# ---------------------------------------------------------------------------
# aux-metric degeneracy (the group-quota failure mode the sweep must survive)
# ---------------------------------------------------------------------------

def test_single_class_eval_writes_na_not_a_crash():
    y = np.zeros(8, dtype=int)
    p = np.linspace(0.01, 0.4, 8)
    got = arena.aux_metrics(y, p)
    for name in ("val_auc", "val_pr_auc", "cal_intercept", "cal_slope"):
        assert got[name][0] is None and got[name][1] == "single-class-eval"
    assert got["val_accuracy"][0] == 1.0
    assert got["val_f1"][0] == 0.0          # zero_division=0, defined and honest
    assert got["val_logloss"][0] > 0.0


def test_eps_clip_touches_logloss_but_never_brier():
    """A 0/1 probability must not make log loss infinite — and must not move Brier."""
    y = np.array([0, 1, 0, 1])
    p = np.array([0.0, 1.0, 0.0, 1.0])
    got = arena.aux_metrics(y, p)
    assert math.isfinite(got["val_logloss"][0])
    assert got["val_logloss"][0] == pytest.approx(-math.log(1.0 - arena.EPS), abs=1e-9)
    from sklearn.metrics import brier_score_loss

    assert brier_score_loss(y, p) == 0.0     # RAW probabilities, no clip


# ---------------------------------------------------------------------------
# the mechanical coda branch
# ---------------------------------------------------------------------------

def _verdicts(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_coda_branch_b_when_no_bar2_cell_at_rung_60():
    v = _verdicts([
        {"family": families.CHALLENGERS[0], "rung": 60, "t": 1.0, "bar2_actionable": False},
        {"family": families.CHALLENGERS[0], "rung": 8, "t": 9.0, "bar2_actionable": True},
    ])
    m = analysis.build_coda_manifest(v, anchor_dev=0.0294, delta=0.029, gaps_at_60={})
    assert m["branch"] == "B"
    assert m["families"] == {"coda_primary": families.ANCHOR, "coda_challenger": None}
    assert m["bands"]["challenger"] is None
    assert m["bands"]["primary"]["center"] == 0.0294
    assert m["bands"]["primary"]["half_width"] == pytest.approx(0.058)
    assert m["train_positions"] == []
    assert m["positions_sha256"] == families.positions_sha256([])


def test_coda_branch_a_picks_the_largest_t_at_rung_60():
    f0, f1 = families.CHALLENGERS[0], families.CHALLENGERS[1]
    v = _verdicts([
        {"family": f0, "rung": 60, "t": 2.5, "bar2_actionable": True},
        {"family": f1, "rung": 60, "t": 7.5, "bar2_actionable": True},
        {"family": f0, "rung": 8, "t": 99.0, "bar2_actionable": True},
    ])
    gaps = {f0: [0.01, 0.02, 0.03], f1: [0.00, 0.05, 0.10, 0.20]}
    m = analysis.build_coda_manifest(v, anchor_dev=0.03, delta=0.01, gaps_at_60=gaps)
    assert m["branch"] == "A"
    assert m["families"]["coda_challenger"] == f1
    assert m["selection"]["t"] == pytest.approx(7.5)
    band = m["bands"]["challenger"]
    assert band["kind"] == "interval" and band["lo"] <= band["hi"]
    assert band["convention"] == "g_sealed = sealed_primary - sealed_challenger"
    assert m["train_positions"] == [] and m["positions_sha256"] == families.positions_sha256([])


def test_coda_branch_a_ties_break_by_registry_order():
    f0, f1 = families.CHALLENGERS[0], families.CHALLENGERS[1]
    v = _verdicts([
        {"family": f1, "rung": 60, "t": 4.0, "bar2_actionable": True},
        {"family": f0, "rung": 60, "t": 4.0, "bar2_actionable": True},
    ])
    gaps = {f0: [0.01, 0.02, 0.03], f1: [0.01, 0.02, 0.03]}
    m = analysis.build_coda_manifest(v, anchor_dev=0.03, delta=0.01, gaps_at_60=gaps)
    assert m["families"]["coda_challenger"] == f0, "ties break by REGISTRY order"


# ---------------------------------------------------------------------------
# headroom / RQ0 arithmetic
# ---------------------------------------------------------------------------

def test_headroom_is_numerator_over_bar_with_ideal_zero():
    assert rq0_headroom.headroom(0.0294, 0.029) == pytest.approx(0.0294 / 0.029)
    assert rq0_headroom.headroom(0.02, 0.04) < 1.0      # measurement-closed
    assert rq0_headroom.headroom(0.05, 0.04) >= 1.0     # not arithmetically excluded


def test_headroom_refuses_a_non_positive_bar():
    with pytest.raises(SystemExit):
        rq0_headroom.headroom(0.03, 0.0)


def test_delta_may_be_raised_but_never_lowered():
    floors = pd.DataFrame([
        {"family": families.CHALLENGERS[0], "role": "challenger", "stat_kind":
         "paired-comparison", "k": 20, "mean_d": 0.0, "floor_c": 0.0284},
    ])
    assert "AGREES" in rq0_headroom.check_delta(floors, 0.029)
    assert "RAISED" in rq0_headroom.check_delta(floors, 0.05)
    with pytest.raises(SystemExit, match="never be lowered"):
        rq0_headroom.check_delta(floors, 0.01)


# ---------------------------------------------------------------------------
# registered-constant guards
# ---------------------------------------------------------------------------

def test_registered_arena_constants():
    assert arena.RUNGS == REGISTERED_RUNGS
    assert arena.REPEATS == 10 and arena.FOLDS == 4
    assert arena.DELTA_FLOOR == 0.005
    assert arena.CEILING_CLOSED_M == 0.06
    assert arena.EPS == 1e-6
    assert set(arena.AUX_METRICS) == {
        "val_logloss", "val_auc", "val_pr_auc", "val_accuracy", "val_f1",
        "cal_intercept", "cal_slope",
    }
    assert metrology_paired.DRAWS == 20
    assert metrology_paired.DRAW_DEV_FRACTION == 0.25
    assert analysis.CODA_BRANCH_RUNG == 60
    assert analysis.ALPHA == 0.05


def test_delta_n_uses_the_floor_of_the_floor():
    """delta_n = max(ceil3dp(2*sd), DELTA_FLOOR) — the 0.005 is a registered constant."""
    tiny = [0.02, 0.02, 0.020000001, 0.02]
    sd = statistics.stdev(tiny)
    assert max(arena.ceil_3dp(2.0 * sd), arena.DELTA_FLOOR) == arena.DELTA_FLOOR
    wide = [0.0, 0.10, 0.05, 0.20]
    assert max(arena.ceil_3dp(2.0 * statistics.stdev(wide)), arena.DELTA_FLOOR) > arena.DELTA_FLOOR


def test_roster_shape_and_disjointness():
    names = [families.ANCHOR, *families.CHALLENGERS, *families.CONTROLS]
    assert len(set(names)) == len(names), "a family may not hold two roles"
    assert families.ANCHOR not in families.CHALLENGERS
    assert families.ANCHOR not in families.CONTROLS
    assert not set(families.CHALLENGERS) & set(families.CONTROLS)
    assert analysis.CONTROL_WORSENING in families.CONTROLS
    if len(families.CHALLENGERS) != REGISTERED_CHALLENGERS:
        pytest.skip(f"stand-in roster ({len(families.CHALLENGERS)} challengers)")
    assert families.ANCHOR == "anchor_lda4"
    assert families.CHALLENGERS == (
        "lda_shrinkage", "qda", "logit_l2", "knn_tuned", "svm_rbf_platt", "hgbt", "tabpfn"
    )
    assert families.CONTROLS == ("lda_petal", "lda_sepal")
    assert families.ESTIMATOR_SEED == 20260912
    assert all(families.MIN_RUNG[f] == 8 for f in families.CHALLENGERS)
    assert all(families.eligible(f, n) for f in families.CHALLENGERS for n in arena.RUNGS)


def test_parse_rungs_only_subsets_the_registered_ladder():
    assert arena.parse_rungs(None) == arena.RUNGS
    assert arena.parse_rungs("12,60") == (60, 12), "registered order, always"
    with pytest.raises(SystemExit):
        arena.parse_rungs("61")
    with pytest.raises(SystemExit):
        arena.parse_rungs("")
