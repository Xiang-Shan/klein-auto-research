#!/usr/bin/env python3
"""new_study.py — scaffold a Klein study directory from the bundled templates.

Usage:
    uv run python .claude/skills/klein/scripts/new_study.py <NN-slug> \\
        --goal "..." [--domain insurance] \\
        [--metric val_auc --goal-direction higher] \\
        [--data "data_hub:insurance-claims"]

Creates ``studies/<NN-slug>/`` with study.yaml, program.md, research_plan.md,
prepare.py, train.py, results.tsv (schema header ONLY), aux_metrics.tsv (aux header
ONLY), and empty figures/ models/ report/ sweeps/ (each with a .gitkeep). Placeholders
are filled where the corresponding CLI flag is given; the rest stay for the CONSULT and
gate stages to fill. Refuses to overwrite an existing study dir. Stdlib only.

The results.tsv / aux_metrics.tsv headers come from kleinlib.schema when importable;
otherwise from an embedded fallback literal. When kleinlib IS importable, the fallback
is ASSERTED equal to it — drift between this script and the lib fails loudly, never
silently (the same discipline preflight uses).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

# --- schema (single source of truth: kleinlib/schema.py) --------------------
_FALLBACK_HEADER = "experiment\tprimary_metric\tstatus\tcommit\tdescription"
_FALLBACK_AUX = "experiment\tmetric\tvalue"
_AUX_FILENAME = "aux_metrics.tsv"

_SCRIPT = Path(__file__).resolve()
REPO_ROOT = _SCRIPT.parents[4]              # .../klein-auto-research
ASSETS_DIR = _SCRIPT.parents[1] / "assets"  # .../.claude/skills/klein/assets

_TEMPLATES = {
    "study-template.yaml": "study.yaml",
    "program-template.md": "program.md",
    "research-plan-template.md": "research_plan.md",
    "prepare-template.py": "prepare.py",
    "train-template.py": "train.py",
}
_SUBDIRS = ("figures", "models", "report", "sweeps")
_SLUG_RE = re.compile(r"^\d{2}-[a-z0-9][a-z0-9-]*$")


def resolve_headers() -> tuple[str, str]:
    """Return (results_header, aux_header). Prefer kleinlib.schema; assert no drift."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from kleinlib import schema  # type: ignore
    except ImportError:
        return _FALLBACK_HEADER, _FALLBACK_AUX
    header = schema.header_line()
    aux = "\t".join(schema.AUX_COLUMNS)
    assert header == _FALLBACK_HEADER, (
        f"schema drift: kleinlib.schema.header_line()={header!r} != new_study.py "
        f"fallback {_FALLBACK_HEADER!r}; reconcile before scaffolding"
    )
    assert aux == _FALLBACK_AUX, (
        f"aux schema drift: {aux!r} != new_study.py fallback {_FALLBACK_AUX!r}"
    )
    return header, aux


def substitutions(args: argparse.Namespace) -> dict[str, str]:
    """Placeholder -> value, only for values the CLI actually supplied."""
    raw = {
        "STUDY_ID": args.slug,
        "DATE": _dt.date.today().isoformat(),
        "GOAL": args.goal,
        "DOMAIN": args.domain,
        "METRIC_NAME": args.metric,
        "METRIC_GOAL": args.goal_direction,
        "DATA_SOURCE": args.data,
    }
    return {k: v for k, v in raw.items() if v is not None}


def fill(text: str, subs: dict[str, str]) -> str:
    for key, val in subs.items():
        text = text.replace("{{" + key + "}}", val)
    return text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scaffold a Klein study directory.")
    p.add_argument("slug", help="study id as NN-slug, e.g. 00-glm-claims-quickstart")
    p.add_argument("--goal", help="one-sentence study goal")
    p.add_argument("--domain", help="e.g. insurance, credit, energy, general")
    p.add_argument("--metric", help="primary metric name — binary clf: val_auc; "
                                    "regression/severity: val_rmse or val_mae (goal lower); "
                                    "simulation: a scalar like premium_error_pct (goal lower)")
    p.add_argument("--goal-direction", dest="goal_direction",
                   choices=["higher", "lower"], help="is higher or lower better? "
                   "(error-style metrics want lower)")
    p.add_argument("--data", help="data source: data_hub:<name> | kaggle:<handle> | "
                                  "csv:<path> | synthetic:<generator>")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not _SLUG_RE.match(args.slug):
        parser.error(
            f"slug {args.slug!r} must match NN-slug (two digits, hyphen, then a "
            f"lowercase slug), e.g. 00-glm-claims-quickstart"
        )

    study_dir = REPO_ROOT / "studies" / args.slug
    if study_dir.exists():
        print(f"[REFUSE] {study_dir} already exists — refusing to overwrite.",
              file=sys.stderr)
        return 1

    results_header, aux_header = resolve_headers()
    subs = substitutions(args)

    # Create the tree.
    study_dir.mkdir(parents=True)
    for sub in _SUBDIRS:
        d = study_dir / sub
        d.mkdir()
        (d / ".gitkeep").write_text("", encoding="utf-8")

    # Render templates with the supplied placeholders.
    for src, dest in _TEMPLATES.items():
        text = (ASSETS_DIR / src).read_text(encoding="utf-8")
        (study_dir / dest).write_text(fill(text, subs), encoding="utf-8")

    # Ledgers: the header line ONLY (schema-sourced, never hardcoded elsewhere).
    (study_dir / "results.tsv").write_text(results_header + "\n", encoding="utf-8")
    (study_dir / _AUX_FILENAME).write_text(aux_header + "\n", encoding="utf-8")

    rel = study_dir.relative_to(REPO_ROOT)
    print(f"[OK] scaffolded {rel}/")
    for name in ("study.yaml", "program.md", "research_plan.md", "prepare.py",
                 "train.py", "results.tsv", _AUX_FILENAME):
        print(f"       {rel}/{name}")
    for sub in _SUBDIRS:
        print(f"       {rel}/{sub}/  (empty, .gitkeep)")
    print()
    print("Next:")
    print(f"  1. git checkout -b experiments/{args.slug}")
    print("  2. CONSULT — confirm study.yaml + research_plan.md with the user (Gate 0)")
    print("  3. DATA gate — implement prepare.py, then write data_card.md (Gate 1)")
    print("  4. METHOD gate — write method_card.md (Gate 2)")
    print("  5. RUN — edit train.py, one experiment at a time (see SKILL.md Hard Rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
