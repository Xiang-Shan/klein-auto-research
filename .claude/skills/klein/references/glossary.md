# Glossary — Klein in plain words

The one place each term is defined. `klein explain <term>` prints an entry from here;
the README and the protocols link to it instead of redefining anything.

## The objects of a study

### study
One research question worked from start to finish in one directory
(`studies/NN-slug/`): a contract, the runs, the findings, an independent review and a
teaching report. A study is closed with a label — `confirmed` or `exploratory` — and
then never edited.

### contract
`study.yaml`. What the study commits to before any result exists: the question, the
metric and which direction is better, how small a difference counts, the data split,
the predictions and the rule that will decide each one. It is hashed when the question
is acknowledged, so it cannot quietly change later.

### kind / modality / profile
The three labels that type a study. **Kind** is the shape of the question (`predict`,
`estimate`, `test`, `simulate`, `replicate`, `discover`, `optimize`) and fixes how it is
judged. **Modality** is the shape of the evidence (a table, images, text, a simulator,
or nothing but a checker). **Profile** is the audience, and changes wording only.

### track
One metric being pursued inside a study. A **frontier** track climbs: each run either
beats the best so far by enough (`keep`) or does not (`discard`). A **registered**
track measures: each run is a planned measurement, recorded as `measured`.

### prediction
A belief written down *before* its evidence, with an arithmetic rule ("supported if the
metric is above 0.6"). The engine applies the rule to what a run printed; nobody decides
by reading. A prediction ends `supported`, `refuted`, `inconclusive` — or stays `open`,
which blocks closing the study.

### run / experiment
One execution of the study's code, with an id like `E0007`. The engine saves the exact
code before running it, runs it once, decides the outcome by the contract's arithmetic,
and stores a manifest. A failed idea is kept as evidence, not deleted.

### disposition
The outcome of a run: `keep`, `discard`, `measured` or `crash`. A crash is recorded as a
crash, with no metric — never silently retried.

### probe
A quick look, on the record (`klein probe`): a histogram, a rough fit, "what happens
if". Cheap — no gate, no outcome — but logged and hash-chained, never allowed to read
the sealed data, and never usable as evidence for a claim. A probe earns a *prediction*,
which a run then tests.

### claim
One sentence the study asserts, with an id (`10-hubble-1929-replication#C3`), a class
(what kind of statement it is) and a strength (`confirmed` or `exploratory`). Every claim
points at the runs that support it.

### claims lock
`claims.lock`. The list of a study's claims and of every number quoted in its findings,
each tied to the file and hash where that number actually lives. A number with no home
fails verification.

### decision
A dated line in `program.md` (the study's notebook) saying what was decided and why —
required whenever a prediction is refuted.

## The process

### gate
A checkpoint a person acknowledges before the study may go on. Four of them:
**Gate 0 — consult** (is the question well posed?), **Gate 1 — data** (is the data fit
to use?), **Gate 2 — method** (is the method understood?), **Gate 3 — referee** (did an
independent reviewer pass the findings?). No run happens before the first three.

### notary
The engine's role in a run: it does not choose what to try, it *witnesses* — commits the
candidate, runs it once, judges it by the declared rule, files the evidence. The
researcher or agent drives; the notary records.

### noise floor / minimum delta
How much the metric moves when nothing real changed (a different seed, a different
split). It is measured, not guessed, and sets `minimum_delta`: the smallest improvement
that counts as real.

### headroom
How many `minimum_delta` steps remain between the current best and a perfect score.
Below one, no improvement is detectable, and the engine asks for that to be
acknowledged before more runs are spent.

### sealed data / final test
The part of the data nobody looks at while developing. It is read once per track, by one
run, to confirm the result. A rehearsal (`--dry-run`) comes first, and the sealed run is
refused unless the latest rehearsal passed on the same code.

### replication
Re-running a recorded run from its saved code to check that it reproduces.

### referee
A reviewer in a fresh context — a different model, tool or person from whoever ran the
study — who checks the findings against the record and writes a verdict. A study closed
without one is labelled `unrefereed`.

### receipt
A small file a verb writes to prove it ran and what it found (`verify_receipt.json`).
Receipts are generated, never hand-edited.

### evidence map
`klein map`: the study drawn as question → predictions → runs → claims → decisions,
with what is still open. Derived from the records; it adds nothing of its own.

## The repository

### exhibit
A finished study shipped with Klein as a worked example (`studies/`). Older ones are
listed in `studies/ARCHIVE.md`.

### skill / protocol
The written procedures an agent or a person follows at each stage
(`.claude/skills/klein/`). Plain markdown; `klein explain <stage>` prints one.

### plug-in
Code outside the kernel that adds a verb, an audience profile or an evidence modality.
A plug-in can never change how a run is judged.

### generation layer
An optional plug-in that also records what was committed to *before* each action
(hypothesis slates, a pre-mortem, an expert baseline). A study that does not opt in is
untouched by it.
