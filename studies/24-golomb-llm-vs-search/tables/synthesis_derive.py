"""SYNTHESIZE-stage derivation for study 24 (read-only over pinned evidence).

Reads ONLY committed evidence — tables/solution_E000{1,4,5,6}.json, runs/*/manifest.json,
runs/*/usage.json, runs/E0004/replications/20261103T090054Z.json, the committed call
shards calls/E000{2,3,4,6}-000.jsonl.gz, study_state.json, aux_metrics.tsv, study.yaml
and verify.py's pinned ORACLE (read with ast, never imported) — and writes two tables beside it.
search.py (the mutable surface) is never imported: its extraction rule is re-implemented
in strict_entries() so the ledger recount (referee note 2) is independent of it:

  tables/synthesis_pairs.tsv    one row per (arm, order, trial): optimum, best verified
                                length, gap, matched, first-match index, valid/unparsed,
                                first-batch signatures
  tables/synthesis_summary.tsv  study-level aggregates, the exact McNemar tests at pair
                                and order level, n_comparisons, cost and usage totals

No model call, no search, no verifier run. Re-run:
  uv run --no-sync python studies/24-golomb-llm-vs-search/tables/synthesis_derive.py
"""

from __future__ import annotations

import ast
import gzip
import json
import re
from pathlib import Path

from kleinlib.metrology import mcnemar_exact

STUDY = Path(__file__).resolve().parents[1]

# The tabulated rulers the data card transcribed (data_card.md, verifier positive control).
TAB_8 = [0, 1, 4, 9, 15, 22, 32, 34]
TAB_11 = [0, 1, 4, 13, 28, 33, 47, 54, 64, 70, 72]
# The other 11-mark ruler at the tabulated length (method_card.md; referee note 1).
TAB_11B = [0, 1, 9, 19, 24, 31, 52, 56, 58, 69, 72]


def oracle() -> dict:
    tree = ast.parse((STUDY / "verify.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ORACLE" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit("ORACLE not found in verify.py")


def is_golomb(r, n):
    if not isinstance(r, list) or len(r) != n or not all(isinstance(x, int) for x in r):
        return False
    if r[0] != 0 or any(b <= a for a, b in zip(r, r[1:])):
        return False
    d = [b - a for i, a in enumerate(r) for b in r[i + 1:]]
    return len(d) == len(set(d))


def strict_entries(text, batch):
    """The declared extraction rule (method card §3c, program.md instrument notes),
    re-implemented here so search.py is never imported: the outermost [...] span as
    JSON (one bare ruler is wrapped), else every complete inner list; first `batch`
    entries; nothing unwrapped or repaired (an object entry stays invalid)."""
    entries = None
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start:end + 1])
        except ValueError:
            value = None
        if isinstance(value, list):
            if value and all(isinstance(v, int) and not isinstance(v, bool) for v in value):
                value = [value]
            entries = value
    if entries is None:
        entries = []
        for chunk in re.findall(r"\[[^\[\]]*\]", text):
            try:
                entries.append(json.loads(chunk))
            except ValueError:
                continue
    return entries[:batch]


def repeated_differences(r):
    d = [b - a for i, a in enumerate(r) for b in r[i + 1:]]
    return len(d) - len(set(d))


def common_prefix(a, b):
    k = 0
    for x, y in zip(a, b):
        if x != y:
            break
        k += 1
    return k


def main() -> None:
    orc = oracle()
    optima = {int(k): int(v) for k, v in orc["optima"].items()}
    rows = []
    for exp in ("E0001", "E0004", "E0005", "E0006"):
        sol = json.loads((STUDY / "tables" / f"solution_{exp}.json").read_text(encoding="utf-8"))
        for p in sol["pairs"]:
            n, opt = int(p["order"]), optima[int(p["order"])]
            best = p.get("best")
            valid_best = best is not None and is_golomb(best, n)
            length = best[-1] if valid_best else None
            fb = p.get("first_batch") or []
            fb_lists = [r for r in fb if isinstance(r, list)]
            row = {
                "experiment": exp,
                "arm": sol["arm"],
                "lane": sol["lane"],
                "order": n,
                "trial": int(p["trial"]),
                "optimum": opt,
                "best_length": "NA" if length is None else length,
                "gap": "NA" if length is None else length - opt,
                "matched": int(length == opt),
                "first_match_index": (
                    p.get("first_optimal_evaluation") if sol["arm"] == "search"
                    else p.get("first_optimal_proposal")
                ),
                "evaluations": int(p["evaluations"]),
                "valid_rulers": p.get("valid_rulers", "NA"),
                "unparsed_replies": p.get("unparsed_replies", "NA"),
                "fb_rulers_with_n_marks": (
                    sum(len(r) == n for r in fb_lists) if sol["arm"] == "llm" else "NA"
                ),
                "fb_valid": sum(is_golomb(r, n) for r in fb_lists) if sol["arm"] == "llm" else "NA",
                "fb_min_repeated_differences": (
                    min((repeated_differences(r) for r in fb_lists if len(r) == n), default="NA")
                    if sol["arm"] == "llm" else "NA"
                ),
                "fb_prefix_tab8_ge7": (
                    sum(common_prefix(r, TAB_8) >= 7 for r in fb_lists) if sol["arm"] == "llm" else "NA"
                ),
                "fb_prefix_tab11_ge6": (
                    sum(common_prefix(r, TAB_11) >= 6 for r in fb_lists) if sol["arm"] == "llm" else "NA"
                ),
                "best_is_prefix_of_tab11": (
                    int(length is not None and best == TAB_11[: len(best)]) if sol["arm"] == "llm" else "NA"
                ),
            }
            row["first_match_index"] = "NA" if row["first_match_index"] is None else row["first_match_index"]
            rows.append(row)

    cols = list(rows[0])
    with (STUDY / "tables" / "synthesis_pairs.tsv").open("w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")

    def sel(exp):
        return [r for r in rows if r["experiment"] == exp]

    summary: list[tuple[str, object, str]] = []

    def put(name, value, note):
        summary.append((name, value, note))

    # matched counts per cell
    for exp in ("E0001", "E0004", "E0005", "E0006"):
        put(f"{exp}_matched", sum(r["matched"] for r in sel(exp)), "pairs matched, recomputed from the solution table")
    put("dev_delta_llm_minus_search", sum(r["matched"] for r in sel("E0004")) - sum(r["matched"] for r in sel("E0001")), "pairs, E0004 minus E0001")
    put("sealed_delta_llm_minus_search", sum(r["matched"] for r in sel("E0006")) - sum(r["matched"] for r in sel("E0005")), "pairs, E0006 minus E0005")

    # exact McNemar, pair level and order level (development)
    def key(r):
        return (r["order"], r["trial"])
    llm = {key(r): r["matched"] for r in sel("E0004")}
    srch = {key(r): r["matched"] for r in sel("E0001")}
    keys = sorted(llm)
    m = mcnemar_exact([llm[k] for k in keys], [srch[k] for k in keys])
    put("dev_pair_mcnemar_n10", int(m["n10"]), "pairs llm matched, search did not (12 pairs)")
    put("dev_pair_mcnemar_n01", int(m["n01"]), "pairs search matched, llm did not")
    put("dev_pair_mcnemar_p", round(float(m["p_value"]), 6), "exact two-sided; treats the 12 pairs as independent, which the order clustering contradicts")
    orders = sorted({k[0] for k in keys})
    lo = [int(any(llm[(o, t)] for t in range(3))) for o in orders]
    so = [int(any(srch[(o, t)] for t in range(3))) for o in orders]
    mo = mcnemar_exact(lo, so)
    put("dev_order_mcnemar_n10", int(mo["n10"]), "orders (of 4) with any llm match and no search match")
    put("dev_order_mcnemar_n01", int(mo["n01"]), "orders with a search match and no llm match")
    put("dev_order_mcnemar_p", round(float(mo["p_value"]), 6), "exact two-sided, 4 orders as the unit")
    put("llm_orders_all_or_none", sum(len({llm[(o, t)] for t in range(3)}) == 1 for o in orders), "development orders (of 4) where all 3 llm trials agree")

    # multiplicity
    put("n_comparisons_arm_contrast", 2, "development (E0004 vs E0001) and sealed (E0006 vs E0005)")
    put("n_comparisons_predictions", 5, "P1-P5, each a deterministic rule on one cell")
    put("n_comparisons_card_priors", 5, "method card part 4(b) priors C1-C5, descriptive checks")
    put("bonferroni_alpha_arm_contrast", round(0.05 / 2, 6), "0.05 over the 2 arm contrasts")

    # search gaps per order
    for exp in ("E0001", "E0005"):
        for o in sorted({r["order"] for r in sel(exp)}):
            gaps = [r["gap"] for r in sel(exp) if r["order"] == o]
            put(f"search_gap_mean_n{o}", round(sum(gaps) / len(gaps), 3), f"{exp}: mean best_length minus optimum over 3 trials, length units")
            put(f"search_gap_min_n{o}", min(gaps), f"{exp}: smallest gap over 3 trials")
    gaps10 = [r["gap"] for r in sel("E0004") if r["order"] == 10]
    put("llm_gap_n10", max(gaps10), "E0004 order 10: every trial best 70 vs optimum 55")

    # llm timing / recall signatures
    idx = [r["first_match_index"] for r in sel("E0004") if r["matched"]]
    put("llm_first_match_proposal_min", min(idx), "E0004, proposal index (of 200) of the first optimal ruler")
    put("llm_first_match_proposal_max", max(idx), "E0004")
    put("llm_matches_after_proposal_1", sum(i > 1 for i in idx), "E0004 matched pairs whose first optimum came after the first batch")
    put("card_prior_C4_threshold", sum(r["matched"] for r in sel("E0004")) / 2, "M_llm / 2; prior C4 needs first_batch_matches at or above it")
    for exp in ("E0004", "E0006"):
        put(f"{exp}_fb_prefix_tab8_ge7", sum(r["fb_prefix_tab8_ge7"] for r in sel(exp)), "first-batch rulers sharing the first 7 marks of the tabulated 8-mark ruler")
        put(f"{exp}_fb_prefix_tab11_ge6", sum(r["fb_prefix_tab11_ge6"] for r in sel(exp)), "first-batch rulers sharing at least the first 6 marks of the tabulated 11-mark ruler")
        put(f"{exp}_fb_rulers", sum(10 for _ in sel(exp)), "first-batch slots (10 per pair)")
        put(f"{exp}_fb_valid", sum(r["fb_valid"] for r in sel(exp)), "valid Golomb rulers in the first batches")
        put(f"{exp}_fb_with_n_marks", sum(r["fb_rulers_with_n_marks"] for r in sel(exp)), "first-batch rulers with the requested number of marks")
    put("E0006_fb_min_repeated_differences", min(r["fb_min_repeated_differences"] for r in sel("E0006")), "fewest repeated differences in any sealed first-batch ruler with n marks")
    put("E0004_n9_valid_rulers", sum(r["valid_rulers"] for r in sel("E0004") if r["order"] == 9), "valid 9-mark rulers in 600 proposals")
    put("E0004_best_is_tab11_prefix", sum(r["best_is_prefix_of_tab11"] for r in sel("E0004")), "E0004 pairs whose best ruler is a prefix of the tabulated 11-mark ruler (orders 10 and 11)")

    # parse / validity rates
    aux = {}
    for line in (STUDY / "aux_metrics.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        e, k, v = line.split("\t")
        aux[(e, k)] = float(v)
    for exp in ("E0004", "E0006"):
        calls = aux[(exp, "calls_total")]
        put(f"{exp}_unparsed_rate", round(aux[(exp, "unparsed_replies")] / calls, 4), "unparsed replies / calls")
        put(f"{exp}_valid_rate", round(aux[(exp, "valid_rulers")] / aux[(exp, "evaluations")], 4), "valid rulers / candidate evaluations")
    put("E0004_cached_share", round(aux[("E0004", "calls_cached")] / aux[("E0004", "calls_total")], 4), "share of E0004's requests answered from the E0002/E0003 shards")

    # compute (not matched)
    put("wall_ratio_dev_llm_over_search", round(aux[("E0004", "wall_seconds")] / aux[("E0001", "wall_seconds")], 0), "aux wall_seconds, E0004 / E0001")
    put("wall_ratio_sealed_llm_over_search", round(aux[("E0006", "wall_seconds")] / aux[("E0005", "wall_seconds")], 0), "aux wall_seconds, E0006 / E0005")

    # usage totals across every live call the study made
    live_calls = live_tokens = 0
    for exp in ("E0002", "E0003", "E0004", "E0006"):
        u = json.loads((STUDY / "runs" / exp / "usage.json").read_text(encoding="utf-8"))
        live_calls += int(u["calls"])
        live_tokens += int(u["tokens"])
    rep = json.loads((STUDY / "runs/E0004/replications/20261103T090054Z.json").read_text(encoding="utf-8"))
    sb = rep["searcher_block"]
    rep_tokens = int(sb["tokens_in"] + sb["tokens_out"])
    put("replication_live_calls", int(sb["calls_total"] - sb["calls_cached"]), "salted re-query of E0004")
    put("replication_tokens", rep_tokens, "tokens_in + tokens_out of the salted re-query")
    put("study_live_calls", live_calls + int(sb["calls_total"] - sb["calls_cached"]), "E0002 + E0003 + E0004 + E0006 + replication, live (uncached) calls")
    put("study_live_tokens", live_tokens + rep_tokens, "same scope, tokens in + out")
    put("price_configured", int("price" in (STUDY / "study.yaml").read_text(encoding="utf-8").split("calls:", 1)[1].split("max_run_seconds", 1)[0]), "1 if study.yaml calls: declares price:, else 0 (usd 0 then means unpriced)")

    # data card NOTE 5 / WARN 1: cross-check the self-reported first batches and the
    # per-pair call count against the pinned call ledger (requests keyed by sha256, so a
    # request E0004 answered from the E0002/E0003 shards is the same record).
    shards = {
        "E0004": ["calls/E0002-000.jsonl.gz", "calls/E0003-000.jsonl.gz", "calls/E0004-000.jsonl.gz"],
        "E0006": ["calls/E0006-000.jsonl.gz"],
    }
    for exp, files in shards.items():
        recs: dict[str, dict] = {}
        for f in files:
            with gzip.open(STUDY / f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    recs.setdefault(r["key"], r)
        sol = json.loads((STUDY / "tables" / f"solution_{exp}.json").read_text(encoding="utf-8"))
        lane_orders = set(sol["orders"])
        per_pair: dict[tuple[int, int], int] = {}
        first: dict[tuple[int, int], list[dict]] = {}
        for r in recs.values():
            text = r["request"]["messages"][1]["content"]
            n = int(re.search(r"with (\d+) marks", text).group(1))
            k = int(re.search(r"proposal (\d+) of", text).group(1))
            if n not in lane_orders:
                continue
            per_pair[(n, int(r["sample"]))] = per_pair.get((n, int(r["sample"])), 0) + 1
            if k == 1:
                first.setdefault((n, int(r["sample"])), []).append(r)
        agree = 0
        for p in sol["pairs"]:
            (r,) = first[(p["order"], p["trial"])]
            reply = r["response"]["choices"][0]["message"]["content"]
            lists = [json.loads(m) for m in re.findall(r"\[[0-9,\s]+\]", reply)]
            agree += int(lists[:10] == p["first_batch"])
        put(f"{exp}_ledger_calls_min_per_pair", min(per_pair.values()), "calls in the ledger per (order, trial), minimum")
        put(f"{exp}_ledger_calls_max_per_pair", max(per_pair.values()), "maximum")
        put(f"{exp}_ledger_first_batch_agree", agree, f"pairs (of {len(sol['pairs'])}) whose stored first batch equals the ledger's first reply")
        distinct = []
        for o in sorted(lane_orders):
            distinct.append(len({json.dumps(first[(o, t)][0]["request"], sort_keys=True) for t in range(3)}))
        put(f"{exp}_distinct_first_requests_per_order", max(distinct), "distinct first requests across the 3 trials of an order (max over orders)")
    put("E0004_n9_proposals", 3 * 200, "order-9 proposals in E0004 (3 trials x 200)")

    # Referee note 2 (2026-11-03): recompute "no valid ruler" from the pinned shards
    # instead of the searcher's self-reported valid_rulers. Two readings of every reply
    # in the cell: (a) EVERY bracketed integer list anywhere in the reply, no batch cap
    # (the most generous reading); (b) the first `llm_batch` such lists per reply. A list
    # counts if it has the order's n marks and passes is_golomb above (this file's own
    # check, not search.py's).
    inner = re.compile(r"\[[^\[\]]*\]")
    for exp, files in shards.items():
        recs = {}
        for f in files:
            with gzip.open(STUDY / f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    recs.setdefault(r["key"], r)
        sol = json.loads((STUDY / "tables" / f"solution_{exp}.json").read_text(encoding="utf-8"))
        lane_orders = set(sol["orders"])
        replies = lists_n = valid_any = valid_capped = valid_strict = 0
        optimal_seen: dict[int, set[tuple[int, ...]]] = {}
        g_best: dict[tuple[int, int], int] = {}
        g_first: dict[tuple[int, int], int] = {}
        for r in recs.values():
            text = r["request"]["messages"][1]["content"]
            n = int(re.search(r"with (\d+) marks", text).group(1))
            k = int(re.search(r"proposal (\d+) of", text).group(1))
            if n not in lane_orders:
                continue
            replies += 1
            content = r["response"]["choices"][0]["message"]["content"] or ""
            parsed = []
            for chunk in inner.findall(content):
                try:
                    value = json.loads(chunk)
                except ValueError:
                    continue
                if isinstance(value, list) and value and all(
                    isinstance(x, int) and not isinstance(x, bool) for x in value
                ):
                    parsed.append(value)
            lists_n += sum(len(v) == n for v in parsed)
            valid_any += sum(is_golomb(v, n) for v in parsed)
            valid_capped += sum(is_golomb(v, n) for v in parsed[: int(orc["llm_batch"])])
            valid_strict += sum(is_golomb(v, n) for v in strict_entries(content, int(orc["llm_batch"])))
            pair = (n, int(r["sample"]))
            for v in strict_entries(content, int(orc["llm_batch"])):
                if is_golomb(v, n) and v[-1] == optima[n]:
                    optimal_seen.setdefault(n, set()).add(tuple(v))
            for v in parsed[: int(orc["llm_batch"])]:
                if is_golomb(v, n):
                    g_best[pair] = min(g_best.get(pair, v[-1]), v[-1])
                    if v[-1] == optima[n]:
                        g_first[pair] = min(g_first.get(pair, k), k)
        put(f"{exp}_ledger_replies", replies, "lane replies read from the pinned call shards")
        # Referee note 1: which optimal rulers (and orientations) were ever proposed.
        for o in sorted(lane_orders):
            seen = optimal_seen.get(o, set())
            tab = {8: TAB_8, 11: TAB_11}.get(o)
            put(f"{exp}_n{o}_distinct_optimal_rulers_proposed", len(seen), "distinct valid rulers at the tabulated length in any proposal (strict reading)")
            if tab is not None:
                mirror = tuple(tab[-1] - x for x in reversed(tab))
                put(f"{exp}_n{o}_printed_row_proposed", int(tuple(tab) in seen), "1 if the table's printed row was proposed")
                put(f"{exp}_n{o}_mirror_row_proposed", int(mirror in seen), "1 if its mirror image was proposed")
            if o == 11:
                other = tuple(TAB_11B)
                put(f"{exp}_n11_other_optimum_proposed", int(other in seen or tuple(72 - x for x in reversed(other)) in seen), "1 if the second 11-mark optimum (either orientation) was proposed")
        put(f"{exp}_ledger_valid_strict", valid_strict, "valid rulers under the declared strict extraction, recomputed here (compare aux valid_rulers)")
        put(f"{exp}_searcher_valid_rulers", int(aux[(exp, "valid_rulers")]), "searcher-reported valid_rulers (aux), for comparison")
        put(f"{exp}_ledger_wrapped_valid_extra", valid_capped - valid_strict, "valid rulers only the generous reading counts (e.g. lists wrapped in objects), post-hoc")
        put(f"{exp}_ledger_generous_matched", len(g_first), "pairs matched if every bracketed list is read (first llm_batch per reply); post-hoc")
        put(f"{exp}_ledger_generous_first_batch_matches", sum(v == 1 for v in g_first.values()), "same reading, optimum already in proposal 1")
        same = all(
            g_first.get((p["order"], p["trial"])) == p.get("first_optimal_proposal")
            and g_best.get((p["order"], p["trial"])) == p.get("best_length")
            for p in sol["pairs"]
        )
        put(f"{exp}_ledger_generous_pairs_unchanged", int(same), "1 if every pair's best length and first optimal proposal equal the searcher's strict reading")
        put(f"{exp}_ledger_lists_with_n_marks", lists_n, "every bracketed integer list with the order's n marks, no batch cap")
        put(f"{exp}_ledger_valid_any", valid_any, "of those, valid Golomb rulers (this file's check), no batch cap")
        put(f"{exp}_ledger_valid_first_batch_lists", valid_capped, f"valid Golomb rulers among the first {orc['llm_batch']} lists per reply")

    # priors scorecard: P(rule holds) as stated in method_card.md part 4(a) and in the
    # study.yaml RQ priors (RQ2 "about even" -> P2 0.5; RQ3 "about 0.5" -> P3; RQ4 0.85 -> P4,
    # 0.4 -> P5; RQ1 states no probability). Outcomes from the ledger (study_state.json).
    state = json.loads((STUDY / "study_state.json").read_text(encoding="utf-8"))
    held = {pid: int(rec.get("verdict") == "supported") for pid, rec in state["predictions"].items()}
    card = {"P1": 0.95, "P2": 0.30, "P3": 0.25, "P4": 0.97, "P5": 0.15}
    consult = {"P2": 0.5, "P3": 0.5, "P4": 0.85, "P5": 0.4}
    put("card_brier_P1_P5", round(sum((card[p] - held[p]) ** 2 for p in card) / len(card), 6), "method card P(rule holds) vs ledger outcome, 5 predictions")
    put("card_brier_P2_P5", round(sum((card[p] - held[p]) ** 2 for p in consult) / len(consult), 6), "method card, the 4 predictions the CONSULT priors also priced")
    put("consult_brier_P2_P5", round(sum((consult[p] - held[p]) ** 2 for p in consult) / len(consult), 6), "study.yaml RQ priors, 4 predictions")
    put("predictions_held", sum(held.values()), "ledger: supported")
    put("predictions_refuted", len(held) - sum(held.values()), "ledger: refuted")

    with (STUDY / "tables" / "synthesis_summary.tsv").open("w", encoding="utf-8") as fh:
        fh.write("metric\tvalue\tnote\n")
        for name, value, note in summary:
            fh.write(f"{name}\t{value}\t{note}\n")


if __name__ == "__main__":
    main()
