"""Self-contained v2 study scaffolding used by ``klein new``.

Templates live in Python so the command continues to work from an installed wheel;
the copies under ``.claude/skills/klein/assets`` are the agent-readable equivalents.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .workflow import (
    IDENTIFIER_RE,
    STUDY_ID_RE,
    V2_RESULTS_COLUMNS,
    append_event,
    atomic_write_json,
    initial_state,
)

STUDY_YAML = """\
schema_version: 2
study_id: "{{STUDY_ID}}"
goal: "{{GOAL}}"
domain: "{{DOMAIN}}"
target: "{{TARGET}}"
task_type: "{{TASK_TYPE}}"       # classification | regression
method_depth: "{{METHOD_DEPTH}}" # brief | full
family: "{{FAMILY}}"

# A track owns its metric frontier. Never compare unrelated research tasks globally.
tracks:
  {{TRACK}}:
    metric:
      name: "{{METRIC_NAME}}"
      goal: "{{METRIC_GOAL}}"     # higher | lower
      minimum_delta: {{MINIMUM_DELTA}}
    guardrails: {}

data:
  source: "{{DATA_SOURCE}}"
  prepared_path: "{{DATA_PATH}}"
  split:
    kind: {{SPLIT_KIND}}           # stratified | random | group | time
    seed: 42
    development_size: 0.20
    test_size: 0.20
{{SPLIT_COLUMN}}
    # group_column: account_id     # required when kind=group
    # time_column: event_time      # required when kind=time

# Per-run, per-phase time, and experiment-count limits are intentionally separate.
max_run_seconds: {{MAX_RUN_SECONDS}}
phases:
  - id: adaptive-1
    description: "split-identity anchor, baseline, then bounded adaptive work"
    budget_seconds: 3600
    max_experiments: 4
  - id: confirmation
    description: "one sealed final-test evaluation per track"
    budget_seconds: 900
    max_experiments: 1

research_questions:
  - id: RQ1
    question: "{{RQ1_QUESTION}}"
    prior: "{{RQ1_PRIOR}}"

predictions_to_falsify:
  - lever: "{{LEVER_1}}"
    predicted_delta: "{{DELTA_1}}"

deliverables:
  - findings.md
  - report/index.html
"""

PROGRAM = """\
# Program — {{STUDY_ID}}

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: {{GOAL}}
- Track: `{{TRACK}}`
- Primary metric: `{{METRIC_NAME}}` ({{METRIC_GOAL}} is better; minimum meaningful
  delta {{MINIMUM_DELTA}})
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: {{DATA_SOURCE}}
- Adaptive work uses train + development only. The test partition stays sealed.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/{{STUDY_ID}}`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track {{TRACK}} --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores the last working `train.py`.

## Decisions (append-only)

- {{DATE}} — schema-v2 study scaffolded; gates pending.
"""

RESEARCH_PLAN = """\
# Research plan — {{STUDY_ID}}

## Question

{{GOAL}}

## Contract

- Domain: {{DOMAIN}}
- Data: {{DATA_SOURCE}}
- Track: {{TRACK}}
- Metric: {{METRIC_NAME}} ({{METRIC_GOAL}}, minimum delta {{MINIMUM_DELTA}})
- Method depth: {{METHOD_DEPTH}}
- Per-run maximum: {{MAX_RUN_SECONDS}} seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. Reproduce a split-identity anchor.
2. Establish an honest baseline.
3. Test the proposed method and ablations inside phase limits.
4. Run the chosen track candidate once on the sealed final test.
"""

PREPARE = '''\
"""Prepare the immutable local artifact declared by study.yaml:data.prepared_path."""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError("write the prepared artifact without reading the sealed test")


if __name__ == "__main__":
    main()
'''

TRAIN = '''\
"""The only per-candidate mutable surface in a Klein v2 study."""

from __future__ import annotations

import os
import time

import kleinlib

RANDOM_SEED = 42
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID")
TRACK = os.environ.get("KLEIN_TRACK")


def load_split(evaluation_kind: str):
    """Select development or the sealed final-test partition explicitly.

    The workflow sets KLEIN_EVALUATION_KIND. Implement this function so
    ``development`` returns train/development and ``final_test`` returns the frozen
    chosen training data/final test. Never choose the partition from experiment code.
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    raise NotImplementedError("implement the fixed three-way split declared in study.yaml")


def build_model():
    raise NotImplementedError("build this candidate")


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
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
            "train.py must be invoked through `klein run-one`; missing "
            + ", ".join(missing)
        )
    X_tr, X_dev, y_tr, y_dev = load_split(evaluation_kind)
    model = build_model()
    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start
    kleinlib.eval.evaluate(
        model,
        X_dev,
        y_dev,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_tr),
        val_n=len(X_dev),
        metric_name="{{METRIC_NAME}}",
        metric_goal="{{METRIC_GOAL}}",
    )


if __name__ == "__main__":
    main()
'''


def _quote_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def scaffold_study(
    root: Path,
    slug: str,
    *,
    goal: str | None = None,
    domain: str | None = None,
    target: str | None = None,
    task_type: str = "classification",
    method_depth: str = "full",
    family: str | None = None,
    track: str = "primary",
    metric_name: str | None = None,
    metric_goal: str | None = None,
    minimum_delta: float = 0.0,
    data_source: str | None = None,
    data_path: str | None = None,
    split_kind: str | None = None,
    group_column: str | None = None,
    time_column: str | None = None,
    max_run_seconds: int = 600,
) -> Path:
    from .eval import get_metric_spec

    if not STUDY_ID_RE.fullmatch(slug):
        raise ValueError("study id must match NN-lowercase-slug")
    if not IDENTIFIER_RE.fullmatch(track):
        raise ValueError("track must be a safe identifier")
    if task_type not in {"classification", "regression"}:
        raise ValueError("task_type must be classification or regression")
    if method_depth not in {"brief", "full"}:
        raise ValueError("method_depth must be brief or full")
    if split_kind is None:
        split_kind = "stratified" if task_type == "classification" else "random"
    if split_kind not in {"stratified", "random", "group", "time"}:
        raise ValueError("split_kind must be stratified, random, group, or time")
    if task_type == "regression" and split_kind == "stratified":
        raise ValueError("regression studies cannot use a stratified split")
    if split_kind == "group" and not group_column:
        raise ValueError("group_column is required for a group split")
    if split_kind == "time" and not time_column:
        raise ValueError("time_column is required for a time split")
    if metric_name is not None:
        spec = get_metric_spec(
            metric_name,
            goal=metric_goal,
            task=task_type,
        )
        metric_goal = spec.goal
    elif metric_goal is not None:
        raise ValueError("metric_name is required when metric_goal is supplied")
    study_dir = root.resolve() / slug
    if study_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing study: {study_dir}")
    values: dict[str, str] = {
        "STUDY_ID": slug,
        "DATE": dt.date.today().isoformat(),
        "GOAL": _quote_text(goal or "{{GOAL}}"),
        "DOMAIN": _quote_text(domain or "{{DOMAIN}}"),
        "TARGET": _quote_text(target or "{{TARGET}}"),
        "TASK_TYPE": task_type,
        "METHOD_DEPTH": method_depth,
        "FAMILY": _quote_text(family or "{{FAMILY}}"),
        "TRACK": track,
        "METRIC_NAME": _quote_text(metric_name or "{{METRIC_NAME}}"),
        "METRIC_GOAL": metric_goal or "{{METRIC_GOAL}}",
        "MINIMUM_DELTA": format(float(minimum_delta), ".12g"),
        "DATA_SOURCE": _quote_text(data_source or "{{DATA_SOURCE}}"),
        "DATA_PATH": _quote_text(data_path or "data/prepared/dataset.parquet"),
        "SPLIT_KIND": split_kind,
        "SPLIT_COLUMN": (
            f'    group_column: "{_quote_text(group_column)}"'
            if split_kind == "group" and group_column
            else f'    time_column: "{_quote_text(time_column)}"'
            if split_kind == "time" and time_column
            else ""
        ),
        "MAX_RUN_SECONDS": str(int(max_run_seconds)),
        "RQ1_QUESTION": "{{RQ1_QUESTION}}",
        "RQ1_PRIOR": "{{RQ1_PRIOR}}",
        "LEVER_1": "{{LEVER_1}}",
        "DELTA_1": "{{DELTA_1}}",
    }
    study_dir.mkdir(parents=True)
    for dirname in ("figures", "models", "report", "runs", "sweeps"):
        (study_dir / dirname).mkdir()
        if dirname != "runs":
            (study_dir / dirname / ".gitkeep").write_text("", encoding="utf-8")
    files = {
        "study.yaml": STUDY_YAML,
        "program.md": PROGRAM,
        "research_plan.md": RESEARCH_PLAN,
        "prepare.py": PREPARE,
        "train.py": TRAIN,
    }
    for name, template in files.items():
        (study_dir / name).write_text(_render(template, values), encoding="utf-8")
    (study_dir / "results.tsv").write_text("\t".join(V2_RESULTS_COLUMNS) + "\n", encoding="utf-8")
    (study_dir / "aux_metrics.tsv").write_text("experiment\tmetric\tvalue\n", encoding="utf-8")
    import yaml

    contract: dict[str, Any] = yaml.safe_load((study_dir / "study.yaml").read_text(encoding="utf-8"))
    state = initial_state(study_dir, contract)
    atomic_write_json(study_dir / "study_state.json", state)
    append_event(study_dir, "study_created", study_id=slug, schema_version=2)
    return study_dir
