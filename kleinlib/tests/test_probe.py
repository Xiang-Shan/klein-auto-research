"""``klein probe`` — exploration on the record, fenced away from the sealed data.

A probe is cheap (one bounded subprocess, no gate, no disposition), recorded (an
append-only hash chain), fenced (``KLEIN_PROBE=1``) and never evidence (an ``X####``
id is not an id the claims law resolves).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from test_claims import (
    locked_study as claims_locked_study,  # noqa: F401  (fixture, aliased: see conftest)
)
from test_workflow_v3 import _fill, commit_all, git

from kleinlib import api, cli
from kleinlib.checks import verify_study
from kleinlib.claims import add_claim, verify_lock
from kleinlib.data import contract_split, load_partition
from kleinlib.errors import WorkflowError
from kleinlib.primitives import sha256_file
from kleinlib.probe import (
    PROBES_DIR,
    PROBES_FILE,
    probe_chain_problems,
    probe_head,
    read_probes,
    run_probe,
)
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import load_contract, load_state, record_gate

PY = sys.executable
PRINT_HI = [PY, "-c", "print('hi')"]
PRINT_ENV = [
    PY,
    "-c",
    "import os; print('|'.join(os.environ.get(k, '<unset>') for k in "
    "('KLEIN_PROBE', 'KLEIN_PROBE_ID', 'KLEIN_PROBE_DIR', 'KLEIN_EVALUATION_KIND')))",
]


def _porcelain(repo: Path) -> str:
    return git(repo, "status", "--porcelain")


def _head_files(repo: Path) -> set[str]:
    return set(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())


def _rewrite(path: Path, transform) -> None:
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")


@pytest.fixture
def ungated_study(tmp_path: Path) -> tuple[Path, Path]:
    """A filled study in a git repo whose gates are NOT recorded."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies", "03-demo", goal="compare a candidate", domain="test", target="y",
        task_type="classification", method_depth="brief", family="linear", metric_name="val_auc",
        metric_goal="higher", data_source="csv:fixture.csv", data_path="data/prepared/fixture.csv",
        max_run_seconds=5, schema_version=3, kind="predict", modality="tabular", profile="generic",
        audience="the maintainers of this test suite",
    )
    _fill(study)
    (study / "data" / "prepared").mkdir(parents=True)
    (study / "data" / "prepared" / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    commit_all(repo, "scaffold, filled, ungated")
    return repo, study


@pytest.fixture
def two_probes(ready_study):
    repo, study = ready_study
    first = run_probe(study, PRINT_HI, note="first", echo=False)
    second = run_probe(study, [PY, "-c", "print('again')"], note="second", echo=False)
    return repo, study, first, second


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------


def test_a_probe_is_recorded_hashed_and_committed_alone(ready_study) -> None:
    repo, study = ready_study
    record = run_probe(study, PRINT_HI, note="  look   here ", echo=False)
    assert record["id"] == "X0001" and record["sequence"] == 1 and record["exit_code"] == 0
    assert record["note"] == "look here" and record["command"] == PRINT_HI and record["previous_hash"] is None
    lines = (study / PROBES_FILE).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0]) == record
    log = study / PROBES_DIR / "X0001.log"
    assert "hi" in log.read_text(encoding="utf-8")
    assert record["log"] == {"path": "probes/X0001.log", "sha256": sha256_file(log)}
    assert _porcelain(repo) == ""
    assert _head_files(repo) == {"studies/03-demo/probes.jsonl", "studies/03-demo/probes/X0001.log"}
    assert git(repo, "log", "-1", "--format=%s") == "klein: probe X0001"
    assert record["git_head"] and probe_chain_problems(study) == []


def test_probes_chain_and_ids_are_sequential(two_probes) -> None:
    _repo, study, first, second = two_probes
    assert (first["id"], second["id"]) == ("X0001", "X0002")
    assert second["previous_hash"] == first["hash"] and second["hash"] != first["hash"]
    assert probe_head(study) == {"count": 2, "head": second["hash"]}
    assert [row["id"] for row in read_probes(study)] == ["X0001", "X0002"]


def test_a_probe_hashes_the_study_files_its_command_names(ready_study) -> None:
    repo, study = ready_study
    (study / "look.py").write_text("print('looking')\n", encoding="utf-8")
    commit_all(repo, "a look script")
    record = run_probe(study, [PY, "look.py"], echo=False)
    assert record["files"] == {"look.py": sha256_file(study / "look.py")}
    assert "looking" in (study / record["log"]["path"]).read_text(encoding="utf-8")


def test_a_failing_command_is_still_recorded(ready_study) -> None:
    _repo, study = ready_study
    record = run_probe(study, [PY, "-c", "raise SystemExit(3)"], echo=False)
    assert record["exit_code"] == 3 and record["timed_out"] is False
    assert [row["exit_code"] for row in read_probes(study)] == [3]


def test_a_probe_works_before_any_gate_and_the_consult_gate_remembers_it(ungated_study) -> None:
    repo, study = ungated_study
    record = run_probe(study, PRINT_HI, note="looked before asking", echo=False)
    assert record["id"] == "X0001" and _porcelain(repo) == ""
    contract = load_contract(study)
    assert load_state(study, contract)["gates"]["consult"]["status"] == "pending"
    state = record_gate(study, "consult", acknowledged_by="tester")
    assert state["gates"]["consult"]["probes"] == {"count": 1, "head": record["hash"]}
    assert load_state(study, contract)["gates"]["consult"]["probes"] == {"count": 1, "head": record["hash"]}


def test_a_study_that_never_probed_records_no_probes_on_its_gate(ungated_study) -> None:
    _repo, study = ungated_study
    state = record_gate(study, "consult", acknowledged_by="tester")
    assert "probes" not in state["gates"]["consult"]


def test_a_timeout_beyond_the_contract_is_refused_and_records_nothing(ready_study) -> None:
    repo, study = ready_study  # max_run_seconds: 5
    for bad in (6, 0, -1):
        with pytest.raises(WorkflowError, match="max_run_seconds=5"):
            run_probe(study, PRINT_HI, timeout_seconds=bad, echo=False)
    with pytest.raises(WorkflowError, match="needs a command"):
        run_probe(study, [], echo=False)
    assert read_probes(study) == [] and _porcelain(repo) == ""
    assert run_probe(study, PRINT_HI, timeout_seconds=5, echo=False)["exit_code"] == 0


# --------------------------------------------------------------------------
# the fences
# --------------------------------------------------------------------------


def test_the_child_sees_the_probe_environment_and_its_output_directory(ready_study) -> None:
    repo, study = ready_study
    record = run_probe(study, PRINT_ENV, echo=False)
    flag, probe_id, directory, kind = (study / record["log"]["path"]).read_text(encoding="utf-8").splitlines()[0].split("|")
    assert (flag, probe_id, kind) == ("1", "X0001", "development")
    assert Path(directory) == study / PROBES_DIR / "X0001"


def test_figures_written_to_the_probe_dir_are_committed_with_the_probe(ready_study) -> None:
    repo, study = ready_study
    script = "import os; open(os.path.join(os.environ['KLEIN_PROBE_DIR'], 'hist.txt'), 'w').write('bins')"
    run_probe(study, [PY, "-c", script], echo=False)
    assert (study / PROBES_DIR / "X0001" / "hist.txt").read_text(encoding="utf-8") == "bins"
    assert _porcelain(repo) == ""
    assert "studies/03-demo/probes/X0001/hist.txt" in _head_files(repo)
    assert not (study / PROBES_DIR / "X0002").exists()
    run_probe(study, PRINT_HI, echo=False)  # a probe that writes nothing leaves no empty directory
    assert not (study / PROBES_DIR / "X0002").exists()


@pytest.fixture
def split_study(ready_study) -> Path:
    _repo, study = ready_study
    frame = pd.DataFrame({"x": range(60), "y": [i % 2 for i in range(60)]})
    frame.to_csv(study / "data" / "prepared" / "fixture.csv", index=False)
    return study


def test_a_probe_may_not_read_the_sealed_partition(split_study, monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_PROBE", "1")
    with pytest.raises(ValueError, match="a probe may not read the sealed partition"):
        load_partition(study_dir=split_study, kind="final_test")
    fit_X, eval_X, _, _ = load_partition(study_dir=split_study, kind="development")
    assert len(fit_X) > 0 and len(eval_X) > 0  # looking at train and development is the point
    monkeypatch.setenv("KLEIN_SEALED_DRYRUN", "1")  # the rehearsal does not open the seal to a probe either
    with pytest.raises(ValueError, match="a probe may not read"):
        load_partition(study_dir=split_study, kind="final_test")


def test_outside_a_probe_the_sealed_partition_still_loads(split_study, monkeypatch) -> None:
    monkeypatch.delenv("KLEIN_PROBE", raising=False)
    _, eval_X, _, _ = load_partition(study_dir=split_study, kind="final_test")
    assert len(eval_X) > 0


def test_contract_split_returns_the_test_partitions_empty_under_a_probe(split_study, monkeypatch) -> None:
    monkeypatch.delenv("KLEIN_PROBE", raising=False)
    open_parts = contract_split(split_study)
    assert len(open_parts[2]) > 0 and len(open_parts[5]) > 0
    monkeypatch.setenv("KLEIN_PROBE", "1")
    fenced = contract_split(split_study)
    assert len(fenced[2]) == 0 and len(fenced[5]) == 0
    assert list(fenced[2].columns) == list(open_parts[2].columns)  # empty, not absent
    for index in (0, 1, 3, 4):  # train and development are unchanged
        pd.testing.assert_index_equal(fenced[index].index, open_parts[index].index)
    monkeypatch.setenv("KLEIN_PROBE", "0")  # only the exact value 1 fences
    assert len(contract_split(split_study)[2]) > 0


def test_a_real_probe_child_cannot_open_the_seal(split_study) -> None:
    script = (
        "from kleinlib.data import contract_split; p = contract_split('.'); "
        "print('test_rows', len(p[2]), 'train_rows', len(p[0]))"
    )
    record = run_probe(split_study, [PY, "-c", script], echo=False)
    assert record["exit_code"] == 0
    out = (split_study / record["log"]["path"]).read_text(encoding="utf-8")
    assert "test_rows 0" in out and "train_rows 0" not in out


# --------------------------------------------------------------------------
# tamper detection
# --------------------------------------------------------------------------


def test_editing_a_log_is_detected(two_probes) -> None:
    _repo, study, *_ = two_probes
    with (study / "probes" / "X0001.log").open("a", encoding="utf-8") as handle:
        handle.write("doctored\n")
    assert any("X0001: its log changed after it was recorded" in p for p in probe_chain_problems(study))


def test_editing_a_line_of_the_ledger_is_detected(two_probes) -> None:
    _repo, study, *_ = two_probes
    _rewrite(study / PROBES_FILE, lambda text: text.replace('"note":"first"', '"note":"edited"'))
    assert any("X0001: hash does not match its content" in p for p in probe_chain_problems(study))


def test_deleting_the_first_line_is_detected(two_probes) -> None:
    _repo, study, *_ = two_probes
    _rewrite(study / PROBES_FILE, lambda text: text.split("\n", 1)[1])
    problems = probe_chain_problems(study)
    assert problems and any("X0002: id should be X0001" in p for p in problems)
    assert any("previous_hash does not match" in p for p in problems)


def test_a_deleted_log_is_detected_and_a_damaged_ledger_blocks_new_probes(two_probes) -> None:
    _repo, study, *_ = two_probes
    (study / "probes" / "X0002.log").unlink()
    assert any("X0002: its log is missing" in p for p in probe_chain_problems(study))
    with pytest.raises(WorkflowError, match="the probe ledger is damaged"):
        run_probe(study, PRINT_HI, echo=False)


def test_replacing_a_probe_the_consult_gate_recorded_is_reported(ready_study) -> None:
    repo, study = ready_study
    run_probe(study, PRINT_HI, note="before the question was fixed", echo=False)
    state = record_gate(study, "consult", acknowledged_by="tester")
    recorded = state["gates"]["consult"]["probes"]
    assert probe_chain_problems(study, recorded=recorded) == []
    (study / PROBES_FILE).unlink()
    for log in (study / PROBES_DIR).glob("*.log"):
        log.unlink()
    run_probe(study, [PY, "-c", "print('a different first look')"], echo=False, commit=False)
    assert probe_chain_problems(study) == []  # the chain alone is internally consistent ...
    problems = probe_chain_problems(study, recorded=recorded)  # ... but it is not the one recorded
    assert any("not the ones the consult gate recorded" in p for p in problems)
    failed = [c for c in verify_study(study, receipt=False) if c.name == "probe ledger"]
    assert len(failed) == 1 and not failed[0].ok
    assert "not the ones the consult gate recorded" in failed[0].message


def test_verify_has_a_probe_ledger_check_only_for_a_study_that_probed(ready_study) -> None:
    _repo, study = ready_study
    assert [c for c in verify_study(study, receipt=False) if c.name == "probe ledger"] == []
    run_probe(study, PRINT_HI, echo=False)
    checks = [c for c in verify_study(study, receipt=False) if c.name == "probe ledger"]
    assert len(checks) == 1 and checks[0].ok
    assert "1 probe(s), hash chain intact" in checks[0].message and "none of it is evidence" in checks[0].message
    with (study / "probes" / "X0001.log").open("a", encoding="utf-8") as handle:
        handle.write("x")
    checks = [c for c in verify_study(study, receipt=False) if c.name == "probe ledger"]
    assert len(checks) == 1 and not checks[0].ok


# --------------------------------------------------------------------------
# a probe is never evidence
# --------------------------------------------------------------------------


def test_a_probe_id_is_never_claim_evidence(claims_locked_study) -> None:  # noqa: F811
    _repo, study = claims_locked_study
    record = run_probe(study, PRINT_HI, note="a lead", echo=False)
    add_claim(
        study,
        "C3",
        claim_class="procedural-verdict",
        strength="exploratory",
        claim="A claim that leans on a look.",
        evidence=[record["id"]],
    )
    evidence = next(c for c in verify_lock(study) if c.name == "claims evidence")
    assert not evidence.ok
    assert "'X0001'" in evidence.message and "not an id in the inquiry-model grammar" in evidence.message


# --------------------------------------------------------------------------
# the command line and the API
# --------------------------------------------------------------------------


def _cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_klein_probe_runs_records_and_lists(ready_study) -> None:
    repo, study = ready_study
    code, out, _ = _cli(["probe", "--study", str(study), "--note", "n", "--quiet", "--", PY, "-c", "print(1)"])
    assert code == 0 and out.startswith("X0001: exit 0") and "a probe is a lead, not evidence" in out
    assert _porcelain(repo) == ""
    code, out, _ = _cli(["probe", "--study", str(study), "--list"])
    assert code == 0 and "X0001" in out and "ok" in out and "1 probe(s)" in out and "       n" in out


def test_klein_probe_echoes_the_childs_output_unless_quiet(ready_study) -> None:
    _repo, study = ready_study
    _, loud, _ = _cli(["probe", "--study", str(study), "--", PY, "-c", "print('echoed-line')"])
    _, quiet, _ = _cli(["probe", "--study", str(study), "--quiet", "--", PY, "-c", "print('hidden-line')"])
    assert "echoed-line" in loud and "hidden-line" not in quiet


def test_klein_probe_without_a_command_exits_two(ready_study) -> None:
    _repo, study = ready_study
    for argv in (["probe", "--study", str(study)], ["probe", "--study", str(study), "--"]):
        code, _out, err = _cli(argv)
        assert code == 2 and "needs a command after `--`" in err
    assert read_probes(study) == []


def test_klein_probe_exits_one_for_a_failing_command_and_still_records_it(ready_study) -> None:
    _repo, study = ready_study
    code, out, _ = _cli(["probe", "--study", str(study), "--quiet", "--", PY, "-c", "raise SystemExit(4)"])
    assert code == 1 and out.startswith("X0001: exit 4")
    assert [row["exit_code"] for row in read_probes(study)] == [4]
    code, out, _ = _cli(["probe", "--study", str(study), "--list"])
    assert "exit 4" in out


def test_klein_probe_list_exits_one_on_a_damaged_ledger(two_probes) -> None:
    _repo, study, *_ = two_probes
    (study / "probes" / "X0001.log").write_text("doctored", encoding="utf-8")
    code, out, _ = _cli(["probe", "--study", str(study), "--list"])
    assert code == 1 and "LEDGER DAMAGED" in out


def test_klein_probe_rejects_a_timeout_beyond_the_contract(ready_study) -> None:
    _repo, study = ready_study
    code, _out, err = _cli(["probe", "--study", str(study), "--timeout", "60", "--", *PRINT_HI])
    assert code == 2 and "max_run_seconds=5" in err


def test_klein_probe_json_envelope_carries_the_record(ready_study) -> None:
    _repo, study = ready_study
    code, out, _ = _cli(["probe", "--study", str(study), "--json", "--quiet", "--", *PRINT_HI])
    env = json.loads(out)
    assert code == 0 and env["verb"] == "probe" and env["ok"] is True
    assert env["data"]["probe"]["id"] == "X0001"
    code, out, _ = _cli(["probe", "--study", str(study), "--json", "--list"])
    listed = json.loads(out)["data"]
    assert [row["id"] for row in listed["probes"]] == ["X0001"] and listed["problems"] == []


def test_api_probe_is_not_ok_when_the_command_fails(ready_study) -> None:
    _repo, study = ready_study
    good = api.probe(study, PRINT_HI, note="n")
    assert good["ok"] and good["data"]["probe"]["id"] == "X0001"
    bad = api.probe(study, [PY, "-c", "raise SystemExit(3)"])
    assert bad["ok"] is False and bad["data"]["probe"]["exit_code"] == 3 and bad["problems"] == []
    refused = api.probe(study, PRINT_HI, timeout_seconds=99)
    assert refused["ok"] is False and refused["problems"][0]["code"] == "refused"
