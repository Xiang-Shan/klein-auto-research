# Program — 09-iris-first-lesson

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: Measure, with per-candidate paired resolution thresholds and a registered
  family selection guard, whether any frozen modern challenger earns a licensed win
  over 1936 four-feature LDA on the fully scouted iris hard pair — and record what
  the evidence permits us to claim.
- Tracks: `primary` (anchor lane; carries ALL development transactions — E0001,
  both controls, the 7-challenger parade — and sealed T1) and `challenger`
  (carries ONLY the Branch-A sealed T2; under Branch B its seal stays shut and the
  study finalizes `--allow-exploratory` per the pre-registered rule).
- Lanes ≠ tracks: the empirical lane is everything above; the SIMULATION LANE
  (known-DGP bias–variance companion, `sweeps/sim_dgp.py`) shares no data, no
  seeds, and no claims with the empirical lane (study.yaml `simulation_firewall`).
- Primary metric: `val_brier` (lower; minimum_delta measured by the PAIRED
  metrology recipe — scaffold 0 is a placeholder, never a bar). `bound {ideal:
  0.0, on_infeasible: ack}` armed at scaffold: klein's own detection-limit audit
  is live from the first transaction.
- Results are exploratory until each track's sealed final-test runs per its
  branch. A small delta without its floor must not be described as real or
  decisive; a delta without a named estimand is not a registered decision rule.

## Data and split

- Source: csv:data/prepared/iris_hard_pair.csv (fixtures/ copy committed; byte-
  identical to 07/08's fixture, sha256 9d67302e…f23f05 asserted by prepare.py).
- Declared split: group-aware, seed 20260912 (20260909 RETIRED pre-gate - scouting_ledger S10), twins rows 102/143 one group
  (99 groups / 100 rows). NO REDRAW under any outcome.
- The FULL 150-row audit (provenance vs committed UCI bytes, precision profile,
  duplicate scan, setosa triviality) is `prepare.py --audit` →
  `fixtures/full150_audit.json`; the hard-pair modeling frame remains the
  registered 100-row scope.
- Adaptive work uses train + development only. The test partition stays sealed
  and is PROCEDURALLY FRESH ONLY (scouting_ledger.md §0 — third study on these
  rows; both prior sealed values are public).
- The DATA gate records the prepared-data SHA-256 and split-policy fingerprint,
  plus whether any multi-row group sits in the non-sealed pool under seed
  20260912 (the 08 non-group inner-CV lawfulness argument does NOT port; every
  inner CV in this study is group-aware by construction).

## The registered ladder (not adaptively chosen — the registration IS the slate)

Phase adaptive-1: E0001 anchor_lda4 · E0002 lda_petal · E0003 lda_sepal ·
k-seed sweep (degenerate expectation) · metrology_paired (20 draws) →
candidate_floors → paste + consult re-record → rq0_headroom (h + h_c published
BEFORE any challenger arena number) → headroom branch fires (DOOR-CLOSED
expected; ack note pre-committed in research_plan §3.7) → Stage-A arena.
Phase adaptive-2: the parade — 7 challenger run-ones on PRIMARY, registry order:
lda_shrinkage, qda, logit_l2, knn_tuned, svm_rbf_platt, hgbt, tabpfn.
Phase adaptive-3: Stage-B arena → frozen analysis.py under run_with_log →
verdicts + coda_manifest.json → simulation lane imported, identity test green.
Phase confirmation: sealed per branch (§Sealed below).

## Decisions (append-only)

- 2026-08-27 — schema-v2 study scaffolded; gates pending.
- 2026-08-27 — contract authored: two tracks, four phases, bound armed at
  scaffold, per-candidate paired-floor protocol registered
  (`noise_floor_protocol`), 42-cell guard family, claims_discipline with five
  claim classes. TabPFN spike PASSED pre-consult (bit-identical sha256
  b452f7d0…dadb17 across two offline processes, ~0.9 s; breast_cancer rows,
  never iris) — TabPFN is live in the roster; `nystroem_logit` fallback stays
  dormant. Framework baseline: 306 passed / 6 skipped at e99a89a.
- 2026-08-27 — SEED RETIREMENT (pre-gate): a staging smoke scored dev+sealed
  Briers under candidate seed 20260909 (scouting_ledger S10); logs deleted;
  seed retired on the 07 seed-42 precedent; declared split re-registered as
  20260912 before any ack; agent-smoke synthetic-only law added to method
  card §6. Simulation truth-seed namespace bumped 2026500000+g ->
  2026900000+g after the sim agent disclosed a numeric collision with four
  training-draw seeds (pre-consult; the lane re-runs under the fixed seeds
  before import). Sensitivity MC seed likewise re-registered 2026099500 ->
  2026101500 (the drafted value sat inside the arena subset range at repeat 2,
  fold 0 — disclosed by the sweep build). Both fixes land BEFORE the consult
  ack; the registry's disjointness claim is now true, and the two disclosures
  stay in the sweep docstrings so the near-misses remain auditable.

## Phase slates

This study's slates are pre-registered (the parade is the registration): the
phase-start ritual records the registered ladder above verbatim rather than
proposing new candidates; any deviation would be a registered amendment with a
consult re-record. Mirror kept in playbook.md "Next-best candidates".

### Phase adaptive-1 slate (registered)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | anchor + controls + paired metrology + RQ0 headroom publication | 3 | 3 | 3 | 9 |

### Phase adaptive-2 slate (registered)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | the 7-challenger declared-split parade, registry order | 2 | 3 | 2 | 7 |

### Phase adaptive-3 slate (registered)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | Stage-B arena + frozen analysis (Bar-1/Bar-2/control/RQ4) + sim lane | 3 | 3 | 3 | 9 |

## §Sealed — pre-committed sentences (一个字都不许改 after this commit)

Branch rule (mechanical, frozen in analysis.py): **Branch A** iff ≥1 Bar-2 cell
at rung 60 (winner = largest guard t among rung-60 Bar-2 qualifiers); **Branch
B** otherwise. The spoken line later is whichever variant the record makes true;
除以下句子外，任何关于封存结果的句子都不许现编。

Branch A/B common — T1 `coda_primary` (anchor, all train rows), prediction
|sealed − E0001 dev| ≤ 2×minimum_delta:

- HELD · EN: "The anchor's sealed level landed inside the registered two-delta
  band: the locked procedure is consistent. That is discipline, not new
  evidence."
- HELD · zh: 「主锚的封存水平落在预先登记的两倍分辨率带内：流程一致。这是纪律，
  不是新证据。」
- BROKE · EN: "The anchor's sealed level left the registered band. As
  pre-registered: this does not overturn the arena evidence; the consistency
  check failed, the reason goes to findings, and nothing is re-run."
- BROKE · zh: 「主锚的封存水平出了预先登记的带子。按登记的读法：这不推翻擂台的
  证据；一致性检查未通过，原因写进 findings，不补跑任何东西。」

Branch A only — T2 `coda_challenger` (the mechanically selected winner, slots
(f\*, margin) filled by the frozen rule; group-aware inner CV per the registered
coda amendment), prediction g_sealed = sealed_primary − sealed_challenger inside
f\*'s arena [p10, p90] fold-level paired-gap band at rung 60:

- INSIDE · EN: "One sealed look each for 1936 and for the winner: the gap landed
  inside the band the arena predicted. The arena is the evidence; the seal is
  the discipline."
- INSIDE · zh: 「一九三六和获胜者，各拆一眼封条：差距落在擂台事先画好的带子里。
  证据在擂台，封条管纪律。」
- OUTSIDE · EN: "The sealed gap landed outside the arena's band — recorded as a
  miss against the registered prediction. It degrades consistency only; it
  never rewrites the arena verdict."
- OUTSIDE · zh: 「封存差距落在擂台带子之外——对照登记的预测，这记作一次未中。
  只降一致性，不改擂台的判决。」

Branch B only — the challenger seal stays shut:

- EN: "No challenger cleared both its own resolution bar and the selection
  guard, so by the pre-registered rule the challenger seal stays shut and the
  study completes with the exploratory protocol label. This sentence was
  written before any run."
- zh: 「没有任何挑战者同时清过自己的分辨率门槛和选择守卫——按预先登记的规则，
  挑战者封条不拆，研究以 exploratory 协议标签完成。这句话在开跑之前就写死了。」

备而不用 (any sealed outcome outside every registered case):

- EN: "The sealed record shows a case outside every registered sentence. We stop
  at this sentence, file it in findings, and improvise no explanation."
- zh: 「封存记录出现了登记之外的情形。我们停在这句话，写进 findings，不现编任何
  解释。」

Epistemic status, registered: the coda band has NO nominal coverage after
selection — an in-band result is a procedurally locked audit at the 2δ scale,
never an evidence upgrade; klein's `confirmed`/`exploratory` labels record
protocol completion only. The arena is the evidence; the seal is the discipline.

- 2026-08-27 — STATE FINGERPRINT REFRESH (pre-transaction): `klein new` freezes
  `fingerprints.split` from the scaffold's placeholder seed 42; the pre-gate
  contract rewrite (seed 20260912) left it stale and preflight FAILed. Applied
  the 07/08 "state regenerated pre-gate" precedent narrowly: refreshed ONLY
  `fingerprints.split` to the contract's value (no transaction exists; the
  stale value was never a measured or enforced quantity; the hash-chained
  event history is untouched and stays valid). Preflight 21/21 after commit.
  Filed as a framework P1 candidate in framework_assessment.md: the DATA gate
  refreshes the prepared-data fingerprint but not the split fingerprint.

- 2026-08-27 — SEALED CODA (Branch B): E0011 `coda_primary` CRASHED at the
  column-resolution line (manifest-key seam `primary` vs `coda_primary`
  between the independently built families.py and analysis.py; traceback
  upstream of load_split — zero sealed values computed). The seal spends on a
  crash by law; no retry exists and none was attempted. The pre-committed
  备而不用 sentence is the record's verdict (findings §Sealed, C14). The
  registered T1 band check is UNFULFILLED; finalize proceeds on the
  pre-registered Branch-B `--allow-exploratory` path. Frictions filed:
  integration seam (mock-manifest-only testing) + no sealed dry-run in the
  framework (P1).

- 2026-08-27 — ERRATUM E1 (post-finalize): train.py:78 hardcoded the retired
  seed 20260909 (retirement sweep missed the file) — the ledger lane E0001–
  E0011 ran on the retired partition; all sweeps ran on the registered
  20260912 pool; sealed rows untouched by the ledger under either seed.
  Filed as findings C15 + claims.lock erratum tags; no re-run (finalized).
  Discovered by the tutorial build's zero-unsourced-numerals scan — the
  process caught its own operator. Friction #5: no evaluator-vs-contract
  split-consistency check in klein (P1).
