# Klein Auto Research

[![ci](https://github.com/Xiang-Shan/klein-auto-research/actions/workflows/ci.yml/badge.svg)](https://github.com/Xiang-Shan/klein-auto-research/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-3776AB.svg)](pyproject.toml)

**Process-verifiable research for AI for Science.** Klein is the lab-notebook
discipline an AI agent runs *inside*: predictions registered before their evidence,
every run notarized in git, claims whose strength is earned, an independent referee
before anything is called a finding. It works on your data, on public data, on a
simulator, or on nothing but a verifier — and a stranger can audit the whole process
with no model in the loop.

It is not hard to let an agent do research overnight. What is hard is signing the
conclusion the next morning. Klein exists for the signature.

Every study moves through seven stages, past four gates:

```
new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ REFEREE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md    Gate 3     report/
```

<p align="center"><img src="docs/diagrams/lifecycle.png" alt="The Klein study lifecycle — seven stages, four checkpoints" width="640"></p>

## Why Klein

In April 2026, a study of 25,000+ runs of AI-scientist systems across eight domains
(Ríos-García, Jablonka et al., [arXiv:2604.18805](https://arxiv.org/abs/2604.18805))
found that agents produce results without reasoning scientifically — and that
outcome-based evaluation cannot detect it. Scaffolding explained 1.5 % of outcome
variance. No scaffold makes a model reason better; what a scaffold *can* do is make
the failures detectable. Klein does that mechanically, with no model checking itself:

| Failure the 2026 study measured | What Klein makes mechanical |
|---|---|
| **Evidence ignored** — 68 % of traces | Every candidate is committed *before* it runs; `klein verify --evidence-use` reports what the write-up ignored |
| **No belief revision on refutation** — 26 % revise | Predictions carry an arithmetic rule; a refuted one with no dated `Decision:` line fails verification |
| **Convergent evidence rare** | One sealed look per track; `confirmed` needs the evidence kinds the track requires, and single-source confirmations are flagged |
| **Outcome evaluation cannot see it** | An independent referee, on a different model, applies a fixed ten-check rubric before `finalize` |

The rest of the discipline is the part its studies paid for: a measured noise floor
before any comparison, a detection-limit law, contract-driven splits, a sealed dry-run,
errata that re-scope and never delete. The incident reports are in
[`war-stories.md`](.claude/skills/klein/references/war-stories.md); the promoted
lessons, each cited to the claim that earned it, in
[`knowledge/research-discipline.md`](knowledge/research-discipline.md).

## One kernel, any inquiry

A study is typed on three orthogonal axes; the same trust kernel serves all of them.

| Axis | Values | What it changes |
|---|---|---|
| **kind** — the question's shape | `predict` · `estimate` · `test` · `simulate` · `replicate` · `discover` · `optimize` | track mode, what "sealed" means, what `confirmed` requires |
| **modality** — the evidence source | `tabular` · `timeseries` · `image` · `sequence` · `graph` · `text` · `simulation` · `none` | which data-gate card the DATA gate demands |
| **profile** — the audience | `generic` · `ml-research` · `math` · `insurance` · your own `profile_doc` | headings, doctrine, figures, budgets, banned words |

A mathematician's keep means "beat the best known value"; a deep-learning researcher's
means "clear a five-seed noise floor". The engine does not know the difference; the
protocols do — [`inquiry-model.md`](.claude/skills/klein/references/inquiry-model.md).

## Quickstart

Needs Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), and git. No credentials and no
downloads: the quickstart is a five-minute study on synthetic data whose truth you
know, and every dataset an exhibit needs is bundled or generated.

```bash
git clone https://github.com/Xiang-Shan/klein-auto-research
cd klein-auto-research
uv sync --locked --extra encoders
uv run --no-sync klein doctor                       # what this machine can run; fetches nothing
uv run --no-sync pytest kleinlib/tests .claude/skills/klein/scripts/tests scripts/tests -q
uv run --no-sync python scripts/verify_shipped_studies.py   # every shipped ledger still verifies
uv run --no-sync klein verify --study studies/00-known-truth-quickstart --numbers   # the receipt
```

Then open `studies/00-known-truth-quickstart/report/index.html` — offline, one file —
and read its `claims.lock`: every number on that page has a home there.

Extras compose, and `uv sync` *removes* the ones you omit. `--extra gbdt` for
LightGBM/XGBoost/CatBoost, `--extra deep` for PyTorch (only to re-run the
character-language-model exhibit).

## The `klein` command line

New studies default to `schema_version: 3` and are driven through the packaged `klein`
command. The arc of a study:

```bash
klein new 14-my-question --kind predict --modality tabular --profile generic \
    --metric val_auc --goal-direction higher --data "csv:data/my.csv" --track primary
git switch -c experiments/14-my-question       # the loop refuses to run on main
klein gate record consult --study studies/14-my-question --acknowledged-by <name>   # then data, method
klein noise-floor --study … --recipe seed-sweep --estimand fit-noise   # measure the keep bar
klein preflight   --study …                                            # then the loop:
klein run-one     --study … --track primary --description "anchor" --tests P1
klein run-one     --study … --track primary --final-test --dry-run     # rehearse the seal
klein claims init --study … && klein gate record referee --study …
klein finalize    --study … && klein verify --study …    # writes verify_receipt.json
```

Run `--help` on any command for its full arguments. The CLI commits its own receipts,
so the loop never dead-ends on state it generated itself; `gate override`,
`headroom ack` and `stop ack` each put a reason on the record instead of silently
bypassing a rule. The full contract is in [`AGENTS.md`](AGENTS.md).

<p align="center"><img src="docs/diagrams/loop-transaction.png" alt="One candidate transaction — you think; run-one notarizes; the files remember" width="640"></p>

### Detection limit: audit headroom before spending challengers

A measured noise floor can honestly outgrow the incumbent's entire distance to
perfection — then no challenger can ever win, and nothing says so. Declare the metric's
best achievable value and Klein does the subtraction:
`h = (incumbent − ideal) / minimum_delta`, disclosed at preflight, verify and run-one.
`h < 1` refuses further development runs until `klein headroom ack` records the closed
door. Read `h ≥ 1` as "not excluded", never as "plausible": study 08 stood at
h = 1.015 and twenty-one challengers produced zero keeps.

## Drive it with your agent — or none

Klein is agent-agnostic and calls no model API. The operating manual is
[`AGENTS.md`](AGENTS.md); every protocol it points to is plain markdown.

| You use… | How to drive Klein |
|---|---|
| **Codex, Copilot, Cursor, Jules, …** | They auto-read `AGENTS.md` — just ask for a Klein study |
| **Claude Code** | The `/klein` skill routes the stages; eight worker agents ship pre-wired |
| **Claude Science** | A custom agent follows `AGENTS.md`; REFEREE goes to a different session |
| **Gemini CLI / Qwen Code** | Add `AGENTS.md` to the context files |
| **GLM & Anthropic-compatible CLIs** | They load `CLAUDE.md`, which imports `AGENTS.md` |
| **No agent** | `AGENTS.md` doubles as a human runbook; every helper is a plain CLI |

Where Klein sits among its neighbours — positioning, not a benchmark:

| | Claude Science | [Kosmos](https://arxiv.org/abs/2511.02824) | [Curie](https://arxiv.org/abs/2502.16069) | autoresearch | **Klein 2.0** |
|---|---|---|---|---|---|
| Runs where | hosted workbench | hosted | local | local | local, from git |
| Model | Claude | its own | any | any | any — none inside Klein |
| Unit of work | a session | a world model | an experiment | one script | a typed inquiry |
| Verification | reviewer agent | citation trails | rigor modules | keep / discard | ledger arithmetic, then a referee |
| Pre-registration | plan first | — | — | — | hashed arithmetic rules |
| Audit by a stranger | message history | citations | — | git history | every claim resolves |

Klein does not compete with a workbench on connectors or scale; it is the discipline a
workbench's agent can run *inside*. The full argument:
[`docs/design/klein-2-design.md`](docs/design/klein-2-design.md).

## The shipped studies

Every study below ran the whole lifecycle in this repository's history: every candidate
commit resolves and every ledger verifies, checked by CI on every push.

**Klein 2.0 exhibits (schema 3) — one per axis of generality:**

| Study | Typed as | What it showed |
|---|---|---|
| [`00-known-truth-quickstart`](studies/00-known-truth-quickstart/) | predict · tabular · generic | With the Bayes-optimal score known, three keeps closed most of the distance to it, and the one sealed look confirmed the level |
| [`10-hubble-1929-replication`](studies/10-hubble-1929-replication/) | replicate · tabular · generic | Hubble's 465 is unreproducible for missing inputs, not method; his own 24 objects support a value whose interval contains it |
| [`11-exact-verifier-construction`](studies/11-exact-verifier-construction/) | optimize · none · math | Zero keeps by arithmetic under an exact verifier — and what a search may claim when it cannot win |
| [`12-insurance-claims-frequency`](studies/12-insurance-claims-frequency/) | predict · tabular · insurance | All three v1 anchors reproduce on 58k real claims; the measured floor leaves the v1 ladder exactly one keep |
| [`13-charlm-fixed-budget`](studies/13-charlm-fixed-budget/) | predict · text · ml-research | At a fixed step budget, none of four registered levers cleared the noise floor; the only gain carried no prediction |

**Schema-2 exhibits (frozen; they verify under schema-2 rules forever):**

| Study | What it showed |
|---|---|
| [`03-noisy-rosenbrock-dfo`](studies/03-noisy-rosenbrock-dfo/) | Restarts beat Nelder-Mead at 2.96× the measured floor and replicate sealed — but random search ties them |
| [`05-fremtpl2-gap-forensics`](studies/05-fremtpl2-gap-forensics/) | On 678k rows the GBDT's sealed edge is 9.3× its paired SE, and ≈83 % of it is non-additive |
| [`06-hurricane-gqls-returnlevels`](studies/06-hurricane-gqls-returnlevels/) | All 120 published parameters reproduced sealed, once the loop found the thesis's own quantile convention |
| [`07-iris-90years`](studies/07-iris-90years/) | The measured floor outgrew the anchor's whole distance to perfection — the study that produced the headroom law |
| [`08-iris-rematch`](studies/08-iris-rematch/) | Twenty-one challengers walked through a door ajar at h = 1.015 and produced zero keeps |
| [`09-iris-first-lesson`](studies/09-iris-first-lesson/) | Door closed at h = 0.33 before a challenger ran; an erratum re-scoped a retired seed rather than deleting it |

Earlier exhibits and the original v1 quickstart are preserved intact at tags
[`v1.0.0`](https://github.com/Xiang-Shan/klein-auto-research/tree/v1.0.0/studies) and
[`v1.3.0`](https://github.com/Xiang-Shan/klein-auto-research/tree/v1.3.0/studies).
To see what "closing the loop" means, open any tutorial:
`open studies/10-hubble-1929-replication/report/index.html`.

## Run it on your own question

1. **Scaffold, typed** — `klein new … --kind … --modality … --profile … --data <source>`
   (`csv:`, `parquet:`, `synthetic:`, `bundled:`, `hub:`, `sklearn:`, `openml:`, `url:`;
   network sources are pinned by sha256 and refused under `KLEIN_OFFLINE=1`).
2. **CONSULT** — at most six questions turn the goal into predictions with rules.
3. **DATA** — the modality-typed card ranks go/no-go issues; partitions come from the
   contract, never from a seed in a script.
4. **METHOD** — the card teaches the method to your audience; a verifier, when declared,
   is hashed here and never edited again.
5. **EXPERIMENT** — branch, pass `klein preflight`, run one candidate at a time, and
   rehearse the sealed run before you spend it.
6. **CLOSE** — SYNTHESIZE writes findings and the lock; the REFEREE reads them before
   the story; the tutorial teaches it back.

Compute is one bounded foreground subprocess per run on whatever you have; long runs
are budgeted in steps or tokens, not seconds. Details in
[`compute-and-devices.md`](.claude/skills/klein/references/compute-and-devices.md).

## Limitations

Klein cannot make a model reason better — it makes reasoning failures detectable. It
runs one experiment at a time and does not schedule, parallelize, or learn a policy
across runs. It does not execute notebooks. The referee is independent by mechanism,
not by magic: a fresh session of the same model is the lowest rung of the independence
ladder, and the rung reached is on the record. A measured floor bounds honesty, not
power; a lock verifies that numbers have homes, not that the homes were the right
places to look. Evaluators today cover binary classification, point and rate regression
(incl. Poisson/Gamma/Tweedie deviance), scalar, estimate, test and table cells;
multiclass, survival and ranking are documented extension points.

## Is Klein a skill or a harness? Both — a harness that carries a skill.

- **Harness (recommended):** clone this repo and run studies inside it — engine,
  protocols, agents, knowledge base and executed exhibits, with commit hashes that
  resolve.
- **Skill (portable doctrine):** copy `.claude/skills/klein/` into any repo. The
  protocols are self-contained markdown and the engine is a one-line git dependency
  pinned by tag *and* commit (see `assets/pyproject-study-template.toml`).

## Layout

| Path | What |
|---|---|
| `AGENTS.md` | the operating manual — any agent, or a human |
| `.claude/skills/klein/` | lifecycle protocols, profiles, templates, helper scripts |
| `.claude/agents/` | eight optional worker-role definitions |
| `kleinlib/` | the engine: contract, events, state, transactions, checks, claims |
| `knowledge/` | promoted lessons and domain knowledge by profile |
| `datasets/` | bundled datasets with their licences and provenance |
| `studies/` | one directory per study — the unit of research |
| `docs/` | the Klein 2.0 design rationale, `migration-schema2-to-3.md`, driver reviews |
| `scripts/` | the end-to-end proofs, including tests of the docs themselves |

## Lineage & citing

Klein descends from [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
(the `program.md` lab notebook and edit-run-log loop) via
[elan-elan/agent-smith](https://github.com/elan-elan/agent-smith) (the loop as a
portable skill). Klein keeps the loop and adds the gates, the notary, the registered
predictions, the claims lock, the referee, and the mandatory synthesis and tutorial
stages. The name nods to the Klein bottle: a research loop whose output feeds its own
input.

<p align="center"><img src="docs/diagrams/klein-bottle.png" alt="Why Klein — the inside is the outside; a study's findings become the next study's priors" width="560"></p>

Release history is in [`CHANGELOG.md`](CHANGELOG.md); versioning is SemVer, and 2.0.0
froze the schema-3 contract, the CLI surface and the ledger formats. To cite Klein see
[`CITATION.cff`](CITATION.cff); to contribute, [`CONTRIBUTING.md`](CONTRIBUTING.md);
for vulnerabilities, [`SECURITY.md`](SECURITY.md). The software is MIT licensed
([LICENSE](LICENSE)); third-party data and lineage notices are collected in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
