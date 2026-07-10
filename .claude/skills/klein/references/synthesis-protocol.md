# SYNTHESIZE — mine the trajectory into findings

The stage that makes it research, not experiment-running. Mine the full study trajectory
and write `findings.md` with EXACTLY seven sections. Every claim cites experiment IDs.

Role: synthesist. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-synthesist` worker.

## Mine four sources

### 1. results.tsv — the keep-chain and the discards
- **Keep-chain deltas.** List the `status=keep` experiments in order; the metric deltas
  between consecutive keeps are the story of what actually moved the number.
- **Discard clusters.** Group discards by theme (an encoder family, a model class, a
  regularization sweep). A cluster of discards is EVIDENCE — "we tried five imbalance
  strategies; none beat cw=None" is a finding, not a gap.
- **Crash audit.** Read every `crash` row. Was it a bad idea or a bug that killed a good
  idea? A crashed direction never retried is a caveat, not a verdict.

### 2. aux_metrics.tsv — the tradeoffs
- Rank-vs-calibration: did the best-AUC model also have the best brier/logloss, or did
  ranking and calibration trade off? For actuarial use, calibration often matters more
  than rank.
- Wall-clock: was the best model 10× slower for +0.001? Note the cost.
- Prediction health: check `min_proba_std` — a near-collapsed run is suspect even if its
  headline metric looked fine.

### 3. program.md — the decision history
Read the Log. Why did the study change direction? What was decided at each phase
boundary? The narrative explains WHY the trajectory bends where it does.

### 4. method_card.md — the priors
Pull the falsifiable priors from part 4 of the method card. Each becomes a verdict in
section ① and a row in section ②. Where results CONTRADICT a prior, say so explicitly — a
refuted prior is the most valuable kind of finding.

## Write findings.md — exactly seven sections

Copy `assets/findings-template.md`. Fill, in order:

- **① Research-question verdicts.** One row per RQ in study.yaml: supported / refuted /
  inconclusive, with evidence experiment IDs and the metric delta.
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
- No number appears that cannot be traced to results.tsv or aux_metrics.tsv.
