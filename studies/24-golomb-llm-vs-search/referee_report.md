Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 24-golomb-llm-vs-search

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. There is no `generation/manifest.yaml`, so `Generation:` is `n/a`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**.
`program.md` `## Roster` lists the experimenter as the `klein-experimenter` subagent (Sonnet
tier), Claude Code. This referee runs on claude-opus-5-5 (Opus tier) in a fresh subagent
context that did not see the loop, so the rung is "different model". It is not "different
tool": both run in Claude Code.

Against the **synthesist**, the Roster's `klein-synthesist` (Opus tier) is on the same model
tier as this referee, so independence from the author of `findings.md` reaches only the
fresh-session rung. See note 8.

## Mechanical verifiers run

All commands were run from the worktree root with `KLEIN_OFFLINE=1` and `uv run --no-sync`.
No network call was made.

| Command | Result |
|---|---|
| `klein verify --study … --numbers --evidence-use --no-receipt` | 34 checks, 0 failed. Two inline `[WARN]`s: the referee gate is not yet recorded, which is expected, and the contract-driven split. The split warning is inherent to modality `none` with `split.kind: none`: the study has no rows, the lanes are order sets pinned in `instance.json`, and they are guarded by the verifier's `ORACLE` and `KLEIN_EVALUATION_KIND` (data card NOTE 6, split policy). It is accepted on that basis. evidence_use_rate 1.00 (6/6). Findings numbers: 221 numerals trace to 21 pinned sources. |
| `klein claims verify --study …` | 7 checks, 0 failed (19 artifacts hash as pinned; append-only holds across history). |
| `klein predict list --study …` | 2 supported (P1, P4), 3 refuted (P2, P3, P5), 0 inconclusive, 0 open. |
| `klein status --study …` | 6 experiments: measured 4, crash 2. Sealed accesses: search = E0005, llm = E0006. |
| figure re-render | Not applicable. `figures/` and `report/` are empty, and `findings.md` cites no figure. |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS | There are three `confirmed` claims. **C1** (search, development 0/12) cites E0001, rep:E0001@20261103T090037Z (difference 0, tolerance 0) and the sealed E0005. **C5** (sealed 0/6 per arm) cites E0005 and E0006, both verifier-decided (`metric.reported == metric.verified`), plus each track's replication. **C6** is a procedural verdict whose ids all resolve. Each track holds both kinds in `confirmation.require: [sealed, replicate]`, and `convergent evidence` passes. No run is detached or attested. Every hypothesis is labelled: C7 and C8 are `mechanism-interpretation`/exploratory and open with "Untested hypothesis", and §③ opens with a blanket hypothesis label. C2, C3, C4 and C9 to C16 are exploratory. The C5 statement that no LLM candidate was a valid ruler rests in findings on the searcher's self-reported `valid_rulers`. **I re-checked it independently** against the pinned shard `calls/E0006-000.jsonl.gz`: 1200 replies hold 11,395 extractable 12- or 13-element integer lists, and 0 are Golomb rulers. Notes 1, 2 and 5 apply. |
| 2 | predictions adjudicated and reported | PASS | All five predictions are adjudicated by the notary (events seq 7, 19, 20, 27, 31). The §② verdicts and observed values equal `klein predict list`. The refuted P2, P3 and P5 each have dated `Decision:` lines (program.md lines 226, 256, 267–269), and the `belief revision` check passes. |
| 3 | negative evidence reported | PASS | evidence_use_rate is 1.00. The crashes E0002 and E0003 are in findings' Crash audit with their classes (HTTP 429; a bare ConnectionResetError). The fact that the crashed cell was rerun is stated ("the crashed direction *was* retried"), and so is the **shared ledger**: E0004 answered 1136 of 2400 requests from the E0002/E0003 shards (`manifest.usage.calls_cached` 1136, aux `calls_cached`), with the salted re-query named as the only independent draw (Crash audit, C12). The measured nulls E0005 and E0006 are findings (C5). |
| 4 | controls | PASS | Verifier-level controls exist and are recorded in `data_card.md`: rejection of planted invalid, forged, wrong-lane and tampered artifacts, and acceptance of hand-transcribed tabulated rulers (12/12 development, 6/6 sealed). `sweeps/verifier_checks.py` re-runs nine refusals. The missing pipeline controls are **declared with reasons** in findings ①: contamination, no-feedback LLM, compute-matched classical arm, second snapshot, and empirical random null. The control artifacts are unpinned, which is disclosed. Note 4 applies. |
| 5 | multiple comparisons | PASS | n_comparisons is stated for each of five families (findings ① table; `art:synth_summary` keys `n_comparisons_*`). The arm-contrast family uses Bonferroni 0.025, and the development contrast (pair-level p 0.03125, order-level p 0.5) stays exploratory (C3). No `confirmed` claim is drawn from a contrast family: C1 and C5 are per-arm counts. |
| 6 | pre-registration integrity | PASS | There are three consult re-records, each with a reason, and all precede the runs they enable. (a) 05:xx, before any run: model pinned to the snapshot `qwen-flash-2025-07-28`, budget comment clarified. (b) After E0002: `max_workers` 6→2, development `max_experiments` 2→3, `budget_seconds` 7200→10800. (c) After E0003: `max_experiments` 3→4. I hashed the `predictions:` block in every committed version of `study.yaml` (48ad270, 5534a64, 18d08e5, fa27b8c): it is byte-identical in all four. The RQ priors and method-card priors predate E0001: the METHOD gate is at 06:19:06 and E0001 starts at 06:19:36. Every adjudication post-dates its registration. The transport (library) fixes between E0002 and E0004 are disclosed as framework changes, and the mutable `search.py` was not changed after aadbeda (every `run_started` shows `empty_diff: true`). |
| 7 | numbers traceable | PASS | `--numbers` passes, and there are no `klein:numbers-ok` markers in findings or the lock. **Hand-checked:** (i) C1 gap means 5.667 = (7+4+6)/3 and 35.333 = (39+33+34)/3 from `tables/synthesis_pairs.tsv` E0001 rows. (ii) C5 "at least 48" = min sealed search gap (E0005 n=12 trial 1: 133−85). (iii) C5 "265 of 1200" = 54+43+36+40+46+46 from E0006 rows, = aux `unparsed_replies`. (iv) C12 0.4733 = 1136/2400 (`runs/E0004/manifest.json` usage). (v) C10 10234 = 3292.082/0.32168 (aux wall_seconds E0004/E0001), and 6507285 = 585586+513333+1388003+1523219 (manifests E0002/3/4/6) + 2497144 (rep:E0004 `searcher_block` tokens). (vi) C3 p 0.03125 = 2·0.5⁶ and 0.5 = 2·0.5²; the consult Brier 0.170625 = (0.25+0.25+0.0225+0.16)/4. All agree. |
| 8 | references | PASS | All 21 entries in `references.yaml` are `verified: true`. Every `ref:` cited in findings (12 keys) resolves there, and the method card's `refs_verified: true` is consistent. No unverified reference supports a confirmed claim. |
| 9 | figures | PASS (vacuous) | No figure is committed or cited, so there is nothing to re-render. This verdict does not cover TUTORIAL-stage figures (note 9). |
| 10 | vocabulary and scope | PASS | Math profile §7: "proved"/"proof" are absent. "Optimal/optimality" always carries the OEIS A003022 citation and the statement that optimality rests on others' exhaustive searches. "Impossibility" appears only negated (§⑤). "Matched" is the verb throughout, and "best" is "best verified" at the stated 2000-evaluation budget. The floor estimand is named: `exactness: exact`, resolution 1, floor waived by declaration, and verify reports this. Resolution is never sold as materiality. It is not a simulation study. |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md)

1. **C7's "unique tabulated optimum" is mathematically wrong at n = 11, and that weakens the
   argument made on it.** C7 and §③ say "identity with a unique tabulated optimum cannot
   separate recall from search" and "Identity is uninformative when the optimum is unique".
   - Order 11 has two optimal rulers up to reflection: `0 1 4 13 28 33 47 54 64 70 72` and
     `0 1 9 19 24 31 52 56 58 69 72`. I checked both are Golomb. `method_card.md` line 82
     says so, and findings §⑥ itself says "11 marks with its two optima".
   - Even at n = 8 the optimum is unique only up to mirror image.
   - Six of six matched pairs returned the table's *printed* row in its *printed* orientation,
     never the mirror image and never the other 11-mark optimum. That is weak but non-zero
     evidence bearing on C7, so "uninformative" overstates the case.
   - C7 is exploratory, so this is not a strength violation. But the locked claim text holds
     a false statement. Answer it with an erratum on C7 (`klein claims`, append-only),
     re-scoping it to "unique up to reflection at n = 8; one of two optima at n = 11, and in
     every match the printed orientation".
2. **C5 and the §① headline rest "none of its candidates a valid Golomb ruler" on the
   searcher's self-report.** The verifier checks best and first batch only; `valid_rulers` is
   printed by `search.py`, which is the mutable surface (data card WARN 1).
   - The statement holds: my independent pass over `calls/E0006-000.jsonl.gz` found 0 valid
     12- or 13-mark rulers.
   - Findings should name the pinned ledger shard as the home of that sentence. Better, have
     `tables/synthesis_derive.py` recompute it from the shard, as it already does for first
     batches.
3. **C2's re-query detail is searcher-reported, not verified.** The replica's "valid rulers
   788" and "unparsed 531" come from the record's `searcher_block`. The `replicate_block` (the
   verifier) does not carry them. A clause saying so would keep the numbers honest about their
   source.
4. **The control labels are swapped between the data card and findings.** The data card calls
   rejection of invalid objects the "Positive control" and acceptance of valid objects the
   "Negative control". Findings ① uses the opposite, conventional, labelling. Pick one, and
   say in findings that the controls test the *verifier*, not either searcher.
5. **C1 and C5 are confirmed on development replications.** Findings already discloses that
   rep:E0001 and rep:E0004 re-ran development orders, not sealed ones, so they confirm the
   instrument rather than the sealed counts. The mechanism accepts this at track level. A
   `klein replicate E0005 --verify-only` (or E0006) record would bind the sealed artifacts
   themselves to a second verifier pass. This is optional, but the orchestrator should state
   the choice.
6. **§⑥ "The results sit where `ref:carlini2023` would place a flash-tier model".** Carlini
   et al. make no prediction about a "flash-tier" model. This sentence is a memorization
   reading in literature prose, outside C7's hypothesis label. Reword it as "consistent with
   the memorization-scales-with-capacity account of `ref:carlini2023`; untested here (C7)".
7. **The synthesist's correction to program.md is verified correct.** program.md line 222
   says "Every n=8 first batch opens with the same prefix 0,1,4,9,15,22,32". In
   `tables/solution_E0004.json`, the first rulers of the n = 8 first batches are:
   - trial 0: `0 1 4 9 15 22 32 34`;
   - trial 1: `0 1 3 7 12 20 29 38`;
   - trial 2: `0 1 4 9 15 22 32 38`.

   So the prefix opens trials 0 and 2 only, exactly as findings §③ states. Leave program.md's
   log line as written, since the notebook is append-only. Answer it with a dated
   `Referee note:` that points at the findings correction.
8. **Independence from the synthesist reaches only the fresh-session rung.** The synthesist
   and this referee are both Opus tier in Claude Code. The `independent-of-experimenter: yes`
   claim concerns the experimenter only, as the protocol defines it. Record the
   synthesist-referee rung in the Roster's referee row.
9. **No figures and no tutorial yet.** This verdict does not cover the TUTORIAL artifact or
   its figures.
10. **Minor.**
    - The C1 evidence cell in the findings ① table omits `art:sol_E0001`, which the lock cites.
    - program.md's "block keys outside tolerance: evaluations, restarts" for rep:E0001 means
      those keys are *absent* from the verifier block. In the `searcher_block` they are equal
      (24000; 94), not different.
    - Data card NOTE 11 expected about 7,200 study-wide live calls. The recorded total is 6000.
      Findings uses the recorded value, correctly, but does not say why it differs from the
      card's estimate.

## Clearing conditions (FAIL only)

None. No FAIL condition holds.
