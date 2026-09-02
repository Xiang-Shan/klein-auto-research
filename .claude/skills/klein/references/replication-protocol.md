# Replication — convergent evidence, inside and outside a study

Two things are called replication and Klein keeps them apart. **Internal
replication** re-executes one of this study's own runs to show the number was not an
accident of one process. **External replication** is a study kind (`replicate`) whose
question is whether a published result reproduces. Both produce evidence ids; neither
is a second look at sealed data.

Role: the driving agent; the referee reads the records. Any agent or human can follow
this document directly.

## Internal: `klein replicate`

```bash
uv run --locked klein replicate --study studies/NN-slug E0003 [--tolerance 0.001]
uv run --locked klein replicate --study studies/NN-slug E0007 --verify-only   # verifier tracks
uv run --locked klein replicate --study studies/NN-slug --list
```

- A development run is re-executed from its manifest in a **detached git worktree**
  at its `candidate_commit`, created in the system temporary directory and always
  removed afterwards; the prepared data is copied in and its fingerprint asserted;
  the child runs with `KLEIN_REPLICATION=1` and every smoke or dry-run flag cleared.
- The printed block is compared with the manifest's within a tolerance chosen from
  this ladder: `--tolerance` > the track's `minimum_delta` > the floor's std > exact
  (for `metric.exactness: exact`).
- The record is `runs/E####/replications/<ts>.json` (`reproduced: true|false`, both
  blocks, the difference, the tolerance, the environment fingerprint) plus the log;
  the event `run_replicated` is appended; the manifest is never touched. The evidence
  id is `rep:E####@<ts>`.
- `--verify-only` (tracks with a declared verifier) re-runs only the verifier on the
  pinned artifact in a fresh process — no search, no worktree — and records
  `mode: verify`; the evidence id is `verify:E####@<ts>`.
- Refused, with no override: sealed runs (a replication would be a second look) and
  crashes (there is nothing to reproduce; run a new candidate instead).

## `confirmation.require`

Per track, a subset of `{sealed, replicate, verify}`; the default follows the kind
(`inquiry-model.md`). `klein finalize` labels a track's claims `confirmed` only when
every required kind of record exists for the final incumbent (or, for registered
tracks, for every cell a confirmed claim cites); otherwise the label is `exploratory`
and the receipt says which record is missing.

## Reading a failed replication

`reproduced: false` is evidence, not a scandal. In order: compare the two environment
fingerprints (device, library versions, thread counts); look for undeclared
nondeterminism (seeds not set, hash-ordered iteration, GPU kernels); decide whether the
difference exceeds the floor. If it does and a claim rested on the run, file an
erratum (`klein claims erratum`) that re-scopes the claim to what still holds. Never
re-run until it passes and keep only the pass: every attempt leaves a record.

## External: the `replicate` kind

A `replicate` study registers, at CONSULT, every target value with its source and its
tolerance, and an **identity anchor**: E0001 reproduces a published sum, count or
table dimension from the transcribed data and hard-STOPs on mismatch (study 10: the
sums of distance and velocity over Hubble's 24 objects). Data that had to be re-typed
is transcribed from two independent sources and the transcriptions diffed before the
DATA gate.

Each target is one prediction (`within: {target, tol}`), adjudicated by a registered
cell. Findings report target by target; "we replicated X" is banned unless every
target reproduced within its tolerance, and a target that did not reproduce is
reported with the most likely reason (a method gap, an undocumented step, a
transcription error) — a documented method gap is a finding, not a failure.

## Where replication sits

REFEREE check 1 asks which evidence kind confirms each claim; `klein verify
--evidence-use` warns on a `confirmed` claim with a single evidence kind. A study that
wants its claims to survive a stranger's re-run declares `confirmation.require:
[sealed, replicate]` and pays for it before the seal is spent.
