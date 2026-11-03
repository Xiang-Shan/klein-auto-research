Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 22-cnn-data-scaling (round 2)

> Gate 3 (REFEREE), round 2. Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. The study has no `generation/manifest.yaml`, so `Generation:` is `n/a`.
> Round 1 (committed at 00200ef) returned **FAIL on check 1**. This round re-applies all
> ten checks to the revision at HEAD b26cb8d (commits 2330879, 135526d, ec397d0,
> 9a49a52, b26cb8d) and confirms each round-1 clearing condition and note.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**. I am a
`klein-referee` subagent on Opus (claude-opus-5-5), in a fresh context that saw neither the
loop nor round 1's reasoning (only its committed report). Experimenter, from `program.md`
`## Roster` (row filled in): `klein-experimenter` subagent (Sonnet tier) · Claude Code. The
synthesist (Opus tier) was a separate subagent. The tool rung (same tool, Claude Code) and
the person rung were not reached.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use --no-receipt` | 34 checks, 0 failed. The only WARN is "not yet refereed". evidence_use_rate 1.00 (8/8). Findings numbers: 282 scanned numerals trace to 28 pinned sources. Noise floor "not measured" on both tracks. Belief revision OK. Convergent evidence: 5 confirmed claims cite two or more evidence kinds |
| `klein claims verify` | 7 checks, 0 failed: 20 pinned artifacts hash as recorded, append-only holds, git_head is an ancestor |
| `klein predict list` | 2 supported (P1, P7), 5 refuted (P2–P6), 0 inconclusive, 0 open |
| `klein status` | 8 experiments, all `measured`. Sealed access: primary 1/1 (E0008), exponent 0/1 (by design) |
| figure re-render | **No figures exist.** `figures/` holds only `synthesis_summary.py`, there is no `make_figures.py`, and `report/` is empty. I re-ran `figures/synthesis_summary.py` (as revised) against a scratch copy of `tables/` and `aux_metrics.tsv`. The resulting `tables/synthesis_summary.tsv` is **byte-identical** to the committed one, including the two new rows `rel_error_mean_of_seeds` and `rel_error_of_seed_mean_loss` |

## Round-1 clearing conditions and notes: were they addressed?

| Round-1 item | Addressed? | Where |
|---|---|---|
| Clearing, check 1: C17 prose (§④ item 5) stated the C9 mechanism as fact | **Yes** | It now reads "One untested reading (C9) is that the protocol's shared step budget, not a floor, shaped the curve; no cell was run to test it." The locked C17 sentence is unchanged |
| Clearing, check 1: C10 "kept steepening past N=16000" was unqualified | **Yes** | It is now "a **cross-partition reading only** … confounded with the development-vs-t10k gap (C16) and reads as steepening only if the C11 interpretation holds". "Small-end slope bias" is replaced by "the flat local slope of the three smallest cells (C7, a measured shape whose cause is untested, C9)". The closing sentence is conditional ("if the steepening is real") |
| Note 1, controls | Yes | §① "Controls" names the positive control and says no negative control was run. It says honestly that the record is silent on why |
| Note 2, n_comparisons | Yes | §① "Multiplicity": 7 rules (3 exponent, 4 primary), no family-wise guard, with the reason |
| Note 3, relative-error definition | Yes, via erratum E1 | See the errata row below |
| Note 4, noise floor | Yes | program.md "Referee note 4 / Decision: no separate noise floor" (2026-11-03); §⑤ points to it |
| Note 5, C11 selective comparison | Yes, via erratum E2 | §③ C11 now reports the full ratio row, says "does not obviously explain" instead of "unlikely", gives the inner-set sizes, and drops "strengthens C4" |
| Note 6, "real" in §⑥ | Yes | It now reads "present in all three paired seeds (C8)" |
| Note 7, C1/C2 evidence | Yes | `rep:E0005@20261103T084144Z` was appended to the C1 and C2 evidence lists. The lists only grew, and append-only passes |
| **Errata path (E1/E2)** | **Correct: re-scopes, does not rewrite** | `claims.lock` adds `errata.E1` (claims [C3]) and `errata.E2` (claims [C11]). It tags `C3.errata = [E1]` and `C11.errata = [E2]`. The locked `claim` text of C3 and C11 is byte-unchanged in the diff 00200ef..HEAD, and their strengths are unchanged (C3 confirmed, C11 exploratory). The `erratum_filed` events are sequences 56 and 57 in `events.jsonl` (chain valid). In findings, the locked C3 and C11 sentences are quoted verbatim and flagged "(As locked; re-scoped by erratum E…)". An Errata appendix gives both. The new number `rel_error_seed_mean_loss` (−0.279708) was added under C3 with a home in `art:synth`. No number was removed or mutated |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS | **Confirmed claims.** C1 and C2 are on `exponent` (`require: [replicate]`), backed by `rep:E0007@20261103T084735Z` and now also by `rep:E0005@20261103T084144Z`. C3, C4 and C5 are on `primary` (`require: [sealed, replicate]`), backed by the sealed run E0008 (`execution.mode: local`, run in the foreground under the notary) and by `rep:E0005@20261103T084144Z`. **Attested runs.** E0001–E0006 have `execution.mode: detached` and `observed_by_notary: false`. Findings states this in its opening paragraph. "Strength scoping" adds that rep:E0007 replicates the fit's arithmetic, not the cells, and that only E0005 was re-executed. The protocol accepts either an observed replication or such a sentence, and both exist. **Exploratory claims in prose.** I re-read every section afresh. C9 and C11 are labelled interpretation/hypothesis. C10's cross-partition reading is qualified. C17 names C9 as untested. §⑤ cites "the untested reading C9", and the post-hoc rows are labelled exploratory. One residual soft phrase is in §⑥ (note 2) and does not amount to an unqualified causal claim |
| 2 | predictions adjudicated and reported | PASS | All 7 are adjudicated by run in state: P1, P2 and P5 by E0007 (events 39–41), and P3, P4, P6 and P7 by E0008 (events 48–51). The §② table matches `klein predict list` row for row. Each refuted prediction (P2–P6) has a dated `Decision:` line in program.md, and verify's belief-revision check agrees |
| 3 | negative evidence reported | PASS | evidence_use_rate is 1.00 (8/8). There are no discards, crashes or sweeps, and findings discloses the two `sweeps/sealed_dryrun.*.log` files as no-spend dry runs |
| 4 | controls | PASS | Positive control: the method card's §4 synthetic harness recovers a planted α of 0.200 at floor fraction 0, with signed error +0.000 (method_card.md lines 370–380), through `lib/scaling.py`. That control covers the fit code only, not the training or evaluation path. Negative control: not run, and findings declares the absence. It says the record gives no reason and calls the far-below-chance losses (at most 0.9492 against ln 10 ≈ 2.30) "a sanity bound, not a control". That is honest, and the FAIL condition (neither present nor declared) does not hold |
| 5 | multiple comparisons | PASS | `n_comparisons` = 7 is stated per family (3 + 4). No guard was applied, and findings gives the reason: one deterministic threshold per pre-registered cell, no selection, no p-values. The post-hoc C6–C12 stay exploratory |
| 6 | pre-registration integrity | PASS | Consult was recorded three times, all before the first run (07:42:44Z): 05:04:32Z initial; 05:49:55Z `max_run_seconds` 1800→5400; 06:45:26Z P5–P7 registered from METHOD analysis plus P3 wording for the 59,992 pool, rule unchanged. `study.yaml` was last changed at 20e6454 (06:45:25Z). The fit E0007 (08:08Z) came before the sealed dry runs (08:09:27Z, 08:09:53Z) and the sealed E0008 (08:09:56Z). Round 2 changed no prediction or contract |
| 7 | numbers traceable (hand-checked: −0.2797, 1.0813, 0.1195, 0.0090, 0.0824/0.0876) | PASS | `--numbers` passes, and there are no `klein:numbers-ok` markers in findings, the lock or the report. I recomputed from `runs/E000*/seeds.tsv` and `aux_metrics.tsv`, independently of `synthesis_summary.tsv`. (i) (0.395864 − 0.50659)/0.395864 = −0.279708 (C3/E1), against a per-seed mean of −0.280152 (C3 locked). (ii) The E0004 held-out/inner ratio is 0.756999/mean(best_inner_loss) = 1.08134 (C11/E2). E0001 gives 1.22454 and E0002 gives 1.08007. (iii) The paired N1000−N500 gaps are 0.149007, 0.174837 and 0.034737, mean 0.119527 (C8). (iv) The E0008 seed sd (ddof 1) is 0.009036 (C3 row, §⑤). (v) val_ece is 0.082366 at E0002 and 0.087568 at E0003, so the "rises from N=1000 to N=2000" exception holds. ECE falls monotonically from N=2000 (0.0876 → 0.0477 → 0.0317 → 0.0261 → 0.0104). The MC5 half value 2202.67 = mean(2240, 2240, 2128) also checks out |
| 8 | references | PASS | All 13 `ref:` keys in findings resolve in `references.yaml`. All 16 rows there are `verified: true`, and the method card's `refs_verified: true` is consistent. The confirmed claims C1–C5 rest on no reference |
| 9 | figures | PASS (n/a) | No figure is committed, so there are no pixels or axes to critique at this gate. The derived-table script re-renders byte-identically (above). Figures arrive at TUTORIAL |
| 10 | vocabulary and scope | PASS | None of the ml-research banned or must-qualify words ("SOTA", "state of the art", "beats", "converged", "faster", "generalizes") appears in findings or the lock. "Real" now appears only in a conditional (C10). §⑤ calls `minimum_delta` 0.001 "a contract resolution, not a measured floor", so resolution is not sold as materiality. No floor was measured, so no estimand is due; that is a recorded decision now. No simulation claims are made. §⑤ scopes the exponent "to this protocol, not of the network alone" |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md)

1. **program.md states C9 as fact (checks 1/10, documentation only).** Findings correctly
   labels the compute-limited reading untested (C9). The lab notebook still states it
   flatly in three places. The E0002 observation says "the small cells are compute-limited,
   not data-limited". The E0006 observation says "the curve measures a compute-limited
   protocol". The P4/P6 Decision says "Reading: the small-N cells were compute-limited at
   the 400-step floor". These are contemporaneous notebook entries and must not be
   rewritten. Add a dated `Referee note:` saying they are readings superseded by C9's
   "hypothesis, untested" status. Otherwise the TUTORIAL stage, which mines program.md
   for the journey, may re-promote the hypothesis to fact.
2. **§⑥ Rosenfeld/Hoffmann/Bahri bullet.** "it says a floor, if present, was masked by the
   steepening" is an interpretation phrased as what the data says, and the steepening
   past N=16000 is itself only a cross-partition reading (C10). Prefer "one reading is
   that a floor, if present, was masked by the in-range steepening (C7)". This can be
   answered in program.md or in a findings edit before TUTORIAL. It is not a locked claim.
3. **For the next reader (no action needed beyond acknowledgement).** The primary track's
   `replicate` requirement is met by an observed re-execution of a development cell
   (E0005), not of the sealed cell. The sealed cell E0008 was itself observed. Findings
   "Strength scoping" states this correctly. The positive control also covers the fit
   code only, not the training or evaluation pipeline, and the negative control's
   absence has no recorded reason. Both are disclosed, and a successor study should run
   a shuffled-label cell.

## Clearing conditions (FAIL only)

None. No FAIL condition holds in round 2. Round 1's two check-1 clearing conditions are met
(see the table above).

## Recording

The referee does not record its own gate (protocol, "What the referee may never do"). The
orchestrator records it after reading this report:
`uv run --locked klein gate record referee --study studies/22-cnn-data-scaling --acknowledged-by <orchestrator>`.
Before `klein finalize`, notes 1–3 must be answered with dated `Referee note:` lines in
`program.md`.
