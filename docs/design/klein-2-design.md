# Klein 2.0 — design rationale

*Process-verifiable research for AI for Science. Written 2026-09-02, the day the 2.0
plan was approved; this is the talk-ready version of the reasoning, kept in the
repository so it can be argued with.*

## 1. Why now

Two things happened in 2026 that define the problem Klein 2.0 answers.

In April, a study of more than 25,000 runs of AI-scientist systems across eight
domains (Ríos-García, Jablonka et al., arXiv:2604.18805) reported that the agents
*produce results without reasoning scientifically*: evidence was ignored in 68 % of
traces; refutation-driven belief revision occurred in 26 %; convergent multi-test
evidence was rare. The base model explained 41.4 % of the variance in outcomes and the
scaffold 1.5 %, so scaffold engineering alone cannot repair the reasoning — and,
crucially, *outcome-based evaluation cannot detect these failures*. A correct answer
reached by ignoring the evidence looks, from the outside, exactly like a correct
answer.

In June, Anthropic launched Claude Science: a hosted workbench with a coordinating
agent, user-built specialist agents, sixty-plus connectors, and a reviewer agent that
flags untraceable numbers and figures that do not match their code. Every output
carries its code, environment, description and message history. It is a serious
answer to the *tooling* problem of science — and its reviewer is, as its first
critics noted, the same underlying model checking itself.

Klein's position follows from putting the two together. **A scaffold cannot make a
model reason better, but it can make reasoning failures detectable and force the
missing behaviours.** The April study names exactly three: recording evidence,
revising beliefs on refutation, converging independent tests. Klein 1.x already
mechanized fragments of all three — a notary that keeps discards as evidence, a
predictions-to-falsify table, a sealed one-look confirmation, a detection-limit law, a
hand-built claims lock and errata. Klein 2.0 makes them the centre of the framework
instead of side effects of a metric hill-climb, and makes verification *mechanical
first, model second*: arithmetic on hashes and ledgers with no model in the loop,
then an independent referee on a different model.

## 2. What Klein 1.x was, and where it strained

Klein 1.x was two frameworks welded together. A domain-neutral **trust kernel** —
gates with artifact hashes, a hash-chained event log, candidate-commit-before-
execution, immutable run manifests, a derived results table, one sealed access per
track, a finalize verb that labels exploratory or confirmed, a verify verb — and a
**tabular-ML instantiation**: one mutable `train.py`, a printed `primary_metric:`
line, keep / discard / crash, a twelve-metric registry, a dataframe-shaped data gate.

Its own studies strained the instantiation. An estimation study with confidence
intervals had no incumbent to beat. A replication study of a 1936 dataset needed a
positive control and a floor of a different kind. A detection-limit study ran
twenty-one challengers with zero keeps because the floor had outgrown the prize — and
found the impossibility by hand between rounds. A registered-test study kept its
forty-two-cell permission map in a sidecar beside the ledger and invented a JSON
claims lock so a talk deck could trace every number without trusting the author. And
the lock's own numeral scan caught the operator: an evaluator had hardcoded a retired
split seed, the ledger lane had measured the wrong partition for a whole study, and
nothing in the engine had noticed because verify checked the contract's split rather
than the evaluator's.

Every one of those was a science-layer feature the studies had to build by hand.
Klein 2.0 promotes them into the engine.

## 3. The inquiry model

The unit of science is not a script that improves a metric. It is a **question** with
a **pre-registered prediction**, **evidence** a stranger can re-check, and a **claim**
whose strength was earned, closed by a **decision** written down when it was made.
Klein 2.0 types those five objects, gives each a machine surface (contract fields,
ledger entries, a lock) and a human surface (markdown), and checks that the two agree.

A study is typed on three orthogonal axes. **Kind** is the shape of the question —
predict, estimate, test, simulate, replicate, discover, optimize — and fixes the track
mode, what "sealed" means, what confirmation requires, and the strength a claim can
reach. **Modality** is the shape of the evidence source — a table, a time series,
images, sequences, graphs, text, a simulator, or nothing but a verifier — and selects
the data-gate card. **Profile** is who reads the study and what vocabulary is honest
there — generic, ML research, mathematics, insurance — and touches nothing the engine
checks. Generality comes from typing the inquiry, not from adding model wrappers.

## 4. The science layer, now in the engine

- **Two track modes.** *Frontier* keeps the 1.x semantics. *Registered* makes a track
  a pre-registered measurement program: every run is a cell, disposition
  `measured | crash`, no incumbent, tables pinned as evidence by `artifact:` lines.
- **A predictions ledger.** Predictions carry a declarative rule on printed keys —
  never evaluated code — and are adjudicated inside the run transaction:
  supported, refuted, inconclusive. A refuted prediction without a recorded decision
  fails verification. Belief revision becomes an act the ledger can see.
- **A declared verifier.** The searcher never grades itself. A gate-hashed checker
  script outside the mutable surface produces the value the disposition uses;
  disagreement with the searcher's own claim is a crash. Required for `optimize`;
  recommended wherever a checkpoint or a simulator scores the result.
- **Contract-driven splits and a sealed dry-run.** Partitions come from the contract;
  every evaluator prints a split fingerprint that the notary compares to the one
  frozen at the data gate; a rehearsal of the sealed run spends nothing.
- **A claims lock the engine produces and verifies.** Seven checks: shape, artifact
  hashes, presence in findings, evidence resolution, the numbers law, append-only
  history, ancestry. Errata re-scope; nothing is ever deleted.
- **A verify receipt that measures evidence use.** Ignored evidence, refutations
  without decisions, single-source confirmations — the April study's three missing
  behaviours — become three numbers on every study's receipt.
- **A referee gate.** A fresh context on a different model reads the findings before
  the narrative, runs the mechanical verifiers, applies a fixed ten-check rubric, and
  writes a verdict the orchestrator cannot record on a FAIL. Independence is a ladder
  and the rung reached is on the record.
- **Replication as convergent evidence.** A run is re-executed from its manifest in a
  detached worktree; a verifier is re-run on a pinned artifact; confirmation can
  require both a sealed look and a reproduction.
- **A science toolkit.** Floor recipes with a named estimand, a family-wise max-t
  guard, group-aware inner cross-validation, estimate / test / table evaluators,
  registered measurement sweeps, a stop rule, and an optional, explicitly priced
  materiality block that can never be confused with measurement resolution.

## 5. Generality by example

Five exhibits ship with 2.0, one per axis. A **known-truth quickstart** on synthetic
tabular data whose Bayes-optimal score is known — the only way to show the headroom
law against a true ideal. **Hubble 1929**: twenty-four nebulae, a registered
replication and estimation study whose sealed partition is Hubble's own second table,
a prospective lock that the study refuses to call blindness. An **exact-verifier
construction** in mathematics: an integer objective, a literature incumbent seeding
the frontier, a search that may match the best known value and is not allowed to call
that a keep. **Insurance claims frequency**, the study the actuarial audience re-runs,
now one profile rather than the front door. And a **fixed-budget character language
model**: matched compute in steps, a five-seed fit-noise floor, checkpoints scored by a
verifier the training script cannot touch — the autoresearch ancestor pattern done
under contract.

## 6. What the studies taught

The 2.0 mechanisms are not designed from principle alone; each answers a lesson a
shipped study paid for. The promotion of those lessons, with typed claim citations, is
`knowledge/research-discipline.md`. In one table:

| Lesson (paid for by) | Mechanism in 2.0 |
|---|---|
| Measure the floor that will judge the comparison, and name its estimand (07, 09) | `klein noise-floor --recipe --estimand`; the schema-3 floor bar |
| Audit headroom before spending challengers (07, 08, 09) | `metric.bound`, headroom disclosure, `klein headroom ack`, the permission map as a registered cell |
| Put a positive control on the ladder, sized to fail (07, 08, 09) | referee check 4; `evaluate_test` controls |
| A selection guard is not a significance test (08, 09) | `metrology.family_maxt`; the exploratory ceiling for unguarded families |
| Pre-script the branch you think will not fire (08, 09) | predictions with rules; `stop:`; the sealed dry-run |
| Keep the crash rows (07, 08) | `measured | crash` retained; registered sweeps keep crash sidecars |
| The ledger catches its operator (09) | contract-driven splits, printed fingerprints, `verify --numbers`, errata |
| Detectable is not actionable (08, 09) | the `materiality:` block; the vocabulary scan |

## 7. Positioning

| | Claude Science | Kosmos (arXiv:2511.02824) | Curie (arXiv:2502.16069) | autoresearch | Klein 2.0 |
|---|---|---|---|---|---|
| Runs where | hosted workbench; laptop / HPC / Modal compute | hosted | local | local | local, any machine, from git |
| Model | Claude | its own | any | any | any — Klein calls no model API |
| Unit of work | a session with plan and connectors | a structured world model | an experiment with rigor modules | one mutable script, fixed budget | a typed inquiry with a notary |
| Verification | reviewer agent (same model) | statements cited to code or literature | intra- and inter-agent rigor | keep / discard | hash and ledger arithmetic with no model, then an independent referee |
| Pre-registration | plan first | — | — | — | contract-hashed predictions with rules |
| Audit by a stranger | code, environment, message history | citation trails | — | git history | a git history whose every claim, number and decision resolves |

Klein does not compete with a workbench on connectors or scale. It is the
lab-notebook discipline a workbench's agent — or any other agent — can run *inside*,
and the thing a stranger can check afterwards without trusting the agent.

## 8. Limitations and non-goals

Klein cannot make a model reason better; it makes failures detectable and forces the
missing behaviours. It runs one bounded subprocess at a time and does not schedule,
parallelize, or learn a policy across runs; a cluster job is a blocking wrapper. It
does not execute notebooks. The slate ritual is deliberately a thinking procedure,
not a tournament. The referee is independent by mechanism, not by magic: a fresh
session of the same model is the lowest rung of the ladder and is recorded as such.
A measured floor bounds honesty, not power. And a lock verifies that numbers have
homes, not that the homes were the right places to look.

## 9. Compatibility

Schema-2 studies verify under schema-2 rules forever; none of the schema-3 checks are
enforced on them. Legacy locks (schema 1) verify as numbers ledgers and are never
rewritten. Version-1 studies are readable at tag `v1.3.0`. Nothing that was ever
notarized is rewritten, including the release history: `v1.3.0` was tagged
retroactively with a message naming its own bookkeeping defect.

## 10. Roadmap

2.1: study 14, a benchmark replication of a public insurance dataset via the OpenML
adapter (in-sample reproduction plus a registered out-of-sample non-reproduction);
a `discover` exhibit that closes with the `test` study it sketches; modality helpers
for sequence and graph leakage; a `verify` mode that re-checks a whole repository of
studies. Open questions: how much of the referee rubric can become arithmetic
without becoming a checklist that a model games; whether evidence-use rates predict
anything about a study's later replication; and what the ladder of independence is
worth when every rung is a language model.
