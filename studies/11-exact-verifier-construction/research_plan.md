# Research plan — 11-exact-verifier-construction

## Question

On an n × n integer grid, how many points can a budgeted iterated local search place
with no three of them collinear — judged only by a declared exact verifier that shares
no code with the search — at an n where the proven maximum 2n should be reachable and
at an n where it should not?

## The problem, and the one piece of arithmetic that fixes the targets

**No-three-in-line.** Place as many points as possible on the grid
{0,…,n−1}² so that no three of them lie on a common line. The maximum is at most **2n**:
three points in one row are collinear, so each of the n rows holds at most 2 points.
That argument is elementary and exact — it is a theorem, not a record — and it is
where the two magnitudes this study registers come from, before any reference was
consulted and before any code existed:

| Track | grid | proven maximum 2n |
|---|---|---|
| `n_small` | 11 × 11 | 22 |
| `n_large` | 31 × 31 | 62 |

Whether 2n is *attained* at a given n is a separate, empirical question about the
literature, and it is settled at the METHOD gate with verified references — not here.
The consult gate therefore registers the predictions with these two numbers and leaves
`metric.bound.ideal` and `metric.incumbent_external` out of the contract until that
verification exists.

## Contract

- Domain: combinatorial geometry. Kind / modality / profile: `optimize` / `none` / `math`. Schema 3.
- Data: `synthetic:prepare.py` → `data/prepared/instances.json`. There is no dataset:
  the DATA gate freezes a **problem statement** — the two grid sizes, the two seed
  blocks, the budget ladder, and the verifier's two controls.
- Tracks: `n_small` and `n_large`, both `frontier`, both running the SAME search over
  the same budget ladder. They differ only in the grid size they read from the frozen
  instance file, so the pair measures where one search's reach ends.
- Metric: `points` (higher). `minimum_delta: 1`, `exactness: exact` — an integer
  objective has a resolution, not a noise floor, so Phase 0 measures no floor.
- Verifier: `verify.py`, `tolerance: 0`, `artifact_key: solution`. It is outside
  `entrypoint.mutable`, hashed at the METHOD gate, run by the notary in a second
  process, and ITS number is the one that enters the ledger.
- Per-run maximum: 120 seconds; the largest registered budget projects to well under
  one second of search (`scouting_ledger.md` S2).

## Validation policy

There are no rows and no partitions. `data.split.kind` is `none` and comparability
comes from the two seed blocks frozen in the instance file: `development` is the only
block adaptive work may use, and `sealed` is a block no development run may touch.
`klein run-one --final-test` sets `KLEIN_EVALUATION_KIND=final_test` and `search.py`
reads the sealed block by name; that is this study's one sealed access per track, and
it is rehearsed with `--final-test --dry-run` first. `confirmation.require` is
`[verify]`: an `optimize` claim is confirmed by an independent re-verification of the
pinned artifact, which `klein replicate --verify-only` records.

## Experiment ladder

1. **E0001 — the controls.** The cell runs the declared verifier, unchanged, on each
   of the twelve invalid objects planted in the frozen instance file (positive control:
   the checker must fire) and hands the notary the known-valid Erdős parabola set as
   its own artifact (negative control: the checker must accept it and score it at
   exactly 11). Decides P3. This is also the identity anchor: a checker that cannot
   score a known object at its known value cannot be trusted to score an unknown one.
2. **E0002–E0004 — `n_small`.** The same search on the 11 × 11 grid at 20 000,
   200 000 and 2 000 000 addability tests. E0004 decides P1.
3. **E0005–E0007 — `n_large`.** The same search, the same three budgets, on the
   31 × 31 grid. E0007 decides P2.
4. **E0008 — the deliberate disagreement.** `search.py` reports an objective larger
   than the object it wrote. Nothing else changes. The expected outcome is a crash
   whose reason names `verifier_disagreement`; the run is registered evidence for P5,
   and it is spent on purpose because a guard that has never fired is a guard nobody
   has tested.
5. **E0009, E0010 — confirmation.** One sealed run per track, on the sealed seed block,
   at the largest budget. They decide P6 and P7.
6. **Re-verification.** `klein replicate --verify-only --tolerance 0` on every
   development run that produced a verified object; the records decide P4.

## Vocabulary (profile: math)

"Proved" and "proof" are banned unless a proof artifact is pinned by alias; "optimal"
is banned without a citation to a proof of optimality; "impossible" and "cannot exist"
may never be inferred from a search result. The honest verbs are: **found**,
**verified**, **matched the proven maximum**, **did not reach it under budget B**. A
search that fails is a statement about the search, never about the problem.

## Deliverables

`findings.md`, `claims.lock`, `referee_report.md`, `report/index.html`, and the first
typed citation into `knowledge/domains/math/README.md`.
