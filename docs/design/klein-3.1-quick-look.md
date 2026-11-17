# Klein 3.1 — proportional rigor: the quick look

The design for Klein 3.1's one new judging rule. Earlier rationale:
[`klein-3-design.md`](klein-3-design.md) (§7 named this as the next release's main item).

## 1. The problem

Every Klein study runs the whole lifecycle: four gates, a sealed look, a referee, a
teaching report. That is right for a result someone will build on. It is wrong for most
questions a person actually asks — "did conversion drop after the price change?", "is
this column skewed enough to matter?" — and it is wrong for a product, such as an
agentic BI tool, where a question should cost minutes.

Today the only alternatives are off the record: an ad-hoc script, or `klein probe`, which
is deliberately not evidence. So a quick answer is either unrecorded or unusable.

## 2. The idea

A study declares how much rigor it is asking for, and **the declaration caps what it can
claim**.

```yaml
policy:
  rigor: quick        # default: full
```

A quick look is a real study — a typed question, a data check, a registered prediction
decided by the notary, a claim with a pinned number — that skips what it does not need
and can never be quoted as more than it is.

| | `full` (today) | `quick` |
|---|---|---|
| Gates before a run | CONSULT, DATA, METHOD | CONSULT, DATA |
| Predictions registered with a rule | yes | yes |
| Runs notarized | yes | yes |
| Sealed look | once per track | **none** — refused |
| Strongest claim | `confirmed` | **`exploratory`** |
| Referee before closing | required (or recorded waiver) | not required |
| Closing label | `confirmed` / `exploratory` | `exploratory`, marked `quick look` |
| Teaching report | expected | optional |

What does not change: predictions before evidence, the notary's transaction, the event
chain, the claims law, the numbers law, `klein verify`. A quick look is weaker in what it
may conclude, not in how honestly it is recorded.

## 3. Why a cap, not a lighter verdict

The tempting design is a "light confirmation". That creates a second, weaker meaning of
`confirmed`, and every reader must then ask which one they are looking at. Klein has one
meaning for `confirmed` — the evidence a track's contract required was collected — and a
quick look does not collect it. So it says `exploratory`, which is already the honest
word in the vocabulary (`claims.py`: `exploratory | confirmed | refuted`).

The same reasoning as for a probe in 3.0: the weaker thing is kept separate by
construction, not by convention.

## 4. Rules, exactly

1. **Key.** `policy.rigor ∈ {full, quick}`; default `full`. `policy` is the contract block
   that refuses unknown keys and values, so a 3.0.0 engine *refuses* a quick study instead
   of judging it by full rules it does not meet.
2. **Gates.** Required modeling gates become a function of the contract:
   `required_gates(contract)` returns `(consult, data)` for quick and
   `(consult, data, method)` for full. Every reader of `MODELING_GATES` calls it
   (`workflow.run_one`, `checks`, `state`, `next_step`). A method card may still be
   written and its gate recorded; it is not required.
3. **No sealed access.** `run-one --final-test` (and its rehearsal) is refused:
   "a quick look does not spend sealed evidence — promote the study first". The sealed
   partition stays untouched, so promotion loses nothing.
4. **Claim cap.** `klein claims add` refuses strength `confirmed`, and the claims law
   fails a lock that carries one, when the study's rigor is quick. `refuted` is allowed:
   a quick look may kill an idea.
5. **Closing.** `klein finalize` needs no `--allow-exploratory` and no referee; it records
   `closure.rigor: quick` and `closure.referee: {status: "not-required"}`. Open
   predictions are still refused, findings are still required, the label is
   `exploratory`.
6. **Visible everywhere.** `klein status`, `klein map`, the verify receipt and the report
   builder carry `quick look` beside the label. A quick look that is quoted is quoted
   with its tier.
7. **Verify.** No check is skipped silently: the gate check reports
   `method: not required (quick look)`; the referee check reports the same.

## 5. Promotion

`klein promote --study S --reason "…"`:

- rewrites `policy.rigor` to `full` in `study.yaml` and appends a `rigor_promoted` event
  with the reason and the contract hash before and after;
- the CONSULT gate is then stale (its artifact changed) and is re-acknowledged — the
  existing amendment path; its first-probe anchor is kept;
- from then on the full rules apply to the whole study: METHOD is required before the
  next run, the sealed look becomes available (and rehearsed), the referee is required.

Nothing is re-run and nothing is rewritten. Runs made under `quick` stay development
evidence, which is all they ever were. A claim made under `quick` stays `exploratory`
until evidence earned under `full` supports a new, stronger claim; the claims law's
append-only history shows both.

Demotion (`full → quick`) is refused once any sealed access has been spent, and
otherwise is an ordinary recorded amendment.

## 6. Entry points

- `klein new --rigor quick` (and `--recipe quick-look`): a scaffold with the two cards a
  quick look needs and no method-card template.
- `klein next` drives it: consult → data → run(s) → findings → claims → finalize.
- `kleinlib.api`: the same functions; `status` and `next` carry `rigor`.
- `docs/embedding.md`: "a BI question, end to end" — the host types the question, the
  agent runs a quick look, the host shows the claim with its tier and offers "promote".

## 7. What a quick look is not

- Not a probe. A probe is a look with no prediction and no claim. A quick look has both.
- Not a way round the data gate. GIGO applies to a fast answer more than a slow one.
- Not publishable as confirmed, by any flag.

## 8. Risks

- **Tier creep** — people stop at quick. The cap is the answer: nothing `confirmed`
  exists without the full path, and the tier is on every surface.
- **A third tier** — not planned. Two is the smallest number that solves the problem.

## 9. Also in 3.1 (small, found while closing 3.0)

- A replication tolerance for seed-array runs in the engine: the run's own seed-to-seed
  spread, which the weekly job states by hand for study 22 today.
- CPU, BLAS and thread detail recorded beside the environment fingerprint, so a failed
  cross-machine replication can be explained from the record.
- An anchor for the event chain's head, so a chain truncated at its tail is detected
  (the 3.0 review's finding).
- The rehearsal also runs a declared verifier.
- A warning for an unknown top-level contract key (today a typo is silently ignored).
