---
type: method-card
domain: "{{DOMAIN}}"
status: draft
concepts: []
related: []
refs_verified: false   # set true ONLY after every reference below is verified
---

# Method card — {{METHOD_NAME}}

> Gate 2 (METHOD). Pedagogy for an unfamiliar or frontier method, written BEFORE
> modeling. Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.
> The five parts are an authoring ARC — write them in order.

## 1. Intuition (for a practitioner)

Explain it to an actuary / data scientist who has NOT read the paper. Lead with an
analogy to something they already know (e.g. "a denoising autoencoder is nonlinear
PCA"). No equations yet — build the mental model first.

## 2. Math core

Notation table first, then the ≤5 load-bearing equations. Define every symbol.

| Symbol | Meaning |
|---|---|
| … | … |

$$ \text{key equation here} $$

## 3. Minimal from-scratch implementation plan

numpy / sklearn-level pseudocode — the smallest honest version, no framework magic.
Name the kleinlib helpers it will lean on (`kleinlib.torch_loop` for MPS-safe
batching, `kleinlib.encoders`, `kleinlib.eval`). This is the plan train.py realizes.

## 4. When it pays / when it doesn't

A regime table keyed on data size and signal strength — the honest verdict.

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| … | … | … | pays / doesn't |

**Falsifiable priors this study will test** (mirror to
`study.yaml:predictions_to_falsify`): list the specific, checkable predictions the
method card commits to — SYNTHESIZE will hold each to account.

## 5. Verified references

Verify EACH via `alphaxiv-paper-lookup` / `paper_search` / WebSearch. Mark anything you
could not verify CLEARLY — an unverified reference is a liability, not a citation.

| Reference | Where | Verified? |
|---|---|---|
| Author Year, Title | venue / arXiv:id | ✅ / ⚠️ UNVERIFIED |

- Frontier methods REQUIRE a lit-scan step before this card is complete.
- When every row is verified, set `refs_verified: true` in the frontmatter.
