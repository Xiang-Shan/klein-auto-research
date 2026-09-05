# EXPERT — acquiring a domain, and proving you acquired it

An agent can read a field's literature and write a fluent card about it in an
afternoon. Fluency is exactly what a language model produces without
understanding, so a card on its own establishes nothing — and a study whose first
move is a confident summary of a field it has never executed in is the most
common way AI-for-science work goes quietly wrong.

The `expertise` capability turns the card into a falsifiable commitment: it names
a baseline recipe from the literature, freezes the numbers that recipe should
reproduce, and then **executes it through the ordinary notary** before any
challenger of the driver's own is allowed to run. Opt-in, schema-3 only, and
inert unless `generation/manifest.yaml` declares `expertise`
(`references/generation-protocol.md`).

> **Passing establishes reproduction of THAT recipe, on THAT fixture, to THOSE
> tolerances. It does not establish representative domain expertise**, that the
> card's doctrine is right, or that the shortlist was the right shortlist. The
> outcome vocabulary says so: `source-reconstructed` when the team reproduced it
> themselves, `independent-review` only when a reviewer who is not the roster's
> experimenter attests it with a session receipt.

Role: the driving agent, before CONSULT and again after METHOD. Any agent or
human can follow this document directly.

## Verbs

```bash
uv run --locked klein generation expert lock   --study studies/NN-slug [--allow-late]
uv run --locked klein generation expert amend  --study studies/NN-slug
uv run --locked klein generation expert bind   --study studies/NN-slug E0001
uv run --locked klein generation expert repair --study studies/NN-slug --changed lib/prep.py --note "…"
uv run --locked klein generation expert review --study studies/NN-slug --reviewer NAME \
    [--reviewer-model M] [--reviewer-tool T] [--session-receipt PATH] --statement "…"
```

Every one takes the four testimony flags `--actor --tool --model --session`
(recorded, never authenticated). Exit codes follow the layer's convention: `0`
did it, `1` the study is not in a state where the question can be asked, `2` the
question was asked and answered no. `expert bind` exits `2` on `mismatch` or
`crash` — the verdict is still recorded, because negative evidence is evidence.

## 1. The domain card, locked before CONSULT

Copy `assets/domain-card-template.md` to the study as `domain_card.md`, fill its
frontmatter, and lock it **before `klein gate record consult`**. The lock is what
makes the card evidence: it hashes the file, copies the frontmatter verbatim into
a write-once object, and anchors it in the core chain ahead of the gate. A card
locked afterwards cannot constrain what it was supposed to constrain —
`--allow-late` records it anyway and `expert card` FAILs for the life of the
study.

| Frontmatter key | Rule at lock |
|---|---|
| `type`, `study`, `scope`, `as_of`, `incumbent` | present, non-empty |
| `sources[]` | non-empty; each `{record_id, role}` with `role ∈ doctrine, pipeline, metric, incumbent, pitfall`, and each `record_id` resolving to `knowledge/references/<id>.json` (`references/reference-protocol.md`) |
| `pipeline_steps[]`, `metrics[]` | non-empty — what the field actually runs, and what it actually measures |
| `method_shortlist[]` | non-empty. **It precedes METHOD**: the shortlist is what the method card will choose FROM, so writing it after the choice is writing the exam after the answer |
| `doctrine[]`, `pitfalls[]`, `unknowns[]` | lists; may be empty. An empty `unknowns` is a claim, not an omission |
| `baseline.implementation`, `baseline.fixture` | study-relative paths that EXIST at lock |
| `baseline.config` | a study-relative path or an inline mapping |
| `baseline.targets[]` | non-empty `{key, value, tol, rel}`; `key` is the metric key the run will PRINT, `tol >= 0`, `rel: true` reads the tolerance as a fraction of `value` |
| `baseline.review` | `source-reconstructed` or `independent` — what the driver INTENDS; the outcome is decided by the recorded reviews, never by this word |

`expert amend` records a new version with `parent_ids` pointing at the previous
lock. **Targets are frozen at version 1** — key set, value, tolerance and `rel`.
An amendment that moves any of them is refused, and one hand-edited into the
ledger FAILs `expert card`:

> Lowering a bar you did not clear is not a repair. A target change requires a
> successor study.

## 2. The obligation, executed as an ordinary run

After DATA and METHOD, the baseline runs like everything else runs — edit the
surface, take an admission, run the notary:

```bash
uv run --locked klein generation check --study studies/NN-slug --action baseline --track primary
uv run --locked klein run-one --study studies/NN-slug
uv run --locked klein generation expert bind --study studies/NN-slug E0001
```

There is **no off-notary path**. `baseline` and `repair` are ordinary checkpoints
of `klein generation check`; the run is an ordinary `run-one` transaction with an
ordinary manifest and an ordinary disposition. What the capability adds is
arithmetic afterwards.

`expert bind E####` reads the run's manifest, requires it to have consumed an
admitted receipt whose checkpoint is `baseline` or `repair`, and for each frozen
target computes

```
observed = manifest.metrics[key]        # the block the run PRINTED
delta    = observed − value
within   = |delta| <= (tol × |value| if rel else tol)
```

| Verdict | When |
|---|---|
| `crash` | the run's disposition is `crash` — a crashed run reproduced nothing |
| `mismatch` | a target key was not printed, or any `within` is false |
| `reproduced` | every target within tolerance on a non-crash run |

The verdict is recorded whatever it is. **Until a `reproduced` bind exists, no
`run` or `sealed` admission (and no hypothesis admission) is granted** — the
refusal reads `baseline obligation open: no expert bind with verdict
reproduced`. `baseline`, `repair`, `calibration` and `cell` stay admittable, so
the way forward is always open and it always goes through the record.

## 3. Repairs are versioned, and they change the implementation

A failed reproduction is a finding about the driver's implementation, not about
the target. Fix the implementation, then say so before running again:

```bash
uv run --locked klein generation expert repair --study studies/NN-slug \
    --changed lib/prepare_offsets.py --note "the exposure offset was omitted"
uv run --locked klein generation check --study studies/NN-slug --action repair --track primary
uv run --locked klein run-one --study studies/NN-slug          # --allow-rerun if the surface is byte-identical
uv run --locked klein generation expert bind --study studies/NN-slug E0002
```

- `--changed` records each file's sha256 AT REPAIR TIME. `klein generation
  verify` re-reads those paths at the **candidate commit of the next bound run**
  and FAILs if the bytes differ — a repair that claims a change it did not make
  is detectable.
- A changed file **outside** the mutable surface is filed by the repair (the next
  `run-one` refuses a dirty tree). A changed file **inside** the surface is left
  alone: `run-one` owns the surface, and committing it here would silently move
  the restore anchor.
- **The declared verifier is never repairable.** The checker is never the
  searcher, and it is never the repair either; `--changed <verifier>` is refused.
- `--action repair` is admitted only when an `expert repair` object was recorded
  after the last bind. Repairing without recording it is the same failure as
  running without an admission.

Each repair is version *n+1* with the last bind as its parent, and the count
appears in the capability outcome as `repairs: n`. A study that needed three
repairs and says so is in better shape than one that needed three and reported
one.

## 4. Review rungs

```bash
uv run --locked klein generation expert review --study studies/NN-slug \
    --reviewer "A. Practitioner" --session-receipt review-session.md \
    --statement "the recipe and the fixture match the published ones"
```

| Outcome | Earned when |
|---|---|
| `incomplete` | no `reproduced` bind yet. **Label-eligible**: an honestly open obligation with no challenger runs is a WARN, never a FAIL |
| `source-reconstructed` | reproduced by the team that wrote the card — the default, and the honest ceiling for most studies |
| `independent-review` | a recorded review carrying a **session-receipt hash** whose reviewer is not `program.md`'s `## Roster` experimenter |

Independence is checked as **string inequality against the roster cell and each
of its `model · tool · session` components** — testimony, exactly like the
referee's rung, never authenticated identity
(`references/generation-protocol.md`, "what this does NOT establish"). A review
with no session receipt, or by an actor the roster already names, is a WARN and
raises nothing. A blank experimenter row means independence cannot be
established at all — the same cap the referee protocol applies.

## 5. Verification

`klein generation verify` runs the `expert` family alongside the spine's eight.

| Check | FAILs when |
|---|---|
| `expert card` | not locked; locked late (or `--allow-late`); the lock does not precede the consult gate by sequence AND git ancestry; `domain_card.md`'s sha256 differs from the newest lock; an amendment changed a target |
| `expert references` | a `sources[].record_id` has no record; a recorded reference's bytes changed; a record contradicts its own verification basis; a `references.yaml` row says `verified: true` with no resolvable `record_id` |
| `expert obligation` | a bind's arithmetic does not recompute from the manifest and the lock; a bind on a run whose admission was not `baseline`/`repair`; an **admitted** `run`/`sealed`/hypothesis receipt recorded before the first `reproduced` bind |
| `expert repairs` | a repair's changed files do not match their bytes at the next bound run's candidate commit |
| `expert review` | — (WARN only: no session receipt, reviewer is the experimenter, or no roster to compare against) |

The capability entry in `generation/verify_receipt.json` is
`{"integrity": PASS|FAIL, "outcome": incomplete|source-reconstructed|independent-review,
"repairs": n}`, and `generation/label.json` copies the **outcome** into its
`capabilities` column. Integrity is not outcome: a study that never reproduced
its baseline can still be `generation-verified` if it never pretended otherwise.

## What this establishes, and what it does not

- **Establishes:** that a named recipe from named sources, with numbers frozen
  before it ran, was executed under the notary and either hit those numbers or
  did not — and how many recorded repairs it took.
- **Does not establish:** domain expertise; that the card's doctrine or pitfalls
  are correct; that the shortlist was complete; that the fixture is
  representative; that the reviewer read anything (the receipt is a hash of a
  file the driver points at). A baseline weakened in a way that still passes its
  own fixture is **not detected** — that is a referee obligation
  (`references/referee-protocol.md`).
