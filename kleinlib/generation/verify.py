"""``klein generation verify`` — the extension's own audit and its own receipt.

Deliberately a SEPARATE verb writing a SEPARATE receipt.  Appending these checks
to ``kleinlib/checks.py`` would change ``summary.checks`` for every opted-in
study and put the core receipt's byte-reproducibility at the mercy of this
package; instead ``verify_receipt.json`` stays exactly what it was and
``generation/verify_receipt.json`` stands beside it.  A core ``klein verify``
never mentions the word "generation".

Eight check families, each PASS / WARN / FAIL:

``generation manifest``
    The opt-in is present, unaltered since the ``generation_opted_in`` event,
    and ANCHORED BEFORE the first CONSULT gate record — by core sequence and by
    git ancestry.  A late opt-in fails here, permanently: you cannot register a
    commitment after seeing what it was supposed to constrain.
``generation chain`` / ``generation anchors``
    The extension's own hash chain, and the core anchors it claims.
``generation orphans``
    Objects with no event and events with no object.  A voided orphan is a WARN
    that names the ``recovered`` event that voided it.
``generation admission``
    One line per in-scope run with its classification.  Anything but
    ``admitted`` is a FAIL.
``generation replay``
    A receipt matched by more than one run.
``generation findings label``
    Once a label exists, ``findings.md`` must quote it — the same discipline
    ``finalize`` applies to its own label.
``generation commits``
    The ledger is committed.  An uncommitted event is a receipt nobody can
    resolve by ancestry.

The receipt carries no timestamp: at one HEAD it is a pure function of the
study, and :func:`write_receipt` will not rewrite a receipt that differs from
the one on disk only in ``git_head`` — so a second ``verify`` files no commit
and the bytes are stable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..primitives import atomic_write_json, canonical_json
from ..transaction import git
from . import admission as _admission
from . import manifest as _manifest
from .chronology import (
    changed_paths_between,
    core_anchor_problem,
    gate_events,
    git_head,
    introducing_commit,
    is_ancestor,
    read_core_events,
    repo_for,
    study_event_commit,
)
from .envelope import GENERATION_SCHEMA
from .ledger import (
    chain_problems,
    commit_generation,
    missing_object_shas,
    orphan_object_shas,
    read_events,
    voided_object_shas,
)

__all__ = [
    "RECEIPT_NAME",
    "Check",
    "build_receipt",
    "generation_checks",
    "receipt_is_current",
    "write_receipt",
]

RECEIPT_NAME = "generation/verify_receipt.json"

#: Commits that may lie between a receipt's ``git_head`` and HEAD without making
#: it stale: the two audits' own receipts, and nothing else.  A commit that
#: touched findings, a manifest, the ledger or the surface invalidates it.
RECEIPT_ONLY_PATHS: tuple[str, ...] = ("verify_receipt.json", "generation/verify_receipt.json")


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


# --------------------------------------------------------------------------
# the families
# --------------------------------------------------------------------------


def _manifest_checks(
    study_dir: Path,
    contract: Mapping[str, Any],
    repo: Path | None,
    events: Sequence[Mapping[str, Any]],
    core: Sequence[Mapping[str, Any]],
) -> tuple[list[Check], dict[str, Any]]:
    name = "generation manifest"
    scope: dict[str, Any] = {
        "opt_in_anchor": {"sequence": 0, "event_hash": None},
        "capabilities": [],
        "late_added": [],
    }
    try:
        manifest = _manifest.load_manifest(study_dir)
    except WorkflowError as exc:
        return [_fail(name, str(exc))], scope
    checks: list[Check] = []
    problems: list[str] = []
    if manifest.get("generation_schema") != _manifest.GENERATION_SCHEMA_VERSION:
        problems.append(f"generation_schema is {manifest.get('generation_schema')!r}")
    declared = manifest.get("study_id")
    expected = _manifest.study_id(study_dir, contract)
    if declared != expected:
        problems.append(f"study_id is {declared!r}, expected {expected!r}")
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list):
        problems.append("capabilities must be a list")
        capabilities = []
    else:
        problems.extend(_manifest.capability_problems([str(c) for c in capabilities]))
    scope["capabilities"] = [str(c) for c in capabilities]

    opt_in = next((e for e in events if e.get("type") == "generation_opted_in"), None)
    if opt_in is None:
        problems.append("no generation_opted_in event")
    else:
        anchor = opt_in.get("core_anchor")
        if isinstance(anchor, Mapping):
            scope["opt_in_anchor"] = dict(anchor)
        recorded = opt_in.get("manifest_sha256")
        actual = _manifest.manifest_sha256(study_dir)
        if recorded != actual:
            problems.append(
                f"manifest.yaml sha256 {actual[:12]}… does not match the "
                f"generation_opted_in event ({str(recorded)[:12]}…) — the opt-in is immutable"
            )
        if opt_in.get("late_opt_in"):
            problems.append(
                "opt-in was recorded with --allow-late, after the CONSULT gate: the "
                "scope freeze cannot be established"
            )
        problems.extend(_opt_in_order_problems(study_dir, repo, core, opt_in))

    if problems:
        checks.append(_fail(name, "; ".join(problems)))
    else:
        checks.append(
            _pass(
                name,
                f"opt-in anchored at core sequence {scope['opt_in_anchor'].get('sequence')} "
                f"before the consult gate; {len(scope['capabilities'])} capabilit"
                f"{'y' if len(scope['capabilities']) == 1 else 'ies'} declared",
            )
        )

    recorded_hashes = manifest.get("protocol_hashes")
    current = _manifest.protocol_hashes(repo)
    if isinstance(recorded_hashes, Mapping) and dict(recorded_hashes) != current:
        checks.append(
            _warn(
                "generation manifest",
                "protocol hashes have drifted since opt-in ("
                + ", ".join(sorted(set(recorded_hashes) | set(current)))
                + ") — the receipts were taken under different rules than are on disk now",
            )
        )
    return checks, scope


def _opt_in_order_problems(
    study_dir: Path,
    repo: Path | None,
    core: Sequence[Mapping[str, Any]],
    opt_in: Mapping[str, Any],
) -> list[str]:
    """The opt-in must precede the first consult gate record, by BOTH witnesses."""
    consult = gate_events(core, "consult")
    if not consult:
        return []
    first = consult[0]
    anchor = opt_in.get("core_anchor")
    anchor_sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    gate_sequence = first.get("sequence")
    problems: list[str] = []
    if not isinstance(anchor_sequence, int) or not isinstance(gate_sequence, int):
        return ["the opt-in anchor or the consult gate record has no sequence"]
    if anchor_sequence >= gate_sequence:
        problems.append(
            f"opt-in anchored at core sequence {anchor_sequence}, at or after the "
            f"consult gate record (sequence {gate_sequence})"
        )
    if repo is not None:
        opt_in_commit = introducing_commit(
            repo, _relpath(repo, study_dir, "generation/manifest.yaml")
        )
        gate_hash = first.get("event_hash")
        gate_commit = (
            study_event_commit(repo, study_dir, str(gate_hash))
            if isinstance(gate_hash, str)
            else None
        )
        if opt_in_commit is None:
            problems.append("generation/manifest.yaml is not committed, so ancestry cannot be read")
        elif gate_commit is None:
            problems.append("the consult gate record is not committed, so ancestry cannot be read")
        elif not is_ancestor(repo, opt_in_commit, gate_commit):
            problems.append(
                f"the opt-in commit {opt_in_commit[:12]} is not an ancestor of the "
                f"consult gate commit {gate_commit[:12]}"
            )
    return problems


def _relpath(repo: Path, study_dir: Path, name: str) -> str:
    from ..transaction import relative

    return relative(repo, study_dir / name)


def _chain_checks(events: Sequence[Mapping[str, Any]]) -> list[Check]:
    problems = chain_problems(events)
    if problems:
        return [_fail("generation chain", "; ".join(problems[:8]))]
    return [_pass("generation chain", f"{len(events)} events, hashes and links intact")]


def _anchor_checks(
    events: Sequence[Mapping[str, Any]], core: Sequence[Mapping[str, Any]]
) -> list[Check]:
    problems: list[str] = []
    previous = -1
    for event in events:
        anchor = event.get("core_anchor")
        problem = core_anchor_problem(core, anchor)
        if problem:
            problems.append(f"{event.get('id')}: {problem}")
            continue
        sequence = int(anchor.get("sequence") or 0)  # type: ignore[union-attr]
        if sequence < previous:
            problems.append(
                f"{event.get('id')}: core anchor {sequence} goes backwards from {previous}"
            )
        previous = max(previous, sequence)
    if problems:
        return [_fail("generation anchors", "; ".join(problems[:8]))]
    return [
        _pass(
            "generation anchors",
            f"every anchor resolves against the core chain ({len(core)} core events); "
            "anchors are non-decreasing",
        )
    ]


def _orphan_checks(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[Check]:
    checks: list[Check] = []
    orphans = orphan_object_shas(study_dir, events)
    missing = missing_object_shas(study_dir, events)
    voided = voided_object_shas(events)
    if orphans:
        checks.append(
            _fail(
                "generation orphans",
                "objects with no event: "
                + ", ".join(sha[:12] for sha in orphans)
                + " — run `klein generation recover` to void them",
            )
        )
    if missing:
        checks.append(
            _fail(
                "generation orphans",
                "events whose object is missing: " + ", ".join(sha[:12] for sha in missing),
            )
        )
    if voided:
        checks.append(
            _warn(
                "generation orphans",
                "voided objects retained on disk: "
                + ", ".join(f"{sha[:12]} (by {event})" for sha, event in sorted(voided.items())),
            )
        )
    if not orphans and not missing:
        checks.append(
            _pass("generation orphans", "every object has an event and every event its object")
        )
    return checks


def _admission_checks(match: _admission.Match, receipt_count: int) -> list[Check]:
    name = "generation admission"
    checks: list[Check] = []
    if not match.in_scope:
        return [_pass(name, "no run in scope yet")]
    if receipt_count == 0:
        checks.append(
            _fail(
                name,
                f"{len(match.in_scope)} run(s) in scope and no admission receipt was ever "
                "recorded — `klein generation check` runs before `klein run-one`",
            )
        )
    for run in match.in_scope:
        classification = match.runs.get(run, "unadmitted")
        detail = f"{run}: {classification}"
        checks.append(_pass(name, detail) if classification == "admitted" else _fail(name, detail))
    return checks


def _replay_checks(match: _admission.Match) -> list[Check]:
    name = "generation replay"
    replayed = [run for run, value in match.runs.items() if value == "replayed"]
    counts: dict[str, list[str]] = {}
    for sha, entry in match.receipts.items():
        if entry.get("consumed_by"):
            counts.setdefault(sha, []).append(str(entry["consumed_by"]))
    doubled = [sha for sha, runs in counts.items() if len(runs) > 1]
    problems: list[str] = []
    if replayed:
        problems.append("runs re-using a spent receipt: " + ", ".join(sorted(replayed)))
    if doubled:
        problems.append("receipts matched twice: " + ", ".join(sha[:12] for sha in sorted(doubled)))
    if problems:
        return [_fail(name, "; ".join(problems))]
    return [_pass(name, "every receipt was consumed by at most one run")]


def _label_checks(study_dir: Path) -> list[Check]:
    name = "generation findings label"
    path = study_dir / "generation" / "label.json"
    if not path.is_file():
        return [_pass(name, "no label issued")]
    try:
        label = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [_fail(name, f"generation/label.json is unreadable: {exc}")]
    from .label import findings_line

    line = findings_line(label)
    findings = study_dir / "findings.md"
    if not findings.is_file():
        return [_fail(name, f"findings.md is missing and must carry `{line}`")]
    if line not in findings.read_text(encoding="utf-8"):
        return [_fail(name, f"findings.md must carry the label line `{line}`")]
    return [_pass(name, f"findings.md quotes `{line}`")]


def _commit_checks(study_dir: Path, repo: Path | None) -> list[Check]:
    name = "generation commits"
    if repo is None:
        return [_warn(name, "not a git repository; ancestry and commit state cannot be read")]
    relpath = _relpath(repo, study_dir, "generation")
    result = git(
        repo, ["status", "--porcelain", "--untracked-files=all", "--", relpath], check=False
    )
    if result.returncode:
        return [_warn(name, "git status failed; commit state cannot be read")]
    dirty = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        return [
            _fail(
                name,
                "uncommitted generation writes: "
                + ", ".join(dirty[:8])
                + " — run `klein generation recover`",
            )
        ]
    return [_pass(name, "every generation/** path is tracked and unmodified")]


# --------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------


def generation_checks(
    study_dir: Path, contract: Mapping[str, Any]
) -> tuple[list[Check], dict[str, Any]]:
    """Run every family.  Never raises on a broken study — breakage is a FAIL."""
    repo = repo_for(study_dir)
    try:
        events = read_events(study_dir)
    except WorkflowError as exc:
        return (
            [
                _fail("generation chain", str(exc)),
                _fail("generation manifest", "the extension chain is unreadable"),
            ],
            {"scope": {"opt_in_anchor": {"sequence": 0, "event_hash": None}, "capabilities": [], "late_added": []},
             "runs": {}, "receipts": {}},
        )
    try:
        core = read_core_events(study_dir)
    except WorkflowError as exc:
        core = []
        core_problem: Check | None = _fail("generation anchors", f"core events.jsonl: {exc}")
    else:
        core_problem = None

    checks: list[Check] = []
    manifest_checks, scope = _manifest_checks(study_dir, contract, repo, events, core)
    checks += manifest_checks
    checks += _chain_checks(events)
    checks += [core_problem] if core_problem else _anchor_checks(events, core)
    checks += _orphan_checks(study_dir, events)

    try:
        match = _admission.match_runs(study_dir, contract, repo=repo, events=events)
    except WorkflowError as exc:
        match = _admission.Match({}, {}, dict(scope["opt_in_anchor"]), [], {})
        checks.append(_fail("generation admission", f"run manifests unreadable: {exc}"))
    else:
        checks += _admission_checks(match, len(_admission.load_receipts(study_dir, events)))
        checks += _replay_checks(match)
    checks += _label_checks(study_dir)
    checks += _commit_checks(study_dir, repo)
    extras = {"scope": scope, "runs": dict(match.runs), "receipts": dict(match.receipts)}
    return checks, extras


def build_receipt(
    study_dir: Path,
    contract: Mapping[str, Any],
    checks: Sequence[Check],
    extras: Mapping[str, Any],
    *,
    head: str | None,
) -> dict[str, Any]:
    """The receipt payload — pure, and free of any clock."""
    from .. import __version__

    failed = [check for check in checks if check.status == "FAIL"]
    warned = [check for check in checks if check.status == "WARN"]
    try:
        manifest_sha: str | None = _manifest.manifest_sha256(study_dir)
    except OSError:
        manifest_sha = None
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "verify_receipt",
        "study": _manifest.study_id(study_dir, contract),
        "git_head": head,
        "klein_version": __version__,
        "manifest_sha256": manifest_sha,
        "scope": extras.get("scope"),
        "checks": [
            {"name": check.name, "status": check.status, "detail": check.detail}
            for check in checks
        ],
        "summary": {"checks": len(checks), "failed": len(failed), "warned": len(warned)},
        "runs": extras.get("runs", {}),
        "receipts": extras.get("receipts", {}),
        "capabilities": {},
    }


def receipt_is_current(repo: Path | None, receipt: Mapping[str, Any], head: str | None) -> bool:
    """Is this audit still the current one?

    True when the receipt's ``git_head`` IS ``HEAD``, or when every commit since
    it touched only the two audits' own receipt files.  Writing a receipt moves
    HEAD, so a stricter equality would refuse the label the instant it was
    earned; a looser one would let a study change under a stale audit.
    """
    recorded = receipt.get("git_head")
    if not isinstance(recorded, str) or head is None:
        return False
    if recorded == head:
        return True
    if repo is None or not is_ancestor(repo, recorded, head):
        return False
    changed = changed_paths_between(repo, recorded, head)
    return all(
        any(path.endswith(allowed) for allowed in RECEIPT_ONLY_PATHS) for path in changed
    )


def write_receipt(study_dir: Path, contract: Mapping[str, Any]) -> tuple[list[Check], Path]:
    """Audit, write ``generation/verify_receipt.json``, commit exactly that.

    A payload that differs from the receipt already on disk ONLY in ``git_head``
    is not written: the audit found nothing new, so the receipt that is there
    stands and no commit is filed.  That is what makes two consecutive verifies
    byte-identical instead of an endless chain of receipt commits.
    """
    checks, extras = generation_checks(study_dir, contract)
    repo = repo_for(study_dir)
    payload = build_receipt(study_dir, contract, checks, extras, head=git_head(repo))
    path = study_dir / RECEIPT_NAME
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and _same_but_head(existing, payload):
            return checks, path
    atomic_write_json(path, payload)
    failed = payload["summary"]["failed"]
    commit_generation(
        study_dir,
        f"klein: generation verify receipt ({payload['summary']['checks']} checks, {failed} failed)",
        paths=(RECEIPT_NAME,),
    )
    return checks, path


def _same_but_head(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    def strip(value: Mapping[str, Any]) -> str:
        return canonical_json({key: item for key, item in value.items() if key != "git_head"})

    return strip(left) == strip(right)
