# 03 — Noisy Rosenbrock derivative-free optimization

**The schema-v2 flagship exhibit.** The first study executed entirely under the
hardened v0.2/v0.3 contract, in *this* repository's public history: every one of
its 7 candidate commits resolves right here (`git cat-file -e <hash>` any
`candidate_commit` from `runs/E####/manifest.json`), the disposition of every
run was arithmetic against a **measured** noise floor, and the track's one
sealed fresh-seed evaluation was spent exactly once — and replicated.

The question: at a fixed 200-evaluation budget on noisy Rosenbrock (σ = 0.5,
known truth f\* = 0), do random restarts beat single-start Nelder-Mead, and
does SPSA beat both?

## The ledger at a glance

| Exp | Config | mean_final_gap | Disposition |
|---|---|---|---|
| E0001 | NM single-start (anchor) | 1.2512 | keep — reproduced the prepared reference cell to 1e-9 |
| E0002 | NM adaptive (Gao-Han) | 1.2512 | discard — coefficients ≡ standard NM at n=2; delta exactly 0 |
| E0003 | **4×50 restarts** | **0.4071** | **keep** — 2.96× the floor std |
| E0004 | SPSA a₀=50 | 1.1e196 | discard — divergence saturates *finite* |
| E0005 | SPSA c₀=0 | NA | crash — the estimator's own denominator (ZeroDivisionError) |
| E0006 | SPSA a₀=0.1 "textbook" | 1.9e178 | discard — mis-tuned per Spall 1998's own rule |
| E0007 | incumbent, sealed block | 0.3121 | sealed confirmation — replicates (0.33× floor std) |

Noise floor: std 0.2848 over k=5 disjoint seed blocks →
`minimum_delta = 0.5695` (`sweeps/noise_floor.sidecar.tsv`). The study's
biggest finding predates E0001: the DATA gate's clean-room audit showed plain
random search scores **0.397** — the honest bar was never the stalled anchor.
Full verdicts with citable claim IDs (`03-noisy-rosenbrock-dfo#C1…C7`):
`findings.md`. The teaching write-up: `report/index.html` (self-contained,
opens from `file://`).

## Reproduce the anchor cell

```bash
uv run --no-sync python prepare.py    # writes + prints the reference cell
# then flip train.py's config to OPTIMIZER="nm" (the committed file holds the
# E0003 incumbent) and run one development rep set:
KLEIN_EVALUATION_KIND=development KLEIN_EXPERIMENT_ID=E0001 KLEIN_TRACK=primary \
  uv run --no-sync python -u train.py
```

Expected `primary_metric: 1.251208` — deterministic from the seed-block
contract (`objective.py`); CI asserts ±0.001 on ubuntu for every push. To run
NEW experiments here, use the real loop: `klein preflight`, then
`klein run-one` on an `experiments/<study>` branch.

## Provenance

Executed 2026-07-30 as the v0.3 release's live acceptance test (one keep, one
discard, one crash, one sealed confirmation — all with real fits). Mid-study
contract amendments (the phase-ladder fold, the corrected crash registration)
are logged in `program.md` and were themselves the source of two framework
fixes — see `docs/reviews/2026-07-30-v0.2-adoption-audit.md` items A19–A20.
