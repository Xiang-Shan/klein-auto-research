"""Prepare the Dehejia–Wahba analysis table (study 23) — one row per unit.

Three pinned NBER files (Dehejia's data page), resolved through kleinlib.sources
so the bytes are checked against the contract's sha256 before they are read:

  partition `train`        the NSW experimental sample: 185 treated + 260 controls
  partition `development`  PSID-1, Lalonde's 2,490-man comparison group — the adaptive lane
  partition `test`         CPS-1, the 15,992-man comparison group — SEALED, read once

Only the source's own columns are kept, renamed to one spelling; nothing is
imputed, trimmed, deduplicated or derived here (squares, zero-earnings flags and
propensity scores are specification choices and live in analyze.py). `re78` is
the outcome; every other column is measured before the program.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yaml

from kleinlib.sources import resolve, resolve_inputs

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "prepared" / "prepared.csv"
COLUMNS = ["treat", "age", "education", "black", "hispanic", "married", "nodegree", "re74", "re75", "re78"]
SAMPLES = (("nsw", "train"), ("psid1", "development"), ("cps1", "test"))


def main() -> None:
    contract = yaml.safe_load((HERE / "study.yaml").read_text(encoding="utf-8"))
    data = contract["data"]
    offline = os.environ.get("KLEIN_OFFLINE") == "1"
    primary = resolve(data["source"], study_dir=HERE, offline=offline, expected_sha256=data["sha256"])
    paths = [primary.path, *(r.path for r in resolve_inputs(contract, study_dir=HERE, offline=offline))]
    frames = []
    for path, (sample, partition) in zip(paths, SAMPLES, strict=True):
        raw = pd.read_stata(path)
        missing = sorted(set(COLUMNS) - set(raw.columns))
        if missing:
            raise SystemExit(f"{Path(path).name}: missing columns {missing}")
        frame = raw[COLUMNS].copy()
        frame["treat"] = frame["treat"].astype(int)
        for column in ("age", "education", "black", "hispanic", "married", "nodegree"):
            frame[column] = frame[column].astype(int)
        frame.insert(0, "id", [f"{sample}-{i:05d}" for i in range(len(frame))])
        frame.insert(1, "sample", sample)
        frame.insert(2, "partition", partition)
        frames.append(frame)
    table = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False, lineterminator="\n", float_format="%.6f")
    counts = table.groupby(["sample", "treat"]).size().to_dict()
    print(f"prepared {len(table)} units: " + ", ".join(f"{s}/treat={t}: {n}" for (s, t), n in sorted(counts.items())))


if __name__ == "__main__":
    main()
