---
name: klein
description: Run Klein Auto Research studies — disciplined, visualization-first ML research on the user's (or synthetic) data, closed with insights and a teaching artifact. Use for a research study, an experiment loop / autotuning, exploring or comparing a model or method (GLM to gradient boosting to frontier deep-tabular), auditing/quality-gating data before modeling, studying an unfamiliar or frontier method, synthesizing findings from a run, or building an ML tutorial — whenever the user wants to research, experiment with, compare, or learn about models on a dataset, EVEN IF they don't say "klein".
---

# /klein — study lifecycle router

> `/klein` is the Claude Code packaging of Klein's lifecycle. Everything it routes —
> the reference protocols and helper scripts below — is plain markdown/Python usable
> with ANY coding agent or by hand; the tool-neutral entry point is the repo-root
> `AGENTS.md`.

Klein runs research **studies** under `studies/NN-slug/` through a fixed lifecycle. The
last two stages are what make it *research*, not just experiment-running.

```
new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ hard-block lifts here ┘   findings   report/
```

**Hard-block rule:** no modeling until CONSULT, DATA, and METHOD are recorded and the
DATA artifact says GO. Schema-v2 acknowledgements and explicit overrides are recorded
with `klein gate`; prose in `program.md` alone cannot unlock a v2 run.

## Stages

`/klein <stage>` routes the lifecycle stages below. The STAGES are protocol routes;
the `klein` CLI verbs (`new gate preflight run-one recover status finalize noise-floor verify`)
are the machine actions each stage uses — the two are mapped here, not identical.
Run stages in lifecycle order for a new study; `status` any time. The reference
PROTOCOLS are the source of truth — the worker agents in `.claude/agents/` are
optional accelerators; a solo session follows the protocols directly.

| Stage | What it does | Protocol | CLI verbs used | Worker agent |
|---|---|---|---|---|
| `new` | Scaffold a study dir | `references/defaults-and-scaffolding.md` | `klein new` | — |
| `consult` | Gate 0: ≤6-question interview (or fast-path) | `references/consult-protocol.md` | `klein gate record consult` after the **user ack** | klein-consultant |
| `data` | Gate 1: profile → clean-room leakage audit → ranked go/no-go → data_card.md | `references/data-gate-protocol.md` | `python -m kleinlib.leakage`; `klein gate record data` (or `gate override data --reason`) | klein-data-auditor |
| `method` | Gate 2: intuition→math→impl→refs → method_card.md | `references/method-gate-protocol.md` | `klein gate record method` | klein-method-scholar |
| `run` | One candidate transaction (edit → commit → run → retain evidence) | Hard Rules below; phase starts: `references/phase-ritual.md`; sweeps: `references/sweep-rules.md` | `klein preflight`, then `klein run-one` (each candidate); `klein noise-floor` at Phase 0; `klein recover` after interruption | klein-experimenter / klein-sweeper |
| `synthesize` | Mine trajectory → 7-section findings; close the study | `references/synthesis-protocol.md` | `klein finalize` (labels exploratory/confirmed) | klein-synthesist |
| `tutorial` | Build self-contained teaching HTML | `references/tutorial-spec.md` | — (`.claude/skills/klein/scripts/build_tutorial.py`) | klein-tutor |
| `status` | Summarize results + phase telemetry | `.claude/skills/klein/scripts/summarize_results.py` | `klein status`; `klein verify` for any-study validation | — |

War stories behind the guards: `references/war-stories.md`. Schema authority:
`kleinlib/schema.py` — never restate columns anywhere.

## Setup

```bash
uv sync --locked             # core deps + dev tools; add --extra gbdt | deep as needed
uv run --locked python -c "import kleinlib"
```

Data resolution: `kleinlib.data.load_data_hub(name)` tries the `$DATA_HUB` env var
(an external data-hub repo) and then a repo-bundled `datasets/<name>/` copy, printing
a `data source:` provenance line either way; plain local files go through
`kleinlib.data.load_prepared` (`csv:<path>` sources). Study 00's `prepare.py --sample`
uses a committed 2k fixture for fast offline smoke runs.

Smoke-testing a candidate before its run: `KLEIN_SMOKE=1 python train.py` is the ONE
sanctioned off-loop execution — it prints the canonical block but writes no sidecars
or snapshots and is not evidence. Never fake `KLEIN_EXPERIMENT_ID`/`KLEIN_TRACK` by
hand; `run-one` force-clears `KLEIN_SMOKE` in the child, so an exported smoke flag
can never suppress real evidence writes.

Before every schema-v2 experiment, run the machine preflight (exact branch, gates,
acknowledgements, placeholders, artifact hashes, prepared-data/split fingerprints,
ledger integrity, and clean mutable surface):

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

The primary metric direction always comes from `study.yaml`; the summarizer refuses
to guess. `--goal` is only a warned compatibility override for a v1 study whose
contract lacks a direction.

- **Studies convention:** one study = one directory and one coherent research goal.
  Distinct tasks or metrics are separate v2 tracks, each with its own frontier.
  Scaffold with `klein new` (see defaults-and-scaffolding.md).
- **Branch rule:** studies run on `experiments/<study-slug>`, NEVER on `main`. Branch
  before the first experiment; merge at study end.

## Hard Rules

Violating these has caused real data-loss and workflow failures — the specific
incidents live in `references/war-stories.md`, and the 215-experiment ancestor
campaign they come from ships its distilled findings in `knowledge/`. Do not
renegotiate them mid-study.

Three layers, one division of labor: **the loop is yours** (think → edit
`train.py` with one falsifiable idea → run → reflect → repeat); **`run-one` is
only the crash boundary** (commit candidate → one bounded run → honest
disposition by YOUR declared contract → restore on non-keep); **the state files
are receipts** the CLI generates and commits itself. The rules below defend that
division.

### 1. Commit every candidate before execution; derive the ledger afterward

The mutable surface is `train.py` only (normally a 5–15 line diff). `klein run-one`
commits that exact candidate before running it, even when it later becomes a discard
or crash. It then writes the immutable `runs/E####/manifest.json`, appends the
self-verifying event, restores `train.py` to the pre-candidate base commit after a
non-keep, derives `results.tsv`, and
commits evidence transactionally. Never hand-edit the v2 ledger. If interrupted, run:

```bash
uv run --locked klein recover --study studies/NN-slug
```

`keep` means a track-specific improvement of at least `minimum_delta` with every
configured guardrail satisfied. `discard` is valid scientific evidence. `crash` has
an `NA` primary metric. Every disposition keeps a resolvable candidate commit.
run-one refuses an unchanged `train.py` before any id or commit exists (an
accidental rerun burns a phase slot); pass `--allow-rerun` for an intentional
identical replication — sealed final tests and `--command` overrides are exempt.

### 2. One foreground run, with a real timeout and exit status

```bash
uv run --locked klein run-one --study studies/NN-slug --track <track> \
  --description "<one falsifiable hypothesis>"
```

The workflow runs one unbuffered subprocess, streams and stores its output, enforces
`max_run_seconds` separately from phase budget and experiment count, terminates the
process group on timeout, and records crashes. Never use a `command | tee` pipeline:
without careful shell settings it can report `tee`'s success instead of the model's
failure.

### 3. Gates and acknowledgements are machine state

```bash
uv run --locked klein gate record consult --study studies/NN-slug \
  --acknowledged-by <actor>
uv run --locked klein gate record data --study studies/NN-slug \
  --acknowledged-by <actor>
uv run --locked klein gate record method --study studies/NN-slug \
  --acknowledged-by <actor>
```

An override must name the gate, actor, and non-empty reason using `klein gate
override`; it is timestamped in state/events. Silent fast paths are invalid.

### 4. Development is adaptive; final test is sealed

Training and adaptive selection use only train/development partitions. A track gets
one confirmation access:

```bash
uv run --locked klein run-one --study studies/NN-slug --track <track> --final-test \
  --description "sealed confirmation of the selected candidate"
```

The final-test result is evidence, not another adaptive frontier candidate. Close
the study with `klein finalize` (add `--allow-exploratory` when no sealed run
exists): findings without sealed evidence are labelled exploratory; findings with a
successful sealed run may be labelled confirmed. Small deltas without uncertainty
are not described as real or decisive — finalize warns on that language.

### 5. Keep until the user stops — with the map open

Default stop rule: keep experimenting until the user says stop or a phase `max_experiments`
is hit. Do not unilaterally declare the batch done on a plateau. RE-READ `playbook.md`
— the study's rolling map (current best / ruled out with evidence / open hypotheses /
next-best candidates; `program.md` stays the append-only journal) — before choosing
every candidate, and refresh it at every phase boundary (or every 5 experiments);
start each phase with the slate ritual (`references/phase-ritual.md`).
Summarize and STOP for ack at every phase boundary — the acknowledgement requires a
refreshed, placeholder-free playbook and records its hash.

Record that acknowledgement before the next phase:

```bash
uv run --locked klein gate record phase --study studies/NN-slug \
  --phase <current-phase> --acknowledged-by <actor>
```

### Legacy v1 compatibility

A missing `schema_version` means v1. Existing five-column ledgers and Python APIs stay
readable and are not rewritten. Use `klein verify` for explicit warnings/errata. When reproducing a legacy command, replace the old tee
pipeline with the exit-safe helper from inside the study directory:

```bash
uv run --locked python ../../scripts/run_with_log.py \
  --timeout-seconds 600 --log run.log -- \
  uv run --locked python -u train.py
```

## Installing in another repo

Klein is self-contained under `.claude/skills/klein/`:

```bash
cp -r .claude/skills/klein /path/to/your-repo/.claude/skills/
```

The engine is a dependency, not an option: every helper (`preflight.py`,
`new_study.py`, the `klein` CLI) imports `kleinlib` — the schema and templates live
there and nowhere else, so nothing can drift. In the foreign repo, add the engine
(see `assets/pyproject-study-template.toml`), then `uv sync --locked`:

```bash
uv add "klein-auto-research @ git+https://github.com/Xiang-Shan/klein-auto-research@v1.1.0"  # pin a tag
```

Tags are safe to pin: since v1.0.0 the study schema (v2), the `klein` CLI
surface, and the ledger formats are stable — breaking changes mean a major
version. `klein new` then scaffolds byte-identical schema-v2 studies anywhere.

## Limitations

Klein is intentionally a small, single-machine harness. Know the edges.

- **Three evaluator shapes, one deviance family**: binary classification (`evaluate`),
  point/rate regression (`evaluate_regression` — RMSE/MAE/R², plus
  Poisson/Gamma/Tweedie deviance under the exposure-weighted-rate convention: y is the
  rate, `sample_weight` the exposure; Tweedie declares its `power` in the track
  contract), and scalar/simulation (`evaluate_scalar`) — all printing the same
  canonical block. Regression weighting is optional and off by default;
  **classification metrics remain unweighted**. Multiclass, survival, and ranking are
  extension points, deliberately not shipped until a worked study proves them (the
  repo's own ethos); `evaluate_with_inner_cv` is binary-only.
- **One primary metric per track.** Each track owns its direction, minimum delta, and
  guardrails. Everything else (calibration, wall-clock, lift) remains auxiliary, and
  SYNTHESIZE weighs those tradeoffs without manufacturing a global cross-task frontier.
- **Single machine, one experiment at a time** (blocking foreground, token-economical).
  No parallel dispatch. *Extension:* wrap a distributed launcher INSIDE one `train.py`
  (e.g. `torchrun` as a subprocess); the adaptive loop is lost if experiments run in
  parallel.
- **No distributed / no learned meta-controller.** The agent reasons about results
  conversationally; it does not learn a policy across runs. *Extension:* `playbook.md`
  is the within-study memory and `knowledge/` the cross-study memory — priors promote
  through claim-cited findings, not learned weights.
- **The measured noise floor bounds honesty, not power.** A `minimum_delta` from k seed
  blocks stops within-noise keeps; it does not create statistical power. Shrinking the
  floor (more reps, CRN pairing) is study design, not framework magic.
