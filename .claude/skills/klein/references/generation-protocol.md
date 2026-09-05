# The generation layer — recording what was committed to, before the evidence

Klein's core makes the *verification* half of research auditable: a typed question, a
registered prediction, notarized evidence, a locked claim, an independent referee. The
generation layer records the other half — what the driver committed to BEFORE the
evidence existed — so a stranger can check the ORDER of the work, not only its result.

It is **opt-in and schema-3 only**. A study without `generation/manifest.yaml` is
untouched by every rule here, `klein verify` never prints the word "generation", and
no core verb, receipt or disposition changes. Schema-2 studies are refused outright.

> **The layer records, hashes, and computes arithmetic on rows the driver wrote; it
> never proposes, ranks, selects, schedules, or retries.** No generation verb calls
> `run-one`. No module under `kleinlib/generation/` calls a model API or the network.
> The phase ritual is still not automated: nothing here writes a candidate.

Role: the driving agent, before each action; the referee reads the receipts afterwards.
Any agent or human can follow this document directly.

## Verbs

```bash
uv run --locked klein generation init    --study studies/NN-slug [--capability NAME]… [--allow-late]
uv run --locked klein generation check   --study studies/NN-slug --action run --track primary [--tests P1]
uv run --locked klein generation verify  --study studies/NN-slug
uv run --locked klein generation label   --study studies/NN-slug
uv run --locked klein generation status  --study studies/NN-slug
uv run --locked klein generation recover --study studies/NN-slug
```

Every WRITING verb (`init`, `check`, `label`, `recover`) takes the four **testimony**
flags `--actor --tool --model --session`; `verify` and `status` write no event and take
none.

Exit codes are three-valued: `0` did it, `1` an ERROR (the study is not in a state
where the question can be asked — wrong schema, no manifest, broken chain, orphan
objects, dirty tree; nothing is recorded), `2` a REFUSAL or a failing audit (the
question was asked and answered no — and the refusal is on the record first).

## Opt in before CONSULT

`klein generation init` writes `generation/manifest.yaml` and anchors it in the core
chain. **It must run before the CONSULT gate is recorded**: the manifest freezes the
scope, and a commitment registered after seeing what it was supposed to constrain
constrains nothing. `init` refuses once a `gate_recorded consult` event exists;
`--allow-late` records the opt-in anyway, marks it `late_opt_in`, and `generation
verify` then FAILs `generation manifest` for the life of the study. That is the
honest outcome, not a workaround.

The manifest is immutable. Its sha256 is carried in the `generation_opted_in` event
and re-hashed at every verify.

```yaml
generation_schema: 1
study_id: NN-slug
capabilities: []            # subset of the ten-name vocabulary; [] = admission discipline only
protocol_hashes:
  references/generation-protocol.md: <sha256 at init>
predecessor: null           # or {study_id, successor_receipt, inherited_exposure: []}
custody: null               # or {holder, mechanism}
```

`assets/generation-manifest-template.yaml` carries the same shape with comments.

**Capabilities** are a fixed vocabulary — `expertise, slates, premortem, parity,
contribution, surprise, escalation, knowledge, benchmark, design` — and a versioned
availability. A name outside the vocabulary is refused as *unknown*; a known name this
version cannot check is refused as *not available*. The dependency table is fixed:
`premortem ⇒ slates`, `parity ⇒ expertise`, `contribution ⇒ slates`,
`benchmark ⇒ parity`, `surprise ⇒ design`. **This release supports none of them**:
opting in buys the admission discipline and the chronology witnesses, and nothing
that scores research. Later additions are `generation_amended` events which may only
ADD capabilities; each addition is reported `late_added`.

## The envelope

Every generation event is one line of `generation/events.jsonl`:

```
{"schema": "klein-generation/1", "id": "G0001", "sequence": 1, "type": "…",
 "study": "…", "actor": null, "tool": null, "model": null, "session": null,
 "created_at": "…", "parent_ids": [], "payload_sha256": "…",
 "core_anchor": {"sequence": 7, "event_hash": "…"}, "git_head": "…",
 "previous_event_hash": "…", …type-specific summary keys…, "event_hash": "…"}
```

`event_hash = sha256(canonical_json(body without event_hash))`, the core's own rule.
`created_at` is informational: **nothing in this layer decides anything from a clock.**
`actor` / `tool` / `model` / `session` are **testimony** — self-reported strings,
never authenticated. "This model wrote this receipt" is a claim the record carries,
not a fact the record establishes.

## Objects

`generation/objects/<sha256>.json` is a write-once store: the file name IS the sha256
of the object's canonical JSON bytes, so re-writing an identical object is a no-op and
two different objects can never collide on one name. An object no event references is
an **orphan** — see Recovery.

## Admission: a receipt before every action

```bash
uv run --locked klein generation check --study studies/NN-slug --action run --track primary --tests P1
```

`--action` names the checkpoint: `run` (an ordinary development transaction), `sealed`
(the track's one look at its confirmation evidence), `baseline`, `repair`,
`calibration`, `cell`. Every one of them passes through ordinary `run-one`; there is
no off-notary path. The receipt object records:

| Field | What it binds |
|---|---|
| `checkpoint`, `track`, `intended_action` | what is about to be run, and which predictions it adjudicates |
| `surface_digest`, `surface_files` | the exact bytes of `entrypoint.mutable`, AS ON DISK |
| `inputs` | the manifest hash (and, later, the slate / pre-mortem / parity / cells / design hashes) |
| `protocol_hashes` | which rules the receipt was taken under |
| `core_anchor` | the core chain tip at write time |
| `verdict`, `reasons` | `admitted` or `refused`, and why |

**Edit the surface first, then check, then run.** The digest is taken from the working
tree; `run-one` commits that same surface as the candidate, so the digest resolves.
Editing after the check and running anyway is `mismatched`.

**A refusal is evidence.** A refused check is written, hashed and committed exactly
like an admitted one, and the verb exits 2. That is how "the driver was told no and
ran anyway" becomes a recorded fact instead of an absence.

**Supersession, not refusal.** Asking for a second admission on a track whose previous
admission was never consumed is lawful: the new receipt names the old one in
`parent_ids` and `supersedes`, and the old one is never matched to a run again.
(Refusing would strand a track whose `run-one` aborted before writing a manifest.)
Only an ADMITTED receipt supersedes: a refusal neither grants nor revokes.

Every run in scope is classified afterwards:

| Classification | What happened |
|---|---|
| `admitted` | an eligible receipt precedes the run and its digest is the surface that ran |
| `unadmitted` | no receipt at all, or none that precedes the run |
| `refused-but-run` | the newest receipt before the run said no |
| `mismatched` | the receipt bound a different surface than the candidate commit carries |
| `replayed` | a receipt already consumed by an earlier run |

Anything but `admitted` FAILs `generation admission`. The core run stays lawful, its
disposition unchanged, and `finalize` is unaffected — the study simply cannot earn the
label.

## Chronology: three local witnesses

"Receipt R precedes action X" is established when **all three** hold:

1. **The extension chain.** R's own `previous_event_hash` links are intact, so it
   cannot be inserted into the middle of the ledger without rewriting everything after.
2. **The core anchor.** `R.core_anchor` resolves to a real core event with that hash,
   and `R.core_anchor.sequence < X.sequence`.
3. **Git ancestry.** The commit that INTRODUCED R's object is an ancestor of the
   commit X refers to (a gate record's commit, or a run's `candidate_commit`).
   `run-one` refuses a dirty tree, so a receipt committed before a run is an ancestor
   by construction.

### What this does NOT establish

- **Byte integrity is not secrecy.** A hash of a private bundle proves later
  non-alteration, not that nobody read it. "Hidden" is a custody attestation, labelled
  `custodied` only when a named custodian attests denied-access accounts, containers or
  machines; otherwise `unverified`. The mechanism cannot verify custody.
- **Roster testimony is not authenticated identity.** `actor` / `tool` / `model` /
  `session` and the reviewer roster are self-reported strings; "reviewer ≠ referee" is
  checked as string inequality, never as an authenticated fact.
- **Local ordering is not independently established chronology.** The three witnesses
  prove order relative to this study's own chains and this repository's git history. A
  party who rewrites both the core chain and git history wholesale is not detected; no
  trusted timestamp exists. A custody receipt for a pushed, protected remote ref would
  raise the rung to `custodied`; this layer records such a receipt and does not verify
  it over the network.
- **Import is not acquisition.** A measured cell pins bytes at import time; the
  physical or external acquisition time is attested, not observed.
- **Recorded activity is not all activity.** Work in scratch copies, other checkouts
  or chats is invisible. A contribution ledger records what was recorded.

## Verification

```bash
uv run --locked klein generation verify --study studies/NN-slug
```

A **separate verb writing a separate receipt** (`generation/verify_receipt.json`), by
design: appending these checks to `klein verify` would change `summary.checks` for
every opted-in study and put the core receipt's byte-reproducibility at the mercy of
this layer. Eight families:

| Family | FAILs when |
|---|---|
| `generation manifest` | absent, altered, wrong schema/study id, a late opt-in, or the opt-in anchor does not precede the first consult gate record by BOTH sequence and ancestry. Protocol-hash drift is a WARN |
| `generation chain` | a hash, link, id or sequence in `generation/events.jsonl` is broken |
| `generation anchors` | an anchor does not resolve against the core chain, or anchors go backwards |
| `generation orphans` | an object has no event, or an event's object is missing. A voided object is a WARN naming the `recovered` event |
| `generation admission` | any in-scope run is not `admitted` |
| `generation replay` | a receipt was matched by more than one run |
| `generation findings label` | a label exists and `findings.md` does not quote its line |
| `generation commits` | a `generation/**` path is uncommitted or modified |

The receipt carries no timestamp: at one HEAD it is a pure function of the study, and a
second `verify` that finds nothing new neither rewrites it nor files a commit.

**Capability families and outcomes.** Beyond those eight, each capability the manifest
DECLARED contributes its own family — registered, not hard-coded: a capability is a
name, some admission rules, and one verify family, and adding one edits no spine rule.
A declared capability this version cannot run FAILs `generation manifest`
("declared but not supported by this version"), because an unrunnable commitment is not
a passed one; a study that declares nothing runs no family at all and its receipt is
byte-for-byte the one it got before capabilities existed. Every family reports two
things separately under `capabilities[<name>]`: **`integrity`** (`PASS` / `FAIL`) — is
the RECORD intact — and **`outcome`** (a string such as `incomplete`) — what the
research got. The spine reads only `integrity`; it never treats an outcome as a
judgement. The label copies each declared capability's `outcome` into its
`capabilities` column and leaves every other name `n/a`, and `klein generation status`
prints `<name>: <integrity> / <outcome>` once a receipt exists.

## The label

```bash
uv run --locked klein generation label --study studies/NN-slug
```

Issued only when the core `verify_receipt.json` has `summary.failed == 0`, the
extension receipt has `summary.failed == 0`, **both are still current** (their
`git_head` is HEAD, or every commit since touched only the two receipt files), and the
tree is clean except the mutable surface. Then `generation/label.json` is written and
`findings.md` must carry:

```
Generation label: generation-verified @ <git_head[:12]>
```

`generation verify` checks that quotation from then on — the same discipline
`finalize` applies to its own label.

**Integrity is not outcome.** `generation-verified` says the record is intact and every
action was admitted before it ran. It says nothing about whether the research
succeeded: an honestly stopped study with every capability outcome `incomplete` can
carry it, and a spectacular result with one unadmitted run cannot. The label is
capability-scoped — every capability this version cannot score is listed `n/a` — and
its `rung` is `local-order`.

## Recovery

A verb writes an object, appends an event, and commits. Dying between those steps
leaves exactly two states, and both are detected:

- **An orphan object** (written, never referenced). Every writing verb refuses until
  `klein generation recover` appends ONE `recovered` event listing the orphan shas in
  `voided_objects`. **Nothing is deleted** — the bytes stay on disk and verify reports
  them as a WARN naming the event that voided them. Deleting is the one operation an
  append-only ledger cannot audit.
- **An uncommitted ledger** (event appended, never committed). The next verb refuses a
  dirty tree; `recover` files the `generation/**` paths, because until they are
  committed the receipt has no introducing commit and cannot be resolved by ancestry.

`recover` never invents, retries or re-runs anything.

## Write ownership

Generation verbs write ONLY under `<study>/generation/` and commit only those paths
(`commit_state_writes(..., scope="own")`). They never write `study_state.json`, the
core `events.jsonl`, `runs/`, `claims.lock`, `verify_receipt.json` or `study.yaml`. An
in-flight edit to the mutable surface is the operator's and stays theirs.

<!-- WP-09: design -->
## Evidence design

*The `design` capability — declared with `klein generation init --capability design`.*

```bash
uv run --locked klein generation design lock --study studies/NN-slug [--allow-late]
```

The five objects (`references/inquiry-model.md`) run a study; they do not say what a
number MEANS. A metric that improved says nothing about which quantity was estimated,
on which population, under which identification assumptions, how far the result was
meant to travel, or which warrant carries it to a claim. Those commitments are cheap to
write afterwards, in whatever shape the result happened to take — which is exactly why
they are written first. `evidence_design.yaml` is that artifact: one document at the
study root, five blocks, locked into the extension chain **before the DATA gate**.

Before the DATA gate, not before CONSULT: the data gate is where the evidence source is
first profiled, and a design registered once the evidence has been looked at is a
description rather than a commitment. `design lock` refuses once a `gate_recorded data`
event exists; `--allow-late` records the lock anyway, marks it `late`, and FAILs
`design lock` for the life of the study. The design is locked ONCE — a change of
estimand, validity condition or warrant is a successor study, not a second lock.

| Block | Fields |
|---|---|
| `question` | `estimand`, `population`, `units`, `measurement_process`, `identification_assumptions[]`, `intended_generalization` |
| `prediction` | `uncertainty_method`, `validity_conditions[]` (`{condition, rule_ref}`), `practical_threshold`, `provenance` |
| `evidence` | `representations[]`, `dependency_hierarchy`, `permitted_reuse`, `seal` (`{holder, mechanism}` or null), `acquisition[]` |
| `claim` | `warrant`, `supporting_evidence[]` |
| `decision` | `continuation`, `predecessor`, `successor` |

`warrant` is closed: `prediction | conditional-estimation | causal-inference |
exploratory-structure | checked-witness` — a warrant nobody can name is a warrant nobody
can review. `continuation` is closed too: `continue | stop | escalate | pivot`.
Template: `assets/evidence-design-template.yaml`.

**A validity condition is executable, or it is decoration.** Each
`validity_conditions[].rule_ref` names a registered prediction (`P#`) in `study.yaml`,
and that prediction's rule must be able to FIRE the condition: either an
`inconclusive_if` **rule** (checked before the rule, returning `inconclusive` — the
pre-registered admission that some runs cannot decide the question) or a `rule` whose
root is an `all_of` / `any_of` / `not` combinator. Two shapes are refused: a plain leaf
comparison, which asks only whether the number cleared the bar and never whether the run
was in a position to answer; and a prose `inconclusive_if`, which documents a human
condition the machine never reads. The condition has to reach the arithmetic `run-one`
actually runs, or the design has recorded a hope.

The cross-check is re-run at every `generation verify` against `study.yaml` **as it is
now**. The design's copy is frozen; the contract is not, so a prediction whose
`inconclusive_if` was dropped after the lock leaves a validity condition pointing at a
rule that can no longer express it — caught, rather than silently tolerated.

**Import chronology is not acquisition chronology.** Each `evidence.acquisition[]` entry
carries `source`, `kind` and `acquired_at`. `kind: import` records when the BYTES
arrived here and needs nothing more. `kind: acquisition` claims when the MEASUREMENT was
taken — a statement about the world that no hash can check — and is refused without
`custody` (who held it in between) and `attested_by` (who attests that chain, by name).
Recorded, never verified: like the roster and the seal's mechanism, these are testimony.
Record the arrival as `kind: import` when only the arrival is known.

**Admission.** On a declaring study a `klein generation check --action cell` is refused
until the design is locked: a cell measures something, and the design is what says what.
Ordinary `run`, `sealed`, `baseline`, `repair` and `calibration` admissions are
untouched by this capability.

**The family** (`design lock`, `design document`, `design acquisition`,
`design conditions`) FAILs when: no lock exists; the lock is `late`, or its anchor does
not precede the data gate record by both core sequence and git ancestry; more than one
lock exists; `evidence_design.yaml`'s sha256 differs from the locked one; a block is
incomplete or a vocabulary word is wrong; an acquisition entry lacks its custody chain;
or a `rule_ref` no longer resolves to something executable. The capability `outcome` is
`locked` or `unlocked`, reported beside `integrity` and never read as a judgement.

**What a locked design establishes.** That these commitments predate the data gate and
have not changed since. **Not** that the identification assumptions hold, not that the
estimand is the right one for the question, not that the intended generalization is
achievable, and not that the custody chain was honoured. Every one of those is a matter
for the referee and for the reader; the lock only guarantees they were stated in
advance, in a form a stranger can compare against what the study ended up claiming.
<!-- end WP-09 -->
