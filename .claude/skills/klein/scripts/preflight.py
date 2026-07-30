#!/usr/bin/env python3
"""
Preflight checks for a Klein Auto Research experiment loop.

Run before the first experiment in a study (and after any long pause):

    uv run python .claude/skills/klein/scripts/preflight.py --study studies/00-glm-claims-quickstart

Catches the most common pre-loop mistakes before they corrupt a run: uv
missing, experimenting on main/master, a dirty working tree, a malformed
results.tsv (header, per-row validity, experiment-number gaps), entrypoints
that don't compile, missing prepared data, and an aux_metrics.tsv sidecar
whose header has drifted from the schema.

The schema and row validators come from ``kleinlib.schema`` — the single
source (AGENTS.md "Schema discipline"). In a foreign repo, install the engine
first (see SKILL.md "Installing in another repo"); the skill directory alone
is not a runnable copy of Klein.

Exit code
---------

The number of ``[FAIL]`` checks (0 means all clear). ``[WARN]``/``[SKIP]``
never affect the exit code.

Usage
-----

```bash
uv run python .claude/skills/klein/scripts/preflight.py
uv run python .claude/skills/klein/scripts/preflight.py \\
    --mutable train.py --mutable prepare.py \\
    --prepared-data data/prepared/foo.csv

# Convenience: expand to a study directory's conventional paths.
uv run python .claude/skills/klein/scripts/preflight.py --study studies/00-glm-claims-quickstart
```
"""

from __future__ import annotations

import argparse
import csv
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Schema source
# --------------------------------------------------------------------------
#
# The results schema lives ONLY in kleinlib.schema (AGENTS.md "Schema
# discipline") — this script is a thin consumer, exactly like new_study.py.

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from kleinlib.schema import (  # noqa: E402
        AUX_COLUMNS,
        OPTIONAL_COLUMNS,
        RESULTS_COLUMNS,
        is_valid_header,
        validate_row,
    )
except ImportError as _exc:  # pragma: no cover — reachable only outside the repo
    print("[FAIL] schema source: kleinlib is not importable — the schema lives only in kleinlib.schema.")
    print("       In a foreign repo, install the engine first, e.g.:")
    print('       uv add "klein-auto-research @ git+https://github.com/Xiang-Shan/klein-auto-research@v0.3.0"')
    print(f"       ({_exc})")
    sys.exit(1)

DEFAULT_MUTABLE_FILES = ("train.py", "prepare.py")
DEFAULT_PROTECTED_BRANCHES = ("main", "master")


# --------------------------------------------------------------------------
# Check plumbing
# --------------------------------------------------------------------------


class CheckResult:
    __slots__ = ("name", "status", "message")

    def __init__(self, name: str, status: str, message: str) -> None:
        self.name = name
        self.status = status
        self.message = message


def _result(name: str, status: str, message: str) -> CheckResult:
    return CheckResult(name, status, message)


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------


def check_schema_source() -> CheckResult:
    return _result("schema source", "OK", "kleinlib.schema (single source)")


def check_uv_available() -> CheckResult:
    path = shutil.which("uv")
    if path is None:
        return _result(
            "uv on PATH",
            "FAIL",
            "uv is required (the only sanctioned package manager). Install with "
            "the official installer (https://docs.astral.sh/uv/) and re-run.",
        )
    return _result("uv on PATH", "OK", path)


def check_git_branch(protected: tuple[str, ...]) -> CheckResult:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return _result("git branch", "WARN", "git not on PATH; skipping branch check.")
    if result.returncode != 0:
        return _result("git branch", "WARN", "not a git repo (or git failed); skipping branch check.")
    branch = result.stdout.strip()
    if branch in protected:
        return _result(
            "git branch",
            "FAIL",
            f"on protected branch '{branch}' — create an experiment branch first: "
            f"git switch -c experiments/<tag>",
        )
    return _result("git branch", "OK", f"on branch '{branch}'")


def check_tree_clean(ignore: tuple[Path, ...]) -> CheckResult:
    """Working tree clean check (restored from the original preflight).

    Uncommitted changes to results.tsv itself are tolerated (in v2 it is
    a derived view that run-one/recover regenerate and sweep into the next
    state commit), everything else must be clean before the loop starts.
    """
    proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if proc.returncode != 0:
        return _result("working tree clean", "SKIP", "not a git repo; skipping (see git branch check).")
    ignore_strs = {str(p) for p in ignore}
    dirty = [line for line in proc.stdout.splitlines() if line[3:].strip() not in ignore_strs]
    if dirty:
        detail = "; ".join(line.strip() for line in dirty[:5])
        more = f" (+{len(dirty) - 5} more)" if len(dirty) > 5 else ""
        return _result(
            "working tree clean",
            "FAIL",
            f"{len(dirty)} uncommitted path(s) beyond {list(ignore_strs) or 'none'}: {detail}{more} — "
            "commit or stash before the loop",
        )
    return _result("working tree clean", "OK", "clean (results.tsv exempted)")


def check_results_tsv(path: Path) -> list[CheckResult]:
    if not path.exists():
        return [
            _result(
                "results.tsv",
                "SKIP",
                f"{path} does not exist yet (initialize with the header before the baseline).",
            )
        ]

    results: list[CheckResult] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        lines = f.read().splitlines()

    if not lines:
        results.append(_result("results.tsv header", "FAIL", f"{path} is empty (no header row)."))
        results.append(_result("results.tsv rows", "SKIP", "header invalid; skipping row validation."))
        results.append(_result("results.tsv sequence", "SKIP", "header invalid; skipping sequence check."))
        return results

    header_fields = tuple(lines[0].split("\t"))
    if not is_valid_header(lines[0]):
        results.append(
            _result(
                "results.tsv header",
                "FAIL",
                f"{path} header {header_fields!r} invalid — expected {RESULTS_COLUMNS!r} "
                f"optionally followed by a prefix of {OPTIONAL_COLUMNS!r}.",
            )
        )
        results.append(_result("results.tsv rows", "SKIP", "header invalid; skipping row validation."))
        results.append(_result("results.tsv sequence", "SKIP", "header invalid; skipping sequence check."))
        return results
    results.append(_result("results.tsv header", "OK", f"{header_fields!r} matches schema"))

    n_columns = len(header_fields)
    data_lines = lines[1:]
    if not data_lines:
        results.append(_result("results.tsv rows", "OK", "header valid, no rows yet"))
        results.append(_result("results.tsv sequence", "OK", "no rows yet"))
        return results

    exp_idx = RESULTS_COLUMNS.index("experiment")
    row_problems: list[str] = []
    experiment_numbers: list[int] = []
    for n, line in enumerate(data_lines, start=1):
        fields = line.split("\t")
        problems = validate_row(fields, n_columns=n_columns)
        if problems:
            row_problems.append(f"row {n}: {'; '.join(problems)} ({line!r})")
        # Recover an experiment number for the sequence check independently
        # of any OTHER field problems on this row (e.g. a bad status) — gap
        # detection is specifically about the numbering column, so a row
        # that fails validation for an unrelated reason should not silently
        # disappear from the sequence and manufacture a phantom gap.
        if exp_idx < len(fields):
            try:
                experiment_numbers.append(int(fields[exp_idx]))
            except ValueError:
                pass

    if row_problems:
        detail = " | ".join(row_problems[:5])
        more = f" (+{len(row_problems) - 5} more)" if len(row_problems) > 5 else ""
        results.append(_result("results.tsv rows", "FAIL", f"{detail}{more}"))
    else:
        results.append(_result("results.tsv rows", "OK", f"{len(data_lines)} row(s) all valid"))

    # Gap detection: experiment numbers must be strictly sequential from 1,
    # regardless of whether individual rows validated above (a duplicate or
    # out-of-order number is a distinct failure mode from a malformed row).
    expected = list(range(1, len(experiment_numbers) + 1))
    if experiment_numbers and experiment_numbers != expected:
        results.append(
            _result(
                "results.tsv sequence",
                "FAIL",
                f"experiment numbers {experiment_numbers} are not strictly sequential "
                f"from 1 (expected {expected}) — gap, duplicate, or reorder detected",
            )
        )
    elif experiment_numbers:
        results.append(
            _result("results.tsv sequence", "OK", f"1..{len(experiment_numbers)} strictly sequential")
        )

    return results


def check_aux_metrics_tsv(path: Path) -> CheckResult:
    if not path.exists():
        return _result(
            "aux_metrics.tsv",
            "SKIP",
            f"{path} does not exist yet (created by kleinlib.eval on first evaluate() call).",
        )
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        try:
            header = tuple(next(reader))
        except StopIteration:
            return _result("aux_metrics.tsv", "FAIL", f"{path} is empty (no header row).")
    if header != AUX_COLUMNS:
        return _result(
            "aux_metrics.tsv",
            "FAIL",
            f"{path} header {header!r} != schema.AUX_COLUMNS {AUX_COLUMNS!r}",
        )
    return _result("aux_metrics.tsv", "OK", f"header matches {AUX_COLUMNS!r}")


def check_prepared_data(paths: list[Path]) -> list[CheckResult]:
    if not paths:
        return [
            _result(
                "prepared data",
                "OK",
                "no --prepared-data paths supplied; skipping (pass paths to enable).",
            )
        ]
    results: list[CheckResult] = []
    for path in paths:
        if not path.exists():
            results.append(
                _result(f"prepared data: {path}", "FAIL", f"{path} does not exist. Run the prep command first.")
            )
            continue
        if path.is_dir():
            if not any(path.iterdir()):
                results.append(_result(f"prepared data: {path}", "FAIL", f"{path} exists but is an empty directory."))
                continue
            results.append(_result(f"prepared data: {path}", "OK", "directory present and non-empty"))
            continue
        if path.stat().st_size == 0:
            results.append(_result(f"prepared data: {path}", "FAIL", f"{path} exists but is empty."))
            continue
        results.append(_result(f"prepared data: {path}", "OK", f"{path.stat().st_size:,} bytes"))
    return results


def check_mutable_syntax(paths: list[Path]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for path in paths:
        if not path.exists():
            results.append(_result(f"syntax: {path}", "WARN", f"{path} not found; skipping."))
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            results.append(_result(f"syntax: {path}", "FAIL", f"compile error: {e.msg.strip()}"))
            continue
        results.append(_result(f"syntax: {path}", "OK", "compiles"))
    return results


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Klein Auto Research preflight checks.")
    parser.add_argument(
        "--results-path",
        type=Path,
        default=None,
        help="Path to results.tsv (default: ./results.tsv, or <study>/results.tsv with --study).",
    )
    parser.add_argument(
        "--prepared-data",
        action="append",
        type=Path,
        default=[],
        dest="prepared_data",
        help="Path that must exist and be non-empty before the loop starts. "
        "Repeat the flag for multiple paths.",
    )
    parser.add_argument(
        "--mutable",
        action="append",
        type=Path,
        default=[],
        help=f"Python file to compile-check. Repeat the flag. "
        f"Default if not supplied: {' and '.join(DEFAULT_MUTABLE_FILES)}.",
    )
    parser.add_argument(
        "--protected-branch",
        action="append",
        default=None,
        dest="protected_branch",
        help=f"Branch name that should NOT be checked out. Repeat the flag. "
        f"Default: {list(DEFAULT_PROTECTED_BRANCHES)}.",
    )
    parser.add_argument(
        "--aux-path",
        type=Path,
        default=None,
        help="Path to aux_metrics.tsv (default: ./aux_metrics.tsv, or <study>/aux_metrics.tsv with --study).",
    )
    parser.add_argument(
        "--study",
        type=Path,
        default=None,
        help="Convenience: a studies/NN-<slug> directory. Expands to "
        "<study>/train.py + <study>/prepare.py (mutable), "
        "<study>/data/prepared (prepared-data), <study>/results.tsv, and "
        "<study>/aux_metrics.tsv — unless overridden by the flags above.",
    )
    return parser.parse_args(argv)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, list[Path], list[Path]]:
    """Apply --study expansion, letting explicit flags win over the convenience defaults."""
    if args.study is not None:
        study = args.study
        results_path = args.results_path if args.results_path is not None else study / "results.tsv"
        aux_path = args.aux_path if args.aux_path is not None else study / "aux_metrics.tsv"
        mutable = args.mutable or [study / name for name in DEFAULT_MUTABLE_FILES]
        prepared_data = args.prepared_data or [study / "data" / "prepared"]
    else:
        results_path = args.results_path if args.results_path is not None else Path("results.tsv")
        aux_path = args.aux_path if args.aux_path is not None else Path("aux_metrics.tsv")
        mutable = args.mutable or [Path(p) for p in DEFAULT_MUTABLE_FILES]
        prepared_data = args.prepared_data
    return results_path, aux_path, mutable, prepared_data


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results_path, aux_path, mutable, prepared_data = resolve_paths(args)
    protected = tuple(args.protected_branch) if args.protected_branch else DEFAULT_PROTECTED_BRANCHES

    checks: list[CheckResult] = [
        check_schema_source(),
        check_uv_available(),
        check_git_branch(protected),
        check_tree_clean((results_path,)),
    ]
    checks.extend(check_results_tsv(results_path))
    checks.append(check_aux_metrics_tsv(aux_path))
    checks.extend(check_mutable_syntax(mutable))
    checks.extend(check_prepared_data(prepared_data))

    width = max(len(c.name) for c in checks)
    fail_count = 0
    warn_count = 0
    for c in checks:
        marker = {"OK": "[OK]  ", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(c.status, "[??]  ")
        print(f"{marker} {c.name:<{width}} — {c.message}")
        if c.status == "FAIL":
            fail_count += 1
        elif c.status == "WARN":
            warn_count += 1

    print("---")
    print(
        f"summary: {len(checks)} checks  ok={len(checks) - fail_count - warn_count}  "
        f"warn={warn_count}  fail={fail_count}"
    )
    return fail_count


if __name__ == "__main__":
    sys.exit(main())
