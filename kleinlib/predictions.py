"""The predictions ledger — mechanized belief revision (schema 3).

A registered prediction is a belief written down BEFORE the evidence, with the
arithmetic that will decide it.  This module is the ledger that answers, at any
moment, what each belief now stands at and on which evidence:

- :func:`ledger` joins the contract's register (``study.yaml: predictions[]``)
  to the verdicts in ``study_state.json`` — a prediction with no record is
  ``open``, which is a state the study must either close or explain.
- :func:`record_verdict` writes one verdict, appending to a per-prediction
  ``history`` that is never rewritten: a belief that changed says so, with both
  records intact.  ``run-one --tests`` calls it inside the run transaction;
  ``klein predict adjudicate`` calls it for evidence the machine cannot read.
- :func:`findings_prediction_ids` reads section ② of ``findings.md`` so
  ``finalize`` can refuse a study that adjudicated a prediction and then never
  reported it.

The arithmetic itself lives in :mod:`kleinlib.decision` (``evaluate_rule`` /
``adjudicate``); nothing here decides a verdict on its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import registered_predictions
from .decision import VALID_VERDICTS, adjudicate
from .errors import WorkflowError
from .events import append_event
from .manifest import _artifact_path
from .primitives import sha256_file, utc_now

__all__ = [
    "EVIDENCE_ID_RE",
    "OPEN",
    "PREDICTIONS_SECTION_RE",
    "counts",
    "findings_prediction_ids",
    "findings_problems",
    "format_ledger",
    "ledger",
    "open_predictions",
    "pin_evidence",
    "record_run_adjudications",
    "record_verdict",
]

#: The absence of a record.  Never stored — it is what `ledger` reports for a
#: registered prediction the study has not decided.
OPEN = "open"

#: The evidence grammar of ``references/inquiry-model.md``.  Anything that does
#: NOT match is treated as a study-relative path and pinned by sha256.
EVIDENCE_ID_RE = re.compile(
    r"^(?:E\d{4,}|P\d+|sweep:\S+|rep:E\d{4,}@\S+|verify:E\d{4,}@\S+|ref:\S+|art:\S+|[A-Za-z0-9_.-]+#C\d+)$"
)

#: Findings section ② — the heading the synthesis protocol and
#: ``assets/findings-template.md`` write, with or without its parenthetical.
PREDICTIONS_SECTION_RE = re.compile(
    r"^\s{0,3}#{2,3}\s*②\s*Registered predictions\b.*$", re.IGNORECASE | re.MULTILINE
)

_PREDICTION_ID_IN_TEXT = re.compile(r"\bP\d+\b")


# ---------------------------------------------------------------------------
# reading the ledger
# ---------------------------------------------------------------------------


def _state_entry(state: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    entries = state.get("predictions")
    entry = entries.get(name) if isinstance(entries, Mapping) else None
    return entry if isinstance(entry, Mapping) else None


def _rule_text(rule: Any) -> str:
    """A rule as one readable line, for the table and for findings §②."""
    if not isinstance(rule, Mapping):
        return "manual"
    for combinator in ("all_of", "any_of"):
        if combinator in rule:
            children = rule[combinator]
            inner = ", ".join(_rule_text(item) for item in children) if isinstance(
                children, Sequence
            ) and not isinstance(children, str) else "…"
            return f"{combinator}({inner})"
    if "not" in rule:
        return f"not({_rule_text(rule['not'])})"
    op = str(rule.get("op", rule.get("operator", "?")))
    parts = [str(rule.get("key", "?")), op, str(rule.get("value", ""))]
    for extra in ("tol", "target", "low", "high"):
        if extra in rule:
            parts.append(f"{extra}={rule[extra]}")
    return " ".join(part for part in parts if part)


def ledger(contract: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every registered prediction with its current verdict, in contract order.

    The CONTRACT is the register — a verdict in state for an id the contract
    does not register is not listed here (it would be a belief with no
    pre-registration, which is the thing the ledger exists to prevent).
    """
    rows: list[dict[str, Any]] = []
    for name, entry in registered_predictions(contract).items():
        recorded = _state_entry(state, name) or {}
        rows.append(
            {
                "id": name,
                "track": entry.get("track"),
                "statement": str(entry.get("statement", "")),
                "rule": _rule_text(entry.get("rule")),
                "manual": entry.get("rule") is None,
                "verdict": str(recorded.get("verdict", OPEN)),
                "source": recorded.get("source"),
                "evidence": list(recorded.get("evidence", ())),
                "explanation": recorded.get("explanation"),
                "note": recorded.get("note"),
                "acknowledged_by": recorded.get("acknowledged_by"),
                "recorded_at": recorded.get("recorded_at"),
                "artifacts": dict(recorded.get("artifacts", {})),
                "revisions": len(recorded.get("history", ()) or ()),
            }
        )
    return rows


def counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """``supported / refuted / inconclusive / open`` — the referee's four numbers."""
    tally = {"supported": 0, "refuted": 0, "inconclusive": 0, OPEN: 0}
    for row in rows:
        verdict = str(row.get("verdict", OPEN))
        tally[verdict] = tally.get(verdict, 0) + 1
    return tally


def open_predictions(contract: Mapping[str, Any], state: Mapping[str, Any]) -> list[str]:
    """The ids with no verdict — what ``finalize`` refuses to close over."""
    return [row["id"] for row in ledger(contract, state) if row["verdict"] == OPEN]


def format_ledger(rows: Sequence[Mapping[str, Any]]) -> str:
    """The human table `klein predict list` prints (and findings §② copies)."""
    if not rows:
        return "no predictions registered in study.yaml\n"
    widths = {
        "id": max(2, *(len(row["id"]) for row in rows)),
        "verdict": max(7, *(len(str(row["verdict"])) for row in rows)),
        "evidence": max(8, *(len(", ".join(row["evidence"]) or "—") for row in rows)),
    }
    lines = [
        f"{'P#'.ljust(widths['id'])}  {'verdict'.ljust(widths['verdict'])}  "
        f"{'evidence'.ljust(widths['evidence'])}  statement"
    ]
    for row in rows:
        evidence = ", ".join(row["evidence"]) or "—"
        lines.append(
            f"{row['id'].ljust(widths['id'])}  "
            f"{str(row['verdict']).ljust(widths['verdict'])}  "
            f"{evidence.ljust(widths['evidence'])}  {row['statement']}"
        )
        detail = row.get("explanation") or row.get("note")
        if detail:
            lines.append(f"{' ' * widths['id']}  {detail}")
    tally = counts(rows)
    lines.append(
        f"summary: {tally['supported']} supported, {tally['refuted']} refuted, "
        f"{tally['inconclusive']} inconclusive, {tally[OPEN]} open"
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# writing the ledger
# ---------------------------------------------------------------------------


def pin_evidence(study_dir: Path, evidence: Sequence[str]) -> tuple[list[str], dict[str, dict]]:
    """Split evidence into ids and study-relative PATHS pinned by sha256.

    A sidecar TSV cited as evidence is only evidence if the bytes behind it are
    named: the id grammar of ``references/inquiry-model.md`` resolves on its
    own, everything else is a path that must exist and gets its digest recorded
    beside the verdict.
    """
    ids: list[str] = []
    pinned: dict[str, dict] = {}
    for raw in evidence:
        token = raw.strip()
        if not token:
            continue
        if EVIDENCE_ID_RE.match(token):
            if token not in ids:
                ids.append(token)
            continue
        path = _artifact_path(study_dir, token)
        if not path.is_file():
            raise WorkflowError(
                f"evidence {token!r} is neither an evidence id (E####, sweep:<name>, "
                "rep:/verify:, ref:<key>, art:<alias>, P#) nor a file inside the study"
            )
        rel = Path(token).as_posix()
        pinned[rel] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        if rel not in ids:
            ids.append(rel)
    return ids, pinned


def record_verdict(
    study_dir: Path,
    state: dict[str, Any],
    name: str,
    *,
    verdict: str,
    explanation: str,
    source: str,
    evidence: Sequence[str] = (),
    artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    note: str | None = None,
    acknowledged_by: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Write one verdict into ``state`` and append its ``prediction_adjudicated``.

    The current verdict lives at the top of the entry and every verdict ever
    recorded lives in ``history``, which only ever grows: a belief that was
    supported by a development run and refuted by the sealed one is a study's
    most valuable page, and overwriting the first record would erase it.

    The caller owns the state WRITE (``run-one`` folds it into the run
    transaction; the CLI verb self-commits) — this function mutates the dict and
    files the event, nothing else.
    """
    if verdict not in VALID_VERDICTS:
        raise WorkflowError(
            f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r} "
            "(there is no 'open' verdict — open is the absence of a record)"
        )
    record: dict[str, Any] = {
        "verdict": verdict,
        "source": source,
        "evidence": list(evidence),
        "explanation": explanation,
        "recorded_at": utc_now(),
    }
    for key, value in (
        ("note", note),
        ("acknowledged_by", acknowledged_by),
        ("reason", reason),
    ):
        if value:
            record[key] = value
    if artifacts:
        record["artifacts"] = {rel: dict(meta) for rel, meta in artifacts.items()}
    entry = state.setdefault("predictions", {}).setdefault(name, {})
    history = entry.get("history")
    if not isinstance(history, list):
        history = []
    entry.update(record)
    entry["history"] = [*history, dict(record)]
    append_event(
        study_dir,
        "prediction_adjudicated",
        prediction=name,
        verdict=verdict,
        source=source,
        evidence=record["evidence"],
        explanation=explanation,
        **({"note": note} if note else {}),
        **({"acknowledged_by": acknowledged_by} if acknowledged_by else {}),
        **({"reason": reason} if reason else {}),
    )
    return entry


def record_run_adjudications(
    study_dir: Path,
    state: dict[str, Any],
    names: Sequence[str],
    *,
    contract: Mapping[str, Any],
    printed: Mapping[str, float],
    experiment: str,
) -> dict[str, dict[str, str]]:
    """Adjudicate every ``--tests`` id against one run's printed block.

    Returns the map that goes on the manifest (``{P#: {verdict, explanation}}``)
    — the run's own immutable receipt of what it decided, beside the state entry
    that carries the study-wide history.
    """
    registered = registered_predictions(contract)
    decided: dict[str, dict[str, str]] = {}
    for name in names:
        entry = registered.get(name)
        if entry is None:  # pragma: no cover - validated before the lock
            continue
        verdict, explanation = adjudicate(entry, printed)
        decided[name] = {"verdict": verdict, "explanation": explanation}
        record_verdict(
            study_dir,
            state,
            name,
            verdict=verdict,
            explanation=explanation,
            source="run",
            evidence=[experiment],
        )
    return decided


# ---------------------------------------------------------------------------
# findings §② — the report side of the ledger
# ---------------------------------------------------------------------------


def findings_prediction_ids(text: str) -> set[str]:
    """The ``P#`` ids that appear in findings' section ② table rows.

    The section is the one the synthesis protocol names
    (``## ② Registered predictions (from the ledger)``) and the rows are its
    markdown table: a prediction mentioned only in prose elsewhere has not been
    REPORTED, it has been alluded to.
    """
    found: set[str] = set()
    inside = False
    for line in text.splitlines():
        if PREDICTIONS_SECTION_RE.match(line):
            inside = True
            continue
        if inside and re.match(r"^\s{0,3}#{1,6}\s", line):
            break
        if inside and line.lstrip().startswith("|"):
            found.update(_PREDICTION_ID_IN_TEXT.findall(line))
    return found


def findings_problems(
    study_dir: Path, contract: Mapping[str, Any], text: str
) -> list[str]:
    """Why findings.md does not yet report the register.  Empty means it does."""
    registered = set(registered_predictions(contract))
    if not registered:
        return []
    if not PREDICTIONS_SECTION_RE.search(text):
        return [
            "findings.md has no `## ② Registered predictions` section — every "
            f"registered prediction ({', '.join(sorted(registered))}) is reported "
            "there, verdict copied from the ledger (`klein predict list`)"
        ]
    missing = sorted(registered - findings_prediction_ids(text), key=_id_order)
    if missing:
        return [
            "findings.md §② does not report " + ", ".join(missing)
            + " — one table row per registered prediction, in id order"
        ]
    return []


def _id_order(name: str) -> tuple[int, str]:
    match = re.fullmatch(r"P(\d+)", name)
    return (int(match.group(1)), name) if match else (10**9, name)
