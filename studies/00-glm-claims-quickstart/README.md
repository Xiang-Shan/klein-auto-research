# 00 — GLM claims quickstart

**Start here.** The onboarding study: GLM → gradient-boosting baselines on real
auto-insurance claims data (58,592 policies, bundled in this repo), exercising the
full Klein artifact set — ledger, cards, findings, tutorial — in ~10 minutes.

## Reproduce it right now (no credentials, no private infra)

```bash
uv run prepare.py     # resolves the repo-bundled dataset; prints "data source: bundled"
uv run train.py       # the committed winner (exp 6): HGBT, learning_rate=0.06
```

Expected `primary_metric: 0.664322` — exact on the reference setup (Python 3.13,
macOS arm64), and guaranteed within this study's own ±0.001 gate anywhere (CI
asserts exactly that on ubuntu for every push). The 6-experiment journey and the
per-experiment reasoning live in `results.tsv` + `program.md`; the verdicts in
`findings.md`; the teaching write-up in `report/index.html` (open it from `file://`
— fully self-contained).

## Note for cloners — provenance of hashes and anchors

This study was **executed in the Klein development lab** before this repository's
public history began, so:

- The `commit` column in `results.tsv` — and quoted commands like
  `git show b1389ca:...` (e.g. in `sweeps/hgbt_lr.py`) — refer to the *lab's* git
  history, not this clone's. The final state of every winning config is what you
  see in the committed `train.py` / `sweeps/`. Studies **you** run in this clone
  write hashes that resolve here.
- The "campaign anchors" this study reproduces (LR 0.6255, HGBT 0.6629, …) come
  from a 215-experiment ancestor campaign in a private lab; its distilled findings
  ship in this repo under `knowledge/` (`best-practices-auto-insurance.md` and
  siblings), so every claim is checkable against shipped documents.
- The executed ledger, findings, and program notebook are **immutable exhibits**.
  To continue the study, branch (`git checkout -b experiments/00-glm-claims-quickstart`)
  and append new experiments — never edit history.
