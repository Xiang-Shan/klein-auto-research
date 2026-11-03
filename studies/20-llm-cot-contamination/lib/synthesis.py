"""SYNTHESIZE-stage reduction of the pinned call ledgers and cell tables (study 20).

Read-only over the evidence: it re-scores the committed ``calls/`` shards and the
replication shards kept under ``runs/E####/replications/*-calls/`` with the FIXED
scorer (`lib/prompts.py`), and writes three small tables that findings.md and
claims.lock quote:

* ``tables/synthesis_arms.tsv``     one row per (cell, arm): requests, bare-number
  replies, output tokens, length cut-offs, unparsed replies, distinct answers,
  model_served, and the exact-match it re-derives (an instrument check against the
  notarized value);
* ``tables/synthesis_paired.tsv``   the paired per-item outcome table (both right /
  only CoT / only direct / both wrong) for every cot_gain cell and its re-query;
* ``tables/synthesis_quantities.tsv`` every derived number findings quotes, with
  the arithmetic that produced it.

No model is called (the shards are read, never sent). Run from the study root
after ``prepare.py`` has rebuilt ``data/prepared/index.csv``:

    uv run --locked python -m lib.synthesis
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from lib.prompts import ARMS, exact_match, extract

STUDY = Path(__file__).resolve().parents[1]
BARE = re.compile(r"^\s*-?\$?\s*\d[\d,]*(?:\.\d+)?\s*\.?\s*$")
GSM_SYMBOLIC = ("t1264", "t0116", "t0976", "t1031", "t1088")  # program.md, lead decision
SIZE_DRIFT = ("t1281", "t0466")  # answers that must grow (method_card.md §4)
REP_E0002 = "runs/E0002/replications/20261103T082725Z-calls"
REP_E0003 = "runs/E0003/replications/20261103T084446Z-calls"


def _records(*paths: str, namespace: str | None = None) -> list[dict]:
    out = []
    for rel in paths:
        with gzip.open(STUDY / rel, "rt", encoding="utf-8") as handle:
            for line in handle:
                rec = json.loads(line)
                if namespace is None or rec["namespace"] == namespace:
                    out.append(rec)
    return out


def _arm_and_question(rec: dict) -> tuple[str, str]:
    content = rec["request"]["messages"][0]["content"]
    for arm, template in ARMS.items():
        head, _, tail = template.partition("{question}")
        if content.startswith(head) and content.endswith(tail):
            return arm, content[len(head): len(content) - len(tail)]
    raise ValueError("a request matches neither arm")


def _index() -> dict[str, list[dict]]:
    by_question: dict[str, list[dict]] = defaultdict(list)
    with open(STUDY / "data/prepared/index.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_question[row["question"]].append(row)
    return by_question


def _scored(records: list[dict], index, blocks: set[str]) -> dict[tuple[str, str], dict]:
    """(item_id, arm) -> reply facts, restricted to items of ``blocks``."""
    out: dict[tuple[str, str], dict] = {}
    for rec in records:
        arm, question = _arm_and_question(rec)
        choice = rec["response"]["choices"][0]
        text = choice["message"]["content"]
        for row in index.get(question, []):
            if row["block"] not in blocks:
                continue
            out[(row["id"], arm)] = {
                "template": row["template"],
                "em": exact_match(text, row["answer"]),
                "bare": bool(BARE.match(text or "")),
                "tokens_out": int(rec["tokens_out"]),
                "length": choice.get("finish_reason") == "length",
                "unparsed": extract(text) is None,
                "answer": extract(text),
                "model_served": rec["model_served"],
            }
    return out


def _fmt(value: float, places: int = 6) -> str:
    return f"{value:.{places}f}"


def main() -> None:
    index = _index()
    main_shards = sorted(str(p.relative_to(STUDY)) for p in (STUDY / "calls").glob("*.jsonl.gz"))
    study_records = _records(*main_shards, namespace="study")
    scored = _scored(study_records, index, {"gsm8k", "twin_dev", "twin_sealed", "original"})
    rep2 = _scored(_records(f"{REP_E0002}/E0002-000.jsonl.gz"), index, {"gsm8k"})
    rep3 = _scored(_records(f"{REP_E0003}/E0003-000.jsonl.gz"), index, {"original", "twin_dev"})

    block_of = {row["id"]: row["block"] for rows in index.values() for row in rows}
    cells = {"anchor_gsm8k": ("gsm8k", scored), "twin_dev": ("twin_dev", scored),
             "twin_sealed": ("twin_sealed", scored), "originals": ("original", scored),
             "anchor_gsm8k_requery": ("gsm8k", rep2), "originals_requery": ("original", rep3),
             "twin_dev_requery": ("twin_dev", rep3)}

    arms_rows, q = [], {}
    for cell, (block, source) in cells.items():
        for arm in ("direct", "cot"):
            facts = [v for (item, a), v in source.items() if a == arm and block_of[item] == block]
            if not facts:
                continue
            toks = [f["tokens_out"] for f in facts]
            row = {
                "cell": cell, "arm": arm, "requests": len(facts),
                "bare_replies": sum(f["bare"] for f in facts),
                "bare_share": _fmt(sum(f["bare"] for f in facts) / len(facts), 4),
                "tokens_out_median": _fmt(statistics.median(toks), 1),
                "tokens_out_mean": _fmt(statistics.mean(toks), 1),
                "finish_length": sum(f["length"] for f in facts),
                "unparsed": sum(f["unparsed"] for f in facts),
                "distinct_answers": len({f["answer"] for f in facts}),
                "em_rescored": _fmt(sum(f["em"] for f in facts) / len(facts), 4),
                "model_served": ";".join(sorted({f["model_served"] for f in facts})),
            }
            arms_rows.append(row)
            q[f"{cell}_{arm}_tokens_mean"] = float(row["tokens_out_mean"])
    ratio_rows = {}
    for cell in ("anchor_gsm8k", "twin_dev", "twin_sealed", "anchor_gsm8k_requery"):
        if f"{cell}_direct_tokens_mean" in q:
            ratio_rows[cell] = q[f"{cell}_cot_tokens_mean"] / q[f"{cell}_direct_tokens_mean"]

    # Paired outcome tables from the notarized cell tables (+ the salted re-query of E0002).
    paired_rows = []

    def paired(label: str, pairs: list[tuple[int, int]]) -> dict:
        both = sum(1 for d, c in pairs if d and c)
        cot_only = sum(1 for d, c in pairs if c and not d)
        direct_only = sum(1 for d, c in pairs if d and not c)
        neither = sum(1 for d, c in pairs if not d and not c)
        row = {"cell": label, "n": len(pairs), "both_right": both, "cot_only": cot_only,
               "direct_only": direct_only, "both_wrong": neither}
        paired_rows.append(row)
        return row

    for exp in ("E0002", "E0004", "E0005"):
        with open(STUDY / f"tables/cot_gain_{exp}.tsv", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        paired(exp, [(int(r["score_direct"]), int(r["score_cot"])) for r in rows])
    anchor_items = sorted({item for item, _ in rep2})
    paired("rep:E0002@20261103T082725Z",
           [(rep2[(i, "direct")]["em"], rep2[(i, "cot")]["em"]) for i in anchor_items])

    # M5: item-arm scores that changed between E0002 and its salted re-query.
    changed = sum(1 for key, v in rep2.items() if scored[key]["em"] != v["em"])
    q["m5_changed_item_arm_scores"] = changed
    q["m5_item_arm_scores_compared"] = len(rep2)
    q["m5_changed_share"] = changed / len(rep2)

    # E0003 vs its salted re-query, per side.
    orig_items = [k for k in rep3 if block_of[k[0]] == "original"]
    twin_items = [k for k in rep3 if block_of[k[0]] == "twin_dev"]
    q["rep3_originals_changed"] = sum(1 for k in orig_items if scored[k]["em"] != rep3[k]["em"])
    q["rep3_originals_right_to_wrong"] = sum(
        1 for k in orig_items if scored[k]["em"] == 1 and rep3[k]["em"] == 0)
    q["rep3_originals_wrong_to_right"] = sum(
        1 for k in orig_items if scored[k]["em"] == 0 and rep3[k]["em"] == 1)
    q["rep3_twins_changed"] = sum(1 for k in twin_items if scored[k]["em"] != rep3[k]["em"])
    q["rep3_twins_compared"] = len(twin_items)

    # Contamination splits from the pinned per-template tables.
    def gap_table(exp: str) -> list[dict]:
        with open(STUDY / f"tables/contamination_{exp}.tsv", newline="", encoding="utf-8") as h:
            return list(csv.DictReader(h, delimiter="\t"))

    for exp in ("E0003", "E0006"):
        rows = gap_table(exp)

        def gap(keep) -> float:
            sel = [r for r in rows if keep(r["template"])]
            return sum(int(r["score_original"]) - float(r["twin_mean"]) for r in sel) / len(sel)

        q[f"{exp}_gap_all50"] = gap(lambda t: True)
        q[f"{exp}_gap_other45"] = gap(lambda t: t not in GSM_SYMBOLIC)
        q[f"{exp}_gap_gsmsym5"] = gap(lambda t: t in GSM_SYMBOLIC)
        q[f"{exp}_gap_magnitude48"] = gap(lambda t: t not in SIZE_DRIFT)
        q[f"{exp}_m7_abs_diff_45_vs_50"] = abs(q[f"{exp}_gap_other45"] - q[f"{exp}_gap_all50"])
        q[f"{exp}_templates_differing"] = sum(
            1 for r in rows if abs(int(r["score_original"]) - float(r["twin_mean"])) > 0)
    # Per-template twin means that E0003 and E0006 share for the originals: identical by ledger.
    e3, e6 = gap_table("E0003"), gap_table("E0006")
    q["originals_identical_E0003_E0006"] = sum(
        1 for a, b in zip(e3, e6, strict=True) if a["score_original"] == b["score_original"])

    # Method-card priors M1-M4, M6 from the notarized aux metrics.
    aux: dict[tuple[str, str], float] = {}
    with open(STUDY / "aux_metrics.tsv", newline="", encoding="utf-8") as handle:
        for r in csv.DictReader(handle, delimiter="\t"):
            aux[(r["experiment"], r["metric"])] = float(r["value"])
    q["m2_direct_drop_public_minus_twin_dev"] = aux[("E0002", "em_direct")] - aux[("E0004", "em_direct")]
    q["m3_cot_drop_public_minus_twin_dev"] = aux[("E0002", "em_cot")] - aux[("E0004", "em_cot")]
    for exp, label in (("E0002", "public"), ("E0004", "twin_dev"), ("E0005", "twin_sealed")):
        q[f"headroom_{label}_one_minus_em_direct"] = 1.0 - aux[(exp, "em_direct")]
    q["m4_ci_width_E0003"] = aux[("E0003", "ci_high")] - aux[("E0003", "ci_low")]
    q["E0006_ci_width"] = aux[("E0006", "ci_high")] - aux[("E0006", "ci_low")]
    for cell, ratio in ratio_rows.items():
        q[f"m6_token_ratio_{cell}"] = ratio

    write = STUDY / "tables"
    with open(write / "synthesis_arms.tsv", "w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=list(arms_rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(arms_rows)
    with open(write / "synthesis_paired.tsv", "w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=list(paired_rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(paired_rows)
    with open(write / "synthesis_quantities.tsv", "w", newline="", encoding="utf-8") as handle:
        handle.write("quantity\tvalue\n")
        for key, value in q.items():
            text = str(value) if isinstance(value, int) else _fmt(value, 6)
            handle.write(f"{key}\t{text}\n")
    print("wrote tables/synthesis_arms.tsv, tables/synthesis_paired.tsv, tables/synthesis_quantities.tsv")


if __name__ == "__main__":
    main()
