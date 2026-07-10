# Defaults & scaffolding

How a study is laid out, named, budgeted, and branched. Read this before scaffolding a
study or proposing defaults.

## Study layout & naming

Every study is ONE directory: `studies/NN-slug/` — a two-digit ordinal plus a lowercase
slug (`00-glm-claims-quickstart`, `01-dae-claims`). The ordinal orders the research
narrative; the slug says what it is. One study = one question = one `results.tsv`.

Scaffold it — never hand-create the tree:

```bash
uv run python .claude/skills/klein/scripts/new_study.py 03-my-study \
    --goal "does X beat baseline B on my data?" \
    --domain insurance --metric val_auc --goal-direction higher \
    --data "data_hub:insurance-claims"
```

This writes `study.yaml`, `program.md`, `research_plan.md`, `prepare.py`, `train.py`,
`results.tsv` (schema header only), `aux_metrics.tsv`, and empty `figures/ models/
report/ sweeps/`. It refuses to overwrite an existing study dir. Flags fill the matching
placeholders; CONSULT fills the rest.

## The canonical files (fixed names)

Klein scaffolds a canonical layout — do NOT rename these to match an existing repo:

| File | Role | Mutable? |
|---|---|---|
| `study.yaml` | machine-readable contract (goal, metric, split, phases, RQs) | at CONSULT only |
| `program.md` | living lab notebook (narrative, decisions, predictions) | throughout |
| `research_plan.md` | CONSULT output (human-readable plan) | at CONSULT |
| `data_card.md` | DATA-gate output (profile + go/no-go) | at DATA gate |
| `method_card.md` | METHOD-gate output (intuition→math→impl→refs) | at METHOD gate |
| `prepare.py` | stable data prep | rare, deliberate |
| `train.py` | THE per-experiment surface | every experiment (5-15 line diff) |
| `results.tsv` | the one ledger (schema = kleinlib/schema.py) | append-only, one row/exp |
| `aux_metrics.tsv` | everything-not-the-primary-metric sidecar | append-only |
| `findings.md` | SYNTHESIZE output (7 sections) | at SYNTHESIZE |
| `report/index.html` | TUTORIAL output (self-contained) | at TUTORIAL |

`data_card.md` and `method_card.md` are NOT scaffolded by `new_study.py` — they are the
outputs of the DATA and METHOD gates, authored from `assets/*-card-template.md`.

### Adopting an existing (foreign) repo

If a repo already has prep/train scripts, prefer them over renaming. Discovery hints:
prep → `prepare.py`, `scripts/prepare.py`, `download*.py`, `*kaggle*.py`; train →
`train.py`, `scripts/train.py`, `fit.py`, `main.py`. Point `study.yaml` at the real
paths and keep the loop contract.

## Split contract

The split in `study.yaml:data.split` is FIXED for the life of the study. Canonical
default: stratified, `seed=42`, `test_size=0.2`. Never resample or peek at the val split
— cross-experiment comparability is the whole point. `kleinlib.data` owns the split so
every experiment gets the identical one. Synthetic/simulation studies use `kind: none`.

## Per-problem-class default budgets

Starting per-experiment wall-clock budgets when scaffolding `study.yaml:phases`:

| Problem class | Default budget |
|---|---|
| Small tabular (<10k rows, <50 feats) | 2 min |
| Medium tabular (10k-100k rows) | 5 min |
| Large tabular (100k-1M) or text/NLP | 10 min |
| GBDT HPO / sweeps | 15-30 min |
| Deep tabular / torch (MPS) | 30-60 min |
| Monte-Carlo / simulation | per-cell: size × reps, set explicitly |

After the baseline runs, tighten to `max(3× baseline wall-clock, 60s)`. A run over
budget is a `crash` (timeout note), reverted. User-supplied budgets always win.

## Branch rule

Studies run on `experiments/<study-slug>` — NEVER on `main`. Branch before the first
experiment:

```bash
git checkout -b experiments/03-my-study
```

`main` stays the stable baseline; merge the study branch at study end. Preflight treats
being on `main` as a failure for the loop — respect it.

## uv only

All Python runs through `uv run`; all deps through `uv add`. `uv sync` to set up;
`--extra gbdt`, `--extra deep`, `--extra dev` for the optional stacks. If `uv` is
missing, install it first — never fall back to pip/conda (lockfile drift is
undebuggable).

## Foreign-repo bootstrap

Copy `.claude/skills/klein/` into the target repo. Preflight and `new_study.py` carry an
embedded schema fallback, so they work even without `kleinlib` installed — but a real
study needs the engine: add `kleinlib` as a dependency (see
`assets/pyproject-study-template.toml`) and `uv sync`.
