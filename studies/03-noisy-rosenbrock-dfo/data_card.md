---
type: data-card
domain: "optimization"
status: go
concepts: []
related: []
---

# Data card — 03-noisy-rosenbrock-dfo

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source:** synthetic:noisy_rosenbrock_v1 — generated locally by `objective.py`;
  known truth f\*=0 at (1,1); evaluation noise N(0, 0.5²); hard budget 200
  evaluations per rep; R=40 reps per experiment.
- **Prepared artifact:** `data/prepared/reference_cell.csv` — 40 rows × 4 cols
  (`rep, seed, final_gap, evals_used`), the anchor config's per-rep true gaps.
- **Target:** `synthetic` (the score is computed against the known truth; there is
  no label column to leak).
- **Profiler used:** direct inspection — 40×4 is smaller than any profiler's
  overhead; every value verified below.

## Profile summary

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| rep | int 0..39, contiguous | 0 | 40 | yes (index) | no | rep = seed − 42 |
| seed | int 42..81, contiguous | 0 | 40 | yes | no | development block, disjoint from floor/final blocks |
| final_gap | float, all finite, ≥0, 12-dp strings | 0 | 40 | no | no | mean 1.251208; min 0.0034, max 9.7 (long right tail) |
| evals_used | int, constant 200 | 0 | 1 | no | no | every rep spent the full budget |

**Value-pattern check (mandatory war story):** all four columns hold exactly what
they claim — no sentinels, no strings-in-numbers, no NA tokens. `final_gap` is
serialized at 12 dp; `train.py`'s anchor assert compares at 1e-9, inside that
precision.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | **The no-information baseline beats the anchor.** Random search (200 uniform samples, best-noisy selection, same seed blocks) scores mean true gap **0.397** vs the single-start NM anchor's **1.251** — an uninformed searcher is 3.2× better. The noiseless probe (below) proves this is the landscape, not the harness. | Not a blocker — it is the study's first finding. The honest bar for "restarts pay" is 0.397, not 1.251; record in program.md and weigh in SYNTHESIZE. |
| 2 | NOTE | `final_gap` has a long right tail (max 9.7 ≈ 8× mean): some NM runs stall on the far valley wall. | Report median and worst alongside the mean (train.py already emits `gap_median`, `gap_worst` to aux). |
| 3 | NOTE | The metric mean is noise-sensitive at the ~0.1 scale; deltas below the measured floor must read as within-noise. | Phase-0 noise-floor sweep sets `minimum_delta`; enforced by preflight. |

## Clean-room leakage audit

Performed self-clean-room after the profile: inputs were ONLY `study.yaml`,
`prepare.py`, `objective.py`/`optimizers.py` (the generator IS the data source),
and the prepared artifact — `program.md` unread at audit time. Rows 3–4 were run
mechanically; `python -m kleinlib.leakage` targets tabular splits and is N/A under
`split.kind: none` — its two checks are reproduced with the study's own mechanics
below.

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage | N-A | No features exist; the "target" is the known truth f\*, used only for scoring — never visible to the optimizer (`objective.py`: optimizers see noisy evaluations only). |
| 2. Lookahead | N-A | No fitted preprocessing; each rep's noise stream is created fresh from its seed inside the rep. |
| 3. Split contamination | PASS | `assert_blocks_disjoint()` (run by prepare.py and re-run at audit): dev 42–81, floor 142–181/242–281/342–381/442–481, final 10042–10081 — pairwise disjoint, mechanically verified. |
| 4. Eval-harness sanity | PASS | Direction is real: noiseless NM probe scores 0.000000 (exact optimum, all 40 starts), noisy anchor 1.251, random search 0.397 — lower-is-better wiring confirmed end-to-end. The random-vs-anchor inversion is a landscape finding (issue 1), not a harness error: a broken harness could not produce an exact 0 on the clean function. |

## Go / no-go

> **Decision:** GO
>
> **Rationale:** Known-truth generator, mechanically disjoint seed blocks, an
> artifact whose every value was inspected, and a harness that solves the clean
> landscape exactly. The one WARN is a scientific finding that sharpens the study
> (the bar is random search, not the stalled anchor) — exactly what the gate is
> for.
