"""Every read-only audit Klein reports: ``klein preflight`` and ``klein verify``.

Extracted verbatim from :mod:`kleinlib.workflow`.  A :class:`Check` is a named,
pass/fail, human-readable line; ``preflight_checks`` produces the whole report
and ``verify_study`` is that same report with the working-tree and branch
requirements relaxed (a finalized study must keep verifying).  Nothing here
mutates a study — every problem is returned, never raised.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import (
    GATE_ARTIFACTS,
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
from .primitives import fingerprint_path, sha256_bytes, sha256_file
from .schema import AUTO_PRINTED_METRIC_KEYS, EVALUATOR_PRINTED_KEYS
from .state import (
    load_state,
    registered_partition_fingerprints,
    split_policy_hash,
    verifier_script_hashes,
)
from .transaction import current_branch, git, git_blob, relative, repo_root_for

__all__ = ["ABSENT_LOCAL_ARTIFACT", "Check", "preflight_checks", "verify_study"]

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
    checks.append(Check("study contract", not contract_problems, "; ".join(contract_problems) or "schema_version 2 contract valid"))
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
                    "k-seed measurement (see consult-protocol.md)",
                )
            )
            continue
        try:
            floor_std = float(floor.get("std"))
            minimum_delta = float(metric.get("minimum_delta", 0))
        except (TypeError, ValueError):
            continue  # validate_contract already reported the malformed block
        checks.append(
            Check(
                "noise floor",
                minimum_delta >= floor_std,
                f"track {track_name!r}: minimum_delta {minimum_delta:.6g} vs measured "
                f"seed std {floor_std:.6g}"
                + (
                    ""
                    if minimum_delta >= floor_std
                    else " — declaring a floor then keeping inside it is the exact "
                    "dishonesty the measurement exists to prevent"
                ),
            )
        )
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
    for gate in GATE_ARTIFACTS:
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
            sources[str(path.relative_to(study_dir))] = path.read_text(
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



def verify_study(study_dir: Path, *, require_local: bool = False) -> list[Check]:
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

    checks = preflight_checks(
        study_dir,
        require_clean=False,
        require_branch=False,
        require_local=require_local,
    )
    checks += _sweep_registry_checks(study_dir, _state_or_empty(study_dir, contract))
    # The claims law (references/claims-protocol.md): enforcing on schema 3,
    # advisory on schema 2 so 07/08/09 never retro-fail. Empty without a lock.
    return checks + claims_checks(study_dir, schema_version(contract))


def _state_or_empty(study_dir: Path, contract: Mapping[str, Any]) -> Mapping[str, Any]:
    """State for the read-only checks; a broken state file already failed above."""
    try:
        return load_state(study_dir, contract)
    except WorkflowError:
        return {}
