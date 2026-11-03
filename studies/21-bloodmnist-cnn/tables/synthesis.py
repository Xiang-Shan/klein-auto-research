"""SYNTHESIZE-stage derived tables for 21-bloodmnist-cnn (read-only over the evidence).

Reads ONLY committed evidence: results.tsv, runs/E####/seeds.tsv, the pinned per-seed
confusion tables tables/confusion_E####_s{0,1,2}.tsv, the two registered sweep
sidecars and study.yaml's contract values. It trains nothing, reads no image and no
sealed label beyond the row sums of E0009's own pinned confusion tables. Writes:

  tables/synthesis_summary.tsv  quantity -> value (deltas, floors, headroom, SEs, counts)
  tables/controls.tsv           chance-level controls on development and sealed test
  tables/per_class.tsv          seed-mean per-class recall and F1 per run (from confusion)
  tables/seed_dominance.tsv     seed-level comparisons between selected run pairs
  tables/per_class_noise.tsv    binomial SE of the E0004 -> E0008 monocyte recall drop
                                (added after referee note 4; other outputs unchanged;
                                difference SE and per-seed recalls appended after the
                                round-2 referee note 1)

Run from anywhere: `uv run --no-sync python studies/21-bloodmnist-cnn/tables/synthesis.py`.
Deterministic; values rounded to 6 decimals.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

STUDY = Path(__file__).resolve().parents[1]
TABLES = STUDY / "tables"
MIN_DELTA = 0.0438435          # study.yaml tracks.primary.metric.minimum_delta
ITEM_SD = 0.0119694            # study.yaml noise_floor.std
FIT_SD = 0.047219              # study.yaml fit_noise.std
RESNET18_28_ACC = 0.958        # study.yaml P5 rule value (MedMNIST v2 Table 3)
CLASSES = ["basophil", "eosinophil", "erythroblast", "immature_granulocyte",
           "lymphocyte", "monocyte", "neutrophil", "platelet"]  # medmnist info.py order
RUNS = ["E0001", "E0002", "E0003", "E0004", "E0005", "E0006", "E0007", "E0008", "E0009"]


def r6(x: float) -> float:
    return round(float(x), 6)


def results() -> dict[str, float]:
    with open(STUDY / "results.tsv", encoding="utf-8") as fh:
        return {row["experiment"]: float(row["primary_metric"])
                for row in csv.DictReader(fh, delimiter="\t")}


def seeds(exp: str) -> dict[str, np.ndarray]:
    with open(STUDY / "runs" / exp / "seeds.tsv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return {key: np.array([float(r[key]) for r in rows]) for key in rows[0]}


def confusion(exp: str, s: int) -> np.ndarray:
    lines = (TABLES / f"confusion_{exp}_s{s}.tsv").read_text(encoding="utf-8").splitlines()
    return np.array([[float(v) for v in ln.split("\t")[1:]] for ln in lines[1:]])


def per_class(M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tp = np.diag(M)
    recall = tp / M.sum(1)
    den = 2 * tp + (M.sum(0) - tp) + (M.sum(1) - tp)
    f1 = np.divide(2 * tp, den, out=np.zeros_like(tp), where=den > 0)
    return recall, f1


def write(name: str, header: list[str], rows: list[list[object]]) -> None:
    with open(TABLES / name, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    res = results()
    sd = {e: seeds(e) for e in RUNS}
    summary: list[tuple[str, float]] = []

    def put(name: str, value: float) -> None:
        summary.append((name, r6(value)))

    # --- keep chain and discards (development, track primary) -------------------
    put("keep_E0004_minus_E0001", res["E0004"] - res["E0001"])
    put("keep_E0008_minus_E0004", res["E0008"] - res["E0004"])
    for e, inc in (("E0002", "E0001"), ("E0003", "E0001"), ("E0005", "E0004"),
                   ("E0006", "E0004"), ("E0007", "E0004")):
        put(f"{e}_minus_{inc}", res[e] - res[inc])
    for e, inc in (("E0004", "E0001"), ("E0006", "E0004"), ("E0007", "E0004"),
                   ("E0008", "E0004"), ("E0005", "E0004")):
        put(f"{e}_minus_{inc}_in_floors", (res[e] - res[inc]) / MIN_DELTA)
    put("E0006_short_of_bar", res["E0004"] + MIN_DELTA - res["E0006"])
    put("E0007_short_of_bar", res["E0004"] + MIN_DELTA - res["E0007"])
    put("E0008_margin_over_bar", res["E0008"] - (res["E0004"] + MIN_DELTA))
    put("E0008_minus_E0006", res["E0008"] - res["E0006"])
    put("E0008_minus_E0007", res["E0008"] - res["E0007"])
    put("E0004_minus_E0003", res["E0004"] - res["E0003"])
    put("E0001_minus_E0002", res["E0001"] - res["E0002"])
    put("E0001_minus_E0002_in_floors", (res["E0001"] - res["E0002"]) / MIN_DELTA)
    put("keep_bar_after_E0004", res["E0004"] + MIN_DELTA)
    put("keep_bar_after_E0008", res["E0008"] + MIN_DELTA)
    for e in ("E0001", "E0004", "E0008"):
        put(f"headroom_h_at_{e}", (1.0 - res[e]) / MIN_DELTA)
    put("bar_over_item_sd", MIN_DELTA / ITEM_SD)
    put("bar_over_fit_sd", MIN_DELTA / FIT_SD)
    put("fit_sd_over_item_sd", FIT_SD / ITEM_SD)

    # --- anchor: card priors K3, fit-noise blocks ------------------------------
    acc1 = sd["E0001"]["val_accuracy"].mean()
    put("E0001_val_accuracy_seed_mean", acc1)
    put("E0001_accuracy_minus_macro_f1", acc1 - res["E0001"])
    blocks = np.array([res["E0001"], 0.671912, 0.588594, 0.668756])  # fit_noise sidecar
    put("anchor_four_block_mean", blocks.mean())
    put("anchor_four_block_std", blocks.std(ddof=1))
    put("E0001_ece_seed_mean", sd["E0001"]["val_ece"].mean())
    put("E0001_mlogloss_seed_mean", sd["E0001"]["val_mlogloss"].mean())
    put("E0002_val_accuracy_seed_mean", sd["E0002"]["val_accuracy"].mean())

    # --- seed spread -----------------------------------------------------------
    for e in RUNS:
        put(f"{e}_seed_std", sd[e]["primary_metric"].std(ddof=1))

    w8 = sd["E0008"]["wall_seconds"]
    put("E0008_seed_wall_max_over_min", w8.max() / w8.min())

    # --- sealed confirmation ---------------------------------------------------
    put("sealed_minus_dev_E0009_minus_E0008", res["E0009"] - res["E0008"])
    acc9 = sd["E0009"]["val_accuracy"]
    n_test = int(confusion("E0009", 0).sum())
    put("E0009_n_test", n_test)
    put("E0009_val_accuracy_seed_mean", acc9.mean())
    put("E0009_val_accuracy_seed_std", acc9.std(ddof=1))
    put("E0009_val_accuracy_seed_max", acc9.max())
    gap = RESNET18_28_ACC - acc9.mean()
    se_ref = math.sqrt(RESNET18_28_ACC * (1 - RESNET18_28_ACC) / n_test)
    se_own = math.sqrt(acc9.mean() * (1 - acc9.mean()) / n_test)
    put("resnet18_28_minus_E0009_accuracy", gap)
    put("binomial_se_at_0958_n_test", se_ref)
    put("gap_in_binomial_se_at_0958", gap / se_ref)
    put("binomial_se_at_E0009_n_test", se_own)
    put("gap_in_binomial_se_at_E0009", gap / se_own)
    put("two_sample_se", math.sqrt(se_ref ** 2 + se_own ** 2))
    put("gap_in_two_sample_se", gap / math.sqrt(se_ref ** 2 + se_own ** 2))
    put("E0009_train_rows", sd["E0009"]["train_rows"][0])
    put("E0008_train_rows", sd["E0008"]["train_rows"][0])

    # --- multiplicity ----------------------------------------------------------
    put("n_comparisons_frontier", 7)        # E0002..E0008, each against its incumbent
    put("n_registered_predictions", 5)      # P1..P5
    put("n_card_priors", 5)                 # K1..K5 (method_card.md section 4)
    put("n_development_configs_selected_from", 8)  # E0001..E0008
    put("n_sealed_accesses", 1)             # E0009
    put("p_all_three_seeds_dominate_exchangeable", 1 / 20)  # 3 vs 3, one-sided

    write("synthesis_summary.tsv", ["quantity", "value"], [[k, v] for k, v in summary])

    # --- controls --------------------------------------------------------------
    rows = []
    for part, exp in (("development", "E0001"), ("test", "E0009")):
        counts = confusion(exp, 0).sum(1)
        n = counts.sum()
        p = counts / n
        maj = int(np.argmax(counts))
        f1_maj = 2 * p[maj] / (1 + p[maj]) / len(p)          # constant majority prediction
        f1_unif = float(np.mean(2 * p * (1 / len(p)) / (p + 1 / len(p))))  # uniform guess
        rows += [
            [part, "n_items", int(n)],
            [part, "majority_class", maj],
            [part, "majority_class_accuracy", r6(p[maj])],
            [part, "majority_class_macro_f1", r6(f1_maj)],
            [part, "uniform_random_accuracy", r6(1 / len(p))],
            [part, "uniform_random_expected_macro_f1", r6(f1_unif)],
            [part, "prior_matched_random_expected_macro_f1", r6(np.mean(p))],
            [part, "prior_matched_random_expected_accuracy", r6(np.sum(p ** 2))],
        ]
    rows += [["development", "pixel_linear_softmax_macro_f1_E0002", r6(res["E0002"])],
             ["development", "pixel_linear_softmax_accuracy_E0002",
              r6(sd["E0002"]["val_accuracy"].mean())]]
    write("controls.tsv", ["partition", "control", "value"], rows)

    # --- per-class -------------------------------------------------------------
    rows = []
    for e in RUNS:
        M = sum(confusion(e, s) for s in range(3)) / 3.0  # seed-mean table
        rec, f1 = per_class(M)
        for k, name in enumerate(CLASSES):
            rows.append([e, k, name, r6(rec[k]), r6(f1[k])])
    write("per_class.tsv", ["experiment", "class", "name", "recall_seed_mean", "f1_seed_mean"], rows)

    # --- seed dominance (descriptive; seeds share index and batch order) --------
    rows = []
    for a, b in (("E0004", "E0001"), ("E0006", "E0004"), ("E0007", "E0004"), ("E0005", "E0004"),
                 ("E0008", "E0004"), ("E0008", "E0006"), ("E0008", "E0007")):
        xa, xb = sd[a]["primary_metric"], sd[b]["primary_metric"]
        wins = int(sum(int(u > v) for u in xa for v in xb))
        paired = xa - xb
        rows.append([a, b, wins, 9, r6(xa.min() - xb.max()), r6(paired.min()), r6(paired.mean()),
                     r6(paired.max())])
    write("seed_dominance.tsv", ["candidate", "reference", "pair_wins", "pairs", "min_minus_max",
                                 "paired_diff_min", "paired_diff_mean", "paired_diff_max"], rows)
    # --- per-class noise on the monocyte drop (referee note 4) ------------------
    n_mono = int(confusion("E0008", 0).sum(1)[5])
    rec4 = per_class(sum(confusion("E0004", s) for s in range(3)) / 3.0)[0][5]
    rec8 = per_class(sum(confusion("E0008", s) for s in range(3)) / 3.0)[0][5]
    drop = rec4 - rec8
    se4 = math.sqrt(rec4 * (1 - rec4) / n_mono)
    se8 = math.sqrt(rec8 * (1 - rec8) / n_mono)
    write("per_class_noise.tsv", ["quantity", "value"], [
        ["n_dev_monocytes", n_mono],
        ["monocyte_recall_drop_E0004_to_E0008", r6(drop)],
        ["binomial_se_at_E0004_recall", r6(se4)],
        ["binomial_se_at_E0008_recall", r6(se8)],
        ["drop_in_se_at_E0004", r6(drop / se4)],
        ["drop_in_se_at_E0008", r6(drop / se8)],
        # round-2 referee note 1: the rows above divide a DIFFERENCE by the SE of ONE
        # recall. The independent-samples SE of the difference is below; the two recalls
        # share the same images, so a paired SE could be smaller -- unmeasured here.
        ["diff_se_independent_samples", r6(math.sqrt(se4 ** 2 + se8 ** 2))],
        ["drop_in_diff_se_independent_samples", r6(drop / math.sqrt(se4 ** 2 + se8 ** 2))],
    ] + [[f"monocyte_recall_{e}_s{s}", r6(per_class(confusion(e, s))[0][5])]
         for e in ("E0004", "E0008") for s in range(3)])
    print("wrote synthesis_summary.tsv, controls.tsv, per_class.tsv, seed_dominance.tsv, per_class_noise.tsv")


if __name__ == "__main__":
    main()
