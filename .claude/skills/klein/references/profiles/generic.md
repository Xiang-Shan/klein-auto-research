# Profile: generic

The default. Assumes a reader who runs computational research in some science and has
not read Klein's history.

## 1. Audience
A scientist or analyst who wants to know what the study found, how strongly, and what
would change their next decision. Assume numeracy; assume no knowledge of the method.

## 2. §⑤ heading
**⑤ Implications — what changes if this holds.** Prompt: state what a reader should do
differently if the confirmed claims are true, and what they should NOT conclude from
the exploratory ones. If the study registered a `materiality:` block, price the
consequence there and nowhere else; without one, "actionable" means only that a
registered bar was cleared.

## 3. Doctrine
Measurement resolution before comparison: no delta is discussed before the floor that
would detect it has been measured (`noise_floor`), and no frontier is opened before its
headroom is disclosed. Convergent evidence over single results: a confirmed claim cites
two kinds of evidence (`E####` plus sealed, replicated, or verified).

## 4. Figures
By `task_type`: classification — ROC, PR, reliability, score histogram by class,
decile lift, confusion at best threshold; regression — predicted-vs-actual, residuals,
QQ; scalar/simulation — the breakdown curve and the efficiency-cost bar; estimation —
the estimate with its interval against every reference value; every study — the
decision trajectory per track. Tutorial §⑥ heading: **Method coding advice**.

## 5. Knowledge
`knowledge/research-discipline.md` (the process lessons of studies 07–09) and
`knowledge/domains/<field>/` when a field directory exists.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` |
|---|---|
| sub-second cells (analytic, small tables, exact verifiers) | 60 |
| seconds (sklearn on ≤100k rows, small simulations) | 300 |
| minutes (GBDT sweeps, medium simulations, small nets on CPU) | 1 800 |
| hours (deep nets, large simulations, cluster jobs) | set explicitly; budget in steps or tokens, `wall_seconds` informational |
After the anchor run: `max(3× anchor wall-clock, 60 s)`.

## 7. Vocabulary
Banned: "blind" (a prospective lock is not blindness — say "locked before"), "proved"
(unless a proof artifact is pinned), "significant" without the test and its family
size, "material" / "actionable" without a `materiality:` block. Must be qualified by
the floor: "better", "improves", "beats". Honest verbs: measured, cleared, matched,
refuted, inconclusive.

## 8. CONSULT hints
"Does X predict Y" → `predict`; "how large is" → `estimate`; "is there a difference" →
`test`; "does the method recover" → `simulate`; "does the paper's number reproduce" →
`replicate`; "what is in this data" → `discover`; "find the best" with a checker →
`optimize`. Modality from the data's shape; `none` when there is only a verifier.
