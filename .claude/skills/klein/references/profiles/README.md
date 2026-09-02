# Profiles — who reads the study, and what is honest to say there

A **profile** adapts Klein's human surface to an audience without touching what the
engine checks. The same contract, ledger, claims law, and referee rubric apply to every
profile; a profile only decides *headings, audience sentences, figure sets, doctrine
anchors, budgets, and vocabulary*. Four ship with Klein 2.0:

| profile | Audience | Reference exhibit |
|---|---|---|
| `generic` | any scientist or analyst | `00-known-truth-quickstart`, `10-hubble-1929-replication` |
| `ml-research` | an ML / deep-learning researcher | `13-charlm-fixed-budget` |
| `math` | a mathematician or algorithm designer | `11-exact-verifier-construction` |
| `insurance` | an actuary or pricing analyst | `12-insurance-claims-frequency`, studies 05–09 |

`generic` is the default. Insurance is a *reference* profile — the discipline was first
proven on insurance data and its vocabulary is the most developed — but it is not the
default and nothing in the core text assumes it.

## The eight knobs a profile controls

| # | Knob | Where it lands |
|---|---|---|
| 1 | The §⑤ heading and its prompt in `findings.md` | `findings-template.md` (`{{SECTION5_HEADING}}`), `synthesis-protocol.md` |
| 2 | The audience sentence of the method card ("explain it to …") | `method-card-template.md` (`{{AUDIENCE}}`) |
| 3 | The doctrine anchor — the standing expectation a study is measured against | method card §4, findings §⑥ |
| 4 | Figure sets and the tutorial's §⑥ heading | `tutorial-spec.md` |
| 5 | Knowledge pointers — which `knowledge/domains/<name>/` docs seed priors | CONSULT prior provenance |
| 6 | The budget table — `max_run_seconds` starting points by **run-cost class** (seconds / minutes / hours per run), never by row count | `defaults-and-scaffolding.md` |
| 7 | The vocabulary seed — words that are banned or must be qualified | `klein verify` vocabulary scan; the referee rubric |
| 8 | CONSULT inference hints — which kinds and modalities this audience usually means | `consult-protocol.md` |

## Adding a profile (no engine change)

1. Write `profiles/<name>.md` with the eight sections below, in order.
2. Either register the name in `kleinlib/schema.py: KNOWN_PROFILES` (a one-line pull
   request) or point a study at the file directly: `profile_doc: docs/profiles/<name>.md`
   (repo-relative). The engine reads neither file — it only checks that the name or path
   exists — so a foreign repo can carry its own profile without forking Klein.
3. Seed `knowledge/domains/<name>/README.md` with the doctrine anchor and one typed
   claim citation once a study in that profile has closed.

## The eight sections of a profile file

```
## 1. Audience        — one sentence: who reads this, what they already know
## 2. §⑤ heading      — the heading + a two-line prompt
## 3. Doctrine        — the standing expectation, with its source
## 4. Figures         — figure sets by task_type; the tutorial §⑥ heading
## 5. Knowledge       — pointers into knowledge/domains/<name>/
## 6. Budgets         — the run-cost-class table
## 7. Vocabulary      — banned words; words that need a qualifier; the honest verbs
## 8. CONSULT hints   — kinds and modalities this audience usually means
```
