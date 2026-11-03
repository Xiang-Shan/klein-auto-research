# Profile: llm

For studies whose object is a language model's behaviour — a prompting or decoding
strategy, a benchmark score, a fine-tune, an agent scaffold, an LLM used as a judge —
measured on a set of items through an API or a local checkpoint.

## 1. Audience
An ML or NLP researcher who knows that benchmark numbers move with the prompt, the
decoding parameters, the model version and the item set, and who will ask "on which
items, with which model snapshot, and could it have seen them?" before "by how much?".

## 2. §⑤ heading
**⑤ What changes in practice — for whoever prompts, evaluates or deploys this model.**
Prompt: state the change (prompt, decoding, scaffold), the exact model identifier and
date it was measured on, the item set and its contamination status, the paired effect
with its interval, and what it cost in tokens per item.

## 3. Doctrine
The item is the unit of uncertainty: a benchmark score is reported with an interval
over items (`kleinlib.eval_items.evaluate_items`, cluster-resampled when items share a
passage or template), and two configurations are compared PAIRED on the same items
(`metrology.paired_item_bootstrap`, `metrology.mcnemar_exact`), never as two marginal
means. Every model call goes through the call ledger (`kleinlib.calls`), so the exact
request, response, model id, parameters and token usage are pinned and the study
re-verifies offline; re-querying is a replication, replaying the ledger is not. A
public benchmark is presumed contaminated until the data card's `## Contamination
audit` argues otherwise, and the sealed comparison is a fresh block the model cannot
have seen (procedurally generated twins, a post-cutoff set, a held-back split) — the
GSM-Symbolic design (Mirzadeh et al. 2024, arXiv:2410.05229). Sampling noise
(`--recipe resample`) is `fit_noise`, never the keep bar. pass@k uses the unbiased
estimator (Chen et al. 2021, arXiv:2107.03374). An LLM judge is a verifier: declared,
hashed at the METHOD gate, outside the mutable surface, and calibrated against human
labels on a stated sample before its scores carry a claim.

## 4. Figures
Paired per-item outcome table (both right / only A / only B / both wrong) for every
headline comparison; accuracy with item-bootstrap intervals per condition and per
item block (public vs fresh); score versus tokens per item; the decision trajectory per
track. Tutorial §⑥ heading: **Prompting and evaluation-harness advice**.

## 5. Knowledge
`knowledge/domains/llm/` (created when the first LLM exhibit closes) and
`knowledge/research-discipline.md`; method card `knowledge/method_cards/llm-prompting-and-eval.md`.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` | Floor recipe |
|---|---|---|
| a few hundred items, small hosted model | 1 800 | `item-bootstrap` on the anchor; `resample` (k ≥ 3) as `fit_noise` |
| thousands of items or a large model | 3 600; set `phases[].budget_usd` | as above, on a declared subsample |
| local checkpoint, GPU | set explicitly; budget in tokens | `resample` at fixed seed list |
Every run states its token and dollar spend (the call ledger prints `tokens_in`,
`tokens_out`, `cost_usd`); a phase's `budget_usd` / `budget_tokens` is enforced.

## 7. Vocabulary
Banned: "understands", "reasoning ability", "emergent", "solved", "SOTA" — each claims a
property the measurement does not reach. Must be qualified: "improves" (on which
items, paired, with the interval), "generalizes" (to which fresh block), "robust" (to
which perturbation). Honest verbs: scored, answered correctly on k of n items, the
paired difference was, did not survive on fresh items, matched the reported value.

## 8. CONSULT hints
`test` for "does prompt/decoding A beat B on these items" (paired, registered cells);
`estimate` for "what is model M's accuracy on benchmark B" (with an interval and a
contamination statement); `replicate` for a published benchmark number; `predict` only
when something is trained. Modality is `text`. The model under test is reached through
`kleinlib.calls`; the mutable surface is the prompt/decoding file, never the scorer.
