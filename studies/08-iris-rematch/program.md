# Program — 08-iris-rematch

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: Large-budget rematch: under a selection-honest registered protocol, can any of
  21 modern challenger families (incl. the 2025 TabPFN v2 foundation model) beat the
  1936 LDA anchor on the versicolor-virginica hard pair - at full n or anywhere down
  the data ladder.
- Tracks: `primary` (anchor lane) and `challenger` — one sealed look EACH, per the
  registered branch rule in §Sealed below.
- Primary metric: `val_brier` (lower; minimum_delta measured at Phase 1 by the ledger
  floor recipe — scaffold 0 is a placeholder, never a bar).
- Results are exploratory until each track's one sealed final-test run confirms them.
  A small delta without its floor must not be described as real or decisive.

## Data and split

- Source: csv:data/prepared/iris_hard_pair.csv (fixtures/ copy committed).
- Declared split: group-aware, seed 20260907, twins rows 102/143 one group. NO REDRAW.
- Adaptive work uses train + development only. The test partition stays sealed and is
  PROCEDURALLY FRESH ONLY (scouting_ledger.md §0).
- The DATA gate records the prepared-data SHA-256 and split-policy fingerprint.

## The registered ladder (not adaptively chosen — the parade IS the pre-registration)

Phase adaptive-1: E0001 anchor_lda4 · E0002 lda_sepal control · k-seed sweep
(registered degenerate) · ledger_floor sweep → paste floor into BOTH tracks →
re-record consult · Stage-A arena → commit headroom.tsv → publish headroom_declared
and fire the door-closed / door-ajar branch (study.yaml predictions rows 1-2).

Phase adaptive-2 — the verification parade, registry order (families.CHALLENGERS):
qda · gnb · lda_shrinkage · lda_platt · lda_isotonic · logit_l2 · logit_area ·
knn_tuned · svm_rbf_platt · svm_linear_platt · rf · rf_isotonic · extratrees ·
hgbt · hgbt_isotonic · gpc_rbf · mlp_small · tabpfn · tabpfn_e16 · vote_soft ·
stack_logit. One run-one each on the declared split; the ledger judges by the one
scalar minimum_delta; every landing point is publishable evidence regardless of
disposition.

Phase adaptive-3: Stage-B arena → frozen rematch_analysis.py → verdicts + coda
branch recorded here (Decisions) before the confirmation phase.

## Phase slates

The slate ritual is satisfied by pre-registration in this study: the candidate set
(23 families, era tags, eligibility) was frozen at CONSULT with the design brief and
red-team review — no adaptive candidate selection happens at phase boundaries. Any
NEW candidate idea arising mid-study goes to findings §next-steps, never onto this
study's ladder.

## Sealed — pre-committed lines and branch rule (written BEFORE any sealed run)

Branch selection is mechanical (the frozen rematch_analysis.py): **Branch W** iff
≥1 Bar-2 cell; **Branch G** otherwise. Either way the analysis writes
`sweeps/coda_manifest.json` (families, baked train positions, hashes, numeric
bands; committed before the confirmation phase) and BOTH sealed runs use the
pre-registered registry entries `coda_primary` / `coda_challenger`, which read
that manifest — the branch is data, not a post-selection code edit. Registered
gap sign convention: g_sealed = sealed_primary − sealed_challenger, checked
against the arena's [p10, p90] of g = anchor − challenger. Epistemic status,
registered: the coda band has NO nominal coverage after selection — an in-band
result is a procedurally locked audit at the 2δ scale, never an evidence
upgrade; klein's `confirmed` label records protocol completion only. The arena
is the evidence; the seal is the discipline.

The four Branch-G sentences (two per track, held/broke) — 一个字都不许改 after this
commit; the spoken line Friday is whichever variant the record makes true:

- T1 primary, prediction |sealed − declared dev| ≤ 2×minimum_delta.
  - HELD · EN: "The incumbent's level held on the fresh seal — inside the registered
    band. Boring, and boring is the point."
  - HELD · zh: 「新封条拆开，在位者的水平落在预先登记的带子里。无聊——无聊正是我们要的。」
  - BROKE · EN: "The incumbent's level left the registered band on the fresh seal.
    The protocol lets us say that sentence, and nothing more."
  - BROKE · zh: 「新封条拆开，在位者的水平出了预先登记的带子。协议只允许我们把这句话说出
    口，多一个字都不行。」
- T2 challenger (tabpfn vs anchor, n=60), prediction: paired sealed gap inside
  tabpfn's arena [p10, p90] fold-level paired-gap band at rung 60.
  - INSIDE · EN: "Nineteen thirty-six and twenty twenty-five, one sealed look each:
    the gap landed inside the band the arena predicted. The arena is the evidence;
    the seal is the discipline."
  - INSIDE · zh: 「一九三六和二〇二五，各拆一眼封条：差距落在擂台事先画好的带子里。证据在
    擂台，封条管纪律。」
  - OUTSIDE · EN: "The 1936-vs-2025 sealed gap landed outside the arena's band —
    recorded as a miss against the registered prediction."
  - OUTSIDE · zh: 「一九三六对二〇二五，封存差距落在擂台带子之外——对照预先登记的预测，这
    记作一次未中。」

Branch-W templates (slots (f*, n*) filled mechanically by the frozen selection rule;
same held/broke discipline): T1 = coda_primary (anchor on the baked n* positions),
prediction |T1 − m_n*| ≤ 2δ_n*; T2 = coda_challenger (f* on the same positions),
prediction g_sealed = (T1 − T2) inside f*'s arena [p10, p90] paired-gap band at n*.
Wording: substitute the family name and rung into the T2 sentences above; the T1
sentences are reused verbatim with 「在位者的水平」 unchanged.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by Xiang`
2. Data card `Decision: GO` → record the DATA gate.
3. Method card → record the METHOD gate.
4. `uv run --locked klein preflight --study .`
5. Per candidate: edit train.py's FAMILY line, then
   `uv run --locked klein run-one --study . --track primary --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate base.

## Decisions (append-only)

- 2026-08-25 — schema-v2 study scaffolded; contract rewritten (fresh seed 20260907,
  two tracks, four phases); state regenerated pre-gate (07 precedent); gates pending.
- 2026-08-25 — scouting_ledger.md committed before consult (07 corpus + smoke preview
  0.029442 + TabPFN v2 spike PASS: bit-identical CPU fits, 0.099 s warm).
- 2026-08-25 — SEED-OVERFLOW CRASH, C19 reproduced: the registered 20260901xxx
  namespace exceeds sklearn's 2**32−1 bound; all 20 ledger-floor trials crashed;
  sidecar preserved as ledger_floor.sidecar.crashed-seed-overflow.tsv; namespace
  amended in-domain (2026091000/2026092000/2026093000/2026095000/2026096000),
  fix committed BEFORE any floor was stated; consult+method gates re-recorded.
