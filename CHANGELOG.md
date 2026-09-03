# Changelog

All notable changes to Klein Auto Research. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/); since 1.0.0 the study schema (v2), the `klein`
CLI surface, and the ledger formats are stable — breaking changes mean a major
version.

## [2.0.0] — 2026-09-XX

**Process-verifiable research for AI for Science.** Klein 1.x ran a disciplined
experiment loop; 2.0 makes the whole study auditable by a stranger with no model in
the loop. A study is now TYPED on three axes — `kind` (what shape of question),
`modality` (what shape of evidence), `profile` (whose vocabulary is honest here) —
predictions are registered before their evidence and adjudicated by arithmetic inside
the run transaction, every number in the write-up has a pinned home, and an
independent referee on a different model applies a fixed ten-check rubric before the
study may close.

**Schema 2 is frozen, not migrated.** Studies 03 and 05–09 keep verifying under the
rules they were run under, byte for byte, forever; none of the schema-3 checks are
enforced on them. Version-1 studies stay readable at tag `v1.3.0`.
`docs/migration-schema2-to-3.md` is the contract diff; the short version is: do not
re-open a closed study, start a new one and cite the old one's claims.

### Added

- **The inquiry model** (`references/inquiry-model.md`): `kind ∈ {predict, estimate,
  test, simulate, replicate, discover, optimize}` × `modality ∈ {tabular, timeseries,
  image, sequence, graph, text, simulation, none}` × `profile ∈ {generic, ml-research,
  math, insurance}` or a repo-local `profile_doc`. The kind fixes the default track
  mode, what "sealed" means, what `confirmation.require` defaults to, and the strength
  a claim can reach; the modality selects the data-gate card; the profile changes
  headings, doctrine anchors, figure sets, budgets and banned words — never what the
  engine checks.
- **Schema-3 contract**: `entrypoint {command[], mutable[]}` (the mutable surface is
  declared, not assumed to be `train.py`), `tracks.<id>.mode ∈ {frontier, registered}`,
  a per-track declared `verifier` (required for `optimize`, always outside the mutable
  surface — the checker is never the searcher), `metric.exactness` (+ `exactness_note`),
  `metric.incumbent_external`, `metric.fit_noise` recorded separately from the keep bar,
  `predictions[]` with arithmetic rules, `confirmation.require ⊆ {sealed, replicate,
  verify}`, `stop`, `materiality`, and `data.modality` / `data.source` / `data.sha256`.
- **Typed scaffolding**: `klein new --kind --modality --profile --profile-doc
  --audience --track NAME[:MODE] --split-seed --schema-version`, which names the
  entrypoint by kind (train.py / analyze.py / simulate.py / search.py).
- **Contract-driven splits**: `kleinlib.data.contract_split` / `load_partition` build
  every partition from `study.yaml` alone and print a `split_fingerprint:` the DATA
  gate freezes and the notary compares — a number measured on the wrong rows is a
  crash, in either direction (war story 8).
- **The sealed dry-run**, mandatory before every real sealed run:
  `klein run-one --final-test --dry-run` rehearses the whole path on development data
  and spends no id, commit, manifest, row or seal; an entrypoint that ignores the flag
  exits 3 rather than silently passing (war story 9).
- **Registered mode** (`references/registered-mode.md`): a track that MEASURES instead
  of climbing. Runs are cells, the disposition is `measured`, `artifact:` lines pin the
  tables a cell produces (hashed into the manifest with `role: declared`), and
  guardrails are recorded rather than flipping a disposition. Three cell evaluators —
  `evaluate_estimate`, `evaluate_test`, `evaluate_table` — print the block for the
  common shapes.
- **The predictions ledger**: `klein run-one --tests P#` evaluates each named
  prediction's declarative rule on the printed block INSIDE the transaction and records
  the verdict in the manifest, in state and as an event; `klein predict list` reads the
  ledger and `klein predict adjudicate` records the verdicts only a human can close,
  pinning every path it is given by sha256. `klein finalize` refuses open predictions.
- **REFEREE, Gate 3** (`references/referee-protocol.md`): a fresh context on a
  different model, tool or person reads `findings.md` first and `program.md` last, runs
  the read-only verifiers, applies a fixed ten-check rubric and writes
  `referee_report.md` with two machine-read lines. `klein gate record referee` parses
  them, refuses a FAIL outright, and stores the independence rung; schema-3
  `klein finalize` requires the gate or `--no-referee --reason`, which labels the study
  `unrefereed` on its receipt.
- **The claims lock and the numbers law** (`references/claims-protocol.md`):
  `claims.lock` schema 2 — claims with a class, a strength and resolvable evidence, and
  numbers with a pinned artifact and a precision — produced by `klein claims
  init|pin|number|add|erratum|verify` and checked by a seven-check law (shape,
  artifacts, presence, evidence, numbers, append-only across git history, ancestry).
  Errata re-scope claims; nothing is ever removed.
- **`klein verify` grows a receipt**: `verify_receipt.json`, self-committed, carrying
  every check, the hashes of the inputs the audit read, `evidence_use_rate` and the
  evidence-use law's three numbers. `--numbers` scans `findings.md` (and, always
  advisorily, the tutorial) for numerals with no home in a pinned artifact;
  `--evidence-use` checks that every discard, crash, measured cell and registered sweep
  is cited, that every refuted prediction has a dated `Decision:` line, and that a
  `confirmed` claim rests on two kinds of evidence.
- **Metrology** (`references/consult-protocol.md` Phase 0): `klein noise-floor
  --recipe {seed-sweep, split-lottery, paired-bootstrap} --estimand {fit-noise,
  marginal-resplit, paired-comparison}` prints the contract block, the schema-3 floor
  bar is `minimum_delta >= max(2*std, range/2)`, a paired bootstrap runs under common
  random numbers, and `metrology.family_maxt` is the sign-flip family-wise guard.
  `klein sweep register` hashes a measurement sweep's sidecar and script into state so
  findings can cite it as `sweep:<name>`; `klein stop ack` records a stop rule firing.
- **`klein replicate`** (`references/replication-protocol.md`): a development run
  re-executed from its own manifest in a detached worktree (`rep:E####@<ts>`), or
  `--verify-only` re-running the declared verifier on the pinned artifact
  (`verify:E####@<ts>`), decided on a documented tolerance ladder. Records never touch
  the manifest, and `reproduced: false` is kept as evidence.
- **Data source tags** (`references/data-sources.md`): `csv: | parquet: | synthetic: |
  bundled: | hub: | sklearn: | openml: | url:`, with `data.sha256` mandatory wherever
  bytes can change and `KLEIN_OFFLINE=1` refusing a network scheme before any request.
  `klein doctor` reports what this machine can run without fetching anything;
  `KLEIN_DEVICE` overrides the mps → cuda → cpu order.
- **Modality-typed DATA gate**: a time policy for time series, a group policy for
  images / sequences / graphs / text (with `python -m kleinlib.leakage --index` over
  the split index table), a DGP card for simulations, a verifier card for
  verifier-only studies — and a literal split seed anywhere in an evaluator or
  entrypoint is a BLOCKER.
- **Bundled datasets**: the Hubble 1929 tables (two-source transcription) and a
  deterministic, sha256-pinned tiny Shakespeare corpus, both with licence notes.
- **`kleinlib` split into modules** — `errors, primitives, contract, events, manifest,
  decision, transaction, state, checks` under a thin `workflow` orchestrator — a pure
  move that left every shipped study verifying byte-identically.
- **`scripts/verify_e2e.py`**, a stdlib-only cross-platform proof with two lanes:
  the v1 compatibility path, and a schema-3 lane that walks one typed inquiry from
  `klein new` to a self-contained tutorial with the CLI and nothing else. CI runs both
  on ubuntu, macOS and Windows, plus an `exhibits` job that verifies every schema-3
  exhibit from a clean, offline checkout with `$DATA_HUB` unset.
- **Six protocol code blocks are executed by the test suite**, so a documented example
  cannot drift from the engine it describes.

### Changed

- **The lifecycle is seven stages past four gates**: CONSULT → DATA → METHOD →
  EXPERIMENT/SWEEP → SYNTHESIZE → REFEREE → TUTORIAL. `AGENTS.md`, `CLAUDE.md`,
  `README.md` and the `/klein` skill are rewritten around it, and the agent roster
  gains `klein-referee` (which must run on a different model than the experimenter).
- **`findings.md` §⑤ and the tutorial's coding-advice heading come from the profile**;
  headline numbers in every downstream deliverable are read from `claims.lock`, not
  from prose.
- **Guardrails, floors and stop rules are disclosed rather than silent**: the floor
  block names its estimand, `fit_noise` is recorded under its own key so a seed-only
  spread can never become a keep bar, and a declared guardrail key that no evaluator
  prints is flagged at preflight.
- **`klein replicate` prepares the worktree before the clock starts**: a `uv run …`
  command gets a recorded `uv sync --locked [--extra …]` step on its own budget
  (`KLEIN_REPLICATE_SETUP_SECONDS`, default 1800 s) instead of building the project
  inside `max_run_seconds`, and the prepared DIRECTORY is copied in — not only
  `data.prepared_path` — so an entrypoint that reads a sibling `prepare.py` wrote
  still runs. Both were found by exhibit study 00.
- **A verb commits only the files it wrote.** `klein verify`, `claims`, `predict
  adjudicate`, `replicate`, `sweep register`, `stop ack` and `headroom ack` file their
  own receipts through `git commit --only` and name on stdout the tracked edits they
  declined to take (`note: N uncommitted edit(s) left in the tree (…) — not part of
  this commit`); previously each swept every modified state file into its own commit,
  so a verify on a tree with a findings draft filed that draft under a
  `klein: verify receipt (…)` subject. Gate records, `run-one` and `finalize` still
  file the study artifacts they hash — "commit before the gate", made mechanical.
  Found by the study-00 driver.
- `knowledge/` is reorganised into `knowledge/research-discipline.md` (the ten process
  lessons of studies 07–09, each with a typed claim citation) and
  `knowledge/domains/<profile>/`.
- Version and description: `2.0.0`, "process-verifiable research for AI for Science".

### Removed

- **The v1 ledger adapter and the v1-era skill entry points**: version-1 studies are
  readable at tag `v1.3.0` and are not carried forward. The legacy five-column ledger
  remains documented for historical reading.
- The v1 study-00 quickstart's CI bootstrap, replaced by a marked anchor placeholder
  that fails loudly if the new exhibit lands while the step is still a no-op.

### Compatibility

- `schema_version` selects the rule set. A schema-2 study gets exactly the checks it
  was notarized under; every schema-3 addition is either schema-3-only or an `ok=True`
  `[WARN]`. `scripts/verify_shipped_studies.py` is the guard rail, run in CI: studies
  03, 05, 06, 07, 08 and 09 report 0 failed before and after every engine change.
- `claims.lock` schema 1 (the hand-built numbers ledgers of studies 07–09) verifies
  under its own rules and is never rewritten; `klein claims init --from-legacy`
  migrates a copy for a study that is being re-opened.
- Python 3.11–3.14; `uv sync --locked` with extras named together.

### Studies published in this line

- **07 `iris-90years`** and **08 `iris-rematch`** (2026-08-26/27) — the detection-limit
  pair: a parade at h = 0.81 with no disclosure, then a door ajar at h = 1.015 with
  twenty-one challengers and zero keeps.
- **09 `iris-first-lesson`** (2026-08-27) — the claim-permission map, the 0/42 guard,
  a sealed coda spent by a crash before any data was read, and erratum E1 (a retired
  split seed hardcoded in an evaluator), which the numbers law caught a study later.
  All three were run against the untagged 1.3.0 tree and their locks therefore record
  `klein_version: "1.2.0"`; pin by commit, not by version string.
- The 2.0 exhibits (`00-known-truth-quickstart`, `10-hubble-1929-replication`,
  `11-exact-verifier-construction`, `12-insurance-claims-frequency`,
  `13-charlm-fixed-budget`) ship with this release; their headline numbers below are
  copies of values their locks pin.
  - **00 `known-truth-quickstart`** (2026-09-03) — synthetic tabular data whose
    Bayes-optimal AUC is known (0.884116 on development): three keeps closed the distance
    from 10.4555 measured floors to 1.7077, the sealed look landed 1.68 floors from the
    sealed partition's own ceiling (confirmed), the over-capacity candidate at h = 1.708
    lost 1.7903 floors (P4 refuted, decision recorded), and both `klein replicate`
    attempts failed for non-scientific reasons — the defects E13 fixed.

## [1.3.0] — 2026-08-26

The detection-limit release — merged as `9f87a01` on 2026-08-26 and used by studies
07, 08 and 09, but **never tagged and never recorded here at the time**; the tag
`v1.3.0` was created retroactively on 2026-09-02 with a message naming that defect,
and this entry was reconstructed from the merge. The tree at the tag still says
`version = "1.2.0"` in `pyproject.toml`, which is why the three studies' claims
locks record `klein_version: "1.2.0"`. Pin by commit, not by version string.

### Added

- `metric.bound {ideal, on_infeasible ∈ {ack, warn, block}}` per track and
  `noise_floor.estimand ∈ {marginal-resplit, paired-comparison}` (required once a
  floor block exists beside a declared bound).
- Headroom `h = (incumbent − ideal) / minimum_delta`, computed and disclosed at
  `klein preflight` and `klein verify`, enforced at `klein run-one`: the default
  posture refuses development runs on a keep-infeasible frontier (`h < 1`) until
  `klein headroom ack --note "re-scope: … | run-anyway: …"` records the closed door
  (hash-chained event, self-committed). Nine dedicated tests.
- War story 7 (the sub-zero keep bar, study 07), SKILL Hard Rule 6, the AGENTS.md
  detection-limit invariant, the README headroom section, and the consult-protocol
  headroom bullet.

### Notes

- Born from study 07's parade at h = 0.81 with no disclosure; first exercised by
  study 08 (door ajar at h = 1.015; twenty-one challengers, zero keeps) and armed for
  the first time by study 09 (`bound` declared; h = 0.33, door closed before any
  challenger).

## [1.2.0] — 2026-08-01

The typeset release: the two frictions the 05/06 arc filed are fixed in the
engine, and generated tutorials gain build-time typeset mathematics and
highlighted code — with the zero-network CSP contract byte-identical. All four
public exhibits are re-authored to the new convention and rebuilt; their prose
numbers are unchanged (verified by numeric-multiset diff against the previous
pages).

### Added

- Tutorial builder: build-time math and code rendering. LaTeX authored in empty
  `data-math` / `data-math-display` elements is typeset to inline SVG glyph
  paths (ziamath, STIX Two Math outlines; no fonts shipped, no runtime script —
  `font-src 'none'` and the single-hash `script-src` stand, and the browser
  netlog CI fixture now exercises math and code forever). Pygments highlights
  `language-…` code blocks with pinned dual-theme styles, and
  `<pre data-code="train.py">` includes the winning script BY REFERENCE — the
  included bytes are guaranteed to be the committed file's, so a hand-paste
  can no longer drift (using the idiom remains the spec checklist's job). New
  builder exit codes: 5 math render, 6 code include, 7 renderer dependency
  missing. New dependencies: `pygments`, `ziamath`, `latex2mathml`.
- `klein preflight` check `"guardrail visibility"`: warns when a declared
  guardrail metric is neither auto-printed by the framework
  (`kleinlib.schema.AUTO_PRINTED_METRIC_KEYS`) nor named anywhere in the
  study's Python sources.
- A ledger-derived seal guard in `klein run-one --final-test`: a sealed access
  recorded in the hash-committed manifests refuses a second access even if
  `study_state.json` was edited afterwards.

- Study `06-hurricane-gqls-returnlevels` (fourth public exhibit): from-scratch
  reproduction of Adjieteh (2024) §6.2.2 — gQLS loss-model fitting on the 30
  most-damaging US hurricanes (Pielke-Landsea 1998; the 30-row dataset is
  bundled under `datasets/`, making this the repo's most reproducible study).
  Sealed evidence is the thesis's own published Table 6.10 grid (120 parameters,
  reproduced at 0.002 mean absolute deviation) plus its exact 10× contamination,
  under which the study's decision incumbent (trimmed gQLS-lognormal, wide trim)
  holds the 1-in-100 event loss to 0.0% while untrimmed MLE moves +99.4%. The
  loop's reproduction ladder discovered the thesis's own ch. 2 quantile
  convention via an honest guardrail breach, localized a typo in one printed
  Table 6.9 cell, and recorded that the best-fitting family (log-Cauchy, no
  finite moments) is decision-degenerate at this sample size.
- Bundled dataset `hurricane_top30_pl1998` (30 rows, provenance-documented,
  including the source's own "1925–95"-vs-1900–95 label trap).
- Study `05-fremtpl2-gap-forensics` (third public exhibit): the two-track
  sealed-gap redesign that study 04 (archived at [1.0.0]) queued as future
  work, executed. Each track owns one sealed final-test access, so the
  GLM-vs-GBDT headline is a difference of two sealed numbers (0.009564 = 9.3×
  the sealed paired-bootstrap SE; confirmed). Forensics layer: train-fold
  surrogate distillation, segment deviance attribution, manual 2-way partial
  dependence; deliverables include a claim-cited
  dataset-characteristics → method-choice `checklist.md`. Two framework
  frictions filed from the run (guardrail-metric print visibility; post-scaffold
  track top-up in `final_holdout_access`) — see the study's `program.md` and
  findings §⑦.

### Fixed

- F1 (study 05, E0001): every evaluator now prints a `wall_seconds:` aux line
  — the runner's guardrail check reads the PRINTED block, and the sidecar-only
  `wall_seconds` discarded an anchor-exact candidate. Callers that already
  pass `wall_seconds` via `extra=` keep byte-identical stdout.
- F2 (study 05, E0012; hand-patched again in study 06): `load_state` now tops
  up `final_holdout_access` from the current contract in memory (never
  deleting or overwriting a recorded access), so a track added to `study.yaml`
  after scaffolding no longer strands the sealed gate.

### Changed

- All four exhibits' report fragments re-authored to the typeset convention
  (three divergent math notations retired); reports rebuilt. Studies 00 and 03
  additionally gain the full winning `train.py` by reference — study 03's
  coding-advice section previously shipped no code at all.
- Report code typography: `pre code` line-height 1.55 → 1.4, 14px → 13.5px
  (the prose-tuned spacing read as "double-spaced" in code blocks).
- `tutorial-spec.md` reworked: the bundled builder is the route of record (all
  shipped exhibits were built by it); the external-renderer route is optional
  and currently non-conforming (runtime KaTeX, no CSP); new authoring
  conventions + validated LaTeX subset documented; war story №6 added (the
  unprinted guardrail).

## [1.1.0] — 2026-07-31

The slim release: public `main` becomes the reader-first product — two executed
exhibits (the bundled-data ML quickstart and the schema-v2 math/optimization
study), the engine, the protocols, and nothing a first-time reader must climb
over. **Nothing is lost:** everything removed is preserved intact at tag
[1.0.0], where every recorded candidate commit resolves — historical references
in earlier entries resolve there too.

### Removed

- Studies `01-dae-claims`, `02-rqls-pv-severity`, and `04-fremtpl2-frequency`
  plus the archive docs — `docs/lineage/`, `docs/benchmarks/`, the three
  pre-1.0 dated reviews, and the pricing eval-card worked example
  (137 files, ~3.2 MB). All preserved at tag [1.0.0].

### Changed

- CI retargeted step-level, no check renamed: core/integration pytest and ruff
  paths, the v1-verify loop (study 00 is the only remaining v1 exhibit), the
  Study-02 reproduction anchor dropped (anchors 00 and 03 remain), scheduled
  jobs run the engine suites.
- README quickstart and CONTRIBUTING commands match the slimmed tree; the
  knowledge method cards distilled from archived studies carry archived-source
  notes — knowledge outliving its source studies is the promotion loop working
  as designed.
- Commit-message trailers normalized across `main` (authorship-metadata
  cleanup); tags v0.1.0–v1.0.0 keep the original pre-normalization history,
  through which all recorded study candidate commits resolve.

### Added

- Framework tests for `kleinlib.data.load_xy` and
  `kleinlib.data.feature_column_groups`, previously exercised only through an
  archived study's suite.
- `.gitattributes` marking generated tutorial HTML as `linguist-generated`.

### Docs

- ML/Math positioning aligned across README, package metadata, and
  CITATION.cff (math labs run under `task_type: simulation`; study 03 is the
  exemplar); repo topics gained `optimization` and `simulation`.

## [1.0.0] — 2026-07-31

The universality release: what v0.4.0 could do, now proven portable and frozen.
The driver matrix is re-verified live
[`docs/reviews/2026-07-31-v1.0-driver-matrix.md`], a CI guard keeps normative
text machine-agnostic, and the pre-1.0 caveats are retired: the study schema
(v2), the `klein` CLI surface, and the ledger formats are stable from here.

### Added

- **Universality guard** (`scripts/tests/test_universality.py`, riding the core
  and integration CI jobs): tracked `*.md`/`*.py` must contain no machine-local
  strings — absolute home paths, the author's machine username, local workspace
  names. `docs/lineage/` archives and the frozen study ledgers stay exempt per
  the evidence doctrine: immutable records are never edited.
- **Driver-matrix evidence doc**
  (`docs/reviews/2026-07-31-v1.0-driver-matrix.md`): two NEW live smokes —
  Codex CLI 0.145.0 derived the doctrine-correct locked command from
  `AGENTS.md` alone; Copilot CLI 1.0.75 drove the same verification through
  `.github/copilot-instructions.md` under a granular shell-only permission —
  both returning grounded 15-check reports with clean trees; plus the two
  prior live proofs (Claude Code provenance; local Qwen-GGUF over llama.cpp's
  native Anthropic endpoint) and doc-verified rows for Gemini CLI, Qwen Code,
  and the `AGENTS.md` auto-reader ecosystem, sources cited with access dates.

### Changed

- **Stability of record**: version 1.0.0; classifier
  `Development Status :: 5 - Production/Stable`; the preamble's "0.x means the
  contract may still move" clause retired. Breaking changes to the study
  schema, the CLI surface, or the ledger formats now require a major version.
- **Foreign-repo pins** point at `v1.0.0` (the SKILL.md install line — now
  carrying the stability statement — plus the study pyproject template and the
  preflight hint).
- `CITATION.cff` cites 1.0.0 and gains the previously missing `date-released`.

### Docs

- README and `AGENTS.md` driver rows for Gemini CLI / Qwen Code updated to the
  current nested `context.fileName` settings key (per both CLIs' official
  docs — the legacy flat `contextFileName` key is gone); both files now link
  the driver-matrix evidence doc.
- README states the 1.0 stability promise at the pin advice and under
  § Lineage & citing; `SECURITY.md` clarifies that "supported" means receiving
  security fixes.

## [0.4.0] — 2026-07-31

The integration release: a real-data soak (study 04) filed six frictions
[F1–F6, `docs/reviews/2026-07-31-v0.3-soak.md`] and every one is closed here —
plus the optional-accelerator seams that let a personal research harness
compose with Klein without Klein depending on it.

### Added

- **Exposure-weighted deviance metrics** [F1]: `val_poisson_deviance` /
  `val_gamma_deviance` / `val_tweedie_deviance` join the registry under the
  exposure-weighted-rate convention (y = rate, `sample_weight` = exposure);
  `evaluate_regression` threads optional strictly-positive weights into
  RMSE/MAE/R² too, refuses out-of-domain values with clip-in-train.py guidance,
  and reports `calibration_ratio` on deviance primaries. Tweedie declares its
  `power` in the track contract (1 < power < 2, validated) and the evaluator
  echoes it as an aux line, so drift is manifest-visible.
- **Sanctioned smoke mode** [F2]: `KLEIN_SMOKE=1 python train.py` executes the
  full path while evaluators skip every sidecar/snapshot write; the scaffold's
  refusal message now teaches this instead of listing fakeable variables, and
  `run-one` force-clears the flag in the child so ambient smoke can never
  suppress real evidence.
- **Empty-diff guard + restore anchor** [F5]: `run-one` refuses an accidental
  rerun of the incumbent configuration before any experiment id, run dir, or
  commit exists (`--allow-rerun` makes intentional replication first-class;
  sealed final tests and `--command` overrides stay exempt; executed empty
  diffs carry `empty_candidate_diff: true`), and after every non-keep the CLI
  names the base commit train.py was restored to and the incumbent whose kept
  config that equals (now recorded in manifests as `incumbent`).
- **Real-data noise-floor recipe** [F4]: the consult protocol distinguishes the
  fit-seed floor, the marginal fold-bootstrap floor, and the paired-difference
  bootstrap floor for comparison studies (common-random-numbers language), and
  the `noise_floor:` block gains an optional `method:` provenance field
  (`seed-sweep` | `paired-bootstrap`) emitted by `klein noise-floor`.
- **Comparison-study guidance** [F6]: decide at CONSULT how a gap gets its
  sealed number — one track per model family, or pre-registered
  exploratory-by-construction; the CLI and summaries label the sealed
  confirmation "sealed" while its recorded disposition stays `discard`.
- **`kleinlib.eval.save_holdout_predictions`**: the per-row holdout table hook
  (`y_true`/`y_pred`/`weight` + rating dims + optional second model) under the
  new gitignored `predictions/` convention — the export path for external
  eval tooling, complementing `models/latest_val_preds.npz`.
- **Optional-accelerator seams**, each existence-checked with the bundled
  fallback named (the dataset-profiler pattern): a pricing eval-card generator
  at SYNTHESIZE (worked example: `docs/integrations/pricing-eval-example/`,
  built from study 04's incumbent; fallback `standard_regression_report`),
  knowledge-vault Q&A and paper-filing at METHOD, practice-leg satisfaction by
  citation of a from-scratch nano, a corpus synthesizer for cross-study
  writeups, and outward promotion from `knowledge/` to personal vaults with
  typed claim citations intact.
- **Model backends note** (`AGENTS.md`): any driver runs over a subscription
  agent CLI or a local model behind an OpenAI-compatible /
  Anthropic-Messages-compatible server; Klein itself calls no model APIs and
  requires no keys.
- **Study `04-fremtpl2-frequency`** — the real-data soak exhibit (678k-row
  freMTPL2 claim frequency, GLM vs GBDT): the paired-floor methodology live
  (three defensible floors differing 25×), a keep decided by 0.000002 over the
  declared delta, an accidental bit-identical replication proving end-to-end
  determinism, and a sealed level confirmation at 0.65× the fold SE.

### Fixed

- **Leakage audit covers simulation and deviance studies** [F3]: real split
  kinds on simulation contracts reproduce as regression-shaped splits,
  `kind: none` reports N/A instead of failing, custom simulation metrics get
  their declared direction, and the deviance family gains chance scorers
  (constant train-mean = the null model; shuffled must not beat it). Study
  04's committed contract now audits clean end to end, as-is.
- **Gate records sweep `sweeps/`** [papercut]: measurement-sweep sidecars are
  filed by the next gate/phase/finalize state commit instead of stranding the
  tree dirty for the following `run-one`.

### Docs

- `docs/lineage/` — the agent-smith ancestry archive (quality audit +
  campaign optimization notes, verbatim) with the ancestry README.
- The v0.3 soak review joins the review series in-repo.
- Data-auditor profiler fallback harmonized to the module CLI
  (`python -m kleinlib.profile_fallback`, csv/parquet).

## [0.3.0] — 2026-07-30

The distillation release: v0.2's hardening adopted, audited live, and slimmed —
plus the researcher-value layer and a fourth executed study proving the v2
contract end to end.

### Added

- **Simulation studies are first-class** (`task_type: simulation`): custom
  scalar metrics with explicit direction, `split.kind: none` with seed-block
  comparability — math/optimization/Monte-Carlo labs now express under v2.
- **Measured noise floor**: `klein noise-floor` + a Phase-0 k-seed measurement
  sweep turn `minimum_delta` into a measured quantity; the contract validates
  the `noise_floor:` block, preflight fails a delta set inside its own floor,
  and summaries state deltas as multiples of the floor std.
- **Rolling playbook** (`playbook.md`): the map the loop re-reads before every
  candidate — current best / ruled out with evidence / open hypotheses /
  next-best candidates; refreshed and hash-recorded at every phase
  acknowledgement, staged into evidence commits, mined as synthesis source 5.
- **Phase-start slate ritual** (`references/phase-ritual.md`): 4–6 scored
  falsifiable candidates before spending any run — procedure, not Elo.
- **Clean-room leakage audit** at the DATA gate: a four-check card table run in
  a fresh context, with `python -m kleinlib.leakage` mechanizing split
  contamination and eval-harness chance checks.
- **Decision-trajectory figure** (`kleinlib.figures.plot_decision_trajectory`):
  the keep/discard/crash journey per track with phase bands, minimum-delta and
  noise-floor bands, the sealed confirmation star — embedded in summaries and
  tutorials, with a declared log scale on extreme ranges.
- **Theory+Papers+Practice triad** on method cards, gate-checked; **stable
  claim IDs** (`<study_id>#Cn`) with typed `supports/refutes` citations
  required at knowledge promotion; RQ priors name their source and findings
  score knowledge-sourced priors against uninformed ones.
- **Study `03-noisy-rosenbrock-dfo`** — the v2 contract's live acceptance test:
  7 experiments (2 keep / 4 discard / 1 crash, all candidate commits
  resolvable), a measured floor governing dispositions, one sealed fresh-seed
  confirmation that replicates, findings C1–C7, self-contained tutorial.
- `docs/reviews/2026-07-30-v0.2-adoption-audit.md` — live behavioral audit of
  the v0.2 hardening: every P0 mechanism verified by driving it, 20 defects
  found and dispositioned (A19 journal-hash freeze and A20 phase-ladder drift
  were caught by real use during this release).
- v2 phase telemetry: `summarize_results.py` renders per-phase experiments and
  wall-seconds from `runs/E####/manifest.json` against the contract's budgets.
- Preflight warns on scaffold stubs in `train.py`, validates declared noise
  floors, and catches contract/state phase-ladder drift.
- Help text on every `klein new` / `klein gate` flag.
- CHANGELOG (this file), canonical diagrams under `docs/diagrams/`.

### Changed

- **CLI verbs file their own receipts**: `klein gate record`, `finalize`, and
  `recover` commit the state files they write; derived views
  (`results_summary.md`, `progress.svg`, `figures/`) never block `run-one` and
  are swept into the next state commit. The documented loop no longer dead-ends
  on a dirty tree the CLI itself created.
- Scaffold's default `prepared_path` is CSV (parquet stays one
  `--prepared-path` away) — the core install can pass its own DATA gate.
- Data-card decision regex accepts markdown headings (`## Decision: GO`); gate
  errors name the accepted forms and explain override semantics.
- GBDT smoke fits self-isolate in subprocesses, so the default `pytest`
  collection is safe even with torch loaded (macOS arm64 dual-libomp war story
  enforced by construction; CI's three-process choreography removed).
- Dev tools moved to a default dependency group — `uv run --locked pytest`
  works as documented; default pytest collection covers framework paths only.
- The strong-claim prose lint in `finalize` is a loud warning; the
  exploratory/confirmed label check stays hard.
- `AGENTS.md`/`SKILL.md` teach the loop as three layers: the loop is yours
  (judgment) / `run-one` is the crash boundary (notary) / state files are
  receipts. Stage names and CLI verbs are mapped explicitly.
- Version is single-sourced from package metadata.

### Removed

- `kleinlib/keep_awake.py` (unused mouse-jiggler; `caffeinate -i` is the
  documented path).
- `klein migrate` — folded into `klein verify` (v1 errata print there; nothing
  was ever migrated).
- The embedded schema fallback in `preflight.py` and the five drifted asset
  templates — `kleinlib` is the single source for schema and scaffold templates.
- Dead code (`ensure_uv_locked_command_available`), the hardcoded CLI version
  string, and a stale `VIRTUAL_ENV` leaking uv warnings into archived run logs.

## [0.2.0] — 2026-07-12

The hardening release, implementing
`docs/reviews/2026-07-10-v0.1-review.md` (4 P0 / 6 P1 / 2 P2): the `klein` CLI;
transactional evidence (per-run `manifest.json`, append-only self-verifying
`events.jsonl`, `study_state.json`, `StudyLock`, atomic writes); candidate
commits before execution so negative evidence stays resolvable; a subprocess
crash boundary with real exit codes (124 on timeout); per-track frontiers with
declared direction/minimum-delta/guardrails; a sealed one-access final-test
partition with exploratory/confirmed labeling; stateful preflight (exact
branch, gate acknowledgements, artifact and split fingerprints); metric specs
that reject non-finite values; collision-proof relocatable snapshots; sweep
sidecar hardening with resume; a 7-job CI (Python 3.11–3.14 matrix, ≥80%
engine coverage, tutorial network isolation, reproduction anchors, macOS +
Windows CLI portability, clean-wheel install) plus a weekly scheduled audit
with an Apple-silicon MPS canary; `SECURITY.md`, `THIRD_PARTY_NOTICES.md`,
standard MIT `LICENSE`.

## [0.1.0] — 2026-07-10

First public release: the six-stage lifecycle (CONSULT → DATA → METHOD →
EXPERIMENT/SWEEP → SYNTHESIZE → TUTORIAL) with hard gates; `kleinlib` engine
(schema single-sourcing, data/split contract, evaluators with a collapsed-
prediction guard, 15 figure functions, snapshotting, the sanctioned
`SweepRunner` escape-hatch); the `/klein` skill with 8 reference protocols and
war stories; tool-neutral `AGENTS.md`; seed `knowledge/` base; bundled
Apache-2.0 insurance-claims dataset; three executed exemplar studies
(GLM quickstart, DAE honest-no, robust-QLS synthetic lab).

[1.2.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v1.2.0
[1.1.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v1.1.0
[1.0.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v1.0.0
[0.4.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.4.0
[0.3.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.3.0
[0.2.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.2.0
[0.1.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.1.0
