# Exploration protocol — looking, on the record

Research starts with looking. This protocol says how to look without spoiling what you
will later claim. It applies at any stage, including before Gate 0.

## 1. Three ways to touch a study

| | What it is for | Needs the gates? | Leaves | Can support a claim? |
|---|---|---|---|---|
| **probe** — `klein probe` | a look: a plot, a rough fit, "what happens if" | no | a line in `probes.jsonl`, a log | **never** |
| **run** — `klein run-one` | one falsifiable idea, judged by the contract | yes | a manifest, a result row | yes |
| **smoke** — `KLEIN_SMOKE=1 python <entrypoint>` | "does the code start?" | no | nothing | never |

A probe is the only sanctioned way to *look at data or behaviour* outside a run. Anything
else — a notebook cell, an ad-hoc script — is off the record, and what it showed you
cannot be told apart later from what you predicted.

## 2. Running a probe

```bash
klein probe --study studies/NN-slug --note "is the target skewed?" -- python look.py
klein probe --study studies/NN-slug --list
```

- The command runs once, bounded by the contract's `max_run_seconds`.
- The child process sees `KLEIN_PROBE=1`, `KLEIN_PROBE_ID` (`X0001`) and
  `KLEIN_PROBE_DIR`. Write figures and tables into `KLEIN_PROBE_DIR`: they are committed
  with the probe, so the working tree stays clean.
- `probes.jsonl` gains one hash-chained record: the command, the sha256 of every study
  file it named (the script that did the looking), the sha256 of the log, your note.
- The probe commits only its own files. It never creates a result row, a manifest or a
  disposition, and it never moves a frontier.

## 3. What a probe may not do

- **Read the sealed partition.** Under `KLEIN_PROBE=1`, `kleinlib.data.load_partition`
  refuses `final_test` and `kleinlib.data.contract_split` returns the sealed partition
  empty. A script that opens the raw file itself is not stopped — but its hash is on the
  record, and a referee reads it. Do not.
- **Support a claim.** A probe id (`X0001`) is not an evidence id; `klein claims` will not
  resolve it. Findings may mention a probe as a *lead* (§③ surprises, §⑦ next), never as
  the reason a claim is true.
- **Replace a run.** If a look is worth believing, it is worth predicting: write the
  prediction with its rule in `study.yaml`, then let a run that did not know the answer
  decide it.

## 4. The explore → predict → test funnel

1. **Explore.** Probe freely on train and development data. Note what you were looking
   for *before* you look (`--note`).
2. **Predict.** Turn what you saw into a registered prediction with an arithmetic rule.
   Before Gate 0 this is ordinary contract drafting. After Gate 0 it is a contract
   amendment, recorded as one — and a prediction registered after a probe of the same
   development data is confirmed only by evidence the probe could not have seen: the
   sealed data, or a replication.
3. **Test.** `klein run-one --tests P#`. The notary applies the rule.

## 5. What the gates record

- **Gate 0 (consult)** stores how many probes existed when the question was acknowledged
  and the hash of the last one. "What was looked at before the contract was fixed" is
  then a fact on the record, not a recollection. `scouting_ledger.md` remains the place
  to *explain* what the probes (and anything read elsewhere) showed.
- **`klein verify`** adds a `probe ledger` line when `probes.jsonl` exists: the chain is
  intact, every log still matches its hash, and the probes that preceded Gate 0 are the
  same ones. A study that never probed gets no such line.
- **`klein map`** lists probes as leads, apart from the evidence.

## 6. For the referee

Read `probes.jsonl` before the predictions. For each prediction, ask: was the thing it
predicts already visible in a probe that ran earlier on the same data? If so, the
prediction is a description of something seen, and only its sealed or replicated
confirmation counts.
