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
  the arithmetic that produced it;
* ``tables/synthesis_controls.tsv``  POST-HOC controls (added after the referee's
  check 4): a negative control (recorded replies re-scored against permuted golds)
  and positive controls (a known effect planted into the recorded direct scores),
  each run through the study's own interval code, plus truncation diagnostics;
* ``tables/synthesis_familywise.tsv`` Bonferroni-level intervals per prediction
  family (referee check 5), next to a re-derivation of the notarized 95% intervals.

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
    controls_and_familywise(scored)
    print("wrote tables/synthesis_arms.tsv, tables/synthesis_paired.tsv, tables/synthesis_quantities.tsv, "
          "tables/synthesis_controls.tsv, tables/synthesis_familywise.tsv")


# --------------------------------------------------------------------------
# Post-hoc controls and family-wise intervals (referee checks 4 and 5)
# --------------------------------------------------------------------------

#: Seeds of the post-hoc controls, offset from the study's bootstrap seed so no
#: control re-uses a block's or the bootstrap's draws. NOTE (referee R2-2): the
#: streams are NOT all distinct — POS_SEED (20261124) equals NEG_SEED + 1, the seed
#: of the 100 negative-control repeats. The two drive different operations
#: (``permutation`` vs ``choice``), so no result depends on it; the values are kept
#: as committed so the pinned tables stay byte-identical. The reverse plant uses
#: POS_SEED + 1 (20261125).
NEG_SEED = 20261103 + 20  # the gold permutation
NEG_REPEATS = 100  # permutations averaged for the chance level
POS_SEED = 20261103 + 21  # which direct items a planted effect flips
FAMILIES = {"cot_gain": ("P1", "P2", "P4", "P5"), "contamination": ("P3", "P6")}


def _interval(estimate_values, level: float) -> tuple[float, float]:
    import numpy as np

    tail = (1.0 - level) / 2.0
    low, high = np.quantile(np.asarray(estimate_values, dtype=float), [tail, 1.0 - tail])
    return float(low), float(high)


def _gain_boot(cot, direct, clusters):
    """The study's own bootstrap distribution (lib/measure.py, same N_BOOT and seed)."""
    import numpy as np

    from kleinlib.metrology import item_bootstrap, paired_bootstrap
    from lib.measure import BOOT_SEED, N_BOOT

    left, right = np.asarray(cot, dtype=float), np.asarray(direct, dtype=float)
    if clusters is None:
        return paired_bootstrap(left, right, n_boot=N_BOOT, seed=BOOT_SEED).values
    return item_bootstrap(left - right, n_boot=N_BOOT, seed=BOOT_SEED, groups=list(clusters)).values


def _cell_rows(exp: str) -> list[dict]:
    with open(STUDY / f"tables/cot_gain_{exp}.tsv", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def controls_and_familywise(scored: dict) -> None:
    import numpy as np

    from kleinlib.metrology import item_bootstrap, paired_bootstrap
    from lib.measure import BOOT_SEED, N_BOOT

    controls: list[tuple[str, str, str, object]] = []  # (control, cell, quantity, value)

    def put(control: str, cell: str, quantity: str, value) -> None:
        controls.append((control, cell, quantity, value))

    for exp in ("E0002", "E0004", "E0005"):
        rows = _cell_rows(exp)
        ids = [r["item_id"] for r in rows]
        gold = np.array([int(r["answer"]) for r in rows])
        direct = np.array([int(r["score_direct"]) for r in rows])
        cot = np.array([int(r["score_cot"]) for r in rows])
        twins = rows[0]["block"] != "gsm8k"
        clusters = [r["template"] for r in rows] if twins else None
        got_d = [scored[(i, "direct")]["answer"] for i in ids]
        got_c = [scored[(i, "cot")]["answer"] for i in ids]
        # instrument check: the extracted answers re-score to the notarized table
        assert all(int(g == a) == d for g, a, d in zip(got_d, gold, direct, strict=True))
        assert all(int(g == a) == c for g, a, c in zip(got_c, gold, cot, strict=True))

        # (a) NEGATIVE CONTROL: the same replies, golds permuted across the cell's items.
        rng = np.random.default_rng(NEG_SEED)
        perm = rng.permutation(len(rows))
        pd_ = np.array([int(g == a) for g, a in zip(got_d, gold[perm], strict=True)])
        pc_ = np.array([int(g == a) for g, a in zip(got_c, gold[perm], strict=True)])
        lo, hi = _interval(_gain_boot(pc_, pd_, clusters), 0.95)
        put("negative_permuted_gold", exp, "em_direct", round(float(pd_.mean()), 6))
        put("negative_permuted_gold", exp, "em_cot", round(float(pc_.mean()), 6))
        put("negative_permuted_gold", exp, "em_gain", round(float(pc_.mean() - pd_.mean()), 6))
        put("negative_permuted_gold", exp, "ci95_low", round(lo, 6))
        put("negative_permuted_gold", exp, "ci95_high", round(hi, 6))
        means_d, means_c = [], []
        rng = np.random.default_rng(NEG_SEED + 1)
        for _ in range(NEG_REPEATS):
            pm = rng.permutation(len(rows))
            means_d.append(np.mean([g == a for g, a in zip(got_d, gold[pm], strict=True)]))
            means_c.append(np.mean([g == a for g, a in zip(got_c, gold[pm], strict=True)]))
        put("negative_permuted_gold", exp, f"em_direct_mean_over_{NEG_REPEATS}", round(float(np.mean(means_d)), 6))
        put("negative_permuted_gold", exp, f"em_cot_mean_over_{NEG_REPEATS}", round(float(np.mean(means_c)), 6))
        put("negative_permuted_gold", exp, f"em_max_over_{NEG_REPEATS}",
            round(float(max(max(means_d), max(means_c))), 6))

        # (b) POSITIVE CONTROLS: a known effect planted into the recorded direct scores.
        n = len(rows)
        right = np.flatnonzero(direct == 1)
        wrong = np.flatnonzero(direct == 0)
        for planted in (0.10, 0.05):
            k = int(round(planted * n))
            pick = np.random.default_rng(POS_SEED).choice(right, size=k, replace=False)
            d2 = direct.copy()
            d2[pick] = 0  # a seeded set of correct direct items scored wrong: gain +planted
            est = float(cot.mean() - d2.mean())
            lo, hi = _interval(_gain_boot(cot, d2, clusters), 0.95)
            tag = f"positive_plant_gain_{planted:.2f}"
            put(tag, exp, "items_flipped_direct_right_to_wrong", k)
            put(tag, exp, "planted_shift", planted)
            put(tag, exp, "recovered_minus_observed", round(est - float(cot.mean() - direct.mean()), 6))
            put(tag, exp, "em_gain", round(est, 6))
            put(tag, exp, "ci95_low", round(lo, 6))
            put(tag, exp, "ci95_high", round(hi, 6))
            put(tag, exp, "ci_excludes_0", int(lo > 0))
            put(tag, exp, "rule_gain_ge_0.10_holds", int(est >= 0.10 - 1e-12))
        # The opposite direction: a seeded half of the WRONG direct items scored correct.
        k = (len(wrong) + 1) // 2
        pick = np.random.default_rng(POS_SEED + 1).choice(wrong, size=k, replace=False)
        d3 = direct.copy()
        d3[pick] = 1
        est = float(cot.mean() - d3.mean())
        lo, hi = _interval(_gain_boot(cot, d3, clusters), 0.95)
        tag = "positive_plant_direct_wrong_to_right"
        put(tag, exp, "items_flipped_direct_wrong_to_right", k)
        put(tag, exp, "planted_shift", round(-k / n, 6))
        put(tag, exp, "recovered_minus_observed", round(est - float(cot.mean() - direct.mean()), 6))
        put(tag, exp, "em_gain", round(est, 6))
        put(tag, exp, "ci95_low", round(lo, 6))
        put(tag, exp, "ci95_high", round(hi, 6))
        put(tag, exp, "ci_excludes_0", int(hi < 0 or lo > 0))

        # Truncation and clustering of the direct-only wins (referee note 5d).
        direct_only = [i for i, d, c in zip(ids, direct, cot, strict=True) if d == 1 and c == 0]
        cut = sum(1 for i in direct_only if scored[(i, "cot")]["length"])
        put("diagnostic_direct_only", exp, "direct_only_items", len(direct_only))
        put("diagnostic_direct_only", exp, "direct_only_with_cot_cut_at_max_tokens", cut)
        if twins:
            per_t: dict[str, int] = defaultdict(int)
            for i in direct_only:
                per_t[scored[(i, "cot")]["template"]] += 1
            put("diagnostic_direct_only", exp, "templates_holding_direct_only", len(per_t))
            put("diagnostic_direct_only", exp, "max_direct_only_in_one_template", max(per_t.values(), default=0))

    with open(STUDY / "tables/synthesis_controls.tsv", "w", newline="", encoding="utf-8") as handle:
        handle.write("control\tcell\tquantity\tvalue\n")
        for control, cell, quantity, value in controls:
            text = str(value) if isinstance(value, int) else _fmt(float(value), 6)
            handle.write(f"{control}\t{cell}\t{quantity}\t{text}\n")

    # Family-wise (Bonferroni) intervals: alpha 0.05 split over each family's rules.
    aux: dict[tuple[str, str], float] = {}
    with open(STUDY / "aux_metrics.tsv", newline="", encoding="utf-8") as handle:
        for r in csv.DictReader(handle, delimiter="\t"):
            aux[(r["experiment"], r["metric"])] = float(r["value"])
    out = []

    def fam_row(family, pred, exp, estimand, estimate, values, threshold, side):
        m = len(FAMILIES[family])
        level = 1.0 - 0.05 / m
        lo95, hi95 = _interval(values, 0.95)
        lofw, hifw = _interval(values, level)
        bound95 = hi95 if side == "upper" else lo95
        boundfw = hifw if side == "upper" else lofw
        excl = (lambda b: int(b < threshold)) if side == "upper" else (lambda b: int(b > threshold))
        out.append({
            "family": family, "prediction": pred, "experiment": exp, "estimand": estimand,
            "n_comparisons": m, "level": _fmt(level, 6), "estimate": _fmt(estimate, 6),
            "ci95_low": _fmt(lo95, 6), "ci95_high": _fmt(hi95, 6),
            "cifw_low": _fmt(lofw, 6), "cifw_high": _fmt(hifw, 6),
            "threshold": _fmt(threshold, 6), "interval_side_vs_threshold": side,
            "ci95_excludes_threshold": excl(bound95), "cifw_excludes_threshold": excl(boundfw),
        })

    rows = _cell_rows("E0002")
    direct = np.array([int(r["score_direct"]) for r in rows], dtype=float)
    fam_row("cot_gain", "P1", "E0002", "em_direct", float(direct.mean()),
            item_bootstrap(direct, n_boot=N_BOOT, seed=BOOT_SEED).values, 0.85, "lower")
    for pred, exp in (("P2", "E0002"), ("P4", "E0004"), ("P5", "E0005")):
        rows = _cell_rows(exp)
        d = np.array([int(r["score_direct"]) for r in rows])
        c = np.array([int(r["score_cot"]) for r in rows])
        clusters = [r["template"] for r in rows] if rows[0]["block"] != "gsm8k" else None
        values = _gain_boot(c, d, clusters)
        lo, hi = _interval(values, 0.95)
        assert abs(lo - aux[(exp, "ci_low")]) < 1e-9 and abs(hi - aux[(exp, "ci_high")]) < 1e-9
        fam_row("cot_gain", pred, exp, "em_gain", float(c.mean() - d.mean()), values, 0.10, "upper")
    for pred, exp in (("P3", "E0003"), ("P6", "E0006")):
        with open(STUDY / f"tables/contamination_{exp}.tsv", newline="", encoding="utf-8") as h:
            rows = list(csv.DictReader(h, delimiter="\t"))
        o = np.array([float(r["score_original"]) for r in rows])
        y = np.array([float(r["twin_mean"]) for r in rows])
        values = paired_bootstrap(o, y, n_boot=N_BOOT, seed=BOOT_SEED).values
        lo, hi = _interval(values, 0.95)
        assert abs(lo - aux[(exp, "ci_low")]) < 1e-9 and abs(hi - aux[(exp, "ci_high")]) < 1e-9
        fam_row("contamination", pred, exp, "em_gap", float(np.mean(o - y)), values, 0.05, "upper")
    with open(STUDY / "tables/synthesis_familywise.tsv", "w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=list(out[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
