# Claims protocol — the lock, the law, the numbers

`findings.md` is what a study says. `claims.lock` is what a stranger can check. Studies
07, 08 and 09 hand-built the lock as JSON and a one-sentence "law" because a talk deck
needed numbers that could be traced without trusting the author; Klein 2.0 makes the
engine produce and verify it. The markdown convention stays the human surface — claim
ids in `findings.md` are still `**[Cn]**` lines — and the lock is the machine surface
underneath.

Role: the synthesist authors the lock at SYNTHESIZE; the referee verifies it; `klein
finalize` refuses a strength the evidence does not support; every downstream
deliverable reads it. Any agent or human can follow this protocol directly.

## The lock (shape) — lock schema 2

Studies 07, 08 and 09 wrote **lock schema 1**: a numbers ledger — every headline
number keyed by an alias, with its value, the artifact it lives in, and the claim id it
belongs to. Schema 2 keeps that map under `numbers` and adds a real `claims` map, so a
claim carries its class, strength, evidence and errata and a number carries its home.

```json
{
  "lock_schema": 2,
  "study_id": "10-hubble-1929-replication",
  "git_head": "<repo commit the lock describes>",
  "klein_commit": "<engine commit that produced it>",
  "klein_version": "2.0.0",
  "law": "Every number in findings.md, this lock and report/index.html is a copy of a value in a pinned artifact; every claim cites evidence that resolves; claims and numbers are appended or erratum-tagged, never removed.",
  "artifacts": {
    "results": {"path": "results.tsv",        "sha256": "…"},
    "boot_k":  {"path": "tables/bootstrap_k.tsv", "sha256": "…"}
  },
  "numbers": {
    "k_free_intercept": {"value": 454.16, "art": "boot_k", "claim": "C2", "precision": 2,
                         "note": "OLS with free intercept, 24 objects"}
  },
  "claims": {
    "C2": {
      "class": "empirical-description",
      "strength": "confirmed",
      "claim": "A free-intercept fit of Hubble's 24 objects gives K = 454.16 km/s/Mpc, not 465",
      "numbers": ["k_free_intercept"],
      "evidence": ["E0003", "verify:E0003@2026-09-05T10:12:00Z"],
      "errata": []
    }
  },
  "errata": {
    "E1": {"filed": "2026-09-01", "claims": ["C3"], "note": "…"}
  }
}
```

Field rules: `class` is one of the five below; `strength ∈ {exploratory, confirmed,
refuted}`; `claim` is the sentence as it appears in `findings.md`; `numbers[]` lists
the aliases the sentence quotes (a sentence with a numeral and no alias fails);
`evidence[]` uses the grammar of `inquiry-model.md`; a `known-dgp-teaching` claim also
carries `"scope": "in-silico"` and names its DGP. In `numbers`, `value` is a number
or a short list, `art` an alias in `artifacts`, `precision` the decimals the numbers
law matches at (default 3), `claim` the id it belongs to (or `"floor"` /
`"contract"` for contract quantities). Paths are study-relative and POSIX, never
absolute.

**Lock schema 1 (legacy, studies 07–09)** has no `lock_schema` key: its `claims` map
is what schema 2 calls `numbers` (`art` or `artifact` both occur, entries may carry
free-form notes, paths are repo-relative). `klein claims verify` recognises it and
applies the schema-1 rules — artifact hashes, numbers found in their artifacts, claim
ids present in findings, append-only history, `git_head` resolvable — and never
rewrites it; `klein claims init --from-legacy` migrates a copy into schema 2 for a
study that is being re-opened.

## The five classes and their ceilings

| class | What it asserts | Strength ceiling |
|---|---|---|
| `empirical-description` | a measured fact about the data or the result | `confirmed` (needs the evidence kinds in `confirmation.require`) |
| `procedural-verdict` | what the procedure decided — a frontier closed, a prediction refuted, a seal spent | `confirmed` when every cited id resolves in the ledger |
| `mechanism-interpretation` | why the result happened | `exploratory` — an interpretation is confirmed only by a later study that tests it |
| `known-dgp-teaching` | how the method behaves under the declared truth | `confirmed`, scoped `in-silico`; never a claim about real data |
| `research-discipline` | a lesson about the process itself | `exploratory`; it promotes into `knowledge/` with a typed citation |

`refuted` is never written at first authoring; it is set only by an erratum or by a
later study's `(refutes <study>#Cn)` record, and the claim stays in the lock.

## The claims law — the seven checks `klein claims verify` runs

1. **Shape.** Every field above is present and typed; every class and strength is
   from the lists; every `art` alias exists.
2. **Artifacts.** Every pinned file exists and its bytes hash to the recorded sha256.
3. **Presence.** Every claim id appears in `findings.md` as `**[Cn]**`, every
   `**[Cn]**` in `findings.md` appears in the lock, and every alias a claim lists in
   `numbers[]` exists.
4. **Evidence.** Every evidence id resolves (`E####` → a manifest; `sweep:` → a
   registered sidecar; `rep:`/`verify:` → a replication record; `ref:` → an entry of
   `references.yaml`; `art:` → a pinned alias). An unverified reference behind a
   `confirmed` claim is a warning; behind nothing else it is fine.
5. **Numbers.** Every `numbers` entry's `value` is found in its `art` at `precision`
   decimals or exactly (text artifacts: TSV, CSV, JSON, YAML, Markdown); a binary
   artifact yields a warning, not a pass; a claim sentence whose numerals are not all
   covered by its `numbers[]` aliases fails.
6. **Append-only.** Across `git log --follow claims.lock`, no claim or number is
   removed and no claim's `class` or `claim`, and no number's `value` or `art`,
   changes; `evidence`, `numbers`, `errata` and notes may only grow; `strength`
   changes only in a commit that also files an erratum.
7. **Ancestry.** `git_head` is an ancestor of `HEAD`; `klein_commit` resolves when the
   engine repository is at hand (advisory otherwise).

`--strict` turns every warning into a failure. `klein finalize` additionally refuses a
`confirmed` strength whose track lacks the evidence kinds in `confirmation.require`.

## The numbers law (stated once, here)

Every numeral in `findings.md`, `claims.lock` and `report/index.html` is a copy of a
value that exists in a pinned artifact: `results.tsv`, `aux_metrics.tsv`, a run
manifest, a registered sweep sidecar, `study.yaml`, `study_state.json`, or an artifact
pinned by alias. Exempt: years and dates; identifiers (`E####`, `P#`, `C#`, `RQ#`);
section, figure and table numbering; small counts that name their source
(`n = 24 (Table 1)`, `k = 5 seeds`); numerals inside code blocks and typeset formulas.
A numeral that needs an exemption not listed here is marked on its line with
`<!-- klein:numbers-ok: <reason> -->`, and the referee reads every such marker.
`klein verify --numbers` mechanizes the scan (enforcing on schema 3, advisory on
schema 2, always advisory on the tutorial).

The law exists because it catches operators: study 09's erratum E1 was found by the
tutorial's unsourced-numeral scan, not by anyone re-reading the code.

## Verbs

```bash
uv run --locked klein claims init    --study studies/NN-slug [--from-legacy]   # skeleton: claims from findings' **[Cn]** lines (class null), numbers empty
uv run --locked klein claims pin     --study studies/NN-slug results results.tsv
uv run --locked klein claims number  --study studies/NN-slug k_free_intercept --value 454.16 --art boot_k --claim C2 [--precision 2] [--note "…"]
uv run --locked klein claims add     --study studies/NN-slug C2 --class empirical-description \
    --strength exploratory --claim "…" --numbers k_free_intercept --evidence E0003
uv run --locked klein claims erratum --study studies/NN-slug E2 --claims C3,C7 \
    --note "…" [--strength exploratory]                                 # downgrade only
uv run --locked klein claims verify  --study studies/NN-slug [--numbers] [--strict]
```

Every verb rewrites `claims.lock` canonically and self-commits it (the lock is a
receipt, never hand-edited after `init`); `erratum` also appends the event
`erratum_filed`. A lock with a `null` class fails verification, so `init` cannot be
mistaken for a finished lock.

## Errata re-scope, never delete

An erratum names the claims it touches and what is now known; the claims keep their
ids, their original text and their original numbers, and gain the tag. A reader of the
lock sees both what was claimed and what was later learned. Nothing is ever removed
from a lock, a ledger, or a findings file — the append-only check makes the promise
mechanical.

## Downstream deliverables read the lock, nothing else

A talk deck, a README gallery row, a tutorial's headline numbers, a knowledge-base
line: each is built from `claims.lock` — the alias, the value, the evidence — not from
memory and not from `findings.md` prose. The precedent is the CAS deck of 2026-08-28,
whose every number came from a small script over study 09's lock; a deck whose numbers
cannot be regenerated from a lock is a deck the author cannot sign.

## Where the lock sits in the lifecycle

SYNTHESIZE writes `findings.md` and the lock together (the lock is authored AFTER the
sealed evidence exists, never before). REFEREE runs `klein claims verify` in a fresh
context. `klein finalize` reconciles strengths with the evidence. TUTORIAL and every
later deliverable read the lock.
