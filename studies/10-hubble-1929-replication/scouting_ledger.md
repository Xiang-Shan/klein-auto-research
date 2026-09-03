---
type: scouting-ledger
study: "10-hubble-1929-replication"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 10-hubble-1929-replication

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`;
> the gate hashes it. Studies 07, 08 and 09 kept this ledger by hand; it is the
> mechanism that keeps "pre-registered" honest.

## §0 Disclosure

Before this contract was written the driving agent (a) read
`datasets/hubble1929/README.md` end to end, including its identity-anchor table and
its transcription-diff report; (b) printed **both** bundled CSVs in full to the
terminal — all 24 rows of Table 1 **and all 22 rows of Table 2, the block this study
seals**; (c) re-computed Table 1's four identity anchors and the two two-parameter
fits with numpy to check the README against the design brief; and (d) did mental
arithmetic on three Table-2 rows that exposed an exact relation between that table's
`v_kms`, `vs_kms` and `r_mpc` columns. None of it is evidence: it was computed
off-loop, under no contract, with no floor, no manifest, no fingerprint and no
adjudication, and none of it is cited by any claim. Its only sanctioned uses are the
E0001 identity anchor and the honest labelling below of which registered predictions
were already foreseeable when they were written.

**The consequence for the seal, stated plainly.** Table 2 is this study's sealed block
and the agent has seen its rows. The seal is therefore a **prospective analysis
lock**, not blindness: what is locked before the sealed cell runs is the *procedure*,
the *statistic* and the *tolerance* — hashed into `study.yaml` at the CONSULT gate and
into `method_card.md` at the METHOD gate — and the sealed access is spent exactly
once. It is not a claim that nobody looked at the rows. The banned word "blind"
(profile `generic` §7) is banned for precisely this reason. The alternative that would
have bought literal unseen-ness — carving a "fresh block" out of the same 46 rows by
bootstrap and calling it a holdout — is rejected as dishonest and the rejection is
taught in `method_card.md` §4: resampling rows an analyst has already seen creates no
new information; it launders a look into the vocabulary of a holdout.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-09-03 | `datasets/hubble1929/README.md` — the identity-anchor table | rows 24 / 22; `sum(r_mpc)` 21.873000; `sum(v_kms)` 8955.000000; `K0` 423.937323; `K1` 454.158441; intercept −40.783649 | design-time, unregistered, no manifest, no fingerprint | becomes the **E0001** identity anchor (P0); the K values become *anchors*, never scored predictions |
| S2 | 2026-09-03 | independent numpy re-computation of S1 from `hubble1929_table1.csv` | every S1 value reproduced to the last printed digit (see §Verification below) | a check of the bundled README, run off-loop | confirms the dataset is fit to anchor on; the same arithmetic is re-run under the notary at E0001 |
| S3 | 2026-09-03 | the design brief's scouting values (`K₀ ≈ 423.94`, `K₁ ≈ 454.16`, intercept `≈ −40.78`) | identical to S1/S2 | supplied with the brief, not measured here | recorded as agreeing; the brief's values are retired in favour of the computed ones |
| S4 | 2026-09-03 | published reference values quoted in the brief and the dataset README: Hubble's `465 ± 50` (24 objects) and `513 ± 60` (9 groups); the textbook `500`; the modern `≈ 70` | the four target values this replication aims at | published quantities, not measurements of ours | become the registered **targets** of P1, P2, P3, P4, P7 with the tolerances fixed in the brief |
| S5 | 2026-09-03 | `hubble1929_table1.csv` — all 24 rows, printed in full | `m_s` blank for 10 objects (6 nearest + 4 Virgo); `v_kms` integer, 3 negative; `r_mpc` 0.032–2.0 | reading the development block before the gate is ordinary preparation | profiled properly at the DATA gate; no cell reads it off-loop again |
| S6 | 2026-09-03 | **`hubble1929_table2.csv` — all 22 rows, printed in full (the sealed block)** | `r_mpc` and `M_t` blank for N.G.C. 404; `vs_kms` ranges −215…+220 | seen off-loop, disclosed here; see §0 — this is why the seal is a lock, not blindness | the seal is declared a **prospective analysis lock**; the sealed statistic, procedure and tolerance are registered at CONSULT and spent once at the sealed cell |
| S7 | 2026-09-03 | mental arithmetic on 3 Table-2 rows (N.G.C. 278, 584, 936) | `v − vs = 500 · r` held exactly on all three — i.e. `r_mpc` is a *derived* column, computed from velocity with Hubble's adopted K ≈ 500 | three rows checked by hand, no code, no manifest | mechanized at the **DATA gate** as leakage row 1: Table 2's `r_mpc` (and `vs_kms`) are excluded from every cell; nothing in this study reads them |
| S8 | 2026-09-03 | Table 1 mean `M_t` (README: −15.4792, paper prints −15.5) and Table 2 means (`m_t` 10.5, `M_t` −15.3) | the paper's own printed column means | published quantities re-derived by the bundling agent | −15.3 becomes the **registered target of the sealed prediction P8**; knowing a published target is what a `replicate` study is *for* |

## Foreseeability of the registered predictions — stated before the runs

A `replicate` study registers predictions about values that are already in print, so
some verdicts are foreseeable at registration time. Hiding that would be the dishonest
move; here it is, in the contract's own order. Findings §② repeats this column.

| P# | Foreseeable from this ledger? | Why |
|---|---|---|
| P0 | **yes** (S1, S2) | it is the identity anchor: it is *supposed* to be foreseeable, and a mismatch is a hard STOP |
| P1 | **yes** (S1) | `|465 − 454.158| = 10.84 > 10` follows from the scouted `K₁`; registered anyway so the arithmetic is on the record rather than in prose |
| P2 | no | nobody has checked whether the paper's four-parameter inputs are obtainable |
| P3 | no | nobody has checked whether the nine-group aggregation is reconstructible from the paper |
| P4 | **direction only** (S1) | that a CI around ~450 excludes 70 is obvious; the *width* of the interval is not, and the interval is what the claim rests on |
| P5 | no | the inverse-regression gap in SE units needs a bootstrap nobody has run |
| P6 | no | the coverage of a bootstrap CI at n = 24 under Hubble-like scatter is unknown here |
| P7 | **yes, arithmetically** (S1) | with `f = K₀/70`, `K₁/f = 70·K₁/K₀ = 74.99`, so `max|K − 70| = 4.99 ≤ 15` is implied by the scouted anchors; registered so the implication is auditable, and disclosed as implied |
| P8 | no | no Table-2 magnitude was computed at design time under any K; only the *target* (−15.3, S8) was known |
| P9 | no | whether the paper's printed `M_t` reproduces from its own `m_t` and `r_mpc` was never checked |

Four of ten predictions are foreseeable in whole or in part. They are kept because a
foreseeable prediction that is *written down and adjudicated by arithmetic* is still
worth more than the same belief asserted in prose — and because P1 and P7 are the two
whose refutation would have overturned the study's premise.

## Verification of the bundled anchors (S2, verbatim)

```
rows 24 22
sum_r  21.873000
sum_v  8955.000000
K0     423.937323
K1     454.158441  intercept -40.783649
mean M_t table1 -15.479167  (n=24)
mean m_t table2 10.500000  mean M_t table2 -15.300000
```

## Retirements

- **The brief's rounded scouting values** (`423.94`, `454.16`, `−40.78`) are retired in
  favour of the full-precision computed values; nothing cites the rounded forms.
- **A "fresh bootstrap block" seal** — proposed in outline as a way to obtain an
  unseen holdout — is retired before the contract as dishonest (see §0). Recorded here
  so the next study does not re-propose it.
- **Fetching J2000 catalogue coordinates for the 24 objects** to attempt Hubble's
  four-parameter solar-motion fit is retired at design time: 24 hand-transcribed
  lookups at an epoch the paper does not state is a fabrication risk, not a
  replication. P2 is registered with an `inconclusive_if` on input availability
  instead, and the missing inputs are documented as the finding.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
