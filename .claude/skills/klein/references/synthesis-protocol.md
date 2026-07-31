# SYNTHESIZE — mine the trajectory into findings

The stage that makes it research, not experiment-running. Mine the full study trajectory
and write `findings.md` with EXACTLY seven sections. Every claim cites experiment IDs.

Role: synthesist. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-synthesist` worker.

## Mine five sources

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

## Write findings.md — exactly seven sections

Copy `assets/findings-template.md`. Fill, in order:

- **① Research-question verdicts.** One row per RQ in study.yaml, each with a stable
  claim ID (`**[C1]**...`, fully qualified `<study_id>#Cn`, never renumbered): supported / refuted /
  inconclusive, with evidence experiment IDs and the metric delta. Label every verdict
  `exploratory` (development only) or `confirmed` (its track has sealed-test evidence).
- **② Predictions to falsify (filled).** Copy each lever from program.md; fill observed
  Δ, verdict (held / falsified), and the evidence exp IDs.
- **③ Surprises & why.** What defied the prior — AND the mechanism you believe explains
  it. A surprise with no explanation is a loose end.
- **④ Practical advice.** "On your own data do X, avoid Y" — concrete, numbered, in the
  best-practices voice.
- **⑤ Business / actuarial value.** Premium, calibration, filing, capital, triage — what
  the result is WORTH in decisions.
- **⑥ Literature tie-back.** Did results match the method-card papers? Where do they sit
  against the trend?
- **⑦ What to try next.** The next 2-4 experiments, in priority order.

## Quality bar (enforce before you finish)

- EVERY claim cites experiment IDs. No claim without evidence.
- Every RQ has a verdict; every prediction has a verdict. A missing verdict = an
  unfinished study.
- Contradictions with method-card priors are called out explicitly, not smoothed over.
- Deltas are signed and unit-bearing. "Better" is not a finding; "+0.0021 val_auc (E12
  vs E7)" is.
- Do not call a small delta real, material, or decisive without configured minimum
  delta plus appropriate uncertainty evidence. State what remains uncertain.
- No number appears that cannot be traced to results.tsv or aux_metrics.tsv.

## Promotion to knowledge/ (closing the Klein bottle)

A statement promotes into `knowledge/` only WITH at least one claim citation —
`(supports <study_id>#Cn)` or `(refutes <study_id>#Cn)` — so every knowledge line
remains greppably traceable to the evidence that earned it
(`grep -rn "#C[0-9]" knowledge/`). When two knowledge lines cite claims that
refute each other, surface the contradiction in the doc text; do not silently
keep both. Ruled-out rows from `playbook.md` promote the same way. No graph
engine, no registry file — the markdown convention IS the mechanism.
