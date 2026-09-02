#!/usr/bin/env python3
"""Verify every shipped schema-2 study's ledger on each push.

Discovers every ``studies/*/study.yaml``, skips schema-v1 studies (no
``schema_version`` key — the legacy ledger format ``klein verify`` reads
through a deprecated adapter rather than checking), and runs
``uv run --locked klein verify --study <dir>`` against every schema-v2 study.
The per-study ``summary: N checks, M failed`` line is the authoritative
source for pass/fail counts; a study also counts as failed if its ``klein
verify`` process itself exits non-zero (e.g. a crash before any summary line
is printed — a malformed contract, an unreadable git object, ...).

This is a guard rail, not a study tool: it never writes anywhere under
``studies/``, and it shells out to the packaged ``klein`` CLI rather than
importing ``kleinlib`` — stdlib only, so it stays usable independent of
whatever the engine looks like on a given day.

Usage::

    uv run --locked python scripts/verify_shipped_studies.py
    uv run --locked python scripts/verify_shipped_studies.py \\
        --studies 03-noisy-rosenbrock-dfo 09-iris-first-lesson

Exit code is 1 if any study reports a failed check or its verify process
exits non-zero; 2 on a usage error (e.g. an unknown ``--studies`` name); 0
otherwise.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDIES_DIR = REPO_ROOT / "studies"

# Top-level (column-0) key only — nested contract keys (tracks.*, metric.*,
# ...) are indented, so this never matches inside a mapping.
SCHEMA_VERSION_RE = re.compile(r"^schema_version:\s*(\d+)", re.MULTILINE)
SUMMARY_RE = re.compile(r"summary:\s*(\d+)\s*checks,\s*(\d+)\s*failed")

# Per-study ceiling for one `klein verify` subprocess. Observed runs take a
# few seconds; this is a generous guard against a hang, not a tuned budget.
VERIFY_TIMEOUT_SECONDS = 300


def discover_studies() -> list[Path]:
    """Every studies/*/study.yaml directory, in deterministic sorted order."""
    return sorted((p.parent for p in STUDIES_DIR.glob("*/study.yaml")), key=lambda p: p.name)


def schema_version(contract_path: Path) -> int | None:
    """The contract's top-level schema_version, or None if the key is absent (v1)."""
    match = SCHEMA_VERSION_RE.search(contract_path.read_text(encoding="utf-8"))
    return int(match.group(1)) if match else None


def run_verify(study_dir: Path) -> subprocess.CompletedProcess[str]:
    rel = study_dir.relative_to(REPO_ROOT)
    try:
        return subprocess.run(
            ["uv", "run", "--locked", "klein", "verify", "--study", str(rel)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=VERIFY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\n[verify_shipped_studies] timed out after {VERIFY_TIMEOUT_SECONDS}s"
        return subprocess.CompletedProcess(exc.cmd, returncode=124, stdout=stdout, stderr=stderr)


def parse_summary(stdout: str) -> tuple[int, int] | None:
    """(total_checks, failed) parsed from the 'summary: N checks, M failed' line."""
    match = SUMMARY_RE.search(stdout)
    return (int(match.group(1)), int(match.group(2))) if match else None


def count_warned(stdout: str) -> int:
    """Checks stay OK/FAIL only; a [WARN] tag is embedded in an OK message
    (train.py scaffold stubs, unprinted guardrails, infeasible headroom) —
    count its occurrences as an informational third bucket."""
    return stdout.count("[WARN]")


def render_table(rows: list[tuple[str, str, str, str, str]]) -> str:
    header = ("study", "passed", "warned", "failed", "exit")
    all_rows = [header, *rows]
    widths = [max(len(row[i]) for row in all_rows) for i in range(len(header))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(header, widths, strict=True))]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)))
    return "\n".join(lines)


def _normalize_selector(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.startswith("studies/"):
        value = value[len("studies/") :]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run `klein verify` on every shipped schema-2 study and summarize the result.",
    )
    parser.add_argument(
        "--studies",
        nargs="+",
        metavar="SLUG",
        help=(
            "restrict to these studies (directory name, e.g. 09-iris-first-lesson, "
            "or studies/<name>); default: every studies/*/study.yaml found"
        ),
    )
    args = parser.parse_args(argv)

    all_studies = discover_studies()

    if args.studies:
        wanted = {_normalize_selector(s) for s in args.studies}
        selected = [s for s in all_studies if s.name in wanted]
        missing = wanted - {s.name for s in selected}
        if missing:
            print(f"error: --studies named unknown studies: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    else:
        selected = all_studies

    if not selected:
        print(f"error: no studies discovered under {STUDIES_DIR}/*/study.yaml", file=sys.stderr)
        return 2

    rows: list[tuple[str, str, str, str, str]] = []
    any_failed = False

    for study_dir in selected:
        rel = study_dir.relative_to(REPO_ROOT)
        version = schema_version(study_dir / "study.yaml")
        if version is None:
            print(f"note: {rel} is schema v1 (no schema_version key) — skipped")
            continue

        result = run_verify(study_dir)
        summary = parse_summary(result.stdout)
        warned = count_warned(result.stdout)

        if summary is None:
            passed_s, failed_s = "?", "?"
            study_failed = True
            print(f"error: {rel}: klein verify produced no summary line (exit {result.returncode})", file=sys.stderr)
            tail = (result.stdout + result.stderr).strip().splitlines()[-5:]
            for line in tail:
                print(f"  | {line}", file=sys.stderr)
        else:
            total, failed = summary
            passed_s, failed_s = str(total - failed), str(failed)
            study_failed = failed > 0 or result.returncode != 0

        any_failed = any_failed or study_failed
        rows.append((str(rel), passed_s, str(warned), failed_s, str(result.returncode)))

    if rows:
        print(render_table(rows))

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
