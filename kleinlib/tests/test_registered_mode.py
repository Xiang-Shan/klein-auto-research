"""E5 — registered mode: a track that MEASURES instead of climbing.

Frontier mode answers "which candidate wins?".  Most science asks something
else — "what is the value?", "does H hold?", "does the method recover the
truth?" — and those questions have no incumbent.  A registered track
(`references/registered-mode.md`) runs CELLS of a pre-registered measurement
program: disposition `measured | crash`, no incumbent, no headroom, the mutable
surface always restored, identical reruns allowed when they adjudicate a
prediction, and `artifact:` lines that make a TABLE first-class evidence.

What is pinned here is the contract diff between the two modes, one property
per test, plus the schema-2 guarantee: a schema-2 study can never produce a
`measured` row, so none of this reaches it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib.contract import VALID_DISPOSITIONS, normalize_tracks
from kleinlib.decision import choose_disposition, registered_guardrails
from kleinlib.schema import VALID_STATUSES
from kleinlib.workflow import (
    ARTIFACT_MISSING,
    WorkflowError,
    load_manifests,
    record_gate,
    run_one,
    status_summary,
)

# ---------------------------------------------------------------------------
# fixtures — a registered lane on top of the shared schema-3 study
# ---------------------------------------------------------------------------

TRACK_SPEC = {"metric": {"name": "val_auc", "goal": "higher", "minimum_delta": 0.0}}

#: A real entrypoint on disk, so the DECLARED command can be exercised — the
#: `--tests` rerun exemption only means anything when `command=None`.
CELL_SOURCE = """\
print("primary_metric:    0.7")
print("metric_name:       val_auc")
print("metric_goal:       higher")
"""


def amend(study: Path, transform, *, note: str) -> dict:
    """Rewrite study.yaml and re-record the consult gate, which hashes it.

    study.yaml is a gate artifact: amending it after acknowledgement is exactly
    what the gate-hash check refuses, so the amendment goes through the gate and
    lands on the event trail — the same route a real study takes.
    """
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    transform(contract)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note=note)
    return contract


@pytest.fixture
def registered_study(ready_study_v3) -> tuple[Path, Path]:
    repo, study = ready_study_v3
    (study / "train.py").write_text(CELL_SOURCE, encoding="utf-8")

    def _register(contract: dict) -> None:
        contract["tracks"]["primary"]["mode"] = "registered"
        # The scaffolded command shells out to `uv run --locked`, which a temp
        # repo with a stub lockfile cannot serve; `python` resolves through the
        # same venv the suite already runs in.  (An absolute interpreter path
        # is refused by the contract: entrypoint.command stays inside the study.)
        contract["entrypoint"]["command"] = ["python", "-u", "train.py"]
        contract["predictions"] = [
            {
                "id": "P1",
                "track": "primary",
                "statement": "the measured value clears 0.6",
                "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
            }
        ]

    amend(study, _register, note="registered lane")
    commit_all(repo, "registered lane declared")
    return repo, study


def edit_cell(study: Path, marker: str) -> None:
    """One falsifiable edit to the mutable surface — one cell."""
    entrypoint = study / "train.py"
    entrypoint.write_text(
        entrypoint.read_text(encoding="utf-8") + f"\n# cell {marker}\n", encoding="utf-8"
    )


def cell_command(
    value: float, *, writes: dict[str, str] | None = None, artifacts: list[str] | None = None
) -> list[str]:
    """A cell that WRITES its tables and then declares them — the real order.

    The notary hashes an ``artifact:`` line when the child exits; a table
    created before the run would just be an uncommitted file the clean-tree
    guard refuses, which is not what registered mode is about.
    """
    command = metric_command(value, artifacts=artifacts or [])
    prologue = "import pathlib; " + "".join(
        f"_p = pathlib.Path({rel!r}); _p.parent.mkdir(parents=True, exist_ok=True); "
        f"_p.write_bytes({text!r}.encode()); "  # exact bytes on every platform (no CRLF translation)
        for rel, text in (writes or {}).items()
    )
    command[-1] = prologue + command[-1]
    return command


# ---------------------------------------------------------------------------
# 1. the vocabulary
# ---------------------------------------------------------------------------


def test_measured_is_an_honest_outcome_in_both_registries() -> None:
    assert "measured" in VALID_DISPOSITIONS
    assert "measured" in VALID_STATUSES


def test_choose_disposition_measures_a_registered_cell() -> None:
    disposition, reason = choose_disposition(
        primary_metric=0.4,
        track_spec=dict(TRACK_SPEC),
        metrics={"primary_metric": 0.4},
        incumbent={"experiment": "E0001", "primary_metric": 0.9},
        final_test=False,
        mode="registered",
    )
    # Worse than a would-be incumbent, and still `measured`: a cell does not
    # compete.
    assert (disposition, reason) == ("measured", "registered cell measured")


def test_frontier_is_the_default_mode_so_schema_2_arithmetic_is_untouched() -> None:
    assert choose_disposition(
        primary_metric=0.9,
        track_spec=dict(TRACK_SPEC),
        metrics={},
        incumbent=None,
        final_test=False,
    ) == ("keep", "first valid result on this track")


def test_a_sealed_registered_cell_is_still_measured() -> None:
    """A registered kind's confirmation is a measurement, not a discard."""
    disposition, _ = choose_disposition(
        primary_metric=0.4,
        track_spec=dict(TRACK_SPEC),
        metrics={},
        incumbent=None,
        final_test=True,
        mode="registered",
    )
    assert disposition == "measured"


# ---------------------------------------------------------------------------
# 2. guardrails are recorded, never disposition-flipping
# ---------------------------------------------------------------------------


def test_a_failing_guardrail_is_recorded_on_the_cell_not_hidden_by_a_discard(
    registered_study,
) -> None:
    repo, study = registered_study
    amend(
        study,
        lambda c: c["tracks"]["primary"].update(
            guardrails={"wall_seconds": {"max": 0.000001}}
        ),
        note="guardrail declared",
    )
    commit_all(repo, "a guardrail the cell will fail")

    edit_cell(study, "guardrail")
    manifest = run_one(study, command=metric_command(0.7), echo=False)

    assert manifest["disposition"] == "measured"  # the measurement happened
    assert manifest["guardrails_ok"] is False
    assert any("wall_seconds" in failure for failure in manifest["guardrail_failures"])
    assert "guardrails failed (recorded, not hidden)" in manifest["decision_reason"]


def test_a_passing_guardrail_records_the_positive_flag(registered_study) -> None:
    _, study = registered_study
    edit_cell(study, "clean")
    manifest = run_one(study, command=metric_command(0.7), echo=False)
    assert manifest["guardrails_ok"] is True
    assert "guardrail_failures" not in manifest


def test_registered_guardrails_never_consult_an_incumbent() -> None:
    """`maximum_degradation` is a frontier comparison; a cell has no rival."""
    spec = {
        **TRACK_SPEC,
        "guardrails": {"val_brier": {"maximum_degradation": 0.001, "goal": "lower"}},
    }
    ok, failures = registered_guardrails(spec, {"val_brier": 99.0})
    assert (ok, failures) == (True, [])


# ---------------------------------------------------------------------------
# 3. no incumbent, no headroom, no frontier
# ---------------------------------------------------------------------------


def test_a_registered_cell_records_no_incumbent_and_never_becomes_one(
    registered_study,
) -> None:
    _, study = registered_study
    edit_cell(study, "one")
    first = run_one(study, command=metric_command(0.9), echo=False)
    edit_cell(study, "two")
    second = run_one(study, command=metric_command(0.1), echo=False)

    assert [m["disposition"] for m in (first, second)] == ["measured", "measured"]
    assert first["incumbent"] is None and second["incumbent"] is None
    # The worse cell is evidence, not a regression: both rows keep their number.
    assert [m["primary_metric"] for m in load_manifests(study)] == [0.9, 0.1]


def test_headroom_never_fires_on_a_registered_track(registered_study) -> None:
    """`h < 1` asks whether a KEEP is possible; a cell is never a keep."""
    repo, study = registered_study
    amend(
        study,
        lambda c: c["tracks"]["primary"]["metric"].update(
            minimum_delta=0.5, bound={"ideal": 1.0, "on_infeasible": "block"}
        ),
        note="a bound that would block",
    )
    commit_all(repo, "declare a bound whose headroom is closed")

    edit_cell(study, "closed-door")
    # h = (1.0 - 0.9) / 0.5 = 0.2 < 1 — on a frontier this is a hard refusal.
    assert run_one(study, command=metric_command(0.9), echo=False)["disposition"] == "measured"


def test_the_mutable_surface_is_always_restored_after_a_cell(registered_study) -> None:
    """The candidate commit IS the record; the working tree returns to base."""
    repo, study = registered_study
    before = (study / "train.py").read_text(encoding="utf-8")
    edit_cell(study, "restored")
    manifest = run_one(study, command=metric_command(0.7), echo=False)

    assert manifest["disposition"] == "measured"
    assert (study / "train.py").read_text(encoding="utf-8") == before
    assert git(repo, "status", "--porcelain") == ""
    # …and the cell's own diff stays resolvable at its candidate commit.
    assert "# cell restored" in git(repo, "show", f"{manifest['candidate_commit']}:studies/03-demo/train.py")


# ---------------------------------------------------------------------------
# 4. an identical rerun that adjudicates a prediction is evidence
# ---------------------------------------------------------------------------


def test_an_unchanged_rerun_is_allowed_when_tests_names_a_prediction(
    registered_study,
) -> None:
    _, study = registered_study
    edit_cell(study, "first")
    # No --command: the DECLARED entrypoint runs, exactly as in a real study.
    assert run_one(study, echo=False)["disposition"] == "measured"
    # train.py is back at base and identical — a frontier track would refuse.
    manifest = run_one(study, tests="P1", echo=False)
    assert manifest["disposition"] == "measured"
    assert manifest["predictions_requested"] == ["P1"]
    assert manifest["empty_candidate_diff"] is True


def test_an_unchanged_rerun_without_tests_is_still_refused(registered_study) -> None:
    _, study = registered_study
    edit_cell(study, "first")
    run_one(study, echo=False)
    with pytest.raises(WorkflowError, match="train.py is unchanged since HEAD"):
        run_one(study, echo=False)


def test_the_refusal_names_the_registered_escape(registered_study) -> None:
    _, study = registered_study
    edit_cell(study, "first")
    run_one(study, echo=False)
    with pytest.raises(WorkflowError, match=r"--tests P# also allows it"):
        run_one(study, echo=False)


def test_a_frontier_track_gets_no_such_exemption(ready_study_v3) -> None:
    """The exemption follows the MODE, not the presence of `--tests`."""
    _, study = ready_study_v3
    amend(
        study,
        lambda c: c.update(
            predictions=[
                {
                    "id": "P1",
                    "statement": "the frontier clears 0.6",
                    "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
                }
            ]
        ),
        note="a frontier prediction",
    )
    with pytest.raises(WorkflowError, match="train.py is unchanged since HEAD"):
        run_one(study, tests="P1", echo=False)


# ---------------------------------------------------------------------------
# 5. artifact: lines — a table is the measurement
# ---------------------------------------------------------------------------


def test_declared_artifacts_are_hashed_into_the_manifest_with_the_declared_role(
    registered_study,
) -> None:
    _, study = registered_study
    rows = "family\tpermission\nlinear\tyes\n"
    edit_cell(study, "table")

    manifest = run_one(
        study,
        command=cell_command(
            0.7,
            writes={"sweeps/permission_map.tsv": rows},
            artifacts=["sweeps/permission_map.tsv"],
        ),
        echo=False,
    )
    entry = manifest["artifacts"]["sweeps/permission_map.tsv"]
    assert entry["role"] == "declared"
    assert entry["bytes"] == len(rows.encode())
    assert len(entry["sha256"]) == 64
    assert entry["availability"] == "recorded"
    assert (study / "sweeps" / "permission_map.tsv").read_text(encoding="utf-8") == rows
    # The manifest on disk is the receipt, not the in-memory dict.
    on_disk = json.loads((study / "runs" / "E0001" / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["artifacts"]["sweeps/permission_map.tsv"]["role"] == "declared"


def test_a_missing_declared_artifact_is_a_crash(registered_study) -> None:
    _, study = registered_study
    edit_cell(study, "no-table")
    manifest = run_one(
        study, command=metric_command(0.7, artifacts=["sweeps/never_written.tsv"]), echo=False
    )
    assert manifest["disposition"] == "crash"
    assert ARTIFACT_MISSING in manifest["decision_reason"]
    assert manifest["primary_metric"] is None


def test_a_declared_artifact_that_escapes_the_study_is_a_crash(registered_study) -> None:
    _, study = registered_study
    edit_cell(study, "escape")
    manifest = run_one(
        study, command=metric_command(0.7, artifacts=["../../etc/hosts"]), echo=False
    )
    assert manifest["disposition"] == "crash"
    assert ARTIFACT_MISSING in manifest["decision_reason"]


def test_a_schema_2_study_never_grows_declared_artifacts(ready_study) -> None:
    """The schema selects the rule set: an `artifact:` line is schema-3 grammar."""
    from test_workflow_v2 import metric_command as v2_metric_command

    _, study = ready_study
    (study / "train.py").write_text(
        (study / "train.py").read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8"
    )
    command = [*v2_metric_command(0.7)]
    command[-1] += "; print('artifact: not/a/path.tsv')"
    manifest = run_one(study, command=command, echo=False)
    assert manifest["disposition"] == "keep"
    assert all(meta.get("role") != "declared" for meta in manifest["artifacts"].values())


# ---------------------------------------------------------------------------
# 6. the derived views learn the word
# ---------------------------------------------------------------------------


def test_results_tsv_and_status_report_the_measured_cell(registered_study) -> None:
    _, study = registered_study
    edit_cell(study, "ledger")
    run_one(study, command=metric_command(0.7), echo=False)

    ledger = (study / "results.tsv").read_text(encoding="utf-8").splitlines()
    assert ledger[1].split("\t")[3] == "measured"
    assert "measured=1" in status_summary(study)


def test_normalize_tracks_defaults_to_frontier(registered_study) -> None:
    _, study = registered_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert normalize_tracks(contract)["primary"]["mode"] == "registered"
    contract["tracks"]["primary"].pop("mode")
    assert normalize_tracks(contract)["primary"]["mode"] == "frontier"
