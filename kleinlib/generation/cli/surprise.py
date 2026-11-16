"""``klein generation surprise …`` (the ``surprise`` capability): surprise-mining verbs.
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
    _state,
    _study,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation surprise register|record|show`` (the ``surprise`` capability)."""
    surprise = actions.add_parser(
        "surprise",
        help="register the discovery search space, then record what its tables found",
        description=(
            "A discovery cell declares WHERE it will look before it looks: template, "
            "statistic, adapter and inputs with their hashes, partition, unit and group "
            "policy, the complete segment inventory, the minimum n, and the multiplicity "
            "rule (a measured effect floor is not one). The cell then runs as an ordinary "
            "`klein run-one --tests P#`; `record` reads the pinned per-unit table, "
            "recomputes every segment, applies the declared family rule and issues one "
            "<study>#Sn receipt per violation - retaining the null and inconclusive "
            "segments, and inventing no explanations. See "
            ".claude/skills/klein/references/surprise-protocol.md."
        ),
    )
    surprise_actions = surprise.add_subparsers(dest="surprise_action", required=True)

    register_cells = surprise_actions.add_parser(
        "register", help="lock discovery_cells.yaml (after METHOD, before any cell evidence)"
    )
    _study(register_cells)
    _testimony(register_cells)
    register_cells.set_defaults(handler=_run_surprise_register)

    record = surprise_actions.add_parser(
        "record", help="read one cell run's pinned table and record every segment"
    )
    _study(record)
    _testimony(record)
    record.add_argument(
        "--run", required=True, metavar="E####", help="the run that produced the table"
    )
    record.add_argument("--cell", help="the cell id, when you want the binding checked explicitly")
    record.add_argument(
        "--explain",
        action="append",
        default=[],
        metavar="SEGMENT=TEXT",
        help="optional testimony for one violating segment (repeatable); the default, "
        "`unresolved`, is the honest value and nothing here invents another",
    )
    record.set_defaults(handler=_run_surprise_record)

    show = surprise_actions.add_parser("show", help="read-only: cells, records, receipts")
    _study(show)
    show.add_argument("--cell", help="one cell (default: every registered cell)")
    show.set_defaults(handler=_run_surprise_show)


def _surprise_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every surprise verb.  Raises ``WorkflowError``."""
    from ..chronology import repo_for
    from ..ledger import read_events
    from ..surprise import CAPABILITY_NAME

    study, contract = _load(args)
    _require_capability(study, CAPABILITY_NAME)
    _require_healthy_ledger(study)
    _require_clean(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, repo, read_events(study)


def _run_surprise_register(args: argparse.Namespace) -> int:
    """``surprise register`` — validate, pin the hashes, freeze, anchor, commit."""
    from ...primitives import atomic_write_text, sha256_file
    from .. import manifest as gm
    from .. import surprise as gs
    from ..admission import core_anchor, load_receipts
    from ..chronology import git_head
    from ..ledger import append_event, commit_artifacts, write_object

    try:
        study, contract, repo, events = _surprise_setup(args, extra=(gs.CELLS_NAME,))
        document = gs.parse_cells(gs.cells_path(study))
    except WorkflowError as exc:
        return _error(str(exc))

    versions = gs.registrations(study, events)
    previous = versions[-1]["object"] if versions else None
    study_name = gm.study_id(study, contract)
    problems = gs.cells_problems(
        document,
        study=study_name,
        study_dir=study,
        contract=contract,
        state=_state(study, contract),
        previous=previous,
    )
    if problems:
        print("surprise register refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    known = set(gs.registered_cells(study, events))
    observed = _cell_evidence_exists(study, contract, repo, events, known)
    payload = _pinned_cells_document(study, document, known=known, observed=observed)
    atomic_write_text(gs.cells_path(study), gs.render_cells(payload))
    file_sha = sha256_file(gs.cells_path(study))

    declared = {str(cell["cell_id"]) for cell in payload["cells"]}
    late = any(
        _receipt_names_a_cell(study, receipt.sha, declared)
        for receipt in load_receipts(study, events)
    )
    obj = gs.build_registration(
        payload,
        study=study_name,
        version=len(versions) + 1,
        parent_ids=[versions[-1]["event"]["id"]] if versions else [],
        file_sha256=file_sha,
        late=late and not versions,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gs.REGISTER_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=obj["parent_ids"],
        testimony_fields=_testimony_fields(args),
        version=obj["version"],
        cells=len(obj["cells"]),
        late=obj["late"],
    )
    commit_artifacts(
        study,
        f"klein: discovery cells registered ({study_name} v{obj['version']})",
        paths=[gs.CELLS_NAME, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} discovery cells v{obj['version']}: {len(obj['cells'])} cell(s), "
        f"file {file_sha[:12]}…, object {sha[:12]}…"
    )
    for cell in payload["cells"]:
        inventory = gs.segment_inventory(cell)
        label = " [post-observation]" if cell.get("post_observation") else ""
        method = (cell.get("multiplicity_rule") or {}).get("method")
        print(
            f"  {cell['cell_id']}  {cell['template']}  {len(inventory)} segment(s)  "
            f"{cell['expectation_P']}  {method}{label}"
        )
    if obj["late"]:
        print(
            "WARNING: a cell admission already named one of these cells — "
            "`klein generation verify` will FAIL `surprise cells` for the life of this study"
        )
    return 0


def _cell_evidence_exists(
    study: Path,
    contract: dict[str, Any],
    repo: Path,
    events: list[dict[str, Any]],
    known: set[str],
) -> bool:
    """Has ANY registered cell produced evidence yet?

    Not "has anything been recorded": recording is a later, voluntary step, and
    a driver who ran a cell, looked at its table and then registered a new
    segment would have had the new cell silently preregistered. What makes a
    cell post-observation is that its OUTPUTS exist — an admitted cell
    admission a run has already consumed, or a pinned table on disk — so that is
    what is asked, and the answer does not depend on the driver's diligence.
    """
    from .. import surprise as gs
    from ..admission import match_runs

    if any((study / gs.table_relpath(name)).is_file() for name in known):
        return True
    try:
        match = match_runs(study, contract, repo=repo, events=events)
    except WorkflowError:  # pragma: no cover - a broken study still gets a registration
        return False
    return bool(gs.cell_runs(study, events, match))


def _receipt_names_a_cell(study: Path, sha: str, declared: set[str]) -> bool:
    from ..ledger import read_object

    try:
        obj = read_object(study, sha)
    except WorkflowError:  # pragma: no cover - the ledger guard catches this first
        return False
    intended = obj.get("intended_action")
    named = intended.get("cell_id") if isinstance(intended, dict) else None
    return isinstance(named, str) and named in declared


def _pinned_cells_document(
    study: Path, document: dict[str, Any], *, known: set[str], observed: bool
) -> dict[str, Any]:
    """The authored document with every hash pinned and every new cell labelled.

    A cell added once ANY cell of this study has produced EVIDENCE is forced
    ``post_observation: true`` — adaptive slices are lawful and are labelled;
    what they may never do is acquire preregistration by arriving in the same
    file as cells that were registered first.  ``observed`` is the study-wide
    answer (see :func:`_cell_evidence_exists`); a cell whose own table is
    already on disk is labelled whatever that answer was.
    """
    from ...primitives import sha256_file
    from .. import surprise as gs

    adapters = [
        {"path": str(entry["path"]), "sha256": sha256_file(study / str(entry["path"]))}
        for entry in document.get("adapters") or []
        if isinstance(entry, dict) and entry.get("path")
    ]
    cells: list[dict[str, Any]] = []
    for raw in document.get("cells") or []:
        cell = dict(raw)
        cell["input_refs"] = [
            {"path": str(ref["path"]), "sha256": sha256_file(study / str(ref["path"]))}
            for ref in cell.get("input_refs") or []
            if isinstance(ref, dict) and ref.get("path")
        ]
        name = str(cell["cell_id"])
        own_table = (study / gs.table_relpath(name)).is_file()
        if name not in known and (observed or own_table):
            cell["post_observation"] = True
        cells.append(gs.ordered_cell(cell))
    return {
        "type": "discovery-cells",
        "study": document.get("study"),
        "adapters": adapters,
        "cells": cells,
    }


def _run_surprise_record(args: argparse.Namespace) -> int:
    """``surprise record`` — recompute one cell run from its pinned table."""
    from ...manifest import load_manifests
    from ...primitives import sha256_file
    from .. import manifest as gm
    from .. import surprise as gs
    from ..admission import core_anchor, match_runs
    from ..chronology import git_head
    from ..ledger import append_event, commit_artifacts, write_object

    run = str(args.run)
    try:
        study, contract, repo, events = _surprise_setup(args)
        explanations = _explanations(args.explain)
    except WorkflowError as exc:
        return _error(str(exc))

    manifests = {str(m.get("experiment")): m for m in load_manifests(study)}
    manifest = manifests.get(run)
    if manifest is None:
        return _error(f"{run} has no manifest under runs/ — nothing to record")
    if manifest.get("disposition") == "crash":
        return _error(f"{run} crashed; a run that produced no table measured nothing")

    match = match_runs(study, contract, repo=repo, events=events)
    bound = gs.cell_runs(study, events, match).get(run)
    if bound is None:
        return _error(
            f"{run} carries no admitted cell admission — a discovery cell is admitted "
            "with `klein generation check --action cell --cell <id>` BEFORE it runs, and "
            f"the spine classified {run} as {match.runs.get(run, 'out of scope')!r}"
        )
    if args.cell and args.cell != bound:
        return _error(f"{run} was admitted for cell {bound}, not {args.cell}")
    cell = gs.registered_cells(study, events).get(bound)
    if cell is None:  # pragma: no cover - admission already refused an unregistered cell
        return _error(f"{bound} is not a registered discovery cell")
    if any(str(entry["object"].get("run")) == run for entry in gs.records(study, events)):
        return _error(
            f"{run} is already recorded; a record is written once, from the pinned table"
        )

    rel = gs.table_relpath(bound)
    artifacts = manifest.get("artifacts") or {}
    pinned = artifacts.get(rel) if isinstance(artifacts, dict) else None
    if not isinstance(pinned, dict) or not pinned.get("sha256"):
        return _error(
            f"{run}'s manifest pins no artifact {rel} — the cell's entrypoint prints "
            f"`artifact: {rel}` and the notary hashes it into the manifest"
        )
    path = study / rel
    if not path.is_file() or sha256_file(path) != pinned["sha256"]:
        return _error(f"{rel} is not the table {run} pinned ({str(pinned['sha256'])[:12]}…)")
    group_column = gs.group_column_of(cell)
    try:
        units = gs.read_units(study, bound, group_column)
    except WorkflowError as exc:
        if group_column:
            return _refuse(
                f"{bound} declares group_policy.column {group_column!r} and its pinned "
                f"table does not carry it: {exc}. A clustered cell's sign flip acts on "
                "groups, and the group of each unit has to be in the evidence"
            )
        return _error(str(exc))

    record = gs.build_record(run=run, cell=cell, units=units, table_sha256=str(pinned["sha256"]))
    record["summary_sha256"] = gs.write_summary_table(study, record)
    sha = write_object(study, record)
    study_name = gm.study_id(study, contract)
    event = append_event(
        study,
        gs.RECORD_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        run=run,
        cell_id=bound,
        family_size=record["family_size"],
        violations=record["n_violations"],
        outcome=record["outcome"],
    )
    issued = _issue_receipts(
        args,
        study,
        study_name=study_name,
        repo=repo,
        record=record,
        cell=cell,
        parent=event["id"],
        explanations=explanations,
    )
    commit_artifacts(
        study,
        f"klein: surprise recorded ({study_name} {bound} on {run}, "
        f"{record['n_violations']} violation(s))",
        paths=["generation/tables", "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} {bound} on {run}: family of {record['family_size']} segment(s), "
        f"{record['n_violations']} violation(s), outcome {record['outcome']}"
    )
    for row in record["segments"]:
        print(
            f"  {row['segment']}: n={row['n']} deviation={_number(row['deviation'])} "
            f"t={_number(row['t'])} adjusted_p={_number(row['adjusted_p'])} → {row['verdict']}"
        )
    for name, segment in issued:
        print(f"  {name}: {segment} (explanation: {explanations.get(segment, 'unresolved')})")
    print(f"summary: {gs.summary_table_path(study, bound).relative_to(study).as_posix()}")
    if record["missing_segments"] or record["extra_segments"]:
        print(
            "REFUSED as evidence: the table's segments do not match the frozen inventory — "
            f"missing {record['missing_segments']}, unregistered {record['extra_segments']}. "
            "The record is filed anyway; `klein generation verify` FAILs `surprise records`."
        )
        return 2
    return 0


def _explanations(raw: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw or []:
        segment, sep, text = str(item).partition("=")
        if not sep or not segment.strip() or not text.strip():
            raise WorkflowError(f"--explain {item!r} must be SEGMENT=TEXT")
        out[segment.strip()] = text.strip()
    return out


def _issue_receipts(
    args: argparse.Namespace,
    study: Path,
    *,
    study_name: str,
    repo: Path | None,
    record: dict[str, Any],
    cell: dict[str, Any],
    parent: str,
    explanations: dict[str, str],
) -> list[tuple[str, str]]:
    """One ``<study>#Sn`` per violating segment, in table order.  Nothing else."""
    from .. import surprise as gs
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, read_events, write_object

    events = read_events(study)
    number = gs.next_surprise_number(study, events)
    exposure = [
        str(cell.get("partition")),
        *sorted({str(entry["object"].get("run")) for entry in gs.records(study, events)}),
    ]
    issued: list[tuple[str, str]] = []
    for row in record["segments"]:
        if row["verdict"] != "violation":
            continue
        name = f"{study_name}#S{number}"
        number += 1
        obj = gs.receipt_object(
            surprise_id=name,
            record=record,
            segment=row,
            cell=cell,
            explanation=explanations.get(str(row["segment"]), "unresolved"),
            exposure=exposure,
        )
        sha = write_object(study, obj)
        append_event(
            study,
            gs.RECEIPT_TYPE,
            study=study_name,
            core_anchor=core_anchor(study),
            git_head=git_head(repo),
            payload_sha256=sha,
            parent_ids=[parent],
            testimony_fields=_testimony_fields(args),
            surprise_id=name,
            cell_id=str(cell["cell_id"]),
            run=str(record["run"]),
            segment=str(row["segment"]),
            label=obj["label"],
        )
        issued.append((name, str(row["segment"])))
    return issued


def _run_surprise_show(args: argparse.Namespace) -> int:
    from .. import surprise as gs
    from ..ledger import read_events

    try:
        study, _contract = _load(args)
        _require_capability(study, gs.CAPABILITY_NAME)
    except WorkflowError as exc:
        return _error(str(exc))
    events = read_events(study)
    versions = gs.registrations(study, events)
    if not versions:
        print("no discovery cell is registered")
        return 0
    for version in versions:
        obj = version["object"]
        print(
            f"{version['event']['id']} discovery cells v{obj['version']}: "
            f"{len(obj['cells'])} cell(s), file {str(obj['file_sha256'])[:12]}…"
        )
        for cell in obj["cells"]:
            if args.cell and cell.get("cell_id") != args.cell:
                continue
            method = (cell.get("multiplicity_rule") or {}).get("method")
            group = gs.group_column_of(cell)
            print(
                f"  {cell['cell_id']}  {cell['template']}/{cell['statistic']}  "
                f"{cell['partition']}  min_n={cell['minimum_n']}  {method}  "
                + (f"per group ({group})" if group else "per unit")
            )
    for entry in gs.records(study, events):
        obj = entry["object"]
        if args.cell and obj.get("cell_id") != args.cell:
            continue
        print(
            f"{entry['event']['id']} {obj['cell_id']} on {obj['run']}: family "
            f"{obj['family_size']}, {obj['n_violations']} violation(s), {obj['outcome']}, "
            f"per {obj.get('unit_of_inference') or 'unit'}"
        )
    for entry in gs.receipts(study, events):
        obj = entry["object"]
        if args.cell and obj.get("cell_id") != args.cell:
            continue
        print(
            f"{obj['id']}  {obj['cell_id']}/{obj['segment']}  deviation "
            f"{_number(obj['deviation'])} {obj['units']}  adjusted_p "
            f"{_number(obj['adjusted_p'])}  [{obj['label']}]  {obj['explanation']}"
        )
    return 0
