# Reference records — what a citation actually rests on

`references.yaml` lets a row say `verified: true`. Verified by whom, against
what, and how closely? Without an answer, that flag is the most quietly
corrosive artifact in a study: it looks like diligence, it costs nothing to
write, and a citation copied out of another paper's bibliography carries it just
as easily as one read at the source. **Citation laundering** is not fabrication —
it is a real work, cited for a statement nobody checked it makes.

A reference RECORD answers the question in a form a stranger can audit. It is
part of the opt-in generation layer (`references/generation-protocol.md`) and
applies to a study whose `generation/manifest.yaml` declares `expertise`.

```bash
uv run --locked klein generation reference record --study studies/NN-slug \
    --id collins2010 --title "Tacit and Explicit Knowledge" --year 2010 \
    --authors "Collins, H." --identifier isbn:9780226113807 \
    --locator isbn:9780226113807 \
    --statement "reproducing a recipe is not the same as holding the tacit knowledge behind it" \
    --basis bibliography --checker "the method scholar"
```

## The record

`knowledge/references/<id>.json`, **repo-level and tracked** — a reference is a
fact about the literature, not about one study, so two studies citing one paper
cite one record. Ids match `[a-z0-9][a-z0-9._-]*`.

```json
{"schema": "klein-generation/1", "kind": "reference", "id": "collins2010",
 "bibliographic_metadata": {"title": "…", "authors": ["…"], "year": 2010,
                            "venue": "…", "identifier": "isbn:…"},
 "locator": "doi|arxiv|url|isbn|path",
 "retrieved_at": "…UTC, informational…",
 "source_blob_sha256": "…|null", "blob_retained": true,
 "supported_statement": "the ONE statement this record is cited for",
 "checker": "…testimony…",
 "verification_basis": "read-at-source|bibliography|abstract-only|hash-only",
 "recorded_by": {"actor": …, "tool": …, "model": …, "session": …}}
```

`retrieved_at` is informational; nothing decides anything from it.
`checker` and `recorded_by` are **testimony** — self-reported strings, never
authenticated.

## Verification levels, and the rule each one owes

Ordered strongest to weakest. The order is the point: a study may cite a work it
only read the abstract of, **as long as it says so**.

| Basis | Means | Consistency rule (refused at write, FAILs at verify) |
|---|---|---|
| `read-at-source` | the source itself was opened and read | requires `source_blob_sha256` **and** `blob_retained: true` |
| `bibliography` | metadata confirmed against a catalogue or another work's bibliography | requires title + year + identifier |
| `abstract-only` | the abstract or landing page was read, not the work | requires an identifier |
| `hash-only` | bytes were hashed; the content is not attested here | requires `source_blob_sha256` |

The pairing of `read-at-source` with `blob_retained: false` is the one that
matters: if the bytes are gone, nobody can ever check what was read, so the
honest record is `hash-only`. The tool refuses the combination rather than
letting the study carry a claim it cannot back.

## Retention: hashes in git, bytes with the driver

**Klein copies nothing.** `--blob <path>` hashes a file the driver points at and
the file stays exactly where it was — outside the study, outside the repo, or in
a git-ignored directory of the driver's choosing. The hash goes into git; the PDF
does not. That keeps the store licence-safe and small, and it is the reason
`hash-only` exists as a basis at all.

`blob_retained` is the driver's statement about whether they still hold those
bytes. It is not verified and cannot be: byte integrity is not custody
(`references/generation-protocol.md`, "what this does NOT establish").

## Write-once, and how a correction works

A record is written once. Re-recording the same id with different content is
refused, and an edit made by hand afterwards FAILs `expert references` — the
record that was cited when a claim was made must stay exactly what it was.

**A correction is a NEW id whose `supersedes` names the old one.** The superseded
record stays in the store and stays readable; a reader who follows an old claim's
citation finds what the claim was actually resting on, and then finds what
replaced it.

## Mirroring into `references.yaml`

The METHOD gate still writes `references.yaml` and the claims law still resolves
`ref:<key>` against it (`references/method-gate-protocol.md` §5,
`references/claims-protocol.md`). On a generation-enabled study each verified row
additionally carries the record:

```yaml
references:
  collins2010:
    title: "Tacit and Explicit Knowledge"
    url: "https://press.uchicago.edu/…"
    verified: true
    verified_by: "klein-method-scholar"
    record_id: collins2010
    verification_level: bibliography
```

> **A bare `verified: true` is insufficient for a generation-enabled study.**
> A row that says `verified: true` with no resolvable `record_id` FAILs
> `expert references`.

`refs_verified: true` in the method card's frontmatter therefore means something
stronger on an enabled study: every row is verified **and** every row has a
record.

## Overclaim is a referee obligation

`supported_statement` is the one thing in the record that no hash can check: it
is a claim that the work at that locator supports that statement. A record can be
perfectly consistent, hashed, retained, `read-at-source` — and cited for
something the paper does not say.

That is the referee's job, not the engine's
(`references/referee-protocol.md` check 8): read the `supported_statement`
against what the locator actually contains, and treat a stretch as an overclaim
finding. The machine can only guarantee that the statement was written down
**before** the evidence was gathered, and that nobody edited it afterwards.

## What this establishes, and what it does not

- **Establishes:** that each cited work was named, located, and assigned a
  declared level of checking before it was leaned on; that the level is
  internally consistent; that the record has not changed since.
- **Does not establish:** that the source says what the record claims it says;
  that the checker read anything; that the retained bytes still exist; that the
  work is the right work to cite.
