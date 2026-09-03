"""RQ2's device half: does the same checkpoint score the same on CPU and on MPS?

`klein replicate --verify-only` re-runs the checker on the pinned artifact, and it
can be pointed at a device with `KLEIN_DEVICE`. What it cannot do is PROVE which
device it used: the replication record's environment fingerprint carries python,
platform and the lockfile hash, but not the torch device. So the device claim gets
its own instrument.

Two trials, each running `verify.py` as a subprocess exactly the way `klein run-one`
does — `KLEIN_ARTIFACT` pointing at the run's own checkpoint, `KLEIN_SMOKE` and
`KLEIN_SEALED_DRYRUN` cleared — with `KLEIN_DEVICE` set to `cpu` and to `mps` in
turn. The sidecar carries the two validation losses; `tables/device_check.tsv`
carries them with the checkpoint's sha256, so the pair is checkable against the
manifest that pinned it.

This measures the CHECKER's device portability, not the trainer's. The trainer's
device story is the full re-execution record `rep:E0001@…`, which re-runs training
and lands somewhere else entirely.

Usage: `python sweeps/device_check.py [E0001]`
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

STUDY = Path(__file__).resolve().parents[1]
DEVICES = ("cpu", "mps")


def _run_verifier(device: str, checkpoint: Path) -> tuple[float, float]:
    env = dict(os.environ)
    env.update(
        {
            "KLEIN_ARTIFACT": str(checkpoint),
            "KLEIN_EXPERIMENT_ID": "DEVICECHECK",
            "KLEIN_TRACK": "primary",
            "KLEIN_EVALUATION_KIND": "development",
            "KLEIN_DEVICE": device,
            "KLEIN_SMOKE": "",
            "KLEIN_SEALED_DRYRUN": "",
        }
    )
    t0 = time.time()
    proc = subprocess.run(
        ["uv", "run", "--locked", "python", "-u", "verify.py"],
        cwd=str(STUDY),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"verify.py exited {proc.returncode} on {device}: {proc.stderr[-400:]}")
    for line in proc.stdout.splitlines():
        if line.startswith("primary_metric:"):
            return float(line.split(":", 1)[1]), time.time() - t0
    raise RuntimeError(f"verify.py printed no primary_metric on {device}")


def main() -> int:
    from kleinlib.sweep import SweepRunner

    run_id = sys.argv[1] if len(sys.argv) > 1 else "E0001"
    checkpoint = STUDY / "models" / f"{run_id}.pt"
    if not checkpoint.is_file():
        print(f"no checkpoint for {run_id} at models/{run_id}.pt", file=sys.stderr)
        return 1
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

    def trial(params: dict) -> dict:
        value, seconds = _run_verifier(str(params["device"]), checkpoint)
        return {"primary_metric": value, "status": "ok", "wall_seconds": seconds}

    summary = SweepRunner(
        "device_check",
        ".",
        trial,
        [{"device": d, "run": run_id} for d in DEVICES],
        metric_goal="lower",
        overwrite=True,
    ).run()

    values = {t.params["device"]: float(t.primary_metric) for t in summary.trials}
    gap = abs(values["cpu"] - values["mps"])
    rows = [
        {
            "run": run_id,
            "checkpoint_sha256": digest,
            "device": device,
            "val_nats_per_char": round(values[device], 6),
        }
        for device in DEVICES
    ]
    rows.append(
        {
            "run": run_id,
            "checkpoint_sha256": digest,
            "device": "cpu_minus_mps",
            "val_nats_per_char": round(values["cpu"] - values["mps"], 9),
        }
    )
    (STUDY / "tables").mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(STUDY / "tables" / "device_check.tsv", sep="\t", index=False)
    print(f"device_check on {run_id} (checkpoint sha256 {digest[:12]}…):")
    for device in DEVICES:
        print(f"  {device:4s} -> {values[device]:.6f} nats")
    print(f"  |cpu - mps| = {gap:.9f} nats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
