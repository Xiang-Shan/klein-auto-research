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
  contract's metric direction must match the canonical registry (a custom
  simulation metric's declared direction is accepted as-is), and two
  no-information predictors — the train-target mean, and a label shuffle —
  must score at chance on the development partition.  A "shuffled" predictor
  scoring far from chance means the harness is showing it the answers.

Simulation studies with a REAL split kind (random/group/time) audit like
regression studies; ``kind: none`` has no partitions, so checks report N/A.
The audit's chance scorers are deliberately **unweighted** — they test that
the harness carries no label information, not the study's exact
exposure-weighted value.

CLI (one ``[OK]``/``[FAIL]`` line per check; any FAIL is a BLOCKER at the
DATA gate and the exit code is 1)::

    uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>
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

from .data import RANDOM_SEED, load_prepared, three_way_split
from .eval import (
    _METRIC_SPECS,
    DEVIANCE_METRICS,
    _classification_metric_values,
    get_metric_spec,
)
from .workflow import Check, WorkflowError, load_contract, normalize_tracks, resolve_study

__all__ = ["CHANCE_ANCHORS", "audit_split", "main"]

#: Metrics with a known absolute no-skill value.  Anchor-less metrics use the
#: relative rule instead: shuffled must not decisively beat the constant baseline.
CHANCE_ANCHORS: dict[str, float] = {"val_auc": 0.5, "val_r2": 0.0}

#: ``(X_train, y_train_shuffled, X_development) -> scores`` — the seam for
#: auditing a study's own prediction path against shuffled labels.  The default
#: ignores the features and scores a seeded permutation of the development target.
ShuffledPredictor = Callable[[pd.DataFrame, pd.Series, pd.DataFrame], Any]

_PARTITION_PAIRS = (("train", "development"), ("train", "test"), ("development", "test"))


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
                  chance_margin: float, seed: int) -> list[Check]:
    tracks = normalize_tracks(contract)
    if not tracks:
        return [Check("metric-direction", False,
                      "study.yaml declares no tracks — no metric contract to audit")]
    simulation = contract.get("task_type") == "simulation"
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
                task="scalar" if simulation else str(contract.get("task_type")),
                allow_custom=simulation,
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
                "(custom simulation metric)"
            )
        checks.append(Check(f"metric-direction[{track}]", True, direction_message))
        if parts is None:
            checks.append(Check(
                f"chance-level[{track}]", True,
                "N/A — split kind 'none': no development partition to score",
            ))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m kleinlib.leakage",
        description="Clean-room split & eval-harness audit — data-card checklist rows 3-4.",
    )
    parser.add_argument("prepared", help="prepared artifact (.csv/.parquet) — the thing train.py sees")
    parser.add_argument("--target", required=True, help="target column name")
    parser.add_argument("--study", required=True, help="study directory containing study.yaml")
    parser.add_argument("--chance-margin", type=float, default=0.15,
                        help="tolerance around chance (default 0.15)")
    parser.add_argument("--seed", type=int, default=0,
                        help="audit RNG seed for the label shuffle (default 0)")
    args = parser.parse_args(argv)
    try:
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
