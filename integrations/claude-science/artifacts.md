# Saving a Klein study as Claude Science artifacts

Claude Science artifacts are versioned files with provenance (messages, code, execution
log, environment, reviewer findings), stored in `~/.claude-science`. A Klein study's
evidence is its **git history** — candidate commits, manifests, the hash-chained
`events.jsonl`, `claims.lock`. The two records complement each other: provenance shows how
a reading copy was produced in this app; the ledger shows what was registered, run and
decided, re-verifiable by `klein verify` on any machine with no model and no app.

## What to save, and when

| After | Save as artifact | Why |
|---|---|---|
| CONSULT | `study.yaml`, `research_plan.md` | the registered contract the person acknowledged |
| DATA | `data_card.md`, the profiling figures | the GO/NO-GO ruling and what it rested on |
| METHOD | `method_card.md` | the teaching card |
| each phase boundary | `results_summary.md`, `progress.svg` (from `summarize_results.py`) | the state of play at the ack |
| SYNTHESIZE | `findings.md`, `claims.lock` | the claims and their pinned numbers |
| REFEREE | `referee_report.md` | the verdict, from the referee's own session |
| TUTORIAL | `report/index.html` | the self-contained teaching artifact (opens from `file://`) |

Ask Claude to save by the study-relative filename (for example `findings.md`) so a
re-save becomes a new version of the same artifact, and the version stepper tracks the
study's revisions.

## What provenance does and does not prove

- The **Execution Log** tab is the authoritative record of what ran *in the app*. It does
  not replace a run manifest: the manifest is what `klein run-one` decided, bound to a
  candidate commit and a split fingerprint.
- An artifact edited in place (Markdown cell edits) is a new artifact version but **not a
  study change** — `findings.md` in git is the one the claims law checks. Make edits in the
  study folder and re-save, never only in the artifact viewer.
- Reviewer findings on the **Review** tab are a pre-referee signal
  (`reviewer-criteria.md`), never Gate 3.

## Exporting

**Export Metadata** on `report/index.html` gives the app-side provenance; commit nothing
from `~/.claude-science` into the study. To share a study, share the repository (or a
`git bundle`) — `klein verify` is the stranger's audit.
