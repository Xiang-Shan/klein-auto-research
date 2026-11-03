---
type: method-card
domain: "LLM evaluation (grade-school math reasoning)"
profile: "llm"
status: complete
concepts: [chain-of-thought, direct-answer, exact-match, paired-comparison, mcnemar-exact, cluster-bootstrap, template-twins, contamination-gap, memorization-mixture, detection-limit, hosted-model-nondeterminism, call-ledger, replication-tolerance]
related: [knowledge/method_cards/llm-prompting-and-eval.md]
refs_verified: true   # references.yaml: 21 rows, each read at its source 2026-11-03; 17 also resolved by `klein refs verify --record`, 4 are url-only
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2: notation table, five display equations, the detection-limit table (closed forms checked by a stated-recipe Monte Carlo)
  papers: true         # references.yaml: 21 rows, all verified 2026-11-03 (refs_verified: true)
  practice: true       # §3: the from-scratch numpy plan, mapped file by file onto lib/ and analyze.py, which already realize it
---

# Method card — chain-of-thought vs direct answering on GSM8K, and the fresh-twin contamination probe

> Gate 2 (METHOD), written 2026-11-03 before any benchmark item was sent to the model,
> and revised twice the same day: after the lead's instrument fixes and an adversarial
> review of the first version, then after a second review (the revision log closes §5).
> Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.
> No model API was called to write this card. Every number below is one of three things,
> and each says which: arithmetic on ASSUMED accuracies (a closed form, or a Monte Carlo
> whose seed, draw count and model are stated); a property of the instrument measured
> from `lib/twins.py` with a scratch seed that matches no block; or a value copied from a
> verified reference (§5).

## 1. Intuition (for a practitioner)

You run LLM benchmarks. You have watched a prompt change move GSM8K by twenty points and
reported it. This card is about two questions that report skipped. Was the gain measured
on items the model could have memorized? And how large would a difference have to be
before 300 items, or 50 templates, could detect it at all?

**CoT vs direct is scratch paper vs no scratch paper.** Both arms send the same question
to the same model (the dated snapshot `qwen-flash-2025-07-28`) with the same decoding
settings: greedy, temperature 0, thinking mode off. With thinking off, the only reasoning
a response contains is the text it prints. The arms differ in one instruction. "Answer
with the final number only" takes the scratch paper away. "Solve the problem step by
step, then give the final number after 'Answer:'" gives it back. In 2022 the step-by-step
prompt was the intervention, because models answered tersely unless told otherwise (Wei
et al. used few-shot worked examples; Kojima et al. a one-line instruction, which is what
this study's `cot` arm is). A 2025 instruct model writes its steps out unprompted. So here
it is really the direct arm that intervenes, and `em_gain` measures how much exact-match
is lost when the scratch paper is taken away.

**Pairing is a within-subject A/B test.** Every item is answered under both arms. That
is like showing each user both variants instead of splitting users into two groups: the
item's difficulty is the same on both sides, so it cancels out of the difference. Items
both arms get right, and items both get wrong, are ties. They say nothing about which
arm is better. Only the items where the arms disagree carry information, and counting
which way they disagree is McNemar's test in one sentence.

**The twin probe is a train-vs-validation gap for the benchmark itself.** You know the
overfitting signature: training accuracy sits above validation accuracy. GSM8K's test
set has been public since 2021 and is mirrored everywhere. If it leaked into the model's
training data, then for this model GSM8K is a training set, and its score is a training
score. A validation score needs items the model cannot have seen. A *twin* is the same
question with new numbers: same names, same wording, same arithmetic structure, and a new
gold answer computed by an exact rule (`lib/twins.py`). A twin's answer is never equal to
the original's. A model that memorized "the shoebox question's answer is 10" gets no help
from that on a twin whose answer is 13. Score the original, score its twins, and subtract,
template by template, then average. That is the contamination gap `em_gap`, and it is
GSM-Symbolic's design (Mirzadeh et al.).

**Twins are augmentations, not new test items.** You would not count four crops of one
image as four independent test images. Four twins of one template share everything
except their numbers. If the template is a trap (an awkward "1/3 red of his shoeboxes"),
all four twins inherit the trap. So the 200 twins hold somewhere between 50 and 200 items'
worth of information, and the honest interval resamples whole templates. With 50
templates, a 5-point contamination gap is below what the study can resolve; about 9
points is the edge (§2 does the arithmetic).

**What the probe cannot do, stated up front.** A twin can be harder or easier than its
original. After the sampler fix, twin numbers are centred on the originals' but twin
*answers* still run modestly larger (median ×1.13 on the development block, §4), so a
positive gap mixes contamination with a small difficulty shift. The probe sees memorized
*instances* (an answer, or the exact solution text) but not exposure to the problem
*type*: a twin is a fresh string, not a fresh kind of problem, and for five of the 50
templates number-swapped variants have been public since December 2024 (§4). Finally, on
a hosted model temperature 0 does not make outputs deterministic. The call ledger freezes
one draw, so the study can be replayed exactly, but only a re-query measures the model
itself.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $i = 1..n$ | an item: a question with an integer gold answer. $n = 300$ on the public lane (`gsm8k`), $n = 200$ on a twin block |
| $t = 1..T$ | a template; $T = 50$ |
| $k = 1..m$ | a twin of template $t$ within one block; $m = 4$ |
| $r_i,\ c_i \in \{0,1\}$ | exact match of item $i$ under the `direct` and the `cot` arm: 1 iff the integer `extract()` reads from the response equals the gold |
| $n_{10},\ n_{01}$ | discordant counts: $\#\{c=1, r=0\}$ (only CoT right) and $\#\{c=0, r=1\}$ (only direct right); $D = n_{10}+n_{01}$ |
| $p_{10},\ p_{01}$ | population shares of those two cells |
| $p_c,\ p_r$ | population exact-match of the cot and direct arms |
| $\Delta$ | the paired CoT gain, `em_gain` $= p_c - p_r$ |
| $o_t \in \{0,1\}$ | CoT score of template $t$'s GSM8K original (one item, one greedy response) |
| $y_{tk} \in \{0,1\}$ | CoT score of twin $k$ of template $t$; $\bar y_t = \frac1m\sum_k y_{tk}$ (`twin_mean`) |
| $G$ | the template-paired contamination gap, `em_gap` |
| $\mu_t$ | template $t$'s true CoT accuracy on its twins (its difficulty) |
| $\pi_t$ | template $t$'s true CoT accuracy on its original, $P(o_t = 1 \mid t)$ |
| $p,\ q$ | $p = \mathbb E[\mu_t]$, $q = p(1-p)$ |
| $p_o$ | $\mathbb E[\pi_t]$, the originals' exact-match |
| $\rho$ | intra-template correlation $\operatorname{Var}(\mu_t)/q$: the share of item variance that is "which template" |
| $\rho_d$ | the same for the per-item paired difference $c - r$ on a twin block |
| $\delta$ | the true contamination shift $p_o - p$; it can never exceed $1 - p$ |
| $\lambda$ | in the memorization mixture of eq. (4), the share of templates whose original is memorized |
| $B$ | bootstrap replicates: 10,000, seed 20261103, percentile 95% (`lib/measure.py`) |
| $\Phi$ | the standard normal CDF |

**(1) The paired gain and its standard error.** This is what `run_cot_gain` prints, and
the closed form shows exactly what pairing buys:

$$\hat\Delta=\frac1n\sum_{i}(c_i-r_i)=\frac{n_{10}-n_{01}}{n},\qquad
\operatorname{SE}(\hat\Delta)=\sqrt{\frac{p_{10}+p_{01}-\Delta^2}{n}}
\quad\text{vs. unpaired}\quad\sqrt{\frac{p_c(1-p_c)+p_r(1-p_r)}{n}}$$

The two variances differ by exactly $2\operatorname{Cov}(c,r)/n$. Pairing buys precision
in proportion to that covariance (how far the same items are hard for both arms), not
to how often the arms agree. Agreement and covariance are different things. Two
independent arms that are each 95% right agree on 90.5% of items, yet their covariance
is 0 and the paired SE equals the unpaired one (0.018 on 300 items). At direct 0.83, CoT
0.93 and $p_{01} = 0.03$ the covariance is $(p_r - p_{01}) - p_c p_r = +0.028$, and the SE
falls from 0.026 to 0.022. The bigger gain is validity. Both arms see the same 300 items,
so the gain cannot come from one arm happening to get easier items.

**(2) McNemar's exact test.** Under $H_0$ (the arms are equally good), each discordant
item is a fair coin:

$$p_{\text{McNemar}}=\min\!\Bigl(1,\;2\sum_{j=0}^{\min(n_{10},n_{01})}\binom{D}{j}\,2^{-D}\Bigr)$$

Concordant items never enter the test. One caveat matters here: the test assumes the $D$
discordant items are independent. That holds for the 300 public GSM8K items. It fails on
a twin block, where four twins share a template. `analyze.py` prints `mcnemar_p` on twin
blocks too, and there it overstates the evidence (the lead's note in `program.md` says
the same). On twins, read the cluster interval instead.

**(3) The cluster bootstrap over templates.** On a twin block `lib/measure.py` resamples
whole templates, using a ratio estimator so that unequal cluster sizes stay correct:

$$\hat\Delta^{*b}=\frac{\sum_{t\in S_b}\sum_{k}(c_{tk}-r_{tk})}{\sum_{t\in S_b}m_t},\quad
S_b=T\text{ templates drawn with replacement};\qquad
\operatorname{Var}_{\text{cluster}}(\hat\Delta)\approx\frac{\sigma_d^2}{n}\bigl(1+(m-1)\rho_d\bigr)$$

with $\sigma_d^2 = p_{10}+p_{01}-\Delta^2$. The design effect $1+(m-1)\rho_d$ is what an
item-level bootstrap leaves out. With $m=4$ and $\rho_d=0.5$, the 200 twins carry the
information of $200/2.5 = 80$ independent items.

**(4) The template-paired contamination gap and its variance.** Each original is compared
with its own twins. Given the template, the original and the twins are independent draws,
so $\operatorname{Cov}(o_t,\bar y_t)=\operatorname{Cov}(\pi_t,\mu_t)$ and, exactly,

$$G=\frac1T\sum_{t}\bigl(o_t-\bar y_t\bigr),\qquad
\operatorname{Var}\bigl(o_t-\bar y_t\bigr)=\underbrace{p_o(1-p_o)}_{\text{one original}}
+\underbrace{\rho q+\frac{(1-\rho)\,q}{m}}_{\text{the twin mean}}-2\operatorname{Cov}(\pi_t,\mu_t),
\qquad \operatorname{SE}(G)=\sqrt{\operatorname{Var}/T}$$

The covariance is subtracted because a template's difficulty is shared by its original
and its twins: a hard template counts against both sides of its own comparison, so the
template mix cannot enter the gap. That is the second thing pairing buys. To evaluate the
covariance you need a model of how contamination moves $\pi_t$. This card uses a
**memorization mixture**. With probability $\lambda$ a template's original is memorized
and answered right. Otherwise it is answered like one of its twins:

$$\pi_t=\lambda+(1-\lambda)\mu_t\;\Rightarrow\;
\delta=\lambda(1-p),\quad\operatorname{Cov}(\pi_t,\mu_t)=(1-\lambda)\rho q,\quad
\operatorname{Var}=p_o(1-p_o)+\rho q+\frac{(1-\rho)q}{m}-2\Bigl(1-\frac{\delta}{1-p}\Bigr)\rho q$$

At $\delta=0$ this is $q(1-\rho)(1+1/m)$. At the ceiling $\delta=1-p$ every original is
right, $o_t$ is constant, and only the twins vary: $\rho q+(1-\rho)q/m$. The first version
of this card shifted $\pi_t=\mu_t+\delta$ and kept the covariance at $\rho q$. That pushes
$\pi_t$ above 1 whenever $\mu_t>1-\delta$, and at $p=0.90$, $\delta=0.10$ it returns a
negative variance ($-0.011$). The mixture never leaves $[0,1]$. A Monte Carlo (Beta
$\mu_t$, seed 20261103+4, 200,000 draws) matches the closed form to within 0.0002 in every
gap row of the table below. A logit-shift alternative, $\pi_t=\operatorname{expit}(\operatorname{logit}\mu_t+\beta)$,
gives SEs at most 0.0015 smaller and rule probabilities within 0.01 (seed 20261103+5,
100,000 draws). One consequence matters for P3: **the gap is capped by the twins' error
rate**, $G\le 1-$ `em_twins`.

**(5) What a point-estimate rule can decide.** P1 to P6 read the printed point estimate
(`primary_metric`, or `em_direct`), not the interval:

$$P\bigl(\hat\theta\le\theta_0\mid\theta\bigr)\approx\Phi\!\Bigl(\frac{\theta_0-\theta}{\operatorname{SE}(\theta)}\Bigr),
\qquad \mathrm{MDE}_{80\%}:\ \frac{\theta}{\operatorname{SE}(\theta)}=1.96+0.84$$

When the truth sits exactly at the threshold, a rule placed there is a coin flip. The
normal form is the mental model. The table below computes the probabilities exactly,
because every threshold sits on the estimate's own grid and every rule is inclusive:
P1 holds iff at most 255 of 300 are right; P2 iff $n_{10}-n_{01}\ge 30$; P4 and P5 iff
$n_{10}-n_{01}\ge 20$ of 200; P3 and P6 iff $200\,G\le 10$. That is why a truth exactly
at a threshold gives 0.51 to 0.58 rather than 0.50.

### Detection limits: what 300 items and 50 templates can resolve

The accuracies below are ASSUMED (no model was queried). SE comes from equations (1), (3)
and (4) at the stated truth. "P(rule holds)" is exact on the rule's integer grid: the
binomial for P1; the exact distribution of $n_{10}-n_{01}$ (300-fold convolution) for P2;
a Monte Carlo for P3 to P6 (200,000 draws, seed 20261103+3 for twin gains with Dirichlet
template effects of intra-template correlation $\rho_d$, seed 20261103+4 for gaps with
Beta template difficulty and the memorization mixture). MDE is the smallest true effect
whose 95% interval excludes 0 with probability 0.80, solved with the SE at that effect
(bisection on $\theta/\operatorname{SE}(\theta)=2.80$, nuisances held: $p_{01}$ 0.03 for the gains, $p$ and
$\rho$ for the gap). With $p_{01}$ held, the paired MDE depends only on the discordance, not
on the arms' accuracy levels, so it is the same 0.054 in every public row.

| Estimand (prediction) | Unit, n | Assumed truth | SE | 95% half-width | MDE (80%) | P(rule holds) |
|---|---|---|---|---|---|---|
| `em_direct` (P1, ≤ 0.85) | 300 items | 0.50 / 0.70 / 0.80 / 0.85 / 0.88 | 0.029 / 0.026 / 0.023 / 0.021 / 0.019 | 0.057 / 0.052 / 0.045 / 0.040 / 0.037 | n/a | 1.00 / 1.00 / 0.99 / 0.52 / 0.07 |
| `em_gain`, public (P2, ≥ 0.10) | 300 paired items | direct 0.65, CoT 0.93 (Δ +0.28, $p_{01}$ 0.03) | 0.030 (unpaired 0.031) | 0.058 | 0.054 | 1.00 |
| | | direct 0.75, CoT 0.93 (Δ +0.18) | 0.026 (unpaired 0.029) | 0.052 | 0.054 | 1.00 |
| | | direct 0.83, CoT 0.93 (Δ +0.10) | 0.022 (unpaired 0.026) | 0.044 | 0.054 | 0.53 |
| | | direct 0.88, CoT 0.94 (Δ +0.06) | 0.020 (unpaired 0.023) | 0.039 | 0.054 | 0.03 |
| `em_gain`, twins (P4, P5, ≥ 0.10) | 200 items in 50 templates | Δ +0.20, $p_{01}$ 0.03; $\rho_d$ = 0 / 0.25 / 0.5 | 0.033 / 0.044 / 0.052 | 0.065 / 0.086 / 0.103 | 0.070 / 0.102 / 0.130 | 1.00 / 0.99 / 0.98 |
| | | Δ +0.10; $\rho_d$ = 0 / 0.25 / 0.5 | 0.027 / 0.036 / 0.043 | 0.054 / 0.071 / 0.085 | (as above) | 0.53 / 0.52 / 0.51 |
| `em_gap` (P3, P6, ≤ 0.05) | 50 templates | $p$ 0.90, $\rho$ 0.3; $\delta$ = 0 / 0.025 / 0.05 / 0.075 / 0.10 | 0.040 / 0.038 / 0.036 / 0.033 / 0.029 | 0.078 / 0.074 / 0.070 / 0.064 / 0.057 | 0.087 | 0.91 / 0.77 / 0.53 / 0.24 / 0.04 |
| | | $p$ 0.90, $\delta$ 0; $\rho$ = 0 / 0.6 | 0.047 / 0.030 | 0.093 / 0.059 | 0.081 / 0.099 | 0.87 / 0.96 |
| | | $p$ 0.85, $\rho$ 0.3; $\delta$ = 0 / 0.05 / 0.10 | 0.047 / 0.045 / 0.041 | 0.093 / 0.087 / 0.080 | 0.111 | 0.87 / 0.52 / 0.12 |
| | | $p$ 0.95, $\rho$ 0.3; $\delta$ = 0 / 0.05 (the ceiling) | 0.029 / 0.021 | 0.057 / 0.042 | none below the ceiling | 0.97 / 0.58 |

How to read the table:

1. **The CoT-gain question is well powered.** A true gain of 0.18 or more clears the
   0.10 bar with probability at least 0.99 on the public lane, and a gain of 0.20 clears
   it with probability at least 0.98 on the twins. At exactly 0.10 the rule is a coin flip
   (0.51 to 0.53).
2. **The contamination question is not.** The 95% interval on `em_gap` spans roughly
   ±0.06 to ±0.09. At 80% power the study detects a gap of about 0.08 to 0.10 when the
   twins score 0.90 (0.11 when they score 0.85), and it cannot tell 0 from 0.05. If P3
   holds, that means "no gap above about the interval's upper end". It does not mean "no
   contamination". Halving the SE would take about four times as many templates.
3. **The ceiling.** $G \le 1 -$ `em_twins`. If the twins score 0.95, no true gap above
   0.05 exists: P3 can then fail only by noise (0.42 at the ceiling), and no gap is
   detectable at 80% power.
4. **Granularity.** `em_original` moves in steps of 1/50 = 0.02, so one original flipping
   from right to wrong moves `em_gap` by 2 points. A twin moves it by 0.005.

**The cells are coupled by construction.** The call ledger answers an identical request
once, which ties several cells together:

- **P3 and P6** share the same 50 original CoT answers (cached). Only the twin means are
  re-drawn, so $\operatorname{SD}(G_{\text{dev}}-G_{\text{sealed}})=\sqrt{2(1-\rho)q/(mT)}$,
  which does not depend on the true gap: 0.025 at $p$ 0.90, $\rho$ 0.3 (0.030 at
  $\rho$ 0, 0.019 at $\rho$ 0.6). P6 should land within about ±0.05 of P3 at 95%. Whether
  the two *verdicts* agree depends on where the true gap sits relative to 0.05
  (simulation, seed 20261103+6, 200,000 draws, $p$ 0.90; the bracket is the range over
  $\rho$ = 0 to 0.6):

  | true gap $\delta$ | 0 | 0.02 | 0.04 | 0.05 | 0.06 | 0.08 | 0.10 |
  |---|---|---|---|---|---|---|---|
  | P(P3 and P6 agree), $\rho$ 0.3 | 0.91 | 0.85 | 0.79 | 0.77 | 0.77 | 0.83 | 0.94 |
  | range over $\rho$ 0–0.6 | 0.88–0.96 | 0.81–0.89 | 0.76–0.83 | 0.74–0.82 | 0.74–0.83 | 0.82–0.87 | 0.94–0.98 |

  Agreement is lowest when the truth sits near the threshold. There the two verdicts are
  two partly independent coin flips around 0.05.
- **P4 and P5** use the same 50 templates with new numbers. Only the template effects tie
  the two blocks together:
  $\operatorname{SD}(\Delta_{\text{dev}}-\Delta_{\text{sealed}})=\sqrt{2\sigma_d^2(1-\rho_d)/(mT)}$
  = 0.047 / 0.041 / 0.033 at Δ +0.20 and $\rho_d$ 0 / 0.25 / 0.5. That is a 95% band of
  ±0.092 / ±0.080 / ±0.065 (±0.076 / ±0.066 / ±0.054 at Δ +0.10). At $\rho_d$ 0 the two
  blocks are independent samples: the band is at its widest, and at a true gain of
  exactly 0.10 the two verdicts are two independent coin flips. The table below gives
  the probability that the verdicts agree. Recipe: the P4 row's simulation, seed
  20261103+10, 200,000 draws per cell. Template effects are Dirichlet with concentration
  $1/\rho_d-1$, so the intra-template correlation of $c-r$ is $\rho_d$, and there are
  none at $\rho_d$ 0. $p_{01}$ is 0.03, both blocks are drawn from the same 50 template
  probabilities, and each verdict is its integer rule $n_{10}-n_{01}\ge 20$.

  | true twin gain Δ | 0.06 | 0.10 | 0.14 | 0.20 | 0.28 |
  |---|---|---|---|---|---|
  | P(P4 and P5 agree), $\rho_d$ 0 | 0.89 | 0.50 | 0.86 | 1.00 | 1.00 |
  | $\rho_d$ 0.25 | 0.86 | 0.69 | 0.84 | 0.99 | 1.00 |
  | $\rho_d$ 0.5 | 0.88 | 0.80 | 0.86 | 0.97 | 1.00 |

  A true gain of 0.20 or more gives the same verdict on both blocks with probability 0.97
  to 1.00 across $\rho_d$ 0 to 0.5. Near the threshold the verdicts can split. At a true
  gain of 0.10 they agree only 0.50 to 0.80 of the time, least when templates carry no
  shared effect, so a split there is expected and is not a contradiction. The sealed
  block therefore guards against luck in the twin instances, not against the choice of
  templates.
- **Mechanical identity:** P4's `em_cot` must equal P3's `em_twins` exactly. Both come
  from the same 200 cached CoT responses, and with four twins per template the
  template-weighted mean equals the item mean. Likewise P5's `em_cot` must equal P6's
  `em_twins`. A mismatch means an instrument fault (the ledger did not serve the same
  answers), not a finding.

## 3. Minimal from-scratch implementation plan

The instrument already exists. This section is the plan it realizes, so a reader can check
each piece against §2. Nothing is trained, so `kleinlib.torch_loop` (MPS-safe
index-shuffle batching) and `kleinlib.encoders` have no role here: nothing is fit,
batched or encoded. The "model" is a hosted endpoint behind the call ledger.

| Piece | Where it lives | kleinlib helper it leans on |
|---|---|---|
| items, lanes, partitions | `prepare.py` → `data/prepared/index.csv` (sha256 a36b5e35…); `lib/measure.py: read_index, lane, twin_lane` | `kleinlib.data.load_items` (prints `split_fingerprint:`; honours the sealed dry run) |
| templates and twins | `lib/twins.py: log_grid, log_uniform, degeneracies, Template.solve / draw / sample, generate, declared_blocks, validate` | none (exact `fractions.Fraction` arithmetic) |
| arms, decoding, scorer | `lib/prompts.py: ARMS, PARAMS, messages, extract, exact_match` | none |
| model calls | `analyze.py: _ask` | `kleinlib.calls.CallLedger.from_contract` (pins every request and response under `calls/`; an identical request is answered once) |
| paired gain + interval + McNemar | `analyze.py: run_cot_gain`; `lib/measure.py: paired_difference_ci` | `kleinlib.metrology.paired_bootstrap` (public items), `item_bootstrap(groups=templates)` (twins), `mcnemar_exact` |
| contamination gap + interval | `analyze.py: run_contamination` | `paired_difference_ci` with one row per template (templates are the resampling unit) |
| printed block | `analyze.py` | `kleinlib.eval.evaluate_estimate` (custom metric spec `em_gain` / `em_gap`; refuses a non-finite estimate, a non-finite or reversed interval, and a point outside its own interval) |

The whole method in numpy, with nothing hidden behind a framework:

```python
import itertools, math, re
import numpy as np

# 0. A twin: the same text with new numbers. Each slot is drawn LOG-uniformly on its
#    range inside [v/2, 2v] (so the median draw is the original v), then the draw is
#    rejected if it is ill-posed, degenerate, the original itself, or keeps the answer.
def draw_slot(rng, v, lo, hi, step):
    grid = np.arange(lo, hi + 1, step)
    left = np.maximum(grid - step / 2, max(lo - step / 2, v / 2))
    right = np.minimum(grid + step / 2, min(hi + step / 2, 2 * v))
    mass = np.log(np.maximum(right / left, 1.0))   # each grid cell's log-length
    return int(rng.choice(grid, p=mass / mass.sum()))
def degenerate(orig, vals):                         # a 1/1 share, a 1x multiplier, ...
    return any(o >= 2 and vals[k] <= 1 for k, o in orig.items()) or any(
        orig[a] != orig[b] and vals[a] == vals[b] for a, b in itertools.combinations(orig, 2))
def twin(rng, t):
    gold0 = t.solve(t.original)
    while True:
        vals = {k: draw_slot(rng, v, *t.ranges[k]) for k, v in t.original.items()}
        if vals == t.original or degenerate(t.original, vals):
            continue
        try:
            gold = t.solve(vals)                    # exact Fractions; raises unless a positive integer
        except IllPosed:
            continue
        if gold != gold0:
            return t.render(vals), gold

# 1. The scorer: the integer after the LAST "Answer:"/"####" marker, else the last number.
MARK = re.compile(r"answer\s*[:=]|####", re.I)
NUM = re.compile(r"(?<![\d.])-?(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.\d+)?")
def to_int(tok):                       # "1,210" -> 1210, "18.00" -> 18, "2.5" -> None
    whole, _, frac = tok.replace(",", "").partition(".")
    return None if frac.strip("0") else int(whole)
def extract(text):
    text = text or ""
    marks = list(MARK.finditer(text))
    hit = NUM.search(text, marks[-1].end()) if marks else None
    if hit:
        return to_int(hit.group())
    nums = NUM.findall(text)
    return to_int(nums[-1]) if nums else None
def em(text, gold):
    return int(extract(text) == gold)

# 2. Two arms, one greedy call per item each (temperature 0, thinking off, max 1024 tokens).
DIRECT = "Answer with the final number only.\n\nQuestion: {q}\nAnswer:"
COT = "Solve the problem step by step, then give the final number after 'Answer:'.\n\nQuestion: {q}"
r = np.array([em(ask(DIRECT.format(q=q)), gold) for q, gold in items])
c = np.array([em(ask(COT.format(q=q)), gold) for q, gold in items])

# 3. Paired gain, its closed-form SE (eq. 1) and McNemar's exact p (eq. 2).
d = c - r
gain = d.mean()
se_paired = d.std() / math.sqrt(len(d))
n10, n01 = int(((c == 1) & (r == 0)).sum()), int(((c == 0) & (r == 1)).sum())
D = n10 + n01
p_mcnemar = 1.0 if D == 0 else min(1.0, 2 * sum(math.comb(D, j) for j in range(min(n10, n01) + 1)) / 2**D)

# 4. Percentile bootstrap: rows on public items, WHOLE TEMPLATES on twins (eq. 3).
rng = np.random.default_rng(20261103)
def cluster_ci(d, groups, B=10_000):
    labels, inv = np.unique(groups, return_inverse=True)
    sums, counts = np.bincount(inv, weights=d), np.bincount(inv).astype(float)
    draw = rng.integers(0, len(labels), size=(B, len(labels)))
    return np.quantile(sums[draw].sum(1) / counts[draw].sum(1), [0.025, 0.975])

# 5. The template-paired contamination gap, CoT arm only (eq. 4).
o = np.array([em(ask(COT.format(q=orig[t].q)), orig[t].gold) for t in templates])
ybar = np.array([np.mean([em(ask(COT.format(q=w.q)), w.gold) for w in twins[t]]) for t in templates])
per_template = o - ybar
gap = per_template.mean()
draw = rng.integers(0, len(templates), size=(10_000, len(templates)))
gap_ci = np.quantile(per_template[draw].mean(1), [0.025, 0.975])
```

The study's code differs from this sketch in three deliberate ways. `ask` is
`CallLedger.chat_many`, so requests run concurrently and are pinned. The intervals come
from `kleinlib.metrology` with the same seed and replicate count. The twins come from
`lib/twins.py` (`log_grid` computes the same cell masses as `draw_slot`; a few templates
carry their own range or a custom drawer, such as the oven template t0580), and
`validate()` must pass before `prepare.py` writes anything: (a) each template reproduces
its GSM8K gold exactly; (b) its text reproduces the question byte for byte; (c) it offers
at least 12 distinct well-posed twins within 0.5x to 2x of its numbers; and (d) no slot
range reaches 0 or 1 under an original of 2 or more, and none of 2,000 sampled instances
per template (100,000 in all, its own seed stream) is degenerate. The template set is 50
templates from the first 57 permutation candidates, and 7 were skipped with a recorded
reason (`twins.SKIPPED`: GSM8K test lines 1, 96, 288, 365, 426, 1149 and 1170).
`prepare.py` prints `50 templates, 7 skipped, ... 57 candidates consumed`. Before the
degeneracy guards the count was 6 skipped out of 56 candidates. Line 96 was a template
then (t0096, Harry's sleep). Once 1/den and den/den shares were forbidden, it had fewer
than `MIN_INSTANCES` non-degenerate twins, so it was retired to `SKIPPED`, and line 805
(t0805, James's ring) was templated in its place.

**Instrument diagnostics.** These are the LLM counterpart of `kleinlib.eval`'s
non-finite and near-constant prediction guards. `evaluate_estimate` already refuses a
non-finite number. It cannot see a degenerate *arm*. SYNTHESIZE can compute each of these
offline from the pinned `tables/*.tsv` and the `calls/` shards, with no new model call:

- the share of responses where `extract()` returns `None`, per arm;
- **direct-arm compliance:** completion tokens per item in the direct arm. A compliant
  direct answer is a handful of tokens. If the median runs to tens of tokens, the direct
  arm is writing its own steps, the scorer is taking the last number, and `em_gain`
  understates what removing the scratch paper costs;
- the number of `finish_reason == "length"` responses in the cot arm (the cap is
  `max_tokens` 1024);
- the set of `model_served` strings across every record. The contract names the
  snapshot `qwen-flash-2025-07-28`, so exactly that value is expected; anything else
  means the endpoint did not serve what the contract names, an instrument fault;
- the number of distinct extracted answers per arm. A constant answer, such as the smoke
  response's 0, is the near-constant failure.

## 4. When it pays / when it doesn't

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| CoT vs direct on multi-step arithmetic, thinking off | ≥ 200 paired items | Δ ≳ 0.15. Sprague et al., Table 7, zero-shot GSM8K: gains of +0.23 to +0.67 across 14 models; among the models whose CoT passed 0.85, the smallest gains belonged to those with the best direct answers (GPT-4o 0.588 → 0.958; Claude 3.5 Sonnet 0.622 → 0.961) | **pays**, and 300 paired items resolve it many times over (SE ≈ 0.02–0.03) |
| CoT vs direct, near-ceiling direct answers, or tasks that are not math or symbolic | any | Δ ≲ 0.05 | **doesn't**: the gain sits within about 2 SE of 0 while the cot arm writes many times more output tokens (Sprague et al.: outside math and symbolic tasks CoT ≈ direct) |
| template-paired contamination gap | 50 templates × 4 twins | true gap ≳ 0.09 (twins at 0.90) | **pays**: detectable at 80% power (0.08–0.10 across $\rho$ 0–0.6; 0.11 if the twins score 0.85) |
| template-paired contamination gap | 50 templates × 4 twins | true gap ≤ 0.05, or twins ≥ 0.95 | **doesn't resolve**: an interval of ±0.06 to ±0.09 covers 0 and 0.05 alike, and with twins at 0.95 no gap above 0.05 can exist; halving the SE needs about 200 templates |
| unpaired gap (originals vs twins of other templates) | any | any | **doesn't**: the template mix enters the gap, and the variance loses its $-2\operatorname{Cov}(\pi_t,\mu_t)$ term |
| item-level bootstrap on twins | 200 twins | any | **doesn't**: understates the SE by $\sqrt{1+3\rho_d}$, a factor of 1.3 to 1.6 at $\rho_d$ = 0.25 to 0.5 |
| replay from the ledger (`klein replicate --replay`) | any | n/a | **pays for audit**: parsing, scoring and aggregation re-derive offline. It says nothing about the model |
| salted re-query (`klein replicate E####`, no flag: its default tolerance is the track's `minimum_delta`, which is the pre-registered 0.03 for `cot_gain` and 0.05 for `contamination`) | 300 items, or 50 templates | per item-arm flip rate ≤ 3% | **pays**: reproduces with probability at least 0.91 (0.91 to 0.97 at a 3% flip rate); at a 10% flip rate, 0.66 to 0.76 (table below) |
| salted re-query at a 0.01 bar (the contract's `minimum_delta` before the tolerances were made mechanical) | 300 items, or 50 templates | flip rate 3% | **doesn't**: reproduces with probability 0.32 to 0.48, so serving noise alone fails it more often than not |

### The model under test: what is and is not documented

- **Pinned.** `study.yaml` calls the dated snapshot `qwen-flash-2025-07-28`, not the
  alias `qwen-flash`, which the provider can repoint (lead decision in `program.md`; the
  lead confirmed the endpoint serves the snapshot with one trivial non-GSM8K request).
  The provider documents the alias as "functionally equivalent to the snapshot model
  qwen-flash-2025-07-28" (`ref:alibaba_qwenflash`). The ledger still records
  `model_served` on every call (§3 diagnostics).
- **Price.** No price is pinned. `calls.price` is commented out, so there is no USD cap
  and no dollar figure; cost is reported in calls and tokens from `manifest.usage`. If a
  price is pinned later, it must cite the provider's pricing page and the date it was
  read, as a dated `ref:` row in `references.yaml`. List prices change, and an undated
  price makes every dollar figure derived from it unauditable.
- **Documented** (Alibaba Cloud Model Studio, read 2026-11-03; `ref:alibaba_qwenflash`,
  `ref:alibaba_thinking`). `qwen-flash` is "Qwen3 Flash", a hybrid thinking/non-thinking
  model. Thinking is *not* enabled by default; `enable_thinking` switches it, sent as a
  non-OpenAI parameter on the compatible endpoint. It has a 1,000,000-token context, a
  32,768-token output cap, and text in and out.
- **Not documented anywhere I could find**: parameter count, architecture (dense or
  MoE), training data or cutoff, and whether it corresponds to any open-weight Qwen3
  checkpoint. The Qwen3 Technical Report (`ref:yang2025qwen3`, May 2025) documents the
  open family (dense and MoE, 0.6B to 235B parameters, thinking and non-thinking modes in
  one model). It predates the 2025-07-28 snapshot and does not name qwen-flash. The
  snapshot's date falls near the Qwen3 "2507" open releases, but a date is not evidence
  of a base model.
- **Consequence.** No prior below leans on "qwen-flash is model X". The priors lean on
  regularities observed across many models (Sprague et al., GSM-Symbolic, GSM1k). The
  snapshot's date (July 2025) is after the GSM-Symbolic data release (December 2024),
  which matters for five templates (below).

### Temperature 0 is not determinism on a hosted model

- **What the provider promises** (`ref:alibaba_openai_compat`): temperature takes values
  in [0, 2); "A value of 0 is not recommended"; lower values give "more deterministic"
  output. The `seed` parameter "controls randomness" and makes no reproducibility
  promise. The study sends temperature 0 and no seed.
- **Why outputs still vary** (`ref:he2025`): server load changes the batch size, and the
  inference kernels are not batch-invariant, so the same request can come back
  different. In that report, 1,000 temperature-0 completions from
  Qwen3-235B-A22B-Instruct-2507 gave 80 distinct texts. Atil et al. (`ref:atil2024`)
  found accuracy varying by up to 15% across runs of five LLMs configured to be
  deterministic.
- **What that means here:**
  1. The ledger freezes one draw per request. A replay is exact; a re-query is not.
  2. Cells share draws (§2), so agreement between P3 and P4, or between P3 and P6, on the
     shared answers is by construction, not replication.
  3. The salted re-query is the only measurement of the model's own wobble. The lead
     pre-registered its tolerances before any run: a `cot_gain` cell reproduces when
     |Δ `em_gain`| ≤ 0.03, a `contamination` cell when |Δ `em_gap`| ≤ 0.05.
     **These tolerances are now mechanical, not a flag someone has to remember.** Each
     track's `minimum_delta` in `study.yaml` equals its tolerance (`cot_gain` 0.03,
     `contamination` 0.05). With no `--tolerance` flag, `klein replicate` takes the
     track's `minimum_delta` (`kleinlib/replicate.py: tolerance_ladder`: `--tolerance` >
     `minimum_delta` > floor std > exact). The replication record names the rung it used
     (`tolerance_source: minimum_delta`), so a plain `klein replicate E####` applies the
     pre-registered bar and an auditor can see that it did. An explicit `--tolerance`
     still overrides, and the record then says `--tolerance`. The notary decides
     `abs(float(new) - float(old)) <= tolerance` on the two `%.6f`-printed values.

     The table below simulates that exact arithmetic (seed 20261103+14, 200,000 draws per
     cell). This is an assumption, not a measurement. Every item-arm score is binary, so a
     1 can only drop and a 0 can only rise. The original run and the re-query are two
     draws from the same per-item law:
     - An item-arm whose accuracy is μ is "wobbly" with probability s, and then answered
       afresh. Otherwise it repeats its first answer.
     - So P(score = 1) = μ in both runs, and P(the score changes) = 2sμ(1−μ). s is set so
       the expected share of changed scores is the flip rate f.
     - μ is each arm's accuracy: direct 0.65 / CoT 0.93 on the anchor, direct 0.55 / CoT
       0.90 on the twin cell.
     - On the gap cell, μ is the template's $\mu_t$ (Beta, $p$ 0.90, $\rho$ 0.3,
       $\delta$ 0), shared by the original and its twins.

     | Cell (tolerance) | f = 1% | f = 3% | f = 5% | f = 10% | at f = 3%, a 0.01 bar |
     |---|---|---|---|---|---|
     | anchor `cot_gain`, 300 items × 2 arms (0.03) | > 0.999 | 0.966 | 0.900 | 0.758 | 0.477 |
     | twin_dev `cot_gain`, 200 twins × 2 arms (0.03) | 0.995 | 0.914 | 0.818 | 0.656 | 0.370 |
     | `contamination`, 50 originals + 200 twins (0.05) | 0.996 | 0.941 | 0.866 | 0.711 | 0.318 |

     **Why binary flips barely moved the table.** Revision 2 moved each score up or down by
     one, with probability f/2 each, whatever its value. That model looks wrong for a 0/1
     score, but it gives the same distribution of the shift. When both runs are draws from
     one law, an item's change, taken over both draws, is +1 or −1 with probability
     sμ(1−μ) each. That is the ±1 model with f/2 = sμ(1−μ). At the pre-registered tolerances every entry above is within 0.002 of
     revision 2's (0.004 in the 0.01-bar column). Two other readings give
     different numbers, and neither is a re-query of the same model:
     - *Hold the recorded original fixed and flip at the block's rates* (a 1 drops with
       probability f/(2p), a 0 rises with f/(2(1−p)); seed 20261103+11). The gain rows are
       unchanged. The contamination row reads 0.944 / 0.873 / 0.729 at f = 3 / 5 / 10%.
       Block-level rates make a template whose twins are nearly always right wobble as
       much as a hard one. They also pull each block's realized accuracy back toward 0.90,
       which a re-query of the same 50 templates cannot do.
     - *Flip every score with probability f, whatever its value* (seed 20261103+12). This
       pulls each arm toward 0.5 and shifts the expected `em_gain` by −2fΔ (−0.017 on the
       anchor at f = 3%). The anchor then reproduces only 0.833 at f = 3% and 0.556 at
       f = 5%. The contamination row is 0.949 / 0.875 / 0.727 at f = 3 / 5 / 10%, nearly
       unchanged, because at δ 0 its originals and twins drift by the same amount.

     **Floating point decides the boundary.** Both tolerances sit exactly on the
     estimates' grids (0.03 = 9/300 = 6/200; 0.05 = 10/200). A shift of exactly the
     tolerance passes or fails depending on how the two printed decimals round in binary.
     In the simulation the notary passed about 57% of exact-0.03 shifts on the anchor,
     about 48% on the twin cell, and all but a few of the exact-0.05 shifts on the gap.
     Against the inclusive reading the pre-registered "≤" intends, that costs at most 0.04
     of reproduction probability in the table (the twin cell at f = 10%). At f = 3% on the
     anchor, strict "< tolerance" gives 0.954 and inclusive "≤ tolerance" gives 0.975,
     against the notary's 0.966.

     **What a failed replication says.** Its weight as evidence about the flip rate is a
     likelihood ratio, P(fail | f₁) / P(fail | f₀), read off the simulation above:

     | Cell | f 5% vs 3% | f 10% vs 3% | f 3% vs 1% | f 5% vs 1% |
     |---|---|---|---|---|
     | anchor | 2.9 | 7.1 | ≈ 90 | ≈ 260 |
     | twin_dev | 2.1 | 4.0 | 18 | 37 |
     | `contamination` | 2.3 | 4.9 | 14 | 31 |

     At f = 1% the anchor failed only about 80 times in 200,000 draws, so read its two
     1% ratios to their first digit. A failure all but rules out a 1% flip rate. It does little to separate
     3% from 5%, so what it implies about f ≥ 5% depends on the prior:
     - With even prior odds on f = 3% against f = 5%, one failure moves P(f = 5%) to 0.75
       on the anchor, 0.68 on the twin cell and 0.69 on the gap.
     - With prior odds of 1:3 against 5%, it moves it to 0.49 / 0.41 / 0.43, about even.
     - With 1:9, it moves it to 0.25 / 0.19 / 0.20.

     So a failure alone does not establish a flip rate of 5% or more. Any such
     conclusion must state the prior it used. A failure is also what a changed endpoint
     would produce, and the `model_served` diagnostic (§3) separates that case.

### A twin can be harder or easier than its original

The fixed instrument, measured. First, a scratch scan: `lib/twins.py` `Template.sample`,
with `numpy.random.default_rng([777, source_index])` per template (a stream that matches
no block or validator seed), 2,000 draws per template. Second, the development block
`twin_dev` of index a36b5e35…. No model was called.

| Twin vs its original | Fixed sampler, scratch scan (100,000 twins) | `twin_dev` block (200 twins) | First sampler (seed 777, 200 draws per template), for comparison |
|---|---|---|---|
| slot values above / below / equal to the original's | 43% / 42% / 15% (median ratio 1.000) | — | 59% above (median ratio 1.20) |
| gold answers larger / smaller than the original's | 58% / 42% (median ratio 1.17, geometric mean 1.16) | 56.5% / 43.5% (median ratio 1.13) | 70% larger (geometric mean 1.36) |
| slot values with more / fewer digits in total | 12% / 12% (mean change −0.00 digits) | — | 21% / 7% (+0.16) |
| templates whose median twin answer exceeds the original's | 36 of 50 (18 above ×1.25) | — | 44 of 50 |

The instrument fixer measured the sealed block on the same index: median answer ratio
1.29, 62.5% larger. I did not re-read the sealed block.

The first sampler drew linearly on ⌈v/2⌉ to 2v, which has mean 1.25v and lies two thirds
above v. The fixed sampler draws log-uniformly on the same range (median v), floors every
range at 2 when the original is 2 or more, and rejects degenerate draws. The slot values
are now centred. The answers still drift up, and the cause is how some answers are built,
not the sampler. Where the answer is a small positive difference or remainder, the rule
must stay positive, so twins move up. The extremes are t0466 (×7.0: the original answer
is 1, so every twin is larger), t1281 (×6.95: 300 − 280 = 20), t0938 (×2.25), t0702
(×1.93), t0487 (×1.75) and t0177 (×1.63). On the low side are t0593 (×0.67), t0250
(×0.71), t0704 (×0.74), t0580 and t0772 (×0.80).

- **Harder.** Bigger operands mean more carries. Długosz et al. (`ref:dlugosz2026`,
  EMNLP 2026) found GSM-Symbolic's integers shifted larger than GSM8K's (K-S 0.12), and
  controlling for size "accounts for significance in half of the remaining cases" (their
  abstract). GSM8K's human writers presumably chose friendly numbers (an assumption, not
  measured here), while twins are drawn subject only to whole-number constraints.
- **Easier.** 42% of twins have smaller answers (43.5% on `twin_dev`). `whole()` and
  `pos()` reject the awkward-fraction instances. The degeneracy guard now also rejects
  the trivially easy draws the first sampler allowed: a 1/1 share, a 1x multiplier, two
  quantities made equal, an answer printed in the question. Those had made some twins
  easier than their originals. The seven skipped candidates never enter. One has an
  ambiguous gold answer (`SKIPPED[288]`). Line 96 (the retired t0096) was dropped
  because the guard left it below `MIN_INSTANCES` (§3).
- **Inherited.** A rule reproduces its original's gold exactly, including any slip in
  the gold. A twin therefore inherits the original's logic, which keeps the pair
  comparable but cannot correct the original.
- **Net.** The gap estimates contamination plus a difficulty shift plus noise. The
  shift is now smaller, but for most templates it still pushes the gap the same way as
  contamination does (positive). If P3 holds, that is conservative evidence against a
  large contamination effect. If P3 fails, that alone is not evidence of contamination.
  SYNTHESIZE can test the size explanation offline: regress the per-template gap (pinned
  table) on log(twin answer / original answer) (index). A positive slope says size, not
  memory. Expect `em_gap` on the sealed block to sit slightly above the development
  block's if size matters (×1.29 vs ×1.13). The ±0.05 coupling band in §2 is noise only
  and does not include that.

### Memorization vs reasoning: what this probe can and cannot separate

- **It can see instance memorization**: an answer string, or the exact solution text of
  one problem. A twin's answer never equals the original's.
- **It cannot see exposure to the problem's structure.** A model trained on GSM8K's
  worked solutions, or on number-swapped variants of GSM8K test items, would do as well
  on twins as on originals. "Fresh" here means a fresh string, not a fresh kind of
  problem. GSM1k (`ref:zhang2024`), with its human-written new problems, is the stronger
  control for that, at far greater cost.
- **Five templates have public number-swapped twins.** t1264, t0116, t0976, t1031 and
  t1088 are GSM-Symbolic templates. Apple's repository (`ref:apple_gsmsymbolic_data`)
  ships `templates/symbolic/0004, 0005, 0016, 0046, 0078.json`. Each file's `question` is
  byte-identical to our GSM8K line and its `id_orig` names that line. The repository also
  ships 50 generated instances of each in `generated_data/GSM_symbolic.jsonl`. Both came
  in its initial data release: commit b6a1625, dated 8 December 2024 on the repository's
  commit list, and mirrored on Hugging Face as `apple/GSM-Symbolic`. I checked these
  five files against `datasets/gsm8k-test/test.jsonl` myself. The instrument fixer
  checked all 100 symbolic templates and found no other overlap; the retired line 96 and
  the new line 805 are not among them. A model whose training data postdates December
  2024 may have seen number-swapped versions of exactly these five questions, so their
  twins are less fresh than the other 45 templates' twins. The overlap is too small to
  measure on its own: a 5-template subgroup gap has SE ≈ 0.13 ($p$ 0.90, $\rho$ 0.3). It
  is also too small to move the headline much (prior M7). Whether to flag, exclude or
  sensitivity-check these five templates is the lead's decision. The 45-template gap can
  be computed offline from the pinned table either way.
- **The cot arm dilutes the signature.** A model holding a memorized answer, when asked
  to show its steps, may re-derive the answer or replay memorized steps. A memorized
  answer would show most clearly in the *direct* arm, and the contract never runs the
  direct arm on the originals.
- **An indirect signature is available inside the contract.** Compare `em_direct` on the
  public lane (P2's cell) with `em_direct` on `twin_dev` (P4's cell). The comparison is
  unpaired and confounded by problem mix and number size, but if the direct arm drops
  much further than the cot arm between the two lanes, that is consistent with memorized
  answers propping up the public direct score (prior M2 and M3 below).

### Falsifiable priors

**The registered predictions** (CONSULT's, in `study.yaml`). For each, this card's
expectation, made before any run:

| P | Rule | Card expectation | P(holds) | Why |
|---|---|---|---|---|
| P1 | `em_direct` ≤ 0.85 (public) | **holds**; `em_direct` ≈ 0.30–0.65 | 0.93 | Zero-shot direct GSM8K accuracy runs 0.069 to 0.622 across Sprague et al.'s 14 models, topped by GPT-4o (0.588) and Claude 3.5 Sonnet (0.622). A fast, low-cost Qwen3 model with thinking off would have to beat them by about 0.23 at multi-step mental arithmetic. Three things could break it: the direct arm writing steps anyway (see the compliance diagnostic in §3), memorized public answers, or heavy 2025 math training. CONSULT's RQ1 prior (0.55–0.85) sits higher than this literature suggests. Exact P(rule) is 0.52 at a true 0.85 and 0.07 at 0.88 (§2). |
| P2 | `em_gain` ≥ 0.10 (public, paired) | **holds**; `em_gain` ≈ +0.25 to +0.60, with `em_cot` ≈ 0.88–0.95 | 0.90 | Table 7 gains run +0.23 to +0.67, and zero-shot CoT reached at least 0.85 for every model in that table except Llama 2 7B and Mistral 7B. P2 nearly duplicates P1: with `em_cot` ≈ 0.93, P2 fails only if `em_direct` ≳ 0.83, which nearly fails P1 as well. Expect the two to stand or fall together. With a paired SE of 0.02–0.03, the rule is decided by signal unless the true gain lies within ±0.05 of 0.10 (P(rule) 0.53 at exactly 0.10, 0.03 at 0.06; §2). |
| P3 | `em_gap` ≤ 0.05 (CoT; originals vs `twin_dev`) | **holds**; `em_gap` ≈ 0.00 to +0.05, with a 95% interval of about ±0.06–0.08 that includes 0 | 0.64 | GSM-Symbolic: every model declined when only the numbers changed, but by widely varying amounts. GSM1k: little overfitting in many frontier models. Długosz et al.: many such drops are not significant and are partly number size. Here the twins' residual answer drift (×1.13 on `twin_dev`) should push the gap up a little under CoT (expectation, not measured), and contamination of an undocumented model on a 2021 benchmark is plausible. The number is $\sum_\delta w(\delta)\,P(\text{rule}\mid\delta)$ at $p$ 0.90, $\rho$ 0.3, with JUDGMENT weights 0.30 / 0.30 / 0.20 / 0.12 / 0.08 on $\delta$ = 0 / 0.025 / 0.05 / 0.075 / 0.10 and the §2 rule probabilities (simulation, seed 20261103+9). Noise decides the rule for any true gap between about 0.02 and 0.08 (P(rule) 0.80 down to 0.20). |
| P4 | `em_gain` ≥ 0.10 (`twin_dev`, paired) | **holds**; the twin gain is at least the public gain | 0.90 | Bigger operands hurt mental arithmetic (direct) more than written arithmetic (cot), and the direct arm has no memorized answers to fall back on. Cluster SE 0.033–0.052 at Δ +0.20 ($\rho_d$ 0–0.5; §2 table), so P(rule) is 0.98 to 1.00 there and 0.51 to 0.53 at a true 0.10. |
| P5 | `em_gain` ≥ 0.10 (sealed twins) | **holds**, within about ±0.09 of P4 | 0.90; same verdict as P4: 0.97 to 1.00 if the true twin gain is 0.20 or more, 0.84 to 0.86 at 0.14, and 0.50 to 0.80 at 0.10, across $\rho_d$ 0 to 0.5 (seed 20261103+10, §2) | Same 50 templates with new numbers; only twin-instance noise differs. That noise is largest relative to the shared signal when templates carry no common effect: at $\rho_d$ 0 the 95% band is ±0.092 at a true 0.20, and at a true 0.10 the two verdicts agree only about half the time. |
| P6 | `em_gap` ≤ 0.05 (sealed twins) | **same verdict as P3**, within about ±0.05 of it | 0.64; same verdict as P3: 0.85 under the P3 weights, 0.74–0.98 across $\delta$ 0–0.10 and $\rho$ 0–0.6, lowest near $\delta$ ≈ 0.05 (simulated, §2) | The 50 original answers are P3's cached responses; only the twin means are re-drawn. The sealed twins' larger answer drift (×1.29) could lift P6 above P3 slightly. |

**The card's own priors.** Each names a lever, a direction and a magnitude with units, and
each can come out false. They are NOT registered: `study.yaml` uses `predictions:`, and the
schema refuses a second register (`predictions_to_falsify:`) beside it. So no notary will
adjudicate these. SYNTHESIZE scores them in findings as method-card expectations, and the
lead may register any of them as P7 and onward by re-recording CONSULT before E0001.

| M | Lever → direction, magnitude | Falsified if | P(holds) |
|---|---|---|---|
| M1 | Removing the scratch paper on public items costs **at least 0.20 EM**: `em_gain` ≥ +0.20 in P2's cell | `em_gain` < 0.20 | 0.80 |
| M2 | Fresh numbers cost the **direct** arm **at least 0.05 EM**: `em_direct`(public, P2 cell) − `em_direct`(`twin_dev`, P4 cell) ≥ +0.05 (unpaired across lanes) | the drop is < 0.05 | 0.60 |
| M3 | Fresh numbers cost the **cot** arm **less** than the direct arm: the CoT drop between the same two cells is smaller than the direct drop (difference of drops > 0 EM) | CoT drop ≥ direct drop | 0.70 |
| M4 | With 50 templates the probe **cannot resolve a 5-point gap**: on `twin_dev`, `ci_high` − `ci_low`, read to 3 decimals, is **at least 0.100 EM** | the width is below 0.100. That is likely only if the twins score ≳ 0.95 (P(M4) 0.64 at $p$ 0.95, $\delta$ 0), the template effect is strong (0.69 at $\rho$ 0.6), or the gap sits near its ceiling (0.72 at $\delta$ 0.10) | 0.91 |
| M5 | Temperature 0 is not deterministic: the salted re-query of the anchor changes **between 1 and 36** (0.17% to 6%) of the 600 item-arm scores, counted offline from the original and replication shards | 0 changes, or more than 36 | 0.75 |
| M6 | Scratch paper is expensive: the cot arm's mean output tokens per item are **at least 20 times** the direct arm's (from the `calls/` shards) | ratio < 20 | 0.90 |
| M7 | The five GSM-Symbolic templates do **not** drive the headline: `em_gap` on `twin_dev` recomputed over the other 45 templates (offline, from the pinned table) differs from the 50-template `em_gap` by **less than 0.03 EM** in either direction. Noise alone gives this difference an SD of 0.013 ($\sqrt{\operatorname{Var}/450}$ at $p$ 0.90, $\rho$ 0.3) | \|Δ\| ≥ 0.03 | 0.95 |

**Where M4's 0.91 comes from.** It is derived from this card's assumptions rather than
judged. The figure is $\sum_\delta w(\delta)\,P(\text{width}\ge 0.100\mid\delta)$ at $p$
0.90, $\rho$ 0.3, using P3's weights. That probability is 0.96 at δ 0, then 0.94 / 0.90 /
0.84 / 0.72 at δ 0.025 / 0.05 / 0.075 / 0.10. Contamination narrows the interval: as the
gap nears its ceiling, more originals are right, $o_t$ stops varying, and only the twin
means are left to spread.

The simulation replicates `lib/measure.paired_difference_ci` exactly: the study's
percentile bootstrap, with 10,000 replicates drawn from `default_rng(20261103)`. It runs
on 20,000 simulated cells per δ, seed 20261103+13. The widths land on the bootstrap's
0.005 grid, and 1.6% to 8% of them sit exactly at 0.100, so M4 reads the width to 3
decimals instead of comparing floats (a float comparison gives 0.90). The twins'
accuracy is what moves the number most: 0.99 at $p$ 0.85, and 0.47 at $p$ 0.95 with δ
capped at that ceiling (P3's weights renormalized onto δ 0 / 0.025 / 0.05). Revision 2's 0.70 was a judgment that the card's own
assumptions did not support.

**Instrument check (not a prior).** P4's `em_cot` equals P3's `em_twins`, and P5's
`em_cot` equals P6's `em_twins`, to six decimals. Any mismatch is a fault to fix before
any claim is made.

## 5. Verified references

Each row was read at its source on 2026-11-03: the arXiv abstract page, the
publisher's, proceedings or Crossref/OpenAlex record, or the provider's own page. Then
`uv run --locked klein refs verify --study studies/20-llm-cot-contamination --record`
resolved all 17 DOIs and arXiv ids and matched every title (21 references, 0 failed). The
four url-only rows (three Alibaba pages and the GSM-Symbolic repository) were checked by
reading them. One locator was left out on purpose. OpenAlex's record for GSM8K's arXiv
DOI (10.48550/arXiv.2110.14168) has the right authors but a corrupted title, so
`cobbe2021` resolves through its arXiv id. The DOI itself is correct: doi.org redirects
it to the arXiv page.

| Key | Reference | Where | Verified? |
|---|---|---|---|
| `cobbe2021` | Cobbe et al. 2021, Training Verifiers to Solve Math Word Problems (GSM8K) | arXiv:2110.14168 | ✅ arXiv abstract + API record |
| `wei2022` | Wei et al. 2022, Chain-of-Thought Prompting Elicits Reasoning in Large Language Models | NeurIPS 35 (2022); arXiv:2201.11903 | ✅ arXiv + NeurIPS proceedings page |
| `kojima2022` | Kojima et al. 2022, Large Language Models are Zero-Shot Reasoners | NeurIPS 2022; arXiv:2205.11916 | ✅ arXiv abstract (comments: accepted to NeurIPS 2022) |
| `sprague2024` | Sprague et al. 2024, To CoT or not to CoT? Chain-of-thought helps mainly on math and symbolic reasoning | ICLR 2025; arXiv:2409.12183 | ✅ arXiv abstract + HTML v3 Table 7 |
| `mirzadeh2024` | Mirzadeh et al. 2024, GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models | ICLR 2025; arXiv:2410.05229 | ✅ arXiv + ICLR 2025 proceedings PDF |
| `apple_gsmsymbolic_data` | Apple, ml-gsm-symbolic: GSM-Symbolic templates and generated data | github.com/apple/ml-gsm-symbolic; initial data release commit b6a1625 (8 Dec 2024) | ✅ repo page, commit list and commit page read 2026-11-03; five template files checked against GSM8K (url-only) |
| `dlugosz2026` | Długosz, Oliveira & Díaz-Rodríguez 2026, The Importance of Being Statistically Earnest: A Critical Re-evaluation of GSM-Symbolic | EMNLP 2026 (main); arXiv:2605.28700 | ✅ arXiv abstract + OpenAlex |
| `zhang2024` | Zhang et al. 2024, A Careful Examination of Large Language Model Performance on Grade School Arithmetic (GSM1k) | NeurIPS 2024 Datasets & Benchmarks; arXiv:2405.00332 | ✅ arXiv abstract (v4) |
| `sainz2023` | Sainz et al. 2023, NLP Evaluation in trouble: On the Need to Measure LLM Data Contamination for each Benchmark | Findings of EMNLP 2023, pp. 10776–10787; doi:10.18653/v1/2023.findings-emnlp.722 | ✅ Crossref (the arXiv comment says "EMNLP2024-Findings"; the Anthology DOI says 2023, and the DOI is followed here) |
| `golchin2024` | Golchin & Surdeanu 2023, Time Travel in LLMs: Tracing Data Contamination in Large Language Models | ICLR 2024 (Spotlight); arXiv:2308.08493 | ✅ arXiv abstract |
| `mcnemar1947` | McNemar 1947, Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages | Psychometrika 12(2):153–157; doi:10.1007/BF02295996 | ✅ Crossref |
| `efron1993` | Efron & Tibshirani 1993, An Introduction to the Bootstrap | Chapman & Hall/CRC; doi:10.1201/9780429246593 | ✅ Crossref (record dated 1994) |
| `davison1997` | Davison & Hinkley 1997, Bootstrap Methods and their Application | Cambridge University Press; doi:10.1017/CBO9780511802843 | ✅ Crossref + OpenAlex |
| `field2007` | Field & Welsh 2007, Bootstrapping Clustered Data | JRSS-B 69(3):369–390; doi:10.1111/j.1467-9868.2007.00593.x | ✅ Crossref |
| `miller2024` | Miller 2024, Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations | arXiv:2411.00640 (preprint) | ✅ arXiv abstract + HTML (§2.2 clustered, §4.2 paired, §5 power) |
| `atil2024` | Atil et al. 2024, Non-Determinism of "Deterministic" LLM Settings | arXiv:2408.04667 (preprint) | ✅ arXiv abstract |
| `he2025` | He & Thinking Machines Lab 2025, Defeating Nondeterminism in LLM Inference | Thinking Machines Lab: Connectionism; doi:10.64434/tml.20250910 | ✅ the post + Crossref |
| `yang2025qwen3` | Yang et al. (Qwen Team) 2025, Qwen3 Technical Report | arXiv:2505.09388 (preprint) | ✅ arXiv abstract |
| `alibaba_qwenflash` | Alibaba Cloud Model Studio, Qwen-Flash model page | alibabacloud.com/help/en/model-studio/qwen-flash-us | ✅ read 2026-11-03 (url-only) |
| `alibaba_thinking` | Alibaba Cloud Model Studio, Deep thinking | alibabacloud.com/help/en/model-studio/deep-thinking | ✅ read 2026-11-03 (url-only) |
| `alibaba_openai_compat` | Alibaba Cloud Model Studio, OpenAI compatibility (Chat Completions parameters) | alibabacloud.com/help/en/model-studio/developer-reference/compatibility-of-openai-with-dashscope | ✅ read 2026-11-03 (url-only) |

No row is ⚠️ UNVERIFIED.

### Frontier lit-scan: where this method sits

- **Seminal.** GSM8K (`cobbe2021`) made multi-step grade-school arithmetic a
  standard benchmark. Few-shot CoT (`wei2022`) and zero-shot CoT (`kojima2022`) showed
  that writing intermediate steps raises its accuracy sharply; zero-shot CoT took
  text-davinci-002 from 10.4% to 40.7% on GSM8K.
- **Follow-ups that set this study's regime.** Sprague et al. (`sprague2024`, ICLR 2025)
  bound where CoT pays: mainly math and symbolic tasks. Their Table 7 is the anchor for
  P1 and P2. GSM-Symbolic (`mirzadeh2024`, ICLR 2025) is the design this study copies:
  templates, re-instantiation, and the finding that scores fall when only the numbers
  change. Its templates and generated instances have been public since December 2024
  (`apple_gsmsymbolic_data`), which is why a copy of the design cannot assume its twins
  are unseen. GSM1k (`zhang2024`) is the human-written fresh-items control: drops of up
  to 8% for some families and little overfitting in many frontier models, with the gap
  tracking how likely the model is to generate GSM8K items.
- **The critique this card takes seriously.** Długosz et al. (`dlugosz2026`, EMNLP 2026)
  re-analysed GSM-Symbolic with per-question random effects and found only 8 of 20 models
  with significant drops, and number size accounting for significance in half of the
  remaining cases. That is precisely the pair of hazards §2 and §4 quantify for this
  instrument: a detection limit near the effect being claimed, and twins whose answers
  run larger than their originals'.
- **Contamination detection more broadly.** Sainz et al. (`sainz2023`) argue that a
  public benchmark should be presumed contaminated and measured per benchmark. Golchin &
  Surdeanu (`golchin2024`) probe for verbatim recall of test instances. The twin probe
  measures a *consequence* (a score drop) rather than recall, and needs no access to
  training data. It also cannot tell memorized instances from familiarity with a problem
  type.
- **The statistics.** McNemar (`mcnemar1947`) for paired binary outcomes; the
  percentile bootstrap (`efron1993`, `davison1997`); the cluster bootstrap
  (`field2007`); and the LLM-evaluation statement of all three (`miller2024`: clustered
  standard errors, paired analysis "wherever practicable", and power planning before
  running).
- **Serving.** Atil et al. (`atil2024`) and He (`he2025`) are why the ledger, the replay
  and the salted re-query are three different things.
- **Positioning, honestly.** As an intervention, CoT has largely been absorbed into the
  models: instruct models write steps by default, and since 2025 hidden "thinking" modes
  are the frontier. This study switches thinking off, so the visible CoT is the only
  scratch paper and the direct arm is the counterfactual. The contamination probe is a
  50-template, one-model, template-paired miniature of GSM-Symbolic with pre-registered
  thresholds. On the CoT-gain question it is well powered. On the contamination question
  it can detect only a gap of about 0.09 or more, and the card says so before the data
  does.

### Revision log

- **2026-11-03, revision 2** (after the lead's instrument fixes and an adversarial
  review). Eq. (4) is now the exact covariance identity with a memorization-mixture
  model. The first version's additive shift broke at the ceiling, and its δ > 0 rows
  reused the δ = 0 SE. The detection table is recomputed: exact rule probabilities on the
  integer grid, the SE at each assumed truth, and MDE solved with that SE. The re-query
  pass rates are recomputed under the pre-registered tolerances 0.03 / 0.05 with the
  notary's own float arithmetic. The P3/P6 agreement is now given as a function of the
  true gap, and P4/P5 agreement as a function of the true gain. The pairing prose now
  says covariance, not agreement. The P4 row's cluster SE now matches the table. The
  twin-sampler table is measured on the fixed log-uniform, degeneracy-guarded sampler.
  The snapshot pin and the rule for pinning a price are recorded. Added: the
  GSM-Symbolic overlap (5 templates, `apple_gsmsymbolic_data`), prior M7, and the gap
  ceiling. Changed: P3/P6 P(holds) from 0.65 to 0.64, now derived from stated weights;
  M2 from 0.65 to 0.60 and M3 from 0.75 to 0.70, because the fix removed most of the
  size shift these priors partly leaned on.
- **2026-11-03, revision 3** (after the second review; still no model call). Six changes:
  1. The P4/P5 coupling now covers $\rho_d$ 0 to 0.5 (seed 20261103+10, replacing +7's
     run at 0.25 and 0.5 only). At a true twin gain of 0.10 the verdicts agree 0.50 to
     0.80 of the time, and the dev-to-sealed 95% band reaches ±0.09. The P5 row follows.
  2. The re-query table is recomputed with binary scores (seed 20261103+14, replacing
     +8). The original and the re-query are two draws from one per-item law, so every
     entry at the pre-registered tolerances moved by at most 0.002 (0.004 at the 0.01
     bar). The fixed-original reading (contamination row 0.944 /
     0.873 / 0.729) and the constant-rate reading are reported beside it, with their own
     seeds.
  3. M4 is derived, not judged: 0.70 becomes 0.91 (seed 20261103+13, the study's own
     bootstrap replicated), with the width read to 3 decimals.
  4. The float paragraph no longer says "probably". It states the likelihood ratio of a
     failed replication and how the conclusion depends on the prior.
  5. The replication tolerances are mechanical: each track's `minimum_delta` equals its
     pre-registered tolerance, and `klein replicate` uses it by default. The 0.01 rows are
     relabelled as the old bar.
  6. §3 states the skipped count as 7 of 57 candidates: t0096 was retired by the
     degeneracy guards and t0805 templated in its place.

  Unchanged: every registered prediction's P(holds), P1 to P6.
