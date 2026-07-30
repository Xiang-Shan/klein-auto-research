"""Measured noise floor for the keep/discard threshold (stdlib only).

``minimum_delta`` should never be guessed: repeat the Phase-0 baseline k times
varying ONLY the seed, and the spread of those runs IS the smallest difference
worth talking about. The consult protocol wires this in
(`references/consult-protocol.md` — Phase 0); ``klein noise-floor`` prints the
paste-able ``study.yaml`` block; preflight refuses a ``minimum_delta`` set
inside a declared floor.

The measurement sweep is a normal :mod:`kleinlib.sweep` sidecar
(``sweeps/noise_floor.sidecar.tsv``) that promotes NO winner — see the carve-out
in ``references/sweep-rules.md``.
"""

from __future__ import annotations

import csv
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = ["NoiseFloor", "summarize_noise", "floor_from_sidecar", "yaml_block"]

#: Keys a study.yaml ``metric.noise_floor`` block may carry (validated in
#: kleinlib.workflow.validate_contract).
ALLOWED_KEYS = frozenset(
    {"k", "seeds", "std", "range", "mean", "values", "source", "measured_after"}
)


@dataclass(frozen=True)
class NoiseFloor:
    k: int
    mean: float
    std: float
    value_range: float
    values: tuple[float, ...]
    seeds: tuple[int, ...] | None = None

    @property
    def suggested_minimum_delta(self) -> float:
        """max(2×std, half the observed range) — conservative on small k."""
        return max(2.0 * self.std, self.value_range / 2.0)


def summarize_noise(
    values: Sequence[float], *, seeds: Sequence[int] | None = None
) -> NoiseFloor:
    floats = [float(v) for v in values]
    if len(floats) < 3:
        raise ValueError(
            f"a noise floor needs k >= 3 identical-config runs, got {len(floats)}"
        )
    if any(not _finite(v) for v in floats):
        raise ValueError("noise-floor values must all be finite")
    if seeds is not None and len(seeds) != len(floats):
        raise ValueError("seeds and values must have the same length")
    return NoiseFloor(
        k=len(floats),
        mean=statistics.fmean(floats),
        std=statistics.stdev(floats),  # ddof=1
        value_range=max(floats) - min(floats),
        values=tuple(floats),
        seeds=tuple(int(s) for s in seeds) if seeds is not None else None,
    )


def floor_from_sidecar(path: Path, *, metric: str = "primary_metric") -> NoiseFloor:
    """Read a measurement sweep's sidecar; only ``status == ok`` rows count."""
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    values: list[float] = []
    for row in rows:
        if row.get("status") != "ok":
            continue
        raw = row.get(metric)
        if raw in (None, "", "NA"):
            continue
        values.append(float(raw))
    if len(values) < 3:
        raise ValueError(
            f"{path}: needs >= 3 ok rows with a finite {metric!r}, found {len(values)}"
        )
    return summarize_noise(values)


def yaml_block(track: str, floor: NoiseFloor, *, source: str, measured_after: str | None = None) -> str:
    """The paste-able ``study.yaml`` snippet (indented for tracks.<t>.metric)."""
    lines = [
        f"# tracks.{track}.metric — set minimum_delta from the measured floor:",
        f"      minimum_delta: {floor.suggested_minimum_delta:.6g}"
        f"   # = max(2*std, range/2), std {floor.std:.6g}",
        "      noise_floor:",
        f"        k: {floor.k}",
    ]
    if floor.seeds is not None:
        lines.append(f"        seeds: [{', '.join(str(s) for s in floor.seeds)}]")
    lines += [
        f"        std: {floor.std:.6g}",
        f"        range: {floor.value_range:.6g}",
        f"        mean: {floor.mean:.6g}",
        f"        values: [{', '.join(f'{v:.6g}' for v in floor.values)}]",
        f'        source: "{source}"',
    ]
    if measured_after:
        lines.append(f'        measured_after: "{measured_after}"')
    return "\n".join(lines) + "\n"


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute the measured noise floor and print the study.yaml block."
    )
    parser.add_argument("--track", default="primary", help="track the floor belongs to")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sidecar", type=Path, help="measurement sweep sidecar TSV")
    group.add_argument("--values", help="comma-separated metric values")
    parser.add_argument("--seeds", help="comma-separated seeds (with --values)")
    parser.add_argument("--measured-after", help="anchor experiment id, e.g. E0001")
    args = parser.parse_args(argv)
    if args.sidecar is not None:
        floor = floor_from_sidecar(args.sidecar)
        source = str(args.sidecar)
    else:
        seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else None
        floor = summarize_noise(
            [float(v) for v in args.values.split(",")], seeds=seeds
        )
        source = "--values"
    print(
        f"k={floor.k}  mean={floor.mean:.6g}  std={floor.std:.6g}  "
        f"range={floor.value_range:.6g}  suggested minimum_delta="
        f"{floor.suggested_minimum_delta:.6g}"
    )
    print()
    print(yaml_block(args.track, floor, source=source, measured_after=args.measured_after))
    print(
        "next: edit study.yaml, then re-record the consult gate --note "
        '"minimum_delta set from the measured noise floor"'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
