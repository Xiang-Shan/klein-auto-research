"""``klein job exec`` — run a detached job and write the receipt ``--collect`` checks (Klein 2.3).

``klein run-one --detach`` stops after the candidate commit and files a DETACH
commit holding ``runs/E####/job.json``: the command, environment, seeds and
timeout the notary allows, the candidate commit, and the sha256 of every
mutable-surface file.  Anything that can check that commit out can execute it —
a GPU workstation, a Slurm job, a Modal container, a Claude Science job card —
by running::

    klein job exec studies/NN-slug/runs/E####/job.json [--executor local|here]

* ``--executor local`` (default) runs the job in a throwaway git worktree of this
  repository at HEAD (the detach commit) — the same isolation ``klein replicate``
  uses — then writes ``runs/E####/job_result/`` back into THIS checkout.  Run it
  in the background (``nohup … &``) to keep working; the study stays frozen.
* ``--executor here`` runs in the checkout it is invoked from — a dedicated clone
  on the host, at the detach commit — and leaves ``job_result/`` there for the
  host to copy back next to the job bundle.

``job_result/`` holds ``run.log``, ``usage.json`` (when the child reported one),
``files/<rel>`` for every output the run produced or declared, and
``receipt.json``: the job's own sha256, the candidate commit, the surface hashes
actually executed, the log and file hashes, the exit status and the hardware.
``klein run-one --collect E####`` re-checks all of it before judging the run
locally.  The notary did not watch the process, so the manifest records the run
as attested, not observed.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contract import load_contract
from .decision import parse_printed_strings
from .errors import WorkflowError
from .manifest import artifact_inventory
from .primitives import atomic_write_json, sha256_file, utc_now
from .runner import run_logged, run_seed_array
from .transaction import detached_worktree, repo_root_for

__all__ = ["exec_job"]


def _study_of(job_path: Path) -> Path:
    # runs/E####/job.json -> the study directory
    return job_path.resolve().parents[2]


def _execute(job: Mapping[str, Any], study: Path, run_dir: Path, *, echo: bool) -> dict[str, Any]:
    """Run the job in *study* (a checkout at the detach commit); outputs land in place."""
    surface = {name: sha256_file(study / name) for name in job["surface"] if (study / name).is_file()}
    if surface != job["surface"]:
        raise WorkflowError(
            "the checkout's mutable surface differs from the job's candidate — check out the "
            "detach commit unmodified"
        )
    log_path = run_dir / "job_run.log"
    env = {**job["env"], "KLEIN_RUN_DIR": str(run_dir)}
    command = list(job["command"])
    if command[:2] == ["uv", "run"]:
        from .replicate import _prepare_environment

        setup = _prepare_environment(command, repo_root_for(study), log_path, echo=echo)
        if setup.failure_reason is not None:
            raise WorkflowError(f"job environment setup failed: {setup.failure_reason}")
        append = setup.ran
    else:
        append = False
    started_at = utc_now()
    seeds = job.get("seeds")
    if seeds:
        result = run_seed_array(
            command, [int(s) for s in seeds], cwd=study, log_path=log_path,
            timeout_seconds=float(job["timeout_seconds"]), echo=echo, env_overrides=env, append=append,
        )
    else:
        result = run_logged(
            command, cwd=study, log_path=log_path, timeout_seconds=float(job["timeout_seconds"]),
            echo=echo, env_overrides=env, append=append,
        )
    return {
        "surface": surface,
        "log_path": log_path,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "wall_seconds": result.wall_seconds,
        "started_at": started_at,
        "ended_at": utc_now(),
    }


def _outputs(job: Mapping[str, Any], study: Path, log_path: Path) -> dict[str, Path]:
    """Every file the run produced or changed under the watched dirs, plus declared artifacts."""
    before = job.get("artifacts_before") or {}
    after = artifact_inventory(study, tuple(job.get("watched_dirs") or ()))
    out = {rel: study / rel for rel, meta in after.items() if before.get(rel) != meta.get("sha256")}
    for raw in parse_printed_strings(log_path).get("artifact", ()):
        rel = raw.strip()
        path = (study / rel).resolve()
        try:
            path.relative_to(study.resolve())
        except ValueError:
            continue
        if path.is_file():
            out[Path(rel).as_posix()] = path
    return out


def exec_job(job_path: str | Path, *, executor: str = "local", echo: bool = True) -> Path:
    """Execute one detached job; return the ``job_result/`` directory written."""
    job_path = Path(job_path).resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    if job.get("job_schema") != 1:
        raise WorkflowError(f"unsupported job_schema {job.get('job_schema')!r}")
    study = _study_of(job_path)
    run_id = str(job["experiment"])
    result_dir = study / "runs" / run_id / "job_result"
    if result_dir.exists():
        raise WorkflowError(f"{result_dir} already exists — collect it, or remove it to re-run the job")
    if executor not in {"local", "here"}:
        raise WorkflowError("executor must be local or here")

    def finish(checkout_study: Path, outcome: Mapping[str, Any], outputs: Mapping[str, Path]) -> Path:
        result_dir.mkdir(parents=True)
        shutil.copyfile(outcome["log_path"], result_dir / "run.log")
        usage = checkout_study / "runs" / run_id / "usage.json"
        hardware = None
        if usage.is_file():
            shutil.copyfile(usage, result_dir / "usage.json")
            try:
                hardware = json.loads(usage.read_text(encoding="utf-8")).get("hardware")
            except ValueError:
                hardware = None
        files: dict[str, str] = {}
        for rel, source in sorted(outputs.items()):
            target = result_dir / "files" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            files[rel] = sha256_file(target)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=checkout_study, capture_output=True, text=True, check=False
        ).stdout.strip()
        receipt = {
            "receipt_schema": 1,
            "experiment": run_id,
            "job_sha256": sha256_file(job_path),
            "candidate_commit": job["candidate_commit"],
            "executed_commit": head,
            "executor": executor,
            "host": platform.node(),
            "surface": outcome["surface"],
            "exit_code": outcome["exit_code"],
            "timed_out": outcome["timed_out"],
            "wall_seconds": round(float(outcome["wall_seconds"]), 3),
            "started_at": outcome["started_at"],
            "ended_at": outcome["ended_at"],
            "log_sha256": sha256_file(result_dir / "run.log"),
            "files": files,
            **({"hardware": hardware} if isinstance(hardware, Mapping) else {}),
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        atomic_write_json(result_dir / "receipt.json", receipt)
        return result_dir

    if executor == "here":
        run_dir = study / "runs" / run_id
        outcome = _execute(job, study, run_dir, echo=echo)
        return finish(study, outcome, _outputs(job, study, outcome["log_path"]))

    from .replicate import _copy_prepared_data

    contract = load_contract(study)
    repo = repo_root_for(study)
    with detached_worktree(repo, "HEAD", prefix="klein-job-") as worktree:
        checkout_study = worktree / job["study"]
        _copy_prepared_data(study, checkout_study, contract, job.get("data_fingerprint"))
        run_dir = checkout_study / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        outcome = _execute(job, checkout_study, run_dir, echo=echo)
        return finish(checkout_study, outcome, _outputs(job, checkout_study, outcome["log_path"]))

