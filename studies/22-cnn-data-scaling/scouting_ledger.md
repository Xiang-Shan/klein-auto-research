---
type: scouting-ledger
study: "22-cnn-data-scaling"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 22-cnn-data-scaling

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

One thing was looked at before this contract was written (lead agent, 2026-11-03): the
four downloaded files' sizes and sha256 digests, to pin them. No image or label was read,
nothing was trained. The exponent ranges in the priors are recalled from the literature and
are verified at METHOD.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-11-03 | the four Fashion-MNIST IDX .gz files from raw.githubusercontent.com/zalandoresearch/fashion-mnist (master) and its LICENSE | sizes 26,421,880 / 29,515 / 4,422,102 / 5,148 bytes; sha256 in study.yaml; MIT | file identity | pin all four (`data.source` + `data.inputs`) |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
