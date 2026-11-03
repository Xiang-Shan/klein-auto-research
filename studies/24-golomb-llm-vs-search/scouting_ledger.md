---
type: scouting-ledger
study: "24-golomb-llm-vs-search"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 24-golomb-llm-vs-search

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

Nothing about this study's arms was computed before this contract was written. The one
model request made on this machine before the gate (study 20's connectivity check, a
multiplication prompt) is not about Golomb rulers. The optimal lengths are OEIS A003022
values, recalled and re-checked against OEIS by prepare.py's author before the DATA gate.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-11-03 | OEIS A003022 (optimal Golomb ruler lengths), recalled | 0, 1, 3, 6, 11, 17, 25, 34, 44, 55, 72, 85, 106, 127 for orders 1-14 | reference values the verifier compares against, not a result | re-checked against oeis.org before DATA; frozen in instance.json |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
