# The opt-in generation layer — overview

Moved here from `SKILL.md` in Klein 2.3 so the router stays short: everything below is
optional, and a study that does not opt in is untouched by it. The normative protocol is
`references/generation-protocol.md`; this page is the map of its capabilities.

**Opt-in generation layer (schema 3).** A study may additionally record what it
committed to BEFORE the evidence: `klein generation init` before Gate 0, then one
`klein generation check` before every `run-one`, verified separately by `klein
generation verify` — `references/generation-protocol.md`. A study that does not opt in
is untouched by it, and no core verb, receipt or disposition changes either way.
Declaring `--capability expertise` adds the reproduction obligation: `klein generation
expert lock` freezes `domain_card.md` (pipeline, metrics, doctrine, pitfalls, a
`method_shortlist` that precedes METHOD, and a baseline recipe with numeric targets)
before Gate 0; the baseline runs as an ordinary `run-one` admitted with `--action
baseline`; `klein generation expert bind E0001` adjudicates it, and no challenger run
is admitted until a bind reproduces — repairs are versioned and targets never move
(`references/expert-protocol.md`). Its citations are `klein generation reference
record` entries under `knowledge/references/` — locator, supported statement, source
hash and verification level — because on an enabled study a bare `verified: true` is
insufficient (`references/reference-protocol.md`).
A study that declares the **`slates`** capability additionally records each phase's
hypothesis slate (`klein generation slate lock`, 4–6 authored rows → `<study>#Hn` ids),
admits runs by `--hypothesis`, and scores the driver's own forecasts at phase end
(`klein generation slate score` → `generation/tables/slate_calibration_<phase>.tsv`).
Declaring `--capability design` adds the evidence-design artifact: `klein generation
design lock` freezes `evidence_design.yaml` — estimand, population, units, measurement
process, identification assumptions and intended generalization; uncertainty method,
validity conditions, practical threshold and provenance; evidence representations,
dependency hierarchy, permitted reuse, seal and acquisition custody; the warrant; the
typed continuation — **before Gate 1**, and every validity condition must name a
registered `P#` whose rule can fire it (an `inconclusive_if` rule or an
`all_of`/`any_of`/`not` combinator, never a plain leaf). A `--action cell` admission is
refused until it is locked (`references/generation-protocol.md`, "Evidence design").
Declaring **`premortem`** (which requires `slates`) puts a recorded red team between
the draft slate and the first run: `klein generation premortem record` binds the draft
slate's hash, the reviewer, the hashed input bundle and the issues; `klein generation
premortem respond` records one disposition per issue, and a `blocking` + `mechanical`
issue must be accepted with the hash of a NEW slate version before any hypothesis of
that phase is admitted. The reviewer may not be the roster's referee — the critic is
not the closing referee (`references/premortem-protocol.md`).
Declaring **`parity`** adds the AI-vs-expert comparison: `klein generation parity lock`
freezes `parity.yaml` before Gate 0 (both pipelines, the sampling unit and block, and
each metric's direction, measured-floor reference, noninferiority margin and written
rationale, tied to the registered `P#` whose rule IS that margin); `parity bind` pins
the scorer's hash, both frozen snapshots and the floors, and no `--action sealed`
admission is granted on ANY track until it exists; one sealed registered cell measures;
`klein generation parity assess` recomputes `d/L/U` from the cell's pinned per-unit
table and decides `exceeds | parity | refuted | inconclusive` — an undefined metric can
never pass, and the by-δ agreement check is reported as `agreement_within_floor`,
never as parity. **`contribution`** appends `ai_value.jsonl` through `klein generation
contribution record` (coverage includes rejections; an accepted row with no human
acceptor stays agent-accepted; causal AI value needs the cited matched ablation)
— `references/expert-parity-protocol.md`.
Declaring `--capability escalation` adds the escalation ladder: `klein generation
escalate lock` freezes `escalation_plan.yaml` before Gate 0 — the triggers a stall is
reconstructed from (consecutive discards, closed headroom, an exhausted phase budget),
the five rungs in one fixed order (metric diagnosis → method family → data leverage →
adjacent-field analogy → human expert, with `stop` always available), unit-bearing
budgets, and `stop`/`pivot` as terminal actions. Once a trigger trips, no `run` or
`--hypothesis` admission is granted until `klein generation escalate record` files a
`<study>#Dn` decision naming the concrete changed resource; `escalate close` adds the
actual costs and `escalate pivot` links a successor study with both contract hashes and
its inherited exposure. Editing the plan afterwards cannot discharge a stall
(`references/escalation-protocol.md`).
Declaring `--capability knowledge` couples the study to the repo-level knowledge
store: `klein generation knowledge query` records the consultation receipt CONSULT
cites — pinned `store_head`, deterministic `lex-1` retrieval, COMPLETE hits, each
hit's contest closure, and a use/reject reason for every one, or an explicit
`no_match` — **before** Gate 0; `knowledge promote` imports a VERIFIED claim (or a
method card) with its class, strength and evidence roots copied verbatim;
`contest` and `resolve` append opposing evidence and adjudications without
deleting either side. The markdown under `knowledge/` stays the human surface and
is never rewritten (`references/knowledge-protocol.md`).
Declaring `--capability surprise` (which requires `design`) adds discovery cells:
`klein generation surprise register` freezes `discovery_cells.yaml` after METHOD and
before any cell evidence — template, statistic, adapter and inputs with their hashes,
partition (never sealed), unit and group policy, the COMPLETE segment inventory,
`minimum_n`, and a declared multiplicity rule, because a measured effect floor is not a
multiplicity correction. A cell then runs as an ordinary `klein run-one --tests P#`
(admitted with `--action cell --cell <id>`), and `klein generation surprise record --run
E####` reads the pinned per-unit table, recomputes every segment, and issues one
`<study>#Sn` receipt per violation while retaining the null and inconclusive ones —
explanations stay `unresolved` until a human writes one, and no `confirmed` claim may
rest on a discovery table (`references/surprise-protocol.md`).
Declaring **`benchmark`** (which requires `parity`) makes the study the CUSTODIAN of
a planted-truth benchmark: `klein generation benchmark commit` freezes
`benchmark.yaml` at METHOD — arms and budgets, the hypothesis cap, the matching rule,
the false-positive penalty, disjoint development/sealed seed blocks, the per-arm
recovery `P#`s — and records `sha256(salt ‖ private bundle)` before any participant
sees the public one; `benchmark submit --arm` imports each frozen answer;
`benchmark reveal` recomputes the commitment (a mismatch is refused AND recorded) once
every arm has submitted or has a recorded missing trial; ONE sealed registered cell
then scores all arms, and verification re-applies the matching rule to the pinned
`tables/benchmark_scores.tsv`. Each participant is a separate `discover` study on a
separate machine that declares no `benchmark` capability. **A hash is not secrecy**:
`klein generation custody attest` — capability-agnostic, usable by any
generation-enabled study — records a named holder's testimony, and without one the
outcome reads `unverified` (`references/planted-truth-protocol.md`).
