# TUTORIAL — the teaching artifact

Close the loop with `report/index.html`: a self-contained TEACHING artifact that feeds
the findings AND the model-coding advice back to the researcher. Not a figure dump — a
tutorial someone could learn the study from.

Role: tutor. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-tutor` worker.

## The fixed seven-section arc

Every tutorial has these sections, in order:

1. **The question.** What the study set out to answer, as a decision (from study.yaml /
   research_plan.md).
2. **The method taught.** Intuition + the load-bearing math, from `method_card.md` —
   teach it, don't just cite it.
3. **The data story.** The `data_card.md` highlights: shape, the value-pattern gotchas,
   the go/no-go call.
4. **The experiment journey.** The annotated metric-vs-experiment trajectory with the
   KEEPS highlighted — the narrative of what moved the number (results.tsv + program.md
   Log).
5. **Findings & insights.** The verdicts and surprises, from `findings.md`.
6. **Model coding advice.** An annotated walkthrough of the WINNING `train.py` plus the
   pitfalls / war stories that bit this study (the MPS trap, swap-noise details, QLS
   window rules, the value-pattern check). This is the section that makes it useful.
7. **Next steps + references.** What to try next, and the verified references from the
   method card.

## Two routes to the HTML

### Route A — the global nano-tutorial-html skill (preferred when present)
If the `nano-tutorial-html` skill is available (check
`~/.claude/skills/nano-tutorial-html/SKILL.md`; main sessions invoke the skill, worker
agents read that SKILL.md and drive its harvest/render scripts via Bash), run it on the
study directory in repo-profile mode. It harvests deterministically (frontmatter,
results tables, figures, findings), authors a spec, and renders a vendor-inlined single
file. Point it at `studies/NN/` and steer the focus to the seven-section arc above.
Verify the output against the acceptance checklist — a klein study dir is neither a
nano nor a plain repo, so if the harvest misses results.tsv/findings.md content, fall
back to Route B rather than shipping a thin page.

### Route B — the bundled fallback builder
If the skill is absent, split the work: the tutor AUTHORS the content as seven HTML
fragments, and the bundled assembler stitches them into one offline file. The concrete
script is **`.claude/skills/klein/scripts/build_tutorial.py`** (stdlib only):

- Author `<study_dir>/report/sections/` with exactly the seven fragments (no
  `<html>`/`<head>`/`<body>` wrappers), named for the arc above:
  `01-question.html`, `02-method.html`, `03-data.html`, `04-journey.html`,
  `05-findings.html`, `06-coding-advice.html`, `07-next-steps.html`. Use `<pre><code>`
  for the train.py walkthrough; reference figures as `<img data-fig="figures/<name>.png">`
  (the builder base64-inlines each PNG); drop a `<!--LEDGER-->` marker in 04-journey where
  the auto-generated results.tsv ledger table should go.
- Build: `uv run python .claude/skills/klein/scripts/build_tutorial.py <study_dir>
  [--title "..."]` → writes `<study_dir>/report/index.html`. It reads study.yaml for the
  header (goal/metric), inlines every figure, and runs its own acceptance guard (all seven
  anchors present; zero `http://`/`https://` in `src`/`href` attributes) — a build that
  references a missing figure or an external asset URL FAILS with a non-zero exit listing
  the offenders. No CDN, no external fonts, no network.

## Self-contained: the hard requirement

- Opens from `file://` with NO network. Strictly no CDN scripts, external stylesheets,
  remote images, or fonts.
- All figures are base64-inlined PNGs (`<img src="data:image/png;base64,...">`).
- One file: `report/index.html`. Everything it needs is inside it.

## Which figures to inline

Pull from `figures/` (produced by `kleinlib.figures`), matched to the problem:

- **binary-clf:** ROC, PR, reliability, score-hist-by-class, decile-lift, confusion@best.
- **severity / regression:** pred-vs-actual, residuals, QQ, Lorenz/Gini, lift-quantile.
- **simulation:** breakdown curve, efficiency-cost bar, the premium-error "money" slide.

Always inline the metric-vs-experiment trajectory for the journey section.

## Acceptance checklist (all must pass)

- [ ] All SEVEN sections are present and in order.
- [ ] Opens offline from `file://` — verified, not assumed (no network requests).
- [ ] Includes the model-coding-advice section with the ACTUAL winning train.py.
- [ ] Every NUMBER on the page traces to results.tsv / aux_metrics.tsv / findings.md.
- [ ] Every figure is inlined (grep the file: no `http://` / `https://` asset refs).
- [ ] The references match the method card (no unverified refs promoted to verified).
