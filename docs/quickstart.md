# Quickstart — from an empty folder to a signed study

Three steps: **watch** a study run, **read** a finished one, then **run** your own. Every
command on this page is real; the first half is exactly what `klein demo` executes, so you
can compare your screen with it line by line. Words in *italics* are defined in the
[glossary](../.claude/skills/klein/references/glossary.md) — or run `klein explain <word>`.

## 0. Install

You need Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) and git (with `user.name` and
`user.email` set — Klein records its work as commits).

```bash
git clone https://github.com/Xiang-Shan/klein-auto-research
cd klein-auto-research
uv sync --locked --extra encoders
uv run klein doctor          # what this machine can run; fetches nothing
```

`doctor` reports a few `[WARN]` lines for optional extras you did not install
(gradient boosting, PyTorch). That is expected. Add them when a study needs them — and
name every extra together, because `uv sync` removes the ones you leave out:
`uv sync --locked --extra encoders --extra gbdt --extra deep`.

In the rest of this page `klein …` means `uv run klein …` inside this repository, or
plain `klein …` after `pip install klein-auto-research`.

## 1. Watch a study run

```bash
klein demo
```

In about 15 seconds this builds `./klein-demo` — its own git repository — and runs the
first half of a real study on scikit-learn's breast-cancer table, offline. Nothing is
simulated: these are the engine's real gates and real runs. It prints each command it is
running, so the transcript is also a script you could type yourself.

| Step | What happens | The command |
|---|---|---|
| Scaffold | A study folder with a typed *contract*, a notebook and an empty ledger, on its own branch | `klein new 01-demo --recipe tabular-predict` |
| Look | One *probe*: class balance and the strongest single features. Logged, never evidence | `klein probe --note "…" -- python look.py` |
| Gate 0 — consult | The question and two *predictions* are fixed, each with the rule that will decide it | `klein gate record consult` |
| Gate 1 — data | A data card with a go / no-go decision; a leakage audit must pass | `python -m kleinlib.leakage …` then `klein gate record data` |
| Gate 2 — method | A short method card: intuition, maths, plan, when it pays | `klein gate record method` |
| Phase 0 | The *noise floor* is measured by re-drawing the split ten times; it becomes the smallest gain that counts | `klein noise-floor --recipe split-lottery --estimand marginal-resplit` |
| Three runs | A baseline (kept), the full model (kept; prediction 1 supported), an over-engineered idea (discarded; prediction 2 refuted) | `klein run-one --description "…" --tests P2` |
| The state | Status, the *evidence map*, and the one next action | `klein status`, `klein map`, `klein next` |

Then explore what it left:

```bash
klein map    --study klein-demo/studies/01-demo --html      # writes ./01-demo-map.html — open it
klein verify --study klein-demo/studies/01-demo --no-receipt
git -C klein-demo log --oneline                             # every gate and run is a commit
cat klein-demo/studies/01-demo/study.yaml                   # the contract
```

Two things worth noticing. The discarded run is still there, with its code — a failed
idea is evidence. And prediction 2 was refuted by arithmetic on a rule written before the
run, after which the notebook had to record a dated `Decision:` line; a refutation that
changes nothing fails verification.

The demo stops before the second half of the lifecycle, and says so: those stages need a
person's judgment.

## 2. Read a finished study

Eight finished studies ship in `studies/`. Take the Hubble replication:

```bash
klein map     --study studies/10-hubble-1929-replication     # 5 questions → 10 predictions → 13 runs → 18 claims
klein status  --study studies/10-hubble-1929-replication
klein verify  --study studies/10-hubble-1929-replication --no-receipt
```

`--no-receipt` only reads. Without it, `verify` writes and commits a receipt — right for
the owner of a study, wrong for a visitor.

Then open its files in this order:

1. `report/index.html` — the teaching report. Start here.
2. `findings.md` — what was learned, as numbered *claims*.
3. `referee_report.md` — what an independent reviewer made of it.
4. `program.md` — the notebook: hypotheses, decisions, dead ends.
5. `claims.lock` — every number in the findings, with the file and hash it came from.

## 3. Run your own study, with an agent

This is the intended way to work. Open the repository in your agent and state the
question:

> Run a Klein study: on `data/claims.csv`, does gradient boosting beat a GLM at predicting
> claim frequency by more than the noise?

The agent follows the written procedures stage by stage and **stops at each gate for your
decision** — it shows you the contract, the data card, the method card, and asks. You can
ask at any time: *"klein next"*, *"show me the map"*, *"explain headroom"*.

| Agent | Setup |
|---|---|
| Claude Code, in this repository | nothing — the `/klein` skill and the worker agents are wired |
| Claude Code, in your own project | `/plugin install klein --marketplace Xiang-Shan/klein-auto-research` |
| Any other agent | it reads [`AGENTS.md`](../AGENTS.md); in another repository run `klein skill install` first |

## 4. Run your own study, by hand

Everything the agent does is a plain command. `klein next` always names the next one and
says why, so you never need to remember the order.

### The first half — what the demo did

```bash
klein new 30-my-question --recipe tabular-predict --data csv:data/my.csv --target outcome
git switch -c experiments/30-my-question
S=studies/30-my-question

klein probe --study $S --note "what does the target look like?" -- python look.py   # optional, any time

# Gate 0: replace every {{placeholder}} in study.yaml, research_plan.md and program.md
# — the question, a prior belief, and predictions with rules — then:
klein gate record consult --study $S --acknowledged-by "<your name>"

# Gate 1: run prepare.py, audit the data, write data_card.md with a decision
( cd $S && python prepare.py && python -m kleinlib.leakage data/prepared/prepared.csv --target outcome --study . )
klein gate record data --study $S --acknowledged-by "<your name>"

# Gate 2: write method_card.md (klein explain template:method-card-template.md)
klein gate record method --study $S --acknowledged-by "<your name>"

# Phase 0: measure the noise floor, paste the block it prints into study.yaml.
# You write sweeps/noise_floor.py: it refits the baseline on ten re-drawn splits and
# records each score (a working example: klein-demo/studies/01-demo/sweeps/noise_floor.py).
( cd $S && python -u sweeps/noise_floor.py )
klein noise-floor --study $S --recipe split-lottery --estimand marginal-resplit \
  --sidecar sweeps/split_lottery.sidecar.tsv
klein gate record consult --study $S --acknowledged-by "<your name>" \
  --note "minimum_delta set from the measured noise floor"

# The loop: one idea per run. Edit train.py, then:
klein preflight --study $S
klein run-one   --study $S --description "what this run tries, in one line" --tests P1
```

Recipes exist for six kinds of study (`klein new --help`); without `--recipe` you get
templates to fill in. The procedure for each stage is one command away:
`klein explain consult`, `klein explain data`, `klein explain method`.

### The second half — closing the study

**The sealed run.** Each track reads the untouched data once. Rehearse first; the
rehearsal spends nothing and is mandatory.

```bash
klein gate record phase --study $S --phase adaptive-1 --acknowledged-by "<your name>" --note "why the loop stops here"
klein run-one --study $S --final-test --dry-run
klein run-one --study $S --final-test --tests P3
```

**Synthesize.** Write `findings.md` with its seven sections
(`klein explain template:findings-template.md`), then give every number a source and
every claim a class and a strength:

```bash
klein map     --study $S                       # which runs bear on which prediction; what is still open
klein claims init   --study $S
klein claims pin    --study $S results results.tsv
klein claims number --study $S best_auc --value 0.912345 --art results --claim C1 --precision 6
klein claims add    --study $S C1 --class empirical-description --strength confirmed \
  --claim "…the sentence, as in findings.md…" --numbers best_auc --evidence E0002,E0005
klein claims verify --study $S
```

**Referee.** Hand the study to a reviewer in a *fresh context* — a different model, tool
or person from whoever ran it. They write `referee_report.md`, whose first line is
`Verdict: PASS`, `PASS-WITH-NOTES` or `FAIL`. Answer each note in `program.md`, then:

```bash
klein gate record referee --study $S --acknowledged-by "<your name>"
klein finalize --study $S
klein verify   --study $S          # writes and commits the receipt
```

A `FAIL` cannot be recorded. Closing without a referee is allowed and disclosed:
`klein finalize --no-referee --reason "…"` labels the study `unrefereed`.

**The teaching report.** Write the seven sections under `report/sections/`
(`klein explain tutorial`), then:

```bash
klein report build $S --title "30-my-question — what we learned"
klein verify --study $S
```

The result is one self-contained `report/index.html` that opens offline, with figures
inlined, the code of a named run included, and every number traced to its source.

## Where to go next

| You want to | Read |
|---|---|
| Know what a word means | `klein explain <word>` — [glossary](../.claude/skills/klein/references/glossary.md) |
| See every command | [`cli.md`](cli.md) |
| Understand the rules of the loop | [`AGENTS.md`](../AGENTS.md) — the operating manual |
| Put Klein inside another product | [`embedding.md`](embedding.md) |
| Know why it is built this way | [`design/klein-3-design.md`](design/klein-3-design.md) |
| Record commitments before each action as well | the optional generation layer — `klein explain generation` |
| Find an older study | [`studies/ARCHIVE.md`](../studies/ARCHIVE.md) |
