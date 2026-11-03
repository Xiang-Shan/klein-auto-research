---
title: "Prompting Strategies and Item-Level Evaluation of Language Models"
type: method-card
domain: ml
profile: [llm, ml-research]
status: seed
concepts: [chain-of-thought, self-consistency, exact-match, pass-at-k, paired-comparison, contamination, call-ledger, item-bootstrap]
related: [README.md]
triad:
  theory: true
  papers: true
  practice: false
---

# Prompting Strategies and Item-Level Evaluation of Language Models

*Seed card (Klein 2.3) for the `llm-eval` recipe. A study instantiates it at the METHOD
gate and verifies every reference there.*

## 1. Practitioner intuition

A language model answers a question by generating tokens. **Direct prompting** asks
for the answer at once; **chain-of-thought (CoT)** asks the model to write intermediate
steps first, which gives it more computation per answer and lets it condition the final
tokens on its own worked steps. **Self-consistency** samples several CoT completions at
non-zero temperature and takes the majority answer — an ensemble over reasoning paths.

Measuring any of this is harder than running it. A benchmark score is a mean over a few
hundred items, so it moves by several points under item resampling; two prompts must be
compared on the SAME items (paired); the model may have seen a public benchmark during
training, so a gain on public items can be memory rather than method; and hosted models
change under the same name. Hence: a fixed model identifier and date, a call ledger, an
item-level table, a paired test, and a fresh-item control.

## 2. Math core

| Symbol | Meaning |
|---|---|
| `s_i^A, s_i^B ∈ {0,1}` | correctness of item i under prompts A and B |
| `n, c` | samples drawn per item, samples correct |

1. Accuracy with an item-bootstrap interval: `acc = mean_i s_i`, CI from resampling items.
2. Paired difference: `Δ = mean_i (s_i^A - s_i^B)`; McNemar exact test on the discordant
   counts `n10 = #{s^A=1, s^B=0}`, `n01`: `p = min(1, 2·P(Bin(n10+n01, ½) ≤ min(n10, n01)))`.
3. Unbiased pass@k per item: `1 - C(n-c, k) / C(n, k)` (Chen et al. 2021).
4. Contamination probe: `Δ_public - Δ_fresh`, the gain on public items minus the gain on
   freshly generated twins; a large positive value is the memorization signature.

## 3. Minimal from-scratch implementation

```python
from kleinlib.calls import CallLedger, openai_chat
ledger = CallLedger.for_run(budget_usd=5.0)            # every request/response pinned
def ask(prompt, *, sample=0, temperature=0.0):
    return ledger.call(openai_chat, base_url=BASE, model=MODEL,
                       messages=[{"role": "user", "content": prompt}],
                       temperature=temperature, sample=sample)
rows = [{"item_id": q.id, "score": int(extract_number(ask(TEMPLATE.format(q=q.text))) == q.answer)}
        for q in items]
evaluate_items(pd.DataFrame(rows), exp_id=EXP, metric_name="exact_match", study_dir=".")
```

The answer extractor and the normalization are part of the scorer and live outside the
mutable surface; the prompt template is the mutable surface.

## 4. When it pays / when it doesn't

| Regime | Expectation |
|---|---|
| multi-step arithmetic word problems, small/medium model | CoT raises exact-match substantially |
| single-step lookup or classification | CoT gains are small or negative and cost tokens |
| strong recent models | the direct/CoT gap narrows; many answer with implicit reasoning |
| public, widely mirrored benchmark | gains may shrink on fresh twins (GSM-Symbolic) |

Registrable priors: CoT − direct > 0 on public items (paired, CI excludes 0); the gain on
fresh twins lies within a stated margin of the public gain; self-consistency@5 ≥ greedy
CoT; tokens per item rise by a stated factor.

## 5. References (verify at instantiation)

- Wei et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. arXiv:2201.11903
- Kojima et al. (2022). Large language models are zero-shot reasoners. arXiv:2205.11916
- Wang et al. (2023). Self-consistency improves chain of thought reasoning in language models. arXiv:2203.11171
- Cobbe et al. (2021). Training verifiers to solve math word problems (GSM8K). arXiv:2110.14168
- Chen et al. (2021). Evaluating large language models trained on code (pass@k). arXiv:2107.03374
- Mirzadeh et al. (2024). GSM-Symbolic. arXiv:2410.05229
- Brown et al. (2020). Language models are few-shot learners (13-gram contamination analysis). arXiv:2005.14165
