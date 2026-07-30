# Klein Auto Research

[![ci](https://github.com/Xiang-Shan/klein-auto-research/actions/workflows/ci.yml/badge.svg)](https://github.com/Xiang-Shan/klein-auto-research/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-3776AB.svg)](pyproject.toml)

**A reconnaissance aircraft for ML research.** Before you bet a production quarter
on a new modeling method, fly a cheap, honest sortie over it first: a few hours of
disciplined, git-ledgered experiments on *your* data, closed with mined insights
and a teaching artifact. Built by an actuary, for actuaries and data scientists —
from GLMs you know by heart to frontier methods you've only read about.

Klein runs research **studies** through a fixed six-stage lifecycle:

```
new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md   report/
```

<p align="center"><img src="docs/diagrams/lifecycle.png" alt="The Klein study lifecycle — six stages, three checkpoints" width="640"></p>

The last two stages are what make it *research*, not just experiment-running:
every study must end with `findings.md` — verdicts on the research questions,
surprises, practical advice, literature tie-back, every claim citing experiment
IDs — and a self-contained HTML tutorial that teaches the method, the journey,
and the coding pitfalls back to you.

## Why Klein

1. **Recon before conquest.** Learn where a new method pays *on your data* before
   committing serious modeling effort. The shipped DAE study is the exemplar: "no
   for ranking at 58k rows, but 3.4× better than median-imputation at cell repair"
   is exactly the intelligence you want before a production bet.
2. **A disciplined loop instead of notebook chaos.** Under schema v2 every
   candidate is committed before it runs, including discards and crashes. An append-only event
   log and immutable run manifest bind code, data, split, environment, metrics,
   artifacts, and disposition; `results.tsv` is a compact derived view. Git *is*
   the reconstructable config record, not just a list of winners. A rolling
   `playbook.md` keeps the map (current best, ruled-out, open hypotheses) that
   the loop re-reads before every candidate, and each phase starts with a
   scored candidate slate rather than a hunch.
3. **Machine-enforced gates against self-deception.** A GIGO ("garbage in,
   garbage out") data gate blocks modeling until the data problems are on the
   table — closing with a clean-room leakage audit whose mechanical checks ship
   in `kleinlib.leakage`; a method gate forces understanding before compute
   (Theory+Papers+Practice, asserted and checked); a consult gate turns
   vague goals into falsifiable questions. `minimum_delta` — the smallest
   difference worth calling a keep — is MEASURED from a k-seed noise floor,
   never guessed. Gate acknowledgements, overrides,
   prepared-data fingerprints, exact study branches, and ledger integrity are
   checked before a schema-v2 run.
4. **Insight mining is mandatory, not optional.** SYNTHESIZE mines the whole
   trajectory — keeps vs discards, metric trends, aux-metric tradeoffs (rank vs
   calibration), decision history — into findings a colleague can act on, every
   claim carrying a stable citable ID, with the keep/discard/crash journey
   rendered as a per-track decision-trajectory figure.
5. **A teaching artifact closes every study.** The tutorial (`report/index.html`,
   fully offline) levels you up and onboards the next person.
6. **A frontier-method onramp.** Method cards teach unfamiliar methods; when no
   dataset exists, a synthetic known-truth lab (see the QLS study) makes estimator
   claims checkable by construction.
7. **Senior scars, encoded.** Real failures live as executable guards — collapsed-
   prediction assert, schema drift tests, OpenMP process isolation — so beginners
   inherit them. The incident reports: `.claude/skills/klein/references/war-stories.md`.

**Versus notebooks:** a notebook remembers your last state; Klein's ledger
remembers *every* state, including the failures — and the failures are where the
insight lives. **Versus driving an AI assistant freehand:** the lifecycle, gates,
and hard rules are written down, so sessions are reproducible and reviewable
instead of vibes; the assistant works *inside* the contract, not around it.

## Quickstart

Needs Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), and a bash-capable shell
for `verify_e2e.sh` (macOS/Linux out of the box; WSL or Git Bash on Windows). No
credentials, no downloads — the quickstart dataset (58,592 real auto-insurance
claims, Apache-2.0) is bundled in the repo.

```bash
git clone https://github.com/Xiang-Shan/klein-auto-research
cd klein-auto-research
uv sync --locked --extra encoders
uv run --no-sync pytest kleinlib/tests .claude/skills/klein/scripts/tests \
    studies/02-rqls-pv-severity/tests scripts/tests -q
uv run --no-sync klein --help
bash scripts/verify_e2e.sh          # optional: isolated end-to-end proof

cd studies/00-glm-claims-quickstart
uv run --no-sync prepare.py         # prints "data source: bundled — …"
uv run --no-sync python ../../scripts/run_with_log.py --timeout-seconds 600 \
  --log run.log -- uv run --no-sync python -u train.py
# --no-sync keeps step 1's extras: a bare `uv run` re-syncs to default extras
# expect primary_metric: 0.664322 (±0.001 gate; CI-proven)
```

Heads-up on extras: `uv sync` installs exactly what you name — and *removes*
extras you omit. Compose what a study needs: `--extra gbdt`
(LightGBM/XGBoost/CatBoost), `--extra deep` (PyTorch — required for
`studies/01-dae-claims`), e.g.
`uv sync --locked --extra encoders --extra gbdt --extra deep`.

## The `klein` command line

New studies default to `schema_version: 2` and are driven through the packaged
`klein` command. Run `--help` on any command for its complete arguments.

```bash
klein new 04-my-question --metric val_auc --goal-direction higher
git switch -c experiments/04-my-question   # the loop refuses to run on main
# author data_card.md / method_card.md at their gates (templates in assets/), then:
klein gate record consult --study studies/04-my-question --acknowledged-by <name>
klein gate record data --study studies/04-my-question --acknowledged-by <name>
klein gate record method --study studies/04-my-question --acknowledged-by <name>
klein preflight --study studies/04-my-question
klein run-one --study studies/04-my-question --description "registered baseline"
klein noise-floor --study studies/04-my-question   # Phase 0: measure minimum_delta
klein status --study studies/04-my-question
klein recover --study studies/04-my-question
klein finalize --study studies/04-my-question
klein verify --study studies/04-my-question
```

Gate records, `finalize`, and `recover` commit their own state writes — the loop
never dead-ends on receipts the CLI itself generated.

<p align="center"><img src="docs/diagrams/loop-transaction.png" alt="One candidate transaction — you think; run-one notarizes; the files remember" width="640"></p>

`klein gate override` records an explicit reason instead of silently bypassing a
gate. `klein run-one --final-test` permits one sealed final-test evaluation per
track. `klein verify --study <legacy-study>` prints deprecation errata for v1
studies without ever rewriting them.

## Drive it with your agent — or none

Klein is agent-agnostic. The operating manual is [`AGENTS.md`](AGENTS.md) — the
lifecycle, the stage↔protocol map, and the hard rules — and the stage protocols it
points to are plain markdown that any tool (or human) can follow.

| You use… | How to drive Klein |
|---|---|
| **Codex, Copilot coding agent, Cursor, Jules, …** (tools that auto-read `AGENTS.md`) | Just ask: *"run a Klein study on `<your data>` — follow the stage map in AGENTS.md"* |
| **Claude Code** | The `/klein` skill routes the same stages: *"use /klein — start with `studies/00-glm-claims-quickstart`"* |
| **Gemini CLI / Qwen Code** | Point the context file at `AGENTS.md` (e.g. the `contextFileName` setting), or open with *"read AGENTS.md first"* |
| **GLM & other Anthropic-compatible CLIs** | They load `CLAUDE.md`, which imports `AGENTS.md` |
| **No agent** | `AGENTS.md` doubles as a human runbook — follow the stage map by hand; every helper script is a plain CLI |

New here? Reading order: this README → [`AGENTS.md`](AGENTS.md) →
[`studies/00-glm-claims-quickstart/`](studies/00-glm-claims-quickstart/) → the
stage protocols as you need them.

## The shipped studies — immutable v0.1 legacy evidence

The three executed studies predate the public v0.2 transaction contract. Their
`results.tsv`, `program.md`, and `findings.md` ship verbatim as scientific
exhibits; their private-lab commit hashes are candidly unresolved in this public
history. Compatibility tools read them with explicit deprecation/provenance
warnings. They are examples of the six-stage research doctrine, not examples of
v0.2 reconstructable run manifests.

| Study | Question | Headline findings |
|---|---|---|
| [`00-glm-claims-quickstart`](studies/00-glm-claims-quickstart/) | Are GLM/GBDT baselines reproducible here, and is there headroom? | Anchors reproduce to 4 decimals; splines close most of the LR→GBDT gap; a sanctioned sweep finds +0.0014 (best 0.6643) |
| [`01-dae-claims`](studies/01-dae-claims/) | Does a denoising autoencoder pay on 58k-row tabular claims? | Honest no for ranking (0.6683 vs GBDT 0.6701); plain MLP ties tuned GBDT (0.6706); the DAE pays 3.4× as an *imputer*; recon-error is not a claim ranker |
| [`02-rqls-pv-severity`](studies/02-rqls-pv-severity/) | Is robust quantile least squares worth its efficiency cost for loss severity? | At 10% contamination, naive MLE premium error hits 352% vs 50% for window-QLS; robustness costs only 1.083× when clean; parameter bias ≠ pricing bias |

The fourth study is a **v0.3 schema-v2 exhibit** — every candidate commit
resolves in this repository, and it exercised the whole hardened contract live:

| Study | Question | Headline findings |
|---|---|---|
| [`03-noisy-rosenbrock-dfo`](studies/03-noisy-rosenbrock-dfo/) | At 200 noisy evaluations, do restarts beat Nelder-Mead — and does SPSA beat both? | Restarts win 2.96× the measured floor and the sealed fresh-seed run replicates (confirmed); random search ties them — found by the DATA gate before any run; "textbook" SPSA diverges to 1e178 because the method card's own tuning rule went unapplied |

Open a tutorial to see what "closing the loop" means:
`open studies/01-dae-claims/report/index.html` — method taught, journey annotated,
coding pitfalls included, works offline.

## Run it on your own data

The pitch is *your* data, so that path is first-class:

1. Scaffold:
   `klein new 04-my-question --data csv:/path/to/my.csv --metric val_auc --goal-direction higher`
2. Point `prepare.py` at your file (`kleinlib.data.load_prepared`) and keep its
   output stable; the CONSULT protocol (≤6 questions) turns your goal into
   research questions with registered predictions.
3. Pass the DATA gate — the profiler ranks go/no-go issues before any modeling.
4. Create the exact `experiments/04-my-question` branch, record the required gate
   acknowledgements, pass `klein preflight`, then run one candidate at a time with
   `klein run-one`; SYNTHESIZE and TUTORIAL close it.

Evaluator shapes today: **binary classification, point regression, and
scalar/simulation** (`task_type: simulation` gives math/optimization labs custom
scalar metrics and seed-block splits; everything non-primary goes to
`aux_metrics.tsv`). Multiclass/survival/ranking are documented extension
points — see *Limitations* in `.claude/skills/klein/SKILL.md`. If you keep a
data-hub directory, set `$DATA_HUB`; otherwise bundled datasets (see
[`datasets/insurance-claims/`](datasets/insurance-claims/README.md)) and `csv:`
paths just work.

## Is Klein a skill or a harness? Both — a harness that carries a skill.

- **Harness (recommended):** this repo is a complete research lab — engine
  (`kleinlib`), lifecycle skill, agents, knowledge base, executed exemplars.
  Clone it and run studies inside; your ledgers' commit hashes resolve here.
- **Skill (portable doctrine):** copy `.claude/skills/klein/` into any repo —
  the protocols are self-contained markdown, and the engine is a one-line git
  dependency (schema and templates are single-sourced in `kleinlib`, so nothing
  can drift). Pin a tag (see `assets/pyproject-study-template.toml`). The "skill" packaging is Claude
  Code's; every file inside is plain markdown/Python that any agent reads, and
  `AGENTS.md` is the tool-neutral router for the same doctrine. The skill is the
  flight doctrine; the harness is the equipped aircraft.

## Layout

| Path | What |
|---|---|
| `AGENTS.md` | the operating manual — for any coding agent, or a human driving by hand |
| `.claude/skills/klein/` | the lifecycle protocols, templates, and helper scripts — plain markdown/Python (packaged as the `/klein` skill for Claude Code) |
| `.claude/agents/` | seven optional worker-role definitions (pre-wired for Claude Code; the roles are documented tool-neutrally in AGENTS.md) |
| `kleinlib/` | engine: schema contract, data/eval/figures/torch helpers, sweep runner |
| `knowledge/` | distilled research docs + method cards (the seed knowledge base) |
| `datasets/` | bundled datasets with their own licenses/attribution |
| `studies/` | one directory per study — the unit of research |
| `scripts/verify_e2e.sh` | isolated, portable proof of the v1 compatibility pipeline |
| `CLAUDE.md` | Claude Code's entry point — imports AGENTS.md |

## Lineage & citing

Klein descends from
[karpathy/autoresearch](https://github.com/karpathy/autoresearch) (the
`program.md` lab-notebook + edit-`train.py`-run-log loop) via
[elan-elan/agent-smith](https://github.com/elan-elan/agent-smith) (the loop as a
portable skill). Klein keeps the proven loop, drops the Docker/R baggage, and
adds the consulting/data/method gates plus the mandatory synthesis and tutorial
stages. The name nods to the Klein bottle: a research loop whose output feeds
its own input.

<p align="center"><img src="docs/diagrams/klein-bottle.png" alt="Why Klein — the inside is the outside; a study's findings become the next study's priors" width="560"></p>

The public repository history begins in July 2026; the shipped
v0.1 studies were executed in the development lab before that public history.

Release history: [`CHANGELOG.md`](CHANGELOG.md).
To cite Klein, see [`CITATION.cff`](CITATION.cff). To contribute, see
[`CONTRIBUTING.md`](CONTRIBUTING.md); report vulnerabilities via
[`SECURITY.md`](SECURITY.md). The software is MIT licensed ([LICENSE](LICENSE));
third-party data and lineage notices are collected in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). The bundled dataset carries
its own Apache-2.0 license and attribution
([datasets/insurance-claims/DATA_LICENSE](datasets/insurance-claims/DATA_LICENSE)).
