"""The ``expertise`` capability (WP-01): reproduce the baseline, or admit nothing.

Test names carry their validation-plan id (V-09, V-10, V-18).  The spine's
fixtures are reused verbatim — a generation-enabled study with one extra
capability declared — so what these tests exercise is the REGISTRATION path: an
admission rule, a verify family, a receipt outcome and a label column that no
line of ``admission.py``, ``verify.py`` or ``label.py`` knows about.

The A3 §1 smallest exercise runs end to end here: a baseline that prints the
wrong number, a bind that says so, a challenger admission refused while the
obligation is open, a versioned repair, a repair run, a bind that reproduces,
and only then an admitted challenger.  Passing it establishes reproduction of
THAT recipe — not domain expertise.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_generation_spine import _bump, _gates, _gen, _receipt, _scaffold
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib.generation import expert as ge
from kleinlib.generation import ledger
from kleinlib.workflow import run_one

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _front() -> dict[str, Any]:
    """A domain card frontmatter that locks: every required list is non-empty."""
    return copy.deepcopy(
        {
            "type": "domain-card",
            "study": "03-demo",
            "scope": "binary classification on the fixture table",
            "as_of": "2026-09-05",
            "sources": [{"record_id": "collins2010", "role": "doctrine"}],
            "pipeline_steps": ["prepare", "fit", "score"],
            "metrics": ["val_auc"],
            "doctrine": ["trees still win on most tabular data"],
            "pitfalls": ["class weights ruin calibration"],
            "incumbent": "the published recipe reports val_auc 0.5",
            "method_shortlist": ["logistic regression", "gradient boosting"],
            "baseline": {
                "implementation": "train.py",
                "config": {"learning_rate": 0.1},
                "fixture": "data/prepared/fixture.csv",
                "targets": [{"key": "primary_metric", "value": 0.5, "tol": 0.01, "rel": False}],
                "review": "source-reconstructed",
            },
            "unknowns": ["how the incumbent partitioned its data"],
        }
    )


def _write_card(study: Path, front: dict[str, Any] | None = None) -> None:
    body = yaml.safe_dump(front if front is not None else _front(), sort_keys=True)
    (study / "domain_card.md").write_text(
        f"---\n{body}---\n\n# Domain card\n\nWhat the field already knows.\n", encoding="utf-8"
    )


def _reference(study: Path, *, record_id: str = "collins2010", basis: str = "bibliography", extra: tuple[str, ...] = ()) -> int:
    return _gen(
        "reference",
        "record",
        "--study",
        str(study),
        "--id",
        record_id,
        "--title",
        "Tacit and Explicit Knowledge",
        "--year",
        "2010",
        "--identifier",
        "isbn:9780226113807",
        "--locator",
        "isbn:9780226113807",
        "--statement",
        "reproducing a recipe is not the same as holding the tacit knowledge behind it",
        "--basis",
        basis,
        *extra,
    )


def _set_experimenter(repo: Path, study: Path, who: str) -> None:
    path = study / "program.md"
    text = path.read_text(encoding="utf-8").replace(
        "| experimenter | | |", f"| experimenter | {who} | 2026-09-05 |"
    )
    path.write_text(text, encoding="utf-8")
    commit_all(repo, "roster: experimenter")


@pytest.fixture
def expert_study(tmp_path: Path) -> tuple[Path, Path]:
    """A study that declared `expertise` and locked its card BEFORE the gates."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    assert _reference(study) == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study), "--actor", "tester") == 0
    _gates(repo, study)
    return repo, study


@pytest.fixture
def reproduced_study(expert_study) -> tuple[Path, Path]:
    """The happy path: one baseline run that hit its target, bound."""
    repo, study = expert_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.5), echo=False)["experiment"] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 0
    return repo, study


def _capability(study: Path) -> dict[str, Any]:
    return _receipt(study)["capabilities"]["expertise"]


def _expert_statuses(study: Path) -> dict[str, list[str]]:
    receipt = _receipt(study)
    out: dict[str, list[str]] = {}
    for check in receipt["checks"]:
        if check["name"].startswith("expert"):
            out.setdefault(check["name"], []).append(check["status"])
    return out


# --------------------------------------------------------------------------
# V-09 — the A3 §1 smallest exercise
# --------------------------------------------------------------------------


def test_v09_mismatch_then_repair_then_reproduction_opens_the_challenger_gate(
    expert_study,
) -> None:
    """V-09: the baseline misses, the obligation blocks, a repair discharges it."""
    _repo, study = expert_study

    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.7), echo=False)["experiment"] == "E0001"

    # the baseline printed 0.7 where the lock froze 0.5 ± 0.01
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 2
    bound = _last_object(study)
    assert bound["verdict"] == "mismatch"
    assert bound["targets"][0]["observed"] == 0.7
    assert bound["targets"][0]["within"] is False

    # V-10 (valid half): a challenger cannot be admitted while it is open
    _bump(study, "two")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2
    assert any(
        "baseline obligation open" in reason for reason in _last_object(study)["reasons"]
    )

    _bump(study, "repaired")
    assert (
        _gen(
            "expert",
            "repair",
            "--study",
            str(study),
            "--changed",
            "train.py",
            "--note",
            "the exposure offset was omitted; restored",
        )
        == 0
    )
    assert _gen("check", "--study", str(study), "--action", "repair", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.5), echo=False)["experiment"] == "E0002"
    assert _gen("expert", "bind", "--study", str(study), "E0002") == 0
    assert _last_object(study)["verdict"] == "reproduced"

    _bump(study, "challenger")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0

    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study) == {
        "integrity": "PASS",
        "outcome": "source-reconstructed",
        "repairs": 1,
    }
    statuses = _expert_statuses(study)
    assert set(statuses) == {
        "expert card",
        "expert references",
        "expert obligation",
        "expert repairs",
    }
    assert "FAIL" not in [status for values in statuses.values() for status in values]


def test_v09_invalid_control_an_amend_may_not_move_a_target(expert_study) -> None:
    """V-09 invalid control: lowering the bar you failed to clear is a new study."""
    _repo, study = expert_study
    front = _front()
    front["baseline"]["targets"][0]["tol"] = 0.5
    _write_card(study, front)
    assert _gen("expert", "amend", "--study", str(study)) == 2

    # the same amendment WITHOUT touching the targets is lawful
    front = _front()
    front["unknowns"].append("whether the fixture is the published one")
    _write_card(study, front)
    assert _gen("expert", "amend", "--study", str(study)) == 0
    locks = ge.joined(study, ledger.read_events(study), ge.LOCK_TYPE)
    assert [obj["version"] for _event, obj in locks] == [1, 2]
    assert locks[1][0]["parent_ids"] == [locks[0][0]["id"]]
    assert locks[1][1]["late"] is True  # every amend follows the consult gate
    # …and being late is LABELLED, not failed: only version 1 must precede CONSULT
    assert _gen("verify", "--study", str(study)) == 0
    assert _expert_statuses(study)["expert card"] == ["PASS", "WARN"]


def test_a_repair_may_not_touch_the_checker(expert_study) -> None:
    """The checker is never the searcher — and never the repair either."""
    repo, study = expert_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 2

    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    contract["tracks"]["primary"]["verifier"] = {
        "command": ["python", "verify_baseline.py"],
        "tolerance": 0.0,
        "artifact_key": "model_path",
    }
    (study / "study.yaml").write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    (study / "verify_baseline.py").write_text("print('primary_metric: 0.5')\n", encoding="utf-8")
    commit_all(repo, "declare a verifier")
    assert ge.verifier_scripts(contract) == {"verify_baseline.py"}
    assert (
        _gen(
            "expert",
            "repair",
            "--study",
            str(study),
            "--changed",
            "verify_baseline.py",
            "--note",
            "make the checker agree with me",
        )
        # exit 1: naming the verifier is a malformed `--changed`, not a rule of
        # the study saying no — nothing is recorded either way.
        == 1
    )


def test_a_repair_before_a_bind_is_refused(expert_study) -> None:
    _repo, study = expert_study
    assert (
        _gen("expert", "repair", "--study", str(study), "--changed", "train.py", "--note", "n")
        == 2
    )


# --------------------------------------------------------------------------
# V-10 — a challenger admitted before the reproduction
# --------------------------------------------------------------------------


def test_v10_a_forged_challenger_receipt_fails_the_expert_family(expert_study) -> None:
    """V-10 invalid control: bypassing `check` writes the evidence against you."""
    repo, study = expert_study
    from kleinlib.generation.admission import core_anchor
    from kleinlib.generation.envelope import GENERATION_SCHEMA

    receipt = {
        "schema": GENERATION_SCHEMA,
        "kind": "admission",
        "study": "03-demo",
        "checkpoint": "run",
        "track": "primary",
        "intended_action": {
            "kind": "run",
            "hypothesis_id": None,
            "cell_id": None,
            "obligation_id": None,
            "tests": [],
        },
        "surface_digest": "0" * 64,
        "surface_files": [],
        "inputs": {"manifest": None, "slate": None, "premortem": None, "parity": None,
                   "cells": None, "design": None},
        "protocol_hashes": {},
        "core_anchor": core_anchor(study),
        "verdict": "admitted",
        "reasons": [],
    }
    sha = ledger.write_object(study, receipt)
    ledger.append_event(
        study,
        "admission_checked",
        study="03-demo",
        core_anchor=core_anchor(study),
        git_head=git(repo, "rev-parse", "HEAD"),
        payload_sha256=sha,
        checkpoint="run",
        track="primary",
        verdict="admitted",
    )
    commit_all(repo, "a receipt nobody earned")

    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _expert_statuses(study)["expert obligation"]
    assert _capability(study)["integrity"] == "FAIL"
    assert _capability(study)["outcome"] == "incomplete"


def test_an_open_obligation_with_no_challenger_is_incomplete_not_failed(expert_study) -> None:
    """Honest incompleteness stays label-eligible: WARN, never FAIL."""
    _repo, study = expert_study
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study) == {"integrity": "PASS", "outcome": "incomplete", "repairs": 0}
    assert "WARN" in _expert_statuses(study)["expert obligation"]


def test_a_bind_on_a_non_baseline_admission_is_refused(reproduced_study) -> None:
    """Only `baseline` or `repair` discharges the obligation."""
    _repo, study = reproduced_study
    _bump(study, "challenger")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.9), echo=False)["experiment"] == "E0002"
    assert _gen("expert", "bind", "--study", str(study), "E0002") == 2


# --------------------------------------------------------------------------
# V-18 — reference records
# --------------------------------------------------------------------------


def test_v18_a_card_source_without_a_record_cannot_be_locked(tmp_path: Path) -> None:
    """V-18: a source is a record id, not a footnote."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study)) == 2
    assert not ge.joined(study, ledger.read_events(study), ge.LOCK_TYPE)

    commit_all(repo, "the card draft is the driver's until it locks")
    assert _reference(study) == 0
    assert _gen("expert", "lock", "--study", str(study)) == 0


def test_v18_read_at_source_without_retention_is_refused(tmp_path: Path) -> None:
    """V-18 invalid control: a basis its own fields cannot support."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    blob = tmp_path / "collins2010.pdf"
    blob.write_bytes(b"%PDF-1.4 not really\n")

    assert _reference(study, basis="read-at-source", extra=("--blob", str(blob))) == 2
    assert _reference(study, basis="read-at-source") == 2
    # hash-only is the honest record for bytes you hashed and did not keep
    assert _reference(study, basis="hash-only", extra=("--blob", str(blob))) == 0
    record = json.loads(
        (repo / "knowledge" / "references" / "collins2010.json").read_text(encoding="utf-8")
    )
    assert record["blob_retained"] is False
    assert record["source_blob_sha256"]

    # write-once: the same id with different bytes is refused, not overwritten
    assert _reference(study, basis="bibliography") == 2


def test_v18_a_bare_verified_true_is_insufficient_for_an_enabled_study(expert_study) -> None:
    """R-EXP-2: `references.yaml` mirrors the record or it fails."""
    repo, study = expert_study
    (study / "references.yaml").write_text(
        "references:\n"
        "  collins2010:\n"
        "    title: Tacit and Explicit Knowledge\n"
        "    url: https://example.invalid/collins2010\n"
        "    verified: true\n",
        encoding="utf-8",
    )
    commit_all(repo, "cite it")
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _expert_statuses(study)["expert references"]

    (study / "references.yaml").write_text(
        "references:\n"
        "  collins2010:\n"
        "    title: Tacit and Explicit Knowledge\n"
        "    url: https://example.invalid/collins2010\n"
        "    verified: true\n"
        "    record_id: collins2010\n"
        "    verification_level: bibliography\n",
        encoding="utf-8",
    )
    commit_all(repo, "mirror the record id")
    assert _gen("verify", "--study", str(study)) == 0
    assert _expert_statuses(study)["expert references"] == ["PASS"]


def test_an_edited_record_fails_the_family(expert_study) -> None:
    repo, study = expert_study
    path = repo / "knowledge" / "references" / "collins2010.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["supported_statement"] = "something much stronger"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    commit_all(repo, "strengthen a citation after the fact")
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _expert_statuses(study)["expert references"]


# --------------------------------------------------------------------------
# the card is immutable once locked; the lock precedes CONSULT
# --------------------------------------------------------------------------


def test_a_card_edited_after_the_lock_fails(expert_study) -> None:
    repo, study = expert_study
    card = study / "domain_card.md"
    card.write_text(card.read_text(encoding="utf-8") + "\nand another thought\n", encoding="utf-8")
    commit_all(repo, "edit the locked card in place")
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _expert_statuses(study)["expert card"]


def test_a_late_lock_is_refused_and_forced_late_fails_forever(tmp_path: Path) -> None:
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    assert _reference(study) == 0
    _gates(repo, study)
    _write_card(study)
    assert _gen("expert", "lock", "--study", str(study)) == 2

    assert _gen("expert", "lock", "--study", str(study), "--allow-late") == 0
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _expert_statuses(study)["expert card"]


def test_an_unlocked_card_blocks_a_baseline_admission(tmp_path: Path) -> None:
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    _gates(repo, study)
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 2
    assert any("not locked" in reason for reason in _last_object(study)["reasons"])


# --------------------------------------------------------------------------
# the review rung
# --------------------------------------------------------------------------


def test_a_review_without_a_session_receipt_stays_source_reconstructed(
    reproduced_study,
) -> None:
    repo, study = reproduced_study
    _set_experimenter(repo, study, "sonnet · pytest · session-a")
    assert (
        _gen(
            "expert",
            "review",
            "--study",
            str(study),
            "--reviewer",
            "a practitioner",
            "--statement",
            "the recipe matches the published one",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study)["outcome"] == "source-reconstructed"
    assert "WARN" in _expert_statuses(study)["expert review"]


def test_a_receipted_review_by_someone_else_raises_the_rung(reproduced_study) -> None:
    repo, study = reproduced_study
    _set_experimenter(repo, study, "sonnet · pytest · session-a")
    receipt = repo.parent / "review-session.txt"
    receipt.write_text("transcript of the review session\n", encoding="utf-8")
    assert (
        _gen(
            "expert",
            "review",
            "--study",
            str(study),
            "--reviewer",
            "a different practitioner",
            "--session-receipt",
            str(receipt),
            "--statement",
            "I reproduced the recipe independently",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study)["outcome"] == "independent-review"
    assert _expert_statuses(study)["expert review"] == ["PASS"]

    # and the label copies the OUTCOME, not the integrity
    from kleinlib import cli

    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _gen("label", "--study", str(study)) == 0
    label = json.loads((study / "generation" / "label.json").read_text(encoding="utf-8"))
    assert label["capabilities"]["expertise"] == "independent-review"
    assert label["capabilities"]["parity"] == "n/a"


def test_a_review_by_the_experimenter_raises_no_rung(reproduced_study) -> None:
    repo, study = reproduced_study
    _set_experimenter(repo, study, "sonnet · pytest · session-a")
    receipt = repo.parent / "review-session.txt"
    receipt.write_text("transcript\n", encoding="utf-8")
    assert (
        _gen(
            "expert",
            "review",
            "--study",
            str(study),
            "--reviewer",
            "Sonnet",
            "--session-receipt",
            str(receipt),
            "--statement",
            "I reviewed myself",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert _capability(study)["outcome"] == "source-reconstructed"
    assert "WARN" in _expert_statuses(study)["expert review"]


def test_the_roster_parser_reads_the_experimenter_cell(reproduced_study) -> None:
    repo, study = reproduced_study
    assert ge.roster_experimenter(study) is None
    _set_experimenter(repo, study, "sonnet · pytest · session-a")
    assert ge.roster_experimenter(study) == "sonnet · pytest · session-a"
    assert ge.same_actor("pytest", "sonnet · pytest · session-a")
    assert not ge.same_actor("a practitioner", "sonnet · pytest · session-a")
    assert not ge.same_actor("anyone", None)


def test_same_actor_is_symmetric(reproduced_study) -> None:
    """A-5: the answer may not depend on which side is the compound cell."""
    assert ge.same_actor("opus · codex · s-42", "codex")
    assert ge.same_actor("codex", "opus · codex · s-42")
    assert ge.same_actor("Codex", "opus · codex · s-42")  # normalized, not exact
    assert not ge.same_actor("opus · codex · s-42", "sonnet")
    assert not ge.same_actor("", "codex")


# --------------------------------------------------------------------------
# R-INV-3 — the recipe is frozen with the targets
# --------------------------------------------------------------------------


def _recipe_study(tmp_path: Path) -> tuple[Path, Path]:
    """A study whose baseline implementation lives OUTSIDE the mutable surface."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    assert _reference(study) == 0
    (study / "lib").mkdir(exist_ok=True)
    (study / "lib" / "baseline.py").write_text("OFFSET = 0.0\n", encoding="utf-8")
    front = _front()
    front["baseline"]["implementation"] = "lib/baseline.py"
    _write_card(study, front)
    commit_all(repo, "the baseline recipe, outside the surface")
    assert _gen("expert", "lock", "--study", str(study), "--actor", "tester") == 0
    return repo, study


def test_r_inv_3_the_lock_records_the_recipe_and_a_still_recipe_reproduces(
    tmp_path: Path,
) -> None:
    """Valid control: the lock hashes implementation + fixture, and nothing moved."""
    repo, study = _recipe_study(tmp_path)
    lock = _last_object(study)
    assert set(lock["baseline_hashes"]) == {"lib/baseline.py", "data/prepared/fixture.csv"}
    assert all(sha for sha in lock["baseline_hashes"].values())
    _gates(repo, study)

    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.5), echo=False)["experiment"] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert "FAIL" not in _expert_statuses(study)["expert obligation"]


def test_r_inv_3_a_recipe_that_drifted_under_the_targets_fails(tmp_path: Path) -> None:
    """Invalid control: the targets are hit by a recipe the lock never saw.

    The bind still says `reproduced` — the numbers ARE the frozen numbers. What
    fails is the claim that this recipe produced them.
    """
    repo, study = _recipe_study(tmp_path)
    _gates(repo, study)
    (study / "lib" / "baseline.py").write_text("OFFSET = 1.0\n", encoding="utf-8")
    commit_all(repo, "quietly change the recipe after the lock")

    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.5), echo=False)["experiment"] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 0
    assert _last_object(study)["verdict"] == "reproduced"

    assert _gen("verify", "--study", str(study)) == 2
    detail = " ".join(
        check["detail"]
        for check in _receipt(study)["checks"]
        if check["name"] == "expert obligation"
    )
    assert "baseline recipe drifted" in detail
    assert "lib/baseline.py" in detail


def test_r_inv_3_the_mutable_surface_is_exempt_from_the_freeze(tmp_path: Path) -> None:
    """`train.py` IS what E0001 runs; freezing it would fail every baseline."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    assert _reference(study) == 0
    _write_card(study)  # implementation: train.py, the declared surface
    assert _gen("expert", "lock", "--study", str(study)) == 0
    assert "train.py" in _last_object(study)["baseline_hashes"]
    _gates(repo, study)

    _bump(study, "the surface moves, as it must")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.5), echo=False)["experiment"] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 0
    assert _gen("verify", "--study", str(study)) == 0


# --------------------------------------------------------------------------
# A-2 / D-3 — a repair changes what it says it changes, and nothing core
# --------------------------------------------------------------------------


def _failed_baseline(expert_study) -> tuple[Path, Path]:
    repo, study = expert_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "baseline", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.7), echo=False)["experiment"] == "E0001"
    assert _gen("expert", "bind", "--study", str(study), "E0001") == 2
    return repo, study


def test_a_repair_may_not_hide_a_change_it_did_not_name(expert_study) -> None:
    """A-2: `changed_files` is a claim about the whole diff, not a subset of it."""
    repo, study = _failed_baseline(expert_study)
    (study / "lib").mkdir(exist_ok=True)
    (study / "lib" / "prep.py").write_text("SCALE = 2.0\n", encoding="utf-8")
    commit_all(repo, "a helper nobody mentioned")

    _bump(study, "repaired")
    assert (
        _gen(
            "expert", "repair", "--study", str(study), "--changed", "train.py",
            "--note", "restored the offset",
        )
        == 0
    )
    assert _gen("check", "--study", str(study), "--action", "repair", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.5), echo=False)["experiment"] == "E0002"
    assert _gen("expert", "bind", "--study", str(study), "E0002") == 0

    assert _gen("verify", "--study", str(study)) == 2
    detail = " ".join(
        check["detail"]
        for check in _receipt(study)["checks"]
        if check["name"] == "expert repairs"
    )
    assert "lib/prep.py" in detail
    assert "without being named in --changed" in detail


@pytest.mark.parametrize(
    "name",
    ["study_state.json", "events.jsonl", "study.yaml", "runs/E0001/manifest.json",
     "generation/events.jsonl", "findings.md", "results.tsv"],
)
def test_a_repair_may_not_name_core_state_or_evidence(expert_study, name: str) -> None:
    """D-3: naming a path also EXEMPTS it from the clean-tree check."""
    repo, study = _failed_baseline(expert_study)
    head = git(repo, "rev-parse", "HEAD")
    assert (
        _gen("expert", "repair", "--study", str(study), "--changed", name, "--note", "n") == 1
    )
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == ""


def test_a_repair_admission_without_a_repair_object_is_refused(expert_study) -> None:
    """A-10: the invalid control for `_rule_repair_needs_a_repair_object`."""
    _repo, study = _failed_baseline(expert_study)
    _bump(study, "repaired but unrecorded")
    assert _gen("check", "--study", str(study), "--action", "repair", "--track", "primary") == 2
    assert any(
        "no `expert repair` object was recorded" in reason
        for reason in _last_object(study)["reasons"]
    )
    # the valid control: record the repair first, and the same request is admitted
    assert (
        _gen(
            "expert", "repair", "--study", str(study), "--changed", "train.py",
            "--note", "restored the offset",
        )
        == 0
    )
    assert _gen("check", "--study", str(study), "--action", "repair", "--track", "primary") == 0


# --------------------------------------------------------------------------
# A-3 / A-10 — every record the study rests on is opened
# --------------------------------------------------------------------------


def test_a_citation_may_not_claim_a_stronger_basis_than_its_record(expert_study) -> None:
    """A-3: `verification_level` is checked against the record it names."""
    repo, study = expert_study
    _cite(study, "read-at-source")  # the record was recorded as `bibliography`
    commit_all(repo, "cite the record, generously")
    assert _gen("verify", "--study", str(study)) == 2
    assert "stronger basis than its record" in _reference_detail(study)

    # the valid control: a level the record actually supports
    _cite(study, "abstract-only")
    commit_all(repo, "cite the record honestly")
    assert _gen("verify", "--study", str(study)) == 0


def test_a_record_reachable_only_from_references_yaml_is_still_opened(expert_study) -> None:
    """A-10 + A-3: a hand-written record used to pass by never being looked at."""
    repo, study = expert_study
    forged = study.parents[1] / "knowledge" / "references" / "forged.json"
    forged.parent.mkdir(parents=True, exist_ok=True)
    forged.write_text(
        json.dumps(
            {
                "schema": "klein-generation/1",
                "kind": "reference",
                "id": "forged",
                "bibliographic_metadata": {"title": "A paper", "year": None, "identifier": None},
                "locator": "https://example.invalid/x",
                "supported_statement": "everything I say",
                "verification_basis": "read-at-source",
                "source_blob_sha256": None,
                "blob_retained": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _cite(study, None, record_id="forged", key="forged")
    commit_all(repo, "a record nobody recorded")
    assert _gen("verify", "--study", str(study)) == 2
    assert "record forged:" in _reference_detail(study)
    assert "read-at-source" in _reference_detail(study)


def test_a_recorded_reference_whose_file_vanished_fails_the_family(expert_study) -> None:
    """A-10: the `record_id names a record that has no record` branch, at verify."""
    repo, study = expert_study
    (study.parents[1] / "knowledge" / "references" / "collins2010.json").unlink()
    commit_all(repo, "delete the record the card rests on")
    assert _gen("verify", "--study", str(study)) == 2
    detail = _reference_detail(study)
    assert "has no record" in detail or "the file is gone" in detail


def _cite(study: Path, level: str | None, *, record_id: str = "collins2010",
          key: str = "collins2010") -> None:
    entry: dict[str, Any] = {
        "title": "Tacit and Explicit Knowledge",
        "year": 2010,
        "doi": "10.7208/chicago/9780226113821.001.0001",
        "verified": True,
        "record_id": record_id,
    }
    if level is not None:
        entry["verification_level"] = level
    (study / "references.yaml").write_text(
        yaml.safe_dump({"references": {key: entry}}, sort_keys=True), encoding="utf-8"
    )


def _reference_detail(study: Path) -> str:
    return " ".join(
        check["detail"]
        for check in _receipt(study)["checks"]
        if check["name"] == "expert references"
    )


def test_an_expert_verb_files_only_its_card_and_the_ledger(tmp_path: Path) -> None:
    """A-10: write ownership, read off the commit the verb actually filed."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    assert _reference(study) == 0
    _write_card(study)
    (study / "playbook.md").write_text("# Playbook\n\nan operator edit\n", encoding="utf-8")
    assert _gen("expert", "lock", "--study", str(study)) == 0
    names = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert names
    assert all(
        name.endswith("domain_card.md") or "/generation/" in f"/{name}" for name in names
    ), names
    # the operator's edit is still theirs, uncommitted
    assert "playbook.md" in git(repo, "status", "--porcelain")


# --------------------------------------------------------------------------
# guards, extended to the new modules
# --------------------------------------------------------------------------


def test_the_new_modules_are_covered_by_the_spine_guards() -> None:
    """The WP-00 guards rglob the package; assert the new files are in reach."""
    package = REPO_ROOT / "kleinlib" / "generation"
    names = {path.name for path in package.rglob("*.py")}
    assert {"expert.py", "references.py"} <= names
    banned = ("requests", "httpx", "urllib.request", "anthropic", "openai", "socket")
    for name in ("expert.py", "references.py"):
        text = (package / name).read_text(encoding="utf-8")
        for module in banned:
            assert f"import {module}" not in text and f"from {module}" not in text


def test_the_capability_is_registered_in_both_lists() -> None:
    from kleinlib.generation import capabilities, manifest

    assert "expertise" in manifest.SUPPORTED_CAPABILITIES
    assert "expertise" in manifest.KNOWN_CAPABILITIES
    assert capabilities.load()["expertise"] is ge.CAPABILITY


def _last_object(study: Path) -> dict:
    lines = (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    sha = json.loads(lines[-1])["payload_sha256"]
    return json.loads(
        (study / "generation" / "objects" / f"{sha}.json").read_text(encoding="utf-8")
    )
