---
type: scouting-ledger
study: "23-lalonde-causal-replication"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 23-lalonde-causal-replication

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

Two things were looked at before this contract was written, both by the lead agent on
2026-11-03 while confirming that the pinned files are the ones the paper used: the
three files' shapes and the two raw differences in means listed below, and the
published tables of Dehejia & Wahba's NBER working paper w6586 (the targets
themselves). Nothing else was computed — no regression, no standard error, no
propensity score. The two values seen are anchors: no registered prediction is
scored on them (P1 is decided by the adjusted values and the standard errors as
much as by them, and RQ2 carries no prediction).

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-11-03 | `nsw_dw.dta`, `psid_controls.dta`, `cps_controls.dta` from users.nber.org/~rdehejia/data (sha256 pinned in study.yaml) — shapes and treatment counts | 445 NSW rows (185 treated, 260 controls), 2,490 PSID rows, 15,992 CPS rows; identical column sets | file identity, not an outcome | pin the three files; predefined lanes train / development / test |
| S2 | 2026-11-03 | raw differences in mean `re78`: NSW treated − NSW controls; NSW treated − PSID controls | 1,794.34 and −15,204.78 | both equal published Table 3 column (1) values; seen, so they are anchors only | no prediction is scored on these two numbers alone; RQ1 and RQ2 priors are labelled `(source: scouted)` |
| S3 | 2026-11-03 | Dehejia & Wahba, NBER w6586 (1998), Tables 1-3 and notes (pdftotext of the NBER PDF) | Table 3 columns (1)-(2) for NSW, PSID-1, CPS-1 with standard errors; the regression covariates (note a) and the PSID-1 logit (note c) | these ARE the published targets a replication is scored against | transcribed into `lib/lalonde.py:TARGETS`; CPS-1 targets belong to the sealed lane |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
