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
Explain it to the profile's audience (`references/profiles/<profile>.md` §1 — an ML
researcher, a mathematician, an actuary, a scientist) who has NOT read the paper. Lead with an
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
the profile's doctrine anchor (`references/profiles/<profile>.md` §3; for insurance,
Grinsztajn: trees still win on most tabular; deep methods need scale/signal). For an
`optimize` study the Practice leg is the from-scratch VERIFIER, written and tested
before any search runs — the checker is never the searcher.
Then state the **falsifiable priors** this study will test — the specific, checkable
predictions the card commits to. Mirror them into `study.yaml:predictions_to_falsify`.
The card is not done until it has staked a claim SYNTHESIZE can falsify.

### 5. Verified references
Verify EACH reference — do not cite from memory:

- **If the `alphaxiv-paper-lookup` skill is available** (check for its SKILL.md under
  `~/.claude/skills/` or `.agents/skills/`), use it for the lit-scan — worker agents
  without the Skill tool read that SKILL.md and drive its scripts via Bash.
- **If personal knowledge-base skills are available** (check
  `~/.claude/skills/ask-vault/SKILL.md` and `~/.claude/skills/arxiv-into-vault/SKILL.md`
  — example bindings from the author's harness; any grounded note store works the
  same way): a vault Q&A answers method questions with citations into the user's own
  study notes — useful for part 1's intuition and part 4's regime table; a
  paper-filing skill files each paper cited on the card so the papers leg leaves a
  durable trace outside the study. Neither replaces per-reference verification;
  UNVERIFIED marking rules are unchanged.
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
experiment loop can begin only after an acknowledgement is recorded:

```bash
uv run --locked klein gate record method --study studies/NN-slug \
  --acknowledged-by <actor>
```

If METHOD is deliberately abbreviated or skipped, use `klein gate override method`
with a non-empty reason and actor. Also note it in `program.md`; a prose-only v1
fast-path does not satisfy v2 preflight.

## The triad contract

A method is grasped when all three legs stand — **Theory** (the math core is
written, §2), **Papers** (the references are verified, `refs_verified: true`),
**Practice** (a runnable minimal implementation plan exists, §3). Assert them in
the card's `triad:` frontmatter; `klein gate record method` refuses while any leg
is false unless the `--note` names the missing leg and why it is acceptable
(e.g. `--note "papers pending: preprint only, flagged UNVERIFIED"`). Self-asserted,
machine-surfaced: the gate makes the assertion explicit and auditable, nothing more.

The practice leg may also be satisfied **by citation** when a from-scratch
implementation already exists elsewhere: cite a nano-research-style repo
(`nano_repos/NNN-slug/` with `final_summary.md` and `tutorial/index.html` as the
citable endpoints — the author's harness keeps a registry of these; any runnable
from-scratch repo with a measured-results summary counts). Name the exact nano and
the measured result relied on; a bare link with no measured result does not
satisfy the leg.
