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
4. **The experiment journey.** One annotated development frontier per track, with keeps
   highlighted, plus separately labelled sealed confirmation evidence (run manifests,
   derived results.tsv, and program.md Log).
5. **Findings & insights.** The verdicts and surprises, from `findings.md`.
6. **Model coding advice.** An annotated walkthrough of the WINNING `train.py` plus the
   pitfalls / war stories that bit this study (the MPS trap, swap-noise details, QLS
   window rules, the value-pattern check). This is the section that makes it useful.
7. **Next steps + references.** What to try next, and the verified references from the
   method card.

## The builder

Split the work: the tutor AUTHORS the content as seven HTML fragments, and the
bundled assembler stitches them into one offline file with build-time typeset math
and highlighted code. The concrete script is
**`.claude/skills/klein/scripts/build_tutorial.py`** (dependencies: pygments +
ziamath + latex2mathml, declared in pyproject.toml — every shipped exhibit is built
this way):

- Author `<study_dir>/report/sections/` with exactly the seven fragments (no
  `<html>`/`<head>`/`<body>` wrappers), named for the arc above:
  `01-question.html`, `02-method.html`, `03-data.html`, `04-journey.html`,
  `05-findings.html`, `06-coding-advice.html`, `07-next-steps.html`. Reference
  figures as `<img data-fig="figures/<name>.png">` (the builder base64-inlines each
  PNG); include the winning train.py by reference (see below); drop a
  `<!--LEDGER-->` marker in 04-journey where the auto-generated results.tsv ledger
  table should go.
- Build: `uv run --locked python .claude/skills/klein/scripts/build_tutorial.py <study_dir>
  [--title "..."]` → writes `<study_dir>/report/index.html`. It reads study.yaml for the
  header (goal/metric), inlines every figure, renders math and code, and runs its own
  acceptance guard. Non-zero exits list the offenders: 2 missing fragments, 3 missing
  figures, 4 acceptance guard (external asset URL / modified CSP), 5 math render
  failure, 6 code include failure, 7 renderer dependency missing.

## Math and code in fragments

**Math** is authored as LaTeX in EMPTY elements and typeset at BUILD time into
inline SVG glyph paths — no fonts, no runtime script, identical pixels everywhere:

- Inline: `<span data-math="\hat{\sigma}^{2}_{\mathrm{gQLS}}"></span>`
- Display: `<div data-math-display="d(y,\mu) = 2\Big(y\log\tfrac{y}{\mu} - y + \mu\Big)"></div>`
- The data attribute is the element's ONLY attribute and the element is EMPTY.
  Inside the attribute escape exactly four characters: `&`→`&amp;` `"`→`&quot;`
  `<`→`&lt;` `>`→`&gt;`; backslashes are literal. An unescaped quote, a non-empty
  element, or an unparseable formula is a HARD build error naming the fragment.
- The LaTeX source survives into the built page as `data-latex` and as the SVG
  `<title>` — numbers inside formulas stay greppable and the source stays copyable.
- Validated LaTeX subset (the shipped-exhibit corpus): fractions (`\frac`/`\tfrac`),
  sub/superscripts including `^{\star-1}` and negative exponents, `\hat`, Greek,
  `\sum` with limits, `\big`/`\Big`/`\left`/`\right`, `\text`/`\mathrm`/`\mathbb`,
  `\underbrace`, `\displaystyle`, `\sqrt`, `\nabla`, relations
  (`\le`/`\sim`/`\approx`/`\in`/`\Longrightarrow`), `\dots`, spacing
  (`\,`/`\;`/`\quad`/`\qquad`), primes as apostrophes. Multi-line derivations:
  one display element per line with prose between — not alignment environments.
- Convert self-contained mathematical STATEMENTS only; prose typography
  (a `3.7×` multiplier, an arrow in a sentence) stays plain text.

**Code** is highlighted at build time (Pygments, pinned dual-theme styles):

- The winning train.py is included BY REFERENCE:
  `<pre data-code="train.py" data-lang="python"></pre>` — the builder reads the file
  from the study dir, so the page carries the ACTUAL bytes (a missing file or a path
  outside the study dir fails the build). `data-lang` is optional (inferred from the
  suffix). Deliberately NOT supported: line-range includes — ranges drift the moment
  the file changes, which is the failure mode include-by-reference exists to remove;
  keep snippets as literal pastes.
- Literal snippets: `<pre><code class="language-python">…escaped…</code></pre>`
  (also bash/yaml/json/diff/console/text). A `<pre><code>` with NO language class is
  left byte-identical — the escape hatch for console dumps and not-code monospace.

**Diagrams** ship as pre-rendered static figures like any other figure — see
`docs/diagrams/src/` for the repo's matplotlib-to-PNG idiom. No diagram-description
language is rendered at build time.

## Optional: an external renderer

Some protocols name a global `nano-tutorial-html` skill as an accelerator for
harvest-and-render. If used, its output must still pass this spec's hard gates and
the full acceptance checklist below. Today it renders math at RUNTIME via bundled
KaTeX with no CSP, so it does not pass them, and no shipped exhibit uses it — the
bundled builder above is the route of record.

## Self-contained: the hard requirement

- Opens from `file://` with NO network. Strictly no CDN scripts, external stylesheets,
  remote images, or fonts.
- All figures are base64-inlined PNGs (`<img src="data:image/png;base64,...">`).
- Math is typeset at BUILD time into inline SVG; no math is rendered by script in
  the browser, and no font is fetched or embedded — `font-src 'none'` stands.
- One file: `report/index.html`. Everything it needs is inside it.
- Include a restrictive Content-Security-Policy meta tag compatible with inline styles
  and `data:` images but with no remote/default connections.

## Which figures to inline

Pull from `figures/` (produced by `kleinlib.figures`), matched to the problem:

- **binary-clf:** ROC, PR, reliability, score-hist-by-class, decile-lift, confusion@best.
- **severity / regression:** pred-vs-actual, residuals, QQ, Lorenz/Gini, lift-quantile.
- **simulation:** breakdown curve, efficiency-cost bar, the premium-error "money" slide.

Always inline the decision trajectory for the journey section — one
`plot_decision_trajectory__<track>` PNG per track (step frontier of development
keeps, discard dots, crash rug, the sealed final-test star, phase bands;
`make_figures.py` emits them from the run manifests). v1 studies without
manifests fall back to the plain `plot_metric_trajectory`.

## Figure critique (run before any figure lands)

Apply four checks to EVERY figure before it is inlined; fix and re-render on any
failure:

1. **Axis labels unit-bearing and non-default.** Each axis names its quantity and
   unit/scale (`val_pr_auc`, `wall_seconds`, `Experiment ordinal`) — never a bare
   library default like `value` or an unlabeled axis.
2. **Scale honesty.** Bars are zero-based; no truncated axis inflating a
   within-noise delta; any log scale is declared on the axis label.
3. **Legend readability.** Every mark type on the plot appears in the legend, and
   marks stay distinguishable in grayscale (shape/ring/linestyle, never hue alone).
4. **Chart-type-fits-claim.** A frontier claim gets a step/line, not bars; a
   distribution claim gets a histogram, not a mean bar; an A-vs-B claim gets
   paired marks.

## Acceptance checklist (all must pass)

- [ ] All SEVEN sections are present and in order.
- [ ] Opens offline from `file://` — verified in a browser with zero network requests.
- [ ] Restrictive CSP is present and the browser console records no CSP errors.
- [ ] Includes the model-coding-advice section with the ACTUAL winning train.py —
      via `<pre data-code="train.py">`, so the builder guarantees the bytes.
- [ ] Every mathematical EXPRESSION is typeset (`data-math` / `data-math-display`):
      no ASCII pseudo-math (`SUM_i`, `sqrt()`, spelled-out operators) and no
      HTML-built formulas (`<sub>`/`<sup>` constructions) anywhere. A bare symbol
      or cited value named mid-sentence (a σ̂ or χ²₂₃ in prose) may stay Unicode
      text — prose names symbols; formulas get typeset.
- [ ] Every code block is highlighted or deliberately classless (console dumps).
- [ ] Every NUMBER on the page traces to results.tsv / aux_metrics.tsv / findings.md
      (formula digits stay greppable via `data-latex`).
- [ ] Every figure is inlined (no `http://` / `https://` in any `src`/`href`
      attribute; plain-text URLs in citations are fine).
- [ ] The references match the method card (no unverified refs promoted to verified).
- [ ] Figure critique passed for every inlined figure.
