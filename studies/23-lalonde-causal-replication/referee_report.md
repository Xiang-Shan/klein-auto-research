Verdict: FAIL
Referee: klein-referee (Claude Code subagent, model: claude-opus-5-5) · fresh context · independent-of-experimenter: yes
Generation: n/a

# Referee report — 23-lalonde-causal-replication

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. `Generation:` is `n/a` because the study has no
> `generation/manifest.yaml`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**. The
experimenter ran on a different model tier from this referee.

Experimenter: `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh
subagent context per phase. Source: `program.md` `## Roster`, read only for this
line. The referee runs on `claude-opus-5-5` (Opus tier), so `independent-of-experimenter: yes`
agrees with the roster. The experimenter row gives a tier, not an exact model id. That is
enough to tell the two models apart, because the tiers differ.

Caveat (Note 3): the roster's synthesist, who wrote `findings.md` and `claims.lock`, ran on
`claude-opus-5-5`, the same model as this referee, and was also a child context of the
orchestrating session `session_01DRcLputoCrDTEvbxp6Rby1`. Against the authors of the
findings, this referee reaches only the **fresh session** rung. Against the experimenter,
it reaches the **model** rung.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `uv run --no-sync klein verify --study studies/23-lalonde-causal-replication --numbers --evidence-use --no-receipt` | 34 checks, 0 failed (one `[WARN]` inside an OK row: not yet refereed); `evidence_use_rate 1.00`, all 9 non-keep runs cited; 7 confirmed claims cite two or more evidence kinds; findings numbers: 803 scanned numerals trace to 31 pinned sources |
| `uv run --no-sync klein claims verify --study studies/23-lalonde-causal-replication` | 7 checks, 0 failed (shape, 20 artifacts hash as recorded, presence, evidence, numbers, append-only, ancestry) |
| `uv run --no-sync klein predict list` | 3 supported (P3, P5, P7) / 4 refuted (P1, P2, P4, P6) / 0 inconclusive / 0 open |
| `uv run --no-sync klein status` | 9 experiments (measured=7, crash=2); final holdout att=1/1, reproduction=1/1; successful confirmation reproduction=E0008, att=E0009 |
| figure re-render (`make_figures.py` → temp dir, byte compare) | not applicable yet: `figures/` is empty and the study has no `figures/make_figures.py`. The TUTORIAL stage builds them |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | **FAIL** | The mechanism side holds. Every `confirmed` claim (C1, C2, C5, C8, C26, C29, C30) has the track's `confirmation.require: [sealed, replicate]`: E0008 and E0009 are `evaluation_kind: final_test`, and rep:E0001@20261103T065031Z and rep:E0006@20261103T065104Z are exact re-executions of development cells on the same tracks. The fact that no sealed cell was re-executed is disclosed (scope item 6, erratum E6). No manifest has `execution.mode: detached`, and no `seeds_n` is used. **The prose fails.** The heading of findings.md §③ item 1 reads "The paper's Table 3 column (2) is not one regression — found at METHOD, confirmed on both lanes as transcribed." That is the editorial reading erratum E4 downgraded to exploratory: C6's "is two regressions" rests on a one-source transcription. Its exploratory home is C10, which says "appears to be assembled". The heading states the reading as fact and calls it `confirmed`. The paragraph under it says "The column-(5) half is open", which contradicts the heading. That heading meets the FAIL condition "prose states an exploratory claim as fact". |
| 2 | predictions adjudicated and reported | PASS | `study_state.json` `predictions` holds P1–P7, all from `source: run` with evidence E0001/E0002/E0006/E0005/E0007/E0008/E0009. findings §② copies the `klein predict list` verdicts (3/4/0/0) row by row, and each observed value matches the manifest's printed `att_gap_usd` / `primary_metric`. verify reports a dated `Decision:` line for every refuted prediction, and program.md has them for P1, P2, P4 and P6. The P7 selection Decision line ("selected from E0006") was committed in 00672e2 at 05:39:00Z, before the first sealed dry run at 05:57:34Z. |
| 3 | negative evidence reported | PASS | `evidence_use_rate 1.00` (9/9). The crashes E0003 and E0004 are cited in scope item 5, §② P4 and C18. I checked the claim that E0004's candidate commit 2eee5d29 set `CELL` to `ipw` and found it accurate. The registered tracks have no discards, so there are no discard clusters. The killed, misnumbered run is preserved in `incidents/2026-11-03-e0005-history-repair/` and is not cited as evidence. |
| 4 | controls | PASS (note) | Positive control, present in substance: the reproduction track recovers the randomised NSW experiment's known values (1794.34 / 632.85; 1672.20 / 638.40 in `tables/reproduction_psid1.tsv`), and every att cell is scored against that experimental benchmark. Negative control: none was run. findings ⑤ ("What would change these conclusions"), ⑥ ("no placebo was run") and ⑦ item 1, plus method_card.md §4 ("A `re75`-as-outcome placebo cell would be the next test … not registered in this study"), give its absence and the reason. Neither is called a "control" by name (Note 1). |
| 5 | multiple comparisons | PASS | findings scope item 4 names the family: four PSID-1 att cells, no family-wise adjustment. Every claim drawn from them stays exploratory (C3/C23, C4/C22, C7, C31). The confirmed att claim C29 rests on the single pre-registered sealed cell E0009 (P7). The confirmed reproduction claims rest on single cells whose rule counts targets and tests no hypothesis. No `confirmed` claim comes from an unguarded family. |
| 6 | pre-registration integrity | PASS | The consult gate was recorded three times (events.jsonl seq at 04:42:40Z, 05:18:40Z and 06:15:31Z), and each re-record's reason appears in scope item 8 and in program.md's two `Decision (lead)` lines. `git diff 9bfa799 395f9b8 -- study.yaml` changes only `wall_seconds.max` (900 → 10800), `max_run_seconds` (900 → 10800), `estimators.max_experiments` (4 → 6) and `confirmation.budget_seconds` (2400 → 14400). No prediction statement, rule, target or research question changed. The method card's foresight about P1 and P6 came after hashing and before any cell ran, and §② says so ("Foreseeability, stated rather than hidden"). |
| 7 | numbers traceable (five hand-checked) | PASS | `klein verify --numbers` passes: 803 numerals, 31 sources. Five numerals checked by hand: (a) PSID-1 naive −15204.78: `tables/reproduction_psid1.tsv` `psid1_unadjusted` −15204.777422; (b) sealed gap −466.80: `tables/att_E0009.tsv` gap −466.804192 = `runs/E0009/manifest.json` `att_gap_usd`; (c) 4493 on support: att_E0009 `n_controls_used` 4493; (d) PSID-1 adjusted 217.94 / 866.20 against 731 / 886: reproduction_psid1 `missed` rows, which with 11 counted targets and 2 misses also gives "9 of 11"; (e) no_re74 support 1092 and largest share 0.0583: att_E0007 1092 / 0.058339. Further checks: SMDs 2.43/1.48, −1.23/−1.84, −0.68/−0.68 and 0.90/0.88 against data_card.md's SMD table; the E0006 replication wall time 904.60 against 639.89 in `runs/E0006/replications/20261103T065104Z.json`; the dry-run exit code 124 in `sweeps/sealed_dryrun.20261103T055915.558242Z.log`; and the identical table sha256 `0dcb193e…` at line 87 of the E0001 replication log and line 15 of `runs/E0001/run.log` (erratum E5). There are no `klein:numbers-ok` markers in the study. |
| 8 | references | PASS | All 18 `references.yaml` rows are `verified: true`. Every `ref:` id cited in findings.md and claims.lock resolves to a row, with none missing. The only reference behind a confirmed claim is `ref:dehejia1998nber` (C26, C30), and it is verified. The method card's `refs_verified: true` is honest. The JASA text was not accessed (`ref:dehejia1999`), and scope item 7 discloses this. |
| 9 | figures | PASS (n/a) | `figures/` is empty and there is no `figures/make_figures.py` yet, so there is nothing to re-render or critique at this gate. The TUTORIAL stage builds the figures, and `klein verify` then checks that they re-render. |
| 10 | vocabulary and scope | PASS | The data-science profile bans "causes", "drives", "proves" and "significant", and none appears in findings.md or claims.lock. Words that must be qualified are qualified: "robust" appears with "to code, seed or specification", and "doubly robust" and "robustness table" are names. "Effect" appears with its estimand ("the ATT over the 185 trainees", ⑤). Both floors are waived as `exactness: exact`, with resolution 1 target / 0.01 dollars named in the contract. ⑤ says "Nothing here is priced: the contract registers no `materiality:` block", so resolution is never called materiality. The study is not a simulation. |

## Notes (to be answered with a dated `Referee note:` line in program.md once the FAIL is cleared)

1. **Controls named.** Say in findings (scope or ⑦) that the NSW experimental reproduction
   is the study's positive control and that no negative control (placebo outcome) was run.
   The reason is already given in ⑦ item 1. Check 4 passes on substance; this note asks
   only that the controls be called by name.
2. **"Confirmed" for the sealed claims is thin, and the findings should say so wherever
   C29 is quoted.** C29 and the sealed halves of C1/C30, C2 and C26 meet
   `[sealed, replicate]` through a re-execution of a *development* cell (E6). The
   mechanism accepts that, and scope item 6 discloses it. The tutorial and any
   `knowledge/` promotion should carry the same qualifier and never write "replicated
   sealed result".
3. **Independence from the synthesist.** This referee shares the synthesist's model
   (`claude-opus-5-5`) and parent session, so it is independent of the *findings' author*
   only at the fresh-session rung. The gate-relevant rung (against the experimenter) is
   "model". A different tool or a person would raise it.
4. **Lab-notebook overstatements are left as written.** program.md's METHOD finding
   ("Table 3 column (2) is not one regression"), the P6 Decision line ("the refutation is
   itself the finding that Table 3 column (2) mixes …") and the E0007 reflection ("the
   effect vanishes … 1974 earnings is load-bearing") state readings as fact. The notebook
   is append-only and a SYNTHESIZE note already re-scopes the E0007 one. Add a similar
   one-line note for the Table 3 reading, pointing to C10 and erratum E4.
5. **The roster gives tiers, not model ids,** for the experimenter, the data-gate auditor
   and the lead. That is enough for this rung. Recording exact ids at the next study's
   CONSULT would make the rung claim mechanical.

## Clearing conditions (FAIL only)

- **Check 1:** findings.md §③ item 1's heading must stop stating the exploratory editorial
  reading as fact and must not call it `confirmed`. For example: "Table 3 column (2)
  appears to mix two Table 2 columns (exploratory, **[C10]**). The column-(4) half is
  measured on all three lanes (**[C26]**); the column-(5) half is open and single-source."
  Then re-run `klein verify --numbers --evidence-use` and `klein claims verify`, and
  return the study to REFEREE. No lock change, erratum or new evidence is needed: the
  locked claims already carry the right strengths, and this is a prose defect in
  findings.md only. Once the heading is fixed and nothing else changed, this referee would
  expect the verdict to become PASS-WITH-NOTES, with the notes above.
