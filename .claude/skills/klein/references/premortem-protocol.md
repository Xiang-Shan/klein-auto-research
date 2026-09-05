# PRE-MORTEM — the slate-time red team, recorded

The driver who wrote a slate is the last reader able to see what is wrong with it.
The `premortem` capability puts a REVIEW between the draft slate and the first
run: someone other than the driver reads the scoped question, the cards, the prior
evidence and the draft slate, and writes down what will go wrong. The driver
answers every objection. A mechanical defect the reviewer called blocking must be
FIXED — and the fix must produce a new slate version — before any hypothesis of
that phase is admitted.

Opt-in, schema-3 only, inert unless `generation/manifest.yaml` declares
`premortem` (which requires `slates` — `references/generation-protocol.md`).

> **The critic is not the closing referee.** A reviewer whose name matches
> `program.md`'s `## Roster` **referee** row FAILs verification: a study that
> spends its independent reader at slate time has no independent review left for
> Gate 3 (`references/referee-protocol.md`). The pre-mortem reviewer's rung is
> recorded separately and raises nothing at REFEREE.

> **Nothing here scores, ranks or selects.** There is no quality score for an
> issue, no ranking of reviewers, no tournament between candidates. The reviewer
> supplies adversarial arguments and discriminating checks; the driver keeps every
> selection judgement, exactly as `references/phase-ritual.md` requires.

Role: the driving agent arranges the review session and records both halves.
**Klein calls no model and spawns nothing** — the fresh context is the driver's to
arrange, with a second agent, a colleague, or a person.

## Verbs

```bash
uv run --locked klein generation premortem record  --study studies/NN-slug --phase <id> \
    [--session-receipt review-session.md] [--allow-late]
uv run --locked klein generation premortem respond --study studies/NN-slug --phase <id>
```

Both take the four testimony flags `--actor --tool --model --session` (recorded,
never authenticated). Exit codes follow the layer's convention: `0` did it, `1`
the study is not in a state where the question can be asked, `2` the question was
asked and answered no.

## 1. The order, and why it is the whole mechanism

```
slate lock (v1 — the DRAFT)
  → premortem record         # the reviewer's issues, bound to that draft's hash
  → the fixes                # slate amend (v2), the corrected rows
  → premortem respond        # one disposition per issue, accepts naming v2
  → generation check --hypothesis …   # admitted, at last
```

`record` binds four things at once: the sha256 of the **draft slate lock object**
being reviewed, the reviewer's identity, the **input bundle** (every path the
reviewer was handed, each hashed), and the issues themselves. `respond` binds the
driver's answers and the sha256 of the slate version each acceptance produced.

`record` refuses once a hypothesis of the phase has been ADMITTED to run, or once
a run has gone ahead on a refused hypothesis check — a pre-mortem written after
the evidence started arriving criticised nothing. `--allow-late` records it anyway
and `generation verify` then FAILs `generation premortem` for the life of the
study. (Only the phase's FIRST review carries that weight: a later review of a
later draft follows the phase's earlier work by construction and is labelled, not
failed.)

A refused hypothesis check is *not* evidence that the phase started — while a
review is open this capability refuses every hypothesis check, and reading its own
refusals as "too late" would lock the driver out of recording the review that
clears them.

## 2. The artifact

Copy `assets/premortem-template.yaml` to the study as `premortem/<phase>.yaml`.
The reviewer writes `issues`; the driver writes `responses` afterwards.

| Key | Rule at `record` |
|---|---|
| `type`, `study`, `phase` | present and matching the study and the phase |
| `slate_object` | the sha256 of a locked slate object of this phase, and the version **in force** — a review of a superseded draft corrects nothing |
| `reviewer` | `{name, model, tool, session_receipt}`; `name` is required and is what the independence checks read |
| `inputs[]` | non-empty study-relative paths that EXIST, including `slates/<phase>.yaml`. Each is hashed; the bundle hash is recomputed at verify time from the commit that introduced the record |
| `issues[]` | non-empty. Each `{id: I1…, target, severity, kind, text}`; `target` is a live row id of the reviewed slate, or `slate`, or `design`; `severity ∈ blocking, major, minor`; `kind ∈ mechanical, scientific`. Any further key the reviewer wrote (`failure_story`, `challenged_assumption`, `source_or_counterexample`, `discriminating_check`) is copied verbatim and never interpreted |
| `responses` | **must be empty or absent** — a review is recorded before it is answered, or it is not a review |

**`mechanical` vs `scientific` is the load-bearing distinction.** A mechanical
issue is one the record can adjudicate: a denominator that omits failed batches, a
partition the metric cannot be computed on, a success rule no registered `P#`
decides. A scientific issue is a judgement about the world. Only
`blocking` + `mechanical` gates admission; everything else is answered on the
record and the driver decides.

## 3. The responses

| Key | Rule at `respond` |
|---|---|
| `issues` | byte-identical to what was recorded — a recorded review is immutable; answering it may not quietly rewrite it |
| `responses[]` | exactly one per issue: no missing, no duplicate, no unknown id |
| `disposition` | `accept` \| `reject` \| `defer`, each with a non-empty `rationale` |
| `changed_artifact_hash` | required on `accept`: the sha256 of a slate version that **descends from** `slate_object` (i.e. `slate amend` really produced a new version). Forbidden on `reject` and `defer` |
| blocking mechanical | every `blocking` + `mechanical` issue is `accept`ed, or `respond` is refused |

A qualitative disagreement is recorded as `reject` with a rationale — forced
agreement is not review. A deferral is recorded as `defer` and stays visible; it
is never a silent drop.

Between `record` and `respond` the file is uncommitted by design (the dispositions
are being written into it). Every other generation verb and `run-one` refuse a
dirty tree, so answer the review before running anything else. From the moment
`respond` files it, the file is frozen: an edit FAILs verification.

## 4. Admission

With `premortem` declared, `klein generation check --hypothesis <H>` is refused
unless, for the phase in force:

1. a review exists whose `slate_object` is the slate version in force or an
   ancestor of it,
2. that review has a recorded response set, and
3. every `blocking` + `mechanical` issue is `accept`ed with a
   `changed_artifact_hash` that is the version in force or an ancestor of it — the
   correction actually reached the slate the run would use.

The refusal names the issue ids. Like every refusal in this layer it is written,
hashed and committed first: ignoring one is a detectable, recorded fact.

## 5. Verification

`klein generation verify` runs the `premortem` family alongside the spine's eight.

| FAILs when | |
|---|---|
| order | the phase's FIRST review was recorded after a hypothesis admission of that phase, or after a run went ahead on a refused hypothesis check |
| unanswered | a review carries no response set while the phase's hypotheses already ran; a recorded response set that does not answer every issue exactly once |
| ignored blocker | a `blocking` + `mechanical` issue was never accepted and the phase's hypotheses ran anyway |
| hash | an `accept` whose `changed_artifact_hash` is not a slate object of the phase, or does not descend from the reviewed draft |
| identity | the reviewer's name matches the roster's `referee` cell (or one of its `model · tool · session` components) |
| bundle | the input bundle recomputed from the record's introducing commit differs from the hash recorded — including an input that was never committed |
| document | `premortem/<phase>.yaml` at the commit that FILED the record is not the file the record hashed, or names a different `reviewer` or `inputs` than the record copied — the record and its document are one artifact |
| immutability | `premortem/<phase>.yaml` is not the bytes the recorded response hashed |

WARNs, which fail nothing: no session receipt (independence is `self-attested`);
the reviewer matches the roster `experimenter`; **`program.md`'s roster names no
`referee`, so reviewer independence cannot be established** (once per phase — the
"reviewer ≠ referee" FAIL is a string comparison, and an absent row makes it
vacuous rather than satisfied); a review recorded and not yet answered on a phase
that has not run; a later review recorded after the phase was under way.

The capability entry in `generation/verify_receipt.json` is
`{"integrity": PASS|FAIL, "outcome": receipted|self-attested|incomplete, "phases": {…}}`
— a DECLARED capability with no review yet is `incomplete`, never `n/a`: `n/a` is
the label's word for "this study did not declare it", and it comes only from the
label's own defaults. `generation/label.json` copies the **outcome**. Integrity is
not outcome: a
study whose every review is self-attested can still be `generation-verified`.

## What this establishes, and what it does not

- **Establishes:** that a named reviewer, given a named and hashed set of inputs,
  raised these issues against THIS draft of the slate before its hypotheses ran;
  that every issue got exactly one recorded disposition; and that each accepted
  correction produced a slate version the executed runs actually used.
- **Does not establish:** that the review was independent (a session receipt is a
  hash of a file the driver points at — testimony, not authentication), that the
  reviewer was competent, that the issues were the right issues, or that a
  specific-but-useless critique is worth anything. A generic "consider bias"
  paragraph fails the schema; a specific and useless one passes it. **Whether the
  checks were meaningful, and whether accepted corrections reached the executed
  artifacts in substance, is a referee obligation**
  (`references/referee-protocol.md`, "Generation addenda").
