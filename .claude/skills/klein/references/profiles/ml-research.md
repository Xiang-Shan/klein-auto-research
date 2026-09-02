# Profile: ml-research

For studies whose question is about a learning method itself — an architecture, an
optimizer, a training recipe, a scaling behaviour — rather than about a dataset's domain.

## 1. Audience
An ML researcher who knows the method family, expects seed variance to be reported, and
will ask "at what compute?" before "by how much?".

## 2. §⑤ heading
**⑤ Practitioner impact — what to change in a training recipe, and at what cost.**
Prompt: state the change, the matched-compute condition under which it held, the seed
spread it was measured against, and the hardware it was measured on.

## 3. Doctrine
Compare at matched compute (steps or tokens, never wall-clock as the budget); report
seed variance as `fit_noise` and never paste a k-seed spread as the keep bar; never
compare a tuned candidate against an untuned baseline; checkpoints are `artifact:`
lines scored by a declared verifier script (`tracks.<id>.verifier`), so the training
script never grades itself. A single seed is an anecdote.

## 4. Figures
Training and validation curves per candidate; seed-variance bars at the anchor; metric
versus compute (steps or tokens) on a log axis; the decision trajectory per track.
Tutorial §⑥ heading: **Training-recipe advice**.

## 5. Knowledge
`knowledge/domains/ml-research/` (seeded by study 13) and
`knowledge/research-discipline.md`.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` | Floor recipe |
|---|---|---|
| seconds (tiny nets, CPU) | 300 | 5-seed `fit_noise` |
| minutes (small nets, one GPU or MPS) | 1 800 | 3–5-seed `fit_noise` |
| hours (real training runs) | set explicitly; budget in steps | 3-seed `fit_noise` at a reduced budget, disclosed as such |
Long runs use `max_steps` or `max_tokens` as a printed guardrail; `wall_seconds` is
informational so CPU and accelerator runs agree within the floor.

## 7. Vocabulary
Banned: "SOTA" / "state of the art" without the benchmark, budget and date; "beats"
without the floor and the matched budget; "converged" without the criterion. Must be
qualified: "faster" (by what clock, on what device), "generalizes" (to what held-out
partition). Honest verbs: at matched steps, within fit noise, cleared the bar by k×
the floor.

## 8. CONSULT hints
Almost always `predict` on a held-out partition, occasionally `estimate` (a scaling
exponent with its interval) or `test` (does recipe A differ from B at fixed budget).
Modality from the data (`text`, `image`, `sequence`, `tabular`). The mutable surface is
usually more than one file (`entrypoint.mutable: [model.py, train.py]`); a candidate
is one idea, whatever its diff size.
