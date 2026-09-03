Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5[1m]) · fresh context · independent-of-experimenter: no

# Referee report — 12-insurance-claims-frequency

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **fresh session**.

`program.md`'s `## Roster` names the experimenter as "a Claude Code general-purpose
subagent · `claude-opus-5` · a fresh git worktree, this session". This referee runs on
`claude-opus-5[1m]` — the same model, a different context and a different session. The
**model** rung of the ladder is therefore **not** reached, and
`independent-of-experimenter` is `no`.

The roster anticipated this in writing ("Independence rung expected: `fresh session`
unless the referee runs on a different model … if Gate 3 is another Opus context the
model half of the ladder is NOT met and the gate record must say so"). It is said here.
The roster is present and complete for the experimenter and data-gate auditor rows, so
the rung is read from evidence rather than capped for want of it. Nothing else in this
report depends on the rung; the ten checks below are mechanical or arithmetical.

## Mechanical verifiers run

All from the repo root, `KLEIN_OFFLINE=1`, against the study worktree at HEAD `a57fdab`.

| Command | Result |
|---|---|
| `klein verify --study … --numbers --evidence-use --no-receipt` | **35 checks, 0 failed**; `evidence_use_rate 1.00 (10/10 cited)`; 146 findings numerals trace to 23 pinned sources; two informational `[WARN]`s inside `[OK]` checks (profile vocabulary; referee gate not yet recorded) |
| `klein claims verify --study … --numbers` | **7 checks, 0 failed** (shape, artifacts, presence, evidence, numbers, append-only, ancestry) |
| `klein predict list --study …` | **6 supported, 2 refuted, 0 inconclusive, 0 open** |
| figure re-render (`make_figures.py --out <tmp>`, byte compare) | **6 of 7 byte-identical** into the requested directory; the 7th (`plot_decision_trajectory.png`) is not routed to `--out` at all — it re-renders byte-identically **in place** in the study tree. All seven PNGs hash unchanged after the run and `git status` is clean. See Note 1. |
| `klein status --study …` | 5 experiments (keep=2 discard=3 measured=0 crash=0); final holdout `primary=1/1`; 0 refutations without a decision; 0 single-source confirmed claims; no pending transactions |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** | Exactly one `confirmed` claim, C7, on `E0005` (`evaluation_kind: final_test`, `split_partition 06d18ee16624` = the registered sealed partition) + `E0003` + `P7` + `rep:E0003@20260903T083929Z`; `confirmation.require: [sealed]` is met and `klein verify` records "1 confirmed claim(s) cite two or more evidence kinds". The other 11 claims are `exploratory`, and findings §⑤ states the limit in prose: "only the incumbent's LEVEL is confirmed … every rung-to-rung gap quoted above is development evidence and is exploratory by construction". Mechanism talk is classed, not smuggled: C9 is `mechanism-interpretation`/exploratory. |
| 2 | predictions adjudicated and reported | **PASS** | `klein predict list` verdicts equal findings §② row for row (P1 s / P2 s / P3 r / P4 s / P5 r / P6 s / P7 s / P8 s) and equal the `predictions` block of each run manifest. Both refutations carry dated `Decision:` lines — `program.md:522` (P3) and `program.md:530` (P5) — and `klein verify`'s belief-revision check confirms it. 0 open. |
| 3 | negative evidence reported | **PASS** | `evidence_use_rate 1.00`, all 10 non-keep runs and registered sweeps cited. No crashes exist. Every discard is load-bearing rather than buried: E0002 and E0004 are the whole of C4 and C5, and the sealed discard E0005 is the confirmation itself. |
| 4 | controls | **PASS** | Negative control: `data_card.md:140` mechanized eval-harness row — constant predictor `val_auc=0.5000`, label-shuffled `val_auc=0.5114` against a chance anchor of 0.5. Positive control: E0001 had to recover an independent study's number on identical training rows and did, to 0.011322. Both are named as controls in findings §②. |
| 5 | multiple comparisons | **PASS** | `n_comparisons` stated for all three families in findings §② (ANCHOR 3, FLOOR 4, ARITHMETIC 1). The guard is pre-registration, and it is real (check 6). The sole `confirmed` claim rests on P7, whose observed 0.168 against a ±2-floor threshold is nowhere near its boundary; a Bonferroni correction over eight comparisons changes no verdict, as findings states. |
| 6 | pre-registration integrity | **PASS** | Two consult records, both at events `sequence 2` (07:57:41Z) and `sequence 9` (08:23:23Z) — **both before `E0001`'s `run_started` at `sequence 10`, 08:25:43Z**. The re-record's diff (`git diff 9197c4a 7228d92 -- study.yaml`) is exactly `minimum_delta: 0 → 0.0375805`, the `noise_floor:`/`fit_noise:` blocks and `bound:` — **no prediction rule, tolerance, target, rung or phase changed**, precisely as the gate note claims. The current `study.yaml` still hashes to `05839c6d…`, the value hashed at 08:23:23Z, so nothing changed after it either. All three departures from the brief carry dated `Decision:` lines in the program.md that the *first* consult gate hashed (`c318718925…`, verified byte-identical): the 0.10/0.10 split (`program.md:141`), the 0.0225 tolerance (`:151`), and P2's target 0.651707 (`:160`). `scouting_ledger.md` S2 records why the brief's 0.6528 was retired — it was never measured by v1 — and S5 derives 0.0225 = 2 × 0.011226 from Hanley–McNeil on row counts alone, before any fit. |
| 7 | numbers traceable (five hand-checked: `keep_lift`, `sealed_shift_in_floors`, `brier_ratio_doctrine`, `paired_std_ratio`, `minimum_delta`) | **PASS** | `klein verify --numbers` and `klein claims verify --numbers` both clean. There are **no `klein:numbers-ok` markers anywhere in the study** — every numeral traces without an exemption. Hand-checks below. |
| 8 | references | **PASS** | `references.yaml` holds 10 entries, `verified: true` on all 10, `verified: false` on none, each with a DOI/URL and a dated `verified_by`. The 10 `ref:` keys cited in `findings.md` and those cited in `method_card.md` are exactly those 10 — no citation without an entry. `method_card.md` asserts `refs_verified: true` and a complete `triad:` (theory/papers/practice all true), which the METHOD gate note substantiates item by item. No reference sits behind the one confirmed claim (C7 cites runs only). |
| 9 | figures | **PASS** | All seven PNGs re-render byte-identically (six verified into a scratch `--out`, the seventh verified in place, all seven hashes unchanged, tree clean). Axes: `floors_vs_gaps` sets `set_ylim(0, …)` explicitly on both panels; `plot_decile_lift` is a bar chart from zero; ROC/PR/reliability are unit-square plots with the diagonal drawn. No truncated axis, and no figure inflates a within-noise delta — the `floors_vs_gaps` right panel draws the one-floor line and shows the sub-floor gaps *below* it, which is the honest direction. `make_figures.py` also cross-checks each refit AUC against the ledger in-script and raises rather than renders. Harness defect in Note 1; decile-lift bin nuance in the hand-checks below. |
| 10 | vocabulary and scope | **PASS** | §⑤ carries the profile's exact heading, "Business / actuarial value implications". **No `materiality:` block is registered** — correctly, and findings says so explicitly and then uses the profile's prescribed fallback wording verbatim: "no `materiality:` block is registered, so the honest statement is exactly that: the registered keep-sized bar was not cleared". "material" and "actionable" appear nowhere; "significant" appears nowhere. The estimand is named everywhere the floor is (`paired-comparison`, and `fit-noise` is explicitly labelled "PROVENANCE, never the bar"). Comparatives are qualified as the profile demands: the tree's calibration deficit is "worse by a factor of 3.789" and its rank advantage "0.3714 of the measured floor and 0.4624 of that comparison's own floor". Every decile-lift use carries its decile and base rate (C11, §③ Surprise 4, §④.6). Three residual "lift" warnings in a second sense — Note 4. |

### The five hand-checked numerals

Recomputed from the pinned artifacts, not copied from the lock.

1. **`keep_lift = 0.049911`** — `aux_metrics.tsv` E0003 `val_auc` 0.6640510576221735 − E0001 `val_auc` 0.614139800632142 = **0.0499112570**. Matches `tables/verdict_arithmetic.tsv` row `E0003_vs_incumbent`.
2. **`sealed_shift_in_floors = 0.1680`** — the numeral carrying the only `confirmed` claim. (0.664051 − 0.6577385597082954) / 0.0375805 = **0.1679727**. Sources: `results.tsv` E0003/E0005 and `study.yaml`'s `minimum_delta`.
3. **`brier_ratio_doctrine = 4.055`** — E0004 `reference_brier` 0.240641 / `val_brier` 0.059337202510254206 = **4.0554827**.
4. **`paired_std_ratio = 10.92`** — recomputed from the raw sidecars, not the rounded table: sample stdev of `sweeps/paired_bootstrap_b1000.sidecar.tsv` (n=1000) = 0.013941578, of `sweeps/pair_anchor_doctrine.sidecar.tsv` (n=1000) = 0.001276257, ratio **10.9238**. (Worth recording that the 6-dp values in `tables/pair_floors.tsv` give 10.9263, which rounds to 10.93 — the pinned 10.92 is correct only at full sidecar precision, which is where it was computed. It checks out.)
5. **`minimum_delta = 0.0375805`** — recomputed from `sweeps/paired_bootstrap.sidecar.tsv` (k=20): sample stdev 0.01730215, range 0.075161, so max(2×std, range/2) = max(0.0346043, **0.0375805**) = 0.0375805. The bar is set by range/2, and the contract's comment says so.

Also re-derived and confirmed: `bar_over_v1_spread` 0.9671, `splines_in_floors` 0.9568, `tree_over_glm_in_floors` 0.3714, `doctrine_in_floors` 0.0390, `splines_in_own_floors` 1.0926, `v1_sweep_in_floors` 0.0379, `lift10_drop` 0.5101, `claim_rate` 0.063968 (= 3748/58592), `anchor_residual_margin` 0.000458, `brier_ratio_tree_vs_splines` 3.789, `marginal_std` 0.017964, and `max_twin_gap` 0.001415 (= max |`twin_free_gap`| over E0001–E0004).

One figure nuance found while checking C11 against its panel, recorded for the record and not as a note: `kleinlib.eval` computes `val_lift_top10` on `len//10` = 585 rows (giving exactly the pinned 2.2167384615), while `kleinlib.figures.plot_decile_lift` bins with `array_split`, putting 586 rows in D1 (giving 2.2129556). The two differ by 0.0038, the chart prints no numeral, and the difference is a framework bin convention rather than anything this study chose. The reliability diagram and the decile-lift chart are otherwise drawn from the same probabilities the in-script cross-check pins to the ledger.

## The two large judgement calls

Both were put to me explicitly, and both are judged here rather than noted.

### The overridden DATA gate — honest and sufficient

`data_card.md` returns **NO-GO** on a mechanized leakage FAIL (615 row-content hashes
straddle the partitions; 5.12% of development and 5.32% of sealed rows have a
byte-identical training twin) and **still says NO-GO** at HEAD; its sha256 is what the
`gate_overridden` event hashed. The auditor laid out options (a) accept with the risk
documented and (b) dedupe/group-split, and declined to choose. The override took (a).
I judge the reason a **reason, not an excuse**, on four grounds I could check:

1. **The defect is inherited, and the override proves it rather than asserting it.**
   `tables/duplicate_exposure.tsv` measures the same contamination in the v1 study's own
   validation partition — 612 of 11,719 rows, 5.22% — which v1 never checked. The
   anchors being chased were themselves measured on a contaminated holdout.
2. **Both fixes would delete the question.** Either fix changes which rows are trained
   on, which voids the train-partition identity that P1/P2/P4 are registered against.
   That is a design argument, not a convenience argument, and it was made before the
   loop.
3. **The risk was carried with an instrument, and the instrument is correct.**
   `lib/duplicate_exposure.py: duplicate_free_mask` hashes the *actual fit rows*, not a
   fixed training partition. On the sealed run, fitted on train+development, it excluded
   332 rows (5860 − 5528), not the 312 the partition table alone would suggest — it
   caught the 20 extra sealed rows whose twin sits in development. The instrument is
   more conservative than the table, which is the right direction.
4. **The card was not edited to unlock the gate.** The disagreement lives on the event
   trail where the protocol puts it.

**Does C7 survive?** Yes, and I checked it rather than taking it. On the 5528 sealed
rows with no twin among the rows the model was fitted on, E0005 scores `twin_free_auc`
0.656647 — a gap of −0.001091, smaller in magnitude than the 0.001415 bound findings
quotes, so that bound holds for the sealed run too. The development-to-sealed shift
computed on twin-free rows is 0.197 floors instead of 0.168 — still far inside P7's
±2-floor rule. The confirmed claim does not depend on the contaminated rows.

**Is every AUC-level claim scoped?** Yes. §⑤'s "Two scope limits an underwriter should
carry" states that *every* number in the study, and every v1 number it is compared
against, was measured on a partition carrying 0.051203 (development) and 0.053242
(sealed) twin shares, and bounds the consequence. §③ Surprise 3 reports the direction
honestly and against the study's own prior: the duplicates did **not** flatter the tree —
three of four development rungs score *higher* twin-free — and the playbook's H1 is
recorded as refuted. No unscoped claim rests on the leaked partition. **No FAIL.** One
residual gap is Note 3.

### The two `claims.lock` rebuilds — disclosed, and nothing else moved

Both are disclosed in `program.md:592–648` with their reasons. I reconstructed both from
the reflog and diffed them:

| Discarded revision | Reset | `git diff --stat` of what was dropped |
|---|---|---|
| draft 1, tip `307b67e` | to `0b05de5` | `studies/12-…/claims.lock` (+529) **plus** `kleinlib/claims.py` and `kleinlib/tests/test_claims.py` — framework files, not study files |
| draft 2, tip `49af7f4` | to `979bb92` | `studies/12-…/claims.lock` **only** (+87 / −30) |

**No manifest, no event, no ledger row, no table and no figure was touched in either
chain.** The engine commit caught up in draft 1 was re-created after the reset as
`da8c542`; I diffed the two patches and they are **byte-identical**, so nothing was lost.
The disclosure is complete and matches the git record, including the second pass's cause
(a claim sentence naming `log1p`, whose digit the sentence scanner reads as a numeral) —
and C4's lock sentence indeed now reads "a logged density" in prose. I note approvingly
that the engine was *not* loosened for that second case, with the reasoning written down.

Judged as study 10's referee judged the same act: **a note, not a FAIL** — the history
rewrite happened before the lock had any reader, destroyed no measurement, and the
fixed-forward path was arithmetically unavailable because `art` may never change. The one
thing missing is durability — Note 2.

## Notes (each needs a dated `Referee note:` answer in `program.md`)

1. **The figure harness does not honour `--out` for 5 of its 7 figures, and the
   documented recipe writes into the study tree.** In `figures/make_figures.py`, the four
   profile figures are called as `figures.plot_roc(…, out_dir.parent, …)` and
   `kleinlib.figures._save_fig` appends `/figures` to whatever it is given, so they land
   in `<out>/../figures/`; `plot_decision_trajectory` is passed `study` literally and so
   always writes into `studies/12-…/figures/` regardless of `--out`. Two consequences a
   future reader should not have to rediscover: (a) `klein verify`'s automated check
   reports "**2** figure(s) re-render byte-identically" — it audits only `lorenz_gini`
   and `floors_vs_gaps`, the two that use `out_dir` directly, so five figures are outside
   its guarantee; (b) a referee following the `--out <tmpdir>` recipe silently rewrites a
   committed study file. Nothing is *wrong* with the figures — I confirmed all seven are
   deterministic and byte-identical, and the tree stayed clean — but the re-render
   guarantee is weaker than it reads. Passing `out_dir` (not `out_dir.parent`) and
   `out_dir.parent` (not `study`) would make all seven honour `--out`.
2. **Tag the two discarded lock revisions so a clone can see them.** They currently exist
   only in this machine's reflog; the disclosure in `program.md:592` invites the referee
   to judge an act whose evidence a clone cannot reach, and the commits are GC-eligible.
   The repo already carries the precedent tag `discarded/10-claims-lock-draft`. Recommend
   `discarded/12-claims-lock-draft-1` → `307b67e` and `discarded/12-claims-lock-draft-2`
   → `49af7f4`, named in the disclosure paragraph.
3. **The sealed run's own twin-free numbers never surface.** `aux_metrics.tsv` records
   E0005 `twin_free_rows` 5528, `twin_free_auc` 0.656647, `twin_free_gap` −0.001091, but
   no line of `findings.md` and no number on C7 quotes them; §⑤ discloses the sealed twin
   *share* (0.053242) and then bounds the consequence with 0.001415, a figure derived
   from the four **development** rungs (`claims.lock` pins `max_twin_gap` with exactly
   that note). The bound does hold for the sealed run — I checked, 0.001091 < 0.001415 —
   so this is an incompleteness, not an error. But the override's entire warrant is that
   instrument, and the one claim that reaches `confirmed` is the one place the instrument
   is not shown. Quoting E0005's twin-free AUC beside C7, or adding it as a pinned
   number, would close the loop the override opened.
4. **Three "lift" warnings from the profile's vocabulary scan.** `klein verify` flags
   `findings.md:77`, `:92` and `:135` (and the same word in C8's lock sentence). I did not
   treat these as the banned use and did not fail check 10: the insurance profile bans
   "lift" without its decile and base rate, and every *decile*-lift use in this study is
   properly qualified (C11 and §③ Surprise 4 both give "top-decile" and the base rate
   0.063968; §④.6 likewise). The three flagged lines use "lift" in the distinct sense of a
   metric improvement — "the v1 sweep's lift", "P3's lift is 0.035956" — where a decile and
   a base rate do not exist, and each is immediately expressed in floors, which is the
   profile's own honesty standard. The warning will recur at every verify and in the
   tutorial build; writing "AUC lift" or "paired lift" at those three sites would silence
   it without loosening anything.

## Clearing conditions (FAIL only)

None. No FAIL condition holds.

---

**A closing observation for the next reader, outside the rubric.** The strongest thing in
this study is not a result, it is a habit: two decisions that could each have been
quietly optimised — a NO-GO gate and a lock that failed its own law — were instead
written down at length, with the arithmetic that makes them checkable and with the
alternative that was rejected. Both survived an adversarial reading because of that, not
in spite of it. The refuted P3 is the same habit in miniature: it is reported as refuted
on the bar that was registered, *and* as 1.0926 floors on the bar it would have preferred,
with the second labelled instrument-limited and classed exploratory rather than
substituted for the first. The verdicts did not move onto friendlier floors.
