"""Admission receipts, and the matcher that binds them to runs afterwards.

``klein generation check`` writes ONE receipt before ONE action.  The receipt
binds what the driver is about to do (``intended_action``), the exact bytes the
action will run (``surface_digest`` over ``entrypoint.mutable``), the inputs and
protocol rules it was taken under, the core-chain anchor, and a verdict.  Then
``run-one`` runs — unchanged, unaware, and un-hooked: the notary is not extended,
it is WITNESSED.  ``klein generation verify`` reconstructs the pairing afterwards
by arithmetic over the two chains, the manifests, and git ancestry.

**A refusal is evidence.**  A refused check is written, hashed and committed
exactly like an admitted one, and the verb exits 2.  That is how "the driver was
told no and ran anyway" becomes a detectable, recorded fact
(``refused-but-run``) instead of an absence.

**Supersession, not refusal.**  Asking for a second admission on a track whose
previous admission was never consumed is lawful: the new receipt names the old
one in ``parent_ids`` and ``supersedes``, and the old one is never matched to a
run again.  (Refusing instead would strand a track whose ``run-one`` aborted
before it wrote a manifest.)  Only an ADMITTED receipt supersedes: a refusal
neither grants nor revokes.

Nothing in this module proposes, ranks, selects, schedules or retries anything.
``ADMISSION_RULES`` is a list of plain predicates over a :class:`Context`; each
returns the reasons it objects to the intended action.  A later work package
adds none of its rules here: it REGISTERS a
:class:`~kleinlib.generation.registry.Capability`, and
:func:`capability_reasons` runs the rules of every capability the study's
manifest declared, after the spine's own.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contract import mutable_surface
from ..manifest import load_manifests
from ..primitives import canonical_json, sha256_bytes
from ..transaction import git_blob, relative
from .chronology import (
    core_tip,
    introducing_commit,
    is_ancestor,
    read_core_events,
    run_started_events,
)
from .envelope import GENERATION_SCHEMA
from .ledger import read_events, read_object

__all__ = [
    "ADMISSION_RULES",
    "CHECKPOINTS",
    "CLASSIFICATIONS",
    "Context",
    "Match",
    "Receipt",
    "build_receipt",
    "capability_reasons",
    "core_anchor",
    "declared_capabilities",
    "load_receipts",
    "match_runs",
    "outstanding_receipt",
    "superseded_shas",
    "surface_digest",
    "surface_digest_at",
]

#: What an admission can be taken FOR.  ``run`` is an ordinary development
#: transaction; ``sealed`` spends a track's one look at its confirmation
#: evidence; ``baseline``, ``repair``, ``calibration`` and ``cell`` are the
#: typed obligations the capability packages add — every one of them passes
#: through ordinary ``run-one``, and there is no off-notary path.
CHECKPOINTS: tuple[str, ...] = ("run", "sealed", "baseline", "repair", "calibration", "cell")

#: How a run is classified against the receipts.  ``admitted`` is the only
#: passing value; everything else is a FAIL in ``generation admission``.
CLASSIFICATIONS: tuple[str, ...] = (
    "admitted",
    "unadmitted",
    "refused-but-run",
    "replayed",
    "mismatched",
)


# --------------------------------------------------------------------------
# the surface digest
# --------------------------------------------------------------------------


def _digest(entries: Sequence[Sequence[Any]]) -> str:
    return sha256_bytes(canonical_json([list(entry) for entry in entries]).encode())


def surface_digest(study_dir: Path, contract: Mapping[str, Any]) -> tuple[str, list[list[Any]]]:
    """The mutable surface AS ON DISK: ``(digest, [[path, sha256|null], …])``.

    Sorted by path; a declared file that does not exist hashes as null, so
    "the file was deleted" and "the file was empty" are different digests.
    """
    entries: list[list[Any]] = []
    for name in sorted(mutable_surface(contract)):
        path = study_dir / name
        entries.append([name, sha256_bytes(path.read_bytes()) if path.is_file() else None])
    return _digest(entries), entries


def surface_digest_at(
    repo: Path, study_dir: Path, contract: Mapping[str, Any], commit: str
) -> tuple[str, list[list[Any]]]:
    """The same digest, read out of a commit rather than the working tree."""
    entries: list[list[Any]] = []
    for name in sorted(mutable_surface(contract)):
        blob = git_blob(repo, commit, relative(repo, study_dir / name))
        entries.append([name, sha256_bytes(blob) if blob is not None else None])
    return _digest(entries), entries


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------


@dataclass
class Context:
    """Everything an admission rule may look at.  Read-only by convention."""

    study_dir: Path
    repo: Path | None
    contract: Mapping[str, Any]
    state: Mapping[str, Any]
    manifest: Mapping[str, Any]
    action: str
    track: str
    tests: tuple[str, ...] = ()
    hypothesis: str | None = None
    cell: str | None = None
    obligation: str | None = None
    outstanding: Receipt | None = None
    tracks: Mapping[str, Any] = field(default_factory=dict)


def _rule_known_checkpoint(ctx: Context) -> list[str]:
    if ctx.action not in CHECKPOINTS:
        return [f"unknown checkpoint {ctx.action!r}; expected one of {', '.join(CHECKPOINTS)}"]
    return []


def _rule_track_is_declared(ctx: Context) -> list[str]:
    if ctx.track not in ctx.tracks:
        declared = ", ".join(sorted(ctx.tracks)) or "none"
        return [f"track {ctx.track!r} is not declared in study.yaml (declared: {declared})"]
    return []


def declared_capabilities(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """The capability names ``generation/manifest.yaml`` declared, in order."""
    value = manifest.get("capabilities")
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value)


def _needs_capability(ctx: Context, requested: str | None, what: str, capability: str) -> list[str]:
    """The spine's half of a typed request: is the capability DECLARED at all?

    When it is, the spine steps aside and the capability's own registered rules
    decide (see :mod:`kleinlib.generation.registry`); when it is not, the
    request is refused here and the fix is a manifest, not a flag.
    """
    if not requested or capability in declared_capabilities(ctx.manifest):
        return []
    return [
        f"{what} admission requires the {capability} capability; declare it in "
        "generation/manifest.yaml"
    ]


def _rule_hypothesis_needs_slates(ctx: Context) -> list[str]:
    return _needs_capability(ctx, ctx.hypothesis, "hypothesis", "slates")


def _rule_cell_needs_surprise(ctx: Context) -> list[str]:
    return _needs_capability(ctx, ctx.cell, "cell", "surprise")


def _rule_obligation_needs_expertise(ctx: Context) -> list[str]:
    return _needs_capability(ctx, ctx.obligation, "obligation", "expertise")


def _rule_seal_is_unspent(ctx: Context) -> list[str]:
    """A track gets ONE look at its sealed evidence; admitting a second is a lie.

    Read-only from ``study_state.json``'s ``final_holdout_access``; the core
    still owns the seal and refuses the second run itself.
    """
    if ctx.action != "sealed":
        return []
    access = ctx.state.get("final_holdout_access")
    if not isinstance(access, Mapping):
        return []
    spent = access.get(ctx.track)
    count = spent.get("count") if isinstance(spent, Mapping) else None
    if isinstance(count, int) and count >= 1:
        return [f"track {ctx.track!r} has already spent its sealed final test"]
    return []


#: The spine's rules, run for every study.  A capability's own rules are NOT
#: appended here — they are registered (see :func:`capability_reasons`).
ADMISSION_RULES: list[Callable[[Context], list[str]]] = [
    _rule_known_checkpoint,
    _rule_track_is_declared,
    _rule_hypothesis_needs_slates,
    _rule_cell_needs_surprise,
    _rule_obligation_needs_expertise,
    _rule_seal_is_unspent,
]


def capability_reasons(ctx: Context) -> list[str]:
    """The registered rules of every capability the manifest DECLARED.

    The loader is imported here rather than at module scope: ``registry`` types
    against this module, so a top-level import would cycle.  A declared
    capability this version cannot load is refused rather than skipped — ``init``
    already refuses to declare an unsupported name, so reaching this branch means
    the manifest was hand-edited or the study was carried to an older Klein.
    """
    declared = declared_capabilities(ctx.manifest)
    if not declared:
        return []
    from .capabilities import load

    available = load()
    reasons: list[str] = []
    for name in declared:
        capability = available.get(name)
        if capability is None:
            reasons.append(f"capability {name!r} declared but not supported by this version")
            continue
        for rule in capability.admission_rules:
            reasons.extend(rule(ctx))
    return reasons


def build_receipt(
    ctx: Context,
    *,
    study: str,
    manifest_sha: str,
    protocol_hashes: Mapping[str, str | None],
    core_anchor: Mapping[str, Any],
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Evaluate every rule and return the receipt object, admitted or refused."""
    digest, entries = surface_digest(ctx.study_dir, ctx.contract)
    reasons: list[str] = []
    for rule in ADMISSION_RULES:
        reasons.extend(rule(ctx))
    reasons.extend(capability_reasons(ctx))
    receipt: dict[str, Any] = {
        "schema": GENERATION_SCHEMA,
        "kind": "admission",
        "study": study,
        "checkpoint": ctx.action,
        "track": ctx.track,
        "intended_action": {
            "kind": ctx.action,
            "hypothesis_id": ctx.hypothesis,
            "cell_id": ctx.cell,
            "obligation_id": ctx.obligation,
            "tests": list(ctx.tests),
        },
        "surface_digest": digest,
        "surface_files": entries,
        "inputs": {
            "manifest": manifest_sha,
            "slate": None,
            "premortem": None,
            "parity": None,
            "cells": None,
            "design": None,
        },
        "protocol_hashes": dict(protocol_hashes),
        "core_anchor": dict(core_anchor),
        "verdict": "refused" if reasons else "admitted",
        "reasons": reasons,
    }
    if supersedes is not None:
        receipt["supersedes"] = supersedes
    return receipt


# --------------------------------------------------------------------------
# the receipts table
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Receipt:
    """One ``admission_checked`` event joined to its object."""

    sha: str
    event_id: str
    sequence: int
    core_sequence: int
    track: str | None
    checkpoint: str | None
    verdict: str
    surface_digest: str | None
    supersedes: str | None


def load_receipts(study_dir: Path, events: Sequence[Mapping[str, Any]]) -> list[Receipt]:
    """Every admission receipt in extension order; unreadable objects are skipped."""
    from ..errors import WorkflowError

    receipts: list[Receipt] = []
    for event in events:
        if event.get("type") != "admission_checked":
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            obj = read_object(study_dir, sha)
        except WorkflowError:
            continue
        anchor = event.get("core_anchor")
        core_sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
        receipts.append(
            Receipt(
                sha=sha,
                event_id=str(event.get("id")),
                sequence=int(event.get("sequence") or 0),
                core_sequence=int(core_sequence or 0),
                track=obj.get("track"),
                checkpoint=obj.get("checkpoint"),
                verdict=str(obj.get("verdict")),
                surface_digest=obj.get("surface_digest"),
                supersedes=obj.get("supersedes"),
            )
        )
    return receipts


def superseded_shas(receipts: Sequence[Receipt]) -> set[str]:
    return {r.supersedes for r in receipts if isinstance(r.supersedes, str)}


# --------------------------------------------------------------------------
# the matcher
# --------------------------------------------------------------------------


@dataclass
class Match:
    """What ``verify`` and ``status`` both report."""

    runs: dict[str, str]
    receipts: dict[str, dict[str, Any]]
    opt_in_anchor: dict[str, Any]
    in_scope: list[str]
    consumed: dict[str, str]


def _opt_in_anchor(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for event in events:
        if event.get("type") == "generation_opted_in":
            anchor = event.get("core_anchor")
            if isinstance(anchor, Mapping):
                return dict(anchor)
    return {"sequence": 0, "event_hash": None}


def match_runs(
    study_dir: Path,
    contract: Mapping[str, Any],
    *,
    repo: Path | None = None,
    events: Sequence[Mapping[str, Any]] | None = None,
) -> Match:
    """Classify every in-scope run against the receipts.

    Scope is every run whose core ``run_started`` sequence is after the opt-in
    anchor.  Runs are walked in that order, and a receipt is consumed by at most
    one run — which is what makes replay detectable.

    For run *R* the ELIGIBLE receipts are: verdict ``admitted``, same track, not
    superseded, not already consumed, introducing commit an ancestor of
    ``R.candidate_commit``, and ``core_anchor.sequence < R.run_started``.  The
    newest eligible receipt wins; its ``surface_digest`` must equal the digest of
    the surface AT ``R.candidate_commit``.
    """
    events = list(events if events is not None else read_events(study_dir))
    core = read_core_events(study_dir)
    started = run_started_events(core)
    manifests = {str(m.get("experiment")): m for m in load_manifests(study_dir)}
    receipts = load_receipts(study_dir, events)
    superseded = superseded_shas(receipts)
    anchor = _opt_in_anchor(events)
    anchor_sequence = int(anchor.get("sequence") or 0)

    commits: dict[str, str | None] = {}
    if repo is not None:
        for receipt in receipts:
            commits[receipt.sha] = introducing_commit(
                repo, relative(repo, study_dir / "generation" / "objects" / f"{receipt.sha}.json")
            )

    ordered: list[tuple[int, str]] = sorted(
        (
            (int(event.get("sequence") or 0), run)
            for run, event in started.items()
            if int(event.get("sequence") or 0) > anchor_sequence and run in manifests
        )
    )
    in_scope = [run for _sequence, run in ordered]
    consumed: dict[str, str] = {}
    runs: dict[str, str] = {}

    for sequence, run in ordered:
        manifest = manifests[run]
        track = manifest.get("track")
        candidate = manifest.get("candidate_commit")
        preceding = [
            r for r in receipts if r.track == track and r.core_sequence < sequence
        ]
        eligible = [
            r
            for r in preceding
            if r.verdict == "admitted"
            and r.sha not in superseded
            and r.sha not in consumed
            and repo is not None
            and is_ancestor(repo, commits.get(r.sha), candidate)
        ]
        if eligible:
            chosen = max(eligible, key=lambda r: r.sequence)
            digest = None
            if repo is not None and isinstance(candidate, str):
                digest, _entries = surface_digest_at(repo, study_dir, contract, candidate)
            if digest is not None and digest == chosen.surface_digest:
                runs[run] = "admitted"
                consumed[chosen.sha] = run
            else:
                runs[run] = "mismatched"
            continue
        if any(r.sha in consumed for r in preceding):
            runs[run] = "replayed"
        elif preceding and max(preceding, key=lambda r: r.sequence).verdict == "refused":
            runs[run] = "refused-but-run"
        else:
            runs[run] = "unadmitted"

    table = {
        receipt.sha: {"consumed_by": consumed.get(receipt.sha), "commit": commits.get(receipt.sha)}
        for receipt in receipts
    }
    return Match(
        runs=runs,
        receipts=table,
        opt_in_anchor=dict(anchor),
        in_scope=in_scope,
        consumed=consumed,
    )


def outstanding_receipt(
    study_dir: Path,
    contract: Mapping[str, Any],
    *,
    repo: Path | None,
    events: Sequence[Mapping[str, Any]],
    track: str,
) -> Receipt | None:
    """The newest admitted receipt on *track* that no run has consumed yet.

    ``klein generation check`` supersedes it rather than refusing: a ``run-one``
    that aborted before writing a manifest must not strand the track.
    """
    receipts = load_receipts(study_dir, events)
    if not receipts:
        return None
    superseded = superseded_shas(receipts)
    from ..errors import WorkflowError

    try:
        consumed = match_runs(study_dir, contract, repo=repo, events=events).consumed
    except WorkflowError:  # pragma: no cover - a broken study still gets a receipt
        consumed = {}
    live = [
        r
        for r in receipts
        if r.track == track
        and r.verdict == "admitted"
        and r.sha not in superseded
        and r.sha not in consumed
    ]
    return max(live, key=lambda r: r.sequence) if live else None


def core_anchor(study_dir: Path) -> dict[str, Any]:
    """The core chain's tip, for a receipt about to be written."""
    return core_tip(read_core_events(study_dir))
