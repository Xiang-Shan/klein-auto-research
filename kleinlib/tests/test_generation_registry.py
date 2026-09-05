"""Capability registration hooks (WP-00b): a capability plugs in, never patches in.

The spine ships zero capabilities, so the only way to test the hooks is to
register a fake one — which is exactly the point: if a fake capability written
in this file can add an admission rule, a verify family, a receipt outcome, a
label column and a status line without one edit to ``admission.py``,
``verify.py`` or ``label.py``, then so can the real ones.

The last test here is the byte-identity guard: a study that declares nothing
must produce the receipt it produced before capabilities existed — same key
set, same check names, ``capabilities == {}``.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest
from test_generation_spine import _bump, _gates, _gen, _receipt, _scaffold, _statuses
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib import cli
from kleinlib.generation import capabilities, manifest, registry
from kleinlib.generation.verify import Check
from kleinlib.workflow import run_one

FAKE_MODULE = "kleinlib.generation._fake"


# --------------------------------------------------------------------------
# the fake capability
# --------------------------------------------------------------------------


def _rule_run_needs_tests(ctx) -> list[str]:
    """One registered admission rule: this capability wants adjudication."""
    if ctx.action == "run" and not ctx.tests:
        return ["the fake capability requires --tests on a run admission"]
    return []


def _family(ctx) -> tuple[list[Check], dict[str, object]]:
    """One registered verify family: one check, and an outcome beside it."""
    detail = f"{len(ctx.receipts)} receipt(s), {len(ctx.match.in_scope)} run(s) in scope"
    return [Check("generation fake", "PASS", detail)], {"integrity": "PASS", "outcome": "demo"}


@pytest.fixture
def fake_capability(monkeypatch):
    """Register ``fake`` in both registries and in the loader, for one test."""
    module = types.ModuleType(FAKE_MODULE)
    module.CAPABILITY = registry.Capability(
        name="fake",
        admission_rules=(_rule_run_needs_tests,),
        verify_family=_family,
    )
    monkeypatch.setitem(sys.modules, FAKE_MODULE, module)
    monkeypatch.setattr(capabilities, "MODULES", ("_fake",))
    monkeypatch.setattr(manifest, "KNOWN_CAPABILITIES", (*manifest.KNOWN_CAPABILITIES, "fake"))
    monkeypatch.setattr(manifest, "SUPPORTED_CAPABILITIES", ("fake",))
    return module.CAPABILITY


@pytest.fixture
def fake_study(tmp_path: Path, fake_capability) -> tuple[Path, Path]:
    """A generation-enabled study that DECLARED the fake capability."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "fake") == 0
    _gates(repo, study)
    return repo, study


# --------------------------------------------------------------------------
# §2 — one source of truth, checked rather than derived
# --------------------------------------------------------------------------


def test_the_loader_and_the_manifest_registry_agree() -> None:
    """`manifest.py` cannot import the loader, so the agreement is asserted."""
    assert set(capabilities.load()) == set(manifest.SUPPORTED_CAPABILITIES)
    assert len(set(capabilities.MODULES)) == len(capabilities.MODULES)  # each listed once


def test_the_loader_and_the_manifest_registry_agree_with_one_registered(
    fake_capability,
) -> None:
    loaded = capabilities.load()
    assert set(loaded) == set(manifest.SUPPORTED_CAPABILITIES) == {"fake"}
    assert loaded["fake"] is fake_capability


def test_a_module_without_a_capability_is_a_defect_not_a_silent_skip(monkeypatch) -> None:
    from kleinlib.errors import WorkflowError

    monkeypatch.setitem(sys.modules, FAKE_MODULE, types.ModuleType(FAKE_MODULE))
    monkeypatch.setattr(capabilities, "MODULES", ("_fake",))
    with pytest.raises(WorkflowError, match="exports no module-level"):
        capabilities.load()


# --------------------------------------------------------------------------
# §3 — the admission hook
# --------------------------------------------------------------------------


def test_a_registered_rule_decides_admission_for_a_declared_capability(fake_study) -> None:
    """The capability's own rule refuses, and satisfying it admits."""
    _repo, study = fake_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2
    refused = _last_object(study)
    assert refused["verdict"] == "refused"
    assert refused["reasons"] == ["the fake capability requires --tests on a run admission"]

    assert (
        _gen(
            "check", "--study", str(study), "--action", "run", "--track", "primary", "--tests", "P1"
        )
        == 0
    )


def test_a_typed_request_names_the_capability_to_declare(tmp_path: Path) -> None:
    """The spine's half: undeclared → declare it; declared → its rules decide."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study)) == 0
    _gates(repo, study)
    assert (
        _gen(
            "check",
            "--study",
            str(study),
            "--action",
            "run",
            "--track",
            "primary",
            "--obligation",
            "O1",
        )
        == 2
    )
    assert _last_object(study)["reasons"] == [
        "obligation admission requires the expertise capability; declare it in "
        "generation/manifest.yaml"
    ]


# --------------------------------------------------------------------------
# §3 — the verify, label and status hooks
# --------------------------------------------------------------------------


def test_a_registered_family_reaches_the_receipt_the_label_and_status(
    fake_study, capsys
) -> None:
    """One family: a check in the receipt, an outcome, a label column, a line."""
    _repo, study = fake_study
    _bump(study, "one")
    assert (
        _gen(
            "check", "--study", str(study), "--action", "run", "--track", "primary", "--tests", "P1"
        )
        == 0
    )
    assert run_one(study, command=metric_command(0.7), echo=False)["experiment"] == "E0001"

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert _statuses(receipt, "generation fake") == ["PASS"]
    assert receipt["capabilities"] == {"fake": {"integrity": "PASS", "outcome": "demo"}}
    detail = next(c["detail"] for c in receipt["checks"] if c["name"] == "generation fake")
    assert detail == "1 receipt(s), 1 run(s) in scope"

    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _gen("label", "--study", str(study)) == 0
    label = json.loads((study / "generation" / "label.json").read_text(encoding="utf-8"))
    assert label["capabilities"]["fake"] == "demo"
    assert label["capabilities"]["parity"] == "n/a"

    capsys.readouterr()
    assert _gen("status", "--study", str(study)) == 0
    assert "  fake: PASS / demo" in capsys.readouterr().out


def test_a_failing_integrity_refuses_the_label(fake_study) -> None:
    """Belt and braces: the receipt's failed count AND the integrity column."""
    repo, study = fake_study
    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0

    path = study / "generation" / "verify_receipt.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["capabilities"]["fake"] = {"integrity": "FAIL", "outcome": "incomplete"}
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    commit_all(repo, "a family reported a broken record")

    from kleinlib.generation.chronology import git_head, repo_for
    from kleinlib.generation.label import label_problems

    problems = label_problems(study, repo_for(study), git_head(repo_for(study)))
    assert any("capability integrity FAILed for fake" in problem for problem in problems)
    assert _gen("label", "--study", str(study)) == 2


def test_a_declared_capability_this_version_cannot_load_fails_verify(
    fake_study, monkeypatch
) -> None:
    """A commitment this Klein cannot check is a FAIL, never a silent skip."""
    _repo, study = fake_study
    monkeypatch.setattr(capabilities, "MODULES", ())
    assert _gen("verify", "--study", str(study)) == 2
    details = " ".join(
        check["detail"] for check in _receipt(study)["checks"] if check["name"] == "generation manifest"
    )
    assert "'fake' declared but not supported by this version" in details
    # and the same refusal reaches admission, so nothing new can be admitted
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2


# --------------------------------------------------------------------------
# the byte-identity guard
# --------------------------------------------------------------------------


SPINE_RECEIPT_KEYS = {
    "schema",
    "kind",
    "study",
    "git_head",
    "klein_version",
    "manifest_sha256",
    "scope",
    "checks",
    "summary",
    "runs",
    "receipts",
    "capabilities",
}


def test_a_study_declaring_nothing_gets_the_receipt_it_always_got(tmp_path: Path) -> None:
    """`capabilities: []` runs no family, adds no check, and keeps `{}`."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study)) == 0
    _gates(repo, study)
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert set(receipt) == SPINE_RECEIPT_KEYS
    assert receipt["capabilities"] == {}
    assert {check["name"] for check in receipt["checks"]} == {
        "generation manifest",
        "generation chain",
        "generation anchors",
        "generation orphans",
        "generation admission",
        "generation replay",
        "generation findings label",
        "generation commits",
    }

    # unchanged determinism: a second verify rewrites nothing and files nothing
    before = (study / "generation" / "verify_receipt.json").read_bytes()
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("verify", "--study", str(study)) == 0
    assert (study / "generation" / "verify_receipt.json").read_bytes() == before
    assert git(repo, "rev-parse", "HEAD") == head


def _last_object(study: Path) -> dict:
    """The object the newest extension event points at."""
    lines = (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    sha = json.loads(lines[-1])["payload_sha256"]
    return json.loads(
        (study / "generation" / "objects" / f"{sha}.json").read_text(encoding="utf-8")
    )
