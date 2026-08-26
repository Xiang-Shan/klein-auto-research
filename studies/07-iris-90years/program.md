# Program — 07-iris-90years

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: On Fisher's 100 hard-pair iris rows (versicolor vs virginica, target
  `is_virginica`), does any of four pre-registered post-1936 challengers — logistic
  regression, kNN, SVM-RBF, HGBT — improve `val_brier` over the 1936 Fisher/LDA anchor
  by at least the measured split-lottery floor on the declared group-aware split, and is
  petal-only LDA within that floor of the all-four-feature LDA?
- Track: `primary`
- Primary metric: `val_brier` (lower is better; minimum meaningful delta
  **TO BE MEASURED at Phase 0** — currently 0, which is the only honest value before the
  split-lottery has run)
- Auxiliary, recorded every run, never a keep/discard input: `val_auc`, `val_logloss`
  (+ pr_auc, lift@10, f1). AUC pegs at this n and logloss is clipping-epsilon dominated
  for kNN — both are evidence, neither is the verdict.
- Guardrail: `wall_seconds` max 30.
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## What this study IS and IS NOT (read before writing any prose)

A **prospectively locked, sealed confirmation run after documented scouting**. The
2026-08-24 design panel measured this dataset; that scouting adaptively shaped the metric,
the candidate set, the floor recipe, and both narratives. `scouting_ledger.md` — committed
BEFORE the CONSULT gate record — discloses every scouted number *and* every adaptive
influence. A fresh seed does not restore blindness; its honest, narrower value is that
this specific partition, and therefore these specific sealed 20 rows, were never scored
during scouting.

BANNED everywhere: 独立复现 / blind / untouched / virgin data; tie / equivalent / no
difference / 打平 / 一样好 / 等价; any translation of "did not clear the floor" into
equality. See `study.yaml:claims_discipline` for the sanctioned phrasings.

## Data and split

- Source: `csv:data/prepared/iris_hard_pair.csv`, built by `prepare.py` from
  `sklearn.datasets.load_iris`; a byte-identical fixture is committed under `fixtures/`.
- 100 rows × 7 cols: four measurements, `species` (sklearn's 3-class code, kept from the
  first write — the registered crash rung needs it, and adding it later would move the
  DATA fingerprint), `is_virginica`, `group_id`.
- Split `kind: group`, seed **20260828**, 0.20 / 0.20. Materialized 2026-08-24:
  train 60 (33 virginica / 27 versicolor), development 20 (10/10), sealed test 20 (7/13).
  A group split is not stratified — the sealed 7/13 base rate is documented, not fixed.
- **Twin ruling.** Hard-pair rows 51/92 (iris rows 102/143, both virginica) are identical
  at (5.8, 2.7, 5.1, 1.9) and are the only duplicated row-content in the hard pair. At
  0.1 cm resolution identical measurements do not prove duplicated record entry, and no
  provenance evidence exists either way. We do not delete historical data: both rows share
  one `group_id`, so they always travel together. The leakage mechanism is removed
  regardless of which explanation is true; the audit passes without deletion and without
  an override.
- Gate 1 records the prepared-data SHA-256 and the split-policy fingerprint.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/07-iris-90years`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track primary --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Tuesday ack window — the three commands, verbatim

Rehearsed 2026-08-24 on a scratch copy of this directory: all three recorded first-try,
exit 0. Run from the **repository root**, on branch `experiments/07-iris-90years`, with a
clean working tree. Replace `<actor>` with the acknowledging person's name.

```bash
uv run --locked klein gate record consult --study studies/07-iris-90years \
  --acknowledged-by <actor>

uv run --locked klein gate record data --study studies/07-iris-90years \
  --acknowledged-by <actor> \
  --note "cautions accepted: species is a deliberate target proxy for the registered crash rung (never a feature); group_id is ID-like by construction; n=100 with a 20-row development partition; sealed partition is 7/13"

uv run --locked klein gate record method --study studies/07-iris-90years \
  --acknowledged-by <actor> \
  --note "papers leg pending: Fisher 1936 and Bezdek 1999 are citation-verification-pending and are verified Tuesday morning before any deliverable cites them"
```

Then `uv run --locked klein preflight --study studies/07-iris-90years` (expect all green
once the tree is clean and the branch is `experiments/07-iris-90years`).

Two notes on the `--note` arguments, both mechanical rather than stylistic:

- The **data** note is the card's own suggested wording; the gate stores it as the
  recorded reason the cautions were accepted.
- The **method** note MUST contain the word **papers**. `method_card.md` asserts
  `triad.papers: false` (both references are citation-verification-pending), and
  `klein gate record method` refuses an incomplete triad unless the `--note` names each
  missing leg. If the references are verified before the window, flip `refs_verified`
  and `triad.papers` to `true` in the card and the note becomes optional.

Two things that happen BEFORE the window, not inside it:

1. The clean-room leakage audit re-runs in a fresh isolated context (it has not read
   `program.md`) and its output replaces the pre-check quoted on the data card.
2. The two references are verified; if they pass, the card's frontmatter is updated.

## Phase-0 measurement sequence (mandatory before any challenger rung)

1. E0001 anchor (LDA 1936, four features, fit on train only) — sets the frontier.
2. `sweeps/kseed_floor.py` — the protocol-prescribed k-seed fit-noise sweep. Expected
   output: **std exactly 0**, because LDA is closed-form. The degenerate result is
   committed as the documented deviation, never skipped. (The 「1936 没有随机种子」 beat.)
3. `sweeps/split_lottery.py` — the real recipe: k = 20 group-aware re-draws of the **80
   non-sealed rows** into 60/20, sealed 20 frozen out of every draw; per draw fit the
   anchor and each family and record development Brier plus every paired delta.
4. `minimum_delta = 2 × std(anchor development Brier across the 20 draws)`, rounded UP to
   3 dp. Paste the measured `noise_floor:` block into `study.yaml` (with
   `method: "split-lottery"`), then **re-record CONSULT** with
   `--note "minimum_delta set from the measured split-lottery floor"`.
5. Only then may E0003 and beyond run.

The floor is an actionability threshold — "the incumbent's own score wobbles this much when
only the split changes" — conditional on these 100 flowers. Not a CI, not a test. The
ledger judges the declared-split delta; findings report declared-split delta AND lottery
spread, labelled.

## Sealed look — pre-registered scope

One track, one seal. E0009 confirms the **incumbent's LEVEL** on the 20 untouched rows.
The ladder gap is **exploratory by construction** (the losing families never get a sealed
value) and the verdict card says so. The sealed partition's base rate is 7/13, not 10/10;
the level is read against that, not against the development base rate.

**Both sealed spoken lines are written HERE, before the run** — the outcome cannot choose
the sentence:

- *No move (near-certain, and the one we want):*
  「它没动——这正是你该想要的无聊结果，也是我唯一被允许说出口的那句话。」
  ("It didn't move. That is exactly the boring result you should want, and it is the only
  sentence I am allowed to say.")
- *It moved beyond ±2× the floor:*
  「它动了，超过了地板的两倍。那么今晚的结论只剩一句诚实的话：这台仪器在二十行上给不出
  可签字的结论——这一条也记在案上。」
  ("It moved, by more than twice the floor. Then tonight's conclusion is one honest
  sentence: on twenty rows this instrument cannot produce a signable conclusion — and that
  goes on the record too.")

Sell the constraint, not the number. Notarization (task worklog, outside this tree):
append intent + `git rev-parse HEAD` before the sealed run; append the new HEAD + the
sealed value after; print `klein verify` + HEAD SHA on the verdict card.

## Both story branches, pre-committed before any run

Neither branch may be chosen after seeing results — they are both written now, and the
S8 moral survives either one.

- **Branch A — "no challenger earned a keep; the differences sit inside the churn."**
  Every challenger's delta is smaller than the floor. Spoken form: 「没有一个挑战者的改进
  爬过地板。」 NOT "they tied", NOT "they're equally good" — the estimand does not license
  that sentence.
- **Branch B — "challengers measurably WORSE on this draw."** The scouted seed-42 point
  deltas leaned this way. Spoken form: 「在这一次抽签上，挑战者们输得看得见。但请注意我
  没说'它们比较差'——我说的是'在这一次抽签上'。」
- **Shared moral (S8):** a numerical #1 is not a signable claim. The incumbent stands by
  default, not by victory — 「在位者站住了——不是打赢，是没人打倒它」.
- **RQ3 failure branch:** if sepal-only LDA does not clear the floor, the instrument
  cannot resolve differences of this size at n=100; every within-floor claim in the study
  is downgraded, and that downgrade becomes the honest headline slide.

## Registered estimand (governs every claim)

Under this pre-registered contract — this dataset (n=100, group-constrained splits), this
declared split (seed 20260828), `val_brier`, and δ = the measured split-lottery floor —
challenger X did or did not produce an improvement ≥ δ over the 1936 anchor. klein's
one-sided keep/discard disposition answers exactly this. It is a statement about what this
protocol licenses you to act on, not about population-level performance.

Explicitly NOT claimed: population-level equivalence or superiority of any pair. At 20
development rows that estimand is unanswerable (design-phase paired bootstrap: all six
intervals wider than the floor band). One pre-scripted spoken sentence carries it:
「在 20 行的考卷上，'两个方法一样好' 这句话谁也没资格说——我们说的是更小的一句：没有一个
挑战者的改进，大到值得你行动。」 The comparison family is **6** and findings say so.

## Decisions (append-only)

- 2026-08-24 — schema-v2 study scaffolded; gates pending.
- 2026-08-24 — CONTRACT AMENDMENT AT SCAFFOLD (framework friction, logged): `klein new`
  has no `--split-seed` flag and hardcodes `seed: 42` in the scaffold template, while
  `study_state.json` snapshots the split fingerprint at scaffold time and
  `reconcile_state` never tops it up. Setting the pre-committed fresh seed 20260828
  therefore orphaned the recorded fingerprint. Fixed BEFORE any gate or run by
  regenerating `study_state.json` + `events.jsonl` through the library's own
  `initial_state` / `append_event` (exactly the calls `klein new` makes), so the state is
  what a scaffold of THIS contract would have written. Nothing had been recorded yet.
  Suggested upstream fix: a `--split-seed` flag, or reconcile the split fingerprint while
  no gate is recorded.
- 2026-08-24 — twin-row ruling adopted: group-aware split, no deletion, n stays 100. The
  clean-room audit's duplicate check is STRADDLE-only, so co-located duplicates pass; the
  group split makes co-location structural rather than lucky.
- 2026-08-24 — `species` (3-class) kept in the prepared artifact from the first write.
  It is a PERFECT PROXY for `is_virginica` and is therefore a documented WARN on the data
  card with an explicit mitigation: `train.py` names its feature columns literally and the
  anchor asserts the feature set. The column exists so E0002's crash is real evidence
  rather than a story.
- 2026-08-24 — metric locked: `val_brier` (lower). Study 06 needed three consult
  re-records over exactly this kind of mid-run edit; `study.yaml` is a hash-frozen gate
  artifact, so the metric is decided once, here, with the reasons written down.
- 2026-08-24 — Equivalence-CI disposition REJECTED on ESTIMAND grounds (not narrative
  grounds): this study registers a protocol-level decision claim, which klein's one-sided
  rule answers exactly; equivalence CIs answer a population-level estimand this study does
  not register and, at 20 rows, cannot answer. The refuter's executed interval analysis is
  ADOPTED as the documentation of that impossibility (a stated limitation plus one spoken
  sentence), not discarded. Also rejected: a family-wise 3× bar (same estimand confusion —
  family honesty means stating the family size, 6, in findings); per-method floors (an
  unstable method buys itself a wide band); `UNDETERMINED` as a fourth machine status
  (`VALID_DISPOSITIONS` is frozen, and slide-only vocabulary contradicting `results.tsv`
  would break ledger-as-audit-trail).

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase adaptive-1 slate (2026-08-24, pre-registered)

`adaptive-1` has `max_experiments: 1` on purpose: the phase is the anchor plus metrology,
and the two floor sidecars are measurement sweeps that promote no winner and no ledger row
(`references/sweep-rules.md` carve-out). The slate is scored anyway so the choice is on
the record.

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | LDA 1936, four features, fit on train only — the anchor; sets the frontier and the floor's subject | 1 | 3 | 3 | 7 |
| 2 | k-seed fit-noise sweep of candidate 1 — registered prediction: std exactly 0 | 3 | 3 | 2 | 8 |
| 3 | split-lottery floor, k=20 group-aware re-draws of the 80 non-sealed rows — yields `minimum_delta` | 3 | 3 | 3 | 9 |
| 4 | scratch-vs-sklearn direction check (cosine ≥ 1 − 1e-12) — METHOD-gate artifact, scores nothing | 2 | 3 | 2 | 7 |
| 5 | constant-predictor / shuffled-label chance probe | 1 | 3 | 1 | 5 |
| 6 | stratified-split counterfactual (what the twins would have done) | 2 | 3 | 2 | 7 |

Chosen: **1 as the single ledger transaction**, then 2 and 3 as measurement sidecars in
that order (2 must run first — the protocol prescribes it, and its degeneracy is itself a
registered prediction). 4 is quarantined into the METHOD gate and scores nothing. 5 is
covered mechanically by `python -m kleinlib.leakage` at the DATA gate. 6 is DEFERRED to
findings § ⑦ — the twin ruling is already decided and re-litigating it with a run would be
in-flight curiosity, not pre-registration.

### Phase adaptive-2 slate — to be recorded at the phase boundary

The seven rungs are pre-registered in `study.yaml:phases` and
`predictions_to_falsify`; the slate table is written at the adaptive-1 → adaptive-2
boundary, against a refreshed `playbook.md`.
