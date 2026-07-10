---
title: "Method Cards — Index & Authoring Contract"
type: reference
domain: ml
status: seed
concepts: [method-card, method-gate, authoring-contract, five-part-arc, seed-cards]
related: [glm-pricing.md, gbdt-tabular.md]
---

# Method Cards

A **method card** is the reusable seed for the METHOD gate (Gate 2). It teaches a method
once — intuition, math, a minimal implementation, and the honest boundary of where it
pays — so that a study's per-study `method_card.md` can instantiate it against that
study's data instead of re-deriving from scratch. Cards live here; the gate that grades
and instantiates them is the framework's METHOD stage.

## Index

| Card | Method | Domain | Status | Anchored in |
|---|---|---|---|---|
| [`glm-pricing.md`](glm-pricing.md) | GLM / logistic regression for insurance risk | insurance | seed | campaign Phase 1 (LR 0.6255 → 0.6528) |
| [`gbdt-tabular.md`](gbdt-tabular.md) | GBDT three-family landscape (LGBM / XGB / CatBoost) | ml | seed | campaign Phase 3 (0.6701 single, 0.6715 soft-vote) |
| [`dae-tabular.md`](dae-tabular.md) | Swap-noise denoising-autoencoder representations | ml / insurance | validated — Study 01 | study 01 (DAE→LGBM 0.6683 < MLP 0.6706 ≈ GBDT 0.6701; imputer 3.4×; anomaly no) |
| [`quantile-least-squares.md`](quantile-least-squares.md) | Robust quantile least squares for loss severity | insurance | validated — Study 02 | study 02 (QLS-OLS 1.083× MLE; MLE 352% vs QLS 50% @ ε=10; window ≫ trim; $2M cap bounds GPD tail to +0.17%; the cancellation caveat) |

Studies **01** and **02** have each promoted their card at the SYNTHESIZE stage
(`dae-tabular.md`, `quantile-least-squares.md`) — both promised cards are now delivered and
`validated`. The remaining `seed` cards (`glm-pricing.md`, `gbdt-tabular.md`) instantiate
against their next study; the index is the single place to see what methods the framework
knows.

## Authoring contract

- **Five-part arc, in order:** ① practitioner intuition → ② math core → ③ minimal
  from-scratch implementation sketch → ④ when-it-pays / when-it-doesn't → ⑤ verified
  references. 80–150 lines.
- **Frontmatter:** `type: method-card`, `domain`, `status` (`seed` | `planned` |
  `active`), `concepts` (5–10 kebab-case), `related` (sibling cards + relevant
  `knowledge/` docs).
- **Accuracy rule:** every number or claim comes from a cited source — a `knowledge/`
  doc, a study's `results.tsv`, or a verified paper. Never invent or "improve" a finding;
  mark any needed-but-absent fact `[TODO: verify]`.
- **Boundary honesty:** part ④ must state where the method *loses*, not just where it
  wins. A card that only sells the method fails the gate.

The authoritative protocol — how the METHOD gate produces, grades, and instantiates a
card — is `../.claude/skills/klein/references/method-gate-protocol.md`. A seed card here
is the reusable teaching artifact;
the Gate-2 `method_card.md` inside a study is that card instantiated against the study's
data, target, and metric.
