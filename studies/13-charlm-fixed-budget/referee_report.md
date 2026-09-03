Verdict: PASS-WITH-NOTES
Referee: klein-referee (Claude Code subagent, model: claude-sonnet-5) · fresh context · independent-of-experimenter: yes

# Referee report — 13-charlm-fixed-budget

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

## Independence

Rung reached (person > tool > model > backend > fresh session): **model**.

Experimenter: Claude Code general-purpose subagent · model `claude-opus-5[1m]` ·
session `session_016HefKjsAszSh9M5FJ8Zw4g` (`program.md` `## Roster`, row
"experimenter" — drove CONSULT, DATA, METHOD, every `klein run-one`, the sweeps and
SYNTHESIZE). No run manifest or `study_state.json` field records an actor or model
anywhere (checked: `runs/*/manifest.json` keys, `study_state.json` top level), so the
Roster is, exactly as the protocol anticipates, the only artifact naming what ran the
loop, and it is complete (experimenter row is not blank).

I am running as `claude-sonnet-5`, a different model from the Roster's recorded
`claude-opus-5`, so the rung reached is **model** and `independent-of-experimenter:
yes` agrees with the Roster.

One wrinkle recorded rather than hidden: the Roster's experimenter session id
(`session_016HefKjsAszSh9M5FJ8Zw4g`) is identical to the top-level orchestrating
session id attached to this review's own git-attribution header. This is expected
under the subagent architecture this repository documents (`CLAUDE.md`): the
Roster's "session" column names the enclosing lead session that spawns each stage's
subagent (CONSULT through REFEREE), not an isolated per-subagent context. The
protocol's actual independence requirement is a fresh context on a different model,
and both hold: I received nothing but the study directory and the protocol, with no
memory of the experimenter's loop, and I am a different model than the one the
Roster names. The rung claimed is "model", unaffected by the shared enclosing
session id.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --study studies/13-charlm-fixed-budget --numbers --evidence-use --no-receipt` | 35 checks, 0 failed; `evidence_use_rate` 1.00 (11/11 cited); `convergent evidence`: 2/2 confirmed claims cite ≥2 evidence kinds; `findings numbers`: all 97 scanned numerals trace to 26 pinned sources; figure re-render OK |
| `klein claims verify --study studies/13-charlm-fixed-budget --numbers` | 7 checks, 0 failed |
| `klein predict list --study studies/13-charlm-fixed-budget` | 2 supported (P1, P4), 4 refuted (P2, P3, P5, P6), 0 inconclusive, 0 open — matches findings §② exactly |
| figure re-render (`figures/make_figures.py` → scratch dir, byte compare) | identical: `learning_curves.png`, `seed_variance.png`, `candidate_effects.png`, `trajectory.png` (re-run independently of `klein verify`'s own report; worktree confirmed clean afterward with `git status --short`) |
| `KLEIN_DEVICE=cpu KLEIN_ARTIFACT=models/E0006.pt uv run --locked python -u verify.py` (fresh process, independent of `klein run-one`) | `val_loss 1.519319` — exact match to the pinned manifest's verified value (`runs/E0006/manifest.json: metric.verified = 1.519319`); printed `verifier_gap 0.00000003` nats (trainer-reported vs. this fresh CPU re-derivation), far inside the declared `0.01` tolerance. Device used: **CPU**. |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS | Only C4 and C5 are `confirmed`; both cite ≥2 evidence kinds per `kleinlib/checks.py:1326-1328` ("a development run (E####) + a sealed final test" or a `rep:`/`verify:` record) — C4: `E0006` (development) + `E0008` (sealed); C5: `E0001..E0008` (mixed development/sealed) + `sweep:harness_controls`. `klein verify`'s "convergent evidence" check confirms both. All other claims (C1,C2,C3,C6,C7 empirical/mechanism; C8-C13 research-discipline) are labelled `exploratory` in `claims.lock` and findings.md's Strength column, and findings.md's post-table "Strength note" (line 39-44) explains why in one arithmetic sentence ("one track means one sealed number, and a gap needs two"). No claim's prose overclaims its evidence on a line-by-line read of §①-§③. |
| 2 | predictions adjudicated and reported | PASS | `klein predict list`: 2 supported / 4 refuted / 0 inconclusive / 0 open, matching findings §②'s own tally verbatim. All four refuted predictions carry dated `Decision:` lines in `program.md`, each quoted verbatim (not paraphrased) by findings §②'s Decision column — checked P2 (`program.md:286-288`), P3 (`:298-300`), P5 (`:321-323`), P6 (`:402-404`) word-for-word against the findings citations; all match exactly. `klein verify`: "[OK] belief revision" and "[OK] predictions closure". |
| 3 | negative evidence reported | PASS | `evidence_use_rate` 1.00 (11/11 non-keep runs + registered sweeps cited); `klein status`: "0 refutation(s) without a recorded decision, 0 single-source confirmed claim(s)". The 6-run discard cluster (E0002, E0003, E0004, E0005, E0007, plus the by-design-discard sealed E0008) is written up as findings, not silently dropped: §① C1's row and §③ surprises 1, 2, 4 and 5 name every one of them with its number and reading; `program.md`'s phase logs give each its own dated paragraph. Zero crashes exist anywhere in the study (`crash=0` in `klein status`; all 8 run manifests show `exit_code: 0`), so no crash-vs-verdict conflation is possible. |
| 4 | controls | PASS | `sweep:harness_controls` (`tables/harness_controls.tsv`, 4/4 PASS) supplies two negative controls (`uniform` = chance = 4.174388 nats; `untrained_network` = 4.305432, no better than chance) and one positive control (`unigram_train_fit` = 3.306991, strictly better than chance) plus a second, targeted negative control (`copy_input` = 4.750043, worse than chance — the classic off-by-one-alignment catcher, which would score `0.693147` under the bug). All four are explicitly named with the word "control" and a pos/neg role in `data_card.md` §"Clean-room leakage audit" row 4, in `claims.lock`'s number notes (`control_uniform`, `control_untrained`, `control_unigram`, `control_copy`), and in findings **[C5]**/**[C11]**. |
| 5 | multiple comparisons | PASS | Findings §② states `n_comparisons = 6` explicitly, discloses that no family-wise correction is applied or claimed, and reasons about which of the six effects would/would not survive one (P3 at −11.3693 floors and P4 at −4.7255 floors "far outside any plausible multiplicity correction"; P5 at −0.4742 "would not survive one"). Neither confirmed claim (C4, C5) is drawn from this unguarded 6-prediction family: C4 rests on the single sealed run E0008 (a level, not a multiple-comparison test), C5 rests on the harness/guardrail record across all runs (a procedural fact, not a significance test). |
| 6 | pre-registration integrity | PASS | Walked `events.jsonl` end to end. All six predictions and the `0.01`-nat verifier tolerance were registered at the FIRST consult gate (`11:38:55Z`), before `study.yaml` was ever amended. Two later consult RE-RECORDs are both dated and reasoned in `study_state.json:gates.consult.note` and mirrored in `program.md`'s Decisions log: the floor-setting re-record (`12:07:18Z`, sets `minimum_delta = 0.0149525`) happened **before** E0001's `run_started` event (`12:10:16Z`); the phase-id-rename re-record (`12:09:09Z`, cosmetic only) also precedes it. Both re-record notes state explicitly that no prediction's rule changed. The one DATA-gate re-record (`11:50:01Z`, fingerprint-labelling only) precedes any run by 20 minutes. No prediction rule is an absolute-nats number: all six use small integer counts (`2, 1, 1, -1, 1, 2`) of floors or fit-noise standard deviations, fixed before the floor itself existed. |
| 7 | numbers traceable (six hand-checked: `e0003_floors`, `sealed_gap_floors`, `control_copy`, `headroom_h`, `tying_params_removed`, `replication_difference`) | PASS | `klein verify --numbers`: "all 97 scanned numerals trace to 26 pinned source(s)". I independently hand-checked six numerals against their pinned artifacts (one more than the protocol's minimum of five): `e0003_floors = -11.3693` ↔ `tables/frontier.tsv` row E0003 exactly; `sealed_gap_floors = 3.140679` ↔ `tables/study_summary.tsv:6` exactly; `control_copy = 4.750043` ↔ `tables/harness_controls.tsv` row `copy_input` exactly; headroom `h ≈ 101.6` ↔ `tables/study_summary.tsv:2` (`101.609697`) and the live `verify_receipt.json` message ("h = ... = 101.610") exactly; `tying_params_removed = 8320` ↔ derived independently from raw manifests BEFORE reading the pinned table (`E0001.metrics.n_params 824320 − E0003.metrics.n_params 816000 = 8320`), then confirmed identical to `tables/study_summary.tsv:12`; `replication_difference = 0.000962` ↔ `study_state.json:replications.E0001.records[0].difference` exactly. No `klein:numbers-ok` markers exist anywhere in this study (grepped `.`), so there is nothing to adjudicate on that front. |
| 8 | references | PASS | `references.yaml`: 10/10 entries `verified: true`, dated 2026-09-03, each with a `why` tying it to a specific prediction or design choice; `method_card.md`'s own reference table matches 1:1 and `refs_verified: true` in its front matter is honest. Neither confirmed claim (C4, C5) cites any `ref:` evidence id at all, so the "unverified reference behind a confirmed claim" trigger cannot occur structurally; no reference anywhere in the study is marked UNVERIFIED. |
| 9 | figures | PASS, with a note | Independently re-ran `figures/make_figures.py` into a scratch directory from the repo root and byte-compared all four PNGs with `cmp` — identical, confirmed separately from `klein verify`'s own report; the worktree was clean afterward. Axis labels are unit-bearing throughout (`nats / character`, `optimizer steps (log scale)`, etc.); the log scale is declared on its own axis label. `seed_variance.png`'s bar panel is explicitly zero-based (labelled "zero-based bars", y-axis 0–1.8) and `candidate_effects.png`'s diverging floor-unit bars originate at 0. **Note:** `learning_curves.png`'s two series (anchor vs. cosine decay) are plotted with the identical marker shape and linestyle (`marker="o"`, solid line — `figures/make_figures.py:222-228`), differing only by hue (`#7570b3` vs `#1b9e77`, whose approximate grayscale luminances, 121 vs 114, are close enough to be hard to tell apart desaturated) — a partial gap against `tutorial-spec.md`'s figure-critique point 3 ("marks stay distinguishable in grayscale... never hue alone"). This does not meet check 9's own FAIL trigger (a re-render mismatch or a truncated axis inflating a within-noise delta), and every value on the chart is redundantly annotated in text (a text legend plus colour-matched end-value labels), so no number or conclusion is actually obscured by it — but it is a real, cheaply fixable gap against the letter of the critique. |
| 10 | vocabulary and scope | PASS, with a note | Grepped `findings.md` and `claims.lock` for the ml-research profile's banned/qualify list (`references/profiles/ml-research.md` §7: "material", "actionable", "significant", "SOTA", "beats", "converged", "faster", "generalizes"). "materiality" appears once (`findings.md:187`), used to explicitly DISCLAIM a materiality block ("This study registers no `materiality:` block") — confirmed accurate by grepping `study.yaml`, which has none. "converged"/"faster"/"generalizes"/"actionable"/"significant"/"SOTA" do not appear at all. **Note:** "beats" appears once, not in any claim's operative sentence but in `claims.lock`'s `control_unigram` number annotation ("real but minimal information beats chance", `claims.lock:328`) — describing a diagnostic control's expected, definitional behaviour (any fitted model beats an uninformative one) rather than a recipe-versus-floor performance claim, and the operative C5 claim sentence states the same four control numbers plainly with no "beats" framing. It still lacks the profile's literal "floor and matched budget" qualifier, so I record it as a hygiene note rather than resolve the ambiguity myself; I do not read it as the kind of unqualified performance overclaim the ban exists to catch, since it appears in provenance metadata, not in a reader-facing finding, and the number and its role are stated correctly everywhere else the same fact appears (`data_card.md`, findings **[C5]**). The engine's own headroom disclosure (`h = 101.610` floors, `tables/study_summary.tsv:2`, `verify_receipt.json`) is stated as "not excluded... NOT plausible" by the tool itself; findings.md does not repeat or restate it at all (a legitimate choice, since disclosure happens at preflight/verify rather than being mandated in prose), and `program.md`'s two mentions (`:164`, `:391`, "≈105"/"≈102 floors") both say "not excluded" and never "plausible". Every confirmed claim names its estimand precisely (`val_loss` nats/character on a named partition, under named matched-compute guardrails); the modality is text, not simulation, so no in-silico scope tag applies; no measurement-resolution value is sold as materiality anywhere I found. |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md)

1. `figures/make_figures.py:222-228` (`figure_learning_curves`) differentiates the
   anchor and cosine-decay series by colour alone (same marker, same linestyle).
   Add a linestyle or marker distinction (e.g. dashed vs. solid, or a different
   marker shape) the next time this figure is regenerated, for full compliance
   with `tutorial-spec.md`'s grayscale/colour-blind legend-readability point. Not
   blocking — every value the chart carries is independently legible from its text
   annotations — but worth a dated acknowledgement before `klein finalize`.
2. `claims.lock`'s `control_unigram` number note (line 328, "... beats chance")
   uses the ml-research profile's banned word "beats" without its literal "floor
   and matched budget" qualifier. The usage describes a diagnostic eval-harness
   control, not a recipe-performance comparison, and is not part of any claim's
   operative sentence — my reading is that this does not misrepresent evidence —
   but for strict vocabulary hygiene, retitle the note (e.g. "exceeds chance") on
   the next lock revision that touches this artifact (append-only: a note-only
   wording fix, not a value or claim-text change, is unaffected by the
   append-only law's "no `value` or `art` changes" restriction, but confirm that
   reading with `klein claims verify` before touching it).

## Clearing conditions (FAIL only)

Not applicable — no FAIL condition holds on any of the ten checks.
