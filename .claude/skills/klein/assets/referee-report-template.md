Verdict: {{PASS | PASS-WITH-NOTES | FAIL}}
Referee: {{ACTOR}} ({{TOOL / MODEL}}) · fresh context · independent-of-experimenter: {{yes|no}}
Generation: n/a

# Referee report — {{STUDY_ID}}

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The first two lines above are machine-read by `klein gate record referee`; the
> third is read by people. Leave `Generation:` at `n/a` unless the study has a
> `generation/manifest.yaml`, in which case it is `verified` or `failed` — read
> off `generation/verify_receipt.json`, never re-derived by hand.

## Independence

Rung reached (person > tool > model > backend > fresh session): {{RUNG}}.
Experimenter: {{EXPERIMENTER ACTOR / MODEL}} (from `study_state.json` and the run manifests).

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use` | {{n passed / n warned / n failed; evidence_use_rate}} |
| `klein claims verify` | {{result}} |
| `klein predict list` | {{supported / refuted / inconclusive / open}} |
| figure re-render (`make_figures.py` → temp dir, byte compare) | {{identical / differs: which}} |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS / FAIL | … |
| 2 | predictions adjudicated and reported | PASS / FAIL | … |
| 3 | negative evidence reported | PASS / FAIL | … |
| 4 | controls | PASS / FAIL | … |
| 5 | multiple comparisons | PASS / FAIL | … |
| 6 | pre-registration integrity | PASS / FAIL | … |
| 7 | numbers traceable (five hand-checked: …) | PASS / FAIL | … |
| 8 | references | PASS / FAIL | … |
| 9 | figures | PASS / FAIL | … |
| 10 | vocabulary and scope | PASS / FAIL | … |

## Notes (PASS-WITH-NOTES: each needs a dated `Referee note:` answer in program.md)

1. …

## Clearing conditions (FAIL only)

- Check {{n}}: {{what would clear it}}.
