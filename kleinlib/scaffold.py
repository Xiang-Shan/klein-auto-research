"""Self-contained v2 study scaffolding used by ``klein new``.

Templates live HERE and only here, so the command works from an installed wheel
and nothing can drift. The card templates under ``.claude/skills/klein/assets``
are different animals: they are gate-authoring aids (data/method/findings), not
scaffold sources — ``assets/scouting-ledger-template.md`` documents the ledger's
shape and rationale for a human author, while :data:`SCOUTING_LEDGER` below is
what ``klein new`` actually writes (the engine never reads the skill directory).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .contract import (
    ENTRYPOINT_BY_KIND,
    KNOWN_KINDS,
    SUPPORTED_SCHEMA_VERSIONS,
    VALID_TRACK_MODES,
)
from .schema import KNOWN_MODALITIES, KNOWN_PROFILES
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
task_type: "{{TASK_TYPE}}"       # classification | regression | simulation
method_depth: "{{METHOD_DEPTH}}" # brief | full
family: "{{FAMILY}}"

# A track owns its metric frontier. Never compare unrelated research tasks globally.
tracks:
  {{TRACK}}:
    metric:
      name: "{{METRIC_NAME}}"
      goal: "{{METRIC_GOAL}}"     # higher | lower
      minimum_delta: {{MINIMUM_DELTA}}
      # noise_floor:                # measured at Phase 0, never guessed —
      #   k: 5                      # klein noise-floor prints this block
      #   std: ...
      #   range: ...
      #   estimand: marginal-resplit  # or paired-comparison — name WHICH
      #                             # question the floor answers (required once
      #                             # metric.bound is declared; measure both
      #                             # spreads before choosing)
      # bound:                      # arms the headroom (detection-limit) audit:
      #   ideal: 0.0                # best achievable score (0.0 brier/logloss,
      #                             # 1.0 auc); h = (incumbent - ideal) / delta
      #   on_infeasible: ack        # ack | warn | block when h < 1
    guardrails: {}

data:
  source: "{{DATA_SOURCE}}"
  prepared_path: "{{DATA_PATH}}"
  split:
    kind: {{SPLIT_KIND}}           # stratified | random | group | time | none (simulation)
    seed: 42
{{SPLIT_SIZES}}
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

#: Schema 3 keeps every schema-2 key and TYPES the inquiry on top of it: the
#: question's shape (``kind``), the evidence source's shape (``data.modality``),
#: and the audience (``profile``/``audience``).  Placeholders that CONSULT must
#: fill are left as ``{{...}}`` so the consult gate refuses an untyped contract.
STUDY_YAML_V3 = """\
schema_version: 3
study_id: "{{STUDY_ID}}"
goal: "{{GOAL}}"
domain: "{{DOMAIN}}"
target: "{{TARGET}}"

# The three axes (references/inquiry-model.md). kind fixes the default track
# mode, what "sealed" means, the confirmation default and the strength ceiling.
kind: "{{KIND}}"                  # predict | estimate | test | simulate | replicate | discover | optimize
{{PROFILE_LINE}}
audience: "{{AUDIENCE}}"

task_type: "{{TASK_TYPE}}"       # classification | regression | scalar (simulation is the old spelling)
method_depth: "{{METHOD_DEPTH}}" # brief | full
family: "{{FAMILY}}"

# The declared entrypoint. `mutable` is THE per-experiment surface — one
# falsifiable idea per candidate — and nothing else in the study may change
# inside a run. A declared verifier is never listed here.
entrypoint:
  command: ["uv", "run", "--locked", "python", "-u", "{{ENTRYPOINT}}"]
  mutable: ["{{ENTRYPOINT}}"]

# A track owns its metric frontier. Never compare unrelated research tasks globally.
tracks:
{{TRACK_BLOCK}}
data:
  source: "{{DATA_SOURCE}}"      # csv: | parquet: | synthetic: | bundled: | hub: | sklearn: | openml: | url:
  # sha256: "..."                # mandatory for openml: and url: — bytes that can change are pinned
  modality: "{{MODALITY}}"       # tabular | timeseries | image | sequence | graph | text | simulation | none
  prepared_path: "{{DATA_PATH}}"
  split:
    kind: {{SPLIT_KIND}}           # stratified | random | group | time | none (scalar)
    seed: {{SPLIT_SEED}}
{{SPLIT_SIZES}}
{{SPLIT_COLUMN}}
    # group_column: account_id     # required when kind=group
    # time_column: event_time      # required when kind=time

# Per-run, per-phase time, and experiment-count limits are intentionally separate.
max_run_seconds: {{MAX_RUN_SECONDS}}
phases:
  - id: adaptive-1
    description: "split-identity anchor, baseline, then bounded adaptive work"
    budget_seconds: 3600
    max_experiments: {{ADAPTIVE_EXPERIMENTS}}
  - id: confirmation
    description: "one sealed final-test evaluation per track"
    budget_seconds: 900
    max_experiments: {{CONFIRMATION_EXPERIMENTS}}

research_questions:
  - id: RQ1
    question: "{{RQ1_QUESTION}}"
    prior: "{{RQ1_PRIOR}}"

# Registered BEFORE the evidence exists; the consult gate hashes this file, so a
# prediction added later is visible as a gate re-record with a reason. Each
# carries an arithmetic rule on a printed key, or `manual: true` when no run can
# decide it. Operators: lt le gt ge ne abs_lt abs_le (value), eq (+ tol),
# within (target + tol), between (value: [low, high]); combine with all_of /
# any_of / not, at most three deep. `<`, `<=`, `>`, `>=`, `==`, `!=` also work.
# predictions:
#   - id: P1
#     track: {{TRACK}}
#     statement: "{{LEVER_1}} moves {{METRIC_NAME}} by {{DELTA_1}}"
#     rule: {key: primary_metric, op: ">=", value: 0.0}
#     inconclusive_if: "the run crashes before the evaluator prints"

# confirmation:
#   require: [sealed]            # sealed | replicate | verify (default: by kind)
# stop:
#   max_consecutive_discards: 5  # end a losing phase on the record; klein stop ack
#   scope: track
# materiality:                   # "material"/"actionable" is priced or absent
#   currency: EUR
#   unit: "per policy-year"
#   threshold: 0.0
#   priced_by: "<who>"
#   priced_on: "<yyyy-mm-dd>"
#   basis: "<at least 40 characters saying what was priced, on what data, under which assumptions>"
#   applies_to: "<the decision this bar governs>"

deliverables:
  - findings.md
  - claims.lock
  - report/index.html
"""

#: One track's block inside ``STUDY_YAML_V3``.  Rendered once per ``--track``.
TRACK_BLOCK_V3 = """\
  {{TRACK}}:
    mode: {{TRACK_MODE}}          # frontier (climbs an incumbent) | registered (measures a cell)
    metric:
      name: "{{METRIC_NAME}}"
      goal: "{{METRIC_GOAL}}"     # higher | lower
      minimum_delta: {{MINIMUM_DELTA}}
      exactness: stochastic       # exact for an integer/closed-form objective
      # exactness_note: "..."     # required when exactness is exact: the objective's resolution
      # noise_floor:                # measured at Phase 0, never guessed —
      #   k: 5                      # klein noise-floor prints this block
      #   std: ...
      #   range: ...
      #   estimand: marginal-resplit  # or paired-comparison
      # fit_noise:                  # the k-seed spread, recorded SEPARATELY so it
      #   k: 5                      # can never be pasted in as a keep bar
      #   std: ...
      # bound:                      # arms the headroom (detection-limit) audit:
      #   ideal: 0.0                # best achievable score; h = (incumbent - ideal) / delta
      #   on_infeasible: ack        # ack | warn | block when h < 1
      # incumbent_external:         # beat the literature, not just yourself
      #   value: ...
      #   source: "<citation>"
      #   verified_on: "<yyyy-mm-dd>"
    guardrails: {}
{{VERIFIER_BLOCK}}"""

#: The commented hint every non-``optimize`` track carries.
VERIFIER_HINT = """\
    # verifier:                   # REQUIRED for kind: optimize, recommended for
    #   command: ["uv", "run", "--locked", "python", "-u", "verify.py"]
    #   tolerance: 0.0            # checkpoint-scored DL and simulator-scored
    #   artifact_key: solution    # designs. Outside mutable[]; hashed at METHOD;
    #                             # ITS number decides the run.
"""

#: Rendered instead, uncommented, when the kind is ``optimize`` — where the
#: verifier is not optional and a scaffold without one cannot validate.
VERIFIER_BLOCK = """\
    verifier:                     # the checker is NEVER the searcher: this script
      command: ["uv", "run", "--locked", "python", "-u", "verify.py"]
      tolerance: 0.0              # is outside mutable[], is hashed at the METHOD
      artifact_key: solution      # gate, and ITS number decides the disposition.
"""

#: Schema 3 only, spliced into ``PROGRAM`` as ``{{ROSTER}}``. The referee reads
#: this table for the independence rung (``references/referee-protocol.md``);
#: nothing else in a study says what model or tool ran the loop, so a blank
#: experimenter row caps the rung at "fresh session".
ROSTER = """\

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| experimenter | | |
| data-gate auditor | | |
| referee | | |
| lead | (the human who owns this study) | {{DATE}} |
"""

PROGRAM = """\
# Program — {{STUDY_ID}}
{{ROSTER}}
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
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Decisions (append-only)

- {{DATE}} — schema-v2 study scaffolded; gates pending.
## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
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

#: Schema 3 only: the pre-registration disclosure the consult gate hashes. It
#: ships SCAFFOLDED (not copied by hand from ``assets/scouting-ledger-template.md``)
#: so that every new study has one and the gate's hash is the norm rather than the
#: exception — and it ships placeholder-free, because an unresolved ``{{…}}`` in a
#: hashed gate artifact is refused at ``klein gate record consult``.
SCOUTING_LEDGER = """\
---
type: scouting-ledger
study: "{{STUDY_ID}}"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — {{STUDY_ID}}

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

Nothing was computed, read, or plotted before this contract was written — the study
was scaffolded first and its questions typed from the brief alone. Replace this
paragraph the moment that stops being true: values seen before the gate may seed
anchors and identity checks; they may never be scored predictions.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| — | {{DATE}} | nothing scouted before the gate | — | — | — |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥.
"""

PLAYBOOK = """\
# Playbook — {{STUDY_ID}}

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. (fill at the phase-start slate ritual)
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
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)


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
            "train.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
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


#: The non-``predict`` entrypoints.  ``train.py`` fits and grades a model;
#: ``analyze.py`` / ``simulate.py`` / ``search.py`` compute ONE number and print
#: the canonical block for it, which is all the notary reads.  The guard rail and
#: the smoke-mode contract are identical in all four — only the middle changes.
ENTRYPOINT_STUB = '''\
"""{{ENTRYPOINT_DOC}}

This is the per-experiment mutable surface declared in study.yaml:entrypoint.
ONE falsifiable idea per candidate; `klein run-one` commits it before it runs.
"""

from __future__ import annotations

import os
import time

from kleinlib.eval import evaluate_scalar

RANDOM_SEED = 42
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("{{TRACK}}" if SMOKE else None)


def load_partition(evaluation_kind: str):
    """Select development or the sealed partition — explicitly, from the contract.

    `kleinlib.data.contract_split(study_dir)` / `load_partition(kind)` read
    study.yaml:data.split and print the `split_fingerprint:` line the notary
    checks. A literal split seed here is a DATA-gate BLOCKER (war story 8).
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    raise NotImplementedError("read the partition from the contract, never from a literal seed")


def {{ENTRYPOINT_FUNC}}(data) -> float:
    """{{ENTRYPOINT_FUNC_DOC}}"""
    raise NotImplementedError("{{ENTRYPOINT_FUNC_TODO}}")


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
            "{{ENTRYPOINT}} must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python {{ENTRYPOINT}}` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )
    data = load_partition(evaluation_kind)
    value = {{ENTRYPOINT_FUNC}}(data)
    evaluate_scalar(
        value,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="{{METRIC_NAME}}",
        metric_goal="{{METRIC_GOAL}}",
    )


if __name__ == "__main__":
    main()
'''

#: The declared verifier `klein new --kind optimize` writes.  It lives OUTSIDE
#: ``entrypoint.mutable``, is hashed into ``state.fingerprints.verifier`` at the
#: METHOD gate, and never changes again: an objective a search reports about
#: itself is not evidence.
VERIFY = '''\
"""The declared verifier — the checker, never the searcher.

`klein run-one` runs this as a second bounded subprocess after the entrypoint
exits, with KLEIN_ARTIFACT pointing at the artifact the search produced, and
decides the run on the number THIS script prints. It is outside
study.yaml:entrypoint.mutable and is hashed at the METHOD gate: once E0001 has
run, a change here is refused.
"""

from __future__ import annotations

import os
import time

from kleinlib.eval import evaluate_scalar


def check(artifact_path: str) -> float:
    """Independently score the artifact; raise on an invalid one.

    Give it a positive control (a hand-planted invalid object it must reject)
    and a negative control (a known-valid object it must accept) in the DATA
    gate's verifier card.
    """
    raise NotImplementedError("verify the artifact and return its objective value")


def main() -> None:
    t0 = time.time()
    artifact_path = os.environ.get("KLEIN_ARTIFACT")
    if not artifact_path:
        raise RuntimeError(
            "verify.py is run by `klein run-one`, which sets KLEIN_ARTIFACT to the "
            "artifact the entrypoint declared."
        )
    evaluate_scalar(
        check(artifact_path),
        exp_id=os.environ.get("KLEIN_EXPERIMENT_ID", "VERIFY"),
        study_dir=".",
        t0=t0,
        metric_name="{{METRIC_NAME}}",
        metric_goal="{{METRIC_GOAL}}",
    )


if __name__ == "__main__":
    main()
'''

#: Per-kind wording for :data:`ENTRYPOINT_STUB`.
ENTRYPOINT_WORDING: dict[str, dict[str, str]] = {
    "analyze.py": {
        "ENTRYPOINT_DOC": "Compute the estimate or test statistic this cell registers.",
        "ENTRYPOINT_FUNC": "analyze",
        "ENTRYPOINT_FUNC_DOC": "Return the one number this cell measures.",
        "ENTRYPOINT_FUNC_TODO": "compute the estimand (with its uncertainty) or the test statistic",
    },
    "simulate.py": {
        "ENTRYPOINT_DOC": "Run the declared DGP and measure how well the method recovers it.",
        "ENTRYPOINT_FUNC": "simulate",
        "ENTRYPOINT_FUNC_DOC": "Return the recovery criterion the DGP card defines.",
        "ENTRYPOINT_FUNC_TODO": "draw from the declared truth and score the recovery",
    },
    "search.py": {
        "ENTRYPOINT_DOC": "Search for the object the verifier will grade.",
        "ENTRYPOINT_FUNC": "search",
        "ENTRYPOINT_FUNC_DOC": (
            "Write the candidate artifact and return the searcher's own score.\n\n"
            "    The DISPOSITION comes from the declared verifier's number, not this\n"
            "    one — the checker is never the searcher."
        ),
        "ENTRYPOINT_FUNC_TODO": "construct a candidate, write it out, and print its artifact: line",
    },
}


def _quote_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def _normalize_tracks_argument(
    tracks: Sequence[str] | str | None, default_mode: str
) -> list[tuple[str, str]]:
    """``["primary", "control:registered"]`` -> ``[("primary", "frontier"), ...]``."""
    if tracks is None:
        tracks = ["primary"]
    elif isinstance(tracks, str):
        tracks = [tracks]
    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in tracks:
        name, _, mode = str(raw).partition(":")
        mode = mode or default_mode
        if not IDENTIFIER_RE.fullmatch(name):
            raise ValueError(f"track must be a safe identifier: {name!r}")
        if mode not in VALID_TRACK_MODES:
            raise ValueError(f"track mode must be frontier or registered: {raw!r}")
        if name in seen:
            raise ValueError(f"duplicate track: {name!r}")
        seen.add(name)
        parsed.append((name, mode))
    if not parsed:
        raise ValueError("at least one track is required")
    return parsed


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
    split_seed: int = 42,
    group_column: str | None = None,
    time_column: str | None = None,
    max_run_seconds: int = 600,
    schema_version: int = 2,
    kind: str | None = None,
    modality: str | None = None,
    profile: str | None = None,
    profile_doc: str | None = None,
    audience: str | None = None,
    tracks: Sequence[str] | None = None,
) -> Path:
    """Write one study directory from the templates in THIS module.

    ``schema_version`` selects the contract shape.  The Python default stays 2
    so the frozen schema-2 fixtures keep scaffolding schema-2 studies unchanged;
    ``klein new`` passes 3, which is the default the docs promise for a NEW
    study.  Schema 3 additionally types the inquiry (``kind``, ``modality``,
    ``profile``/``profile_doc``, ``audience``), names the entrypoint by kind, and
    accepts repeatable ``tracks`` as ``NAME[:MODE]``.
    """
    from .eval import get_metric_spec

    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError("schema_version must be 2 or 3")
    schema_3 = schema_version >= 3
    if not STUDY_ID_RE.fullmatch(slug):
        raise ValueError("study id must match NN-lowercase-slug")
    if schema_3:
        if kind is not None and kind not in KNOWN_KINDS:
            raise ValueError(f"kind must be one of {list(KNOWN_KINDS)}")
        if modality is not None and modality not in KNOWN_MODALITIES:
            raise ValueError(f"modality must be one of {list(KNOWN_MODALITIES)}")
        if profile is not None and profile not in KNOWN_PROFILES:
            raise ValueError(f"profile must be one of {list(KNOWN_PROFILES)}")
        if profile is not None and profile_doc is not None:
            raise ValueError("give profile or profile_doc, not both")
        if profile_doc is not None and not str(profile_doc).endswith(".md"):
            raise ValueError("profile_doc must point at a .md file")
    else:
        if any(v is not None for v in (kind, modality, profile, profile_doc, audience)):
            raise ValueError(
                "kind, modality, profile, profile_doc and audience are schema-3 "
                "options — pass schema_version=3"
            )
        if tracks is not None and (len(tracks) > 1 or ":" in str(tracks[0] if tracks else "")):
            raise ValueError(
                "multi-track scaffolding and NAME:MODE are schema-3 options — pass "
                "schema_version=3 (a schema-2 study adds tracks by editing study.yaml)"
            )
        if split_seed != 42:
            raise ValueError("--split-seed is a schema-3 option — pass schema_version=3")
    # `kind` fixes the default track mode: predict and optimize climb a
    # frontier; every registered kind measures cells (references/inquiry-model.md).
    default_mode = "registered" if kind in {"estimate", "test", "simulate", "replicate", "discover"} else "frontier"
    track_specs = _normalize_tracks_argument(tracks or [track], default_mode)
    track = track_specs[0][0]
    if task_type not in {"classification", "regression", "simulation"} | (
        {"scalar"} if schema_3 else set()
    ):
        raise ValueError(
            "task_type must be classification, regression, or simulation"
            + (" (or scalar)" if schema_3 else "")
        )
    if method_depth not in {"brief", "full"}:
        raise ValueError("method_depth must be brief or full")
    scalar_family = task_type in {"simulation", "scalar"}
    if split_kind is None:
        if scalar_family:
            split_kind = "none"
        else:
            split_kind = "stratified" if task_type == "classification" else "random"
    allowed_kinds = {"stratified", "random", "group", "time"}
    if scalar_family:
        allowed_kinds = allowed_kinds | {"none"}
    if split_kind not in allowed_kinds:
        raise ValueError(
            "split_kind must be stratified, random, group, or time"
            + (" (or none)" if scalar_family else "")
        )
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
            task="scalar" if scalar_family else task_type,
            allow_custom=scalar_family,
        )
        metric_goal = spec.goal
    elif metric_goal is not None:
        raise ValueError("metric_name is required when metric_goal is supplied")
    entrypoint = ENTRYPOINT_BY_KIND.get(kind or "predict", "train.py") if schema_3 else "train.py"
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
        # CSV by default: writable with core deps alone (parquet needs the optional
        # pyarrow extra; opt in via --prepared-path *.parquet).
        "DATA_PATH": _quote_text(data_path or "data/prepared/prepared.csv"),
        "SPLIT_KIND": split_kind,
        "SPLIT_SEED": str(int(split_seed)),
        "SPLIT_SIZES": (
            f"    # kind none: comparability comes from fixed seed blocks inside {entrypoint};\n"
            "    # the sealed final test is a pre-registered fresh-seed block\n"
            "    # (run-one sets KLEIN_EVALUATION_KIND=final_test)."
            if split_kind == "none"
            else "    development_size: 0.20\n    test_size: 0.20"
        ),
        "SPLIT_COLUMN": (
            f'    group_column: "{_quote_text(group_column)}"'
            if split_kind == "group" and group_column
            else f'    time_column: "{_quote_text(time_column)}"'
            if split_kind == "time" and time_column
            else ""
        ),
        "MAX_RUN_SECONDS": str(int(max_run_seconds)),
        # Schema 2 renders the roster line away entirely, so its program.md stays
        # byte-identical to the frozen shape every schema-2 fixture pins.
        "ROSTER": "",
        "RQ1_QUESTION": "{{RQ1_QUESTION}}",
        "RQ1_PRIOR": "{{RQ1_PRIOR}}",
        "LEVER_1": "{{LEVER_1}}",
        "DELTA_1": "{{DELTA_1}}",
        "ENTRYPOINT": entrypoint,
    }
    if schema_3:
        values.update(
            {
                "ROSTER": _render(ROSTER, values),
                "KIND": kind or "{{KIND}}",
                "MODALITY": modality or "{{MODALITY}}",
                "PROFILE_LINE": (
                    f"profile_doc: {profile_doc}   # a repo-local profile of your own"
                    if profile_doc is not None
                    else f'profile: "{profile or "{{PROFILE}}"}"'
                    "            # generic | ml-research | math | insurance\n"
                    "# profile_doc: profiles/my-field.md   # ... or a repo-relative profile of your own"
                ),
                "AUDIENCE": _quote_text(audience or "{{AUDIENCE}}"),
                # The final phase must have room for one sealed run per track.
                "ADAPTIVE_EXPERIMENTS": str(max(4, len(track_specs))),
                "CONFIRMATION_EXPERIMENTS": str(len(track_specs)),
                "TRACK_BLOCK": "".join(
                    _render(
                        TRACK_BLOCK_V3,
                        {
                            **values,
                            "TRACK": name,
                            "TRACK_MODE": mode,
                            # `optimize` cannot validate without one, so it is
                            # scaffolded real, not as a comment.
                            "VERIFIER_BLOCK": (
                                VERIFIER_BLOCK if kind == "optimize" else VERIFIER_HINT
                            ),
                        },
                    )
                    for name, mode in track_specs
                ),
            }
        )

    study_dir.mkdir(parents=True)
    for dirname in ("figures", "models", "report", "runs", "sweeps"):
        (study_dir / dirname).mkdir()
        if dirname != "runs":
            (study_dir / dirname / ".gitkeep").write_text("", encoding="utf-8")
    entrypoint_template = (
        TRAIN
        if entrypoint == "train.py"
        else _render(ENTRYPOINT_STUB, ENTRYPOINT_WORDING[entrypoint])
    )
    files = {
        "study.yaml": STUDY_YAML_V3 if schema_3 else STUDY_YAML,
        "program.md": PROGRAM,
        "playbook.md": PLAYBOOK,
        "research_plan.md": RESEARCH_PLAN,
        "prepare.py": PREPARE,
        entrypoint: entrypoint_template,
    }
    if schema_3:
        # Every schema-3 study starts with a ledger, so the consult gate's hash of
        # it (kleinlib.contract.GATE_OPTIONAL_ARTIFACTS) is the norm, not the
        # exception. Schema 2 keeps its frozen file set.
        files["scouting_ledger.md"] = SCOUTING_LEDGER
    if schema_3 and kind == "optimize":
        files["verify.py"] = VERIFY
    for name, template in files.items():
        (study_dir / name).write_text(_render(template, values), encoding="utf-8")
    (study_dir / "results.tsv").write_text("\t".join(V2_RESULTS_COLUMNS) + "\n", encoding="utf-8")
    (study_dir / "aux_metrics.tsv").write_text("experiment\tmetric\tvalue\n", encoding="utf-8")
    import yaml

    contract: dict[str, Any] = yaml.safe_load((study_dir / "study.yaml").read_text(encoding="utf-8"))
    state = initial_state(study_dir, contract)
    atomic_write_json(study_dir / "study_state.json", state)
    append_event(study_dir, "study_created", study_id=slug, schema_version=schema_version)
    return study_dir
