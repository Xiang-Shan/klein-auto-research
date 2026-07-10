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

**Hard-block rule:** no modeling (`run`) until `data_card.md` says GO **and**
`method_card.md` exists. The only override is an explicitly logged `--fast-path`,
recorded with a reason in `program.md`.

## Subcommands

Run in lifecycle order for a new study; `status` any time. The reference PROTOCOLS are
the source of truth — the worker agents in `.claude/agents/` are optional accelerators;
a solo session follows the protocols directly.

| Subcommand | What it does | Protocol | Key outputs | Worker agent |
|---|---|---|---|---|
| `new` | Scaffold a study dir | `references/defaults-and-scaffolding.md` | study.yaml, program.md, prepare/train, ledgers | `scripts/new_study.py` |
| `consult` | Gate 0: ≤6-question interview (or fast-path) | `references/consult-protocol.md` | study.yaml, research_plan.md; **user ack** | klein-consultant |
| `data` | Gate 1: profile → ranked go/no-go | `references/data-gate-protocol.md` | data_card.md | klein-data-auditor |
| `method` | Gate 2: intuition→math→impl→refs | `references/method-gate-protocol.md` | method_card.md | klein-method-scholar |
| `run` | Experiment loop (edit train.py → run → record → commit) | Hard Rules below; sweeps: `references/sweep-rules.md` | results.tsv rows, models/, figures/ | klein-experimenter / klein-sweeper |
| `synthesize` | Mine trajectory → 7-section findings | `references/synthesis-protocol.md` | findings.md | klein-synthesist |
| `tutorial` | Build self-contained teaching HTML | `references/tutorial-spec.md` | report/index.html | klein-tutor |
| `status` | Summarize results + phase telemetry | `scripts/summarize_results.py` | results_summary.md, progress.svg | — |

War stories behind the guards: `references/war-stories.md`. Schema authority:
`kleinlib/schema.py` — never restate columns anywhere.

## Setup

```bash
uv sync                      # core deps; add --extra gbdt | deep | dev as needed
uv run python -c "import kleinlib"
```

Data resolution: `kleinlib.data.load_data_hub(name)` tries the `$DATA_HUB` env var
(an external data-hub repo) and then a repo-bundled `datasets/<name>/` copy, printing
a `data source:` provenance line either way; plain local files go through
`kleinlib.data.load_prepared` (`csv:<path>` sources). Study 00's `prepare.py --sample`
uses a committed 2k fixture for fast offline smoke runs.

Before the first experiment of a study, run preflight (checks uv, branch, results.tsv
schema, prepared data, mutable-file syntax):

```bash
uv run python .claude/skills/klein/scripts/preflight.py --study studies/NN-slug
```

Preflight is a PRE-EXPERIMENT check: on a finished study merged back to `main`, the
branch check FAILs by design — that is your reminder to branch (`git checkout -b
experiments/NN-slug`) before continuing it, not a broken ledger. To read a study's
health/status any time:

```bash
uv run python .claude/skills/klein/scripts/summarize_results.py \
    studies/NN-slug/results.tsv --goal higher   # or --goal lower
# → results_summary.md (frontier, aux panels, phase telemetry) + progress.svg
```

- **Studies convention:** one study = one dir `studies/NN-slug/` = one question = one
  `results.tsv`. Scaffold with `new_study.py` (see defaults-and-scaffolding.md).
- **Branch rule:** studies run on `experiments/<study-slug>`, NEVER on `main`. Branch
  before the first experiment; merge at study end.

## Hard Rules

Violating these has caused real data-loss and workflow failures — the specific
incidents live in `references/war-stories.md`, and the 215-experiment ancestor
campaign they come from ships its distilled findings in `knowledge/`. Do not
renegotiate them mid-study.

### 1. Commit-or-revert FIRST, then exactly ONE results.tsv row

Never the reverse; never batch rows; never reconstruct from memory. Every experiment
gets exactly one row — keep, discard, OR crash. A MISSING row is worse than a crash row:
it breaks the sequential numbering and makes the history unrecoverable.

- **improved** → `git add train.py && git commit -m "exp N: ..."`, `COMMIT=$(git rev-parse --short HEAD)`
- **not improved / crash** → `git checkout -- train.py`, `COMMIT="-"`

Append with a positional `printf` (column order = `kleinlib.schema.RESULTS_COLUMNS`):

```bash
printf '%s\t%s\t%s\t%s\t%s\n' "$N" "$METRIC" "$STATUS" "$COMMIT" "$DESC" >> results.tsv
```

A crash uses `NA` for the metric; a non-committed row uses `-` for the commit. Validate
the row you just wrote (quick check; `kleinlib.schema.validate_row` is the authority):

```bash
tail -1 results.tsv | awk -F'\t' '{ok=1;
  if($1!~/^[0-9]+$/)ok=0; if($3!~/^(keep|discard|crash)$/)ok=0;
  if($3=="crash"){if($2!="NA")ok=0}else if($2!~/^-?[0-9.]+([eE][-+]?[0-9]+)?$/)ok=0;
  if($4!="-"&&$4!~/^[0-9a-f]{7,40}$/)ok=0;
  print (ok?"OK: ":"ERROR: ")$0}'
```

If `ERROR`, delete the bad row and re-append. Common mistake: swapping metric (col 2)
and description (col 5). Everything that is NOT the one primary metric (PR-AUC, brier,
wall_seconds, ...) goes to `aux_metrics.tsv`, never into a new results column.

### 2. Foreground runs, within budget

`uv run train.py 2>&1 | tee run.log`, terminal timeout = the phase budget in ms. Never a
background poll. A run over budget is a `crash` (timeout note), reverted. The mutable
surface is `train.py` ONLY (5-15 line diffs); the split is FIXED and never resampled.

### 3. The gates hard-block modeling

No `run` until `data_card.md` = GO and `method_card.md` exists. Skipping a gate requires
a `--fast-path` LOGGED in program.md with a reason — a silent skip is a bug.

### 4. Keep until the user stops

Default stop rule: keep experimenting until the user says stop or a phase `max_experiments`
is hit. Do not unilaterally declare the batch done on a plateau. Summarize and STOP for
ack at every phase boundary.

## Installing in another repo

Klein is self-contained under `.claude/skills/klein/`:

```bash
cp -r .claude/skills/klein /path/to/your-repo/.claude/skills/
```

`preflight.py` and `new_study.py` carry an embedded schema fallback and ASSERT it equals
`kleinlib.schema` when the engine is importable — so they work in a foreign repo without
`kleinlib`, and drift fails loudly. A real study needs the engine, though: add `kleinlib`
as a dependency (see `assets/pyproject-study-template.toml`), `uv sync`, then
`new_study.py` bootstraps the study from `assets/` templates.

## Limitations

Klein is intentionally a small, single-machine, single-metric harness. Know the edges.

- **Three evaluator shapes today**: binary classification (`evaluate`), point
  regression (`evaluate_regression`), and scalar/simulation (`evaluate_scalar`) — all
  printing the same canonical block. Multiclass, survival, and ranking are extension
  points, deliberately not shipped until a worked study proves them (the repo's own
  ethos); `evaluate_with_inner_cv` is binary-only.
- **Single primary metric.** The loop optimizes ONE number. *Relief valve:* everything
  else (calibration, wall-clock, lift) goes to `aux_metrics.tsv`, and SYNTHESIZE weighs
  the rank-vs-calibration tradeoff there. *Extension:* add a study-specific summarizer
  panel; the sidecar is long-format and open.
- **Single machine, one experiment at a time** (blocking foreground, token-economical).
  No parallel dispatch. *Extension:* wrap a distributed launcher INSIDE one `train.py`
  (e.g. `torchrun` as a subprocess); the adaptive loop is lost if experiments run in
  parallel.
- **No distributed / no learned meta-controller.** The agent reasons about results
  conversationally; it does not learn a policy across runs. *Extension:* `program.md` IS
  the persistent memory — write priors and doctrine there between studies.
