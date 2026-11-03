"""One measurement cell of study 20 (the mutable surface).

`klein run-one --track <track>` sets ``KLEIN_TRACK``; the cell measures that
track's estimand on the partition the contract hands it. ``CELL`` chooses the
LANE only — the instrument (prompts, decoding, scorer: `lib/prompts.py`), the
intervals and the table writer (`lib/measure.py`) are fixed outside this file.

* ``cot_gain`` — exact-match gain of the ``cot`` arm over the ``direct`` arm,
  paired on the same items. Development lane: ``CELL["block"]`` — ``gsm8k`` (P1,
  P2) or ``twin_dev`` (P4). A sealed run (``KLEIN_EVALUATION_KIND=final_test``)
  ignores ``CELL`` and measures the twin block ``load_items()`` hands back:
  twin_sealed (P5), or twin_dev on the sealed dry run. Interval: paired item
  bootstrap on GSM8K items, paired cluster bootstrap (whole templates) on twins.
* ``contamination`` — CoT arm only. Per template: the original item's score
  minus the mean over its twins in the evaluated twin block (twin_dev on
  development, P3; twin_sealed when sealed, P6). Primary ``em_gap`` = mean of
  those per-template gaps; interval: bootstrap over templates. ``CELL`` is
  ignored.

Every model call goes through ``CallLedger.from_contract`` (pinned under
`calls/`); a sealed dry run is answered from the ledger only (offline), so the
rehearsal spends nothing and leaves no new shard behind.
"""

from __future__ import annotations

import os
import time

import numpy as np
from lib import measure
from lib.prompts import PARAMS, exact_match, messages

from kleinlib.calls import CallLedger
from kleinlib.data import load_items
from kleinlib.eval import evaluate_estimate
from kleinlib.metrology import mcnemar_exact

SMOKE = measure.smoke()
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK")
TRACKS = ("cot_gain", "contamination")

# The lane of this cell (cot_gain, development only): "gsm8k" (P1, P2) | "twin_dev" (P4).
CELL = {"block": "twin_dev"}


def _summary(ledger: CallLedger) -> dict[str, float]:
    """Call accounting as ``calls_*`` keys (machine keys: replication ignores them)."""
    return {
        key if key.startswith("calls_") else f"calls_{key}": value
        for key, value in ledger.summary().items()
    }


def _ask(ledger: CallLedger, arm: str, questions: list[str]) -> list[str]:
    return ledger.chat_many([messages(arm, q) for q in questions], **PARAMS)


def run_cot_gain(t0: float, eval_ids: list[str], index) -> None:
    if measure.evaluation_kind() == "final_test":
        ids, block = measure.twin_lane(index, eval_ids)
    else:
        block = CELL["block"]
        if block not in (measure.BLOCK_GSM8K, measure.BLOCK_TWIN_DEV):
            raise SystemExit(f"CELL['block'] must be 'gsm8k' or 'twin_dev', got {block!r}")
        ids = measure.lane(index, eval_ids, [block])
    if SMOKE:
        ids = ids[: measure.SMOKE_ITEMS]
    if len(ids) < 2:
        raise RuntimeError(f"lane {block!r} holds {len(ids)} items")
    items = index.loc[ids]
    twins = block in measure.TWIN_BLOCKS
    print(f"cell: track=cot_gain block={block} items={len(ids)} arms=direct,cot "
          f"interval={'cluster bootstrap over templates' if twins else 'paired item bootstrap'}")

    offline = True if measure.sealed_dry_run() else None
    with CallLedger.from_contract(".", smoke_response="Answer: 0", offline=offline) as ledger:
        questions = items["question"].tolist()
        direct = _ask(ledger, "direct", questions)
        cot = _ask(ledger, "cot", questions)
        answers = items["answer"].tolist()
        score_direct = np.array([exact_match(r, a) for r, a in zip(direct, answers, strict=True)])
        score_cot = np.array([exact_match(r, a) for r, a in zip(cot, answers, strict=True)])

        table = measure.write_table(
            f"tables/cot_gain_{EXPERIMENT_ID}.tsv",
            ["item_id", "block", "template", "answer", "score_direct", "score_cot"],
            (
                {"item_id": item_id, "block": row["block"], "template": row["template"],
                 "answer": int(row["answer"]), "score_direct": int(d), "score_cot": int(c)}
                for (item_id, row), d, c in zip(items.iterrows(), score_direct, score_cot, strict=True)
            ),
        )
        if table:
            print(f"artifact: {table}")

        em_direct = float(score_direct.mean())
        em_cot = float(score_cot.mean())
        gain = em_cot - em_direct
        clusters = items["template"].tolist() if twins else None
        ci_low, ci_high = measure.paired_difference_ci(score_cot, score_direct, clusters)
        test = mcnemar_exact(score_cot, score_direct)
        evaluate_estimate(
            gain, ci_low, ci_high, len(ids),
            exp_id=EXPERIMENT_ID, metric_name="em_gain", metric_goal="higher",
            extra={
                "em_direct": round(em_direct, 6),
                "em_cot": round(em_cot, 6),
                "n_items": len(ids),
                "n_clusters": len(set(clusters)) if clusters else len(ids),
                "mcnemar_p": test["p_value"],
                "discordant_cot_only": int(test["n10"]),
                "discordant_direct_only": int(test["n01"]),
                **_summary(ledger),
            },
            study_dir=None if SMOKE else ".",
            t0=t0,
        )


def run_contamination(t0: float, fit_ids: list[str], eval_ids: list[str], index) -> None:
    twin_ids, block = measure.twin_lane(index, eval_ids)
    original_ids = measure.lane(index, fit_ids, [measure.BLOCK_ORIGINAL])
    originals = index.loc[original_ids]
    templates = originals["template"].tolist()  # template order = selection order
    if SMOKE:
        templates = templates[: measure.SMOKE_TEMPLATES]
    originals = originals[originals["template"].isin(templates)]
    twin_items = index.loc[twin_ids]
    twin_items = twin_items[twin_items["template"].isin(templates)]
    if sorted(set(twin_items["template"])) != sorted(templates) or len(originals) != len(templates):
        raise RuntimeError("every template needs exactly one original and at least one twin")
    print(f"cell: track=contamination block={block} templates={len(templates)} "
          f"twins={len(twin_items)} arm=cot interval=bootstrap over templates")

    offline = True if measure.sealed_dry_run() else None
    with CallLedger.from_contract(".", smoke_response="Answer: 0", offline=offline) as ledger:
        responses = _ask(ledger, "cot", originals["question"].tolist() + twin_items["question"].tolist())
        n_orig = len(originals)
        orig_scores = dict(zip(
            originals["template"],
            (exact_match(r, a) for r, a in zip(responses[:n_orig], originals["answer"], strict=True)),
            strict=True,
        ))
        twin_scores = [exact_match(r, a) for r, a in zip(responses[n_orig:], twin_items["answer"], strict=True)]
        by_template: dict[str, list[int]] = {t: [] for t in templates}
        for template, score in zip(twin_items["template"], twin_scores, strict=True):
            by_template[template].append(score)

        rows = [
            {"template": t, "source_id": originals.index[originals["template"] == t][0],
             "score_original": int(orig_scores[t]),
             "twin_mean": float(np.mean(by_template[t])), "twin_n": len(by_template[t])}
            for t in templates
        ]
        table = measure.write_table(
            f"tables/contamination_{EXPERIMENT_ID}.tsv",
            ["template", "source_id", "score_original", "twin_mean", "twin_n"],
            rows,
        )
        if table:
            print(f"artifact: {table}")

        score_original = np.array([row["score_original"] for row in rows], dtype=float)
        twin_mean = np.array([row["twin_mean"] for row in rows], dtype=float)
        em_original = float(score_original.mean())
        em_twins = float(twin_mean.mean())  # template-weighted, so em_gap = em_original - em_twins
        gap = float(np.mean(score_original - twin_mean))
        ci_low, ci_high = measure.paired_difference_ci(score_original, twin_mean)
        evaluate_estimate(
            gap, ci_low, ci_high, len(templates),
            exp_id=EXPERIMENT_ID, metric_name="em_gap", metric_goal="lower",
            extra={
                "em_original": round(em_original, 6),
                "em_twins": round(em_twins, 6),
                "n_templates": len(templates),
                "n_twin_items": len(twin_items),
                **_summary(ledger),
            },
            study_dir=None if SMOKE else ".",
            t0=t0,
        )


def main() -> None:
    if EXPERIMENT_ID is None:
        raise SystemExit("run through `klein run-one` (or KLEIN_SMOKE=1 for a shape check)")
    if TRACK not in TRACKS:
        raise SystemExit(f"KLEIN_TRACK must be one of {TRACKS}, got {TRACK!r}")
    t0 = time.time()
    fit_ids, eval_ids = load_items()  # prints split_fingerprint (and sealed_dryrun when rehearsing)
    index = measure.read_index()
    if TRACK == "cot_gain":
        run_cot_gain(t0, eval_ids, index)
    else:
        run_contamination(t0, fit_ids, eval_ids, index)


if __name__ == "__main__":
    main()
