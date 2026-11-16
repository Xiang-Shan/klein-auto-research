# Klein 3 — from a notary to a research instrument

Klein 2 answered one question well: *can I sign this conclusion?* It built a trust kernel
— predictions registered before their evidence, runs notarized in git, claims locked to
pinned numbers, a referee who did not run the loop — and proved it on eleven studies
across seven domains. This document records why Klein 3 is shaped as it is. The kernel's
judgment did not change. What changed is everything a researcher meets before and after
it.

Earlier rationale, still valid for the parts it covers: [`klein-2-design.md`](klein-2-design.md)
(the inquiry model, the science layer) and [`klein-2.3-design.md`](klein-2.3-design.md)
(domain packs, host bridges).

## 1. The aim

> **Every study should leave the researcher understanding more than the agent that ran
> it — and leave a stranger able to check why.**

A notary certifies. An instrument lets you see. Klein 2 certified research an agent had
done; it did little for the two things a researcher does most — looking around, and
making sense of what was found. Klein 3 keeps the certification and adds the seeing.

| | Promise | What makes it true in 3.0 |
|---|---|---|
| **Explore** | Looking is cheap and always on the record | `klein probe`: one bounded command, hash-chained in `probes.jsonl`, fenced from the sealed data, never claim evidence |
| **Understand** | A study is a map, not a metric | `klein map`: question → predictions → runs → claims → decisions, with what is open and what a follow-up would start from |
| **Trust** | A kernel small enough to audit | one schema, one registry for the three axes, the generation layer outside the kernel's imports |
| *General* | A new domain is data, not surgery | a profile or a modality is one registry entry; a plug-in adds them, and verbs, with no core edit |
| *Embeddable* | Works anywhere, speaks one shape | every verb takes `--json`; `kleinlib.api`; the whole skill ships in the wheel; a Claude Code plug-in |

And one target for the first five minutes: `klein demo` runs a real, tiny study live.

## 2. Why process, not outcome

In April 2026 a study of more than 25,000 runs of AI-scientist systems across eight
domains (Ríos-García, Jablonka et al., [arXiv:2604.18805](https://arxiv.org/abs/2604.18805))
found that agents produce results without reasoning scientifically, and that
outcome-based evaluation cannot detect it. Scaffolding explained 1.5 % of outcome
variance. No scaffold makes a model reason better; what a scaffold can do is make the
failures detectable — mechanically, with no model checking itself:

| Failure the 2026 study measured | What Klein makes mechanical |
|---|---|
| **Evidence ignored** — 68 % of traces | Every candidate is committed *before* it runs; `klein verify` reports the runs the write-up never mentions |
| **No belief revision on refutation** — 26 % revise | Predictions carry an arithmetic rule; a refuted one with no dated `Decision:` line fails verification |
| **Convergent evidence rare** | One sealed look per track; `confirmed` needs the evidence kinds the track requires, and single-source confirmations are flagged |
| **Outcome evaluation cannot see it** | An independent referee applies a fixed ten-check rubric before `finalize` |

Klein 3 adds the one failure that table does not name and every exploratory analysis
has: **what was looked at before the prediction was made.** Until now that lived in a
hand-written ledger. A probe puts it on a hash, and the consult gate records how many
probes preceded it.

## 3. Decisions worth defending

**One schema, and older studies verify where they were judged.** Klein 2 promised that
schema-2 studies "verify under schema-2 rules forever", and kept the promise with about
seventy `if version >= 3` branches across thirteen modules. Every new feature then had
to answer "and on schema 2?". Klein 3 keeps the promise a different way, the way version 1
already did: a schema-2 study verifies with the engine that notarized it, at tag
`v2.3.1`. Nothing was rewritten; `load_contract` refuses an older study once, with the
tag. The engine has one rule set and a reader can hold it in their head.

**Nine studies archived, not deleted.** The repository shipped seventeen studies; four
asked the same iris question and six were in the older format with no claims lock or
referee. Eight remain, one refereed study per domain and kind of question.
`studies/ARCHIVE.md` and `studies/archive.yaml` record the commit where each archived
study verifies and list its claim ids, so the typed citations in `knowledge/` still
resolve — the lessons those studies paid for stay in force.

**Kinds are closed; modalities and profiles are open.** The three axes were spread over
three modules and re-derived in a fourth. They now live in `kleinlib/inquiry.py`. A kind
fixes how a track is judged — its default mode, what confirmation requires, whether a
checker is mandatory — so adding one is a change to the kernel. A modality only selects
data-card headings and a profile only selects wording, so a plug-in may add either.

**The generation layer is a plug-in, and proves the seam.** It was a third of the engine,
opt-in, and unused by any exhibit, yet its 5,177-line command file sat in the kernel's
import list. It is now loaded through `kleinlib/plugins.py` exactly as a third-party
plug-in would be, its commands split one module per capability. A plug-in that fails to
load is reported by `klein doctor` and cannot break a core verb.

**A plug-in can add, never judge — as far as a surface can promise.** The plug-in surface
is verbs, profiles, modalities and read-only MCP tools. Dispositions, the claims law and
the receipts are not on it; a built-in name cannot be shadowed; a plug-in that fails, or
reaches for a core verb, is undone and reported. But a plug-in is installed Python code in
the same process, and no surface can stop code from misbehaving. So the honest version of
the promise has a second half: a receipt issued with third-party plug-ins loaded names
them, and `KLEIN_NO_PLUGINS=1` verifies a study without any.

**A probe is not a light run.** The tempting design was a "quick run" with fewer gates.
That would have created a second, weaker kind of evidence. A probe is deliberately not
evidence at all: it has no disposition, no result row, and its id does not resolve in the
claims law. What it earns is a prediction, which an ordinary run then decides. The
exploratory and the confirmatory stay separate by construction.

**The fence is honest about what it fences.** Under `KLEIN_PROBE=1` the split loader
returns the sealed partition empty and refuses a sealed read. A script that opens the raw
file itself, or a simulator that picks its own sealed seeds, is not stopped — and the
protocol says so, because the script's hash is on the record and a referee reads it. A
guarantee Klein cannot enforce is not claimed. The variable itself is fenced the other
way too: only a probe's child ever sees it, so an exported `KLEIN_PROBE=1` cannot empty
the sealed partition a gate fingerprints.

**A probe ledger has two witnesses.** A hash chain alone detects edits, not truncation
or deletion. Each probe therefore also leaves an event in the study's own event chain,
and verification compares the two; the first consult record is the anchor for "what was
looked at before the question was fixed", and re-recording the gate cannot move it. Both
weaknesses were found by the independent review this release was put through before it
shipped — the same rule the framework applies to studies.

**The map is derived, never a record.** `klein map` joins what the contract, the ledger,
the manifests, the lock and the notebook already say. It writes nothing of its own, so it
cannot disagree with the record, and nothing the engine judges depends on it. It separates
`open` (what must be resolved before closing) from `leads` (legitimate final states that
say where a follow-up starts): an exploratory claim is not a defect.

**One envelope, three seams.** `kleinlib.api`, `klein <verb> --json` and the MCP server
return the same `data`. The envelope carries a `format` number so a host can depend on
it. `--json` is implemented once, around the dispatcher: a verb with structured output
fills `data`; any other verb's text comes back as `data.text`, so *every* verb is usable
by a host on day one rather than only the ones someone got round to.

**The API's `verify` reads; the command line's writes.** `klein verify` writes and
commits a receipt because the study's owner runs it. A host checking a study it does not
own must not commit to it, so `api.verify` defaults to `receipt=False`. The old
quickstart had this backwards and committed to the reader's clone.

**The MCP server stays read-only.** A tool that recorded a gate would let a model
acknowledge for a person; an experiment outlives a tool call. Hosts write through the
API or the command line, where the acknowledger is named.

**The skill ships in the wheel.** Protocols, templates, profiles, the two report scripts
and the worker agents were reachable only from a checkout, so an installed Klein could
not run its own TUTORIAL stage or explain its own stages. They are package data now,
resolved by one function (`kleinlib/resources.py`): the host repository's pinned copy
first, then the package. `klein explain` and `klein skill install` are the two verbs a
reader needs.

**One list of verbs.** The verb list was hand-kept in five places and one had drifted.
`docs/cli.md` is generated from the parser and a test fails when it is stale.

## 4. What was removed, and where it lives

| Removed from the tree | Where it is |
|---|---|
| Studies 03, 05, 06, 07, 08, 09, 13, 15, 24 | commit `217cd46` (release 2.3.1); index in `studies/ARCHIVE.md` |
| The schema-2 rule set, the version-1 reader, `--schema-version` | tag `v2.3.1` / `v1.3.0` |
| Datasets used only by archived studies (hurricane, tinyshakespeare) | commit `217cd46` |
| `docs/reviews/`, the schema 2→3 migration note | commit `217cd46` |
| `kleinlib/cli_generation.py` | split into `kleinlib/generation/cli/` |

## 5. What did not change

No rule a kept study was judged under moved. The eight exhibits verify with the same
checks, the same passes and the same warnings as under 2.3.1, and CI re-verifies them on
every push. The notary's transaction, the event chain, the manifests, the claims law and
the referee gate are untouched.

## 6. Positioning

Where Klein sits among its neighbours — positioning, not a benchmark:

| | Claude Science | [Kosmos](https://arxiv.org/abs/2511.02824) | [Curie](https://arxiv.org/abs/2502.16069) | autoresearch | **Klein** |
|---|---|---|---|---|---|
| Runs where | hosted workbench | hosted | local | local | local, from git |
| Model | Claude | its own | any | any | any — none inside Klein |
| Unit of work | a session | a world model | an experiment | one script | a typed inquiry |
| Verification | reviewer agent | citation trails | rigor modules | keep / discard | ledger arithmetic, then a referee |
| Pre-registration | plan first | — | — | — | hashed arithmetic rules |
| Audit by a stranger | message history | citations | — | git history | every claim resolves |

A workbench owns connectors, compute and conversation. Klein owns none of those. It is
the discipline a workbench's agent runs *inside*, and from 3.0 it can be embedded as
one: [`../embedding.md`](../embedding.md).

## 7. Roadmap

**Proportional rigor.** Every study runs the whole lifecycle today. Many real questions —
most questions in a BI product — deserve less: a typed question, a data check, one
registered analysis, a claim with a pinned number. The design is a declared tier in the
contract that fixes which gates are required and *caps the strength a claim can reach*,
so a quick look can never be quoted as a confirmed result, and can be promoted to a full
study without restarting. This is the next release's main item.

**A cross-study map.** `klein map` draws one study. The same join across studies — which
claim in study A became a prior in study B, which lesson in `knowledge/` rests on which
claims — would make the repository's accumulated knowledge navigable.

**Parallel candidates.** The loop runs one experiment at a time by design; a registered
track's cells are independent and could run concurrently without changing what is judged.

**Open questions.** How much of the referee rubric can become arithmetic without becoming
a checklist a model games; whether evidence-use rates predict anything about a study's
later replication; and what the ladder of independence is worth when every rung is a
language model.
