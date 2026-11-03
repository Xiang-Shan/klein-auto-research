# Klein in Claude Science

Claude Science is a research workbench: plan-first sessions, a sandboxed kernel, permission
cards, connectors (Literature Graph, PubMed, Hugging Face and your own MCP servers), SSH /
Slurm and Modal jobs, versioned artifacts with provenance, Specialists and a built-in
Reviewer. Klein is a notary for the research *process*: registered predictions, notarized
runs, a claims lock and an independent referee. They compose — Claude Science drives the
work and keeps the artifacts; Klein keeps the ledger that a stranger can re-verify with no
model in the loop.

This kit wires the two together. Nothing here changes what the engine checks.

| File | What it gives you |
|---|---|
| `README.md` (this file) | install, project instructions, the stage-to-feature map |
| `specialists/klein-researcher.md` | a Specialist that runs CONSULT → TUTORIAL by `AGENTS.md` |
| `specialists/klein-referee.md` | a Specialist for Gate 3 — run it in a *different tool or session* |
| `reviewer-criteria.md` | extra Reviewer instructions (additive; never Gate 3) |
| `remote-compute.md` | detached runs on an SSH/Slurm host or Modal (`run-one --detach` → `klein job exec` → `--collect`) |
| `artifacts.md` | which study files to save as artifacts, and what provenance does and does not prove |

## 1. Install the skill and the engine

**The skill.** Import the Klein skill from GitHub (Settings → Skills → import from a
repository): `https://github.com/Xiang-Shan/klein-auto-research`, path
`.claude/skills/klein`. It carries every protocol as plain markdown; the Specialists below
point at it.

**The engine (`klein` CLI, `kleinlib`).** It is pure Python (a `py3-none-any` wheel; every
dependency ships wheels). Claude Science's pip installs only prebuilt wheels from PyPI, so:

1. **From PyPI** (once a release is published there):
   `pip install "klein-auto-research==2.3.*"` into a task environment — ask Claude to create
   a `klein` environment so the install persists across sessions. Add `[deep]` for torch
   recipes (or install torch with conda from the `pytorch` channel).
2. **From a clone, with uv** (works today): grant the repository folder *Read & write*, and
   run the CLI with a shell command — `uv run --locked klein next --study studies/NN-slug`.
   On Linux a uv environment inside a granted folder can be read-only to Claude; point uv at
   a writable one: `export UV_PROJECT_ENVIRONMENT=$HOME/.cache/klein-venv` before
   `uv sync --locked`.
3. **No uv on the machine:** scaffold with `klein new … --runner python` (commands become
   `python -u train.py`), and run the CLI as `python -m kleinlib.cli …` with the clone on
   `PYTHONPATH` inside an environment that has the core dependencies (pandas,
   scikit-learn, scipy, matplotlib, pyyaml, joblib, pygments, ziamath, latex2mathml).

Check what this machine can run, without fetching anything:

```bash
klein doctor --host claude-science
```

It reports a read-only uv environment, a missing uv, the Python it will run, GPUs
(`nvidia-smi`), the skill and this kit, and the command for the built-in MCP server.

## 2. Project instructions

Paste into the project's custom instructions so every session starts in the discipline:

```text
This project runs Klein studies. Before any work, read AGENTS.md at the repository root
(the canonical manual) and .claude/skills/klein/SKILL.md. Use `klein next --study
studies/<id>` to find the one next action and follow it. Never hand-edit runs/,
study_state.json, events.jsonl, claims.lock or verify_receipt.json — they are receipts.
Every experiment is ONE `klein run-one` invocation; never run the entrypoint yourself
except as `KLEIN_SMOKE=1 python <entrypoint>`. Gate acknowledgements (consult, data,
method, phase) are mine to give: stop and ask, then record them with `klein gate record`.
The REFEREE stage happens in a different session or tool, never in this one.
```

## 3. Which Claude Science feature serves which stage

| Stage | Klein verb(s) | Claude Science feature |
|---|---|---|
| scaffold | `klein new NN-slug --recipe <domain>` | a plan step; the study folder is a granted folder |
| CONSULT | `klein doctor --study` | Literature Graph / PubMed / Hugging Face connectors for scouting — every page goes into `scouting_ledger.md` |
| DATA | `python -m kleinlib.leakage …` | the kernel for profiling; figures saved as artifacts |
| METHOD | `klein refs verify` | Literature Graph (OpenAlex, arXiv) to find sources; `klein refs verify` to resolve DOIs / arXiv ids against the registries |
| EXPERIMENT | `klein preflight`, `klein run-one` | shell commands; GPU work via `remote-compute.md` |
| SYNTHESIZE | `klein claims apply claims.yaml` | the Reviewer with `reviewer-criteria.md` as a pre-referee pass |
| REFEREE | `klein verify --numbers --evidence-use`, `klein claims verify`, `klein gate record referee` | `specialists/klein-referee.md` in **Claude Code or another session** (see below) |
| TUTORIAL | `build_tutorial.py` | `report/index.html` saved as an HTML artifact |
| any time | `klein next`, `klein status --json` | a read-only MCP connector: `klein mcp` (below) |

### `klein mcp` as a Local command connector

`klein mcp` (built in — the engine's stdlib only, no extra to install) is a stdio MCP server
exposing **read-only** tools —
`list_studies`, `next`, `status`, `doctor`, `preflight`, `verify` (no receipt written),
`predictions`, `claims_verify`, `explain`. Add it under Settings → Connectors → custom connector →
*Local command*:

```text
command: klein
args:    mcp --root /path/to/klein-auto-research
```

It has no gate, run or write tools on purpose: a model must never acknowledge a gate on
your behalf, and an experiment outlives an MCP call's timeout. Writes stay in the shell,
behind Claude Science's permission cards.

## 4. Independence: the Reviewer is not the referee

Claude Science's Reviewer re-reads responses, artifacts and the execution record and flags
claims that do not match what ran. It is valuable *before* Gate 3 — add
`reviewer-criteria.md` to its instructions. It is not Gate 3: the Reviewer runs on the same
model as the session, inside the same tool. Klein's REFEREE needs a fresh context on a
different model, tool or person. Rungs, weakest to strongest:

| Experimenter | Referee | Rung recorded |
|---|---|---|
| Claude Science session | Reviewer in the same session | *not a referee* — never record Gate 3 from it |
| Claude Science session | `klein-referee` Specialist in a **new** Claude Science session | `fresh session` |
| Claude Science session | Claude Code `klein-referee` subagent, or another CLI | `different tool` |
| Claude Science session | a person | `person` |

Record the rung honestly with `klein gate record referee --acknowledged-by … --note
"rung: different tool (Claude Code)"`; the `program.md` Roster names both seats.

## 5. Limits worth knowing

- **Remote jobs** default to 30 minutes on SSH hosts; tell Claude the study's
  `max_run_seconds` before submitting. Files over ~100 MB stay on the host — keep run
  outputs that are evidence under that size or pin their hashes with `artifact:` lines.
- **Modal** returns what the job writes to `./out/` (≤ 5 GiB) and takes ≤ 1 GiB of inputs
  per submit; `remote-compute.md` shows the wrapper that puts `job_result/` there.
- **Artifacts live in `~/.claude-science`**, not in git. The study's evidence is the git
  history; artifacts are the reading copies (`artifacts.md`).
- A live Claude Science smoke of this kit is recorded under `docs/reviews/` only when one
  has been run by a person with a Claude Science seat; the driver matrix says which rows
  were exercised live.
