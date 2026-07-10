"""prepare.py — stable, reproducible data prep for a Klein study.

Keep this file STABLE. It is NOT the mutable experiment surface (train.py is). It
downloads / locates / generates raw data, applies deterministic preprocessing, and
writes a prepared artifact whose path is recorded in study.yaml:data.path.

Scaffolding contract: .claude/skills/klein/references/defaults-and-scaffolding.md
DATA gate (run before modeling): .claude/skills/klein/references/data-gate-protocol.md
"""

from __future__ import annotations

from pathlib import Path

import kleinlib  # noqa: F401 — engine; DATA-gate profiling lives in kleinlib.profile_fallback

# --- data_hub / bundled datasets ---------------------------------------------
# To load a hub-style dataset instead of a local CSV, use the engine's resolver —
# it tries $DATA_HUB (an external data-hub repo) first, then a repo-bundled copy
# under datasets/<name>/, and raises an actionable error otherwise:
#
#     df = kleinlib.data.load_data_hub("insurance-claims")
#
# For kaggle:<handle> download with your own Kaggle credentials; for csv:<path>
# read the file (kleinlib.data.load_prepared); for synthetic:<generator> generate
# deterministically (seed from study.yaml).

RAW_DIR = Path("data/raw")
PREPARED_DIR = Path("data/prepared")
PREPARED_PATH = PREPARED_DIR / "prepared.csv"   # keep in sync with study.yaml:data.path


def ensure_raw_data() -> Path:
    """Download / locate / generate the raw dataset; return its path."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raise NotImplementedError(
        "TODO: implement ensure_raw_data(). Resolve the source named in "
        "study.yaml:data.source (data_hub:<name> | kaggle:<handle> | csv:<path> | "
        "synthetic:<generator>) and return the raw Path. See the file-resolution order "
        "in .claude/skills/klein/references/defaults-and-scaffolding.md."
    )


def build_prepared_artifacts(raw_path: Path) -> Path:
    """Deterministic preprocessing → write the prepared artifact; return its path."""
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    raise NotImplementedError(
        "TODO: implement build_prepared_artifacts(raw_path). Apply ONLY stable, "
        "deterministic transforms (no experiment logic — that belongs in train.py). "
        "CRITICAL value-pattern rule: never trust dtype == 'object'; inspect actual "
        "values and fix string-encoded booleans / numbers-in-strings (the string-dtype "
        "war story). See the mandatory value-pattern check in "
        ".claude/skills/klein/references/data-gate-protocol.md."
    )


def main() -> None:
    raw_path = ensure_raw_data()
    prepared_path = build_prepared_artifacts(raw_path)
    # Optional: run the DATA gate now — kleinlib.profile_fallback.profile(prepared_path)
    # (or the global dataset-profiler skill) → data_card.md before the first model.
    print("---")
    print(f"prepared_path:     {prepared_path}")
    print("status:            ok")


if __name__ == "__main__":
    main()
