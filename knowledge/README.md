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

## Claim citations (required at promotion)

Promoted statements carry at least one typed claim citation —
`(supports 02-rqls-pv-severity#C3)` / `(refutes 01-dae-claims#C1)` — pointing at a
stable claim ID in that study's `findings.md`. Optional frontmatter `claims:` may
list the IDs a doc leans on. Everything stays greppable:
`grep -rn "#C[0-9]" knowledge/`. Two lines citing claims that refute each other is
a contradiction to surface in prose, never to keep silently.

Promotion can continue outward: a finding that belongs in a personal topic vault
(the author's harness registers note vaults with Q&A and concept-page skills; any
equivalent store works) travels **with** its typed claim citations —
`(supports <study_id>#Cn)` — so a vault line stays greppably traceable back to
study evidence, exactly like lines in this directory.
