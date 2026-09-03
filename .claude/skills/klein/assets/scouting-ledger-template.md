---
type: scouting-ledger
study: "{{STUDY_ID}}"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — {{STUDY_ID}}

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`;
> on schema 3 that gate hashes this file into the consult record, so an edit afterwards
> fails `klein verify` until the gate is re-recorded with a reason — and a study that
> keeps no ledger records `scouting_ledger: absent` instead, so the absence is itself
> on the record. `klein new` scaffolds one (this shape, with a "nothing scouted before
> the gate" default entry); studies 07, 08 and 09 kept theirs by hand. It is the
> mechanism that keeps "pre-registered" honest.

## §0 Disclosure

What was computed, read, or plotted before the contract was written, and why none of
it is evidence: {{one paragraph}}. Values seen here may seed anchors and identity
checks; they may never be scored predictions.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | … | … | … | design-time, unregistered, no floor | becomes the E0001 identity anchor |
| S2 | … | … | … | … | retired — see below |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: …

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
