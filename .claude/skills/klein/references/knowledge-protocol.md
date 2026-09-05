# Cross-study knowledge — transactions over pinned evidence

`knowledge/` has always held the framework's durable lessons as markdown with
typed claim citations, and **that convention is unchanged**: it is the human
surface, it is greppable, and no verb described here ever writes a line of it.

What markdown cannot answer is the set of questions that decide whether "we built
on prior work" means anything:

- Did this study **look**, before it committed to a question?
- Did it see the **refutation**, or only the claim?
- Is the imported statement **as strong as** the one that was earned?
- Is one lesson repeated in ten places **one** piece of evidence, or ten?

So a generation-enabled study that declares the **`knowledge`** capability gets a
second, machine surface beside the markdown: a repo-level store of write-once
objects and an append-only chain of transactions over them.

```bash
uv run --locked klein generation knowledge query   --study studies/NN-slug \
    --tags calibration tabular --text "how should weak-signal scores be calibrated" \
    --reject "K1=contested outside our regime; we re-measure rather than inherit"
uv run --locked klein generation knowledge promote --study studies/NN-slug \
    --claim C3 --tags calibration tabular \
    --scope "population=weak-signal insurance-like tables" \
    --scope "measurement_regime=held-out AUC at a tuned threshold"
uv run --locked klein generation knowledge contest --study studies/MM-other \
    --target K1 --evidence MM-other#C1 --rationale "measured outside the stated regime; it lost"
uv run --locked klein generation knowledge resolve --study studies/MM-other \
    --target K1 --outcome scoped --rationale "the claim holds inside its stated regime"
```

## The store — repo-level, because knowledge is not a fact about one study

`knowledge/objects/<sha256>.json`, write-once and content-addressed:

```json
{"schema": "klein-generation/1", "kind": "knowledge", "id": "K7",
 "type": "claim|method", "origin_repo": "<remote url|local>",
 "study": "<study id>", "commit": "<the commit whose tree holds the source>",
 "lock_git_head": "<the lock's own git_head>",
 "source_path": "studies/NN-slug/claims.lock", "source_hash": "<sha256>",
 "claim_id": "<study>#Cn|null", "text": "the sentence, verbatim",
 "class": "<the claim's class>", "strength": "<the claim's strength>",
 "scope": {"population": …, "measurement_regime": …, "intervention": …,
           "assumptions": […], "exclusions": […]},
 "tags": ["…"], "evidence_roots": ["E0001", "art:…", "sweep:…"],
 "dependencies": ["K3"]}
```

`knowledge/events.jsonl` carries the store's OWN hash chain — `previous_hash`
links each transaction to the one before it, exactly as the study ledgers do:

```json
{"schema": "klein-generation/1", "id": "KE0002", "sequence": 2,
 "operation": "promote|contest|resolve", "target": "K7", "study": "<study id>",
 "object_sha": "<sha|null>", "evidence_ids": ["…"], "rationale": "…",
 "resolution": "upheld|scoped|withdrawn|null",
 "actor": …, "tool": …, "model": …, "session": …,
 "created_at": "…informational…", "previous_hash": "…", "event_hash": "…"}
```

`actor/tool/model/session` are **testimony** — self-reported, never
authenticated. `created_at` is informational; order comes from the chain and from
git, never from a clock.

Ids (`K1`, `K2`, …) are monotonic across the whole store and are never recycled.
Objects are never deleted and never edited: an object whose bytes no longer hash
to their own file name FAILs, and so does an object an event references that is
no longer on disk.

## A promotion never strengthens

`knowledge promote` copies `class`, `strength` and `evidence_roots` **verbatim**
out of the source study's `claims.lock`. It creates AVAILABILITY, not evidence:
the same sentence, reachable from another study, at exactly the standing it
earned where it was made.

Two refusals enforce that:

- **The source lock must verify NOW.** `klein claims verify` is run against the
  promoting study at promotion time; any failing check refuses the promotion. A
  claim you cannot verify is not a claim you may export.
- **Dedupe is by EVIDENCE ROOTS, never by citation count.** An object whose roots
  are already in the store is refused, naming the id that holds them. Repeating a
  lesson across ten studies manufactures apparent corroboration; the roots are
  what makes two rows the same row.

`--method` promotes the study's `method_card.md` instead, pinned with its
reference records (`references/reference-protocol.md`): the roots are the
`ref:<key>` rows of `references.yaml` that name a resolvable `record_id`, and a
method promotion with none is refused rather than filed unpinned.

**Scope is the author's judgement and the mechanism cannot check it.** A3 §5
scopes an object by population, material, measurement regime, intervention,
assumptions and exclusions. Nothing here verifies that those tags are honest, and
`--scope` accepts what the driver writes. What it does do is make the scope
visible to the next study, which is what a contest is argued against.

## A contest is contradicting evidence, not disappointment

`knowledge contest` attaches opposing evidence to an object. Both sides stay
forever; nothing is overwritten.

> **A failed transfer is a prediction verdict, not a contest.** A registered
> prediction that did not hold in a new regime is `refuted` or `inconclusive` in
> the citing study's own ledger, with its dated `Decision:` line in `program.md`.
> It becomes a contest only when a CLAIM contradicts the target's scope.

Mechanically: every `--evidence` id must resolve in the citing study's own
verified lock, and **at least one must be a claim** of that study. Prediction ids
alone are refused. The citing study's lock must verify, like a promotion's.

`knowledge resolve` appends an adjudication — `upheld`, `scoped` or `withdrawn` —
without deleting either side. `withdrawn` keeps the object and attaches the
withdrawal: a reader who follows an old citation still finds what the claim was,
and then finds what happened to it.

## The consultation receipt — before the CONSULT ack

A declaring study runs `knowledge query` **before** `klein gate record consult`.
A store read after the ack is a bibliography, not a consultation: it cannot have
changed the question it was supposed to inform. `generation verify` checks the
order by core sequence AND by git ancestry, and FAILs a late one.

The receipt records:

| Field | What it pins |
|---|---|
| `contract_draft_sha256` | the `study.yaml` this consultation informed |
| `store_head` | the repository commit whose `knowledge/` tree was read |
| `retriever_version` | `lex-1` — the algorithm the replay must reproduce |
| `typed_query` | the tags and the text, case-folded |
| `hits[]` | **every** object with any overlap: id, score, object sha, and its contest/resolution closure |
| `limit` / `truncated` | present only when the driver asked for a top-k, so truncation is visible rather than convenient |
| `decision[]` | `use` or `reject`, **with a reason**, for every hit |
| `no_match` | true when the store held nothing that overlapped |

**An empty store is consulted, not skipped.** The first study in a fresh
repository records `no_match: true`, and CONSULT cites that receipt. That is the
bootstrap: there is no state in which "there was nothing to find" is unrecorded.

**Contest closure travels with the hit.** The buried-refutation failure is not
that the refutation is unfindable — it is that it ranks poorly against the query
that found the claim. So every hit carries its contests and resolutions whatever
they would have scored.

`knowledge decide --use K1=<why> --reject K2=<why>` closes hits an earlier receipt
left open; it appends a decision record rather than editing the receipt. An
undecided hit FAILs `knowledge decisions` — seeing a hit and saying nothing about
it is the one thing the receipt exists to prevent.

## `lex-1` — deterministic retrieval, because it has to replay

Retrieval is case-folded alphanumeric token overlap between the query (tags +
text) and each object's **text, tags and scope values**, ordered by overlap size
and then by id. No embeddings, no model call, no network, no ranking service.
Provenance fields (study, commit, evidence roots) are deliberately NOT matched: a
query should find an object by what it says, not by naming where it came from.

That is not a claim that lexical search is good retrieval. It is a claim that
retrieval which cannot be replayed cannot be audited. `generation verify` re-runs
the recorded query against the store as it stood at `store_head` (`git show
<head>:knowledge/objects/…`) and compares hit-for-hit and closure-for-closure. Any
difference is a FAIL: **suppressed hit or contest**.

A new algorithm is a NEW `retriever_version`, never an edit to this one:
historical receipts replay under the rules they were taken under. A receipt whose
`store_head` does not resolve in this clone WARNs — offline or foreign origin —
rather than failing, and says so.

## The `knowledge` verify family

| Check | FAILs when |
|---|---|
| `knowledge query` | no receipt on a declaring study; or the receipt is anchored at or after the consult gate record (by sequence, or by git ancestry) |
| `knowledge decisions` | a hit carries no `use`/`reject`, or a decision carries no reason |
| `knowledge replay` | the recorded query at `store_head` does not reproduce the recorded hits and closure (suppressed hit or contest) |
| `knowledge store` | the store chain is broken; an object's bytes do not hash to its name; an id is claimed twice; an event's target or object is missing (a deleted transaction) |
| `knowledge promotions` | this study's promotion does not hash to its recorded source, cites a claim the source lock does not carry, or records a `class`/`strength`/`evidence_roots` the source lock does not — a strengthened copy |

Outcome: `{integrity, outcome: consulted | no-match | unconsulted, hits, used,
rejected}`. Integrity says whether the RECORD is intact; the outcome says what the
consultation got. An honest `no-match` is label-eligible; a suppressed contest is
not.

There is no admission rule: consulting the store is a CONSULT-time obligation,
not a per-action one, so the coupling lives in the verify family rather than in a
refusal at every `klein generation check`.

## Freezing access, and the pinned snapshot

`store_head` is pinned per consultation (owner decision OD-4): a study's
retrieval is forever the store as it stood when it asked, and a later promotion
never rewrites what an earlier study saw. For an evaluation with arms or waves,
freeze the store per wave and record later use prospectively with its exposure
lineage — a successor study that inherits a predecessor's exposure declares it in
its own `generation/manifest.yaml`.

## Seeding an existing repository

`scripts/seed_knowledge_objects.py` turns the typed claim citations already in
`knowledge/**/*.md` into objects. It is **dry-run by default**, opens every
markdown file read-only, skips any cited study whose lock does not verify, copies
class and strength verbatim, deduplicates by evidence roots, and leaves the scope
fields EMPTY — because inventing a scope from a citation is exactly the failure
the store exists to prevent. Curate scope by hand afterwards; a correction is a
new promotion, never an edit.

## What this establishes, and what it does not

- **Establishes:** that a declaring study consulted the store before it committed
  to its question; that it saw every object its typed query reached, with every
  contest attached to each; that it recorded what it did about each one; that
  imported claims carry the class and strength they earned; that the same
  evidence is counted once; that no transaction has been deleted or rewritten.
- **Does not establish:** that the scope tags are honest; that the retrieval
  corpus is adequate (lexical overlap misses what it misses, and the receipt
  records the query, not the field); that a contest is correct; that a resolution
  settled anything; that a claim applies to the new study at all. Applicability,
  semantic contradiction and adjudication stay agent and reviewer judgement.
  Mandatory typed searches prevent empty-query theatre — they do not prove the
  author searched well.
