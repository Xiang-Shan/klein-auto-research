# Program — 11-exact-verifier-construction

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Roster — who ran what, on which model

| Role | Who | Model | Context |
|---|---|---|---|
| Experimenter (CONSULT → SYNTHESIZE, every `run-one`) | a Claude Code general-purpose subagent | `claude-opus-5` | a fresh git worktree, this session |
| DATA-gate clean-room auditor | the same agent, self-performed | `claude-opus-5` | performed AFTER `prepare.py` was written and run, never interleaved with it; the modality is `none`, so the audit is a verifier card rather than a leakage audit |
| Referee (Gate 3) | *(left blank until the referee runs)* | | |
| Lead / orchestrator | Claude Fable 5.1 | — | spawns the referee, relays its notes, owns the delegated acks |

The referee's rung goes on the gate record, not here; whichever rung it reaches, this
table is what a later reader uses to check it. The experimenter's model is stated
honestly above: a fresh Opus context started after synthesis reaches the rung
`fresh session`, the lowest rung of the ladder (person > tool > model > backend >
fresh session), and neither this file nor the report will claim more.

## Goal and track contract

- Goal: on an n × n integer grid, how many points can a budgeted iterated local search
  place with no three collinear — judged only by a declared exact verifier that shares
  no code with the search — at an n where the proven maximum 2n should be reachable and
  at an n where it should not?
- Kind / modality / profile: `optimize` / `none` / `math`. Schema 3.
- Tracks: `n_small` (11 × 11, proven maximum 22) and `n_large` (31 × 31, proven maximum
  62), both `frontier`, both running the SAME search over the same budget ladder.
- Primary metric: `points` (higher is better), `minimum_delta: 1`,
  `exactness: exact`. An integer objective has a resolution, not a noise floor: two
  runs of `verify.py` on the same bytes return the same integer. Phase 0 measures no
  floor and `klein noise-floor` is never called.
- **The verifier is the only judge.** `verify.py` is outside `entrypoint.mutable`, is
  hashed at the METHOD gate, is run by the notary as a second process on the artifact
  the search wrote, and ITS number decides the run. The searcher's own claim is
  recorded beside it; a disagreement is a crash.
- The two magnitudes the predictions register, 22 and 62, are 2n — the pigeonhole
  bound (three points in one row are collinear, so each row holds at most 2). They are
  arithmetic, fixed before any reference was consulted.

## Data and split

- Source: `synthetic:prepare.py` → `data/prepared/instances.json`. There is no
  dataset. What the DATA gate freezes is a **problem statement**: the two grid sizes
  with their pigeonhole bounds, the two seed blocks, the budget ladder, and the
  verifier's two controls — one known-valid object and twelve planted invalid ones.
  Freezing the controls before any run is the point: the positive control cannot be
  softened after seeing whether the checker caught it.
- `data.split.kind` is `none`: there are no rows and no partitions, so war story 8's
  failure mode (an evaluator carrying a retired split seed) cannot occur here — there
  is no split to carry. What replaces it is the seed-block discipline: `development`
  is the only block adaptive work may use and `sealed` is a block no development run
  may touch, both frozen in the hashed instance file, and no literal seed appears in
  `search.py`, `verify.py` or `lib/`.

## Research questions

- **RQ1** — judged only by the declared verifier, how many points does the same
  budgeted iterated local search place on an 11 × 11 grid and on a 31 × 31 grid, how
  does that count move across a three-decade budget ladder, and does it reach 2n at
  either size? Prior: it reaches 22 at n = 11 and stops short of 62 at n = 31, because
  the same evaluation budget buys about ten times fewer greedy completions on the
  larger grid `(source: uninformed)`.
- **RQ2** — with the objective computed only by a checker that shares no code with the
  search, what does the record show when the searcher's self-report is wrong, and do
  the two independent implementations ever disagree on an honest run? Prior: no honest
  run disagrees, and the overclaiming cell is refused and recorded as a crash naming
  `verifier_disagreement` `(source: uninformed)`.

## Registered predictions

| P# | Statement | Rule | Decided by |
|---|---|---|---|
| P1 | at the largest budget the verifier scores the 11 × 11 search at ≥ 22 | `primary_metric >= 22` | E0004 `--tests P1` |
| P2 | at the same budget the 31 × 31 search is scored < 62 | `primary_metric < 62` | E0007 `--tests P2` |
| P3 | the verifier rejects all 12 planted invalid objects | `rejected == 12` (tol 0) | E0001 `--tests P3` |
| P4 | re-running the verifier on a pinned artifact reproduces its integer exactly | manual | `verify:` records |
| P5 | no run's claimed objective is accepted above the verifier's | manual | E0008's crash + every honest run's `claim_excess` |
| P6 | from the sealed seed block, the 11 × 11 search is again scored ≥ 22 | `primary_metric >= 22` | E0009 `--tests P6` |
| P7 | from the sealed seed block, the 31 × 31 search is again scored < 62 | `primary_metric < 62` | E0010 `--tests P7` |

P4 and P5 are `manual: true` on purpose, and the reason is mechanical rather than
convenient. P4 is decided by replication records, which are written outside a run
transaction and therefore print no block for a rule to read. P5 is decided by a run
that CRASHES by design: `klein run-one` adjudicates `--tests` only after the verifier
agrees, so a cell whose whole purpose is to make the verifier disagree can never reach
the adjudication step. A prediction about a refusal cannot be decided by the machine
that performs the refusal; it is decided by reading the receipt the refusal left.

## Phase plan

| Phase | What happens | Budget | Max experiments |
|---|---|---|---|
| `adaptive-1` | E0001 controls → E0002–E0004 `n_small` ladder → E0005–E0007 `n_large` ladder → E0008 the deliberate disagreement | 3600 s | 8 |
| `confirmation` | sealed dry-run, then E0009 and E0010 once each on the sealed seed block | 900 s | 2 |

## Workflow

1. `scouting_ledger.md` and `sweeps/scout_design_time.py` are committed FIRST — not
   because the consult gate hashes the ledger (it does not: it hashes `study.yaml`,
   `research_plan.md` and `program.md`) but because the commit that carries the
   `study.yaml` the gate DOES hash carries the ledger too.
2. `klein gate record consult`.
3. `prepare.py` (already run), then `verify.py` and `lib/nothree.py`, then the
   verifier card `data_card.md` = GO; `klein gate record data`.
4. `method_card.md` + `references.yaml`; `klein gate record method` — which hashes
   `verify.py` into `state.fingerprints.verifier`, after which it never changes.
5. The consult RE-RECORD that adds `metric.bound.ideal` and
   `metric.incumbent_external` to both tracks, with its reason.
6. `klein headroom ack` on both tracks (see the decision below), then
   `klein preflight`, then the loop: edit `search.py` (a cell: which budget, which
   mode), `klein run-one --tests P#`.

Every candidate is committed before execution. Every run on both tracks is a discard
by arithmetic — see the headroom decision — so the evidence transaction restores
`search.py` to the pre-candidate base commit after every one of them, and each
candidate commit stays resolvable.

## Decisions (append-only)

- 2026-09-03 — schema-3 study scaffolded (`optimize` / `none` / `math`), two frontier
  tracks, gates pending.
- 2026-09-03 — the user's gate acknowledgements are DELEGATED to this agent for the
  Klein 2.0 exhibit studies. Every gate below is therefore recorded with
  `--acknowledged-by lead-agent`, on the lead's standing instruction, and the same
  applies to the phase acknowledgements and to the headroom acknowledgements. Nothing
  else about the gates changes: the artifacts still have to exist, be placeholder-free,
  and hash.
- 2026-09-03 — Decision: the problem is **no-three-in-line**, not equal-circle packing.
  Both were on the table at design time. No-three-in-line has an integer objective, so
  its verifier needs no tolerance and its metric needs no measured floor; circle
  packing has a real-valued objective and would have needed both. A study whose whole
  subject is "the checker is the only judge" should not have to argue about the
  checker's tolerance. Recorded in `scouting_ledger.md` under Retirements.
- 2026-09-03 — Decision: `metric.bound.ideal` and `metric.incumbent_external` are
  DELIBERATELY absent from the contract the consult gate hashes. Both quote a
  published value, and this study does not put a literature number in its contract
  before the METHOD gate has verified the reference that carries it. They are added by
  a consult re-record with a reason, before the first run exists. The predictions'
  own magnitudes are unaffected: 22 and 62 are 2n, arithmetic rather than citation.
- 2026-09-03 — Decision: `prepare.py` writes a problem statement, not a dataset. The
  DATA gate hashes it, which freezes the twelve planted invalid objects and the one
  known-valid object BEFORE the checker is ever run against them. A positive control
  that can be edited after it fails is not a control.
- 2026-09-03 — the machinery was smoke-checked at n = 4 and n = 5 only (`Search(n, seed=1, budget=2000)`), deliberately far from either registered instance, and it reached 2n at both. That is a shape check on the code, run after the consult gate had already hashed every rule; it could not and did not change one. It is recorded here rather than in the scouting ledger because the ledger closed at the consult gate.
- 2026-09-03 — **Consult gate RE-RECORD.** `metric.bound.ideal` and `metric.incumbent_external` are now declared on both tracks: 22 on `n_small`, 62 on `n_large`. Reason: both quote a published value and the study refused to put a literature number in the contract before the METHOD gate had verified the reference carrying it. That verification is now on the record — Flammenkamp's maintained record page (`ref:flammenkamp_records`, "no-three-in-line solutions are known for all grid sizes <= 70", read 2026-09-03) and, independently, MathWorld (`ref:mathworld_no3`, "For 2 <= n <= 32, it is possible to select 2n such points"). No run exists, so no result could have informed the number. The predictions' own magnitudes are untouched: 22 and 62 were registered at the first consult gate as 2n, arithmetic rather than citation.
- 2026-09-03 — Decision: the consequence of that re-record is that **no keep is arithmetically possible on either track**. The best known value equals the pigeonhole bound, so `h = (ideal - incumbent) / minimum_delta = (22 - 22) / 1 = 0` on `n_small` and `(62 - 62) / 1 = 0` on `n_large`. A keep would have to beat a theorem. This is not a discovery made halfway through a losing phase — it is arithmetic the study can do before its first run, and it is what `klein headroom ack` is for. The door is acknowledged CLOSED on both tracks with a run-anyway branch: this study is not looking for an improvement, it is looking for an object that ATTAINS the known maximum and for a record of who certified it. Every run below is therefore a discard by construction, and `matched_external: true` — not a keep — is what "the search reached the best known value" looks like in this ledger.
- 2026-09-03 — **ENGINE DEFECT (fixed, commit `ad87c0f`).** `klein preflight` looked for the literal `train.py` on disk instead of the entrypoint the contract declares, so every study whose kind is not `predict` failed its own preflight with `[FAIL] train.py: missing`. This study is the first `optimize` study, hence the first to hit it. Fixed in its own `engine:` commit by iterating `entrypoint.mutable` through `contract.mutable_surface`, which already returns `("train.py",)` for schema 2 and for any unreadable contract — so the `predict` path is unchanged — plus a regression test on the existing `optimize_study` fixture. Full suite: 1173 passed, 10 skipped, 1 deselected (`test_probe_device_respects_klein_device_override`, which needs the `deep` extra this study does not install).
- 2026-09-03 — **Consult gate RE-RECORD (second).** The first phase's id changed from `search` to `adaptive-1`. Reason, and it is a mechanical one: `klein new` initializes `study_state.json:current_phase` from the SCAFFOLD's phase ids, so a consultant who renames the phases — which the consult protocol expects — leaves the state pointing at a phase the contract no longer has, and preflight refuses with "phases were renamed/removed after initialization; amend the contract to match the recorded state". Amending the contract is the remedy the engine names, and it is what was done. No rule, prediction, metric, budget or experiment cap changed; only the phase's id, and its description still says what the phase does. Reported to the lead as a rough edge rather than patched: re-pointing `current_phase` when no manifests exist would be a behaviour change, not a defect fix.

### Phase adaptive-1 slate

Scored after the headroom acknowledgement, so testability is judged against a bar that
is known to be unreachable: on this study "testable" means *the cell decides something
registered*, never *the cell might produce a keep*.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | `controls`: run the twelve frozen invalid objects through the declared verifier and hand the notary the known-valid parabola set; decides P3 and anchors the checker at a value known in advance | 2 | 3 | 3 | 8 |
| 2 | `n_small` ladder at 20 000 / 200 000 / 2 000 000 addability tests; the largest decides P1 | 2 | 3 | 3 | 8 |
| 3 | `n_large` ladder at the same three budgets; the largest decides P2 | 2 | 3 | 3 | 8 |
| 4 | `overclaim`: the searcher reports one more point than the object it wrote; evidence for P5 | 3 | 2 | 3 | 8 |
| 5 | a second seed on `n_small` at the largest budget, to see whether reaching 2n was one lucky start | 1 | 3 | 2 | 6 |
| 6 | a third instance between the two (say n = 19) to locate the reach boundary | 3 | 3 | 2 | 8 |

Chosen, in order: 1 (nothing else is worth running until the judge has been audited
under the notary), then 2, then 3, then 4. The order matters: the checker is
established before it is trusted, the reach is measured on both instances before
anything is said about it, and the disagreement cell runs LAST because it is the only
cell expected to crash and a crash in the middle of a ladder would be ambiguous.

Not chosen: **#5** scores 2 on information because the confirmation phase already
spends a fresh seed block on exactly that question (P6, P7) and a development
duplicate would spend a slot to learn it a phase early. **#6** is the best idea in the
table and it is refused for one reason only: it needs a third track, and a track is
declared at CONSULT with its own metric, bound and external incumbent — adding one
after the gates would be adding a frontier after seeing results. It goes to the
playbook queue and to findings §⑦ as the study's first recommendation.
- 2026-09-03 — Merged `v2.0-science` (tip `b35acc4`) into the study branch. Three engine fixes landed there while this study was running, and one of them — preflight auditing the literal `train.py` instead of the declared mutable surface — is the same defect this study had already fixed locally in `ad87c0f`. The conflict in `kleinlib/checks.py` was resolved by taking the LANDED version on both hunks (the two fixes were semantically identical; the landed comment is the better one), so nothing local survives where the shared branch has an answer. The study's own remaining engine commit, `6d27d3c`, is a DIFFERENT defect that the landed set does not cover: headroom resolved the external incumbent only inside `run-one`, so preflight/verify reported "no incumbent yet" and `klein headroom ack` refused outright — which together made an externally seeded frontier at h < 1 unrunnable. Both facts are on the record here rather than quietly reconciled.
- 2026-09-03 — E0001 DISCARDS at 11 — the frozen Erdős parabola set, accepted by the notary's own verifier invocation at exactly the value its theorem predicts, and 11 < 22 so it is a discard like every other run here. The positive control fired 12 times out of 12 planted objects and **P3 is SUPPORTED** on the printed block (`rejected 12 == 12 ± 0`). The checker is now established in both directions inside a transaction, which is the only reason anything after this line is worth reading.
- 2026-09-03 — E0002 (20 points at 20 000 tests) → E0003 (21 at 200 000) → E0004 (21 at 2 000 000). The ladder is one trajectory read at three points: same instance, same development seed block, budget a strict prefix, so the objective is monotone by construction.
- 2026-09-03 — **Decision: P1 is REFUTED by E0004.** The prediction said the search would reach the proven maximum 22 on the 11 × 11 grid within 2 000 000 addability tests. It reached 21 — one point short — and the honest detail is sharper than the verdict: the best configuration was found at evaluation 152 572 and the remaining 1 847 428 evaluations, spread over 19 014 greedy completions, produced nothing better. So this is not "the budget was too small"; it is "this search plateaus at 21 on this instance from this seed, and buying it another order of magnitude changes nothing". Consequences, recorded now and not renegotiated: (i) the n_small track's development lane closes here rather than being extended — extending it after seeing a refutation is how a budget ladder becomes a fishing expedition; (ii) P6, the sealed prediction, is deliberately NOT rewritten: it still says the sealed seed block reaches 22, and the sealed run will now most likely refute it too, which is the price of having written it down before the evidence; (iii) the finding this study will report about n = 11 is "did not reach", never "cannot" — 22-point configurations at n = 11 are known to exist (`ref:flammenkamp_records`, `ref:mathworld_no3`), so a search that misses one is a fact about the search; (iv) `ref:ramanathan2025` gains weight rather than losing it: a PPO agent in that paper also fails at exactly n = 11 while integer programming is provably optimal there, so 11 × 11 is a size where *general* heuristics stall and *dedicated* methods do not.
- 2026-09-03 — E0005 (50 points at 20 000 tests) → E0006 (53 at 200 000) → E0007 (54 at 2 000 000) on the 31 × 31 grid. **P2 SUPPORTED**: 54 < 62. The shape of the two ladders is the finding, not either endpoint. The same evaluation budget buys 19 014 greedy completions at n = 11 and 2 190 at n = 31, because one completion costs about n² addability tests — so "the same budget" is not the same search effort at all, and saying the larger instance was searched "as hard" would be false.
- 2026-09-03 — **E0008 crashes by design and the mechanism fired exactly as registered.** The searcher reported one more point than the object it wrote; nothing else changed. `manifest.metric` records `reported 21.0` against `verified 20.0`, the disposition is `crash`, and `decision_reason` is `verifier_disagreement: the run reported 21 but the verifier measured 20 (tolerance 0) — one of them is wrong, and the search is not the one to ask`. `results.tsv` carries `NA` for E0008: the inflated number reaches no table anywhere in the study. This is the cell that cost a phase slot on purpose — a guard that has never fired is a guard nobody has tested.
- 2026-09-03 — `klein replicate --verify-only` on all seven development runs: `reproduced: true` in every record, tolerance 0.0 taken from `verifier.tolerance`, `difference: 0.0` on `primary_metric` every time. **P4 SUPPORTED** (manual adjudication, the seven `verify:` ids pinned). One honest detail for the referee: each record lists `mismatched_keys: [claim_excess, grid_n, triples_checked]`, and those are NOT mismatches — the manifest's stored verifier block carries only `primary_metric`, so the other keys' `original` is `null` and the comparison has nothing to compare. The primary metric, which is the number the ledger holds, matched exactly in all seven.
- 2026-09-03 — **P5 SUPPORTED** (manual adjudication). Both halves: `claim_excess` is 0.0 on every one of the seven honest runs, and the one deliberate overclaim was refused rather than recorded. P5 is `manual: true` because the run that decides it CRASHES, and `run-one` adjudicates `--tests` only after the verifier agrees — a prediction about a refusal cannot be decided by the machine that performs the refusal.
- 2026-09-03 — Phase `adaptive-1` closes with its eight experiments spent: seven discards and one crash, zero keeps, exactly as the headroom acknowledgement said in advance. P1 refuted, P2 P3 P4 P5 supported, P6 and P7 open for the confirmation phase. Playbook refreshed; the acknowledgement is the lead's delegated one.

### Phase confirmation slate

A confirmation phase has exactly two lawful cells here — one sealed access per
track — so the ritual's job is to write down what was NOT done with them.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | E0009: `n_small`, sealed seed block, largest budget, nothing else changed; decides P6 | 2 | 3 | 3 | 8 |
| 2 | E0010: `n_large`, sealed seed block, largest budget; decides P7 | 2 | 3 | 3 | 8 |
| 3 | re-tune the perturbation on development first, then seal the tuned version | 2 | 3 | 1 | 6 |
| 4 | spend the `n_small` seal on a LARGER budget instead, to chase the missing point | 3 | 3 | 1 | 7 |
| 5 | skip both seals and close the study exploratory | 1 | 3 | 1 | 5 |

Chosen: 1 and 2, unchanged from the registration. #3 is refused by the discipline
— the frontier closed when the adaptive phase's experiments were spent, and
re-opening it to improve the number about to be sealed is how a sealed number
stops meaning anything. **#4 is the interesting refusal and it is worth naming:**
after P1 was refuted at 21 of 22, the tempting move is to spend the seal on more
budget rather than on the registered cell, because that is where the missing point
might be. That would have replaced a registered prediction with an unregistered
hope, and E0003/E0004 had already shown the budget was not the binding constraint.
The seal was spent on what it was registered for. #5 would waste an earned
confirmation.

- 2026-09-03 — **E0009 SUPPORTS P6, and it is the study's biggest surprise.** From the sealed seed block — one integer different, nothing else — the same search at the same budget on the same instance reached **22**, the proven maximum, at evaluation 1 612 132. The development block plateaued at 21 and stayed there through 2 000 000 evaluations. So the development lane's honest conclusion ("this search plateaus at 21 on this instance") was a statement about ONE random start, and the sealed lane refuted it in a single run. What the study may say: a search that misses a known-attainable value once has told you about that run, not about the search; a heuristic's outcome on one seed is a draw, not a property. What the study may NOT say: any rate. Two seeds, one success — this study cannot and does not estimate how often the search reaches 22, and a seed sweep is the first item in the follow-up queue.
- 2026-09-03 — Decision: **P1 stays refuted and is not re-scoped by E0009.** P1 named the largest registered budget and the development lane, and there it failed. P6 named the sealed block, and there it held. Two predictions, two lanes, two verdicts, and the pair is the finding — rewriting P1 in the light of P6 would delete the most informative thing this study measured.
- 2026-09-03 — E0010 SUPPORTS P7: 55 of 62 from the sealed block on the 31 × 31 grid, against 54 from the development block. Both seeds land in the same neighbourhood at n = 31, which is what a search well short of its target looks like — the seed matters at the edge of reach and not far from it.
- 2026-09-03 — Phase `confirmation` closes with both sealed accesses spent, both cells successful, P6 and P7 supported. All seven predictions are closed: six supported, one refuted, none inconclusive, none open. Playbook refreshed; the acknowledgement is the lead's delegated one.
- 2026-09-03 — SYNTHESIZE. `findings.md` (seven sections, nine claims C1–C9) and `claims.lock` (lock schema 2, six pinned artifacts, twenty-three numbers) are written. Two honesty notes worth keeping:
  - **The lock caught an invented number at write time.** The first draft of C6 quoted 26235 as 37820, which is C(62,3) — the cost the checker *would* pay on a 62-point object, a number this study never produced because no run ever reached 62. `klein claims number` refused it ("is not in artifact ... a number needs a home that actually holds it") before anything was committed, and the corrected value, 26235, is `triples_checked` in E0010's verifier log: every triple of the 55-point object, the largest this study actually verified. The method card and the data card both quote C(62,3) = 37820 as a *worst-case cost at k = 62*, which is what they say and is accurate; both are gate-hashed and neither is edited.
  - **Four numerals in the first draft of `findings.md` had no home** and `klein verify --numbers` named all four: a `-1` inside a list of slopes, 1847428 twice (a subtraction nobody had recorded anywhere), and the 37820 above. Three were rephrased away and one was corrected. A separate near-miss is recorded here rather than left silent: the phrase "one collinear triple out of 220" PASSED the scan, because 220 happens to appear in `aux_metrics.tsv` as E0006's pass count — the law asks whether a numeral came from anywhere at all, not whether it came from the right place. It was removed anyway; a numeral that passes by coincidence is exactly the kind a referee should not have to catch.
- 2026-09-03 — The first typed citations were added to `knowledge/domains/math/README.md`, promoting C4, C5, C6, C7, C8 and C9 with `(supports 11-exact-verifier-construction#Cn)` citations, plus the two open questions this study could not answer.

## Referee notes (Gate 3, verdict PASS-WITH-NOTES, 2026-09-03)

The referee returned PASS-WITH-NOTES with seven notes and one minor observation. Each
is answered here, dated, with what was done about it. No FAIL condition held, and the
referee re-ran the declared verifier itself on the pinned `models/E0009/solution.json`
and on two frozen planted controls, and independently re-derived all three objects.

- 2026-09-03 — **Referee note 1 ("sub-millisecond" is refuted by the artifact the claim pins).** Upheld, and it is the note this study most deserved. `findings.md` and C6's locked sentence said the exhaustive triple test "stayed sub-millisecond"; `runs/E0010/verify.log` — alias `verify_log_large`, the artifact that supplies C6's own 26235 — reads `wall_seconds: 0.002046` beside it, about twice the stated bound, and four of the ten verifier logs exceed a millisecond (E0005 0.001528, E0006 0.001915, E0007 0.001969, E0010 0.002046). Sub-millisecond holds only for the n = 11 objects, where E0009 reads 0.000169. Three things were done and a fourth deliberately was not. (i) **Erratum E1** is filed against C6 with the pinned values in its note; C6's sentence is NOT edited, because the lock is append-only and that is the whole point of an erratum. (ii) Two numbers, `verifier_seconds_largest` 0.002046 and `verifier_seconds_small` 0.000169, are pinned against `runs/E0010/verify.log` and `runs/E0009/verify.log` and attached to C6, so the corrected quantity has a home. (iii) `findings.md` §④ now quotes those two numbers instead of the adjective, §③ carries a full Correction paragraph, and `knowledge/domains/math/README.md` is corrected and tagged with the erratum. (iv) `data_card.md` line 90 — which wrote "sub-millisecond at every size this study uses" at Gate 1, before any run existed — is NOT edited: it is a gate-hashed artifact whose sha256 is on the DATA gate record and on `events.jsonl`, and editing it after the runs would silently invalidate that record. The origin is recorded here and in findings instead. The lesson worth keeping is why it survived: "sub-millisecond" is a word, not a numeral, so `klein verify --numbers` was never looking at it — a pre-run estimate promoted into a post-hoc factual claim slips through a numeral scan by not being a numeral.
- 2026-09-03 — **Referee note 2 (§⑥ overstates how the references were verified).** Upheld. `references.yaml` was scrupulous and the summary sentence was not. §⑥ now says what the yaml says: four entries were read at the source — `ref:flammenkamp_records` (the maintainer's page), `ref:mathworld_no3` (MathWorld itself), `ref:ramanathan2025` (the arXiv abstract page), `ref:lourenco2019` (the Springer chapter page) — and six were checked against a bibliography rather than the work itself: `ref:dudeney1900`, `ref:roth1951`, `ref:guy1968`, `ref:hall1975`, `ref:flammenkamp1992`, `ref:flammenkamp1998`, whose journal, volume, issue and page ranges come from the Wikipedia article's reference list or MathWorld's. The paragraph now also says which group the load-bearing entries fall in: both external incumbents come from the first.
- 2026-09-03 — **Referee note 3 (the most-repeated "proven" statement is attached to no reference).** Upheld, and the fix is to name the warrant correctly rather than to add a citation. The 2n upper bound is not cited from the literature by this study — it is PROVED inline, in one line, in three places: `findings.md` §⑤, `research_plan.md`, and frozen as `upper_bound_argument` in the DATA-gate-hashed `data/prepared/instances.json`. `findings.md`'s vocabulary paragraph said it was "cited as a theorem from the literature", which is simply the wrong description of its own warrant, and it is rewritten. The math profile permits "proved" only when a proof artifact is pinned by alias and the referee checked it, so both halves are now satisfied mechanically: `research_plan.md` is pinned in `claims.lock` as **`art:proof`** and cited by C9's evidence, and the referee's report records that it re-derived the argument independently. `ref:mathworld_no3`, which states the same bound, is added to C9's evidence as well, so a reader who prefers a citation to a proof has one.
- 2026-09-03 — **Referee note 4 (§⑥ scores the same proposition two ways).** Upheld. The method-card regime table and RQ1's prior assert the identical proposition about n = 11, and the two paragraphs graded it "wrong" and "half right". They are reconciled to the prior's scoring, which is the fairer of the two because it reads both lanes: the card is now scored **half right on n = 11** (wrong on the development seed, right on the sealed one) and **right on n = 31**. What separates the card from the prior is its warrant, not its verdict, and the paragraph now says that instead: the card had `ref:ramanathan2025` in hand — a reinforcement-learning agent failing at exactly n = 11 — and predicted success anyway.
- 2026-09-03 — **Referee note 5 (`reach_vs_budget.png` draws the sealed cell at 1.55x its own budget).** Upheld, and fixed in the figure rather than in a caption. The offset was for legibility and the legend and marker already distinguished the cell, but on an axis whose units are evaluations a position is a number, and the star sat at a budget no run had. The sealed cell is now drawn at its real registered budget of 2 000 000 and is distinguished the way the note suggests: a hollow star with a heavy edge, off the ladder's line, legend "sealed seed block, same budget (one access)". The development marker underneath stays visible through it, which is the honest picture — same budget, different seed block, different outcome. Re-rendered and confirmed byte-identical across two further renders.
- 2026-09-03 — **Referee note 6 (the phase table is stale).** Upheld and corrected: the Phase plan table above now reads `adaptive-1`, matching `study.yaml`, `study_state.json` and all ten manifests. This is a **notebook correction, not a contract change** — `program.md` is the living lab notebook, it is deliberately excluded from the engine's live artifact-hash enforcement for exactly this reason, and the contract itself was changed lawfully back at consult re-record 2, whose reason is on `events.jsonl` sequence 6.
- 2026-09-03 — **Referee note 7 (this Gate 3 does not reach model independence).** Not a correction; a decision, and it is recorded rather than argued away. **Decision: Gate 3 on this exhibit reaches the `fresh session` rung, by fact, and the lead accepts that as the rung for the Klein 2.0 exhibit studies.** The experimenter ran as a Claude Code general-purpose subagent on `claude-opus-5`; the referee ran in a fresh context on `claude-opus-5[1m]` — the same model family, a different context window — so `independent-of-experimenter: no` is what the report says, what the gate record carries, and what the README gallery will show. The roster at the top of this file declared exactly this before the referee ran and declined to claim more, which is the behaviour the ladder is for: the rung is capped by fact, not hidden by a missing record. The referee is right that the `model` rung — a Sonnet experimenter under an Opus referee, as `CLAUDE.md` specifies — is what would earn the stronger sentence, and that is a change to how the exhibits are staffed rather than something this study can fix after the fact. It goes to the lead as a program-level recommendation, not into this study's claims.
- 2026-09-03 — **Referee minor observation (P4's scope).** Taken. P4 says "every development run that produced a verified object", and the seven `verify:` records cover E0001–E0007; E0008 is a development run whose artifact the verifier did score, at 20, and it carries no record because `klein replicate` refuses a crashed run. §② now says so in half a sentence, so a reader does not have to count. The verdict cannot turn on it: an eighth record could only add a reproduction, and E0008's ledger row is `NA`.

- 2026-09-03 — **Decision: the study closes `exploratory`, with `klein finalize --allow-exploratory`, and the reason is arithmetic rather than a shortfall.** `klein finalize` has no `--reason` for the exploratory label, so it is recorded here. `confirmation.require` is `[verify]`, and on a frontier track the engine resolves that to a re-verification record for the track's final KEEP. **Neither track has a keep, and neither ever could have:** `metric.incumbent_external` equals `metric.bound.ideal` on both — 22 against 22 at n = 11, 62 against 62 at n = 31 — because the best known value equals the pigeonhole upper bound at both sizes, so headroom was exactly zero before E0001 and a keep would have had to beat a theorem. With no keep there is no incumbent, so `replicate.confirmation_gaps` reports a gap on both tracks and the label is `exploratory` by the engine's own arithmetic. That is the honest label and this study asked for it in advance: it acknowledged the closed door with `klein headroom ack` on both tracks before its first run and redefined success as ATTAINING the known maximum rather than beating it. On `n_small` it did attain it — E0009 is scored 22 by the declared verifier with `matched_external: true` — and on `n_large` it did not reach the best known value, which is a limit of this search under this budget from these two seeds and **never** evidence of impossibility: 62-point configurations at n = 31 are known to exist (`ref:flammenkamp_records`, `ref:mathworld_no3`), and the study's own counterexample is inside it, since the same search missed 22 at n = 11 from one seed and reached it from another. What the `exploratory` label does NOT mean here: it does not mean the objects are unverified. Every development run carries a `verify:` re-verification record at tolerance 0, the two `procedural-verdict` claims C3 and C4 close `confirmed` on ids that all resolve, and the referee re-ran the declared verifier itself on the pinned `models/E0009/solution.json` in a fresh process and got 22.
