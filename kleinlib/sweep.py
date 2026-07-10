"""SweepRunner — the ONE sanctioned escape-hatch for a boxed parameter sweep.

Klein's experiment loop is normally hand-driven: one `train.py` diff, one foreground
run, one `results.tsv` row (`.claude/skills/klein/SKILL.md` Hard Rule 1). A SWEEP is the
single exception — a parameter search too mechanical to hand-drive one trial at a time.
Full contract: `.claude/skills/klein/references/sweep-rules.md` — READ IT before writing
a sweep script. This module mechanizes rule 2 only: every trial appended to the sidecar
TSV, in arrival order, flushed as each finishes.

This runner deliberately does NOT touch `results.tsv`, does NOT `git commit`, and does
NOT pickle a model via `kleinlib.snapshot`. Those stay manual, per sweep-rules.md rules
3-6: commit-or-revert `train.py` FIRST, THEN append exactly one `results.tsv` row for
the winner (or a `discard` row per rule 7 if nothing improved), THEN pickle the winner
via `kleinlib.snapshot.maybe_save_best` if it's a keep — a sweep script drives all of
that around one call to :meth:`SweepRunner.run`.

Trials run SEQUENTIALLY in the foreground (no background polling, no parallel
dispatch). A trial that raises a normal exception is caught, recorded as a `crash` row
(`NA` metric), and the sweep continues — one bad trial must not lose the rest of the
search. `KeyboardInterrupt` (or any other `BaseException`) is NOT caught: it aborts
`run()` immediately, same as Ctrl-C on the hand loop, but every trial that already
finished is on disk already — the sidecar is written trial-by-trial, never buffered.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import schema

__all__ = ["SweepRunner", "SweepSummary", "TrialRecord"]

#: Canonical sidecar column order — sweep-rules.md rule 2. Do not restate elsewhere.
SIDECAR_COLUMNS: tuple[str, ...] = (
    "trial",
    "params_json",
    "primary_metric",
    "wall_seconds",
    "status",
)

_VALID_GOALS = ("higher", "lower")


@dataclass(frozen=True)
class TrialRecord:
    """One trial's outcome — one sidecar row, plus any extras (not written to disk)."""

    trial: int
    params: dict[str, Any]
    primary_metric: float | None
    wall_seconds: float
    status: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SweepSummary:
    """The full trial table plus the winner, returned by `SweepRunner.run`."""

    name: str
    metric_goal: str
    trials: list[TrialRecord]

    @property
    def winner(self) -> TrialRecord | None:
        """Best `status="ok"` trial by `metric_goal`; None if every trial crashed."""
        candidates = [
            t for t in self.trials if t.status == "ok" and t.primary_metric is not None
        ]
        if not candidates:
            return None
        pick = max if self.metric_goal == "higher" else min
        return pick(candidates, key=lambda t: t.primary_metric)

    def improved_over(self, baseline: float) -> bool:
        """True if the winner strictly beats `baseline` (goal direction); else False.

        Never an error: False when every trial crashed (sweep-rules.md rule 7 — "no
        improving trial -> the row is a discard").
        """
        w = self.winner
        if w is None:
            return False
        if self.metric_goal == "higher":
            return w.primary_metric > baseline
        return w.primary_metric < baseline


class SweepRunner:
    """Run one boxed parameter sweep; append every trial to the sidecar as it finishes.

    `trial_fn(params) -> dict` does the work for ONE trial (build+fit+evaluate against
    the study's FIXED split — a sweep tunes the model, never resamples the split) and
    returns `{"primary_metric": float, "status": "ok" | "crash", ...}`; extra keys land
    on that trial's `TrialRecord.extra`, not the sidecar. Does NOT touch `results.tsv`,
    `git commit`, or `kleinlib.snapshot` — see the module docstring / sweep-rules.md.
    """

    def __init__(
        self,
        name: str,
        study_dir: str | Path,
        trial_fn: Callable[[dict[str, Any]], dict[str, Any]],
        params_list: list[dict[str, Any]],
        *,
        metric_goal: str = "higher",
    ) -> None:
        if metric_goal not in _VALID_GOALS:
            raise ValueError(
                f"metric_goal must be one of {_VALID_GOALS}, got {metric_goal!r}"
            )
        self.name = name
        self.study_dir = Path(study_dir)
        self.trial_fn = trial_fn
        self.params_list = list(params_list)
        self.metric_goal = metric_goal

    @property
    def sidecar_path(self) -> Path:
        """`<study_dir>/sweeps/<name>.sidecar.tsv` — sweep-rules.md rule 1's location."""
        return self.study_dir / "sweeps" / f"{self.name}.sidecar.tsv"

    def run(self) -> SweepSummary:
        """Run every trial in `params_list`, in order; return the summary.

        Starts the sidecar fresh (header only), then appends (open, write, close) each
        trial's row as it finishes, so a `KeyboardInterrupt` partway through still
        leaves every completed trial on disk (see module docstring).
        """
        path = self.sidecar_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\t".join(SIDECAR_COLUMNS) + "\n", encoding="utf-8")

        trials: list[TrialRecord] = []
        for i, params in enumerate(self.params_list, start=1):
            record = self._run_one(i, dict(params))
            trials.append(record)
            self._append_row(path, record)
        return SweepSummary(name=self.name, metric_goal=self.metric_goal, trials=trials)

    def _run_one(self, trial: int, params: dict[str, Any]) -> TrialRecord:
        """Call `trial_fn` once; a normal exception becomes a `crash` row, not a raise."""
        t0 = time.time()
        try:
            result = self.trial_fn(params)
            status = result.get("status", "ok")
            metric = result.get("primary_metric")
            extra = {
                k: v for k, v in result.items() if k not in ("status", "primary_metric")
            }
        except Exception as exc:
            status, metric = "crash", None
            extra = {"error": f"{type(exc).__name__}: {exc}"}
        wall_seconds = time.time() - t0

        if status != "ok" or metric is None:
            status, metric = "crash", None  # NA metric pairs only with crash
        else:
            metric = float(metric)
        return TrialRecord(trial, params, metric, wall_seconds, status, extra)

    @staticmethod
    def _append_row(path: Path, record: TrialRecord) -> None:
        metric_field = (
            schema.NA_METRIC
            if record.primary_metric is None
            else f"{record.primary_metric:.6f}"
        )
        params_json = json.dumps(record.params, separators=(",", ":"), sort_keys=True)
        line = "\t".join(
            [
                str(record.trial),
                params_json,
                metric_field,
                f"{record.wall_seconds:.3f}",
                record.status,
            ]
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
