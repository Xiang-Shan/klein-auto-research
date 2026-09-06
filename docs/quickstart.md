# Klein quick start

One complete study, end to end, on synthetic data with a known truth. The commands run
in minutes; the thinking between them is yours.

Every command below was executed, in this order, in a fresh clone of this repository.
The outputs are real and trimmed; long hashes and machine paths are shortened. The
study id used throughout is `16-quickstart-walkthrough`.

---

## 0. Install, check the machine, verify a study that already exists

Start by proving the framework works before you ask it to do anything. `klein doctor`
never fetches and never mutates a study; `klein verify` re-checks a shipped ledger from
its own receipts.

```bash
git clone https://github.com/Xiang-Shan/klein-auto-research
cd klein-auto-research
uv sync --locked --extra encoders
uv run --no-sync klein doctor
uv run --no-sync klein verify --study studies/00-known-truth-quickstart
```

```
[OK] python: 3.13.3 at <repo>/.venv/bin/python
[OK] git: git version 2.39.3 (Apple Git-146)
[OK] extra: encoders: installed
[WARN] extra: gbdt: missing lightgbm, xgboost, catboost — uv sync --locked --extra gbdt
[OK] tutorial renderer: installed (pygments, ziamath, latex2mathml)
summary: 11 checks, 4 not-ok (never fetches; exit code reflects --strict only)
```

```
[OK] referee gate: PASS-WITH-NOTES — klein-referee, independent-of-experimenter: no
[OK] predictions closure: 5 registered prediction(s), all adjudicated
[OK] claims numbers: every pinned value is found in its artifact
[OK] findings numbers: all 50 scanned numerals trace to 13 pinned source(s)
[OK] tutorial numbers: all 59 rendered numerals trace to a pinned source
summary: 36 checks, 0 failed
```

The `[WARN]` lines are optional extras; nothing below needs them. Now look at what a
finished study produces. The report is one self-contained file — no CDN, no fonts, no
server — so open it straight from disk (`open` on macOS, `xdg-open` on Linux):

```bash
ls -lh studies/00-known-truth-quickstart/report/index.html
```

**What just happened.** `verify` re-derived 36 checks from a ledger somebody else
wrote — gates, hashes, an event chain, every numeral in the findings traced back to a
pinned artifact. That is the whole promise in miniature.

---

## 1. Scaffold the study, and get off `main`

```bash
uv run --no-sync klein new 16-quickstart-walkthrough \
  --kind predict --modality tabular --profile generic \
  --goal "On a synthetic table whose Bayes-optimal AUC is known from the declared generating process, does a linear model handed the true interaction term beat a boosted tree that is told nothing?" \
  --domain synthetic --target y --task-type classification --family linear \
  --audience "Someone running their first Klein study end to end." \
  --metric val_auc --goal-direction higher \
  --data "synthetic:prepare.py" --split-kind stratified --split-seed 20260906 \
  --track primary --max-run-seconds 60
git switch -c experiments/16-quickstart-walkthrough
```

```
scaffolded <repo>/studies/16-quickstart-walkthrough
next: git switch -c experiments/16-quickstart-walkthrough
```

The three axes are the whole typing system: `--kind` is the question's shape,
`--modality` the evidence source's shape, `--profile` the audience whose vocabulary is
honest here. They decide the entrypoint's name, which data-gate card you must fill, and
which headings the findings and the report carry — see
[`.claude/skills/klein/references/inquiry-model.md`](../.claude/skills/klein/references/inquiry-model.md).

**What just happened.** You created a schema-3 study directory and a branch. Studies
run on `experiments/<id>` branches, never on `main`; the loop enforces it.

---

## 2. What the scaffold contains

```bash
ls studies/16-quickstart-walkthrough
```

```
aux_metrics.tsv   models       program.md         results.tsv          study.yaml
events.jsonl      playbook.md  report             runs                 study_state.json
figures           prepare.py   research_plan.md   scouting_ledger.md   sweeps
train.py
```

| File | What it is for |
|---|---|
| `study.yaml` | the machine contract: axes, tracks, metric, split policy, phases, predictions |
| `prepare.py` | writes the prepared artifact; obtains partitions from the contract, never a literal seed |
| `train.py` | the entrypoint, and the ONLY per-experiment mutable surface |
| `program.md` | the living lab notebook: roster, questions, phase plan, dated decisions |
| `playbook.md` | the rolling state of play: current best, ruled-out directions, next candidates |
| `scouting_ledger.md` | everything looked at BEFORE the consult gate, so no prediction can claim a surprise it already knew |
| `research_plan.md` | the plan the consult gate hashes |
| `results.tsv` | the derived ledger — generated from the run manifests, never hand-edited |
| `events.jsonl`, `study_state.json` | append-only, self-verifying audit state — also never hand-edited |
| `runs/`, `models/`, `figures/`, `sweeps/`, `report/` | manifests, model blobs, figures, sweep sidecars, the tutorial |

`prepare.py` and `train.py` arrive as stubs that raise `NotImplementedError`. You write
them.

---

## 3. CONSULT — write the contract, then record Gate 0

Fill in `study.yaml`: the research question with its prior, and the **predictions**,
each with an arithmetic rule on a key the entrypoint will print. Register them now,
before any evidence exists — that is the entire point.

```yaml
predictions:
  - id: P1
    track: primary
    statement: "a logistic regression on the raw features cannot reach the known Bayes ceiling: more than one measured floor of distance is left"
    rule: {key: gap_in_floors, op: ">", value: 1}
    inconclusive_if: "minimum_delta is still 0, so train.py prints no gap_in_floors line"
```

Four were registered here: P1 on the anchor's distance to the ceiling, P2 on the lift
the interaction buys, P3 on the boosted tree failing to beat it, P4 on the sealed run.
Every threshold is an integer count of *measured floors* — a unit that does not exist
yet, which is what keeps the numbers honest.

Then fill the roster and the phase plan in `program.md`, disclose anything you already
looked at in `scouting_ledger.md`, and record the gate:

```bash
uv run --no-sync klein gate record consult \
  --study studies/16-quickstart-walkthrough --acknowledged-by quickstart-reader
```

```
recorded gate consult
```

**What just happened.** The gate hashed `study.yaml`, `research_plan.md` and
`program.md` and committed them. A prediction added later is now visible as a gate
re-record with a reason. Protocol:
[`.claude/skills/klein/references/consult-protocol.md`](../.claude/skills/klein/references/consult-protocol.md).

---

## 4. DATA — Gate 1, the GIGO guard

Write `prepare.py`. Two rules matter more than the rest: read the seed from the
contract (`data.split.seed`), and take partitions from `kleinlib.data.contract_split`.
A literal seed in an evaluator is a BLOCKER — a study once measured the wrong rows for
an entire ledger lane that way.

```bash
cd studies/16-quickstart-walkthrough
uv run --locked python -u prepare.py
uv run --locked python -m kleinlib.profile_fallback data/prepared/prepared.csv --target y
uv run --locked python -m kleinlib.leakage data/prepared/prepared.csv --target y --study .
cd ../..          # every klein verb below runs from the repo root
```

```
rows: 20000  positives: 6009
development: n=4000 positive_rate=0.3005 bayes_auc=0.851112
final_test: n=4000 positive_rate=0.3005 bayes_auc=0.859075
```

```
[OK]   split-reproduces: kind=stratified reproduces deterministically from study.yaml
[OK]   duplicate-rows: no duplicate row content straddles partitions
[OK]   metric-direction[primary]: val_auc: contract direction 'higher' matches the registry
[OK]   constant-chance[primary]: val_auc=0.5000 for the constant predictor
[OK]   shuffled-chance[primary]: val_auc=0.5070 for the label-shuffled predictor
6/6 checks passed: clean
```

Copy [`.claude/skills/klein/assets/data-card-template.md`](../.claude/skills/klein/assets/data-card-template.md) to the study as
`data_card.md`, fill the profile table by **value pattern** (never by dtype — a
`Yes`/`No` column that pandas types as a string is exactly what this catches), paste
the leakage lines above into the four-row audit, rank the issues, and write the
decision box. Then:

```bash
uv run --no-sync klein gate record data \
  --study studies/16-quickstart-walkthrough --acknowledged-by quickstart-reader \
  --note "in-silico scope accepted; carried into every claim"
```

**What just happened.** The gate fingerprinted the prepared bytes and the realized
partitions. Every later run prints a `split_fingerprint:` that the notary compares with
this one. Protocol: [`.claude/skills/klein/references/data-gate-protocol.md`](../.claude/skills/klein/references/data-gate-protocol.md).

---

## 5. METHOD — Gate 2, the triad

Copy [`.claude/skills/klein/assets/method-card-template.md`](../.claude/skills/klein/assets/method-card-template.md) to `method_card.md` and
write the five parts in order: intuition → math core → minimal implementation plan →
when it pays → verified references. Assert the triad in the frontmatter; the gate
refuses while a leg is false unless your `--note` names the missing one.

```yaml
refs_verified: true
triad:
  theory: true      # §2 has the notation table and a display equation
  papers: true      # every row of references.yaml is verified: true
  practice: true    # §3 names the runnable plan train.py will realize
```

Write `references.yaml` beside it. Each entry needs `verified: true`, who verified it
and when — the two here were checked by resolving their DOIs to the publisher landing
pages. An unverified reference is a liability, not a citation.

```bash
uv run --no-sync klein gate record method \
  --study studies/16-quickstart-walkthrough --acknowledged-by quickstart-reader
```

**What just happened.** Modeling was hard-blocked until all three gates were recorded.
Protocol: [`.claude/skills/klein/references/method-gate-protocol.md`](../.claude/skills/klein/references/method-gate-protocol.md).

---

## 6. Phase 0 — measure the keep bar, then preflight

Before the gates were recorded, `klein preflight` said exactly why the loop was shut:

```
[FAIL] working tree: ?? studies/16-quickstart-walkthrough/prepare.py, train.py, …
[FAIL] gate consult: status=pending
[FAIL] gate data: status=pending
[FAIL] gate method: status=pending
[FAIL] prepared-data fingerprint: current=b2b44b65…; recorded=None
summary: 21 checks, 5 failed
```

Now measure the floor. `sweeps/noise_floor.py` re-draws the train/development partition
ten times at the contract's own proportion, refits the anchor rung, and writes a
sidecar. The spread of those ten scores — not a number you like the look of — becomes
`minimum_delta`.

```bash
cd studies/16-quickstart-walkthrough
uv run --locked python sweeps/noise_floor.py
cd ../..
uv run --no-sync klein noise-floor --study studies/16-quickstart-walkthrough \
  --track primary --sidecar studies/16-quickstart-walkthrough/sweeps/split_lottery.sidecar.tsv \
  --recipe split-lottery --estimand marginal-resplit
uv run --no-sync klein sweep register split_lottery \
  --study studies/16-quickstart-walkthrough \
  --sidecar sweeps/split_lottery.sidecar.tsv --script sweeps/noise_floor.py
```

```
estimand=marginal-resplit  recipe=split-lottery  k=10  mean=0.787904  std=0.00733565
suggested minimum_delta=0.0146713

      minimum_delta: 0.0146713   # = max(2*std, range/2), std 0.00733565
      noise_floor: {k: 10, std: 0.00733565, range: 0.023555, ...}
next: edit study.yaml, then re-record the consult gate --note "..."
```

Paste that block into `study.yaml`. This study also declares a bound, which arms the
detection-limit audit — the development partition's Bayes AUC, which `prepare.py`
computed from the declared generating process:

```yaml
      bound:
        ideal: 0.851112
        on_infeasible: ack
```

Re-record the consult gate with a reason, commit the fixed machinery, and preflight:

```bash
uv run --no-sync klein gate record consult --study studies/16-quickstart-walkthrough \
  --acknowledged-by quickstart-reader \
  --note "minimum_delta set from the measured noise floor; metric.bound.ideal set to the development partition's Bayes AUC"
git add studies/16-quickstart-walkthrough
git commit -m "16-quickstart-walkthrough: the fixed machinery (prepare.py, train.py, references.yaml)"
uv run --no-sync klein preflight --study studies/16-quickstart-walkthrough
```

```
[OK] git branch: current='experiments/16-quickstart-walkthrough'
[OK] working tree: clean
[OK] gate artifact hashes: match
[OK] split fingerprint: current=a479c5f8…; recorded=a479c5f8…
[OK] headroom: track 'primary': bound declared; no incumbent yet — audited at first keep
summary: 21 checks, 0 failed
```

**What just happened.** The loop refuses a dirty tree, so the fixed machinery is
committed before any experiment. `train.py`'s two candidate constants are committed
parked at whichever rung you like — the first experiment's edit then really is a diff,
and `run-one` refuses an unchanged surface. Protocols:
[`.claude/skills/klein/references/sweep-rules.md`](../.claude/skills/klein/references/sweep-rules.md) and
[`.claude/skills/klein/references/phase-ritual.md`](../.claude/skills/klein/references/phase-ritual.md).

---

## 7. The loop — three candidate transactions

The whole per-experiment diff is two constants:

```python
CANDIDATE = "logreg_raw"          # E0001: the anchor
REFERENCE = None
```

The rest of `train.py` is fixed machinery, modelled on study 00's: it loads the prepared
artifact, fits the candidate, and hands the predictions to `kleinlib.eval.evaluate(...)`,
which prints the block the notary reads — `split_fingerprint`, `primary_metric`,
`wall_seconds` — plus whatever you pass as `extra` (the `gap_in_floors` line that P1's
rule keys on comes from there).

Edit them, smoke-check off the loop, then hand the candidate to the notary:

```bash
cd studies/16-quickstart-walkthrough
KLEIN_SMOKE=1 uv run --locked python train.py       # the ONE sanctioned off-loop check
cd ../..
uv run --no-sync klein run-one --study studies/16-quickstart-walkthrough --track primary \
  --description "anchor: logistic regression on the raw features" --tests P1
```

```
split_fingerprint: 7fc80089…
primary_metric:    0.789861
bayes_auc: 0.851112
gap_to_ideal: 0.061251
gap_in_floors: 4.1749
E0001: keep metric=0.789861 commit=9eb82ab0
```

Second candidate: the same linear model, handed the generating process's own product
term, with the anchor named as the reference so both are refitted on the same rows
inside one run.

```bash
uv run --no-sync klein run-one --study studies/16-quickstart-walkthrough --track primary \
  --description "the DGP's own interaction term, handed to the linear model" --tests P2
```

```
gap_in_floors: 0.0157
reference_auc: 0.789861
delta_in_floors: 4.1592
E0002: keep metric=0.850882 commit=90841279
```

The third candidate — a boosted tree told none of the true terms — was refused before
it could run:

```
klein: error: track 'primary': headroom (0.850882 - 0.851112) / 0.0146713 = 0.016 < 1
— no keep is arithmetically possible on this frontier (not even a perfect score clears
minimum_delta); register awareness first: klein headroom ack ...
```

That is not advice, it is arithmetic: the whole distance left to the ceiling is smaller
than the floor a keep must clear. Spending the run anyway is allowed — the prediction it
adjudicates is about *failing* to clear a floor — but the closed door goes on the
record first.

```bash
uv run --no-sync klein headroom ack --study studies/16-quickstart-walkthrough --track primary \
  --acknowledged-by quickstart-reader \
  --note "run-anyway: the door is closed — E0003 cannot become the incumbent, and is spent only to adjudicate P3"
uv run --no-sync klein run-one --study studies/16-quickstart-walkthrough --track primary \
  --description "a boosted tree, told none of the true terms" --tests P3
```

```
delta_in_floors: -0.4488
E0003: discard metric=0.844297 commit=af643378
train.py restored to pre-candidate base f75b0d1a (= E0002's kept config); candidate
stays resolvable at af643378
```

Look at what the loop wrote:

```bash
cat studies/16-quickstart-walkthrough/results.tsv
uv run --no-sync klein status --study studies/16-quickstart-walkthrough
```

```
E0001  primary  0.789861  keep     9eb82ab0  anchor: logistic regression on the raw features
E0002  primary  0.850882  keep     90841279  the DGP's own interaction term; frontier improvement over 0.789861
E0003  primary  0.844297  discard  af643378  a boosted tree; did not improve frontier by minimum_delta=0.0146713
```

```
experiments: 3 (keep=2 discard=1 measured=0 crash=0)
final holdout: primary=0/1
predictions: 3 supported, 0 refuted, 0 inconclusive, 1 open
evidence use: 0.50 (1/2 cited)
```

Each row's `manifest.json` carries what the derived table cannot: `base_commit`,
`candidate_commit`, `code_patch_hash`, the four `fingerprints` (data, split,
split_partition, environment), `decision_reason`, and every printed metric.

**What just happened.** Three transactions, each committed before execution, each
dispositioned by arithmetic on the contract you declared. The discard is evidence and
stays resolvable in git. Record your reasoning in `program.md` as you go — `evidence
use: 0.50` above is Klein telling you a run has not been mentioned again yet.

---

## 8. The sealed run

Each track gets one look at the held-out partition. Rehearse it first; the dry-run
spends nothing and is mandatory.

```bash
uv run --no-sync klein gate record phase --study studies/16-quickstart-walkthrough \
  --phase adaptive-1 --acknowledged-by quickstart-reader \
  --note "3 of 3 experiments spent; frontier E0002; door closed at h=0.016"
uv run --no-sync klein run-one --study studies/16-quickstart-walkthrough --track primary \
  --final-test --dry-run
uv run --no-sync klein run-one --study studies/16-quickstart-walkthrough --track primary \
  --final-test --tests P4
```

```
sealed dry-run OK: primary rehearsed on development data; nothing spent
```

```
bayes_auc: 0.859075
gap_in_floors: -0.0108
delta_in_floors: 3.9335
E0004: sealed (recorded as discard — confirmation evidence, excluded from the adaptive
frontier) metric=0.859233 commit=9c0676c6
```

**What just happened.** The sealed score is a hair *above* that partition's Bayes
ceiling. Nothing broke: the ceiling is the AUC of the true probabilities on one finite
sample, and a fitted score can order those particular rows marginally better by luck.
The two are indistinguishable — a hundredth of one measured floor apart. That is why
the floor, and not the sign of a delta, decides anything.

---

## 9. SYNTHESIZE — findings, then the claims lock

Write `findings.md` from
[`.claude/skills/klein/assets/findings-template.md`](../.claude/skills/klein/assets/findings-template.md) with its seven sections: ① verdicts
carrying claim ids, ② the predictions copied from the ledger, ③ surprises, ④ advice,
⑤ the profile's implications section, ⑥ literature, ⑦ next. Then build the machine
surface underneath it.

```bash
uv run --no-sync klein claims init --study studies/16-quickstart-walkthrough
uv run --no-sync klein claims pin --study studies/16-quickstart-walkthrough results results.tsv
uv run --no-sync klein claims pin --study studies/16-quickstart-walkthrough aux aux_metrics.tsv
uv run --no-sync klein claims pin --study studies/16-quickstart-walkthrough contract study.yaml
uv run --no-sync klein claims pin --study studies/16-quickstart-walkthrough split_lottery sweeps/split_lottery.sidecar.tsv
uv run --no-sync klein claims pin --study studies/16-quickstart-walkthrough data_card data_card.md
uv run --no-sync klein claims number --study studies/16-quickstart-walkthrough anchor_auc \
  --value 0.789861 --art results --claim C1 --precision 6
# ... one `claims number` per headline value (fourteen here), then one `claims add`
# per **[Cn]** line in findings.md:
uv run --no-sync klein claims add --study studies/16-quickstart-walkthrough C3 \
  --class research-discipline --strength exploratory \
  --claim "Measure the floor before interpreting any delta: the split-lottery sweep put minimum_delta at 0.0146713, and the whole distance from the interaction rung to the ceiling is smaller than that, so every further development run on this track was arithmetically incapable of a keep" \
  --numbers minimum_delta,floor_k,floor_std --evidence sweep:split_lottery,E0002
uv run --no-sync klein claims verify --study studies/16-quickstart-walkthrough
```

```
[OK] claims artifacts: 5 pinned artifacts hash as recorded
[OK] claims presence: every claim id resolves in findings.md
[OK] claims numbers: every pinned value is found in its artifact
[OK] claims append-only: no claim or number removed or mutated across git history
summary: 7 checks, 0 failed
```

**What just happened.** Every headline number now has a home in a hashed artifact and
every claim a class, a strength and evidence that resolves. `confirmed` needs the evidence
kinds the track's `confirmation.require` names, and a confirmed claim resting on one
kind alone is flagged. Protocols:
[`.claude/skills/klein/references/synthesis-protocol.md`](../.claude/skills/klein/references/synthesis-protocol.md) and
[`.claude/skills/klein/references/claims-protocol.md`](../.claude/skills/klein/references/claims-protocol.md).

---

## 10. REFEREE, finalize, receipt

Gate 3 runs in a **fresh context, on a different model or tool or person** than the
experimenter. Hand it the study directory and nothing else; it reads `findings.md`
before `program.md`, runs the mechanical verifiers, applies the ten-check rubric, and
writes `referee_report.md` whose first two lines are machine-read:

```
Verdict: PASS-WITH-NOTES
Referee: quickstart-referee (Claude Code, claude-opus-5) · fresh context · independent-of-experimenter: no
```

Answer each note with a dated line in `program.md`, then:

```bash
uv run --no-sync klein verify --study studies/16-quickstart-walkthrough --numbers --evidence-use
uv run --no-sync klein gate record referee --study studies/16-quickstart-walkthrough \
  --acknowledged-by quickstart-reader
uv run --no-sync klein finalize --study studies/16-quickstart-walkthrough
uv run --no-sync klein verify --study studies/16-quickstart-walkthrough
```

```
finalized: confirmed
```

```
[OK] headroom: h = (0.850882 - 0.851112) / 0.0146713 = 0.016 < 1 — infeasible,
     acknowledged by quickstart-reader at 2026-09-06T07:02:14Z: run-anyway: ...
[OK] evidence use: evidence_use_rate 1.00 — all 3 non-keep run(s) and sweeps cited
[OK] convergent evidence: 1 confirmed claim(s) cite two or more evidence kinds
[OK] findings numbers: all 29 scanned numerals trace to 11 pinned source(s)
summary: 33 checks, 0 failed
```

A `FAIL` verdict cannot be recorded. If you close a study without a referee at all,
`klein finalize --no-referee --reason "..."` records the reason and labels the study
`unrefereed` forever. Protocol:
[`.claude/skills/klein/references/referee-protocol.md`](../.claude/skills/klein/references/referee-protocol.md).

---

## 11. TUTORIAL — the teaching artifact

The tutor writes seven HTML fragments; the builder does deterministic assembly.

```bash
ls studies/16-quickstart-walkthrough/report/sections
uv run --no-sync python .claude/skills/klein/scripts/build_tutorial.py \
  studies/16-quickstart-walkthrough --title "16-quickstart-walkthrough — a known truth, end to end"
uv run --no-sync klein verify --study studies/16-quickstart-walkthrough
```

```
01-question.html  02-method.html  03-data.html  04-journey.html
05-findings.html  06-coding-advice.html  07-next-steps.html
```

```
[build_tutorial] wrote <repo>/studies/16-quickstart-walkthrough/report/index.html
(110,960 bytes, 0 inlined figure(s))
```

```
[OK] tutorial numbers: all 25 rendered numerals trace to a pinned source
summary: 34 checks, 0 failed
```

Math is authored as LaTeX in empty `data-math` attributes and typeset to SVG at build
time; the winning `train.py` is included by reference (`<pre data-code="train.py">`), so
the page carries the actual bytes; `<!--LEDGER-->` becomes the results table; figures
are base64-inlined. The acceptance guard fails the build on any external URL. Protocol:
[`.claude/skills/klein/references/tutorial-spec.md`](../.claude/skills/klein/references/tutorial-spec.md).

---

## 12. Optional — the generation layer

Everything above audits the *verification* half of research. The opt-in generation
layer records the other half: what you committed to **before** the evidence existed.
It is schema-3 only, and a study that does not opt in is untouched by it.

Opt in on a **fresh** study, before the consult gate — a commitment registered after
seeing what it was supposed to constrain constrains nothing.

```bash
uv run --no-sync klein new 17-generation-demo \
  --kind predict --modality tabular --profile generic \
  --goal "Repeat the known-truth ladder with the generation layer switched on: does every run carry an admission receipt filed before it ran?" \
  --domain synthetic --target y --task-type classification --family linear \
  --audience "A reader who wants to see the opt-in generation layer on a real study." \
  --metric val_auc --goal-direction higher \
  --data "synthetic:prepare.py" --split-kind stratified --split-seed 20260906 \
  --track primary --max-run-seconds 60
git switch -c experiments/17-generation-demo
git add studies/17-generation-demo
git commit -m "17-generation-demo: scaffold"
uv run --no-sync klein generation init --study studies/17-generation-demo \
  --actor quickstart-reader --tool "Claude Code" --model "claude-opus-5" \
  --session "quickstart-walkthrough"
```

```
generation enabled: G0001 anchored at core sequence 1, manifest 4a02f511…,
0 capability/ies declared
```

(`init` needs a clean tree — commit the scaffold first. Ten capabilities can be
declared here; with none, you get the admission discipline alone.)

Then set the study up exactly as steps 3–6, and file one admission receipt before every
`run-one`:

```bash
uv run --no-sync klein generation check --study studies/17-generation-demo \
  --action run --track primary --tests P1 --actor quickstart-reader \
  --tool "Claude Code" --model "claude-opus-5" --session "quickstart-walkthrough"
uv run --no-sync klein run-one --study studies/17-generation-demo --track primary \
  --description "anchor: logistic regression on the raw features" --tests P1
```

```
G0002 admitted: run on primary — object 6d828549…
```

The receipt binds the intended action to the exact bytes of the mutable surface:

```json
  "intended_action": {"kind": "run", "tests": ["P1"], "hypothesis_id": null},
  "surface_files": [["train.py", "6b20cfb1…"]],
  "verdict": "admitted"
```

If the check refuses, the refusal itself is written, hashed and committed — a refusal is
evidence. Afterwards, the layer audits itself into a **separate** receipt, and the label
needs both audits passing at the same HEAD:

```bash
uv run --no-sync klein generation verify --study studies/17-generation-demo
uv run --no-sync klein verify --study studies/17-generation-demo
uv run --no-sync klein generation label --study studies/17-generation-demo \
  --actor quickstart-reader --tool "Claude Code" --model "claude-opus-5" \
  --session "quickstart-walkthrough"
```

```
[PASS] generation manifest — opt-in anchored at core sequence 1 before the consult gate
[PASS] generation anchors — every anchor resolves against the core chain
[PASS] generation admission — E0001: admitted
[PASS] generation replay — every receipt was consumed by at most one run
summary: 9 checks, 0 failed, 0 warned
receipt: generation/verify_receipt.json
```

```
label issued: generation-verified @ 4a6572fd (rung local-order)
add this line to findings.md: Generation label: generation-verified @ 4a6572fd
```

**What just happened.** Chronology came from three local witnesses — the extension's
own hash chain, its anchors into the core chain, and git ancestry — never a clock. The
layer records, hashes and computes arithmetic on rows you wrote; it never proposes,
ranks, selects, schedules or retries. Protocol:
[`.claude/skills/klein/references/generation-protocol.md`](../.claude/skills/klein/references/generation-protocol.md).

---

## Where to go next

- **[`AGENTS.md`](../AGENTS.md)** — the canonical operating manual: the lifecycle, the stage map, the
  inquiry model, the experiment-loop contract, schema discipline, and the war stories
  behind every guard you met above. Read this one next.
- **[`.claude/skills/klein/SKILL.md`](../.claude/skills/klein/SKILL.md)** — the stage router and the hard rules, for driving
  Klein from Claude Code; the same table works by hand.
- **The shipped studies table in [`README.md`](../README.md)** — finished studies across the axes —
  predict, replicate and optimize; tabular, text and no data at all — plus the frozen
  schema-2 exhibits. Read
  [`studies/00-known-truth-quickstart`](../studies/00-known-truth-quickstart/) first; it is the study this walk-through is
  modelled on, and its `program.md` shows how those decisions were actually reasoned.
- **[`CONTRIBUTING.md`](../CONTRIBUTING.md)** — how to add a study, a protocol or a capability, and what the
  test suite will hold you to.
