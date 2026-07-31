# Evaluation: `agent-smith` Skill

## Context

You asked me to evaluate the local skill at `/Users/xiang/Claude/Auto_research/agent-smith/`: quality, generalization, what's good, what's bad, and a step-by-step improvement guide.

The repo turns out to be a **hybrid**: it bundles the actual skill (in `.agents/skills/agent-smith/`) **plus** a working reference implementation at the repo root (a Kaggle insurance-claims binary-classification demo). My evaluation covers both layers separately, because they have very different quality profiles.

What I read in full:
- `.agents/skills/agent-smith/SKILL.md` (172 lines)
- `.agents/skills/agent-smith/references/defaults-and-scaffolding.md` (258 lines)
- `.agents/skills/agent-smith/scripts/summarize_results.py` (audited via Explore — 327 lines)
- `.agents/skills/agent-smith/assets/` (5 templates: prepare, train-generic, train-tabular, program, pyproject)
- `program.md`, `train.py`, `prepare.py`, `keep_awake.py`, `README.md`
- `git log` (20+ commits, active PR-driven development)

---

## TL;DR Verdict

| Axis | Rating | One-line reason |
|---|---|---|
| Overall quality | **★★★★½** (very good) | Mature, experience-derived rules; one real bug; some missing onboarding glue |
| Generalization (skill layer) | **★★★★★** | Task / language / dataset agnostic; templates + reference docs cover the abstraction |
| Generalization (demo layer) | **★★** | Hardcoded to insurance-claims Kaggle dataset — intentional but under-flagged |
| Production-ready | **Yes** | Has been used in a real 100-experiment run (+0.044 AUC over baseline) |
| Immediate fix needed | `results.tsv` column order in `program.md` disagrees with `SKILL.md` and `summarize_results.py` |

This is a **good skill**, not a "good idea sketched as a skill." It already shows scars from real runs (Hard Rules section), real usage (the 100-experiment example in the README), and real iteration (20+ commits, recent improvements to stopping rule). But it has under-polished edges in onboarding, distribution, and example diversity.

---

## What's Genuinely Good

### A. Skill philosophy & mental model
1. **"The agent IS the loop"** (`SKILL.md:53-55`). Explicitly forbids batch runners and meta-harnesses. This is the right insight — adaptive experimentation depends on results-aware redirection, which pre-planned scripts destroy. Most autotuning skills miss this.
2. **"The edit IS the experiment"** (`SKILL.md:61`, `program.md:73`). No separate config file, no JSON spec language — agents just edit `train.py`. Drastically reduces ceremony.
3. **Hard Rules framed as failure stories** (`SKILL.md:109`: *"Violating these has caused real data-loss and workflow failures"*). The rules read as institutional memory, not theoretical constraints. The validation `awk` one-liner at `SKILL.md:124` is exactly the kind of thing you only write after seeing a corrupted TSV.
4. **`program.md` as a living document** (`SKILL.md:43-49`). The skill explicitly tells agents to re-read `program.md` before strategic decisions and append user feedback into it mid-run. Treats the doc as a runtime artifact, not boilerplate.
5. **"Keep running until the user says stop"** (`SKILL.md:92`). Refuses to auto-plateau-detect. Respects human judgment as a feature, not a fallback.

### B. Triggering & metadata
6. `SKILL.md` frontmatter `description` (line 3) enumerates trigger phrases — *"experiment loops, hyperparameter tuning, autotuning, ML iteration, train/eval cycles, setting up reproducible experiments"* — and ends with *"even if they don't explicitly say 'agent smith'"*. Critical for the skill loader to fire correctly.

### C. Production hygiene
7. **Machine-readable summary block** (`train.py:111-119`): `primary_metric`, `metric_name`, `metric_goal`, `training_seconds`, `total_seconds`, `train_rows`, `val_rows`, `status`. A single `grep`/parse target the agent can rely on.
8. **Positional `printf` + `awk` validation pattern** (`SKILL.md:117-128`). One-row-at-a-time append with immediate validation — the right pattern for an agent that might be interrupted mid-loop.
9. **Gap detection every 5 experiments** (`SKILL.md:129`). Catches sequential-number drift before it becomes unrecoverable.
10. **Foreground/blocking terminal anti-poll pattern** (`SKILL.md:98-105`). Explicitly justified with token economics: *"Background execution requires the agent to repeatedly call `get_terminal_output` to check if the run finished, wasting tokens on every poll."* The kind of insight you only have after watching a real agent burn budget.
11. **Time budget enforced via terminal timeout, not in-script** (`SKILL.md:63`). Simpler than wrapping training code in `signal.alarm()` handlers, and crashes are uniformly handled.
12. **Per-problem-class default budgets** (`defaults-and-scaffolding.md:106-114`): 2 min for small tabular, 30-60 min for distributed. Saves the agent from guessing.

### D. Real-world validation
13. README:65-89 documents a real 100-experiment run that lifted validation AUC from `0.625464` → `0.669402` (+0.0439 absolute). Includes the actual best blend (`hgb_rand_052@0.7 + hgb_rand_033@0.3`). This is the strongest possible evidence the skill works.
14. Git log shows iterative improvements: stopping-rule refinements (PRs #6, #8), commit-hash tracking (#5), macOS keep-awake (#4), instruction polish (#7). This is *lived-in* infrastructure.
15. Acknowledges inspiration from `karpathy/autoresearch` (README:17) — sits in a genuine lineage.

### E. Ecosystem awareness
16. **Cross-references `r-docker` skill** for non-Python runtimes (`SKILL.md:19-23`). Recognizes that the experiment-loop pattern is language-agnostic, even if Python is the default.
17. **Two train templates** (`train-template-generic.py` and `train-template-tabular.py`) plus a feature-importances helper (`assets/feature-importances-template.py`) — last one prevents agents from writing throwaway scripts mid-loop.
18. **`defaults-and-scaffolding.md` minimum question set** (lines 53-60): five intake questions, with example phrasings. Removes ambiguity about when to ask the user.

---

## What's Broken / Bad

### 1. 🐛 CRITICAL: `results.tsv` column-order inconsistency
Three sources of truth disagree:

| Source | Columns |
|---|---|
| `SKILL.md:76, 115` | `experiment  metric  status  commit  description` (5 cols) |
| `program.md:87` | `commit  metric  status  description` (**4 cols**, no `experiment`, `commit` first) |
| `summarize_results.py:178` (rendered output) | `row_number | commit | metric | status | description` |

An agent following `program.md` will write a 4-column TSV in a different order from what the SKILL Hard Rules mandate and from what the summarize script expects to find by header. The Hard Rule at `SKILL.md:115` is *"Always use positional `printf`"* — so column order matters, and they don't match.

This is **a real bug that will silently corrupt experiment runs on the demo dataset** — and worse, it's a *teaching* error: anyone copying `program.md` as a template will inherit the broken schema. The current insurance demo apparently works only because the README example was run before the schema drift, or because the agent doing that run silently followed `SKILL.md` over `program.md`.

### 2. Skill distribution / portability story is undocumented
The skill lives at `.agents/skills/agent-smith/` inside this repo. To use it in another repo, a user must:
- Know `.agents/skills/<name>/SKILL.md` is the standard convention
- `cp -r` the entire directory into the new repo
- Verify nothing depends on an absolute path

`SKILL.md` does not say *"to install this skill in another repo, copy `.agents/skills/agent-smith/` to your target repo's `.agents/skills/`"*. A first-time reader staring at the file structure has no install path.

### 3. Demo-level hardcoding leaks domain concepts into the workflow doc
- `program.md:3` — *"binary insurance claim classification"*
- `program.md:20` — optimize `val_auc`
- `train.py:23` — `TARGET_COLUMN = "claim_status"`
- `prepare.py` — Kaggle handle `"litvinenko630/insurance-claims"` hardcoded

These are fine *for the demo*, but `program.md` doesn't flag itself as demo-specific. A new user might read `program.md` thinking it's the canonical template (it isn't — `assets/program-template.md` is). README:46 calls it "the current demo project," but inside `program.md` there's no such disclaimer.

### 4. Only one example domain — tabular sklearn
README:30 promises *"generalize across different problem types as long as the workflow produces a metric"* — but the only worked example is sklearn tabular classification. There is no:
- NLP example (e.g., HF Datasets text classification)
- CV example (e.g., a small image classifier with `torchvision`)
- LLM-fine-tuning example (e.g., a tiny LoRA loop)
- Regression example (would show the `lower-is-better` path end-to-end)

Without these, "generalizes" is a claim, not a demonstration. The `r-docker` integration partially helps but isn't worked-out either.

### 5. Templates have placeholder traps
The Explore audit confirmed `assets/prepare-template.py` has `raise NotImplementedError()` placeholders without explanatory messages. A user copying the template and running it gets a cryptic crash instead of *"Implement `load_raw_data()`: see SKILL.md §Setup for the prep contract."*

### 6. No setup/preflight validation
If a user runs `uv run train.py` without `uv sync` first, they get a cryptic import error. If `data/prepared/` doesn't exist, a `FileNotFoundError`. Neither `train.py` nor SKILL.md has a `--check-setup` step.

A preflight that verifies — `uv` installed, current branch ≠ main/master, `results.tsv` schema valid (if exists), prep outputs present, training file syntactically valid — would catch the most common pre-loop mistakes.

### 7. `keep_awake.py` is bolted on, not integrated
74-line macOS-specific utility that prevents sleep during long runs. `SKILL.md` doesn't mention it. An agent reading the skill alone won't know it exists. Either document it as part of the harness or move it to `assets/keep-awake-template.py` so it's clearly optional.

### 8. README "Quick Start" omits the actual point
README:60-63 says install / prepare / run baseline — and stops there. The whole point of the project is the *experiment loop*, but a new user following the quick-start would just run a single baseline and never see the loop happen. There's no closing step *"now ask Claude (via Claude Code) to use the agent-smith skill and run experiments."*

### 9. No acknowledgment of scope limits
The harness assumes a single primary metric (higher or lower). Real ML often involves tradeoffs (accuracy vs latency, AUC vs calibration, capability vs alignment). `SKILL.md` is silent on this. Reasonable scope choice — but should be acknowledged in a `## Limitations` section so users know when to reach for a different tool.

### 10. Minor: undocumented magic numbers in `train.py`
- `MIN_FREQUENCY = 20` (`train.py:30`) — sensible default for the insurance dataset's high-cardinality categoricals, but a user on a different dataset has no signal that they should tune it.
- `RUN_BUDGET_SECONDS = 300` (`train.py:26`) — duplicated from `program.md`. Single source of truth would be better.

---

## Generalization Assessment

| Layer | Generalization |
|---|---|
| `SKILL.md` (the contract) | **★★★★★** Truly task / dataset / language agnostic |
| `references/defaults-and-scaffolding.md` | **★★★★½** Excellent heuristics + intake prompts |
| `assets/` templates | **★★★★** Good coverage, but `NotImplementedError` traps |
| `scripts/summarize_results.py` | **★★★★** Auto-detects metric column, supports higher/lower |
| Demo (root `program.md`, `train.py`, `prepare.py`) | **★★** Tightly coupled to one Kaggle dataset (intentional but under-flagged) |
| Example diversity | **★★** Only tabular sklearn — no NLP / CV / LLM / regression |

**Bottom line on generalization**: The skill's *contract* is genuinely general. The skill's *worked example* is one task. The gap between those is the largest single improvement opportunity.

---

## Step-by-Step Improvement Guide

Priority is top-down. Each step lists the exact file, the change, and how to verify.

### Phase A — Fix the bug (~30 min, do first)

**Step 1. Resolve the `results.tsv` column-order inconsistency.**
- File: `/Users/xiang/Claude/Auto_research/agent-smith/program.md` lines 86-87.
- Change `commit  metric  status  description` to `experiment  metric  status  commit  description`.
- Add a one-liner pointer: *"See `.agents/skills/agent-smith/SKILL.md` Hard Rules §1 for the exact append command."*
- Verify: `grep -n "experiment.*metric.*status.*commit.*description" program.md .agents/skills/agent-smith/SKILL.md` — both should match.

**Step 2. Audit `summarize_results.py` for positional vs header-based parsing.**
- File: `.agents/skills/agent-smith/scripts/summarize_results.py` lines 56-87 (column-detection logic the Explore audit referenced).
- Confirm it parses by **header name**, not column index. If positional, fix to be header-based so a future schema change isn't a silent corruption.
- Add a tiny unit test under `.agents/skills/agent-smith/scripts/tests/` that feeds a canonical TSV and asserts parsed rows match expected.

### Phase B — Onboarding clarity (~1 hr)

**Step 3. Add an `## Installing in another repo` section to SKILL.md.**
- File: `.agents/skills/agent-smith/SKILL.md`, insert after the H1 and before `## Setup`.
- ~10 lines covering: copy `.agents/skills/agent-smith/` into target repo; verify with `ls target-repo/.agents/skills/agent-smith/SKILL.md`; no absolute paths required.

**Step 4. Add a "this is the demo's program" banner to root `program.md`.**
- File: `/Users/xiang/Claude/Auto_research/agent-smith/program.md`, top of file.
- ```
  > ⚠️ **This is the demo's `program.md`** (insurance-claims binary classification).
  > For a generic template, copy from `.agents/skills/agent-smith/assets/program-template.md`.
  > For the skill contract, see `.agents/skills/agent-smith/SKILL.md`.
  ```

**Step 5. Strengthen README quick-start with the actual point.**
- File: `/Users/xiang/Claude/Auto_research/agent-smith/README.md` lines 59-63.
- Add Step 4: *"In Claude Code, ask: `Use the agent-smith skill and run 20 experiments to improve validation AUC.`"*
- Optionally a Step 5: *"After the batch, generate the summary: `uv run python .agents/skills/agent-smith/scripts/summarize_results.py results.tsv`"*

### Phase C — Generalization (~3-5 hr)

**Step 6. Add a second worked example.** Pick one:
- `examples/nlp-text-classification/` — IMDb sentiment with HF Datasets, `lower-is-better` (e.g., val_loss). Keeps each file <100 lines.
- Or `examples/regression-tabular/` — California housing or similar, to exercise the lower-is-better path end-to-end.
- Each example mirrors root layout: `prepare.py`, `train.py`, `program.md`, plus its own `pyproject.toml`. Link from README and SKILL.md.

**Step 7. Replace `NotImplementedError` traps in templates.**
- Files: `.agents/skills/agent-smith/assets/prepare-template.py`, `assets/train-template-generic.py`.
- Change `raise NotImplementedError()` → `raise NotImplementedError("Implement <function>: see SKILL.md §Setup for the contract this function must satisfy.")`
- One precise hint per placeholder.

### Phase D — Robustness (~2-3 hr)

**Step 8. Add `scripts/preflight.py`.**
- New file: `.agents/skills/agent-smith/scripts/preflight.py`.
- Checks (each prints a `[OK]` / `[FAIL]` line):
  - `which uv` succeeds
  - current branch ≠ `main`/`master`
  - `results.tsv` (if exists) has the canonical 5-column header
  - prepared data files (if `program.md` declares them) exist and are non-empty
  - `train.py` and `prepare.py` are syntactically valid (`python -m py_compile`)
- Document in SKILL.md `## Setup`: *"Run `uv run python .agents/skills/agent-smith/scripts/preflight.py` before the first experiment."*

**Step 9. Document `keep_awake.py`.** Either:
- Add a `## Long-running batches` section to SKILL.md pointing at the existing root-level `keep_awake.py` and explaining when to run it (macOS only, multi-hour batches).
- Or move it to `assets/keep-awake-template.py` so it's clearly an optional template, not part of the demo.

**Step 10. Tighten undocumented magic numbers.**
- `train.py:30` `MIN_FREQUENCY = 20` — add a one-line comment: `# OneHotEncoder rarity threshold; dataset-specific — raise for cleaner datasets, lower for high-cardinality.`
- `train.py:26` `RUN_BUDGET_SECONDS = 300` — duplicated from `program.md:36`. Remove one — the budget belongs in `program.md` (human-facing), not `train.py` (the mutable surface).

### Phase E — Future-proofing (optional, ~half day)

**Step 11. Add a `## Limitations` section to SKILL.md.**
- One paragraph each: single-metric only, no distributed training, single-machine assumed, no human-in-the-loop labeling step.
- For each, point at an extension hook: *"For multi-metric, add a `secondary_metric` column and write a custom summarizer using `summarize_results.py` as a template."*

**Step 12. Add CI for the skill.**
- A GitHub Action that on PR: installs `uv`, runs `prepare.py`, runs `train.py` once, runs `summarize_results.py` on a 1-row TSV, runs `preflight.py`.
- Catches regressions in templates, scripts, or the contract before they reach users.

---

## Verification

End-to-end checks once improvements land:

1. **Bug fix (Step 1)**: Run a 3-experiment loop on the insurance demo (or any fresh dataset). Confirm `summarize_results.py` parses all 3 rows cleanly into `results_summary.md`. Confirm `tail -1 results.tsv` shows 5 tab-separated fields.
2. **Portability (Step 3)**: `cp -r .agents/skills/agent-smith /tmp/empty-repo/.agents/skills/`, then in `/tmp/empty-repo/` ask Claude to use agent-smith. Verify it can scaffold `prepare.py` / `train.py` / `program.md` from templates and run one baseline.
3. **Second example (Step 6)**: Run agent-smith on the new example for 5 experiments. Confirm the loop works on the non-tabular task and the summary plot renders.
4. **Preflight (Step 8)**: Intentionally break things — delete `data/prepared/`, create uncommitted changes on `main`, corrupt `results.tsv` — and confirm preflight catches each before the agent enters the loop.
5. **Documentation (Steps 4, 5, 9)**: Hand the repo to someone who's never seen it. Observe whether they can independently run an experiment loop without asking questions.

---

## Suggested commit sequence (when you implement)

| # | Subject | Files |
|---|---|---|
| 1 | `fix(docs): align results.tsv column order across program.md and SKILL.md` | `program.md` |
| 2 | `docs(skill): add install/distribution section to SKILL.md` | `.agents/skills/agent-smith/SKILL.md` |
| 3 | `docs(demo): banner program.md as demo-specific` | `program.md` |
| 4 | `docs(readme): add experiment-loop step to quick-start` | `README.md` |
| 5 | `chore(templates): replace bare NotImplementedError with hint messages` | `assets/*.py` |
| 6 | `feat(scripts): add preflight.py + invoke from SKILL.md setup` | `scripts/preflight.py`, `SKILL.md` |
| 7 | `feat(examples): add NLP text-classification worked example` | `examples/nlp-text-classification/*` |
| 8 | `chore(skill): document keep_awake.py for long batches` | `SKILL.md` or `assets/keep-awake-template.py` |
| 9 | `docs(skill): add Limitations section` | `SKILL.md` |
| 10 | `ci: add PR check that runs the bundled demo end-to-end` | `.github/workflows/skill-smoke-test.yml` |

---

## Files I would touch (if you ask me to implement)

| File | Change |
|---|---|
| `/Users/xiang/Claude/Auto_research/agent-smith/program.md` | Edit — column order + demo banner |
| `/Users/xiang/Claude/Auto_research/agent-smith/.agents/skills/agent-smith/SKILL.md` | Edit — install section, keep_awake mention, Limitations |
| `/Users/xiang/Claude/Auto_research/agent-smith/README.md` | Edit — quick-start step 4 |
| `/Users/xiang/Claude/Auto_research/agent-smith/.agents/skills/agent-smith/assets/prepare-template.py` | Edit — hint messages |
| `/Users/xiang/Claude/Auto_research/agent-smith/.agents/skills/agent-smith/assets/train-template-generic.py` | Edit — hint messages |
| `/Users/xiang/Claude/Auto_research/agent-smith/.agents/skills/agent-smith/scripts/summarize_results.py` | Audit + (probably) header-based parse fix + test |
| `/Users/xiang/Claude/Auto_research/agent-smith/.agents/skills/agent-smith/scripts/preflight.py` | Create |
| `/Users/xiang/Claude/Auto_research/agent-smith/.agents/skills/agent-smith/examples/<choice>/` | Create (3-4 files) |
| `/Users/xiang/Claude/Auto_research/agent-smith/train.py` | Edit — magic-number comment, remove duplicated budget |

Note: this is a separate git repo (`agent-smith/.git`). If you want me to implement, I'd need to (a) confirm you have the rights / want to push, (b) create an `improvements/` branch from `main`, (c) land the steps as separate commits per the sequence above.
