"""Re-runnable checks of the declared verifier (lead, METHOD gate): the lane follows
KLEIN_EVALUATION_KIND, the oracle is pinned, the artifact must name the run, and each
pair must spend exactly the budget. Toy artifacts only: published optimal rulers for
orders 8-13 typed in by hand, scored by verify.py itself; nothing is searched.

    uv run --locked python sweeps/verifier_checks.py
"""

import copy
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
OUT = Path(tempfile.mkdtemp(prefix="verifier-checks-"))
OPT = {
    8: [0, 1, 4, 9, 15, 22, 32, 34],
    9: [0, 1, 5, 12, 25, 27, 35, 41, 44],
    10: [0, 1, 6, 10, 23, 26, 34, 41, 53, 55],
    11: [0, 1, 4, 13, 28, 33, 47, 54, 64, 70, 72],
    12: [0, 2, 6, 24, 29, 40, 43, 55, 68, 75, 76, 85],
    13: [0, 2, 5, 25, 37, 43, 59, 70, 85, 89, 98, 99, 106],
}


def art(lane, orders):
    pairs = [
        {"order": n, "trial": t, "evaluations": 2000, "best": OPT[n], "best_length": OPT[n][-1]}
        for n in orders
        for t in range(3)
    ]
    return {
        "problem": "golomb-ruler",
        "arm": "search",
        "experiment": "TEST",
        "lane": lane,
        "orders": orders,
        "trials": 3,
        "pairs": pairs,
    }


def run(name, payload, kind, study=STUDY):
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload))
    env = {k: v for k, v in os.environ.items() if k not in ("KLEIN_SMOKE", "KLEIN_EVALUATION_KIND")}
    env.update(
        {"KLEIN_ARTIFACT": str(path), "KLEIN_EXPERIMENT_ID": "TEST", "KLEIN_TRACK": "search"}
    )
    if kind is not None:
        env["KLEIN_EVALUATION_KIND"] = kind
    p = subprocess.run(
        ["uv", "run", "--locked", "python", "-u", "verify.py"],
        cwd=study,
        env=env,
        capture_output=True,
        text=True,
    )
    keep = [
        line
        for line in p.stdout.splitlines()
        if line.split(":")[0] in ("REJECTED", "primary_metric", "sealed_lane")
    ]
    print(f"[{name}] exit={p.returncode} " + " | ".join(keep))
    return p.returncode


dev, sealed = art("development", [8, 9, 10, 11]), art("sealed", [12, 13])
assert run("dev-on-dev", dev, "development") == 0
assert run("sealed-on-final", sealed, "final_test") == 0
assert run("sealed-on-dev", sealed, "development") == 2
assert run("dev-on-final", dev, "final_test") == 2
assert run("no-kind", dev, None) == 2
other = copy.deepcopy(dev)
other["experiment"] = "E0099"
assert run("other-experiment", other, "development") == 2
short = copy.deepcopy(dev)
short["pairs"][0]["evaluations"] = 0
assert run("zero-evaluations", short, "development") == 2
# A tampered instance.json (an optimum raised to what a search reached) is refused.
tmp = Path(tempfile.mkdtemp())
copy = tmp / "study"
shutil.copytree(STUDY, copy, ignore=shutil.ignore_patterns("data/raw", ".venv"))
inst = json.loads((copy / "data/prepared/instance.json").read_text())
inst["optima"]["9"] = 45
(copy / "data/prepared/instance.json").write_text(json.dumps(inst))
assert run("tampered-instance", dev, "development", study=copy) == 2
inst["optima"]["9"] = 44
inst["budget_evaluations"] = 5000
(copy / "data/prepared/instance.json").write_text(json.dumps(inst))
assert run("tampered-budget", dev, "development", study=copy) == 2
shutil.rmtree(tmp)
shutil.rmtree(OUT)
print("ALL OK")
