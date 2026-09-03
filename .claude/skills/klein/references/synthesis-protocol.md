# SYNTHESIZE — mine the trajectory into findings

The stage that makes it research, not experiment-running. Mine the full study trajectory,
write `findings.md` with EXACTLY seven sections, and author `claims.lock` beside it.
Every claim cites evidence ids; every number has a home; the synthesist never referees
its own findings — REFEREE (Gate 3) follows in a fresh context, and `klein finalize`
comes after that gate.

Role: synthesist. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-synthesist` worker.

## Mine six sources

### 1. manifests + derived results.tsv — track frontiers and all evidence
- **Track-specific keep-chain deltas.** Partition by track before comparing metrics.
  List each track's `status=keep` experiments in order; deltas between consecutive keeps
  tell that track's adaptive story. Never calculate a global frontier across tasks.
- **Discard clusters.** Group discards by theme (an encoder family, a model class, a
  regularization sweep). A cluster of discards is EVIDENCE — "we tried five imbalance
  strategies; none beat cw=None" is a finding, not a gap.
- **Crash audit.** Read every crash manifest and `run.log`. Was it a bad idea or a bug
  that killed a good idea? A crashed direction never retried is a caveat, not a verdict.
- **Reconstruction audit.** Use `runs/E####/manifest.json` for exact candidate commit,
  patch/data/split/environment fingerprints, exit status, and artifact hashes. The
  derived TSV is an index, not the full evidence record.
- **Confirmation status.** Separate development runs from the one sealed final-test
  run per track. A final-test value does not become another adaptive keep. A sealed
  confirmation appears as a discard row BY DESIGN (it must never enter the adaptive
  frontier); the CLI and summary label it "sealed" so the vocabulary reads as
  confirmation evidence, not failure.

### 2. aux_metrics.tsv — the tradeoffs
- Rank-vs-calibration: did the best-AUC model also have the best brier/logloss, or did
  ranking and calibration trade off? For actuarial use, calibration often matters more
  than rank.
- Wall-clock: was the best model 10× slower for +0.001? Note the cost.
- Prediction health: check finite range and unique-value diagnostics — a near-collapsed
  run is suspect even if its headline metric looked fine.

### 3. program.md — the decision history
Read the Log. Why did the study change direction? What was decided at each phase
boundary? The narrative explains WHY the trajectory bends where it does.

### 4. method_card.md — the priors
Pull the falsifiable priors from part 4 of the method card. Each becomes a verdict in
section ① and a row in section ②. Where results CONTRADICT a prior, say so explicitly — a
refuted prior is the most valuable kind of finding.

### 5. playbook.md — the pre-clustered map
The Ruled-out table seeds the discard-cluster analysis (it already names the theme and
the evidence IDs); the Current-best history cross-checks each track's frontier; open
hypotheses that were never tested become ⑦ "what to try next" candidates.

### 6. the predictions ledger — the verdicts you copy, never re-decide
`klein predict list --study <dir>` prints every `P#` with its ledger verdict
(supported / refuted / inconclusive / open), the evidence ids that adjudicated it, and
the rule. Section ② is COPIED from it. An open prediction is a finding in itself
("not adjudicated because …") and `klein finalize` will refuse it unless the reason is
recorded; a refuted prediction must already have a dated `Decision:` line in
`program.md` — if it does not, the study is not finished, write the decision now with
the date it is actually written.

Registered tracks (`mode: registered`) have no keep chain: mine their cells as a
measurement program — which cells ran, which artifacts they pinned (`art:` aliases),
which predictions they adjudicated — and never manufacture a frontier from them.

## Pricing studies: the eval-card exhibit (insurance profile; optional accelerator)

For frequency/severity/pure-premium studies under the `insurance` profile
(`references/profiles/insurance.md`), an underwriting-ready eval card of the
incumbent is a synthesis exhibit worth attaching. Other profiles skip this section.

- **If the `pricing-eval` skill is available** (check: does
  `~/.claude/skills/pricing-eval/SKILL.md` exist? — an example binding from the
  author's harness; any eval-card tool with the same input contract works): export
  holdout predictions with `kleinlib.eval.save_holdout_predictions(...)` (columns
  `y_true`, `y_pred`, `weight` + rating dims, written under the gitignored
  `predictions/`) and run the card per that SKILL.md. Tweedie power is
  dataset-dependent: **1 = frequency (Poisson), 2 = severity (Gamma), 1<p<2 = pure
  premium**. Commit the card and its small charts; never the predictions table.
- **Else:** `kleinlib.figures.standard_regression_report` — the bundled Lorenz,
  CAS-style lift/quantile, and A/E calibration-by-decile figures cover the same
  ground (`make_figures.py` regenerates them from `models/latest_val_preds.npz`).

## Write findings.md — exactly seven sections

Copy `assets/findings-template.md`. Fill, in order:

- **① Research-question verdicts.** One row per RQ in study.yaml, each with a stable
  claim ID (`**[C1]**...`, fully qualified `<study_id>#Cn`, never renumbered): supported / refuted /
  inconclusive, with evidence experiment IDs and the metric delta. Label every verdict
  `exploratory` (development only) or `confirmed` (its track has sealed-test evidence).
- **② Registered predictions (from the ledger).** One row per `P#`, verdict copied
  from `klein predict list`, the observed value, the evidence ids, and — for a refuted
  row — the dated `Decision:` line in `program.md` that answered it.
- **③ Surprises & why.** What defied the prior — AND the mechanism you believe explains
  it. A surprise with no explanation is a loose end.
- **④ Practical advice.** "On your own data do X, avoid Y" — concrete, numbered, in the
  best-practices voice.
- **⑤ {{SECTION5_HEADING}}.** The heading and prompt come from the study's profile
  (`references/profiles/<profile>.md` §2): "Implications" for generic, "Practitioner
  impact" for ml-research, "Consequences for the conjecture or bound" for math,
  "Business / actuarial value" for insurance. Price nothing without a registered
  `materiality:` block.
- **⑥ Literature tie-back.** Did results match the method-card papers? Where do they sit
  against the trend?
- **⑦ What to try next.** The next 2-4 experiments, in priority order.

## Author the lock

With findings drafted, produce `claims.lock` (`references/claims-protocol.md`):

```bash
uv run --locked klein claims init   --study <dir>                       # claims from the **[Cn]** lines
uv run --locked klein claims pin    --study <dir> results results.tsv    # every artifact a number lives in
uv run --locked klein claims number --study <dir> <alias> --value … --art … --claim Cn
uv run --locked klein claims add    --study <dir> Cn --class … --strength … --claim "…" --numbers … --evidence …
uv run --locked klein claims verify --study <dir> --numbers
```

Every claim gets its class (five classes, each with a strength ceiling) and a strength
no higher than the evidence kinds its track's `confirmation.require` demands; every
numeral in a claim sentence is an alias in `numbers`. The lock is authored AFTER the
sealed evidence exists, never before.

## Quality bar (enforce before you finish)

- EVERY claim cites evidence ids. No claim without evidence.
- Every discard, crash and measured cell is cited somewhere in findings or program —
  `klein verify --evidence-use` reports the rate; a rate below 1.0 needs a sentence
  naming what was left uncited and why.
- Every RQ has a verdict; every prediction has a verdict. A missing verdict = an
  unfinished study.
- Contradictions with method-card priors are called out explicitly, not smoothed over.
- Deltas are signed and unit-bearing. "Better" is not a finding; "+0.0021 val_auc (E12
  vs E7)" is.
- Do not call a small delta real, material, or decisive without configured minimum
  delta plus appropriate uncertainty evidence. State what remains uncertain.
- No number appears that cannot be traced to a pinned artifact — the numbers law of
  `references/claims-protocol.md`; `klein verify --numbers` scans for you.
- The profile's banned words are absent or qualified (`references/profiles/<profile>.md` §7).

## Cross-study writeups (optional accelerator)

Surveys or comparisons spanning several studies (or an external paper corpus) are
outside findings.md's scope. If a corpus-synthesis skill is available (example
binding from the author's harness: a paper_book-style corpus repo whose
`/synthesize` emits per-claim-cited writeups), hand it the studies' `findings.md`
claim IDs; else author the doc by hand under `docs/` with the same typed
citations. findings.md remains the per-study source of truth either way.

## Hand off to the referee

**First, confirm `program.md`'s `## Roster` is complete** — `experimenter`,
`data-gate auditor` and `lead` filled with model · tool · session, and `since` dates
that cover the loop. The referee reads that table for the independence rung
(`references/referee-protocol.md`); a blank experimenter row caps the study's rung at
"fresh session" no matter which model actually referees, and the synthesist is the
last reader who still knows who ran what. Fill any row the loop left blank now.

Do not record anything after the lock verifies. The orchestrator invokes REFEREE
(`references/referee-protocol.md`) in a fresh context on a different model; the
referee reads `findings.md` before `program.md`, runs the verifiers, and writes
`referee_report.md`. Only after `klein gate record referee` does `klein finalize` run.
A synthesist who also referees has audited nothing.

## Promotion to knowledge/ (closing the Klein bottle)

A statement promotes into `knowledge/` — the field's `knowledge/domains/<profile>/`
for domain lessons, `knowledge/research-discipline.md` for process lessons — only
WITH at least one claim citation —
`(supports <study_id>#Cn)` or `(refutes <study_id>#Cn)` — so every knowledge line
remains greppably traceable to the evidence that earned it
(`grep -rn "#C[0-9]" knowledge/`). When two knowledge lines cite claims that
refute each other, surface the contradiction in the doc text; do not silently
keep both. Ruled-out rows from `playbook.md` promote the same way. No graph
engine, no registry file — the markdown convention IS the mechanism.
