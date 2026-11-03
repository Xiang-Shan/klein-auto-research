"""Deep-learning run helpers (Klein 2.3): seeding, usage + hardware records, checkpoints.

Everything here is optional and imports torch lazily, so ``import kleinlib.dl``
works in a torch-free environment (and the test of the engine's import weight
stays green).

* :func:`seed_everything` — Python, numpy and (when present) torch RNGs from one
  integer; ``deterministic=True`` also asks torch for deterministic kernels.
* :func:`report_usage` — merge counts (steps, tokens, calls, USD, GPU seconds)
  into ``$KLEIN_RUN_DIR/usage.json``; ``klein run-one`` folds the file into the
  manifest for EVERY exit status (a crashed run still spent its budget) and
  phases may budget it (``phases[].budget_steps`` / ``budget_tokens`` /
  ``budget_usd``).  The first call also records the hardware the run used.
* :func:`hardware_report` — torch / CUDA / cuDNN versions, device names, MPS —
  read without initialising anything that is not already importable.
* :class:`Checkpointer` — atomic save/resume of a training state INSIDE one job
  (preemption on a cluster, a crashed worker).  A checkpoint is never a way to
  continue a crashed TRANSACTION: a crash is recorded as a crash.
"""

from __future__ import annotations

import json
import os
import platform
import random
import time
from pathlib import Path
from typing import Any

__all__ = ["Checkpointer", "hardware_report", "report_usage", "seed_everything"]


def seed_everything(seed: int, *, deterministic: bool = False) -> None:
    """Seed ``random``, numpy and torch (if installed) from one integer."""
    import numpy as np

    random.seed(seed)
    np.random.seed(seed % (2**32))
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True


def hardware_report() -> dict[str, Any]:
    """What this run executed on — recorded in the manifest's ``execution.hardware``."""
    report: dict[str, Any] = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "system": platform.system(),
        "cpu_count": os.cpu_count(),
    }
    try:
        import torch
    except ImportError:
        report["torch"] = None
        return report
    report["torch"] = torch.__version__
    report["cuda_available"] = bool(torch.cuda.is_available())
    if torch.cuda.is_available():
        report["cuda"] = torch.version.cuda
        report["cudnn"] = torch.backends.cudnn.version() if hasattr(torch.backends, "cudnn") else None
        report["devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    mps = getattr(torch.backends, "mps", None)
    report["mps_available"] = bool(mps is not None and mps.is_available())
    report["device_override"] = os.environ.get("KLEIN_DEVICE")
    return report


def _usage_path() -> Path | None:
    run_dir = os.environ.get("KLEIN_RUN_DIR")
    if not run_dir or os.environ.get("KLEIN_SMOKE") == "1":
        return None
    return Path(run_dir) / "usage.json"


def report_usage(**counts: float) -> dict[str, Any]:
    """Add ``counts`` (steps=…, tokens_in=…, usd=…) to this run's usage record.

    Counts ACCUMULATE across calls and across the seeds of an array (the record is
    one per run).  Outside ``klein run-one`` (no ``KLEIN_RUN_DIR``) and under
    ``KLEIN_SMOKE=1`` nothing is written; the merged record is returned either way.
    """
    path = _usage_path()
    record: dict[str, Any] = {}
    if path is not None and path.is_file():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            record = {}
    for key, value in counts.items():
        record[key] = float(record.get(key, 0.0)) + float(value)
    if "hardware" not in record:
        record["hardware"] = hardware_report()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return record


class Checkpointer:
    """Atomic save / resume of a training state within ONE job.

    ``Checkpointer(path).save(state, step=step)`` writes ``state`` (any
    ``torch.save``-able mapping) to a temp file and renames it into place, so a
    preempted job never leaves a half-written checkpoint; ``load()`` returns the
    last complete state or None.  Checkpoints live under ``models/`` (large,
    unsafe payloads are hashed into the manifest, not committed).
    """

    def __init__(self, path: str | Path, *, every_steps: int = 0) -> None:
        self.path = Path(path)
        self.every_steps = int(every_steps)

    def due(self, step: int) -> bool:
        return self.every_steps > 0 and step > 0 and step % self.every_steps == 0

    def save(self, state: dict[str, Any], *, step: int) -> Path:
        import torch

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        torch.save({"step": int(step), "saved_at": time.time(), "state": state}, tmp)
        os.replace(tmp, self.path)
        return self.path

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        import torch

        return torch.load(self.path, map_location="cpu", weights_only=False)
