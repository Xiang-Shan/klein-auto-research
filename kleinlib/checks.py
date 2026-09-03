"""Every read-only audit Klein reports: ``klein preflight`` and ``klein verify``.

Extracted verbatim from :mod:`kleinlib.workflow`.  A :class:`Check` is a named,
pass/fail, human-readable line; ``preflight_checks`` produces the whole report
and ``verify_study`` is that same report with the working-tree and branch
requirements relaxed (a finalized study must keep verifying).  Nothing here
mutates a study — every problem is returned, never raised.

One documented exception: ``klein verify`` on a schema-3 study files its own
receipt (:func:`write_verify_receipt`, ``verify_receipt.json``) through
``transaction.commit_state_writes(scope="own")`` — the receipt and nothing else,
the same way every other reading verb commits only what it generated.  That
write is the receipt of the audit, never a change to the evidence, and it is off
for schema 2 so studies 03 and 05–09 verify byte-identically.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import (
    MODELING_GATES,
    _guardrail_entries,
    _phase_ids,
    load_contract,
    mutable_surface,
    normalize_tracks,
    prepared_data_path,
    schema_version,
    split_fingerprint,
    validate_contract,
)
from .decision import _headroom_ack, _headroom_context, _incumbent
from .errors import WorkflowError
from .events import verify_event_chain
from .manifest import (
    _artifact_path,
    _evidence_commit,
    _manifest_paths,
    load_manifests,
    render_results,
    validate_manifest,
)
from .predictions import OPEN
from .predictions import ledger as prediction_ledger
from .primitives import atomic_write_json, fingerprint_path, sha256_bytes, sha256_file, utc_now
from .schema import AUTO_PRINTED_METRIC_KEYS, EVALUATOR_PRINTED_KEYS
from .state import (
    load_state,
    referee_gate,
    registered_partition_fingerprints,
    split_policy_hash,
    verifier_script_hashes,
)
from .transaction import (
    commit_state_writes,
    current_branch,
    git,
    git_blob,
    relative,
    repo_root_for,
)

__all__ = [
    "ABSENT_LOCAL_ARTIFACT",
    "Check",
    "RECEIPT_NAME",
    "preflight_checks",
    "verify_receipt",
    "verify_study",
    "write_verify_receipt",
]

@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str



#: The one sentence every "the bytes are not here, and policy says they never
#: would be" report uses.  ``klein verify`` on a bare clone must be able to check
#: what was actually committed; a prepared dataset under a gitignored path and a
#: model blob whose manifest says ``committed: false`` are absent by design, not
#: by damage.  The recorded hash stays in the message so the claim is still
#: falsifiable the moment the artifact is regenerated.
ABSENT_LOCAL_ARTIFACT = (
    "local artifact absent (not committed by policy) — hash recorded {sha}; "
    "re-run prepare.py / `klein replicate` to re-check"
)


def _is_git_ignored(repo: Path | None, path: Path) -> bool:
    """True when .gitignore covers ``path`` (tracked paths are never ignored)."""
    if repo is None:
        return False
    try:
        rel = relative(repo, path)
    except WorkflowError:
        return False
    result = git(repo, ["check-ignore", "-q", "--", rel], check=False)
    return result.returncode == 0


def _v2_ledger_problems(
    study_dir: Path, *, require_local: bool = True
) -> tuple[list[str], list[str]]:
    """(hard problems, policy-absent artifacts) for the ledger-integrity check.

    With ``require_local`` (the default, and what ``klein preflight`` uses) an
    absent local-only artifact is a hard problem exactly as before.  Without it
    — ``klein verify`` on a fresh checkout — the absence moves to the second
    list and becomes a ``[WARN]``.  A PRESENT artifact is byte-checked
    identically either way.
    """
    problems: list[str] = []
    absences: list[str] = []
    try:
        manifests = load_manifests(study_dir)
    except WorkflowError as exc:
        return [str(exc)], absences
    for index, manifest in enumerate(manifests, start=1):
        problems.extend(f"{manifest.get('experiment', index)}: {p}" for p in validate_manifest(manifest, index))
    try:
        surface = mutable_surface(load_contract(study_dir))
    except WorkflowError:
        surface = ("train.py",)
    try:
        repo = repo_root_for(study_dir)
        surface_rels = [relative(repo, study_dir / name) for name in surface]
    except WorkflowError as exc:
        problems.append(str(exc))
        repo = None
        surface_rels = []
    if repo is not None:
        for manifest_path, manifest in zip(
            _manifest_paths(study_dir), manifests, strict=True
        ):
            run_id = str(manifest.get("experiment", "?"))
            manifest_rel = relative(repo, manifest_path)
            committed_manifest = git_blob(repo, "HEAD", manifest_rel)
            if committed_manifest is None:
                problems.append(f"{run_id}: manifest is not tracked at HEAD")
            elif committed_manifest != manifest_path.read_bytes():
                problems.append(f"{run_id}: manifest differs from its HEAD blob")
            for field in ("base_commit", "candidate_commit"):
                commit = manifest.get(field)
                if isinstance(commit, str):
                    resolved = git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"], check=False)
                    if resolved.returncode:
                        problems.append(f"{run_id}: {field} does not resolve")
            evidence = _evidence_commit(manifest)
            if evidence is not None:
                resolved = git(repo, ["cat-file", "-e", f"{evidence}^{{commit}}"], check=False)
                if resolved.returncode:
                    problems.append(f"{run_id}: evidence_commit does not resolve")
            base = manifest.get("base_commit")
            candidate = manifest.get("candidate_commit")
            if isinstance(base, str) and isinstance(candidate, str):
                patch = git(
                    repo,
                    ["diff", "--binary", base, candidate, "--", *surface_rels],
                    check=False,
                )
                if patch.returncode or sha256_bytes(patch.stdout.encode()) != manifest.get("code_patch_hash"):
                    problems.append(f"{run_id}: code_patch_hash does not match commits")
            artifacts = manifest.get("artifacts", {})
            if isinstance(artifacts, Mapping):
                for rel, meta in artifacts.items():
                    if not isinstance(meta, Mapping):
                        problems.append(f"{run_id}: invalid artifact metadata for {rel}")
                        continue
                    try:
                        path = _artifact_path(study_dir, str(rel))
                    except WorkflowError as exc:
                        problems.append(f"{run_id}: {exc}")
                        continue
                    expected_hash = meta.get("sha256")
                    committed = meta.get("committed") is True
                    if committed and evidence is not None:
                        repo_rel = relative(repo, path)
                        content = git_blob(repo, evidence, repo_rel)
                        if content is None:
                            problems.append(
                                f"{run_id}: committed artifact missing from evidence commit: {rel}"
                            )
                        elif sha256_bytes(content) != expected_hash:
                            problems.append(
                                f"{run_id}: committed artifact hash mismatch: {rel}"
                            )
                        if str(rel) == f"runs/{run_id}/run.log":
                            if not path.is_file():
                                problems.append(f"{run_id}: run log is missing: {rel}")
                            elif sha256_file(path) != expected_hash:
                                problems.append(f"{run_id}: run-log hash mismatch: {rel}")
                    elif not path.is_file():
                        if require_local or committed:
                            problems.append(f"{run_id}: local artifact missing: {rel}")
                        else:
                            absences.append(
                                f"{run_id}: {rel}: "
                                + ABSENT_LOCAL_ARTIFACT.format(sha=expected_hash)
                            )
                    elif sha256_file(path) != expected_hash:
                        problems.append(f"{run_id}: local artifact hash mismatch: {rel}")
    try:
        expected = render_results(manifests)
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"could not derive results view from manifests: {exc}")
        expected = None
    path = study_dir / "results.tsv"
    if not path.is_file():
        problems.append("results.tsv is missing")
    elif expected is not None and path.read_text(encoding="utf-8") != expected:
        problems.append("results.tsv is not the exact derived view of runs/*/manifest.json")
    return problems, absences


def _artifact_hash_problems(study_dir: Path, state: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    hashes = state.get("artifact_hashes", {})
    if not isinstance(hashes, Mapping):
        return ["study_state artifact_hashes is invalid"]
    for name, expected in hashes.items():
        path = study_dir / str(name)
        if not path.is_file():
            problems.append(f"recorded gate artifact is missing: {name}")
        elif sha256_file(path) != expected:
            problems.append(f"recorded gate artifact changed after acknowledgement: {name}")
    return problems


def _legacy_results_problems(path: Path) -> list[str]:
    from . import schema

    if not path.is_file():
        return ["results.tsv is missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        rows = list(reader)
    if not rows or not schema.is_valid_header("\t".join(rows[0])):
        return ["v1 results.tsv header is incompatible"]
    problems: list[str] = []
    for index, row in enumerate(rows[1:], start=2):
        problems.extend(f"line {index}: {p}" for p in schema.validate_row(row, n_columns=len(rows[0])))
    return problems


def preflight_checks(
    study_dir: Path,
    *,
    require_clean: bool = True,
    require_branch: bool = True,
    require_local: bool = True,
) -> list[Check]:
    checks: list[Check] = []
    try:
        contract = load_contract(study_dir)
    except WorkflowError as exc:
        return [Check("study contract", False, str(exc))]
    version = schema_version(contract)
    if version == 1:
        checks.append(Check("schema", True, "v1 compatibility mode (deprecated, explicit warning)"))
        problems = _legacy_results_problems(study_dir / "results.tsv")
        checks.append(Check("legacy ledger", not problems, "; ".join(problems) or "valid five-column ledger"))
        return checks

    contract_problems = validate_contract(contract, study_dir)
    # The version is interpolated, not hardcoded: a schema-3 study was being
    # told its contract was "schema_version 2 valid". Schema-2 output is
    # byte-identical, which is what studies 03 and 05-09 keep verifying against.
    checks.append(Check("study contract", not contract_problems, "; ".join(contract_problems) or f"schema_version {version} contract valid"))
    for track_name, track_spec in normalize_tracks(contract).items():
        metric = track_spec["metric"]
        floor = metric.get("noise_floor")
        if version >= 3 and metric.get("exactness") == "exact":
            # A k-seed floor is meaningless for a deterministic objective: the
            # spread IS zero, and `minimum_delta` is the objective's resolution
            # (1 for an integer count). The declaration is waived — but a floor
            # block with a non-zero spread contradicts the declaration, and one
            # of the two is wrong.
            std = floor.get("std") if isinstance(floor, Mapping) else None
            try:
                nonzero = std is not None and float(std) > 0
            except (TypeError, ValueError):
                nonzero = True
            checks.append(
                Check(
                    "noise floor",
                    not nonzero,
                    f"track {track_name!r}: exactness=exact — floor waived; "
                    f"minimum_delta {float(metric.get('minimum_delta', 0)):.6g} is the "
                    "objective's resolution (exactness_note)"
                    if not nonzero
                    else f"track {track_name!r}: exactness=exact but noise_floor.std is "
                    f"{std} — a deterministic objective has no spread; drop the floor "
                    "block or drop the exactness claim",
                )
            )
            continue
        if not isinstance(floor, Mapping):
            checks.append(
                Check(
                    "noise floor",
                    True,
                    f"track {track_name!r}: not measured — Phase 0 protocol expects a "
                    "k-seed measurement (see consult-protocol.md)"
                    + (
                        " — metric.fit_noise is recorded, but a seed spread measures "
                        "the FIT, not the comparison: run --recipe split-lottery or "
                        "--recipe paired-bootstrap for the bar"
                        if version >= 3 and isinstance(metric.get("fit_noise"), Mapping)
                        else ""
                    ),
                )
            )
            continue
        checks.append(_floor_bar_check(track_name, metric, floor, version))
    try:
        state = load_state(study_dir, contract)
    except WorkflowError as exc:
        checks.append(Check("study state", False, str(exc)))
        return checks
    checks.append(Check("study state", True, "study_state.json loaded"))

    try:
        repo = repo_root_for(study_dir)
        checks.append(Check("git repository", True, str(repo)))
        if require_branch:
            expected = f"experiments/{contract.get('study_id')}"
            branch = current_branch(repo)
            checks.append(Check("git branch", branch == expected, f"current={branch!r}; required={expected!r}"))
        if require_clean:
            dirty = git(repo, ["status", "--porcelain", "--untracked-files=all"]).stdout.strip()
            checks.append(Check("working tree", not dirty, dirty or "clean"))
    except WorkflowError as exc:
        checks.append(Check("git repository", False, str(exc)))

    phase_ids = _phase_ids(contract)
    current_phase = state.get("current_phase")
    if current_phase not in phase_ids:
        checks.append(
            Check(
                "phase ladder",
                False,
                f"state current_phase {current_phase!r} is not in the contract's "
                f"phases {phase_ids} — phases were renamed/removed after "
                "initialization; amend the contract to match the recorded state",
            )
        )
    else:
        acked = set(state.get("phase_acknowledgements", {}))
        earlier_unacked = [
            pid for pid in phase_ids[: phase_ids.index(current_phase)] if pid not in acked
        ]
        checks.append(
            Check(
                "phase ladder",
                not earlier_unacked,
                (
                    f"contract declares phases before the current one that were never "
                    f"acknowledged: {earlier_unacked} — phases cannot be inserted "
                    "retroactively; fold them into the ladder the machine actually ran"
                )
                if earlier_unacked
                else f"current={current_phase!r}; ladder consistent",
            )
        )

    gates = state.get("gates", {})
    # The gates that block MODELING. The referee gate (Gate 3) is checked at
    # `finalize`, not here: a study cannot be refereed before it has run.
    for gate in MODELING_GATES:
        entry = gates.get(gate, {}) if isinstance(gates, Mapping) else {}
        valid = (
            isinstance(entry, Mapping)
            and entry.get("status") in {"recorded", "overridden"}
            and bool(entry.get("acknowledged_at"))
            and bool(entry.get("acknowledged_by"))
        )
        status = entry.get("status", "missing") if isinstance(entry, Mapping) else "invalid"
        checks.append(Check(f"gate {gate}", valid, f"status={status}"))

    artifact_problems = _artifact_hash_problems(study_dir, state)
    checks.append(Check("gate artifact hashes", not artifact_problems, "; ".join(artifact_problems) or "match"))
    event_problems = verify_event_chain(study_dir)
    checks.append(Check("event chain", not event_problems, "; ".join(event_problems) or "valid"))

    recorded_data = state.get("fingerprints", {}).get("data")
    try:
        prepared = prepared_data_path(study_dir, contract)
    except WorkflowError as exc:
        checks.append(Check("prepared-data fingerprint", False, str(exc)))
    else:
        repo_for_ignore = None
        try:
            repo_for_ignore = repo_root_for(study_dir)
        except WorkflowError:
            pass
        policy_absent = (
            not require_local
            and not prepared.exists()
            and isinstance(recorded_data, str)
            and _is_git_ignored(repo_for_ignore, prepared)
        )
        if policy_absent:
            checks.append(
                Check(
                    "prepared-data fingerprint",
                    True,
                    "[WARN] " + ABSENT_LOCAL_ARTIFACT.format(sha=recorded_data),
                )
            )
        else:
            try:
                current_data = fingerprint_path(prepared)
                checks.append(Check("prepared-data fingerprint", current_data == recorded_data, f"current={current_data}; recorded={recorded_data}"))
            except WorkflowError as exc:
                checks.append(Check("prepared-data fingerprint", False, str(exc)))
    current_split = split_fingerprint(contract)
    recorded_split = split_policy_hash(state)
    checks.append(Check("split fingerprint", current_split == recorded_split, f"current={current_split}; recorded={recorded_split}"))
    if version >= 3:
        checks.append(_contract_split_check(study_dir, state))
        checks.append(_verifier_hash_check(study_dir, contract, state))

    ledger_problems, ledger_absences = _v2_ledger_problems(
        study_dir, require_local=require_local
    )
    if ledger_problems:
        ledger_message = "; ".join(ledger_problems)
    elif ledger_absences:
        ledger_message = "[WARN] " + "; ".join(ledger_absences)
    else:
        ledger_message = "derived view matches manifests"
    checks.append(Check("ledger integrity", not ledger_problems, ledger_message))
    try:
        manifests = load_manifests(study_dir)
    except WorkflowError as exc:
        checks.append(Check("transactions", False, str(exc)))
    else:
        pending = [
            m.get("experiment")
            for m in manifests
            if not isinstance(m.get("transaction"), Mapping)
            or m.get("transaction", {}).get("status") != "complete"
        ]
        checks.append(
            Check("transactions", not pending, f"pending={pending}" if pending else "none pending")
        )
        for headroom_track, headroom_spec in normalize_tracks(contract).items():
            checks.append(
                _headroom_check(headroom_track, headroom_spec, manifests, state)
            )
    train = study_dir / "train.py"
    if not train.is_file():
        checks.append(Check("train.py", False, "missing"))
    else:
        try:
            compile(train.read_text(encoding="utf-8"), str(train), "exec")
        except SyntaxError as exc:
            checks.append(Check("train.py", False, f"syntax error: {exc}"))
        else:
            source = train.read_text(encoding="utf-8")
            if "NotImplementedError" in source:
                checks.append(
                    Check(
                        "train.py",
                        True,
                        "[WARN] syntax valid but scaffold stubs remain "
                        "(NotImplementedError) — fill load_split/build_model "
                        "before the loop; run-one would record the stub as a crash",
                    )
                )
            else:
                checks.append(Check("train.py", True, "syntax valid"))

    # Guardrail visibility (the study-05 F1 lesson): `klein run-one` reads
    # guardrails off the PRINTED metric block, so a declared key the run
    # never prints scores "missing" and discards the candidate. A key is
    # considered visible when the framework auto-prints it, or when it
    # appears textually anywhere in the study's Python sources (the
    # escape hatch for keys printed via `extra=` — naming it in a comment
    # is enough). Advisory only: ok stays True, the message carries [WARN].
    tracks = normalize_tracks(contract)
    sources = _study_python_sources(study_dir)
    # Universal keys plus the aux keys of exactly the evaluator(s) this
    # study's sources actually call — a flat union would bless keys the
    # calling evaluator prints as NA (or not at all), turning this check
    # into a false all-clear on the very failure it exists to catch.
    visible = set(AUTO_PRINTED_METRIC_KEYS)
    for evaluator, keys in EVALUATOR_PRINTED_KEYS.items():
        pattern = re.compile(rf"\b{evaluator}\s*\(")
        if any(pattern.search(text) for text in sources.values()):
            visible |= keys
    invisible: list[str] = []
    for track_name, track_spec in tracks.items():
        entries, _ = _guardrail_entries(track_spec.get("guardrails", {}))
        for key, _spec in entries:
            if key in visible:
                continue
            if any(key in text for text in sources.values()):
                continue
            invisible.append(f"track {track_name!r} declares {key!r}")
    if invisible:
        named = ", ".join(sorted(sources)) if sources else "no study .py files found"
        checks.append(
            Check(
                "guardrail visibility",
                True,
                "[WARN] "
                + "; ".join(invisible)
                + f" — not auto-printed by the evaluator and not named in {named}. "
                "`klein run-one` reads guardrails off the PRINTED block, so an "
                "unprinted guardrail scores \"missing\" and discards the candidate. "
                "Print it via evaluate*(..., extra={<key>: value}).",
            )
        )
    else:
        checks.append(
            Check(
                "guardrail visibility",
                True,
                "every declared guardrail metric is printed by the evaluator "
                "or named in the study's Python sources",
            )
        )
    return checks


def _verifier_hash_check(
    study_dir: Path, contract: Mapping[str, Any], state: Mapping[str, Any]
) -> Check:
    """The checker is the fixed thing; a change to it after E0001 is refused.

    A verifier that can be edited mid-study is just the searcher with extra
    steps.  Before any evidence exists the hash is simply re-recorded at the
    METHOD gate; once E0001 is on the ledger a difference FAILS.
    """
    current = verifier_script_hashes(study_dir, contract)
    recorded = state.get("fingerprints", {}).get("verifier")
    recorded = recorded if isinstance(recorded, Mapping) else {}
    if not current and not recorded:
        return Check("verifier", True, "no track declares a verifier")
    if current == recorded:
        return Check(
            "verifier",
            True,
            "; ".join(f"{name}={value[:12]}" for name, value in sorted(current.items()))
            or "declared but not hashed",
        )
    has_evidence = bool(_manifest_paths(study_dir))
    changed = sorted(set(current) | set(recorded))
    detail = ", ".join(
        f"{name}: recorded={str(recorded.get(name))[:12]} current={str(current.get(name))[:12]}"
        for name in changed
        if current.get(name) != recorded.get(name)
    )
    if not has_evidence:
        return Check(
            "verifier",
            True,
            f"[WARN] verifier differs from the METHOD gate record ({detail}) — "
            "re-record the gate before E0001; after that it is frozen",
        )
    return Check(
        "verifier",
        False,
        f"verifier changed after evidence exists ({detail}) — every recorded "
        "disposition was decided by the previous checker; the checker is never "
        "the searcher",
    )


#: How a schema-3 study is supposed to obtain its partitions.
_CONTRACT_SPLIT_RE = re.compile(r"\b(contract_split|load_partition)\s*\(")


def _contract_split_check(study_dir: Path, state: Mapping[str, Any]) -> Check:
    """Advisory: does anything in this study actually ASK the contract to split?

    War story 8 is the reason. An evaluator that builds its own partitions from
    a literal seed prints no fingerprint, so the notary has nothing to compare
    and a whole ledger lane can measure the wrong rows undetected. ``ok`` stays
    True — a study may legitimately have no row partitions (``split.kind: none``,
    a verifier-only study) — but the absence is on the record either way.
    """
    sources = _study_python_sources(study_dir)
    callers = sorted(name for name, text in sources.items() if _CONTRACT_SPLIT_RE.search(text))
    registered = registered_partition_fingerprints(state)
    if not callers:
        return Check(
            "contract-driven split",
            True,
            "[WARN] no study source calls kleinlib.data.contract_split / load_partition — "
            "the printed split_fingerprint cannot be checked, and a literal split seed in "
            "an evaluator is a DATA-gate BLOCKER (war story 8)",
        )
    if not registered:
        return Check(
            "contract-driven split",
            True,
            f"[WARN] {', '.join(callers)} obtain partitions from the contract, but no "
            "realized fingerprints are registered — re-record the DATA gate before E0001 "
            "so run-one can compare them",
        )
    return Check(
        "contract-driven split",
        True,
        f"{', '.join(callers)}; registered "
        + ", ".join(f"{kind}={value[:12]}" for kind, value in sorted(registered.items())),
    )


def _study_python_sources(study_dir: Path) -> dict[str, str]:
    """The study's Python sources (top level + lib/), for textual scans.

    Wider than train.py on purpose: study 06 declares guardrail keys that
    are computed in analysis.py and only routed through train.py's `extra=`.
    """
    sources: dict[str, str] = {}
    for path in sorted(study_dir.glob("*.py")) + sorted(study_dir.glob("lib/**/*.py")):
        try:
            # errors="replace": a non-UTF-8 study file must degrade to a
            # weaker textual scan, never abort the whole preflight report.
            # .as_posix(): these keys are printed in check messages and land
            # verbatim in verify_receipt.json, so a Windows separator would
            # enter a committed receipt (C5).
            sources[path.relative_to(study_dir).as_posix()] = path.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
    return sources



def _headroom_check(
    track_name: str,
    track_spec: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> Check:
    """Detection-limit disclosure. Always ``ok=True`` — a FAIL here would
    retro-fail ``klein verify`` on finalized studies (verify == preflight);
    enforcement belongs to run-one, where a refusal burns nothing."""
    from .eval import KNOWN_IDEALS

    metric = track_spec["metric"]
    name = metric.get("name")
    if not isinstance(metric.get("bound"), Mapping):
        known = KNOWN_IDEALS.get(name) if isinstance(name, str) else None
        if known is not None:
            return Check(
                "headroom",
                True,
                f"track {track_name!r}: metric {name!r} has a known ideal ({known:g}) "
                "but no metric.bound declared — headroom not audited (HINT: declare "
                "metric.bound.ideal to arm the detection-limit check)",
            )
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: no metric.bound declared — not audited",
        )
    context = _headroom_context(track_spec, _incumbent(manifests, track_name))
    if context is None:
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: bound declared; no incumbent yet (or no measured "
            "minimum_delta) — audited at first keep",
        )
    h = context["h"]
    arithmetic = (
        f"h = ({context['incumbent']:.6g} - {context['ideal']:g}) / "
        f"{context['minimum_delta']:.6g} = {h:.3f}"
    )
    if h >= 1:
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: {arithmetic} — a keep is arithmetically possible "
            "(h >= 1 means not excluded, NOT plausible: the attainable ceiling may "
            "sit short of the ideal)",
        )
    ack = _headroom_ack(state, track_name)
    if ack:
        return Check(
            "headroom",
            True,
            f"track {track_name!r}: {arithmetic} < 1 — infeasible, acknowledged by "
            f"{ack.get('acknowledged_by')} at {ack.get('acknowledged_at')}: "
            f"{ack.get('note')}",
        )
    return Check(
        "headroom",
        True,
        f"track {track_name!r}: [WARN] {arithmetic} < 1 — NO keep is arithmetically "
        "possible: not even a perfect score clears minimum_delta "
        f"(on_infeasible: {context['posture']}). Register awareness with "
        "`klein headroom ack` or re-scope the contract",
    )



def sweep_registry_problems(study_dir: Path, state: Mapping[str, Any]) -> list[str]:
    """Re-hash every measurement sweep registered with ``klein sweep register``.

    The sidecar IS the evidence of a measurement sweep — it promotes no winner
    and writes no ledger row (``references/sweep-rules.md``, the carve-out), so
    a study citing ``sweep:<name>`` is citing those bytes.  Registering hashed
    them; verify checks them, and a sidecar edited afterwards fails.  The script
    is hashed for the same reason the METHOD gate hashes a verifier: the rule
    that produced the rows must not change after the rows are quoted.

    Returns an empty list when nothing is registered — a study with no
    measurement sweep is not a study with a broken one.
    """
    registry = state.get("sweeps")
    if not isinstance(registry, Mapping) or not registry:
        return []
    problems: list[str] = []
    for name in sorted(registry):
        record = registry[name]
        if not isinstance(record, Mapping):
            problems.append(f"sweep:{name} record is not a mapping")
            continue
        for role in ("sidecar", "script"):
            relative_path = record.get(role)
            recorded = record.get(f"{role}_sha256")
            if not isinstance(relative_path, str) or not isinstance(recorded, str):
                problems.append(
                    f"sweep:{name} has no recorded {role} path/hash — re-register it"
                )
                continue
            path = study_dir / relative_path
            if not path.is_file():
                problems.append(f"sweep:{name} {role} is missing: {relative_path}")
                continue
            current = sha256_file(path)
            if current != recorded:
                problems.append(
                    f"sweep:{name} {role} {relative_path} changed after registration "
                    f"(recorded {recorded[:12]}…, now {current[:12]}…) — the evidence "
                    "findings cite is not the evidence on disk; re-run the sweep and "
                    "re-register it, or restore the committed bytes"
                )
    return problems


def _sweep_registry_checks(study_dir: Path, state: Mapping[str, Any]) -> list[Check]:
    """One check, and only when the study registered a measurement sweep.

    Silent otherwise, like the claims law without a lock: a schema-2 study that
    never used the verb sees no new line in its verify output.
    """
    registry = state.get("sweeps")
    if not isinstance(registry, Mapping) or not registry:
        return []
    problems = sweep_registry_problems(study_dir, state)
    return [
        Check(
            "registered sweeps",
            not problems,
            "; ".join(problems)
            or f"{len(registry)} registered sweep(s) hash unchanged: "
            + ", ".join(f"sweep:{name}" for name in sorted(registry)),
        )
    ]




def floor_bar_problems(
    metric: Mapping[str, Any], floor: Mapping[str, Any], version: int
) -> list[str]:
    """Is ``minimum_delta`` outside the floor that would have to detect it?

    Schema 2 keeps its original bar, ``minimum_delta >= std`` — those studies
    were run and closed against it and must keep verifying byte-identically.
    Schema 3 raises it to the number the consult protocol states and study 07
    paid for: ``minimum_delta >= max(2*std, range/2)``.  Two standard
    deviations, or half the observed range, whichever is larger — on the k a
    real Phase 0 can afford the range carries information a five-sample std
    does not, and a bar set at 1 std keeps roughly a third of pure noise.

    Returns problem strings; an empty list means the delta clears its own
    floor.  A malformed block returns nothing — ``validate_contract`` has
    already reported it and a second voice would only add noise.
    """
    try:
        std = float(floor.get("std"))
        minimum_delta = float(metric.get("minimum_delta", 0))
    except (TypeError, ValueError):
        return []
    if version < 3:
        return (
            []
            if minimum_delta >= std
            else [
                f"minimum_delta {minimum_delta:.6g} < measured seed std {std:.6g} — "
                "declaring a floor then keeping inside it is the exact dishonesty "
                "the measurement exists to prevent"
            ]
        )
    try:
        value_range = float(floor.get("range"))
    except (TypeError, ValueError):
        return []
    bar = max(2.0 * std, value_range / 2.0)
    if minimum_delta >= bar:
        return []
    return [
        f"minimum_delta {minimum_delta:.6g} < max(2*std {2 * std:.6g}, range/2 "
        f"{value_range / 2:.6g}) = {bar:.6g} — the schema-3 bar; a delta inside its "
        "own floor cannot be detected by the measurement that would have to detect it"
    ]


def _floor_bar_check(
    track_name: str, metric: Mapping[str, Any], floor: Mapping[str, Any], version: int
) -> Check:
    """One ``noise floor`` line per track, at the bar its schema version sets."""
    problems = floor_bar_problems(metric, floor, version)
    if version < 3:
        try:
            std = float(floor.get("std"))
            minimum_delta = float(metric.get("minimum_delta", 0))
        except (TypeError, ValueError):
            return Check("noise floor", True, f"track {track_name!r}: malformed floor block")
        return Check(
            "noise floor",
            not problems,
            f"track {track_name!r}: minimum_delta {minimum_delta:.6g} vs measured "
            f"seed std {std:.6g}"
            + (
                ""
                if not problems
                else " — declaring a floor then keeping inside it is the exact "
                "dishonesty the measurement exists to prevent"
            ),
        )
    estimand = floor.get("estimand")
    named = f", estimand {estimand!r}" if estimand else ""
    try:
        std = float(floor.get("std"))
        value_range = float(floor.get("range"))
        minimum_delta = float(metric.get("minimum_delta", 0))
        bar = max(2.0 * std, value_range / 2.0)
    except (TypeError, ValueError):
        return Check(
            "noise floor",
            True,
            f"track {track_name!r}: floor block malformed — see the contract check",
        )
    return Check(
        "noise floor",
        not problems,
        "; ".join(f"track {track_name!r}: {problem}" for problem in problems)
        or f"track {track_name!r}: minimum_delta {minimum_delta:.6g} >= "
        f"max(2*std, range/2) = {bar:.6g}{named}",
    )


#: Words a findings document may not use without a priced consequence on the
#: record (``research-discipline.md`` lesson 10: detectable is not actionable).
MATERIALITY_WORDS: tuple[str, ...] = (
    "materially",
    "material",
    "actionable",
    "business-critical",
)

_MATERIALITY_RE = re.compile(
    r"(?i)\b(?:" + "|".join(MATERIALITY_WORDS) + r")\b"
)

#: Where a profile named by `profile:` lives inside a Klein checkout.
PROFILE_DIR = ".claude/skills/klein/references/profiles"


def _profile_path(study_dir: Path, contract: Mapping[str, Any]) -> Path | None:
    """The profile markdown this contract points at, if it is on this machine.

    ``profile_doc:`` wins when both are present (it is the escape hatch a
    foreign repo uses to carry its own profile without forking Klein).  Returns
    None when neither resolves — the scan is then skipped, never failed: a
    wheel install has no `.claude/` tree.
    """
    from .contract import _repo_root_hint

    root = _repo_root_hint(study_dir)
    doc = contract.get("profile_doc")
    if isinstance(doc, str) and doc.strip():
        for candidate in (root / doc, study_dir / doc):
            if candidate.is_file():
                return candidate
        return None
    name = contract.get("profile")
    if isinstance(name, str) and name.strip():
        candidate = root / PROFILE_DIR / f"{name}.md"
        if candidate.is_file():
            return candidate
    return None


def profile_banned_words(profile_text: str) -> list[str]:
    """The quoted terms in a profile's §7 ``Banned:`` sentence.

    A profile controls vocabulary and nothing the engine enforces
    (``references/profiles/README.md``, knob 7), so the list is READ from the
    document rather than restated in code — adding a profile stays a one-file
    change.  Everything from ``Banned:`` up to the section's ``Must be
    qualified``/``Honest verbs`` sentence is scanned for double-quoted terms.
    """
    section = re.search(
        r"^##\s*7\.\s*Vocabulary\s*$(.*?)(?=^##\s|\Z)",
        profile_text,
        re.MULTILINE | re.DOTALL,
    )
    if section is None:
        return []
    # One line: the sentences wrap, and "Must be\nqualified" must still be found.
    body = " ".join(section.group(1).split())
    start = body.find("Banned:")
    if start < 0:
        return []
    tail = body[start:]
    for terminator in ("Must be qualified", "Honest verbs"):
        cut = tail.find(terminator)
        if cut > 0:
            tail = tail[:cut]
    # Parentheticals hold the SUGGESTED REPLACEMENT ("say \"locked before\""),
    # which is the one phrase the profile wants used, not banned.
    tail = re.sub(r"\([^()]*\)", " ", tail)
    seen: list[str] = []
    for term in re.findall(r'"([^"]+)"', tail):
        cleaned = " ".join(term.split())
        if cleaned and cleaned.lower() not in {t.lower() for t in seen}:
            seen.append(cleaned)
    return seen


def _offending_lines(text: str, pattern: re.Pattern[str], *, limit: int = 3) -> list[str]:
    """Up to *limit* `line N: <text>` strings, so the report is actionable."""
    hits: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            stripped = line.strip()
            hits.append(f"line {number}: {stripped[:120]}")
            if len(hits) >= limit:
                break
    return hits


def vocabulary_problems(
    study_dir: Path, contract: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Scan ``findings.md`` for unpriced materiality and the profile's banned words.

    Two independent readings of one file:

    ``materiality`` (schema 3, a FAILURE) — "material", "materially",
    "actionable" or "business-critical" appearing while the contract carries no
    ``materiality:`` block.  Measurement resolution is never business value: a
    gain of 0.29x the floor at n = 8 is detectable and not actionable (study
    08), and study 09 banned the conflation outright.  The fix is a priced
    consequence with its own provenance, or a different sentence.

    ``profile`` (a WARNING) — the terms the study's own profile bans, read from
    that document's §7 rather than restated here.  A warning, not a failure:
    vocabulary is the profile's business and the referee's, and the engine
    checks the same things in every profile.

    Returns ``{}`` when there is no ``findings.md`` yet — a study mid-loop has
    nothing to scan.
    """
    findings = study_dir / "findings.md"
    if not findings.is_file():
        return {}
    try:
        text = findings.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    problems: dict[str, list[str]] = {}
    if schema_version(contract) >= 3 and not isinstance(contract.get("materiality"), Mapping):
        hits = _offending_lines(text, _MATERIALITY_RE)
        if hits:
            problems["materiality"] = hits
    path = _profile_path(study_dir, contract)
    if path is not None:
        banned = profile_banned_words(path.read_text(encoding="utf-8", errors="replace"))
        if banned:
            pattern = re.compile(
                r"(?i)(?:"
                + "|".join(rf"\b{re.escape(term)}\b" for term in banned)
                + r")"
            )
            hits = _offending_lines(text, pattern)
            if hits:
                problems["profile"] = hits
    return problems


def _vocabulary_checks(study_dir: Path, contract: Mapping[str, Any]) -> list[Check]:
    """At most two lines, and none at all for a schema-2 study with a clean page."""
    problems = vocabulary_problems(study_dir, contract)
    checks: list[Check] = []
    if problems.get("materiality"):
        checks.append(
            Check(
                "materiality vocabulary",
                False,
                "findings.md claims materiality with no priced consequence on the "
                "record: "
                + "; ".join(problems["materiality"])
                + " — register a materiality: block (currency, unit, threshold, "
                "priced_by, priced_on, basis, applies_to) or say only that a "
                "registered bar was cleared. Measurement resolution is never "
                "business value.",
            )
        )
    if problems.get("profile"):
        profile = contract.get("profile_doc") or contract.get("profile")
        checks.append(
            Check(
                "profile vocabulary",
                True,
                f"[WARN] findings.md uses words the {profile!r} profile bans: "
                + "; ".join(problems["profile"])
                + " — see the profile's §7 (the referee checks the same list)",
            )
        )
    return checks


def verify_study(
    study_dir: Path,
    *,
    require_local: bool = False,
    numbers: bool | None = None,
    claims: bool | None = None,
    evidence: bool | None = None,
    strict: bool = False,
    receipt: bool | None = None,
) -> list[Check]:
    """The audit ``klein verify`` prints; ``schema_version`` selects the rule set.

    Every keyword after ``require_local`` is TRI-STATE: ``None`` means "the
    default for this study's schema".  Schema 3 runs the numbers scan, the
    claim-sentence scan, the evidence-use checks and writes a receipt; schema 2
    runs none of them unless asked, and runs them advisory when it is — so
    studies 03 and 05–09 keep printing byte-identical output as long as no new
    flag is passed.  ``strict`` promotes every ``[WARN]`` this verb owns into a
    failure.
    """
    contract = load_contract(study_dir)
    if schema_version(contract) == 1:
        problems = _legacy_results_problems(study_dir / "results.tsv")
        return [
            Check(
                "legacy warning",
                True,
                "schema_version missing means v1; readable through the deprecated v1 adapter"
                " — no study evidence is rewritten",
            ),
            Check(
                "legacy errata",
                True,
                "v1 discard/crash rows may use `-` because exact candidate commits were not retained",
            ),
            Check(
                "legacy errata",
                True,
                "v1 has no machine-recorded gates, split fingerprint, track frontier, or sealed test count",
            ),
            Check(
                "legacy migration",
                True,
                "create a new v2 study; preserve this directory as immutable legacy evidence",
            ),
            Check("legacy ledger", not problems, "; ".join(problems) or "valid"),
        ]
    from .claims import claims_checks

    version = schema_version(contract)
    schema_3 = version >= 3
    state = _state_or_empty(study_dir, contract)
    want_numbers = schema_3 if numbers is None else numbers
    want_claims = schema_3 if claims is None else claims
    want_evidence = schema_3 if evidence is None else evidence
    want_receipt = schema_3 if receipt is None else receipt

    checks = preflight_checks(
        study_dir,
        require_clean=False,
        require_branch=False,
        require_local=require_local,
    )
    checks += _sweep_registry_checks(study_dir, state)
    checks += _vocabulary_checks(study_dir, contract)
    # Gate 3 and the predictions ledger close a schema-3 study; silent below it.
    checks += _referee_gate_checks(state, version)
    checks += _predictions_closure_checks(study_dir, contract, state, version)
    # The claims law (references/claims-protocol.md): enforcing on schema 3,
    # advisory on schema 2 so 07/08/09 never retro-fail. Empty without a lock.
    checks += claims_checks(study_dir, version, sentences=want_claims, strict=strict)
    checks += _evidence_use_checks(
        study_dir, contract, state, enabled=want_evidence, enforcing=schema_3, strict=strict
    )
    checks += _numbers_checks(study_dir, state, enabled=want_numbers, enforcing=schema_3)
    checks += _figure_rerender_checks(study_dir, enabled=schema_3)
    if want_receipt:
        checks += _receipt_checks(study_dir, contract, state, checks, version)
    return checks


def _state_or_empty(study_dir: Path, contract: Mapping[str, Any]) -> Mapping[str, Any]:
    """State for the read-only checks; a broken state file already failed above."""
    try:
        return load_state(study_dir, contract)
    except WorkflowError:
        return {}


# --------------------------------------------------------------------------
# Gate 3 and the predictions ledger, as verify sees them (Package B's helpers)
# --------------------------------------------------------------------------


def _referee_gate_checks(state: Mapping[str, Any], version: int) -> list[Check]:
    """Was the study reviewed by someone who did not run it?

    Silent below schema 3 — the referee gate does not exist there.  Before
    finalize an unrefereed study is a ``[WARN]``: REFEREE runs between SYNTHESIZE
    and finalize, and a study still in the loop has not reached it.  AFTER
    finalize it is a failure unless the closing receipt records the
    ``--no-referee`` reason, because then the study closed unreviewed and said
    nothing about it.
    """
    if version < 3:
        return []
    reviewed = referee_gate(state)
    if reviewed is not None:
        independence = "yes" if reviewed.get("independent_of_experimenter") else "no"
        return [
            Check(
                "referee gate",
                True,
                f"{reviewed.get('verdict')} — {reviewed.get('referee')}, "
                f"independent-of-experimenter: {independence}",
            )
        ]
    closed = state.get("finalization")
    if not isinstance(closed, Mapping):
        return [
            Check(
                "referee gate",
                True,
                "[WARN] not yet refereed — Gate 3 (`references/referee-protocol.md`) "
                "runs between SYNTHESIZE and finalize: a fresh context on a different "
                "model or tool writes referee_report.md, then `klein gate record referee`",
            )
        ]
    disclosed = closed.get("referee")
    reason = disclosed.get("reason") if isinstance(disclosed, Mapping) else None
    if isinstance(reason, str) and reason.strip():
        return [
            Check(
                "referee gate",
                True,
                f"[WARN] finalized unrefereed, disclosed on the receipt: {reason}",
            )
        ]
    return [
        Check(
            "referee gate",
            False,
            "the study is finalized with no referee gate and no recorded "
            "--no-referee reason — an unreviewed conclusion must say so on its own "
            "receipt (`klein gate record referee`, or re-finalize with "
            '--no-referee --reason "<why>")',
        )
    ]


def _predictions_closure_checks(
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    version: int,
) -> list[Check]:
    """Open predictions listed; every refuted one carries a recorded decision.

    The second half is D14's "refutation without revision": a belief the
    evidence contradicted, and a program that never says what changed.  It is
    computed once, in :func:`kleinlib.evidence_use.evidence_use`, and reported
    here rather than twice.
    """
    if version < 3:
        return []
    rows = prediction_ledger(contract, state)
    if not rows:
        return []
    from .evidence_use import evidence_use

    still_open = [row["id"] for row in rows if str(row.get("verdict")) == OPEN]
    checks = [
        Check(
            "predictions closure",
            True,
            f"[WARN] {len(still_open)} open: " + ", ".join(still_open)
            if still_open
            else f"{len(rows)} registered prediction(s), all adjudicated",
        )
    ]
    usage = evidence_use(study_dir, contract, state, load_manifests(study_dir))
    if usage.refuted:
        undecided = usage.undecided_refutations
        checks.append(
            Check(
                "belief revision",
                not undecided,
                "; ".join(
                    f"{name} is refuted and program.md records no dated `Decision:` "
                    "line naming it"
                    for name in undecided
                )
                + (
                    " — belief revision is a recorded act, not a feeling"
                    if undecided
                    else ""
                )
                or f"every refuted prediction ({', '.join(usage.refuted)}) has a dated "
                "`Decision:` line in program.md",
            )
        )
    return checks


# --------------------------------------------------------------------------
# D14 — evidence use
# --------------------------------------------------------------------------


def _evidence_use_checks(
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    enabled: bool,
    enforcing: bool,
    strict: bool,
) -> list[Check]:
    """``evidence_use_rate`` and convergent evidence; silent when not asked for."""
    if not enabled:
        return []
    from .evidence_use import evidence_use

    usage = evidence_use(study_dir, contract, state, load_manifests(study_dir))
    checks: list[Check] = []
    if usage.evidence:
        shortfall = bool(usage.uncited)
        checks.append(
            Check(
                "evidence use",
                not (shortfall and strict),
                (
                    f"[WARN] evidence_use_rate {usage.rate:.2f} "
                    f"({len(usage.cited)}/{len(usage.evidence)}): "
                    + ", ".join(usage.uncited[:8])
                    + (f", … {len(usage.uncited) - 8} more" if len(usage.uncited) > 8 else "")
                    + " cited in neither program.md nor findings.md — a discard, a "
                    "crash and a measured cell are all evidence; a study that never "
                    "mentions one again has filtered its own record"
                    if shortfall
                    else f"evidence_use_rate 1.00 — all {len(usage.evidence)} non-keep "
                    "run(s) and registered sweep(s) are cited"
                ),
            )
        )
    if usage.claim_kinds:
        single = usage.single_source_claims
        checks.append(
            Check(
                "convergent evidence",
                not (single and strict and enforcing),
                (
                    "[WARN] convergent evidence absent — "
                    + "; ".join(
                        f"{cid} is confirmed on "
                        + (
                            ", ".join(usage.claim_kinds[cid])
                            if usage.claim_kinds[cid]
                            else "no recognised evidence kind"
                        )
                        for cid in single
                    )
                    + " — a confirmed claim cites at least two of: a development run "
                    "(E####), a sealed final test, a replication (rep:), a "
                    "re-verification (verify:)"
                    if single
                    else f"{len(usage.claim_kinds)} confirmed claim(s) cite two or more "
                    "evidence kinds"
                ),
            )
        )
    if not enforcing:
        checks = [_advisory(check, "schema 2") for check in checks]
    return checks


def _advisory(check: Check, label: str) -> Check:
    """A failing check demoted to a warning — the schema-2 posture, everywhere."""
    if check.ok:
        return check
    return Check(check.name, True, f"[WARN] advisory on {label}: {check.message}")


# --------------------------------------------------------------------------
# The numbers law over whole documents (references/claims-protocol.md)
# --------------------------------------------------------------------------


def _numbers_checks(
    study_dir: Path,
    state: Mapping[str, Any],
    *,
    enabled: bool,
    enforcing: bool,
) -> list[Check]:
    """The findings scan (enforcing on schema 3) and the tutorial scan (always advisory).

    ``references/claims-protocol.md``: every numeral in findings.md is a copy of
    a value in a pinned artifact.  The tutorial pass reads ``report/index.html``
    text nodes only and NEVER fails — a rendered page carries layout numbers no
    index can know, and the law says so.
    """
    if not enabled:
        return []
    from .numbers import LiteralIndex, extract_literals, format_literals, html_text

    checks: list[Check] = []
    findings = study_dir / "findings.md"
    if findings.is_file():
        text = findings.read_text(encoding="utf-8", errors="replace")
        index = LiteralIndex.for_study(study_dir, state, exclude=[findings])
        literals = extract_literals(text)
        unsourced = [item for item in literals if not index.covers(item)]
        checks.append(
            Check(
                "findings numbers",
                not unsourced,
                f"{len(unsourced)} of {len(literals)} numerals have no home in "
                f"{len(index.sources)} pinned source(s) — "
                + format_literals(unsourced)
                + " — pin each with `klein claims number`, or mark the line "
                "`<!-- klein:numbers-ok: <reason> -->`"
                if unsourced
                else f"all {len(literals)} scanned numerals trace to "
                f"{len(index.sources)} pinned source(s)",
            )
        )
        if not enforcing:
            # An unsourced numeral is already a failure at any strictness; the
            # only lever schema 2 needs is the demotion.
            checks = [_advisory(check, "schema 2") for check in checks]

    tutorial = study_dir / "report" / "index.html"
    if tutorial.is_file():
        page = html_text(tutorial.read_text(encoding="utf-8", errors="replace"))
        index = LiteralIndex.for_study(study_dir, state)
        literals = extract_literals(page)
        unsourced = [item for item in literals if not index.covers(item)]
        checks.append(
            Check(
                "tutorial numbers",
                True,
                f"[WARN] {len(unsourced)} of {len(literals)} rendered numerals have no "
                "home — " + format_literals(unsourced) + " (advisory: the tutorial "
                "pass never fails a study; the referee reads the list)"
                if unsourced
                else f"all {len(literals)} rendered numerals trace to a pinned source",
            )
        )
    return checks


# --------------------------------------------------------------------------
# The figures re-render byte-identically (referee rubric item 9)
# --------------------------------------------------------------------------

#: How long one figure re-render may take before verify gives up on it.
FIGURE_RENDER_TIMEOUT = 300


def _figure_rerender_checks(study_dir: Path, *, enabled: bool) -> list[Check]:
    """Re-run ``figures/make_figures.py`` into a temp dir and compare the bytes.

    Silent unless the script exists.  It is only mechanically checkable when the
    script takes ``--out`` (study 09's shape); the older ones that write into
    their own ``figures/`` directory get a ``[WARN]`` naming why, because running
    them would overwrite the evidence they are supposed to reproduce.  A crash
    or a missing plotting dependency is a ``[WARN]`` too: a machine that cannot
    render is not a study that cannot reproduce.  Only a BYTE MISMATCH fails.
    """
    script = study_dir / "figures" / "make_figures.py"
    if not enabled or not script.is_file():
        return []
    source = script.read_text(encoding="utf-8", errors="replace")
    if "--out" not in source:
        return [
            Check(
                "figure re-render",
                True,
                "[WARN] figures/make_figures.py takes no --out, so re-rendering it "
                "would overwrite the figures it must reproduce — give it "
                "`--study <dir> --out <dir>` (study 09's shape) to make the check "
                "mechanical; the referee re-renders by hand until then",
            )
        ]
    with tempfile.TemporaryDirectory(prefix="klein-figures-") as temporary:
        out = Path(temporary)
        try:
            result = subprocess.run(  # noqa: S603 - a study's own committed script
                [
                    sys.executable,
                    str(script),
                    "--study",
                    str(study_dir),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=FIGURE_RENDER_TIMEOUT,
                check=False,
                cwd=str(repo_root_for(study_dir)) if _in_repo(study_dir) else str(study_dir),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [Check("figure re-render", True, f"[WARN] could not run it: {exc}")]
        if result.returncode != 0:
            tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["(no output)"]
            return [
                Check(
                    "figure re-render",
                    True,
                    f"[WARN] figures/make_figures.py exited {result.returncode}: {tail[0]}",
                )
            ]
        return [_compare_figures(study_dir, out)]


def _in_repo(study_dir: Path) -> bool:
    try:
        repo_root_for(study_dir)
    except WorkflowError:
        return False
    return True


def _compare_figures(study_dir: Path, rendered: Path) -> Check:
    """Byte-compare each re-rendered figure against the committed one."""
    produced = sorted(path for path in rendered.rglob("*") if path.is_file())
    if not produced:
        return Check("figure re-render", True, "[WARN] the script produced no files")
    committed = study_dir / "figures"
    differ: list[str] = []
    missing: list[str] = []
    for path in produced:
        name = path.relative_to(rendered).as_posix()
        target = committed / name
        if not target.is_file():
            missing.append(name)
        elif sha256_file(target) != sha256_file(path):
            differ.append(name)
    if differ:
        return Check(
            "figure re-render",
            False,
            "figures/make_figures.py does not re-render byte-identically: "
            + ", ".join(differ)
            + " — a figure whose bytes move with the machine is a figure whose "
            "numbers cannot be re-checked (tutorial-spec.md; referee rubric 9)",
        )
    if missing:
        return Check(
            "figure re-render",
            True,
            "[WARN] re-rendered but never committed: " + ", ".join(missing),
        )
    return Check(
        "figure re-render",
        True,
        f"{len(produced)} figure(s) re-render byte-identically",
    )


# --------------------------------------------------------------------------
# The receipt
# --------------------------------------------------------------------------

#: The file `klein verify` writes and commits on a schema-3 study.
RECEIPT_NAME = "verify_receipt.json"

#: Study files whose bytes the receipt records, so a later reader knows exactly
#: which inputs the audit saw.
RECEIPT_INPUTS: tuple[str, ...] = (
    "study.yaml",
    "study_state.json",
    "events.jsonl",
    "results.tsv",
    "aux_metrics.tsv",
    "findings.md",
    "program.md",
    "playbook.md",
    "claims.lock",
    "referee_report.md",
    "report/index.html",
)


def verify_receipt(
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    checks: Sequence[Check],
    version: int,
) -> dict[str, Any]:
    """The receipt payload — pure, so a test can build one without writing it.

    ``checks`` are the findings of the audit; the ``verify receipt`` line itself
    is bookkeeping added afterwards and is the one line the receipt cannot
    carry, so ``summary.checks`` is one less than the number verify prints.
    """
    from . import __version__
    from .evidence_use import evidence_use

    failed = [check for check in checks if not check.ok]
    warned = [check for check in checks if check.ok and "[WARN]" in check.message]
    usage = evidence_use(study_dir, contract, state, load_manifests(study_dir))
    return {
        "klein_version": __version__,
        "klein_commit": _engine_commit(),
        "git_head": _study_head(study_dir),
        "timestamp": utc_now(),
        "schema": version,
        "study": state.get("study_id", study_dir.name),
        "checks": [
            {"name": check.name, "ok": check.ok, "message": check.message}
            for check in checks
        ],
        "summary": {
            "checks": len(checks),
            "failed": len(failed),
            "warned": len(warned),
        },
        "evidence_use_rate": round(usage.rate, 6),
        "uncited_evidence": list(usage.uncited),
        "undecided_refutations": list(usage.undecided_refutations),
        "single_source_claims": list(usage.single_source_claims),
        "inputs": _hashes(study_dir, RECEIPT_INPUTS),
        "manifests": {
            path.parent.name: sha256_file(path) for path in _manifest_paths(study_dir)
        },
    }


def _hashes(study_dir: Path, names: Sequence[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in names:
        path = study_dir / name
        if path.is_file():
            found[name] = sha256_file(path)
    return found


def _engine_commit() -> str | None:
    """HEAD of the repository kleinlib itself is running from, when there is one."""
    try:
        repo = repo_root_for(Path(__file__).resolve().parent)
    except WorkflowError:
        return None
    result = git(repo, ["rev-parse", "HEAD"], check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def _study_head(study_dir: Path) -> str | None:
    try:
        repo = repo_root_for(study_dir)
    except WorkflowError:
        return None
    result = git(repo, ["rev-parse", "HEAD"], check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def write_verify_receipt(
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    checks: Sequence[Check],
    version: int,
) -> Path:
    """Write ``verify_receipt.json`` and file exactly that.

    ``scope="own"`` keeps the commit to the receipt (plus state and events when
    verify touched them).  An in-progress edit to findings, the playbook, a
    figure or a sweep sidecar is the operator's, and stays theirs — filing it
    under a ``klein: verify receipt`` subject would describe a tree nobody
    deliberately committed.  The verb names what it left behind on stdout.
    """
    path = study_dir / RECEIPT_NAME
    atomic_write_json(path, verify_receipt(study_dir, contract, state, checks, version))
    failed = len([check for check in checks if not check.ok])
    commit_state_writes(
        study_dir,
        f"klein: verify receipt ({len(checks)} checks, {failed} failed)",
        paths=[RECEIPT_NAME],
        scope="own",
    )
    return path


def _receipt_checks(
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    checks: Sequence[Check],
    version: int,
) -> list[Check]:
    """Write the receipt and report where it landed; never fails the study."""
    try:
        path = write_verify_receipt(study_dir, contract, state, checks, version)
    except (OSError, WorkflowError) as exc:
        return [Check("verify receipt", True, f"[WARN] not written: {exc}")]
    return [Check("verify receipt", True, f"written to {path.name}")]
