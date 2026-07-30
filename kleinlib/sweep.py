"""SweepRunner — the ONE sanctioned escape-hatch for a boxed parameter sweep.

Klein's experiment loop is normally hand-driven: one `train.py` diff, one candidate
transaction through `klein run-one` (`.claude/skills/klein/SKILL.md` Hard Rule 1). A
SWEEP is the single exception — a parameter search too mechanical to hand-drive one
trial at a time. Full contract:
`.claude/skills/klein/references/sweep-rules.md` — READ IT before writing a sweep
script. This module mechanizes rule 2 only: every trial appended to the sidecar TSV,
in arrival order, flushed as each finishes.

This runner deliberately does NOT touch `results.tsv`, does NOT `git commit`, and does
NOT snapshot a model. Per sweep-rules.md rules 3-6 the close-out stays with the loop:
commit the sweep script + sidecar, copy the winner's config into `train.py`, then
`klein run-one` commits that candidate and derives the ONE v2 ledger row transactionally
(a `discard` per rule 7 if nothing improved). Never hand-edit the v2 ledger.

Trials run SEQUENTIALLY in the foreground (no background polling, no parallel
dispatch). A trial that raises a normal exception is caught, recorded as a `crash` row
(`NA` metric), and the sweep continues — one bad trial must not lose the rest of the
search. `KeyboardInterrupt` (or any other `BaseException`) is NOT caught: it aborts
`run()` immediately, same as Ctrl-C on the hand loop, but every trial that already
finished is on disk already — the sidecar is written trial-by-trial, never buffered.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import schema

__all__ = ["SweepRunner", "SweepSummary", "TrialRecord"]

#: Canonical sidecar column order — sweep-rules.md rule 2. Do not restate elsewhere.
SIDECAR_COLUMNS: tuple[str, ...] = (
    "trial",
    "params_json",
    "primary_metric",
    "wall_seconds",
    "status",
    "error",
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
        try:
            numeric_baseline = float(baseline)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"baseline must be numeric, got {baseline!r}") from exc
        if not math.isfinite(numeric_baseline):
            raise ValueError(f"baseline must be finite, got {numeric_baseline!r}")
        w = self.winner
        if w is None:
            return False
        if self.metric_goal == "higher":
            return w.primary_metric > numeric_baseline
        return w.primary_metric < numeric_baseline


class SweepRunner:
    """Run one boxed parameter sweep; append every trial to the sidecar as it finishes.

    `trial_fn(params) -> dict` does the work for ONE trial (build+fit+evaluate against
    the study's FIXED split — a sweep tunes the model, never resamples the split) and
    returns `{"primary_metric": float, "status": "ok" | "crash", ...}`; extra keys land
    on that trial's `TrialRecord.extra`, not the sidecar. Does NOT touch `results.tsv`,
    `git commit`, or `kleinlib.snapshot` — see the module docstring / sweep-rules.md.
    Crash details are persisted in the sidecar; other extras remain in memory.
    """

    def __init__(
        self,
        name: str,
        study_dir: str | Path,
        trial_fn: Callable[[dict[str, Any]], dict[str, Any]],
        params_list: list[dict[str, Any]],
        *,
        metric_goal: str = "higher",
        resume: bool = False,
        overwrite: bool = False,
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
        self.resume = resume
        self.overwrite = overwrite
        if resume and overwrite:
            raise ValueError("resume and overwrite are mutually exclusive")
        self._params_json = [self._serialize_params(params) for params in self.params_list]

    @property
    def sidecar_path(self) -> Path:
        """`<study_dir>/sweeps/<name>.sidecar.tsv` — sweep-rules.md rule 1's location."""
        return self.study_dir / "sweeps" / f"{self.name}.sidecar.tsv"

    def run(self) -> SweepSummary:
        """Run every trial in `params_list`, in order; return the summary.

        Refuses to replace an existing sidecar unless ``overwrite=True``.
        ``resume=True`` validates and loads the completed prefix, then continues
        at the first missing trial.
        """
        path = self.sidecar_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if self.resume:
                trials = self._read_existing(path)
            elif self.overwrite:
                path.write_text("\t".join(SIDECAR_COLUMNS) + "\n", encoding="utf-8")
                trials = []
            else:
                raise FileExistsError(
                    f"sweep sidecar already exists: {path}; pass resume=True to "
                    "continue it or overwrite=True to replace it"
                )
        else:
            path.write_text("\t".join(SIDECAR_COLUMNS) + "\n", encoding="utf-8")
            trials = []

        for i in range(len(trials) + 1, len(self.params_list) + 1):
            params = self.params_list[i - 1]
            record = self._run_one(i, dict(params))
            trials.append(record)
            self._append_row(path, record)
        return SweepSummary(name=self.name, metric_goal=self.metric_goal, trials=trials)

    @staticmethod
    def _serialize_params(params: Any) -> str:
        if not isinstance(params, dict):
            raise TypeError(f"each parameter set must be a dict, got {type(params).__name__}")
        try:
            return json.dumps(
                params,
                separators=(",", ":"),
                sort_keys=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"sweep parameters must be finite JSON values: {params!r}") from exc

    def _read_existing(self, path: Path) -> list[TrialRecord]:
        lines = path.read_text(encoding="utf-8").splitlines()
        expected_header = "\t".join(SIDECAR_COLUMNS)
        if not lines or lines[0] != expected_header:
            raise ValueError(
                f"cannot resume {path}: expected header {expected_header!r}"
            )
        records: list[TrialRecord] = []
        for expected_trial, line in enumerate(lines[1:], start=1):
            fields = line.split("\t")
            if len(fields) != len(SIDECAR_COLUMNS):
                raise ValueError(
                    f"cannot resume {path}: trial {expected_trial} has "
                    f"{len(fields)} fields, expected {len(SIDECAR_COLUMNS)}"
                )
            row = dict(zip(SIDECAR_COLUMNS, fields, strict=True))
            if int(row["trial"]) != expected_trial:
                raise ValueError("cannot resume: existing trial numbers are not contiguous")
            if expected_trial > len(self.params_list):
                raise ValueError("cannot resume: sidecar has more trials than params_list")
            if row["params_json"] != self._params_json[expected_trial - 1]:
                raise ValueError(
                    f"cannot resume: parameters changed at trial {expected_trial}"
                )
            status = row["status"]
            metric = None
            if status == "ok":
                try:
                    metric = float(row["primary_metric"])
                except ValueError as exc:
                    raise ValueError(
                        f"cannot resume: invalid metric at trial {expected_trial}"
                    ) from exc
                if not math.isfinite(metric):
                    raise ValueError(
                        f"cannot resume: non-finite metric at trial {expected_trial}"
                    )
            elif status != "crash" or row["primary_metric"] != schema.NA_METRIC:
                raise ValueError(
                    f"cannot resume: invalid status/metric pair at trial {expected_trial}"
                )
            try:
                error = json.loads(row["error"]) if row["error"] else ""
                wall_seconds = float(row["wall_seconds"])
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"cannot resume: malformed persisted fields at trial {expected_trial}"
                ) from exc
            if not math.isfinite(wall_seconds) or wall_seconds < 0:
                raise ValueError(
                    f"cannot resume: invalid wall_seconds at trial {expected_trial}"
                )
            records.append(
                TrialRecord(
                    trial=expected_trial,
                    params=dict(self.params_list[expected_trial - 1]),
                    primary_metric=metric,
                    wall_seconds=wall_seconds,
                    status=status,
                    extra={"error": error} if error else {},
                )
            )
        return records

    def _run_one(self, trial: int, params: dict[str, Any]) -> TrialRecord:
        """Call `trial_fn` once; a normal exception becomes a `crash` row, not a raise."""
        t0 = time.time()
        try:
            result = self.trial_fn(params)
            if not isinstance(result, dict):
                raise TypeError(
                    f"trial_fn must return a dict, got {type(result).__name__}"
                )
            status = result.get("status", "ok")
            metric = result.get("primary_metric")
            extra = {
                k: v for k, v in result.items() if k not in ("status", "primary_metric")
            }
            if status not in ("ok", "crash"):
                raise ValueError(f"trial status must be 'ok' or 'crash', got {status!r}")
            if status == "ok":
                if metric is None:
                    raise ValueError("status='ok' requires primary_metric")
                metric = float(metric)
                if not math.isfinite(metric):
                    raise ValueError(f"primary_metric must be finite, got {metric!r}")
        except Exception as exc:
            status, metric = "crash", None
            extra = {"error": f"{type(exc).__name__}: {exc}"}
        wall_seconds = time.time() - t0

        if status != "ok" or metric is None:
            status, metric = "crash", None  # NA metric pairs only with crash
        return TrialRecord(trial, params, metric, wall_seconds, status, extra)

    @staticmethod
    def _append_row(path: Path, record: TrialRecord) -> None:
        metric_field = (
            schema.NA_METRIC
            if record.primary_metric is None
            else f"{record.primary_metric:.6f}"
        )
        params_json = SweepRunner._serialize_params(record.params)
        error = str(record.extra.get("error", ""))
        error_field = json.dumps(error, ensure_ascii=True) if error else ""
        line = "\t".join(
            [
                str(record.trial),
                params_json,
                metric_field,
                f"{record.wall_seconds:.3f}",
                record.status,
                error_field,
            ]
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
