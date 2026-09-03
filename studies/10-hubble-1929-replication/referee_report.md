Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: Opus 5 / claude-opus-5[1m]) · fresh context · independent-of-experimenter: no

# Referee report — 10-hubble-1929-replication (round 2)

> Gate 3 (REFEREE). Round 1 read `findings.md` first and `program.md` last, in a fresh
> context. Round 2 re-runs every verifier from scratch at HEAD `1d51bbf` and re-reads
> `findings.md` in full. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

**One paragraph for the orchestrator.** The FAIL is cleared, and cleared the right way:
the false ratio was not softened, it was removed and replaced by a passage that rests
only on already-pinned values and then *teaches the mistake it was* ("comparing a full
modern interval with a nineteenth-century half-width at a different confidence level").
The experimenter went further than I asked — it swept the whole document for spelled
multiples and found two more escapees plus one I had noticed and not raised (the "60 %"
that traced only by an accidental match to the unrelated `hubble_pe_9group = 60`). All
five notes are answered with dated `Referee note:` lines; two of them are answered by
**refusing** what I proposed, with reasons I accept and endorse below. Every hashed gate
artifact, `claims.lock`, every table, figure, manifest, sweep, `results.tsv`,
`aux_metrics.tsv`, `events.jsonl` and `study_state.json` is byte-identical to round 1 —
the repair touched only `findings.md`, `program.md` and the receipt. One new item, and
it was created by the fix to note N4: the sentence that states the multiplicity posture
contains the word "significant" while asserting that the word "appears nowhere in this
document", which is self-falsifying and leaves a standing `[WARN] profile vocabulary` on
every future `klein verify` of this exhibit. That is a NOTE (N6), not a FAIL — the
profile bans "significant" *without the test and its family size*, and the sentence sits
inside the paragraph that states the family size. Verdict: **PASS-WITH-NOTES**.

## Round 1 — what failed and how it cleared

Round 1 returned **FAIL on check 7 (numbers traceable)**. `findings.md` line 25, in the
study-summary paragraph, asserted that the 24 objects "support an interval **nearly six
times wider** than Hubble's quoted one". No pinned artifact held that ratio; the pinned
ones gave 2.8706 (`ci_width` 287.056180 against `hubble_pe_24` ±50, width-over-width or
half-over-half), and the only arithmetic reaching six divided the study's *full* width
by Hubble's *half*-width. It also contradicted the study's own §③.1, which reports that
his ±50 reproduces (`probable_error` 50.747428): converted to a common convention his
stated uncertainty is 290.58 against the measured 287.06, a ratio of 0.99. The
mechanized scan had passed only because "six" is spelled as a word. Five notes
accompanied it (N1 roster, N2 reference count, N3 the `claims.lock` history reset, N4
multiplicity posture, N5 a self-contradicting sentence in `research_plan.md`). The gate
was not recorded.

**Cleared.** The summary now reads on pinned values only (`ci_width` 287.056180,
`hubble_pe_24` 50, `inverse_forward_ratio` 1.603771, `ci_level` 95, `n_table1` 24) and
defers explicitly to §③.1, which gained the reconciliation in one line — **"his constant
does not reproduce and his uncertainty does"** — plus a paragraph naming the exact
comparison error for the next reader. No ratio was pinned, C3's frozen `claim` sentence
was not touched, and no artifact hash moved. Two further spelled multiples were removed
on the experimenter's own initiative ("saved twice" in C14; "about a factor of seven" in
§⑥'s `ref:sandage1958` entry, dropped with the reason that no cell measured it so it has
no home), and the accidental "60 %" match was replaced by the pinned factor.

## Independence

Rung reached (person > tool > model > backend > fresh session): **fresh session**.

N1 is closed: `program.md` now opens with a `## Roster` naming lead, experimenter,
DATA-gate auditor and referee with model and context. The rung is unchanged and the
roster says so itself — experimenter and referee are both Opus-family agents, so
`independent-of-experimenter` stays **no** and the "model" rung was never available. My
line now agrees with an explicit roster rather than with an absence, which is the point
of the note. The roster also volunteers a weakness I had not raised: the clean-room
leakage audit was **self-performed** by the same agent rather than run in a separate
context — `data-gate-protocol.md` §5 permits this but does not prefer it, and rows 3–4
were mechanized by `python -m kleinlib.leakage` in both modes, which is what makes the
weaker option tolerable. Disclosing that unprompted is the behaviour this seat exists to
reward.

## Mechanical verifiers run (round 2, at HEAD `1d51bbf`)

All from the worktree `/Users/xiang/Claude/Auto_research/klein-auto-research/.claude/worktrees/agent-a8f2d47a81f401ad0`, `KLEIN_OFFLINE=1`, `uv run --locked`.

| Command | Result |
|---|---|
| `klein verify --study … --numbers --evidence-use --no-receipt` | **39 checks, 0 failed** (round 1: 38 — the extra row is the conditional `profile vocabulary` check, which now fires as a `[WARN]`; see N6). `evidence use: 1.00 (15/15)`; `findings numbers: all 126 scanned numerals trace to 34 pinned source(s)` |
| `klein claims verify --study … --numbers` | **7 checks, 0 failed** — the lock is byte-identical to round 1 |
| `klein predict list --study …` | **7 supported, 1 refuted, 2 inconclusive, 0 open** (unchanged) |
| `klein status --study …` | 13 measured, 0 crash; holdout `estimate=1/1, reproduction=1/1, simulate=1/1`; 0 refutations without a decision; 0 single-source confirmed claims |
| figure re-render (`make_figures.py` → temp dir, `cmp`) | **all four byte-identical**, re-run by me at HEAD; "all cross-checks passed" |
| `kleinlib.replicate.confirmation_gaps` (read-only) | **`{}`** |

### Scope of the round-2 change, verified independently

`git diff 6149ee8..1d51bbf --stat` touches four files: `findings.md`, `program.md`,
`referee_report.md` (my round-1 report, committed by the orchestrator) and
`verify_receipt.json`. I then checked the blobs directly:

- **UNCHANGED between rounds:** `claims.lock`, `study.yaml`, `data_card.md`,
  `method_card.md`, `research_plan.md`, `results.tsv`, `aux_metrics.tsv`,
  `events.jsonl`, `study_state.json`, `playbook.md`; and **0 files** changed under
  `tables/`, `figures/`, `runs/`, `sweeps/`.
- **The four hash-pinned gate artifacts still MATCH** their recorded digests in
  `study_state.json:artifact_hashes` (`study.yaml` 6378b730…, `data_card.md`
  ca3a6ec9…, `method_card.md` 94434f3b…, `research_plan.md` 5d4a75a2…). `program.md`
  is deliberately *not* in that map — it is the living notebook — which is exactly why
  answering N5 there instead of editing `research_plan.md` was the correct trade.
- **C3's frozen `claim` sentence is untouched**, as are its `class`, `strength` and
  `numbers[]`. `events.jsonl` and `study_state.json` are unchanged, so no gate was
  recorded on the FAIL.

## The ten checks (round 2)

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** | Lock byte-identical to round 1; `confirmation_gaps` = `{}`; all 3 tracks spent 1/1 seals (E0011/E0012/E0013, `evaluation_kind: final_test`); 9/9 confirmed claims cite ≥2 evidence kinds; C4 carries `"scope": "in-silico"` in the lock and the scope sentence in §① and §⑤; C10–C17 remain `exploratory` and are labelled inline. |
| 2 | predictions adjudicated and reported | **PASS** | `predict list` = §② line for line; 10 `prediction_adjudicated` events; P9's dated `Decision:` at `program.md:148` still present and still the only refutation; P2/P3 inconclusive strictly through their registered `inconclusive_if` keys. Unchanged by round 2 except the added posture paragraph. |
| 3 | negative evidence reported | **PASS** | `evidence_use_rate 1.00` (15/15); zero crashes stated in §③.5; the 15 failed `klein replicate` attempts still retained (25 records, 10 `reproduced: true` at `difference 0.0`) and reported at `program.md:527–566`. |
| 4 | controls | **PASS** | Positive: E0001 identity anchor, max deviation 0.000000, hard-STOP on mismatch. Negative: the 2000-permutation control, **0 of 2000** reaching the real K (`data_card.md` leakage row 4). |
| 5 | multiple comparisons | **PASS** (N4 closed) | §② now states the posture explicitly: all ten predictions registered before evidence and all ten reported (no selected family); no verdict rests on a p-value; the reproduction comparisons are deterministic arithmetic against contract tolerances and have no null distribution; every stochastic quantity (E0006–E0008 intervals, E0009/E0010/E0013 coverages) is a single pre-registered estimate, so `n_comparisons` is 1 per family and no `metrology:` block is declared. I verified the cited `kleinlib.metrology.family_maxt` exists (`kleinlib/metrology.py:324`) — the citation is real, not decorative. The P6 carve-out is named and carried as C15. |
| 6 | pre-registration integrity | **PASS** | Unchanged and re-verified: the `predictions:`, `sealed_lock:` and `simulation:` blocks hash identically at all four consult records and at HEAD (`539dfdde06c6…`, `39205ecaa917…`, `842b0e8c0bdd…`). Round 2 touched no hashed artifact and recorded no gate. |
| 7 | numbers traceable | **PASS** *(was FAIL)* | `findings numbers: all 126 scanned numerals trace to 34 pinned sources`; still **no `klein:numbers-ok` markers anywhere** — nothing is exempted by hand. I re-read `findings.md` in full and swept it myself for the failure mode the scanner cannot see: every `factor of` now carries a pinned numeral (1.603771 `inverse_forward_ratio`; 6.056247 `rescale_factor`; 6.487978 `estimate_over_modern`), and **no** `twice`, `thrice`, `double`, `triple`, `fold` or "N times" survives. The two remaining word-quantities are sound: "half the paper's own printed precision" is the *definition* of the pinned `p9_tolerance` 0.06 against a printed 0.1 and is frozen inside C7's lock sentence; "half-width" in §③.1 is a noun in the explanation of the cleared error. Every spelled cardinal that remains is a count naming its source (13 cells, 5 targets, 24 objects, 5 floor blocks, 9 groups, 4 Virgo rows, 2 defects, 2 references). |
| 8 | references | **PASS** (N2 closed) | §⑥ now *names* the two rather than counting them — `ref:hubble1929` (C2) and `ref:sandage1958` (C5) — which matches `claims.lock` exactly and, as the answer notes, cannot drift again. All 8 entries remain `verified: true` with locators; every `ref:` in findings resolves; nothing unverified stands behind a confirmed claim. |
| 9 | figures | **PASS** | I re-rendered all four at HEAD into a temp dir: byte-identical, and the script's own cross-checks passed. Unchanged bytes since round 1. Four-point critique as before: the comparison axes of `bootstrap_k.png` and `velocity_distance.png` are zero-based, `trajectory.png` is categorical, and `coverage.png`'s truncation does not inflate a within-noise delta (plotted deltas 0.027 and 0.014 against the measured floor 0.0060663, with both anchors in frame). |
| 10 | vocabulary and scope | **PASS** (note N6) | `findings.md` and `claims.lock` contain **no** "blind", "proved", "material", "actionable", "better", "improves" or "beats". The brief's banned phrases appear only inside their own refutations. Floor estimands named; C4's in-silico scope carried; nothing priced. The single "significant" is a self-referential meta-mention inside the paragraph that supplies exactly what the profile's ban demands (the test and its family size) — qualified, therefore not a FAIL — but see N6. |

## Note — needs a dated `Referee note:` answer in `program.md` before `klein finalize`

**N6 — `findings.md:98` is self-falsifying and leaves a standing engine WARN.** The new
multiplicity paragraph says:

> "…no verdict rests on a p-value — the word **"significant"** appears nowhere in this
> document."

The word appears in that sentence, so the sentence is false in the document that
contains it. It also newly trips the engine's own check —
`[WARN] profile vocabulary: findings.md uses words the 'generic' profile bans: line 98
… (the referee checks the same list)` — which will print on every `klein verify` of this
exhibit from now on and will invite each future reader to re-litigate it. This is the
same construction I flagged as N5 in `research_plan.md`, now reproduced in the study's
most-read artifact. Not a FAIL: the profile bans «"significant" without the test and its
family size», and this sentence sits inside the paragraph that states both. **Clearing
is one clause** — e.g. "…and no verdict rests on a p-value; this study performs no
significance test at all." — which keeps the meaning, drops the word, and returns
`klein verify` to a clean 38/38.

## Answers I accept without further action

- **N3 (the `claims.lock` history reset) — durable repair done, and the knowledge
  promotion correctly refused.** The annotated tag `discarded/10-claims-lock-draft`
  exists at exactly `4dc901160401a6afe5c88d68f3d7538d0bf8a15c`, the discarded tip I
  identified in round 1; its message points back to the SYNTHESIZE disclosure, and the
  disclosure now names the tag and gives the `git show` command a stranger runs. I read
  the discarded lock through the tag and it still shows the defect exactly as disclosed
  (`bad_rescale_gap` → `art: aux`, plus the orphan `bad_rescale_gap_home` →
  `art: dryrun_rescale`). An annotated tag survives a clone and `git gc`, so the note is
  closed. **On the `knowledge/` promotion the experimenter declined, and it was right
  to.** My suggested citation `#C13` is about derived columns, not authoring verbs, and
  no claim in this study supports the lesson; writing one now would be manufacturing a
  claim to fit a citation, which is worse than not promoting. The lesson is about the
  ENGINE (its evidence is commit `a1f30b2` and its regression test, not any `E####`), so
  it is the lead's to promote. **Open handoff to the lead, not a note for the
  orchestrator.**
- **N5 — answered by recording rather than editing, which is the better trade.**
  `research_plan.md` is hashed by the CONSULT gate; editing it would invalidate the
  recorded digest and force a fourth consult re-record *after evidence exists*. I
  verified the digest still matches. Recording the corrected reading in `program.md`
  costs a prose infelicity in a plan document and preserves the gate — the right call,
  and better than the one my note implied.

## Observations (no action required)

- **O1 — the two long-standing `[WARN]`s inside OK rows remain correct and expected.**
  "no realized fingerprints are registered" follows from `split.kind: none` (the
  partition is the paper's two tables, not a draw; both block digests are published on
  `data_card.md` for hand-recomputation), and "scaffold stubs remain" is what a
  registered track's mandatory surface-restore leaves behind after every cell — what ran
  lives in the candidate commits. Neither should be re-litigated.
- **O2 — "a nineteenth-century half-width" (§③.1)** describes the era of the *probable
  error convention*, not of the 1929 paper. Accurate on the intended reading, momentarily
  ambiguous on the other.
- **O3** — `figures/velocity_distance.png`'s legend prints 423.94 / 454.16 / −40.78, the
  rounded forms `scouting_ledger.md` §Retirements says "nothing cites". They are display
  roundings of the pinned full-precision table, not citations of the brief's scouted
  values; no law is broken.
- **O4** — the study's honesty about foreseeability (four of ten predictions, disclosed
  before any run and repeated in §②, with C15 on the floor that partly spent P6) remains
  the strongest thing in it, and the round-2 additions did not dilute it. The
  experimenter's own sweep catching the accidental `hubble_pe_9group = 60` match — a
  defect I had noticed and not raised — is the second strongest.

## Recording

No FAIL condition holds. The orchestrator may record the gate:

```bash
uv run --locked klein gate record referee --study studies/10-hubble-1929-replication \
    --acknowledged-by <actor>
```

It will store `PASS-WITH-NOTES` and `independent-of-experimenter: no`. N6 needs its
dated `Referee note:` line in `program.md` before `klein finalize`; the `knowledge/`
promotion is an open handoff to the lead.
