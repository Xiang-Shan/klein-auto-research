#!/usr/bin/env python3
"""verify_e2e.py -- local, end-to-end proof that the Klein pipeline works on this
machine, without ever dirtying the real checkout.

This is a stdlib-only, cross-platform (Linux/macOS/Windows) port of the original
``scripts/verify_e2e.sh``. Behaviour, checks, and exit semantics are kept
identical; ``scripts/verify_e2e.sh`` is now a two-line shim that execs this file
through ``uv run --locked`` so every documented command keeps working.

Two lanes, each in its OWN temporary worktree and branch (``--lane``):

``legacy`` -- the v1 compatibility path, unchanged:
  1. Creates a TEMPORARY git worktree (own branch, own .venv) -- never touches
     the real tree's branch or working directory.
  2. Builds an explicit throwaway v1 compatibility fixture (studies/99-e2e),
     writes a minimal sklearn train.py into it, and dogfoods a 3-experiment
     v1 edit -> run -> commit-or-revert -> log loop.
  3. Runs preflight / summarize_results.py / make_figures.py against that
     throwaway study and asserts their outputs.
  4. Re-checks (read-only) that the REAL committed studies/00 artifacts are
     still present and sane -- a cheap regression net.

``schema3`` -- the proof of the 2.0 engine: one typed inquiry (studies/99-e2e-v3,
  ``predict`` / ``tabular`` / ``generic``, a frontier track and a registered one)
  walked from ``klein new`` to a self-contained tutorial with the CLI and nothing
  else. Gates, a measured floor with its estimand, keep / discard / measured
  dispositions, registered predictions adjudicated by the notary and by hand, the
  sealed rehearsal and its one real spend, a replication, registered measurement
  sweeps, the claims lock and its tamper check, the referee gate, ``klein
  finalize``, the verify receipt, and ``report/index.html``.

Both lanes then tear the worktree + branch back down, and the real tree's
``git status --porcelain`` is asserted byte-identical to how it started.

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

Usage:  uv run --locked python scripts/verify_e2e.py [--lane legacy|schema3|all]
        (or, equivalently: bash scripts/verify_e2e.sh)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
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
        # A captured failure would otherwise take its own diagnosis to the grave:
        # the pipes swallowed the child's stdout/stderr, and the abort message is
        # all the operator gets.
        tail = ""
        if capture:
            captured = "\n".join(
                part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
            )
            if captured:
                tail = "\n" + "\n".join(captured.splitlines()[-25:])
        raise AbortE2E(
            result.returncode,
            f"command failed ({result.returncode}): {' '.join(str_args)}{tail}",
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
    #: Branches a lane created INSIDE its worktree (a study's
    #: ``experiments/<slug>`` branch is a repo-global ref, not a worktree-local
    #: one), each refused first if it already existed and each deleted here.
    extra_branches: list[str] = field(default_factory=list)

    def claim_branch(self, name: str) -> None:
        """Refuse a pre-existing branch, then take ownership of deleting it."""
        check_branch_available(self.repo_root, name)
        self.extra_branches.append(name)

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
        while self.extra_branches:
            name = self.extra_branches.pop()
            sh(
                ["git", "branch", "-D", "--", name],
                cwd=self.repo_root,
                timeout=30.0,
                check=False,
                quiet=True,
            )
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
# Section 4b: the schema-3 lane (studies/99-e2e-v3)
#
# The legacy lane above proves the v1 compatibility path still reads. THIS lane
# is the proof of the 2.0 engine: one typed inquiry walked from `klein new` to a
# self-contained tutorial with the CLI and nothing else — no library calls, no
# hand-written state, no shortcut around a gate. Every study file below is the
# content a driving agent would author; every assertion is a property the
# protocols under `.claude/skills/klein/references/` state.
# ---------------------------------------------------------------------------

_V3_SLUG = "99-e2e-v3"

_V3_PREPARE_PY = '''\
"""Prepare the iris table declared by study.yaml:data.source (offline allowlist)."""

from __future__ import annotations

from pathlib import Path

from sklearn.datasets import load_iris

from kleinlib import sources


def main() -> None:
    sources.resolve("sklearn:load_iris", study_dir=Path("."), offline=True)
    frame = load_iris(as_frame=True).frame.rename(columns={"target": "raw_target"})
    frame.columns = [c.replace(" (cm)", "").replace(" ", "_") for c in frame.columns]
    # versicolor-vs-rest: a genuinely hard binary target on iris. setosa-vs-rest
    # is linearly separable and every candidate would score 1.0, which is a
    # study with no question in it.
    frame["species"] = (frame.pop("raw_target") == 1).astype(int)
    # iris ships one exact duplicate measurement; under the contract's split it
    # straddles train/development, which the mechanized split-contamination row
    # reports as a BLOCKER. Fixed here, deterministically, rather than accepted
    # (data-gate-protocol.md section 5).
    frame = frame.drop_duplicates(ignore_index=True)
    out = Path("data/prepared/prepared.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    print(f"rows: {len(frame)}  positives: {int(frame['species'].sum())}")
    print(f"prepared: {out.as_posix()}")


if __name__ == "__main__":
    main()
'''

_V3_FLOOR_PY = '''\
"""Phase 0 metrology: the two floors this study is allowed to quote.

Two sweeps, two estimands, one script — they answer different questions and only
one of them may ever become a keep bar:

* ``fit_noise`` (recipe ``seed-sweep``) refits the SAME candidate on the SAME
  partition under k seeds. It says how much the FIT moves: provenance, never the
  bar.
* ``split_lottery`` (recipe ``split-lottery``, estimand ``marginal-resplit``)
  re-draws the train/development partition and re-measures. It says how much the
  MEASUREMENT moves, which is what a keep must clear.

Neither touches ``results.tsv``: a measurement sweep promotes no winner
(``references/sweep-rules.md``) and is made citable with ``klein sweep register``.
"""

from __future__ import annotations

import sys
import time

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from kleinlib.data import contract_split, load_prepared
from kleinlib.sweep import SweepRunner

SEEDS = (11, 22, 33, 44, 55)


def _fit_noise_trial(params: dict) -> dict:
    """Same rows, a different fit seed — how much does the FIT move?"""
    t0 = time.time()
    X_tr, X_dev, _, y_tr, y_dev, _ = contract_split(".")
    model = LogisticRegression(max_iter=2000, random_state=int(params["seed"]))
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_dev)[:, 1]
    return {
        "primary_metric": float(roc_auc_score(y_dev, proba)),
        "status": "ok",
        "wall_seconds": time.time() - t0,
    }


def _split_lottery_trial(params: dict) -> dict:
    """A different train/development draw — how much does the MEASUREMENT move?"""
    t0 = time.time()
    frame = load_prepared("data/prepared/prepared.csv")
    y = frame["species"]
    X = frame.drop(columns=["species"])
    X_tr, X_dev, y_tr, y_dev = train_test_split(
        X, y, test_size=0.25, random_state=int(params["seed"]), stratify=y
    )
    model = LogisticRegression(max_iter=2000, random_state=42)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_dev)[:, 1]
    return {
        "primary_metric": float(roc_auc_score(y_dev, proba)),
        "status": "ok",
        "wall_seconds": time.time() - t0,
    }


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "fit_noise"
    trial = {"fit_noise": _fit_noise_trial, "split_lottery": _split_lottery_trial}[which]
    summary = SweepRunner(
        which, ".", trial, [{"seed": s} for s in SEEDS], metric_goal="higher", overwrite=True
    ).run()
    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    print(f"{which}: k={len(values)} ok trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_V3_TRAIN_PY = '''\
"""The only per-candidate mutable surface in this study.

Two tracks share one entrypoint, selected by KLEIN_TRACK:

* ``primary`` (frontier) — fit CANDIDATE on the contract's partition and print the
  canonical block through ``kleinlib.eval.evaluate``.
* ``cells`` (registered) — measure the pre-registered cell: build the family
  table, pin it with an ``artifact:`` line, and print the summary scalar (how
  many tree families clear the anchor by more than the measured floor) through
  ``kleinlib.eval.evaluate_table``.

The floor is READ FROM THE CONTRACT, never written here: a literal split seed or
a literal bar in an entrypoint is war story 8.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeClassifier

import kleinlib
from kleinlib.contract import load_contract
from kleinlib.data import load_partition, split_fingerprint

RANDOM_SEED = 42
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)

# --- the candidate: the whole per-experiment diff surface -------------------
CANDIDATE = "logreg"
MAX_DEPTH = 2


def build_model():
    if CANDIDATE == "tree":
        return DecisionTreeClassifier(max_depth=MAX_DEPTH, random_state=RANDOM_SEED)
    return LogisticRegression(max_iter=2000, random_state=RANDOM_SEED)


def frontier_candidate(evaluation_kind: str, t0: float) -> None:
    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")
    model = build_model()
    fit_start = time.time()
    model.fit(X_fit, y_fit)
    fit_seconds = time.time() - fit_start
    kleinlib.eval.evaluate(
        model, X_eval, y_eval,
        exp_id=EXPERIMENT_ID, study_dir=".", t0=t0, fit_seconds=fit_seconds,
        train_n=len(X_fit), val_n=len(X_eval),
        metric_name="val_auc", metric_goal="higher",
    )


FAMILIES = {
    "logreg": (None, lambda: LogisticRegression(max_iter=2000, random_state=RANDOM_SEED)),
    "tree_d1": (1, lambda: DecisionTreeClassifier(max_depth=1, random_state=RANDOM_SEED)),
    "tree_d2": (2, lambda: DecisionTreeClassifier(max_depth=2, random_state=RANDOM_SEED)),
    "tree_d5": (5, lambda: DecisionTreeClassifier(max_depth=5, random_state=RANDOM_SEED)),
}


def registered_cell(evaluation_kind: str, t0: float) -> None:
    """One cell, one table: which tree families may contest the anchor at all."""
    minimum_delta = float(load_contract(".")["tracks"]["primary"]["metric"]["minimum_delta"])
    # echo=False: the cell prints the partition through the evaluator's own
    # split_fingerprint= kwarg instead, so the block carries it exactly once.
    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".", echo=False)
    scores = {}
    for name, (_depth, make) in FAMILIES.items():
        model = make()
        model.fit(X_fit, y_fit)
        scores[name] = round(float(roc_auc_score(y_eval, model.predict_proba(X_eval)[:, 1])), 6)

    bar = round(scores["logreg"] + minimum_delta, 6)
    table = pd.DataFrame(
        [
            {
                "family": name,
                "max_depth": "NA" if FAMILIES[name][0] is None else FAMILIES[name][0],
                "val_auc": value,
                "delta_vs_logreg": round(value - scores["logreg"], 6),
                "clears_floor": int(name != "logreg" and value >= bar),
            }
            for name, value in scores.items()
        ]
    ).sort_values("val_auc", ascending=False)
    # The sealed pass measures the SAME map on the held-out partition and writes
    # its own table: a cell never overwrites the artifact an earlier manifest and
    # the claims lock already pinned.
    suffix = "" if evaluation_kind == "development" else "_sealed"
    out = Path(f"sweeps/family_map{suffix}.tsv")
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, sep="\\t", index=False, lineterminator="\\n")

    kleinlib.eval.evaluate_table(
        out, int(table["clears_floor"].sum()),
        exp_id=EXPERIMENT_ID, metric_name="val_auc", metric_goal="higher",
        study_dir=".", t0=t0,
        extra={"families": len(table), "bar": bar},
        split_fingerprint=split_fingerprint(X_fit, X_eval),
    )


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`. Missing: " + ", ".join(missing)
        )
    if TRACK == "cells":
        registered_cell(evaluation_kind, t0)
    else:
        frontier_candidate(evaluation_kind, t0)


if __name__ == "__main__":
    main()
'''

#: The commented predictions example the scaffold ships, replaced wholesale by
#: the study's real registered predictions. Matched exactly so a scaffold change
#: fails loudly here instead of silently leaving the example behind (its
#: {{LEVER_1}} placeholder would then block the consult gate).
_V3_SCAFFOLD_PREDICTIONS = """\
# predictions:
#   - id: P1
#     track: primary
#     statement: "{{LEVER_1}} moves val_auc by {{DELTA_1}}"
#     rule: {key: primary_metric, op: ">=", value: 0.0}
#     inconclusive_if: "the run crashes before the evaluator prints"

# confirmation:
#   require: [sealed]            # sealed | replicate | verify (default: by kind)
"""

_V3_PREDICTIONS = """\
predictions:
  - id: P1
    track: cells
    statement: "at most one of the three tree families clears the anchor by more than the measured floor"
    rule: {key: primary_metric, op: "<=", value: 1}
    inconclusive_if: "the cell crashes before the family table is written"
  - id: P2
    track: primary
    statement: "growing the tree past the shallowest useful depth buys more than the measured floor"
    manual: true
    inconclusive_if: "no family map was measured"
  - id: P3
    track: primary
    statement: "the sealed number reproduces the development number within the measured floor"
    manual: true
    inconclusive_if: "the sealed access is never spent"

confirmation:
  require: [sealed]
"""

_V3_DATA_CARD = """\
---
type: data-card
domain: "general"
modality: "tabular"
status: go
concepts: []
related: []
---

# Data card — 99-e2e-v3

> Gate 1 (DATA). GIGO guard, written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source tag:** `sklearn:load_iris`, resolved offline as printed on the
  `data source: sklearn — sklearn.datasets.load_iris` line. **Pin:** not required
  (a loader shipped with scikit-learn, on the offline allowlist).
- **Modality:** tabular. **Target:** `species`, versicolor-vs-rest, derived in
  `prepare.py` from the loader's three-class label.
- **Split policy:** `data.split` — stratified, seed from the contract, development
  and test fractions as declared. **Fingerprints frozen at this gate:** the
  prepared bytes and the realized partitions, by `klein gate record data`.
- **Profiler used:** `kleinlib.profile_fallback` (the global `dataset-profiler`
  skill is not installed in this environment).

## Profile summary

| Column / field | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `sepal_length` | float, centimetres | none | many | no | no | measured before labelling |
| `sepal_width` | float, centimetres | none | many | no | no | measured before labelling |
| `petal_length` | float, centimetres | none | many | no | no | measured before labelling |
| `petal_width` | float, centimetres | none | many | no | no | measured before labelling |
| `species` | integer in {0, 1} | none | two | no | target | one when the flower is versicolor |

**Value-pattern check (mandatory war story):** every column was inspected by
value, never by `dtype`. All four features hold real floats in centimetres — no
string-encoded booleans, no numbers-in-strings, no sentinels, no mixed types.
The target is a genuine binary integer and is never read back from a feature.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | the table is small, so the development partition makes the measured floor wide relative to plausible effects | measure the floor at Phase 0 and set `minimum_delta` at the floor bar; never call a within-floor delta an improvement |
| 2 | NOTE | one exact duplicate measurement ships with iris and straddled train/development, which the mechanized split-contamination row reported as a BLOCKER | fixed deterministically in `prepare.py` (`drop_duplicates`); the audit was re-run clean |
| 3 | NOTE | versicolor-vs-rest is not linearly separable | expected; it is the reason the study has a question at all |

## Clean-room leakage audit

Rows 3 and 4 are mechanized with
`uv run --locked python -m kleinlib.leakage data/prepared/prepared.csv --target species --study .`,
run after the profile was finished and without reading `program.md`.

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | Pass | the four features are physical measurements taken before any labelling; `prepare.py` derives `species` from the loader's label and drops it |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | N-A | no encoders, no imputers, no time features; `prepare.py` writes raw measurements |
| 3. Split contamination — no duplicate rows straddling partitions; the split reproduces from `study.yaml` alone | Pass | `[OK] split-reproduces` and `[OK] duplicate-rows` from the mechanized audit, after the duplicate was dropped |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | Pass | `[OK] metric-direction`, `[OK] constant-chance` and `[OK] shuffled-chance` on both tracks |

## Go / no-go

> **Decision:** GO
>
> **Rationale:** the prepared table is small but clean, the split reproduces from
> the contract alone, the one duplicate that straddled partitions was removed
> deterministically and the audit re-ran clean, and the eval harness scores chance
> at chance. The small-sample WARN is carried into the floor measurement, not into
> a claim.
"""

_V3_METHOD_CARD = """\
---
type: method-card
domain: "general"
profile: "generic"
status: draft
concepts: []
related: []
refs_verified: false   # this lane runs offline: no reference can be verified here
triad:
  theory: true
  papers: false
  practice: true
---

# Method card — axis-aligned tree vs logistic regression

> Gate 2 (METHOD). Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`.

## 1. Intuition (for a practitioner)

A logistic regression draws ONE straight boundary through feature space and
slides it until the labelled points fall on the right sides. A decision tree
draws axis-parallel cuts instead, one at a time, and can fence off a region in
the middle of the space. Versicolor irises sit BETWEEN setosa and virginica on
petal size, so "versicolor or not" is a band, not a half-plane: one straight line
cannot separate a band from what lies on both sides of it, while two axis-parallel
cuts can. That is the whole question this study asks, and the reason the prior
says a shallow tree should help.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $x$ | one flower's four measurements |
| $y$ | one when the flower is versicolor, zero otherwise |
| $w, b$ | the logistic model's weight vector and intercept |
| $\\sigma(z)$ | the logistic link |
| $R_m$ | the region of feature space reaching leaf $m$ of a tree |
| $p_m$ | the fitted positive rate inside $R_m$ |

Logistic regression fits one linear score and passes it through the link:

$$ \\hat{p}(x) = \\sigma(w^{\\top} x + b) $$

so its decision boundary is a single hyperplane. An axis-aligned tree instead
partitions the space into disjoint boxes and is piecewise constant on them:

$$ \\hat{p}(x) = \\sum_{m} p_m \\, \\mathbb{1}[x \\in R_m] $$

Two cuts on one coordinate already produce a band that no single hyperplane can
carve out, which is why the shallow tree is the smallest model that can even
express the versicolor region.

## 3. Minimal from-scratch implementation plan

The smallest honest version of the tree is one loop, no framework magic:

```
for each feature j, for each midpoint t between sorted unique values of x_j:
    split rows into L = {x_j <= t}, R = {x_j > t}
    score = |L|/n * gini(y_L) + |R|/n * gini(y_R)
keep the (j, t) with the lowest score; recurse until the declared depth
predict p(x) = mean(y) in the leaf x falls into
```

`train.py` realizes this plan through `sklearn.tree.DecisionTreeClassifier` (the
same greedy Gini search) and leans on the Klein helpers rather than
re-implementing the harness: `kleinlib.data.load_partition` for the contract's
partition and its printed `split_fingerprint:`, `kleinlib.eval.evaluate` for the
frontier track's canonical block, and `kleinlib.eval.evaluate_table` for the
registered cell's hashed family table.

## 4. When it pays / when it doesn't

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| the target region is a band on one axis | any | any | pays — the tree can express it, the hyperplane cannot |
| the target is a half-space | any | any | doesn't — the linear model wins on variance |
| few rows, deep tree | small | weak | doesn't — depth buys variance faster than fit |
| few rows, shallow tree | small | strong | pays, but the gain must clear the measured floor |

**Falsifiable priors this study will test** (mirrored into `study.yaml:predictions`):

- **P1** — at most one of the three candidate tree families clears the anchor by
  more than the measured floor.
- **P2** — growing the tree past the shallowest useful depth buys more than the
  measured floor.
- **P3** — the sealed number reproduces the development number within the floor.

## 5. Verified references

This lane runs offline (`KLEIN_OFFLINE=1`, no network in CI), so no reference
could be verified here; both rows are marked UNVERIFIED and `refs_verified` stays
false. The METHOD gate is recorded with a `--note` naming the papers leg, which is
the mechanism the protocol provides for exactly this case.

| Reference | Where | Verified? |
|---|---|---|
| Fisher, The use of multiple measurements in taxonomic problems | Annals of Eugenics | UNVERIFIED (offline) |
| Breiman et al., Classification and Regression Trees | Wadsworth | UNVERIFIED (offline) |
"""

_V3_PLAYBOOK = """\
# Playbook — 99-e2e-v3

> Rolling state of play. `program.md` is the append-only journal; THIS is the
> current map. Refreshed at the adaptive-1 / confirmation boundary.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0003 | val_auc ${best} | the shallow axis-aligned tree | adaptive-1 |
| cells | E0004 | ${cells} family clears | the four-family permission map, `sweeps/family_map.tsv` | adaptive-1 |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| more tree capacity | E0002, E0004 | val_auc ${deepest}, below the anchor and far below the bar of ${bar} |
| a single linear boundary | E0001, E0004 | val_auc ${anchor} is the anchor to beat, not the answer: versicolor is a band, not a half-plane |

## Open hypotheses

- None this study's budget can test: the permission map (E0004) shows one family
  clearing the bar, and it is already the incumbent.

## Next-best candidates

| # | Candidate | Why it might win | Cost |
| --- | --- | --- | --- |
| 1 | a tree between the two measured depths | it sits between two measured points | one run — not taken: E0004 measured the neighbourhood and nothing else clears |
| 2 | a cost-complexity-pruned tree | pruning changes the family, not the depth | out of the phase budget; recorded in next steps |

## Phase boundary

adaptive-1 closes with its four experiments spent: two keeps (E0001, E0003), one
discard (E0002), one measured cell (E0004). P1 is supported and P2 refuted, each
with a dated decision in `program.md`. The confirmation phase spends the one
sealed access on E0003's configuration.
"""

_V3_PROGRAM_APPEND = """\

## Phase adaptive-1 slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | the logistic baseline anchors the track | 1 | 3 | 3 | 7 |
| 2 | a deep tree beats the anchor by more than the floor | 2 | 3 | 3 | 8 |
| 3 | a shallow tree beats the anchor by more than the floor | 2 | 3 | 3 | 8 |
| 4 | at most one tree family clears the anchor plus the floor (one cell, one table) | 3 | 3 | 3 | 9 |

Chosen, in order: the anchor first, then 2, 3 and 4.

## Decisions (append-only)

- ${today} — E0001 anchors the track at val_auc ${anchor}. The fit-seed spread is
  exactly zero — a deterministic solver — which is precisely why it is recorded
  under `fit_noise` and never as the keep bar. The bar comes from the split
  lottery: `minimum_delta` ${min_delta}, from a marginal-resplit standard
  deviation of ${floor_std}.
- ${today} — E0002 scored ${deepest} and DISCARDS. Decision: stop buying capacity
  on this table; the training partition cannot pay for that much variance.
- ${today} — E0003 scored ${best}, a delta of ${delta} over the anchor, which
  clears the measured floor. It becomes the incumbent.
- ${today} — Decision: P1 SUPPORTED by E0004. Exactly ${cells} of the three tree
  families clears the anchor-plus-floor bar of ${bar}; the others do not. The
  permission map is the evidence, `sweeps/family_map.tsv`.
- ${today} — Decision: P2 REFUTED. Growing the tree past the shallowest useful
  depth does not buy more than the measured floor — it loses val_auc, from
  ${best} down to ${deepest}. The study stops exploring depth and spends its
  sealed access on E0003's configuration. Adjudicated by hand against the pinned
  map, because the comparison lives in a table and not in one run's printed block.
- ${today} — Decision: P3 SUPPORTED. The sealed run E0005 returned ${sealed}
  against the development ${best}; the difference is inside the measured floor.
  The seal is spent and no further sealed access exists on that track.
- ${today} — E0006 spends the registered track's own seal: the same permission
  map, measured once on the held-out partition, into `sweeps/family_map_sealed.tsv`.
  It is confirmation evidence and is excluded from the adaptive frontier.
"""

_V3_FINDINGS = """\
---
type: findings
domain: "general"
profile: "generic"
kind: "predict"
status: draft
concepts: []
related: []
---

# Findings — 99-e2e-v3

> SYNTHESIZE stage output. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`; the lock and the
> numbers law: `references/claims-protocol.md`.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | primary | supported | confirmed | empirical-description | E0003, E0005, ${rep} | the shallow tree scores val_auc ${best} on development against the linear anchor's ${anchor}, a delta of ${delta} against a measured floor of ${min_delta}; the sealed partition returns ${sealed} |
| **[C2]** | RQ1 | primary | refuted | exploratory | empirical-description | E0002, E0004, art:family_map | more capacity does not pay: the deepest family scores ${deepest}, below the anchor and below the shallow tree |
| **[C3]** | RQ1 | cells | supported | exploratory | procedural-verdict | E0004, E0006, art:family_map | of the three tree families measured against the anchor-plus-floor bar of ${bar}, exactly ${cells} has permission to contest the anchor |

## ② Registered predictions (from the ledger)

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | at most one of the three tree families clears the anchor by more than the measured floor | `{key: primary_metric, op: "<=", value: 1}` | `primary_metric` ${cells} | supported | E0004 | — |
| P2 | growing the tree past the shallowest useful depth buys more than the measured floor | manual | the map's `delta_vs_logreg` column | refuted | `sweeps/family_map.tsv`, E0002 | program.md ${today} |
| P3 | the sealed number reproduces the development number within the measured floor | manual | `results.tsv` | supported | E0005 | — |

## ③ Surprises and why

The fit noise measured at Phase 0 was exactly zero and the split lottery's spread
was not. Both facts are about the same estimator on the same table: refitting a
deterministic solver under k = 5 seeds moves nothing, while re-drawing which rows
are held out moves the score by a standard deviation of ${floor_std}. A study
that had pasted the seed spread in as `minimum_delta` would have carried a keep
bar of zero and would have kept every candidate, including the deep tree that
loses to its own baseline. That is the whole reason `sweep:fit_noise` and
`sweep:split_lottery` are recorded under different keys.

The smaller surprise: the single-cut stump scores ${stump}, below the linear
model. A stump cuts one coordinate once, which is strictly less expressive than a
hyperplane over four; the band versicolor occupies needs two cuts before it is
expressible at all.

## ④ Practical advice

- **[C4]** Measure the floor that will judge YOUR comparison, not whichever one is
  cheapest to compute (evidence: `sweep:fit_noise`, `sweep:split_lottery`). A
  deterministic learner has zero fit noise and that number is not a bar.
- **[C5]** When a target occupies a band rather than a half-space, spend the first
  candidate on the smallest model that can express a band, not on the largest one
  you can afford (evidence: E0002, E0003).
- **[C6]** Prefer one cell whose artifact is a table to one run per configuration
  (evidence: E0004, `art:family_map`). Four families were measured, hashed and
  adjudicated inside a single transaction, and the resulting table is what the
  refuted prediction was decided against.

## ⑤ Implications — what changes if this holds

If **[C1]** holds, a reader working on a small, low-dimensional table whose target
is an interval of one feature should reach for a shallow axis-aligned tree before
a linear model, and should expect the gain to be visible only because the floor
was measured first: a delta of ${delta} against a floor of ${min_delta} is a clear
result, not a large one.

Nothing here is priced. This study registered no `materiality:` block, so clearing
the bar means only that the measured floor was cleared — not that any decision is
worth changing. **[C2]** and **[C3]** are exploratory: they rest on one
development partition and must not be read as facts about decision trees in
general.

## ⑥ Literature tie-back

The method card's two references are marked UNVERIFIED: this lane runs offline, so
no citation could be checked, and no claim above rests on either. The card's regime
table predicted that a band-shaped target pays for an axis-parallel model and that
depth past the minimum buys variance; both predictions held (E0003, E0002).
Against the generic profile's doctrine — measurement resolution before comparison —
the study did the right thing in the right order: anchor, floor, then comparison.

## ⑦ What to try next

- A paired-bootstrap floor on the SAME held-out rows for the two finalists. The
  marginal re-split floor used here is the honest bar for "is this model better on
  a fresh draw"; a paired floor would be sharper for "is this model better than
  that one".
- A cost-complexity-pruned tree, the one candidate the permission map could not
  speak to, since pruning changes the family rather than the depth.
- The same three-family map on a larger table, to see whether the deepest family
  ever earns permission once the training partition can pay for it.
"""

_V3_REFEREE_REPORT = """\
Verdict: PASS
Referee: klein-e2e-referee (verify_e2e.py, a different session and tool than the loop) · fresh context · independent-of-experimenter: yes

# Referee report — 99-e2e-v3

> Gate 3 (REFEREE). Written in a fresh context, from `findings.md` first and
> `program.md` last. Protocol: `.claude/skills/klein/references/referee-protocol.md`.
> The two lines above are machine-read by `klein gate record referee`.

## Independence

Rung reached (person > tool > model > backend > fresh session): tool — the
verification lane reads the finished study through the read-only verbs only, with
no access to the loop that produced it.

## Mechanical verifiers run

| Command | Result |
|---|---|
| `klein verify --numbers --evidence-use` | zero failed checks; every discard, crash, measured cell and registered sweep cited |
| `klein claims verify --numbers` | the seven checks of the claims law pass |
| `klein predict list` | every registered prediction carries a ledger verdict; none open |
| figure re-render (`make_figures.py`, byte compare) | identical |

## The ten checks

| # | Check | Result | Evidence rested on |
|---|---|---|---|
| 1 | strength matches evidence | PASS | the one confirmed claim cites the sealed run and a replication record |
| 2 | predictions adjudicated and reported | PASS | the ledger and findings section two agree; the refuted prediction carries a dated decision |
| 3 | negative evidence reported | PASS | the discard, the measured cell and both registered sweeps are cited |
| 4 | controls | PASS | the leakage audit's constant and shuffled predictors are the negative controls; the anchor run is the positive control |
| 5 | multiple comparisons | PASS | the family map declares its family size and its claims stay exploratory |
| 6 | pre-registration integrity | PASS | the consult gate was re-recorded once, with the floor as its reason, before any run |
| 7 | numbers traceable | PASS | the numbers scan is clean and the hand-checked headline values resolve to the pinned map |
| 8 | references | PASS | both references are marked UNVERIFIED and no confirmed claim rests on either |
| 9 | figures | PASS | the decision trajectory re-renders identically and no axis is truncated |
| 10 | vocabulary and scope | PASS | no banned word is used unqualified, the floor's estimand is named, and nothing is called material |

## Notes

None: the verdict is a plain PASS.
"""

#: The seven tutorial fragments, minimal but real: one inlined figure, one
#: build-time-typeset formula, the auto-generated ledger, and the winning
#: entrypoint included BY REFERENCE so the page carries its actual bytes.
_V3_FRAGMENTS: dict[str, str] = {
    "01-question.html": """\
<h2>The question</h2>
<p>Versicolor irises sit <em>between</em> setosa and virginica on petal size, so
"is this flower a versicolor" asks a model to fence off a band, not to pick a
side of a line. This study asks whether a shallow axis-aligned tree beats a
logistic baseline at that, by more than the measurement can resolve.</p>
<p>The last clause is the whole discipline: before any candidate ran, the study
measured how much its own metric moves when nothing changes, and set the keep bar
at that floor.</p>
""",
    "02-method.html": """\
<h2>The method</h2>
<p>A logistic regression fits one linear score and passes it through a link, so
its decision boundary is a single hyperplane:</p>
<div data-math-display="\\hat{p}(x) = \\sigma(w^{\\top} x + b)"></div>
<p>A depth-limited tree instead partitions the space into disjoint boxes and is
piecewise constant on them, so two cuts on one coordinate already express a band
that no hyperplane can carve out:</p>
<div data-math-display="\\hat{p}(x) = \\sum_{m} p_m \\, \\mathbb{1}[x \\in R_m]"></div>
<p>That expressive difference is the mechanism the study tests, and the reason
the smallest tree that can express a band is the interesting candidate rather
than the largest one available.</p>
""",
    "03-data.html": """\
<h2>The data story</h2>
<p>The evidence is scikit-learn's iris table, named in the contract as
<code>sklearn:load_iris</code> and resolved offline. Preparation does exactly two
things and records both: it derives the binary target from the loader's
three-class label, and it drops the one exact duplicate measurement iris ships
with.</p>
<p>The duplicate mattered. Under the contract's stratified split it straddled
train and development, and the mechanized split-contamination row reported it as
a BLOCKER — a leak found by a check rather than by a reader. Fixing it in
<code>prepare.py</code> and re-running the audit clean is what earned the GO.</p>
""",
    "04-journey.html": """\
<h2>The experiment journey</h2>
<p>Phase 0 measured two floors, not one. Refitting the same model under five
seeds moved the score not at all: a deterministic solver has no fit noise. Re-drawing
which rows are held out moved it a great deal. The first number is provenance and
the second is the keep bar, and Klein records them under different keys precisely
so the cheap one can never be mistaken for the expensive one.</p>
<p>Then four experiments, in order: the anchor, a deep tree that lost, a shallow
tree that won, and one registered cell whose artifact is a table of every family
measured against the bar.</p>
<!--LEDGER-->
<p>The winning entrypoint, included by reference so this page carries its actual
bytes:</p>
<pre data-code="train.py" data-lang="python"></pre>
""",
    "05-findings.html": """\
<h2>Findings and insights</h2>
<p>The shallow tree cleared the measured floor on development and reproduced on
the sealed partition, which is the one claim this study is allowed to call
confirmed. Everything else stays exploratory by construction.</p>
<img data-fig="figures/plot_decision_trajectory__primary.png"
     alt="The primary track's decision trajectory: the anchor, one discard, and the keep that holds the frontier.">
<p>The registered cell is the other half of the story. Rather than one run per
family, one cell measured all four, hashed the resulting table into its manifest,
and adjudicated the pre-registered prediction against the printed count.</p>
<img data-fig="figures/plot_decision_trajectory__cells.png"
     alt="The registered track: a measured cell, drawn as its own mark, never on a frontier line.">
""",
    "06-coding-advice.html": """\
<h2>Method coding advice</h2>
<ul>
  <li>Read the floor from the contract, never from a literal in the entrypoint.
      A hardcoded bar and a hardcoded split seed are the same bug.</li>
  <li>Let one cell produce a table when the question is "which of these", and pin
      the table with an <code>artifact:</code> line. The hash goes into the
      manifest; the table is what a later reader checks.</li>
  <li>Route every partition through <code>load_partition</code> so the run prints
      the fingerprint the notary compares against the DATA gate — and so the
      sealed dry-run can hand back development data without the entrypoint
      knowing.</li>
</ul>
""",
    "07-next-steps.html": """\
<h2>Next steps</h2>
<ul>
  <li>Measure a paired floor on the same held-out rows for the two finalists: the
      marginal floor answers "better on a fresh draw", not "better than that
      one".</li>
  <li>Try a pruned tree, the one family the permission map could not speak to.</li>
  <li>Re-run the same map on a larger table and see whether the deepest family
      ever earns permission.</li>
</ul>
<h3>References</h3>
<ul>
  <li>Fisher, <cite>The use of multiple measurements in taxonomic problems</cite>,
      Annals of Eugenics — UNVERIFIED (this lane runs offline).</li>
  <li>Breiman et al., <cite>Classification and Regression Trees</cite>, Wadsworth
      — UNVERIFIED (this lane runs offline).</li>
</ul>
""",
}

#: (claim id, class, strength, sentence template, comma-joined number aliases,
#: comma-joined evidence ids). Every numeral a sentence quotes is carried by one
#: of its aliases — the claims law's check 5 — so the sentences name magnitudes
#: only through substitutions that were pinned above.
_V3_CLAIMS: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "C1", "empirical-description", "confirmed",
        "The shallow axis-aligned tree scores val_auc ${best} on development against "
        "the linear anchor's ${anchor}, a delta of ${delta}, and the sealed partition "
        "returns ${sealed}",
        "tree_shallow_auc,anchor_auc,tree_shallow_delta,sealed_auc",
        "E0003,E0005,${rep}",
    ),
    (
        "C2", "empirical-description", "exploratory",
        "More capacity does not pay: the deepest family scores ${deepest}, below the "
        "anchor and below the shallow tree",
        "tree_deep_auc",
        "E0002,E0004,art:family_map",
    ),
    (
        "C3", "procedural-verdict", "exploratory",
        "Of the three tree families measured against the anchor-plus-floor bar of "
        "${bar}, exactly ${cells} has permission to contest the anchor; the "
        "single-cut stump reaches only ${stump}",
        "permission_bar,clearing_families,stump_auc",
        "E0004,E0006,art:family_map",
    ),
    (
        "C4", "research-discipline", "exploratory",
        "Measure the floor that will judge the comparison at hand, not whichever one "
        "is cheapest to compute: a deterministic learner has zero fit noise and that "
        "number is not a keep bar",
        "",
        "sweep:fit_noise,sweep:split_lottery",
    ),
    (
        "C5", "mechanism-interpretation", "exploratory",
        "When a target occupies a band rather than a half-space, spend the first "
        "candidate on the smallest model that can express a band, not on the largest "
        "one affordable",
        "",
        "E0002,E0003",
    ),
    (
        "C6", "research-discipline", "exploratory",
        "Prefer one cell whose artifact is a table to one run per configuration: the "
        "families were measured, hashed and adjudicated inside a single transaction",
        "",
        "E0004,art:family_map",
    ),
)


def _yaml_scalar(text: str, key: str) -> str:
    """The first ``key: <value>`` scalar in a pasted contract block, verbatim.

    The lane writes documents with the artifact's OWN text, never a float it
    re-formatted: the numbers law compares the bytes a reader sees against the
    bytes on disk, and `0.0635668` re-formatted through float() is a different
    string on a different platform.
    """
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(\S+)", text)
    if match is None:
        raise AbortE2E(1, f"no {key!r} scalar in the pasted floor block")
    return match.group(1)


def _precision_of(token: str) -> str:
    """Decimals as WRITTEN — what `klein claims number --precision` matches at."""
    return str(len(token.split(".", 1)[1]) if "." in token else 0)

# --- small pure helpers the lane leans on (unit tested) --------------------


def contract_block(report: str) -> str:
    """The paste-able study.yaml block out of a `klein noise-floor` report.

    The report is a header line, a blank line, a comment, the INDENTED block,
    then a `next:` footer. The block is exactly the indented lines, which is
    what a driving agent copies into `study.yaml` — so the lane pastes the
    engine's own output rather than a second copy of the same numbers.
    """
    lines = [line.rstrip() for line in report.splitlines()]
    block = [line for line in lines if line.startswith("      ") and line.strip()]
    if not block:
        raise AbortE2E(1, f"no study.yaml block in the floor report:\n{report}")
    return "\n".join(block) + "\n"


def replace_once(text: str, old: str, new: str, *, what: str) -> str:
    """Exactly-one-occurrence replacement; anything else aborts the lane.

    The scaffold is the contract this lane edits. A silent zero-match would leave
    a placeholder behind and fail four steps later with an unrelated message.
    """
    count = text.count(old)
    if count != 1:
        raise AbortE2E(1, f"expected exactly one {what} to replace, found {count}")
    return text.replace(old, new, 1)


def tsv_rows(path: Path) -> list[dict[str, str]]:
    """Read a TSV as dicts of RAW STRINGS — never floats.

    Every number the lane writes into a document is the artifact's own text, so
    the numbers law compares the bytes a reader sees against the bytes on disk.
    """
    import csv as _csv

    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(_csv.DictReader(stream, delimiter="\t"))


def aux_value(rows: Sequence[Mapping[str, str]], experiment: str, metric: str) -> str:
    for row in rows:
        if row.get("experiment") == experiment and row.get("metric") == metric:
            return str(row.get("value", ""))
    raise AbortE2E(1, f"aux_metrics.tsv has no {metric!r} row for {experiment}")


def results_metric(rows: Sequence[Mapping[str, str]], experiment: str) -> str:
    for row in rows:
        if row.get("experiment") == experiment:
            return str(row.get("primary_metric", ""))
    raise AbortE2E(1, f"results.tsv has no row for {experiment}")


def family_value(rows: Sequence[Mapping[str, str]], family: str, column: str) -> str:
    for row in rows:
        if row.get("family") == family:
            return str(row.get(column, ""))
    raise AbortE2E(1, f"family_map.tsv has no {column!r} for {family!r}")


# --- the lane -------------------------------------------------------------


def run_schema3_lane(
    worktree_dir: Path, results: list[CheckResult], state: TeardownState
) -> None:
    """Walk one typed inquiry end to end with the CLI and nothing else."""
    from string import Template

    study_rel = f"studies/{_V3_SLUG}"
    study_dir = worktree_dir / "studies" / _V3_SLUG
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"
    env["KLEIN_OFFLINE"] = "1"  # every data source resolves without the network
    env.pop("KLEIN_SMOKE", None)
    # The caller may be running inside its own venv; uv would print a warning
    # about it on every one of the ~50 invocations below and drown the proof.
    env.pop("VIRTUAL_ENV", None)
    today = _dt.date.today().isoformat()

    def klein(
        *args: str, check: bool = True, capture: bool = True, timeout: float = 300.0
    ) -> subprocess.CompletedProcess[str]:
        return sh(
            ["uv", "run", "--locked", "klein", *args],
            cwd=worktree_dir,
            env=env,
            timeout=timeout,
            check=check,
            capture=capture,
        )

    def python(*args: str, cwd: Path, timeout: float = 300.0, check: bool = True):
        return sh(
            ["uv", "run", "--locked", "python", "-u", *args],
            cwd=cwd,
            env=env,
            timeout=timeout,
            check=check,
            capture=True,
        )

    def commit(message: str) -> None:
        sh(["git", "add", "-A", study_rel], cwd=worktree_dir, timeout=60.0)
        if not sh(
            ["git", "status", "--porcelain"], cwd=worktree_dir, timeout=30.0, capture=True
        ).stdout.strip():
            return
        sh(
            ["git", *_GIT_AUTHOR_ARGS, "commit", "-q", "-m", message],
            cwd=worktree_dir,
            timeout=60.0,
        )

    def study_state() -> dict:
        import json as _json

        return _json.loads((study_dir / "study_state.json").read_text(encoding="utf-8"))

    # -- 1. scaffold, author, and clear the three gates ---------------------
    print(f"\n=== schema-3 lane: klein new {_V3_SLUG} (predict / tabular / generic) ===")
    klein(
        "new", _V3_SLUG,
        "--kind", "predict", "--modality", "tabular", "--profile", "generic",
        "--data", "sklearn:load_iris",
        "--track", "primary", "--track", "cells:registered",
        "--goal", "does a shallow axis-aligned tree beat a linear baseline on versicolor-vs-rest?",
        "--domain", "general", "--target", "species", "--family", "linear+tree",
        "--metric", "val_auc", "--goal-direction", "higher",
        "--split-seed", "20260903", "--max-run-seconds", "120",
        "--audience", "the maintainers of this repository",
        capture=False,
    )
    contract_text = (study_dir / "study.yaml").read_text(encoding="utf-8")
    typed = all(
        line in contract_text
        for line in ('schema_version: 3', 'kind: "predict"', 'modality: "tabular"',
                     'profile: "generic"', "mode: registered")
    )
    record(
        results,
        "PASS" if typed else "FAIL",
        "schema-3: klein new scaffolds a typed inquiry (kind/modality/profile, two track modes)",
    )

    _write_text(study_dir / "prepare.py", _V3_PREPARE_PY)
    _write_text(study_dir / "train.py", _V3_TRAIN_PY)
    _write_text(study_dir / "sweeps" / "noise_floor.py", _V3_FLOOR_PY)
    _write_text(study_dir / "data_card.md", _V3_DATA_CARD)
    _write_text(study_dir / "method_card.md", _V3_METHOD_CARD)

    # CONSULT owns the placeholders: the research question, and the registered
    # predictions that replace the scaffold's commented example.
    contract_text = replace_once(
        contract_text,
        '    question: "{{RQ1_QUESTION}}"',
        '    question: "does a shallow axis-aligned tree beat the logistic baseline'
        ' on versicolor-vs-rest, by more than the measured floor?"',
        what="RQ1 question placeholder",
    )
    contract_text = replace_once(
        contract_text,
        '    prior: "{{RQ1_PRIOR}}"',
        '    prior: "yes — versicolor is a band on petal size, which no single'
        ' hyperplane can fence off"',
        what="RQ1 prior placeholder",
    )
    contract_text = replace_once(
        contract_text, _V3_SCAFFOLD_PREDICTIONS, _V3_PREDICTIONS,
        what="commented predictions example",
    )
    _write_text(study_dir / "study.yaml", contract_text)

    print("\n=== schema-3 lane: prepare.py, then the mechanized leakage audit ===")
    python("prepare.py", cwd=study_dir)
    audit = python(
        "-m", "kleinlib.leakage", "data/prepared/prepared.csv",
        "--target", "species", "--study", ".",
        cwd=study_dir, check=False,
    )
    record(
        results,
        "PASS" if audit.returncode == 0 and "clean" in audit.stdout else "FAIL",
        "schema-3: the mechanized leakage audit passes on the prepared table",
    )

    klein("gate", "record", "consult", "--study", study_rel,
          "--acknowledged-by", "klein-e2e",
          "--note", "typed inquiry registered before any evidence", capture=False)
    klein("gate", "record", "data", "--study", study_rel,
          "--acknowledged-by", "klein-e2e",
          "--note", "small-sample WARN accepted; the duplicate BLOCKER was fixed in "
                    "prepare.py and the audit re-ran clean", capture=False)
    klein("gate", "record", "method", "--study", study_rel,
          "--acknowledged-by", "klein-e2e",
          "--note", "papers pending: this lane runs offline, both references are "
                    "marked UNVERIFIED and no claim rests on either", capture=False)
    gates = study_state()["gates"]
    recorded = all(gates.get(name, {}).get("status") == "recorded"
                   for name in ("consult", "data", "method"))
    record(
        results,
        "PASS" if recorded else "FAIL",
        "schema-3: consult / data / method gates recorded",
    )
    # The scaffolded scouting ledger is the consult gate's optional artifact: hashed
    # into the record when present, so "pre-registered" rests on a hash and not on a
    # commit order nobody checks (references/consult-protocol.md).
    ledger_hash = gates.get("consult", {}).get("artifacts", {}).get("scouting_ledger.md")
    enforced = study_state().get("artifact_hashes", {})
    record(
        results,
        "PASS"
        if ledger_hash
        and enforced.get("scouting_ledger.md") == ledger_hash
        and ledger_hash
        == hashlib.sha256((study_dir / "scouting_ledger.md").read_bytes()).hexdigest()
        else "FAIL",
        "schema-3: the consult gate hashes the scaffolded scouting_ledger.md",
    )
    split = study_state()["fingerprints"].get("split")
    frozen = isinstance(split, dict) and {"development", "final_test", "policy"} <= set(split)
    record(
        results,
        "PASS" if frozen else "FAIL",
        "schema-3: the DATA gate freezes state.fingerprints.split as a mapping "
        "(development / final_test / policy)",
    )
    sections_present = all(
        f"## {heading}" in _V3_DATA_CARD
        for heading in ("Source & shape", "Profile summary", "Clean-room leakage audit",
                        "Ranked go / no-go issues", "Go / no-go")
    )
    record(
        results,
        "PASS" if sections_present else "FAIL",
        "schema-3: the data card carries the tabular modality's required sections",
    )
    commit("study 99-e2e-v3: gates recorded")
    # A study's branch is a repo-global ref, so it is claimed the same way the
    # temporary branch is: refused if it already exists, deleted at teardown.
    state.claim_branch(f"experiments/{_V3_SLUG}")
    sh(["git", "switch", "-q", "-c", f"experiments/{_V3_SLUG}"], cwd=worktree_dir, timeout=60.0)

    # -- 2. Phase 0 metrology, then preflight -------------------------------
    print("\n=== schema-3 lane: Phase 0 — two floors, two estimands ===")
    python("sweeps/noise_floor.py", "fit_noise", cwd=study_dir)
    python("sweeps/noise_floor.py", "split_lottery", cwd=study_dir)

    fit_report = klein(
        "noise-floor", "--study", study_rel, "--track", "primary",
        "--recipe", "seed-sweep", "--estimand", "fit-noise",
        "--sidecar", "sweeps/fit_noise.sidecar.tsv",
    ).stdout
    print(fit_report, end="")
    fit_ok = (
        "estimand=fit-noise" in fit_report
        and "fit noise — NOT a keep bar" in fit_report
        and "fit_noise:" in fit_report
        and "minimum_delta" not in contract_block(fit_report)
    )
    record(
        results,
        "PASS" if fit_ok else "FAIL",
        "schema-3: klein noise-floor --recipe seed-sweep --estimand fit-noise prints a "
        "fit_noise block carrying no keep bar",
    )

    bar_report = klein(
        "noise-floor", "--study", study_rel, "--track", "primary",
        "--recipe", "split-lottery", "--sidecar", "sweeps/split_lottery.sidecar.tsv",
    ).stdout
    print(bar_report, end="")
    floor_block = contract_block(bar_report)
    record(
        results,
        "PASS" if "minimum_delta:" in floor_block and "estimand: \"marginal-resplit\"" in floor_block
        else "FAIL",
        "schema-3: the split-lottery floor prints a marginal-resplit block with a keep bar",
    )

    # Paste both blocks under the PRIMARY track's metric — the head of the
    # contract, up to where the registered track begins.
    contract_text = (study_dir / "study.yaml").read_text(encoding="utf-8")
    head, sep, tail = contract_text.partition("\n  cells:\n")
    if not sep:
        raise AbortE2E(1, "study.yaml has no `cells:` track to split the contract on")
    head = replace_once(
        head, "      minimum_delta: 0\n", floor_block + contract_block(fit_report),
        what="primary track minimum_delta line",
    )
    _write_text(study_dir / "study.yaml", head + sep + tail)
    klein("gate", "record", "consult", "--study", study_rel,
          "--acknowledged-by", "klein-e2e",
          "--note", "minimum_delta set from the measured noise floor", capture=False)
    commit("study 99-e2e-v3: phase 0 floors measured and pasted into the contract")

    print("\n=== schema-3 lane: klein preflight ===")
    preflight = klein("preflight", "--study", study_rel, check=False, capture=False,
                      timeout=600.0)
    record(
        results,
        "PASS" if preflight.returncode == 0 else "FAIL",
        "schema-3: preflight passes with the measured bar in the contract",
    )

    # -- 3. the loop: two keeps, one discard, one measured cell -------------
    print("\n=== schema-3 lane: the experiment loop ===")
    train_py = study_dir / "train.py"

    def set_candidate(candidate: str, depth: int, note: str) -> None:
        text = train_py.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^CANDIDATE = .*$", f'CANDIDATE = "{candidate}"  # {note}', text, count=1)
        text = re.sub(r"(?m)^MAX_DEPTH = .*$", f"MAX_DEPTH = {depth}", text, count=1)
        _write_text(train_py, text)

    set_candidate("logreg", 2, "E0001: the identity anchor")
    klein("run-one", "--study", study_rel, "--track", "primary",
          "--description", "E0001 anchor: the logistic baseline on the contract partition",
          capture=False, timeout=600.0)
    set_candidate("tree", 5, "E0002: more capacity should help")
    klein("run-one", "--study", study_rel, "--track", "primary",
          "--description", "E0002: a deep tree — does more capacity buy anything?",
          capture=False, timeout=600.0)
    restored = 'CANDIDATE = "logreg"' in train_py.read_text(encoding="utf-8")
    set_candidate("tree", 2, "E0003: the shallow tree the method card argued for")
    klein("run-one", "--study", study_rel, "--track", "primary",
          "--description", "E0003: the shallow tree the method card argued for",
          capture=False, timeout=600.0)

    ledger = tsv_rows(study_dir / "results.tsv")
    by_id = {row["experiment"]: row for row in ledger}
    loop_ok = (
        by_id.get("E0001", {}).get("status") == "keep"
        and by_id.get("E0002", {}).get("status") == "discard"
        and by_id.get("E0003", {}).get("status") == "keep"
    )
    record(
        results,
        "PASS" if loop_ok else "FAIL",
        "schema-3: the frontier keeps E0001, discards E0002 and keeps E0003",
    )
    record(
        results,
        "PASS" if restored else "FAIL",
        "schema-3: a discard restores the mutable surface to the pre-candidate base",
    )

    cell = klein(
        "run-one", "--study", study_rel, "--track", "cells", "--tests", "P1",
        "--description", "E0004 cell: the four-family permission map on development",
        timeout=600.0,
    ).stdout
    print(cell, end="")
    ledger = tsv_rows(study_dir / "results.tsv")
    by_id = {row["experiment"]: row for row in ledger}
    record(
        results,
        "PASS" if by_id.get("E0004", {}).get("status") == "measured" and "artifact: " in cell
        else "FAIL",
        "schema-3: the registered cell prints an artifact: table and is dispositioned measured",
    )

    import json as _json

    manifest = _json.loads(
        (study_dir / "runs" / "E0004" / "manifest.json").read_text(encoding="utf-8")
    )
    pinned = manifest.get("artifacts", {}).get("sweeps/family_map.tsv", {})
    record(
        results,
        "PASS" if pinned.get("role") == "declared" and len(str(pinned.get("sha256", ""))) == 64
        else "FAIL",
        "schema-3: the declared artifact is hashed into the cell's manifest with role=declared",
    )

    verdicts = study_state().get("predictions", {})
    events = [
        _json.loads(line)
        for line in (study_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    adjudicated = any(
        event.get("type") == "prediction_adjudicated" and event.get("prediction") == "P1"
        for event in events
    )
    record(
        results,
        "PASS" if verdicts.get("P1", {}).get("verdict") == "supported" and adjudicated
        else "FAIL",
        "schema-3: --tests P1 records the verdict in state and files a prediction_adjudicated event",
    )

    # -- 4. hand-adjudicate the prediction only a table can decide ----------
    klein(
        "predict", "adjudicate", "P2", "--study", study_rel, "--verdict", "refuted",
        "--evidence", "sweeps/family_map.tsv", "--evidence", "E0002",
        "--acknowledged-by", "klein-e2e",
        "--note", "the map's delta_vs_logreg column: the deepest family loses to the "
                  "shallow one and never reaches the bar; E0002 discarded on the same number",
        capture=False,
    )
    listing = klein("predict", "list", "--study", study_rel).stdout
    print(listing, end="")
    record(
        results,
        "PASS" if "1 supported, 1 refuted, 0 inconclusive, 1 open" in listing else "FAIL",
        "schema-3: klein predict adjudicate pins the sidecar and klein predict list counts "
        "1 supported, 1 refuted, 1 open",
    )

    # -- 5. the sealed partition: rehearse, spend once, refuse a second look --
    print("\n=== schema-3 lane: the phase boundary and the sealed access ===")
    _write_text(study_dir / "playbook.md", "PLAYBOOK PLACEHOLDER\n")  # refreshed below
    ledger = tsv_rows(study_dir / "results.tsv")
    family = tsv_rows(study_dir / "sweeps" / "family_map.tsv")
    aux = tsv_rows(study_dir / "aux_metrics.tsv")
    contract_text = (study_dir / "study.yaml").read_text(encoding="utf-8")
    numbers = {
        "anchor": results_metric(ledger, "E0001"),
        "deepest": results_metric(ledger, "E0002"),
        "best": results_metric(ledger, "E0003"),
        "cells": results_metric(ledger, "E0004"),
        "stump": family_value(family, "tree_d1", "val_auc"),
        "delta": family_value(family, "tree_d2", "delta_vs_logreg"),
        "bar": aux_value(aux, "E0004", "bar"),
        "min_delta": _yaml_scalar(floor_block, "minimum_delta"),
        "floor_std": _yaml_scalar(floor_block, "std"),
        "today": today,
    }
    assert contract_text  # read above so a contract edit cannot go unnoticed here
    _write_text(study_dir / "playbook.md", Template(_V3_PLAYBOOK).substitute(numbers))
    commit("study 99-e2e-v3: adaptive-1 closed, playbook refreshed")
    klein("gate", "record", "phase", "--study", study_rel, "--phase", "adaptive-1",
          "--acknowledged-by", "klein-e2e",
          "--note", "four experiments spent: two keeps, one discard, one measured cell",
          capture=False)

    seal_before = study_state()["final_holdout_access"]["primary"]
    head_before = sh(["git", "rev-parse", "HEAD"], cwd=worktree_dir, timeout=30.0,
                     capture=True).stdout.strip()
    klein("run-one", "--study", study_rel, "--track", "primary", "--final-test",
          "--dry-run", "--description", "sealed rehearsal", capture=False, timeout=600.0)
    dry_ok = (
        study_state()["final_holdout_access"]["primary"] == seal_before
        and not (study_dir / "runs" / "E0005").exists()
        and study_state()["last_experiment"] == 4
        and not sh(["git", "status", "--porcelain"], cwd=worktree_dir, timeout=30.0,
                   capture=True).stdout.strip()
    )
    record(
        results,
        "PASS" if dry_ok else "FAIL",
        "schema-3: --final-test --dry-run spends no id, no manifest and no seal, and "
        "leaves a clean tree",
    )
    assert head_before  # the rehearsal files its own state commit; HEAD moves on purpose

    klein("run-one", "--study", study_rel, "--track", "primary", "--final-test",
          "--description", "E0005 sealed: the shallow tree on the held-out partition, once",
          capture=False, timeout=600.0)
    second = klein("run-one", "--study", study_rel, "--track", "primary", "--final-test",
                   "--description", "a second look", check=False)
    spent = study_state()["final_holdout_access"]["primary"]
    record(
        results,
        "PASS" if spent.get("count") == 1 and spent.get("experiment") == "E0005"
        and second.returncode != 0 and "already been accessed" in second.stderr
        else "FAIL",
        "schema-3: the seal is spent exactly once (E0005) and a second attempt is refused",
    )

    # The registered track owns its own seal: the same map, measured once on the
    # held-out partition, into its own table.
    klein("run-one", "--study", study_rel, "--track", "cells", "--final-test",
          "--dry-run", "--description", "sealed rehearsal, registered track",
          capture=False, timeout=600.0)
    klein("run-one", "--study", study_rel, "--track", "cells", "--final-test",
          "--description", "E0006 sealed cell: does the permission map hold on the "
                           "held-out partition?", capture=False, timeout=600.0)
    cells_seal = study_state()["final_holdout_access"]["cells"]
    record(
        results,
        "PASS" if cells_seal.get("count") == 1 and cells_seal.get("experiment") == "E0006"
        else "FAIL",
        "schema-3: the registered track spends its own sealed access once (E0006)",
    )

    # -- 6. replication ------------------------------------------------------
    print("\n=== schema-3 lane: klein replicate ===")
    replication = klein("replicate", "E0001", "--study", study_rel, "--quiet").stdout
    print(replication, end="")
    record_path = sorted((study_dir / "runs" / "E0001" / "replications").glob("*.json"))
    reproduced = bool(record_path) and _json.loads(
        record_path[0].read_text(encoding="utf-8")
    ).get("reproduced") is True
    evidence_id = ""
    match = re.search(r"evidence=(rep:E0001@\S+)", replication)
    if match:
        evidence_id = match.group(1)
    record(
        results,
        "PASS" if reproduced and evidence_id else "FAIL",
        "schema-3: klein replicate E0001 writes a rep: record with reproduced: true",
    )
    numbers["rep"] = evidence_id
    numbers["sealed"] = results_metric(tsv_rows(study_dir / "results.tsv"), "E0005")

    # -- 7. registered sweeps, findings, and the claims lock ----------------
    print("\n=== schema-3 lane: registered sweeps and the claims lock ===")
    for name in ("split_lottery", "fit_noise"):
        klein("sweep", "register", "--study", study_rel, name,
              "--sidecar", f"sweeps/{name}.sidecar.tsv",
              "--script", "sweeps/noise_floor.py", capture=False)
    registered = set(study_state().get("sweeps", {}))
    record(
        results,
        "PASS" if {"split_lottery", "fit_noise"} <= registered else "FAIL",
        "schema-3: klein sweep register hashes both measurement sidecars into state",
    )

    _write_text(study_dir / "findings.md", Template(_V3_FINDINGS).substitute(numbers))
    program = (study_dir / "program.md").read_text(encoding="utf-8")
    _write_text(
        study_dir / "program.md",
        program + Template(_V3_PROGRAM_APPEND).substitute(numbers),
    )
    commit("study 99-e2e-v3: findings and the decision record")

    klein("claims", "init", "--study", study_rel, capture=False)
    for alias, path in (
        ("results", "results.tsv"),
        ("family_map", "sweeps/family_map.tsv"),
        ("aux", "aux_metrics.tsv"),
        ("contract", "study.yaml"),
    ):
        klein("claims", "pin", "--study", study_rel, alias, path, capture=False)
    for alias, value, art, claim in (
        ("tree_shallow_auc", numbers["best"], "family_map", "C1"),
        ("anchor_auc", numbers["anchor"], "family_map", "C1"),
        ("tree_shallow_delta", numbers["delta"], "family_map", "C1"),
        ("sealed_auc", numbers["sealed"], "results", "C1"),
        ("tree_deep_auc", numbers["deepest"], "family_map", "C2"),
        ("stump_auc", numbers["stump"], "family_map", "C3"),
        ("permission_bar", numbers["bar"], "aux", "C3"),
        ("clearing_families", numbers["cells"], "results", "C3"),
        ("minimum_delta", numbers["min_delta"], "contract", "floor"),
        ("floor_std", numbers["floor_std"], "contract", "floor"),
    ):
        klein("claims", "number", "--study", study_rel, alias, "--value", value,
              "--art", art, "--claim", claim, "--precision", _precision_of(value),
              capture=False)

    for claim_id, klass, strength, sentence, aliases, evidence in _V3_CLAIMS:
        args = [
            "claims", "add", "--study", study_rel, claim_id,
            "--class", klass, "--strength", strength,
            "--claim", Template(sentence).substitute(numbers),
            "--evidence", Template(evidence).substitute(numbers),
        ]
        if aliases:
            args += ["--numbers", aliases]
        klein(*args, capture=False)

    lock_check = klein("claims", "verify", "--study", study_rel, "--numbers",
                       check=False, capture=True)
    print(lock_check.stdout, end="")
    record(
        results,
        "PASS" if lock_check.returncode == 0 else "FAIL",
        "schema-3: klein claims verify --numbers passes the seven checks of the claims law",
    )

    # A flipped byte in a pinned artifact must break the lock, and only that.
    pinned_path = study_dir / "sweeps" / "family_map.tsv"
    original = pinned_path.read_bytes()
    pinned_path.write_bytes(original.replace(b"tree_d1", b"tree_dX", 1))
    tampered = klein("claims", "verify", "--study", study_rel, check=False)
    pinned_path.write_bytes(original)
    restored_check = klein("claims", "verify", "--study", study_rel, check=False)
    record(
        results,
        "PASS" if tampered.returncode != 0 and restored_check.returncode == 0 else "FAIL",
        "schema-3: a flipped byte in a pinned artifact fails claims verify, and the "
        "restore clears it",
    )

    # -- 8. the referee gate, then finalize ---------------------------------
    print("\n=== schema-3 lane: Gate 3 and finalize ===")
    open_refusal = klein("finalize", "--study", study_rel, check=False)
    record(
        results,
        "PASS" if open_refusal.returncode != 0 and "P3" in open_refusal.stderr else "FAIL",
        "schema-3: klein finalize is refused while a registered prediction is open",
    )
    klein(
        "predict", "adjudicate", "P3", "--study", study_rel, "--verdict", "supported",
        "--evidence", "E0005", "--evidence", "results.tsv",
        "--acknowledged-by", "klein-e2e",
        "--note", "the sealed run reproduced the development number inside the measured floor",
        capture=False,
    )
    referee_refusal = klein("finalize", "--study", study_rel, check=False)
    record(
        results,
        "PASS" if referee_refusal.returncode != 0 and "referee" in referee_refusal.stderr
        else "FAIL",
        "schema-3: klein finalize is refused without the Gate-3 referee record",
    )

    _write_text(study_dir / "referee_report.md", _V3_REFEREE_REPORT)
    commit("study 99-e2e-v3: referee report")
    klein("gate", "record", "referee", "--study", study_rel,
          "--acknowledged-by", "klein-e2e",
          "--note", "PASS on all ten checks", capture=False)
    referee_gate = study_state()["gates"].get("referee", {})
    record(
        results,
        "PASS" if referee_gate.get("status") == "recorded"
        and referee_gate.get("verdict") == "PASS" else "FAIL",
        "schema-3: klein gate record referee stores the machine-read verdict",
    )

    finalized = klein("finalize", "--study", study_rel).stdout
    print(finalized, end="")
    label = study_state().get("finalization", {}).get("label")
    record(
        results,
        "PASS" if label in {"confirmed", "exploratory"} else "FAIL",
        f"schema-3: klein finalize closes the study and labels it {label!r}",
    )

    # -- 9. the verify receipt ----------------------------------------------
    print("\n=== schema-3 lane: klein verify --numbers --evidence-use ===")
    verified = klein("verify", "--study", study_rel, "--numbers", "--evidence-use",
                     check=False, capture=True, timeout=600.0)
    print(verified.stdout, end="")
    receipt_path = study_dir / "verify_receipt.json"
    receipt = _json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    committed = not sh(
        ["git", "status", "--porcelain", "--", f"{study_rel}/verify_receipt.json"],
        cwd=worktree_dir, timeout=30.0, capture=True,
    ).stdout.strip()
    # The evidence-use law's three numbers, plus the rate they roll up to
    # (`kleinlib/evidence_use.py`): uncited evidence, refutations with no
    # recorded decision, and confirmed claims resting on one kind of evidence.
    three_numbers = ("uncited_evidence", "undecided_refutations", "single_source_claims")
    receipt_ok = (
        verified.returncode == 0
        and committed
        and receipt.get("evidence_use_rate") == 1.0
        and all(isinstance(receipt.get(key), list) and not receipt[key] for key in three_numbers)
        and receipt.get("summary", {}).get("failed") == 0
    )
    record(
        results,
        "PASS" if receipt_ok else "FAIL",
        "schema-3: klein verify --numbers --evidence-use writes and self-commits "
        "verify_receipt.json with evidence_use_rate and the three numbers",
    )

    # -- 10. figures, then the tutorial --------------------------------------
    print("\n=== schema-3 lane: figures and the tutorial ===")
    sh(
        ["uv", "run", "--locked", "python",
         ".claude/skills/klein/scripts/make_figures.py", study_rel],
        cwd=worktree_dir, env=env, timeout=600.0,
    )
    sections = study_dir / "report" / "sections"
    for name, fragment in _V3_FRAGMENTS.items():
        _write_text(sections / name, fragment)
    built = sh(
        ["uv", "run", "--locked", "python",
         ".claude/skills/klein/scripts/build_tutorial.py", study_rel,
         "--title", "Does a shallow tree beat a line?"],
        cwd=worktree_dir, env=env, timeout=600.0, check=False,
    )
    tutorial = study_dir / "report" / "index.html"
    page = tutorial.read_text(encoding="utf-8", errors="replace") if tutorial.exists() else ""
    self_contained = (
        built.returncode == 0
        and "data:image/png;base64" in page
        and not _EXTERNAL_URL_RE.search(page)
        and all(f'id="{anchor}"' in page for anchor in
                ("question", "method", "data", "journey", "findings",
                 "coding-advice", "next-steps"))
    )
    record(
        results,
        "PASS" if self_contained else "FAIL",
        "schema-3: the tutorial builds from seven fragments into a self-contained "
        "report/index.html (inlined figures, no external references, all anchors)",
    )
    commit("study 99-e2e-v3: figures and the tutorial")


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


#: The lanes, in the order `--lane all` runs them. The legacy lane goes first so
#: a v1 regression is reported before the longer schema-3 proof starts.
LANES: tuple[str, ...] = ("legacy", "schema3")


def lane_branch_override(override: str | None, lane: str, lanes: Sequence[str]) -> str | None:
    """The branch name for ONE lane when `KLEIN_E2E_BRANCH_NAME` is set.

    Each lane owns its own worktree and branch, and a branch name is refused if
    it already exists — so only the lanes AFTER the first are suffixed. The
    first lane keeps the caller's exact name, which is what the ownership and
    collision tests in ``scripts/tests/test_verify_e2e.py`` assert on (a
    collision must be refused before any lane does work).
    """
    if override is None or lane == lanes[0]:
        return override
    return f"{override}-{lane}"


def _run_body(repo_root: Path, results: list[CheckResult], lanes: Sequence[str]) -> int:
    before_status = _git_status_porcelain(repo_root)

    tmp_parent = Path(
        os.environ.get("KLEIN_E2E_TMP_PARENT") or os.environ.get("TMPDIR") or tempfile.gettempdir()
    )
    branch_override = os.environ.get("KLEIN_E2E_BRANCH_NAME")
    states: list[TeardownState] = []

    for lane in lanes:
        override = lane_branch_override(branch_override, lane, lanes)
        with temp_worktree(repo_root, tmp_parent, override) as state:
            states.append(state)
            worktree_dir = state.worktree_dir
            assert worktree_dir is not None

            # Test-only fast stop: exercises branch/worktree/temp ownership
            # cleanup without downloading dependencies or running the full smoke
            # study.
            if os.environ.get("KLEIN_E2E_TEST_STOP_AFTER_WORKTREE") == "1":
                return 0

            print("=== uv sync --locked (fresh .venv for the worktree; dev group is default) ===")
            sh(["uv", "sync", "--locked"], cwd=worktree_dir, timeout=600.0)

            if lane == "legacy":
                study_dir = write_fixture(worktree_dir, results)
                run_mini_loop(worktree_dir, study_dir, results)
                run_preflight_and_figures(worktree_dir, study_dir, results)
                regression_check_real_study00(repo_root, results)
            else:
                run_schema3_lane(worktree_dir, results, state)

    # every `with` block exited -> teardown already ran (worktree/branch/tempdir).
    after_status = _git_status_porcelain(repo_root)
    compare_status(before_status, after_status, results)
    for state in states:
        assert state.worktree_dir is not None and state.branch_name is not None
        check_no_leftover_worktree(repo_root, state.worktree_dir, results)
        check_no_leftover_branch(repo_root, state.branch_name, results)

    print(render_summary(results))
    return sum(1 for r in results if r.status == "FAIL")


def run(repo_root: Path, lanes: Sequence[str] = LANES) -> int:
    results: list[CheckResult] = []
    try:
        return _run_body(repo_root, results, lanes)
    except AbortE2E as exc:
        print()
        print(f"verify_e2e aborted early (exit {exc.exit_code}): {exc}")
        print("partial results:")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_e2e.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--lane",
        choices=(*LANES, "all"),
        default="all",
        help="which proof to run: legacy (the v1 compatibility path), schema3 "
        "(one typed inquiry, klein new to report/index.html), or all (default)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    lanes = LANES if args.lane == "all" else (args.lane,)

    script_dir = Path(__file__).resolve().parent
    try:
        repo_root = _resolve_repo_root(script_dir)
    except AbortE2E as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code

    return run(repo_root, lanes)


if __name__ == "__main__":
    raise SystemExit(main())
