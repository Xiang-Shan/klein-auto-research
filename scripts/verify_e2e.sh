#!/usr/bin/env bash
# verify_e2e.sh — local, end-to-end proof that the Klein pipeline works on this
# machine, without ever dirtying the real checkout.
#
# What it does:
#   1. Creates a TEMPORARY git worktree (own branch, own .venv) — never touches
#      the real tree's branch or working directory.
#   2. Scaffolds a throwaway study (studies/99-e2e) via new_study.py, writes a
#      minimal sklearn train.py into it, and dogfoods a real 3-experiment
#      edit -> run -> commit-or-revert -> log loop (SKILL.md Hard Rules).
#   3. Runs preflight / summarize_results.py / make_figures.py against that
#      throwaway study and asserts their outputs.
#   4. Re-checks (read-only) that the REAL committed studies/00 artifacts are
#      still present and sane — a cheap regression net.
#   5. Tears the worktree + branch back down and asserts the real tree's
#      `git status --porcelain` is byte-identical to how it started.
#
# Written for macOS's stock /bin/bash (3.2): no associative arrays, no `+=`,
# no `mapfile`, no `${var,,}` — so it runs on a stock macOS shell unmodified.
#
# Usage:  bash scripts/verify_e2e.sh
#
set -euo pipefail

# --------------------------------------------------------------------------
# Paths + state (ALL declared before the trap is installed — with `set -u`,
# the trap must never dereference a variable that might not exist yet).
# --------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

RESULT_LOG=""
CHECK_COUNT=0
FAIL_COUNT=0
MAIN_COMPLETED=0
WORKTREE_DIR=""
BRANCH_NAME=""

BEFORE_STATUS="$(git status --porcelain)"

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

record() {  # record PASS|FAIL "description"
  CHECK_COUNT=$((CHECK_COUNT + 1))
  RESULT_LOG="${RESULT_LOG}[$1] $2"$'\n'
  printf '[%s] %s\n' "$1" "$2"
  if [ "$1" = "FAIL" ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

check() {  # check "description" command args...  (swallows output; PASS iff exit 0)
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    record PASS "$desc"
  else
    record FAIL "$desc"
  fi
}

teardown_worktree() {
  if [ -n "$WORKTREE_DIR" ] && [ -d "$WORKTREE_DIR" ]; then
    git worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1 || rm -rf "$WORKTREE_DIR"
  fi
  git worktree prune >/dev/null 2>&1 || true
  if [ -n "$BRANCH_NAME" ] && git branch --list "$BRANCH_NAME" | grep -q .; then
    git branch -D "$BRANCH_NAME" >/dev/null 2>&1 || true
  fi
}

cleanup_trap() {
  local ec=$?
  cd "$REPO_ROOT" 2>/dev/null || true
  teardown_worktree
  if [ "$MAIN_COMPLETED" -ne 1 ] && [ "$ec" -ne 0 ]; then
    echo ""
    echo "verify_e2e.sh aborted early (exit $ec) -- partial results:"
    printf '%s' "$RESULT_LOG"
  fi
  exit "$ec"
}
trap cleanup_trap EXIT

# --------------------------------------------------------------------------
# 1. Temporary worktree
# --------------------------------------------------------------------------

BRANCH_NAME="e2e-smoke-$$"
BASE_TMP="$(mktemp -d)"
WORKTREE_DIR="$BASE_TMP/klein-e2e-worktree"

echo "=== creating worktree $WORKTREE_DIR on branch $BRANCH_NAME ==="
git worktree add "$WORKTREE_DIR" -b "$BRANCH_NAME" >/dev/null
cd "$WORKTREE_DIR"

echo "=== uv sync --extra dev (fresh .venv for the worktree) ==="
uv sync --extra dev

# --------------------------------------------------------------------------
# 2. Scaffold the throwaway study + a minimal train.py
# --------------------------------------------------------------------------

echo "=== scaffolding studies/99-e2e ==="
uv run python .claude/skills/klein/scripts/new_study.py 99-e2e \
  --goal "smoke-test the full Klein loop end to end (scaffold, run, log, preflight, summarize, figures)" \
  --domain general --metric val_auc --goal-direction higher \
  --data "synthetic:make_classification"

mkdir -p studies/99-e2e/data/prepared
cat > studies/99-e2e/data/prepared/NOTE.txt <<'EOF'
synthetic in-memory data (sklearn make_classification) -- no prepared file
needed; this marker only satisfies preflight's prepared-data directory check.
EOF

cat > studies/99-e2e/train.py <<'PYEOF'
"""train.py -- throwaway e2e smoke-test study (99-e2e).

Dogfoods the real Klein loop: sklearn make_classification -> kleinlib.data.fixed_split
-> LogisticRegression -> kleinlib.eval.evaluate. EXPERIMENT_ID comes from the EXP_ID env
var (verify_e2e.sh's mini-loop bumps it per run); MODEL_C is the one hyperparameter the
loop edits via sed, matching the "5-15 line diff" mutable-surface contract.
"""

from __future__ import annotations

import os
import time

import pandas as pd
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

import kleinlib

RANDOM_SEED = 42
EXPERIMENT_ID = int(os.environ.get("EXP_ID", "0"))
MODEL_C = 1.0


def load_split():
    X, y = make_classification(
        n_samples=2000, n_features=20, n_informative=8, random_state=RANDOM_SEED,
    )
    X = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
    y = pd.Series(y, name="target")
    return kleinlib.data.fixed_split(X, y)  # seed=42, test_size=0.2, stratified


def build_model() -> LogisticRegression:
    return LogisticRegression(max_iter=1000, C=MODEL_C, random_state=RANDOM_SEED)


def main() -> None:
    t0 = time.time()
    X_tr, X_va, y_tr, y_va = load_split()
    model = build_model()

    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start

    kleinlib.eval.evaluate(
        model, X_va, y_va,
        exp_id=EXPERIMENT_ID,
        t0=t0, fit_seconds=fit_seconds,
        train_n=len(X_tr), val_n=len(X_va),
        metric_name="val_auc", metric_goal="higher",
        study_dir=".",
    )


if __name__ == "__main__":
    main()
PYEOF

check "studies/99-e2e/train.py compiles" uv run python -m py_compile studies/99-e2e/train.py

# preflight requires a clean tree (results.tsv exempted) BEFORE the loop starts — in a
# real study that's satisfied by committing the CONSULT/DATA/METHOD gate outputs;
# fast-path that here with one baseline commit of the whole scaffold (data/ is
# gitignored, so the prepared-data marker above is correctly excluded).
git add studies/99-e2e
git -c user.name="Klein E2E" -c user.email="klein-e2e@local" \
  commit -q -m "scaffold studies/99-e2e (e2e smoke-test baseline)"

# --------------------------------------------------------------------------
# 3. 3-experiment mini-loop: edit (sed) -> run -> commit-or-revert -> log row
# --------------------------------------------------------------------------

cd studies/99-e2e
BEST_METRIC=""
EXP_N=0
for C_VAL in 0.1 1.0 10.0; do
  EXP_N=$((EXP_N + 1))
  sed -i '' "s/^MODEL_C = .*/MODEL_C = ${C_VAL}/" train.py

  echo ""
  echo "=== mini-loop experiment $EXP_N (MODEL_C=$C_VAL) ==="
  EXP_ID="$EXP_N" MPLBACKEND=Agg uv run python train.py 2>&1 | tee run.log

  METRIC=$(awk '/^primary_metric:/{print $2; exit}' run.log)
  if [ -z "$METRIC" ]; then
    METRIC="NA"
    STATUS="crash"
  elif [ "$EXP_N" -eq 1 ]; then
    STATUS="keep"
  elif awk -v a="$METRIC" -v b="$BEST_METRIC" 'BEGIN{exit !(a>b)}'; then
    STATUS="keep"
  else
    STATUS="discard"
  fi

  if [ "$STATUS" = "keep" ]; then
    git add train.py
    git -c user.name="Klein E2E" -c user.email="klein-e2e@local" \
      commit -q -m "exp $EXP_N: MODEL_C=$C_VAL smoke"
    COMMIT="$(git rev-parse --short HEAD)"
    BEST_METRIC="$METRIC"
  else
    git checkout -- train.py
    COMMIT="-"
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' "$EXP_N" "$METRIC" "$STATUS" "$COMMIT" \
    "e2e smoke: sklearn LR C=$C_VAL (exp $EXP_N)" >> results.tsv

  VALIDATE=$(tail -1 results.tsv | awk -F'\t' '{ok=1;
    if($1!~/^[0-9]+$/)ok=0; if($3!~/^(keep|discard|crash)$/)ok=0;
    if($3=="crash"){if($2!="NA")ok=0}else if($2!~/^-?[0-9.]+([eE][-+]?[0-9]+)?$/)ok=0;
    if($4!="-"&&$4!~/^[0-9a-f]{7,40}$/)ok=0;
    print (ok?"OK: ":"ERROR: ")$0}')
  case "$VALIDATE" in
    OK:*) record PASS "exp $EXP_N results.tsv row valid (status=$STATUS metric=$METRIC)" ;;
    *) record FAIL "exp $EXP_N results.tsv row INVALID: $VALIDATE" ;;
  esac
done
cd "$WORKTREE_DIR"

# kleinlib.eval.evaluate() writes aux_metrics.tsv + models/manifest.tsv on every run
# (not just the ONE results.tsv row the loop contract commits-or-reverts per experiment);
# preflight only exempts results.tsv from its tree-clean check (by design — it targets
# the state BEFORE experiment 1). Fast-path the natural phase-boundary checkpoint here.
git add studies/99-e2e/aux_metrics.tsv studies/99-e2e/models
git -c user.name="Klein E2E" -c user.email="klein-e2e@local" \
  commit -q -m "phase checkpoint: aux_metrics.tsv + models/ after the 3-exp mini-loop"

# --------------------------------------------------------------------------
# 4. preflight / summarize / make_figures against the throwaway study
# --------------------------------------------------------------------------

echo ""
echo "=== preflight --study studies/99-e2e ==="
if MPLBACKEND=Agg uv run python .claude/skills/klein/scripts/preflight.py --study studies/99-e2e; then
  record PASS "preflight --study studies/99-e2e: 0 fails"
else
  record FAIL "preflight --study studies/99-e2e: reported failing checks"
fi

echo ""
echo "=== summarize_results.py studies/99-e2e/results.tsv ==="
MPLBACKEND=Agg uv run python .claude/skills/klein/scripts/summarize_results.py studies/99-e2e/results.tsv
check "results_summary.md produced" test -s studies/99-e2e/results_summary.md
check "progress.svg produced" test -s studies/99-e2e/progress.svg
if grep -q "## Aux Panels" studies/99-e2e/results_summary.md 2>/dev/null; then
  record PASS "results_summary.md contains an Aux Panels section"
else
  record FAIL "results_summary.md missing an Aux Panels section"
fi

echo ""
echo "=== make_figures.py studies/99-e2e ==="
MPLBACKEND=Agg uv run python .claude/skills/klein/scripts/make_figures.py studies/99-e2e
check "metric-trajectory PNG produced" test -s studies/99-e2e/figures/plot_metric_trajectory.png

MANIFEST_ROWS=$(tail -n +2 studies/99-e2e/models/manifest.tsv 2>/dev/null | grep -c . || true)
if [ "${MANIFEST_ROWS:-0}" -ge 1 ]; then
  record PASS "models/manifest.tsv has >=1 data row ($MANIFEST_ROWS)"
else
  record FAIL "models/manifest.tsv has no data rows"
fi

MISSING_EXP=""
for e in 1 2 3; do
  if ! awk -F'\t' -v e="$e" 'NR>1 && $1==e {found=1} END{exit !found}' studies/99-e2e/aux_metrics.tsv; then
    MISSING_EXP="$MISSING_EXP $e"
  fi
done
if [ -z "$MISSING_EXP" ]; then
  record PASS "aux_metrics.tsv has rows for experiments 1, 2, 3"
else
  record FAIL "aux_metrics.tsv missing rows for experiment(s):$MISSING_EXP"
fi

# --------------------------------------------------------------------------
# 5. Regression net: the REAL committed studies/00 artifacts (read-only)
# --------------------------------------------------------------------------

echo ""
echo "=== regression check: committed studies/00 artifacts (read-only) ==="
REAL00="$REPO_ROOT/studies/00-glm-claims-quickstart"

REAL_ROWS=$(tail -n +2 "$REAL00/results.tsv" 2>/dev/null | grep -c . || true)
if [ "${REAL_ROWS:-0}" -ge 4 ]; then
  record PASS "committed studies/00 results.tsv has >=4 rows ($REAL_ROWS)"
else
  record FAIL "committed studies/00 results.tsv has <4 rows (${REAL_ROWS:-0})"
fi
check "committed studies/00 results_summary.md non-empty" test -s "$REAL00/results_summary.md"
check "committed studies/00 progress.svg non-empty" test -s "$REAL00/progress.svg"

PNG_MISSING=""
for png in "$REAL00"/figures/*.png; do
  [ -s "$png" ] || PNG_MISSING="$PNG_MISSING $(basename "$png")"
done
if [ -z "$PNG_MISSING" ]; then
  record PASS "committed studies/00 figures/*.png all present and non-empty"
else
  record FAIL "committed studies/00 figures/*.png missing/empty:$PNG_MISSING"
fi

# Tutorial artifact: self-contained (base64 figures inlined, no external asset URLs)
if [ -s "$REAL00/report/index.html" ] \
   && grep -q "data:image/png;base64" "$REAL00/report/index.html" \
   && ! grep -qE 'src="https?://|href="https?://' "$REAL00/report/index.html"; then
  record PASS "committed studies/00 report/index.html self-contained tutorial"
else
  record FAIL "committed studies/00 report/index.html missing, figure-less, or references external assets"
fi

# --------------------------------------------------------------------------
# 6. Tear down the worktree + branch, verify the real tree is untouched
# --------------------------------------------------------------------------

cd "$REPO_ROOT"
teardown_worktree

AFTER_STATUS="$(git status --porcelain)"
if [ "$AFTER_STATUS" = "$BEFORE_STATUS" ]; then
  record PASS "real tree git status unchanged after the run"
else
  # This repo has other agents concurrently committing/writing in the SAME main tree
  # (separately from this script's own throwaway worktree) — an unrelated change
  # landing mid-run is a false positive, not a bug in this script. Only fail if the
  # delta actually mentions something this script itself could have produced.
  STATUS_DELTA=$(diff <(printf '%s\n' "$BEFORE_STATUS") <(printf '%s\n' "$AFTER_STATUS") || true)
  if printf '%s' "$STATUS_DELTA" | grep -qE "99-e2e|e2e-smoke|klein-e2e-worktree"; then
    record FAIL "real tree git status changed in a way traceable to this script: $STATUS_DELTA"
  else
    record PASS "real tree git status delta is unrelated concurrent activity, not this script's doing"
    echo "NOTE: git status changed during this run (this is a shared tree with other concurrent agents; the delta below names none of this script's own artifacts):"
    printf '%s\n' "$STATUS_DELTA"
  fi
fi

# Targeted, not a before/after `git worktree list` diff: other agents may own other
# worktrees that legitimately change (new commits, lock state) while this runs.
if [ -d "$WORKTREE_DIR" ] || git worktree list | grep -qF "$WORKTREE_DIR"; then
  record FAIL "worktree $WORKTREE_DIR was not fully removed"
else
  record PASS "no leftover worktree ($WORKTREE_DIR fully removed)"
fi

if git branch --list "$BRANCH_NAME" | grep -q .; then
  record FAIL "branch $BRANCH_NAME still exists"
else
  record PASS "no leftover branch ($BRANCH_NAME removed)"
fi

# --------------------------------------------------------------------------
# 7. Final summary
# --------------------------------------------------------------------------

echo ""
echo "==================== verify_e2e.sh summary ===================="
printf '%s' "$RESULT_LOG"
echo "=================================================================="
echo "total: PASS=$((CHECK_COUNT - FAIL_COUNT))  FAIL=$FAIL_COUNT  (of $CHECK_COUNT checks)"
if [ "$FAIL_COUNT" -eq 0 ]; then
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL"
fi

MAIN_COMPLETED=1
exit "$FAIL_COUNT"
