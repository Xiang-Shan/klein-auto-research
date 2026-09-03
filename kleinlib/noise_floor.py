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

__all__ = [
    "ESTIMANDS",
    "add_recipe_arguments",
    "FIT_NOISE",
    "NoiseFloor",
    "RECIPES",
    "block_key",
    "floor_from_sidecar",
    "floor_report",
    "resolve_estimand",
    "summarize_noise",
    "yaml_block",
]

#: The floor recipes and estimands the consult protocol names. Re-exported from
#: :mod:`kleinlib.metrology` so this stdlib-only module (and the CLI it backs)
#: does not import numpy just to spell three strings; a drift test pins them.
RECIPES: tuple[str, ...] = ("seed-sweep", "split-lottery", "paired-bootstrap")
ESTIMANDS: tuple[str, ...] = ("fit-noise", "marginal-resplit", "paired-comparison")

#: The one estimand that is NEVER the keep bar.
FIT_NOISE: str = "fit-noise"

#: Which estimand a recipe measures unless the caller says otherwise.
RECIPE_ESTIMAND: dict[str, str] = {
    "seed-sweep": "fit-noise",
    "split-lottery": "marginal-resplit",
    "paired-bootstrap": "paired-comparison",
}


def resolve_estimand(recipe: str | None, estimand: str | None) -> str | None:
    """The estimand to record: the declared one, else the recipe's default.

    A recipe/estimand pair outside :data:`RECIPE_ESTIMAND` is allowed but must
    be stated: study 09 ran a split lottery that produced PAIRED differences
    (`--recipe split-lottery --estimand paired-comparison`), and silently
    relabelling it would have made a paired floor look marginal.
    """
    if estimand is not None:
        if estimand not in ESTIMANDS:
            raise ValueError(f"estimand must be one of {list(ESTIMANDS)}, got {estimand!r}")
        return estimand
    if recipe is None:
        return None
    if recipe not in RECIPES:
        raise ValueError(f"recipe must be one of {list(RECIPES)}, got {recipe!r}")
    return RECIPE_ESTIMAND[recipe]

#: Keys a study.yaml ``metric.noise_floor`` block may carry (validated in
#: kleinlib.workflow.validate_contract). ``method`` is free-text provenance for
#: HOW the floor was measured — the consult protocol's vocabulary is
#: ``seed-sweep`` (the Phase-0 k-seed ladder) and ``paired-bootstrap`` (the
#: real-data comparison recipe).
#: ``estimand`` names WHICH question the floor answers — ``marginal-resplit``
#: (spread of the incumbent's own score across split re-draws) or
#: ``paired-comparison`` (spread of challenger-minus-incumbent differences on
#: the same draws). Study 07 measured both: the paired spread EXCEEDED the
#: marginal one for five of six families (challenger fit-variance dominates),
#: so neither is "the sharp one" a priori — a delta without a named estimand
#: is not a registered decision rule. Required once ``metric.bound`` is
#: declared.
ALLOWED_KEYS = frozenset(
    {
        "k",
        "seeds",
        "std",
        "range",
        "mean",
        "values",
        "source",
        "measured_after",
        "method",
        "estimand",
    }
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


def block_key(estimand: str | None) -> str:
    """``fit_noise`` for the fit-noise estimand, ``noise_floor`` otherwise.

    A seed-only spread measures how much the FIT moves, not how much a
    COMPARISON moves; pasting it as ``minimum_delta`` is how a study ends up
    defending a bar it never measured (consult protocol, Phase 0). It is
    recorded as provenance under its own key and the block carries no
    ``minimum_delta:`` line at all.
    """
    return "fit_noise" if estimand == FIT_NOISE else "noise_floor"


def yaml_block(
    track: str,
    floor: NoiseFloor,
    *,
    source: str,
    measured_after: str | None = None,
    method: str | None = None,
    estimand: str | None = None,
) -> str:
    """The paste-able ``study.yaml`` snippet (indented for tracks.<t>.metric).

    ``estimand`` names WHICH question the floor answers and selects the key the
    block lands under (:func:`block_key`): a bar-carrying estimand gets
    ``minimum_delta:`` + ``noise_floor:``; ``fit-noise`` gets ``fit_noise:``
    alone.
    """
    key = block_key(estimand)
    if key == "fit_noise":
        lines = [
            f"# tracks.{track}.metric — fit noise is PROVENANCE about the fit, "
            "NOT the keep bar:",
            "      fit_noise:",
        ]
    else:
        lines = [
            f"# tracks.{track}.metric — set minimum_delta from the measured floor:",
            f"      minimum_delta: {floor.suggested_minimum_delta:.6g}"
            f"   # = max(2*std, range/2), std {floor.std:.6g}",
            "      noise_floor:",
        ]
    lines.append(f"        k: {floor.k}")
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
    if method:
        lines.append(f'        method: "{method}"')
    if estimand:
        lines.append(f'        estimand: "{estimand}"')
    return "\n".join(lines) + "\n"


def floor_report(
    track: str,
    floor: NoiseFloor,
    *,
    source: str,
    measured_after: str | None = None,
    method: str | None = None,
    estimand: str | None = None,
) -> str:
    """Everything ``klein noise-floor`` prints: summary, block, and next step.

    One implementation so the packaged verb and ``python -m kleinlib.noise_floor``
    can never drift.
    """
    header = f"k={floor.k}  mean={floor.mean:.6g}  std={floor.std:.6g}  range={floor.value_range:.6g}"
    if method:
        header = f"recipe={method}  " + header
    if estimand:
        header = f"estimand={estimand}  " + header
    if block_key(estimand) == "fit_noise":
        header += "  (fit noise — NOT a keep bar)"
        footer = (
            "next: paste the fit_noise block, then measure the floor that will JUDGE "
            "the comparison — --recipe split-lottery (marginal-resplit) or "
            "--recipe paired-bootstrap (paired-comparison). Neither the marginal nor "
            "the paired spread is sharper a priori; for a COMPARISON the honest floor "
            "is the paired one."
        )
    else:
        header += f"  suggested minimum_delta={floor.suggested_minimum_delta:.6g}"
        footer = (
            "next: edit study.yaml, then re-record the consult gate --note "
            '"minimum_delta set from the measured noise floor"'
        )
    block = yaml_block(
        track,
        floor,
        source=source,
        measured_after=measured_after,
        method=method,
        estimand=estimand,
    )
    return f"{header}\n\n{block}\n{footer}\n"


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def add_recipe_arguments(parser) -> None:
    """Declare ``--recipe``/``--estimand``/``--method`` on a floor parser.

    One declaration so the packaged ``klein noise-floor`` verb and
    ``python -m kleinlib.noise_floor`` cannot drift in spelling or help text.
    ``--recipe`` is the vocabulary-constrained flag the consult protocol names;
    ``--method`` remains as free text for a recipe Klein does not ship, and the
    two are mutually exclusive so a block can never claim both.
    """
    recipe = parser.add_mutually_exclusive_group()
    recipe.add_argument(
        "--recipe",
        choices=list(RECIPES),
        help="how the floor was measured: seed-sweep (fit noise), split-lottery "
        "(marginal re-split), paired-bootstrap (paired comparison, common random "
        "numbers) — written to the block as method:",
    )
    recipe.add_argument(
        "--method",
        help="free-text provenance for a recipe Klein does not ship (use --recipe "
        "for the three the consult protocol names)",
    )
    parser.add_argument(
        "--estimand",
        choices=list(ESTIMANDS),
        help="WHICH question the floor answers (default: the recipe's own). "
        "fit-noise is provenance, never the bar: it lands under fit_noise: with "
        "no minimum_delta line",
    )


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
    add_recipe_arguments(parser)
    args = parser.parse_args(argv)
    if args.sidecar is not None:
        floor = floor_from_sidecar(args.sidecar)
        source = str(args.sidecar)
        args.method = args.method or ("seed-sweep" if args.recipe is None else None)
    else:
        seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else None
        floor = summarize_noise(
            [float(v) for v in args.values.split(",")], seeds=seeds
        )
        source = "--values"
    print(
        floor_report(
            args.track,
            floor,
            source=source,
            measured_after=args.measured_after,
            method=args.recipe or args.method,
            estimand=resolve_estimand(args.recipe, args.estimand),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
