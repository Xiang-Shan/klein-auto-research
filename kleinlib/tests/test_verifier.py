"""E4b — the declared verifier: trust the checker, never the searcher.

A searcher reporting its own score is the oldest way to be wrong without lying:
a construction that grades itself, a training loop that scores its own
checkpoint, a simulator scoring its own design. When a track declares a
verifier, ``klein run-one`` re-derives the objective in a SECOND immutable
process from the artifact the run produced, and the disposition is decided on
THAT number.

The properties pinned here: agreement records both values; disagreement beyond
tolerance is a crash, not a discard; a verifier that cannot produce a number is
a crash; the checker may never live in the mutable surface; it is hashed at the
METHOD gate and frozen after E0001; an `exact` metric waives the measured floor;
and a declared external incumbent means a `keep` is "beat the literature".
"""

from __future__ import annotations

import itertools
import json
import subprocess
from pathlib import Path

import pytest
import yaml
from test_workflow_v3 import metric_command

from kleinlib.contract import validate_contract
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import (
    VERIFIER_DISAGREEMENT,
    VERIFIER_FAILED,
    load_state,
    preflight_checks,
    record_gate,
    run_one,
)

SEARCH = """\
import json
import pathlib

value = {reported}
path = pathlib.Path("models/solution.json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps({{"value": {artifact_value}}}))
print("artifact_path:     models/solution.json")
print("primary_metric:    %s" % value)
print("metric_name:       objective")
print("metric_goal:       higher")
"""

VERIFY = """\
import json
import os
import pathlib

artifact = pathlib.Path(os.environ["KLEIN_ARTIFACT"])
value = json.loads(artifact.read_text())["value"]
print("wall_seconds:      0.5")
print("primary_metric:    %s" % value)
print("metric_name:       objective")
print("metric_goal:       higher")
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    if _git(repo, "status", "--porcelain") == "":
        return
    _git(repo, "-c", "user.name=T", "-c", "user.email=t@e.invalid", "commit", "-q", "-m", message)


def _edit_contract(study: Path, transform) -> dict:
    """Rewrite study.yaml and re-record the consult gate, which hashes it.

    study.yaml is a gate artifact: changing it after acknowledgement is exactly
    what the gate-hash check refuses. A study that amends its contract re-records
    the gate, which leaves the amendment on the event trail — so the tests do the
    same rather than reaching around the mechanism.
    """
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    transform(contract)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester", note="contract amended")
    return contract


@pytest.fixture
def optimize_study(tmp_path: Path) -> tuple[Path, Path]:
    """A schema-3 ``optimize`` study: a searcher, a checker, gates recorded."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies",
        "11-construction",
        goal="find an object the checker accepts",
        domain="combinatorics",
        target="objective",
        task_type="scalar",
        method_depth="brief",
        family="local-search",
        metric_name="objective",
        metric_goal="higher",
        minimum_delta=1.0,
        data_source="synthetic:prepare.py",
        data_path="data/prepared/seed.csv",
        split_kind="none",
        max_run_seconds=60,
        schema_version=3,
        kind="optimize",
        modality="none",
        profile="math",
        audience="combinatorialists",
    )
    for name in ("study.yaml", "program.md", "research_plan.md"):
        path = study / name
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace("{{RQ1_QUESTION}}", "does a better object exist?")
            .replace("{{RQ1_PRIOR}}", "unknown")
            .replace("{{LEVER_1}}", "swap rate")
            .replace("{{DELTA_1}}", "+1"),
            encoding="utf-8",
        )
    # An exact objective: the floor is waived, the resolution is declared.
    _edit_contract(
        study,
        lambda c: c["tracks"]["primary"]["metric"].update(
            exactness="exact", exactness_note="integer objective; resolution 1"
        ),
    )
    (study / "data" / "prepared").mkdir(parents=True)
    (study / "data" / "prepared" / "seed.csv").write_text("seed\n1\n", encoding="utf-8")
    (study / "data_card.md").write_text(
        "# Data card\n\n## Verifier card\n\nExact checker.\n\n> **Decision:** **GO**\n",
        encoding="utf-8",
    )
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    (study / "verify.py").write_text(VERIFY, encoding="utf-8")
    (study / "search.py").write_text(SEARCH.format(reported=10, artifact_value=10), encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    _commit(repo, "an optimize study with a declared checker")
    _git(repo, "switch", "-q", "-c", "experiments/11-construction")
    return repo, study


#: One candidate is one falsifiable edit, so every rewrite differs from HEAD —
#: run-one refuses an unchanged surface before it allocates anything.
_CANDIDATE = itertools.count(1)


def _search(study: Path, *, reported: float, artifact_value: float) -> None:
    (study / "search.py").write_text(
        SEARCH.format(reported=reported, artifact_value=artifact_value)
        + f"# candidate {next(_CANDIDATE)}\n",
        encoding="utf-8",
    )


def _artifact_key(study: Path, key: str = "artifact_path") -> None:
    _edit_contract(
        study, lambda c: c["tracks"]["primary"]["verifier"].update(artifact_key=key)
    )


# ---------------------------------------------------------------------------
# 1. agreement
# ---------------------------------------------------------------------------


def test_the_verifier_number_decides_and_both_values_are_recorded(optimize_study) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    _commit(repo, "point the verifier at the printed artifact key")
    _search(study, reported=10, artifact_value=10)
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "keep"
    assert manifest["metric"] == {"reported": 10.0, "verified": 10.0}
    assert manifest["primary_metric"] == 10.0
    assert manifest["verifier"]["command"][-1] == "verify.py"
    assert manifest["verifier"]["artifact"] == "models/solution.json"
    assert set(manifest["verifier"]["sha256"]) == {"verify.py"}
    assert manifest["verifier"]["exit_code"] == 0
    # The checker ran as its own bounded subprocess with its own log.
    assert (study / "runs" / "E0001" / "verify.log").is_file()


def test_a_guardrail_the_checker_printed_wins(optimize_study) -> None:
    """Either process may print a guardrail; the verifier's value is the one used."""
    repo, study = optimize_study
    _artifact_key(study)
    _edit_contract(
        study,
        lambda c: c["tracks"]["primary"].update(guardrails={"wall_seconds": {"max": 1.0}}),
    )
    _commit(repo, "a guardrail both processes could print")
    # The searcher claims a wall_seconds that would fail; the checker prints 0.5.
    (study / "search.py").write_text(
        SEARCH.format(reported=10, artifact_value=10) + "print('wall_seconds:      99.0')\n",
        encoding="utf-8",
    )
    manifest = run_one(study, echo=False)
    assert manifest["disposition"] == "keep"
    assert manifest["metrics"]["wall_seconds"] == 0.5


# ---------------------------------------------------------------------------
# 2. disagreement and failure are crashes, not discards
# ---------------------------------------------------------------------------


def test_disagreement_beyond_tolerance_is_a_crash(optimize_study) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    _commit(repo, "point the verifier at the printed artifact key")
    _search(study, reported=99, artifact_value=10)  # the search flatters itself
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "crash"
    assert VERIFIER_DISAGREEMENT in manifest["decision_reason"]
    assert "99" in manifest["decision_reason"] and "10" in manifest["decision_reason"]
    assert manifest["primary_metric"] is None  # a crash records no metric
    assert manifest["metric"] == {"reported": 99.0, "verified": 10.0}


def test_a_tolerance_admits_a_small_difference(optimize_study) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    _edit_contract(
        study, lambda c: c["tracks"]["primary"]["verifier"].update(tolerance=0.5)
    )
    _commit(repo, "declare a tolerance")
    _search(study, reported=10.2, artifact_value=10.0)
    manifest = run_one(study, echo=False)
    assert manifest["disposition"] == "keep"
    assert manifest["primary_metric"] == 10.0  # the CHECKER's number is the record


def test_a_crashing_verifier_is_a_crash_with_its_own_reason(optimize_study) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    (study / "verify.py").write_text("raise SystemExit(4)\n", encoding="utf-8")
    _commit(repo, "a checker that cannot check")
    _search(study, reported=10, artifact_value=10)
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "crash"
    assert VERIFIER_FAILED in manifest["decision_reason"]
    assert "exited 4" in manifest["decision_reason"]
    assert manifest["verifier"]["exit_code"] == 4


def test_a_run_that_declares_no_artifact_cannot_be_checked(optimize_study) -> None:
    repo, study = optimize_study
    _artifact_key(study, "solution")  # the contract asks for a key the run never prints
    _commit(repo, "an artifact key the searcher does not print")
    _search(study, reported=10, artifact_value=10)
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "crash"
    assert VERIFIER_FAILED in manifest["decision_reason"]
    assert "printed no `solution:` line" in manifest["decision_reason"]


# ---------------------------------------------------------------------------
# 3. the checker is never the searcher
# ---------------------------------------------------------------------------


def test_a_verifier_inside_the_mutable_surface_is_refused_by_the_contract(
    optimize_study,
) -> None:
    _, study = optimize_study
    contract = _edit_contract(
        study, lambda c: c["entrypoint"].update(mutable=["search.py", "verify.py"])
    )
    problems = validate_contract(contract, study)
    assert any("the checker is never the searcher" in p for p in problems)
    # ... and run-one refuses to start at all on an invalid contract.
    with pytest.raises(Exception, match="invalid study contract"):
        run_one(study, echo=False)


def test_the_method_gate_hashes_the_verifier_and_freezes_it_after_e0001(
    optimize_study,
) -> None:
    repo, study = optimize_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    recorded = load_state(study, contract)["fingerprints"]["verifier"]
    assert set(recorded) == {"verify.py"}

    # Before any evidence, an edit is a [WARN]: re-record the gate.
    _artifact_key(study)
    (study / "verify.py").write_text(VERIFY + "# a late thought\n", encoding="utf-8")
    _commit(repo, "edit the checker before E0001")
    check = next(c for c in preflight_checks(study) if c.name == "verifier")
    assert check.ok and "[WARN] verifier differs" in check.message

    record_gate(study, "method", acknowledged_by="tester")
    _commit(repo, "re-record the method gate")
    assert next(c for c in preflight_checks(study) if c.name == "verifier").ok

    _search(study, reported=10, artifact_value=10)
    run_one(study, echo=False)

    # After E0001 the checker is frozen: every recorded disposition was decided
    # by the previous one.
    (study / "verify.py").write_text(VERIFY + "# too late\n", encoding="utf-8")
    _commit(repo, "edit the checker after evidence exists")
    check = next(c for c in preflight_checks(study) if c.name == "verifier")
    assert not check.ok
    assert "verifier changed after evidence exists" in check.message
    assert "the checker is never the searcher" in check.message


def test_a_study_without_a_verifier_reports_so(ready_study_v3) -> None:
    _, study = ready_study_v3
    check = next(c for c in preflight_checks(study) if c.name == "verifier")
    assert check.ok and check.message == "no track declares a verifier"


# ---------------------------------------------------------------------------
# 4. exactness waives the measured floor
# ---------------------------------------------------------------------------


def test_exact_mode_waives_the_floor_requirement(optimize_study) -> None:
    _, study = optimize_study
    check = next(c for c in preflight_checks(study) if c.name == "noise floor")
    assert check.ok
    assert "exactness=exact — floor waived" in check.message
    assert "resolution" in check.message


def test_exact_mode_refuses_a_floor_block_with_a_non_zero_spread(optimize_study) -> None:
    """A deterministic objective has no spread; one of the two claims is wrong."""
    repo, study = optimize_study
    _edit_contract(
        study,
        lambda c: c["tracks"]["primary"]["metric"].update(
            noise_floor={"k": 5, "std": 0.4, "range": 1.0}
        ),
    )
    _commit(repo, "a floor that contradicts the exactness claim")
    check = next(c for c in preflight_checks(study) if c.name == "noise floor")
    assert not check.ok
    assert "a deterministic objective has no spread" in check.message


def test_a_stochastic_track_still_needs_its_measured_floor(ready_study_v3) -> None:
    _, study = ready_study_v3
    check = next(c for c in preflight_checks(study) if c.name == "noise floor")
    assert "exactness" not in check.message
    assert "not measured" in check.message


# ---------------------------------------------------------------------------
# 5. the external incumbent
# ---------------------------------------------------------------------------


def _declare_external(study: Path, value: float) -> None:
    _edit_contract(
        study,
        lambda c: c["tracks"]["primary"]["metric"].update(
            incumbent_external={
                "value": value,
                "source": "Smith & Jones 2019, Table 2",
                "verified_on": "2026-08-01",
            }
        ),
    )


def test_a_first_result_that_only_matches_the_literature_is_a_discard(
    optimize_study,
) -> None:
    """Found / matched / improved — never proved. The match is disclosed."""
    repo, study = optimize_study
    _artifact_key(study)
    _declare_external(study, 10.0)
    _commit(repo, "seed the frontier from the literature")
    _search(study, reported=10, artifact_value=10)
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "discard"
    assert manifest["matched_external"] is True
    assert "external incumbent 10" in manifest["decision_reason"]


def test_beating_the_external_incumbent_by_the_minimum_delta_is_a_keep(
    optimize_study,
) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    _declare_external(study, 10.0)
    _commit(repo, "seed the frontier from the literature")
    _search(study, reported=11, artifact_value=11)
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "keep"
    assert manifest["matched_external"] is False
    assert "frontier improvement over 10" in manifest["decision_reason"]


def test_falling_short_of_the_literature_is_a_discard_not_an_impossibility(
    optimize_study,
) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    _declare_external(study, 10.0)
    _commit(repo, "seed the frontier from the literature")
    _search(study, reported=8, artifact_value=8)
    manifest = run_one(study, echo=False)

    assert manifest["disposition"] == "discard"
    assert manifest["matched_external"] is False
    # The run is retained evidence of a search limit, with its number intact.
    assert manifest["primary_metric"] == 8.0
    assert json.loads(
        (study / "runs" / "E0001" / "manifest.json").read_text(encoding="utf-8")
    )["matched_external"] is False


def test_without_a_verifier_the_match_is_decided_at_the_tracks_minimum_delta(
    ready_study_v3,
) -> None:
    """"Matched" needs a resolution, and a bare float equality is not one.

    With a checker declared, its tolerance says how close counts as reaching
    the published value.  Without one, the honest resolution is the track's own
    measured ``minimum_delta`` — the same number that decides every other
    "did it move?" question on that track.  (Tolerance 0.0 would make
    ``matched_external`` a coin flip on the last float bit.)
    """
    repo, study = ready_study_v3
    _edit_contract(
        study,
        lambda c: c["tracks"]["primary"]["metric"].update(
            minimum_delta=0.05,
            incumbent_external={
                "value": 0.70,
                "source": "Smith & Jones 2019, Table 2",
                "verified_on": "2026-08-01",
            },
        ),
    )
    _commit(repo, "seed the frontier from the literature, no checker declared")
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")

    manifest = run_one(study, command=metric_command(0.72), echo=False)

    # 0.72 does not clear 0.70 + 0.05, so it is a discard …
    assert manifest["disposition"] == "discard"
    # … and |0.72 - 0.70| <= 0.05, so it MATCHED the literature and says so.
    assert manifest["matched_external"] is True


def test_without_an_external_incumbent_the_first_result_is_still_a_keep(
    optimize_study,
) -> None:
    repo, study = optimize_study
    _artifact_key(study)
    _commit(repo, "no literature value declared")
    _search(study, reported=1, artifact_value=1)
    manifest = run_one(study, echo=False)
    assert manifest["disposition"] == "keep"
    assert "first valid result on this track" in manifest["decision_reason"]
    assert "matched_external" not in manifest


def test_preflight_discloses_headroom_against_an_external_incumbent(
    optimize_study,
) -> None:
    """Disclosure must resolve the same incumbent enforcement does.

    With `metric.incumbent_external` seeding the frontier, a track HAS an
    incumbent before its first keep — and when that value equals the declared
    ideal, run-one refuses development runs on h = 0. Preflight used to report
    "no incumbent yet ... audited at first keep" for exactly that study, so the
    disclosure disagreed with the enforcement.
    """
    repo, study = optimize_study
    _artifact_key(study)
    _edit_contract(
        study,
        lambda c: c["tracks"]["primary"]["metric"].update(
            {
                "bound": {"ideal": 22, "on_infeasible": "ack"},
                "incumbent_external": {
                    "value": 22,
                    "source": "the pigeonhole bound, which is also the best known value",
                    "verified_on": "2026-09-03",
                },
            }
        ),
    )
    _commit(repo, "an externally seeded frontier at the proven maximum")

    check = next(c for c in preflight_checks(study, require_clean=False) if c.name == "headroom")
    assert check.ok
    assert "h = (22 - 22) / 1 = 0.000" in check.message
    assert "NO keep is arithmetically possible" in check.message

    # …and the ack run-one demands has to be RECORDABLE in that same state.
    from kleinlib.workflow import acknowledge_headroom

    entry = acknowledge_headroom(
        study,
        track="primary",
        acknowledged_by="tester",
        note="run-anyway: the best known value is the proven maximum",
    )
    assert entry["h"] == 0.0 and entry["incumbent"] == 22.0 and entry["infeasible"] is True
    check = next(c for c in preflight_checks(study, require_clean=False) if c.name == "headroom")
    assert "acknowledged by tester" in check.message


def test_preflight_checks_the_declared_entrypoint_not_the_literal_train_py(
    optimize_study,
) -> None:
    """An `optimize` study's surface is `search.py`; preflight must check THAT.

    The check hard-coded `train.py` — a v1 leftover — so every study whose kind
    names a different entrypoint failed its own preflight with "train.py:
    missing" and could never start its loop.
    """
    _, study = optimize_study
    assert (study / "search.py").is_file()
    assert not (study / "train.py").exists()
    names = {check.name for check in preflight_checks(study, require_clean=False)}
    assert "search.py" in names
    assert "train.py" not in names

    check = next(c for c in preflight_checks(study, require_clean=False) if c.name == "search.py")
    assert check.ok and check.message == "syntax valid"

    # A surface that still carries its scaffold stubs is warned about, by name.
    (study / "search.py").write_text(
        'def search():\n    raise NotImplementedError("fill me in")\n', encoding="utf-8"
    )
    check = next(c for c in preflight_checks(study, require_clean=False) if c.name == "search.py")
    assert check.ok and "scaffold stubs remain" in check.message

    (study / "search.py").write_text("def broken(:\n", encoding="utf-8")
    check = next(c for c in preflight_checks(study, require_clean=False) if c.name == "search.py")
    assert not check.ok and "syntax error" in check.message

    (study / "search.py").unlink()
    check = next(c for c in preflight_checks(study, require_clean=False) if c.name == "search.py")
    assert not check.ok and check.message == "missing"
