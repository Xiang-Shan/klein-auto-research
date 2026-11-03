Verdict: FAIL
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 21-bloodmnist-cnn

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. The study has no `generation/manifest.yaml`, so
> `Generation:` is `n/a`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**. Both seats
use the same tool (Claude Code) but different models.
Experimenter: `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh
subagent context per phase (`program.md` `## Roster`, experimenter row, filled). The
referee runs on Opus (claude-opus-5-5), which differs from the experimenter's model, so
`independent-of-experimenter: yes` matches the roster. The synthesist (Opus tier) was a
separate subagent; this referee did not write findings.md. The roster is complete, so
the rung is not capped.

## Mechanical verifiers run

All commands were run from the worktree root `/home/user/wt-21` with `uv run --no-sync`.

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use --no-receipt` | 34 checks, 0 failed. Two `[WARN]`s inside OK rows: (a) contract-driven split: "no study source calls kleinlib.data.contract_split / load_partition". This is a false positive: `train.py` and `sweeps/fit_noise.py` call `kleinlib.data.load_items`, which wraps `load_partition` (kleinlib/data.py:600-614), and every run.log prints `split_fingerprint: 29130f0c…`, which matches the frozen development fingerprint. (b) The referee gate has not been recorded yet, which is expected. evidence_use_rate 1.00 (8/8). Findings numbers: 317 numerals trace to 34 pinned sources. Headroom h = 1.230. |
| `klein claims verify` | 7 checks, 0 failed (23 pinned artifacts hash as recorded; append-only; ancestry OK) |
| `klein predict list` | 4 supported, 1 refuted (P2), 0 inconclusive, 0 open |
| `klein status` | 9 experiments (keep 3, discard 6, measured 0, crash 0); final holdout 1/1 (E0009); 0 single-source confirmed claims |
| figure re-render (`make_figures.py` → temp dir, byte compare) | Not applicable. `figures/` holds only `.gitkeep`, there is no `figures/make_figures.py`, and findings.md cites no figure. |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **FAIL** | Both confirmed claims have the evidence their track requires. C5 rests on the sealed run E0009 (`evaluation_kind: final_test`, `execution.mode: local`, so it was observed, not attested) and on `rep:E0008@20261103T090709Z` (difference 0). C6 is procedural and rests on the same records. `confirmation.require: [sealed, replicate]` is therefore met. Every comparison between development candidates is labelled exploratory. **The FAIL is in the prose.** §③ item 3 states an untested mechanism as fact, with no exploratory label and no claim id: "Mechanism: an unstable constant-rate optimiser at about 8 epochs". The study never varied the learning-rate schedule, and §⑦ item 3 says so ("the one recipe difference … the study never varied"). Constancy of the rate is therefore a hypothesis, not a measured cause. Two smaller unqualified interpretations ride along. §③ item 1 ends with "colour stencils versus local texture" as the explanation of the per-class pattern in `art:per_class`, with no test behind it. §⑥ (batch-normalization bullet) says "E0003 shows what the momentum shortcut costs when the weights are still moving". Weights still moving is backed only by the off-loop seed-0 diagnostic, which program.md and §③ item 2 themselves call "not evidence". Contrast §③ items 1, 2, 5 and 6, which label their mechanisms "(C11, exploratory)", "(C7, exploratory)" or "unresolved". |
| 2 | predictions adjudicated and reported | PASS | Every one of P1–P5 has a run-sourced verdict in `study_state.json` (events seq 7, 11, 35, 41, 42). The §② table matches `klein predict list` row for row. The refuted P2 has its dated `Decision:` line in program.md ("Decision: P2 refuted (anchor 0.7189 < 0.85 …"), and verify's belief-revision row is OK. P5's arithmetic "below" is reported alongside the honest "indistinguishable" reading, not replaced by it. |
| 3 | negative evidence reported | PASS | evidence_use_rate is 1.00 and every discard is in the keep-chain paragraph: E0002, E0003, E0005, E0006, E0007, plus E0009 as the by-design sealed discard row. The discard cluster (single levers after BN that were sub-bar) is written up as a finding in C3 and §③ item 4, and recorded as "positive, below the bar", not as null. E0003 is correctly read as a broken inference path, not as a ruled-out lever. The diff between candidates 3b9a5e5 and e03ed76 is only the running-statistics pass, so C7's +0.5955 is a direct one-edit measurement. No crash occurred. |
| 4 | controls | PASS (note) | Negative control: analytic chance levels (`art:controls`: majority, uniform and prior-matched on both partitions). Positive or reference control: the pixel-linear softmax E0002, plus agreement of the sealed level with the published MedMNIST v2 number. The label-shuffled harness control that data card leakage row 4 required "at EXPERIMENT" was never run. Findings declares this absence openly (controls paragraph, C17, §⑦ item 3), so the FAIL condition "neither present nor declared" does not hold. See note 2. |
| 5 | multiple comparisons | PASS (note) | Every family states `n_comparisons`: 7 frontier comparisons, 5 predictions, 5 card priors, 7 post-hoc seed-dominance pairs. No family-wise guard was applied. Every claim drawn from the frontier family (C2–C4, C7–C11) is exploratory. The confirmed C5 is the level of the selected configuration, measured on the untouched sealed split. It is not one of the seven comparisons, so no confirmed claim comes from an unguarded family. E0008 was the pre-registered P3 cell (registered at d961250, 04:49Z, before any run), not a post-hoc bundle. See note 1 for a wording conflict about selection optimism. |
| 6 | pre-registration integrity | PASS | `events.jsonl` shows four CONSULT records: seq 2 (initial) and three re-records. Seq 4 was before any run (RQ1/RQ4 prior text). Seq 16 set `minimum_delta` from the measured floor, the sanctioned Phase-0 step after E0001 and E0002. Seq 17 raised the run limit from 1800 s to 5400 s before E0003. Each re-record has a reason in its gate note and a dated line in program.md. `git diff d961250 HEAD -- study.yaml` leaves the `predictions:` block untouched, so no rule post-dates its evidence. Raising the delta after E0002 changed no disposition: E0002 is below the incumbent at any delta. |
| 7 | numbers traceable (five hand-checked: see below) | PASS | `klein verify --numbers` passes. Hand-checks: (i) E0009 macro-F1 0.9465 is the mean of seeds 0.945333, 0.954278 and 0.939948 in `runs/E0009/seeds.tsv`, which gives 0.946520. (ii) E0009 accuracy 0.9527 is the mean of 0.951655, 0.958687 and 0.947846, which gives 0.952729. (iii) The binomial SE sqrt(0.958·0.042/3413) = 0.003434, and the gap (0.958 − 0.952729)/0.003434 = 1.535, as in `art:summary`. (iv) `minimum_delta` = max(2·0.0119694, 0.087687/2) = 0.0438435, and h = (1 − 0.946093)/0.0438435 = 1.2295. (v) Fit-noise sd of block means 0.671912, 0.588594 and 0.668756 is 0.047219 (sample sd), and its ratio to 0.0119694 is 3.945. The four-block mean is 0.662049. Also checked: the C9 recalls 0.2562, 0.9201, 0.7949, 0.8582 and 0.8345 were recomputed from the pinned per-seed confusion tables. "33 of 143" monocytes is row 5, column 3 of `tables/confusion_E0008_s0.tsv`. The one `klein:numbers-ok` marker (findings.md line 108) quotes program.md's "about 1.6" (program.md line 322) in order to correct it to 1.54. The reason holds. |
| 8 | references | PASS | All 8 `ref:` ids cited in findings are rows in `references.yaml`, and all 19 rows there are `verified: true`. The method card's `refs_verified: true` comment honestly discloses 18 resolved and 1 url-only (`medmnist_info`). No confirmed claim rests on an unverified reference. The comparator 0.958 is in `yang2023medmnist.why` (Table 3). |
| 9 | figures | PASS (vacuous) | No committed figure exists, so none can fail to re-render and no axis can be truncated. See note 3. |
| 10 | vocabulary and scope | PASS | The cv profile bans "SOTA", "state of the art", "human-level" and "superhuman", and requires qualification of "accurate", "generalizes" and "robust". A grep of findings.md and claims.lock finds none of these. The floor estimands are named (`marginal-resplit` for the bar, `fit-noise` for provenance). The study is not a simulation. No materiality is claimed, and findings §⑤ says so explicitly. The image-level, not-patient-grouped scope is stated with every claim. |

## Notes (each needs a dated `Referee note:` answer in program.md once the FAIL is cleared)

1. **Selection optimism is described two ways (check 5).** §② says the selection effect of picking the best of 8 configurations is "not corrected for but *measured* — by the single sealed access, which came back +0.0004". §③ item 7 says that selection optimism and the train+development refit (13668 against 11959 rows) push in opposite directions, and that "one sealed number cannot separate them … not as 'no optimism'". §③ item 7 is right. The §② sentence should say the sealed access *bounds the net effect* of selection and refit, not that it measures selection.
2. **Data-card obligation left open (check 4).** Data card leakage row 4 deferred the constant / label-shuffled harness check "to be reproduced from train.py at EXPERIMENT". It was never run. Findings discloses this (C17, §⑦ item 3). Before finalize, program.md should state that the obligation is closed as a disclosed gap, not met.
3. **No figures at Gate 3 (check 9).** The TUTORIAL stage needs captioned figures that re-render byte-identically. None exist yet, so check 9 could not exercise anything. Any figure added later (for example a keep-chain or per-class plot) is unreviewed. Its axes must start at zero, or the plot must show the 0.0438 bar, so that sub-bar deltas such as E0006 (+0.0326) and E0007 (+0.0280) are not inflated.
4. **The §③ item 6 heading overreads per-class noise.** "The bundle lowered monocyte recall" is a 0.0396 drop on 143 development monocytes, about 1.2 binomial SEs. The body says this is "close to per-class item noise", but the heading states it as an effect. Suggest "monocyte recall fell (within per-class noise)".
5. **Framework WARN, not a study defect.** verify's contract-driven-split detector does not recognise `kleinlib.data.load_items` as a contract-driven loader. The printed fingerprints match, so the split is checked in substance. The detector should be fixed in kleinlib, not worked around in the study.
6. **Disclosed aux caveat.** The E0001 and E0002 rows in `aux_metrics.tsv` hold last-seed values, filed before framework fix fcadacf. Findings discloses this, and claims correctly read `seeds.tsv`. Nothing needs to change.

## Clearing conditions (FAIL only)

- **Check 1.** Return to SYNTHESIZE and qualify each untested mechanism stated as fact:
  - §③ item 3: label "an unstable constant-rate optimiser at about 8 epochs" as exploratory and cite C11, or write it as a hypothesis. It should say that the learning-rate schedule was never varied, so "constant-rate" is not a measured cause.
  - §③ item 1: mark "colour stencils versus local texture" as an untested interpretation.
  - §⑥ batch-normalization bullet: state that "when the weights are still moving" rests on the off-loop diagnostic, which is not evidence, or drop the clause.

  The rewording must not change any numeral or claim sentence in `claims.lock`. If it does, append claims with `klein claims` rather than editing them. Then re-run `klein verify --numbers --evidence-use` and `klein claims verify`, and hand the study to a fresh referee. Fixing note 1 in the same pass is recommended.
