"""The schema-3 study fixture, and the loop invariants that change with it.

``ready_study`` (in ``test_workflow_v2``) is frozen: it scaffolds the schema-2
shape and every test in that module pins schema-2 behaviour forever.
``ready_study_v3`` is its schema-3 sibling — typed inquiry, declared entrypoint,
gates recorded, on an experiments branch — re-exported through ``conftest.py`` so
sibling modules can inject it by name.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
import yaml

from kleinlib.contract import mutable_surface
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import (
    WorkflowError,
    load_manifests,
    load_state,
    record_gate,
    run_one,
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain") == "":
        return
    git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )


def _fill(study: Path, **extra: str) -> None:
    """Resolve the placeholders CONSULT owns, so the contract validates."""
    replacements = {
        "{{RQ1_QUESTION}}": "does it improve?",
        "{{RQ1_PRIOR}}": "no",
        "{{LEVER_1}}": "candidate",
        "{{DELTA_1}}": "+0.1 score",
        **extra,
    }
    for name in ("study.yaml", "program.md", "research_plan.md"):
        path = study / name
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


@pytest.fixture
def ready_study_v3(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies",
        "03-demo",
        goal="compare a candidate",
        domain="test",
        target="y",
        task_type="classification",
        method_depth="brief",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
        data_path="data/prepared/fixture.csv",
        max_run_seconds=5,
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="the maintainers of this test suite",
    )
    _fill(study)
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text(
        "# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8"
    )
    (study / "method_card.md").write_text("# Method card\n\nBrief method.\n", encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "ready schema-3 study")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    return repo, study


def metric_command(
    value: float,
    *,
    expected_kind: str | None = None,
    expected_experiment: str | None = None,
    expected_track: str | None = None,
    split_fingerprint: str | None = None,
    artifacts: Sequence[str] | Mapping[str, str] | None = None,
    extra: Mapping[str, float] | None = None,
) -> list[str]:
    """A stand-in entrypoint that prints one canonical block.

    ``split_fingerprint`` / ``artifacts`` / ``extra`` add the schema-3 lines the
    notary reads: the partition fingerprint it compares against the DATA gate,
    the ``artifact:`` lines a registered cell pins, and any further printed keys
    a guardrail or a prediction rule names.

    ``artifacts`` are STUDY-RELATIVE POSIX PATHS, printed one per line exactly
    as ``references/registered-mode.md`` shows them — the manifest keys its
    artifact map by path, and aliases live in ``claims.lock``, not here.  A
    mapping is accepted for readability at the call site; only its values are
    printed.
    """
    check = ""
    if expected_kind:
        check = (
            "import os; "
            f"assert os.environ['KLEIN_EVALUATION_KIND'] == {expected_kind!r}; "
        )
    if expected_experiment:
        check += f"assert os.environ['KLEIN_EXPERIMENT_ID'] == {expected_experiment!r}; "
    if expected_track:
        check += f"assert os.environ['KLEIN_TRACK'] == {expected_track!r}; "
    lines = [
        f"print('primary_metric:    {value}')",
        "print('metric_name:       val_auc')",
        "print('metric_goal:       higher')",
    ]
    if split_fingerprint is not None:
        lines.append(f"print('split_fingerprint: {split_fingerprint}')")
    paths = (
        list(artifacts.values()) if isinstance(artifacts, Mapping) else list(artifacts or ())
    )
    for path in paths:
        lines.append(f"print('artifact:          {path}')")
    for key, number in (extra or {}).items():
        lines.append(f"print('{key}: {number}')")
    return [sys.executable, "-c", check + "; ".join(lines)]


def test_v3_fixture_scaffolds_a_typed_inquiry(ready_study_v3) -> None:
    _, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["schema_version"] == 3
    assert (contract["kind"], contract["profile"], contract["data"]["modality"]) == (
        "predict",
        "generic",
        "tabular",
    )
    assert contract["entrypoint"]["mutable"] == ["train.py"]
    assert contract["tracks"]["primary"]["mode"] == "frontier"
    assert load_state(study, contract)["schema_version"] == 3


def test_v3_runs_one_transaction_and_records_its_schema(ready_study_v3) -> None:
    _, study = ready_study_v3
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = True\n", encoding="utf-8")
    manifest = run_one(study, command=metric_command(0.7), echo=False)
    assert manifest["schema_version"] == 3
    assert manifest["disposition"] == "keep"
    assert load_manifests(study)[0]["experiment"] == "E0001"


def test_the_declared_surface_is_what_the_empty_diff_guard_watches(ready_study_v3) -> None:
    """The guard follows entrypoint.mutable, not the literal name 'train.py'."""
    _, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert mutable_surface(contract) == ("train.py",)
    with pytest.raises(WorkflowError, match="train.py is unchanged since HEAD"):
        run_one(study, echo=False)
