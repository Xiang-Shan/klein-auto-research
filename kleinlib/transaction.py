"""Git-backed evidence transactions: the notary half of ``klein run-one``.

Extracted verbatim from :mod:`kleinlib.workflow` (the private helpers took their
public names in their new home; ``workflow`` re-exports them under the old
names, same objects).  Two entry points take an injectable ``commit`` callable —
:func:`complete_evidence_transaction` and :func:`commit_state_writes` — so a
caller can substitute the committer without reaching into this module's globals.
``workflow`` passes its own module-global ``_git_commit``, which is what lets
the interrupted-transaction tests inject a failure INSIDE the transaction by
patching ``workflow._git_commit``.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .events import append_event
from .manifest import derive_results
from .primitives import (
    atomic_write_json,
    canonical_json,
    sha256_bytes,
    sha256_file,
    utc_now,
)

__all__ = [
    "STATE_WRITE_PATHS",
    "assert_run_worktree",
    "commit_state_writes",
    "complete_evidence_transaction",
    "current_branch",
    "detached_worktree",
    "environment_fingerprint",
    "git",
    "git_blob",
    "git_commit",
    "relative",
    "repo_root_for",
    "stage_evidence",
]

#: The committer :func:`complete_evidence_transaction` and
#: :func:`commit_state_writes` call.  Defaults to :func:`git_commit`.
Committer = Callable[..., str]

def environment_fingerprint(repo_root: Path) -> tuple[str, dict[str, Any]]:
    lock = repo_root / "uv.lock"
    details = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "uv_lock_sha256": sha256_file(lock) if lock.is_file() else None,
    }
    return sha256_bytes(canonical_json(details).encode()), details


def git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise WorkflowError(f"git {' '.join(args)} failed: {detail}")
    return result


def repo_root_for(study_dir: Path) -> Path:
    result = git(study_dir, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def current_branch(repo_root: Path) -> str:
    result = git(repo_root, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    if result.returncode:
        raise WorkflowError("detached HEAD is not allowed for a study run")
    return result.stdout.strip()


def git_blob(repo: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def git_commit(repo: Path, message: str, *, allow_empty: bool = False, amend: bool = False) -> str:
    args = ["-c", "user.name=Klein Workflow", "-c", "user.email=klein@localhost", "commit", "-q"]
    if amend:
        args.extend(["--amend", "--no-edit"])
    else:
        if allow_empty:
            args.append("--allow-empty")
        args.extend(["-m", message])
    git(repo, args)
    return git(repo, ["rev-parse", "HEAD"]).stdout.strip()


@contextmanager
def detached_worktree(repo: Path, commit: str, *, prefix: str = "klein-worktree-") -> Iterator[Path]:
    """A throwaway ``git worktree add --detach`` checkout of *commit*.

    The checkout is created in the SYSTEM temporary directory (whatever
    ``tempfile`` resolves — ``TMPDIR``/``TMP``/``TEMP``), never inside *repo*:
    a nested worktree would put a second copy of the study under the study's
    own tree, where ``assert_run_worktree`` and every ``git add`` glob would
    see it.  The path is refused if it lands inside the repository anyway.

    Teardown is unconditional and belt-and-braces — ``git worktree remove
    --force``, then ``shutil.rmtree`` of the temp parent, then ``git worktree
    prune`` — so an exception raised inside the ``with`` body (or a child that
    left the checkout dirty) still leaves neither directory nor admin record
    behind.  ``remove`` and ``prune`` are ``check=False``: cleanup must never
    mask the caller's own failure.
    """
    repo = repo.resolve()
    parent = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    try:
        try:
            parent.relative_to(repo)
        except ValueError:
            pass
        else:
            raise WorkflowError(
                f"the temporary directory {parent} is inside the repository {repo}; "
                "a replication worktree must live outside it — set TMPDIR elsewhere"
            )
        # `git worktree add` requires a path that does not already exist.
        path = parent / "worktree"
        git(repo, ["worktree", "add", "--detach", str(path), commit])
        try:
            yield path
        finally:
            git(repo, ["worktree", "remove", "--force", str(path)], check=False)
    finally:
        shutil.rmtree(parent, ignore_errors=True)
        git(repo, ["worktree", "prune"], check=False)


def relative(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo).as_posix()
    except ValueError as exc:
        raise WorkflowError(f"path is outside git repository: {path}") from exc


#: Study files a CLI verb may (re)write outside a run transaction: contract and
#: narrative docs, machine state, regenerable derived views, and sweep sidecars
#: (measurement evidence the next state commit must file). Never train.py —
#: committing it here would silently move run-one's restore anchor.
STATE_WRITE_PATHS = (
    "study.yaml",
    "playbook.md",
    "study_state.json",
    "events.jsonl",
    "research_plan.md",
    "program.md",
    "data_card.md",
    "method_card.md",
    "findings.md",
    "results_summary.md",
    "progress.svg",
    "figures",
    "sweeps",
)


def commit_state_writes(
    study_dir: Path,
    message: str,
    *,
    commit: Committer | None = None,
    paths: Sequence[str] = (),
) -> str | None:
    """Commit the state/derived files a CLI verb just wrote.

    The loop contract requires a clean tree at ``run-one``; the receipts the CLI
    itself generates must therefore be filed by the CLI, not hand-committed by
    the operator. No-op outside a git repository (unit fixtures scaffold studies
    in bare temp dirs) and when nothing actually changed.

    ``paths`` names EXTRA study-relative files or directories to include beyond
    :data:`STATE_WRITE_PATHS`; each is staged only if it exists, so passing a
    path a verb did not write is harmless. ``commit`` substitutes the committer
    (default :func:`git_commit`).
    """
    probe = git(study_dir, ["rev-parse", "--show-toplevel"], check=False)
    if probe.returncode:
        return None
    repo = Path(probe.stdout.strip()).resolve()
    names = [*STATE_WRITE_PATHS, *(name for name in paths if name not in STATE_WRITE_PATHS)]
    existing = [
        relative(repo, study_dir / name)
        for name in names
        if (study_dir / name).exists()
    ]
    if not existing:
        return None
    git(repo, ["add", "--", *existing])
    if git(repo, ["diff", "--cached", "--quiet"], check=False).returncode == 0:
        return None
    return (commit or git_commit)(repo, message)


def stage_evidence(repo: Path, study_dir: Path, manifest: Mapping[str, Any]) -> None:
    core = [
        study_dir / "study_state.json",
        study_dir / "events.jsonl",
        study_dir / "results.tsv",
        study_dir / "playbook.md",
        study_dir / "runs" / str(manifest["experiment"]) / "manifest.json",
        study_dir / "runs" / str(manifest["experiment"]) / "run.log",
    ]
    for rel, meta in manifest.get("artifacts", {}).items():
        if meta.get("committed"):
            core.append(study_dir / rel)
    existing = [relative(repo, p) for p in core if p.exists()]
    if existing:
        git(repo, ["add", "-f", "--", *existing])


def complete_evidence_transaction(
    repo: Path,
    study_dir: Path,
    manifest: dict[str, Any],
    *,
    restored_train: bool,
    recovery: bool = False,
    commit: Committer | None = None,
    surface: Sequence[str] = ("train.py",),
) -> str:
    """File the two-commit evidence transaction for one completed run.

    ``commit`` substitutes the committer (default :func:`git_commit`) so a
    caller can inject a failure — or an instrumented committer — INSIDE the
    transaction rather than around it.  ``surface`` is the declared mutable
    surface that was restored on a non-keep: ``train.py`` for schema 2,
    ``entrypoint.mutable`` for schema 3.
    """
    commit = commit or git_commit
    run_id = str(manifest["experiment"])
    derive_results(study_dir)
    if restored_train:
        surface_rels = [
            relative(repo, study_dir / name)
            for name in surface
            if (study_dir / name).exists()
        ]
        if surface_rels:
            git(repo, ["add", "--", *surface_rels])
    stage_evidence(repo, study_dir, manifest)
    first_commit = commit(
        repo,
        f"evidence {run_id}: {manifest['disposition']}",
        allow_empty=False,
    )
    manifest["transaction"] = {
        "status": "complete",
        "committed_at": utc_now(),
        "evidence_commit": first_commit,
        "recovered": recovery,
    }
    atomic_write_json(study_dir / "runs" / run_id / "manifest.json", manifest)
    append_event(
        study_dir,
        "transaction_recovered" if recovery else "transaction_committed",
        experiment=run_id,
        disposition=manifest["disposition"],
        evidence_commit=first_commit,
    )
    stage_evidence(repo, study_dir, manifest)
    return commit(repo, f"transaction {run_id}: finalize evidence")


def assert_run_worktree(
    repo: Path, study_dir: Path, *, surface: Sequence[str] = ("train.py",)
) -> None:
    status = git(repo, ["status", "--porcelain", "--untracked-files=all"]).stdout.splitlines()
    # The uncommitted candidate IS the experiment, so the declared mutable
    # surface is exempt — ``train.py`` for schema 2, ``entrypoint.mutable`` for
    # schema 3, where the entrypoint is named by kind.
    surface_rels = {relative(repo, study_dir / name) for name in surface}
    # The lock is ephemeral state; a foreign repo has no .gitignore for it, so
    # it must be exempt here rather than rely on ignore rules. Derived views
    # (summary, progress, figures) are regenerable at any time and are swept
    # into the next state commit by a gate record — they never gate a run.
    lock_rel = relative(repo, study_dir / ".klein.lock")
    playbook_rel = relative(repo, study_dir / "playbook.md")
    summary_rel = relative(repo, study_dir / "results_summary.md")
    progress_rel = relative(repo, study_dir / "progress.svg")
    figures_prefix = relative(repo, study_dir / "figures") + "/"
    allowed = surface_rels | {lock_rel, playbook_rel, summary_rel, progress_rel}
    bad: list[str] = []
    for line in status:
        path = line[3:].split(" -> ")[-1]
        if path not in allowed and not path.startswith(figures_prefix):
            bad.append(line)
    if bad:
        raise WorkflowError(
            f"run-one requires a clean tree except for {', '.join(surface)} and derived "
            "views; found: "
            + ", ".join(bad)
            + " — commit these first (gate records, finalize, and recover file their own "
            "state writes automatically; for manual edits: git add <files> && git commit)"
        )
