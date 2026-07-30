---
type: findings
domain: "optimization"
status: final
concepts: [derivative-free-optimization, spsa, nelder-mead, random-restarts, noise-floor]
related: [02-rqls-pv-severity]
---

# Findings — 03-noisy-rosenbrock-dfo

> Every claim cites experiment IDs from the immutable run manifests. Claim IDs
> are stable (`03-noisy-rosenbrock-dfo#C<n>`, never renumbered). Deltas are
> stated as multiples of the measured noise-floor std (0.2848, k=5 disjoint
> seed blocks); deltas under 2× floor are reported as within-noise. This study
> is **confirmed**: its track's one sealed fresh-seed evaluation was spent and
> replicated the incumbent.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|---|
| **[C1]** | RQ1 (restarts beat single-start NM) | primary | **supported** | **confirmed** | E0001, E0003, E0007 | 1.2512 → 0.4071 on the dev block (Δ 0.844 = 2.96× floor std, clears the 0.5695 contract bar); sealed fresh block 0.3121 replicates (|0.407−0.312| = 0.33× std) |
| **[C2]** | RQ2 (SPSA beats restarted NM at this budget) | primary | **refuted** — and more strongly than predicted | exploratory | E0004, E0006 | "textbook" a₀=0.1 does not merely lose: it diverges to 1.9e178. The prior said within-noise; reality was unbounded |
| **[C3]** | RQ3 (8×25 fragmentation) | primary | **inconclusive — untested** | — | (deferred at the mid-phase re-plan, program.md 2026-07-30) | next-study queue |

## ② Predictions to falsify (filled)

| Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|
| restarts 1→4, fixed 200-eval budget | improve ≥ 3× floor std | 2.96× floor std (0.844) | **held** (to rounding) | E0003 |
| NM adaptive=True at n=2 | within 2× floor std | **exactly 0** — Gao-Han coefficients ≡ standard NM at n=2, bit-identical run | held (trivially — a no-op by mathematics) | E0002 |
| SPSA a₀=50 | non-finite → CRASH | 1.1e196, **finite** → discard | **falsified on mechanism** — decaying gains self-limit divergence below overflow (off-ledger probes: a₀=500→1e81, a₀=5000→1e97) | E0004 |
| SPSA c₀=0 (re-registered mid-phase) | ZeroDivisionError → CRASH | ZeroDivisionError → crash, NA metric | held | E0005 |

## ③ Surprises and why

1. **Random search beats single-start NM 3.2× — found by the DATA gate, before
   any experiment ran.** The clean-room audit's chance check scored 200 uniform
   samples at 0.397 vs the anchor's 1.2512. Mechanism: σ=0.5 noise corrupts
   NM's simplex ordering, so it stalls wherever the noise first confuses it;
   200 scattered darts sample the valley floor by volume. (Noiseless probe:
   NM = exact 0.0 on all 40 starts — the landscape is trivial without noise;
   the noise is the entire problem.)
2. **"Adaptive" Nelder-Mead is a dimensional illusion at n=2** (E0002): the
   Gao–Han coefficients χ=1+2/n, ψ=3/4−1/(2n), σ=1−1/n equal the classic
   2, 1/2, 1/2 exactly when n=2. The probe was structurally a rerun — delta
   exactly 0. Know your method's dimension dependence before spending a run.
3. **SPSA divergence saturates finite** (E0004): iterates explode until the
   decaying gain a_k strangles the step size; the trajectory freezes at
   absurd-but-representable values (1e81–1e196), never reaching float
   overflow. Divergence is not a crash — it is a very confident wrong answer.
4. **My "tuned" SPSA was mis-tuned by the method card's own reference**
   (E0006): Spall 1998 sizes a₀ from the desired first-step magnitude; with
   gradient magnitudes ~10³–10⁴ here, that rule gives a₀ ≈ 2×10⁻⁵ — not the
   0.1 I registered. The card contained the cure; I didn't apply it.

## ④ Practical advice

1. **[C4]** Measure your noise floor before judging any delta: the anchor's dev
   block was the LUCKIEST of five blocks (1.25 vs cross-block mean 1.72);
   single-block deltas under 0.57 here are weather, not climate (evidence:
   sweeps/noise_floor.sidecar.tsv, E0001).
2. **[C5]** Under evaluation noise, buy exploration before polish: restarts'
   entire value at this budget is their random-sampling component — they tie
   random search (0.407 vs 0.397, 0.04× floor std apart) (evidence: E0003,
   data card issue 1).
3. **[C6]** Treat gain-sequence scales as landscape quantities, never as
   defaults: apply Spall 1998's first-step rule to YOUR gradient magnitudes
   before the first SPSA run (evidence: E0004, E0006).
4. **[C7]** Register crash predictions on mechanisms, not vibes: "it will
   diverge" (true, E0004) is not "it will be non-finite" (false, E0004; true
   only for the c₀=0 denominator, E0005) (evidence: E0004, E0005).

## ⑤ Business / research value implications

For any tuning task whose evaluations are noisy (simulation calibration,
hyperparameter search over CV folds, A/B-measured policies): the floor-first
discipline in [C4] is the difference between shipping a real improvement and
shipping block-weather; and [C5] says a cheap random-search baseline is
mandatory before crediting any clever local optimizer — here it would have
saved 4 of 7 ledger rows.

## ⑥ Literature tie-back

- Spall (1992): SPSA's mean-zero gradient error is asymptotic doctrine — at 100
  iterations on a steep landscape, the pre-asymptotic regime dominated,
  exactly as the method card's regime table predicted (prior held, E0006).
- Spall (1998): the a₀ selection rule was the study's own unused cure ([C6]) —
  the literature predicted our failure and we reproduced it by skipping one
  paragraph.
- Priors' scorecard: method-card-sourced priors went 2/2 (RQ1's direction,
  SPSA's regime); `uninformed` priors went 1/2 (RQ2 direction right, magnitude
  qualitatively wrong; RQ3 untested). Knowledge-sourced priors outpredicted
  uninformed ones — the promotion loop earned its keep.

## ⑦ What to try next

1. Random search as a ledger experiment with its own noise floor (the DATA-gate
   finding deserves frontier status; deferred at the slate, program.md).
2. SPSA at a₀≈2×10⁻⁵ (the Spall-rule value) and/or gradient-normalized SPSA —
   does the method compete once actually tuned by its own reference?
3. 8×25 vs 4×50 restart fragmentation (RQ3, untested).
4. CRN pairing (common random numbers across configs) to shrink the paired
   noise floor and sharpen minimum_delta below 0.57.
