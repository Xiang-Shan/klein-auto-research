"""``kleinlib.workflow`` stayed a drop-in facade after the module split.

The 2,600-line coordinator was split into errors/primitives/contract/events/
manifest/decision/transaction/state/checks.  Everything the rest of the repo
imports still comes from ``kleinlib.workflow`` and is the SAME object as the one
its home module defines — this file freezes that surface so a later move cannot
quietly drop or duplicate a name.

It also pins the import weight: the pure modules must not drag torch, LightGBM,
or scikit-learn into the interpreter.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys

import pytest

import kleinlib.workflow as workflow

# --------------------------------------------------------------------------
# The frozen public surface: name -> (home module, name in that module).
# --------------------------------------------------------------------------

PUBLIC_SURFACE: dict[str, tuple[str, str]] = {
    "AUTO_PRINTED_METRIC_KEYS": ("kleinlib.schema", "AUTO_PRINTED_METRIC_KEYS"),
    "Check": ("kleinlib.checks", "Check"),
    "EVALUATOR_PRINTED_KEYS": ("kleinlib.schema", "EVALUATOR_PRINTED_KEYS"),
    "GATE_ARTIFACTS": ("kleinlib.contract", "GATE_ARTIFACTS"),
    "IDENTIFIER_RE": ("kleinlib.contract", "IDENTIFIER_RE"),
    "METRIC_LINE_RE": ("kleinlib.decision", "METRIC_LINE_RE"),
    "PLACEHOLDER_RE": ("kleinlib.contract", "PLACEHOLDER_RE"),
    "ProcessResult": ("kleinlib.workflow", "ProcessResult"),
    "RUN_ID_RE": ("kleinlib.manifest", "RUN_ID_RE"),
    "SCHEMA_VERSION": ("kleinlib.contract", "SCHEMA_VERSION"),
    "STRONG_CLAIM_RE": ("kleinlib.workflow", "STRONG_CLAIM_RE"),
    "STUDY_ID_RE": ("kleinlib.contract", "STUDY_ID_RE"),
    "StudyLock": ("kleinlib.primitives", "StudyLock"),
    "UNCERTAINTY_EVIDENCE_RE": ("kleinlib.workflow", "UNCERTAINTY_EVIDENCE_RE"),
    "UNSAFE_PAYLOAD_SUFFIXES": ("kleinlib.manifest", "UNSAFE_PAYLOAD_SUFFIXES"),
    "V2_RESULTS_COLUMNS": ("kleinlib.schema", "V2_RESULTS_COLUMNS"),
    "VALID_DISPOSITIONS": ("kleinlib.contract", "VALID_DISPOSITIONS"),
    "VALID_GOALS": ("kleinlib.contract", "VALID_GOALS"),
    "WorkflowError": ("kleinlib.errors", "WorkflowError"),
    "acknowledge_headroom": ("kleinlib.state", "acknowledge_headroom"),
    "append_event": ("kleinlib.events", "append_event"),
    "artifact_inventory": ("kleinlib.manifest", "artifact_inventory"),
    "atomic_write_json": ("kleinlib.primitives", "atomic_write_json"),
    "atomic_write_text": ("kleinlib.primitives", "atomic_write_text"),
    "canonical_json": ("kleinlib.primitives", "canonical_json"),
    "choose_disposition": ("kleinlib.decision", "choose_disposition"),
    "current_branch": ("kleinlib.transaction", "current_branch"),
    "derive_results": ("kleinlib.manifest", "derive_results"),
    "environment_fingerprint": ("kleinlib.transaction", "environment_fingerprint"),
    "events_path": ("kleinlib.events", "events_path"),
    "finalize": ("kleinlib.workflow", "finalize"),
    "fingerprint_path": ("kleinlib.primitives", "fingerprint_path"),
    "initial_state": ("kleinlib.state", "initial_state"),
    "load_contract": ("kleinlib.contract", "load_contract"),
    "load_manifests": ("kleinlib.manifest", "load_manifests"),
    "load_state": ("kleinlib.state", "load_state"),
    "normalize_tracks": ("kleinlib.contract", "normalize_tracks"),
    "parse_metric_log": ("kleinlib.decision", "parse_metric_log"),
    "preflight_checks": ("kleinlib.checks", "preflight_checks"),
    "prepared_data_path": ("kleinlib.contract", "prepared_data_path"),
    "read_events": ("kleinlib.events", "read_events"),
    "reconcile_state": ("kleinlib.state", "reconcile_state"),
    "record_gate": ("kleinlib.state", "record_gate"),
    "recover": ("kleinlib.workflow", "recover"),
    "render_results": ("kleinlib.manifest", "render_results"),
    "repo_root_for": ("kleinlib.transaction", "repo_root_for"),
    "resolve_study": ("kleinlib.contract", "resolve_study"),
    "run_one": ("kleinlib.workflow", "run_one"),
    "run_subprocess": ("kleinlib.workflow", "run_subprocess"),
    "save_state": ("kleinlib.state", "save_state"),
    "schema_version": ("kleinlib.contract", "schema_version"),
    "sha256_bytes": ("kleinlib.primitives", "sha256_bytes"),
    "sha256_file": ("kleinlib.primitives", "sha256_file"),
    "split_fingerprint": ("kleinlib.contract", "split_fingerprint"),
    "state_path": ("kleinlib.state", "state_path"),
    "status_summary": ("kleinlib.workflow", "status_summary"),
    "track_headroom": ("kleinlib.decision", "track_headroom"),
    "utc_now": ("kleinlib.primitives", "utc_now"),
    "validate_contract": ("kleinlib.contract", "validate_contract"),
    "validate_manifest": ("kleinlib.manifest", "validate_manifest"),
    "verify_event_chain": ("kleinlib.events", "verify_event_chain"),
    "verify_study": ("kleinlib.checks", "verify_study"),
}

#: Private helpers that moved out but are still reachable as ``workflow._name``.
#: ``_complete_evidence_transaction`` and ``_commit_state_writes`` are the two
#: deliberate exceptions: workflow keeps thin wrappers under those names so a
#: test patching ``workflow._git_commit`` still injects INSIDE the transaction.
PRIVATE_SURFACE: dict[str, tuple[str, str]] = {
    "_STATE_WRITE_PATHS": ("kleinlib.transaction", "STATE_WRITE_PATHS"),
    "_artifact_hash_problems": ("kleinlib.checks", "_artifact_hash_problems"),
    "_artifact_path": ("kleinlib.manifest", "_artifact_path"),
    "_assert_run_worktree": ("kleinlib.transaction", "assert_run_worktree"),
    "_commit_state_writes": ("kleinlib.workflow", "_commit_state_writes"),
    "_complete_evidence_transaction": (
        "kleinlib.workflow",
        "_complete_evidence_transaction",
    ),
    "_enforce_headroom": ("kleinlib.decision", "_enforce_headroom"),
    "_evidence_commit": ("kleinlib.manifest", "_evidence_commit"),
    "_git": ("kleinlib.transaction", "git"),
    "_git_blob": ("kleinlib.transaction", "git_blob"),
    "_git_commit": ("kleinlib.transaction", "git_commit"),
    "_guardrail_contract_problems": ("kleinlib.contract", "_guardrail_contract_problems"),
    "_guardrail_entries": ("kleinlib.contract", "_guardrail_entries"),
    "_guardrails_pass": ("kleinlib.decision", "_guardrails_pass"),
    "_headroom_ack": ("kleinlib.decision", "_headroom_ack"),
    "_headroom_check": ("kleinlib.checks", "_headroom_check"),
    "_headroom_context": ("kleinlib.decision", "_headroom_context"),
    "_incumbent": ("kleinlib.decision", "_incumbent"),
    "_legacy_results_problems": ("kleinlib.checks", "_legacy_results_problems"),
    "_manifest_paths": ("kleinlib.manifest", "_manifest_paths"),
    "_method_card_triad": ("kleinlib.state", "_method_card_triad"),
    "_noise_floor_problems": ("kleinlib.contract", "_noise_floor_problems"),
    "_phase_ids": ("kleinlib.contract", "_phase_ids"),
    "_phase_spec": ("kleinlib.contract", "_phase_spec"),
    "_placeholder_locations": ("kleinlib.contract", "_placeholder_locations"),
    "_relative": ("kleinlib.transaction", "relative"),
    "_run_log_evidence": ("kleinlib.manifest", "_run_log_evidence"),
    "_sealed_access_zero": ("kleinlib.state", "_sealed_access_zero"),
    "_stage_evidence": ("kleinlib.transaction", "stage_evidence"),
    "_study_python_sources": ("kleinlib.checks", "_study_python_sources"),
    "_v2_ledger_problems": ("kleinlib.checks", "_v2_ledger_problems"),
}

#: The split's dependency order.  Every module imports only modules ABOVE it.
SPLIT_MODULES = (
    "kleinlib.errors",
    "kleinlib.primitives",
    "kleinlib.contract",
    "kleinlib.events",
    "kleinlib.manifest",
    "kleinlib.decision",
    "kleinlib.transaction",
    "kleinlib.state",
    "kleinlib.checks",
    "kleinlib.workflow",
)


# --------------------------------------------------------------------------
# 1. the surface is complete, and every name is the home module's own object
# --------------------------------------------------------------------------


def test_all_lists_exactly_the_frozen_public_surface() -> None:
    assert sorted(workflow.__all__) == sorted(PUBLIC_SURFACE)


@pytest.mark.parametrize("name", sorted(PUBLIC_SURFACE))
def test_public_name_is_importable_and_identical_to_its_home(name: str) -> None:
    home_name, attribute = PUBLIC_SURFACE[name]
    module = importlib.import_module("kleinlib.workflow")
    assert hasattr(module, name), f"{name} is no longer importable from kleinlib.workflow"
    home = importlib.import_module(home_name)
    assert getattr(module, name) is getattr(home, attribute), (
        f"kleinlib.workflow.{name} is not the same object as {home_name}.{attribute}"
    )


@pytest.mark.parametrize("name", sorted(PRIVATE_SURFACE))
def test_private_name_is_still_reachable_and_identical(name: str) -> None:
    home_name, attribute = PRIVATE_SURFACE[name]
    home = importlib.import_module(home_name)
    assert getattr(workflow, name) is getattr(home, attribute)


def test_from_import_still_works_for_every_public_name() -> None:
    namespace: dict[str, object] = {}
    exec(  # noqa: S102 - the point is to exercise the real import statement
        "from kleinlib.workflow import " + ", ".join(sorted(PUBLIC_SURFACE)),
        namespace,
    )
    for name in PUBLIC_SURFACE:
        assert namespace[name] is getattr(workflow, name)


def test_the_split_modules_all_import() -> None:
    for name in SPLIT_MODULES:
        assert importlib.import_module(name).__name__ == name


# --------------------------------------------------------------------------
# 2. the pure modules stay light
# --------------------------------------------------------------------------

HEAVY = ("torch", "lightgbm", "sklearn")


def test_pure_modules_do_not_pull_the_heavy_stacks() -> None:
    code = """
import json
import sys
import kleinlib.contract
import kleinlib.events
import kleinlib.state
import kleinlib.decision
print(json.dumps({name: name in sys.modules for name in ("torch", "lightgbm", "sklearn")}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert json.loads(completed.stdout) == dict.fromkeys(HEAVY, False)


def test_importing_workflow_itself_stays_light() -> None:
    code = """
import json
import sys
import kleinlib.workflow
print(json.dumps({name: name in sys.modules for name in ("torch", "lightgbm", "sklearn")}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert json.loads(completed.stdout) == dict.fromkeys(HEAVY, False)


# --------------------------------------------------------------------------
# 3. the dependency order really is acyclic
# --------------------------------------------------------------------------


def test_each_split_module_imports_alone_in_a_fresh_interpreter() -> None:
    """A cycle would surface as a partially-initialized module on direct import."""
    for name in SPLIT_MODULES:
        completed = subprocess.run(
            [sys.executable, "-c", f"import {name}; print({name}.__name__)"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == name
