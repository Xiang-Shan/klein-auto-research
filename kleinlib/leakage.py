"""Clean-room split and eval-harness audit — DATA-gate checklist rows 3 and 4.

Mechanizes the two mechanizable rows of the data card's clean-room leakage
checklist (`.claude/skills/klein/references/data-gate-protocol.md`): split
contamination and eval-harness sanity.  Rows 1-2 (target leakage, lookahead)
stay judgment calls read out of ``prepare.py`` plus the profile — no code can
audit intent.

Contract-driven and hope-free: the audit reads the prepared artifact and the
``study.yaml`` declarations, never ``program.md``.  Checks:

- **split-reproduces** — the declared ``data.split`` block re-materializes
  through :func:`kleinlib.data.three_way_split` twice, identically, covering
  every row exactly once.
- **duplicate-rows** — full-row content hashes must not straddle partitions:
  a memorized twin of a sealed row is contamination, not skill.
- **group-overlap** (``kind: group`` only) — exact ids are disjoint by
  construction once the split reproduces, so this compares *normalized* ids
  (``strip().casefold()``): the same entity under a dirty key (``"G7"`` vs
  ``"g7 "``) is precisely the leak a by-construction split cannot see.
- **metric-direction / constant-chance / shuffled-chance** (per track) — the
  contract's metric direction must match the canonical registry (in the SCALAR
  metric family — ``task_type: scalar``, or its schema-2 spelling
  ``simulation`` — a custom metric's declared direction is accepted as-is), and two
  no-information predictors — the train-target mean, and a label shuffle —
  must score at chance on the development partition.  A "shuffled" predictor
  scoring far from chance means the harness is showing it the answers.

**Index-table mode** (``--index``) audits the same row-3 contaminations for a
modality whose items are not rows of a frame — images, sequences, graphs, text.
The table is ``id, group?, time?, split``: the index IS the realized split, so
this mode does not re-derive it, and instead checks that no id straddles
partitions, no normalized group id crosses them, and (for a declared time
split) no partition looks ahead.  Row 4 needs a target and features an index
does not carry, so its chance rows report N/A with that reason while
metric-direction still runs off the contract.

Simulation studies with a REAL split kind (random/group/time) audit like
regression studies; ``kind: none`` has no partitions, so checks report N/A.
The audit's chance scorers are deliberately **unweighted** — they test that
the harness carries no label information, not the study's exact
exposure-weighted value.

CLI (one ``[OK]``/``[FAIL]`` line per check; any FAIL is a BLOCKER at the
DATA gate and the exit code is 1)::

    uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>
    uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study <dir>
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_gamma_deviance,
    mean_poisson_deviance,
    mean_tweedie_deviance,
)

from .contract import task_family
from .data import RANDOM_SEED, load_prepared, three_way_split
from .eval import (
    _METRIC_SPECS,
    DEVIANCE_METRICS,
    _classification_metric_values,
    get_metric_spec,
)
from .workflow import Check, WorkflowError, load_contract, normalize_tracks, resolve_study

__all__ = [
    "CHANCE_ANCHORS",
    "INDEX_OPTIONAL_COLUMNS",
    "INDEX_PARTITIONS",
    "INDEX_REQUIRED_COLUMNS",
    "audit_index",
    "audit_split",
    "main",
]

#: Metrics with a known absolute no-skill value.  Anchor-less metrics use the
#: relative rule instead: shuffled must not decisively beat the constant baseline.
CHANCE_ANCHORS: dict[str, float] = {"val_auc": 0.5, "val_r2": 0.0}

#: ``(X_train, y_train_shuffled, X_development) -> scores`` — the seam for
#: auditing a study's own prediction path against shuffled labels.  The default
#: ignores the features and scores a seeded permutation of the development target.
ShuffledPredictor = Callable[[pd.DataFrame, pd.Series, pd.DataFrame], Any]

_PARTITION_PAIRS = (("train", "development"), ("train", "test"), ("development", "test"))

#: Why the chance-level rows report N/A when there is no scorable partition.
NO_PARTITION_REASON = "N/A — split kind 'none': no development partition to score"

#: The split index table's schema (``--index`` mode).  ``id`` names the item —
#: an image file, a sequence, a graph, a document — and ``split`` names its
#: realized partition; ``group`` carries the entity a group policy protects and
#: ``time`` the timestamp a time split orders by.
INDEX_REQUIRED_COLUMNS: tuple[str, ...] = ("id", "split")
INDEX_OPTIONAL_COLUMNS: tuple[str, ...] = ("group", "time")

#: Partition labels the ``split`` column may carry, in ladder order.
INDEX_PARTITIONS: tuple[str, ...] = ("train", "development", "test")


def _split_partitions(df: pd.DataFrame, *, target: str, contract: Mapping[str, Any]) -> tuple:
    data = contract.get("data")
    split = data.get("split") if isinstance(data, Mapping) else None
    if not isinstance(split, Mapping):
        raise ValueError("study.yaml:data.split is required")
    kind = split.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError("study.yaml:data.split.kind is required")
    kwargs: dict[str, Any] = {}
    for value, option, argument in (("group", "group_column", "groups"),
                                    ("time", "time_column", "time_values")):
        if kind == value:
            column = split.get(option)
            if column not in df.columns:
                raise ValueError(f"{option} {column!r} is not a prepared-artifact column")
            kwargs[argument] = df[column]
    task = contract.get("task_type")
    if task == "simulation":
        # three_way_split deliberately refuses "simulation": a simulation lab's
        # REAL split reproduces as an unstratified regression-shaped split.
        task = "regression"
    return three_way_split(
        df.drop(columns=[target]),
        df[target],
        task=task,
        strategy=kind,
        development_size=float(split.get("development_size", 0.2)),
        test_size=float(split.get("test_size", 0.2)),
        seed=int(split.get("seed", RANDOM_SEED)),
        **kwargs,
    )


def _split_check(df: pd.DataFrame, first: tuple, second: tuple, kind: str) -> tuple[dict, Check]:
    positions = {
        "train": np.asarray(first[0].index),
        "development": np.asarray(first[1].index),
        "test": np.asarray(first[2].index),
    }
    problems: list[str] = []
    if not all(
        np.array_equal(np.asarray(a.index), np.asarray(b.index))
        for a, b in zip(first, second, strict=True)
    ):
        problems.append("two reproductions disagree — the split is not deterministic")
    assigned = np.concatenate(list(positions.values()))
    if len(np.unique(assigned)) != len(assigned):
        problems.append("partitions overlap")
    elif len(assigned) != len(df):
        problems.append(f"{len(df) - len(assigned)} row(s) missing from every partition")
    if problems:
        return positions, Check("split-reproduces", False, "; ".join(problems))
    sizes = " ".join(f"{name}={len(pos)}" for name, pos in positions.items())
    message = f"kind={kind} reproduces deterministically from study.yaml ({sizes} rows)"
    return positions, Check("split-reproduces", True, message)


def _duplicate_check(df: pd.DataFrame, positions: Mapping[str, np.ndarray]) -> Check:
    hashes = pd.util.hash_pandas_object(df, index=False).to_numpy()
    sets = {name: set(hashes[pos]) for name, pos in positions.items()}
    counts = {f"{a}/{b}": len(sets[a] & sets[b]) for a, b in _PARTITION_PAIRS}
    straddlers = set().union(*(sets[a] & sets[b] for a, b in _PARTITION_PAIRS))
    if straddlers:
        detail = ", ".join(f"{pair}={count}" for pair, count in counts.items())
        message = f"{len(straddlers)} duplicated row-content hash(es) straddle partitions ({detail})"
        return Check("duplicate-rows", False, message)
    return Check("duplicate-rows", True, "no duplicate row content straddles partitions")


def _group_check(df: pd.DataFrame, positions: Mapping[str, np.ndarray],
                 contract: Mapping[str, Any]) -> Check:
    split = contract["data"]["split"]
    if split.get("kind") != "group":
        return Check("group-overlap", True, "N/A — split kind is not 'group'")
    normalized = df[split["group_column"]].astype(str).str.strip().str.casefold().to_numpy()
    sets = {name: set(normalized[pos]) for name, pos in positions.items()}
    overlap = sorted(set().union(*(sets[a] & sets[b] for a, b in _PARTITION_PAIRS)))
    if overlap:
        shown = ", ".join(repr(group) for group in overlap[:3])
        message = (
            f"{len(overlap)} normalized group id(s) cross partitions (e.g. {shown}) — "
            "the same entity under a dirty key leaks across the split"
        )
        return Check("group-overlap", False, message)
    total = len(set(normalized))
    return Check("group-overlap", True, f"{total} normalized group ids each stay in one partition")


def _score(spec, y_true: pd.Series, scores: Any, *, power: float | None = None) -> float:
    values = np.asarray(scores, dtype=float)
    if spec.task == "classification":
        computed, _ = _classification_metric_values(y_true, np.clip(values, 0.0, 1.0))
        return computed[spec.name]
    y_arr = np.asarray(y_true, dtype=float)
    if spec.name in DEVIANCE_METRICS:
        # Unweighted by design (see module docstring); predictions clipped to
        # stay in-domain — a shuffled counts target contains zeros, and the
        # audit needs a huge-but-finite deviance there, not an exception.
        preds = np.clip(values, 1e-9, None)
        if spec.name == "val_poisson_deviance":
            return float(mean_poisson_deviance(y_arr, preds))
        if spec.name == "val_gamma_deviance":
            return float(mean_gamma_deviance(y_arr, preds))
        if power is None:
            raise ValueError("val_tweedie_deviance requires metric.power in study.yaml")
        return float(mean_tweedie_deviance(y_arr, preds, power=float(power)))
    residual = y_arr - values
    if spec.name == "val_rmse":
        return float(np.sqrt(np.mean(residual**2)))
    if spec.name == "val_mae":
        return float(np.mean(np.abs(residual)))
    if spec.name == "val_r2":
        total = float(np.sum((y_arr - y_arr.mean()) ** 2))
        return 1.0 - float(np.sum(residual**2)) / total if total > 0 else 0.0
    raise ValueError(f"no chance scorer for metric {spec.name!r}")


def _has_chance_scorer(spec) -> bool:
    return (
        spec.task == "classification"
        or spec.name in {"val_rmse", "val_mae", "val_r2"}
        or spec.name in DEVIANCE_METRICS
    )


def _chance_check(name: str, spec, value: float, *, baseline: float | None,
                  margin: float) -> Check:
    anchor = CHANCE_ANCHORS.get(spec.name)
    label = "constant" if baseline is None else "label-shuffled"
    if anchor is not None and abs(value - anchor) > margin:
        message = (
            f"{spec.name}={value:.4f} for the {label} predictor is far from the chance "
            f"anchor {anchor:g} (margin {margin:g}) — the harness is leaking labels"
        )
        return Check(name, False, message)
    if baseline is not None and anchor is None:
        gain = value - baseline if spec.goal == "higher" else baseline - value
        if gain > margin * max(abs(baseline), 1e-12):
            message = (
                f"{spec.name}={value:.4f} for the {label} predictor decisively beats the "
                f"no-information baseline {baseline:.4f} — the harness is leaking labels"
            )
            return Check(name, False, message)
    reference = f"chance anchor {anchor:g}" if anchor is not None else "no-information baseline"
    return Check(name, True, f"{spec.name}={value:.4f} for the {label} predictor ({reference})")


def _track_checks(contract: Mapping[str, Any], parts: tuple | None, *,
                  shuffled_predictor: ShuffledPredictor | None,
                  chance_margin: float, seed: int,
                  no_parts_reason: str = NO_PARTITION_REASON) -> list[Check]:
    tracks = normalize_tracks(contract)
    if not tracks:
        return [Check("metric-direction", False,
                      "study.yaml declares no tracks — no metric contract to audit")]
    # The scalar metric family is spelled `scalar` in schema 3 and `simulation`
    # in schema 2; `contract.task_family` is the single source of truth for that
    # alias, so this check never has to know both spellings.  Testing only the
    # retired one made every schema-3 study with a CUSTOM metric name — which is
    # every registered track — a DATA-gate BLOCKER, while the byte-identical
    # schema-2 contract passed.
    scalar_family = task_family(contract) == "scalar"
    checks: list[Check] = []
    rng = np.random.default_rng(seed)
    for track, spec_dict in tracks.items():
        metric = spec_dict.get("metric", {})
        goal = metric.get("goal")
        try:
            if not isinstance(goal, str):
                raise ValueError(f"track {track!r}: metric.goal is missing from the contract")
            spec = get_metric_spec(
                str(metric.get("name")),
                goal=goal,
                task=task_family(contract),
                allow_custom=scalar_family,
            )
        except ValueError as exc:
            checks.append(Check(f"metric-direction[{track}]", False, str(exc)))
            continue
        if spec.name in _METRIC_SPECS:
            direction_message = (
                f"{spec.name}: contract direction {spec.goal!r} matches the canonical registry"
            )
        else:
            direction_message = (
                f"{spec.name}: contract-declared direction {spec.goal!r} accepted "
                "(custom metric of the scalar family)"
            )
        checks.append(Check(f"metric-direction[{track}]", True, direction_message))
        if parts is None:
            checks.append(Check(f"chance-level[{track}]", True, no_parts_reason))
            continue
        if not _has_chance_scorer(spec):
            checks.append(Check(
                f"chance-level[{track}]", True,
                f"N/A — no bundled chance scorer for custom metric {spec.name!r}; "
                "reproduce checklist row 4 by hand",
            ))
            continue
        X_tr, X_dev, _X_te, y_tr, y_dev, _y_te = parts
        power = metric.get("power")
        constant = np.full(len(y_dev), float(np.asarray(y_tr, dtype=float).mean()))
        if shuffled_predictor is None:
            shuffled: Any = rng.permutation(np.asarray(y_dev, dtype=float))
        else:
            y_shuffled = pd.Series(rng.permutation(np.asarray(y_tr)),
                                   index=y_tr.index, name=y_tr.name)
            shuffled = shuffled_predictor(X_tr, y_shuffled, X_dev)
        try:
            constant_score = _score(spec, y_dev, constant, power=power)
            shuffled_score = _score(spec, y_dev, shuffled, power=power)
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            checks.append(Check(f"chance-level[{track}]", False,
                                f"cannot score {spec.name} on the development partition: {exc}"))
            continue
        checks.append(_chance_check(f"constant-chance[{track}]", spec, constant_score,
                                    baseline=None, margin=chance_margin))
        checks.append(_chance_check(f"shuffled-chance[{track}]", spec, shuffled_score,
                                    baseline=constant_score, margin=chance_margin))
    return checks


def audit_split(
    prepared_path: str | Path,
    *,
    target: str,
    study_dir: str | Path,
    shuffled_predictor: ShuffledPredictor | None = None,
    chance_margin: float = 0.15,
    seed: int = 0,
) -> list[Check]:
    """Audit a prepared artifact against the study's declared split contract.

    Returns one :class:`kleinlib.workflow.Check` per audit row; any failed
    check is a BLOCKER at the DATA gate.  ``seed`` drives only the audit's
    label shuffle — the split itself always uses the ``study.yaml`` seed.
    Caller errors (missing study, unreadable artifact, bad ``chance_margin``)
    raise; audit findings never do.
    """
    if not (0.0 < chance_margin < 1.0):
        raise ValueError("chance_margin must be between 0 and 1")
    contract = load_contract(resolve_study(study_dir))
    df = load_prepared(prepared_path).reset_index(drop=True)
    data = contract.get("data")
    split = data.get("split") if isinstance(data, Mapping) else None
    if isinstance(split, Mapping) and split.get("kind") == "none":
        checks = [
            Check("split-reproduces", True,
                  "N/A — split kind 'none' (simulation lab): no partitions to audit"),
            Check("duplicate-rows", True, "N/A — no partitions"),
            Check("group-overlap", True, "N/A — no partitions"),
        ]
        checks.extend(_track_checks(contract, None, shuffled_predictor=shuffled_predictor,
                                    chance_margin=chance_margin, seed=seed))
        return checks
    if target not in df.columns:
        return [Check("split-reproduces", False,
                      f"target column {target!r} is not in the prepared artifact")]
    try:
        first = _split_partitions(df, target=target, contract=contract)
        second = _split_partitions(df, target=target, contract=contract)
    except (KeyError, TypeError, ValueError) as exc:
        return [Check("split-reproduces", False, f"declared split does not reproduce: {exc}")]
    positions, split_check = _split_check(df, first, second, contract["data"]["split"]["kind"])
    checks = [split_check, _duplicate_check(df, positions), _group_check(df, positions, contract)]
    checks.extend(_track_checks(contract, first, shuffled_predictor=shuffled_predictor,
                                chance_margin=chance_margin, seed=seed))
    return checks


def _normalized(series: pd.Series) -> np.ndarray:
    """``strip().casefold()`` — the same normalization the dataframe audit uses.

    Exact ids are disjoint by construction once a split reproduces; the leak a
    by-construction split cannot see is the same entity under a dirty key
    (``"G7"`` vs ``"g7 "``).
    """
    return series.astype(str).str.strip().str.casefold().to_numpy()


def _index_shape_check(index: pd.DataFrame) -> tuple[dict[str, np.ndarray] | None, Check]:
    """Structural audit of the index table; returns positions per partition."""
    missing = [column for column in INDEX_REQUIRED_COLUMNS if column not in index.columns]
    if missing:
        return None, Check(
            "index-table",
            False,
            f"missing required column(s) {missing}; an index table is "
            f"{list(INDEX_REQUIRED_COLUMNS)} plus the optional {list(INDEX_OPTIONAL_COLUMNS)}",
        )
    if index.empty:
        return None, Check("index-table", False, "the index table has no rows")
    problems: list[str] = []
    ids = _normalized(index["id"])
    if any(value in ("", "nan", "none") for value in ids):
        problems.append("some rows have an empty id")
    labels = _normalized(index["split"])
    unknown = sorted(set(labels) - set(INDEX_PARTITIONS))
    if unknown:
        problems.append(
            f"unknown split label(s) {unknown} — Klein's partitions are "
            f"{list(INDEX_PARTITIONS)}"
        )
    positions = {
        name: np.flatnonzero(labels == name) for name in INDEX_PARTITIONS
    }
    present = [name for name, pos in positions.items() if pos.size]
    if len(present) < 2:
        problems.append(
            f"only {present or 'no'} partition(s) present — an index with one "
            "partition cannot show contamination"
        )
    if problems:
        return None, Check("index-table", False, "; ".join(problems))
    sizes = " ".join(f"{name}={pos.size}" for name, pos in positions.items())
    return positions, Check(
        "index-table",
        True,
        f"{len(index)} rows partitioned by the `split` column ({sizes}); the "
        "index IS the realized split — this audit does not re-derive it",
    )


def _index_duplicate_check(
    index: pd.DataFrame, positions: Mapping[str, np.ndarray]
) -> Check:
    """The index-table analogue of duplicate row content: a straddling id."""
    ids = _normalized(index["id"])
    sets = {name: set(ids[pos]) for name, pos in positions.items()}
    counts = {f"{a}/{b}": len(sets[a] & sets[b]) for a, b in _PARTITION_PAIRS}
    straddlers = sorted(set().union(*(sets[a] & sets[b] for a, b in _PARTITION_PAIRS)))
    if straddlers:
        detail = ", ".join(f"{pair}={count}" for pair, count in counts.items())
        shown = ", ".join(repr(value) for value in straddlers[:3])
        return Check(
            "duplicate-rows",
            False,
            f"{len(straddlers)} normalized id(s) straddle partitions (e.g. {shown}; "
            f"{detail}) — a memorized twin of a sealed item is contamination, not skill",
        )
    repeats = len(ids) - len(set(ids))
    within = (
        f"; {repeats} repeated id(s) inside a single partition — deliberate "
        "duplication is fine, an accident is not"
        if repeats
        else ""
    )
    return Check("duplicate-rows", True, f"no id straddles partitions{within}")


def _index_group_check(
    index: pd.DataFrame, positions: Mapping[str, np.ndarray]
) -> Check:
    """Present-means-declared: an index carrying a group column is audited for it.

    Unlike the dataframe audit — which keys off ``data.split.kind == "group"`` —
    a `group` column in an index table IS the study's group policy (the modality
    cards for image, sequence, graph and text ask for one), so it is checked
    whenever it is there.
    """
    if "group" not in index.columns:
        return Check("group-overlap", True, "N/A — the index declares no group column")
    groups = _normalized(index["group"])
    sets = {name: set(groups[pos]) for name, pos in positions.items()}
    overlap = sorted(set().union(*(sets[a] & sets[b] for a, b in _PARTITION_PAIRS)))
    if overlap:
        shown = ", ".join(repr(group) for group in overlap[:3])
        return Check(
            "group-overlap",
            False,
            f"{len(overlap)} normalized group id(s) cross partitions (e.g. {shown}) — "
            "the same entity under a dirty key leaks across the split",
        )
    return Check(
        "group-overlap",
        True,
        f"{len(set(groups))} normalized group ids each stay in one partition",
    )


def _index_time_check(
    index: pd.DataFrame,
    positions: Mapping[str, np.ndarray],
    contract: Mapping[str, Any],
) -> Check:
    """Lookahead on the index: a time-split's partitions must not overlap in time."""
    if "time" not in index.columns:
        return Check("time-order", True, "N/A — the index declares no time column")
    values = pd.to_numeric(index["time"], errors="coerce")
    if values.isna().any():
        values = pd.to_datetime(index["time"], errors="coerce", format="mixed")
    if values.isna().any():
        return Check(
            "time-order",
            False,
            f"{int(values.isna().sum())} time value(s) are neither numeric nor "
            "parseable timestamps — a lookahead audit cannot run on them",
        )
    ordered = [name for name in INDEX_PARTITIONS if positions[name].size]
    ranges = {name: (values.iloc[positions[name]].min(),
                     values.iloc[positions[name]].max()) for name in ordered}
    shown = "; ".join(f"{name} [{low} .. {high}]" for name, (low, high) in ranges.items())
    data = contract.get("data")
    split = data.get("split") if isinstance(data, Mapping) else None
    kind = split.get("kind") if isinstance(split, Mapping) else None
    if kind != "time":
        # A random or stratified split legitimately interleaves times; report
        # the ranges so checklist row 2 is a judgment made with the numbers.
        return Check(
            "time-order",
            True,
            f"observed time ranges — {shown} (declared split kind {kind!r} does not "
            "require ordering; lookahead stays a judgment call on prepare.py)",
        )
    violations = [
        f"{earlier} ends at {ranges[earlier][1]} but {later} starts at {ranges[later][0]}"
        for earlier, later in zip(ordered, ordered[1:], strict=False)
        if ranges[earlier][1] > ranges[later][0]
    ]
    if violations:
        return Check(
            "time-order",
            False,
            "a time split must not look ahead: " + "; ".join(violations),
        )
    return Check("time-order", True, f"partitions are ordered in time — {shown}")


def audit_index(
    index_path: str | Path,
    *,
    study_dir: str | Path,
) -> list[Check]:
    """Audit a SPLIT INDEX TABLE — the modality-agnostic form of checklist row 3.

    A tabular study can hash its whole prepared frame; an image, sequence,
    graph or text study cannot, so its DATA gate audits the index table its
    ``prepare.py`` wrote: ``id`` and ``split`` are required, ``group`` and
    ``time`` optional.  The index IS the realized split — this mode does not
    re-derive it from ``study.yaml`` (that is the printed
    ``split_fingerprint:`` contract's job), it checks the two contaminations a
    realized split can still carry: an item that straddles partitions, and an
    entity whose parts do.

    Checklist row 4 (the chance predictors) needs a target and features, which
    an index does not carry, so its rows report N/A with that reason while the
    metric-direction row still runs off the contract.
    """
    contract = load_contract(resolve_study(study_dir))
    index = load_prepared(index_path).reset_index(drop=True)
    positions, shape = _index_shape_check(index)
    checks = [shape]
    if positions is None:
        return checks
    checks += [
        _index_duplicate_check(index, positions),
        _index_group_check(index, positions),
        _index_time_check(index, positions, contract),
    ]
    checks += _track_checks(
        contract,
        None,
        shuffled_predictor=None,
        chance_margin=0.15,
        seed=0,
        no_parts_reason=(
            "N/A — index-table mode carries no target or features; reproduce "
            "checklist row 4 from the study's own evaluation path"
        ),
    )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m kleinlib.leakage",
        description="Clean-room split & eval-harness audit — data-card checklist rows 3-4.",
    )
    parser.add_argument(
        "prepared",
        nargs="?",
        help="prepared artifact (.csv/.parquet) — the thing train.py sees "
        "(dataframe mode; omit it when using --index)",
    )
    parser.add_argument("--target", help="target column name (required in dataframe mode)")
    parser.add_argument(
        "--index",
        help="split index table (id, group?, time?, split) — index-table mode, "
        "for any modality whose items are not rows of a frame",
    )
    parser.add_argument("--study", required=True, help="study directory containing study.yaml")
    parser.add_argument("--chance-margin", type=float, default=0.15,
                        help="tolerance around chance (default 0.15)")
    parser.add_argument("--seed", type=int, default=0,
                        help="audit RNG seed for the label shuffle (default 0)")
    args = parser.parse_args(argv)
    if bool(args.prepared) == bool(args.index):
        parser.error(
            "give exactly one of <prepared> (dataframe mode) or --index (index-table mode)"
        )
    if args.prepared and not args.target:
        parser.error("--target is required in dataframe mode")
    try:
        if args.index:
            checks = audit_index(args.index, study_dir=args.study)
        else:
            checks = audit_split(args.prepared, target=args.target, study_dir=args.study,
                                 chance_margin=args.chance_margin, seed=args.seed)
    except (FileNotFoundError, ValueError, WorkflowError) as exc:
        print(f"[FAIL] audit: {exc}")
        return 1
    for check in checks:
        print(f"{'[OK]  ' if check.ok else '[FAIL]'} {check.name}: {check.message}")
    failed = sum(1 for check in checks if not check.ok)
    verdict = "clean" if failed == 0 else f"{failed} FAIL — any FAIL is a BLOCKER at the DATA gate"
    print(f"{len(checks) - failed}/{len(checks)} checks passed: {verdict}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
