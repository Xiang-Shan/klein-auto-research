---
name: klein
description: Run Klein Auto Research studies — process-verifiable research for AI for Science on the user's data, public data, a simulator, or a verifier alone, closed with a claims lock, an independent referee verdict, and a teaching artifact. Use for any research study (predict, estimate, test, simulate, replicate, discover, optimize), an experiment loop / autotuning, comparing or exploring a method, auditing data before modeling, studying an unfamiliar method, synthesizing findings, refereeing a study, or building a tutorial — whenever the user wants to research, experiment with, compare, or learn about methods on a question, EVEN IF they don't say "klein".
---

# /klein — study lifecycle router

> `/klein` is the Claude Code packaging of Klein's lifecycle. Everything it routes —
> the reference protocols, profiles, templates and helper scripts below — is plain
> markdown/Python usable with ANY coding agent or by hand; the tool-neutral entry
> point is the repo-root `AGENTS.md`.

Klein runs research **studies** under `studies/NN-slug/` through a fixed lifecycle of
seven stages and four gates. The last three stages are what make it *research*, not
just experiment-running.

```
new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ REFEREE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md    Gate 3     report/
```

**Hard-block rule:** no modeling until CONSULT, DATA, and METHOD are recorded and the
DATA artifact says GO; no `finalize` until REFEREE is recorded. Acknowledgements and
explicit overrides are recorded with `klein gate`; prose in `program.md` alone cannot
unlock a run.

## Stages

`/klein <stage>` routes the lifecycle stages below. The STAGES are protocol routes;
the `klein` CLI verbs (`new gate preflight run-one recover status finalize
noise-floor verify headroom stop predict claims replicate sweep doctor generation`) are the
machine actions each stage uses — the two are mapped here, not identical. Run stages
in lifecycle order for a new study; `status` any time. The reference PROTOCOLS are
the source of truth — the worker agents in `.claude/agents/` are optional
accelerators; a solo session follows the protocols directly.

| Stage | What it does | Protocol | CLI verbs used | Worker agent |
|---|---|---|---|---|
| `new` | Scaffold a study dir, typed by kind / modality / profile | `references/defaults-and-scaffolding.md`, `references/inquiry-model.md` | `klein new`, `klein doctor` | — |
| `consult` | Gate 0: ≤6-question interview (or fast-path); type the inquiry; register predictions with rules | `references/consult-protocol.md` | `klein gate record consult` after the **user ack** | klein-consultant |
| `data` | Gate 1: modality-typed profile → clean-room leakage audit → ranked go/no-go → data_card.md | `references/data-gate-protocol.md`, `references/data-sources.md` | `python -m kleinlib.leakage`; `klein gate record data` (or `gate override data --reason`) | klein-data-auditor |
| `method` | Gate 2: intuition→math→impl→refs → method_card.md (+ the verifier, hashed) | `references/method-gate-protocol.md` | `klein gate record method` | klein-method-scholar |
| `run` | One candidate transaction — or one registered cell — (edit → commit → run → verify → retain evidence) | Hard Rules below; `references/registered-mode.md`; phase starts: `references/phase-ritual.md`; sweeps: `references/sweep-rules.md` | `klein preflight`, then `klein run-one [--tests P#]`; `klein noise-floor --recipe --estimand` at Phase 0; `klein run-one --final-test --dry-run` then `--final-test`; `klein replicate`; `klein sweep register`; `klein recover` after interruption | klein-experimenter / klein-sweeper |
| `synthesize` | Mine trajectory + predictions ledger → 7-section findings + claims.lock | `references/synthesis-protocol.md`, `references/claims-protocol.md` | `klein predict list`, `klein claims init|pin|number|add|verify` | klein-synthesist |
| `referee` | Gate 3: fresh context, different model; verifiers + ten-check rubric → referee_report.md | `references/referee-protocol.md` | `klein verify --numbers --evidence-use`, `klein claims verify`, then `klein gate record referee`; `klein finalize` after | klein-referee |
| `tutorial` | Build self-contained teaching HTML, numbers from the lock | `references/tutorial-spec.md`, `references/profiles/<profile>.md` | — (`.claude/skills/klein/scripts/build_tutorial.py`) | klein-tutor |
| `status` | Summarize results, predictions, evidence use | `.claude/skills/klein/scripts/summarize_results.py` | `klein status`; `klein verify` for any-study validation (writes the receipt); `klein generation verify\|status` on a generation-enabled study (`references/generation-protocol.md`) | — |

War stories behind the guards: `references/war-stories.md`. Schema authority:
`kleinlib/schema.py` — never restate columns anywhere. The five objects and three axes
every study is typed on: `references/inquiry-model.md`.

**Opt-in generation layer (schema 3).** A study may additionally record what it
committed to BEFORE the evidence: `klein generation init` before Gate 0, then one
`klein generation check` before every `run-one`, verified separately by `klein
generation verify` — `references/generation-protocol.md`. A study that does not opt in
is untouched by it, and no core verb, receipt or disposition changes either way.
<!-- WP-01: expertise -->
Declaring `--capability expertise` adds the reproduction obligation: `klein generation
expert lock` freezes `domain_card.md` (pipeline, metrics, doctrine, pitfalls, a
`method_shortlist` that precedes METHOD, and a baseline recipe with numeric targets)
before Gate 0; the baseline runs as an ordinary `run-one` admitted with `--action
baseline`; `klein generation expert bind E0001` adjudicates it, and no challenger run
is admitted until a bind reproduces — repairs are versioned and targets never move
(`references/expert-protocol.md`). Its citations are `klein generation reference
record` entries under `knowledge/references/` — locator, supported statement, source
hash and verification level — because on an enabled study a bare `verified: true` is
insufficient (`references/reference-protocol.md`).
<!-- end WP-01 -->
<!-- WP-02: slates -->
A study that declares the **`slates`** capability additionally records each phase's
hypothesis slate (`klein generation slate lock`, 4–6 authored rows → `<study>#Hn` ids),
admits runs by `--hypothesis`, and scores the driver's own forecasts at phase end
(`klein generation slate score` → `generation/tables/slate_calibration_<phase>.tsv`).
<!-- end WP-02 -->

## Setup

```bash
uv sync --locked             # core deps + dev tools; add --extra gbdt | deep as needed
uv run --locked klein doctor # what this machine can run; fetches nothing
```

Data resolution goes through **source tags** (`references/data-sources.md`): `csv:`,
`parquet:`, `synthetic:<script>`, `bundled:<name>`, `hub:<name>` (the `$DATA_HUB`
seam), `sklearn:<loader>`, `openml:<id>`, `url:<https://…>` — network sources are
pinned by sha256 and refused under `KLEIN_OFFLINE=1`; every resolution prints a
`data source:` provenance line. Partitions come from the contract
(`kleinlib.data.contract_split` / `load_partition`), never from a seed in a script.

Smoke-testing a candidate before its run: `KLEIN_SMOKE=1 python <entrypoint>` is the
ONE sanctioned off-loop execution — it prints the canonical block but writes no
sidecars or snapshots and is not evidence. Never fake `KLEIN_EXPERIMENT_ID` /
`KLEIN_TRACK` by hand; `run-one` force-clears `KLEIN_SMOKE` in the child.

Before every experiment, run the machine preflight (exact branch, gates,
acknowledgements, placeholders, artifact hashes, prepared-data / split / verifier
fingerprints, ledger integrity, headroom, stop rule, and a clean mutable surface):

```bash
uv run --locked klein preflight --study studies/NN-slug
```

The exact branch must be `experiments/<study-id>`. On a finished study merged back to
`main`, that check fails by design. To read a study's machine state and generate a
metric summary:

```bash
uv run --locked klein status --study studies/NN-slug
uv run --locked python .claude/skills/klein/scripts/summarize_results.py \
    studies/NN-slug/results.tsv --track <track>  # omit for a one-track study
# → results_summary.md (frontier, aux panels, phase telemetry) + progress.svg
```

- **Studies convention:** one study = one directory and one coherent research goal.
  Distinct tasks or metrics are separate tracks, each with its own frontier or its
  own registered measurement program (`tracks.<id>.mode: frontier | registered`).
- **Branch rule:** studies run on `experiments/<study-slug>`, NEVER on `main`. Branch
  before the first experiment; merge at study end.

## Hard Rules

Violating these has caused real data-loss and workflow failures — the specific
incidents live in `references/war-stories.md`, and the lessons of the studies that
paid for them are promoted in `knowledge/research-discipline.md`. Do not renegotiate
them mid-study.

Three layers, one division of labor: **the loop is yours** (think → edit the mutable
surface with one falsifiable idea → run → reflect → repeat); **`run-one` is only the
crash boundary** (commit candidate → one bounded run → the declared verifier →
honest disposition by YOUR declared contract → adjudicate the named predictions →
restore); **the state files are receipts** the CLI generates and commits itself —
each verb committing only the files it wrote (verify, claims, predict, replicate,
sweep, stop, headroom), while gate records, `run-one` and `finalize` file the study
artifacts they hash. If the tree is dirty at run time it is your edit, and it stays
yours: the verb names it on stdout instead of taking it. The rules below defend that
division.

### 1. Commit every candidate before execution; derive the ledger afterward

The mutable surface is the set of files `entrypoint.mutable` names (`train.py` by
default for a `predict` study; `analyze.py`, `simulate.py`, `search.py` by kind) —
one idea per candidate. `klein run-one` commits that exact candidate before running
it, even when it later becomes a discard or crash. It then writes the immutable
`runs/E####/manifest.json`, appends the self-verifying event, restores the surface
after a non-keep (always, on a registered track), derives `results.tsv`, and commits
evidence transactionally. Never hand-edit the ledger. If interrupted, run:

```bash
uv run --locked klein recover --study studies/NN-slug
```

`keep` means a track-specific improvement of at least `minimum_delta` with every
configured guardrail satisfied; `measured` is a registered cell; `discard` is valid
scientific evidence; `crash` has an `NA` primary metric. Guardrails read the PRINTED
metric block (the verifier's block when one is declared): `wall_seconds` prints
automatically; any other declared key must reach stdout via
`evaluate*(..., extra={...})` (preflight warns when a declared key is neither
auto-printed nor named in the study's Python sources). Every disposition keeps a
resolvable candidate commit. run-one refuses an unchanged surface before any id or
commit exists; pass `--allow-rerun` for an intentional identical replication, or
`--tests P#` on a registered track — sealed final tests and `--command` overrides
are exempt.

### 2. One foreground run, with a real timeout and exit status

```bash
uv run --locked klein run-one --study studies/NN-slug --track <track> \
  --description "<one falsifiable hypothesis>" [--tests P3,P4]
```

The workflow runs one unbuffered subprocess, streams and stores its output, enforces
`max_run_seconds` separately from phase budget and experiment count, terminates the
process group on timeout, runs the declared verifier as a second subprocess, and
records crashes. Never use a `command | tee` pipeline. A printed `split_fingerprint:`
that differs from the one frozen at the DATA gate is a crash by design.

### 3. Gates and acknowledgements are machine state

```bash
uv run --locked klein gate record consult --study studies/NN-slug --acknowledged-by <actor>
uv run --locked klein gate record data    --study studies/NN-slug --acknowledged-by <actor>
uv run --locked klein gate record method  --study studies/NN-slug --acknowledged-by <actor>
uv run --locked klein gate record referee --study studies/NN-slug --acknowledged-by <actor>
```

An override must name the gate, actor, and non-empty reason using `klein gate
override`; it is timestamped in state/events. Silent fast paths are invalid. The
referee gate cannot be recorded on a `Verdict: FAIL`.

### 4. Development is adaptive; final test is sealed — and rehearsed first

Training and adaptive selection use only train/development partitions. A track gets
one confirmation access, and the rehearsal is mandatory before it:

```bash
uv run --locked klein run-one --study studies/NN-slug --track <track> --final-test --dry-run
uv run --locked klein run-one --study studies/NN-slug --track <track> --final-test \
  --description "sealed confirmation of the selected candidate"
```

The dry-run executes the sealed entrypoint on development data and spends nothing;
study 09 lost its only seal to a crash that ran before any data was read. The
final-test result is evidence, not another adaptive frontier candidate. What "sealed"
means per kind, and which records `confirmed` needs (`confirmation.require ⊆
{sealed, replicate, verify}`), is in `references/inquiry-model.md`;
`klein replicate E####` adds the reproduction record. Close the study with
`klein finalize` after the referee gate: findings without the required evidence are
labelled exploratory; small deltas without uncertainty are not described as real or
decisive — finalize warns on that language.

### 5. Keep until the user stops — with the map open

Default stop rule: keep experimenting until the user says stop, a phase
`max_experiments` is hit, or a registered `stop:` rule fires. Do not unilaterally
declare the batch done on a plateau. RE-READ `playbook.md` before choosing every
candidate, and refresh it at every phase boundary (or every 5 experiments); start each
phase with the slate ritual (`references/phase-ritual.md` — cells, on a registered
track). Summarize and STOP for ack at every phase boundary:

```bash
uv run --locked klein gate record phase --study studies/NN-slug \
  --phase <current-phase> --acknowledged-by <actor>
```

### 6. Detection-limit law — audit headroom before spending challengers

`h = (incumbent − metric.bound.ideal) / minimum_delta`. If `h < 1`, the tournament is
decided before it runs. Declare `metric.bound.ideal` so klein computes and discloses
`h` at preflight/verify and refuses development runs on an infeasible frontier until
it is acknowledged; a `stop:` rule works the same way:

```bash
uv run --locked klein headroom ack --study studies/NN-slug --track <track> \
  --acknowledged-by <actor> --note "re-scope: ... | run-anyway: <door-closed sentence>"
uv run --locked klein stop ack --study studies/NN-slug --track <track> --acknowledged-by <actor> --note "..."
```

Name the floor's estimand (`klein noise-floor --recipe … --estimand …`); never read
`h >= 1` as "a keep is plausible" (study 08: h = 1.015, twenty-one challengers, zero
keeps). An `exact` metric declares its resolution instead of a floor.

### 7. Predictions are adjudicated by the notary, never by prose

Every registered prediction carries an arithmetic rule on a printed key. `run-one
--tests P#` writes its verdict (`supported | refuted | inconclusive`) into the
manifest, the state and the event chain; `klein predict adjudicate` records sidecar
evidence with its hash. A refuted prediction gets a dated `Decision:` line in
`program.md` — `klein verify` fails without it. `finalize` refuses open predictions
unless `--allow-open-predictions --reason` is recorded.

### 8. Claims are locked; numbers have homes; errata re-scope

`findings.md` is what the study says; `claims.lock` is what a stranger can check
(`references/claims-protocol.md`). `klein claims` produces it; the seven-check law
verifies it; it is append-only across its git history. Every numeral in findings,
lock and tutorial is a copy of a pinned value (`klein verify --numbers`). An erratum
tags claims and never deletes them.

### 9. The referee comes before finalize, and is not you

REFEREE runs in a fresh context on a different model or tool than the experimenter
(`references/referee-protocol.md`): findings before program, the mechanical verifiers,
the ten checks, a machine-read verdict. A synthesist never referees its own findings;
an orchestrator that ran the loop hands the stage to a subagent. `finalize` requires
the recorded gate (`--no-referee --reason` is recorded and labels the study
`unrefereed`).

### 10. The verifier is never in the mutable surface

When a track declares `verifier:` (required for `optimize`, recommended for any
checkpoint-scored study), the checker script is hashed at the METHOD gate, never
edited afterwards, run by the notary in a fresh process, and its number decides the
disposition; the searcher's own claim is recorded beside it and a disagreement is a
crash. The checker is never the searcher.

### Schema-2 and v1 compatibility

`schema_version: 2` studies (03, 05–09) keep verifying under schema-2 rules forever —
none of the schema-3 checks are enforced on them, their lock-schema-1 claims locks
verify as numbers ledgers, and nothing is rewritten. A missing `schema_version` is v1:
readable at tag `v1.3.0`, where the original quickstart and the v1 ledger adapter
remain. `docs/migration-schema2-to-3.md` has the field diff.

## Installing in another repo

Klein is self-contained under `.claude/skills/klein/`:

```bash
cp -r .claude/skills/klein /path/to/your-repo/.claude/skills/
```

The engine is a dependency, not an option: every helper (`summarize_results.py`,
`build_tutorial.py`, `make_figures.py`, the `klein` CLI) imports `kleinlib` — the
schema, registries and templates live there and nowhere else, so nothing can drift.
In the foreign repo, add the engine (see `assets/pyproject-study-template.toml`), then
`uv sync --locked`:

```bash
uv add "klein-auto-research @ git+https://github.com/Xiang-Shan/klein-auto-research@v2.0.0"  # pin a tag — and record the commit
```

Pin by tag *and* record the commit in your study's lock (`klein_commit`): since 2.0.0
the schema-3 contract, the `klein` CLI surface, and the ledger formats are stable —
breaking changes mean a major version. `klein new` then scaffolds byte-identical
schema-3 studies anywhere; the engine never reads this skill directory, so a
repo-local `profile_doc` works without forking Klein.

## Limitations

Klein cannot make a model reason better. It makes reasoning failures detectable and
forces the missing behaviours — recording evidence, revising on refutation,
converging independent tests — and it leaves a record a stranger can audit with no
model in the loop. Know the edges:

- **Evaluator shapes**: binary classification (`evaluate`), point/rate regression
  (`evaluate_regression` — RMSE/MAE/R², Poisson/Gamma/Tweedie deviance under the
  exposure-weighted-rate convention), scalar/simulation (`evaluate_scalar`), and the
  registered-cell shapes `evaluate_estimate`, `evaluate_test`, `evaluate_table` — all
  printing the same canonical block. Multiclass, survival, and ranking are extension
  points, deliberately not shipped until a worked study proves them;
  `evaluate_with_inner_cv` is binary-only (group-aware).
- **One primary metric per track.** Each track owns its direction, minimum delta,
  guardrails, bound, exactness, verifier. Everything else remains auxiliary or a
  pinned table; SYNTHESIZE weighs tradeoffs without manufacturing a global frontier.
- **Single machine, one experiment at a time** (blocking foreground). No parallel
  dispatch, no scheduler: a cluster run is a blocking submit-and-wait entrypoint.
- **The generation layer records and scores; it never generates.** The opt-in
  layer (`references/generation-protocol.md`) hashes admission receipts, checks their
  order against local witnesses, and computes arithmetic on rows the driver wrote. It
  never proposes, ranks, selects, schedules or retries — and local ordering is not
  independently established chronology. A slate's 1–3 axis scores are validated and
  copied verbatim; nothing sorts on them, and a Brier score over a four-row slate
  proves the arithmetic, not calibration in general.
- **No learned meta-controller.** The agent reasons conversationally; `playbook.md`
  is the within-study memory and `knowledge/` the cross-study memory — priors promote
  through claim-cited findings, not learned weights.
- **The referee is independent by mechanism, not by magic.** A fresh session of the
  same model is the lowest rung of the ladder and is recorded as such.
- **The measured noise floor bounds honesty, not power.** A `minimum_delta` from a
  floor recipe stops within-noise keeps; it does not create statistical power.
- **The lock verifies that numbers have homes, not that the homes were the right
  places to look.** That is the referee's job, and the next study's.
