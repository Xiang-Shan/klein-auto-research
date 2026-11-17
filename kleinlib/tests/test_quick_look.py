"""Klein 3.1 — proportional rigor: the quick look (docs/design/klein-3.1-quick-look.md).

A study declaring ``policy: {rigor: quick}`` needs only CONSULT and DATA, has no sealed
run, claims ``exploratory`` at most, and closes without a referee. These tests pin the
judging rules (``contract.rigor`` / ``required_gates``, ``run_one``, ``claims``,
``finalize``, ``verify``), the promotion that lifts a quick look to full, and the
surfaces that carry the tier (``klein next`` / ``status`` / ``map``, ``klein new --rigor``,
``klein promote``).
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from test_schemas import assert_conforms
from test_workflow_v3 import _fill, commit_all, git, metric_command, rehearse

from kleinlib import api, cli
from kleinlib import contract as contract_module
from kleinlib.claims import add_claim, init_lock, load_lock, verify_lock, write_lock
from kleinlib.contract import load_contract, required_gates, rigor, validate_contract
from kleinlib.next_step import next_step, status_data
from kleinlib.scaffold import scaffold_study
from kleinlib.study_map import build_map, format_map, render_html
from kleinlib.workflow import (
    WorkflowError,
    finalize,
    load_manifests,
    load_state,
    promote_study,
    read_events,
    record_gate,
    run_one,
    sealed_dry_run,
    status_summary,
    verify_study,
)

FINDINGS = """\
# Findings

The study is exploratory.

- **[C1]** The candidate scores 0.7 on the development split.

## ② Registered predictions (from the ledger)

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | the frontier clears 0.6 | primary_metric > 0.6 | 0.7 | supported | E0001 | program.md 2026-09-03 |
"""

PREDICTION = {
    "id": "P1",
    "track": "primary",
    "statement": "the frontier clears 0.6",
    "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
}


def make_study(
    tmp_path: Path,
    *,
    rigor_value: str,
    gates: tuple[str, ...] = ("consult", "data"),
    predictions: bool = True,
) -> tuple[Path, Path]:
    """A schema-3 study, scaffolded at the given rigor, with exactly ``gates`` recorded."""
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
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="the maintainers of this test suite",
        rigor=rigor_value,
    )
    _fill(study)
    if predictions:
        path = study / "study.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["predictions"] = [PREDICTION]
        path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief method.\n", encoding="utf-8")
    for gate in gates:
        record_gate(study, gate, acknowledged_by="tester")
    commit_all(repo, "ready study")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")
    return repo, study


@pytest.fixture
def quick_study(tmp_path: Path) -> tuple[Path, Path]:
    return make_study(tmp_path, rigor_value="quick")


def candidate(study: Path, marker: str) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\n# {marker}\n", encoding="utf-8")


def run_candidate(study: Path, marker: str = "idea", value: float = 0.7, **kwargs):
    candidate(study, marker)
    return run_one(study, command=metric_command(value), echo=False, **kwargs)


def amend_rigor(repo: Path, study: Path, value: str) -> None:
    """Flip policy.rigor and re-record the consult gate, which hashes study.yaml."""
    path = study / "study.yaml"
    path.write_text(re.sub(r"rigor: \w+", f"rigor: {value}", path.read_text(encoding="utf-8")), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note="rigor amended")
    commit_all(repo, "amend rigor")


def close_quick(repo: Path, study: Path) -> str:
    """Run once, write findings and finalize: no flag, no referee."""
    run_candidate(study, tests="P1")
    (study / "findings.md").write_text(FINDINGS, encoding="utf-8")
    commit_all(repo, "findings")
    return finalize(study)


def run_cli(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, out.getvalue()


# ---------------------------------------------------------------------------
# 1. the gates
# ---------------------------------------------------------------------------


def test_a_quick_study_runs_with_only_consult_and_data_recorded(quick_study) -> None:
    _, study = quick_study
    state = load_state(study, load_contract(study))
    assert state["gates"]["method"]["status"] == "pending"
    assert required_gates(load_contract(study)) == ("consult", "data")
    manifest = run_candidate(study)
    assert manifest["disposition"] == "keep"


def test_a_full_study_with_the_same_two_gates_is_still_refused(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="full")
    candidate(study, "idea")
    with pytest.raises(WorkflowError, match="method"):
        run_one(study, command=metric_command(0.7), echo=False)
    assert load_manifests(study) == []


# ---------------------------------------------------------------------------
# 2. no sealed run
# ---------------------------------------------------------------------------


def test_the_sealed_run_is_refused_under_quick_and_nothing_is_spent(quick_study) -> None:
    repo, study = quick_study
    head = git(repo, "rev-parse", "HEAD")
    with pytest.raises(WorkflowError, match="promote"):
        run_one(study, final_test=True, command=metric_command(0.7), echo=False)
    assert not list((study / "runs").glob("E*"))
    state = load_state(study, load_contract(study))
    assert state["final_holdout_access"]["primary"]["count"] == 0
    assert git(repo, "rev-parse", "HEAD") == head


def test_the_rehearsal_is_refused_under_quick_and_nothing_is_spent(quick_study) -> None:
    _, study = quick_study
    with pytest.raises(WorkflowError, match="promote"):
        sealed_dry_run(study, command=metric_command(0.7), echo=False)
    assert not list((study / "runs").glob("E*"))
    assert load_state(study, load_contract(study))["final_holdout_access"]["primary"]["count"] == 0


# ---------------------------------------------------------------------------
# 3. every phase is adaptive
# ---------------------------------------------------------------------------


def _enter_final_phase(repo: Path, study: Path) -> None:
    run_candidate(study, "first")
    commit_all(repo, "first run")
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "phase acknowledged")
    assert load_state(study, load_contract(study))["current_phase"] == "confirmation"


def test_a_development_run_is_allowed_in_the_final_phase_under_quick(quick_study) -> None:
    repo, study = quick_study
    _enter_final_phase(repo, study)
    manifest = run_candidate(study, "second", value=0.72)
    assert manifest["phase"] == "confirmation"
    assert manifest["evaluation_kind"] != "final_test"


def test_a_development_run_is_still_refused_in_the_final_phase_under_full(tmp_path: Path) -> None:
    repo, study = make_study(tmp_path, rigor_value="full", gates=("consult", "data", "method"))
    _enter_final_phase(repo, study)
    candidate(study, "second")
    with pytest.raises(WorkflowError, match="development runs are forbidden in final phase"):
        run_one(study, command=metric_command(0.72), echo=False)


# ---------------------------------------------------------------------------
# 4. the claim cap
# ---------------------------------------------------------------------------

CLAIM = {
    "claim_class": "empirical-description",
    "claim": "The candidate scores 0.7 on the development split.",
}


def lock_with_claim(repo: Path, study: Path) -> None:
    run_candidate(study, tests="P1")
    (study / "findings.md").write_text(FINDINGS, encoding="utf-8")
    commit_all(repo, "run and findings")
    init_lock(study)
    add_claim(study, "C1", strength="exploratory", evidence=["E0001"], **CLAIM)


def test_claims_add_refuses_confirmed_under_quick(quick_study) -> None:
    repo, study = quick_study
    lock_with_claim(repo, study)
    with pytest.raises(WorkflowError, match="quick look"):
        add_claim(study, "C2", strength="confirmed", evidence=["E0001"], commit=False, **CLAIM)


def test_claims_add_accepts_exploratory_under_quick(quick_study) -> None:
    repo, study = quick_study
    lock_with_claim(repo, study)
    add_claim(study, "C2", strength="exploratory", evidence=["E0001"], **CLAIM)
    assert load_lock(study)["claims"]["C2"]["strength"] == "exploratory"


def _shape(study: Path):
    return next(c for c in verify_lock(study) if c.name == "claims shape")


def _lock_with_a_confirmed_claim(repo: Path, study: Path) -> None:
    lock_with_claim(repo, study)
    lock = load_lock(study)
    lock["claims"]["C1"]["strength"] = "confirmed"
    write_lock(study, lock)


def test_a_lock_carrying_a_confirmed_claim_fails_the_claims_shape_under_quick(quick_study) -> None:
    repo, study = quick_study
    _lock_with_a_confirmed_claim(repo, study)
    shape = _shape(study)
    assert not shape.ok
    assert "capped at 'exploratory'" in shape.message


def test_a_lock_carrying_a_confirmed_claim_passes_the_claims_shape_under_full(tmp_path: Path) -> None:
    repo, study = make_study(tmp_path, rigor_value="full", gates=("consult", "data", "method"))
    _lock_with_a_confirmed_claim(repo, study)
    assert _shape(study).ok


# ---------------------------------------------------------------------------
# 5. closing
# ---------------------------------------------------------------------------


def test_finalize_under_quick_needs_no_flag_and_no_referee(quick_study) -> None:
    repo, study = quick_study
    assert close_quick(repo, study) == "exploratory"
    finalization = load_state(study, load_contract(study))["finalization"]
    assert finalization["label"] == "exploratory"
    assert finalization["rigor"] == "quick"
    assert finalization["referee"]["status"] == "not-required"


def test_a_full_study_finalization_has_no_rigor_key(tmp_path: Path) -> None:
    repo, study = make_study(tmp_path, rigor_value="full", gates=("consult", "data", "method"))
    run_candidate(study, tests="P1")
    (study / "findings.md").write_text(FINDINGS, encoding="utf-8")
    commit_all(repo, "findings")
    finalize(study, allow_exploratory=True, no_referee=True, referee_reason="solo test run")
    finalization = load_state(study, load_contract(study))["finalization"]
    assert "rigor" not in finalization
    assert finalization["referee"]["status"] == "unrefereed"


# ---------------------------------------------------------------------------
# 6. verify
# ---------------------------------------------------------------------------


def test_verify_on_a_finalized_quick_look_has_no_failing_check_and_says_not_required(quick_study) -> None:
    repo, study = quick_study
    close_quick(repo, study)
    commit_all(repo, "closed")
    checks = verify_study(study)
    assert [c for c in checks if not c.ok] == []
    by_name = {c.name: c.message for c in checks}
    assert "not required (quick look" in by_name["referee gate"]
    assert by_name["gate method"] == "not required (quick look)"
    receipt = json.loads((study / "verify_receipt.json").read_text(encoding="utf-8"))
    assert receipt["rigor"] == "quick"


def test_a_full_study_receipt_has_no_rigor_key(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="full", gates=("consult", "data", "method"))
    verify_study(study)
    receipt = json.loads((study / "verify_receipt.json").read_text(encoding="utf-8"))
    assert "rigor" not in receipt


# ---------------------------------------------------------------------------
# 7. klein next
# ---------------------------------------------------------------------------


def _next(study: Path) -> dict:
    return next_step(study)["next"]


def test_next_after_data_is_the_experiment_loop_under_quick(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="quick", gates=("consult",))
    assert _next(study)["stage_id"] == "data"
    record_gate(study, "data", acknowledged_by="tester")
    result = next_step(study)
    assert result["rigor"] == "quick"
    assert result["next"]["stage_id"] == "experiment"
    assert any("not required for a quick look" in note for note in result["notes"])


def test_next_under_full_after_data_still_asks_for_the_method_gate(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="full")
    assert _next(study)["stage_id"] == "method"
    assert next_step(study)["rigor"] == "full"


def test_next_never_names_a_sealed_action_under_quick(quick_study) -> None:
    repo, study = quick_study
    run_candidate(study, "first")
    commit_all(repo, "first run")
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "phase acknowledged")
    assert load_state(study, load_contract(study))["current_phase"] == "confirmation"
    nxt = _next(study)
    assert "sealed" not in nxt["stage"] and "--final-test" not in (nxt["command"] or "")
    # the same position under full is the rehearsal
    amend_rigor(repo, study, "full")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "method")
    assert _next(study)["stage"] == "EXPERIMENT · sealed"


def test_next_after_claims_is_finalize_with_no_referee_stage_under_quick(quick_study) -> None:
    repo, study = quick_study
    lock_with_claim(repo, study)
    nxt = _next(study)
    assert nxt["stage_id"] == "finalize"
    assert "klein finalize" in nxt["command"]
    assert "referee" not in nxt["action"].lower().replace("needs no referee", "")


def test_next_after_findings_without_a_lock_asks_for_the_lock_under_quick(quick_study) -> None:
    repo, study = quick_study
    run_candidate(study, tests="P1")
    (study / "findings.md").write_text(FINDINGS, encoding="utf-8")
    commit_all(repo, "findings")
    assert "claims.lock" in _next(study)["action"]


def test_the_tutorial_stays_after_finalize_and_is_said_to_be_optional(quick_study) -> None:
    repo, study = quick_study
    close_quick(repo, study)
    nxt = _next(study)
    assert nxt["stage_id"] == "tutorial"
    assert "optional" in nxt["why"]


# ---------------------------------------------------------------------------
# 8. promotion
# ---------------------------------------------------------------------------


def test_promote_requires_a_reason_and_a_name(quick_study) -> None:
    _, study = quick_study
    with pytest.raises(WorkflowError, match="--reason"):
        promote_study(study, reason=" ", promoted_by="alice")
    with pytest.raises(WorkflowError, match="--promoted-by"):
        promote_study(study, reason="it matters now", promoted_by="")
    assert rigor(load_contract(study)) == "quick"


def test_promote_flips_only_the_rigor_value_in_study_yaml(quick_study) -> None:
    _, study = quick_study
    before = (study / "study.yaml").read_text(encoding="utf-8")
    promote_study(study, reason="it now deserves the full path", promoted_by="alice")
    after = (study / "study.yaml").read_text(encoding="utf-8")
    assert after == before.replace("rigor: quick", "rigor: full")
    assert rigor(load_contract(study)) == "full"


def test_promote_appends_exactly_one_event_with_both_contract_hashes(quick_study) -> None:
    from kleinlib.primitives import sha256_file

    _, study = quick_study
    sha_before = sha256_file(study / "study.yaml")
    promote_study(study, reason="why", promoted_by="alice")
    events = [e for e in read_events(study) if e["type"] == "rigor_promoted"]
    assert len(events) == 1
    event = events[0]
    assert (event["from"], event["to"]) == ("quick", "full")
    assert (event["reason"], event["promoted_by"]) == ("why", "alice")
    assert event["contract_sha256_before"] == sha_before
    assert event["contract_sha256_after"] == sha256_file(study / "study.yaml") != sha_before


def test_promote_commits_only_its_own_files(quick_study) -> None:
    repo, study = quick_study
    promote_study(study, reason="why", promoted_by="alice")
    assert git(repo, "status", "--porcelain") == ""
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(Path(name).name for name in changed) == ["events.jsonl", "study.yaml"]


def test_promote_refuses_a_study_already_at_full_rigor(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="full")
    with pytest.raises(WorkflowError, match="already at full rigor"):
        promote_study(study, reason="why", promoted_by="alice")


def test_promote_refuses_a_finalized_quick_look(quick_study) -> None:
    repo, study = quick_study
    close_quick(repo, study)
    with pytest.raises(WorkflowError, match="finalized"):
        promote_study(study, reason="why", promoted_by="alice")
    assert rigor(load_contract(study)) == "quick"


def test_after_promotion_a_run_is_refused_while_consult_is_stale_even_with_method_recorded(quick_study) -> None:
    repo, study = quick_study
    promote_study(study, reason="the answer now matters", promoted_by="alice")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "method recorded")
    candidate(study, "after promotion")
    with pytest.raises(WorkflowError, match="changed after acknowledgement"):
        run_one(study, command=metric_command(0.71), echo=False)
    assert load_manifests(study) == []


def test_after_promotion_a_run_waits_for_consult_and_method_then_the_sealed_look_needs_its_rehearsal(
    quick_study,
) -> None:
    repo, study = quick_study
    run_candidate(study, "while quick")
    commit_all(repo, "a quick run")
    promote_study(study, reason="the answer now matters", promoted_by="alice")

    candidate(study, "after promotion")
    with pytest.raises(WorkflowError, match="gate method"):
        run_one(study, command=metric_command(0.71), echo=False)
    # klein next leads to the re-acknowledgement, then to METHOD
    assert _next(study)["stage_id"] == "consult"
    assert "changed after Gate 0" in _next(study)["action"]
    record_gate(study, "consult", acknowledged_by="tester", note="promoted to full")
    commit_all(repo, "re-acknowledged")
    assert _next(study)["stage_id"] == "method"
    with pytest.raises(WorkflowError, match="gate method"):
        run_one(study, command=metric_command(0.71), echo=False)
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "method recorded")
    assert _next(study)["stage_id"] == "experiment"
    assert run_one(study, command=metric_command(0.71), echo=False)["disposition"] == "keep"

    # the sealed look is now available, and needs its rehearsal as usual
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "phase acknowledged")
    with pytest.raises(WorkflowError, match="not rehearsed"):
        run_one(study, final_test=True, command=metric_command(0.7), echo=False)
    rehearse(study, command=metric_command(0.7))
    sealed = run_one(study, final_test=True, command=metric_command(0.7), echo=False)
    assert sealed["evaluation_kind"] == "final_test"


# ---------------------------------------------------------------------------
# 9. an engine without the key
# ---------------------------------------------------------------------------


def test_an_engine_without_the_rigor_key_refuses_a_quick_contract(quick_study, monkeypatch) -> None:
    _, study = quick_study
    contract = load_contract(study)
    assert validate_contract(contract, study) == []
    older = {k: v for k, v in contract_module.POLICY_VALUES.items() if k != "rigor"}
    monkeypatch.setattr(contract_module, "POLICY_VALUES", older)
    problems = validate_contract(contract, study)
    assert any("rigor" in problem and "policy" in problem for problem in problems), problems


# ---------------------------------------------------------------------------
# 10. the command line and the API
# ---------------------------------------------------------------------------


def test_klein_new_rigor_quick_writes_the_policy(tmp_path: Path) -> None:
    code, _ = run_cli(["new", "04-look", "--root", str(tmp_path), "--goal", "g", "--rigor", "quick"])
    assert code == 0
    contract = yaml.safe_load((tmp_path / "04-look" / "study.yaml").read_text(encoding="utf-8"))
    assert contract["policy"] == {"rigor": "quick"}
    for name in ("program.md", "research_plan.md"):
        assert "quick look" in (tmp_path / "04-look" / name).read_text(encoding="utf-8")
    assert (tmp_path / "04-look" / "program.md").read_text(encoding="utf-8").count("klein promote") == 1


def test_klein_new_default_writes_no_policy_and_no_quick_sentence(tmp_path: Path) -> None:
    run_cli(["new", "04-full", "--root", str(tmp_path), "--goal", "g"])
    text = (tmp_path / "04-full" / "study.yaml").read_text(encoding="utf-8")
    assert "policy:" not in text
    assert "quick look" not in (tmp_path / "04-full" / "program.md").read_text(encoding="utf-8")


def test_klein_new_rigor_quick_merges_into_a_recipe_policy_block(tmp_path: Path) -> None:
    code, _ = run_cli(["new", "04-rec", "--root", str(tmp_path), "--recipe", "tabular-predict", "--rigor", "quick"])
    assert code == 0
    text = (tmp_path / "04-rec" / "study.yaml").read_text(encoding="utf-8")
    assert text.count("\npolicy:\n") == 1
    contract = yaml.safe_load(text)
    assert contract["policy"]["rigor"] == "quick"
    assert contract["policy"]["noise_floor"] == "required"


def test_klein_promote_text_and_json_conform_to_the_schema(quick_study, capsys) -> None:
    _, study = quick_study
    code, out = run_cli(
        ["promote", "--study", str(study), "--reason", "it matters now", "--promoted-by", "alice", "--json"]
    )
    assert code == 0
    envelope = json.loads(out)
    assert assert_conforms(envelope) == "promote"
    assert envelope["data"]["rigor"] == "full"
    assert envelope["data"]["event"] >= 1


def test_klein_promote_prints_what_changed_and_the_next_command(quick_study) -> None:
    _, study = quick_study
    code, out = run_cli(["promote", "--study", str(study), "--reason", "r", "--promoted-by", "alice"])
    assert code == 0
    assert "full" in out
    assert "klein gate record consult" in out


def test_klein_promote_requires_reason_and_name_on_the_command_line(quick_study) -> None:
    _, study = quick_study
    with pytest.raises(SystemExit):
        cli.main(["promote", "--study", str(study), "--reason", "r"])


def test_api_promote_conforms_and_a_refusal_is_an_envelope(quick_study, tmp_path: Path) -> None:
    _, study = quick_study
    ok = api.promote(study, reason="r", promoted_by="alice")
    assert ok["ok"] and assert_conforms(ok) == "promote"
    again = api.promote(study, reason="r", promoted_by="alice")
    assert not again["ok"] and again["data"] == {}
    assert assert_conforms(again) == "promote"
    assert "already at full rigor" in again["problems"][0]["message"]


def test_status_and_next_json_carry_the_rigor_and_conform(quick_study) -> None:
    _, study = quick_study
    for verb in ("status", "next"):
        code, out = run_cli([verb, "--study", str(study), "--json"])
        assert code == 0
        envelope = json.loads(out)
        assert assert_conforms(envelope) == verb
        assert envelope["data"]["rigor"] == "quick"
    assert status_data(study)["rigor"] == "quick"


def test_status_text_says_quick_look_and_never_unrefereed(quick_study) -> None:
    repo, study = quick_study
    before = status_summary(study)
    assert "rigor: quick look (claims capped at exploratory; promote with klein promote)" in before
    assert "referee: not required (quick look)" in before
    close_quick(repo, study)
    after = status_summary(study)
    assert "referee: not required (quick look)" in after
    assert "unrefereed" not in after and "not recorded" not in after.split("referee:")[1].splitlines()[0]


def test_status_text_for_a_full_study_has_no_rigor_line(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="full")
    text = status_summary(study)
    assert "rigor:" not in text
    assert "referee: not recorded (Gate 3 runs before finalize)" in text


# ---------------------------------------------------------------------------
# 11. the map and the report
# ---------------------------------------------------------------------------


def test_the_map_shows_quick_look(quick_study) -> None:
    _, study = quick_study
    data = build_map(study)
    assert data["rigor"] == "quick"
    assert "quick look" in format_map(data)
    assert "quick look" in render_html(data)
    code, out = run_cli(["map", "--study", str(study), "--json"])
    assert assert_conforms(json.loads(out)) == "map"


def test_the_map_of_a_full_study_does_not_say_quick_look(tmp_path: Path) -> None:
    _, study = make_study(tmp_path, rigor_value="full")
    data = build_map(study)
    assert data["rigor"] == "full"
    assert "quick look" not in format_map(data)


def test_git_is_clean_after_the_whole_quick_life(quick_study) -> None:
    repo, study = quick_study
    close_quick(repo, study)
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True).stdout.strip() == ""
