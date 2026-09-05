# The inquiry model — what a Klein study IS (schema 3)

Klein 1.x was a disciplined experiment loop: a `train.py` that improves a metric under
a notary. Klein 2.0 keeps that loop and puts it inside a larger unit — **the inquiry**.
A study is not "a script that got better"; it is a **question** with a **pre-registered
prediction**, **evidence** a stranger can re-check, and a **claim** whose strength was
earned, closed by a **decision** written down at the time it was made. Every mechanism
in the engine exists to make one of those five objects harder to fake.

Role: the driving agent — and the consultant at Gate 0, who types the inquiry. Any
agent or human can follow this document directly; it is the source of truth.

## The five objects

| Object | Where it lives | Machine surface | Human surface |
|---|---|---|---|
| **Question** | `study.yaml: research_questions[]`, typed by `kind` | RQ ids, kind, modality, profile | `research_plan.md` |
| **Prediction** | `study.yaml: predictions[]` — id `P#`, statement, a declarative `rule` or `manual: true` | verdict `supported | refuted | inconclusive` in `study_state.json`, event `prediction_adjudicated` | `program.md` (the lever and the reason), findings §② |
| **Evidence** | run manifests, registered sweeps, replication records, verifier re-checks, verified references | `runs/E####/manifest.json`, `state.sweeps`, `runs/E####/replications/`, `references.yaml` | `results.tsv`, `aux_metrics.tsv`, sidecar TSVs |
| **Claim** | `claims.lock` — `<study>#Cn`, a class, a strength, pinned artifacts, errata | `klein claims verify` (the claims law) | `findings.md` ① and ④ |
| **Decision** | `program.md` — a dated `Decision:` line naming what changed and which evidence forced it | `klein verify --evidence-use` checks every refuted prediction has one | the Log |

Markdown stays the human surface; JSON and the ledger are the machine surface. Nothing
in the machine surface is hand-edited; nothing in the human surface is trusted without
the machine surface behind it.

<!-- WP-09: design -->
**The evidence-design artifact supplements these five, on a study that asks for it.** A
schema-3 study that opted into the generation layer with `--capability design` locks one
`evidence_design.yaml` before the DATA gate, giving each object the fields it needs to
say what a number MEANS rather than only what it was: the Question gains an estimand, a
population, units, a measurement process, identification assumptions and an intended
generalization; the Prediction gains an uncertainty method, validity conditions (each
naming a `P#` whose rule can actually fire it), a practical threshold and provenance;
Evidence gains representations, a dependency hierarchy, permitted reuse, a seal and an
acquisition ledger; the Claim gains a named warrant; the Decision gains a typed
continuation with its predecessor and successor. **The id grammar below does not change
and neither does any engine rule** — the artifact adds vocabulary a stranger can review,
and the generation layer's `design` family checks only that it was locked first and has
not moved since (`references/generation-protocol.md`, "Evidence design"). A study that
does not opt in is untouched by all of it.
<!-- end WP-09 -->

## The three axes

A study is typed on three orthogonal axes. CONSULT infers all three from the brief and
CONFIRMS them in its summary — they are never a seventh interview question.

- **`kind`** — the shape of the question (below). Study-level, with an optional
  per-track override `tracks.<id>.kind` when one study carries two lanes (study 09 ran a
  registered test beside a known-truth simulation).
- **`modality`** — the shape of the evidence source: `tabular | timeseries | image |
  sequence | graph | text | simulation | none`. It selects the Gate-1 card template
  and the split vocabulary (`data-gate-protocol.md`).
- **`profile`** — who reads the study and what vocabulary is honest there:
  `generic | ml-research | math | insurance`, or a repo-local `profile_doc:`. A profile
  never changes what the engine checks; it changes headings, audience sentences,
  figure sets, doctrine anchors, budgets, and banned words (`profiles/README.md`).

## The seven kinds

| kind | The question | Default track mode | What "sealed" means | `confirmation.require` default | Strength ceiling |
|---|---|---|---|---|---|
| `predict` | how well can Y be predicted, and which candidate wins | frontier | one look at the held-out partition | `[sealed]` | confirmed |
| `estimate` | what is the value of X, with uncertainty | registered | a prospectively locked block, or an external reference value, compared once | `[sealed]` | confirmed |
| `test` | does H hold; does A differ from B | registered | a held-out block, or a pre-registered confirmatory family | `[sealed]` | confirmed |
| `simulate` | under a declared truth, does the method recover it | registered | a fresh seed block never used in development | `[sealed]` | confirmed only for `known-dgp-teaching` claims; never for a claim about real data |
| `replicate` | does reported result R reproduce | registered | the original's reported value, compared once | `[sealed]` | confirmed |
| `discover` | what structure or hypotheses exist | registered (frontier for screening) | none — a discovery is a hypothesis, not a result | `[]` | exploratory; promotion needs a follow-up `test` study that cites it |
| `optimize` | find an object that maximizes F, judged by a verifier | frontier | independent re-verification of the pinned artifact | `[verify]` | confirmed |

Rules that follow from the table:

- **`predict` and `optimize` are the frontier kinds.** They hold an incumbent, obey the
  headroom law, and restore the mutable surface on a non-keep. `optimize` differs in
  one way that matters: the objective is computed by a **declared verifier** on the
  artifact the search produced, never by the search itself (`tracks.<id>.verifier` is
  required), and its incumbent may be seeded from the literature
  (`metric.incumbent_external`) so that a `keep` means "beat the best known value".
  A search that only matches the known value is a `discard` with the match disclosed;
  a search that fails is a search limit, never evidence of impossibility.
- **`estimate`, `test`, `simulate`, `replicate` are the registered kinds.** Every run is
  a cell of a pre-registered measurement program: disposition `measured | crash`, no
  incumbent, the printed block may pin tables as evidence (`artifact:` lines), and
  identical reruns are allowed when they test a prediction (`registered-mode.md`).
- **`discover` cannot close `confirmed`.** Its findings are hypotheses with evidence
  ids; the honest next step is a `test` study whose predictions cite them.
- **`simulate` confirms methods, not the world.** A `known-dgp-teaching` claim carries
  `scope: in-silico` in the lock and names its DGP; a sentence about real data in a
  simulation study is a claim of a different class and stays exploratory.

## The modalities

| modality | Gate-1 card variant | Split vocabulary | Mechanized leakage rows run on |
|---|---|---|---|
| `tabular` | the classic profile + four-row leakage checklist | stratified / random / group / time | the prepared dataframe |
| `timeseries` | time split, leakage-through-time and look-ahead checklist | time (newest rows sealed) | the split index table |
| `image` `sequence` `graph` `text` | a group id computed in `prepare.py` (patient, cluster, scaffold, document) + modality checklist (duplicates and near-duplicates, label provenance, size/length statistics) | group | the split index table (`data/prepared/index.csv`: `id, group, time, split`) |
| `simulation` | the DGP card: declared truth, parameters, seed blocks, what "recover" means numerically | seed blocks | not applicable — stated on the card |
| `none` | the verifier card: the oracle, its exactness and cost, tolerance, known failure modes | none | not applicable — stated on the card |

## Evidence ids — the grammar every citation uses

| Form | Resolves to |
|---|---|
| `E####` | `runs/E####/manifest.json` (a run — keep, discard, crash, measured, or sealed) |
| `sweep:<name>` | a registered measurement sweep: `sweeps/<name>.sidecar.tsv` + script, hashed in `state.sweeps` |
| `rep:E####@<ts>` | `runs/E####/replications/<ts>.json` — a re-execution of the run in a fresh worktree |
| `verify:E####@<ts>` | the same file with `mode: verify` — the declared verifier re-run on the pinned artifact |
| `ref:<key>` | an entry of `references.yaml` (doi / arXiv / url, with `verified: true|false`) |
| `art:<alias>` | an artifact pinned by alias and sha256 in `claims.lock` |
| `P#` | a prediction in the contract and its verdict in state |
| `<study>#Cn` | a claim in that study's `findings.md` and `claims.lock` |

`klein claims verify` resolves every id a claim cites; an id that resolves nowhere fails
the study.

## Per-kind requirements at CONSULT

Beyond the six-axis interview, the consultant confirms:

- `predict`: the primary metric per track with direction and the measured floor; the
  three-way split; `metric.bound.ideal` when the metric is bounded.
- `estimate`: the estimand in words, the uncertainty method (bootstrap / analytic /
  jackknife), the sealed comparison (a locked block or an external reference value).
- `test`: the hypothesis family, `n_comparisons`, the family-wise guard
  (`metrology.family_maxt` or Bonferroni), and what "inconclusive" means numerically.
- `simulate`: the DGP in full (a `simulation` modality card), the seed blocks, the
  recovery criterion, and the in-silico scope sentence.
- `replicate`: the target values with their source and tolerance, transcribed from at
  least two independent sources when the data must be re-typed; the identity anchor
  (E0001 reproduces a published sum or count, hard-STOP on mismatch).
- `discover`: the screening metric and the statement that no claim will close
  `confirmed`; the follow-up `test` design is sketched in `research_plan.md`.
- `optimize`: the verifier (command, exactness, tolerance), the external incumbent with
  its source, and the vocabulary rule (found / matched / improved; never proved).

## Per-kind verify rules (schema 3)

`klein verify` applies the general checks to every study and adds, by kind:
frontier kinds — headroom disclosed, incumbent chain monotone; registered kinds — every
cell's declared artifacts hash-match; `simulate` — every `known-dgp-teaching` claim
carries `scope: in-silico`; `replicate` — every target value in the contract is cited
by at least one adjudicated prediction; `discover` — no claim has strength `confirmed`;
`optimize` — every keep has a `verify:` record before `finalize` may label it confirmed.

## External evidence

A measurement that Klein cannot execute — a wet-lab result, a survey wave, a field
campaign, a colleague's table — enters any kind as a registered `measured` cell whose
entrypoint does nothing but validate the imported file and print an `artifact:` line
for it. The manifest then pins the bytes, the cell has a candidate commit, and a
prediction can be adjudicated against it (`klein run-one --tests P#`). No new mechanism
is needed for a loop whose experiments happen outside the machine.

## Worked instantiations (the shipped studies, read through the model)

| Study | kind | modality | mode | What the model made explicit |
|---|---|---|---|---|
| 03 noisy-rosenbrock | simulate | simulation | (schema 2) | known-truth lab; claims are in-silico |
| 05 freMTPL2 gap forensics | predict | tabular | frontier | the gap needed two tracks to get two sealed numbers |
| 06 hurricane return levels | estimate | tabular | (schema 2, hand-bent) | an estimate with CI, no incumbent — registered mode in disguise |
| 07 iris 90 years | predict + control | tabular | frontier | headroom found by hand → the headroom law |
| 08 iris rematch | test | tabular | (schema 2, hand-bent) | 21 challengers, 0 keeps at h = 1.015 |
| 09 iris first lesson | test + simulate lane | tabular + simulation | (schema 2, hand-bent) | the 42-cell map lived beside the ledger → registered mode; `claims.lock` → the claims law; E1 → contract-driven splits |
| 00 known-truth quickstart | predict | tabular (synthetic) | frontier | the headroom law shown against a KNOWN ideal |
| 10 Hubble 1929 | replicate + estimate | tabular (24 rows) | registered | a prospective lock is not blindness, and says so |
| 11 exact-verifier construction | optimize | none | frontier | the checker is never the searcher |
| 12 insurance claims frequency | predict | tabular | frontier | one profile, not the front door |
| 13 char-LM fixed budget | predict | text | frontier | matched compute in steps; the training script never grades itself |

## Anti-patterns the model forbids

- **A prediction written after its evidence.** The consult gate hashes `study.yaml`;
  a prediction added later is visible as a gate re-record with a reason.
- **A frontier for a question that has no incumbent.** An estimate or a test is not
  "improved"; it is measured. Use registered mode.
- **A verdict without a decision.** A refuted prediction with no `Decision:` line in
  `program.md` fails `klein verify --evidence-use`.
- **A claim stronger than its evidence.** `finalize` labels; the referee reads; the
  lock records the ceiling per class.
- **A number with no home.** The numbers law (`claims-protocol.md`) — every numeral in
  findings, lock, and tutorial is a copy of a pinned value.
- **"Blind", "proved", "replicated Hubble", "material".** Each profile ships a list of
  words that need a qualifier or are banned outright; `klein verify` scans for them.
