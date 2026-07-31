# Lineage — the ancestor archive

Klein descends from two working systems, in order:

1. **karpathy/autoresearch** — the original idea: `program.md` + an
   edit-`train.py` loop; the simplicity criterion; "the agent IS the loop".
2. **elan-elan/agent-smith** — the loop packaged as a portable agent skill,
   proven on a 215-experiment insurance-claims campaign (Apr 28–30 2026,
   best val_auc 0.6715 from a cross-family soft vote).
3. **Klein** (this repo) — the six-stage gated lifecycle, `kleinlib`, the
   v2 evidence transactions, and everything the CHANGELOG records.

The author's local agent-smith working copies were retired on 2026-07-31
(full git history preserved in `agent-smith-history-2026-07-31.bundle`,
kept beside this repo in the author's workspace). Two design documents from
that era are load-bearing for understanding WHY Klein looks the way it does,
and are archived here **verbatim**:

| File | Origin (historical local path) | Date | What it is |
|---|---|---|---|
| `2026-05-20-agent-smith-evaluation.md` | `Auto_research/agent-smith-EVALUATION.md` | 2026-05-20 | Quality audit of the agent-smith skill + demo (★★★★½ overall; the "results.tsv column-order" critical bug and the 10 broken-items list that seeded Klein's schema discipline) |
| `2026-06-smith-skill-optimization.md` | `Auto_research/agent-simith-demo-insurance_claims/docs/smith_skill_optimization.md` | 2026-06 | Proposal log from the 215-experiment campaign — the ten pain points (aux metrics, phase budgets, research-question tracking, best-model snapshots …) that became Klein v0.1's feature list |

Archived verbatim: machine paths inside these two documents are
**historical, not normative** — nothing in Klein reads them. Deliberately
NOT archived: the campaign's `docs/insights_and_framework.md` (already
ported as `knowledge/insights-and-framework.md`), derived artifacts
(`phase5_base_preds.npz`), and two uncommitted tracked tweaks in the demo
worktree (superseded by Klein's own implementations).

The campaign's scientific residue lives on in `knowledge/` (the four ported
synthesis docs) — this directory holds only the framework-design history.
