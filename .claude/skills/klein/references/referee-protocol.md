# REFEREE — Gate 3 (independent review before finalize)

A study's author cannot audit their own conclusions; the model that ran the loop
cannot either — a hosted reviewer that is "the same underlying model checking itself"
is the critique Klein exists to answer. The REFEREE stage puts a fresh, independent
reader between SYNTHESIZE and `klein finalize`, armed with the mechanical verifiers
and a fixed rubric. Output: `referee_report.md` with a machine-read verdict; the
orchestrator records it with `klein gate record referee`.

Role: referee. Any agent or human can execute this protocol directly; Claude Code ships
it pre-wired as the `klein-referee` worker, which must run on a different model than
the experimenter.

## Rules of the seat

- **Fresh context.** The referee has not seen the loop. It receives the study
  directory and this protocol, nothing else.
- **Independence ladder — record the rung reached.** A different person > a different
  tool > a different model > a different backend of the same model > a fresh session
  of the same model. The `Referee:` line states the rung; `independent-of-experimenter:
  no` is allowed but is printed on the gate record and in the README gallery.
- **The rung is read from `program.md`'s `## Roster`.** That table — `experimenter`,
  `data-gate auditor`, `referee`, `lead`, each with its model · tool · session — is
  the only artifact that says what ran the loop, so it is what the rung claim rests
  on, and the `Referee:` line's `independent-of-experimenter` answer must AGREE with
  it. A blank `experimenter` row caps the achievable rung at "fresh session": nothing
  on the record distinguishes a different model from the same one. A missing or
  incomplete roster is a NOTE in the report (and a capped rung), never a FAIL — the
  roster is documentation, not evidence.
- **A slate-time critic is not a referee.** On a generation-enabled study the
  pre-mortem reviewer's rung is recorded separately (`references/premortem-protocol.md`)
  and does not raise the referee rung; a reviewer who is also the roster's `referee`
  FAILs that capability's own verification rather than earning independence twice.
- **Reading order is part of the method.** `findings.md` FIRST, forming a view of what
  is claimed and how strongly; then `claims.lock`, `study.yaml`, `results.tsv` and the
  manifests, `data_card.md`, `method_card.md`; `program.md` LAST — the narrative that
  makes a conclusion feel inevitable is read only after the evidence has been weighed.
  Its `## Roster` table is the one exception: a metadata header, not narrative, read
  whenever the rung is needed.
- **Read-only verbs only.** `klein verify --numbers --evidence-use`, `klein claims
  verify`, `klein status`, `klein predict list`, and a figure re-render into a
  temporary directory compared byte-for-byte. No `run-one`, no edits to any study file,
  no gate record — the orchestrator records the gate after reading the report.
- **A FAIL is never softened into a note.** If a FAIL condition holds, the verdict is
  FAIL and the report says what would clear it.

## The rubric — ten checks, each with its FAIL condition

| # | Check | FAIL when |
|---|---|---|
| 1 | **Strength matches evidence.** Every `confirmed` claim has the evidence kinds its track's `confirmation.require` demands; exploratory claims are labelled wherever prose states them. | a `confirmed` claim lacks sealed / replicated / verified evidence, or prose states an exploratory claim as fact |
| 2 | **Predictions adjudicated and reported.** Every `P#` has a verdict in state; findings §② agrees with state; every refuted prediction has a `Decision:` line in `program.md`. | an open prediction without a recorded `--allow-open-predictions` reason, a §② verdict that disagrees with state, or a refutation without a decision |
| 3 | **Negative evidence reported.** Every discard, crash and measured cell is cited in findings or program; discard clusters are written as findings. | `evidence_use_rate` below 1.0 with no explanation of the uncited ids |
| 4 | **Controls.** A positive control (a known effect the pipeline must detect) and a negative control (chance-level, shuffled or constant) exist, or their absence is declared with a reason. | neither present nor declared |
| 5 | **Multiple comparisons.** `n_comparisons` is stated for every family; a family-wise guard (`metrology.family_maxt` or Bonferroni) was applied, or the family's claims stay exploratory. | a `confirmed` claim drawn from an unguarded family |
| 6 | **Pre-registration integrity.** Consult-gate re-records are listed with reasons; no prediction's contract hash post-dates the run that adjudicated it. | a prediction added or changed after its evidence |
| 7 | **Numbers traceable.** `klein verify --numbers` passes; the referee hand-checks five numerals against their artifacts and every `klein:numbers-ok` marker. | any numeral with no home, or a marker whose reason does not hold |
| 8 | **References.** Every citation behind a claim is `verified: true` in `references.yaml` or marked UNVERIFIED; no UNVERIFIED reference supports a `confirmed` claim; the method card's `refs_verified` is honest. | an unverified reference behind a confirmed claim, or a citation absent from `references.yaml` |
| 9 | **Figures.** `figures/make_figures.py` re-renders pixel-identically on the platform family that rendered the committed figures (byte-identically on that very machine; another platform's PNG encoder writes the same pixels in different bytes, which `klein verify` decodes and accepts; on another CPU family a computed curve can move a pixel in its last bits, which verify reports as a `[WARN]` naming both platforms — re-render on the rendering platform before signing); the four-point figure critique of `tutorial-spec.md` passes. | a figure whose pixels do not re-render on their own platform, or a truncated axis that inflates a within-noise delta |
| 10 | **Vocabulary and scope.** The profile's banned words are absent or qualified; the floor's estimand is named; simulation claims carry their in-silico scope; measurement resolution is never called materiality. | any banned word unqualified, a missing estimand, an unscoped simulation claim, or resolution sold as materiality |

## Generation addenda

Only for a study whose `generation/manifest.yaml` exists; on every other study this
section does not apply and the `Generation:` line reads `n/a`. **The ten checks above
are unchanged** — these are additional reading obligations, not an eleventh check.

- Read `generation/verify_receipt.json` and `generation/label.json`. **Never re-derive
  a machine verdict**: the arithmetic is the layer's job and re-running it by hand is
  how two answers appear. Report what the receipt says, and whether the study's prose
  agrees with it.
- Confirm the roster's pre-mortem reviewer is not the roster's referee — that is you
  (`references/premortem-protocol.md`).
- Confirm that **accepted pre-mortem corrections reached the executed artifacts** in
  substance. The layer checks that an acceptance named a new slate version and that
  the version was the one in force; only a reader can say whether the correction
  actually fixed what the issue named. This is the check the mechanism cannot make.
- A generic critique that passes the schema, or a specific one that changed nothing
  that mattered, is a NOTE — it is exactly the failure the pre-mortem cannot detect
  about itself.

Add one line beneath the two machine-read lines of the report:

```
Generation: verified | failed | n/a
```

(`verified` when `generation/label.json` exists at this HEAD and the generation
receipt reports no failed check, `failed` when it reports any, `n/a` when the study
is not generation-enabled. It is a separate line rather than a suffix on `Verdict:`
because `klein gate record referee` parses that line whole and the core parser is
frozen.)

## The verdict

- **PASS** — all ten checks pass.
- **PASS-WITH-NOTES** — no FAIL condition holds, but the report lists notes the
  orchestrator must answer in `program.md` (a dated `Referee note:` line each) before
  `klein finalize`.
- **FAIL** — at least one FAIL condition holds. The report names the check, the
  evidence, and what would clear it; the study returns to SYNTHESIZE. The orchestrator
  may not record the gate on a FAIL.

## The report

Copy `assets/referee-report-template.md` to the study as `referee_report.md`. The first
two lines are machine-read by `klein gate record referee`:

```
Verdict: PASS | PASS-WITH-NOTES | FAIL
Referee: <actor> (<tool / model>) · fresh context · independent-of-experimenter: yes|no
```

Then the ten-row table with the evidence each check rested on (ids, file paths, the
verifier output), the notes, and — on FAIL — the clearing conditions.

Those two lines are all `klein gate record referee` reads, and a FAIL is refused
rather than recorded:

<!-- test:referee-verdict-parse:start -->
```python
from kleinlib.errors import WorkflowError
from kleinlib.state import referee_report_facts

report = (
    "Verdict: PASS-WITH-NOTES\n"
    "Referee: r-2 (opus, a different model than the experimenter) \u00b7 fresh"
    " context \u00b7 independent-of-experimenter: yes\n"
    "\n# Referee report \u2014 10-hubble-1929-replication\n"
)
facts = referee_report_facts(report)
assert facts["verdict"] == "PASS-WITH-NOTES"
assert facts["independent_of_experimenter"] is True
assert facts["referee"].startswith("r-2 (opus")

# A FAIL is never softened into a note: the gate cannot be recorded at all.
try:
    referee_report_facts(report.replace("PASS-WITH-NOTES", "FAIL"))
except WorkflowError as exc:
    assert "never softened into a note" in str(exc)
else:
    raise AssertionError("a FAIL verdict must be refused")

# A report missing either machine-read line is refused too, by name.
try:
    referee_report_facts("Verdict: PASS\n")
except WorkflowError as exc:
    assert "Referee:" in str(exc)
```
<!-- test:referee-verdict-parse:end -->

## Recording and override

```bash
uv run --locked klein gate record referee --study studies/NN-slug --acknowledged-by <actor>
```

The gate hashes the report and stores the verdict, the referee line and the
independence flag in state and in the event chain. Schema-3 `klein finalize` requires
this gate; `--no-referee --reason "<why>"` is recorded, and the study is labelled
`unrefereed` on its receipt and wherever it is listed.

## What the referee may never do

Edit a study file; run an experiment; record its own gate; read `program.md` before
`findings.md`; accept an unverifiable claim because the story is good; soften a FAIL;
or write the report for the author — the report is addressed to the orchestrator and
to the next reader, in that order.
