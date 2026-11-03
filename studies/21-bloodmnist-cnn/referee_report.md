Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 21-bloodmnist-cnn (round 2)

> Gate 3 (REFEREE), round 2. Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. The study has no `generation/manifest.yaml`, so
> `Generation:` is `n/a`.
>
> **Round 1** (this file as committed at 7943e06) returned **FAIL** on check 1:
> untested mechanisms were stated as fact in findings §③ item 1, §③ item 3 and §⑥.
> The synthesist revised the study in 039c66e and 64be92d (7943e06..HEAD). This
> round re-applies all ten checks from the start. It does not limit itself to the
> round-1 items. The section "Round-1 items" below states, item by item, whether
> each clearing condition and note was addressed.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**.
Experimenter: `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh
subagent context per phase (`program.md` `## Roster`, experimenter row, filled). This
referee runs on Opus (claude-opus-5-5), a different model from the experimenter's, so
`independent-of-experimenter: yes` agrees with the roster. Both seats use the same
tool, so the rung is "model", not "tool". The synthesist was a separate Opus-tier
subagent, and this referee wrote no part of findings.md. Round 1 ran in a different
fresh context, and nothing from that context was carried here except its committed
report. The roster is complete, so the rung is not capped.

## Mechanical verifiers run

All commands were run from the worktree root `/home/user/wt-21` with `uv run --no-sync`.
Nothing was recorded or committed by them (`git status` stayed clean).

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use --no-receipt` | 34 checks, 0 failed. evidence_use_rate 1.00 (all 8 non-keep runs and registered sweeps cited). Findings numbers: all 320 scanned numerals trace to 35 pinned sources (317 / 34 in round 1; the new pin is `art:per_class_noise`). Headroom h = 1.230. Two `[WARN]`s inside OK rows. (a) contract-driven split: a known framework false positive, because the detector did not recognise `kleinlib.data.load_items`. Per the orchestrator, this is fixed on the deliverable branch, and it is not counted against the study. The split fingerprint check is OK. (b) The referee gate is not recorded yet, which is expected. |
| `klein claims verify` | 7 checks, 0 failed. 24 pinned artifacts hash as recorded, the lock is append-only across history (no claim or number removed or mutated), and ancestry is OK. |
| `klein predict list` | 4 supported, 1 refuted (P2), 0 inconclusive, 0 open |
| `klein status` | 9 experiments (keep 3, discard 6, measured 0, crash 0); final holdout 1/1 (E0009); evidence use 1.00; 0 refutations without a decision; 0 single-source confirmed claims |
| figure re-render (`make_figures.py` → temp dir, byte compare) | Not applicable. `figures/` and `report/` hold only `.gitkeep`, no `figures/make_figures.py` exists, and findings.md cites no figure. |
| derived-table re-render (`tables/synthesis.py` on a scratch copy of the study, with its five outputs deleted first) | All five outputs are byte-identical to the committed ones: `synthesis_summary.tsv`, `controls.tsv`, `per_class.tsv`, `seed_dominance.tsv` and the new `per_class_noise.tsv`. This confirms the program.md statement that "the earlier synthesis outputs are byte-identical". |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS | `confirmation.require: [sealed, replicate]`. **C5** (confirmed) rests on E0009 (`evaluation_kind: final_test`, `execution.mode: local`, so the run was observed, not attested) and on `rep:E0008@20261103T090709Z` (difference 0). **C6** (confirmed, procedural) rests on the same records. All 15 other claims are `exploratory` in `claims.lock`. C7 and C11 are `mechanism-interpretation` and are labelled exploratory wherever the prose uses them. I re-read the prose afresh for mechanisms stated as fact. The round-1 items are now qualified: §③ item 1 ("an untested interpretation: no run probed what either model uses"), §③ item 3 ("an untested hypothesis (C11, exploratory) … 'constant-rate' names a recipe property, not a measured cause") and §⑥ BN ("rests only on the off-loop seed-0 diagnostic … which is not evidence"). The other mechanism statements are also qualified: §③ item 2 (C7, exploratory, diagnostic "not evidence"), §③ item 5 ("unresolved … a hypothesis nobody tested"), §③ item 6 ("unresolved") and §③ item 7 ("unresolved, not 'no optimism'"). "Its loss was still noisy at step 1500" (§③ item 1) is an observation, not a mechanism: `runs/E0001/run.log` prints loss 0.9898, 1.0223, 1.0674 and 0.6497 at steps 750–1500. The one remaining soft premise, in §③ item 4, is hedged in its conclusion ("probably … unmeasured"). It is note 2, not a FAIL. |
| 2 | predictions adjudicated and reported | PASS | P1–P5 all have notary verdicts in state (events `prediction_adjudicated` P2 at 05:37Z, P1 at 05:44Z, P3 at 08:33Z, P4 and P5 at 09:05Z, each inside its run's transaction). §② matches `klein predict list` row for row (observed values 0.69032, 0.718932, 0.946093, 0.946520, 0.952729). The refuted P2 has its dated `Decision:` line (program.md line 131), and verify's belief-revision row is OK. P5's arithmetic "below" is kept alongside the "indistinguishable" reading and is not replaced by it. |
| 3 | negative evidence reported | PASS | evidence_use_rate is 1.00. The keep-chain paragraph cites every discard (E0002, E0003, E0005, E0006, E0007) and the by-design sealed discard row E0009. The sub-bar cluster after BN (E0006, E0007) is written up as a finding: C3 and §③ item 4 call it "positive, below the bar", not null. E0003 is read as a broken inference path, not as a ruled-out lever (C7). No run crashed. |
| 4 | controls | PASS (note 4) | Negative controls: analytic chance levels on development and test (`art:controls`: majority, uniform and prior-matched). Positive / reference control: the pixel-linear E0002, plus agreement of the sealed level with the published MedMNIST v2 number. The label-shuffled harness control is declared absent, with its reason, in the controls paragraph, C17 and §⑦ item 3. program.md now closes the data-card leakage-row-4 obligation as "a DISCLOSED GAP, NOT MET". The FAIL condition "neither present nor declared" does not hold. |
| 5 | multiple comparisons | PASS | `n_comparisons` is stated for all four families: 7 frontier comparisons, 5 predictions, 5 card priors and 7 post-hoc seed-dominance pairs. No family-wise guard was applied, and every frontier-derived claim is exploratory. The confirmed C5 is a level measured on the untouched sealed split, not a member of an unguarded family. The §② selection-optimism sentence now says the sealed access "bounds the net effect of selection and the train + development refit together; it does not measure selection on its own". This agrees with §③ item 7, so round-1 note 1 is cleared. |
| 6 | pre-registration integrity | PASS | `events.jsonl` has four CONSULT records. 04:49Z is the initial record, with P1–P5 registered at d961250. 05:17Z is a re-record before any run, which corrected the prior text of RQ1 and RQ4. 05:50Z set `minimum_delta` from the measured floor after E0001 and E0002, the sanctioned Phase-0 step. 05:51Z raised the run limit from 1800 s to 5400 s before E0003. Each re-record has a reason in its gate note and in program.md. `git diff d961250 HEAD -- study.yaml` changes only `minimum_delta`, `noise_floor`/`fit_noise`, the run limit and the two prior strings, never a `predictions:` rule. The first run started at 05:19Z, after every rule was registered. 7943e06..HEAD touched neither `study.yaml` nor `events.jsonl`. |
| 7 | numbers traceable (five hand-checked, all different from round 1's: see below) | PASS | `klein verify --numbers` passes, with 320 numerals and 35 sources. Five numerals were recomputed from pinned artifacts. (i) E0008 ECE 0.0125 and log-loss 0.1333 (C10) are the means of `runs/E0008/seeds.tsv` val_ece (0.015485, 0.011618, 0.010443 → 0.012515) and val_mlogloss (→ 0.133349). (ii) E0008 seed sd 0.0086 is the sample sd of 0.937187, 0.946645 and 0.954448, which gives 0.008644. (iii) The E0008 wall-clock factor of 17.8 is 2885.578585 / 162.475863 = 17.760. (iv) The sealed seed sds 0.0072 (macro-F1) and 0.0055 (accuracy) and the mean wall time of 171.5 s match `runs/E0009/seeds.tsv` (0.007238, 0.005500, 171.549). (v) The new §③ item 6 figure "1.2 to 1.3 binomial standard errors": recall 0.834499 → 0.794872 on n = 143 gives SEs of sqrt(0.8345·0.1655/143) = 0.031077 and 0.033767. The drop of 0.039627 is then 1.275 and 1.174 SEs, as in `tables/per_class_noise.tsv`. Also checked: the sealed monocyte recall 0.8582 (`per_class.tsv`, 0.858156); C4's margin over the bar, 0.050088 − 0.0438435 = 0.006244; and the E0008-over-E0004 seed dominance of 9/9 (`seed_dominance.tsv`). The one `klein:numbers-ok` marker (findings.md line 108) quotes program.md's "about 1.6" (program.md line 322) in order to correct it to 1.54 (`gap_in_binomial_se_at_0958` 1.535063). Its reason holds. |
| 8 | references | PASS | All 8 `ref:` ids that findings cites (yang2023medmnist, acevedo2019, ioffe2015, santurkar2018, bouthillier2021, picard2021, cohen2016, veeling2018) are rows in `references.yaml`, and all 19 rows there are `verified: true`. The method card's `refs_verified` comment discloses the one url-only row (`medmnist_info`), which supports no claim. No confirmed claim rests on an unverified reference. |
| 9 | figures | PASS (vacuous; note 3) | No committed figure exists, so none can fail to re-render and no axis can be truncated. |
| 10 | vocabulary and scope | PASS | The cv profile bans "SOTA", "state of the art", "human-level" and "superhuman", and requires "accurate", "generalizes" and "robust" to be qualified. A grep of findings.md and claims.lock finds none of these. The estimands are named: `marginal-resplit` for the bar and `fit-noise` for the seed sweep. The study is not a simulation. No materiality is claimed (§⑤ says so). The image-level, not-patient-grouped scope is stated as travelling with every claim. |

## Round-1 items — were they really addressed?

| Round-1 item | Status | Where |
|---|---|---|
| Clearing condition, §③ item 3 | **Cleared.** It is now labelled an untested hypothesis (C11, exploratory) and states that the learning-rate schedule was never varied. | findings §③ item 3; diff 7943e06..039c66e |
| Clearing condition, §③ item 1 | **Cleared.** "Colour stencils versus local texture" is now marked an untested interpretation. | findings §③ item 1 |
| Clearing condition, §⑥ BN bullet | **Cleared.** "Weights still moving" is tied to the off-loop diagnostic, which is explicitly called not evidence. | findings §⑥ |
| "No numeral or claim sentence in claims.lock changes" | **Held.** `klein claims verify` append-only check is OK. The lock diff only adds the pin `per_class_noise` and repins `synthesis_script` (64be92d). No claim or number changed, so no erratum was needed. | `git diff 7943e06..HEAD -- claims.lock` |
| Note 1 (selection optimism described two ways) | **Addressed.** §② now matches §③ item 7. | findings §② `n_comparisons` |
| Note 2 (harness-control obligation) | **Addressed.** It is closed in program.md as a disclosed gap, not met. | program.md, "Referee notes — answers" |
| Note 3 (no figures at Gate 3) | **Acknowledged** for TUTORIAL. It still applies, so it is carried forward as note 3 below. | program.md, same section |
| Note 4 (monocyte heading overread) | **Addressed.** The heading now reads "within per-class noise", and the body gives 1.2 to 1.3 SEs from the new pinned table. See note 1 below for a method caveat. | findings §③ item 6; `tables/per_class_noise.tsv` |
| Note 5 (framework WARN) | **Acknowledged.** It is a framework item, fixed on the deliverable branch per the orchestrator, and not counted. | program.md |
| Note 6 (aux last-seed caveat) | **Acknowledged.** No change was needed. | program.md |

## Notes (PASS-WITH-NOTES)

Notes 1 and 2 are new. Each needs a dated `Referee note:` answer in program.md before
`klein finalize`. Notes 3–5 carry round-1 items forward. Their existing dated answers
in program.md's "Referee notes — answers" section suffice, unless the orchestrator
wants to restate them.

1. **The monocyte noise figure uses a single-recall SE, not the SE of a difference
   (check 7 / §③ item 6).** `tables/per_class_noise.tsv` divides the E0004 → E0008 drop
   by the binomial SE of one recall. The drop is a difference of two recalls measured
   on the same 143 development monocytes. An independent-samples SE would be about 0.046,
   putting the drop near 0.86 SE. A paired SE could be smaller than either. The
   conclusion "not an established effect" is independently supported by the per-seed
   recalls in the pinned confusion tables: E0004 gives 0.825, 0.909 and 0.769, and
   E0008 gives 0.755, 0.727 and 0.902, so the two ranges overlap widely. The wording
   therefore stands. A future revision should say "SE of one recall" or quote the seed
   ranges, so that the reader does not take 1.2–1.3 as a test statistic for the
   difference.
2. **One unmeasured premise in §③ item 4.** "where macro-F1 is noisier per item than
   near 0.93" is stated as fact. It is a reasonable binomial expectation, and the
   sentence's conclusion is correctly hedged ("probably wider … unmeasured — ⑦ item 2").
   But the item bootstrap was never run at the incumbent. Suggested wording: "expected
   to be noisier per item". This does not change any claim.
3. **Still no figures (check 9, carried forward from round-1 note 3).** TUTORIAL will
   add the study's first figures, and Gate 3 has not reviewed any of them. Keep-chain
   and per-class plots must start their axes at zero or draw the 0.0438 bar, so that
   sub-bar deltas (E0006 +0.0326, E0007 +0.0280) are not visually inflated.
4. **Harness control remains a disclosed gap (check 4, carried forward from round-1
   note 2).** This is answered in program.md. C17 and §⑦ item 3 carry it forward.
5. **Framework WARN (carried forward from round-1 note 5).** The contract-driven-split
   detector WARN is a framework false positive, fixed on the deliverable branch. It is
   not counted against this study.

## Clearing conditions (FAIL only)

None. No FAIL condition holds.
