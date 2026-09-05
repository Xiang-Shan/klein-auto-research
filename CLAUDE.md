# Klein Auto Research — Claude Code manual

The canonical operating manual for this repository is **`AGENTS.md`** — the
agent-agnostic runbook (lifecycle, stage map, inquiry model, experiment loop
contract, schema discipline, war stories, run commands). It is imported below; if
your client does not resolve imports, read `AGENTS.md` directly before working here.

@AGENTS.md

## Claude Code specifics

- The **`/klein` skill** (`.claude/skills/klein/SKILL.md`) routes the lifecycle
  STAGES (`new | consult | data | method | run | synthesize | referee | tutorial |
  status`).
- The machine actions are the packaged **`klein` CLI** verbs:
  `new | gate | preflight | run-one | recover | status | finalize | noise-floor |
  verify | headroom | stop | predict | claims | replicate | sweep | doctor |
  generation` — the SKILL.md stage table maps each stage to its verbs.
- The worker roles from AGENTS.md ship pre-wired as subagents in `.claude/agents/`:

| Agent | Model | Stage |
|---|---|---|
| klein-consultant | opus | CONSULT |
| klein-data-auditor | sonnet | DATA |
| klein-method-scholar | opus | METHOD |
| klein-experimenter | sonnet | EXPERIMENT |
| klein-sweeper | sonnet | SWEEP |
| klein-synthesist | opus | SYNTHESIZE |
| klein-referee | opus | REFEREE |
| klein-tutor | sonnet | TUTORIAL |

The referee runs in a fresh context on a different model than the experimenter
(sonnet experiments, opus referees — the "model" rung of the independence ladder);
when the orchestrating session itself ran the loop, hand the REFEREE stage to a
subagent, never review your own findings in the same context.

Simplicity principle: the reference protocols are the source of truth; these
subagents are optional accelerators — a solo session following `AGENTS.md` can run
the entire lifecycle.
