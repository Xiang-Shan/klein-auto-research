"""lib/score_submissions.py — the custodian's planted-truth scorer (opt-in layer).

Copy this into the CUSTODIAN study as the path `benchmark.yaml`'s `scorer.path`
names, fill the one TODO, and call it from the entrypoint of the single sealed
scoring cell.

**It is study LIBRARY code, never the mutable surface.**  `klein generation
benchmark commit` pins its sha256 — at METHOD, before any arm submits — and
`generation verify` re-reads it at the scoring cell's candidate commit.  A scorer
edited after the submissions arrived is a scorer tuned to the answers (R-INV-3,
"the checker is never the searcher"; R-BEN-2, the matching rule is fixed at
METHOD).

What it must produce, and why each piece is load-bearing
--------------------------------------------------------

1. `tables/benchmark_scores.tsv` — one row per arm × submitted structure, with
   the columns `arm`, `rank`, `variables`, `relationship`, `direction`,
   `context_ok`, `matched`, `truth_id`.  This table is the cell's evidence, and
   `generation verify` RECOMPUTES every `matched` and `truth_id` from the same
   submissions and the same revealed truth.  Disagree with it and the family
   FAILs — which is the point: the scorer is checked, not believed.

2. `context_ok` — the ONE judged column.  Variables, relationship and direction
   are decided mechanically; whether the claimed context satisfies
   `matching_rule.context` is the custodian's preregistered adjudication and is
   recorded here as 0 or 1 so a reader can see exactly where judgement entered.
   A row with `context_ok: 0` is never a match, however well its variables line
   up.

3. The printed block, through `kleinlib.eval.evaluate_table`, carrying
   `recall_<arm>`, `precision_<arm>`, `null_fp_<arm>` and `cost_<arm>` for every
   arm — and `predictive_<arm>` where the arm produced a predictive model (`NA`
   is allowed; a non-finite line aborts the notary's parser).  Recall is
   undefined on a null-only benchmark and its key is then simply absent; the
   false-positive rate is the whole result there.

Recovery is scored in RANK order and each planted truth is claimed ONCE: the
best-ranked structure that matches a truth claims it, a later structure matching
the same truth is a duplicate (`matched: 0` with a `truth_id`), and a structure
matching nothing is a false positive (`matched: 0`, `truth_id: NA`) against which
`false_positive_penalty` is charged.

Run it under the notary, never by hand:

    uv run --locked klein run-one --study studies/NN-slug --track scoring \\
        --final-test --dry-run                       # mandatory rehearsal
    uv run --locked klein generation check --study studies/NN-slug \\
        --action sealed --track scoring --tests P1 P2 P3 P4
    uv run --locked klein run-one --study studies/NN-slug --track scoring \\
        --final-test --tests P1,P2,P3,P4
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from kleinlib.eval import evaluate_table
from kleinlib.generation.benchmark import (
    SCORES_TABLE,
    matches_mechanically,
    submission_structures,
)

STUDY_DIR = Path(__file__).resolve().parents[1]


def committed_terms() -> dict[str, Any]:
    """The frozen terms, read from the file the commitment hashed.

    Reading them here rather than restating them keeps one copy: the file the
    commitment hashed is the file the scorer obeys.
    """
    return yaml.safe_load((STUDY_DIR / "benchmark.yaml").read_text(encoding="utf-8"))


def load_truth(terms: dict[str, Any]) -> list[dict[str, Any]]:
    path = STUDY_DIR / str(terms["truth_file"])
    return list(json.loads(path.read_text(encoding="utf-8"))["structures"])


def load_submissions(terms: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Every imported submission, keyed by arm and in rank order."""
    out: dict[str, list[dict[str, Any]]] = {}
    for row in terms["arms"]:
        arm = str(row["id"])
        path = STUDY_DIR / "submissions" / f"{arm}.json"
        if not path.is_file():
            continue  # a recorded missing trial; it stays in the denominator
        out[arm] = submission_structures(json.loads(path.read_text(encoding="utf-8")))
    return out


def adjudicate_context(structure: dict[str, Any], rule: str) -> bool:
    """TODO: the custodian's preregistered context adjudication — the ONE judged bit.

    ``rule`` is ``matching_rule.context`` verbatim.  Implement it as literally as
    the sentence allows — an exact match on a declared stratum, a membership test
    against an enumerated set — and where it genuinely needs a human, decide it
    ONCE, before the reveal, and encode the decision here so the column is
    reproducible.  Never widen it after seeing which arm it would have failed.
    """
    raise NotImplementedError("adjudicate matching_rule.context for one submitted structure")


def score(
    submissions: dict[str, list[dict[str, Any]]],
    truth: list[dict[str, Any]],
    rule: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float | None]]]:
    rows: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, float | None]] = {}
    for arm in sorted(submissions):
        claimed: set[str] = set()
        matched = 0
        false_positives = 0
        for structure in submissions[arm]:
            ok = adjudicate_context(structure, rule)
            judged = [item for item in truth if ok and matches_mechanically(structure, item)]
            free = [str(item["id"]) for item in judged if str(item["id"]) not in claimed]
            if free:
                truth_id: str | None = free[0]
                claimed.add(free[0])
                matched += 1
                is_match = 1
            elif judged:
                truth_id, is_match = str(judged[0]["id"]), 0
            else:
                truth_id, is_match = None, 0
                false_positives += 1
            rows.append(
                {
                    "arm": arm,
                    "rank": int(structure["rank"]),
                    "variables": ",".join(str(name) for name in structure["variables"]),
                    "relationship": str(structure["relationship"]),
                    "direction": str(structure["direction"]),
                    "context_ok": 1 if ok else 0,
                    "matched": is_match,
                    "truth_id": truth_id or "NA",
                }
            )
        submitted = len(submissions[arm])
        metrics[arm] = {
            "recall": (len(claimed) / len(truth)) if truth else None,
            "precision": (matched / submitted) if submitted else None,
            "null_fp": float(false_positives),
        }
    return rows, metrics


def write_table(rows: list[dict[str, Any]]) -> Path:
    path = STUDY_DIR / SCORES_TABLE
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "arm",
        "rank",
        "variables",
        "relationship",
        "direction",
        "context_ok",
        "matched",
        "truth_id",
    ]
    lines = ["\t".join(header)]
    lines += ["\t".join(str(row[name]) for name in header) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    terms = committed_terms()
    truth = load_truth(terms)
    submissions = load_submissions(terms)
    rule = str(terms["matching_rule"]["context"])

    rows, metrics = score(submissions, truth, rule)
    write_table(rows)

    extra: dict[str, Any] = {}
    for arm, row in sorted(metrics.items()):
        if row["recall"] is not None:
            extra[f"recall_{arm}"] = row["recall"]
        if row["precision"] is not None:
            extra[f"precision_{arm}"] = row["precision"]
        extra[f"null_fp_{arm}"] = row["null_fp"]
        # TODO: the arm's realised cost in the unit `benchmark.yaml` declared,
        # and its predictive performance where it built a model (`NA` otherwise).
        extra[f"cost_{arm}"] = float(terms["arms"][0]["budget"].get("person_hours", 0.0))
        extra[f"predictive_{arm}"] = "NA"

    defined = [row["recall"] for row in metrics.values() if row["recall"] is not None]
    primary = sum(defined) / len(defined) if defined else 0.0
    evaluate_table(
        STUDY_DIR / SCORES_TABLE,
        primary,
        exp_id=0,  # TODO: os.environ["KLEIN_EXPERIMENT_ID"]
        metric_name="TODO: the scoring track's metric name",
        metric_goal="higher",
        extra=extra,
        split_fingerprint=None,  # TODO: the contract's split fingerprint
        study_dir=STUDY_DIR,
    )


if __name__ == "__main__":
    main()
