# METHOD — Gate 2 (pedagogy)

For an unfamiliar or frontier method, write `method_card.md` BEFORE modeling — so the
study tests understanding, not cargo-culted code. Output: a five-part card a practitioner
could learn the method from.

Role: method scholar. Any agent or human can execute this protocol directly — it is
the source of truth; Claude Code ships it pre-wired as the `klein-method-scholar` worker.

Copy `assets/method-card-template.md` to the study as `method_card.md`. Write the five
parts IN ORDER — each depends on the one before.

## The authoring arc

### 1. Intuition (for a practitioner)
Explain it to an actuary / data scientist who has NOT read the paper. Lead with an
analogy to something they know ("a denoising autoencoder is nonlinear PCA"; "quantile
least squares is OLS that fits chosen quantiles instead of the mean"). Build the mental
model before any math.

### 2. Math core
A notation table first (define every symbol), then the ≤5 load-bearing equations — not
the whole paper, the equations an implementer must get right.

### 3. Minimal from-scratch implementation plan
numpy / sklearn-level pseudocode — the smallest honest version, no framework magic. Name
the kleinlib helpers train.py will lean on (`kleinlib.torch_loop` for MPS-safe batching,
`kleinlib.encoders`, `kleinlib.eval`). This plan is what train.py realizes.

### 4. When it pays / when it doesn't
A regime table keyed on data size and signal strength — the honest verdict, grounded in
doctrine (Grinsztajn: trees still win on most tabular; deep methods need scale/signal).
Then state the **falsifiable priors** this study will test — the specific, checkable
predictions the card commits to. Mirror them into `study.yaml:predictions_to_falsify`.
The card is not done until it has staked a claim SYNTHESIZE can falsify.

### 5. Verified references
Verify EACH reference — do not cite from memory:

- **If the `alphaxiv-paper-lookup` skill is available** (check for its SKILL.md under
  `~/.claude/skills/` or `.agents/skills/`), use it for the lit-scan — worker agents
  without the Skill tool read that SKILL.md and drive its scripts via Bash.
- **Else** use `WebSearch`/`WebFetch` (arxiv.org, publisher pages) and confirm venue,
  year, and arXiv id.
- Mark anything you could not verify as ⚠️ UNVERIFIED, explicitly. An unverified
  reference is a liability, not a citation.
- Set `refs_verified: true` in the frontmatter only when every row is verified.

## What "from-scratch" and "falsifiable" mean here

- **From-scratch (part 3) applies to non-DL methods too.** For a robust estimator, the
  minimal version is a scipy/numpy loss plus an optimizer call — write THAT, not a
  library one-liner, so the study can see what the method actually does.
- **A good falsifiable prior (part 4)** names a lever, a direction, and a magnitude with
  units — and can come out false. Example: "frozen DAE reps + LGBM will NOT beat the
  0.6701 raw-GBDT baseline (Δ ≤ 0)." SYNTHESIZE later records held / falsified against
  the observed delta.

## Frontier methods require a lit-scan

If the method is recent or unfamiliar (SSL for tabular, a 2023+ architecture, a niche
robust estimator), a lit-scan step is MANDATORY before the card is complete: find the
seminal paper, 1-2 key follow-ups, and any resonant application (e.g. Jahrer's Porto
Seguro DAE for insurance). Position the method against the trend, honestly.

## Then unblock

With `data_card.md` = GO and `method_card.md` complete, the hard-block lifts and the
experiment loop can begin. If you skipped either, you owe a logged `--fast-path` in
`program.md` with a reason.
