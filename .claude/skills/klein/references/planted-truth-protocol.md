# PLANTED TRUTH — a benchmark whose answer nobody could read

"The system discovered the interaction" is worth exactly as much as the answer
was hard to obtain. A public generator whose interaction an arm restates is not a
discovery; a hidden one whose structure an arm recovers is. The `benchmark`
capability makes that difference machine-readable: a salted commitment recorded
before any participant sees the data, submissions frozen before the truth is
disclosed, a matching rule fixed at METHOD, one sealed scoring cell, and a
verification that recomputes every match from the same bytes.

Opt-in, schema-3 only, inert unless `generation/manifest.yaml` declares
`benchmark` (`references/generation-protocol.md`). `benchmark` requires `parity`,
which requires `expertise`: the arms are compared on matched budgets against a
reproduced expert control, so the custodian study is already a parity study
(`references/expert-parity-protocol.md`).

> **Recovering a planted structure establishes in-silico performance on this
> generator, at this sample size, under this matching rule.** It does not
> establish real-world discovery, and it does not generalize across scientific
> fields. Claims about it are `known-dgp-teaching` with `scope: in-silico`; a
> `confirmed` claim resting on the scoring table is refused outright, because
> confirmation needs evidence independent of the selection in a separately
> registered `test` study (`references/inquiry-model.md`).

> **A hash is not secrecy.** Hashing the private bundle proves it was not altered
> afterwards. It proves nothing about who read it in the meantime. Isolation is
> accounts, containers or machines with denied access — **never another directory
> of the same readable worktree** — and the only record of it is a custody
> attestation. Without one the outcome reads `unverified`, which is the honest
> word for "nobody said".

Role: the CUSTODIAN, at METHOD (commit), as each arm finishes (submit), once
every arm is in (reveal), and at the single sealed scoring cell. Any agent or
human can follow this document directly.

## Two studies, two roles

| | CUSTODIAN | PARTICIPANT (one per arm) |
|---|---|---|
| `kind` | `simulate` | `discover` |
| Holds | the full DGP card, the generator, the seed blocks, the structural truth, the scorer | the public bundle and a task card, and nothing else |
| Declares | `--capability benchmark` (and so `parity`, `expertise`) | no `benchmark` capability at all; any others it likes |
| Runs | every `benchmark` verb; the sealed scoring cell | its own ordinary Klein study, unaware of this protocol |
| Lives | on the custodian's own account or machine | on a separate account or machine, with no shared checkout |

The participant's `data_card.md` says **"observations only; truth custodied by
`<holder>`"** and carries no DGP card; the full DGP card lives in the custodian's
`simulate` study, where the simulation disclosure requirement is satisfied
without exposing the answer (`references/data-gate-protocol.md`, "simulation").

## Verbs

```bash
uv run --locked klein generation benchmark commit --study studies/NN-slug \
    --private <path to the private bundle> --salt-file <path to the salt>
uv run --locked klein generation benchmark submit --study studies/NN-slug \
    --arm <id> --file <the participant's frozen submission>
uv run --locked klein generation benchmark reveal --study studies/NN-slug \
    --private <the bundle, now inside the study> --salt-file <the same salt> \
    [--missing-arm <id> <reason>]…
uv run --locked klein generation benchmark retire --study studies/NN-slug --reason <text>
uv run --locked klein generation benchmark show   --study studies/NN-slug
uv run --locked klein generation custody attest   --study studies/NN-slug \
    --holder <name> --mechanism <text> --statement <text> [--subject <text>] [--receipt <path>]
```

`commit`, `submit`, `reveal`, `retire` and `custody attest` take the four
testimony flags `--actor --tool --model --session`; `show` writes nothing and
takes none. Exit codes are the layer's three: `0` did it, `1` the question could
not be asked, `2` refused — and a refusal is on the record first.

## 1. `benchmark.yaml`, committed at METHOD

Authored from `assets/benchmark-template.yaml` into the custodian study root,
then frozen by `benchmark commit`. The commitment happens **after the custodian's
METHOD gate** — the matching rule and the scorer are frozen there, before any arm
sees the data — and **before any participant access**. `commit` refuses if a
submission file already exists, if the METHOD gate is not recorded, if the file
does not validate, or if a second commitment is attempted: a benchmark commits
once and the terms are frozen from that moment.

| Field | What it fixes |
|---|---|
| `scoring_track` | the registered track whose ONE sealed cell scores every arm |
| `public_bundle` | what participants receive; `commit` computes its digest and refuses a declared one that disagrees |
| `truth_file` | the structural truth, INSIDE the private bundle, as a study-relative path — it does not exist until `reveal` |
| `private_commitment` | computed by `commit` as `sha256(salt ‖ canonical bundle bytes)`, beside `sha256(salt)` |
| `custody` | the declared holder and mechanism, and the attestation document if there is one |
| `arms[]` | `id`, `description`, `model`, `framework` (`klein-2.1` / `klein-2.0` / `none`), `budget` — arms without matched resources were not compared |
| `submission_schema` | the participant-facing contract — `assets/benchmark-submission.schema.json`, copied into the study by `commit` and hashed there |
| `hypothesis_cap` | at most this many structures per arm (A5 suggests six) — the cap is what makes precision mean something |
| `matching_rule` | `variables: exact`, `relationship: exact`, `direction: sign`, and `context:` as a preregistered SENTENCE |
| `false_positive_penalty` | charged per submitted structure that matches no planted truth |
| `recovery_predictions` | each arm's registered `P#`s on the scoring track |
| `seed_blocks` | `development` and `sealed`, **disjoint** |
| `reveal_policy` | `after-all-arms` |
| `scorer.path` | the study-local scorer, hashed here and re-read at the scoring cell's candidate commit |

**A directory hashes as its own path manifest** — `canonical_json([[relative
path, sha256], …])` over every file inside it, sorted — so a bundle can be a tree
and its digest is still one number. **The salt never enters the repository.** It
stays with the custodian and is supplied again at `reveal`; a stored salt is a
commitment anybody can open.

## 2. Submissions are frozen before the answer exists

Each arm produces a ranked, machine-readable answer in its own workspace and
freezes it. The custodian imports it:

```json
{"study": "11-participant", "arm": "alpha",
 "structures": [{"rank": 1, "variables": ["shade", "moisture"],
                 "relationship": "interaction", "direction": "positive",
                 "context": "understorey", "h_ids": ["11-participant#H2"]}]}
```

`submit` validates the file against the committed schema and the cap, copies **the
participant's own bytes** to `submissions/<arm>.json` — so the hash the custodian
records is the hash the participant can compute — and refuses a duplicate arm, an
undeclared arm, or any submission after the reveal. Prose interpretations receive
no unregistered judging credit: what is not in `structures` was not submitted.

## 3. Reveal, and what a mismatch means

`reveal` recomputes `sha256(salt ‖ bundle bytes)` from the same salt and the
disclosed bundle. Three things have to hold:

- every arm has submitted, **or** carries a `--missing-arm <id> <reason>` — a
  missing trial is a recorded trial that stays in the denominator, never an
  absence;
- the bundle is disclosed INTO the study (committed to git first), so the bytes
  the scoring cell reads are bytes any reader can hash;
- `truth_file` lies inside that bundle, so the truth is covered by the
  commitment.

**A mismatch is refused AND recorded.** `benchmark_reveal_failed` is written,
hashed and committed exactly like a successful reveal, the verb exits 2, and
`generation verify` FAILs `benchmark commitment` from then on. That is the point:
"the bundle disclosed is not the bundle committed to" becomes a detectable,
permanent fact instead of a deleted file.

A sealed admission on the scoring track is refused until a reveal exists — a cell
that scored before the disclosure either scored against nothing or scored against
a truth the custodian had not yet committed to disclosing.

## 4. The matching rule, and where judgement enters

Three conditions are decided mechanically and one is not:

| Dimension | Decided by |
|---|---|
| `variables` | the machine: the submitted variable SET equals the planted one (order and case are irrelevant, membership is not) |
| `relationship` | the machine: string equality |
| `direction` | the machine: sign equality (`positive` / `negative` / `none`) |
| `context` | the CUSTODIAN, against the preregistered `matching_rule.context` sentence, recorded per row as `context_ok` |

A row whose `context_ok` is 0 is not a match however well its variables line up.
Verification re-applies the three mechanical conditions and **takes `context_ok`
from the pinned table**: the oracle's judgement is labelled as judgement rather
than laundered into arithmetic. Decide the ambiguous cases once, before the
reveal, and encode the decision in the scorer — never widen it after seeing which
arm it would have failed.

**Each planted truth is recovered ONCE.** Walking an arm's structures in rank
order, the best-ranked structure that matches a truth claims it; a later
structure matching the same truth is a **duplicate** (`matched: 0` with a
`truth_id`), and one matching nothing is a **false positive** (`matched: 0`,
`truth_id: NA`) the penalty is charged against.

- `recall_<arm>` = unique planted truths recovered ÷ all planted truths —
  **undefined** on a null-only benchmark, where the false-positive rate is the
  whole result.
- `precision_<arm>` = matched structures ÷ submitted structures.
- `null_fp_<arm>` = structures matching nothing.

## 5. The sealed scoring cell

ONE sealed registered cell covers **all** arms. It is an ordinary transaction —
there is no benchmark-specific execution path:

```bash
uv run --locked klein run-one --study studies/NN-slug --track scoring \
    --final-test --dry-run                        # mandatory rehearsal
uv run --locked klein generation check --study studies/NN-slug \
    --action sealed --track scoring --tests P_recall_alpha P_recall_beta
uv run --locked klein run-one --study studies/NN-slug --track scoring \
    --final-test --tests P_recall_alpha,P_recall_beta
```

Its entrypoint calls `lib/score_submissions.py`
(`assets/score_submissions_template.py`), which prints `recall_<arm>`,
`precision_<arm>`, `null_fp_<arm>` and `cost_<arm>` per arm — `predictive_<arm>`
too where the arm produced a model, `NA` allowed — and pins
`tables/benchmark_scores.tsv` with one row per arm × submitted structure:

```
arm  rank  variables  relationship  direction  context_ok  matched  truth_id
```

Structural recovery, false discoveries, cost and predictive performance are
printed **separately**. An arm that recovered the structure expensively and an
arm that recovered it cheaply are different results, and one number would hide
which is which.

## 6. Verification

`klein generation verify` runs six families and FAILs on:

- **`benchmark commitment`** — no commitment on a study that declared the
  capability; a second one; `benchmark.yaml` altered since; overlapping
  development and sealed seed blocks; a recorded reveal failure; a reveal naming
  a different commitment, a different salt, or a truth file whose bytes changed.
- **`benchmark submissions`** — a submission before the commitment or after the
  reveal; a duplicate or undeclared arm; a submission file that is not the one
  imported; more structures than the cap; an arm that neither submitted nor has a
  recorded missing trial. Recorded missing trials are a WARN naming them.
- **`benchmark scorer`** — the scorer at the scoring cell's candidate commit is
  not the file the commitment pinned — the checker is never the searcher.
- **`benchmark scoring`** — more than one sealed cell on the scoring track; a
  cell that consumed no `sealed` admission; a cell that ran before the reveal; no
  `artifact: tables/benchmark_scores.tsv` pin; a table whose bytes are not the
  pinned ones; **a table that disagrees with the matching rule re-applied to the
  same submissions and the same revealed truth**; a printed `recall_/precision_/
  null_fp_/cost_` key that is missing or that differs from the table's own number.
- **`benchmark ceiling`** — a `confirmed` claim in `claims.lock` citing the
  scoring table: in-silico recovery is never confirmation.
- **`benchmark custody`** — never a FAIL. An attestation ABOUT THIS BENCHMARK is
  a PASS that says `TESTIMONY`; its absence is a WARN and the outcome
  `unverified`. An attestation counts only when its `subject` is null (the
  default: this study's own hidden evidence) or names `benchmark.yaml`'s
  `public_bundle`, `truth_file` or `custody.holder`. Because `custody attest` is
  capability-agnostic, counting any attestation would let a statement about a
  sample chain or a later time block turn this benchmark `custodied`; the others
  stay on the record and are listed by subject in the check's detail.

The capability outcome is decided in one fixed precedence — `retired`, then
`unverified` (nobody attested custody), then `scored`, then `unscored` — and is
reported beside `custody` (`custodied` or `unverified`) and the per-arm numbers.
The label copies the outcome; integrity is reported separately, as everywhere in
this layer.

## 7. Custody, retirement, and the failures neither closes

`custody attest` is **capability-agnostic**: it needs the generation opt-in and
nothing else, so a study custodying a later time block or a wet-lab sample chain
uses the same receipt. It records a NAMED holder, the mechanism in their own
words, a statement of what was denied to whom, the SUBJECT it is about, and
optionally a receipt document inside the study whose bytes are hashed. The
object carries `testimony: true`. Nothing here verifies any of it.

Name the subject deliberately: omit `--subject` (or name the benchmark's
`public_bundle`, `truth_file` or `custody.holder`) when the statement is about
this benchmark's hidden evidence, and give it a subject of its own when it is
not. A benchmark counts only the attestations that are about it.

A participant who reads a public generator and restates its interaction earns
"discovery" for free. Private custody closes that channel; randomized variable
names and parameters and fresh instances reduce memorization; the cap and the
false-positive penalty deter listing every possible interaction. **Audit copied
data, logs, replication bundles and tool access** — a benchmark leaks through all
four, and none of them is hashed here.

**A benchmark known to have leaked is retired** (`benchmark retire --reason`) and
its **results are RETAINED**. The exercise happened; deleting it would be a second
dishonesty on top of the first. A retired benchmark is simply never used as a
hidden benchmark again.

## Reporting it

`findings.md` §① states recovery with its scope — the generator, the sample size,
the matching rule, and the words *in silico* — and never as "the system
discovered X". §② copies the per-arm recovery predictions from the ledger. Every
number is pinned through `art:benchmark_scores` in `claims.lock`, and the claim
class is `known-dgp-teaching` with `scope: in-silico`. Where custody was not
attested, say so: `benchmark: unverified` is a sentence in the report, not a
footnote in a JSON file.

The referee reads `benchmark.yaml`, the pinned table and the decision, and checks
the one thing the mechanism cannot: whether the planted families resemble a
scientific task at all (`references/referee-protocol.md`).

## What this establishes, and what it does not

**Establishes.** That the terms were fixed before any arm saw the data; that each
arm's answer was frozen before the truth was disclosed; that the disclosed bundle
is the one committed to; that the scorer did not change; that development and
sealed seed blocks are disjoint; that the recorded matches are the ones the
locked rule produces on the same bytes; and that recovery, precision and false
discoveries were scored in one sealed registered cell.

**Does not establish.** Secrecy — a hash proves non-alteration, custody is
testimony, and nothing here observes who read what. Real-world discovery —
recovery is in-silico performance on one generator. Cross-field generality — one
packet of planted structures is one packet. That the planted families are
scientifically meaningful — that is the custodian's judgement, and the referee's
to question. And that the arms were equally resourced beyond what `budget`
records: matched budgets are declared, not measured.
