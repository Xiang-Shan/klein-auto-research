Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: Claude Opus 5 / claude-opus-5[1m]) · fresh context · independent-of-experimenter: yes

# Referee report — 15-iris-90years-relaunch

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model** — a
different model than the experimenter.

Experimenter, from `program.md`'s `## Roster` (the artifact the rung rests on):
**Claude Sonnet 5 · Claude Code · session 016HefKjsAszSh9M5FJ8Zw4g**, corroborated by
every gate record's `acknowledged_by` in `study_state.json` ("Claude Sonnet 5
(autonomous redo, ack given in chat by Xiang Shan)"). I am Claude Opus 5
(`claude-opus-5[1m]`), a different model, in a context that had not seen the loop:
`findings.md` was read before `program.md`, and `program.md` was opened only for its
`## Roster` header (the protocol's one metadata exception) until every other artifact
had been weighed.

Two facts a reader should have, neither of which lowers the rung (see note 5):

- I run as a subagent inside the same Claude Code **session id** as the experimenter
  row. The roster's referee row asks for "a different model AND a fresh session"; the
  model half holds outright, the session half holds in the fresh-context sense (a new
  subagent with no view of the loop), not in the session-id sense. The ladder ranks a
  different model *above* a fresh session, so the rung claim is the model rung.
- The **synthesist** row is also Claude Opus 5. I am a separate invocation with a
  fresh context and did not write `findings.md`, so the "a synthesist never referees
  its own findings" rule is satisfied by context; the model tier is nonetheless shared
  and is disclosed here rather than left for a reader to discover.

I read studies 07/08/09 not at all; this review judges study 15 against its own
contract only.

## Mechanical verifiers run

All from the repo root, read-only, against the tree at HEAD `9b2b8e0` (working tree
clean before and after; I created no commit other than this report).

| Command | Result |
|---|---|
| `klein verify --study studies/15-iris-90years-relaunch --numbers --evidence-use` | **38 checks, 0 failed.** `evidence use: 1.00 (13/13 cited)`; `findings numbers: all 78 scanned numerals trace to 25 pinned source(s)`; `claims append-only`, `claims ancestry`, `event chain`, `ledger integrity`, `gate artifact hashes`, prepared-data and split fingerprints all `[OK]`. Two embedded `[WARN]`s, both benign: "not yet refereed" (this gate), and "train.py: scaffold stubs remain (NotImplementedError)" — a heuristic false positive, see the check-6 row |
| `klein claims verify --study studies/15-iris-90years-relaunch` | **7 checks, 0 failed** (shape, 10 pinned artifacts hash as recorded, presence, evidence resolves, numbers found in their artifacts, append-only across git history, `git_head` an ancestor of HEAD) |
| `klein predict list --study studies/15-iris-90years-relaunch` | **5 supported, 4 refuted, 7 inconclusive, 0 open** — identical to findings §②, row by row |
| `klein status --study studies/15-iris-90years-relaunch` | 12 experiments (keep=4 discard=2 measured=6 crash=0); final holdout ablation=1/1, fisher=1/1, modern=1/1; 0 refutations without a recorded decision; 0 single-source confirmed claims |
| figure re-render (`make_figures.py` → temp dir, byte compare) | **not applicable** — `figures/` contains only `.gitkeep` and `report/` only `.gitkeep`; TUTORIAL runs after this gate. Nothing to re-render, nothing to critique (see check 9) |

Artifact identity: the `verify_receipt.json` committed at HEAD pins
`findings.md` `d759bf40…`, `claims.lock` `05cfdd5c…`, `program.md` `b92dcee9…`,
`study.yaml` `19d6edaf…`, `results.tsv` `675c877e…`; I re-hashed all five and they
match, so the artifacts reviewed here are exactly the ones the receipt covers, and
`study.yaml`'s hash is byte-identical to the one in the consult gate record.

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **PASS** | `confirmation.require: [sealed, replicate]` on all three tracks. Each of the six `confirmed` claims cites both kinds: C2 (E0011 sealed + `rep:E0006@20260904T174449Z`), C3 (E0010 + `rep:E0001@20260904T174249Z`), C4 (E0012 + `rep:E0007@…174632Z`), C5 (E0012 + `rep:E0008@…174817Z`), C6 (E0010, E0011 + `rep:E0006`), C7 (E0010, E0012 + `rep:E0001`, `rep:E0008`). All four replication records read `reproduced: true`, `difference 0.0`, `mismatched_keys []`. Every `confirmed` claim is descriptive or procedural — a measured level, a measured gap, a ledger count — never a mechanism; every mechanism sits in C8/C9/C10, each tagged `(exploratory, mechanism-interpretation)` in prose and `"strength": "exploratory"` in the lock. C1 is held at exploratory *because* only `hgbt` of the four parade challengers has a sealed counterpart — the strength note says so explicitly. §⑤ "What should NOT be concluded" forbids exactly the over-readings a hostile reader would reach for ("does not license 'LDA is as good as modern machine learning'"; "Do not read `-0.012821` val_auc as a measurement of how much worse boosting is"). Sealed-run replication is correctly refused by `kleinlib.replicate` and the replicate leg is filed against the development run each sealed cell rests on, disclosed in the strength note |
| 2 | predictions adjudicated and reported | **PASS** | `klein predict list` and findings §② agree on all sixteen rows, verdict for verdict and observed-value for observed-value; `predictions closure: 16 registered, all adjudicated`; 0 open, so no `--allow-open-predictions` reason is needed. All four refutations (P3, P9, P13, P15) carry dated `Decision:` lines in `program.md` — `belief revision` `[OK]` names them, and I read each: P3 ("Decision: P3 refuted"), P9 ("Decision: **P9 REFUTED**"), P13, P15. The seven `inconclusive` rows each fire their *own registered* `inconclusive_if` clause ("the contract still carries `minimum_delta` 0 …"), and the adjudication explanations in `events.jsonl` (seq 19, 23, 27, 31, 35, 59, 60) are the notary's own words, not prose. P9's manual adjudication pins the ledger hash `6dc8c35730c5…` |
| 3 | negative evidence reported | **PASS** | `evidence_use_rate 1.00`, `uncited_evidence []` in `verify_receipt.json`: all 8 non-keep runs + 5 registered sweeps cited. The two discards are load-bearing findings, not footnotes: E0004 (`knn5`, the parade's only genuine loss) carries C1 and C13; E0011 (the sealed run, `discard` by the notary's sealed convention — `decision_reason: "sealed final-test evidence; excluded from the adaptive frontier"`) carries C2, C6, C13, C14. Zero crashes. Beyond the requirement, findings names the two records it deliberately does **not** cite and why — the timed-out first replication attempt `rep:E0001@20260904T174103Z` (`exit_code 124`, `timed_out true`, empty `replicate_block`) and the three `sealed_dryrun` rehearsals — which is the honest handling of a non-reproduction on file |
| 4 | controls | **PASS** | Negative controls exist and are mechanized at Gate 1: `data_card.md` clean-room row 4 records `[OK] constant-chance[*]: val_auc=0.5000` and `[OK] shuffled-chance[*]: val_auc` in {0.5192, 0.4391, 0.4391} on all three tracks, inside `12/12 checks passed: clean` from `python -m kleinlib.leakage`. Positive controls: P0, the registered identity anchor (100/50/50/4 and partitions summing back, all five clauses exact at E0001), and the method card's M1 — a from-scratch numpy LDA reproducing `LinearDiscriminantAnalysis(solver="svd")` to `7.105e-15` max coefficient difference on this study's own training rows, run at the METHOD gate with no evidence spent. `data_card.md` is pinned in the lock as `art:data_card` and hashes as recorded |
| 5 | multiple comparisons | **PASS** (note 2) | `n_comparisons` is stated **nowhere** in the study and no family-wise guard is declared, although the `ablation` track is `kind: test`. I did not raise the FAIL condition ("a confirmed claim drawn from an unguarded family") because the guard that is actually operative here is complete pre-registration of a fixed family with every member reported, and I verified it byte-for-byte (check 6): the sixteen rules were registered before the first run, none was added, changed or dropped, and all sixteen verdicts are published. I then checked by hand that no confirmed verdict turns on an unstated α. The ablation family is five comparisons (E0007, E0008, E0009 development; E0012's two sealed clauses). C4's margins are `delta_in_floors` 0 (development, twice) and −0.0456 (sealed) inside a ±1-floor bar — a *non*-difference claim, which a multiplicity correction only widens. C5 reports its bar as **not cleared**; its supporting evidence is 1000/1000 paired-bootstrap resamples on the correct side of zero (`sweeps/floor_ablation.sidecar.tsv`: min −0.5625, **max exactly 0.0**), reproduced in direction on the sealed block, so a Bonferroni over five changes no verdict. The parade family (4 challengers) yields only the exploratory C1; C6's single sealed comparison is descriptive and its selection effect runs *against* the reported direction (the selected challenger still lost). Note 2 asks for the family sizes to be written down |
| 6 | pre-registration integrity | **PASS** | The consult gate was re-recorded once (`events.jsonl` seq 2 at 15:02:38Z, hash `d1cdcd2d…`; seq 17 at 16:16:42Z, hash `19d6edaf…`) with its reason on the record — gate `note`: "minimum_delta set from the measured noise floor (fit_noise/floor_modern/floor_ablation/floor_fisher, Phase 0)" — plus a dated `program.md` entry. I diffed the two blobs (`cf4b5c2` → `bf99720`): 78 insertions, 5 deletions, in **four hunks, all inside `tracks.*.metric`** (the three measured `minimum_delta`/`noise_floor`/`fit_noise` blocks and a 75→74-row comment correction). The `predictions:` block is byte-identical across both records — sha256 `ce320fc0134ea428e8a0…`, 9599 bytes, in both — as are `research_questions` and `confirmation.require`. No prediction's contract hash post-dates its evidence: P0–P3 were adjudicated at E0001 under the *first* record, and the re-record touched nothing they read. `lib/iris.py` has exactly one commit, made before E0001, and never appears in a candidate transaction; `prepare.py` last changed at the DATA gate. Related: verify's `train.py` scaffold-stub `[WARN]` is a false positive — the `NotImplementedError` at `train.py:116` is a deliberate guard for an unhandled `KLEIN_TRACK`, and the file holds E0006's kept surface (`MODERN_RECIPE = "hgbt"`), not a stub |
| 7 | numbers traceable (five hand-checked, listed below) | **PASS** (note 1) | `klein verify --numbers` `[OK]`: all 78 scanned numerals trace to 25 pinned sources. Both `klein:numbers-ok` markers are the *same* derivation and both reasons hold: `sepal_delta_in_floors` (−0.8547, `aux_metrics.tsv` E0012) × the ablation floor (0.28125, `study.yaml`) = −0.240384, which is the "about −0.24" the prose claims, and no run printed the sealed sepal AUC as its own key (confirmed against `runs/E0012/run.log`). My five hand-checks are below the table; one of them turned up a numeral that has a valid pinned home but is attached to the wrong run in prose — note 1 |
| 8 | references | **PASS** | `references.yaml` carries 18 entries, **all** `verified: true` with a named `verified_by` method and `verified_at: 2026-09-04`; there is no UNVERIFIED row, so no UNVERIFIED reference can support a `confirmed` claim. Every `ref:` key cited in findings §⑥ (`grinsztajn2022`, `fernandezdelgado2014`, `coverhart1967`, `hanley1982`, `efron1979`, `hollmann2025`, `fisher1936`) resolves in the file; the only claim citing references at all is C8, which is exploratory. `method_card.md`'s frontmatter `refs_verified: true` and its `triad:` (theory/papers/practice all true) are honest: §5 lists 18 verified / 0 unverified, and the Practice leg names a script that was actually run (`method_check_lda.py`). Fisher's transcribed figures used in §⑥ (15.31, 4.342, 4.222) live in the pinned `method_card.md`, and findings is explicit that neither they nor the card's derived 0.9943 "may be described as 'Fisher's number'" |
| 9 | figures | **PASS** (vacuous) | No figures exist: `figures/` holds only `.gitkeep`, there is no `make_figures.py`, and `report/` is empty — TUTORIAL runs *after* Gate 3 in the lifecycle, so the pixel law and the four-point figure critique have nothing to bind on today. Nothing to fail, and nothing here should be read as the figures having passed. The obligation transfers intact to TUTORIAL, where `klein verify` enforces the pixel law before `finalize` |
| 10 | vocabulary and scope | **PASS** | A full scan of `findings.md` and `claims.lock` for the generic profile's banned words — "blind", "proved", "significant", "material", "actionable" — returns **zero hits**, in either document. Every comparative verb is either quoting a registered prediction's own wording or floor-qualified in the same clause ("zero of the four challengers beat the incumbent **by any amount the contract can resolve**"), and the one place a naive reading would go wrong is pre-empted by name ("A ledger reader who counts `keep` rows … would conclude that three of four post-1936 methods improved on Fisher. None did"). Every floor names its estimand — `marginal-resplit`, `paired-comparison` ×2, `fit-noise` — in `study.yaml` and again in prose, and verify echoes all three. No simulation claims (modality `tabular`). Resolution is never sold as materiality; findings states outright: "**Nothing here is priced.** The study registered no `materiality:` block, deliberately" |

### The five (six) numerals hand-checked against their pinned artifacts

1. **`ablation_floor` 0.28125** — recomputed from `sweeps/floor_ablation.sidecar.tsv`
   (1000 rows): mean −0.190092, sample std 0.0952175, range 0.5625 →
   `max(2σ, range/2) = max(0.190435, 0.28125) = 0.28125`. Matches `study.yaml`'s
   `tracks.ablation.metric.minimum_delta` and the lock's `floor_ablation_{mean,std,range}`.
   It also confirms C10's mechanism from the data rather than the prose: the sidecar's
   max is exactly `0.0` and its min is `−0.5625`, so `range/2` is set by the effect's
   own tail and binds over `2σ`.
2. **`modern_floor` 0** — recomputed from `sweeps/floor_modern.sidecar.tsv`: the set of
   distinct paired deltas over all 1000 resamples is `{0.0}`; std = range = 0. C8's
   "exactly 0 on all 1000 replicates" is literally true. `sweeps/floor_fisher` and both
   `fit_noise` sidecars are five values of `1.0` each, as declared.
3. **`hgbt_sealed_delta` −0.012821** — `aux_metrics.tsv` E0011 `delta_vs_reference` and
   `runs/E0011/run.log`. Independently: recomputing the partition with
   `kleinlib.data.contract_split` gives a sealed block of 13 virginica / 12 versicolor =
   **156 ordered pairs**, and `1 − 2/156 = 0.987179`, which is E0011's printed
   `primary_metric` to the digit. C6's "exactly `2 / 156` of the block's ordered pairs"
   is exact, not rhetorical.
4. **`dev_knn_auc` 0.990385** — `results.tsv` E0004. The development block recomputes as
   12 virginica / 13 versicolor = 156 pairs, and `1 − 1.5/156 = 0.990385`, confirming
   §⑥'s "the observed `-0.009615` decomposes as exactly three tied pairs" (three ties at
   half a pair each).
5. **`sepal_dev_floors` −0.661** — `aux_metrics.tsv` E0008: `−0.185897 / 0.28125 =
   −0.66097` → `−0.661`, and `primary_metric` 0.814103 = `1 − 0.185897`. The whole C5
   chain closes on itself.
6. **The derived sealed sepal gap** behind both `klein:numbers-ok` markers:
   `−0.8547 × 0.28125 = −0.240384` → "about −0.24". Both markers' stated reasons hold.

Also checked in passing and correct: 0.96 / 0.92 / 0.88 = 24, 23, 22 of 25 (E0001,
E0010, E0011 `val_errors` 1, 2, 3); the metric resolution `1/156 = 0.0064`; the
prepared table at 99 rows / 49 positives with a realized 49/25/25 split (findings never
repeats the contract's stale "50 training flowers"); and the git timestamps behind
"the playbook's H6 was written before E0012 ran" — H6 and its explicit sealed-sepal
anticipation were committed at 18:28:26, twelve minutes before E0012's candidate commit
`b769819` at 18:40:03.

### On the disclosed instrument failure

The zero floor, the tie-as-keep dispositions and the seven `inconclusive` predictions
are, in my reading, handled honestly and soundly, and I want that on the record
separately from the checks:

- The floors were **measured before** the parade, from recipes, pairs, estimands and
  replicate counts fixed in `study.yaml` before any measurement — I verified that the
  pair `(lda_all4, hgbt)` and `k=1000` were in the pre-Phase-0 blob, so neither could be
  chosen after seeing an answer.
- The degenerate result was flagged to the orchestrator *at the phase boundary* and the
  decision to proceed is on the record as a user decision (`events.jsonl` seq 18,
  `phase_acknowledged`, note "AUC pegs (floor=0) on fisher/modern; user directed: run
  the parade anyway"), not taken quietly.
- Nothing was patched to rescue the outcome: no metric swap, no contract edit, no
  post-hoc floor. The seven `inconclusive` verdicts fire their own pre-registered
  clauses, and findings refuses to launder them ("The verdict answers 'did the
  pre-registered bar clear?'; only the raw number answers 'how big is it?'").
- The four `keep`s are reported as what they are — "4 printed keeps, 0 resolvable
  wins" — in the abstract, in C2, in C9, in P9's own adjudication text and in
  `program.md`, with the arithmetic that produced them spelled out.
- The one arithmetic error the loop made (E0011's "2 extra errors", which compared a
  sealed count against a development one) was found *by the authors*, corrected to the
  like-for-like 3-vs-2 in C6, and surfaced for this gate rather than silently fixed.

That is the behaviour the rubric exists to reward. The notes below are small by
comparison.

## Notes (each needs a dated `Referee note:` answer in `program.md`)

1. **One numeral is attached to the wrong run.** findings §① ("Two evidence records
   deliberately not cited above") says of the timed-out replication: "*the successful
   retry's own `wall_seconds` was `0.787251` at run time*". The successful retry is
   `runs/E0001/replications/20260904T174249Z.json`, whose `replicate_block.wall_seconds`
   is **3.598061** — and `program.md`'s own entry gets this right ("the retried run's own
   measured `wall_seconds` was 3.6s"). `0.787251` is E0010's `wall_seconds` in
   `aux_metrics.tsv`. The mechanized law is satisfied (the numeral has a pinned home, and
   inside backticks it is exempt from the document scan anyway), and the point being made
   — the child's own compute is far under the 60 s budget, so the timeout is cold-start
   overhead — survives either number. The sentence as written is still false. *Clearing:*
   replace it with the replication record's own `wall_seconds` (3.598061) or with E0001's
   own run cost (0.803809, `aux_metrics.tsv`), and name the artifact it comes from.
2. **`n_comparisons` is never stated.** No family size and no family-wise guard appear
   anywhere in `study.yaml`, `findings.md` or `program.md`, even though the `ablation`
   track is `kind: test`, for which `references/inquiry-model.md` asks a study to declare
   "the hypothesis family, `n_comparisons`, the family-wise guard". I did the arithmetic
   myself and no confirmed verdict changes under a correction (check-5 row), which is why
   this is a note and not a FAIL. *Clearing:* one sentence in findings §② giving the
   family sizes (modern parade 4 challengers + 1 seeding cell; ablation 5 comparisons;
   fisher 4 anchor predictions), naming pre-registration as the guard, and stating that a
   Bonferroni over the ablation family moves no verdict.
3. **E0011 prints two `split_fingerprint:` lines.** `runs/E0011/run.log` prints the
   development fingerprint `41553e71e4ed…` first and the sealed `49a84dcd63b6…` second,
   because the sealed cell also fits a development copy to feed `sealed_extra`. The
   notary recorded the right one (`manifest.fingerprints.split_partition` =
   `49a84dcd63b6…`, matching the registered `final_test` fingerprint), and the block is
   self-consistently sealed (`train_rows` 74, `val_rows` 25, `val_accuracy` 0.88, in-run
   LDA reference 1.0 agreeing with E0010) — so nothing is wrong with this evidence. But it
   is the one run in the study where an evidence-partition check depends on print order,
   and `program.md`'s E0011 entry says so in passing rather than as a flagged caveat.
   *Clearing:* an explicit line recording that the sealed cell prints two fingerprints by
   construction, that the notary checks the last, and — if the pattern recurs — that a
   future cell should print only the partition it is being judged on.
4. **Two things a findings-only reader cannot see.** (a) §③'s fourth surprise, the
   calibration reversal, is the only item in that section with no claim id and no explicit
   exploratory tag, yet it is the stated basis for §⑦'s top-priority next study. Its
   numbers are correct and pinned (`aux_metrics.tsv`: E0006 Brier 0.000945 / log-loss
   0.012827; E0011 0.118994 / 0.750798; E0012 0.057828 / 0.164260) and its interpretation
   is hedged ("Read that as…"), so it is not an exploratory claim stated as fact — it just
   lacks the label its three siblings carry. (b) P14's "the best-scoring modern family
   from the parade" was **ambiguous** — the parade produced a four-way printed tie — and
   `program.md`'s E0009 entry resolves it to `hgbt` on two stated grounds (the track's
   incumbent, and the family most dissimilar to LDA, i.e. the *hardest* available test of
   P14 rather than a cherry-pick). That reasoning is sound and it belongs in findings §①
   [C4], where a reader meets the comparison. *Clearing:* label the fourth surprise
   exploratory (or give it a claim id), and add the one-clause tie-break disclosure to C4.
5. **Roster and independence bookkeeping.** The referee row is still blank. It should be
   filled with this report's `Referee:` line verbatim, and — because the roster's own
   instruction asks for "a different model AND a fresh session" — should record plainly
   that the model half holds (Opus 5 vs the experimenter's Sonnet 5) while the session
   half is fresh-context rather than a distinct session id, and that the synthesist row
   shares this referee's model tier. *Clearing:* update the `## Roster` referee row and
   note the qualification, so the gate record's independence flag and the roster tell a
   stranger the same story.

## Clearing conditions (FAIL only)

None — no FAIL condition holds. The verdict is PASS-WITH-NOTES; the five notes above
are answered with dated `Referee note:` lines in `program.md` before `klein finalize`,
and check 9 (figures) transfers to TUTORIAL as a live obligation rather than a
settled one.
