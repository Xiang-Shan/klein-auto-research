# Agent-Smith Skill Optimization Notes

**Scope:** This doc is for the *test-bed* copy of agent-smith inside this repo at `.agents/skills/agent-smith/`. The user is testing improvements here before promoting validated ones to the main skill at `~/.claude/skills/agent-smith/`. **No edits propagate.** This doc is the proposal log.

**Source of evidence:** the 215-experiment campaign on the Kaggle insurance-claims dataset (branch `experiments/model-survey`), conducted Apr 28–30, 2026.

---

## 1. What worked (preserve in any future version)

These are the load-bearing pieces of agent-smith that should not change. They were the reason the campaign produced a coherent, auditable, reproducible result.

1. **Single `results.tsv` as ground truth.** One row per experiment, `experiment / primary_metric / status / commit / description`. Scannable with `tail -10`, grepable, git-commit-able. After 215 rows it's still trivial to read end-to-end.
2. **Phase-boundary checkpoints.** The user-acknowledgement pause at each of 5 phases gave 5 redirect points across the campaign. Without them, the user would have been forced to redirect mid-flight or accept a stale plan.
3. **`keep` / `discard` / `crash` status.** Forces honest accounting per experiment. By Phase 5, 192/215 were discards — the campaign was *mostly* failure, and the status field made that visible without shame.
4. **Memory writes per phase.** Durable insights survive context resets, which we hit twice (compactions). Without phase-boundary memory, the second session would have had to re-read 200+ commits to recover state.
5. **Thin `train.py` + `lib/` package.** Per-experiment diffs were typically 5–15 LOC. A reviewer can grep through commits and see what each experiment actually changed.
6. **"Description" column free-text.** Cheaper than ten new TSV columns. Humans read it later and can grep `tail -50 results.tsv | grep monotone`. The freeform discipline outweighed the rigidity of structured fields.

---

## 2. Pain points found during the campaign

Each pain point is a concrete advice item. Numbered for cross-reference.

### 2.1 Optuna integration is awkward

**Problem.** Each Optuna trial is itself a sub-experiment, but only the study's best trial gets one TSV row. The other 49 trials' params and metrics are lost — only `optuna_studies/<study_id>.tsv` (a side-file we wrote ad-hoc) preserves them.

**Advice.** Extend the schema with an optional `study_id` column, and bake the side-table convention into the skill. `summarize_results.py` learns `--expand-study <id>` to flatten trials inline.

```
# results.tsv
experiment  primary_metric  status  commit  description  study_id
107         0.6680         keep    abc123  XGB Optuna ...  xgb_50tr_fast

# optuna_studies/xgb_50tr_fast.tsv
trial  val_auc  params_json
0      0.6612  {"learning_rate":0.04,...}
...
```

`summarize_results.py --expand-study xgb_50tr_fast` then prints the trial table.

### 2.2 Aux metrics captured but not summarized

**Problem.** Each `run.log` has an `--- aux_metrics ---` block (PR-AUC, Brier, log-loss, lift@10, F1@best). `summarize_results.py` only reports the primary metric. To compare base learners on calibration, we had to grep + awk.

**Advice.** Extend the summarizer with `--aux <name>`:

```bash
$ summarize_results.py results.tsv --aux val_brier --goal lower
# Top-10 by val_brier (primary AUC alongside)
```

And add an "Aux panel" section to `results_summary.md` with top-10 by Brier and top-10 by lift@10. Generated automatically.

### 2.3 Phase budgets were guesses, never auto-corrected

**Problem.** We budgeted Phase 4 at 32h; it finished in ~12h (MPS was faster than expected). Phase 3 budgeted at 24h; finished in ~4h (CPU was enough at 47k rows). No mechanism updates the budget for the next dataset.

**Advice.** Log per-experiment wall-clock to `results.tsv` (already present in aux block, but not promoted to a column). Have `summarize_results.py` compute and print "phase actual / phase budgeted" so the user can recalibrate after 2–3 campaigns. Skill template `program.md` then has empirically-grounded budgets.

### 2.4 No first-class "research questions" tracking

**Problem.** The plan tagged each experiment with which Q it informs (Q1, Q4, Q5, Q8 in Phase 5). Tracking Q→experiments was manual — we used `grep "Phase5-Q1" results.tsv` ad-hoc. The Phase 5 ablation work would have been simpler with this baked in.

**Advice.** Add `research_questions.tsv` (manually maintained):

```
q_id  summary                                   evidence_experiments  status
Q1    Priority of optimization levers           196,197,198,199,200,201   answered
Q4    Do we need feature engineering?           198,210                   answered
Q5    Should we bin numerical features?         211,212                   answered
...
```

A small `link_evidence.py` scans descriptions for `Phase5-Q1` patterns and updates the table. Makes Phase 5 (synthesis) almost mechanical.

### 2.5 No automated cross-family ensemble check

**Problem.** Phase 5 had to manually wire base-learner OOF preds from previous experiments — fit each base learner with 3-fold OOF, save predictions to `npz`, average them, rerun threshold tuning. Repetitive and error-prone (we had to debug an OOF index alignment issue in Exp 152).

**Advice.** Skill-level `references/ensembling-template.py` codifying the pattern: takes a list of `(train.py path, encoder kind, model-class)` triples, fits each with stratified k-fold OOF, saves OOF + val preds, runs soft-vote / stacking / Optuna-weighted variants, and writes the comparison table. Ten experiments collapse to one config file.

### 2.6 Memory schema doesn't track contradiction

**Problem.** Phase 1 wrote `feedback_imbalance_strategy.md` claiming "for ~6% positive, cw=None + isotonic + threshold tuning beats class_weight=balanced." Phase 3 found that `scale_pos_weight` (XGB equivalent of cw=balanced) ALSO failed and added supporting evidence. Phase 4 added the same finding for TabNet. None of these reinforcements modified the original memory file — the original got *more right* over time, but the audit trail didn't show it.

**Advice.** Add `superseded_by:` and `reinforced_by:` frontmatter fields. Or: a `memory/CHANGELOG.md` that logs "Phase 5 reinforced Phase 1 claim X with new evidence in Exp Y." Future Claude sessions can trust the memory more if they can see how it was built up.

### 2.7 Best-model snapshot is implicit

**Problem.** "Exp 151 = 0.6715 deployable" is a claim in the description column; there's no `models/best.pkl`. Anyone reproducing has to re-fit from train.py. The base learners needed for the soft vote (XGB, LGBM, CatBoost) aren't pickled either, so the ensemble has to be reconstituted by hand.

**Advice.** Add `lib/save_best.py` with a hook that joblibs the model when a new global best is recorded:

```python
# in lib/eval.evaluate(...)
if val_metric > read_current_best("val_auc"):
    joblib.dump(model, f"models/best_{exp_id}_{val_metric:.4f}.pkl")
    update_manifest(exp_id, val_metric, model_path)
```

Plus a `models/manifest.tsv` mapping experiment → file → val_auc. Reproduction collapses to `joblib.load(...)`.

### 2.8 No SHAP / explanation snapshot

**Problem.** For insurance, regulators want SHAP plots. We have SHAP on demand but no automatic snapshot per phase. After-the-fact SHAP requires re-fitting the model, which is fast for LGBM but inconvenient.

**Advice.** Phase-end hook in the skill: when a phase boundary fires AND a new global best was recorded, run SHAP on it and dump to `analysis/shap_phase<N>.html`. Cost: ~20s for LGBM, ~60s for FTT. The HTML + summary plot becomes part of the deliverable.

### 2.9 MPS bug detection missed it for 3 experiments

**Problem.** `DataLoader + TensorDataset + MPS` silently produced constant predictions in Exp 178–180. The model trained, the loss decreased, but the val proba collapsed to the mean. AUC=0.5; we thought it was a hyperparameter issue. Cost: 3 experiments and 1h debug.

**Advice.** Sanity fixture in `lib/eval.py`:

```python
def evaluate(model, X_va, y_va, *, min_proba_std=0.01, ...):
    proba = model.predict_proba(X_va)[:, 1]
    if proba.std() < min_proba_std:
        raise RuntimeError(
            f"Predictions collapsed to constant (std={proba.std():.4f}). "
            f"Likely DataLoader+device issue. See docs/insights_and_framework.md §5.4."
        )
    ...
```

Catches it in 5 seconds with a clear error pointing at the cause.

### 2.10 Doctrine pre-registration

**Problem.** The plan declared a "modeling priority doctrine" (model > HPO > FE > FS > encoder) but only Phase 5 ablations validated it. We could have written specific predictions ("expect Model Δ ≈ +0.05, HPO Δ ≈ +0.02") *before* running them, then logged "predicted vs observed" after.

**Advice.** Add a `program.md` template field "Predictions to falsify". Stronger science: a doctrine that survives ablation against pre-registered predictions has more credibility than one that's validated post-hoc.

```markdown
## Predictions to falsify (Phase 5 will check)

| Lever | Predicted ΔAUC | Observed ΔAUC | Verdict |
|---|---|---|---|
| Model selection | +0.05 | +0.045 | confirmed |
| HPO | +0.02 | +0.013 | smaller than expected |
| FE | +0.01 | +0.002 | much smaller |
| Encoder (tree) | ±0.01 | ±0.005 | confirmed (small) |
```

---

## 3. Skill-level vs framework-level (where each lives)

| Concern | Skill-level (smith) | Framework-level (per campaign) |
|---|---|---|
| `results.tsv` schema (incl. `study_id`) | Yes | No |
| Aux metric summarizer | Yes | No |
| `lib/data.py`, `lib/eval.py` patterns | Templates in `references/` | Concrete instances per repo |
| Optuna integration helper | Helper in `references/` | Per-family use per repo |
| Memory schema (incl. `superseded_by`) | Yes | Per-campaign content |
| Doctrine pre-registration | Template field in `program.md` | Filled out per campaign |
| Best-model snapshot hook | Yes (generic) | Per-campaign artifact |
| SHAP snapshot hook | Optional hook | Configured per campaign |
| `min_proba_std` sanity check | Yes (in `lib/eval.py` template) | Inherits |
| `research_questions.tsv` convention | Yes | Filled out per campaign |

**Skill-level (eventual promotion to main):** items 1, 2, 5, 6, 7, 8, 9 above (mechanical; benefit any campaign).
**Framework-level (process changes per campaign):** items 3, 4, 10 (need to be filled out anew each time).

---

## 4. Diff sketches

For the future "promote to main skill" PR, here are 5–10 line sketches per advice item.

### 4.1 (Optuna `study_id`)

```diff
# results.tsv header
-experiment\tprimary_metric\tstatus\tcommit\tdescription
+experiment\tprimary_metric\tstatus\tcommit\tdescription\tstudy_id

# summarize_results.py
+    if args.expand_study:
+        path = Path(f"optuna_studies/{args.expand_study}.tsv")
+        ...
```

### 4.2 (Aux metrics summarizer)

```diff
# summarize_results.py
+    if args.aux:
+        for row in rows:
+            log = read_run_log(row.commit)
+            row.aux = parse_aux_block(log).get(args.aux)
+        print_top10_table(rows, key=lambda r: r.aux, descending=goal == "higher")
```

### 4.3 (Wall-clock columns + budget telemetry)

```diff
# results.tsv header
+...\tfit_seconds\twall_seconds

# summarize_results.py
+def print_phase_budget_telemetry(rows, phase_caps):
+    for phase, cap in phase_caps.items():
+        actual = sum(r.wall_seconds for r in rows_in_phase(rows, phase))
+        print(f"Phase {phase}: actual={actual/3600:.1f}h budget={cap}h ratio={actual/3600/cap:.2f}")
```

### 4.4 (Research questions table)

```diff
# new file: research_questions.tsv
q_id\tsummary\tevidence_experiments\tstatus

# new file: scripts/link_evidence.py
"""Scan results.tsv descriptions for Phase<N>-Q<M> patterns and update research_questions.tsv."""
```

### 4.5 (Ensembling template)

```diff
# new file: .agents/skills/agent-smith/references/ensembling-template.py
"""Generic OOF + soft-vote + stacking + Optuna-weighted ensemble runner.

Usage:
    runner = EnsembleRunner(
        base_learners=[
            ("xgb_ord", make_xgb, "ordinal"),
            ("lgb_ohe_mono", make_lgb, "ohe"),
            ("cat_target", make_cat, "target"),
        ],
        cv=StratifiedKFold(3, shuffle=True, random_state=42),
    )
    runner.fit_oof(X_tr, y_tr)
    runner.predict_val(X_va, y_va)
    runner.report()  # writes phase5_ensemble_report.md
"""
```

### 4.6 (`superseded_by` / CHANGELOG)

```diff
# memory file frontmatter
 ---
 name: ...
 description: ...
 type: feedback
+reinforced_by:
+  - exp_148_xgb_scale_pos_weight  # repeated finding from Phase 3
+  - exp_186_tabnet_focal           # repeated finding from Phase 4
 ---
```

### 4.7 (Best-model snapshot)

```diff
# lib/save_best.py (new)
def maybe_save_best(model, exp_id: int, val_metric: float, *, primary="val_auc"):
    cur = read_current_best(primary)
    if val_metric > cur:
        path = f"models/best_{exp_id}_{val_metric:.4f}.pkl"
        joblib.dump(model, path)
        update_manifest(exp_id, val_metric, path)

# lib/eval.evaluate(...)
+    maybe_save_best(model, exp_id, val_auc)
```

### 4.8 (SHAP snapshot hook)

```diff
# scripts/phase_end.py (new)
"""Run on phase boundary. If a new global best was recorded this phase, dump SHAP."""
def main(phase: int):
    best_row = read_global_best_at_phase_end(phase)
    if best_row.is_new_global_best:
        model = joblib.load(best_row.model_path)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_val_sample(1000))
        shap.summary_plot(shap_values, ..., show=False)
        plt.savefig(f"analysis/shap_phase{phase}.html")
```

### 4.9 (`min_proba_std` sanity)

```diff
# lib/eval.py
 def evaluate(model, X_va, y_va, *, min_proba_std=0.01, ...):
     proba = model.predict_proba(X_va)[:, 1]
+    if proba.std() < min_proba_std:
+        raise RuntimeError(
+            f"Predictions collapsed (std={proba.std():.4f}). "
+            f"Likely DataLoader+MPS issue or model never trained."
+        )
```

### 4.10 (Doctrine pre-registration template)

```diff
# program.md template
+## Predictions to falsify
+| Lever | Predicted ΔAUC | Observed ΔAUC | Verdict |
+|---|---|---|---|
+| ... | ... | (filled in Phase 5) | (filled in Phase 5) |
```

---

## 5. Promotion path

Once test-bed has these patches and 2 more campaigns confirm them, the user can promote selectively to `~/.claude/skills/agent-smith/`. Suggested order:

**Tier 1 (mechanical wins, low risk — promote first):**
- 4.9 `min_proba_std` sanity — strict win, would have saved 3 experiments here
- 4.7 best-model snapshot — every campaign benefits
- 4.5 ensembling template — every weak-signal campaign needs this

**Tier 2 (process changes — promote after 1 more confirming campaign):**
- 4.2 aux metrics summarizer — needs the user's calibration-aware reports
- 4.6 memory `superseded_by` — needs to be exercised before committing to schema
- 4.10 doctrine pre-registration — needs the user's habit to actually fill it in

**Tier 3 (data-dependent — need cross-campaign evidence):**
- 4.1 Optuna `study_id` — the schema decision should match what 2–3 campaigns naturally produce
- 4.3 wall-clock columns + budget telemetry — needs 2–3 campaigns to recalibrate budgets meaningfully
- 4.4 research questions table — pattern needs to repeat to justify the convention
- 4.8 SHAP snapshot hook — only useful in regulated domains; gate behind a config flag

---

## 6. Non-changes

What we explicitly should NOT change. These are the load-bearing pieces.

- **The single TSV ground truth.** Don't split into multiple tables, don't move to JSON Lines, don't add a database. The text + git advantage outweighs everything else.
- **The phase-boundary pause-and-acknowledge cadence.** This was the user's main lever for course-correction. Removing it makes the campaign less steerable.
- **The thin `train.py` + `lib/` split.** The 5–15 LOC per-experiment diff is the reason commits are reviewable and reproducible. Adding more abstraction would hurt.
- **The free-text description column.** Don't replace with structured tags. Humans read free text; LLMs generate it well; grep is sufficient.
- **The keep / discard / crash status.** Three buckets is enough.

---

## 7. Open questions for the user

These are decisions that depend on the user's preferences across future campaigns; not blockers, but worth discussing before promoting Tier 2/3 changes.

1. **Tier of memory persistence.** Is the current memory schema (markdown files with frontmatter, indexed in MEMORY.md) the long-term pattern, or do you want to migrate to something searchable (vector store, sqlite)? This study generated 12 memory files; the next domain might generate 100+.
2. **Granularity of "research questions" tracking.** Should every campaign declare its Q-set up front (per the user's habit here), or should we let it emerge organically? Pre-registration is more disciplined; emergence is more flexible.
3. **Skill-level templates vs per-campaign instantiation.** What level of detail belongs in a skill template vs in the campaign's `lib/`? E.g., should `lib/eval.evaluate()` be templated centrally or copied into each campaign for divergence? This study copied it.

---

## 8. Cross-references

- **Campaign synthesis (numbers):** `docs/best_practices_auto_insurance.md`
- **GBDT recipes:** `docs/gbdt_hyperparameter_guide.md`
- **Encoder × family:** `docs/encoder_comparison.md`
- **Framework-level synthesis (above the per-phase docs):** `docs/insights_and_framework.md`
- **The agent-smith skill itself:** `.agents/skills/agent-smith/SKILL.md` (and references, scripts, assets)

The promotion path lives outside this repo; this doc only asserts what the patches *should* be. Promotion to the user's main skill is a separate, deliberate action.
