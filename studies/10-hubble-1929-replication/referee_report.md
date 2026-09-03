Verdict: FAIL
Referee: klein-referee (Claude Code subagent, model: Opus 5 / claude-opus-5[1m]) · fresh context · independent-of-experimenter: no

# Referee report — 10-hubble-1929-replication

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

**One paragraph for the orchestrator.** This is, mechanically, one of the cleanest
studies in the repository: 38/38 engine checks pass, the claims law passes all seven,
all ten predictions are closed by the notary, all four figures re-render byte-identically,
the three seals are lawful and each was rehearsed first, the contract's `predictions:`,
`sealed_lock:` and `simulation:` blocks are byte-identical across all four consult
records, and 10 of 10 development cells reproduce with difference exactly 0. It fails
Gate 3 on one sentence. `findings.md` line 25 — in the study-summary paragraph, the
most-read sentence in the document — asserts that the 24 objects "support an interval
nearly six times wider than Hubble's quoted one". No pinned artifact holds that ratio;
the pinned values give **2.87**, not six; and the study's own §③ surprise 1 says the
opposite (that its uncertainty *reproduces* Hubble's). That is check 7's FAIL condition
— a numeral with no home — and the numbers law exists for exactly this. The fix is one
paragraph in a file no artifact hash depends on; nothing in `claims.lock`, the ledger or
the figures needs to move.

## Independence

Rung reached (person > tool > model > backend > fresh session): **fresh session (capped)**.

`program.md` carries **no `## Roster` table**, so nothing on the record names the model,
tool or session that ran the loop. Per the protocol a missing roster caps the achievable
rung at "fresh session" and is a NOTE, never a FAIL. I therefore claim only what the
record supports: a fresh context, and `independent-of-experimenter: no`.

Experimenter: **not on the record.** `study_state.json` and every gate event name the
actor only as `lead-agent` (`acknowledged_by`, with `program.md`'s decision of
2026-09-03 that "the gate acknowledgements for this exhibit study are DELEGATED to the
driving agent by the lead"); the run manifests carry no actor field. The only model named
anywhere in the study is `references.yaml`'s `verified_by: "driving agent (Claude Fable
5.1)"`, which documents who verified citations, not who ran the loop. My commissioning
brief states the experimenter was a separate agent of the Opus family in another context;
that is consistent with `no`, and I have not claimed the "model" rung.

## Mechanical verifiers run

All from the worktree `/Users/xiang/Claude/Auto_research/klein-auto-research/.claude/worktrees/agent-a8f2d47a81f401ad0`, `KLEIN_OFFLINE=1`, `uv run --locked`.

| Command | Result |
|---|---|
| `klein verify --study studies/10-hubble-1929-replication --numbers --evidence-use --no-receipt` | **38 checks, 0 failed**; `evidence use: 1.00 (15/15 cited)`; `findings numbers: all 117 scanned numerals trace to 34 pinned source(s)`; two advisory `[WARN]`s inside OK rows (see Observation O1) |
| `klein claims verify --study … --numbers` | **7 checks, 0 failed** — shape, 19 artifacts hash as recorded, presence, evidence, numbers, append-only, ancestry |
| `klein predict list --study …` | **7 supported, 1 refuted, 2 inconclusive, 0 open** |
| `klein status --study …` | 13 experiments (measured=13, crash=0); final holdout `estimate=1/1, reproduction=1/1, simulate=1/1`; 0 refutations without a decision; 0 single-source confirmed claims |
| figure re-render (`figures/make_figures.py --out <tmp>`, then `cmp`) | **all four byte-identical** — `velocity_distance.png`, `bootstrap_k.png`, `coverage.png`, `trajectory.png`; the script's own in-run cross-checks printed "all cross-checks passed" |
| `kleinlib.replicate.confirmation_gaps` (read-only) | **`{}`** — no track is missing a required `replicate` record for the cells its `confirmed` claims cite |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** | All 3 tracks declare `confirmation.require: [sealed, replicate]` (byte-identical since the first consult record). Each track spent exactly one seal (E0011/E0012/E0013, `evaluation_kind: final_test`); `confirmation_gaps` returns `{}`; all 9 `confirmed` claims cite ≥2 evidence kinds. C4 is `known-dgp-teaching` with `"scope": "in-silico"` in the lock and the scope sentence quoted in `findings.md` §① and again in §⑤. C10, C11 (mechanism-interpretation) and C12–C17 (research-discipline) are `exploratory` and are labelled *(…, exploratory)* inline wherever the prose states them. |
| 2 | predictions adjudicated and reported | **PASS** | `klein predict list` and `findings.md` §② agree line for line on all ten verdicts and observed values. Every verdict was produced by `run-one --tests P#` (10 `prediction_adjudicated` events, seq 8–65), never by prose. P9 refuted with a dated decision at `program.md:148` ("2026-09-03 — Decision: P9 is REFUTED (E0003), and the sealed registration STANDS"), which `klein verify`'s belief-revision check confirms. P2/P3 went inconclusive strictly through their registered `inconclusive_if` keys — `coords_available 0 < 24`, `groups_reconstructed 0 < 9` — read off `tables/solar_motion_inputs.tsv` and `tables/nine_group_inputs.tsv`, which record three sources checked, 0 coordinate columns, 0 offline catalogue files, 0 groups reconstructible. No grouping and no coordinate was invented. |
| 3 | negative evidence reported | **PASS** | `evidence_use_rate 1.00` — all 13 measured cells + `sweep:coverage_floor` + `sweep:mc_resolution` are cited. Zero crashes, zero discards, and §③.5 says so in one sentence rather than passing over it. The four unreproduced targets are written up as findings (C1, C2, C7), not buried. The 15 **failed** `klein replicate` attempts are all retained on disk (25 records across `runs/E0001–E0010/replications/`, 10 `reproduced: true` with `difference 0.0`, 15 `reproduced: false`) and reported in full at `program.md:527–566`, with the three environmental causes and the macOS `TMPDIR` fix; I confirmed the failure mode from `runs/E0010/replications/20260903T064419Z.log` (`ImportError … code signature … library load disallowed by system policy`). None was deleted. |
| 4 | controls | **PASS** | Positive control: E0001, the identity anchor — Hubble's published sums 21.873 Mpc / 8955 km/s and both row counts, recomputed with a hard-STOP on mismatch, max deviation 0.000000 (`tables/identity_anchors.tsv`, P0). Negative control: the permutation control in `data_gate_profile.py` §5, reported on `data_card.md` leakage row 4 — permuting the 24 velocities against the distances 2000 times gives K mean −0.91, sd 118.89 against 454.16 on the real pairing, **0 of 2000** permutations reaching the real value. Both present; neither had to be declared absent. |
| 5 | multiple comparisons | **PASS (with note N4)** | No `confirmed` claim is drawn from a selected family: all ten predictions were registered before any evidence and **all ten are reported**, so there is no selection to guard against; no claim rests on a p-value and the word "significant" does not appear in `findings.md`. The 24-fold comparison behind C7 is deterministic arithmetic on printed table values (no null distribution, so no multiplicity correction applies), and the only stochastic quantities (E0006–E0008 intervals, E0009/E0010/E0013 coverages) are single pre-registered estimates. Note N4: neither `study.yaml` nor `findings.md` ever states `n_comparisons` or names this posture — the reader must infer it. |
| 6 | pre-registration integrity | **PASS** | Four consult records (events seq 2, 3, 6, 13), three of them re-records, each carrying its reason: (#1) `data.source` must be a machine-resolvable tag, "No evidence exists yet"; (#2) phase ids follow the shipped `adaptive-N`/`confirmation` convention, "No evidence exists yet"; (#3) `minimum_delta` and `fit_noise` pasted in from the measured Phase-0 floors, "Measured after E0001". Only re-record #3 post-dates any run (E0001 at 05:56:40, gate at 06:00:58). I diffed it: `git diff 15cacad 0b1994f -- study.yaml` touches **only** the two floor blocks. Decisively, the `predictions:` block hashes to `539dfdde06c6…`, the `sealed_lock:` block to `39205ecaa917…` and the `simulation:` block (including sealed seed block C = 20260905) to `842b0e8c0bdd…` — **identical at all four revisions and at HEAD**. No prediction was added or changed after its evidence; no seal moved. |
| 7 | numbers traceable (five hand-checked below) | **FAIL** | `klein verify --numbers` passes (117/117 scanned numerals trace to 34 pinned sources) and there are **no `klein:numbers-ok` markers anywhere in the study** — nothing is exempted by hand. My five hand-checks all pass. But `findings.md:25` states a ratio ("nearly six times wider") that no pinned artifact holds and that the pinned artifacts contradict. The mechanized scan missed it only because the numeral is spelled out as a word. See F1. |
| 8 | references | **PASS (with note N2)** | All 8 entries of `references.yaml` are `verified: true` with a `verified_at: 2026-09-03` and a locator; every `ref:` cited in `findings.md` (hubble1929, lemaitre1927, sandage1958, planck2018, riess2022, diciccio1996, frost2000) resolves to an entry; `method_card.md`'s `refs_verified: true` and its 8-row table are honest. No unverified reference stands behind anything. Note N2: `findings.md:218` says "five stand behind `confirmed` claims"; the lock shows **two** — `ref:hubble1929` (C2) and `ref:sandage1958` (C5). |
| 9 | figures | **PASS** | All four re-render byte-identically into a temp dir (`cmp` clean), and `make_figures.py` cross-checks every drawn value against a second pinned source at render time. Four-point critique: `bootstrap_k.png` and `velocity_distance.png` are zero-based on the axis that carries the comparison; `trajectory.png` is categorical. `coverage.png`'s left panel starts at 0.88, but the plotted deltas (0.938−0.911 = 0.027 and 0.925−0.911 = 0.014) are **4.5× and 2.3× the measured floor** `minimum_delta = 0.0060663`, and both anchors (nominal 0.95, P6's registered bar 0.90) are in frame — the truncation does not inflate a within-noise delta. Every panel names its source ids in the footer. |
| 10 | vocabulary and scope | **PASS** | Banned word "blind": 13 occurrences across `study.yaml`, `data_card.md`, `method_card.md`, `scouting_ledger.md`, `research_plan.md`, `program.md` — **every one is a qualified meta-mention** of the form "a prospective lock is not blindness; the profile bans the word" (the 14th, in `make_figures.py`, is inside "colourblind-safe"). It appears nowhere in `findings.md` or `claims.lock`. "proved", "significant", "material", "actionable", "better/improves/beats" are all absent from `findings.md`. The brief's banned phrases: "Hubble was wrong" appears only inside §⑤'s "**What must NOT be concluded**" list with its refutation; "we replicated Hubble" appears only as a quoted phrase the study says does not appear; "500 is Hubble's value" appears nowhere — C18 and the `bootstrap_k.png` legend both say 500 was *adopted as an intermediate*, in neither published solution. Floor estimands are named (`marginal-resplit`, `fit-noise`) with `source` and `measured_after`; the exact tracks declare `exactness_note` resolutions instead. C4's in-silico scope is carried in the lock and in the prose. No `materiality:` block, and §⑤ says nothing is priced. |

### The five hand-checked numerals (check 7)

| # | Alias / value | Pinned home | Verified against |
|---|---|---|---|
| 1 | `k_free = 454.158441` | `tables/two_parameter_fits.tsv` → row `free_intercept`, col `k_kms_per_mpc` | matches `runs/E0012/manifest.json:primary_metric` and `results.tsv` E0012 |
| 2 | `gap_465_nearest = 10.841559` | `tables/two_parameter_fits.tsv` → `free_intercept.abs_gap_to_target` | matches P1's notary explanation `min_abs_gap_465 10.8415590774 > 10 → supported` |
| 3 | `coverage_sealed = 0.925` | `tables/sealed_coverage_blockC.tsv` → col `coverage`, `seed_block C`, `seed 20260905` | matches `runs/E0013/run.log` `primary_metric: 0.925000` and `results.tsv` E0013 |
| 4 | `sealed_deviation = 0.224998` | `aux_metrics.tsv` line 145 `E0011 abs_deviation 0.22499812864863244` | matches `runs/E0011/run.log` and P8's explanation `|Δ| = 0.224998128649` |
| 5 | `bad_rescale_gap = 2680.495911` | `sweeps/sealed_dryrun.20260903T062602.416191Z.log` `max_abs_gap_70: 2680.4959109684214` | **and confirmed absent from `aux_metrics.tsv`** (0 matches for "2680") — the exact fact the SYNTHESIZE disclosure rests on |

Spot-checks beyond the five (all pass): `max_gap_70 4.990073`, `virgo_influence 77.188826`,
`k_without_virgo 531.347267`, `residual_sd 232.910670`, `probable_error 50.747428`,
`se_units 2.447419`, `inverse_forward_ratio 1.603771`, `analytic_se 75.237105`,
`ci_low/ci_high/ci_width`, `coverage_dev 0.911`, `coverage_analytic 0.938`,
`max_mag_deviation 0.071213`, `n_outside_p9 3`.

## Adversarial findings the brief asked me to test

**Table 2's derived `r_mpc` never enters any cell as evidence — verified three ways.**
`lib/hubble.py:79` freezes `TABLE2_FORBIDDEN_COLUMNS = ("r_mpc", "vs_kms", "M_t")` and
`load_block()` drops them before any cell sees the block; the E0011 candidate
(`34107cee`) re-asserts the guard itself and raises on a leak (which is what fired in
the first rehearsal); and `tables/sealed_table2_magnitudes.tsv` carries only
`object, v_kms, m_t, r_implied_mpc, M_implied` — the last two computed *from* the study's
own K, never read from the paper. P8 is phrased on `v_kms` and `m_t` only. The DATA gate
proved the derivation (`r = (v − v_s)/500` exact on 20 of 21 printed rows, rounding on
the 21st) rather than asserting it.

**The three seals are lawful under `inquiry-model.md`, one per track, each rehearsed.**
reproduction (kind `replicate`, "the original's reported value, compared once") → E0011
against Hubble's printed −15.3 on the sealed Table-2 block, printed
`split_fingerprint: b3d8796e91bc…`, which is the sealed digest published on
`data_card.md` **before** any cell ran. estimate (kind `estimate`, "an external
reference value, compared once") → E0012 against H₀ = 70. simulate (kind `simulate`, "a
fresh seed block never used in development") → E0013 on block C = 20260905, which
development (B = 20260904), the floor (20260911–15) and the estimate track (A =
20260903) never touched, and which the candidate refuses to read outside `--final-test`.
The event chain shows every seal preceded by a `sealed_dryrun` on its own track (seq
50, 51 → E0011; 56, 57 → E0012; 63 → E0013), and the two defects the rehearsals caught
are real and both in the logs: `sealed_dryrun.…062248…log` crashes on
`forbidden columns reached the sealed cell: ['r_mpc', 'vs_kms', 'M_t']`, and
`…062602…log` **exits 0 with a well-formed block** carrying `max_abs_gap_70:
2680.4959109684214` from an inverted rescale that would have recorded P7 refuted on the
track's only access. C14 is therefore earned, not narrated.

**The `claims.lock` history reset — judged a NOTE (N3), and here is the reasoning.**
I verified every factual assertion in the disclosure at `program.md:571–617`
independently, from the reflog rather than from the prose:
`bb55678 HEAD@{08:21:32}: reset: moving to bb55678`, and `bb55678` is exactly the
commit `study 10: findings.md — seven sections, 18 claims`. `git diff --stat bb55678
4dc9011` (the discarded tip) shows **one file changed: `studies/10-hubble-1929-replication/claims.lock`,
792 insertions, 0 deletions** — repo-wide, not just study-wide. No manifest, no event,
no `results.tsv` row, no table, no figure, no replication record and no dry-run log was
touched by the discarded work, so none could be destroyed by the reset. Reading the
discarded blob confirms the cause exactly as disclosed: it pinned `bad_rescale_gap =
2680.495911` to `art: aux`, a file that does not contain the value (check 5 fails), and
the attempted repair added an orphan alias `bad_rescale_gap_home` rather than repointing
the original — because check 6 forbids changing a number's `art`, and every `klein
claims` verb self-commits. The lock could never have verified again. Why this is a NOTE
and not a FAIL: no rubric check's FAIL condition covers it (the machine-checked claims
law passes all seven on the current history, including append-only and ancestry); no
evidence artifact was touched; the discarded revisions were three minutes old, had never
verified, had never been refereed and were read by no downstream artifact; the
`predictions:` and `sealed_lock:` blocks are provably untouched; and the disclosure is
complete, dated, prominent, self-incriminating and explicitly addressed to the referee
before the lock. What a stranger nevertheless loses is real and should be repaired: the
discarded commits are reachable only from a **local** reflog, which does not survive a
clone and expires under `git gc`. See N3.

## Notes — each needs a dated `Referee note:` answer in `program.md`

1. **N1 — no `## Roster` in `program.md`.** Nothing on the record names the model, tool
   or session that ran the loop, which caps the independence rung at "fresh session"
   and forces `independent-of-experimenter: no` on this gate record and in the README
   gallery. `study_state.json` names only `lead-agent`. Add the roster table
   (`experimenter`, `data-gate auditor`, `referee`, `lead`, each with model · tool ·
   session) so the next referee can claim the rung the study actually reached.
2. **N2 — `findings.md:218` overstates the reference/claim coupling.** "all of them are
   `verified: true`, which matters because five stand behind `confirmed` claims" —
   `claims.lock` shows two: `ref:hubble1929` (C2) and `ref:sandage1958` (C5). The other
   five `ref:` citations sit behind `exploratory` claims (C11, C16, C18) or appear in
   §⑥ prose only. Correct the count.
3. **N3 — preserve the discarded `claims.lock` drafts as a durable ref.** The disclosure
   is exemplary and the reset touched nothing but the lock, but "auditable from the
   reflog" is not auditable by a stranger: reflogs are local and expire. Create a ref
   that survives a clone (e.g. `git tag -a discarded/10-claims-lock-draft 4dc9011 -m
   "never-verified lock drafts, discarded and re-authored — see program.md SYNTHESIZE"`)
   and name that tag in the disclosure paragraph. Consider promoting the lesson to
   `knowledge/research-discipline.md` with `(supports 10-hubble-1929-replication#C13)`
   or a new claim: *a self-committing authoring verb needs its validation at write time,
   because the append-only law leaves no lawful repair afterwards* — which is precisely
   what the engine fix `a1f30b2` now enforces.
4. **N4 — the multiplicity posture is never stated.** No `n_comparisons`, no
   `metrology.family_maxt`, no sentence explaining why none is needed. The reader has to
   work out for themselves that every reproduction comparison is deterministic and every
   stochastic quantity is a single registered estimate. One sentence in §⑤ or in
   `study.yaml` would close it.
5. **N5 — `research_plan.md:60` contradicts itself.** "It is not blindness, and the word
   'blind' does not appear in this study" — in a sentence containing the word, and while
   five other study files carry qualified mentions of it. The intent (the word is never
   used to *describe the seal*) is right; the sentence as written is not. Reword.

## Clearing conditions (FAIL)

**F1 — check 7. `findings.md` lines 25–26 quote a ratio with no home, which the pinned
artifacts contradict.**

The sentence, in the study-summary paragraph:

> "Meanwhile the estimate track found that the same 24 objects support an interval
> **nearly six times wider** than Hubble's quoted one…"

What the pinned artifacts hold: `ci_width = 287.056180` (`art:boot`,
`tables/bootstrap_k.tsv`) and `hubble_pe_24 = 50` (`art:contract`). Every consistent
comparison of those two gives **2.87**, not six:

- width against width: 287.056180 / (2 × 50) = **2.8706**
- half-width against half-width: 143.528090 / 50 = **2.8706**
- the only route to "nearly six": 287.056180 / 50 = 5.7411 — the study's **full** width
  divided by Hubble's **half**-width, which is not a comparison of two intervals.

Worse, on a like-for-like reading the sentence is not merely imprecise but inverted.
Hubble's ±50 is a *probable error* (the 1929 convention), which the study itself
reproduces: C10 pins `probable_error = 50.747428 = 0.6745 × analytic_se`. Converting his
±50 to a 95 % interval gives a width of 290.58 against the measured 287.06 — a ratio of
**0.99**. That is exactly what §③ surprise 1 says ("Hubble's ±50 reproduces almost
exactly"), so the document currently asserts both that its interval is six times wider
than Hubble's and that its uncertainty reproduces his. Both cannot be true, and the
false one is in the opening paragraph, where it will be inlined into `report/index.html`.

No `klein:numbers-ok` marker covers it; `klein verify --numbers` passed only because the
numeral is spelled as a word. `findings.md` is not a pinned artifact, so the repair
breaks no hash and requires no change to the ledger, the figures or any claim.

**What clears it — any one of these, then re-run the verifiers and re-referee:**

1. **Preferred.** Reword lines 24–26 to rest on values that already have homes, e.g.
   "…support an interval of width **287.056180** km/s/Mpc against the **±50** probable
   error Hubble quoted — 2.9 times his interval taken at face value, and, converted to a
   common convention, almost exactly it." Then also reconcile §③ surprise 1 so the two
   passages tell one story.
2. Keep a ratio, but give it a home: `klein claims number interval_width_ratio --value
   … --art … --claim C3` and append the alias to C3's `numbers[]` (growth of `numbers[]`
   is lawful under check 6). **Do not edit C3's `claim` sentence** — that field is
   frozen by the append-only law; if the ratio needs to be a claim, open a new id.
3. Delete the ratio and state the two pinned numbers.

Re-verification after the fix: `uv run --locked klein verify --study
studies/10-hubble-1929-replication --numbers --evidence-use` and `klein claims verify
--study … --numbers` must both stay at 0 failed, and Gate 3 must be re-run — the
orchestrator may not record the referee gate on this report.

## Observations (no action required)

- **O1 — the two `[WARN]`s inside `klein verify`'s OK rows are correct and expected.**
  "analyze.py obtain partitions from the contract, but no realized fingerprints are
  registered" follows from `split.kind: none` (the partition is the paper's two tables,
  not a draw) and is disclosed on `data_card.md` as issue 3 with both block digests
  published for hand-recomputation; "scaffold stubs remain (NotImplementedError)" is
  what a registered track's mandatory surface-restore leaves behind after every cell —
  what ran lives in the candidate commits (e.g. `34107cee` for E0011), which I read.
  Neither should be re-litigated by the next reader.
- **O2** — `figures/velocity_distance.png`'s legend prints 423.94 / 454.16 / −40.78,
  the rounded forms `scouting_ledger.md` §Retirements says "nothing cites". They are
  display roundings of the pinned full-precision table, not citations of the brief's
  scouted values, so no law is broken; the ledger sentence is just no longer literally
  true.
- **O3** — E0001 obtains Table 2's row count from the prepared artifact's `block`
  column rather than through `load_block("table2")`, and says so in its candidate
  docstring. No sealed value enters the cell; the count is a published fact registered in
  P0. Correct, and worth keeping visible.
- **O4** — the study's honesty about foreseeability (four of ten predictions, disclosed
  in `scouting_ledger.md` §Foreseeability before any run, repeated in §②, and C15 on
  the floor that partly spent P6) is the strongest thing in this study and is fully
  supported by the record: the E0013 candidate's own docstring discloses P6's
  foreseeability *before* the sealed run, and the floor's seeds are provably disjoint
  from block C.
