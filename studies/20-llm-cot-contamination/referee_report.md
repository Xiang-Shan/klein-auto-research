Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report (round 2) — 20-llm-cot-contamination

> Gate 3 (REFEREE), round 2, written 2026-11-03 in a fresh context that saw neither the
> loop nor the round-1 review session. Round 1 is the report committed at `d7cc0dd`
> (Verdict: FAIL on check 4, controls, and check 5, multiple comparisons, plus eight
> notes). This round reviews HEAD `21e90df` (revision `d7cc0dd..21e90df`: `a949ada`,
> `a061f0a`, `21e90df`). I applied all ten checks again, not only the two that failed.
> Reading order: `findings.md` first; then the round-1 report and the revision diff;
> `claims.lock`, `study.yaml`, `results.tsv`, the manifests, `events.jsonl`,
> `study_state.json`, the pinned tables, `lib/synthesis.py`; then `data_card.md`,
> `method_card.md`, `references.yaml`; `program.md` last (the `## Roster` header was read
> only for the rung). Protocols: `.claude/skills/klein/references/referee-protocol.md`
> and `references/model-calls-protocol.md`. Every command ran with `KLEIN_OFFLINE=1` and
> `uv run --no-sync`, and no network call was made. The only file I wrote in the study is
> this one.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**.
Experimenter: the `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh
subagent context per phase (`program.md` `## Roster`). I am an Opus-tier subagent
(`claude-opus-5-5`) in a fresh context, so `independent-of-experimenter: yes` agrees with
the roster.

Disclosure: the tool (Claude Code) and the orchestrating session are shared with the
experimenter and the synthesist, so the rung is "model" and nothing higher. The
synthesist is also Opus tier. I did not write or revise these findings. The round-1
referee was on the same model, so this round does not add a new rung. It adds a reader
who did not write round 1.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use --no-receipt` | 34 checks, 0 failed. Warnings inside OK rows: no study source calls `contract_split`/`load_partition` (explained, see check 10 / round-1 note 8); both noise floors not measured; referee gate not yet recorded. `evidence_use_rate 1.00` (6/6). Findings numbers: 343 scanned numerals trace to 25 pinned sources. `convergent evidence`: 6 confirmed claims, each citing two or more evidence kinds. |
| `klein claims verify` | 7 checks, 0 failed. 17 pinned artifacts hash as recorded; append-only holds across git history. |
| `klein predict list` | 2 supported (P3, P6), 4 refuted (P1, P2, P4, P5), 0 inconclusive, 0 open |
| `klein status` | 6 experiments (measured 5, crash 1); gates consult=recorded, data=overridden, method=recorded; successful confirmation cot_gain=E0005, contamination=E0006; 0 refutations without a decision |
| figure re-render | not applicable: `figures/` is empty and the study has no `figures/make_figures.py` (unchanged since round 1) |
| re-execution of `lib/synthesis.py` (mine) | The whole study dir was copied to a scratch directory outside the repo and `python -m lib.synthesis` was run there. All five synthesis tables (`synthesis_arms`, `_paired`, `_quantities`, `_controls`, `_familywise`) re-render **byte-identically** to the committed ones. The script's internal assertions pass: the extracted answers re-score to every notarized cell table, and the re-derived 95% intervals for P2–P6 equal the notarized `ci_low`/`ci_high` in `aux_metrics.tsv`. |
| independent family-wise re-derivation (mine) | A separate script calls `kleinlib.metrology.paired_bootstrap`/`item_bootstrap` directly on the pinned `tables/cot_gain_E000{2,4,5}.tsv` and `tables/contamination_E000{3,6}.tsv` (N_BOOT 10,000, seed 20261103, template clusters on twin blocks). It reproduces every `cifw_low`/`cifw_high` in `tables/synthesis_familywise.tsv` exactly. |

## Round-1 clearing conditions: were they really met?

| Round-1 item | Met? | What I checked |
|---|---|---|
| **Check 4: controls**, option (b): offline controls from the committed ledger, pinned | **yes** | Negative control: the recorded replies are re-extracted from the committed `calls/` shards and re-scored against golds permuted within each cell (`controls_and_familywise`, seeds 20261123/20261124). Positive controls: planted shifts on the pinned cell tables (seeds 20261124/20261125), run through the study's own bootstrap (`lib/measure.py` N_BOOT and BOOT_SEED). The output is `tables/synthesis_controls.tsv`, pinned as `art:controls` (sha256 `1c87eba8…`), and it re-renders byte-identically. No model call: the code reads shards and cell tables only. The claims are C16 and C17, both `exploratory`, and both labelled post-hoc in the sentence itself and in the caveats. |
| **Check 5: multiple comparisons**: `n_comparisons` per family in §②, a guard applied from a pinned artifact, or a downgrade | **yes** | §② now states `cot_gain` = P1, P2, P4, P5 (n=4, level 0.9875) and `contamination` = P3, P6 (n=2, level 0.975). The Bonferroni-level percentile intervals use the study's own bootstrap and are pinned as `art:familywise` (sha256 `4a661ab4…`). I reproduced them independently. Every "interval excludes 0.10" statement (C2, C4) survives at the family level (upper ends 0.0367 / 0.01 / 0.055). Every "0.05 not excluded" statement (C3) survives trivially, because widening cannot exclude. P1's family-wise lower end 0.9167 is still above 0.85, so C1 survives. The guard is disclosed as post-hoc (C18, caveats). Round 1 told the study not to copy its unpinned figures. It did not: the pinned sealed-twin upper end is 0.055, not round 1's approximate 0.05. |
| **Erratum must re-scope, never rewrite** | **yes** | `claims.lock` C6: the `claim` text is byte-identical to round 1, `strength` is still `exploratory`, and `errata: ["E1"]` was added. The top-level `errata.E1` names C6 with a note. `events.jsonl` seq 39 `erratum_filed` is in a valid chain. The C6 sentence in `findings.md` is also unchanged, with the re-scope written beneath it and in the appendix table. `klein claims verify` append-only: OK. No other claim sentence changed in findings (diff checked). Only explanatory prose under C8 and C10, §⑤ and the caveats was edited. |
| Note 1 `gsm8k_name_numeral` | answered | `program.md` Referee note (1). Still applies at TUTORIAL (note R2-5 below). |
| Note 2 DATA override not in findings | answered | Caveat "DATA gate passed by override". |
| Note 3 coupling E0003/E0004 | answered | Caveat "Coupled cells" names both pairs. |
| Note 4 C4 replication is track-level | answered | Caveat "C4's replication is track-level, not cell-level". |
| Note 5a–d phrasing | answered | (a) erratum E1; (b) C10 prose is now conditional on the observed direct score; (c) §⑤ now reads "within the interval [-0.01, 0.03] … no equivalence margin"; (d) C8 prose now cites the pinned diagnostic (1 of 6 cut at `max_tokens`, 3 templates, at most 2 in one). It matches `art:controls` and my round-1 count. |
| Note 6 data-card W3 | answered | Caveat on structural non-independence of the sealed block. |
| Note 7 figures | deferred to TUTORIAL (acceptable; carried as R2-5) | — |
| Note 8 contract-split warning | answered | Caveat added. I confirmed the explanation in `kleinlib/data.py`: `load_items` calls `load_partition` (line 613), and `analyze.py:192` calls `load_items()`. The split fingerprint matches the frozen one (`klein verify`). The data card was correctly not edited (gate-hashed). |

Each of these has a dated `Referee note:` / `Referee check` line in `program.md` ("Referee
notes answered", 2026-11-03).

## The ten checks (applied afresh)

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** (notes R2-1, R2-3) | Confirmed claims: C1, C2, C3, C4, C5, C15 (`claims.lock`). Both tracks declare `confirmation.require: [sealed, replicate]`, and both have them: sealed E0005 (`final_test`, fresh queries) and E0006 (`final_test`, re-scoring of E0003/E0005 ledger entries, disclosed in C3(a), C12 and the caveats); replicate `rep:E0002@20261103T082725Z` and `rep:E0003@20261103T084446Z`, both salted re-queries. The replay `replay:E0002@20261103T085311Z` backs only exploratory C13 and is said to satisfy no requirement, as model-calls-protocol.md "Replay is not replication" requires. C4 rests on the track-level replication, and this is now disclosed. No run is `detached`, so no attested-only headline exists. All new claims C16–C18 are `exploratory`, and each sentence says so ("Post-hoc … exploratory"; C18 "exploratory as a check"). Mechanisms C6, C7 and C8 keep their `mechanism-interpretation, exploratory` labels. |
| 2 | predictions adjudicated and reported | PASS | `klein predict list` agrees with §② row for row (the observed values 0.95, 0.01, 0.02, -0.025, 0, 0.01 match the notary's adjudication events seq 12–33). P1, P2, P4 and P5 each carry a dated `Decision:` line (`klein verify` belief revision OK). The revision added the family statement to §② and changed no verdict. |
| 3 | negative evidence reported | PASS | `evidence_use_rate 1.00`. E0001 (crash, HTTP 429 after 599 calls) is reported as an infrastructure fault and retried as E0002 with disclosed reuse of 599 pinned answers. It is not read as a verdict. Every measured cell is cited. |
| 4 | controls | **PASS** (note R2-1) | Both controls are present and declared post-hoc. **Negative**: re-scoring against permuted golds gives chance-level exact-match, a mean of 0.012633 direct on public items over 100 permutations; the largest mean in any cell and arm is 0.036667, and the gain is 0.003333 public and 0 on both twin blocks (`art:controls`). This exercises extraction, scoring and pairing on the recorded replies. **Positive**: a planted +0.10 is recovered with a 95% interval above zero in all three cells ([0.073333, 0.15], [0.02, 0.125], [0.045, 0.15]). A planted +0.05 is detected only on the public items. The reverse plant is limited by the ceiling, which is disclosed. The table reproduces byte-identically. This clears round-1 check 4. See R2-1 for the scope of what the positive control tests. |
| 5 | multiple comparisons | **PASS** (note R2-4) | `n_comparisons` is stated for both families in §② and in C18. A Bonferroni guard is applied and pinned (`art:familywise`) and independently reproduced. No confirmed claim's verdict depends on an unguarded interval: C1 (P1 family-wise lower end 0.916667 > 0.85), C2 (0.036667 < 0.10), C4 (0.01 and 0.055 < 0.10), C3 (0.065 and 0.075, still not excluding 0.05). C5 and C15 make no inferential comparison. The guard is post-hoc. That is disclosed, and because Bonferroni only widens the intervals and no verdict was moved toward significance, the post-hoc timing cannot have flattered a result. This clears round-1 check 5. |
| 6 | pre-registration integrity | PASS | `study.yaml` was not touched in `d7cc0dd..HEAD`. The P1–P6 statements and rules are unchanged from the first CONSULT record (`git diff 8e5f657 a7bf6af -- study.yaml` touches only `minimum_delta` 0.01→0.03/0.05, the dated snapshot id, `calls.*` budgets and workers, and the anchor phase budget). There are three CONSULT re-records, each with a stated reason (events seq 3, 4, 10). Seq 3 and 4 precede the first run (E0001 started 07:42:33Z). Seq 10 (07:57:30Z) follows the E0001 crash and changes no prediction, rule, prompt or cell. Every `prediction_adjudicated` event post-dates the last contract record. The post-hoc controls and the family-wise guard are labelled post-hoc and were not back-dated into the contract. |
| 7 | numbers traceable (hand-checked below) | PASS | `klein verify --numbers` passes, and there is no `klein:numbers-ok` marker in findings, lock or program. Hand-checked against pinned artifacts: (1) C16 "0.0126" = `synthesis_controls.tsv` E0002 `em_direct_mean_over_100 0.012633`; (2) C17 "[0.0733, 0.15]" = E0002 `positive_plant_gain_0.10` `ci95_low 0.073333`, `ci95_high 0.150000`, and the dev-twin "0.075" / "[0.02, 0.125]" match E0004's rows; (3) C18 "0.055 sealed twins" = `synthesis_familywise.tsv` P5 `cifw_high 0.055000`, independently reproduced by my own `item_bootstrap` call; (4) C18 "0.075" = P6 `cifw_high 0.075000`, independently reproduced; (5) the C8 prose "1 of the 6 … 3 templates, at most 2" = E0004 `diagnostic_direct_only` 6 / 1 / 3 / 2; (6) §① "P1's family-wise lower end 0.9167" = P1 `cifw_low 0.916667`; (7) C17 recipe "30 … (20 on each twin block)" = `items_flipped_direct_right_to_wrong` 30/20/20, and the reverse plant 8/2/3 = ceil(15/2), ceil(3/2), ceil(6/2) from the cell tables' wrong-direct counts (15, 3, 6, which I counted). Round-1 note 1 (`gsm8k_name_numeral`) is unchanged and still accepted as a disclosed identifier workaround. |
| 8 | references | PASS | `references.yaml` is unchanged since round 1: 21 entries, all `verified: true`, 0 `false`. All eight cited `ref:` ids resolve and are verified. No confirmed claim rests on a reference. C16–C18 cite none. I did not re-resolve them (offline). |
| 9 | figures | PASS (note R2-5) | There are no committed figures and no `make_figures.py`, so nothing can fail to re-render and no axis can be truncated. |
| 10 | vocabulary and scope | PASS | No llm-profile banned word ("understands", "reasoning ability", "emergent", "solved", "SOTA") appears in findings or lock. The only grep hit is "unresolved", in C8's label. "improves", "generalizes" and "robust" are absent. The scope (one dated snapshot, the query date, temperature 0, thinking off, two registered prompts) is stated up front and in the caveats. "Resolution" is used only for the probe's detection limit, and §⑤ says no `materiality:` block exists. There is no measured floor and therefore no floor estimand; findings §⑦ item 4 says that both `minimum_delta` values are replication tolerances, not floors. Simulation scope: not applicable (`modality: text`, real model queries). |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md before `klein finalize`)

R2-1. **What the positive control tests.** The controls preamble says the two controls
   "test the *pipeline* (extraction, scoring, pairing, bootstrap)". Only the negative
   control touches extraction and scoring. The positive control plants its shift on the
   already-scored 0/1 vectors, so it tests the pairing, the clustering and the interval
   code, and its point recovery is exact by construction (findings says this). Taken
   together the two controls cover the pipeline, but neither one plants a known effect
   at the reply level. Neither can show that the scorer would credit a real CoT
   advantage that the extraction might mangle. The instrument assertion (re-scored =
   notarized) and the replay partly cover that, and the program note should say so. I
   do not ask for a new computation.
R2-2. **Seed-stream comment in `lib/synthesis.py`.** The comment says "one declared
   stream each … so no control re-uses … draws", but `POS_SEED = 20261103 + 21`
   equals `NEG_SEED + 1`, the seed of the 100 negative-control repeats. The two streams
   drive different operations (`permutation` vs `choice`), so no result is affected,
   and findings discloses both seeds honestly as 20261124. The comment is inaccurate.
   Acknowledge it in program.md. `lib/` is not the mutable surface of a run, and the
   committed table must not be regenerated with a different seed after this review.
R2-3. **C17's "cannot resolve a gain as small as 0.05" rests on one seeded plant per
   block.** It is a single realization, not a power estimate. It is consistent with
   the twin-block interval half-widths (about 0.05; C11), and C17 is exploratory, so
   this is not a FAIL. A tutorial or a knowledge promotion should phrase it as "a single
   seeded 0.05 plant was not detected on either twin block" or cite C11's widths, not
   state it as a power result.
R2-4. **The family definition is the synthesist's choice, made post-hoc.** The families
   follow the tracks (4 + 2). In an unpinned check of my own (not to be copied into
   findings), a single study-wide family of six also leaves every C2/C4 upper end below
   0.10 and every C3 upper end above 0.05. The verdicts therefore do not depend on how
   the family is drawn. Record in program.md that the next `test` study fixes the family,
   `n_comparisons` and the guard at CONSULT, as inquiry-model.md asks.
R2-5. **Carried to TUTORIAL (round-1 notes 1 and 7).** (a) Exclude `gsm8k_name_numeral`
   from any number rendered from `claims.lock`. (b) Build `figures/make_figures.py`, with
   re-renderable figures and zero-based delta axes. The headline deltas are 0.01–0.025.
R2-6. **Housekeeping.** The findings front matter `related:` and the "Derived tables"
   paragraph still list three synthesis tables. They omit `tables/synthesis_controls.tsv`
   and `tables/synthesis_familywise.tsv`, which are cited in the body. This is a
   cosmetic omission and changes no claim. Separately, the pinned E0005 diagnostic (6
   direct-only sealed twins, 2 with a CoT reply cut at `max_tokens`, at most 4 in one
   template) is reported nowhere. It is not required, but it is the sealed counterpart of
   C8's development-block sentence, and the tutorial's data story can use it.

## Clearing conditions (FAIL only)

None. No FAIL condition holds. Round-1 checks 4 and 5 are cleared as described above.
The orchestrator may record the gate after answering R2-1 to R2-6 with dated `Referee
note:` lines in `program.md` before `klein finalize`.
