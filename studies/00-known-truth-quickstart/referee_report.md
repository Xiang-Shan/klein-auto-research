Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-opus-5[1m]) · fresh context · independent-of-experimenter: no

# Referee report — 00-known-truth-quickstart

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **fresh session of the
same model** — the LOWEST rung of the ladder. The fresh-context requirement is met in
full (this context has never seen the loop; `findings.md` was read first and
`program.md` last), but the *model* rung was NOT reached: the experimenter ran on Opus
and so does this referee, so `independent-of-experimenter` is recorded as `no` rather
than claiming a rung that was not achieved.

Experimenter: recorded only as actor `lead-agent` in `study_state.json`
(`acknowledgements`, `gates.*.acknowledged_by`) and in every `gate_recorded` event of
`events.jsonl`; the run manifests (`runs/E000*/manifest.json`) carry no actor or model
field at all, so the experimenter's model cannot be established from the study
artifacts alone. The orchestrating agent's brief states it was a separate Opus agent in
another context. That is the basis for the rung above, and it rests on testimony, not
on an artifact — which is itself worth recording.

## Mechanical verifiers run

All from the worktree root, `KLEIN_OFFLINE=1`, `uv run --locked`.

| Command | Result |
|---|---|
| `klein verify --study … --numbers --evidence-use` | **35 checks, 0 failed.** `evidence_use_rate 1.00 (4/4 cited)`; `findings numbers: all 45 scanned numerals trace to 13 pinned source(s)`; `convergent evidence: 2 confirmed claim(s) cite two or more evidence kinds`; `headroom: h = (0.87139 − 0.884116) / 0.00745212 = 1.708`. The only WARN is the expected `referee gate: not yet refereed`. |
| `klein claims verify --study … --numbers` | **7 checks, 0 failed** — shape, 6 pinned artifacts hash as recorded, every claim id resolves in `findings.md`, every evidence id resolves, every pinned value found in its artifact, append-only across git history, `git_head` an ancestor of HEAD. |
| `klein predict list --study …` | **4 supported, 1 refuted, 0 inconclusive, 0 open** (P1 P2 P3 P5 supported; P4 refuted). |
| `klein status --study …` | 5 experiments (keep=3 discard=2 measured=0 crash=0); `final holdout: primary=1/1`; `successful confirmation: primary=E0005`; 0 refutations without a recorded decision; 0 single-source confirmed claims; no pending transactions. |
| figure re-render (`figures/make_figures.py --out <tmp>`, byte compare) | **all 3 identical** — `plot_decision_trajectory__primary.png`, `headroom_bar.png`, `known_truth_calibration.png` all `cmp`-identical to the committed bytes; the script's own in-run cross-checks printed `all cross-checks passed`. |

Independent recomputation performed by this referee (not read from any Klein output):

- `minimum_delta` recomputed from `sweeps/split_lottery.sidecar.tsv` as
  `max(2·std, range/2)` = **0.00745212**; std **0.00372606**; range 0.012855; mean
  0.804577 — all four match `study.yaml` exactly.
- The Bayes ceiling recomputed from scratch — `contract_split(study)` + `truth.json`'s
  `true_log_odds` → `roc_auc_score` — gives development **0.884116398515** and
  final_test **0.893469112513**, matching `truth.json` and the contract's
  `metric.bound.ideal`; development Bayes Brier **0.103604** matches `data_card.md`.
- Every floors number reconciles at full precision: E0001 `gap_in_floors` 10.4555,
  E0003 1.7077, E0005 1.6800, E0002 `delta_in_floors` 3.9699, E0003 4.7779, E0004
  −1.7903, E0005 4.6190. (Recomputing from the 6-dp *rounded* ceiling shifts the 4th
  decimal of two of them; the full-precision values are exact. No discrepancy.)
- `headroom_at_e0004` = (0.884116 − 0.87139) / 0.00745212 = **1.708**.

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** (note 3) | `confirmation.require: [sealed]` (`study.yaml:144`). Both confirmed claims cite the sealed run: C1 → E0001/E0002/E0003 + **E0005**, C2 → E0002/E0003 + **E0005** (`claims.lock`); `klein verify` reports 0 single-source confirmed claims. Every exploratory claim is labelled: C3/C4 in the §① Strength column, C5 inline as *(mechanism-interpretation, exploratory)* (`findings.md:74`), C6–C8 scoped by name in §⑤ (`findings.md:121-123`). Neither failed replication supports any confirmed claim — C7 alone cites them and is exploratory. |
| 2 | predictions adjudicated and reported | **PASS** | `klein predict list` (4/1/0/0) agrees verdict-for-verdict with `findings.md:45-49` and with `study_state.json:predictions`; every verdict was written by the notary from a printed block (`events.jsonl` seq 9, 13, 17, 21, 27, all `"source": "run"`). P4's refutation carries its dated decision at `program.md:140-151` (“2026-09-03 — Decision: **P4 REFUTED** by E0004…”), and `klein verify` independently confirms `belief revision: every refuted prediction (P4) has a dated Decision: line`. Nothing open, no `--allow-open-predictions`. |
| 3 | negative evidence reported | **PASS** | `evidence_use_rate 1.00 (4/4 cited)`. E0004 (discard) is the subject of C3, C4 and C8 and of a full `program.md` decision; E0005 (sealed, dispositioned discard) carries C1 and C2; `sweep:fit_noise` and `sweep:split_lottery` are both cited by C6. The one discard cluster — capacity on top of the boosted rung — is written up as a finding (§③ second surprise, §④ C8) and as a ruled-out direction (`playbook.md`, "Ruled out"). Both FAILED replications are reported rather than buried (`findings.md:93-103`, `program.md:168-189`), including the fact that the second was given `--timeout-seconds 300`. |
| 4 | controls | **PASS** (note 4) | Negative control present and evidenced: `data_card.md:114` — `constant-chance[primary]: val_auc=0.5000` and `shuffled-chance[primary]: val_auc=0.5011`, both at the 0.5 chance anchor, mechanized by `python -m kleinlib.leakage`. Positive control present in substance: E0002 hands the model the DGP's known-true `x1·x2` term — a known-present effect the pipeline must detect — and recovers +3.9699 floors; the design-time linear-oracle diagnostic (`scouting_ledger.md:33`, 0.807679 → 0.838248 → 0.883874) states the expected magnitude in advance and E0002's realized 0.835785 lands near the oracle's 0.838248. Neither is *labelled* a control anywhere (note 4). |
| 5 | multiple comparisons | **PASS** (note 5) | The family is the five registered predictions, each locked with its own arithmetic rule in `study.yaml` at the first consult gate (hash `c4f66ed8…`, `events.jsonl` seq 2, 05:25:06Z) before any evidence existed, and each adjudicated against exactly one run. No post-hoc selection among candidate comparisons exists: 4 development runs + 1 sealed, and neither registered sweep feeds a claim (both measure the floor). The two confirmed claims rest on 4.62–10.46 floors, and one floor = `max(2σ, range/2)`, so these are ≥ 9σ effects — not an unguarded family. `n_comparisons` is nevertheless never stated (note 5). |
| 6 | pre-registration integrity | **PASS** (note 6) | The consult gate was re-recorded exactly once (`events.jsonl` seq 5, 05:27:25.780Z) with a reason on the record. I diffed the two hashed versions myself: `git diff 5bda63da 55edc93 -- study.yaml` touches ONLY `metric.minimum_delta` (0 → 0.00745212), the `noise_floor`/`fit_noise` blocks and `bound` — the `predictions:` block is **byte-identical** across the re-record. The floor did not exist when the rules were written: `minimum_delta` was literally `0`, and every rule is an integer count of floors (1, 1, 1, 1, 2), so no rule numeral could have been read off any observed value. Both floor sweeps were registered AFTER the re-record (seq 6, 7). No run existed before either gate (first `run_started` is seq 8). `overrides: []`. The pre-gate smoke check is disclosed rather than hidden (`scouting_ledger.md:35`, S4) and could not have set a rule, since `gap_in_floors` is only printed once `minimum_delta > 0` (`train.py:176`). |
| 7 | numbers traceable (five hand-checked: `minimum_delta`, `floor_std`, `dev_ceiling`, `sealed_ceiling`, `sealed_gap_floors`; plus `bayes_brier_dev`, `overcapacity_delta_floors`, `boosted_delta_floors`) | **PASS** | `klein verify --numbers`: all 45 scanned numerals trace to 13 pinned sources. My own extraction finds 26 distinct decimal numerals in `findings.md` and **every one** matches a pinned value in `claims.lock`; the only bare integers are 0/1/2/5/10 (rule thresholds and sweep `k`, all in `study.yaml`) plus the date and study id. Each of the eight numerals above was recomputed from raw artifacts (see "Independent recomputation") and matched. **No `klein:numbers-ok` marker exists anywhere in the study** — nothing was suppressed, so there is no marker whose reason could fail to hold. |
| 8 | references | **PASS** | All four entries in `references.yaml` carry `verified: true` with `verified_by` and `verified_at: 2026-09-03`; `method_card.md:8` asserts `refs_verified: true` and §5's table names the same four. No claim in `claims.lock` cites a `ref:` id, so no reference — verified or not — carries a confirmed claim. Every citation in `findings.md:134-145` (`ref:hanley1982`, `ref:friedman2001`, `ref:ke2017`, `ref:grinsztajn2022`) resolves in `references.yaml`; the bibliographic details (Radiology 143(1):29-36 · doi:10.1148/radiology.143.1.7063747; Ann. Statist. 29(5):1189-1232 · doi:10.1214/aos/1013203451; NeurIPS 30:3146-3154; arXiv:2207.08815) are each correct on their face. Network re-verification was not possible under `KLEIN_OFFLINE=1`. |
| 9 | figures | **PASS** (notes 1, 7) | All three re-render byte-identically into a temp dir (verified by `cmp`, not by trusting `klein verify`). Critique point 1 (unit-bearing axes): pass — `val_auc`, `distance to the ceiling, in measured floors (h)`, `Experiment ordinal (E#### sequence)`, `mean (predicted − true)`. Point 3 (legend/grayscale): pass — keep/discard/sealed differ by hatch and marker, not hue alone. Point 4 (chart fits claim): pass — the frontier claim gets a step plot, the A-vs-B calibration claim gets paired lines. Point 2 (scale honesty) is where the shortfall is: `make_figures.py:214` sets `left.set_ylim(0.78, 0.912)` on a **bar** panel (note 1). This does not meet the check-9 FAIL condition — the deltas displayed are 1.7–10.5 floors, i.e. ≥ 3σ to ≥ 20σ, decisively NOT within-noise, and the companion right panel presents the identical comparison zero-based in floor units with the `h = 1` line drawn. |
| 10 | vocabulary and scope | **PASS** (note 2) | Generic-profile banned words: **"blind" appears nowhere** in the study (full recursive grep); "significant"/"significance" appear nowhere; "material"/"actionable" appear nowhere, and §⑤ pre-empts the question outright — "this study registered no `materiality:` block, so clearing the measured bar means only that the bar was cleared" (`findings.md:125-127`). The one occurrence of "proven" (`program.md:182-183`) is a self-negation ("is NOT edited … to make an unproven fix look proven") — qualified. "beats" appears only inside the registered P2/P3 statements, each qualified "by at least one measured floor". The floor's estimand is named (`marginal-resplit`, `study.yaml:41` and `findings.md:29`). Simulation scope: C2 carries `scope: in-silico` in the lock and in the §① Class column, the §⑤ "what a reader should NOT conclude" paragraph scopes C3–C8, and the findings preamble scopes the whole study ("Nothing here is a fact about any real population"). Measurement resolution is never sold as materiality. The shortfall is in `data_card.md`'s literal-seed sentence (note 2). |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md)

1. **A truncated-axis bar panel (`figures/make_figures.py:214`).** The left panel of
   `headroom_bar.png` draws bars with `left.set_ylim(0.78, 0.912)`. `tutorial-spec.md`
   critique point 2 says flatly "Bars are zero-based". This is not a check-9 FAIL —
   nothing within noise is being inflated, and the right panel already shows the same
   comparison zero-based in floors — but `tutorial-spec.md`'s acceptance checklist
   asserts "Figure critique passed for every inlined figure", and this figure is
   destined for `report/index.html`. Either switch the left panel to points/dumbbells
   against the ceiling line, or state the truncation in the caption before inlining.
   (A literally zero-based AUC axis would be its own distortion — chance is 0.5, not
   0 — which is the argument for changing the mark type rather than the limit.)

2. **The data card's literal-seed sentence over-claims (`data_card.md:118-120` vs
   `train.py:58`).** The card states "there is no literal integer seed and no direct
   `train_test_split(random_state=<int>)` call **in any script the study owns**".
   `train.py:58` is `RANDOM_SEED = 42`. The *substance* of war story 8 is fully
   satisfied — that literal is a FIT seed passed only to `LogisticRegression` and
   `HistGradientBoostingClassifier`; partitions come from `load_partition(...)`, which
   prints the `split_fingerprint:` the notary checks, and `klein verify` confirms
   current == recorded for both the policy and the realized partitions. But the
   sentence as written is false, and it is asserted about a file the clean-room
   auditor declares it never read (`data_card.md:102-105`: "read ONLY `study.yaml`,
   `prepare.py`, the prepared artifact, `truth.json` and the kleinlib source — never …
   `train.py`"). Re-scope it to "no literal SPLIT seed", name `train.py:58` as a fit
   seed, and keep the claim inside the auditor's declared reading scope. Nothing in
   the ledger changes; this is a wording correction to the study's most-read gate
   artifact.

3. **An unmeasured superlative in §⑤ (`findings.md:116-117`).** "the tree recovered
   more of the distance to the ceiling (4.7779 floors) than **the single most valuable
   hand-specified term available** (3.9699)". No run measured that superlative: the
   study fitted `raw` and `raw + x1·x2`, never `raw + x3²`. The study's own
   design-time oracle points the other way — `scouting_ledger.md:33` records
   0.807679 → 0.838248 (+x1·x2, +0.0306) → 0.883874 (+x3², +0.0456), so the quadratic
   plausibly carries the larger share. The claim is defensible on DGP coefficient
   magnitude (interaction 1.00 is the largest), but §⑤ is discussing distance to the
   ceiling, where it is unmeasured. Note that `claims.lock`'s C2 text does NOT contain
   the superlative — this is findings prose running ahead of the lock. Drop it ("than
   the one hand-specified term the study tried"), or cite S2 and say the ordering of
   single terms was never measured. §⑤ is the section that tells a reader what to do
   differently, which is where an unevidenced superlative costs the most.

4. **The controls are present but never called controls.** The negative control is
   real and mechanized (`data_card.md:114`) and the positive control is real
   (E0002 recovering a known-present term at +3.9699 floors, against the S2 oracle's
   advance expectation), but the word "control" does not occur anywhere in
   `findings.md`, `program.md`, `data_card.md`, `method_card.md`, `research_plan.md`,
   `playbook.md`, `scouting_ledger.md` or `study.yaml`. A stranger currently has to
   reconstruct the control structure. One sentence in findings §① or in the data
   card's audit table naming them would settle check 4 by declaration rather than by
   the referee's reconstruction — and this is the onboarding exhibit, where showing
   the reader what a control looks like is part of the teaching.

5. **`n_comparisons` is never stated.** No family size and no family-wise guard is
   named anywhere. The family here is small (5), fully pre-registered, and each
   prediction is bound to exactly one run, so nothing is unguarded — but the rubric
   asks for the statement. Add one line to findings §②: `n_comparisons = 5` (the
   registered prediction family), guard = pre-registration at the consult gate plus
   one run per prediction, no post-hoc selection; and note that at 4.62–10.46 floors a
   Bonferroni over 5 changes nothing.

6. **"the gate hashes it" is not true of the scouting ledger
   (`scouting_ledger.md:10-11`, `program.md:75-76`).** `GATE_ARTIFACTS["consult"]` in
   `kleinlib/contract.py:133` is `("study.yaml", "research_plan.md", "program.md")` —
   `scouting_ledger.md` is not hashed by any gate. The wording is inherited verbatim
   from Klein's own boilerplate (`.claude/skills/klein/assets/scouting-ledger-template.md:11`
   and `references/consult-protocol.md:134`), so this is a framework defect surfacing
   in a study, not an authoring error. It matters here specifically because S4
   discloses a pre-gate smoke run: a reader told "the gate hashes it" will believe the
   disclosure is frozen by the gate record when it is in fact frozen only by the git
   commit. The protection IS intact — `scouting_ledger.md` has exactly one commit
   (`5bda63da`, the scaffold/gates commit), never touched since, and `claims.lock`'s
   ancestry check passes — but the sentence should be fixed at the template level and
   in this study, e.g. "committed before the gate, so the commit that the gate's
   `study.yaml` hash belongs to also contains it".

7. **§③/C5's description of the calibration figure is incomplete
   (`findings.md:80-83`).** "the linear model's error is not noise but a systematic
   under-prediction that grows with the true probability" describes the right-hand
   half of the right panel correctly, but the same panel shows a systematic
   **over**-prediction of about +0.05 for true probabilities below ≈ 0.3. The full
   pattern is shrinkage toward the base rate — over-predicts low, under-predicts high
   — which is a *stronger* illustration of C5's own point (missing structure, not
   noise) than the one-sided sentence. C5 is exploratory and correctly labelled, so
   this is a precision fix, not a strength problem; but the tutorial will inline this
   figure and should describe both tails.

## Clearing conditions (FAIL only)

None — no FAIL condition of the ten-check rubric holds. The seven notes above are
answered with dated `Referee note:` lines in `program.md`; the gate may be recorded.

Two things this referee wants on the record as *strengths*, because they are what a
stranger auditing this study should learn from:

- **The pre-registration is genuinely airtight, and it is checkable without trusting
  anyone.** The prediction rules are integers in units of a floor that provably did not
  exist when they were written (`minimum_delta: 0` in the gate-1 contract), the
  re-record diff is inspectable and touches no rule, and the pre-gate smoke check that
  *could* have contaminated P1 is disclosed rather than hidden — and is neutralized by
  a mechanism (`gap_in_floors` is not printed when `minimum_delta` is 0), not by an
  assurance.
- **The two failed replications were kept.** Both stand at `reproduced: false`,
  neither was retried into a pass, `train.py` was not edited after the loop closed to
  manufacture a fix, and the failure was converted into a claim (C7, exploratory) that
  names a real seam in the engine: `klein replicate` copies only the contract's
  declared `prepared_path`, and this study's entrypoint reads an undeclared second
  artifact. That is the single most useful thing in the study for the next author, and
  the honest handling of it is what a referee most wants to see and least often does.
