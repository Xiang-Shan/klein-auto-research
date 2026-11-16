"""``klein demo`` -- a real study, first half of the lifecycle, live and offline.

One command creates a tiny ``predict . tabular . generic`` study in a fresh git
repository and walks the first half of the lifecycle with REAL transactions:
scaffold, one probe, the three gates, the Phase-0 noise floor, and three
``run-one`` candidates.  Nothing is simulated: every gate goes through
:func:`kleinlib.state.record_gate`, every run through
:func:`kleinlib.workflow.run_one`, every probe through
:func:`kleinlib.probe.run_probe`.  If an engine function refuses, the demo fails
loudly; it never overrides a gate.

What it deliberately does NOT do: spend the sealed partition, write findings,
lock claims, referee, finalize, or build the report.  Those are the second half of
a real study, and ``klein next`` names them.

The only things the driver authors are the *judgment* files a person would write
(the question, the predictions, the data card, the method card); they ship inside
the package (``kleinlib/demo_files``) and are read with :mod:`importlib.resources`.
The gate acknowledgements say, verbatim, that a program and not a person gave them.
"""

from __future__ import annotations

import contextlib
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Iterator
from importlib import resources
from pathlib import Path
from typing import Any

from .errors import WorkflowError

__all__ = ["ACKNOWLEDGED_BY", "SLUG", "run_demo"]

SLUG = "01-demo"
BRANCH = f"experiments/{SLUG}"
ACKNOWLEDGED_BY = "klein demo (automated walkthrough — in a real study a person acknowledges each gate)"
SPLIT_SEED = 20260101
STEPS = 8

GOAL = (
    "How much does a 30-feature logistic model beat a one-feature baseline at telling "
    "malignant from benign tumours, on the Wisconsin breast-cancer table?"
)
QUESTION = (
    "Does a standardized logistic regression on all 30 measurements clear val_auc 0.97 "
    "where a one-feature baseline cannot, and do degree-2 interactions then add anything "
    "beyond the measured floor?"
)
AUDIENCE = "a newcomer watching their first Klein study run, in a few minutes"

_GITIGNORE = """\
# Prepared data and local model blobs are never committed (klein verify re-derives them).
data/
**/data/prepared/
__pycache__/
*.pyc
.klein.lock
*.pkl
*.pickle
*.joblib
predictions/
"""

_PREDICTIONS = """\
predictions:
  - id: P1
    track: primary
    statement: "a standardized logistic regression on all 30 features reaches val_auc above 0.97 on the development partition"
    rule: {key: primary_metric, op: ">", value: 0.97}
    inconclusive_if: "the run crashes before the evaluator prints"
  - id: P2
    track: primary
    statement: "adding every degree-2 interaction to that model beats it by more than one measured floor of val_auc, on the same rows"
    rule: {key: delta_in_floors, op: ">", value: 1}
    inconclusive_if: "minimum_delta is still 0, so train.py prints no delta_in_floors line"
"""

_SLATE = """\
### Phase adaptive-1 slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | one-feature logistic on `mean_radius` -- the anchor every later rung is read against | 1 | 3 | 3 | 7 |
| 2 | standardized logistic on all 30 features -- registered as P1 (val_auc above 0.97) | 1 | 3 | 3 | 7 |
| 3 | all degree-2 interactions of the 30 features -- registered as P2 (more than one floor of lift) | 2 | 3 | 3 | 8 |
| 4 | a depth-limited tree on the 30 features -- NOT run in this demo; left for the next phase | 2 | 3 | 2 | 7 |
"""


# --------------------------------------------------------------------------
# narration
# --------------------------------------------------------------------------


class _Narrator:
    """Plain-language transcript.  ``echo=False`` makes every method a no-op."""

    def __init__(self, echo: bool) -> None:
        self.echo = echo

    def _print(self, text: str = "") -> None:
        if self.echo:
            print(text, flush=True)

    def header(self, number: int, title: str, why: str) -> None:
        self._print()
        self._print(f"[{number}/{STEPS}] {title}")
        for line in textwrap.wrap(why, 94):
            self._print(f"  {line}")

    def cmd(self, command: str) -> None:
        self._print(f"  $ {command}")

    def out(self, text: str) -> None:
        for raw in text.splitlines():
            for line in textwrap.wrap(raw, 92, subsequent_indent="      ") or [""]:
                self._print(f"    {line}")

    def plain(self, text: str) -> None:
        self._print(text)


# --------------------------------------------------------------------------
# environment, git and subprocess helpers
# --------------------------------------------------------------------------


@contextlib.contextmanager
def _same_interpreter() -> Iterator[None]:
    """Make ``python`` resolve to THIS interpreter for every child process.

    The contract writes the plain command ``python -u train.py`` (the contract
    validator refuses absolute paths there, and a pip-installed Klein has no ``uv``).
    Prepending the running interpreter's directory to PATH is ordinary environment
    setup: it guarantees the children import the same ``kleinlib`` and scikit-learn
    that the notary is running with.
    """
    exe = Path(sys.executable)
    names = ("python.exe", "python") if os.name == "nt" else ("python",)
    shim: Path | None = None
    if any((exe.parent / name).exists() for name in names):
        bin_dir = exe.parent
    else:  # e.g. only `python3` on this interpreter's directory: a tiny launcher
        shim = Path(tempfile.mkdtemp(prefix="klein-demo-bin-"))
        launcher = shim / "python"
        launcher.write_text(f'#!/bin/sh\nexec "{exe}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
        bin_dir = shim
    previous = os.environ.get("PATH")
    os.environ["PATH"] = str(bin_dir) + os.pathsep + (previous or "")
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = previous
        if shim is not None:
            shutil.rmtree(shim, ignore_errors=True)


@contextlib.contextmanager
def _engine_notes(say: _Narrator) -> Iterator[None]:
    """Capture what an engine call prints; show it indented under the command (or drop it)."""
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            yield
    finally:
        for line in buffer.getvalue().splitlines():
            say.out(line)


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        raise WorkflowError(f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}")
    return result.stdout.strip()


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    if _git(repo, "status", "--porcelain"):
        _git(repo, "commit", "-q", "-m", message)


def _child(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one helper the way the docs do (`python -u ...`), as a real subprocess."""
    env = dict(os.environ)
    env.pop("KLEIN_SMOKE", None)
    result = subprocess.run(
        [sys.executable, "-u", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise WorkflowError(
            f"`python {' '.join(args)}` failed (exit {result.returncode}): "
            f"{(result.stderr or result.stdout).strip()[-600:]}"
        )
    return result


def _asset(name: str) -> str:
    return (resources.files("kleinlib") / "demo_files" / name).read_text(encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _replace(text: str, old: str, new: str, *, what: str) -> str:
    if old not in text:
        raise WorkflowError(f"the scaffold no longer contains the {what} the demo fills in")
    return text.replace(old, new, 1)


def _ensure_empty(target: Path) -> None:
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise WorkflowError(
            f"{target} already exists and is not empty: `klein demo` builds a fresh study "
            "and never writes into a directory that has content — pass --dir <new path>"
        )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    # Always the demo's own repository (nested if the parent directory is one too):
    # the notary switches branches and commits, and must never do that to your work.
    _git(repo, "init", "-q")
    for key, value in (("user.name", "Klein demo"), ("user.email", "klein-demo@example.invalid")):
        if not _git(repo, "config", "--get", key, check=False):
            _git(repo, "config", key, value)  # repo-local only, and only when git has none
    (repo / ".gitignore").write_text(_GITIGNORE, encoding="utf-8")
    _commit_all(repo, "klein demo: repository skeleton")
    _git(repo, "switch", "-q", "-c", BRANCH)


# --------------------------------------------------------------------------
# the study's judgment files
# --------------------------------------------------------------------------


def _probe_facts(log_text: str) -> dict[str, Any]:
    balance = re.search(r"class balance: ([\d.]+)% benign", log_text)
    tops = re.findall(r"top correlation with target: (\S+) r=([+-][\d.]+)", log_text)
    if not balance or not tops:
        raise WorkflowError("the probe's log did not carry the lines the demo reads back")
    return {
        "benign_pct": balance.group(1),
        "top": [(name, float(value)) for name, value in tops],
        "lines": [ln for ln in log_text.splitlines() if ln.startswith(("train rows", "class", "top"))],
    }


def _fill_consult(study: Path, today: str, facts: dict[str, Any]) -> None:
    top_name, top_r = facts["top"][0]
    yaml_path = study / "study.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    text = _replace(text, "{{RQ1_QUESTION}}", QUESTION, what="RQ1 question placeholder")
    prior = (
        f"yes, by a wide margin: the probe saw no single feature separate the classes "
        f"(strongest |r| = {abs(top_r):.2f}, {top_name}), so thirty should clear 0.97; "
        "interactions are doubtful with only a few hundred rows (source: scouted)"
    )
    text = _replace(text, "{{RQ1_PRIOR}}", prior, what="RQ1 prior placeholder")
    text, n = re.subn(r"# predictions:\n(?:#   .*\n)+", lambda _m: _PREDICTIONS, text, count=1)
    if not n:
        raise WorkflowError("the scaffold no longer carries its commented predictions example")
    yaml_path.write_text(text, encoding="utf-8")

    program = study / "program.md"
    text = program.read_text(encoding="utf-8")
    text = _replace(
        text,
        "| experimenter | | |",
        f"| experimenter | klein demo driver (kleinlib.demo — a program, not a model) | {today} |",
        what="experimenter roster row",
    )
    text = _replace(
        text,
        "| data-gate auditor | | |",
        f"| data-gate auditor | klein demo driver (kleinlib.leakage audit output) | {today} |",
        what="auditor roster row",
    )
    text = _replace(
        text,
        "| referee | | |",
        "| referee | none yet — a real study hands this to a fresh context on another model | — |",
        what="referee roster row",
    )
    text = re.sub(
        r"### Phase <id> slate\n\n\| # .*\n\| --- .*\n", lambda _m: _SLATE, text, count=1
    )
    program.write_text(text, encoding="utf-8")

    ledger = study / "scouting_ledger.md"
    text = ledger.read_text(encoding="utf-8")
    text, n = re.subn(
        r"(## §0 Disclosure\n\n).*?(\n\n## Entries)",
        lambda m: m.group(1)
        + "Before this contract was written the study was scaffolded, `prepare.py` wrote the "
        "table, and ONE probe (X0001, `look.py`) read the TRAIN rows only: the class balance and "
        "the three strongest single-feature correlations. The sealed partition was never read. "
        "The probe's numbers seeded the prior of RQ1 (labelled `source: scouted`); no "
        "registered prediction quotes them."
        + m.group(2),
        text,
        count=1,
        flags=re.DOTALL,
    )
    if not n:
        raise WorkflowError("the scouting ledger no longer has a Disclosure section to fill")
    seen = "; ".join(
        [f"{facts['benign_pct']}% benign"] + [f"{n} r={r:+.2f}" for n, r in facts["top"]]
    )
    text, n = re.subn(
        r"\| — \| \S+ \| nothing scouted before the gate \|[^\n]*\n",
        lambda _m: f"| S1 | {today} | probe X0001: `look.py` on train rows | {seen} | a lead, "
        "not evidence: no run produced it, no claim can cite it | seeded the RQ1 prior only |\n",
        text,
        count=1,
    )
    if not n:
        raise WorkflowError("the scouting ledger no longer has its placeholder entry row")
    ledger.write_text(text, encoding="utf-8")


def _write_data_card(study: Path, leakage: str) -> dict[str, str]:
    import pandas as pd
    import yaml

    from .data import contract_split

    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    frame = pd.read_csv(study / contract["data"]["prepared_path"])
    features = frame.drop(columns=["target"])
    X_train, X_dev, X_test, *_ = contract_split(study)
    values = {
        "ROWS": str(len(frame)),
        "FEATURES": str(features.shape[1]),
        "SEED": str(contract["data"]["split"]["seed"]),
        "TRAIN": str(len(X_train)),
        "DEV": str(len(X_dev)),
        "TEST": str(len(X_test)),
        "MISSING": "none" if int(frame.isna().sum().sum()) == 0 else f"{int(frame.isna().sum().sum())} cells",
        "CONSTANT": "none" if not (features.nunique() <= 1).any() else "present",
        "BENIGN": f"{float((frame['target'] == 1).mean()):.1%}",
        "LEAKAGE": leakage.strip(),
    }
    text = _asset("data_card.md.tmpl")
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", value)
    (study / "data_card.md").write_text(text, encoding="utf-8")
    return values


def _paste_floor(study: Path) -> dict[str, Any]:
    """Phase 0: the engine's own floor block, pasted into the contract."""
    from .noise_floor import floor_from_sidecar, resolve_estimand, yaml_block

    sidecar = study / "sweeps" / "split_lottery.sidecar.tsv"
    floor = floor_from_sidecar(sidecar)
    estimand = resolve_estimand("split-lottery", "marginal-resplit")
    block = yaml_block(
        "primary",
        floor,
        source="sweeps/split_lottery.sidecar.tsv",
        method="split-lottery",
        estimand=estimand,
    )
    pasteable = "".join(ln + "\n" for ln in block.splitlines() if ln.startswith("      "))
    path = study / "study.yaml"
    text = _replace(
        path.read_text(encoding="utf-8"),
        "      minimum_delta: 0\n",
        pasteable,
        what="primary track `minimum_delta: 0` line",
    )
    path.write_text(text, encoding="utf-8")
    return {
        "estimand": estimand,
        "recipe": "split-lottery",
        "k": floor.k,
        "mean": round(floor.mean, 6),
        "std": round(floor.std, 6),
        "range": round(floor.value_range, 6),
        "minimum_delta": float(f"{floor.suggested_minimum_delta:.6g}"),
    }


def _append_decisions(study: Path, today: str, runs: list[dict[str, Any]], floor: dict[str, Any]) -> None:
    metric = {row["experiment"]: row["primary_metric"] for row in runs}
    delta = _read_json(study / "runs" / "E0003" / "manifest.json")["metrics"].get(
        "delta_in_floors", "NA"
    )
    lines = [
        f"- {today} — Note: E0001 (the anchor, one feature) scored {metric['E0001']}; the first run "
        "of a frontier track is a keep by construction. Every later rung is read against it.",
        f"- {today} — Decision: P1 stands and the 30-feature model is the incumbent. E0002 scored "
        f"{metric['E0002']}, a keep, and the notary's arithmetic supports P1 (val_auc above 0.97).",
        f"- {today} — Decision: P2 is refuted by E0003, so drop interactions from this table's "
        f"ladder. E0003 scored {metric['E0003']} and was discarded; its paired lift over the plain "
        f"30-feature model was {delta} measured floors (floor {floor['minimum_delta']}, "
        "sweep:split_lottery). With 495 columns on a few hundred rows they add variance, as the "
        "method card warned.",
    ]
    program = study / "program.md"
    text = program.read_text(encoding="utf-8")
    marker = "\n\n## Phase slates"
    if marker not in text:
        raise WorkflowError("program.md lost its '## Phase slates' heading")
    text = text.replace(marker, "\n" + "\n".join(lines) + marker, 1)
    program.write_text(text, encoding="utf-8")

    playbook = study / "playbook.md"
    text = playbook.read_text(encoding="utf-8")
    text = text.replace(
        "| Track | Exp | Metric | Config one-liner | Held since |\n| --- | --- | --- | --- | --- |\n",
        "| Track | Exp | Metric | Config one-liner | Held since |\n| --- | --- | --- | --- | --- |\n"
        f"| primary | E0002 | {metric['E0002']} | standardized logistic, all 30 features | {today} |\n",
        1,
    )
    text = text.replace(
        "| Direction | Evidence (exp IDs) | Why it lost (one line) |\n| --- | --- | --- |\n",
        "| Direction | Evidence (exp IDs) | Why it lost (one line) |\n| --- | --- | --- |\n"
        "| degree-2 interactions on all 30 features | E0003 | 495 columns on a few hundred "
        "rows: a lift smaller than the measured floor (P2 refuted) |\n",
        1,
    )
    text = text.replace(
        "1. (fill at the phase-start slate ritual)",
        "1. a depth-limited tree on the 30 features (slate candidate 4) -- not run in the demo\n"
        "2. the sealed confirmation run of the incumbent (E0002's configuration)",
        1,
    )
    playbook.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# the driver
# --------------------------------------------------------------------------


def run_demo(target: Path, *, echo: bool = True) -> dict[str, Any]:
    """Run the demo in ``target`` (must not exist, or be empty); return a summary dict."""
    started = time.time()
    target = Path(target).expanduser().resolve()
    _ensure_empty(target)
    say = _Narrator(echo)
    with _same_interpreter():
        return _run(target, say, started)


def _run(target: Path, say: _Narrator, started: float) -> dict[str, Any]:
    from .cli_sweep import register_sweep
    from .contract import load_contract
    from .next_step import format_next, next_step
    from .probe import probe_head, read_probes, run_probe
    from .recipes import apply_recipe, recipe_defaults
    from .scaffold import apply_runner, scaffold_study
    from .state import record_gate
    from .study_map import build_map, format_map
    from .workflow import preflight_checks, run_one, status_summary, verify_study

    today = datetime.date.today().isoformat()
    repo = target
    study = repo / "studies" / SLUG
    rel = f"studies/{SLUG}"
    say.plain(f"klein demo -- a real study in {repo}")
    say.plain(
        "Everything below is the real engine on real data (scikit-learn's bundled breast-cancer "
        "table, offline). The three gates are acknowledged by this program and say so on the record."
    )

    # 1 -- scaffold ---------------------------------------------------------
    say.header(
        1,
        "SCAFFOLD -- a typed study in its own git repository",
        "A study is a directory with a machine-readable contract (study.yaml), a lab notebook "
        "(program.md) and an empty ledger, on its own branch. This one asks a predict question "
        "about a table.",
    )
    say.cmd(f"git init && git switch -c {BRANCH}")
    _init_repo(repo)
    say.cmd(
        f'klein new {SLUG} --recipe tabular-predict --runner python --split-seed {SPLIT_SEED} '
        '--goal "<the question>"'
    )
    defaults = recipe_defaults("tabular-predict")
    study = scaffold_study(
        repo / "studies",
        SLUG,
        goal=GOAL,
        domain="medical diagnostics",
        target=defaults["target"],
        task_type=defaults["task_type"],
        family=defaults["family"],
        metric_name=defaults["metric_name"],
        metric_goal=defaults["metric_goal"],
        data_source=defaults["data_source"],
        data_path=defaults["data_path"],
        split_kind=defaults["split_kind"],
        split_seed=SPLIT_SEED,
        max_run_seconds=defaults["max_run_seconds"],
        kind=defaults["kind"],
        modality=defaults["modality"],
        profile=defaults["profile"],
        audience=AUDIENCE,
    )
    written = apply_recipe(study, "tabular-predict", split_seed=SPLIT_SEED)
    apply_runner(study, "python")
    contract = load_contract(study)
    kind, modality, profile = contract["kind"], contract["data"]["modality"], contract["profile"]
    say.out(
        f"scaffolded {rel}: {kind} . {modality} . {profile}; recipe wrote {', '.join(written)}"
    )
    say.out(f"entrypoint: {' '.join(contract['entrypoint']['command'])} (the interpreter running this demo)")
    _commit_all(repo, f"{SLUG}: scaffold")

    # 2 -- look (probe) -----------------------------------------------------
    say.header(
        2,
        "LOOK -- one probe, on the record, before the question is fixed",
        "Looking at data is how forking paths begin, so Klein makes a look cheap but recorded: "
        "a probe is logged and hash-chained, can never read the sealed rows, and can never be "
        "evidence -- only a lead.",
    )
    _child(["prepare.py"], cwd=study)
    (study / "look.py").write_text(_asset("look.py.tmpl"), encoding="utf-8")
    _commit_all(repo, f"{SLUG}: look.py, the script the probe will run")
    say.cmd(
        f'klein probe --study {rel} --note "class balance and strongest single features" '
        "-- python look.py"
    )
    with _engine_notes(say):
        probe = run_probe(
            study,
            ["python", "look.py"],
            note="class balance and the three strongest single-feature correlations, train rows only",
            echo=False,
        )
    if probe["exit_code"] != 0:
        raise WorkflowError("the demo's probe failed; see " + str(study / probe["log"]["path"]))
    facts = _probe_facts((study / probe["log"]["path"]).read_text(encoding="utf-8"))
    for line in facts["lines"][1:]:
        say.out(line)
    say.out(f"{probe['id']} recorded in probes.jsonl -- a lead, not evidence")

    # 3 -- consult ----------------------------------------------------------
    say.header(
        3,
        "CONSULT -- Gate 0: fix the question before any result exists",
        "The question, the prior belief and two predictions are written down now, each prediction "
        "with an arithmetic rule the notary will apply later. Gate 0 hashes the files, so a "
        "prediction added after the results is visible as a re-recording.",
    )
    _fill_consult(study, today, facts)
    say.out("P1: the 30-feature model reaches val_auc > 0.97")
    say.out("P2: degree-2 interactions beat it by more than one measured floor (delta_in_floors > 1)")
    say.cmd(f'klein gate record consult --study {rel} --acknowledged-by "{ACKNOWLEDGED_BY}"')
    with _engine_notes(say):
        record_gate(
            study,
            "consult",
            acknowledged_by=ACKNOWLEDGED_BY,
            note="question, prior and two predictions with rules registered before any run",
        )
    state = _read_json(study / "study_state.json")
    seen = state["gates"]["consult"].get("probes") or probe_head(study)
    say.out(f"recorded gate consult; the gate recorded {seen.get('count')} probe(s) already looked at")

    # 4 -- data -------------------------------------------------------------
    say.header(
        4,
        "DATA -- Gate 1: is this table safe to model?",
        "Garbage in, garbage out: the data card ranks what could mislead a model, and a "
        "clean-room leakage audit checks that the split reproduces, no duplicate row straddles "
        "partitions, and chance-level predictors score chance. Any failure blocks.",
    )
    say.cmd(f"cd {rel} && python -m kleinlib.leakage data/prepared/prepared.csv --target target --study .")
    audit = _child(
        ["-m", "kleinlib.leakage", "data/prepared/prepared.csv", "--target", "target", "--study", "."],
        cwd=study,
    )
    leakage = audit.stdout
    verdict = [ln for ln in leakage.splitlines() if "checks passed" in ln]
    say.out(verdict[0] if verdict else "leakage audit ran")
    cells = _write_data_card(study, leakage)
    say.out(
        f"data_card.md: {cells['ROWS']} rows, {cells['TRAIN']}/{cells['DEV']}/{cells['TEST']} "
        "train/development/sealed, decision GO (two warnings ranked)"
    )
    say.cmd(f'klein gate record data --study {rel} --acknowledged-by "{ACKNOWLEDGED_BY}"')
    with _engine_notes(say):
        record_gate(
            study,
            "data",
            acknowledged_by=ACKNOWLEDGED_BY,
            note="leakage audit clean; small-sample and correlated-feature warnings accepted and carried",
        )
    say.out("recorded gate data; the prepared bytes and the realized split are now fingerprinted")

    # 5 -- method -----------------------------------------------------------
    say.header(
        5,
        "METHOD -- Gate 2: understand the tool before using it",
        "A short method card explains logistic regression in plain words, then the math, then "
        "the runnable plan, then when it pays. It asserts a Theory + Papers + Practice triad; "
        "this offline demo cannot resolve citations, so it says the papers leg is false.",
    )
    (study / "method_card.md").write_text(_asset("method_card.md.tmpl"), encoding="utf-8")
    (study / "references.yaml").write_text(_asset("references.yaml.tmpl"), encoding="utf-8")
    note = (
        "papers: the demo runs offline, so both references are marked UNVERIFIED and no claim "
        "may rest on either; theory and practice legs are complete"
    )
    say.cmd(f'klein gate record method --study {rel} --acknowledged-by "{ACKNOWLEDGED_BY}" --note "papers: ..."')
    with _engine_notes(say):
        record_gate(study, "method", acknowledged_by=ACKNOWLEDGED_BY, note=note)
    say.out("recorded gate method; modeling is now unblocked")

    # 6 -- phase 0 ----------------------------------------------------------
    say.header(
        6,
        "PHASE 0 -- measure the keep bar instead of guessing it",
        "Re-drawing the train/development partition ten times and refitting the baseline shows how "
        "much a score moves from luck alone. That spread becomes minimum_delta, the smallest "
        "improvement a 'keep' must clear.",
    )
    (study / "sweeps").mkdir(exist_ok=True)
    (study / "sweeps" / "noise_floor.py").write_text(_asset("noise_floor.py.tmpl"), encoding="utf-8")
    say.cmd(f"cd {rel} && python -u sweeps/noise_floor.py")
    _child(["sweeps/noise_floor.py"], cwd=study)
    say.cmd(
        f"klein noise-floor --study {rel} --track primary --recipe split-lottery "
        "--estimand marginal-resplit --sidecar sweeps/split_lottery.sidecar.tsv"
    )
    floor = _paste_floor(study)
    say.out(
        f"estimand={floor['estimand']} recipe={floor['recipe']} k={floor['k']} "
        f"mean={floor['mean']} std={floor['std']} range={floor['range']}"
    )
    say.out(f"minimum_delta = max(2*std, range/2) = {floor['minimum_delta']}  (pasted into study.yaml)")
    _commit_all(repo, f"{SLUG}: the fixed machinery (look.py, noise floor script, sidecar, floor in the contract)")
    say.cmd(
        f"klein sweep register split_lottery --study {rel} "
        "--sidecar sweeps/split_lottery.sidecar.tsv --script sweeps/noise_floor.py"
    )
    with _engine_notes(say):
        register_sweep(
            study,
            "split_lottery",
            sidecar=Path("sweeps/split_lottery.sidecar.tsv"),
            script=Path("sweeps/noise_floor.py"),
        )
    say.cmd(
        f'klein gate record consult --study {rel} --acknowledged-by "{ACKNOWLEDGED_BY}" '
        '--note "minimum_delta set from the measured noise floor"'
    )
    with _engine_notes(say):
        record_gate(
            study,
            "consult",
            acknowledged_by=ACKNOWLEDGED_BY,
            note="minimum_delta set from the measured noise floor",
        )
    say.out("the contract changed after Gate 0, so Gate 0 is re-recorded with that reason")
    say.cmd(f"klein preflight --study {rel}")
    checks = preflight_checks(study)
    failed = [c for c in checks if not c.ok]
    if failed:
        raise WorkflowError("preflight refused: " + "; ".join(f"{c.name}: {c.message}" for c in failed))
    say.out(f"preflight: {len(checks)} checks, 0 failed -- the loop is open")

    # 7 -- three runs -------------------------------------------------------
    say.header(
        7,
        "EXPERIMENT -- three candidates, each one notarized transaction",
        "klein run-one commits the candidate BEFORE running it, runs it once, compares the "
        "printed split fingerprint, then decides keep or discard by arithmetic on the contract. "
        "It never proposes an idea: the ideas are the three below.",
    )
    plan = [
        ("E0001", "train_e0001.py.tmpl", None, "baseline: one-feature logistic on mean_radius"),
        ("E0002", "train_e0002.py.tmpl", "P1", "all 30 features, standardized logistic regression"),
        ("E0003", "train_e0003.py.tmpl", "P2", "every degree-2 interaction of the 30 features"),
    ]
    runs: list[dict[str, Any]] = []
    for expected, template, tests, description in plan:
        (study / "train.py").write_text(_asset(template), encoding="utf-8")
        flag = f" --tests {tests}" if tests else ""
        say.cmd(f'klein run-one --study {rel} --track primary --description "{description}"{flag}')
        with _engine_notes(say):
            manifest = run_one(study, description=description, tests=tests, echo=False)
        if manifest["experiment"] != expected:
            raise WorkflowError(f"expected {expected}, the notary filed {manifest['experiment']}")
        printed = manifest.get("metrics") or {}
        row = {
            "experiment": manifest["experiment"],
            "disposition": manifest["disposition"],
            "primary_metric": manifest["primary_metric"],
        }
        runs.append(row)
        extra = ""
        if "delta_in_floors" in printed:
            extra = f"  delta_in_floors={printed['delta_in_floors']}"
        verdicts = ""
        if tests:
            verdict = _read_json(study / "study_state.json")["predictions"][tests]["verdict"]
            verdicts = f"  {tests} {verdict}"
        say.out(
            f"{row['experiment']}: {row['disposition']}  val_auc={row['primary_metric']}{extra}{verdicts}"
        )
    state = _read_json(study / "study_state.json")
    predictions = {pid: str(entry["verdict"]) for pid, entry in state["predictions"].items()}
    _append_decisions(study, today, runs, floor)
    _commit_all(repo, f"{SLUG}: program.md decisions and playbook after three runs")
    say.out("program.md: dated lines added, including `Decision:` for the refuted P2 (committed)")

    # 8 -- state ------------------------------------------------------------
    say.header(
        8,
        "THE STATE -- what the records say now",
        "Everything below is derived from the receipts, nothing is hand-written: status, the "
        "evidence map (question -> predictions -> evidence -> decisions) and the one next action.",
    )
    say.cmd(f"klein status --study {rel}")
    for line in status_summary(study).splitlines():
        if line.startswith(("experiments:", "final holdout:", "predictions:", "gates:")):
            say.out(line)
    say.cmd(f"klein map --study {rel}")
    for line in format_map(build_map(study)).splitlines():
        say.out(line)
    say.cmd(f"klein next --study {rel}")
    upcoming = next_step(study)
    for line in format_next(upcoming).splitlines():
        say.out(line)

    checks = verify_study(study, receipt=False)
    failures = [c for c in checks if not c.ok]
    seconds = round(time.time() - started, 1)
    summary = {
        "study": str(study),
        "repo": str(repo),
        "seconds": seconds,
        "gates": {
            name: {
                "status": gate.get("status"),
                "acknowledged_by": gate.get("acknowledged_by"),
            }
            for name, gate in _read_json(study / "study_state.json")["gates"].items()
            if name in ("consult", "data", "method")
        },
        "floor": floor,
        "runs": runs,
        "predictions": predictions,
        "probes": len(read_probes(study)),
        "verify": {"checks": len(checks), "failed": len(failures)},
        "next": upcoming["next"],
    }
    if failures:
        raise WorkflowError(
            "klein verify failed on the demo study: "
            + "; ".join(f"{c.name}: {c.message}" for c in failures)
        )
    say.plain("")
    say.plain(f"Done in {seconds:.0f}s. What just happened, for real:")
    for bullet in (
        "a look on the record: one probe, hash-chained, fenced off from the sealed rows",
        "three gates recorded (question, data, method) before any model ran",
        f"a measured bar: minimum_delta {floor['minimum_delta']} from ten re-drawn partitions, not a guess",
        "a keep (E0002), a discard (E0003) and a prediction refuted by arithmetic (P2)",
        "the evidence map: every run, prediction and decision linked and re-verifiable",
    ):
        say.plain(f"  * {bullet}")
    say.plain(
        "A real study continues: the sealed confirmation run, findings + a claims lock, an "
        "independent referee, and the teaching report."
    )
    say.plain("Explore further:")
    say.plain(f"  $ klein map --study {study} --html")
    say.plain("  $ klein explain gate")
    return summary
