# Research plan — 08-iris-rematch (registered protocol)

Frozen at CONSULT. Mirrors the design brief (presentation task 20260828,
`reference/study08_design_brief_v1.md`) — where they disagree, THIS file governs.
Disclosure: see `scouting_ledger.md` §0 — this is a prospectively locked second
study on fully scouted data; the lock, not blindness, is the integrity claim.

## §1 Question

With a 3× larger roster than study 07 — calibration-first variants, a Gaussian
process, a small MLP, ensembles, and the 2025 TabPFN v2 tabular foundation model —
and a registered large try budget, can ANY challenger beat the 1936 LDA anchor on
the versicolor–virginica hard pair:
(a) on the fresh declared split (the ledger question),
(b) detectably across the registered split lottery (Bar-1),
(c) by an actionable, keep-sized margin at any training size (Bar-2, the data
    ladder n ∈ {60, 45, 30, 20, 12, 8})?
And if anything wins anywhere — is it architecture, or just calibration (RQ4)?

## §2 Identity (all pre-committed)

Declared split: group-aware 60/20/20, seed **20260907**, twins rows 102/143 one
group (99 groups / 100 rows) — NO REDRAW under any outcome. Seed namespaces,
all fresh and disjoint from every study-07 seed: ledger floor draws
20260901001–020 · arena repeats 20260901100+j · arena subsampling
20260901000+100j+k · analysis sensitivity MC 20260901550 · coda subset
derivation 20260901999. Metric `val_brier` (lower) on BOTH tracks; rationale in
study.yaml. Guardrails: max_run_seconds 120, wall_seconds ≤ 60.

## §3 Ledger protocol (declared split)

- E0001 anchor_lda4 (keep expected — first valid result sets the frontier).
- E0002 lda_sepal positive control (registered: discard, large degradation).
- k-seed fit-noise sweep: registered expectation degenerate (std exactly 0).
- `sweeps/ledger_floor.py` = study 07's EXACT floor recipe on the new split
  (GroupShuffleSplit test_size 0.25 over the 79 non-sealed rows, k=20, seeds
  20260901001–020, anchor only; statistic ceil3dp(2×std); RAISE-ONLY escalation
  to klein default max(2×std, range/2)). Measured block pasted into BOTH tracks;
  consult gate re-recorded. **No challenger transaction before that re-record.**
- At the adaptive-1 phase boundary the phase note publishes
  `headroom_declared = anchor_dev / minimum_delta` and names the branch that
  fired (study.yaml `predictions_to_falsify` rows 1–2: door-closed / door-ajar).
- Adaptive-2 = the verification parade: one run-one per challenger family,
  **registry order** (families.CHALLENGERS), 21 transactions, crash slack 26.

## §4 Arena protocol (primary evidence)

`sweeps/rematch_arena.py` — geometry, seeds, twins-last quota scan, and the
two-stage commit order are registered in that file's docstring (part of this
plan by reference). Key registered rules:

- Stage A (anchor + control, 480 fold-evals over the 79-row pool) commits
  `rematch_arena_anchor.sidecar.tsv`, `arena_partitions.tsv` (incl. the
  max-Jaccard dev-vs-declared disclosure; disclosure only, never exclusion), and
  `headroom.tsv` **before any challenger fit is summarized**.
- Per-rung floor δ_n = max(ceil3dp(2×sd of the anchor's 40 fold-eval Briers),
  **0.005**). No range/2 escalation at rungs — k=40 inflates range mechanically;
  this registered deviation from the ledger recipe is deliberate and disclosed.
  (0.005 gloss: the Brier movement of materially moving one prediction on a
  20-row dev fold, 0.32²/20.)
- OPEN(n) ⇔ m_n (full precision, unweighted mean over the 40 fold-evals) ≥ δ_n
  (sd ddof=1 over the same 40; ≥ on every boundary so OPEN, Bar-2 and the
  door-ajar rule agree at equality). Closure reason labels are DESCRIPTIVE, not
  causal diagnoses: `ceiling-closed` if m_n < 0.06 (07's sealed anchor rounded
  up, registered constant), else `fog-closed`. The 0.005 term is a fixed
  materiality floor (a registered constant), not an estimated noise quantity.
  Gloss: "open means a perfect oracle could clear the bar — necessary, nowhere
  near sufficient."
- UNMEASURABLE rung: >10% anchor fit failures — reported, excluded from
  open/closed and from the test family.
- Stage B: the 21 challengers, eligibility-filtered (`families.MIN_RUNG`),
  113 cells × 40 fold-evals. Crashes are sidecar rows, honest data.

## §5 Verdict quantities (frozen in `sweeps/rematch_analysis.py`)

Bar-1 / Bar-2 / control / capture / coda-branch selection exactly as that
file's docstring registers them. Registered statuses (post red-team): Bar-1 is
a SELECTION GUARD — a joint repeat-level sign-flip max-t diagnostic under a
registered symmetry assumption, never described as exact, as FWER control, or
as population inference; "detectable" is always shorthand for "cleared this
registered guard in this lottery". The guard family is FIXED at the 113
eligibility-matrix cells; cells lacking data occupy their slots as never-firing
placeholders (t = −inf) — nothing is dropped or substituted after outcomes are
visible; kNN's all-candidates-infeasible case raises and is recorded as a crash
row, never silently re-gridded. RQ4 is the LDA-FAMILY ADJUSTMENT CAPTURE — a
non-causal observed ratio (two calibration maps + covariance shrinkage), fired
at 0.5. Ledger-floor arithmetic: sample std (ddof=1); minimum_delta =
max(ceil3dp(2×std), max(2×std, range/2)) exactly as the committed script
computes it — the script is the registration. The fold-level max-t is a
sensitivity exhibit only.

## §6 Sealed coda (confirmation phase; two tracks, one look each)

Branch rules, band predictions, and the epistemic-status sentence are
pre-committed in `program.md` §Sealed. Mechanics (post red-team): the frozen
analysis writes `sweeps/coda_manifest.json` — branch, families, BAKED
train-position lists (Branch W: the registered quota scan, seed 20260901999,
ceiling class virginica, twins-last, applied to the declared train partition;
Branch G: all train rows), position hashes, and numeric bands with the
registered sign convention g_sealed = sealed_primary − sealed_challenger
checked against the arena's [p10, p90] of g = anchor − f. The confirmation
phase runs the pre-registered registry entries `coda_primary` /
`coda_challenger`, which READ the committed manifest — no code is edited after
selection. The coda band carries no nominal coverage after selection: an
in-band result is a procedurally locked audit, never an evidence upgrade; the
klein label `confirmed` records protocol completion only. "The arena is the
evidence; the seal is the discipline."

## §7 RQs, priors, tags

As study.yaml `research_questions` (RQ1–RQ5). Scorecard rule: only
`(source: uninformed)` priors are scorable — RQ3(a), RQ3(b), RQ4.

## §8 Claims discipline

study.yaml `claims_discipline` (banned/sanctioned/framing) binds findings.md,
claims.lock, the report, and every talk deliverable. Additions over 07:
open/closed rung, ceiling-closed/fog-closed, headroom, detectable-but-not-
actionable, keep-sized, door-ajar, procedurally-fresh; banned: unscoped
"beat(s) Fisher", bare "significant", "generalizes", any estimation framing of
the coda.

## §9 Feasibility + fallbacks (registered before running)

Compute: ≈4,520 challenger + 480 anchor/control fold-evals, ms-scale except
TabPFN (~0.1 s warm, spike-verified) — < 30 min total; analysis seconds.
TabPFN fallbacks (spike already PASSED, so dormant): roster `nystroem_logit` +
`mlp_bag5`, coda branch-G challenger `gpc_rbf`. Door-ajar branch is pre-scripted
(predictions_to_falsify row 2). If an arena stage crashes irrecoverably, the
study finalizes on the ledger evidence alone with `--allow-exploratory` and the
failure published — the one outcome that downgrades the label.
