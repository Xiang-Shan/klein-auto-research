"""``klein generation parity …`` (the ``parity`` capability).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _number,
    _refuse,
    _require_capability,
    _require_clean,
    _require_healthy_ledger,
    _study,
    _study_relative_file,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation parity lock|amend|bind|assess|show``.

    Argparse only, like every other group here: the handlers import
    ``kleinlib.generation.parity`` lazily, so a study that never declares
    ``parity`` never loads a line of it.
    """
    parity = actions.add_parser(
        "parity",
        help="one registered vector comparison of the AI and expert pipelines",
        description=(
            "Lock parity.yaml at CONSULT (both pipelines, the sampling unit and block, "
            "every metric with its direction, floor reference, margin and a written "
            "rationale for that margin); bind the scorer, both frozen snapshots and the "
            "measured floors BEFORE any sealed access on any track; measure in one sealed "
            "registered cell; assess the verdict from the pinned per-unit table. See "
            ".claude/skills/klein/references/generation/expert-parity-protocol.md."
        ),
    )
    parity_actions = parity.add_subparsers(dest="parity_action", required=True)

    lock = parity_actions.add_parser(
        "lock", help="freeze parity.yaml's criteria (before the CONSULT gate)"
    )
    _study(lock)
    _testimony(lock)
    lock.add_argument(
        "--allow-late",
        action="store_true",
        help="lock AFTER the consult gate: recorded as late and permanently FAILs `parity lock`",
    )
    lock.set_defaults(handler=_run_parity_lock, parity_amend=False)

    amend = parity_actions.add_parser(
        "amend",
        help="record a new version with parents; the metric set, margins and uncertainty "
        "rule may NOT change",
    )
    _study(amend)
    _testimony(amend)
    amend.set_defaults(handler=_run_parity_lock, parity_amend=True, allow_late=True)

    bind = parity_actions.add_parser(
        "bind", help="pin the scorer, both frozen pipelines and every measured floor"
    )
    _study(bind)
    _testimony(bind)
    bind.add_argument(
        "--floor-run",
        metavar="E####",
        help="restate the calibration run every metric's floor_ref already names "
        "(refused when it names a different run)",
    )
    bind.add_argument(
        "--ai-snapshot",
        action="append",
        default=[],
        metavar="PATH",
        help="a study-relative file of the frozen AI pipeline (repeatable)",
    )
    bind.add_argument(
        "--expert-snapshot",
        action="append",
        default=[],
        metavar="PATH",
        help="a study-relative file of the frozen expert pipeline (repeatable)",
    )
    bind.set_defaults(handler=_run_parity_bind)

    assess = parity_actions.add_parser(
        "assess", help="recompute d/L/U from the sealed cell's pinned table and decide"
    )
    _study(assess)
    _testimony(assess)
    assess.add_argument("--run", required=True, metavar="E####", help="the sealed comparison cell")
    assess.set_defaults(handler=_run_parity_assess)

    show = parity_actions.add_parser("show", help="read-only: versions, bind, assessments")
    _study(show)
    show.set_defaults(handler=_run_parity_show)


def _parity_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every parity verb.  Raises ``WorkflowError``."""
    from ..chronology import repo_for
    from ..ledger import read_events

    study, contract = _load(args)
    _require_capability(study, "parity")
    _require_healthy_ledger(study)
    _require_clean(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, repo, read_events(study)


def _run_parity_lock(args: argparse.Namespace) -> int:
    """``parity lock`` and ``parity amend`` — one transaction, two entry points."""
    from ...primitives import sha256_file
    from .. import manifest as gm
    from .. import parity as gp
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events
    from ..ledger import append_event, commit_artifacts, write_object

    amending = bool(getattr(args, "parity_amend", False))
    try:
        study, contract, repo, events = _parity_setup(args, extra=(gp.PARITY_NAME,))
        payload = gp.read_parity_file(study)
    except WorkflowError as exc:
        return _error(str(exc))

    versions = gp.locks(study, events)
    if versions and not amending:
        return _error(
            f"{gp.PARITY_NAME} is already locked at version {versions[-1][1].get('version')} — "
            "a change is `klein generation parity amend`, which keeps the parents and cannot "
            "move a margin"
        )
    if amending and not versions:
        return _error("nothing to amend: `klein generation parity lock` records version 1")
    if amending and gp.joined(study, events, gp.BIND_TYPE):
        return _refuse(
            "the pipelines are already bound: the criteria a sealed comparison will be "
            "measured against cannot be restated after they were frozen"
        )

    study_name = gm.study_id(study, contract)
    problems = gp.validation_problems(
        payload,
        study=study_name,
        contract=contract,
        experimenter=gp.experimenter_of(study),
        previous=versions[0][1].get("payload") if versions else None,
    )
    if problems:
        print(f"parity {'amend' if amending else 'lock'} refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    late = bool(gate_events(read_core_events(study), "consult"))
    if late and not amending and not args.allow_late:
        return _refuse(
            "the consult gate is already recorded: the comparison's criteria must be locked "
            "BEFORE CONSULT, so the margins precede every number they judge. `--allow-late` "
            "records the lock anyway; `generation verify` then FAILs `parity lock` permanently."
        )

    version = len(versions) + 1
    parents = [str(versions[-1][0].get("id"))] if versions else []
    file_sha = sha256_file(gp.parity_path(study))
    obj = gp.lock_object(
        study=study_name,
        version=version,
        payload=payload,
        file_sha256=file_sha,
        parent_ids=parents,
        late=late,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gp.AMEND_TYPE if amending else gp.LOCK_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=parents,
        testimony_fields=_testimony_fields(args),
        version=version,
        file_sha256=file_sha,
        metrics=len(gp.metric_rows(payload)),
        **({"late": True} if late else {}),
    )
    commit_artifacts(
        study,
        f"klein: parity {'amend' if amending else 'lock'} v{version} ({study_name})",
        paths=[gp.PARITY_NAME, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} parity lock v{version}: {gp.PARITY_NAME} {file_sha[:12]}…, "
        f"track {payload.get('comparison_track')!r}, object {sha[:12]}…"
    )
    for row in gp.metric_rows(payload):
        print(
            f"  - {row.get('key')} ({row.get('direction')}): margin "
            f"{row.get('margin')}, floor from {row.get('floor_ref')}, "
            f"adjudicated by {(payload.get('predictions') or {}).get(row.get('key'))}"
        )
    if late:
        print(
            "WARNING: late lock recorded — `klein generation verify` will FAIL `parity lock` "
            "for the life of this study"
            if not amending
            else "NOTE: this amendment is labelled late; version 1's criteria remain primary"
        )
    return 0


def _resolve_floor(
    key: str,
    reference: str,
    manifests: dict[str, dict[str, Any]],
    override: str | None,
) -> dict[str, Any]:
    """The measured floor ``delta_j``, read where the LOCK said it would be.

    ``--floor-run`` is a convenience for the common case where every metric's
    floor came from the same Phase-0 calibration run; it may only NAME that run.
    Pointing it somewhere else would be a floor chosen once the comparison was in
    sight, which is the whole reason ``floor_ref`` is registered — and the bind
    family FAILs the mismatch afterwards anyway, so refusing it here is the same
    rule said earlier.
    """
    source = str(reference)
    if source.startswith("sweep:"):
        raise WorkflowError(
            f"metric {key!r}: floor_ref {source!r} — a registered sweep records its sidecar "
            "and script hashes, not a numeric floor, so this version cannot read delta from "
            "it. Print floor_" + key + " from a Phase-0 `--action calibration` run "
            "(`evaluate*(..., extra={...})`) and reference it as `run:E####` in an amended "
            "lock."
        )
    if override and source != f"run:{override}":
        raise WorkflowError(
            f"metric {key!r}: --floor-run {override!r} does not name the run the lock froze "
            f"({source!r}) — the floor's source is registered before the comparison, and the "
            "flag may only restate it"
        )
    run = source.split(":", 1)[1] if ":" in source else ""
    manifest = manifests.get(run)
    if manifest is None:
        raise WorkflowError(f"metric {key!r}: no run manifest for {run!r}")
    metrics = manifest.get("metrics")
    value = metrics.get(f"floor_{key}") if isinstance(metrics, dict) else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise WorkflowError(
            f"metric {key!r}: {run} printed no numeric `floor_{key}` — the paired floor recipe "
            "prints one key per metric via `evaluate*(..., extra={...})`"
        )
    return {"value": float(value), "source": source, "metric_key": f"floor_{key}"}


def _run_parity_bind(args: argparse.Namespace) -> int:
    from ...manifest import load_manifests
    from .. import expert as ge
    from .. import manifest as gm
    from .. import parity as gp
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, repo, events = _parity_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    versions = gp.locks(study, events)
    if not versions:
        return _error(
            f"{gp.PARITY_NAME} is not locked: there are no criteria to bind the pipelines to"
        )
    if gp.joined(study, events, gp.BIND_TYPE):
        return _error(
            "the pipelines are already bound — they are frozen ONCE, before the first sealed "
            "access on any track"
        )
    if not gate_events(read_core_events(study), "method"):
        return _refuse(
            "the METHOD gate is not recorded: the scorer is frozen at METHOD, so binding it "
            "before the gate would pin a checker the gate never hashed"
        )
    if ge.reproduced_bind(ge.joined(study, events, ge.BIND_TYPE)) is None:
        return _refuse(
            "the expertise obligation is open: no `expert bind` reproduced the baseline, so "
            "the 'expert' side of the comparison is not the recipe the card froze"
        )

    lock_event, lock = versions[-1]
    payload = lock.get("payload") or {}
    # Two passes, because they fail for different reasons: a path that cannot be
    # resolved is a question that cannot be ASKED (exit 1), while a floor the lock
    # registered and the evidence does not carry is a rule saying no (exit 2).
    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(study)}
        scorer_path, scorer_sha = _study_relative_file(
            study, str((payload.get("scorer") or {}).get("path")), label="scorer.path"
        )
        snapshots = {
            "ai": [
                list(_study_relative_file(study, raw, label="--ai-snapshot"))
                for raw in args.ai_snapshot
            ],
            "expert": [
                list(_study_relative_file(study, raw, label="--expert-snapshot"))
                for raw in args.expert_snapshot
            ],
        }
    except WorkflowError as exc:
        return _error(str(exc))
    for side in ("ai", "expert"):
        if not snapshots[side]:
            return _error(
                f"--{side}-snapshot names no file: BOTH pipelines are frozen at the bind, and "
                "an unpinned pipeline is one that can still change before the sealed cell"
            )
    try:
        floors = {
            str(row.get("key")): _resolve_floor(
                str(row.get("key")), str(row.get("floor_ref")), manifests, args.floor_run
            )
            for row in gp.metric_rows(payload)
        }
    except WorkflowError as exc:
        return _refuse(str(exc))

    study_name = gm.study_id(study, contract)
    obj = gp.bind_object(
        study=study_name,
        lock_sha=str(lock_event.get("payload_sha256")),
        scorer={"path": scorer_path, "sha256": scorer_sha},
        floors=floors,
        snapshots=snapshots,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gp.BIND_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(lock_event.get("id"))],
        testimony_fields=_testimony_fields(args),
        scorer_sha256=scorer_sha,
        floors=len(floors),
    )
    commit_generation(
        study,
        f"klein: parity bind ({study_name}, {len(floors)} floor(s))",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(f"{event['id']} parity bind: scorer {scorer_path} {scorer_sha[:12]}…, object {sha[:12]}…")
    for key, floor in floors.items():
        print(f"  - {key}: delta {floor['value']:.12g} from {floor['source']}")
    for side in ("ai", "expert"):
        for path, digest in snapshots[side]:
            print(f"  - {side}: {path} {digest[:12]}…")
    print("every sealed access on every track must now follow this anchor")
    return 0


def _run_parity_assess(args: argparse.Namespace) -> int:
    from ...manifest import load_manifests
    from .. import manifest as gm
    from .. import parity as gp
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, repo, events = _parity_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    versions = gp.locks(study, events)
    binds = gp.joined(study, events, gp.BIND_TYPE)
    if not versions or not binds:
        return _error(
            "parity is not both locked and bound: an assessment needs the criteria and the "
            "measured floors that were frozen before the comparison ran"
        )
    run = str(args.run)
    existing = [
        obj for _event, obj in gp.joined(study, events, gp.ASSESS_TYPE) if obj.get("run") == run
    ]
    if existing:
        return _error(
            f"{run} is already assessed ({existing[-1].get('verdict')}) — the assessment is a "
            "recomputation of pinned bytes, so a second one would say the same thing"
        )

    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(study)}
    except WorkflowError as exc:
        return _error(str(exc))
    manifest = manifests.get(run)
    if manifest is None:
        return _error(f"no run manifest for {run} — assess the sealed comparison cell")
    if manifest.get("evaluation_kind") != "final_test":
        return _refuse(
            f"{run} is a {manifest.get('evaluation_kind')} run; the comparison is the "
            "comparison track's SOLE sealed evaluation"
        )
    payload = versions[-1][1].get("payload") or {}
    track = str(payload.get("comparison_track"))
    if str(manifest.get("track")) != track:
        return _refuse(
            f"{run} is a sealed run on track {manifest.get('track')!r}, not the locked "
            f"comparison track {track!r} — the parity outcome is that track's sole sealed "
            "evaluation, and assessing another one would put a second verdict on the ledger"
        )

    study_name = gm.study_id(study, contract)
    try:
        body = gp.build_assessment(
            study,
            study=study_name,
            run=run,
            lock=versions[-1][1],
            bind=binds[0][1],
            manifest=manifest,
        )
    except WorkflowError as exc:
        return _refuse(str(exc))

    sha = write_object(study, body)
    event = append_event(
        study,
        gp.ASSESS_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(binds[0][0].get("id"))],
        testimony_fields=_testimony_fields(args),
        run=run,
        verdict=body["verdict"],
        agreement_within_floor=body["agreement_within_floor"],
    )
    commit_generation(
        study,
        f"klein: parity assessed {run} ({body['verdict']})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(
        f"{event['id']} parity assess {run}: {body['verdict']} over {body['n_units']} unit(s) "
        f"in {body['n_blocks']} block(s) — object {sha[:12]}…"
    )
    for key, row in body["metrics"].items():
        print(
            f"  - {key}: ai {_number(row['ai'])} expert {_number(row['expert'])} "
            f"d {_number(row['d'])} [{_number(row['L'])}, {_number(row['U'])}] "
            f"delta {row['delta_floor']:.6g} margin {row['margin']:.6g}"
            + ("" if row["defined"] else "  UNDEFINED — cannot pass")
        )
    for reason in body["reasons"]:
        print(f"  {reason}")
    print(
        f"agreement_within_floor: {body['agreement_within_floor']} "
        "(the by-delta agreement rule, reported under its own name — never as parity)"
    )
    return 0 if body["verdict"] in ("parity", "exceeds") else 2


def _run_parity_show(args: argparse.Namespace) -> int:
    from .. import parity as gp
    from ..ledger import read_events

    try:
        study, _contract = _load(args)
        _require_capability(study, "parity")
    except WorkflowError as exc:
        return _error(str(exc))
    events = read_events(study)
    versions = gp.locks(study, events)
    if not versions:
        print("parity: nothing locked")
        return 0
    for event, obj in versions:
        payload = obj.get("payload") or {}
        print(
            f"{event['id']} parity v{obj.get('version')}: track "
            f"{payload.get('comparison_track')!r}, {len(gp.metric_rows(payload))} metric(s), "
            f"file {str(obj.get('file_sha256'))[:12]}…"
            + (" [late]" if obj.get("late") else "")
        )
    for event, obj in gp.joined(study, events, gp.BIND_TYPE):
        print(
            f"{event['id']} bind: scorer {(obj.get('scorer') or {}).get('path')} "
            f"{str((obj.get('scorer') or {}).get('sha256'))[:12]}…, "
            f"{len(obj.get('floors') or {})} floor(s)"
        )
    for event, obj in gp.joined(study, events, gp.ASSESS_TYPE):
        print(
            f"{event['id']} assess {obj.get('run')}: {obj.get('verdict')} "
            f"(agreement_within_floor={obj.get('agreement_within_floor')}, "
            f"undefined={', '.join(obj.get('undefined_metrics') or []) or 'none'})"
        )
    return 0
