---
type: scouting-ledger
study: "21-bloodmnist-cnn"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 21-bloodmnist-cnn

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

One thing was looked at before this contract was written: the downloaded archive's
array shapes, to confirm the file is the 28-pixel BloodMNIST the pin names. No image
was viewed, no label counted per class, nothing trained. Published MedMNIST v2
numbers quoted in the priors are recalled, not read here, and are verified at METHOD.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-11-03 | `bloodmnist.npz` from zenodo.org/records/10519652 — array names, shapes, dtypes | train 11,959 / val 1,712 / test 3,421 images, 28 x 28 x 3 uint8, labels (N, 1) | file identity, not an outcome | pin the file (sha256 in study.yaml); keep the official split |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
