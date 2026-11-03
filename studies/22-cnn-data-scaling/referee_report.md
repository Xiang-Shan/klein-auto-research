Verdict: FAIL
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 22-cnn-data-scaling

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. The study has no `generation/manifest.yaml`, so `Generation:` is `n/a`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**. I am a
`klein-referee` subagent running on Opus (claude-opus-5-5) in a fresh context that never saw the loop.
Experimenter: `klein-experimenter` subagent (Sonnet tier) · Claude Code (from `program.md`
`## Roster`, row `experimenter`, which is filled in). The synthesist (Opus tier) was a separate
subagent. I did not reach the tool rung (same tool, Claude Code) or the person rung.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use --no-receipt` | 34 checks, 0 failed; evidence_use_rate 1.00 (8/8); findings numbers: 239 numerals trace to 28 pinned sources; the only WARN is "not yet refereed"; noise floor "not measured" on both tracks |
| `klein claims verify` | 7 checks, 0 failed (20 artifacts hash as recorded; append-only holds) |
| `klein predict list` | 2 supported (P1, P7), 5 refuted (P2–P6), 0 inconclusive, 0 open |
| `klein status` | 8 experiments, all `measured`; primary sealed 1/1 (E0008); exponent sealed 0/1 (by design) |
| figure re-render | **no figures exist** (`figures/` holds only `.gitkeep` and `synthesis_summary.py`; there is no `make_figures.py` and `report/` is empty). Instead I re-ran `figures/synthesis_summary.py` against a scratch copy of `tables/` + `aux_metrics.tsv`: the output `tables/synthesis_summary.tsv` is **byte-identical** to the committed one |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **FAIL** | The strengths in the lock fit the evidence. C1/C2 are `confirmed` on `exponent` (`require: [replicate]`), backed by `rep:E0007@20261103T084735Z`. C3/C4/C5 are `confirmed` on `primary` (`require: [sealed, replicate]`), backed by the sealed run E0008 and `rep:E0005@20261103T084144Z`. Attested runs: E0001–E0006 are `execution.mode: detached`, `observed_by_notary: false`. Findings says so in its opening paragraph and in "Strength scoping", and E0005 has an observed re-execution, so the attested-run condition is met. **However, prose states an exploratory claim as fact.** ④ item 5 (C17) says: "the curve's shape over the measured range came from the protocol (its step schedule and checkpoint rule) as much as from any floor (E0007, E0008)". That is the C9 mechanism, which §③ itself labels "*a hypothesis, not tested*" ("no step-matched or step-extended small cell was run"). Here it is restated with no qualifier, as a causal finding, and cited to E0007/E0008, which do not test it. A second instance is in ③ C10: "So beyond the small-end slope bias, the curve kept steepening past N=16000". That inference crosses partitions (N=16000 is scored on development, the full pool on t10k). C16 says this gap "cannot be split exactly between the law and the partition". The statement only holds if the C11 interpretation holds |
| 2 | predictions adjudicated and reported | PASS | All 7 adjudicated in `study_state.json` by `source: run` (P1/P2/P5 by E0007; P3/P4/P6/P7 by E0008). The §② table matches the ledger row for row. Every refuted prediction (P2, P3, P4, P5, P6) has a dated `Decision:` line in `program.md`, and `klein verify` "belief revision" agrees |
| 3 | negative evidence reported | PASS | evidence_use_rate 1.00. There are no discards, crashes or sweeps. The two `sweeps/sealed_dryrun.*.log` files are disclosed as dry runs. All eight `measured` cells are cited |
| 4 | controls | PASS (note) | A positive control exists. The method card's §4 synthetic harness recovers a planted exponent (α 0.200 at floor fraction 0; signed error +0.000) through `lib/scaling.py`, which is the fit code E0007 ran. No negative control (shuffled labels or a constant predictor at ln 10) was run. Its absence is not declared in findings, and the data card's NOTE 3 defers the chance check. This is not a FAIL, because a control is present. See note 1 |
| 5 | multiple comparisons | PASS (note) | `n_comparisons` is not stated anywhere. Each confirmed claim (C1–C5) applies one pre-registered deterministic threshold rule to one registered cell. None is the best of a searched family, and there are no p-values, so no confirmed claim comes from an unguarded selection. See note 2 |
| 6 | pre-registration integrity | PASS | There are two consult re-records, both before any run. 05:49:55Z: `max_run_seconds` 1800→5400, no prediction changed. 06:45:26Z: P5–P7 registered from the METHOD analysis, P3 wording names the 59,992 pool, rules unchanged. `study.yaml` was last changed at commit 20e6454 (06:45:25Z), and its hash b1b7d96b… is pinned by the gate and by `art:contract`. The first run started at 07:42:44Z (E0001). The fit E0007 (08:08Z) was frozen before the sealed access E0008 (08:09:56Z). The sealed dry runs trained 60 steps on development data only |
| 7 | numbers traceable (hand-checked: see list) | PASS | `--numbers` passes, and there are no `klein:numbers-ok` markers in findings or the lock. I recomputed these from `runs/E000*/seeds.tsv` and `tables/scaling_fit.tsv`. (i) The predicted loss 2.125837·59992^−0.130360 = 0.50659 matches the pinned 0.5066. (ii) Predicted minus measured = 0.11073, matching the pinned 0.1107. (iii) The 3-cell OLS local exponent over 500–2000 is −0.00960, and over 4000–16000 it is 0.21270, with refit a = 4.4164 predicting 0.42536 (rel. −0.07450). These match C7/C10. (iv) The per-seed slopes are 0.14232, 0.12598 and 0.12193, and the t₂ interval is 0.10326 to 0.15689. These match C12. (v) The paired N1000−N500 gaps are 0.1490, 0.1748 and 0.0347, with mean 0.1195. These match C8. (vi) The sealed ratio 0.395864/0.363943 = 1.08771 and the cross-partition exponent 0.26742 match C11/C10. See note 3 on the rel-error definition |
| 8 | references | PASS | All 13 `ref:` keys cited in findings resolve in `references.yaml`, and all 16 rows there are `verified: true`. The method card's `refs_verified: true` is consistent with that. No confirmed claim (C1–C5) rests on a reference |
| 9 | figures | PASS (n/a) | No figure is committed, so nothing can be pixel-checked or axis-critiqued at this gate. The one derived-table script re-renders byte-identically (above). Figures arrive at TUTORIAL and are not refereed here |
| 10 | vocabulary and scope | PASS (note) | No ml-research banned word appears ("SOTA", "beats", "converged", unqualified "faster"/"generalizes") in findings or the lock. No resolution is sold as materiality: ⑤ says `minimum_delta` 0.001 is "a contract resolution, not a measured floor". No simulation claim is made. There is no floor estimand to name because none was measured, and that is disclosed. See note 4 |

## Notes

These must be answered with dated `Referee note:` lines in `program.md` once the FAIL is cleared.

1. **Controls (check 4).** Findings never says which controls exist. Add one sentence: the
   positive control is the method card's synthetic recovery of a planted α through `lib/scaling.py`.
   The negative control (chance-level ln 10 ≈ 2.30, or a shuffled-label cell) was not run, and
   the reason should be given.
2. **Multiplicity (check 5).** State `n_comparisons`: 7 registered rules, 3 on `exponent` and 4
   on `primary`. Also say that no family-wise guard was applied, because each rule is a single
   deterministic threshold on a pre-registered cell, not a selection.
3. **Relative-error definition (check 7).** The quoted −0.2802 is the mean of the three per-seed
   relative errors. The seed-mean loss gives (0.395864 − 0.506590)/0.395864 = −0.2797. The
   difference is immaterial, but C3's sentence should say "seed mean of per-seed signed relative
   errors". The registered method (program.md Decision on per-seed errors) already defines it that way.
4. **Noise floor (check 10).** `policy.noise_floor: required`, yet `klein verify` reports the floor
   "not measured" on both tracks. On registered tracks no keep bar is used, and findings says so.
   The per-cell seed sd (`runs/E####/seeds.tsv`) is the only noise measure. Record this in program.md
   as a decision rather than leaving it implicit.
5. **C11's comparison is selective.** The "test looks harder" contrast uses the two largest development
   cells (ratios 1.0158 and 1.0161). The pinned `tables/synthesis_summary.tsv` also has E0004 at 1.0813,
   E0002 at 1.0801 and E0001 at 1.2245, so the held-out/inner ratio is not monotone in N. E0008's 1.0877
   sits close to E0004's. The inner sets also differ in size (800/1600 vs 5,999 images), which changes
   how optimistic the min-over-checkpoints is. C11 is labelled an interpretation and is exploratory, so
   this is not a FAIL. Still, report the full ratio row and soften "unlikely". The clause "and so
   strengthens C4" should go: C4 is a procedural verdict on a registered rule and needs no mechanism.
6. **"Real" in ⑥.** "the inversion is real across all three seeds" overstates 3/3 paired seeds (a sign
   test gives 1/8 under the null). Say "present in all three paired seeds" (C8 is exploratory).
7. **C1/C2 evidence list.** Neither cites `rep:E0005@20261103T084144Z`, the only observed re-execution of an
   input cell. The prose's attested-run sentence carries the disclosure, so this is not a FAIL. A future
   claims revision could add it, without mutating the lock.

## Development-vs-test disclosure (asked for specifically)

The fit cells (development lane, train rows 50,000–59,999) and the sealed cell (official t10k) are scored on
different partitions. This is disclosed in the opening paragraph, in the C4 row and sentence, and in C11, C16,
⑤ and the ECE sentence. It is also the subject of ⑦ item 2. Disclosure is adequate. The FAIL above is about
C10 drawing a "kept steepening" conclusion across that very gap without qualification.

## Clearing conditions (FAIL)

- **Check 1, ④ item 5 (C17 prose).** Qualify or remove the clause "— the curve's shape over the measured
  range came from the protocol (its step schedule and checkpoint rule) as much as from any floor (E0007,
  E0008)". An acceptable form: "— one untested reading (C9) is that the protocol's shared step budget, not a
  floor, shaped the curve". It must name C9 and its status. The locked C17 sentence already omits the clause
  and does not need to change.
- **Check 1, ③ C10 prose.** Qualify "So beyond the small-end slope bias, the curve kept steepening past
  N=16000". It is a cross-partition reading that is confounded with the development-vs-t10k gap (C16) and
  holds only under the C11 interpretation. "small-end slope bias" should be described as the flat local
  slope of the three smallest cells (C7), not as a bias with a cause.
- Then re-run `klein verify --numbers --evidence-use` and `klein claims verify` and return to REFEREE, where
  a fresh referee pass reads the revised findings. The notes above should be answered in the same revision.
