"""The planted-truth benchmark and custody receipts (WP-05).

Test names carry their validation-plan id (V-17).  Four layers, kept apart on
purpose:

1. **The arithmetic** — the commitment, the bundle digest, the mechanical
   matching rule and the recovery scoring, on hand-written rows.  No study, no
   git, no CLI: if recall counts a duplicate twice it fails here.
2. **The submission contract** — what ``submission_problems`` refuses, and that
   the packaged JSON Schema still says the same thing (the module claims they
   are kept in step; this is what keeps them).
3. **The custodian fixture** — the A3 §8 smallest exercise end to end: one
   planted interaction and one null counterpart across disjoint seed blocks, two
   arms with explicit submissions frozen before the reveal, one sealed scoring
   cell over both, and a verification that recomputes every match from the same
   bytes.
4. **The refusals** — the four V-17 rows: a submission after the reveal, a
   revealed bundle that is not the committed one, overlapping seed blocks, and a
   benchmark nobody attested custody of.

``benchmark`` requires ``parity``, which requires ``expertise``, so the custodian
fixture is genuinely all three: the dependency table is not decoration, and a
study that declares the benchmark inherits the parity bind's rule that no sealed
access on ANY track precedes the frozen comparison.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_generation_expert import _reference, _set_experimenter, _write_card
from test_generation_parity import (
    AI_SNAPSHOT,
    EXPERIMENTER,
    EXPERT_SNAPSHOT,
    FLOOR,
    KEYS,
    _amend_contract,
    _parity_payload,
    _predictions,
    _write_parity,
    _write_pipeline_files,
)
from test_generation_spine import _bump, _gates, _gen, _receipt, _scaffold
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib.generation import benchmark as gb
from kleinlib.generation import custody as gcu
from kleinlib.primitives import sha256_bytes
from kleinlib.workflow import record_gate, run_one

STUDY = "03-demo"
ARMS: tuple[str, ...] = ("alpha", "beta")
SCORER = "lib/score_submissions.py"
PUBLIC = "bundles/public"
PRIVATE = "bundles/private"
TRUTH = f"{PRIVATE}/truth.json"
CAP = 3
PENALTY = 1.0
SALT = b"a-salt-that-never-enters-the-repository\n"

#: The A3 §8 smallest exercise: ONE planted interaction, and ONE null
#: counterpart — a structure over variables nothing was planted on, so an arm
#: that lists it earns a false positive rather than a second recovery.
TRUTH_STRUCTURES: list[dict[str, Any]] = [
    {
        "id": "T1",
        "variables": ["shade", "moisture"],
        "relationship": "interaction",
        "direction": "positive",
        "context": "understorey",
        "seed_block": "dev-1",
    }
]


# --------------------------------------------------------------------------
# 1. the arithmetic
# --------------------------------------------------------------------------


def _structure(**overrides: Any) -> dict[str, Any]:
    row = {
        "rank": 1,
        "variables": ["shade", "moisture"],
        "relationship": "interaction",
        "direction": "positive",
        "context": "understorey",
        "h_ids": ["11-arm#H1"],
    }
    row.update(overrides)
    return row


def test_the_matching_rule_is_a_set_a_string_and_a_sign() -> None:
    truth = TRUTH_STRUCTURES[0]
    assert gb.matches_mechanically(_structure(), truth)
    # variables are a SET: order and case do not decide a discovery
    assert gb.matches_mechanically(_structure(variables=["Moisture", "shade"]), truth)
    # ...but the set itself must be the same one
    assert not gb.matches_mechanically(_structure(variables=["shade"]), truth)
    assert not gb.matches_mechanically(
        _structure(variables=["shade", "moisture", "slope"]), truth
    )
    assert not gb.matches_mechanically(_structure(relationship="main"), truth)
    assert not gb.matches_mechanically(_structure(direction="negative"), truth)


def test_a_planted_truth_is_recovered_once_and_a_duplicate_is_not_a_second_recovery() -> None:
    submissions = {
        "alpha": [
            _structure(rank=1),
            _structure(rank=2, variables=["moisture", "shade"]),  # the same truth again
            _structure(rank=3, variables=["slope", "aspect"]),  # matches nothing
        ]
    }
    ok = {("alpha", rank): True for rank in (1, 2, 3)}
    scored = gb.score_arms(submissions, TRUTH_STRUCTURES, ok, penalty=PENALTY)
    rows = scored["rows"]
    assert [row["matched"] for row in rows] == [1, 0, 0]
    assert [row["truth_id"] for row in rows] == ["T1", "T1", None]
    metrics = scored["arms"]["alpha"]
    assert metrics["recall"] == 1.0, "the one planted truth was found"
    assert metrics["precision"] == pytest.approx(1 / 3), "a duplicate is not a second hit"
    assert metrics["null_fp"] == 1.0 and metrics["penalty"] == PENALTY


def test_the_adjudicated_context_can_veto_an_otherwise_perfect_match() -> None:
    submissions = {"alpha": [_structure(context="everywhere")]}
    scored = gb.score_arms(
        submissions, TRUTH_STRUCTURES, {("alpha", 1): False}, penalty=PENALTY
    )
    assert scored["rows"][0] == {
        "arm": "alpha",
        "rank": 1,
        "variables": ["shade", "moisture"],
        "relationship": "interaction",
        "direction": "positive",
        "context_ok": 0,
        "matched": 0,
        "truth_id": None,
    }
    assert scored["arms"]["alpha"]["recall"] == 0.0
    assert scored["arms"]["alpha"]["null_fp"] == 1.0


def test_a_null_only_benchmark_leaves_recall_undefined_and_counts_false_positives() -> None:
    """A5 §3: with nothing planted, the false-positive rate IS the result."""
    scored = gb.score_arms({"alpha": [_structure()]}, [], {("alpha", 1): True}, penalty=2.0)
    metrics = scored["arms"]["alpha"]
    assert metrics["recall"] is None
    assert metrics["precision"] == 0.0
    assert metrics["null_fp"] == 1.0 and metrics["penalty"] == 2.0


def test_the_commitment_is_salted_and_a_directory_hashes_as_its_manifest(tmp_path: Path) -> None:
    single = tmp_path / "one.json"
    single.write_text('{"structures": []}\n', encoding="utf-8")
    assert gb.bundle_bytes(single) == single.read_bytes()

    tree = tmp_path / "bundle"
    (tree / "nested").mkdir(parents=True)
    (tree / "a.json").write_text("a\n", encoding="utf-8")
    (tree / "nested" / "b.json").write_text("b\n", encoding="utf-8")
    digest = gb.bundle_bytes(tree)
    assert b"nested/b.json" in digest, "a directory hashes as its own path manifest"

    first = gb.commitment_of(SALT, digest)
    assert first == gb.commitment_of(SALT, digest), "the commitment is a pure function"
    assert first != gb.commitment_of(b"another salt\n", digest), "the salt is load-bearing"
    assert first != sha256_bytes(digest), "an unsalted digest is a guessable commitment"

    (tree / "a.json").write_text("tampered\n", encoding="utf-8")
    assert gb.commitment_of(SALT, gb.bundle_bytes(tree)) != first


def test_seed_blocks_that_share_a_block_are_named(tmp_path: Path) -> None:
    payload = {"seed_blocks": {"development": ["dev-1", "shared"], "sealed": ["shared"]}}
    assert gb.seed_block_overlap(payload) == ["shared"]
    assert gb.seed_block_overlap({"seed_blocks": {"development": ["a"], "sealed": ["b"]}}) == []


# --------------------------------------------------------------------------
# 2. the submission contract
# --------------------------------------------------------------------------


def _submission(*structures: dict[str, Any], arm: str = "alpha") -> dict[str, Any]:
    return {"study": "11-participant", "arm": arm, "structures": list(structures)}


def test_a_well_formed_submission_passes_and_a_ranked_one_is_read_in_rank_order() -> None:
    payload = _submission(_structure(rank=2), _structure(rank=1, variables=["slope"]))
    assert gb.submission_problems(payload, arm="alpha", cap=CAP) == []
    assert [row["rank"] for row in gb.submission_structures(payload)] == [1, 2]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (_submission(*[_structure(rank=n) for n in range(1, 5)]), "cap is 3"),
        (_submission(_structure(rank=0)), "rank must be an integer >= 1"),
        (_submission(_structure(rank=1), _structure(rank=1)), "rank 1 is used twice"),
        (_submission(_structure(variables=[])), "non-empty list of names"),
        (_submission(_structure(variables=["a", "a"])), "lists a name twice"),
        (_submission(_structure(relationship="")), "relationship is required"),
        (_submission(_structure(direction="up")), "direction is 'up'"),
        (_submission(_structure(h_ids="11-a#H1")), "h_ids must be a list"),
        (_submission(arm="gamma"), "imported as 'alpha'"),
    ],
)
def test_the_submission_schema_refuses_what_it_says_it_refuses(
    payload: dict[str, Any], expected: str
) -> None:
    problems = "; ".join(gb.submission_problems(payload, arm="alpha", cap=CAP))
    assert expected in problems


def test_the_packaged_json_schema_and_the_python_validator_agree() -> None:
    """The asset is the participant's copy of exactly these rules."""
    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / ".claude" / "skills" / "klein" / "assets" / gb.SCHEMA_NAME).read_text("utf-8")
    )
    assert schema["required"] == ["study", "arm", "structures"]
    item = schema["properties"]["structures"]["items"]
    assert item["required"] == ["rank", "variables", "relationship", "direction", "context", "h_ids"]
    assert tuple(item["properties"]["direction"]["enum"]) == gb.DIRECTIONS


# --------------------------------------------------------------------------
# 3. the custodian fixture — the A3 section 8 smallest exercise
# --------------------------------------------------------------------------


def _three_tracks(contract: dict[str, Any]) -> None:
    """The parity comparison track, plus the registered track that scores arms."""
    for name in ("comparison", "scoring"):
        contract["tracks"][name] = copy.deepcopy(contract["tracks"]["primary"])
        contract["tracks"][name]["mode"] = "registered"
        contract["tracks"][name]["metric"]["minimum_delta"] = 0.0
    contract["predictions"] = [
        *_predictions(),
        *[
            {
                "id": f"P{index}",
                "track": "scoring",
                "statement": f"arm {arm} recovers at least one planted structure",
                "rule": {"key": f"recall_{arm}", "op": ">=", "value": 0.0},
            }
            for index, arm in enumerate(ARMS, start=5)
        ],
    ]
    contract["phases"][0]["max_experiments"] = 8
    contract["phases"][-1]["max_experiments"] = 4


def _benchmark_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "benchmark",
        "study": STUDY,
        "scoring_track": "scoring",
        "public_bundle": {"path": PUBLIC, "sha256": None},
        "truth_file": TRUTH,
        "private_commitment": None,
        "custody": {
            "holder": "the named custodian",
            "mechanism": "separate accounts on separate machines; no shared checkout",
            "attestation": None,
        },
        "arms": [
            {
                "id": "alpha",
                "description": "novice team with the generation layer",
                "model": "a small model",
                "framework": "klein-2.1",
                "budget": {"person_hours": 3},
            },
            {
                "id": "beta",
                "description": "AI-free control with matched information and effort",
                "model": "none",
                "framework": "none",
                "budget": {"person_hours": 3},
            },
        ],
        "submission_schema": gb.SCHEMA_NAME,
        "hypothesis_cap": CAP,
        "matching_rule": {
            "variables": "exact",
            "relationship": "exact",
            "direction": "sign",
            "context": "the claimed context must name the stratum the structure was planted in",
        },
        "false_positive_penalty": PENALTY,
        "recovery_predictions": {"alpha": ["P5"], "beta": ["P6"]},
        "seed_blocks": {"development": ["dev-1"], "sealed": ["sealed-1"]},
        "reveal_policy": "after-all-arms",
        "scorer": {"path": SCORER},
    }
    payload.update(overrides)
    return payload


def _write_benchmark(study: Path, payload: dict[str, Any] | None = None) -> None:
    (study / gb.BENCHMARK_NAME).write_text(
        yaml.safe_dump(payload if payload is not None else _benchmark_payload(), sort_keys=False),
        encoding="utf-8",
    )


def _write_custodian_files(study: Path) -> None:
    scorer = study / SCORER
    scorer.parent.mkdir(parents=True, exist_ok=True)
    scorer.write_text("# the custodian's planted-truth scorer\nSCORER = 1\n", encoding="utf-8")
    public = study / PUBLIC
    public.mkdir(parents=True, exist_ok=True)
    (public / "observations.csv").write_text(
        "shade,moisture,slope,y\n1,2,3,0\n2,3,4,1\n", encoding="utf-8"
    )


def _private_bundle(tmp_path: Path) -> Path:
    """The custodian's private bundle — outside the repository, as it must be."""
    root = tmp_path / "custodian" / "private"
    root.mkdir(parents=True, exist_ok=True)
    (root / "truth.json").write_text(
        json.dumps({"structures": TRUTH_STRUCTURES}, indent=2) + "\n", encoding="utf-8"
    )
    (root / "generator.py").write_text("# the DGP, never shared\nSEEDS = ['dev-1']\n", "utf-8")
    salt = tmp_path / "custodian" / "salt.bin"
    salt.write_bytes(SALT)
    return root


def _salt_path(tmp_path: Path) -> Path:
    return tmp_path / "custodian" / "salt.bin"


@pytest.fixture
def custodian(tmp_path: Path) -> tuple[Path, Path]:
    """A `simulate`-style custodian: expertise reproduced, parity bound, ready to commit.

    Everything before ``benchmark commit`` is the dependency chain doing its job:
    ``benchmark`` needs ``parity``, which refuses a sealed admission on any track
    until both pipelines and every floor are frozen, and which itself needs the
    reproduced expert baseline.
    """
    repo, study = _scaffold(tmp_path)
    _amend_contract(study, _three_tracks)
    _write_pipeline_files(study)
    _write_custodian_files(study)
    _set_experimenter(repo, study, EXPERIMENTER)
    commit_all(repo, "three tracks, the scorer and the public bundle")
    assert (
        _gen(
            "init",
            "--study",
            str(study),
            "--capability",
            "expertise",
            "--capability",
            "parity",
            "--capability",
            "benchmark",
        )
        == 0
    )
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study), "--actor", EXPERIMENTER) == 0
    _write_parity(study, _parity_payload())
    assert _gen("parity", "lock", "--study", str(study), "--actor", EXPERIMENTER) == 0
    _gates(repo, study)

    _bump(study, "baseline")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, track="primary", command=metric_command(0.5), echo=False)[
        "experiment"
    ] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 0

    _bump(study, "floors")
    assert (
        _gen("check", "--study", str(study), "--action", "calibration", "--track", "comparison")
        == 0
    )
    assert run_one(
        study,
        track="comparison",
        command=metric_command(0.7, extra={f"floor_{key}": FLOOR for key in KEYS}),
        echo=False,
    )["experiment"] == "E0002"
    assert (
        _gen(
            "parity",
            "bind",
            "--study",
            str(study),
            "--ai-snapshot",
            AI_SNAPSHOT,
            "--expert-snapshot",
            EXPERT_SNAPSHOT,
        )
        == 0
    )
    _private_bundle(tmp_path)
    _write_benchmark(study)
    return repo, study


def _commit_benchmark(tmp_path: Path, study: Path) -> int:
    return _gen(
        "benchmark",
        "commit",
        "--study",
        str(study),
        "--private",
        str(_private_bundle(tmp_path)),
        "--salt-file",
        str(_salt_path(tmp_path)),
        "--actor",
        "the named custodian",
    )


def _submit(tmp_path: Path, study: Path, arm: str, *structures: dict[str, Any]) -> int:
    path = tmp_path / f"{arm}-submission.json"
    path.write_text(
        json.dumps(_submission(*structures, arm=arm), indent=2) + "\n", encoding="utf-8"
    )
    return _gen("benchmark", "submit", "--study", str(study), "--arm", arm, "--file", str(path))


#: What each arm submitted.  ``alpha`` finds the planted interaction and adds one
#: null distractor; ``beta`` — the AI-free control — misses it and submits the
#: distractor alone, so recall separates the arms and precision punishes neither
#: for staying inside the cap.
SUBMISSIONS: dict[str, list[dict[str, Any]]] = {
    "alpha": [
        _structure(rank=1),
        _structure(rank=2, variables=["slope", "aspect"], relationship="main"),
    ],
    "beta": [_structure(rank=1, variables=["slope", "aspect"], relationship="main")],
}


def _disclose(tmp_path: Path, repo: Path, study: Path) -> None:
    """The custodian copies the private bundle INTO the study and commits it."""
    shutil.copytree(_private_bundle(tmp_path), study / PRIVATE, dirs_exist_ok=True)
    commit_all(repo, "disclose the private bundle")


def _reveal(tmp_path: Path, study: Path, *extra: str) -> int:
    return _gen(
        "benchmark",
        "reveal",
        "--study",
        str(study),
        "--private",
        str(study / PRIVATE),
        "--salt-file",
        str(_salt_path(tmp_path)),
        *extra,
    )


def _table(rows: list[dict[str, Any]]) -> str:
    lines = ["\t".join(gb.SCORE_COLUMNS)]
    for row in rows:
        lines.append(
            "\t".join(
                [
                    str(row["arm"]),
                    str(row["rank"]),
                    ",".join(row["variables"]),
                    str(row["relationship"]),
                    str(row["direction"]),
                    str(row["context_ok"]),
                    str(row["matched"]),
                    row["truth_id"] or "NA",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _honest_score() -> dict[str, Any]:
    ok = {
        (arm, int(row["rank"])): True
        for arm, rows in SUBMISSIONS.items()
        for row in rows
    }
    return gb.score_arms(
        {arm: gb.submission_structures(_submission(*rows)) for arm, rows in SUBMISSIONS.items()},
        TRUTH_STRUCTURES,
        ok,
        penalty=PENALTY,
    )


def _cell_command(table: str, metrics: dict[str, Any]) -> list[str]:
    printed: dict[str, Any] = {}
    for arm, row in sorted(metrics.items()):
        if row["recall"] is not None:
            printed[f"recall_{arm}"] = row["recall"]
        if row["precision"] is not None:
            printed[f"precision_{arm}"] = row["precision"]
        printed[f"null_fp_{arm}"] = row["null_fp"]
        printed[f"cost_{arm}"] = 3.0
        # `NA` is allowed for a metric an arm did not produce; it prints as a
        # string line the notary keeps out of `manifest.metrics`.
        printed[f"predictive_{arm}"] = "NA"
    command = metric_command(0.5, artifacts=[gb.SCORES_TABLE], extra=printed)
    prologue = (
        "import pathlib; "
        f"_p = pathlib.Path({gb.SCORES_TABLE!r}); "
        "_p.parent.mkdir(parents=True, exist_ok=True); "
        f"_p.write_bytes({table!r}.encode()); "
    )
    command[-1] = prologue + command[-1]
    return command


def _seal(repo: Path, study: Path, table: str, metrics: dict[str, Any]) -> dict[str, Any]:
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "acknowledge the adaptive phase")
    assert (
        _gen(
            "check",
            "--study",
            str(study),
            "--action",
            "sealed",
            "--track",
            "scoring",
            "--tests",
            "P5",
            "P6",
        )
        == 0
    )
    return run_one(
        study,
        track="scoring",
        final_test=True,
        command=_cell_command(table, metrics),
        tests=["P5", "P6"],
        echo=False,
    )


def _attest(study: Path, subject: str = TRUTH) -> int:
    """Attest custody OF THIS BENCHMARK: the subject names benchmark.yaml's truth file."""
    return _gen(
        "custody",
        "attest",
        "--study",
        str(study),
        "--holder",
        "the named custodian",
        "--mechanism",
        "separate accounts on separate machines; participants had no read path",
        "--statement",
        "the private bundle lived only on the custodian account from commit to reveal",
        "--subject",
        subject,
    )


def _capability(study: Path) -> dict[str, Any]:
    return _receipt(study)["capabilities"]["benchmark"]


def _checks(study: Path, name: str) -> list[str]:
    return [check["status"] for check in _receipt(study)["checks"] if check["name"] == name]


def _detail(study: Path, name: str) -> str:
    return " ".join(
        check["detail"] for check in _receipt(study)["checks"] if check["name"] == name
    )


@pytest.fixture
def scored(custodian, tmp_path: Path) -> tuple[Path, Path]:
    """Commit → two submissions → reveal → one sealed scoring cell → attested."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 0
    assert _attest(study) == 0
    honest = _honest_score()
    manifest = _seal(repo, study, _table(honest["rows"]), honest["arms"])
    assert manifest["evaluation_kind"] == "final_test"
    return repo, study


def test_v17_the_smallest_exercise_scores_two_arms_from_one_sealed_cell(scored) -> None:
    """V-17 / A3 §8: one planted interaction, one null, two arms, one sealed cell."""
    _repo, study = scored
    assert _gen("verify", "--study", str(study)) == 0

    outcome = _capability(study)
    assert outcome["integrity"] == "PASS"
    assert outcome["outcome"] == "scored"
    assert outcome["custody"] == gcu.CUSTODIED
    # alpha found the planted truth and paid for one distractor; beta found none
    assert outcome["arms"]["alpha"]["recall"] == 1.0
    assert outcome["arms"]["alpha"]["precision"] == 0.5
    assert outcome["arms"]["alpha"]["null_fp"] == 1.0
    assert outcome["arms"]["beta"]["recall"] == 0.0
    assert outcome["arms"]["beta"]["null_fp"] == 1.0

    assert _checks(study, "benchmark commitment") == ["PASS", "PASS"]
    assert _checks(study, "benchmark submissions") == ["PASS"]
    assert _checks(study, "benchmark scorer") == ["PASS"]
    assert _checks(study, "benchmark scoring") == ["PASS"]
    assert _checks(study, "benchmark custody") == ["PASS"]
    assert _checks(study, "benchmark ceiling") == ["PASS"]
    assert "TESTIMONY" in _detail(study, "benchmark custody")

    # the notary reached its own verdict on the printed block, independently
    manifest = json.loads(
        (study / "runs" / "E0003" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["predictions"]["P5"]["verdict"] == "supported"
    assert manifest["metrics"]["recall_alpha"] == 1.0


def test_the_seal_of_the_scoring_track_is_refused_before_the_reveal(custodian, tmp_path) -> None:
    """The truth has to be disclosed against the commitment before it is scored."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "acknowledge the adaptive phase")
    assert (
        _gen("check", "--study", str(study), "--action", "sealed", "--track", "scoring") == 2
    )
    # the refusal is on the record, and the run that ignored it would be caught
    events = [
        json.loads(line)
        for line in (study / "generation" / "events.jsonl").read_text("utf-8").splitlines()
    ]
    assert events[-1]["type"] == "admission_checked" and events[-1]["verdict"] == "refused"


def test_the_commit_transaction_touches_only_the_paths_it_owns(custodian, tmp_path) -> None:
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    touched = sorted(git(repo, "show", "--name-only", "--format=", "HEAD").split())
    named = {
        f"studies/{STUDY}/{gb.BENCHMARK_NAME}",
        f"studies/{STUDY}/{gb.SCHEMA_NAME}",
        f"studies/{STUDY}/generation/events.jsonl",
    }
    assert named <= set(touched)
    objects = f"studies/{STUDY}/generation/objects/"
    assert [path for path in touched if path not in named and not path.startswith(objects)] == []
    assert len([path for path in touched if path.startswith(objects)]) == 1
    # the packaged schema was copied into the study and hashed there
    assert (study / gb.SCHEMA_NAME).is_file()


def test_a_second_commitment_and_a_second_reveal_are_both_refused(scored, tmp_path) -> None:
    _repo, study = scored
    assert _commit_benchmark(tmp_path, study) == 1
    assert _reveal(tmp_path, study) == 1


# --------------------------------------------------------------------------
# 4. the refusals — V-17's four rows
# --------------------------------------------------------------------------


def test_v17_a_submission_after_the_reveal_is_refused_and_fails_the_audit(
    scored, tmp_path
) -> None:
    """V-17 row 1: late submission. The CLI refuses; a forced one FAILs the audit."""
    repo, study = scored
    assert _submit(tmp_path, study, "beta", _structure(rank=3)) == 2

    # The CLI cannot produce a late submission, so the ledger API stands in for a
    # hand-edited record: the chain stays valid and only the ORDER is wrong.
    from kleinlib.generation.ledger import append_event, commit_generation, write_object

    late = study / "late.json"
    late.write_text(json.dumps(_submission(_structure(), arm="beta")) + "\n", encoding="utf-8")
    obj = gb.submission_object(
        study=STUDY,
        arm="beta",
        commit_sha="0" * 64,
        file_path="late.json",
        file_sha256=sha256_bytes(late.read_bytes()),
        structures=1,
        participant="11-participant",
    )
    sha = write_object(study, obj)
    append_event(
        study,
        gb.SUBMIT_TYPE,
        study=STUDY,
        core_anchor={"sequence": 0, "event_hash": None},
        git_head=None,
        payload_sha256=sha,
        arm="beta",
    )
    commit_all(repo, "a submission that arrived after the answer")
    commit_generation(study, "klein: forced late submission")

    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _checks(study, "benchmark submissions")
    assert "submitted AFTER the reveal" in _detail(study, "benchmark submissions")
    assert _capability(study)["integrity"] == "FAIL"


def test_v17_a_bundle_that_is_not_the_committed_one_is_refused_and_recorded(
    custodian, tmp_path
) -> None:
    """V-17 row 2: revealed bundle != commitment. Refused, recorded, and permanent."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    truth = study / TRUTH
    truth.write_text(
        json.dumps(
            {"structures": [{**TRUTH_STRUCTURES[0], "variables": ["slope", "aspect"]}]}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    commit_all(repo, "a truth nobody committed to")

    assert _reveal(tmp_path, study) == 2
    events = [
        json.loads(line)
        for line in (study / "generation" / "events.jsonl").read_text("utf-8").splitlines()
    ]
    assert events[-1]["type"] == gb.REVEAL_FAILED_TYPE and events[-1]["matched"] is False
    assert _gen("verify", "--study", str(study)) == 2
    assert "did not recompute to the commitment" in _detail(study, "benchmark commitment")
    assert _capability(study)["outcome"] == "unverified"


def test_v17_overlapping_seed_blocks_are_refused_at_the_commitment(custodian, tmp_path) -> None:
    """V-17 row 3: a block handed out as development data is never sealed evidence."""
    _repo, study = custodian
    _write_benchmark(
        study,
        _benchmark_payload(seed_blocks={"development": ["dev-1", "shared"], "sealed": ["shared"]}),
    )
    assert _commit_benchmark(tmp_path, study) == 2
    from kleinlib.generation.ledger import read_events

    assert gb.commits(study, read_events(study)) == [], "nothing was committed to"
    assert _gen("verify", "--study", str(study)) == 2, "a declared benchmark must commit"
    assert "is not committed" in _detail(study, "benchmark commitment")


def test_v17_without_a_custody_attestation_the_outcome_is_unverified(
    custodian, tmp_path
) -> None:
    """V-17 row 4: nobody said, so nobody is believed — and nothing FAILs for it."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 0
    honest = _honest_score()
    _seal(repo, study, _table(honest["rows"]), honest["arms"])

    assert _gen("verify", "--study", str(study)) == 0, "an unattested benchmark still verifies"
    outcome = _capability(study)
    assert outcome["integrity"] == "PASS"
    assert outcome["outcome"] == "unverified"
    assert outcome["custody"] == gcu.UNVERIFIED
    assert outcome["arms"]["alpha"]["recall"] == 1.0, "the arithmetic is unaffected"
    assert _checks(study, "benchmark custody") == ["WARN"]
    assert "another directory of the same readable worktree is not custody" in _detail(
        study, "benchmark custody"
    )


def test_c6_an_attestation_about_something_else_does_not_custody_this_benchmark(
    custodian, tmp_path
) -> None:
    """C-6: `custody attest` is capability-agnostic, so counting ANY of them is wrong.

    A study may attest the custody of a sample chain, an interview transcript, a
    later time block.  Before the fix, any one of those turned this benchmark's
    outcome from `unverified` to `custodied` — a word about someone else's
    evidence spent on this one.
    """
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 0
    assert _attest(study, subject="the wet-lab sample chain") == 0
    honest = _honest_score()
    _seal(repo, study, _table(honest["rows"]), honest["arms"])

    assert _gen("verify", "--study", str(study)) == 0, "an unrelated attestation FAILs nothing"
    outcome = _capability(study)
    assert outcome["custody"] == gcu.UNVERIFIED
    assert outcome["outcome"] == "unverified"
    detail = _detail(study, "benchmark custody")
    assert "Attestations about other subjects" in detail
    assert "the wet-lab sample chain" in detail


def test_c6_the_default_subject_is_this_studys_own_hidden_evidence(
    custodian, tmp_path
) -> None:
    """C-6: an attestation with no --subject still means this study's own bundle."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 0
    assert (
        _gen(
            "custody",
            "attest",
            "--study",
            str(study),
            "--holder",
            "the named custodian",
            "--mechanism",
            "separate accounts on separate machines",
            "--statement",
            "the bundle never left the custodian account",
        )
        == 0
    )
    honest = _honest_score()
    _seal(repo, study, _table(honest["rows"]), honest["arms"])

    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study)["custody"] == gcu.CUSTODIED
    assert gb.benchmark_subjects(_benchmark_payload()) == {PUBLIC, TRUTH, "the named custodian"}


def test_a_missing_arm_is_a_recorded_trial_and_never_an_absence(custodian, tmp_path) -> None:
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    assert _submit(tmp_path, study, "alpha", *SUBMISSIONS["alpha"]) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 2, "beta has neither submitted nor been accounted for"
    assert _gen("verify", "--study", str(study)) == 0

    assert (
        _reveal(tmp_path, study, "--missing-arm", "beta", "the machine was never provisioned")
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    statuses = _checks(study, "benchmark submissions")
    assert statuses == ["PASS", "WARN"]
    assert "missing trial(s) recorded at the reveal: beta" in _detail(
        study, "benchmark submissions"
    )


def test_a_scorer_that_changed_before_the_sealed_cell_fails(custodian, tmp_path) -> None:
    """R-INV-3 / R-BEN-2: the matching code is frozen before any submission."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 0
    (study / SCORER).write_text("# tuned to the answers\nSCORER = 2\n", encoding="utf-8")
    commit_all(repo, "edit the scorer after the submissions arrived")
    honest = _honest_score()
    _seal(repo, study, _table(honest["rows"]), honest["arms"])

    assert _gen("verify", "--study", str(study)) == 2
    assert _checks(study, "benchmark scorer") == ["FAIL"]
    assert "is not the scorer the commitment pinned" in _detail(study, "benchmark scorer")


def test_a_table_that_does_not_recompute_fails_even_though_it_is_the_pinned_one(
    custodian, tmp_path
) -> None:
    """The scorer is checked, not believed: the matching rule is re-applied."""
    repo, study = custodian
    assert _commit_benchmark(tmp_path, study) == 0
    for arm, rows in SUBMISSIONS.items():
        assert _submit(tmp_path, study, arm, *rows) == 0
    _disclose(tmp_path, repo, study)
    assert _reveal(tmp_path, study) == 0
    honest = _honest_score()
    generous = copy.deepcopy(honest["rows"])
    for row in generous:
        if row["arm"] == "beta":
            row["matched"], row["truth_id"] = 1, "T1"
    flattering = copy.deepcopy(honest["arms"])
    flattering["beta"]["recall"] = 1.0
    flattering["beta"]["precision"] = 1.0
    flattering["beta"]["null_fp"] = 0.0
    _seal(repo, study, _table(generous), flattering)

    assert _gen("verify", "--study", str(study)) == 2
    assert _checks(study, "benchmark scoring") == ["FAIL"]
    detail = _detail(study, "benchmark scoring")
    assert "does not agree with the matching rule" in detail
    assert "beta rank 1" in detail


def test_the_track_gets_exactly_one_sealed_look_and_the_core_enforces_it(scored) -> None:
    """R-BEN-4's "one sealed cell" is guarded twice: by the core, and by the family."""
    _repo, study = scored
    from kleinlib.errors import WorkflowError

    honest = _honest_score()
    with pytest.raises(WorkflowError):
        run_one(
            study,
            track="scoring",
            final_test=True,
            command=_cell_command(_table(honest["rows"]), honest["arms"]),
            echo=False,
        )


def test_a_confirmed_claim_on_the_in_silico_table_is_refused(scored) -> None:
    """R-INV-6: recovery is in-silico performance, never a confirmed finding."""
    repo, study = scored
    lock = {
        "lock_schema": 2,
        "study": STUDY,
        "artifacts": {
            "benchmark_scores": {
                "path": gb.SCORES_TABLE,
                "sha256": sha256_bytes((study / gb.SCORES_TABLE).read_bytes()),
            }
        },
        "numbers": {},
        "claims": {
            "C1": {
                "class": "known-dgp-teaching",
                "strength": "confirmed",
                "claim": "the pipeline recovers the interaction",
                "numbers": [],
                "evidence": ["art:benchmark_scores"],
                "scope": "in-silico",
            }
        },
        "errata": {},
    }
    (study / "claims.lock").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", "utf-8")
    commit_all(repo, "a lock that confirms an in-silico recovery")

    assert _gen("verify", "--study", str(study)) == 2
    assert _checks(study, "benchmark ceiling") == ["FAIL"]
    assert "never a confirmed finding" in _detail(study, "benchmark ceiling")


def test_a_retired_benchmark_keeps_its_results(scored) -> None:
    _repo, study = scored
    assert (
        _gen(
            "benchmark",
            "retire",
            "--study",
            str(study),
            "--reason",
            "the generator was posted to a public forum",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    outcome = _capability(study)
    assert outcome["outcome"] == "retired"
    assert outcome["arms"]["alpha"]["recall"] == 1.0, "the results are retained"
    assert "results are RETAINED" in _detail(study, "benchmark commitment")
    assert _gen("benchmark", "retire", "--study", str(study), "--reason", "again") == 1


# --------------------------------------------------------------------------
# custody: capability-agnostic by construction
# --------------------------------------------------------------------------


def test_custody_attest_needs_no_capability_at_all(tmp_path: Path) -> None:
    """S2's custodian-held block is custody without a benchmark anywhere."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study)) == 0
    _gates(repo, study)
    (study / "custody-receipt.md").write_text(
        "# Access log export\n\nNo participant account was granted read access.\n", "utf-8"
    )
    commit_all(repo, "the custody receipt document")
    assert (
        _gen(
            "custody",
            "attest",
            "--study",
            str(study),
            "--holder",
            "the data steward",
            "--mechanism",
            "the later block sits on a separate account with no shared checkout",
            "--statement",
            "released once, on the recorded date, to nobody before it",
            "--receipt",
            "custody-receipt.md",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    events = [
        json.loads(line)
        for line in (study / "generation" / "events.jsonl").read_text("utf-8").splitlines()
    ]
    assert events[-1]["type"] == gcu.ATTEST_TYPE
    assert events[-1]["holder"] == "the data steward"
    obj = json.loads(
        (study / "generation" / "objects" / f"{events[-1]['payload_sha256']}.json").read_text(
            "utf-8"
        )
    )
    assert obj["testimony"] is True
    assert obj["receipt"]["path"] == "custody-receipt.md"
    # the attestation commit stays inside the layer's own subtree
    touched = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert all(path.startswith(f"studies/{STUDY}/generation/") for path in touched)


def test_custody_attest_refuses_an_unnamed_holder_and_an_outside_receipt(tmp_path: Path) -> None:
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study)) == 0
    _gates(repo, study)
    assert (
        _gen(
            "custody",
            "attest",
            "--study",
            str(study),
            "--holder",
            "   ",
            "--mechanism",
            "accounts",
            "--statement",
            "nothing",
        )
        == 2
    )
    outside = tmp_path / "elsewhere.md"
    outside.write_text("not in the record\n", encoding="utf-8")
    assert (
        _gen(
            "custody",
            "attest",
            "--study",
            str(study),
            "--holder",
            "someone",
            "--mechanism",
            "accounts on separate machines",
            "--statement",
            "denied access throughout",
            "--receipt",
            str(outside),
        )
        == 2
    )
    assert gcu.custody_state([]) == gcu.UNVERIFIED
