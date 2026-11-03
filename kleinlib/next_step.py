"""``klein next`` — the one next action a study needs, read from its own records.

A study moves through seven stages past four gates; a newcomer (or an agent picking
a study back up) should not have to reconstruct where it stands from five files.
This module reads the contract, ``study_state.json``, the run manifests, the event
log and the presence of the human artifacts, and answers three questions:

* **where** the study stands (``stage``),
* **what** is already done (``done``),
* **what ONE thing comes next** — the action, the exact command, and the protocol
  section that explains it (``next``).

It is strictly read-only: it never takes the study lock, never writes state,
never commits, never touches the network.  It is advice derived from the records,
never a record itself — every action it names is still performed (and notarized)
by the verb it points at.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contract import (
    PLACEHOLDER_RE,
    _phase_ids,
    load_contract,
    normalize_tracks,
    prepared_data_path,
    schema_version,
)
from .errors import WorkflowError

__all__ = ["format_next", "next_step", "status_data"]

#: Where the protocols live, relative to the repository root.  Pointers only.
_REF = ".claude/skills/klein/references"


def _rel(study_dir: Path) -> str:
    try:
        return study_dir.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return study_dir.as_posix()


def _git_branch(study_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=study_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _manifests(study_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    runs = study_dir / "runs"
    if not runs.is_dir():
        return out
    for path in sorted(runs.glob("E*/manifest.json")):
        data = _read_json(path)
        if isinstance(data, dict):
            out.append(data)
    return out


def _events(study_dir: Path) -> list[dict[str, Any]]:
    path = study_dir / "events.jsonl"
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _gate_recorded(state: Mapping[str, Any], gate: str) -> bool:
    gates = state.get("gates")
    entry = gates.get(gate) if isinstance(gates, Mapping) else None
    return isinstance(entry, Mapping) and entry.get("status") in {"recorded", "overridden"}


def _placeholder_files(study_dir: Path, names: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for name in names:
        path = study_dir / name
        if path.is_file() and PLACEHOLDER_RE.search(path.read_text(encoding="utf-8")):
            found.append(name)
    return found


def _action(
    stage: str,
    action: str,
    command: str | None,
    protocol: str | None,
    why: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "action": action,
        "command": command,
        "protocol": protocol,
        "why": why,
    }


def next_step(study_dir: str | Path = ".") -> dict[str, Any]:
    """The study's position and its single next action, as a JSON-able mapping."""
    study = Path(study_dir)
    s = _rel(study)
    done: list[str] = []
    notes: list[str] = []
    result: dict[str, Any] = {"study": study.name, "done": done, "notes": notes}

    try:
        contract = load_contract(study)
    except WorkflowError as exc:
        result["schema"] = None
        result["next"] = _action(
            "scaffold",
            "create the study contract",
            f"klein new {study.name} --kind … --modality … --profile …  (or: klein new {study.name} --recipe <id>)",
            f"{_REF}/defaults-and-scaffolding.md",
            str(exc),
        )
        return result
    version = schema_version(contract)
    result["schema"] = version
    if version == 1:
        result["next"] = _action(
            "legacy",
            "nothing to run: a v1 study is read-only legacy evidence",
            f"klein verify --study {s}",
            None,
            "schema_version missing means v1 (readable at tag v1.3.0)",
        )
        return result

    state = _read_json(study / "study_state.json")
    if not isinstance(state, dict):
        state = {}
    manifests = _manifests(study)
    tracks = normalize_tracks(contract)
    study_id = str(contract.get("study_id") or study.name)

    # --- CONSULT ---------------------------------------------------------------
    consult_files = ("study.yaml", "research_plan.md", "program.md")
    unfilled = _placeholder_files(study, consult_files)
    if not _gate_recorded(state, "consult"):
        if unfilled:
            result["next"] = _action(
                "CONSULT",
                "fill the contract: replace every {{placeholder}} in " + ", ".join(unfilled),
                None,
                f"{_REF}/consult-protocol.md",
                "the consult gate refuses unresolved placeholders; at most six questions turn "
                "the goal into tracks, metrics and predictions with rules",
            )
            return result
        result["next"] = _action(
            "CONSULT",
            "summarize the contract to the user, get their explicit ack, then record Gate 0",
            f'klein gate record consult --study {s} --acknowledged-by "<name>"',
            f"{_REF}/consult-protocol.md",
            "modeling is blocked until CONSULT, DATA and METHOD are recorded",
        )
        return result
    done.append("CONSULT (Gate 0) recorded")

    # --- DATA ------------------------------------------------------------------
    if not _gate_recorded(state, "data"):
        try:
            prepared = prepared_data_path(study, contract)
            prepared_exists = prepared.exists()
        except WorkflowError:
            prepared_exists = False
        if not prepared_exists and (study / "prepare.py").is_file():
            result["next"] = _action(
                "DATA",
                "build the prepared data",
                f"cd {s} && uv run --locked python -u prepare.py",
                f"{_REF}/data-gate-protocol.md",
                "the DATA gate fingerprints the prepared artifact; it does not exist yet",
            )
            return result
        card = study / "data_card.md"
        if not card.is_file() or PLACEHOLDER_RE.search(card.read_text(encoding="utf-8")):
            result["next"] = _action(
                "DATA",
                "profile the data, run the clean-room leakage audit, and write data_card.md "
                "with ranked go/no-go issues",
                f"uv run --locked python -m kleinlib.leakage --study {s} …",
                f"{_REF}/data-gate-protocol.md",
                "GIGO guard: no modeling before the card says GO",
            )
            return result
        result["next"] = _action(
            "DATA",
            "record Gate 1 (the card must say GO)",
            f'klein gate record data --study {s} --acknowledged-by "<name>"',
            f"{_REF}/data-gate-protocol.md",
            "recording freezes the prepared-data and split fingerprints every run is checked against",
        )
        return result
    done.append("DATA (Gate 1) recorded")

    # --- METHOD ----------------------------------------------------------------
    if not _gate_recorded(state, "method"):
        card = study / "method_card.md"
        if not card.is_file() or PLACEHOLDER_RE.search(card.read_text(encoding="utf-8")):
            result["next"] = _action(
                "METHOD",
                "write method_card.md: intuition → math → minimal implementation → "
                "when it pays → verified references (and references.yaml)",
                None,
                f"{_REF}/method-gate-protocol.md",
                "the card stakes the falsifiable priors SYNTHESIZE will check",
            )
            return result
        result["next"] = _action(
            "METHOD",
            "record Gate 2",
            f'klein gate record method --study {s} --acknowledged-by "<name>"',
            f"{_REF}/method-gate-protocol.md",
            "a declared verifier is hashed here and never changes again",
        )
        return result
    done.append("METHOD (Gate 2) recorded")

    finalization = state.get("finalization")
    finalized = isinstance(finalization, Mapping) and bool(finalization.get("label"))

    # --- the loop --------------------------------------------------------------
    pending = [
        str(m.get("experiment"))
        for m in manifests
        if not isinstance(m.get("transaction"), Mapping)
        or m.get("transaction", {}).get("status") != "complete"
    ]
    branch = _git_branch(study)
    expected_branch = f"experiments/{study_id}"
    if not finalized:
        if pending:
            result["next"] = _action(
                "EXPERIMENT",
                f"finish the interrupted transaction(s) {', '.join(pending)}",
                f"klein recover --study {s}",
                None,
                "a pending manifest blocks every further run",
            )
            return result
        if branch is not None and branch != expected_branch:
            result["next"] = _action(
                "EXPERIMENT",
                f"switch to the study branch {expected_branch}",
                f"git switch {expected_branch} 2>/dev/null || git switch -c {expected_branch}",
                f"{_REF}/defaults-and-scaffolding.md",
                f"run-one refuses any branch but {expected_branch} (current: {branch})",
            )
            return result

    phase_ids = _phase_ids(contract)
    current_phase = str(state.get("current_phase") or (phase_ids[0] if phase_ids else ""))
    final_phase = phase_ids[-1] if phase_ids else None
    acks = state.get("phase_acknowledgements")
    acks = acks if isinstance(acks, Mapping) else {}

    if not finalized:
        # Phase 0: a measured floor before any comparison (frontier tracks).
        if not manifests:
            for name, spec in tracks.items():
                metric = spec.get("metric", {})
                if str(spec.get("mode", "frontier")) != "frontier":
                    continue
                if version >= 3 and metric.get("exactness") == "exact":
                    continue
                if not isinstance(metric.get("noise_floor"), Mapping):
                    result["next"] = _action(
                        "EXPERIMENT · Phase 0",
                        f"measure track {name!r}'s noise floor (a registered sweep), paste the "
                        "printed block into study.yaml and re-record the consult gate with a note",
                        f"klein noise-floor --study {s} --track {name} --recipe <seed-sweep|"
                        "split-lottery|paired-bootstrap|item-bootstrap> --estimand <…>",
                        f"{_REF}/consult-protocol.md",
                        "minimum_delta is MEASURED, never guessed",
                    )
                    return result

        # Phase bookkeeping.
        phase_runs = [m for m in manifests if str(m.get("phase")) == current_phase]
        phase_spec = next(
            (p for p in contract.get("phases", []) if isinstance(p, Mapping) and str(p.get("id")) == current_phase),
            {},
        )
        limit = int(phase_spec.get("max_experiments", 0) or 0)
        if current_phase != final_phase and current_phase not in acks and limit and len(phase_runs) >= limit:
            result["next"] = _action(
                "EXPERIMENT · phase boundary",
                f"phase {current_phase!r} is full ({len(phase_runs)}/{limit}): refresh playbook.md, "
                "summarize to the user, get their ack, then record the boundary",
                f'klein gate record phase --study {s} --phase {current_phase} --acknowledged-by "<name>"',
                f"{_REF}/phase-ritual.md",
                "phase boundaries are user acknowledgements, recorded in state",
            )
            return result

        sealed_spent = {
            str(m.get("track")) for m in manifests if m.get("evaluation_kind") == "final_test"
        }
        if current_phase == final_phase:
            rehearsed = {
                str(e.get("track"))
                for e in _events(study)
                if e.get("type") == "sealed_dryrun" and e.get("acknowledged")
            }
            for name in tracks:
                if name in sealed_spent:
                    continue
                if name not in rehearsed:
                    result["next"] = _action(
                        "EXPERIMENT · sealed",
                        f"rehearse track {name!r}'s one sealed look (spends nothing)",
                        f"klein run-one --study {s} --track {name} --final-test --dry-run",
                        ".claude/skills/klein/SKILL.md",
                        "the dry run is mandatory before every real sealed run",
                    )
                    return result
                result["next"] = _action(
                    "EXPERIMENT · sealed",
                    f"spend track {name!r}'s single sealed look on the frozen configuration",
                    f'klein run-one --study {s} --track {name} --final-test --description "sealed confirmation"',
                    ".claude/skills/klein/SKILL.md",
                    "each track may access its sealed evidence exactly once",
                )
                return result
        else:
            ledger_rows = {
                str(pid): row
                for pid, row in (state.get("predictions") or {}).items()
            } if isinstance(state.get("predictions"), Mapping) else {}
            open_preds = [
                str(p.get("id"))
                for p in contract.get("predictions", []) or []
                if isinstance(p, Mapping) and str(p.get("id")) not in ledger_rows
            ]
            track_name = next(iter(tracks)) if len(tracks) == 1 else "<track>"
            tests = f" --tests {','.join(open_preds[:3])}" if open_preds else ""
            result["next"] = _action(
                f"EXPERIMENT · {current_phase}",
                "re-read playbook.md, pick ONE falsifiable change to the mutable surface "
                f"({', '.join(contract.get('entrypoint', {}).get('mutable', []) or ['train.py'])}), "
                "run it, then reflect in program.md",
                f'klein preflight --study {s} && klein run-one --study {s} --track {track_name} '
                f'--description "<one idea>"{tests}',
                f"{_REF}/phase-ritual.md",
                f"{len(phase_runs)}/{limit or '?'} runs used in phase {current_phase!r}"
                + (f"; open predictions: {', '.join(open_preds)}" if open_preds else ""),
            )
            return result
        done.append("sealed evidence spent on every track")

    # --- SYNTHESIZE / REFEREE / finalize / TUTORIAL ------------------------------
    findings = study / "findings.md"
    if not finalized:
        if not findings.is_file() or PLACEHOLDER_RE.search(findings.read_text(encoding="utf-8")):
            result["next"] = _action(
                "SYNTHESIZE",
                "mine the trajectory and write findings.md (seven sections, claim ids)",
                f"uv run --locked python .claude/skills/klein/scripts/summarize_results.py {s}/results.tsv",
                f"{_REF}/synthesis-protocol.md",
                "the loop is over; the evidence must become claims",
            )
            return result
        if version >= 3 and not (study / "claims.lock").is_file():
            result["next"] = _action(
                "SYNTHESIZE",
                "author claims.lock: pin artifacts, give every number a home, add every claim",
                f"klein claims init --study {s}   # then: klein claims apply --study {s} claims.yaml",
                f"{_REF}/claims-protocol.md",
                "every numeral in findings needs a pinned home",
            )
            return result
        if version >= 3 and not _gate_recorded(state, "referee"):
            report = study / "referee_report.md"
            if not report.is_file():
                result["next"] = _action(
                    "REFEREE",
                    "hand the study to an independent referee in a FRESH context on a different "
                    "model or tool; it writes referee_report.md",
                    f"klein verify --study {s} --numbers --evidence-use && klein claims verify --study {s}",
                    f"{_REF}/referee-protocol.md",
                    "a synthesist never referees its own findings",
                )
                return result
            result["next"] = _action(
                "REFEREE",
                "record Gate 3 (a FAIL verdict cannot be recorded)",
                f'klein gate record referee --study {s} --acknowledged-by "<name>"',
                f"{_REF}/referee-protocol.md",
                "finalize runs only after the referee gate",
            )
            return result
        result["next"] = _action(
            "finalize",
            "label the study exploratory or confirmed from its evidence",
            f"klein finalize --study {s}",
            None,
            "finalize refuses open predictions and strengths the evidence does not support",
        )
        return result
    done.append(f"finalized ({finalization.get('label')})")

    report = study / "report" / "index.html"
    if not report.is_file():
        result["next"] = _action(
            "TUTORIAL",
            "author the seven report fragments and build the teaching artifact",
            f"uv run --locked python .claude/skills/klein/scripts/build_tutorial.py {s}",
            f"{_REF}/tutorial-spec.md",
            "the study closes with a self-contained report/index.html",
        )
        return result
    done.append("tutorial built")

    receipt = study / "verify_receipt.json"
    if version >= 3 and not receipt.is_file():
        result["next"] = _action(
            "verify",
            "issue the verify receipt",
            f"klein verify --study {s}",
            None,
            "the receipt is what a stranger checks first",
        )
        return result
    if version >= 3:
        done.append("verify receipt present")
    result["next"] = _action(
        "closed",
        "nothing is required: the study is closed — promote what generalizes into knowledge/",
        f"klein verify --study {s}",
        "knowledge/README.md",
        "a finished study's findings become the next study's priors",
    )
    return result


def format_next(result: Mapping[str, Any]) -> str:
    lines = [f"study: {result.get('study')}  (schema {result.get('schema')})"]
    for item in result.get("done", []):
        lines.append(f"  [done] {item}")
    nxt = result.get("next") or {}
    lines.append(f"stage: {nxt.get('stage')}")
    lines.append(f"next:  {nxt.get('action')}")
    if nxt.get("command"):
        lines.append(f"  $ {nxt['command']}")
    if nxt.get("why"):
        lines.append(f"  why: {nxt['why']}")
    if nxt.get("protocol"):
        lines.append(f"  read: {nxt['protocol']}")
    for note in result.get("notes", []):
        lines.append(f"  note: {note}")
    return "\n".join(lines) + "\n"


def status_data(study_dir: str | Path = ".") -> dict[str, Any]:
    """``klein status --json``: the machine state ``klein status`` prints, as data.

    Read-only, like :func:`next_step`.  Derived from the same records the text
    status reads (contract, ``study_state.json``, manifests); it adds the
    per-track frontier and the next action so an agent or an MCP client needs
    one call, not five file reads.
    """
    study = Path(study_dir)
    contract = load_contract(study)
    version = schema_version(contract)
    state = _read_json(study / "study_state.json")
    state = state if isinstance(state, dict) else {}
    manifests = _manifests(study)
    counts: dict[str, int] = {"keep": 0, "discard": 0, "measured": 0, "crash": 0}
    for manifest in manifests:
        key = str(manifest.get("disposition"))
        counts[key] = counts.get(key, 0) + 1
    tracks: dict[str, Any] = {}
    for name, spec in normalize_tracks(contract).items():
        metric = spec.get("metric", {})
        mine = [m for m in manifests if str(m.get("track")) == name]
        keeps = [m for m in mine if m.get("disposition") == "keep"]
        incumbent = keeps[-1] if keeps else None
        tracks[name] = {
            "mode": spec.get("mode", "frontier"),
            "metric": metric.get("name"),
            "goal": metric.get("goal"),
            "minimum_delta": metric.get("minimum_delta"),
            "noise_floor_measured": isinstance(metric.get("noise_floor"), Mapping),
            "runs": len(mine),
            "incumbent": (
                {"experiment": incumbent.get("experiment"), "primary_metric": incumbent.get("primary_metric")}
                if incumbent
                else None
            ),
            "sealed": next(
                (
                    {"experiment": m.get("experiment"), "primary_metric": m.get("primary_metric")}
                    for m in mine
                    if m.get("evaluation_kind") == "final_test"
                ),
                None,
            ),
        }
    gates = state.get("gates") if isinstance(state.get("gates"), Mapping) else {}
    predictions = state.get("predictions") if isinstance(state.get("predictions"), Mapping) else {}
    registered = [
        str(p.get("id")) for p in contract.get("predictions", []) or [] if isinstance(p, Mapping)
    ]
    tally = {"supported": 0, "refuted": 0, "inconclusive": 0, "open": 0}
    for pid in registered:
        row = predictions.get(pid)
        verdict = row.get("verdict") if isinstance(row, Mapping) else None
        tally[verdict if verdict in tally else "open"] += 1
    return {
        "study": str(state.get("study_id") or contract.get("study_id") or study.name),
        "schema": version,
        "kind": contract.get("kind"),
        "modality": (contract.get("data") or {}).get("modality") if isinstance(contract.get("data"), Mapping) else None,
        "profile": contract.get("profile") or contract.get("profile_doc"),
        "status": state.get("status"),
        "current_phase": state.get("current_phase"),
        "gates": {
            name: (entry.get("status") if isinstance(entry, Mapping) else None)
            for name, entry in gates.items()
        },
        "experiments": {"total": len(manifests), **counts},
        "pending_transactions": [
            str(m.get("experiment"))
            for m in manifests
            if not isinstance(m.get("transaction"), Mapping)
            or m.get("transaction", {}).get("status") != "complete"
        ],
        "tracks": tracks,
        "predictions": tally,
        "finalization": state.get("finalization"),
        "next": next_step(study).get("next"),
    }
