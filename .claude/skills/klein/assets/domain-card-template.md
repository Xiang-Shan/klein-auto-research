---
# domain_card.md — what the field already knows, frozen before CONSULT.
#
# Locked by `klein generation expert lock`, which hashes this file and copies the
# frontmatter verbatim into a write-once object anchored BEFORE the consult gate.
# Do not hand-edit after the lock: an edit fails `expert card`. A change is
# `klein generation expert amend`, and it may NOT move a baseline target.
#
# Protocol: .claude/skills/klein/references/expert-protocol.md
# Records:  .claude/skills/klein/references/reference-protocol.md

type: domain-card
study: NN-slug
scope: one line naming the task, the data family and the decision this card covers
as_of: YYYY-MM-DD

# Every source this card rests on. Each record_id must already resolve to
# knowledge/references/<id>.json (`klein generation reference record`).
# role: doctrine | pipeline | metric | incumbent | pitfall
sources:
  - record_id: author2020
    role: doctrine
  - record_id: author2023
    role: incumbent

# What the field actually RUNS, end to end. Non-empty.
pipeline_steps:
  - ingest and validate the policy/claim tables
  - build the exposure offset
  - fit the frequency model
  - calibrate and evaluate

# What the field actually MEASURES. Non-empty.
metrics:
  - weighted Poisson deviance
  - normalized Gini

# What practitioners hold to be true. May be empty — but an empty list is a claim.
doctrine:
  - trees still win on most tabular data at this scale

# The mistakes the field already knows about. May be empty.
pitfalls:
  - class-weight reweighting destroys calibration on weak-signal data

# The published or in-house result this study is measured against.
incumbent: the published recipe reports a weighted Poisson deviance of 0.4551

# The methods METHOD will choose FROM. Non-empty, and it precedes the choice:
# writing the shortlist after the method is chosen is writing the exam after the answer.
method_shortlist:
  - Poisson GLM with an exposure offset
  - Tweedie GBDT

# The recipe this study will REPRODUCE before it proposes anything of its own.
baseline:
  # Both paths must exist in the study at lock time.
  implementation: lib/baseline_glm.py
  fixture: data/prepared/baseline_fixture.csv
  # A study-relative path, or an inline mapping.
  config:
    link: log
    offset: log_exposure
  # FROZEN AT LOCK. `key` is the metric key the run will PRINT; `tol >= 0`;
  # `rel: true` reads the tolerance as a fraction of `value`. A repair changes the
  # IMPLEMENTATION — never these numbers. A target change requires a successor study.
  targets:
    - {key: primary_metric, value: 0.4551, tol: 0.0005, rel: false}
  # What the driver INTENDS: source-reconstructed | independent. The recorded
  # reviews decide the outcome; this word does not.
  review: source-reconstructed

# What this card does NOT know. An empty list is a claim, not an omission.
unknowns:
  - how the incumbent partitioned its data
---

# Domain card — NN-slug

## What the field runs

Prose for the profile's audience: the pipeline above, in sentences, with the
choices that are load-bearing and the ones that are conventional.

## What the field measures, and why those metrics

One paragraph per metric: what it rewards, what it hides, and the estimand it is
computed at.

## Doctrine and pitfalls

The rules of thumb a practitioner would state without looking anything up — each
one traceable to a `sources[]` record, and each one falsifiable by this study.

## The incumbent and the baseline recipe

What is being reproduced, from which source, with which fixture, and why THESE
targets and tolerances are the right bar. State what a miss would mean.

## Unknowns

What this card could not establish, and what would settle each one.
