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
6. **{{SECTION6_HEADING}}** — the profile's heading (`references/profiles/<profile>.md`
   §4: "Model coding advice", "Training-recipe advice", "Search and verifier coding
   advice", "Method coding advice"). An annotated walkthrough of the EXECUTED source
   — the exact bytes a named run executed, never the file lying on disk (see "Code"
   below) — and the verifier, when one is declared, plus the pitfalls / war stories
   that bit this study. This is the section that makes it useful.
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
  figures as `<img data-fig="figures/<name>.png" alt="…" data-caption="…">` (the
  builder base64-inlines each PNG and captions it); include the executed source by
  reference (see below); drop a `<!--LEDGER-->` marker in 04-journey where the
  auto-generated ledger table belongs (`Exp · Track · Kind · Metric · Status ·
  Description`, under a key line naming each track's metric and goal) and an
  `<!--EVIDENCE-->` marker in 05-findings where the claim and referee totals belong
  (see "Records, not retyping").
- Build: `uv run --locked python .claude/skills/klein/scripts/build_tutorial.py <study_dir>
  [--title "..."]` → writes `<study_dir>/report/index.html`. It reads study.yaml for the
  header (goal/metric), inlines every figure, renders math and code, and runs its own
  acceptance guard. Non-zero exits list the offenders: 2 missing fragments, 3 figure
  problems (missing file, or bytes that are not a PNG), 4 acceptance guard (external
  asset URL / modified CSP / a lock with no `<!--EVIDENCE-->` marker), 5 math render
  failure, 6 code include failure, 7 renderer dependency missing.
- Every `<h3>` is given a stable slug id at build time, and a section holding two or
  more of them gets an "In this section" list under its `<h2>`. So author `<h3>`s as
  the subsections a reader would want to link to, and never hand-write the ids.

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

- The EXECUTED source is included BY REFERENCE:
  `<pre data-code="search.py" data-lang="python" data-run="E0009"></pre>` (or
  `train.py`, `analyze.py`, `verify.py` — whatever the study runs) — the builder reads
  the bytes itself, so the page carries the ACTUAL source (a missing file or a path
  outside the study dir fails the build). `data-lang` is optional (inferred from the
  suffix).
- `data-run="E####"` includes the file AS IT WAS at that run's `candidate_commit`
  (read from `runs/E####/manifest.json`) and prints a provenance line: run id,
  evaluation kind, track, short commit, sha256 of the included bytes. That is what
  "executed" means here — the cell that produced the evidence, as the notary recorded
  it, not a reconstruction.
- A BARE include of a file named in `entrypoint.mutable` (`train.py` on schema 2) is
  REFUSED. The notary restores the mutable surface on every non-keep, and after every
  run on a registered track, so the file on disk is either the last keep's bytes with
  no run named or the restored template — a bare include cannot say which, and on a
  registered track it teaches bytes that measured nothing. Say which one you mean:
  - **frontier track** — `data-run` naming the final keep's run;
  - **registered track** — `data-run` naming the representative or sealed cell the
    surrounding prose discusses;
  - `data-role="template"` when the scaffold everyone edits IS the point; the
    provenance line then says "restored template on disk, not a run's cell".
- Files OUTSIDE the mutable surface — `verify.py`, `lib/*.py`, `model.py`, a `report/`
  analysis script — stay bare and are labelled "current file at build".
- An include renders as a CLOSED `<details class="source">` disclosure, its provenance
  line as the summary, so a long listing never buries the prose; printing opens every
  one. Literal `<pre><code class="language-…">` snippets stay visible inline — use
  those for the SHORT examples the prose teaches from, and the include for the whole
  file the reader may want to steal.
- Literal snippets: `<pre><code class="language-python">…escaped…</code></pre>`
  (also bash/yaml/json/diff/console/text). A `<pre><code>` with NO language class is
  left byte-identical — the escape hatch for console dumps and not-code monospace.
- Deliberately NOT supported: line-range includes — ranges drift the moment
  the file changes, which is the failure mode include-by-reference exists to remove;
  keep snippets as literal pastes.

**Diagrams** ship as pre-rendered static figures like any other figure — see
`docs/diagrams/src/` for the repo's matplotlib-to-PNG idiom. No diagram-description
language is rendered at build time.

## Records, not retyping

Claim totals, claim strengths and classes, errata, the referee's verdict and the
finalization label are RECORDS. Never retype them into prose. Drop an
`<!--EVIDENCE-->` marker where they belong — 05-findings, where they used to be typed
by hand — and the builder generates the block from `claims.lock` (the claim count,
counts by strength and by class, errata, the lock's git head and the Klein version)
and `study_state.json` (the finalization label; the referee's verdict, who refereed,
and whether they were independent of the experimenter; `unrefereed` and any
confirmation gaps when the record says so). A record that does not exist renders as an
explicit "not recorded" line — the page never guesses and never computes a total.

A study that HAS a `claims.lock` and no fragment carrying the marker FAILS the build
(acceptance guard, exit 4). Headline numbers are unchanged: still copied from a value
pinned in `claims.lock`, never recomputed for the page.

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
- Mobile and print are BUILDER guarantees, not authoring chores: the page must not
  scroll horizontally at 320 px (wide tables, code and math scroll inside their own
  box), and it must print its tables, code and equations IN FULL, with every source
  disclosure opened. `scripts/check_shipped_reports.py` measures the shipped reports at
  1440 / 768 / 390 / 320 px and through a print-to-PDF pass, weekly in CI.

## Which figures to inline

Pull from `figures/` (produced by `figures/make_figures.py`, which must re-render
byte-identically — the referee checks), matched to the problem by the profile's
figure sets (`references/profiles/<profile>.md` §4). The generic sets:

- **classification:** ROC, PR, reliability, score-hist-by-class, decile-lift, confusion@best.
- **regression:** pred-vs-actual, residuals, QQ (insurance adds Lorenz/Gini and lift-quantile).
- **estimation:** the estimate with its interval against every reference value.
- **simulation:** breakdown curve, efficiency-cost bar.
- **optimize:** objective against search budget with the external incumbent as a line.

Always inline the decision trajectory for the journey section — one
`plot_decision_trajectory__<track>` PNG per track (step frontier of development
keeps, discard dots, crash rug, the sealed final-test star, phase bands;
`make_figures.py` emits them from the run manifests). v1 studies without
manifests fall back to the plain `plot_metric_trajectory`.

Every figure in sections 4 and 5 is authored WITH a caption:
`<img data-fig="figures/<name>.png" alt="…" data-caption="…">`, which the builder turns
into a `<figure>` + `<figcaption>` with a zoom link (CSS-only enlargement; the close
link or Esc returns). A caption says four things in a sentence or two: what is plotted,
which track and which split, what it is compared against, and the one-line takeaway the
reader should leave with. `alt` describes the image for someone who cannot see it;
`data-caption` teaches. A bare `data-fig` with no caption still works — that is the form
for a fragment authoring its own `<figure>`/`<figcaption>` — and bytes that are not a
PNG are refused (exit 3); the decoded width and height are stamped on the `<img>`.

An opening "takeaways" block in section 1 — an `<h3>` and three items naming what the
study found, the way study 15 opens — is RECOMMENDED, not required: it hands the reader
the verdicts before the method, and the rest of the page earns them.

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
- [ ] Includes the coding-advice section with the EXECUTED source via `data-run` —
      `<pre data-code="…" data-run="E####">`, so the builder guarantees the bytes are
      the ones that run executed.
- [ ] The evidence block is present (`<!--EVIDENCE-->`, in 05-findings) and every claim
      total, strength or class count, erratum count, referee verdict and finalization
      label on the page is read from it — none retyped in prose.
- [ ] Every `data-code` include is provenance-labelled (`data-run` or
      `data-role="template"`); no include of a mutable-surface file is bare.
- [ ] Every figure in sections 4 and 5 carries a `data-caption`.
- [ ] Every mathematical EXPRESSION is typeset (`data-math` / `data-math-display`):
      no ASCII pseudo-math (`SUM_i`, `sqrt()`, spelled-out operators) and no
      HTML-built formulas (`<sub>`/`<sup>` constructions) anywhere. A bare symbol
      or cited value named mid-sentence (a σ̂ or χ²₂₃ in prose) may stay Unicode
      text — prose names symbols; formulas get typeset.
- [ ] Every code block is highlighted or deliberately classless (console dumps).
- [ ] Every NUMBER on the page traces to a pinned artifact — the numbers law of
      `references/claims-protocol.md`; headline numbers are read from `claims.lock`,
      never retyped (formula digits stay greppable via `data-latex`). `klein verify
      --numbers` runs an advisory pass over the built page.
- [ ] `figures/make_figures.py` re-renders every inlined figure pixel-identically on
      the platform family that rendered it (byte-identically on that machine; another
      platform's PNG encoder writes the same pixels in different bytes, which `klein
      verify` decodes and accepts; on another CPU family a computed curve can move a
      pixel, which verify reports as a warning naming both platforms).
- [ ] Every figure is inlined (no `http://` / `https://` in any `src`/`href`
      attribute; plain-text URLs in citations are fine).
- [ ] The references match the method card (no unverified refs promoted to verified).
- [ ] Figure critique passed for every inlined figure.
