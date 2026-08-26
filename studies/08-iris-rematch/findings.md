# Findings — 08-iris-rematch (draft; T2 + label pending)

Study label: **confirmed** (protocol-completion label: one successful sealed
final-test per track; NOT an evidence upgrade — research_plan §6).

## ① RQ verdicts

- **C1 · RQ1 — the door was ajar.** headroom_declared = anchor dev 0.029442 ÷
  measured minimum_delta 0.029 = **1.015 ≥ 1**: for the first time in either iris
  study, a declared-split keep was arithmetically possible (a challenger needed
  dev Brier ≤ 0.000442). The ~20% branch (registered predictions row 2, prior
  P≈0.8 door-closed, source: scouting-study-07) FIRED AGAINST the majority prior —
  scouted-tagged, excluded from the scorecard, and the pre-scripted door-ajar
  branch ran exactly as registered: live contest, no redraw.
- **C2 · RQ1 coda — nobody walked through.** 21 parade transactions (E0003–E0023):
  18 discard, 3 crash, 0 keep. Best challenger qda at 0.024709 — an improvement of
  0.004733 = 0.16× the floor. The door stood ajar by 0.000442; the nearest visitor
  stopped 0.024 short of it.
- **C3 · RQ2 — nothing detectable at full n.** At rung 60 no family cleared the
  Bar-1 selection guard (joint repeat-level sign-flip max-t over the fixed
  113-cell family, adjusted score ≤ 0.05). Classical prior (scouted) held;
  the calibration and foundation lanes (uninformed) resolved: not detectable.
- **C4 · RQ3(a) — no rung ever opened.** All six rungs CLOSED: n=60/45/30/20
  ceiling-closed (m_n < δ_n with the anchor 0.017–0.028 from perfect), n=12/8
  fog-closed (the floor 0.147/0.252 dwarfs the anchor's own error 0.069/0.129).
  **m_n/δ_n ≈ 0.45–0.53 at every rung** — the incumbent's error and its own
  split-lottery wobble stay the same size all the way down the data ladder; the
  fog always outruns the ceiling. (Prior: uninformed → resolved NO; scorable.)
- **C5 · RQ3(b) — zero Bar-2 cells.** With every rung closed, a keep-sized arena
  win was arithmetically impossible everywhere; none occurred. (Prior: uninformed
  "no, weakly held" → HELD; scorable.)
- **C6 · RQ2/RQ3 rider — exactly one guard clearance, and it is 1930s.** Of 113
  cells, one cleared the guard: **qda at n=8** (mean paired gain +0.0730,
  adjusted score ≤ 0.05). A quadratic discriminant — Fisher-era machinery — at
  eight training rows. Its gain is 0.29× that rung's floor: detectable, not
  actionable. REGISTERED FRAGILITY: the fold-level sensitivity exhibit (40 units,
  MC flips) does NOT confirm it (0 cells fire) — the lone detection is
  unit-choice-sensitive and is reported with that caveat attached, per protocol.
- **C7 · RQ4 — the capture ratio is 0.98.** The best LDA-family adjustment at n=8
  (covariance shrinkage) achieves +0.0711 of qda's +0.0730 — observed capture
  **0.98**, far past the registered 0.5 downgrade threshold. The one detectable
  improvement over 1936-LDA is, to within 2%, available by adjusting Fisher's own
  family. Architecture never showed up. (Non-causal observed ratio, as
  registered. Prior: uninformed lean-yes → HELD; scorable.)
- **C8 · RQ5 — the instrument is alive at every size.** The sepal-only control
  separates (one-sided worsening, Bonferroni 0.05/6) at every rung: t = 121.7 at
  n=60 down to t = 5.8 at n=8, all adjusted scores ≤ 0.002. Degradations of the
  registered size are visible even where the fog closes the rung. (Prior:
  scouted → held; excluded from scorecard.)

## ② The sealed coda (Branch G, both looks spent)

- **C9 · T1 (primary):** anchor sealed Brier **0.077176** on the 21 procedurally
  fresh rows (13/21 virginica; twins behind the seal). |sealed − declared dev| =
  0.047734 ≤ 2×0.029 = 0.058 — **the registered band HELD**, at 82% of its width
  (+1.65×δ vs dev). Pre-committed line (program.md): 「新封条拆开，在位者的水平落
  在预先登记的带子里。无聊——无聊正是我们要的。」
- **C10 · T2 (challenger):** tabpfn sealed Brier **0.066863**; g_sealed = T1 − T2 =
  +0.010313 vs the arena band [−0.0160, +0.0050] — **OUTSIDE — a
  registered MISS.** The direction favored the challenger: its one sealed score
  came in 0.010313 better than the anchor's — 0.36×δ, far below keep size — and
  the gap overshot the band's upper edge (+0.0050) by 0.0053. Recorded exactly
  as the pre-committed OUTSIDE line requires: 「一九三六对二〇二五，封存差距落在
  擂台带子之外——对照预先登记的预测，这记作一次未中。」 One look, no coverage,
  no upgrade — and the vocabulary law forbids reading a 0.36×δ, single-look,
  out-of-band number as anyone "beating" anyone.
- Registered epistemic status: the coda band has no nominal coverage after
  selection; an in-band result is a procedurally locked audit, never an evidence
  upgrade.

## ③ Surprises (each with its mechanism)

- **C11 · The predecessor's lesson, reproduced in its successor.** Study 07's
  claim C19 says "register seed schemes inside the numeric domain of the library
  that will consume them." Study 08's registered namespace 20260901xxx exceeds
  sklearn's 2³²−1 bound — all 20 ledger-floor trials crashed exactly as 07's
  first lottery had; the crash sidecar is preserved
  (ledger_floor.sidecar.crashed-seed-overflow.tsv), the in-domain fix was
  committed before any floor was stated, and the gates were re-recorded. Reading
  the lesson is not the same as obeying it; the ledger caught the difference.
- **C12 · The Gaussian process failed only where data was plentiful.** gpc_rbf
  fits converge (finite kernel, finite log-marginal-likelihood) but its
  Laplace/erf probability integral returns NaN on near-separable 59- and 44-row
  fits — the evaluator refuses non-finite probabilities, and the vote that
  contains it dies of the same wound (E0018/E0022; 160 crash rows in the arena;
  guard placeholders at n=60/45 only). At n ≤ 30 the posterior stays finite and
  the family scores normally. Separability, not scarcity, is what broke it.
- **C13 · One wiring crash, owned.** stack_logit's parade transaction (E0023)
  crashed on "cross_val_predict only works for partitions" — an infrastructure
  bug (precomputed absolute inner splits cannot survive nested refits), not a
  property of stacking. Fixed pre-Stage-B with the registered lawfulness argument
  (no multi-row group exists outside the seal this study), method gate
  re-recorded, ledger record standing.
- **C14 · The twins drew the sealed ticket.** The pre-committed seed's group
  split put the printed twin rows (iris 102/143) behind the seal, together — the
  ruling ("they travel as one") held automatically, the arena pool (79 rows)
  contains no multi-row group, and the twins-last subsampling rule was registered
  but never fired.
- **C15 · Three challengers beat the anchor's raw score; the floor laughed.**
  qda 0.024709, lda_shrinkage 0.026958, knn_tuned 0.028670 — all under the
  anchor's 0.029442, all improvements ≤ 0.16×δ. Under study 07's split none of
  the six challengers managed even that. Fresh split, same verdict grammar:
  score-beating is cheap; floor-beating is the game.
- **C16 · The 2025 foundation model landed mid-pack.** TabPFN v2: declared-split
  0.055303 (e4) / 0.054707 (e16), roughly 2× the anchor's Brier; no guard
  clearance at any rung. The spike verified bit-identical seeded CPU fits and
  0.099 s warm inference — operationally excellent, statistically ordinary here.
  And yet on the single sealed look its score came in ahead of the anchor's by
  0.36×δ, outside the arena's predicted band (C10): a registered miss the ledger
  keeps, a single number the law forbids inflating. Scope: this pair, these
  sizes, this procedure.

## ④ Practical advice (earned here)

- **C17 · Audit headroom before you spend a challenger budget.** One measured
  table (m_n vs δ_n) told us before any challenger ran that no rung could pay a
  keep. The 21-family parade then cost minutes and produced landing points, not
  false hope. Compute how much room exists above your incumbent in floor units;
  if the answer is < 1, re-scope the question before running the tournament.
- **C18 · Pre-script the branch you think won't fire.** The door-ajar branch had
  ~20% scouted probability and it FIRED. Because both branches were registered
  sentences, the surprise cost zero improvisation and zero temptation to redraw.
- **C19 · A selection guard is not a significance test — name it what it is.**
  The red-team demoted our max-t from "exact FWER" to "registered selection
  guard under a symmetry assumption", and the fold-level sensitivity exhibit
  then showed exactly why the humility was warranted: the lone detection does
  not survive the unit change. Publish the sensitivity exhibit next to the
  guard, every time.
- **C20 · Calibration lanes need `ensemble=False` and your split law applies
  INSIDE estimators.** Row-level inner CV silently violated the twins ruling
  until the red-team caught it; sklearn 1.9 now deprecates `SVC(probability=
  True)` in favor of exactly the external-calibration construction the fix
  installed. And nested refits break precomputed splits (C13) — pass split
  POLICIES, not split INDICES, into anything that refits.
- **C21 · Keep the crash rows.** 160 arena crashes and 3 parade crashes are
  data: they located GPC's failure mode (separability), timed the stack fix,
  and kept the guard family honest via never-firing placeholders instead of
  silent shrinkage.

## ⑤ Prior scorecard (uninformed-tagged only, per scouting ledger §4)

| RQ | prior (uninformed) | outcome |
|---|---|---|
| RQ3(a) any rung opens | (none stated — open question) | resolved: NO rung opened |
| RQ3(b) no Bar-2 at an open rung | no, weakly held | HELD (vacuously strong: no open rung; 0 Bar-2) |
| RQ4 capture ≥ 0.5 | yes, lean | HELD (0.98) |

Scouted-tagged (excluded): RQ1 (door-closed P≈0.8 — the 20% side happened),
RQ2-classical (held), RQ5 (held).

## ⑥ What to try next

- A learning-curve arena on data where headroom EXISTS (m_n ≫ δ_n) — freMTPL2
  severity or the hurricane tails — where "does the foundation model win when
  data runs out" is measurable instead of fog-bound.
- A GPC variant with bounded kernels as a registered candidate, to test whether
  the separability pathology is fixable inside the same guard.
- The capture-ratio design is portable (the discipline moves even where findings may not): for any "modern beats classical" claim,
  register the classical-family-adjustment lane first.
