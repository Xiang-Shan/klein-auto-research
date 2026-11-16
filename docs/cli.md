# `klein` — command reference

Generated from the command line itself by `scripts/gen_cli_reference.py`; do not edit.
Every verb accepts `--help` (the full text) and `--json` (one versioned envelope —
`docs/embedding.md`). Terms are defined in the glossary: `klein explain <term>`.

## Start

| Verb | What it does | Options |
|---|---|---|
| `klein demo` | watch a real study run: scaffold, a probe, three gates, a measured bar, three notarized runs | `--dir` `--quiet` |
| `klein new` | scaffold a study: a typed contract, templates and an empty ledger | `--root` `--goal` `--domain` `--target` `--task-type` `--recipe` `--runner` `--method-depth` `--family` `--kind` `--modality` `--profile` `--profile-doc` `--audience` `--track` `--metric` `--goal-direction` `--minimum-delta` `--data` `--prepared-path` `--split-kind` `--group-column` `--time-column` `--split-seed` `--max-run-seconds` |
| `klein doctor` | report environment and data-source readiness — never fetches, never mutates a study | `--study` `--host` `--strict` |
| `klein explain` | print a protocol or a glossary term (run with no topic for the list) |  |
| `klein skill …` | the protocols and worker agents that ship with Klein | |
| `klein skill install` | copy the skill and the worker agents into a repository (default: the current one) | `--target` `--no-agents` `--force` |
| `klein skill path` | print where the skill resolves from on this machine |  |

## Look and plan

| Verb | What it does | Options |
|---|---|---|
| `klein probe` | run one exploratory command on the record: logged, hash-chained, never at sealed data, never claim evidence | `--study` `--note` `--timeout` `--list` `--quiet` |
| `klein next` | the ONE next action this study needs, with the exact command (read-only) | `--study` |
| `klein status` | show gates, frontiers, transactions, and sealed-test use | `--study` |
| `klein map` | the study as a map: question → predictions → evidence → claims → decisions, and what is still open | `--study` `--html` |

## Gates

| Verb | What it does | Options |
|---|---|---|
| `klein gate …` | record or explicitly override a gate | |
| `klein gate record` | record a gate acknowledgement (artifact must exist, placeholder-free) | `--study` `--acknowledged-by` `--note` `--phase` |
| `klein gate override` | proceed against a gate's conclusion, with a recorded reason | `--study` `--acknowledged-by` `--note` `--phase` `--reason` |
| `klein headroom …` | acknowledge a keep-infeasible frontier (headroom h < 1) before spending transactions | |
| `klein headroom ack` | register awareness that no keep is arithmetically possible on a track | `--study` `--track` `--acknowledged-by` `--note` |
| `klein stop …` | acknowledge a fired stop rule (consecutive discards) before spending more | |
| `klein stop ack` | record the branch taken at a fired stop rule (valid for that count) | `--study` `--track` `--acknowledged-by` `--note` |

## Run

| Verb | What it does | Options |
|---|---|---|
| `klein preflight` | enforce gates, git, fingerprints, and ledger integrity | `--study` `--allow-dirty` |
| `klein noise-floor` | compute the measured noise floor from a k-seed sweep; prints the study.yaml block | `--study` `--track` `--sidecar` `--values` `--seeds` `--measured-after` `--recipe` `--method` `--estimand` |
| `klein run-one` | commit and execute exactly one candidate transaction | `--study` `--track` `--description` `--timeout-seconds` `--final-test` `--dry-run` `--tests` `--quiet` `--allow-rerun` `--detach` `--collect` `--abandon` `--reason` `--command` |
| `klein job …` | execute a detached run's job bundle (Klein 2.3) | |
| `klein job exec` | run runs/E####/job.json and write job_result/ + receipt.json for --collect | `--executor` `--quiet` |
| `klein recover` | finish an interrupted evidence transaction | `--study` |
| `klein sweep …` | register a measurement sweep so findings can cite it as sweep:<name> | |
| `klein sweep register` | hash a sweep's sidecar + script into state.sweeps and log the event | `--study` `--sidecar` `--script` |
| `klein replicate` | re-execute a development run and record whether its number reproduces | `--study` `--tolerance` `--verify-only` `--replay` `--list` `--timeout-seconds` `--quiet` |

## Close

| Verb | What it does | Options |
|---|---|---|
| `klein summarize` | summarize a results ledger (results_summary.md, progress.svg); arguments pass through |  |
| `klein predict …` | read the predictions ledger, or adjudicate a prediction by hand | |
| `klein predict list` | every registered prediction with its ledger verdict, evidence and rule | `--study` `--open` |
| `klein predict adjudicate` | record a verdict from evidence the notary cannot read (sidecar, external, human) | `--study` `--verdict` `--evidence` `--note` `--acknowledged-by` `--force` `--reason` |
| `klein claims …` | author and verify claims.lock — the machine surface under findings.md | |
| `klein claims init` | write the skeleton lock: claims from findings' **[Cn]** lines, numbers empty | `--study` |
| `klein claims pin` | pin an artifact by alias: study-relative path + sha256 | `--study` |
| `klein claims number` | give a headline value a home: artifact + claim | `--study` `--value` `--art` `--claim` `--precision` `--note` |
| `klein claims add` | record a claim with its class, strength and evidence | `--study` `--class` `--strength` `--claim` `--numbers` `--evidence` `--scope` |
| `klein claims erratum` | re-scope claims without deleting them (tag, optionally downgrade) | `--study` `--claims` `--note` `--strength` |
| `klein claims apply` | apply one YAML file of pins, numbers and claims in a single commit (all or nothing) | `--study` |
| `klein claims verify` | run the seven checks of the claims law | `--study` `--numbers` `--strict` |
| `klein refs …` | resolve references.yaml DOIs / arXiv ids against Crossref, OpenAlex and arXiv (network) | |
| `klein refs verify` | look up every DOI / arXiv id and compare titles; refused under KLEIN_OFFLINE=1 | `--study` `--key` `--record` |
| `klein report …` | the teaching report (TUTORIAL stage) | |
| `klein report build` | build report/index.html for a study; arguments pass through to the builder |  |
| `klein finalize` | mark findings exploratory or confirmed | `--study` `--allow-exploratory` `--allow-open-predictions` `--no-referee` `--reason` |
| `klein verify` | re-check the whole study: contract, gates, ledger, predictions, claims, numbers; writes a receipt (--no-receipt only reads) | `--study` `--require-local` `--numbers` `--claims` `--evidence-use` `--no-receipt` `--strict` |

## Hosts

| Verb | What it does | Options |
|---|---|---|
| `klein mcp` | serve read-only Klein tools over MCP stdio (list_studies, next, status, map, doctor, preflight, verify, predictions, claims_verify, explain) | `--root` |
| `klein notebook` | write a run as a reading-copy .ipynb: the executed source at its candidate commit + its printed block | `--study` `--out` |

## Plug-ins

| Verb | What it does | Options |
|---|---|---|
| `klein generation …` | opt-in generation layer: admission receipts before actions, verified after | |
| `klein generation init` | opt in: write generation/manifest.yaml and anchor it before CONSULT | `--study` `--actor` `--tool` `--model` `--session` `--capability` `--predecessor` `--successor-receipt` `--custody-holder` `--custody-mechanism` `--allow-late` |
| `klein generation check` | record one admission receipt BEFORE one action (a refusal is evidence) | `--study` `--actor` `--tool` `--model` `--session` `--action` `--track` `--tests` `--hypothesis` `--cell` `--obligation` |
| `klein generation verify` | audit the generation ledger and write generation/verify_receipt.json | `--study` |
| `klein generation label` | issue generation/label.json — needs BOTH audits passing at this HEAD | `--study` `--actor` `--tool` `--model` `--session` |
| `klein generation status` | read-only summary; writes nothing, commits nothing | `--study` |
| `klein generation recover` | void orphan objects (append-only) and file an uncommitted ledger | `--study` `--actor` `--tool` `--model` `--session` |
| `klein generation expert …` | the expertise obligation: lock the domain card, reproduce its baseline, bind it | |
| `klein generation expert lock` | freeze domain_card.md and its baseline targets (before the CONSULT gate) | `--study` `--actor` `--tool` `--model` `--session` `--allow-late` |
| `klein generation expert amend` | record a new card version with parents; baseline targets may NOT change | `--study` `--actor` `--tool` `--model` `--session` |
| `klein generation expert bind` | adjudicate one baseline/repair run against the frozen targets | `--study` `--actor` `--tool` `--model` `--session` |
| `klein generation expert repair` | record a versioned repair after a bind that did not reproduce | `--study` `--actor` `--tool` `--model` `--session` `--changed` `--note` |
| `klein generation expert review` | record a practitioner's review of the reproduced baseline (testimony) | `--study` `--actor` `--tool` `--model` `--session` `--reviewer` `--reviewer-model` `--reviewer-tool` `--session-receipt` `--statement` |
| `klein generation reference …` | reference records: what a citation rests on, and how closely it was checked | |
| `klein generation reference record` | write one reference record | `--study` `--actor` `--tool` `--model` `--session` `--id` `--title` `--year` `--authors` `--venue` `--identifier` `--locator` `--statement` `--basis` `--blob` `--retained` `--checker` `--supersedes` |
| `klein generation slate …` | record a phase's authored hypotheses and score the forecasts afterwards | |
| `klein generation slate lock` | lock version 1 of a phase's slate | `--study` `--actor` `--tool` `--model` `--session` `--phase` |
| `klein generation slate amend` | record the next version of a locked slate (ids are never recycled) | `--study` `--actor` `--tool` `--model` `--session` `--phase` |
| `klein generation slate score` | close the cohort and compute the phase's calibration table | `--study` `--actor` `--tool` `--model` `--session` `--phase` `--rescore` `--reason` |
| `klein generation slate show` | read-only: versions, cohort, panels | `--study` `--phase` |
| `klein generation design …` | the evidence design: what the evidence is FOR, locked before the DATA gate | |
| `klein generation design lock` | freeze evidence_design.yaml (before the DATA gate is recorded) | `--study` `--actor` `--tool` `--model` `--session` `--allow-late` |
| `klein generation premortem …` | record a red team's review of a DRAFT slate, and the driver's answer to it | |
| `klein generation premortem record` | record the review of a phase's draft slate (responses stay empty) | `--study` `--actor` `--tool` `--model` `--session` `--phase` `--session-receipt` `--allow-late` |
| `klein generation premortem respond` | record one disposition per issue (accept | reject | defer) | `--study` `--actor` `--tool` `--model` `--session` `--phase` |
| `klein generation parity …` | one registered vector comparison of the AI and expert pipelines | |
| `klein generation parity lock` | freeze parity.yaml's criteria (before the CONSULT gate) | `--study` `--actor` `--tool` `--model` `--session` `--allow-late` |
| `klein generation parity amend` | record a new version with parents; the metric set, margins and uncertainty rule may NOT change | `--study` `--actor` `--tool` `--model` `--session` |
| `klein generation parity bind` | pin the scorer, both frozen pipelines and every measured floor | `--study` `--actor` `--tool` `--model` `--session` `--floor-run` `--ai-snapshot` `--expert-snapshot` |
| `klein generation parity assess` | recompute d/L/U from the sealed cell's pinned table and decide | `--study` `--actor` `--tool` `--model` `--session` `--run` |
| `klein generation parity show` | read-only: versions, bind, assessments | `--study` |
| `klein generation contribution …` | the AI-value ledger: proposals, decisions, rejections and errors | |
| `klein generation contribution record` | append one ledger line | `--study` `--actor` `--tool` `--model` `--session` `--kind` `--subject` `--origin` `--decision` `--human-acceptor` `--implementation-ref` `--refs` `--outcome` `--cost` `--transcript-hash` |
| `klein generation contribution show` | read-only: the ledger and its coverage | `--study` |
| `klein generation escalate …` | the escalation ladder: account for getting unstuck, before you do it | |
| `klein generation escalate lock` | freeze escalation_plan.yaml (before the CONSULT gate is recorded) | `--study` `--actor` `--tool` `--model` `--session` `--allow-late` |
| `klein generation escalate record` | file one <study>#Dn escalation decision BEFORE its action | `--study` `--actor` `--tool` `--model` `--session` `--trigger` `--track` `--rung` `--skip` `--action` `--changed` `--rationale` `--estimated-cost` `--next` `--successor` `--advisor` `--advice` `--advice-accepted` `--advice-cost` |
| `klein generation escalate close` | add the outcome and the actual costs to an open decision | `--study` `--actor` `--tool` `--model` `--session` `--decision` `--actual-cost` `--cost-evidence` `--outcome` |
| `klein generation escalate pivot` | link a successor study: both contract hashes, and everything already seen | `--study` `--actor` `--tool` `--model` `--session` `--decision` `--successor` `--new-contract` `--inherited` |
| `klein generation escalate show` | read-only: the plan, the live trigger counts, the decisions | `--study` |
| `klein generation knowledge …` | the repo-level knowledge store: promote, contest, resolve, and consult it | |
| `klein generation knowledge promote` | import one verified claim (or a method card) into the store | `--study` `--actor` `--tool` `--model` `--session` `--claim` `--method` `--tags` `--scope` `--dependency` `--rationale` |
| `klein generation knowledge contest` | attach contradicting evidence to a store object (nothing is deleted) | `--study` `--actor` `--tool` `--model` `--session` `--target` `--evidence` `--rationale` |
| `klein generation knowledge resolve` | adjudicate a contested object; the object and the contest both stay | `--study` `--actor` `--tool` `--model` `--session` `--target` `--outcome` `--rationale` |
| `klein generation knowledge query` | consult the store BEFORE the CONSULT ack and record the receipt | `--study` `--actor` `--tool` `--model` `--session` `--tags` `--text` `--limit` `--use` `--reject` |
| `klein generation knowledge decide` | record use/reject reasons for hits an earlier receipt left open | `--study` `--actor` `--tool` `--model` `--session` `--use` `--reject` |
| `klein generation knowledge show` | read-only: objects, contests, resolutions | `--study` `--target` |
| `klein generation surprise …` | register the discovery search space, then record what its tables found | |
| `klein generation surprise register` | lock discovery_cells.yaml (after METHOD, before any cell evidence) | `--study` `--actor` `--tool` `--model` `--session` |
| `klein generation surprise record` | read one cell run's pinned table and record every segment | `--study` `--actor` `--tool` `--model` `--session` `--run` `--cell` `--explain` |
| `klein generation surprise show` | read-only: cells, records, receipts | `--study` `--cell` |
| `klein generation benchmark …` | the custodian's planted-truth benchmark: commit, import, reveal | |
| `klein generation benchmark commit` | freeze benchmark.yaml and record the salted commitment | `--study` `--actor` `--tool` `--model` `--session` `--private` `--salt-file` |
| `klein generation benchmark submit` | import one arm's frozen submission (before the reveal) | `--study` `--actor` `--tool` `--model` `--session` `--arm` `--file` |
| `klein generation benchmark reveal` | disclose the private bundle and recompute the commitment | `--study` `--actor` `--tool` `--model` `--session` `--private` `--salt-file` `--missing-arm` |
| `klein generation benchmark retire` | retire a leaked benchmark from hidden evaluation; results are retained | `--study` `--actor` `--tool` `--model` `--session` `--reason` |
| `klein generation benchmark show` | read-only: the commitment, the submissions, the reveal | `--study` |
| `klein generation custody …` | record who holds hidden evidence and how — testimony, never verified | |
| `klein generation custody attest` | record one custody attestation | `--study` `--actor` `--tool` `--model` `--session` `--holder` `--mechanism` `--statement` `--subject` `--receipt` |
