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
        == 2
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
