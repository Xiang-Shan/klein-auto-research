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

## Subcommands

Run in lifecycle order for a new study; `status` any time. The reference PROTOCOLS are
the source of truth — the worker agents in `.claude/agents/` are optional accelerators;
a solo session follows the protocols directly.

| Subcommand | What it does | Protocol | Key outputs | Worker agent |
|---|---|---|---|---|
| `new` | Scaffold a study dir | `references/defaults-and-scaffolding.md` | study.yaml, state/events, prepare/train, ledgers | `klein new` |
| `consult` | Gate 0: ≤6-question interview (or fast-path) | `references/consult-protocol.md` | study.yaml, research_plan.md; **user ack** | klein-consultant |
| `data` | Gate 1: profile → ranked go/no-go | `references/data-gate-protocol.md` | data_card.md | klein-data-auditor |
| `method` | Gate 2: intuition→math→impl→refs | `references/method-gate-protocol.md` | method_card.md | klein-method-scholar |
| `run` | One candidate transaction (edit → commit → run → retain evidence) | Hard Rules below; sweeps: `references/sweep-rules.md` | run manifests, derived results, models/, figures/ | klein-experimenter / klein-sweeper |
| `synthesize` | Mine trajectory → 7-section findings | `references/synthesis-protocol.md` | findings.md | klein-synthesist |
| `tutorial` | Build self-contained teaching HTML | `references/tutorial-spec.md` | report/index.html | klein-tutor |
| `status` | Summarize results + phase telemetry | `scripts/summarize_results.py` | results_summary.md, progress.svg | — |

War stories behind the guards: `references/war-stories.md`. Schema authority:
`kleinlib/schema.py` — never restate columns anywhere.

## Setup

```bash
uv sync --locked             # core deps; add --extra gbdt | deep | dev as needed
uv run --locked python -c "import kleinlib"
```

Data resolution: `kleinlib.data.load_data_hub(name)` tries the `$DATA_HUB` env var
(an external data-hub repo) and then a repo-bundled `datasets/<name>/` copy, printing
a `data source:` provenance line either way; plain local files go through
`kleinlib.data.load_prepared` (`csv:<path>` sources). Study 00's `prepare.py --sample`
uses a committed 2k fixture for fast offline smoke runs.

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

### 1. Commit every candidate before execution; derive the ledger afterward

The mutable surface is `train.py` only (normally a 5–15 line diff). `klein run-one`
commits that exact candidate before running it, even when it later becomes a discard
or crash. It then writes the immutable `runs/E####/manifest.json`, appends the
hash-chained event, restores `train.py` after a non-keep, derives `results.tsv`, and
commits evidence transactionally. Never hand-edit the v2 ledger. If interrupted, run:

```bash
uv run --locked klein recover --study studies/NN-slug
```

`keep` means a track-specific improvement of at least `minimum_delta` with every
configured guardrail satisfied. `discard` is valid scientific evidence. `crash` has
an `NA` primary metric. Every disposition keeps a resolvable candidate commit.

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

The final-test result is evidence, not another adaptive frontier candidate. Findings
without it are labelled exploratory; findings with it may be labelled confirmed.
Small deltas without uncertainty are not described as real or decisive.

### 5. Keep until the user stops

Default stop rule: keep experimenting until the user says stop or a phase `max_experiments`
is hit. Do not unilaterally declare the batch done on a plateau. Summarize and STOP for
ack at every phase boundary.

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
uv add "klein-auto-research @ git+https://github.com/Xiang-Shan/klein-auto-research"
```

`klein new` then scaffolds byte-identical schema-v2 studies anywhere.

## Limitations

Klein is intentionally a small, single-machine harness. Know the edges.

- **Three evaluator shapes today**: binary classification (`evaluate`), point
  regression (`evaluate_regression`), and scalar/simulation (`evaluate_scalar`) — all
  printing the same canonical block. Multiclass, survival, and ranking are extension
  points, deliberately not shipped until a worked study proves them (the repo's own
  ethos); `evaluate_with_inner_cv` is binary-only.
- **One primary metric per track.** Each track owns its direction, minimum delta, and
  guardrails. Everything else (calibration, wall-clock, lift) remains auxiliary, and
  SYNTHESIZE weighs those tradeoffs without manufacturing a global cross-task frontier.
- **Single machine, one experiment at a time** (blocking foreground, token-economical).
  No parallel dispatch. *Extension:* wrap a distributed launcher INSIDE one `train.py`
  (e.g. `torchrun` as a subprocess); the adaptive loop is lost if experiments run in
  parallel.
- **No distributed / no learned meta-controller.** The agent reasons about results
  conversationally; it does not learn a policy across runs. *Extension:* `program.md` IS
  the persistent memory — write priors and doctrine there between studies.
