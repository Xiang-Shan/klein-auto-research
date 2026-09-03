Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5[1m]) · fresh context · independent-of-experimenter: no

# Referee report — 11-exact-verifier-construction

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **fresh session** — the
lowest rung of the ladder.

`program.md`'s `## Roster` names the experimenter as "a Claude Code general-purpose
subagent" on model `claude-opus-5`, in a fresh git worktree, this session. This referee
runs on `claude-opus-5[1m]` — the same model, a different context window. A different
context window is not a different model, so the honest answer is
`independent-of-experimenter: no`, and the rung is `fresh session`.

The roster is complete and it pre-declared exactly this outcome before the referee ran
("a fresh Opus context started after synthesis reaches the rung `fresh session`, the
lowest rung of the ladder … neither this file nor the report will claim more"). The rung
is therefore capped by fact, not by a missing record — no NOTE is owed on the roster
itself. It is still the weakest link in this study's evidence chain, and it is listed as
disclosure NOTE 7 so that whoever reads the gallery entry decides knowingly.

## Mechanical verifiers run

All from the worktree root, `KLEIN_OFFLINE=1`, `uv run --locked`.

| Command | Result |
|---|---|
| `klein verify --study … --numbers --evidence-use --no-receipt` | 36 checks, 0 failed; 2 `[WARN]`s (profile vocabulary — the self-audit paragraph; referee gate — not yet recorded, i.e. this report). `evidence_use_rate 1.00 (10/10)`; `findings numbers: all 91 scanned numerals trace to 17 pinned sources` |
| `klein claims verify --study … --numbers` | 7 checks, 0 failed (shape, artifacts, presence, evidence, numbers, append-only, ancestry) |
| `klein predict list --study …` | 6 supported, 1 refuted, 0 inconclusive, **0 open** |
| `klein status --study …` | 10 experiments (keep=0 discard=9 measured=0 crash=1); final holdout n_small 1/1, n_large 1/1; successful confirmation n_small=E0009, n_large=E0010 |
| figure re-render (`make_figures.py --out <tmp>`, `cmp`) | **3/3 byte-identical** (`reach_vs_budget.png`, `verified_object.png`, `checker_ledger.png`) |

Verifier re-run by the referee, in fresh processes, on the pinned artifacts — the check
this study exists to make checkable:

| Artifact | Command | Result |
|---|---|---|
| `models/E0009/solution.json` (sha256 `1ef97ed5…`, = the lock's `solution`) | `KLEIN_ARTIFACT=… python verify.py` | `primary_metric: 22.000000`, `triples_checked: 1540.0`, `claim_excess: 0.0`, exit 0 — **reports 22, as claimed** |
| planted control `parabola_plus_one` (from the DATA-gate-frozen `instances.json`) | same | `REJECTED: points (2, 4), (9, 4) and (0, 4) are collinear`, **exit 2** — identical to the message `data_card.md` row 12 records |
| planted control `row_triple` | same | `REJECTED: points (2, 5), (6, 5) and (9, 5) are collinear`, **exit 2** — identical to `data_card.md` row 1 |

Independent re-derivation (referee's own code, sharing nothing with either the search or
`verify.py`): the E0009 object has **22 points, 0 collinear triples, exactly 2 per row and
2 per column**; the negative control has 11 points and 0 collinear triples; the
`parabola_plus_one` control has **exactly 1 collinear triple out of C(12,3) = 220**, which
is what makes it a real test of an exhaustive checker.

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS | Only C3 and C4 are `confirmed`, both class `procedural-verdict`, whose ceiling is "confirmed when every cited id resolves in the ledger" (claims-protocol class table); every id resolves (`klein claims verify`, and by hand: E0001–E0008, P3, P5, three `verify:` records for C3; E0004, E0009, P1, P6 for C4). C1/C2 stay `exploratory` and §① lines 40–47 explain why; I confirmed the engine agrees — `replicate.confirmation_gaps` returns a gap on **both** tracks ("has no development run to reproduce (confirmation.require names verify)"), so `finalize` labels the study `exploratory` and requires `--allow-exploratory`. C5 (mechanism-interpretation) and C6–C9 (research-discipline) are at their ceilings. Prose never states an exploratory claim as fact |
| 2 | predictions adjudicated and reported | PASS | `klein predict list`: 7/7 adjudicated, 0 open. §②'s table reproduces every ledger verdict and explanation verbatim (`21 >= 22 → refuted`, `54 < 62`, `12 == 12 ± 0`, `22 >= 22`, `55 < 62`). P1's refutation carries two dated `Decision:` lines (`program.md` 184 and 216); `klein verify` belief-revision check passes. P4/P5 are `manual: true` in the *first* hashed contract and were adjudicated with `klein predict adjudicate` (events 43, 44, `source: manual`, evidence ids pinned) |
| 3 | negative evidence reported | PASS | `evidence_use_rate 1.00` — all 10 runs cited, 0 registered sweeps. Zero keeps is stated in the preamble, §①, C9. The two discard clusters ARE the findings (C1, C2); the crash is C3 + C8 |
| 4 | controls | PASS | Both directions, frozen before the checker met them and re-run inside a transaction. Positive: 12 planted objects, `rejected 12 == planted 12` in E0001's printed block (P3). Negative: the Erdős parabola set accepted at exactly 11, its value a theorem known in advance. I re-ran two planted objects (incl. the hardest) and re-derived all three objects independently — see the table above |
| 5 | multiple comparisons | PASS | §② states `n_comparisons = 7` and enumerates the whole family; each prediction binds to exactly one cell. No alpha guard is applied and none is meaningful: the metric is `exactness: exact` with `verifier.tolerance: 0.0` (an integer recomputed from bytes — no sampling distribution), and the guard is pre-registration, which I verified byte-for-byte (check 6). The two `confirmed` claims are procedural, not selected from a noisy family |
| 6 | pre-registration integrity | PASS | Both consult re-records carry reasons on `events.jsonl` (seq 5, 6) and both PRE-DATE the first run (07:17:25 and 07:30:40 vs E0001 at 07:39:59). I extracted all three hashed `study.yaml` blobs and diffed them: re-record 1 adds only `bound:`/`incumbent_external:` on both tracks; re-record 2 changes only a phase id — exactly what the notes claim. **The `predictions:` block is byte-identical (2630 bytes) across all three**, so P1–P7 and their magnitudes were fixed at 07:06:43, before the METHOD gate and before any reference was fetched. Verifier: `verify.py` = `959ba15b…` = `state.fingerprints.verifier`; last content change was the DATA-gate commit `eb17420`, before the METHOD gate; all ten manifests record that same sha256 |
| 7 | numbers traceable (five hand-checked: `small_sealed` 22, `passes_small`/`passes_large` 19014/2190, `best_at_dev`/`best_at_sealed` 152572/1612132, E0008 `reported 21.0`/`verified 20.0`, `triples_largest` 26235) | PASS + NOTE 1 | All five resolve exactly in `results.tsv`, `aux_metrics.tsv`, `runs/E0008/manifest.json` and `runs/E0010/verify.log`. `klein verify --numbers`: 91/91 numerals traced. **No `klein:numbers-ok` markers exist** in `findings.md`, so none can carry a bad reason. The FAIL condition ("any numeral with no home") does not hold — but a spelled-out quantity does contradict its own pinned artifact: see NOTE 1 |
| 8 | references | PASS + NOTES 2, 3 | 10/10 entries `verified: true` with `verified_by` + `verified_at: 2026-09-03`; no UNVERIFIED reference anywhere, and the two `confirmed` claims cite no reference at all. The load-bearing external values (22 and 62) are attributed to `ref:flammenkamp_records` **and** `ref:mathworld_no3` in `study.yaml`, §⑤ and §⑥ — never bare, and deliberately two independent sources. "provably optimal" appears only about `ref:ramanathan2025`, the qualified use the profile permits. Two accuracy notes below |
| 9 | figures | PASS + NOTE 5 | 3/3 re-render byte-identically into a temp dir. Zero-based y-axes on both `reach_vs_budget` panels (`set_ylim(0, bound*1.18)`) and on `checker_ledger`'s bars — the 21-vs-20 overclaim is drawn on a zero-based axis, so it looks as small as it is rather than inflated. `verified_object.png`'s left panel draws exactly the 22 coordinates of the pinned `models/E0009/solution.json` (I checked every point; 2 per row, 2 per column) and the right panel the 11-point frozen control. One presentational note below |
| 10 | vocabulary and scope | PASS | The engine's `[WARN]` names only lines 222/224/225 — the self-audit paragraph, where the banned words are *mentioned*. I checked the profile's §7 quoted list (`proved`, `proof`, `optimal`, `impossible`, `cannot exist`) against every occurrence: "optimal" appears only as "provably optimal" with `ref:ramanathan2025`; impossibility is explicitly refused (line 211: `"did not reach", never "cannot"`); "proven" (not on the mechanical list) is used ~10 times and **always** for the 2n upper bound, never for a result of this study. The estimand: `exactness: exact` with a resolution note replaces a measured floor, which the schema requires and `klein verify` waives on that basis. No materiality is claimed (§⑤ says so outright); modality is `none`, so no in-silico scope is owed |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md)

Ordered by severity. NOTE 1 is the only one that touches a notarized artifact.

1. **"sub-millisecond" is contradicted by the artifact the claim itself pins.** `findings.md`
   line 163 and `claims.lock` C6 both say the checker's exhaustive triple test cost 26235
   cross products on the largest object "and **stayed sub-millisecond**". The pinned
   artifact for that very number — `runs/E0010/verify.log`, alias `verify_log_large`,
   sha256 `1de9ce66…` — reads `triples_checked: 26235.0` beside `wall_seconds: 0.002046`.
   That is 2.0 ms, twice the stated bound. Four of the ten verifier logs exceed a
   millisecond (E0005 0.001528, E0006 0.001915, E0007 0.001969, E0010 0.002046);
   sub-millisecond holds only for the n = 11 objects (k ≤ 22, 0.000097–0.000173).
   The phrase's origin is visible: `data_card.md` line 90 wrote "sub-millisecond at every
   size this study uses" at Gate 1, **before any run existed** — a fair pre-run estimate
   that was never re-checked against the logs once they existed, and was then promoted
   into a post-hoc factual claim. It has propagated to a third file,
   `knowledge/domains/math/README.md` line 16.
   This is not a FAIL: no *numeral* lacks a home, which is check 7's stated FAIL
   condition, and nothing depends on it — the verifier's cost is charged to no guardrail
   (`evaluations`, `search_seconds`) and C6's advice rests on two independent
   implementations agreeing, not on the checker's speed. It is still a quantity in an
   append-only lock that its own pinned artifact refutes, in the one study whose subject
   is that the record must say what the artifact says.
   **To clear:** correct `findings.md` line 163 (e.g. "≈2 ms, and sub-millisecond at
   n = 11") and `knowledge/domains/math/README.md` line 16; file `klein claims erratum`
   against C6 recording the correction, since the lock is append-only; and consider
   annotating `data_card.md`'s row as an at-gate estimate that the logs later revised.
   (I record that a referee applying check 7 by spirit rather than by its enumerated FAIL
   condition could reasonably return FAIL here; I applied it as written.)

2. **§⑥ line 244 overstates how the references were verified.** It says "Ten references,
   all verified against the publisher, arXiv or maintainer page on 2026-09-03". Only four
   were: `flammenkamp_records` (the maintainer page), `mathworld_no3` (MathWorld itself),
   `ramanathan2025` (arXiv), `lourenco2019` (Springer). The other six record
   `verified_by:` as the Wikipedia article or MathWorld's bibliography entry —
   `dudeney1900`, `roth1951`, `guy1968`, `hall1975`, `flammenkamp1992`, `flammenkamp1998`.
   `references.yaml` is scrupulously honest about this; the summary sentence in
   `findings.md` is not. **To clear:** reword line 244 to match the yaml (e.g. "four
   against the publisher/arXiv/maintainer page, six against Wikipedia or MathWorld, each
   named in `verified_by`").

3. **The study's most-repeated "proven" statement is attached to no reference.** The 2n
   upper bound carries every use of "proven maximum"/"proven bound" in `findings.md`,
   `claims.lock`, `study.yaml` and the figures. No entry in `references.yaml` is cited for
   it, and `claims.lock` pins no proof artifact — yet `findings.md` line 225 says "the only
   proof invoked, the pigeonhole bound, is cited as a theorem from the literature". It is
   not cited; the study *proves it itself*, in one line, in §⑤ ("three points in a row are
   collinear, so each of the n rows holds at most 2"), in `research_plan.md`, and frozen
   as `upper_bound_argument` in the DATA-gate-hashed `data/prepared/instances.json`. That
   is a perfectly good warrant — arguably better than a citation, since a reader can check
   it in a sentence — but it is a different warrant from the one line 225 claims, and the
   profile's exemption for "proved" turns on exactly which one is in play. **To clear:**
   either reword line 225 to say the argument is given inline and frozen at the DATA gate,
   or attach a verified reference that states the upper bound (`ref:mathworld_no3` does).

4. **§⑥ scores the same proposition two ways.** Line 274 says the method card's regime
   table was "**wrong on the first and right on the second**" about n = 11 and n = 31;
   line 283 says RQ1's prior — the identical proposition, "reaches 22 at n = 11" — was
   "**half right** … (wrong on the development seed, right on the sealed one)". Both
   cannot be the fairest reading of the same record. The error runs self-critical, so it
   inflates nothing, but the prior scorecard is a durable cross-study artifact.
   **To clear:** score the card the same way as the prior, or say why the card is held to
   the development lane alone.

5. **`reach_vs_budget.png` draws the sealed cell at 1.55× its own budget.** `sealed_x =
   sealed_budget * 1.55` places the star to the right of the 2 000 000 rung on an axis
   labelled "evaluation budget", where the sealed run's budget was identical (and its
   *consumed* evaluations were 1 612 132 — fewer, since the search stops on reaching 2n).
   The code comment gives the reason (a confirmation cell is not another rung; overlapping
   markers would say it was) and the legend and marker distinguish it, so this is
   presentational, not misleading arithmetic. **To clear:** a one-line caption or annotation
   in the tutorial saying the star sits at the same budget and is offset for legibility.

6. **`program.md`'s phase table is stale.** Line 96 still names the first phase `search`;
   consult re-record 2 renamed it to `adaptive-1`, and `study.yaml`, `study_state.json` and
   every E0001–E0008 manifest say `adaptive-1`. Cosmetic — no check reads that table —
   but a stranger diffing the notebook against the manifests will trip on it.

7. **Disclosure: this Gate 3 does not reach model independence.** The referee's model
   (`claude-opus-5[1m]`) is the experimenter's model (`claude-opus-5`); the rung is
   `fresh session`, and `independent-of-experimenter: no` goes onto the gate record and the
   README gallery. `program.md`'s roster predicted this and declined to claim more, which
   is the right behaviour — but if this study is to be an exhibit for "the referee is
   independent by mechanism", a second pass on a different model or tool (the `model` rung
   CLAUDE.md specifies: sonnet experiments, opus referees) is the thing that would earn the
   sentence. This note needs a decision, not a correction.

**Minor observation, not requiring an answer.** P4's statement covers "every development
run that produced a verifiable object"; the seven `verify:` records cover E0001–E0007, and
E0008 — a development run whose artifact the verifier *did* score, at 20 — carries none.
The verdict cannot turn on it (an eighth record could only add a reproduction, and E0008's
ledger row is `NA`), and the adjudication explanation is precise about what it checked, but
a reader may ask. A half-sentence in §② would settle it.

## What I checked adversarially and found sound

Recorded because a referee's silence on these would be indistinguishable from not looking.

- **The checker is never the searcher.** `verify.py` is outside `entrypoint.mutable`,
  imports nothing from `lib/nothree.py`, hashes to the METHOD-gate fingerprint, and is
  byte-unchanged from before E0001 through E0010. Every disposition was decided on its
  number: all ten manifests carry `verifier.sha256 = 959ba15b…`, and `metric.verified`
  drives `primary_metric`.
- **E0008's deliberate overclaim is recorded as a refusal, not a result.** `disposition:
  crash`, `decision_reason: verifier_disagreement…`, `metric {reported 21.0, verified
  20.0}`, `primary_metric: null`, `metrics: {}`, `results.tsv` row `NA`. The inflated 21
  appears in no table. I read the engine: `_run_declared_verifier` raises before
  `record_run_adjudications` is reached, so the findings' stated reason for P5 being
  `manual` — a disagreeing cell can never reach `--tests` — is true of the code, not just
  of this run (whose `predictions_requested` is `[]`).
- **Zero keeps by arithmetic, acknowledged in advance.** Both `headroom ack` events
  (07:36:14, 07:36:25) pre-date E0001 (07:39:59), record `h = (22-22)/1 = 0` and
  `(62-62)/1 = 0`, and give run-anyway reasons that redefine success as *attaining* the
  known maximum. Every run is `discard`; E0009 carries `matched_external: true`. No search
  limit is anywhere read as impossibility — §⑤ says the opposite explicitly, and cites the
  study's own counterexample.
- **"A difference, not a rate."** The headline is stated as a difference in §①(C4), §③,
  C5, §⑦ and the knowledge entry, and the study states outright that it cannot estimate a
  rate. The sealed run is used to *undercut* the development lane's over-reading, never to
  vouch for it — the honest direction.
- **The dev/sealed pair really does differ only in the seed.** I diffed the two candidate
  commits: `lib/` and `verify.py` identical; `search.py` differs by one string,
  `CELL = "n_small@2M"` → `"n_small@2M-sealed"`, a label that feeds nothing (the seed comes
  from `instances["seed_blocks"][block]`, chosen by `KLEIN_EVALUATION_KIND`). No literal
  seed exists in `search.py`, `verify.py` or `lib/` — war story 8's failure mode is absent.
- **Both sealed rehearsals spent nothing.** Each `sealed_dryrun` event precedes its real
  run and each log prints `sealed_dryrun: 1`, `search_seed: 20260903.0`,
  `sealed_block: 0.0` — the rehearsal used the development block, so the one sealed access
  per track survived to be spent on the registered cell.
- **The mid-study engine commits do not flatter the study.** `6d27d3c` moves
  `_seed_external_incumbent` from `workflow.py` to `decision.py` with a byte-identical
  body so preflight/verify/`headroom ack` resolve the same incumbent `run-one` already
  enforced; `ad87c0f` makes preflight audit the declared entrypoint. Both make the closed
  door *visible*, not passable; neither touches disposition arithmetic. Both are disclosed
  in `program.md`.
- **The six typed citations in `knowledge/domains/math/README.md` each point at a claim
  that says what the entry says** (C6; C7+C8; C5+C4; C9) — subject to NOTE 1, which the
  first entry repeats.

## Clearing conditions (FAIL only)

None — no FAIL condition holds. The gate may be recorded. NOTES 1–6 want a dated
`Referee note:` answer in `program.md` before `klein finalize`; NOTE 1 additionally wants a
`klein claims erratum` on C6, because the lock is append-only and the sentence is in it.
NOTE 7 wants a decision, not a correction.

The study's plan to finalize with `--allow-exploratory` is honest and I verified it
mechanically: `confirmation.require: [verify]` resolves, on a frontier track, to the final
incumbent's re-verification record; with zero keeps there is no incumbent, so
`replicate.confirmation_gaps` reports a gap on both tracks and the label is `exploratory`.
`findings.md` states this and why, and contains the word `exploratory` that `finalize`
requires.
