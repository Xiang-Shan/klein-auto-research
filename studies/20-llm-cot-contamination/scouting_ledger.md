---
type: scouting-ledger
study: "20-llm-cot-contamination"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 20-llm-cot-contamination

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

Three things were looked at before this contract was written (lead agent, 2026-11-03):
one connectivity request to the model (not a benchmark item), the first line of the
bundled GSM8K file (to confirm the format), and the provider's terms and pricing pages.
No benchmark item was sent to the model; no score of any kind was computed.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-11-03 | one `qwen-flash` chat completion on DashScope's compatible-mode endpoint: "What is 17*23? Reply with only the number." (temperature 0) | "391"; 23 prompt / 3 completion tokens | a connectivity check on a non-benchmark prompt; it says the model can multiply two 2-digit numbers, nothing about GSM8K | endpoint and model id fixed in `calls:`; no prediction depends on it |
| S2 | 2026-11-03 | `datasets/gsm8k-test/test.jsonl` from openai/grade-school-math: line count and the first record | 1,319 records; `question` / `answer` with the gold after `#### ` | file identity | bundle with its MIT licence |
| S3 | 2026-11-03 | Alibaba Cloud Model Studio terms (service agreement, service-specific terms) and model pages | API data is the customer's; labelling duty; no training of competing models; trial outputs restricted; no qwen-flash price on the official page | governs what may be committed, not what the model does | outputs committed with an AI-generated label; costs in tokens, not dollars |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
