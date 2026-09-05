# PHASE RITUAL — the slate at every phase start

At every phase start — immediately after the previous phase's acknowledgement is
recorded (`klein gate record phase --phase <id>`) — lay out a slate of candidate
experiments BEFORE touching the mutable surface. Output: a `### Phase <id> slate` block in
`program.md` and a refreshed "Next-best candidates" section in the study playbook
(`playbook.md`). Re-read the playbook first so the slate never re-proposes a
direction already ruled out with evidence.

Role: the driving agent — or the human at the wheel. No dedicated worker exists and
none is missing: proposing and choosing is the loop's judgment layer.

## 1. Propose 4–6 candidates

Each candidate is ONE falsifiable hypothesis achievable in ONE candidate transaction
— for a `predict` track typically a small `train.py` diff (the size is profile
guidance, not a rule: one idea per candidate, whatever the diff); for a **registered
track a candidate is a cell**: which measurement, on which partition, adjudicating
which `P#`, at what cost. "Try feature engineering" is not a candidate; "log1p the
three right-skewed numerics: +0.002 val_auc" is; "bootstrap CI of K, 1000 resamples,
seed block A, adjudicates P4" is. Draw from the playbook's open hypotheses, the
method card's when-it-pays conditions, and the contract's `predictions`.

On a **generation-enabled study** (`references/generation-protocol.md`) the same 4–6
candidates are also written as rows of `slates/<phase>.yaml`, and each row carries four
more fields so the forecast can be scored later against what actually happened:

- `p_success` — your probability this candidate succeeds, strictly inside (0, 1).
- `success_P` — the registered predictions that DEFINE success for this row. Every one
  needs a rule and this row's track, because `run-one --tests` is what decides them.
- `provenance` — `unscouted` (a fresh forecast), `derived` (read off an earlier `#Hn`),
  or `scouted` (the scouting ledger already saw the outcome). Scouted rows are computed
  into a descriptive panel and never summarised as calibration.
- `expected_effect` + `units`, against a `floor_ref` — the size you expect, and the
  floor it must clear: the track's `minimum_delta`, or a registered `sweep:<name>`. This
  is where the testability axis stops being a feeling: an expected effect below its own
  floor cannot be decided by one run.

## 2. Score each candidate 1–3 on three axes

- **Novelty** — touches a lever none of the last 5 experiments touched.
  3 = untouched lever family; 2 = touched lever, genuinely new setting; 1 = re-tread.
- **Testability** — the diff runs inside `max_run_seconds`, and the outcome is
  decidable against the track's `minimum_delta`. A predicted move smaller than the
  minimum delta cannot be decided by one run: score 1.
- **Expected information** — EITHER outcome (keep or discard) moves a research
  question, a registered prediction, or an open hypothesis. If only a win teaches
  anything, score 1.

Sum the axes. Break ties by expected information, then testability — a decidable
answer to a live question beats a bold idea the budget cannot judge.

## 3. Record the slate in program.md

Append the scored table, the chosen candidate, and a ONE-line rationale under the
fixed heading `### Phase <id> slate` (the fixed heading is what makes slates
greppable across the whole program history). The unchosen candidates are not
discarded — they are the queue.

## 4. Mirror the survivors into the playbook

Copy the ranked non-chosen candidates into the playbook's "Next-best candidates"
section, replacing whatever staled there. When an experiment later lands somewhere
unexpected, the next candidate comes from this list — or from a fresh slate if the
result invalidated it.

## What this ritual is NOT

No Elo, no judge model, no tournament, no helper code proposes, scores, ranks, or
selects. It is a thinking procedure any agent or human runs in minutes with nothing but
the study files. The scores are coarse on purpose (1–3, three axes): their job is to
force the comparison to be written down, not to pretend a ranking model exists. Do not
automate it.

A **generation-enabled study** additionally RECORDS the slate (`klein generation slate
lock`), gives each candidate a `<study>#Hn` id, and at phase end COMPUTES the Brier
score of the forecasts the driver wrote (`klein generation slate score`). That
bookkeeping is arithmetic on authored rows and does not automate the ritual: the layer
still writes no candidate, compares none, and orders none — the 1–3 scores are copied
verbatim into the record and never fed to a comparison.

## Worked example

```markdown
### Phase adaptive-2 slate

| # | H | Candidate (one hypothesis, one transaction)                | Nov | Test | Info | Σ |
|---|---|------------------------------------------------------------|-----|------|------|---|
| 1 | #H7  | Target-encode `region` (smoothing=20): +0.004 val_auc  | 3   | 3    | 3    | 9 |
| 2 | #H8  | log1p the 3 right-skewed numerics: +0.002 val_auc      | 2   | 3    | 3    | 8 |
| 3 | #H9  | Interaction `age×vehicle_power` in the GLM: +0.002 val_auc | 2 | 3  | 2    | 7 |
| 4 | #H10 | Drop the 2 near-constant flags: no change (cleanup)    | 3   | 2    | 1    | 6 |
| 5 | #H11 | Swap OHE→ordinal for the GBDT: +0.001 val_auc          | 1   | 2    | 2    | 5 |

Chosen: #1 — highest-information untouched lever; RQ2's encoder prior gets a
direct test either way.
```

The `H` column is empty on an ordinary study and carries the ids `klein generation slate
lock` assigned on an enabled one — the same table, greppable either way.
