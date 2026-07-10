---
title: "Klein Auto Research — Knowledge Base"
type: reference
domain: ml
status: seed
concepts: [knowledge-base, provenance, frontmatter-conventions, synthesize-loop, method-cards]
related: [insights-and-framework.md, method_cards/README.md]
---

# knowledge/ — the framework's seed knowledge base

Durable, cross-study knowledge: what the framework has learned that outlives any one
study. Two kinds of file live here.

- **Ported synthesis / reference docs** — the distilled deliverables of the 2026-04
  ancestor model-survey campaign (215 experiments on insurance-claims, best val_auc
  0.6715 — the campaign Klein's loop contract descends from), ported faithfully
  (findings unchanged): `insights-and-framework.md`,
  `best-practices-auto-insurance.md`, `gbdt-hyperparameter-guide.md`,
  `encoder-comparison.md`.
- **Seed method cards** — `method_cards/`, the reusable teaching seeds for the METHOD
  gate (`glm-pricing.md`, `gbdt-tabular.md`; studies 01/02 add two more).

**Provenance.** Every ported doc carries a one-line banner under its H1 and a `source:`
frontmatter field naming the campaign document it was ported from; the originals live
in that campaign's private lab. Numbers come from the sources — the port never
rewrites a finding.

**Frontmatter conventions** (simple YAML, self-contained to this repo): `title`, `type` (`synthesis` | `reference` | `retro` | `method-card`),
`domain` (`insurance` | `ml`), `status` (`ported` | `seed`), `concepts` (5–10
kebab-case), `related` (sibling files); ported docs also carry `source`. Every file in
this directory — including these READMEs — has valid YAML frontmatter.

**The SYNTHESIZE feedback loop.** Closing a study, the SYNTHESIZE stage writes that
study's `findings.md` (RQ verdicts, predictions-to-falsify, practical advice). When a
finding generalizes beyond its study, it is promoted back into this directory — a new or
updated synthesis doc, or a new method card — so the next study starts from accumulated
knowledge instead of a blank page. That is the Klein-bottle loop: a study's output feeds
the framework's own input.
