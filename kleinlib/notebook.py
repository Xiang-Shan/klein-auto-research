"""``klein notebook E####`` — a run as a Jupyter notebook, for reading (Klein 2.3).

Hosts that think in notebooks (Claude Science's kernel and artifact viewer,
JupyterLab, VS Code) read a run more easily as cells.  This writes an nbformat-4
``.ipynb`` holding:

* a header cell — experiment, track, disposition, metric, decision reason, the
  candidate commit, and the command the notary ran;
* one code cell per mutable-surface file **as executed** — the bytes at the
  run's candidate commit (``git show``), never the restored file on disk;
* the printed metric block from ``runs/E####/run.log`` (block scope when the
  manifest says so).

It is a DERIVATIVE: outputs are not stored, nothing is executed, and the file is
never evidence — the manifest and the candidate commit are.  The header says so.
The JSON is written by hand (sorted keys, fixed metadata) so the same run always
produces the same bytes, and no ``nbformat`` dependency is needed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .contract import load_contract, mutable_surface
from .decision import block_lines
from .errors import WorkflowError

__all__ = ["notebook_for_run", "write_notebook"]


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise WorkflowError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def _source(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def _markdown(text: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": _source(text)}


def _code(text: str, name: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"klein": {"file": name}},
        "outputs": [],
        "source": _source(text),
    }


def notebook_for_run(study_dir: Path, run_id: str) -> dict[str, Any]:
    study_dir = Path(study_dir).resolve()
    run_dir = study_dir / "runs" / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise WorkflowError(f"no manifest for {run_id} in {study_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commit = str(manifest.get("candidate_commit") or "")
    if not commit:
        raise WorkflowError(f"{run_id} records no candidate commit")
    top = Path(_git(study_dir, "rev-parse", "--show-toplevel").strip())
    rel = study_dir.relative_to(top).as_posix()
    try:
        contract_at = yaml.safe_load(_git(top, "show", f"{commit}:{rel}/study.yaml"))
        surface = mutable_surface(contract_at)
    except (WorkflowError, yaml.YAMLError, KeyError, TypeError):
        surface = mutable_surface(load_contract(study_dir))
    metric = manifest.get("primary_metric")
    header = "\n".join(
        [
            f"# {study_dir.name} — {run_id}",
            "",
            "> A reading copy of a Klein run, written by `klein notebook`. Not evidence: the",
            f"> manifest (`runs/{run_id}/manifest.json`) and candidate commit `{commit[:12]}` are.",
            "> Cells were not executed here; run the experiment with `klein run-one` or",
            f"> re-execute it with `klein replicate {run_id}`.",
            "",
            "| field | value |",
            "|---|---|",
            f"| track | `{manifest.get('track', 'primary')}` |",
            f"| evaluation | `{manifest.get('evaluation_kind', 'development')}` |",
            f"| disposition | **{manifest.get('disposition')}** |",
            f"| {manifest.get('metric_name') or 'primary_metric'} | `{metric}` |",
            f"| description | {str(manifest.get('description') or '').replace('|', '/')} |",
            f"| decision | {str(manifest.get('decision_reason') or '').replace('|', '/')} |",
            f"| command | `{' '.join(str(p) for p in manifest.get('command') or [])}` |",
            f"| candidate commit | `{commit}` |",
            *(
                [f"| execution | `{manifest['execution'].get('mode')}` (attested, not observed) |"]
                if isinstance(manifest.get("execution"), dict)
                else []
            ),
            *([f"| seeds | {manifest['seeds_n']} |"] if manifest.get("seeds_n") else []),
        ]
    )
    cells = [_markdown(header)]
    for name in surface:
        try:
            text = _git(top, "show", f"{commit}:{rel}/{name}")
        except WorkflowError:
            continue
        cells.append(_markdown(f"## `{name}` as executed at `{commit[:12]}`"))
        cells.append(_code(text, name))
    log = run_dir / "run.log"
    if log.is_file():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        block = block_lines(lines) if manifest.get("printed_scope") == "block" else None
        shown = block if block is not None else lines[-60:]
        label = "the printed block" if block is not None else "the last lines of the run log"
        cells.append(_markdown(f"## Output — {label}\n\n```text\n" + "\n".join(shown) + "\n```"))
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "klein": {"study": study_dir.name, "experiment": run_id, "candidate_commit": commit, "derivative": True},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(study_dir: Path, run_id: str, out: Path | None = None) -> Path:
    notebook = notebook_for_run(study_dir, run_id)
    for index, cell in enumerate(notebook["cells"]):
        cell["id"] = f"klein-{index:03d}"  # nbformat 4.5 cell ids, deterministic
    target = Path(out) if out else Path.cwd() / f"{Path(study_dir).resolve().name}-{run_id}.ipynb"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(notebook, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
