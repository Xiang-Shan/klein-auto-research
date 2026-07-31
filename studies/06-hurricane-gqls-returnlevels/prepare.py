"""Prepare the immutable local artifact declared by study.yaml:data.prepared_path.

Two outputs, both under the gitignored ``data/prepared/``:

* ``hurricane_top30.csv`` — the 30 events plus the fitting column
  ``log_damage_usd = log(damage_bn_1995 * 1e9)``. Everything downstream fits on that
  log-dollar column; nothing re-derives it.
* ``reference_cell.json`` — the DATA-IDENTITY ANCHOR: the six published Table-6.8
  statistics recomputed here (Hazen quartiles, ddof=1 sd), the prepared file's SHA-256,
  and the two MLE-lognormal anchor pairs (clean and under the thesis's 10x
  modification). E0001 recomputes this cell through the loop and must match.

The gate is not advisory. If any published statistic moves by more than 1e-4 this
script RAISES — because at n = 30 a silently different sample (the wrong "top 30",
the wrong normalization year) reproduces nothing downstream and every later number
would be a confident answer to the wrong question. See the dataset README's two
provenance traps: the "1925–1995" period label is a mislabel (Table 8 carries three
supplemental pre-1925 storms), and the quartiles only reproduce under Hazen.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import estimators as E  # noqa: E402
import stress as S  # noqa: E402

from kleinlib.data import load_data_hub  # noqa: E402

STUDY_DIR = Path(__file__).resolve().parent
OUT_CSV = STUDY_DIR / "data" / "prepared" / "hurricane_top30.csv"
OUT_JSON = STUDY_DIR / "data" / "prepared" / "reference_cell.json"
THESIS_TABLES = STUDY_DIR / "reference" / "thesis_tables.json"

#: Deviation above which prepare REFUSES to write a usable artifact.
TOLERANCE = 1e-4


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frame = load_data_hub("hurricane_top30_pl1998")
    if not isinstance(frame, __import__("pandas").DataFrame):  # multi-table hub entry
        raise TypeError(f"expected a DataFrame from the hub, got {type(frame)!r}")

    damages = frame["damage_bn_1995"].to_numpy(float)  # billions of 1995 USD
    log_dollars = np.log(damages * 1e9)  # the fitting column
    frame = frame.assign(damage_usd=damages * 1e9, log_damage_usd=log_dollars)

    published = json.loads(THESIS_TABLES.read_text())["table_6_8"]
    observed = {
        "n": int(damages.size),
        "min": float(damages.min()),
        "q1": float(np.quantile(damages, 0.25, method=E.SUMMARY_QUANTILE_METHOD)),
        "q2": float(np.quantile(damages, 0.50, method=E.SUMMARY_QUANTILE_METHOD)),
        "q3": float(np.quantile(damages, 0.75, method=E.SUMMARY_QUANTILE_METHOD)),
        "max": float(damages.max()),
        "mean": float(damages.mean()),
        "std_dev": float(damages.std(ddof=1)),
    }

    print("\n=== data-identity gate — Adjieteh (2024) Table 6.8 (PDF p. 79) ===")
    print(f"{'statistic':>10s}{'published':>14s}{'observed':>16s}{'|deviation|':>14s}")
    failures = []
    for key, want in published.items():
        if key.startswith("_"):
            continue
        got = observed[key]
        deviation = abs(got - float(want))
        flag = "" if deviation <= TOLERANCE else "   <-- FAIL"
        print(f"{key:>10s}{float(want):14.4f}{got:16.6f}{deviation:14.2e}{flag}")
        if deviation > TOLERANCE:
            failures.append((key, want, got, deviation))

    # The two MLE-lognormal anchors — cheap, and they pin the fitting column as well
    # as the sample (a wrong 1e9 scaling would move mu by log(1000) = 6.9).
    clean = E.mle(log_dollars, "lognormal")
    modified = E.mle(S.inflate_max(log_dollars, 10.0), "lognormal")
    anchors = {
        "mle_lognormal_original": {"mu": round(clean.mu, 4), "sigma": round(clean.sigma, 4)},
        "mle_lognormal_modified": {
            "mu": round(modified.mu, 4),
            "sigma": round(modified.sigma, 4),
        },
    }
    expected_anchors = {
        "mle_lognormal_original": {"mu": 22.8002, "sigma": 0.8339},
        "mle_lognormal_modified": {"mu": 22.8769, "sigma": 1.0975},
    }
    print("\n=== MLE-lognormal anchors (Table 6.10, PDF p. 82) ===")
    for name, want in expected_anchors.items():
        got = anchors[name]
        for param in ("mu", "sigma"):
            deviation = abs(got[param] - want[param])
            flag = "" if deviation <= TOLERANCE else "   <-- FAIL"
            print(
                f"{name + '.' + param:>32s}{want[param]:12.4f}{got[param]:14.4f}"
                f"{deviation:14.2e}{flag}"
            )
            if deviation > TOLERANCE:
                failures.append((f"{name}.{param}", want[param], got[param], deviation))

    if failures:
        detail = "; ".join(
            f"{k}: published {w}, observed {g:.6f} (|dev| {d:.2e})" for k, w, g, d in failures
        )
        raise SystemExit(
            f"DATA-IDENTITY GATE FAILED — {len(failures)} statistic(s) deviate by more "
            f"than {TOLERANCE:g}: {detail}. This is NOT the sample Adjieteh (2024) §6.2.2 "
            "fitted; stop and resolve the provenance before any modeling (see the "
            "dataset README's two provenance traps)."
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT_CSV, index=False)
    digest = _sha256(OUT_CSV)

    reference_cell = {
        "study_id": "06-hurricane-gqls-returnlevels",
        "prepared_path": str(OUT_CSV.relative_to(STUDY_DIR)),
        "prepared_sha256": digest,
        "rows": int(len(frame)),
        "fitting_column": "log_damage_usd",
        "fitting_scale": "log(damage_bn_1995 * 1e9)",
        "conventions": {
            "summary_quantiles": E.SUMMARY_QUANTILE_METHOD,
            "std_dev_ddof": 1,
            "thesis_fitting_quantiles": E.THESIS_QUANTILE_METHOD,
        },
        "table_6_8_published": {k: v for k, v in published.items() if not k.startswith("_")},
        "table_6_8_observed": observed,
        "mle_anchors_published": expected_anchors,
        "mle_anchors_observed": anchors,
        "tolerance": TOLERANCE,
        "gate": "PASS",
    }
    OUT_JSON.write_text(json.dumps(reference_cell, indent=2) + "\n")

    print(f"\nwrote {OUT_CSV.relative_to(STUDY_DIR)} ({len(frame)} rows)")
    print(f"  sha256: {digest}")
    print(f"wrote {OUT_JSON.relative_to(STUDY_DIR)}")
    print(
        "GATE PASS — all 8 Table-6.8 statistics and both MLE-lognormal anchors "
        f"reproduce to <= {TOLERANCE:g}."
    )


if __name__ == "__main__":
    main()
