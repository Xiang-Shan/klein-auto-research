# Embedding Klein in another product

Klein is a library and a command line with no model inside. A host product — an agentic
BI tool, a notebook, a research workbench — can put Klein under its own agent so that
every analysis the agent runs leaves a record a person can check. This page is the
contract between the two.

## What the host gets

| Need | Klein gives |
|---|---|
| "What should the agent do next on this analysis?" | `next` — one action, with the command, as data |
| "Where does this analysis stand?" | `status` — gates, tracks, best result so far, predictions |
| "Show the user what was learned and why" | `map` — questions, predictions, runs, claims, open items, as a graph |
| "Can I trust this number?" | `verify` / `claims_verify` — every check, pass or fail, with the reason |
| "Run this idea and judge it fairly" | `run_one` — the same notary the command line uses |
| "Let the agent look at the data first" | `probe` — a logged look that can never become evidence |
| "Explain this term to the user" | `explain` — the glossary and every procedure |

## Three seams, one shape

Every seam returns the same **envelope**:

```json
{
  "klein": "3.0.0",
  "format": 1,
  "verb": "verify",
  "ok": true,
  "data": { "checks": [ {"name": "study contract", "ok": true, "level": "ok", "message": "…"} ],
            "summary": {"total": 35, "failed": 0, "warned": 3} },
  "problems": [ {"level": "warn", "code": "check", "name": "figure re-render", "message": "…"} ]
}
```

- `format` changes only on a breaking change; within a format, fields are only added.
- `ok` is true when the verb succeeded (exit code 0).
- `problems` says why not, or what to look at: `level` is `error` or `warn`; `code` is
  `refused` (the engine declined, with the reason) or `check` (a named check).
- A refusal is an envelope, never a traceback.

### 1. Python — `kleinlib.api`

```python
from kleinlib import api

api.next_action("studies/30-churn")["data"]["next"]      # {"stage_id": "data", "action": …, "argv": [...]}
api.status("studies/30-churn")["data"]["tracks"]
api.study_map("studies/30-churn")["data"]                # nodes, edges, open, leads
api.verify("studies/30-churn")                           # read-only by default (receipt=False)

reply = api.run_one("studies/30-churn", description="add tenure buckets", tests="P2")
if not reply["ok"]:
    show(reply["problems"])
```

Functions never print and never raise for a refusal. Reading: `next_action`, `status`,
`preflight`, `verify`, `claims_verify`, `predictions`, `study_map`, `explain`, `schema`. Writing,
through the notary: `run_one`, `sealed_dry_run` (the mandatory rehearsal before
`run_one(final_test=True)`), `gate`, `finalize`, `probe`. Anything the engine would have
printed (a notice, a warning) comes back in `problems` with `level: "warn"`.

### 2. Command line — `klein <verb> --json`

Every verb takes `--json` and prints exactly one envelope on standard output; the exit
code is unchanged: 0 for success, 2 for a refusal, any other non-zero value for failed
checks or a crashed run.

```bash
klein next   --study studies/30-churn --json
klein verify --study studies/30-churn --no-receipt --json
klein map    --study studies/30-churn --json
```

Verbs with structured results fill `data` (`next`, `status`, `map`, `verify`,
`preflight`, `claims verify`, `predict list`, `run-one`, `gate`, `finalize`, `recover`,
`probe`, `doctor`, `explain`, `schema`, `new`, `skill …`). Any other verb returns its printed text
as `data.text`. The full list of verbs is [`cli.md`](cli.md).

### 3. MCP — `klein mcp --root <project>`

A dependency-free MCP server over stdio. It is **read-only by design**: `list_studies`,
`next`, `status`, `map`, `preflight`, `verify`, `predictions`, `claims_verify`,
`explain`, `doctor`. There is no tool that records a gate or starts a run — an agent
must not acknowledge a checkpoint for a person, and an experiment outlives a tool call.

## `next`, for a host that drives the lifecycle

The shape of `data.next` (the wording of `action` and `why` varies by stage):

```json
{ "stage": "EXPERIMENT · Phase 0", "stage_id": "experiment",
  "action": "measure the noise floor before any comparison",
  "command": "klein noise-floor --study studies/30-churn --recipe split-lottery …",
  "argv": null,
  "protocol": ".claude/skills/klein/references/consult-protocol.md",
  "explain": "klein explain consult-protocol",
  "why": "a keep bar that was guessed is not a keep bar" }
```

- `stage_id` is a closed vocabulary: `scaffold`, `legacy`, `consult`, `data`, `method`,
  `experiment`, `synthesize`, `referee`, `tutorial`, `finalize`, `verify`, `closed`.
- `argv` is the command as a ready-to-run list when it is complete; `null` when a person
  has to fill something in (the `command` text then shows the template).
- `explain` is the portable way to read the procedure for this stage.

## Schemas

A host that wants to validate what Klein returns does not have to read the code: the
envelope and the `data` of every structured verb have JSON Schemas (draft 2020-12).

- **Where.** `kleinlib/_schemas/` inside the package, so they ship in the wheel:
  `envelope.schema.json` (the wrapper, closed), one `<name>.schema.json` per kind of
  `data` (`next`, `status`, `map`, `checks`, `predictions`, `explain`, `run-one`, `gate`,
  `finalize`, `probe`, `doctor`, `text`, …) and `index.json`, which maps each verb path
  (`"claims verify"`) to the name of its data schema, with `"*": "text"` as the default.
- **`klein schema`** lists the schemas and which verbs use each; `klein schema envelope`
  prints one as JSON; `klein schema --json` (and `kleinlib.api.schema(name="")`) returns
  the same as an envelope — `{"schemas": [...], "verbs": {...}}`, or `{"name", "schema"}`.
- **Validating.** Validate the whole reply against `envelope`, then `reply["data"]`
  against the schema `verbs[reply["verb"]]` names (`verbs["*"]` when the verb is not
  listed). A refused verb has `ok: false`, an empty `data` and the reason in `problems`;
  every data schema accepts that empty object, and requires its keys otherwise.
- **`$id`.** `https://github.com/Xiang-Shan/klein-auto-research/schemas/v1/<name>.schema.json`.
  The `v1` is the envelope `format`: the ids of a format never change meaning.
- **Compatibility, in plain words.** Within `format: 1` keys are only ever *added*.
  Removing or renaming a key, or changing a key's type, raises `format` (and the `v1` in
  the `$id`). The wrapper is closed because its six keys are the contract; every `data`
  schema is open, so a validator keeps passing when a later release adds a key — do not
  turn that off in your own copy.

## Rules for a host

1. **Gates belong to a person.** `api.gate(..., acknowledged_by=...)` must carry the name
   of whoever decided. Show the gate's artifact (the contract, the data card, the method
   card, the referee report), ask, then record. Never auto-acknowledge.
2. **Write only through the notary.** Do not edit `runs/`, `study_state.json`,
   `events.jsonl`, `claims.lock` or `results.tsv`; they are receipts. Edit the study's
   own code and documents, then call `run_one`.
3. **Use `verify(receipt=False)` to check a study you do not own.** The default command
   line writes and commits a receipt; the API default only reads.
4. **Show strength with every claim.** A claim is `confirmed` or `exploratory`, and a
   study closed without a referee is labelled `unrefereed`. A host that drops those
   labels is making a stronger statement than the study did.
5. **A probe is a lead.** Show probes apart from evidence, as `klein map` does.

## Installing Klein inside a host

| Setting | How |
|---|---|
| A Python environment | `pip install klein-auto-research` — the engine, the `klein` command, every procedure, template, audience profile and worker agent ship in the package |
| A repository an agent works in | `klein skill install --target <repo>` writes `.claude/skills/klein/` and `.claude/agents/klein-*.md` there |
| Claude Code | `/plugin install klein --marketplace Xiang-Shan/klein-auto-research` — skill, agents, a `klein` launcher on the agent's PATH, the MCP server. Needs `uv` |
| Claude Science | [`integrations/claude-science/`](../integrations/claude-science/README.md) |

Studies live under `<project>/studies/NN-slug/` in a git repository, on a branch
`experiments/<slug>`. Klein needs git; it does not need network access, an API key, or
this repository.

## Extending Klein from a host: plug-ins

A plug-in is one function, advertised under the `klein.plugins` entry-point group:

```python
# my_bi_pack/__init__.py
from pathlib import Path
from kleinlib.inquiry import ProfileSpec

def register(api):
    api.add_profile(ProfileSpec("bi", doc=Path(__file__).parent / "bi.md",
                                summary="a business analyst reading a dashboard"))
    api.add_cli(my_verbs.register)                 # adds `klein <your-verb>`
    api.add_mcp_tool(TOOL_DEFINITION, my_handler)  # a read-only MCP tool
```

```toml
[project.entry-points."klein.plugins"]
bi = "my_bi_pack:register"
```

A plug-in can add an audience profile (wording, banned words, section headings), an
evidence modality (the headings its data card must carry), verbs, and read-only MCP
tools. Question kinds, outcomes, the claims rules and the receipts are not on the
plug-in surface. What Klein enforces: a plug-in cannot shadow a built-in profile,
modality, verb or MCP tool; one that fails to load, or that tries to replace a core
verb, is undone and reported by `klein doctor` without breaking any core verb; and a
verify receipt issued with third-party plug-ins loaded names them. What Klein cannot
enforce: a plug-in is Python code you chose to install, running in the same process.
Install plug-ins you trust, and note that a study typed with a plug-in's profile or
modality validates only where that plug-in is installed. `KLEIN_NO_PLUGINS=1` loads the
built-ins only. Klein's own optional generation layer is loaded through this same seam.

## What is not built yet

A lighter "quick-look" tier for questions that do not need the full seven stages — the
natural fit for many BI questions — is on the roadmap
([`design/klein-3-design.md`](design/klein-3-design.md)). Today every study runs the
whole lifecycle; a host can stop early, and the study then says so (`exploratory`,
`unrefereed`).
