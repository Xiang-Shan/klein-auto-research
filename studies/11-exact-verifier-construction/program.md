# Program — 11-exact-verifier-construction

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Roster — who ran what, on which model

| Role | Who | Model | Context |
|---|---|---|---|
| Experimenter (CONSULT → SYNTHESIZE, every `run-one`) | a Claude Code general-purpose subagent | `claude-opus-5` | a fresh git worktree, this session |
| DATA-gate clean-room auditor | the same agent, self-performed | `claude-opus-5` | performed AFTER `prepare.py` was written and run, never interleaved with it; the modality is `none`, so the audit is a verifier card rather than a leakage audit |
| Referee (Gate 3) | *(left blank until the referee runs)* | | |
| Lead / orchestrator | Claude Fable 5.1 | — | spawns the referee, relays its notes, owns the delegated acks |

The referee's rung goes on the gate record, not here; whichever rung it reaches, this
table is what a later reader uses to check it. The experimenter's model is stated
honestly above: a fresh Opus context started after synthesis reaches the rung
`fresh session`, the lowest rung of the ladder (person > tool > model > backend >
fresh session), and neither this file nor the report will claim more.

## Goal and track contract

- Goal: on an n × n integer grid, how many points can a budgeted iterated local search
  place with no three collinear — judged only by a declared exact verifier that shares
  no code with the search — at an n where the proven maximum 2n should be reachable and
  at an n where it should not?
- Kind / modality / profile: `optimize` / `none` / `math`. Schema 3.
- Tracks: `n_small` (11 × 11, proven maximum 22) and `n_large` (31 × 31, proven maximum
  62), both `frontier`, both running the SAME search over the same budget ladder.
- Primary metric: `points` (higher is better), `minimum_delta: 1`,
  `exactness: exact`. An integer objective has a resolution, not a noise floor: two
  runs of `verify.py` on the same bytes return the same integer. Phase 0 measures no
  floor and `klein noise-floor` is never called.
- **The verifier is the only judge.** `verify.py` is outside `entrypoint.mutable`, is
  hashed at the METHOD gate, is run by the notary as a second process on the artifact
  the search wrote, and ITS number decides the run. The searcher's own claim is
  recorded beside it; a disagreement is a crash.
- The two magnitudes the predictions register, 22 and 62, are 2n — the pigeonhole
  bound (three points in one row are collinear, so each row holds at most 2). They are
  arithmetic, fixed before any reference was consulted.

## Data and split

- Source: `synthetic:prepare.py` → `data/prepared/instances.json`. There is no
  dataset. What the DATA gate freezes is a **problem statement**: the two grid sizes
  with their pigeonhole bounds, the two seed blocks, the budget ladder, and the
  verifier's two controls — one known-valid object and twelve planted invalid ones.
  Freezing the controls before any run is the point: the positive control cannot be
  softened after seeing whether the checker caught it.
- `data.split.kind` is `none`: there are no rows and no partitions, so war story 8's
  failure mode (an evaluator carrying a retired split seed) cannot occur here — there
  is no split to carry. What replaces it is the seed-block discipline: `development`
  is the only block adaptive work may use and `sealed` is a block no development run
  may touch, both frozen in the hashed instance file, and no literal seed appears in
  `search.py`, `verify.py` or `lib/`.

## Research questions

- **RQ1** — judged only by the declared verifier, how many points does the same
  budgeted iterated local search place on an 11 × 11 grid and on a 31 × 31 grid, how
  does that count move across a three-decade budget ladder, and does it reach 2n at
  either size? Prior: it reaches 22 at n = 11 and stops short of 62 at n = 31, because
  the same evaluation budget buys about ten times fewer greedy completions on the
  larger grid `(source: uninformed)`.
- **RQ2** — with the objective computed only by a checker that shares no code with the
  search, what does the record show when the searcher's self-report is wrong, and do
  the two independent implementations ever disagree on an honest run? Prior: no honest
  run disagrees, and the overclaiming cell is refused and recorded as a crash naming
  `verifier_disagreement` `(source: uninformed)`.

## Registered predictions

| P# | Statement | Rule | Decided by |
|---|---|---|---|
| P1 | at the largest budget the verifier scores the 11 × 11 search at ≥ 22 | `primary_metric >= 22` | E0004 `--tests P1` |
| P2 | at the same budget the 31 × 31 search is scored < 62 | `primary_metric < 62` | E0007 `--tests P2` |
| P3 | the verifier rejects all 12 planted invalid objects | `rejected == 12` (tol 0) | E0001 `--tests P3` |
| P4 | re-running the verifier on a pinned artifact reproduces its integer exactly | manual | `verify:` records |
| P5 | no run's claimed objective is accepted above the verifier's | manual | E0008's crash + every honest run's `claim_excess` |
| P6 | from the sealed seed block, the 11 × 11 search is again scored ≥ 22 | `primary_metric >= 22` | E0009 `--tests P6` |
| P7 | from the sealed seed block, the 31 × 31 search is again scored < 62 | `primary_metric < 62` | E0010 `--tests P7` |

P4 and P5 are `manual: true` on purpose, and the reason is mechanical rather than
convenient. P4 is decided by replication records, which are written outside a run
transaction and therefore print no block for a rule to read. P5 is decided by a run
that CRASHES by design: `klein run-one` adjudicates `--tests` only after the verifier
agrees, so a cell whose whole purpose is to make the verifier disagree can never reach
the adjudication step. A prediction about a refusal cannot be decided by the machine
that performs the refusal; it is decided by reading the receipt the refusal left.

## Phase plan

| Phase | What happens | Budget | Max experiments |
|---|---|---|---|
| `search` | E0001 controls → E0002–E0004 `n_small` ladder → E0005–E0007 `n_large` ladder → E0008 the deliberate disagreement | 3600 s | 8 |
| `confirmation` | sealed dry-run, then E0009 and E0010 once each on the sealed seed block | 900 s | 2 |

## Workflow

1. `scouting_ledger.md` and `sweeps/scout_design_time.py` are committed FIRST — not
   because the consult gate hashes the ledger (it does not: it hashes `study.yaml`,
   `research_plan.md` and `program.md`) but because the commit that carries the
   `study.yaml` the gate DOES hash carries the ledger too.
2. `klein gate record consult`.
3. `prepare.py` (already run), then `verify.py` and `lib/nothree.py`, then the
   verifier card `data_card.md` = GO; `klein gate record data`.
4. `method_card.md` + `references.yaml`; `klein gate record method` — which hashes
   `verify.py` into `state.fingerprints.verifier`, after which it never changes.
5. The consult RE-RECORD that adds `metric.bound.ideal` and
   `metric.incumbent_external` to both tracks, with its reason.
6. `klein headroom ack` on both tracks (see the decision below), then
   `klein preflight`, then the loop: edit `search.py` (a cell: which budget, which
   mode), `klein run-one --tests P#`.

Every candidate is committed before execution. Every run on both tracks is a discard
by arithmetic — see the headroom decision — so the evidence transaction restores
`search.py` to the pre-candidate base commit after every one of them, and each
candidate commit stays resolvable.

## Decisions (append-only)

- 2026-09-03 — schema-3 study scaffolded (`optimize` / `none` / `math`), two frontier
  tracks, gates pending.
- 2026-09-03 — the user's gate acknowledgements are DELEGATED to this agent for the
  Klein 2.0 exhibit studies. Every gate below is therefore recorded with
  `--acknowledged-by lead-agent`, on the lead's standing instruction, and the same
  applies to the phase acknowledgements and to the headroom acknowledgements. Nothing
  else about the gates changes: the artifacts still have to exist, be placeholder-free,
  and hash.
- 2026-09-03 — Decision: the problem is **no-three-in-line**, not equal-circle packing.
  Both were on the table at design time. No-three-in-line has an integer objective, so
  its verifier needs no tolerance and its metric needs no measured floor; circle
  packing has a real-valued objective and would have needed both. A study whose whole
  subject is "the checker is the only judge" should not have to argue about the
  checker's tolerance. Recorded in `scouting_ledger.md` under Retirements.
- 2026-09-03 — Decision: `metric.bound.ideal` and `metric.incumbent_external` are
  DELIBERATELY absent from the contract the consult gate hashes. Both quote a
  published value, and this study does not put a literature number in its contract
  before the METHOD gate has verified the reference that carries it. They are added by
  a consult re-record with a reason, before the first run exists. The predictions'
  own magnitudes are unaffected: 22 and 62 are 2n, arithmetic rather than citation.
- 2026-09-03 — Decision: `prepare.py` writes a problem statement, not a dataset. The
  DATA gate hashes it, which freezes the twelve planted invalid objects and the one
  known-valid object BEFORE the checker is ever run against them. A positive control
  that can be edited after it fails is not a control.
