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

Beside those six, each capability adds its own verb group — plus one group that
belongs to no capability at all. Every group in this release, in dependency order:

```bash
uv run --locked klein generation expert lock|amend|bind|repair|review --study studies/NN-slug
uv run --locked klein generation reference record                     --study studies/NN-slug
uv run --locked klein generation slate lock|amend|score|show --study studies/NN-slug --phase <id>
uv run --locked klein generation design lock                 --study studies/NN-slug [--allow-late]
uv run --locked klein generation premortem record|respond    --study studies/NN-slug --phase <id>
uv run --locked klein generation parity lock|amend|bind|assess|show --study studies/NN-slug
uv run --locked klein generation contribution record|show    --study studies/NN-slug
uv run --locked klein generation escalate lock|record|close|pivot|show --study studies/NN-slug
uv run --locked klein generation knowledge promote|contest|resolve|query|decide|show --study studies/NN-slug
uv run --locked klein generation surprise register|record|show --study studies/NN-slug [--run E####]
uv run --locked klein generation benchmark commit|submit|reveal|retire|show --study studies/NN-slug
uv run --locked klein generation custody attest              --study studies/NN-slug
```

`expert` and `reference` are the two groups of the single `expertise` capability
(`references/expert-protocol.md`, `references/reference-protocol.md`). Each group from
`slate` to `benchmark` is one capability, named the same but for two: the `slate` group
is the `slates` capability and the `escalate` group is `escalation`. A capability not
declared at `init` is inert: its verbs exit 1 rather than write, because the opt-in is
immutable and a study that wants one declares it at `init` or succeeds itself.

`custody attest` is **capability-agnostic**: it needs the opt-in and nothing else,
because a hidden benchmark bundle, a custodian-held later time block and a wet-lab
sample chain are the same receipt (`references/planted-truth-protocol.md`).

Every WRITING verb (`init`, `check`, `label`, `recover`,
`expert lock|amend|bind|repair|review`, `reference record`,
`slate lock|amend|score`, `design lock`, `premortem record|respond`,
`parity lock|amend|bind|assess`, `contribution record`,
`escalate lock|record|close|pivot`,
`knowledge promote|contest|resolve|query|decide`, `surprise register|record`,
`benchmark commit|submit|reveal|retire`, `custody attest`) takes the four
**testimony** flags `--actor --tool --model --session`; `verify`, `status`,
`slate show`, `parity show`, `contribution show`, `escalate show`, `knowledge show`,
`surprise show` and `benchmark show` write no event and take none.

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
`benchmark ⇒ parity`, `surprise ⇒ design`. **This release supports all ten:
`expertise`, `slates`, `design`, `premortem`, `parity`, `contribution`,
`escalation`, `knowledge`, `surprise` and `benchmark`** (see
`references/expert-protocol.md`, "Slates and calibration" and "Evidence design"
below, `references/premortem-protocol.md`, `references/expert-parity-protocol.md`,
`references/escalation-protocol.md`, `references/knowledge-protocol.md`,
`references/surprise-protocol.md`, and `references/planted-truth-protocol.md`) —
so the *not available* refusal is what a study meets when it is carried back to an
older Klein, or to a build whose modules were trimmed. Opting in with
`capabilities: []` still buys the admission discipline and
the chronology witnesses, and nothing that scores research. **Capability additions
after opt-in are not available in this release**: there is no amendment verb and no
manifest amendment event, so declare the full set at `init`, or start a successor
study. (`scope.late_added` is part of the receipt's fixed shape and is always `[]`.)

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
| `inputs` | the manifest hash, plus six fixed slots a declared capability may FILL and none may add to: `slate`, `premortem`, `parity`, `cells`, `design`, `benchmark` — the commitments in force, null when the capability is not declared or cannot resolve its artifact yet |
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

## Slates and calibration

*The `slates` capability. Declare it at `init`; a study that did not is untouched by
everything in this section.*

```bash
uv run --locked klein generation slate lock  --study studies/NN-slug --phase adaptive-1
uv run --locked klein generation slate amend --study studies/NN-slug --phase adaptive-1
uv run --locked klein generation slate score --study studies/NN-slug --phase adaptive-1
uv run --locked klein generation slate show  --study studies/NN-slug [--phase <id>]
```

**You write the slate; Klein records it.** `slates/<phase>.yaml` is authored by hand at
the phase start, exactly as `references/phase-ritual.md` has always asked: 4–6
falsifiable candidates, each scored 1–3 on novelty / testability / expected
information, before the mutable surface is touched. Nothing here proposes a candidate,
compares two, or orders the rows — the axis scores are validated and copied verbatim,
and the arithmetic below is arithmetic on rows you typed. `assets/slate-template.yaml`
carries the full shape with comments.

`slate lock` refuses 3 rows or 7, a duplicate statement, a probability that is not
strictly inside (0, 1), an axis score outside {1, 2, 3}, an undeclared track, a
`floor_ref` that is neither `minimum_delta` nor a **registered** `sweep:<name>`, and a
`success_P` that study.yaml does not register, that is manual, or that belongs to
another track, and a `parent_ids` entry naming a hypothesis id no slate in this study
ever allocated. Then it assigns each row a permanent **`<study>#Hn`** — monotonic across
the whole study, never recycled — rewrites the file with the ids in place, and hashes
the committed bytes into the lock object.

**A locked forecast is immutable.** Editing `p_success` afterwards changes the file's
sha and FAILs `generation slate` for the life of the study. The lawful revision is
`slate amend`: a new version with the previous lock as its parent, in which a changed
`p_success` sets `revision_of` and is scored in its own panel — the primary panels
always use the FIRST forecast. Once set, `revision_of` is carried forward by every later
version, so a revised row stays in the revisions panel rather than sliding back into the
primary one at the next amendment that leaves it alone. An amendment may add rows (fresh ids) and drop rows, but
may never revive a freed id, re-point an existing one at a different hypothesis, or
restate the frozen `base_rate_forecast` and `cohort_window`.

### Admission: a run is bound to the hypothesis it was admitted for

```bash
uv run --locked klein generation check --study studies/NN-slug --action run \
  --track primary --hypothesis NN-slug#H1 --tests P2
```

`--hypothesis H` is admitted only when H is a **live row of the newest locked slate for
the study's current phase**, `--track` is the row's track, and `--tests` names every one
of the row's `success_P` — the notary must adjudicate them inside that run, or the row's
outcome could never resolve. The receipt pins the lock's object sha in `inputs.slate`
and the id in `intended_action.hypothesis_id`; that receipt, once consumed by an
`admitted` run, is what BINDS the run to the row. There is no separate bind step and no
prose route: a run the extension classified anything but `admitted` binds nothing.

On an enabled study, `--action run` (and `--action cell`) **without** a hypothesis is
refused: "an enabled study runs hypotheses; use `--hypothesis`, or `--action
calibration|baseline|repair`". The Phase-0 floor recipe, the expert baseline, a repair
and the sealed final test are the typed obligations that legitimately carry no `H`
(R-ADM-7) — they are ordinary `run-one` transactions with their own checkpoint, and no
off-notary path exists for any of them.

### The success event, exactly

For row `H`, the bound run is the one its **FIRST** admitted receipt was consumed by — a
forecast is about what happens when the idea is tried, so the first resolution scores.
Every further admitted run on the row is counted as `n_bound_runs` (a column of the
calibration table and a field of the score object) and the family WARNs when any row
carries more than one; re-running a resolved row leaves `y` where it was.

| | |
|---|---|
| `y = 1` | that run did not crash AND every `success_P` was adjudicated `supported` on it |
| `y = 0` | that run crashed, OR any `success_P` was adjudicated `refuted` |
| censored | no bound run before the cohort closed; or a `success_P` came back `inconclusive` or was never adjudicated on that run |
| withdrawn | the row was dropped by an amendment — retained in the cohort, censored, with the version that dropped it on the record |

`slate score` records the core-chain tip as `closed_at_core_sequence`, writes
`generation/tables/slate_calibration_<phase>.tsv` (one row per cohort member: id, panel,
p_first, p_latest, status, y, reason, run, n_bound_runs) and hashes it. A phase is scored once;
`--rescore --reason <why>` records a further score whose parent is the previous one —
both objects survive, because a cohort that reopened is a fact about the study.

**The denominator is frozen at lock.** Coverage is `resolved / cohort` over every id
ever locked for the phase. Withdrawing a row does not shrink it, and neither does never
running one: both report as coverage below 1.0 and an outcome of `conditional`, never as
a better Brier. `complete` is issued at coverage 1.0 and nowhere else. Every panel also
carries `best_case_brier` and `worst_case_brier` — the censored rows scored the most and
the least favourably possible — so a partial cohort reports the interval its own gaps
allow instead of a single flattering number.

**Four panels, and only two of them are calibration.**

| Panel | Rows | Read as |
|---|---|---|
| `unscouted` | `provenance: unscouted`, on `p_first` | calibration |
| `derived` | `provenance: derived` (read off an earlier H), on `p_first` | calibration, separately |
| `scouted_descriptive` | `provenance: scouted` — the scouting ledger already saw the outcome | **descriptive only, never calibration** |
| `revisions` | rows with `revision_of`, on `p_latest` | how a revised forecast fared |

Each panel reports `n`, `brier`, `binned_brier`, `base_rate_brier`, `skill`, the Murphy
decomposition (`reliability`, `resolution`, `uncertainty`) over five equal-width bins,
the bins themselves, and the two bounds. The Murphy identity `brier = reliability −
resolution + uncertainty` closes exactly on `binned_brier`, not on the plain Brier; both
are reported so a reader does not have to derive that.

`generation slate` FAILs on: a hypothesis admitted before the lock in force, or naming an
id that is not a live row of it; a slate file whose sha is not the newest version's; a
recycled or non-monotonic id; a recorded score whose recomputation from the receipts,
the manifests and the core chain differs in any number (compared at rel 1e-12); a cohort
row missing from the score; a calibration table that is not the one the score hashed. It
WARNs on coverage below 1.0, on a row with `n_bound_runs > 1`, and on a phase
acknowledged without a score. Its outcome is
`complete`, `conditional` or `unscored`, and the label copies it.

### What a slate score establishes, and what it does not

A four-row slate proves the ARITHMETIC, not calibration in general: three resolved rows
say nothing about whether the driver is well calibrated, and the receipt's `n` is printed
beside every Brier so nobody reads it as more. Nor does the mechanism see semantic
duplicates — two rows phrased differently for one idea pass the duplicate check — or
judge whether a hypothesis was worth forecasting. What it does establish is that the
forecasts existed, unchanged, before the evidence, and that the score over them is the
one the ledger implies.

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

`generation/label.json` carries exactly these fields:

| Field | What it says |
|---|---|
| `schema`, `kind` | `klein-generation/1`, `label` |
| `study` | the study's own id |
| `label` | always `generation-verified` — the one label this verb issues |
| `git_head` | HEAD at issue; the findings line quotes its first 12 characters |
| `core_receipt_sha256`, `generation_receipt_sha256` | the two receipts that passed together |
| `capabilities` | every name of the ten-name vocabulary, mapped to the OUTCOME its family reported, `n/a` for the rest — the key set is stable across releases |
| `rung` | `local-order` |

**Integrity is not outcome.** `generation-verified` says the record is intact and every
action was admitted before it ran. It says nothing about whether the research
succeeded: an honestly stopped study with every capability outcome `incomplete` can
carry it, and a spectacular result with one unadmitted run cannot. The label copies
each declared capability's outcome and never its integrity — which the label as a whole
already carries. It is capability-scoped — every capability this study did not declare
is listed `n/a` — and its `rung` is **always `local-order` in this release**: no input
raises it, a `custody attest` receipt included. A custody attestation is reported where
it was recorded (the `benchmark` capability's entry, and the receipt on the ledger),
never as the rung — this layer cannot verify custody, and a rung is a claim about what
was verified.

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

`recover` never invents, retries or re-runs anything — and it never rewrites a stored
object. The store is content-addressed and write-once: a file whose bytes no longer
hash to its own name (or that cannot be read at all) was rewritten in place, every
writing verb refuses until it is restored BY HAND (`git checkout -- <path>`), and
writing an object over different bytes under the same name is refused rather than
completed.

## Write ownership

Generation verbs write ONLY under `<study>/generation/` and commit only those paths
(`git commit --only -- <the paths the verb wrote>` — never a commit scope that
prepends core state to them), plus the named human artifacts a capability
files with them — `domain_card.md`, `slates/<phase>.yaml`, `premortem/<phase>.yaml`,
`evidence_design.yaml`, `parity.yaml`, `ai_value.jsonl`, `escalation_plan.yaml`,
`discovery_cells.yaml`, and the benchmark's `benchmark.yaml`,
`benchmark-submission.schema.json` and `submissions/<arm>.json` — and the two
REPO-level stores that are facts about the repository rather than one study:
`knowledge/references/<id>.json` and `knowledge/objects/<sha256>.json` with
`knowledge/events.jsonl`. The one verb that files paths it is not given in advance is
`expert repair`, which commits exactly the repaired files it recorded — minus anything
in the mutable surface, which `run-one` owns and which filing would silently move the
restore anchor. They never write `study_state.json`, the core
`events.jsonl`, `runs/`, `claims.lock`, `verify_receipt.json` or `study.yaml`, and
naming one of those in a commit is refused rather than filed. An in-flight edit to
the mutable surface is the operator's and stays theirs.

**A dirty core state stops a generation verb.** If `study_state.json` or the core
`events.jsonl` has uncommitted changes, every writing verb refuses ("core state is
dirty; that is run-one's or `klein recover`'s to file, not a generation verb's"):
a receipt anchored to a core event that no commit yet carries cannot be resolved by
ancestry afterwards.

**A study that never opted in is never touched.** `klein generation verify` on a
study with no `generation/manifest.yaml` and no `generation/events.jsonl` exits 1
and writes nothing — no directory, no FAIL receipt, no commit. Not opting in is not
a failure. A manifest that was deleted or edited AFTER an opt-in still meets the
FAIL path: losing the opt-in is a finding, not an exemption.

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
<!-- WP-06: surprise -->

## Discovery cells

*The `surprise` capability, which requires `design`. Its rules are long enough to have
their own file: `references/surprise-protocol.md`.*

`klein generation surprise register` freezes `discovery_cells.yaml` — the cells, their
adapters and inputs with pinned hashes, their frozen segment inventories, `minimum_n`,
and a declared multiplicity rule — after METHOD and before any cell evidence. A cell is
admitted with `--action cell --cell <id>` (whose `--tests` must include the cell's
registered `expectation_P`) and runs through ordinary `run-one`, pinning its per-unit
table with an `artifact:` line. `surprise record --run E####` re-reads those bytes,
recomputes every segment of the frozen inventory, applies the declared family rule once,
and issues one `<study>#Sn` receipt per violation while retaining the null and
inconclusive segments. The receipt pins the registration in `inputs.cells`; the
`surprise` family recomputes the record and FAILs a `confirmed` claim that rests on it.
<!-- end WP-06 -->
