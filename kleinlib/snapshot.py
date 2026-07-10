"""Best-model snapshotting for Klein Auto Research studies.

Each study keeps a `models/manifest.tsv` ledger (created on first use, with
columns `experiment / path / metric / created_utc`) tracking every "new
best" checkpoint saved during the experiment loop, so the winning model is
always on disk under a name that encodes which experiment and what metric it
scored — no separate bookkeeping needed. `kleinlib.eval.evaluate` and
`evaluate_regression` call :func:`maybe_save_best` automatically whenever a
`study_dir` is given.

History is append-only: superseded checkpoints are never deleted from disk
(only from "current best" status), matching the project's single-source
audit-trail ethos. `read_current_best` treats the manifest's last row as the
global best-so-far, which holds by construction since every appended row was
strictly better than the prior best at the time it was written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

#: Manifest filename, under `<study_dir>/models/`.
MANIFEST_NAME = "manifest.tsv"

#: Column order for the manifest.
MANIFEST_COLUMNS = ("experiment", "path", "metric", "created_utc")

_VALID_GOALS = ("higher", "lower")


@dataclass(frozen=True)
class BestRecord:
    """One row of `models/manifest.tsv`."""

    experiment: str
    path: str
    metric: float
    created_utc: str


def _models_dir(study_dir: str | Path) -> Path:
    d = Path(study_dir) / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manifest_path(study_dir: str | Path) -> Path:
    return _models_dir(study_dir) / MANIFEST_NAME


def read_current_best(study_dir: str | Path) -> BestRecord | None:
    """Return the current best record (the manifest's last data row), or None.

    None means either the manifest doesn't exist yet or has a header only.
    """
    path = _manifest_path(study_dir)
    if not path.exists() or path.stat().st_size == 0:
        return None
    with path.open(encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    if len(lines) <= 1:  # header only (or, defensively, truly empty)
        return None
    experiment, path_str, metric, created_utc = lines[-1].split("\t")
    return BestRecord(
        experiment=experiment,
        path=path_str,
        metric=float(metric),
        created_utc=created_utc,
    )


def maybe_save_best(
    model: Any,
    *,
    exp_id: int | str,
    metric_value: float,
    metric_goal: str,
    study_dir: str | Path,
    primary_name: str,
) -> str | None:
    """Pickle `model` as the new best-so-far if it beats the manifest's best.

    Writes `models/best_<exp_id>_<metric_value:.4f>.pkl` and appends a row to
    `models/manifest.tsv` (creating it with the header if absent) when
    `model` is a new best. `metric_goal` must be `"higher"` or `"lower"`.
    `primary_name` is accepted for call-site symmetry with `eval.evaluate`
    but is not currently persisted (the manifest already scopes `metric` to
    one study, which has exactly one primary metric name throughout).

    Returns the saved path as a string if a new best was written, else None.
    """
    if metric_goal not in _VALID_GOALS:
        raise ValueError(
            f"metric_goal must be one of {_VALID_GOALS}, got {metric_goal!r}"
        )

    current = read_current_best(study_dir)
    is_better = current is None or (
        metric_value > current.metric
        if metric_goal == "higher"
        else metric_value < current.metric
    )
    if not is_better:
        return None

    models_dir = _models_dir(study_dir)
    out_path = models_dir / f"best_{exp_id}_{metric_value:.4f}.pkl"
    joblib.dump(model, out_path)

    manifest_path = _manifest_path(study_dir)
    write_header = not manifest_path.exists() or manifest_path.stat().st_size == 0
    created = datetime.now(timezone.utc).isoformat()
    with manifest_path.open("a", encoding="utf-8") as f:
        if write_header:
            f.write("\t".join(MANIFEST_COLUMNS) + "\n")
        f.write(f"{exp_id}\t{out_path}\t{metric_value:.6f}\t{created}\n")

    return str(out_path)


def load_best(study_dir: str | Path) -> Any:
    """Load and return the current best model.

    Raises `FileNotFoundError` if no best model has been recorded yet.
    """
    current = read_current_best(study_dir)
    if current is None:
        raise FileNotFoundError(
            f"no best model recorded yet under {Path(study_dir) / 'models' / MANIFEST_NAME}"
        )
    return joblib.load(current.path)
