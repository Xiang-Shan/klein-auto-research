# Klein Auto Research — Claude Code manual

The canonical operating manual for this repository is **`AGENTS.md`** — the
agent-agnostic runbook (lifecycle, stage map, experiment loop contract, schema
discipline, war stories, run commands). It is imported below; if your client does
not resolve imports, read `AGENTS.md` directly before working here.

@AGENTS.md

## Claude Code specifics

- The **`/klein` skill** (`.claude/skills/klein/SKILL.md`) routes the same stage
  map as subcommands: `new | consult | data | method | run | synthesize |
  tutorial | status`.
- The worker roles from AGENTS.md ship pre-wired as subagents in `.claude/agents/`:

| Agent | Model | Stage |
|---|---|---|
| klein-consultant | opus | CONSULT |
| klein-data-auditor | sonnet | DATA |
| klein-method-scholar | opus | METHOD |
| klein-experimenter | sonnet | EXPERIMENT |
| klein-sweeper | sonnet | SWEEP |
| klein-synthesist | opus | SYNTHESIZE |
| klein-tutor | sonnet | TUTORIAL |

Simplicity principle: the reference protocols are the source of truth; these
subagents are optional accelerators — a solo session following `AGENTS.md` can run
the entire lifecycle.
