# Changelog

All notable changes to Klein Auto Research. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/): a breaking change to the study schema, the `klein`
command line, the JSON envelope or the ledger formats means a major version. Releases
before 2.0 are in [`docs/history/CHANGELOG-1.x.md`](docs/history/CHANGELOG-1.x.md).

## [3.0.0] — 2026-11-17

**From a notary to a research instrument.** The kernel's judgment is unchanged — the
eight shipped exhibits verify with the same checks, passes and warnings as under 2.3.1.
What changed is everything around it: one schema, a smaller and extensible engine, an
installed package that needs no checkout, one machine-readable shape for every verb, and
three new verbs for exploring and understanding a study. The rationale is
[`docs/design/klein-3-design.md`](docs/design/klein-3-design.md).

### Breaking

- **The engine reads and judges schema 3 only.** A schema-2 or version-1 study is refused
  once, by every verb, with the tag and the commit where it still verifies (`v2.3.1` =
  `217cd46`, `v1.3.0` = `9f87a01`).
  Nothing notarized was rewritten. `klein new --schema-version` and
  `scaffold_study(schema_version=2)` are gone; lock schema 1 ledgers are no longer
  written to or migrated (`klein claims init --from-legacy` remains readable history at
  the tag).
- **`--json` output is an envelope.** `klein status --json`, `next --json`,
  `doctor --json`, `refs verify --json` and `predict list --json` used to print bare
  data; each now prints `{"klein", "format": 1, "verb", "ok", "data", "problems"}` with
  the old payload under `data` (`predict list` → `data.predictions`, `refs verify` →
  `data.references`).
- **Function signatures that carried a schema version lost it:**
  `checks.floor_bar_problems(metric, floor)`, `claims.claims_checks(study_dir, …)`.
  `workflow._legacy_results_problems` is removed.
- **Nine studies left the working tree** (03, 05, 06, 07, 08, 09, 13, 15, 24) with the two
  datasets only they used. They are indexed, with their claim ids, in
  `studies/ARCHIVE.md` / `studies/archive.yaml`, and recoverable from commit `217cd46`.
- **A sealed run requires its rehearsal.** `klein run-one --final-test` is refused unless
  the track's latest `--dry-run` rehearsal exited 0, did not time out, printed its
  acknowledgement and a metric the notary can judge, ran the same command over the same
  mutable surface and the same scripts that command names, and fits the time the sealed
  run is allowed (the `sealed_dryrun` event now records the digests). A rehearsal that
  prints no `primary_metric:` line now fails with exit code 4. An entrypoint with no row
  partition acknowledges a rehearsal with the new `kleinlib.data.sealed_dryrun()`. The rule is one function,
  `kleinlib/rehearsal.py`, shared by the notary and `klein next`; there is no bypass
  flag. A study mid-flight rehearses once more. Until now the rehearsal was mandatory
  by protocol only, and one that timed out counted as done (war story 11).
- **The generation layer's protocols and templates moved** to `references/generation/`
  and `assets/generation/`. `klein explain <name>` is unchanged; a generation manifest
  written before the move reports a protocol-hash drift warning.
- `kleinlib/cli_generation.py` is now the package `kleinlib/generation/cli/`; the wheel
  no longer ships `kleinlib/tests` or `kleinlib/_profiles` (profiles are under
  `kleinlib/_skill/references/profiles`).

### Added

- **`klein demo`** — builds a tiny study in its own git repository and runs the first half
  of the lifecycle live, with real gates and real runs, in about 15 seconds, offline, from
  a checkout or from an installed wheel.
- **`klein probe`** — exploration on the record: one bounded command, appended to a
  hash-chained `probes.jsonl` and witnessed by a `probe_recorded` event in the study's
  event chain, fenced from the sealed partition (`KLEIN_PROBE=1`), never evidence for a
  claim (nothing under `probes/` can be pinned). The first consult record anchors how
  many probes preceded it; `klein verify` fails a ledger that was edited, truncated or
  deleted. Protocol: `references/exploration-protocol.md`.
- **`klein map`** — the study as a graph: questions, predictions, runs, claims and
  decisions, the links between them, what is still `open`, and the `leads` a follow-up
  would start from. Text, `--json`, or `--html` (one self-contained page). Also an MCP
  tool. A prediction may name its question (`question: RQ1`).
- **`klein explain`** — any protocol, profile, template or glossary term, from any
  directory. **`klein skill install`** copies the skill and the worker agents into a
  repository. **`klein summarize`** and **`klein report build`** run the two report
  scripts from wherever Klein is installed.
- **`--json` on every verb** and **`kleinlib.api`**, a stable Python surface returning the
  same envelope and never printing (engine notices come back as `warn` problems); it
  includes `sealed_dry_run`, the rehearsal a sealed run requires. `klein next` adds `stage_id` (a closed vocabulary),
  `argv` (the command as a runnable list, when complete) and `explain`.
- **JSON Schemas** for the envelope and for each structured verb's `data`
  (`kleinlib/_schemas/`, draft 2020-12), printed by **`klein schema [name]`** and
  validated against real output in the test suite. The engine itself depends on no
  validator. Within `format: 1` keys are only ever added.
- **A plug-in seam** (`kleinlib/plugins.py`, entry-point group `klein.plugins`): a plug-in
  may add verbs, audience profiles, evidence modalities and read-only MCP tools — never
  anything that changes how a run is judged. The generation layer is loaded through it.
  A plug-in that fails, or reaches for a core verb, is undone; `klein doctor` reports
  what loaded and what failed; a receipt names third-party plug-ins that were loaded.
- **A Claude Code plug-in** (`.claude-plugin/`): the skill, eight agents, a `bin/klein`
  launcher and the read-only MCP server, installable into any project.
- **One registry for the inquiry model** (`kleinlib/inquiry.py`): kinds, modalities and
  profiles as data. No engine module branches on one by name.
- **A glossary** (`references/glossary.md`), a generated command reference
  (`docs/cli.md`, with a freshness test), `docs/embedding.md`, and a rewritten README and
  quickstart.
- The whole skill — protocols, templates, profiles, report scripts, worker agents and the
  operating manual — ships inside the wheel.

### Changed

- The opt-in generation layer's commands are split one module per capability; its tests
  live in `kleinlib/tests/generation/`. Its protocol hashes and benchmark schema resolve
  through `kleinlib/resources.py`, so they work from an installed wheel.
- Every core verb is a handler function; the 250-line dispatch chain in `kleinlib/cli.py`
  is gone. `kleinlib.calls` uses the one `canonical_json`.
- **Throwaway repositories never sign.** The test suite (root `conftest.py`), `klein demo`
  and `scripts/verify_e2e.py` switch commit signing off for their own repositories:
  under `commit.gpgsign = true` the suite called the signer once per commit. A real
  study keeps the researcher's signing settings.
- The weekly workflow also runs when a pull request changes it.
- `AGENTS.md`: exploration is a sanctioned off-loop path; the verb list and the war
  stories point at their single sources.
- CI: the package job proves the installed wheel is self-sufficient (explain, skill
  install, the envelope, an MCP round trip) and byte-identical to the repository's skill;
  the `--help` smoke walks the parser instead of a hand-kept list.
- `scripts/verify_e2e.py` has one lane: the version-1 lane is gone, and the remaining
  proof now also exercises `klein summarize` and `klein map`. The two report scripts read
  schema 3 only.

### Fixed

- `summarize_results.py` rejected every schema-3 study (`unsupported study.yaml
  schema_version: 3`); it now reads them.
- The README quickstart committed a verify receipt into the reader's clone; it now uses
  `--no-receipt`, and `kleinlib.api.verify` reads by default.
- The README's noise-floor example used an estimand that yields no keep bar.
- The release workflow's package-data check looked for a directory that did not exist and
  passed silently; a missing directory now fails the release.
- `scripts/check_generated_tutorial_network.py` scaffolded an untyped fixture and failed
  on every run (a test had been masking it); `scripts/check_shipped_reports.py` rejected a
  long code line that the print stylesheet had correctly wrapped.
- CI's exhibit job decided whether to run `prepare.py` from an exit code, so an
  unparseable `klein doctor` read as "skip"; the answer is now printed and a parse error
  fails the step.

- **CI, Windows:** a step that walks the parser was a bash heredoc run under PowerShell;
  it failed and skipped the full Windows suite behind it.
- **The weekly job, red on `main` since 2.3.0:** study 23's replication was asserted
  bit-identical on a different CPU, where an iterative logit moves 6e-7 relative; the job
  now states the tolerance the study's contract declares (one cent). The MPS canary asked
  for a runner image GitHub retired on 2026-11-02. Study 20's replay step never prepared
  its data, which only showed once the steps before it passed.
  Study 22's CNN run reproduced to the last digit on one runner and moved 0.003 on another,
  against a 0.001 analysis resolution; across machines the job now asserts the run's own
  recorded seed-to-seed standard deviation.
- `replication-protocol.md` gave the tolerance ladder in the wrong order (`exact` is
  checked before `minimum_delta`), and it and the replicate message told the reader to
  compare fields no record holds.
- **Windows: a bare `python` in a contract ran the wrong interpreter.** Windows looks a
  program up in the running program's own directory before `PATH`, and inside a virtual
  environment that is the base interpreter's. `klein demo` and every study scaffolded
  with `--runner python` crashed there. The engine's one launch point now resolves a bare
  program name on the child's `PATH`, as POSIX always did; the command is recorded as the
  contract wrote it. Found by the first full Windows run of the suite on 3.0.
- `klein next` suggested a command that split in two when the study path held a space.
- `klein demo`'s interpreter shim could not work on Windows.

### Known limitations

- Every study still runs the whole lifecycle; a declared quick-look tier is the next
  release's main item (design doc §7).
- A probe's fence covers Klein's row-partition loaders. A script that opens raw files
  itself, or a simulator that picks its own sealed seeds, is recorded, not stopped.
- A plug-in is installed code in the same process: Klein prevents shadowing and undoes a
  failed plug-in, but cannot sandbox one.
- The rehearsal rule covers the command, the mutable surface and the scripts the command
  names. It does not cover library code the command does not name (`lib/`,
  `prepare.py`), a declared verifier, or a detached host; and it reads the event chain,
  which is tamper-evident, not tamper-proof (a forged or tail-truncated event satisfies
  it). The guard is against a hurried honest run, not a forger.
- An `exact` metric replicates bit for bit on the machine that ran it; across machines a
  replication states its tolerance (`--tolerance`). The engine does not yet record enough
  of the environment (CPU, BLAS, threads) to explain a cross-machine difference.
- `bin/klein` (the plug-in launcher) is a POSIX shell script and needs `uv`.
- Recipes do not yet scaffold the Phase 0 noise-floor script; `klein demo` leaves a
  working example.
- What ran for this release: GitHub CI on Linux (Python 3.11–3.14, the torch + GBDT
  suite with the coverage floor, the exhibits, the wheel), macOS and Windows (end to end;
  the full suite on Windows). Hosts exercised live: Claude Code (this repository and
  `claude plugin validate`). The Claude Science kit is documented against that product's
  published documentation and was not re-run.

## [2.3.1] — 2026-11-03

A follow-up to 2.3.0 that fixes the PyPI page and closes two of its known limitations.
No rule a shipped study is judged under changes: both additions are silent unless a
study opts in or declares the field they read.

### Fixed

- The README uses absolute URLs for its images and links, so the PyPI project page
  renders the lifecycle, loop and Klein-bottle diagrams (relative paths resolved only on
  GitHub).

### Added

- `policy: {numerals: identifier-aware}` — an opt-in for the numbers law: a digit run
  glued to a preceding letter (`GSM8K`, `qwen2`, `A003022`) is part of a name, not a
  number. A hyphen still separates and a trailing unit still scans. The default stays
  `literal`, so every shipped receipt is unchanged; an older engine refuses the key
  instead of misjudging the study.
- `klein preflight` warns when a study declares `calls:` without `calls.price` (every
  call would record `usd: 0`, unrecorded rather than free, and `budget_usd` would be
  refused). `klein verify` does not add the row, so verify receipts keep their checks.

## [2.3.0] — 2026-11-03

Klein 2.2 notarized research on tables well and on everything else by workaround: a
binary evaluator, a whole-log metric channel, one input file, wall-clock budgets only,
a blocking wrapper as the only remote compute, and a Claude Science row that was a
paragraph. 2.3 keeps the trust kernel exactly as it was — the notary transaction, the
hash-chained events, manifests, the claims law, the predictions ledger, the referee
gate, the verify receipt — and grows domain packs and host bridges around it, so a
study in computer vision, deep-learning training, LLM evaluation, data science or
mathematics is a first-class Klein study. Every shipped study re-verifies unchanged:
new behaviour lives only in contract fields 2.3 scaffolds write (an older engine
refuses such a study loudly instead of misjudging it), and a manifest records a
non-default rule only when it applied.

### Added — guided onboarding

- **`klein next [--study S] [--json]`** — the ONE next action a study needs: its stage,
  what is done, the exact command, the protocol section and why. Strictly read-only.
  **`klein status --json`** beside it.
- **`klein new --recipe <domain>`** — `tabular-predict`, `cv-classify`, `dl-scaling`,
  `llm-eval`, `ds-causal`, `math-verify`: kind / modality / profile / metric / split,
  the 2.3 contract blocks and a `policy:` block pre-filled, and a `prepare.py` +
  entrypoint (+ verifier) that smoke offline — with `{{…}}` placeholders wherever
  judgment is required, so a gate still refuses a rubber stamp. Explicit flags win
  over the recipe. **`--runner python`** writes `python -u …` commands for hosts
  without uv.
- **`klein claims apply claims.yaml`** — artifact pins, numbers and claims in one
  all-or-nothing file.

### Added — the metric channel, data and evaluation

- **`entrypoint.printed: block`** — metrics are read from the last line that is
  exactly `---` to the end of the log, so training chatter (`loss: nan`, `epoch: 3`)
  can neither crash nor pollute a run; a log without the opener is a crash. The
  manifest records `printed_scope` and replication follows it.
- **Index-table splits** (`data.split.index`, `id_column`, `label_column`,
  `split_column`) for images, text, sequences and graphs, and **`kind: predefined`**
  for official partitions (MedMNIST, GSM8K): real fingerprints over item ids, enforced
  at every run. `kleinlib.data.load_items()` hands an entrypoint its partition's ids.
- **`data.inputs`** for multi-file studies and **`hf:<owner>/<repo>@<commit>/<path>`**
  pinned Hugging Face sources; `klein doctor --study` reports one line per file.
- **Near-duplicate and contamination audits** — `python -m kleinlib.leakage --index …
  --near-dup image|text [--against <pool>]`: 64-bit dHash for images, normalized
  13-gram overlap for text.
- **`policy:`** — strictness-only knobs: `card_sections: enforce` (the modality's data
  card headings, plus `Near-duplicate audit` for image/text/sequence/graph and
  `Contamination audit` for the `llm` profile), `realized_split: required`,
  `noise_floor: required`.
- **Evaluators**: `evaluate_multiclass` (accuracy, balanced accuracy, macro-F1, top-5,
  log-loss, ECE; confusion table pinned; a one-class collapse guard), `evaluate_items`
  (exact match, pass@k with the unbiased estimator, per-item tables, cluster bootstrap),
  ranking (NDCG@k, MRR, recall@k), survival (Harrell's C) and segmentation (mIoU,
  Dice). Metrology: exact McNemar, paired item bootstrap, seed-by-item variance; the
  `item-bootstrap` and `resample` floor recipes.
- **Profiles** `llm`, `cv`, `data-science` (eight sections each, banned words included);
  `ml-research` deepened as the deep-learning profile. Five new seed method cards.

### Added — execution

- **Seed arrays** (`entrypoint.seeds: [0, 1, 2]`): one candidate is N children with
  `KLEIN_SEED`; the notary decides on the mean, records std / min / max and pins
  `runs/E####/seeds.tsv`. A contract field, never a flag, so N cannot be chosen after
  seeing results.
- **Usage and budgets** — a child reports steps / tokens / calls / USD with
  `kleinlib.dl.report_usage`; `manifest.usage` and `execution.hardware` are recorded
  for every exit status, and `phases[].budget_steps|tokens|usd` are enforced beside
  `budget_seconds`. `kleinlib.dl`: `seed_everything`, `hardware_report`, an atomic
  `Checkpointer`. `SweepRunner(workers=N)`.
- **The model-call ledger** (`kleinlib.calls.CallLedger`, stdlib only): a
  content-addressed record of every request and response (`calls/E####-NNN.jsonl.gz`,
  deterministic shards, secrets scrubbed), a hard budget that crashes honestly,
  `KLEIN_OFFLINE=1` cache-only replay, and pinning on every exit status.
  **`klein replicate --replay`** re-runs offline from the pinned ledger (a `replay:`
  record, never counted as a replication); plain `klein replicate` re-queries with
  salted keys. No Klein verb imports it.
- **Detached runs** (opt-in, `entrypoint.execution: [local, detached]`):
  `klein run-one --detach` files the candidate and a job bundle and freezes the study;
  **`klein job exec`** runs it on any host and writes a receipt; `klein run-one
  --collect` checks the receipt against the committed job and judges the run locally,
  recorded as attested, not observed; `--abandon --reason` closes one that never
  returns. `verify`, `finalize`, `recover` and `next` all know about an open one.

### Added — host bridges

- **`integrations/claude-science/`** — install (PyPI wheel, or uv with
  `UV_PROJECT_ENVIRONMENT`), project instructions, `klein-researcher` and
  `klein-referee` Specialists, Reviewer criteria (a pre-referee pass, never Gate 3),
  remote compute via SSH/Slurm and Modal job cards, artifacts.
- **`klein mcp`** — a stdlib, read-only MCP server over stdio (`list_studies`, `next`,
  `status`, `doctor`, `preflight`, `verify` without a receipt, `predictions`,
  `claims_verify`, `explain`). No gate or run tool, by design.
- **`klein refs verify [--record]`** — resolve every DOI (Crossref, OpenAlex) and arXiv
  id in `references.yaml` and compare titles; opt-in network, never imported by verify;
  `--record` is a comment-preserving edit that never overwrites a human verification.
- **`klein notebook E####`** — a run as a reading-copy `.ipynb` of the executed source
  at its candidate commit plus its printed block.
- **`klein doctor --host claude-science|claude-code|generic`**.
- The audience profiles ship inside the wheel, so a PyPI install keeps the vocabulary
  scan; CI asserts byte-identity and that the recipes are packaged.
- `.github/workflows/release.yml` — PyPI trusted publishing on `v*` tags.

### Added — five exhibits, one per domain pack

Each ran the full lifecycle on its own `experiments/<id>` branch, merged with history:
recipe scaffold, typed data card with the new audits, method card with verified
references, registered predictions, sealed run after the mandatory dry run,
replications, claims lock, an independent referee (20–23 failed round 1 and passed round 2
with notes; 24 passed round 1 with notes), finalize `confirmed`, a tutorial, and knowledge promoted with typed
citations (`knowledge/domains/{llm,cv,data-science}/`, `ml-research/`, `math/`,
`research-discipline.md` lessons 12 onward).

- **20 `llm-cot-contamination`** (test · text · llm) — chain-of-thought vs direct
  answers on GSM8K and on procedurally generated twins, every DashScope call ledgered;
  re-verifies with the network off.
- **21 `bloodmnist-cnn`** (predict · image · cv) — pixel logistic regression to a small
  CNN under a 3-seed-array floor; predefined official split with cross-split
  near-duplicates removed by the audit's rule.
- **22 `cnn-data-scaling`** (estimate · image · ml-research) — a data-scaling law fitted
  on detached (attested) cells and held to a sealed full-data extrapolation.
- **23 `lalonde-causal-replication`** (replicate · tabular · data-science) — Dehejia–Wahba
  NSW/PSID/CPS via `data.inputs`; an operator incident (a history repair during a live
  run) is filed under `incidents/`.
- **24 `golomb-llm-vs-search`** (test · none · math) — LLM proposals vs a classical
  randomized search at a matched budget of exact-verifier calls.
- Studies 20 and 24 commit their model call ledgers (`calls/`), produced on a paid
  pay-as-you-go DashScope key and labelled AI-generated in `calls/README.md`, as the
  provider's terms require.

### Fixed

- The leakage audit reproduces scalar-task and predefined splits (found at study 23's
  DATA gate).
- A phase ladder rewritten at CONSULT is followed by the state until work starts
  (found at study 23's first preflight).
- The `cv-classify` and `dl-scaling` recipe smokes train long enough to clear the
  collapse guard on real data (found at study 21).
- `klein finalize` and `klein next` honour a track's own `confirmation.require`: a
  track declaring a non-empty list without `sealed` (study 22's fitted exponent,
  `[replicate]`) closes on its records instead of being held to a sealed look it was
  never meant to take; an empty list still cannot close `confirmed`. Labels already
  recorded are never recomputed (found at study 22's finalize).
- The sealed dry run files the new files its evaluator wrote (a DRYRUN-keyed
  confusion table) in its own commit, so the mandatory rehearsal no longer leaves a
  tree that refuses the sealed run (found at study 21).
- The contract-driven split check recognises `load_items`, the index-table wrapper
  over `load_partition`, instead of warning that no source asks the contract for a
  partition (found by the referees of studies 20 and 21).
- The referee protocol asks for repo-relative paths: a gate-hashed report cannot be
  edited afterwards, and study 21's round-2 report named its worktree (exempted by exact
  path in the universality guard, as frozen evidence).
- `klein verify`'s ledger integrity no longer depends on the repository's size: `git
  diff` abbreviates object names on its `index` lines to a width git derives from the
  object count, so a fresh, fully packed clone printed 8 characters where the recording
  repository printed 7 and every study's `code_patch_hash` failed on CI. `run-one`
  records the patch at a pinned width of 7 (the width every shipped manifest used) and
  verify accepts any width git may widen to (found on the release PR's CI).
- The figure re-render runs the study's script with matplotlib's defaults (an empty
  `MATPLOTLIBRC`, a private `MPLCONFIGDIR`, the Agg backend), never the machine's
  config; the 2.3 exhibits' figures, first rendered under a host config that preferred
  an installed font, were re-rendered that way and their tutorials rebuilt (text
  unchanged).
- Study 22's scaling plot is drawn in log10 space with `math.log10` (rounded) on linear
  axes: matplotlib's log axes transform each vertex with numpy's vectorized `log10`, which
  differs from the C library in the last bit on AVX-512 machines and moved pixels between
  hosts. `tutorial-spec.md` carries the rule for dense curves.
- A phase-ladder test still expected the pre-repoint behaviour; it now checks both
  halves (followed before work, drift after).

### Changed

- Literature steps try connectors first (Literature Graph, PubMed, Scholar Gateway,
  Consensus, Hugging Face papers), then the web; the consultant can scout with
  WebSearch/WebFetch, logged in the scouting ledger. Insurance doctrine moved out of the
  generic agents into `profiles/insurance.md`. SKILL.md's generation-layer block moved
  to `references/generation-overview.md`.

### Known limitations

- The claims numeral scan reads digits inside identifiers (the "8" of `GSM8K`) as
  numerals; study 20 carries a labelled identifier alias. Changing the scanner would
  re-count shipped receipts, so it waits for a schema bump.
- `klein replicate --verify-only` refuses a sealed run by design, so a sealed artifact's
  re-verification is the notary's own verifier pass; confirmation rests on development
  replications.
- A study without a `calls.price` block records `usd: 0` for model calls: unrecorded,
  not free.
- The Claude Science kit is written against the product's published documentation; its
  live smoke record needs a person with a seat. PyPI publishing needs the project's
  trusted publisher to be created by its owner.

## [2.2.0] — 2026-09-07

The report builder learns to read the study's own records. A tutorial used to be
trusted to retype what `claims.lock` and `study_state.json` already said, to include
whichever bytes happened to be sitting on disk, and to be legible on a phone or on
paper because someone looked once. All three are now mechanical.

### Added

- **The evidence block — the records copied, never retyped.** A fragment drops
  `<!--EVIDENCE-->` (05-findings, where the claim totals used to be typed by hand) and
  `build_tutorial.py` generates the block from `claims.lock` — claim count, counts by
  strength and by class, errata, the lock's git head and the Klein version — and from
  `study_state.json` — the finalization label, the referee's verdict, who refereed,
  whether they were independent of the experimenter, `unrefereed` and any confirmation
  gaps. Nothing is computed and nothing is guessed: a record that does not exist prints
  an explicit "not recorded" line, and a study that HAS a lock while no fragment
  carries the marker fails the acceptance guard (exit 4).
- **`data-run="E####"` — the source the run actually executed.**
  `<pre data-code="search.py" data-run="E0009">` reads `runs/E0009/manifest.json` for
  the `candidate_commit` and includes the file AT that commit (read-only `git show`),
  with a provenance line naming the run, its evaluation kind, its track, the short
  commit and the sha256 of the included bytes. `data-role="template"` labels a
  deliberate include of the scaffold instead.
- **Captions, intrinsic sizes and a zoom for figures.**
  `<img data-fig="…" alt="…" data-caption="…">` becomes a `<figure>` + `<figcaption>`
  with a CSS-only enlargement (`:target`, a visible close link, Esc to return) that
  duplicates no image bytes. The builder decodes the PNG header and stamps the real
  `width`/`height`, so a page no longer reflows while it loads. A bare `data-fig` is
  unchanged, for fragments that write their own `<figure>`.
- **Subsection anchors.** Every `<h3>` gets a stable slug id, and a section holding two
  or more of them gets an "In this section" list under its `<h2>` — a report is now
  linkable at the paragraph a reader wants to send someone to.
- **`scripts/check_shipped_reports.py`** — a focused acceptance pass over every shipped
  `report/index.html` from `file://`: zero network, no horizontal overflow at 1440 /
  768 / 390 / 320 px (local scrolling allowed only inside `pre`, tables, math and the
  nav), every nav target revealed below the nav bar, every image decoding at its
  declared size, and a print-to-PDF pass that asserts the ledger's last header and the
  longest code line survive into the text. Schema-2 studies, and any schema-3 report
  built before the builder's current layout generation (read from the page head's
  generator tag), report `LEGACY`: measured and recorded, never failing the run — so
  a stylesheet fix never turns the reports shipped before it red, and a rebuilt report
  is enforced from the day it is rebuilt. New weekly `shipped-reports` job in
  `.github/workflows/scheduled.yml`; `ci.yml` is untouched.

### Changed

- **The experiment ledger is track- and kind-aware**: `Exp · Track · Kind · Metric ·
  Status · Description`, `Kind` read as `evaluation_kind` from the run manifests so a
  sealed cell is visibly a sealed cell, under a key line naming each track's metric and
  goal. The `Track` column is omitted when `results.tsv` has no such column and the
  `Kind` column when the study has no run manifests, so such a ledger (the test
  fixtures, a v1 study) renders exactly as it did.
- **A source include is a disclosure, not a wall.** Each `data-code` include renders as
  a closed `<details class="source">` whose summary IS the provenance line, so a
  400-line listing no longer buries the prose that explains it; print opens every one.
  Literal `<pre><code class="language-…">` snippets stay visible inline — they are the
  short examples the prose teaches from.
- **The page fits a 320 px screen.** The section nav becomes one horizontally
  scrollable row instead of wrapping to four, `scroll-margin` clears it at every width
  so a nav link no longer lands the heading under the bar, long tokens, URLs and
  plain-text DOIs wrap (inside `code`/`a`/`cite` and in ordinary prose alike), and
  wide tables, code and math scroll inside their own box rather than the document.
  Measured on the six schema-3 reports rebuilt in a scratch checkout: every one fits
  at 390 and 320 px, every nav and subsection anchor is revealed at phone widths, and
  studies 13 and 15 print whole. The page head now names its layout generation
  (`<meta name="generator" content="klein build_tutorial layout-2">`).
- **The six schema-3 reports are rebuilt under this contract** — studies 00, 10, 11, 12,
  13 and 15. Each `05-findings` fragment carries the `<!--EVIDENCE-->` marker, every
  mutable-surface include names the run it shows (`data-run` on the frontier's final
  keep — E0003, E0003, E0006, E0006 — or on the sealed cell — study 10's E0011, study
  11's E0009), every figure in sections 4 and 5 carries a teaching caption (34 in
  all), and the prose that retyped a claim total, a strength count or the finalization
  label is reworded to say it in words. Study 15's "What the lock says" paragraph,
  which described a ten-claim lock while the lock held fifteen, is replaced by the
  generated block plus a paragraph that names the claims without counting them; study
  10's hand-made copy `report/e0011-analyze.py` is removed because the builder now
  reads those bytes from the candidate commit itself (the copy was byte-identical).
  Nothing else in any study changed: no run, ledger, prediction, claim, gate record,
  lock, referee report or `findings.md`; each `program.md` discloses the rebuild and
  `klein verify` re-issued each receipt so it hashes the rebuilt page.
- **The tutorial numeral scan skips `<nav>`.** `kleinlib.numbers.html_text` no longer
  reads navigation text nodes: the section bar and the builder's "In this section"
  lists repeat heading text, so a numbered heading (`5.1 …`) was counted twice — once
  as content and once as chrome — on every rebuilt page. The scan is advisory on
  every schema and no disposition depends on it.
- **The tutorial protocol and the tutor worker teach the new contract.**
  `references/tutorial-spec.md` gains "Records, not retyping", the executed-source rule
  (including why a bare mutable-surface include is wrong), the caption requirement for
  every section-4 and section-5 figure, and three new acceptance boxes;
  `.claude/agents/klein-tutor.md` mirrors them. `AGENTS.md` § TUTORIAL no longer says
  "the winning entrypoint".

### Fixed

- **A tutorial can no longer teach bytes that no named run executed.** `run-one`
  restores the mutable surface on every non-keep and after every run on a registered
  track, so a bare `<pre data-code="search.py">` on a registered track included the
  restored template while the prose called it the executed cell (study 11's report
  did exactly that), and on a frontier track a bare include carried the last keep's
  bytes with no run named. A bare include of a file in `entrypoint.mutable`
  (`train.py` on schema 2) is now refused (exit 6) with the fix named: add
  `data-run="E####"`, or `data-role="template"` to say it IS the template.
- **Printing carries the whole page.** Wide tables were clipped at the paper's edge,
  code lines ran off it, and `break-inside: avoid` on whole sections produced
  near-empty pages. Print now wraps code, lets tables and equations overflow visibly,
  breaks inside sections but never inside a figure or a ledger row, keeps headings with
  what follows them, opens every source disclosure (a `beforeprint` handler that
  `afterprint` undoes), and re-declares the light palette so a dark-mode reader does
  not print a dark page.
- **A tag inside a figure caption is refused, not silently dropped.** The `<img>`
  matcher stopped at the first `>` inside a quoted attribute, so a `data-caption`
  holding `<code>` made the figure lose its caption with exit 0 — three rebuild lanes
  hit it on their first build. The matcher now steps over quoted values, and a caption
  containing markup is a figure problem (exit 3) naming the figure: a caption is plain
  text, entities allowed, because the builder escapes it into the `<figcaption>`.
- **A figure that is not a PNG is refused instead of shipped.** Whatever bytes sat at
  the `data-fig` path were base64-inlined behind an `image/png` prefix, so a JPEG or a
  truncated file became a broken image inside a self-contained artifact nobody could
  re-render. The signature is decoded now; a bad file is a figure problem (exit 3)
  naming the file and the reason.

## [2.1.0] — 2026-09-06

### Added

- **Opt-in process-verifiable generation layer — the spine** (`klein generation
  init | check | verify | label | status | recover`). A schema-3 study may now record
  what it committed to BEFORE the evidence existed: an immutable opt-in manifest
  anchored ahead of the CONSULT gate, one admission receipt per action binding the
  intended action and the exact bytes of `entrypoint.mutable`, and a separate audit
  (`generation/verify_receipt.json`) that classifies every run in scope as
  `admitted | unadmitted | refused-but-run | mismatched | replayed`. Order is
  established by three local witnesses — the extension hash chain, a core-chain
  anchor, and git ancestry — never by a clock. A refusal is written and committed
  like an admission, so ignoring one is detectable. The dual-pass
  `generation-verified` label requires the core `klein verify` receipt AND the
  generation receipt to pass at the same HEAD, and `findings.md` to quote it.
  Protocol: `.claude/skills/klein/references/generation-protocol.md`; template:
  `.claude/skills/klein/assets/generation-manifest-template.yaml`.
- The capability vocabulary (`expertise, slates, premortem, parity, contribution,
  surprise, escalation, knowledge, benchmark, design`) and its dependency table are
  encoded. Opting in with `capabilities: []` buys the admission discipline and the
  chronology witnesses, and nothing that scores research; each capability below is
  declared explicitly at `klein generation init`. This release supports all ten; a
  name a build cannot check is still refused as *not available* — a different message,
  and a different problem, from a typo — which is what a study meets when it is
  carried back to an older Klein.
- **Capability registration hooks.** A capability now plugs into the generation spine
  by registration (`kleinlib/generation/registry.py`: a name, admission rules, one
  verify family; `capabilities.py`: the modules this version ships), never by editing
  `admission.py`, `verify.py` or `label.py`. A capability the manifest does not declare
  is not consulted; one it declares that this version cannot run FAILs
  `generation manifest`. Families report `integrity` (is the record intact) and
  `outcome` (what the research got) separately — the label copies the outcome, the
  spine judges only the integrity — and a study with `capabilities: []` runs no family,
  so its receipt is byte-for-byte the one the spine already produced.
- `Capability.receipt_inputs` — a registered capability may FILL one of the admission
  receipt's six existing `inputs` slots (`slate`, `premortem`, `parity`, `cells`,
  `design`, `benchmark`) beside the spine's own `manifest` — the `slates` capability, for
  instance, pins the lock's object sha in `inputs.slate`. The receipt's key set stays the
  spine's — no capability may add a key — and a study that declares nothing gets the
  receipt it always got.

The ten capabilities follow, in the order the spine loads them — dependencies first.

- **The `expertise` capability — acquire the domain, then prove you acquired it**
  (`klein generation expert lock | amend | bind | repair | review`). A declaring study
  freezes `domain_card.md` before the CONSULT gate — pipeline, metrics, doctrine,
  pitfalls, incumbent, a `method_shortlist[]` that precedes METHOD, and a baseline
  recipe with numeric targets — then executes that baseline as an ordinary `run-one`
  transaction admitted with `--action baseline`. `expert bind E####` recomputes each
  target from the run's printed metric block and records `reproduced | mismatch |
  crash`; **until a bind reproduces, no `run` or `sealed` admission is granted.** A
  failed reproduction is fixed by a versioned `expert repair` naming the changed files
  and their hashes (never the declared verifier), verified afterwards against those
  files at the next bound run's candidate commit. Targets are frozen at version 1: an
  amendment that moves one is refused, because lowering a bar you did not clear is a
  successor study, not a repair. The capability outcome is `incomplete` (label-eligible
  — an honestly open obligation is a WARN, never a FAIL), `source-reconstructed`, or
  `independent-review` when a recorded review carries a session-receipt hash and a
  reviewer who is not `program.md`'s roster experimenter. Protocol:
  `.claude/skills/klein/references/expert-protocol.md`; template:
  `.claude/skills/klein/assets/domain-card-template.md`.
- **Reference records** (`klein generation reference record`) — write-once, repo-level
  `knowledge/references/<id>.json` carrying the locator, the one statement the work is
  cited for, the hash of the bytes that were read, whether they were retained, and the
  verification basis (`read-at-source > bibliography > abstract-only > hash-only`),
  each basis enforcing its own consistency rule. Klein copies no bytes: the hash goes
  into git, the source stays where it is. On an `expertise`-enabled study a
  `references.yaml` row saying `verified: true` without a resolvable `record_id` FAILs
  verification. Protocol:
  `.claude/skills/klein/references/reference-protocol.md`.

- **Hypothesis slates and forecast calibration** (the `slates` capability;
  `klein generation slate lock | amend | score | show`). A generation-enabled study may
  now record each phase's 4–6 authored candidates in `slates/<phase>.yaml`, give each a
  permanent `<study>#Hn`, admit a run with `klein generation check --hypothesis` (which
  binds the run to the row and refuses unless `--tests` covers the row's `success_P`),
  and at phase end compute the Brier score, Murphy decomposition, base-rate skill and
  best/worst bounds of the forecasts it wrote — into
  `generation/tables/slate_calibration_<phase>.tsv`, pinned as
  `art:slate_calibration_<phase>`. A locked forecast is immutable (an edit fails
  verification for the life of the study); a revision is an amendment scored in its own
  panel; the cohort denominator is frozen at lock, so withdrawal and perpetual deferral
  report as coverage below 1.0 and outcome `conditional`, never as a better Brier; a
  `provenance: scouted` row is descriptive and never calibration. Verification recomputes
  every number from the receipts, the manifests and the core chain. **Nothing generates,
  scores, ranks or selects a candidate** — the 1–3 axis scores are validated and copied,
  and the phase ritual is still not automated. Protocol:
  `references/generation-protocol.md` "Slates and calibration"; template:
  `.claude/skills/klein/assets/slate-template.yaml`.
- **Evidence design — what the evidence is FOR, locked before the DATA gate**
  (`klein generation design lock`, capability `design`). A declaring study freezes
  `evidence_design.yaml` into the extension chain before Gate 1: the Question's estimand,
  population, units, measurement process, identification assumptions and intended
  generalization; the Prediction's uncertainty method, validity conditions, practical
  threshold and provenance; the Evidence's representations, dependency hierarchy,
  permitted reuse, seal and acquisition ledger; the Claim's warrant (`prediction |
  conditional-estimation | causal-inference | exploratory-structure | checked-witness`);
  and the Decision's typed continuation with its predecessor and successor. **Every
  validity condition must reach the arithmetic:** its `rule_ref` names a registered `P#`
  carrying an `inconclusive_if` rule or an `all_of`/`any_of`/`not` combinator — a plain
  leaf comparison and a prose `inconclusive_if` are both refused, and the cross-check is
  re-run at every `generation verify` against `study.yaml` as it is now, so dropping an
  `inconclusive_if` after the lock is caught. **Import chronology is not acquisition
  chronology:** an `acquisition[]` entry with `kind: import` records when bytes arrived,
  while `kind: acquisition` claims when the measurement was taken and is refused without
  a `custody` chain and a named `attested_by` (testimony, never verified). A `--action
  cell` admission is refused until the design is locked; the capability outcome is
  `locked` or `unlocked`, and a late lock (`--allow-late`) FAILs `design lock`
  permanently. The artifact supplements the five objects and changes no id grammar and no
  engine rule. Protocol: the "Evidence design" section of
  `.claude/skills/klein/references/generation-protocol.md`; template:
  `.claude/skills/klein/assets/evidence-design-template.yaml`.
- **Slate-time pre-mortem** — the `premortem` capability (`klein generation
  premortem record | respond`), a recorded red team between the draft slate and the
  first run. `record` binds the sha256 of the DRAFT slate lock, the reviewer, a hashed
  bundle of exactly the inputs the reviewer was handed, and the issues — each
  `{id, target, severity, kind, text}`, with the reviewer's own further fields copied
  verbatim; `respond` binds one disposition per issue. A `blocking` + `mechanical`
  issue must be `accept`ed with the hash of a NEW slate version descended from the
  reviewed draft, or `klein generation check --hypothesis` is refused naming the issue
  ids; a `scientific` objection may be rejected with a rationale, because the reviewer
  supplies arguments and never a veto. **Nothing scores or ranks**: there is no
  quality score for an issue and no comparison between candidates. A review recorded
  after the phase's hypotheses ran FAILs; the reviewer's name matching `program.md`'s
  roster `referee` FAILs — the proposal critic is not the closing referee; independence
  is `self-attested` until a session receipt is hashed into the record, and Klein calls
  no model to produce the review. The input bundle is recomputed at verify time from
  the commit that introduced the record, and an answered review is immutable. The
  generation spine's `generation orphans` family additionally FAILs an object file
  whose bytes no longer hash to its own name. Protocol:
  `.claude/skills/klein/references/premortem-protocol.md`; template:
  `.claude/skills/klein/assets/premortem-template.yaml`.
- **Expert parity and contribution ledger** — two more registered capabilities.
  `parity` (`klein generation parity lock | amend | bind | assess | show`) turns "the AI
  matched the expert" into a commitment made before the evidence: `parity.yaml` is locked
  at CONSULT with both pipelines and their selection rules, the sampling unit and
  dependence block, the matched budget rule, and every metric's direction, estimand,
  measured-floor reference, noninferiority margin and **written margin rationale** — set
  by someone who is not the roster's experimenter, and tied to a registered prediction
  whose rule must be exactly `L_<key> >= -margin`, so the notary decides the same
  inequality the assessment does. `parity bind` pins the scorer's hash, both frozen
  snapshots and every measured floor, and a registered admission rule refuses
  `--action sealed` on **any** track until it exists — the core still grants each
  track its own single look, so parity must bind before any is spent. One sealed
  registered cell measures; `parity assess` recomputes `d/L/U` from the cell's own pinned
  `tables/parity_units.tsv` and applies the rule — **exceeds / at least parity / refuted
  / inconclusive**, mutually exclusive by construction, with an undefined metric never
  passing and the by-δ agreement check reported as `agreement_within_floor`, never parity.
  Verification recomputes the same numbers from the same bytes and fails on a scorer or
  snapshot that differs at the sealed candidate commit, on a second sealed run of the
  comparison track, and on a locked metric the cell never printed or declared undefined.
  `kleinlib.generation.stats.simultaneous_bounds` is the arithmetic: a block-bootstrap
  max-t on per-block sums, pure numpy, deterministic under its seed — simultaneous bounds
  under the declared block structure, not a p-value and not FWER control beyond this
  registered family. `contribution` (`klein generation contribution record | show`)
  appends `ai_value.jsonl` and seals each line's hash into the chain; coverage counts
  every slate row and every hypothesis admission, rejections included, an accepted row
  with no human acceptor is recorded as agent-accepted and never promoted, and the
  outcome stays `descriptive` unless the parity lock cites a matched frozen-2.0 ablation
  study. Protocol: `references/expert-parity-protocol.md`; templates:
  `.claude/skills/klein/assets/parity-template.yaml` and `assets/parity_score_template.py`.
- **The escalation ladder and successor studies — getting unstuck, accounted
  for** (`klein generation escalate lock | record | close | pivot | show`, capability
  `escalation`). A declaring study freezes `escalation_plan.yaml` before the CONSULT
  gate: the triggers a stall is RECONSTRUCTED from — `consecutive_discards` through the
  `stop:` rule's own counter, `headroom_closed` through the same `kleinlib.decision`
  helpers `run-one` enforces on, `budget_exhausted` against a phase's registered
  `max_experiments` — the five rungs in one fixed order (metric diagnosis → method
  family → data leverage → adjacent-field analogy → human expert, with `stop` always
  available from anywhere), unit-bearing budgets over compute/person-time/money/samples,
  and `stop`/`pivot` as terminal actions. **Once a trigger trips, no `run` or
  `--hypothesis` admission is granted** until a `<study>#Dn` decision citing it is
  recorded after the tripping run — and the discharge is scoped to that count, exactly
  like `klein stop ack`. Each decision names the rung, the lower rungs skipped WITH
  REASONS (a silent skip is refused), the concrete changed resource or assumption, the
  estimated cost and the condition that would close it; `close` adds the outcome and the
  actuals, where a unit that cannot be measured is `unknown` with cost evidence rather
  than omitted. Verification recomputes every count from the manifests, re-derives the
  episode from the chain, FAILs an unaccounted rung, an open decision that outlived
  `evidence_window`, a budget passed without a prior `extend-budget` decision, and a
  pivot whose `old_contract_sha256` is not `study.yaml` at the pivot's own commit —
  **editing the locked threshold cannot discharge a stall**. `escalate pivot` links a
  successor study with both contract hashes, the exposure it inherits (spent seals, the
  development partition, scouted ids) and every `#Hn`/`#Sn` id handed over; the
  successor cites it back with `generation init --predecessor … --successor-receipt …`,
  and its `escalation predecessor` check reads the receipt out of the predecessor's
  store. A successor id restores no blindness. The capability outcome is
  `none | escalated | stopped | pivoted`, reported beside its integrity. **The verb
  neither chooses a rung nor launches, schedules or retries work** — whether the work
  under a rung label deserves it stays the referee's judgement, which is why the changed
  resource is written down. Protocol:
  `.claude/skills/klein/references/escalation-protocol.md`; template:
  `.claude/skills/klein/assets/escalation-plan-template.yaml`.
- **Cross-study knowledge — transactions over pinned evidence** (the
  `knowledge` capability; `klein generation knowledge promote | contest | resolve |
  query | decide | show`). The markdown under `knowledge/` keeps its typed claim
  citations and is never rewritten; beside it, a **repo-level** store of write-once
  `knowledge/objects/<sha256>.json` and an append-only `knowledge/events.jsonl`
  chain answers what prose cannot. `promote` imports a claim only if `klein claims
  verify` passes on its study NOW, copies `class`, `strength` and `evidence_roots`
  **verbatim** — a promotion creates availability, never stronger evidence — and
  deduplicates by evidence roots, so one lesson repeated across ten studies is one
  piece of evidence. `contest` attaches contradicting evidence from the citing
  study's own verified lock and requires at least one CLAIM: **a prediction that
  failed to transfer is a prediction verdict, not a refutation.** `resolve` appends
  `upheld | scoped | withdrawn` and deletes nothing. Before the CONSULT ack, `query`
  records the consultation receipt — contract draft hash, pinned `store_head`,
  retriever version, typed query, COMPLETE hits (no top-k unless `--limit`, which is
  recorded), **each hit's contest closure whatever it would have scored**, and a
  use/reject reason for every one, or an explicit `no_match` so that an empty store
  is consulted rather than skipped. Retrieval is `lex-1`: deterministic case-folded
  token overlap, no embeddings and no model call, chosen because `generation verify`
  replays the recorded query against the store at `store_head` via `git show` and
  FAILs any difference as a suppressed hit or contest. The family also FAILs a late
  consultation, an undecided hit, a broken store chain, a deleted transaction, an
  unresolvable source hash (a foreign origin WARNs), and a strengthened copy.
  `scripts/seed_knowledge_objects.py` seeds a repository from the citations already
  in `knowledge/**/*.md` — dry-run by default, read-only over the markdown, skipping
  any study whose lock does not verify, with scope fields left empty for human
  curation. Protocol: `.claude/skills/klein/references/knowledge-protocol.md`.
- **Surprise mining — registered discovery cells, three table templates, `<study>#Sn`
  receipts** (`klein generation surprise register | record | show`, capability
  `surprise`, which requires `design`). A study screening many segments now records the
  DENOMINATOR: `discovery_cells.yaml` freezes the search space after METHOD and before
  any cell evidence — template, statistic, adapter and inputs (hashed from disk by
  `register` and pinned back into the file), partition (never `sealed`), unit and group
  policy, the complete segment inventory, `minimum_n`, and a declared multiplicity rule.
  **A measured effect floor is refused as one:** a floor answers "bigger than noise on
  ONE comparison", so a screen declares `family_maxt` (`kleinlib.metrology.family_maxt`
  over both signs of every segment), `bonferroni`, or a threshold from a registered null
  sweep. Three table producers ship as library code a study entrypoint imports —
  residual-by-segment, error slices, family disagreement — and the pinned table is PER
  UNIT, because a sign-flip max-t acts on units and a summary-only artifact could not be
  recomputed. A cell runs through ordinary `run-one --tests P#` (admitted with
  `--action cell --cell <id>`, whose `--tests` must include the cell's registered
  expectation); `surprise record --run E####` re-reads the pinned table, recomputes every
  segment of the frozen inventory, makes a slice below `minimum_n` `inconclusive` rather
  than `null`, and issues one `<study>#Sn` receipt per violation while retaining the null
  and inconclusive segments in a complete inventory object and a derived
  `generation/tables/surprise_<cell_id>.tsv`. **Explanations are never invented:**
  a receipt reads `unresolved` until a driver types one, and `--explain SEGMENT=TEXT`
  records that as testimony. The `surprise` verify family recomputes the record from the
  pinned bytes and FAILs on a late first registration, an edited registry, an adapter or
  input that differs today or at the run's candidate commit, a sealed-partition cell run,
  an omitted eligible segment, an admitted cell run that was never recorded, and a
  `confirmed` claim resting on a cell table or an S receipt — a screen selects what to
  look at and cannot also confirm it. A bare `S#` in findings §③ WARNs, because the
  scouting ledger already uses that token. Protocol:
  `.claude/skills/klein/references/surprise-protocol.md`; templates:
  `.claude/skills/klein/assets/discovery-cells-template.yaml` and
  `.claude/skills/klein/assets/discovery_cell_template.py`.
- **Planted-truth benchmark and custody receipts** — the `benchmark`
  capability (`klein generation benchmark commit | submit | reveal | retire | show`),
  plus one verb group that belongs to no capability at all,
  `klein generation custody attest`. `commit` freezes `benchmark.yaml` after the
  CUSTODIAN's METHOD gate and before any participant access: it hashes the public
  bundle, computes `sha256(salt ‖ private-bundle bytes)` beside `sha256(salt)`, pins
  the scorer and the participant-facing submission schema, and freezes the arms and
  their budgets, the hypothesis cap, the false-positive penalty, the matching rule,
  the per-arm recovery predictions and the **disjoint** development/sealed seed
  blocks. The salt never enters the repository. `submit` validates each arm's ranked
  structures against the schema and the cap and files the participant's own bytes as
  `submissions/<arm>.json`; `reveal` recomputes the commitment once every arm has
  submitted or carries a recorded missing trial that stays in the denominator — **a
  mismatch is refused AND recorded** as `benchmark_reveal_failed`, and fails the audit
  from then on. Scoring is an ordinary sealed `run-one` on a registered track: ONE
  cell over all arms, pinning `tables/benchmark_scores.tsv`, which verification
  recomputes row by row by re-applying the locked matching rule to the same
  submissions and the same revealed truth. The machine decides variables (as a set),
  relationship and sign; the fourth condition, *context*, is a preregistered sentence
  the custodian adjudicates and records per row as `context_ok`, and verification
  takes that column rather than pretending to derive it. Each planted truth is
  recovered once — a later structure matching it is a duplicate, one matching nothing
  is a false positive the declared penalty is charged against. The family also FAILs a
  scorer that is not the pinned one at the scoring cell's candidate commit, a second
  sealed scoring cell, and a `confirmed` claim resting on the in-silico table —
  in-silico recovery is never confirmation. **A hash is not secrecy**: `custody
  attest` records a NAMED holder's statement about accounts, containers or machines, stored with `testimony: true` and
  reported as testimony; without one the outcome reads `unverified`, which fails
  nothing. A benchmark known to have leaked is retired and its results are retained.
  Protocol: `references/planted-truth-protocol.md`; templates:
  `assets/benchmark-template.yaml`, `assets/benchmark-submission.schema.json` and
  `assets/score_submissions_template.py`.
- **The documentation surface says the same thing everywhere.** `AGENTS.md` and
  `CLAUDE.md` carry the layer in one paragraph and one verb list — no new lifecycle
  stage; `SKILL.md`'s stage table names the generation verbs used at each EXISTING
  stage; `references/generation-protocol.md` lists every verb group, the six receipt
  input slots, the dependency table, the eight verify families and the label's fields
  as the code has them, and states once what the mechanism does not establish;
  `references/inquiry-model.md` carries one table of the generation record ids
  (`#Hn`, `#Sn`, `#Dn`, knowledge objects, generation objects) and the rule that they
  reach a claim only through an `art:` alias; `references/referee-protocol.md` carries
  one "Generation addenda" subsection — the ten core checks unchanged — with a reading
  obligation per capability and the report's separate `Generation:` line, now in
  `assets/referee-report-template.md`; and
  `references/defaults-and-scaffolding.md` has a row per artifact the layer writes,
  with the verb that writes it. `scripts/tests/test_docs_integrity.py` now checks the
  `.yaml` / `.json` / `.py` templates protocols name, not only the `.md` and `.toml`
  ones, and fails a packaged asset no protocol points at — the mirror of the
  orphan-protocol check that has guarded `references/` since 2.0.

### Fixed

Everything below was found and repaired in one review pass over the layer before it
shipped, so nothing here changes behaviour any study has ever depended on. The spine's
fixes come first, then the capabilities' in the order the spine loads them.

- **A generation receipt refreshes at a new HEAD.** `klein generation verify` used to
  skip the rewrite whenever the new audit differed from the receipt on disk only in
  `git_head`. After any unrelated commit — a `program.md` decision, a playbook
  refresh, a framework doc — the receipt was therefore stale, re-verifying changed
  nothing, and `klein generation label` refused for the life of the study. The
  rewrite is now skipped only while the receipt is still current; two verifies at one
  HEAD still file nothing.
- **A generation commit carries generation paths only.** Every generation verb filed
  its writes through a commit scope that also prepended `study_state.json` and the
  core `events.jsonl`, so an operator's uncommitted core-state edit could be swept
  into a generation transaction. Verbs now commit exactly the paths they wrote,
  refuse to name core state or core evidence at all, and refuse to run while
  `study_state.json` or the core `events.jsonl` is dirty.
- **A study that never opted in is left untouched.** `klein generation verify` on a
  study with no manifest and no chain exits 1 and writes nothing, instead of creating
  `generation/` and filing a FAIL receipt against a study that had promised nothing.
- **A run that went ahead after a refusal says so.** It is classified
  `refused-but-run` from the newest preceding receipt, rather than `replayed` from any
  older consumed one. Both still FAIL; only one is the truth.
- **The object store refuses to complete a tamper.** Writing an object over different
  bytes under the same name raises instead of overwriting, a file that is not its own
  hash (or cannot be read) blocks every writing verb until it is restored by hand, and
  `recover` never rewrites an object.
- **The two ways a verb says no are told apart.** Exit 1 is an ERROR on stderr — the
  question could not be asked: a malformed argument, an argument naming a file, run,
  claim, trigger or decision that does not exist, or a study that cannot be read.
  Exit 2 is a REFUSAL on stdout — a rule of the study, the ledger or an authored
  artifact answered no, and the reasons ARE that answer. Only `check` records its
  refusal, because a refusal is evidence; every other verb prints it and leaves the
  ledger exactly as it found it.
- **Two capabilities cannot fill one receipt input slot.** A slot pins one artifact,
  so a build in which two declared capabilities both resolve `inputs.slate` now
  refuses the admission and names both — rather than letting load order silently
  decide which artifact the action was taken under.
- Smaller: `check --action` takes argparse `choices` from a tuple asserted equal to
  `admission.CHECKPOINTS`; an unreadable `study_state.json` is a recorded refusal
  reason rather than an empty state that would admit a spent seal; `same_actor`
  compares actor components symmetrically; a declared-but-unexercised capability
  reports `incomplete` rather than `n/a`, which is the label's word for "not
  declared"; admission receipts pin the protocol file of every declared capability
  instead of the spine's alone; docs no longer describe a manifest amendment feature
  that does not ship, and state that the label's rung is always `local-order` in this
  release.

Then the capabilities, dependencies first:

- **The expert baseline's recipe is frozen with its targets.** `expert lock`
  records the sha256 of `baseline.implementation` and `baseline.fixture`; a
  `reproduced` bind whose recipe drifted since the lock now FAILs unless a repair
  declared the change. Files inside the mutable surface are recorded but exempt.
- **A repair changes what it says it changes.** `verify` diffs the study subtree
  between the failing run and the repaired one and FAILs on any unnamed change;
  `expert repair --changed` refuses core state, run evidence and the generation
  ledger (naming a path also exempts it from the clean-tree check).
- **Every cited reference record is opened.** A record reachable only from a
  `references.yaml` row used to pass by never being looked at, and a row's
  `verification_level` may no longer claim a stronger basis than its record's
  `verification_basis`.
- **A slate row's `y` comes from its FIRST admitted run**, not its last, so a resolved
  row cannot be re-run into a better score. Every further admitted run is counted in a
  new `n_bound_runs` field of the score object and column of the calibration table,
  and the family WARNs when any row exceeds one. `revision_of` is carried forward
  across later amendments, so a revised forecast stays in the revisions panel. A row's
  `parent_ids` must name hypotheses this study locked.
- **Pre-mortem independence is not asserted from an empty roster.** A missing
  `referee` row now WARNs once per phase instead of passing silently, and a recorded
  review is FAILed when the document it hashed is not the document at its own commit.
- **The parity outcome is one cell's, decided once.** Four ways the comparison could
  drift from the criteria it registered are closed:
  - The outcome is read from the **comparison track's sole sealed cell**, resolved
    from the lock, rather than from whatever was assessed most recently.
    `parity assess --run` refuses a sealed run on any other track, and an assessment
    naming one FAILs `parity assessment` without displacing the comparison's verdict.
  - The sealed comparison cell must **ask the notary the questions the lock
    registered**: `generation check --action sealed` on the comparison track is
    refused unless `--tests` names every parity prediction, and `parity cell` FAILs a
    comparison run whose manifest carries no verdict for one of them.
  - `parity bind` may only read each metric's floor **where its `floor_ref` says**.
    `--floor-run` must restate the run the lock froze, and a bound floor whose
    `source` differs from the locked reference FAILs `parity bind`.
  - A `scorer.path` inside `entrypoint.mutable` is refused by `parity lock` and FAILs
    at every verify — the checker is never the searcher. A
    `scoring.scorer_name` equal to the roster experimenter is a WARN (testimony).
- **Parity arithmetic is honest about what it could not measure.** A comparison over
  no metrics is `inconclusive` rather than a vacuous `parity`; a constant metric on
  unequal blocks is undefined rather than bounded by floating-point residue; a
  non-numeric, non-empty cell of `tables/parity_units.tsv` is an error naming its line
  and column instead of a silent NA (and the NA count is recorded). Assessment replay
  compares the bootstrap numbers at a relative tolerance and records `numpy`'s version
  beside `n_boot` and `seed`, so a numpy upgrade is diagnosed rather than read as
  tampering.
- **The escalation plan's order is re-derived, not read off its own flag.** `verify`
  establishes from the core anchor and git ancestry that the plan preceded the CONSULT
  gate; the lock's `late` field stays a write-time refusal and is no longer the
  witness.
- **The knowledge store proves its TIP.** Every earlier state of
  `knowledge/events.jsonl` in git, and every `store_head` a query receipt pinned, must
  still be a prefix of the file on disk — a deleted last line leaves the hash chain
  perfectly intact and was previously invisible. A query receipt that cannot be
  replayed FAILs when the store is in this repository (it only WARNs for a checkout
  that has no store), a promotion whose commit does not resolve is re-checked against
  the source lock on disk rather than excused, and `scripts/seed_knowledge_objects.py`
  records the HEAD it read each lock at.
- **A discovery cell added after evidence arrived says so by itself.** A cell declared
  once another cell already produced evidence is labelled `post_observation` whether
  or not anybody ran `surprise record` — the label follows the run and the pinned
  table, not the diligence of the person writing it down — and `klein generation
  verify` re-derives, for EVERY registration version, that its core anchor and its
  commit precede the runs of the cells that version introduced.
- **A `confirmed` claim cannot rest on a screening table.** Quoting a number that
  lives in one is now caught as well as citing the table as evidence, and the derived
  per-segment summary counts as a screening table too. Registered adapters and inputs
  must carry a `sha256`, segment names that would print as one key are refused, and
  `n_perm` is capped at 100 000.
- **Discovery cells can declare clustered units.** `group_policy: {column: <name>}`
  makes the segment statistic the mean of the GROUP means, the dispersion a dispersion
  over groups, and the sign-flip family rule act on groups — because eight measurements
  at two sites are two observations, and flipping them as eight manufactures
  violations. The pinned table carries the group column under its declared name, the
  record and every `<study>#Sn` receipt carry `unit_of_inference: group | unit`, and a
  cell that declared a clustering column whose table does not carry it FAILs. Cells
  with no `group_policy` are unchanged, to the last digit.
- **A custody attestation only custodies its own subject.** An attestation makes a
  benchmark `custodied` only when its `subject` is that benchmark's own hidden
  evidence; attestations about anything else stay on the record and are reported
  separately.

### Unchanged

- **The core notary, its receipts, and schema-2 verification.** `run-one` gains no
  call site, option, default or import; `verify_receipt.json` is byte-for-byte what it
  was and never mentions the word "generation"; a lawful core run without an
  admission keeps its disposition, its confirmation and its `finalize` label — it
  simply cannot earn the generation label. `kleinlib.generation` is imported by no
  core module and not at `kleinlib.cli` import time. Schema-2 studies are refused by
  `klein generation init` outright.

## [2.0.0] — 2026-09-03

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
  `confirmed` claim rests on two kinds of evidence. The figure re-render check
  compares bytes first and, when they differ, the decoded pixels: the same image
  written through another platform's PNG encoder passes (macOS and Linux link
  different zlibs); a pixel difference fails on the platform family that rendered
  the figures and is a `[WARN]` naming both platforms elsewhere (a computed curve
  can move a pixel between arm64 and x86_64 in its last floating-point bits). The
  check leaves `figures/` exactly as it found it: a script that also writes into the
  study's own figures directory despite `--out` (the engine's trajectory plotter
  does, until 2.1) has those files judged like the rest and restored, and the
  receipt names them.
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
- **The consult gate hashes `scouting_ledger.md`** (schema 3), making true a protocol
  sentence the engine had never honoured: the pre-registration disclosure joins
  `study.yaml` / `research_plan.md` / `program.md` in the consult record, so editing it
  after the gate fails `klein verify` until the gate is re-recorded with a reason — and
  "pre-registered" rests on a hash instead of on a commit order nobody checked. The
  ledger is OPTIONAL: `klein new` now scaffolds one, and a study that keeps none
  records `scouting_ledger: absent` on the gate event, so the absence is on the record
  too. The scaffolded `program.md` also opens with a `## Roster` — experimenter,
  data-gate auditor, referee, lead, each with model · tool · session — which the
  referee reads for the independence rung; a blank experimenter row caps that rung at
  "fresh session", because nothing else in a study says what ran the loop.

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
  - **10 `hubble-1929-replication`** (2026-09-03) — Hubble's two 1929 tables, bundled; three
    registered tracks (replicate, estimate, simulate), 13 measured cells, three sealed
    accesses (one per track): neither two-parameter fit returns 465 (423.937323 / 454.158441),
    the headline is unreproducible for missing inputs rather than method, the 24 objects support
    K = 454.158441 with a 95 % bootstrap interval 316.648582–603.704762, and a single distance
    factor of 6.056247 carries the 1929 fits to within 4.990073 of the modern 70. The first
    referee round FAILED on a spelled-out ratio the numbers scan could not see; cleared, and
    round 2 passed with notes. Its run manifests pin commits from the study branch's
    pre-rebase chain (the driving agent rebased the branch, against the protocol); the
    annotated tag `evidence/10-hubble-1929-replication` keeps those commits reachable on
    every clone, and the ledger itself is untouched.
  - **11 `exact-verifier-construction`** (2026-09-03) — the mathematics exhibit: the
    no-three-in-line problem with `search.py` as the mutable surface and `verify.py`, hashed at
    the METHOD gate, as the only source of the objective. Zero keeps by arithmetic (the best known
    value equals the proven bound, headroom 0 acknowledged before the first run); 21 of 22 from
    the development seed block and 22 from the sealed one, reported as a difference and never a
    rate; 55 of the best-known 62 on the larger grid, never called impossibility; twelve planted
    invalid objects rejected and a deliberate one-point overclaim refused as a
    `verifier_disagreement` crash. The referee found a false quantity in a frozen claim sentence
    ("sub-millisecond" against a pinned 0.002046 s), cleared by erratum, never by edit.
  - **12 `insurance-claims-frequency`** (2026-09-03) — the insurance-profile exhibit, the v1
    quickstart ported onto the bundled 58k-row claims table: all three v1 rungs reproduce
    (anchor 0.011322 from the ledger's value); the paired-comparison floor 0.0375805 is
    0.9671 of the v1 ledger's whole spread, so the ladder yields exactly one measured keep
    (the boosted tree, +0.049911) and the spline chain's 0.035956 lift is 0.9568 of a floor;
    the calibration doctrine improves Brier by a factor of 4.055; the DATA gate found 615
    row-content twins straddling the partitions — a BLOCKER the v1 study never saw,
    overridden on the record with an instrument printed on every run; the sealed level
    0.657739 holds within 0.1680 floors. The v1 quickstart directory leaves the tree with
    this study (read it at tag `v1.3.0`).
  - **13 `charlm-fixed-budget`** (2026-09-03) — the deep-learning exhibit, the autoresearch
    ancestor pattern under contract: a character-level transformer on the bundled
    tiny-Shakespeare corpus at a fixed 2000-step budget, every disposition decided by
    `verify.py` re-scoring the checkpoint (gap 0.0 against a declared tolerance of 0.01).
    None of the four registered levers cleared the paired floor of 0.0149525 nats (weight
    tying cost −11.3693 floors); cosine decay, the one lever without a prediction, gained
    +3.3326 floors; the sealed final tenth came back 3.140679 floors harder, so the study
    confirms a level (1.56628 nats per character) and never a gap. Needs `--extra deep`;
    the main CI verifies its ledger, the weekly job re-runs two anchor cells on CPU.
