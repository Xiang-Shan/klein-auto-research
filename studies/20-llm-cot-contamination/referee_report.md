Verdict: FAIL
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 20-llm-cot-contamination

> Gate 3 (REFEREE), written 2026-11-03 in a fresh context. I read `findings.md` first,
> then `claims.lock`, `study.yaml`, `results.tsv`, `aux_metrics.tsv`, the six manifests,
> the three replication records, `study_state.json`, `events.jsonl`, `data_card.md`,
> `method_card.md`, `references.yaml`, `scouting_ledger.md`, `research_plan.md` and
> `playbook.md`, and `program.md` last. Protocol:
> `.claude/skills/klein/references/referee-protocol.md`; also
> `references/model-calls-protocol.md`. I ran read-only verbs only, with `KLEIN_OFFLINE=1`
> and no network call. I edited no study file other than this one.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**.
Experimenter: the `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh
subagent context per phase (`program.md` `## Roster`). I am an Opus-tier subagent
(`claude-opus-5-5`) in a context that never saw the loop. That is a different model, so
`independent-of-experimenter: yes` agrees with the roster.

Disclosure: the same orchestrating Claude Code session spawned the experimenter, the
synthesist and me, so the tool and the session are shared (the study's commits and this
report carry the same `Claude-Session` URL). The synthesist is also Opus tier. The rung
is "model" with respect to the experimenter, and nothing higher.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use --no-receipt` | 34 checks, 0 failed. Warnings printed inside OK rows: no study source calls `contract_split`/`load_partition`; neither track's noise floor was measured; referee gate not yet recorded. `evidence_use_rate 1.00` (6/6 non-keep runs cited); findings numbers: 267 numerals trace to 23 pinned sources |
| `klein claims verify` | 7 checks, 0 failed |
| `klein predict list` | 2 supported (P3, P6), 4 refuted (P1, P2, P4, P5), 0 inconclusive, 0 open |
| `klein status` | 6 experiments (measured 5, crash 1); gates consult=recorded, data=**overridden**, method=recorded; sealed access contamination 1/1, cot_gain 1/1 |
| figure re-render | not applicable: `figures/` is empty and the study has no `figures/make_figures.py` |
| independent re-score (mine, offline, read-only, using the study's own `lib/prompts.exact_match` on the committed `calls/` shards and the re-query shards) | reproduces em_direct/em_cot 0.95/0.96 (public), 0.985/0.96 (dev twins), 0.97/0.97 (sealed twins), em_original 0.98; 4 of 300 bare direct replies; direct median 112.5 tokens; 9 of 600 item-arm scores changed under the salted re-query (namespace `rep:E0002@20261103T082725Z`, 0 cached) |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** (notes 3, 4, 5) | Both tracks carry the two kinds `confirmation.require: [sealed, replicate]` demands. Sealed: E0005 (`evaluation_kind: final_test`, 400 new calls) and E0006 (`final_test`). Replicate: `rep:E0002@20261103T082725Z` and `rep:E0003@20261103T084446Z`, both `mode: replicate`, both salted (0 cached calls). The replay `replay:E0002@20261103T085311Z` is cited only by C13 (exploratory) and is named in the caveats as satisfying no requirement. That is correct under model-calls-protocol.md ("Replay is not replication"). E0006 made 0 new calls: its originals are E0003's ledger entries and its twins are E0005's. Findings says so three times (C3 limit (a), C12, caveats), so the coupled sealed cells are not presented as independent. Mechanisms C6, C7 and C8 are labelled `mechanism-interpretation, exploratory` in the prose. C5's "terse chain-of-thought" holds: I read the direct-arm replies in `calls/E0001-000.jsonl.gz`, and they write worked steps. |
| 2 | predictions adjudicated and reported | PASS | `klein predict list`: 6/6 adjudicated by the notary (`prediction_adjudicated` events, seq 12–33). Findings §② matches state row for row. P1, P2, P4 and P5 each have a dated `Decision:` line in program.md "Belief-revision decisions", and `klein verify` reports belief revision OK. |
| 3 | negative evidence reported | PASS | `evidence_use_rate 1.00`. The E0001 crash (HTTP 429 after 599 calls) is reported as an infrastructure fault and re-run as E0002, which reused 599 of its pinned answers (disclosed). That is a retried crash, not a crash read as a verdict. All five measured cells are cited. |
| 4 | controls | **FAIL** | The study has no positive control and no negative control, and `findings.md` and `program.md` never declare either absence. The only nearby statement is `data_card.md` clean-room row 4: the chance-level row is "N/A in index mode … Reasoned, not executed", which partly declares a negative control's absence. The positive control (a known effect the pipeline must detect) is neither present nor declared anywhere. That matters more here than usual, because the confirmed headlines C2 and C4 are nulls: nothing on the record shows that this scorer and paired bootstrap would detect a gain if there were one. The mechanical identities (E0004 em_cot = E0003 em_twins; re-scored = notarized) and the replay show the pipeline is consistent. They are not controls. |
| 5 | multiple comparisons | **FAIL** | `n_comparisons` is not stated for either family anywhere in the study: `grep` of findings, program, research_plan, study.yaml, method and data cards finds no `n_comparisons`, Bonferroni or `family_maxt`. No family-wise guard was applied. This is a `kind: test` study, and inquiry-model.md:160 requires CONSULT to fix "the hypothesis family, `n_comparisons`, the family-wise guard". The confirmed claims C2 and C4 come from the `cot_gain` family (P1, P2, P4, P5: four rules) and C3 from the `contamination` family (P3, P6). The rubric's FAIL condition, a confirmed claim drawn from an unguarded family, therefore holds. On substance, and only to show the fix is cheap: I re-ran the paired/cluster bootstrap on the pinned `tables/cot_gain_E000{2,4,5}.tsv`. My 95% intervals reproduce the notarized ones. At a Bonferroni level for four comparisons (98.75%), the upper ends were about 0.037, 0.01 and 0.05, all below 0.10, and widening only strengthens C3's "0.05 not excluded". So no verdict is likely to move. These are my numbers, not pinned ones, and they must not be copied into findings; the study has to compute and pin its own. |
| 6 | pre-registration integrity | PASS (note 6) | P1–P6 and their rules are byte-unchanged from the first CONSULT record (05:04:33Z) to HEAD (`git diff 8e5f657 a7bf6af -- study.yaml` touches only `minimum_delta`, `calls.*` and the anchor phase budget). There are three CONSULT re-records: 05:19 (per-run caps, scouting S4), 07:41 (tolerances 0.03/0.05 as `minimum_delta`, dated model snapshot, before any study call; E0001 started 07:42:33Z) and 07:57 (workers 8→2, anchor slot +1, after the E0001 crash, with no prediction, rule, prompt or cell changed). Each has a stated reason in the gate note and in program.md. No prediction's contract hash post-dates the run that adjudicated it. The lead saw the E0001 crash shard's direct-arm outputs (lengths) before E0002 and explicitly did not change the prompt (program.md 2026-11-03). |
| 7 | numbers traceable | PASS (note 1) | `klein verify --numbers` passes, and findings contains no `klein:numbers-ok` marker. Hand-checked: (1) C2 McNemar p 0.5078 = 2·(1+9+36+84)/512 for 3 of 9 discordant, matching `aux_metrics.tsv` E0002 `mcnemar_p 0.5078125`; (2) C3 sealed interval [-0.04, 0.065] = E0006 `ci_low -0.0400…036`, `ci_high 0.06499…95`; (3) C5 ratio 1.85 = 265.7/143.5 (`synthesis_quantities.tsv` `m6_token_ratio_anchor_gsm8k 1.851568`); (4) C7 shift 0.045 = abs(-0.025 - 0.02), em_original 0.98 → 0.94 (`rep_E0003` `replicate_block`); (5) M5 / C13 "9 of 600", recomputed by me from the raw shards; (6) C11 widths 0.075 = 0.06+0.015 and 0.105 = 0.065+0.04; (7) C6/C8 discordant 9, 12 and 7 against `synthesis_paired.tsv`. See note 1 on the `gsm8k_name_numeral` alias. |
| 8 | references | PASS | All eight cited `ref:` ids (wei2022, kojima2022, sprague2024, mirzadeh2024, dlugosz2026, zhang2024, he2025, atil2024) are `verified: true` in `references.yaml`. No confirmed claim rests on a reference (only exploratory C7 cites he2025 and atil2024). The method card's `refs_verified: true` matches 21/21 rows. I did not re-resolve them (offline). |
| 9 | figures | PASS (note 7) | No committed figures and no `make_figures.py`, so nothing can fail to re-render and no axis can be truncated. |
| 10 | vocabulary and scope | PASS (note 8) | None of the llm profile's banned words appears ("understands", "reasoning ability", "emergent", "solved", "SOTA"), and "improves", "generalizes" and "robust" are absent. Scope is stated (one dated snapshot, one date, temperature 0, thinking off, two registered prompts). "Resolution" is used only for the probe's detection limit, and §⑤ says no `materiality:` block exists. There is no measured floor and therefore no floor estimand. §⑦ item 4 says plainly that both `minimum_delta` values are pre-registered replication tolerances, not measured floors. |

## The `gsm8k_name_numeral` alias (asked for by the orchestrator)

`claims.lock` → `numbers.gsm8k_name_numeral = {value: 8, art: study_yaml, precision: 0}`,
listed in C1's and C2's `numbers[]`. It was added in commit `acd640a` because the
claim-sentence scan (`kleinlib/claims.py` `NUMERAL_RE`, which has no look-behind on digits)
reads the "8" inside the benchmark name GSM8K as a numeral. `SENTENCE_EXEMPT_RE` exempts
only `E####`, `P#`, `C#`, `RQ#`, `S#`, years and versions, not alphanumeric names.

**My judgement: acceptable as a disclosed workaround, not a fabricated home. It is a
NOTE, not a FAIL.**
- claims-protocol.md exempts identifiers from the numbers law. GSM8K is one, so the
  sentence quotes no number here. The lock entry's `note` says "NOT a measured value" in
  plain words.
- The value really does occur in its artifact as the same identifier
  (`data.source: "bundled:gsm8k-test/test.jsonl"`). No measured numeral in C1 or C2 is
  homed by it: no other numeral in either sentence rounds to 8 at precision 0.
- The documented escape hatch, a `klein:numbers-ok` marker inside the claim sentence,
  would have exempted every numeral in C1 and C2 (`_check_claim_sentences` skips the
  whole sentence). The alias is the narrower of the two available tools.
- Costs that stay on the record: the numbers ledger now holds a non-number, and the lock
  is append-only, so it is permanent. The alias would silently home any future "8" in
  those sentences. A tutorial that reads headline numbers from `claims.lock` must not
  render it. The right fix belongs in the framework: exempt digits glued between letters
  (for example `GSM8K`, `Llama3B`, `p5`) in `SENTENCE_EXEMPT_RE`, in a framework change
  rather than this study.

## Notes (to be answered with a dated `Referee note:` line in program.md once the FAILs clear)

1. **`gsm8k_name_numeral`.** Accepted as above. Record in program.md that it is an
   identifier workaround. The TUTORIAL stage must exclude it from any number it renders
   from the lock.
2. **DATA gate was overridden, and findings does not say so.** `study_state.json` gates.data
   `status: overridden` (mechanized 13-gram near-dup FAIL: 179/500 and 188/200, all
   own-template by design). The reason is sound and well evidenced in `data_card.md` B1.
   A reader of `findings.md` alone never learns that Gate 1 was passed by override. Add one
   caveat line.
3. **Coupling beyond the sealed pair.** E0004's CoT arm is E0003's 200 development-twin
   ledger entries (`calls_cached 200`). The program's instrument notes disclose this
   design, but findings names only E0005/E0006 as coupled (C12, caveats). Findings
   mentions the E0004/E0003 identity only as a "mechanical identity". The model-calls
   doctrine says cells that share ledger entries are not independent, so the caveat list
   should name both coupled pairs.
4. **C4's replication is track-level, not cell-level.** C4 (confirmed) cites E0004 and
   E0005 but no `rep:` id. The track's replicate requirement is met by `rep:E0002`,
   which re-queried the public items, not the twins. The twin-block gain was never
   re-queried, although E0005 is an independent fresh query that agrees. That is
   acceptable under the track-level rule (`klein finalize` checks the track). Findings
   should say which replication backs C4, or that none re-queried the twin gain.
5. **Phrasing that runs ahead of the evidence (all on exploratory or implication text).**
   (a) C6 calls the gain "near-unmeasurable". It was measured, with a tight interval
   ([-0.01, 0.03] on public items). What the ceiling removes is headroom: the registered
   0.10 was unreachable given the observed direct score. (b) C10's "the refutation is
   guaranteed by arithmetic" holds only conditional on the observed em_direct, which was
   unknown when P2 was registered (prior 0.55–0.85). (c) §⑤ "the cheaper prompt scored
   the same" overstates an interval of [-0.01, 0.03]; no equivalence test was registered.
   "Scored within the interval [-0.01, 0.03] of" is the honest form. (d) C8's "truncation
   is not the mechanism": my re-score finds that 1 of the 6 direct-only development twins
   (twA-t1179-2) was a length-truncated CoT reply, so truncation explains at most one
   sixth of them. The direct-only wins also cluster in 3 templates (t0906, t1046, t1179,
   two each).
6. **Data card W3 is not carried into findings.** 28 sealed twins repeat a (template,
   answer) pair already in twin_dev, and 186/200 sealed twins share a 13-gram with a dev
   twin. The sealed twin block is therefore not structurally independent of the
   development block, which bears on what E0005 and E0006 "confirm". Add one caveat line.
7. **Tutorial figures.** The TUTORIAL stage needs `figures/make_figures.py` and
   re-renderable figures. The four-point figure critique (zero-based axes for deltas of
   0.01–0.025) applies then.
8. **The `contract-driven split` warning.** No study source calls `contract_split`. The
   predefined split is the `split` column of a deterministic index, and `klein verify`
   matches the split fingerprint, so this is informational. The data card should still
   say why the warning is benign.

## Clearing conditions (FAIL only)

- **Check 4 (controls).** One of the following, in findings.md (for example in §③ or the
  caveats), with any computed number pinned through `klein claims` like every other number:
  (a) declare the absence of a positive control and of an executed negative control,
  each with its reason (the data card's chance-level reasoning can be cited for the
  negative control); or (b) add offline controls computed from the committed ledger with
  no model call. A negative control could re-score the recorded replies against permuted
  golds and expect near-zero exact-match. A positive control could plant a known gain, by
  scoring k recorded direct replies as wrong, and show the paired/cluster bootstrap
  recovers it. Because the confirmed headlines are nulls, (b) is the stronger answer.
- **Check 5 (multiple comparisons).** State `n_comparisons` for each family in findings
  §② (`cot_gain`: P1, P2, P4, P5; `contamination`: P3, P6). Then either apply a
  family-wise guard and report it from a pinned artifact (for example Bonferroni-level
  intervals added to `lib/synthesis.py` → `tables/synthesis_quantities.tsv`, showing
  whether each "interval excludes 0.10" statement in C2 and C4 survives), or downgrade
  C2, C3 and C4 to `exploratory` with `klein claims erratum`. Do not copy my
  unpinned figures from check 5 into findings.

Once both are cleared, re-run `klein verify --numbers --evidence-use` and `klein claims
verify` and send the study back to a fresh referee, or back to this seat with the diff
since this report. The notes above then become `Referee note:` lines in program.md.
