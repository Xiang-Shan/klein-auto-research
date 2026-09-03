# Migrating from schema 2 to schema 3

**The key sentence: none of the schema-3 checks are enforced on schema-2 studies.**
A study whose `study.yaml` says `schema_version: 2` keeps verifying under the rules it
was run under, forever; its ledgers are never rewritten; its `claims.lock` (lock
schema 1) verifies as a numbers ledger. Schema 3 is for new studies. Do not migrate a
closed study — start a new one and cite the old one's claims.

## What schema 3 adds to the contract

| Field | Meaning | Required? |
|---|---|---|
| `schema_version: 3` | selects the schema-3 rule set | yes |
| `kind` | `predict | estimate | test | simulate | replicate | discover | optimize`; `tracks.<id>.kind` overrides per track | yes |
| `modality` (under `data`) | `tabular | timeseries | image | sequence | graph | text | simulation | none`; selects the data-card template | yes |
| `profile` | `generic | ml-research | math | insurance` | yes, unless `profile_doc` names a repo-relative `.md` profile instead (there is no default: the scaffold writes a placeholder and the CONSULT gate refuses one) |
| `audience` | who reads this study, in a sentence | scaffolded as a placeholder, so in practice yes; a present value must be non-empty |
| `entrypoint {command[], mutable[]}` | the run command and the files the loop may change; study-relative, no `..` | yes (scaffolded) |
| `tracks.<id>.mode` | `frontier` (default) or `registered` | no |
| `tracks.<id>.verifier {command[], tolerance, artifact_key}` | the checker script outside `mutable[]`; hashed at METHOD | required for `optimize` |
| `tracks.<id>.metric.exactness` | `stochastic` (default) or `exact` (+ `exactness_note`; waives the floor) | no |
| `tracks.<id>.metric.incumbent_external {value, source, verified_on}` | the literature value that seeds the frontier | no |
| `tracks.<id>.metric.fit_noise` | the k-seed spread, recorded separately from the floor so it can never be pasted as a bar; its `estimand` may only be `fit-noise` (a bar estimand belongs under `noise_floor`) | no |
| `predictions[]` | `{id: P#, track?, statement, rule | manual: true, inconclusive_if?}` and nothing else; exactly one of `rule` or `manual: true`; `predictions_to_falsify` is normalized to manual predictions (both present = error) | no to the contract; CONSULT refuses a registered track with none (`references/registered-mode.md`) |
| `confirmation.require` | subset of `{sealed, replicate, verify}`; defaults by kind | no |
| `stop {max_consecutive_discards, scope}` | the stop rule (`scope ∈ {track, study, phase}`, default `track`), enforced like headroom with `klein stop ack` | no |
| `materiality {currency, unit, threshold, priced_by, priced_on, basis, applies_to}` | a priced consequence; never inferred from resolution | no |
| `data.source` | a source tag (`references/data-sources.md`); `data.sha256` mandatory for `openml:` and `url:` | yes |

## What schema 3 adds to the lifecycle

- **REFEREE (Gate 3)** between SYNTHESIZE and TUTORIAL; `klein finalize` runs after
  it and requires it (`--no-referee --reason` is recorded and labels the study
  `unrefereed`).
- **Predictions are adjudicated by the notary** (`klein run-one --tests P#`,
  `klein predict adjudicate`); `finalize` refuses open predictions without a reason.
- **Registered mode** and the `measured` disposition.
- **Contract-driven splits**: evaluators print `split_fingerprint:`; a mismatch with
  the DATA-gate fingerprint is a crash. **The sealed dry-run** rehearses a sealed run.
- **`claims.lock` lock schema 2** produced by `klein claims`; **`verify_receipt.json`**
  written and self-committed by `klein verify` (with `--numbers`, `--claims` and
  `--evidence-use` on by default on schema 3), carrying `evidence_use_rate` and the
  evidence-use law's three numbers.
- **`klein replicate`**, **`klein sweep register`**, **`klein doctor`**,
  **`klein predict list|adjudicate`**, **`klein claims init|pin|number|add|erratum|verify`**,
  **`klein stop ack`**, and `klein noise-floor --recipe --estimand`.
- **The schema-3 floor bar**: `minimum_delta >= max(2*std, range/2)` on a track that
  declares a measured `noise_floor` (schema 2 keeps its `>= std` bar).

## Reading the old studies

- Schema-2 studies (03, 05–09): `klein verify --study <dir>` reports under schema-2
  rules; their locks under lock schema 1; the evidence-use and numbers checks run
  advisory only.
- Schema-1 (v1) studies: readable at tag `v1.3.0` — the last tree that carried the v1
  ledger adapter and the original quickstart. Klein 2.0 removes both.
- Hub-era data sources (`hub:`): reproduce elsewhere with an `openml:` or `url:` tag
  and a pin, recorded as a data-gate re-record with a reason.

## Re-opening a schema-2 study

Don't. Copy what you need into a new schema-3 study whose predictions cite the old
claims (`(supports 08-iris-rematch#C17)`); `klein claims init --from-legacy` can carry
a schema-1 lock's numbers across as the new lock's starting `numbers` map. `load_state`
refuses a schema-3 contract over a schema-2 state file and names this document.
