Verdict: PASS-WITH-NOTES
Referee: klein-referee round 2 (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 23-lalonde-causal-replication (round 2)

> Gate 3 (REFEREE), **round 2**. Written in a fresh context that did not see the loop,
> the synthesis or the round-1 referee's reasoning. Reading order: `findings.md`, then
> `claims.lock`, `study.yaml`, `results.tsv`, `runs/*/manifest.json`, `study_state.json`,
> `events.jsonl`, the pinned tables, `data_card.md`, `method_card.md`, `references.yaml`
> and `scouting_ledger.md`, and `program.md` last. Protocol:
> `.claude/skills/klein/references/referee-protocol.md`. The first two lines above are
> machine-read by `klein gate record referee`. The third is for people. `Generation:` is
> `n/a` because the study has no `generation/manifest.yaml`.
>
> Reading-order disclosure: while grepping the study for `klein:numbers-ok` markers
> (check 7), one line of the round-1 `referee_report.md` (its check-7 row) appeared in the
> grep output. That happened after I had formed my own view of checks 1–7, and before I
> had finished checks 8–10 and read `program.md`. I read the rest of the round-1 report
> only after I had settled all ten checks below.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**.

Experimenter: `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh
subagent context per phase. The source is `program.md` `## Roster`, which I read for
this line only. This referee runs on `claude-opus-5-5` (Opus tier). The tiers differ, so
`independent-of-experimenter: yes` agrees with the roster. The experimenter row records a
tier, not an exact model id. That is enough to tell the two models apart, but it is not
mechanical (Note 6).

Against the **authors of the findings**, this referee reaches only the fresh-session
rung. The roster's synthesist ran on `claude-opus-5-5`, the same model as this referee,
as a child context of the same orchestrating session
(`session_01DRcLputoCrDTEvbxp6Rby1`). The lead's model is not recorded (Note 6).

## Mechanical verifiers run

| Command | Result |
|---|---|
| `uv run --no-sync klein verify --study studies/23-lalonde-causal-replication --numbers --evidence-use --no-receipt` | 34 checks, 0 failed (one `[WARN]` inside an OK row: not yet refereed). `evidence_use_rate 1.00`: all 9 non-keep runs are cited. Convergent evidence: 7 confirmed claims cite two or more evidence kinds. Findings numbers: 805 scanned numerals trace to 31 pinned sources (round 1 counted 803; the reworded §③ heading added two). Belief revision: P1, P2, P4 and P6 each have a dated `Decision:` line. Exit 0. |
| `uv run --no-sync klein claims verify --study studies/23-lalonde-causal-replication` | 7 checks, 0 failed: shape, 20 artifacts hash as recorded, presence, evidence, numbers, append-only, ancestry |
| `uv run --no-sync klein predict list --study …` | 3 supported (P3, P5, P7), 4 refuted (P1, P2, P4, P6), 0 inconclusive, 0 open |
| `uv run --no-sync klein status --study …` | 9 experiments (measured=7, crash=2). Final holdout: att=1/1 (E0009), reproduction=1/1 (E0008). Successful confirmation: reproduction=E0008, att=E0009. 0 single-source confirmed claims. |
| figure re-render (`make_figures.py` → temp dir, byte compare) | **not applicable at this gate.** `figures/` contains only `.gitkeep`, and neither `figures/make_figures.py` nor `report/index.html` exists. Nothing could be re-rendered (check 9, Note 5). |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** (notes 1, 2) | **Confirmed claims.** The lock has seven: C1, C2, C5, C8, C26, C29, C30. Every empirical one cites a sealed run and a replication record of its own track. For the reproduction track that is E0008 (`evaluation_kind: final_test`) with rep:E0001@20261103T065031Z. For the att track it is E0009 (`final_test`, manifest read) with rep:E0006@20261103T065104Z, whose record shows difference 0.0 on every block key except `wall_seconds`/`total_seconds`. So `confirmation.require: [sealed, replicate]` is met. Neither sealed cell was itself re-executed. Scope item 6 and erratum E6 disclose this, and it is also round 1's Note 2, which I endorse. C8 is a `procedural-verdict`, confirmed because every cited P#/E# resolves in the ledger (`claims-protocol.md` class table). C6 was downgraded to exploratory together with erratum E4 (lock 9a37ced had it `confirmed`). The append-only law passes. No manifest has `execution.mode: detached` or `seeds_n`. **Prose.** The round-1 defect is gone. §③ item 1's heading now reads "Table 3 column (2) appears to mix two Table 2 columns (exploratory, [C10]) …" (commit dbe4bee, findings-only diff). Every mechanism claim (C10, C11, C12/C25/C28) is labelled exploratory where it is stated. The summary paragraph calls the Table 3 reading "an exploratory reading", and "Reading the verdicts together" calls it "the exploratory editorial reading". Two residual phrasings go a step past their claim. I list them as notes rather than a FAIL, because each sits under an exploratory label or is hedged. Note 1: the §③ item 1 body states the column-(5) equality without a hedge. Note 2: §⑤ and §④ use the gloss "rests on a few people". |
| 2 | predictions adjudicated and reported | PASS | `study_state.json` `predictions`: P1–P7 all `source: run`. The evidence is P1 E0001, P2 E0002, P3 E0006, P4 E0005, P5 E0007, P6 E0008 and P7 E0009. The `prediction_adjudicated` events are at seq 6, 11, 20, 25, 29, 35 and 42 of `events.jsonl`. findings §② gives 3/4/0/0, and each row's verdict and observed value match `klein predict list` (for example P4: \|gap\| 1234.06100792 from −1234.06100792 → refuted). program.md has dated `Decision:` lines for P1 (E0001), P2 (E0002), P4 (E0005) and P6 (E0008). The P7 selection Decision ("AIPW with spec dw_psid unchanged, selected from E0006 … Recorded before any sealed access") was committed in 00672e2, before the first sealed dry run (events seq 33, 05:57:34Z). |
| 3 | negative evidence reported | PASS | `evidence_use_rate 1.00` (9/9). The registered tracks have no discards, so there are no discard clusters to write up. The two crashes are E0003 (recovered, NA, seq 15) and E0004 (exit 143, seq 17). They are cited in scope item 5, in §② row P4 and in C18. They are described as driver errors, and the matching cell re-ran as E0005, so no crash is read as a verdict on matching. The killed, misnumbered AIPW run is preserved in `incidents/2026-11-03-e0005-history-repair/` (README, killed_aipw_manifest.json, run log, reflog) and is never cited as evidence. |
| 4 | controls | PASS (note 3) | **Positive control, present in substance.** The randomised NSW arm is a known effect, and the pipeline reproduces it: `tables/reproduction_psid1.tsv` `nsw_unadjusted` 1794.342382 against 1794, `nsw_adjusted` 1672.203124 against 1672, and both SEs are within ±1. Every att cell is scored against that experimental ATT. **Negative control, absence declared.** No placebo outcome was run. method_card.md §4 says a "`re75`-as-outcome placebo cell would be the next test … It is not registered in this study". data_card.md check 4 says why constant and shuffled predictors do not apply (a reproduction count and a point estimate). findings §⑥ ("no placebo was run") and §⑦ item 1 repeat it. findings never uses the words "positive control" or "negative control". |
| 5 | multiple comparisons | PASS (note 4) | Scope item 4 names the one stochastic family: "the four PSID-1 att cells", with no family-wise adjustment. All claims drawn from it stay exploratory (C3/C23, C4/C22, C7, C11, C31, C24). The confirmed att claim C29/C5 rests on one pre-registered sealed cell (E0009, P7), chosen by a rule registered before the evidence. The confirmed reproduction claims (C1/C30, C2, C26) compare deterministic closed-form values against transcribed targets at a fixed tolerance. That is a count, not a hypothesis family. No confirmed claim comes from an unguarded family. The literal `n_comparisons` field is not written anywhere. |
| 6 | pre-registration integrity | PASS (note 7) | The consult gate was recorded three times: `events.jsonl` 04:42:40Z, 05:18:40Z (note: "max_experiments 4 -> 6 only … no prediction, rule, track or target changed") and 06:15:31Z (note: time limits only). Both re-records appear in findings scope item 8 and in program.md's two `Decision (lead)` lines. I checked `git diff 9bfa799 395f9b8 -- study.yaml`. It changes only `att.guardrails.wall_seconds.max` 900→10800, `max_run_seconds` 900→10800, `estimators.max_experiments` 4→6 and `confirmation.budget_seconds` 2400→14400. No prediction, rule, research question or target is touched. Each re-record came before the evidence it enabled (E0006 started 05:18:50Z; E0009 started 06:29:18Z). The method card's foresight about P1/P6 (§4 rows P1 and P6: "near 218 and 866", "near 739 … 547") was hashed at the METHOD gate (05:02:33Z), after the predictions and before E0001 (05:04:46Z). The current card hash equals the gate's hash, and the predictions were deliberately left unchanged. |
| 7 | numbers traceable (five hand-checked) | PASS | `klein verify --numbers` passes: 805 numerals, 31 sources. Five numerals checked by hand against their pinned artifacts: (a) **1327.54 and [−129.17, 2835.62]** (C29): `runs/E0009/manifest.json` `primary_metric` 1327.53819, `ci_low` −129.173477, `ci_high` 2835.621967. (b) **−8497.52 (s.e. 712.02)** (C2, sealed half): `tables/reproduction_cps1.tsv` `cps1_unadjusted` −8497.516148 and `_se` 712.020720. (c) **738.83 and 547.05 against 972 and 550**, and "**3 of 5**" (C30): reproduction_cps1 `missed` rows 738.834132 / 547.053372. The five counted CPS-1 targets have 3 `ok`. (d) **−1809.67, 1092, 0.0583** (C22): `tables/att_E0007.tsv` gap −1809.672699, `n_controls_used` 1092, `max_weight_share` 0.058339. (e) **3038.44 / 889.48 / 0.135 / 1146** (C31, C23): `tables/att_E0002.tsv` 3038.435574 and 0.134919 / 1146, and `tables/att_E0006.tsv` gap 889.475838. Spot checks beyond the five: the matching cost 24.28 s (`aux_metrics.tsv` E0005 `wall_seconds` 24.28118); SMD 2.43 / 1.48 for `black` (data_card.md SMD table, line 128); the PSID-1 diagnostics 795.02 / 67.28 (`diag_psid1_all_married*` rows). There are no `klein:numbers-ok` markers in any study markdown. |
| 8 | references | PASS | All 18 entries of `references.yaml` carry `verified: true` with `verified_by` / `verified_at`. All 18 distinct `ref:` ids in findings.md resolve to an entry, with none missing. The only reference behind confirmed claims is `ref:dehejia1998nber` (C26, C30), and it is verified. The method card's `refs_verified: true` matches the file. The JASA article (`ref:dehejia1999`) is verified bibliographically, but its text was not read. Scope item 7 discloses this, together with the profile's unmet two-source transcription hint. |
| 9 | figures | PASS (n/a; note 5) | There are no figures and no `figures/make_figures.py`, so nothing could fail to re-render and no axis can be truncated. The four-point critique has nothing to act on. |
| 10 | vocabulary and scope | PASS | Banned words of the data-science profile ("causes", "drives", "proves", "significant"): a case-insensitive grep of findings.md finds none. The words that must be qualified are qualified or are names. "Effect" appears with its estimand (§⑤ "The estimand": the ATT over the 185 trainees, 1978 earnings, 1982 dollars) and as "not distinguished from no effect" in the summary. "Robust" appears with "to code, seed or specification", and "doubly robust" and "robustness table" are names. Both tracks declare `exactness: exact` with `exactness_note`, so the floor is waived and the resolution is named (1 target; 0.01 dollars). §⑤ says "Nothing here is priced: the contract registers no `materiality:` block", so resolution is never sold as materiality. The study is not a simulation. |

## Round 1: is its FAIL cleared, and do I agree with its notes?

**The FAIL is cleared.** Round 1 failed check 1 on the heading of findings §③ item 1
("… is not one regression — found at METHOD, confirmed on both lanes as transcribed").
Commit dbe4bee replaces it with the clearing condition's wording verbatim. The commit's
findings diff touches only that heading, and it adds a dated program.md line. Both
verifiers still pass. No lock, erratum or evidence changed, and none needed to.

**Its notes.** I agree with all five, and they are carried forward below:

- its Note 1 (name the controls) is my Note 3;
- its Note 2 (confirmed sealed claims rest on a development-cell replication) is part
  of check 1, and I keep it as Note 8 for the tutorial and `knowledge/`;
- its Note 3 (shared model with the synthesist) is in Independence above;
- its Note 4 (lab-notebook overstatements) is my Note 7;
- its Note 5 (tiers, not model ids) is my Note 6.

I add Notes 1, 2, 4 and 5 as new observations, and the scouting-ledger inconsistency in
Note 7.

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md before `klein finalize`)

1. **§③ item 1 body: the column-(5) equality is still unhedged.** Under the corrected
   heading, the body says "the PSID-1 (731 / 886) and CPS-1 (972 / 550) values are Panel C
   column (5)". Erratum E4 named this exact phrase as the single-source part that cost C6
   its confirmed strength. The heading's exploratory label covers it, and the next
   sentences say it "rests on the NBER working paper alone". Even so, "appear, in the
   working-paper transcription, to equal Panel C column (5)" would match C10 and E4. §⑥'s
   closing "the documentary finding that … appears to mix" is hedged but calls the reading
   a "finding". Prefer "the documentary reading".
2. **"Rests on a few people" is a gloss beyond C7.** §⑤ ("each estimate rests on a few
   people (**[C7]**)"), §④ item 2 and "Reading the verdicts together" ("each resting on a
   handful of men") cite C7. C7 measures only the largest single weight share (0.135,
   0.146) and the distinct matched men (56). For IPW and AIPW, one man holding 0.135 of
   the weight over 1146 men on support does not show that the estimate rests on "a few"
   men. The effective sample size and the per-man weights were not pinned (C11 says so).
   Either say "heavily concentrated weights (one man carries 0.135)", or pin an
   effective-sample-size number before using "a few".
3. **Name the controls.** In scope or §⑦, say that the NSW experimental reproduction is
   the positive control and that no negative control (placebo outcome) was run, for the
   reason method_card.md §4 gives.
4. **State `n_comparisons` literally.** Scope item 4 says "the four PSID-1 att cells".
   Add "n_comparisons = 4 (PSID-1 att family); the sealed cells and the deterministic
   reproduction counts are not families". Then the tutorial can copy it verbatim.
5. **Figures have not been refereed.** This gate saw no figures. The profile's set
   (a forest plot against the 1794.34 reference line, balance before and after, overlap
   by group, the decision trajectory) will be built at TUTORIAL without a referee's
   four-point critique. When they exist, the orchestrator should require
   `klein verify` re-render agreement and a zero-based reading of every gap axis.
6. **The roster gives tiers, not model ids,** for the experimenter, the data-gate auditor
   and the lead. The "model" rung therefore rests on a tier difference (Sonnet against
   Opus). It is not a recorded id, and the lead's model is unknown. Record exact ids at the
   next study's CONSULT.
7. **Notebook and ledger statements left as written.** program.md's METHOD finding
   ("Table 3 column (2) is not one regression"), the P1 and P6 Decision lines ("the
   refutation is the finding …") and the E0007 reflection ("the effect vanishes … 1974
   earnings is load-bearing") state readings as fact. A SYNTHESIZE note already re-scopes
   E0007. Add one for the Table 3 reading that points to C10 and E4. Separately, the
   method card's P1 row says the Table 3 / Table 2 mismatch "was not visible at CONSULT:
   scouting ledger S3 transcribed Table 3 only". S3's "What was looked at" column lists
   "Tables 1-3 and notes". The predictions were not changed afterwards, so integrity holds
   (check 6). Still, findings' "Foreseeability" paragraph should say that Table 2 was in
   view at CONSULT, though not cross-read.
8. **Carry the replication qualifier downstream.** C29 and the sealed halves of C1/C30, C2
   and C26 are `confirmed` through a sealed run plus a replication of a *development* cell
   (E6). The tutorial and any `knowledge/` promotion must never write "replicated sealed
   result".

## Clearing conditions (FAIL only)

None. No FAIL condition holds in round 2.
