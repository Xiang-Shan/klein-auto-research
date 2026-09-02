#!/usr/bin/env python3
"""verify_e2e.py -- local, end-to-end proof that the Klein pipeline works on this
machine, without ever dirtying the real checkout.

This is a stdlib-only, cross-platform (Linux/macOS/Windows) port of the original
``scripts/verify_e2e.sh``. Behaviour, checks, and exit semantics are kept
identical; ``scripts/verify_e2e.sh`` is now a two-line shim that execs this file
through ``uv run --locked`` so every documented command keeps working.

What it does:
  1. Creates a TEMPORARY git worktree (own branch, own .venv) -- never touches
     the real tree's branch or working directory.
  2. Builds an explicit throwaway v1 compatibility fixture (studies/99-e2e),
     writes a minimal sklearn train.py into it, and dogfoods a 3-experiment
     v1 edit -> run -> commit-or-revert -> log loop.
  3. Runs preflight / summarize_results.py / make_figures.py against that
     throwaway study and asserts their outputs.
  4. Re-checks (read-only) that the REAL committed studies/00 artifacts are
     still present and sane -- a cheap regression net.
  5. Tears the worktree + branch back down and asserts the real tree's
     ``git status --porcelain`` is byte-identical to how it started.

Safety discipline (unchanged from the bash original):
  - every mutating filesystem removal is contained inside this invocation's own
    mkdtemp directory (``safe_rmtree``); nothing is ever deleted outside it;
  - a pre-existing branch name is refused, never reused or deleted;
  - the temporary worktree/branch/tempdir are owned by context managers so
    teardown always runs, on success, on a recorded failure, or on an
    unexpected exception;
  - every subprocess call goes through ``subprocess.run`` with an explicit
    argument list (never a shell invoked with an interpolated command string)
    and an explicit timeout;
  - the real tree's ``git status --porcelain`` is compared before and after.

Usage:  uv run --locked python scripts/verify_e2e.py
        (or, equivalently: bash scripts/verify_e2e.sh)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Result records + table rendering (pure; unit tested in test_verify_e2e_py.py)
# ---------------------------------------------------------------------------


class CheckResult(NamedTuple):
    status: str  # "PASS" or "FAIL"
    description: str


def render_line(result: CheckResult) -> str:
    return f"[{result.status}] {result.description}"


def render_summary(results: Sequence[CheckResult]) -> str:
    """Render the final PASS/FAIL table -- identical shape to the bash original."""
    fail_count = sum(1 for r in results if r.status == "FAIL")
    lines = [
        "",
        "==================== verify_e2e summary ====================",
        *(render_line(r) for r in results),
        "==============================================================",
        f"total: PASS={len(results) - fail_count}  FAIL={fail_count}  (of {len(results)} checks)",
        "RESULT: PASS" if fail_count == 0 else "RESULT: FAIL",
    ]
    return "\n".join(lines) + "\n"


def record(results: list[CheckResult], status: str, description: str) -> None:
    result = CheckResult(status, description)
    results.append(result)
    print(render_line(result))


# ---------------------------------------------------------------------------
# Abort handling -- the Python analogue of bash's `set -euo pipefail`: any
# unrecorded command failure aborts the whole run with that command's exit
# code, after teardown, printing whatever was recorded so far.
# ---------------------------------------------------------------------------


class AbortE2E(Exception):
    def __init__(self, exit_code: int, message: str | None = None) -> None:
        super().__init__(message or f"aborted (exit {exit_code})")
        self.exit_code = exit_code
        self.message = message


DEFAULT_TIMEOUT = 60.0


def sh(
    args: Sequence[str | Path],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    check: bool = True,
    capture: bool = False,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one command through subprocess.run with an explicit arg list and
    timeout -- no shell is ever invoked with an interpolated command string.

    ``capture`` pipes stdout/stderr back for parsing; ``quiet`` discards them
    (mirrors the bash ``check()`` helper's ``>/dev/null 2>&1``); the default
    streams to the console (mirrors an unredirected bash command). ``check``
    (default True) raises AbortE2E on a nonzero exit, mirroring `set -e`.
    """
    str_args = [str(a) for a in args]
    kwargs: dict[str, object] = {"cwd": str(cwd), "timeout": timeout, "text": True}
    if env is not None:
        kwargs["env"] = dict(env)
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    elif quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    try:
        result = subprocess.run(str_args, **kwargs)  # type: ignore[call-overload]
    except subprocess.TimeoutExpired as exc:
        raise AbortE2E(124, f"timed out after {timeout}s: {' '.join(str_args)}") from exc
    except OSError as exc:
        raise AbortE2E(2, f"failed to launch: {' '.join(str_args)}: {exc}") from exc
    if check and result.returncode != 0:
        raise AbortE2E(
            result.returncode, f"command failed ({result.returncode}): {' '.join(str_args)}"
        )
    return result


def record_check(
    results: list[CheckResult],
    label: str,
    args: Sequence[str | Path],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """Mirror bash's `check()`: swallow output, PASS iff exit 0, same label
    either way."""
    result = sh(args, cwd=cwd, env=env, timeout=timeout, check=False, quiet=True)
    record(results, "PASS" if result.returncode == 0 else "FAIL", label)


def record_streamed(
    results: list[CheckResult],
    args: Sequence[str | Path],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    label_pass: str,
    label_fail: str,
) -> None:
    """Like record_check, but streams output (visible progress) and uses
    different PASS/FAIL descriptions."""
    result = sh(args, cwd=cwd, env=env, timeout=timeout, check=False)
    record(results, "PASS" if result.returncode == 0 else "FAIL", label_pass if result.returncode == 0 else label_fail)


# ---------------------------------------------------------------------------
# Filesystem containment guard (pure-ish; unit tested)
# ---------------------------------------------------------------------------


def safe_rmtree(path: Path, *, containment_root: Path) -> None:
    """Remove ``path`` recursively, but refuse (raise ValueError) unless it is
    ``containment_root`` itself or strictly nested inside it.

    This is the Python analogue of the bash teardown's
    ``case "$WORKTREE_DIR" in "$BASE_TMP"/*) rm -rf -- "$WORKTREE_DIR" ;; esac``
    guard: a `rm -rf` is only ever issued inside the script's own mktemp dir.
    """
    resolved = path.resolve()
    root = containment_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"refusing to remove {resolved}: outside containment root {root}")
    shutil.rmtree(resolved, ignore_errors=True)


# ---------------------------------------------------------------------------
# Branch-name safety (refuse pre-existing / invalid branch names)
# ---------------------------------------------------------------------------


def check_branch_available(repo_root: Path, branch_name: str, *, timeout: float = 15.0) -> None:
    """Raise AbortE2E(2, ...) if branch_name already exists or is not a valid
    git ref name -- never reused, never deleted."""
    exists = sh(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        cwd=repo_root,
        timeout=timeout,
        check=False,
        quiet=True,
    )
    if exists.returncode == 0:
        msg = f"ERROR: refusing to reuse or delete pre-existing branch: {branch_name}"
        print(msg, file=sys.stderr)
        raise AbortE2E(2, msg)
    valid = sh(
        ["git", "check-ref-format", "--branch", branch_name],
        cwd=repo_root,
        timeout=timeout,
        check=False,
        quiet=True,
    )
    if valid.returncode != 0:
        msg = f"ERROR: invalid temporary branch name: {branch_name}"
        print(msg, file=sys.stderr)
        raise AbortE2E(2, msg)


# ---------------------------------------------------------------------------
# Temporary worktree lifecycle (context manager: teardown always runs)
# ---------------------------------------------------------------------------


@dataclass
class TeardownState:
    repo_root: Path
    base_tmp: Path | None = None
    base_tmp_created: bool = False
    worktree_dir: Path | None = None
    worktree_created: bool = False
    branch_name: str | None = None
    branch_created: bool = False

    def teardown(self) -> None:
        """Idempotent -- mirrors bash's teardown_worktree(), safe to call more
        than once (explicitly, and again via the outer context manager)."""
        if self.worktree_created and self.worktree_dir is not None:
            removed = (
                sh(
                    ["git", "worktree", "remove", "--force", str(self.worktree_dir)],
                    cwd=self.repo_root,
                    timeout=60.0,
                    check=False,
                    quiet=True,
                ).returncode
                == 0
            )
            if not removed and self.base_tmp is not None:
                try:
                    safe_rmtree(self.worktree_dir, containment_root=self.base_tmp)
                except ValueError:
                    pass  # not contained -- refuse silently, same as the bash case-guard
            self.worktree_created = False
        sh(
            ["git", "worktree", "prune"],
            cwd=self.repo_root,
            timeout=30.0,
            check=False,
            quiet=True,
        )
        if self.branch_created and self.branch_name is not None:
            sh(
                ["git", "branch", "-D", "--", self.branch_name],
                cwd=self.repo_root,
                timeout=30.0,
                check=False,
                quiet=True,
            )
            still_exists = (
                sh(
                    ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{self.branch_name}"],
                    cwd=self.repo_root,
                    timeout=15.0,
                    check=False,
                    quiet=True,
                ).returncode
                == 0
            )
            if not still_exists:
                self.branch_created = False
        if self.base_tmp_created and self.base_tmp is not None:
            shutil.rmtree(self.base_tmp, ignore_errors=True)
            self.base_tmp_created = False


@contextmanager
def temp_worktree(
    repo_root: Path, tmp_parent: Path, branch_name_override: str | None
) -> Iterator[TeardownState]:
    """Create a throwaway git worktree on a throwaway branch inside a throwaway
    mkdtemp directory, and guarantee teardown on the way out -- success, a
    recorded failure, or an unexpected exception all take this path."""
    state = TeardownState(repo_root=repo_root)
    tmp_parent.mkdir(parents=True, exist_ok=True)
    state.base_tmp = Path(tempfile.mkdtemp(prefix="klein-e2e.", dir=str(tmp_parent)))
    state.base_tmp_created = True
    try:
        branch_suffix = state.base_tmp.name.rsplit(".", 1)[-1]
        state.branch_name = branch_name_override or f"e2e-smoke-{branch_suffix}"
        state.worktree_dir = state.base_tmp / "klein-e2e-worktree"

        check_branch_available(repo_root, state.branch_name)

        print(f"=== creating worktree {state.worktree_dir} on branch {state.branch_name} ===")
        sh(["git", "branch", state.branch_name, "HEAD"], cwd=repo_root, timeout=30.0)
        state.branch_created = True
        sh(
            ["git", "worktree", "add", str(state.worktree_dir), state.branch_name],
            cwd=repo_root,
            timeout=120.0,
            capture=True,
        )
        state.worktree_created = True

        yield state
    finally:
        state.teardown()


# ---------------------------------------------------------------------------
# results.tsv row validation (pure; mirrors the awk VALIDATE block)
# ---------------------------------------------------------------------------

_EXP_RE = re.compile(r"^[0-9]+$")
_STATUS_RE = re.compile(r"^(keep|discard|crash)$")
_METRIC_RE = re.compile(r"^-?[0-9.]+([eE][-+]?[0-9]+)?$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


def validate_results_row(fields: Sequence[str]) -> tuple[bool, str]:
    """Validate one results.tsv row (experiment, primary_metric, status,
    commit, description). Returns (ok, rendered "OK: ..."/"ERROR: ..." line)."""
    raw = "\t".join(fields)
    if len(fields) != 5:
        return False, f"ERROR: {raw}"
    exp, metric, status, commit, _desc = fields
    ok = True
    if not _EXP_RE.match(exp):
        ok = False
    if not _STATUS_RE.match(status):
        ok = False
    if status == "crash":
        if metric != "NA":
            ok = False
    elif not _METRIC_RE.match(metric):
        ok = False
    if commit != "-" and not _COMMIT_RE.match(commit):
        ok = False
    return ok, f"{'OK' if ok else 'ERROR'}: {raw}"


# ---------------------------------------------------------------------------
# Section 2: the throwaway v1 compatibility fixture (studies/99-e2e)
# ---------------------------------------------------------------------------

_NOTE_TXT = (
    "synthetic in-memory data (sklearn make_classification) -- no prepared file\n"
    "needed; this marker only satisfies preflight's prepared-data directory check.\n"
)

_STUDY_YAML = """\
goal: "exercise the legacy five-column study pipeline end to end"
domain: "general"
target: "synthetic"
metric:
  name: "val_auc"
  goal: "higher"
family: "sklearn"
data:
  source: "synthetic:make_classification"
  path: "data/prepared"
  split:
    kind: "stratified"
    seed: 42
    test_size: 0.2
    stratify: true
phases:
  - id: 0
    desc: "legacy compatibility smoke"
    min_experiments: 3
    max_experiments: 3
    experiments: {min: 1, max: 3}
    budget_h: 1
deliverables:
  - findings.md
  - report/index.html
"""

_RESEARCH_PLAN_MD = """\
# E2E v1 compatibility plan

Run three deterministic logistic-regression candidates on one fixed synthetic
split, retain honest keep/discard status, and exercise the legacy helper scripts.
"""

_PROGRAM_MD = """\
# E2E v1 compatibility notebook

This fixture intentionally omits `schema_version`, which means v1. It verifies
that v0.2 keeps the five-column legacy evidence path readable without rewriting it.
"""

_DATA_CARD_MD = """\
# Data card

Synthetic, seeded binary classification data. Gate decision: GO for smoke testing.
"""

_METHOD_CARD_MD = """\
# Method card

Logistic regression is the familiar deterministic baseline for this smoke test.
"""

_PREPARE_PY = '''\
"""The E2E fixture generates data in memory; preparation is an explicit no-op."""

from pathlib import Path


def main() -> None:
    Path("data/prepared").mkdir(parents=True, exist_ok=True)
    print("status: ok (synthetic data generated in train.py)")


if __name__ == "__main__":
    main()
'''

_TRAIN_PY = '''\
"""train.py -- throwaway e2e smoke-test study (99-e2e).

Dogfoods the real Klein loop: sklearn make_classification -> kleinlib.data.fixed_split
-> LogisticRegression -> kleinlib.eval.evaluate. EXPERIMENT_ID comes from the EXP_ID env
var (verify_e2e's mini-loop bumps it per run); MODEL_C is the one hyperparameter the
loop edits directly, matching the "5-15 line diff" mutable-surface contract.
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
'''

_RESULTS_TSV_HEADER = "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
_AUX_METRICS_TSV_HEADER = "experiment\tmetric\tvalue\n"

_GIT_AUTHOR_ARGS = ["-c", "user.name=Klein E2E", "-c", "user.email=klein-e2e@local"]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_fixture(worktree_dir: Path, results: list[CheckResult]) -> Path:
    """Write the throwaway studies/99-e2e fixture and commit the baseline."""
    print("=== creating explicit v1 compatibility fixture studies/99-e2e ===")
    study_dir = worktree_dir / "studies" / "99-e2e"

    _write_text(study_dir / "data" / "prepared" / "NOTE.txt", _NOTE_TXT)
    _write_text(study_dir / "study.yaml", _STUDY_YAML)
    _write_text(study_dir / "research_plan.md", _RESEARCH_PLAN_MD)
    _write_text(study_dir / "program.md", _PROGRAM_MD)
    _write_text(study_dir / "data_card.md", _DATA_CARD_MD)
    _write_text(study_dir / "method_card.md", _METHOD_CARD_MD)
    _write_text(study_dir / "prepare.py", _PREPARE_PY)
    _write_text(study_dir / "results.tsv", _RESULTS_TSV_HEADER)
    _write_text(study_dir / "aux_metrics.tsv", _AUX_METRICS_TSV_HEADER)
    _write_text(study_dir / "train.py", _TRAIN_PY)

    record_check(
        results,
        "studies/99-e2e/train.py compiles",
        ["uv", "run", "--locked", "python", "-m", "py_compile", "studies/99-e2e/train.py"],
        cwd=worktree_dir,
        timeout=120.0,
    )

    # The loop contract expects a clean tree (results.tsv exempted) BEFORE the
    # loop starts -- in a real study that's satisfied by committing the
    # CONSULT/DATA/METHOD gate outputs; fast-path that here with one baseline
    # commit of the whole fixture (data/ is gitignored, so the prepared-data
    # marker above is correctly excluded).
    sh(["git", "add", "studies/99-e2e"], cwd=worktree_dir, timeout=30.0)
    sh(
        ["git", *_GIT_AUTHOR_ARGS, "commit", "-q", "-m", "fixture studies/99-e2e (legacy e2e baseline)"],
        cwd=worktree_dir,
        timeout=30.0,
    )
    return study_dir


# ---------------------------------------------------------------------------
# Section 3: the 3-experiment mini-loop
# ---------------------------------------------------------------------------

_MODEL_C_RE = re.compile(r"^MODEL_C = .*?$", re.MULTILINE)


def _set_model_c(train_py: Path, c_val: str) -> None:
    text = train_py.read_text(encoding="utf-8")
    updated, count = _MODEL_C_RE.subn(f"MODEL_C = {c_val}", text)
    if count != 1:
        raise AbortE2E(1, f"expected one MODEL_C assignment, found {count}")
    train_py.write_text(updated, encoding="utf-8", newline="\n")


def run_mini_loop(
    worktree_dir: Path, study_dir: Path, results: list[CheckResult]
) -> None:
    run_timeout = os.environ.get("KLEIN_E2E_RUN_TIMEOUT_SECONDS", "120")
    run_with_log = worktree_dir / "scripts" / "run_with_log.py"
    train_py = study_dir / "train.py"
    results_tsv = study_dir / "results.tsv"

    base_env = dict(os.environ)
    base_env["MPLBACKEND"] = "Agg"

    # Empty string, like bash's `BEST_METRIC=""` -- awk's numeric context
    # coerces an empty comparand to 0, so a crashed experiment 1 (which never
    # sets best_metric) still lets later experiments compare gracefully
    # instead of crashing the whole script.
    best_metric = ""
    for exp_n, c_val in enumerate(("0.1", "1.0", "10.0"), start=1):
        _set_model_c(train_py, c_val)

        print(f"\n=== mini-loop experiment {exp_n} (MODEL_C={c_val}) ===")
        run_env = dict(base_env)
        run_env["EXP_ID"] = str(exp_n)
        run_result = sh(
            [
                "uv", "run", "--locked", "python", str(run_with_log),
                "--timeout-seconds", run_timeout,
                "--log", "run.log",
                "--",
                "uv", "run", "--locked", "python", "-u", "train.py",
            ],
            cwd=study_dir,
            env=run_env,
            timeout=float(run_timeout) + 120.0,
            check=False,
        )

        log_path = study_dir / "run.log"
        log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        metric_match = re.search(r"(?m)^primary_metric:\s*(\S+)", log_text)
        metric = metric_match.group(1) if metric_match else ""

        if run_result.returncode != 0 or not metric:
            metric = "NA"
            status = "crash"
        elif exp_n == 1:
            status = "keep"
        elif float(metric) > (float(best_metric) if best_metric else 0.0):
            status = "keep"
        else:
            status = "discard"

        if status == "keep":
            sh(["git", "add", "train.py"], cwd=study_dir, timeout=30.0)
            sh(
                ["git", *_GIT_AUTHOR_ARGS, "commit", "-q", "-m", f"exp {exp_n}: MODEL_C={c_val} smoke"],
                cwd=study_dir,
                timeout=30.0,
            )
            commit = sh(
                ["git", "rev-parse", "--short", "HEAD"], cwd=study_dir, timeout=15.0, capture=True
            ).stdout.strip()
            best_metric = metric
        else:
            sh(["git", "checkout", "--", "train.py"], cwd=study_dir, timeout=30.0)
            commit = "-"

        description = f"e2e smoke: sklearn LR C={c_val} (exp {exp_n})"
        row = [str(exp_n), metric, status, commit, description]
        with results_tsv.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\t".join(row) + "\n")

        ok, rendered = validate_results_row(row)
        if ok:
            record(results, "PASS", f"exp {exp_n} results.tsv row valid (status={status} metric={metric})")
        else:
            record(results, "FAIL", f"exp {exp_n} results.tsv row INVALID: {rendered}")

    # kleinlib.eval.evaluate() writes aux_metrics.tsv + models/manifest.tsv on
    # every run (not just the ONE results.tsv row the loop contract
    # commits-or-reverts per experiment); the loop contract's clean-tree
    # expectation only exempts results.tsv (by design -- it targets the state
    # BEFORE experiment 1). Fast-path the natural phase-boundary checkpoint here.
    sh(
        ["git", "add", "studies/99-e2e/aux_metrics.tsv", "studies/99-e2e/models"],
        cwd=worktree_dir,
        timeout=30.0,
    )
    sh(
        [
            "git", *_GIT_AUTHOR_ARGS, "commit", "-q", "-m",
            "phase checkpoint: aux_metrics.tsv + models/ after the 3-exp mini-loop",
        ],
        cwd=worktree_dir,
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# Section 4: preflight / summarize_results.py / make_figures.py
# ---------------------------------------------------------------------------


def run_preflight_and_figures(
    worktree_dir: Path, study_dir: Path, results: list[CheckResult]
) -> None:
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"

    print("\n=== preflight --study studies/99-e2e ===")
    record_streamed(
        results,
        ["uv", "run", "--locked", "klein", "preflight", "--study", "studies/99-e2e"],
        cwd=worktree_dir,
        env=env,
        timeout=180.0,
        label_pass="preflight --study studies/99-e2e: 0 fails",
        label_fail="preflight --study studies/99-e2e: reported failing checks",
    )

    print("\n=== summarize_results.py studies/99-e2e/results.tsv ===")
    sh(
        [
            "uv", "run", "--locked", "python",
            ".claude/skills/klein/scripts/summarize_results.py",
            "studies/99-e2e/results.tsv",
        ],
        cwd=worktree_dir,
        env=env,
        timeout=120.0,
    )
    summary_md = study_dir / "results_summary.md"
    progress_svg = study_dir / "progress.svg"
    record(
        results,
        "PASS" if _nonempty(summary_md) else "FAIL",
        "results_summary.md produced",
    )
    record(
        results,
        "PASS" if _nonempty(progress_svg) else "FAIL",
        "progress.svg produced",
    )
    summary_text = summary_md.read_text(encoding="utf-8") if summary_md.exists() else ""
    if "## Aux Panels" in summary_text:
        record(results, "PASS", "results_summary.md contains an Aux Panels section")
    else:
        record(results, "FAIL", "results_summary.md missing an Aux Panels section")

    print("\n=== make_figures.py studies/99-e2e ===")
    sh(
        [
            "uv", "run", "--locked", "python",
            ".claude/skills/klein/scripts/make_figures.py",
            "studies/99-e2e",
        ],
        cwd=worktree_dir,
        env=env,
        timeout=120.0,
    )
    trajectory_png = study_dir / "figures" / "plot_metric_trajectory.png"
    record(
        results,
        "PASS" if _nonempty(trajectory_png) else "FAIL",
        "metric-trajectory PNG produced",
    )

    manifest_tsv = study_dir / "models" / "manifest.tsv"
    manifest_rows = 0
    if manifest_tsv.exists():
        lines = manifest_tsv.read_text(encoding="utf-8").splitlines()[1:]
        manifest_rows = sum(1 for line in lines if line.strip())
    if manifest_rows >= 1:
        record(results, "PASS", f"models/manifest.tsv has >=1 data row ({manifest_rows})")
    else:
        record(results, "FAIL", "models/manifest.tsv has no data rows")

    aux_tsv = study_dir / "aux_metrics.tsv"
    seen_experiments: set[str] = set()
    if aux_tsv.exists():
        for line in aux_tsv.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip():
                continue
            first_field = line.split("\t", 1)[0]
            seen_experiments.add(first_field)
    missing = [str(e) for e in (1, 2, 3) if str(e) not in seen_experiments]
    if not missing:
        record(results, "PASS", "aux_metrics.tsv has rows for experiments 1, 2, 3")
    else:
        record(
            results,
            "FAIL",
            "aux_metrics.tsv missing rows for experiment(s): " + " ".join(missing),
        )


def _nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Section 5: read-only regression net against the REAL committed studies/00
# ---------------------------------------------------------------------------

_EXTERNAL_URL_RE = re.compile(r'src="https?://|href="https?://')


def regression_check_real_study00(repo_root: Path, results: list[CheckResult]) -> None:
    print("\n=== regression check: committed studies/00 artifacts (read-only) ===")
    real00 = repo_root / "studies" / "00-glm-claims-quickstart"

    results_tsv = real00 / "results.tsv"
    real_rows = 0
    if results_tsv.exists():
        lines = results_tsv.read_text(encoding="utf-8").splitlines()[1:]
        real_rows = sum(1 for line in lines if line.strip())
    if real_rows >= 4:
        record(results, "PASS", f"committed studies/00 results.tsv has >=4 rows ({real_rows})")
    else:
        record(results, "FAIL", f"committed studies/00 results.tsv has <4 rows ({real_rows})")

    record(
        results,
        "PASS" if _nonempty(real00 / "results_summary.md") else "FAIL",
        "committed studies/00 results_summary.md non-empty",
    )
    record(
        results,
        "PASS" if _nonempty(real00 / "progress.svg") else "FAIL",
        "committed studies/00 progress.svg non-empty",
    )

    figures_dir = real00 / "figures"
    pngs = sorted(figures_dir.glob("*.png")) if figures_dir.is_dir() else []
    missing_pngs = [png.name for png in pngs if not _nonempty(png)]
    if not missing_pngs:
        record(results, "PASS", "committed studies/00 figures/*.png all present and non-empty")
    else:
        record(
            results,
            "FAIL",
            "committed studies/00 figures/*.png missing/empty: " + " ".join(missing_pngs),
        )

    tutorial = real00 / "report" / "index.html"
    tutorial_ok = _nonempty(tutorial)
    if tutorial_ok:
        html = tutorial.read_text(encoding="utf-8", errors="replace")
        tutorial_ok = "data:image/png;base64" in html and not _EXTERNAL_URL_RE.search(html)
    if tutorial_ok:
        record(results, "PASS", "committed studies/00 report/index.html self-contained tutorial")
    else:
        record(
            results,
            "FAIL",
            "committed studies/00 report/index.html missing, figure-less, or references external assets",
        )


# ---------------------------------------------------------------------------
# Section 6: teardown status comparison + leftover checks
# ---------------------------------------------------------------------------

_OWN_ARTIFACT_RE = re.compile(r"99-e2e|e2e-smoke|klein-e2e-worktree")


def compare_status(before: str, after: str, results: list[CheckResult]) -> None:
    if after == before:
        record(results, "PASS", "real tree git status unchanged after the run")
        return
    # This repo may have other agents concurrently committing/writing in the
    # SAME main tree (separately from this script's own throwaway worktree) --
    # an unrelated change landing mid-run is a false positive, not a bug in
    # this script. Only fail if the delta actually mentions something this
    # script itself could have produced.
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    delta_lines = [line for line in after_lines if line not in before_lines]
    delta_lines += [line for line in before_lines if line not in after_lines]
    delta_text = "\n".join(delta_lines)
    if _OWN_ARTIFACT_RE.search(delta_text):
        record(
            results,
            "FAIL",
            f"real tree git status changed in a way traceable to this script: {delta_text}",
        )
    else:
        record(
            results,
            "PASS",
            "real tree git status delta is unrelated concurrent activity, not this script's doing",
        )
        print(
            "NOTE: git status changed during this run (this is a shared tree with other "
            "concurrent agents; the delta below names none of this script's own artifacts):"
        )
        print(delta_text)


def check_no_leftover_worktree(repo_root: Path, worktree_dir: Path, results: list[CheckResult]) -> None:
    # Targeted, not a before/after `git worktree list` diff: other agents may
    # own other worktrees that legitimately change (new commits, lock state)
    # while this runs.
    listing = sh(["git", "worktree", "list"], cwd=repo_root, timeout=30.0, capture=True).stdout
    # git always reports worktree paths with forward slashes, even on
    # Windows -- str(worktree_dir) would render backslashes there and never
    # match, silently turning a real leftover worktree into a false PASS.
    if worktree_dir.exists() or worktree_dir.as_posix() in listing:
        record(results, "FAIL", f"worktree {worktree_dir} was not fully removed")
    else:
        record(results, "PASS", f"no leftover worktree ({worktree_dir} fully removed)")


def check_no_leftover_branch(repo_root: Path, branch_name: str, results: list[CheckResult]) -> None:
    listing = sh(
        ["git", "branch", "--list", branch_name], cwd=repo_root, timeout=30.0, capture=True
    ).stdout.strip()
    if listing:
        record(results, "FAIL", f"branch {branch_name} still exists")
    else:
        record(results, "PASS", f"no leftover branch ({branch_name} removed)")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _git_status_porcelain(repo_root: Path) -> str:
    return sh(["git", "status", "--porcelain"], cwd=repo_root, timeout=30.0, capture=True).stdout


def _run_body(repo_root: Path, results: list[CheckResult]) -> int:
    before_status = _git_status_porcelain(repo_root)

    tmp_parent = Path(
        os.environ.get("KLEIN_E2E_TMP_PARENT") or os.environ.get("TMPDIR") or tempfile.gettempdir()
    )
    branch_override = os.environ.get("KLEIN_E2E_BRANCH_NAME")

    with temp_worktree(repo_root, tmp_parent, branch_override) as state:
        worktree_dir = state.worktree_dir
        assert worktree_dir is not None

        # Test-only fast stop: exercises branch/worktree/temp ownership
        # cleanup without downloading dependencies or running the full smoke
        # study.
        if os.environ.get("KLEIN_E2E_TEST_STOP_AFTER_WORKTREE") == "1":
            return 0

        print("=== uv sync --locked (fresh .venv for the worktree; dev group is default) ===")
        sh(["uv", "sync", "--locked"], cwd=worktree_dir, timeout=600.0)

        study_dir = write_fixture(worktree_dir, results)
        run_mini_loop(worktree_dir, study_dir, results)
        run_preflight_and_figures(worktree_dir, study_dir, results)
        regression_check_real_study00(repo_root, results)

    # `with` block exited -> teardown already ran (git worktree/branch/tempdir).
    after_status = _git_status_porcelain(repo_root)
    compare_status(before_status, after_status, results)
    assert state.worktree_dir is not None and state.branch_name is not None
    check_no_leftover_worktree(repo_root, state.worktree_dir, results)
    check_no_leftover_branch(repo_root, state.branch_name, results)

    print(render_summary(results))
    return sum(1 for r in results if r.status == "FAIL")


def run(repo_root: Path) -> int:
    results: list[CheckResult] = []
    try:
        return _run_body(repo_root, results)
    except AbortE2E as exc:
        print()
        print(f"verify_e2e aborted early (exit {exc.exit_code}) -- partial results:")
        for r in results:
            print(render_line(r))
        return exc.exit_code


def _resolve_repo_root(script_dir: Path) -> Path:
    result = sh(
        ["git", "rev-parse", "--show-toplevel"], cwd=script_dir, timeout=15.0, capture=True, check=False
    )
    if result.returncode != 0:
        raise AbortE2E(1, "not a git checkout (git rev-parse --show-toplevel failed)")
    return Path(result.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    script_dir = Path(__file__).resolve().parent
    try:
        repo_root = _resolve_repo_root(script_dir)
    except AbortE2E as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code

    return run(repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
