# Model calls — studies whose entrypoint queries a model (Klein 2.3)

Klein's own verbs never call a model. A study's ENTRYPOINT may — an LLM evaluation, a
prompting comparison, an LLM proposing candidates for a verifier, a scientific model
served over HTTP (a protein-structure endpoint, a BioNeMo NIM), a slow stochastic
simulator. Such calls are expensive, nondeterministic and served by something that
changes under a fixed name, so a run log alone is not evidence. The call ledger
(`kleinlib.calls`) makes them evidence.

Role: the driving agent and the experimenter. Any agent or human can follow this
document directly.

## Declare the ledger

```yaml
calls:
  dir: calls                                    # study-relative; the notary watches it
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"   # any OpenAI-compatible endpoint
  model: "qwen-flash"                           # the exact model id, stated, dated in program.md
  price: {input_per_mtok: 0.05, output_per_mtok: 0.40}   # from the provider's page, dated
  budget_usd: 5.0                               # optional; also budget_calls / budget_tokens
  max_workers: 8                                # concurrent requests in chat_many
```

Declare `price` before the first run: the contract is hashed at CONSULT, and without
it every call records `usd: 0` — unrecorded, not free — and `budget_usd` is refused.
`klein preflight` warns when `calls:` has no `price:` (studies 20 and 24 shipped without
one).

Credentials never enter the study: the transport reads `KLEIN_LLM_API_KEY`,
`DASHSCOPE_API_KEY` or `OPENAI_API_KEY` (or a credential-injecting proxy), and no
header is ever written to a shard.

## Use it from the entrypoint

```python
from kleinlib.calls import CallLedger
with CallLedger.from_contract(".", smoke_response="Answer: 0") as ledger:
    answers = ledger.chat_many([[{"role": "user", "content": p}] for p in prompts],
                               temperature=0.0, max_tokens=512)
evaluate_items(rows, exp_id=..., metric_name="exact_match", extra=ledger.summary(), study_dir=".")
```

* Every request is keyed by the sha256 of its canonical form (endpoint, model, every
  parameter, the `sample=` index, the namespace). A repeat of an identical request is
  answered from the ledger and counted as `calls_cached` — so a second cell that
  re-asks the anchor's questions does not pay twice, and `sample=k` draws the k-th
  independent sample on purpose.
* `KLEIN_SMOKE=1` calls nothing: `smoke_response` answers, nothing is written.
* The budget guard raises `BudgetExceeded`; the run crashes honestly.

## What the notary records

* New records are written as deterministic gzip JSONL shards `calls/E####-NNN.jsonl.gz`
  (rotated below 8 MB uncompressed) and printed as `artifact:` lines; because the
  contract declares `calls.dir`, the notary also hashes and COMMITS every new shard for
  EVERY exit status — a crashed run's paid calls are evidence too.
* `runs/E####/usage.json` (calls, cached calls, tokens in/out, dollars) is folded into
  `manifest.usage` for every exit status; `phases[].budget_usd` / `budget_tokens` sum it.
* `calls_*` keys are machine keys: a replication never reports them as mismatches.

## Replay is not replication

| Verb | What runs | Network | Evidence id | Satisfies `confirmation.require: [replicate]` |
|---|---|---|---|---|
| `klein replicate E#### --replay` | the run's code, in a fresh worktree, against the run's PINNED shards (hash-checked), `KLEIN_OFFLINE=1` | none | `replay:E####@<ts>` | **no** — it re-derives parsing, scoring and aggregation from recorded answers; it says nothing about the model |
| `klein replicate E####` | the same code, every call salted (`KLEIN_CALLS_NAMESPACE=rep:E####@<ts>`) so the model is asked afresh; the new shards are kept beside the record | yes | `rep:E####@<ts>` | yes |

A stranger with no credentials re-verifies a finished LLM study with `klein verify`
(which never re-parses logs) and `klein replicate --replay` (which never touches the
network). A claim about the MODEL needs a re-query.

## Doctrine for LLM studies

* Name the model id and the date it was queried; hosted models change under a name.
* The item is the unit of uncertainty; compare prompts PAIRED on the same items
  (`metrology.paired_item_bootstrap`, `metrology.mcnemar_exact`) — `references/profiles/llm.md`.
* Sampling noise (`--recipe resample`) is `fit_noise`, never the keep bar.
* Model outputs are committed: check the provider's terms before a study ships.
