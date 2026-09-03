# Research plan — 10-hubble-1929-replication

## Question

In 1929 Edwin Hubble published two tables and one number: the velocity–distance
relation is linear, and its constant is **K = 465 ± 50 km/s/Mpc** (24 objects
individually) or **513 ± 60** (the same objects in nine groups). Today's value is
about **70**. Textbooks often quote **500**.

This study asks three things of that paper, in order:

1. **Reproduction.** Does K come back out of the tables the paper printed —
   target by target, with the tolerance registered before the run?
2. **Estimation.** Setting the published targets aside, what do those 24 objects
   actually estimate, with what interval, and how much does the answer depend on
   which variable is called the response?
3. **Simulation.** At n = 24 with Hubble-like scatter, does the interval machinery
   the estimate lane uses actually cover the truth?

It is deliberately a study whose *interesting* outcomes are the failures: a target
that does not reproduce because the paper never printed the inputs is a finding, not
a defect. The banned sentence for this study is "we replicated Hubble" (see
`references/replication-protocol.md`): findings report target by target.

## Contract

- Domain: astronomy. Kind `replicate`; modality `tabular`; profile `generic`.
- Data: `bundled:hubble1929/hubble1929_table1.csv` (24 objects) and
  `bundled:hubble1929/hubble1929_table2.csv` (22 nebulae), public domain, transcribed
  from two independent sources and diffed cell by cell before bundling.
- Three tracks, all `mode: registered` — a cell measures, it does not climb:

  | Track | kind | Primary metric | What a cell is |
  |---|---|---|---|
  | `reproduction` | replicate | `targets_outside_tolerance` (lower, exact, resolution 1) | one attempt at one published target, with its pinned table |
  | `estimate` | estimate | `k_kms_per_mpc` (lower, exact to 1e-6) | one estimator of K with its interval |
  | `simulate` | simulate | `coverage` (higher, floor measured at Phase 0) | one coverage measurement under the declared DGP |

- `confirmation.require: [sealed, replicate]` on every track. A claim closes
  `confirmed` only with a sealed access *and* a `reproduced: true` re-execution
  record — the bar `replication-protocol.md` names for a study that wants its numbers
  to survive a stranger's re-run.
- Per-run maximum: 60 s. Every cell is sub-second; the whole study re-runs in under a
  minute.

## The partition, and why it is a lock rather than a holdout

`data.split.kind: none`. Nothing here is drawn at random. The partition is the
paper's own structure:

- **Development block** — Table 1, the 24 objects whose distances were estimated
  independently of velocity (Cepheids, brightest resolved stars, cluster mean
  luminosity). Everything adaptive happens here.
- **Sealed block** — Table 2, the 22 nebulae. One access, on the reproduction track.

The driving agent had already read all 22 sealed rows before this contract existed
(`scouting_ledger.md` §0). The seal is therefore a **prospective analysis lock**: the
statistic, the procedure, the columns, the K it uses and the tolerance are written
into `study.yaml:sealed_lock` and hashed at the CONSULT gate, and the access is spent
once. It is not blindness, and the word "blind" does not appear in this study.

The alternative — resampling a "fresh block" out of the same 46 rows and calling it a
holdout — was considered and **rejected as dishonest** before the contract:
bootstrapping rows an analyst has already seen creates no new information; it only
launders a look into the vocabulary of a holdout. The rejection is taught in
`method_card.md` §4.

Two of Table 2's columns are forbidden to every cell, sealed or not. `r_mpc` there is
not an independent luminosity distance — Hubble computed it *from* the velocity with
his adopted K ≈ 500 — and `vs_kms` is tied to it by an exact identity. A column
derived from K cannot be evidence about K. The DATA gate mechanizes that exclusion as
leakage row 1.

## Validation policy

Adaptive work uses Table 1 only. Each track gets exactly one sealed access, taken in
the final phase and rehearsed first with `klein run-one --final-test --dry-run` (study
09 lost its only seal to a crash that ran before any data was read):

| Track | What "sealed" means for this kind | The access |
|---|---|---|
| `reproduction` | the original's reported value, compared once | E on Table 2: the paper's printed mean absolute magnitude, −15.3, versus what our K implies (P8) |
| `estimate` | an external reference value, compared once | the modern H₀ = 70 versus this study's interval (P4) and its rescaled fits (P7) |
| `simulate` | a fresh seed block never used in development | coverage on seed block C (P6) |

## Experiment ladder

**Phase p0-anchor.** The identity anchor first: recompute Table 1's published sums and
row counts (P0); a mismatch is a hard STOP. Then two Phase-0 *measurement* sweeps —
the Monte-Carlo resolution of the bootstrap keys (`sweep:mc_resolution`) and the
coverage floor over five simulation seed blocks (`sweep:coverage_floor`) — registered
with `klein sweep register` so findings can cite them.

**Phase p1-reproduction.** One cell per published target: the two two-parameter fits
against 465 (P1); Table 1's printed absolute magnitudes against the distance modulus
(P9); the four-parameter solar-motion solution (P2); the nine-group solution (P3).
The last two are expected to end as *documented method gaps* — the inputs the paper
would need are not in the paper — and the gap, not a guessed number, is the evidence.

**Phase p2-estimate.** The bootstrap interval for K; inverse regression against
forward regression in units of the paired standard error (P5); the jackknife influence
of each of the 24 objects.

**Phase p3-simulate.** Coverage of the analytic interval and of the percentile
bootstrap interval under the declared DGP, on development seed block B.

**Phase confirmation.** Three sealed accesses, each preceded by its dry-run, then
`klein replicate` on every development cell a confirmed claim will cite.

## Deliverables

`findings.md` (seven sections), `claims.lock` (`klein claims`), `referee_report.md`
from an independent fresh context, and `report/index.html`. Plus the first typed
citation into `knowledge/domains/physics/README.md` when the findings close.
