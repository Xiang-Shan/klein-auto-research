---
type: data-card
domain: "small-n tabular classification (Fisher 1936 iris hard pair, n=100)"
status: go
concepts: [provenance, group-split, twins, procedural-freshness]
related: [studies/07-iris-90years/data_card.md]
---

# Data card — 08-iris-rematch

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source:** csv:data/prepared/iris_hard_pair.csv — built by `prepare.py`, inherited
  VERBATIM from study 07 (same sklearn `load_iris` provenance, same 7-column contract).
  sha256 `9d67302e0fcd…f23f05` — **byte-identical to study 07's prepared file** (same
  prepare, same upstream data; verified by hash at prepare time). fixtures/ copy committed.
- **Rows × cols:** 100 × 7 · **Target:** `is_virginica` · **Positive rate:** 0.50.
- **Profiler:** full profile lives in study 07's data card §Profile (same bytes); not
  re-derived here. Columns: 4 float measurements (0.1 cm print resolution), `species`
  (3-class code, kept as the registered crash-rung feed in 07 — never a feature),
  `is_virginica`, `group_id`.

## Provenance, lineage & the twins (inherited rulings — unchanged)

- Three-iris lineage (Fisher 1936 print vs UCI file rows 35/38 vs sklearn ≥0.20
  corrected): resolved and documented in study 07 (claims C9, C10, C17). Nothing new.
- **Twins**: hard-pair rows 51/92 (iris print rows 102/143, both virginica, values
  5.8/2.7/5.1/1.9) are original to Fisher's printed Table I; undecidable duplicate-vs-
  specimens; ruling: never delete — one shared `group_id` (`twins102-143`), 99 groups
  over 100 rows, groups never straddle any boundary (declared split, arena folds,
  arena subsampling via twins-last quota scan, AND — new this study — every inner-CV
  split inside calibrated/tuned/stacked estimators, via `families.inner_splits`).

## What is NEW in study 08 (the honest part)

- **Every value of every row is public knowledge**: study 07's committed ledger and
  sidecars published all 100 rows' behavior. The seed-20260907 sealed partition is
  **procedurally fresh only** — the registered protocol never conditions selection on
  those sealed rows, but nobody is blind to them. This card bans "blind/untouched/virgin"
  for this study's sealed set (study.yaml claims_discipline mirrors this).
- Split: group-aware 60/20/20, seed 20260907, pre-committed, NO REDRAW. MEASURED at
  authoring (three_way_split exactly as train.py calls it): train 59 rows
  (30 versicolor / 29 virginica), development 20 (12 versicolor / 8 virginica),
  sealed **21** (8 versicolor / 13 virginica) — the group machinery's ±1 wobble put
  21 rows behind the seal, and **the twin pair landed in the sealed partition,
  together** (the ruling holds: they travel as one). Consequences, registered here:
  the non-sealed pool is **79 rows containing no multi-row group**, so the arena's
  twins-last rule is registered but never fires this study, and cross-rung nesting
  holds trivially; sealed base rate 13/21 virginica is a documented consequence of a
  group split, not a defect.
- Smoke preview disclosure: the standard KLEIN_SMOKE=1 shape check printed the
  anchor's dev Brier 0.029442 on this split before the gates — enumerated as scouting
  item S9; no other family, row, or partition has been scored on this split.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | `species` is a perfect target proxy | inherited guard: feature columns come only from the registry; `species`/`group_id` can never enter a fit (train.py contract) |
| 2 | WARN | procedural-freshness limit above | registered disclosure wording binds every deliverable |
| 3 | NOTE | arena subsampling under-samples the twins at small rungs (twins-last rule) | registered, documented in rematch_arena.py docstring; the alternative (mid-order twins) breaks cross-rung nesting |
| 4 | NOTE | TabPFN v2 weights are an external artifact | pinned: package tabpfn==8.4.0 (uv.lock), checkpoint family v2, HF repo Prior-Labs/TabPFN-v2-clf (public, ungated; default file tabpfn-v2-classifier-finetuned-zk73skhh.ckpt), cached locally 2026-08-25; all study runs set HF_HUB_OFFLINE=1 |

## Leakage audit

- Duplicate check is STRADDLE-ONLY (07 ruling): the twin group must never straddle
  train/dev/test or any inner fold — enforced by group machinery at every layer listed
  above; the arena additionally publishes per-cell row-set hashes
  (`arena_partitions.tsv`) so any straddle is auditable after the fact.
- No datetime, no ID-like feature columns, no post-outcome fields — 4 physical
  measurements only.

**Decision: GO** — lineage resolved (inherited), twins ruling enforced at every split
layer including inner CV, procedural-freshness disclosed and vocabulary-bound.
