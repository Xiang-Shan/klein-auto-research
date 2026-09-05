"""The ``expertise`` capability — acquire the domain, then PROVE you acquired it.

Reading a field's literature and writing a card about it establishes nothing:
the card is prose, and prose is exactly what an agent is best at producing
without understanding.  This capability turns the card into a falsifiable
commitment in four moves:

1. **Lock** ``domain_card.md`` BEFORE CONSULT.  Its frontmatter names the
   pipeline, the metrics, the doctrine, the pitfalls, the incumbent, a
   ``method_shortlist`` that must precede METHOD, and — the load-bearing part —
   a ``baseline`` recipe with an implementation, a fixture, and numeric
   ``targets`` frozen at that moment.
2. **Execute** the baseline as an ordinary ``run-one`` transaction after METHOD,
   admitted with ``--action baseline``.  There is no off-notary path: the
   obligation is discharged through the same notary as every other run.
3. **Bind** that run: ``expert bind E0001`` reads the run's manifest, compares
   each printed metric with the target frozen at the lock, and records
   ``reproduced`` / ``mismatch`` / ``crash``.  The verdict is recorded either
   way — negative evidence is evidence — and until a ``reproduced`` bind exists
   no challenger run may be admitted.
4. **Repair, versioned.**  A failed reproduction is fixed by an ``expert
   repair`` object that names the changed files and their hashes, then a fresh
   ``--action repair`` run and a fresh bind.  **Targets never move.**  An amend
   that changes a target value, tolerance or key set is refused: lowering the
   bar you failed to clear is not a repair, it is a different study.

**What passing establishes.**  That THIS recipe, on THIS fixture, reproduces
THESE numbers.  Not representative domain expertise, not that the card's
doctrine is right, not that the shortlist was the right shortlist.  The
capability outcome says so in its own vocabulary: ``source-reconstructed`` when
the team reproduced it themselves, ``independent-review`` only when a reviewer
who is not the roster's experimenter attests it with a session receipt, and
``incomplete`` — an honest, label-eligible outcome — while the obligation is
still open.

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability` and the spine's admission and
verify machinery finds it through
:data:`kleinlib.generation.capabilities.MODULES`.
"""

from __future__ import annotations

import datetime as _datetime
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ..errors import WorkflowError
from ..manifest import load_manifests
from ..primitives import canonical_json, sha256_bytes, sha256_file
from ..references import REFERENCES_NAME, is_verified, load_references
from ..transaction import git_blob, relative
from .chronology import gate_events, introducing_commit, is_ancestor
from .envelope import GENERATION_SCHEMA
from .ledger import read_events, read_object
from .references import RECORD_DIR, load_record, record_path, record_problems
from .registry import Capability, FamilyContext
from .verify import Check

__all__ = [
    "CAPABILITY",
    "CAPABILITY_NAME",
    "CARD_NAME",
    "REVIEW_VALUES",
    "SOURCE_ROLES",
    "bind_verdict",
    "card_problems",
    "evaluate_targets",
    "latest",
    "lock_targets",
    "normalized_targets",
    "parse_card",
    "roster_actor",
    "roster_experimenter",
    "verifier_scripts",
]

CAPABILITY_NAME = "expertise"

#: The human artifact.  Study root, not ``generation/``: a domain card is meant
#: to be READ, and the lock is what makes it evidence.
CARD_NAME = "domain_card.md"

#: What a card source is cited FOR.  A source with no role is a bibliography
#: entry, not a foundation.
SOURCE_ROLES: tuple[str, ...] = ("doctrine", "pipeline", "metric", "incumbent", "pitfall")

#: How the baseline was reviewed, as DECLARED on the card.  The verify family
#: decides the outcome from the recorded reviews, never from this word.
REVIEW_VALUES: tuple[str, ...] = ("source-reconstructed", "independent")

#: The checkpoints that may discharge the obligation.  Both go through
#: ``run-one``; the distinction is only whether a repair preceded them.
BASELINE_CHECKPOINTS: tuple[str, ...] = ("baseline", "repair")

#: The checkpoints a CHALLENGER takes — the ones the open obligation blocks.
CHALLENGER_CHECKPOINTS: tuple[str, ...] = ("run", "sealed")

LOCK_TYPE = "expert_locked"
BIND_TYPE = "expert_bound"
REPAIR_TYPE = "expert_repair"
REVIEW_TYPE = "expert_reviewed"
REFERENCE_TYPE = "reference_recorded"

BIND_VERDICTS: tuple[str, ...] = ("reproduced", "mismatch", "crash")


# --------------------------------------------------------------------------
# the card
# --------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Coerce a YAML value into something ``canonical_json`` can hash.

    PyYAML resolves an unquoted ``2026-09-05`` to a ``date``, which JSON cannot
    carry.  Dates become their ISO strings so a locked frontmatter is a stable,
    hashable copy of what the card said.
    """
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (_datetime.date, _datetime.datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def parse_card(path: Path) -> tuple[dict[str, Any], str]:
    """``(frontmatter, body)`` for a card that opens with a YAML block."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"could not read {CARD_NAME}: {exc}") from exc
    if not text.startswith("---"):
        raise WorkflowError(
            f"{CARD_NAME} must open with a `---` YAML frontmatter block "
            "(assets/domain-card-template.md)"
        )
    end = text.find("\n---", 3)
    if end == -1:
        raise WorkflowError(f"{CARD_NAME}: the frontmatter block is not closed with `---`")
    try:
        value = yaml.safe_load(text[3:end])
    except yaml.YAMLError as exc:
        raise WorkflowError(f"{CARD_NAME}: invalid frontmatter YAML: {exc}") from exc
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{CARD_NAME}: the frontmatter must be a mapping")
    return _plain(value), text[end + 4 :]


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def normalized_targets(front: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The frozen targets in one canonical shape, or ``[]`` when unusable.

    Normalizing before comparing is what makes "the amend changed a target"
    decidable: ``tol: 0.01`` and ``tol: 1.0e-2`` are the same commitment, and
    an added ``rel: false`` is not a change.
    """
    baseline = front.get("baseline")
    raw = baseline.get("targets") if isinstance(baseline, Mapping) else None
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    targets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            return []
        key = item.get("key")
        value = _numeric(item.get("value"))
        tol = _numeric(item.get("tol"))
        if not isinstance(key, str) or value is None or tol is None:
            return []
        targets.append({"key": key, "value": value, "tol": tol, "rel": bool(item.get("rel"))})
    return targets


def lock_targets(lock: Mapping[str, Any]) -> list[dict[str, Any]]:
    front = lock.get("frontmatter")
    return normalized_targets(front) if isinstance(front, Mapping) else []


def _target_problems(front: Mapping[str, Any]) -> list[str]:
    baseline = front.get("baseline")
    if not isinstance(baseline, Mapping):
        return ["baseline must be a mapping (implementation, config, fixture, targets, review)"]
    raw = baseline.get("targets")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        return ["baseline.targets must be a non-empty list — a baseline with no number to hit is prose"]
    problems: list[str] = []
    for index, item in enumerate(raw, start=1):
        label = f"baseline.targets[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{label} must be a mapping")
            continue
        if not isinstance(item.get("key"), str) or not str(item.get("key")).strip():
            problems.append(f"{label}.key must be the printed metric key it reads")
        if _numeric(item.get("value")) is None:
            problems.append(f"{label}.value must be a number")
        tol = _numeric(item.get("tol"))
        if tol is None:
            problems.append(f"{label}.tol must be a number")
        elif tol < 0:
            problems.append(f"{label}.tol must be >= 0")
        if "rel" in item and not isinstance(item.get("rel"), bool):
            problems.append(f"{label}.rel must be a boolean")
    return problems


def card_problems(
    study_dir: Path, repo: Path | None, front: Mapping[str, Any], *, study: str
) -> list[str]:
    """Every reason this card cannot be locked, one line each."""
    problems: list[str] = []
    if front.get("type") != "domain-card":
        problems.append(f"type must be 'domain-card', got {front.get('type')!r}")
    declared = front.get("study")
    if declared != study:
        problems.append(f"study is {declared!r}, expected {study!r}")
    for field in ("scope", "as_of", "incumbent"):
        value = front.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{field} is required and must be a non-empty string")
    for field in ("pipeline_steps", "metrics", "method_shortlist"):
        value = front.get(field)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
            problems.append(
                f"{field} must be a non-empty list"
                + (
                    " — the shortlist precedes METHOD, so an empty one commits to nothing"
                    if field == "method_shortlist"
                    else ""
                )
            )
    for field in ("doctrine", "pitfalls", "unknowns"):
        value = front.get(field, [])
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            problems.append(f"{field} must be a list (it may be empty)")

    sources = front.get("sources")
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)) or not sources:
        problems.append("sources must be a non-empty list of {record_id, role}")
    else:
        for index, item in enumerate(sources, start=1):
            label = f"sources[{index}]"
            if not isinstance(item, Mapping):
                problems.append(f"{label} must be a mapping")
                continue
            record_id = item.get("record_id")
            if not isinstance(record_id, str) or not record_id.strip():
                problems.append(f"{label}.record_id is required")
            elif repo is None:
                problems.append(f"{label}: no git repository, so {RECORD_DIR} cannot be resolved")
            elif not record_path(repo, record_id).is_file():
                problems.append(
                    f"{label}.record_id {record_id!r} has no record at "
                    f"{RECORD_DIR}/{record_id}.json — record it with "
                    "`klein generation reference record` first"
                )
            if item.get("role") not in SOURCE_ROLES:
                problems.append(
                    f"{label}.role {item.get('role')!r} must be one of {', '.join(SOURCE_ROLES)}"
                )

    problems.extend(_target_problems(front))
    baseline = front.get("baseline")
    if isinstance(baseline, Mapping):
        for field in ("implementation", "fixture"):
            value = baseline.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"baseline.{field} must be a study-relative path")
            elif not (study_dir / value).exists():
                problems.append(
                    f"baseline.{field} names {value!r}, which does not exist in the study"
                )
        config = baseline.get("config")
        if not isinstance(config, (str, Mapping)) or (isinstance(config, str) and not config.strip()):
            problems.append("baseline.config must be a study-relative path or an inline mapping")
        if baseline.get("review") not in REVIEW_VALUES:
            problems.append(
                f"baseline.review {baseline.get('review')!r} must be one of "
                f"{', '.join(REVIEW_VALUES)}"
            )
    return problems


# --------------------------------------------------------------------------
# reading the ledger
# --------------------------------------------------------------------------


def joined(
    study_dir: Path, events: Sequence[Mapping[str, Any]], event_type: str
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """``[(event, object)]`` for one event type, in chain order.

    An event whose object is unreadable is skipped here and reported by the
    spine's ``generation orphans`` family — one broken object must not blind
    every other check.
    """
    rows: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for event in events:
        if event.get("type") != event_type:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            rows.append((event, read_object(study_dir, sha)))
        except WorkflowError:
            continue
    return rows


def latest(
    rows: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> tuple[Mapping[str, Any], dict[str, Any]] | None:
    return rows[-1] if rows else None


def _sequence(event: Mapping[str, Any]) -> int:
    return int(event.get("sequence") or 0)


def reproduced_bind(
    rows: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> tuple[Mapping[str, Any], dict[str, Any]] | None:
    """The FIRST bind that reproduced — the moment the obligation was discharged."""
    for event, obj in rows:
        if obj.get("verdict") == "reproduced":
            return event, obj
    return None


# --------------------------------------------------------------------------
# the arithmetic
# --------------------------------------------------------------------------


def evaluate_targets(
    targets: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """One row per frozen target, against the metric block the run PRINTED.

    ``rel`` reads the tolerance as a fraction of the target rather than an
    absolute distance, because a 1% tolerance on a loss of 1200 and on an AUC of
    0.71 are different numbers and both are legitimate.
    """
    rows: list[dict[str, Any]] = []
    for target in targets:
        key = str(target.get("key"))
        value = float(target.get("value"))
        tol = float(target.get("tol"))
        rel = bool(target.get("rel"))
        observed = _numeric(metrics.get(key))
        delta = None if observed is None else observed - value
        limit = tol * abs(value) if rel else tol
        rows.append(
            {
                "key": key,
                "value": value,
                "tol": tol,
                "rel": rel,
                "observed": observed,
                "delta": delta,
                "within": delta is not None and abs(delta) <= limit,
            }
        )
    return rows


def bind_verdict(disposition: str | None, rows: Sequence[Mapping[str, Any]]) -> str:
    """``crash`` beats ``mismatch`` beats ``reproduced`` — the honest order.

    A crashed run reproduced nothing, whatever its (absent) numbers say; a run
    with a missing target key mismatched, because a target nobody printed was
    not hit.
    """
    if disposition == "crash":
        return "crash"
    if not rows or any(not row.get("within") for row in rows):
        return "mismatch"
    return "reproduced"


# --------------------------------------------------------------------------
# the roster
# --------------------------------------------------------------------------


def verifier_scripts(contract: Mapping[str, Any]) -> set[str]:
    """Every study-relative script a track's declared verifier runs.

    A repair may touch ``lib/``, ``prepare.py``, anything — except the checker.
    "The checker is never the searcher" is a contract rule for the mutable
    surface; it is the same rule here, one layer out: repairing the thing that
    judges you until it agrees is not a repair.
    """
    from ..contract import normalize_tracks

    scripts: set[str] = set()
    for spec in normalize_tracks(contract).values():
        verifier = spec.get("verifier") if isinstance(spec, Mapping) else None
        command = verifier.get("command") if isinstance(verifier, Mapping) else None
        if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
            continue
        for item in command:
            if isinstance(item, str) and not item.startswith("-") and (
                item.endswith((".py", ".sh")) or "/" in item
            ):
                scripts.add(item)
    return scripts


def roster_actor(study_dir: Path, role: str) -> str | None:
    """One named row's cell of ``program.md``'s ``## Roster`` table.

    Testimony, exactly like the referee's independence rung: a self-reported
    string that says what played a role.  A blank or missing row returns None,
    and independence against that role then cannot be established — the same cap
    the referee protocol applies.  ``role`` is any row label the table carries
    (``experimenter``, ``referee``, …); the capabilities that read them differ,
    the parsing must not.
    """
    path = study_dir / "program.md"
    if not path.is_file():
        return None
    wanted = role.strip().lower()
    inside = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            inside = stripped.lower().startswith("## roster")
            continue
        if not inside or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and cells[0].lower() == wanted:
            return cells[1] or None
    return None


def roster_experimenter(study_dir: Path) -> str | None:
    """The ``experimenter`` cell — what the expertise rungs compare against."""
    return roster_actor(study_dir, "experimenter")


def _norm(value: str) -> str:
    return " ".join(value.split()).casefold()


def same_actor(name: str | None, roster_cell: str | None) -> bool:
    """Is this reviewer the experimenter, as far as the record can tell?

    String comparison, never authentication (``references/generation-protocol.md``
    "what this does NOT establish").  The roster cell is a
    ``model · tool · session`` triple, so a reviewer naming any ONE of those
    components counts as the same actor — a strictly more conservative reading
    than whole-cell inequality, and the conservative direction is the safe one.
    """
    if not name or not roster_cell:
        return False
    left = _norm(name)
    if not left:
        return False
    parts = [_norm(part) for part in re.split(r"[·|/,]", roster_cell)]
    return left == _norm(roster_cell) or left in [part for part in parts if part]


# --------------------------------------------------------------------------
# admission rules (registered into the spine, never appended to its list)
# --------------------------------------------------------------------------


def _rule_baseline_needs_a_locked_card(ctx: Any) -> list[str]:
    if ctx.action != "baseline":
        return []
    events = read_events(ctx.study_dir)
    if joined(ctx.study_dir, events, LOCK_TYPE):
        return []
    return [
        "the domain card is not locked: run `klein generation expert lock` before a "
        "baseline admission, so the targets are frozen before the run that must hit them"
    ]


def _rule_repair_needs_a_repair_object(ctx: Any) -> list[str]:
    if ctx.action != "repair":
        return []
    events = read_events(ctx.study_dir)
    repairs = joined(ctx.study_dir, events, REPAIR_TYPE)
    binds = joined(ctx.study_dir, events, BIND_TYPE)
    if not binds:
        return ["a repair admission requires a bound baseline run that did not reproduce"]
    last_bind = _sequence(binds[-1][0])
    if any(_sequence(event) > last_bind for event, _obj in repairs):
        return []
    return [
        "no `expert repair` object was recorded after the last bind: a repair run must "
        "name the files it changed before it runs"
    ]


def _rule_challenger_needs_a_reproduced_baseline(ctx: Any) -> list[str]:
    if ctx.action not in CHALLENGER_CHECKPOINTS and not ctx.hypothesis:
        return []
    events = read_events(ctx.study_dir)
    if reproduced_bind(joined(ctx.study_dir, events, BIND_TYPE)):
        return []
    return [
        "baseline obligation open: no `expert bind` with verdict reproduced — "
        "reproduce the locked baseline (repairing it if needed) before a challenger runs"
    ]


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _card_checks(ctx: FamilyContext, locks: list[tuple[Mapping[str, Any], dict[str, Any]]]) -> list[Check]:
    name = "expert card"
    if not locks:
        return [
            _fail(
                name,
                f"{CARD_NAME} is not locked — `klein generation expert lock` freezes the "
                "card and its baseline targets before CONSULT",
            )
        ]
    problems: list[str] = []
    warnings: list[str] = []
    # Only VERSION 1 must precede CONSULT — it is the commitment.  Every
    # amendment follows the gate by construction, so failing it would make
    # `expert amend` a verb that guarantees failure; a late amendment is
    # LABELLED (R-ADM-8: scope only grows, late additions are labelled).
    if locks[0][1].get("late"):
        problems.append(
            "lock version 1 was recorded with --allow-late, after the consult gate: "
            "the commitment cannot precede what it constrains"
        )
    for _event, obj in locks[1:]:
        if obj.get("late"):
            warnings.append(f"version {obj.get('version')}")
    problems.extend(_lock_order_problems(ctx, locks[0]))

    _event, newest = locks[-1]
    card = ctx.study_dir / CARD_NAME
    if not card.is_file():
        problems.append(f"{CARD_NAME} is missing but a lock exists")
    else:
        current = sha256_file(card)
        if current != newest.get("card_sha256"):
            problems.append(
                f"{CARD_NAME} sha256 {current[:12]}… does not match lock version "
                f"{newest.get('version')} ({str(newest.get('card_sha256'))[:12]}…) — "
                "a locked card is amended with `expert amend`, never edited in place"
            )

    first_targets = canonical_json(lock_targets(locks[0][1]))
    for _event, obj in locks[1:]:
        if canonical_json(lock_targets(obj)) != first_targets:
            problems.append(
                f"lock version {obj.get('version')} changed baseline.targets — targets are "
                "frozen at version 1; a target change requires a successor study"
            )
    checks: list[Check] = []
    if problems:
        checks.append(_fail(name, "; ".join(problems)))
    else:
        checks.append(
            _pass(
                name,
                f"{CARD_NAME} locked at version {newest.get('version')} (v1 before the "
                f"consult gate); {len(lock_targets(newest))} target(s) frozen",
            )
        )
    if warnings:
        checks.append(
            _warn(
                name,
                "amended after the consult gate: "
                + ", ".join(warnings)
                + " — lawful, and labelled: the targets are still version 1's",
            )
        )
    return checks


def _lock_order_problems(
    ctx: FamilyContext, first: tuple[Mapping[str, Any], dict[str, Any]]
) -> list[str]:
    """The lock must precede the consult gate by BOTH sequence and ancestry."""
    consult = gate_events(ctx.core, "consult")
    if not consult:
        return []
    event, _obj = first
    anchor = event.get("core_anchor")
    anchor_sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    gate_sequence = consult[0].get("sequence")
    problems: list[str] = []
    if not isinstance(anchor_sequence, int) or not isinstance(gate_sequence, int):
        return ["the lock anchor or the consult gate record has no sequence"]
    if anchor_sequence >= gate_sequence:
        problems.append(
            f"the expert lock is anchored at core sequence {anchor_sequence}, at or after "
            f"the consult gate record (sequence {gate_sequence})"
        )
    repo = ctx.repo
    sha = event.get("payload_sha256")
    if repo is not None and isinstance(sha, str):
        from .chronology import study_event_commit

        lock_commit = introducing_commit(
            repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{sha}.json")
        )
        gate_hash = consult[0].get("event_hash")
        gate_commit = (
            study_event_commit(repo, ctx.study_dir, str(gate_hash))
            if isinstance(gate_hash, str)
            else None
        )
        if lock_commit is None:
            problems.append("the expert lock object is not committed, so ancestry cannot be read")
        elif gate_commit is not None and not is_ancestor(repo, lock_commit, gate_commit):
            problems.append(
                f"the lock commit {lock_commit[:12]} is not an ancestor of the consult "
                f"gate commit {gate_commit[:12]}"
            )
    return problems


def _reference_checks(
    ctx: FamilyContext,
    locks: list[tuple[Mapping[str, Any], dict[str, Any]]],
    records: list[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    name = "expert references"
    repo = ctx.repo
    if repo is None:
        return [_warn(name, f"not a git repository; {RECORD_DIR} cannot be resolved")]
    problems: list[str] = []
    seen: set[str] = set()

    if locks:
        front = locks[-1][1].get("frontmatter")
        sources = front.get("sources") if isinstance(front, Mapping) else None
        if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
            for item in sources:
                record_id = item.get("record_id") if isinstance(item, Mapping) else None
                if isinstance(record_id, str):
                    seen.add(record_id)
                    if not record_path(repo, record_id).is_file():
                        problems.append(
                            f"card source {record_id!r} has no record at "
                            f"{RECORD_DIR}/{record_id}.json"
                        )

    for _event, link in records:
        record_id = link.get("record_id")
        if not isinstance(record_id, str):
            continue
        seen.add(record_id)
        path = record_path(repo, record_id)
        if not path.is_file():
            problems.append(f"reference record {record_id!r} was recorded but the file is gone")
            continue
        if sha256_bytes(path.read_bytes()) != link.get("record_sha256"):
            problems.append(
                f"reference record {record_id!r} changed since it was recorded — "
                "records are write-once; a correction is a NEW id"
            )

    for record_id in sorted(seen):
        try:
            record = load_record(repo, record_id)
        except WorkflowError as exc:
            problems.append(str(exc))
            continue
        if record is None:
            continue
        for problem in record_problems(record):
            problems.append(f"record {record_id}: {problem}")

    problems.extend(_references_yaml_problems(ctx.study_dir, repo))
    if problems:
        return [_fail(name, "; ".join(problems[:8]))]
    return [
        _pass(
            name,
            f"{len(seen)} reference record(s) resolve, hash as recorded, and satisfy their "
            "verification basis",
        )
    ]


def _references_yaml_problems(study_dir: Path, repo: Path) -> list[str]:
    """R-EXP-2: on an enabled study a bare ``verified: true`` is not enough."""
    if not (study_dir / REFERENCES_NAME).is_file():
        return []
    try:
        entries = load_references(study_dir)
    except WorkflowError as exc:
        return [str(exc)]
    problems: list[str] = []
    for key, entry in sorted(entries.items()):
        if not is_verified(entry):
            continue
        record_id = entry.get("record_id") if isinstance(entry, Mapping) else None
        if not isinstance(record_id, str) or not record_id.strip():
            problems.append(
                f"{REFERENCES_NAME}: {key} says `verified: true` with no `record_id` — a bare "
                "`verified: true` is insufficient for a generation-enabled study"
            )
        elif not record_path(repo, record_id).is_file():
            problems.append(
                f"{REFERENCES_NAME}: {key} names record_id {record_id!r}, which has no record"
            )
    return problems


def _consumed_receipt(ctx: FamilyContext, run: str) -> Any:
    for sha, consumer in ctx.match.consumed.items():
        if consumer == run:
            return next((receipt for receipt in ctx.receipts if receipt.sha == sha), None)
    return None


def _obligation_checks(
    ctx: FamilyContext,
    locks: list[tuple[Mapping[str, Any], dict[str, Any]]],
    binds: list[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    name = "expert obligation"
    checks: list[Check] = []
    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(ctx.study_dir)}
    except WorkflowError as exc:
        return [_fail(name, f"run manifests unreadable: {exc}")]

    for event, obj in binds:
        problems = _bind_problems(ctx, event, obj, manifests)
        detail = f"{obj.get('run')}: {obj.get('verdict')}"
        checks.append(_fail(name, f"{detail} — " + "; ".join(problems)) if problems else _pass(name, detail))

    checks.extend(_challenger_checks(ctx, binds))
    if not locks:
        return checks
    if not binds:
        checks.append(
            _warn(
                name,
                "the baseline obligation is open: no `expert bind` yet — an honestly "
                "incomplete study is label-eligible, an unadmitted challenger is not",
            )
        )
    return checks


def _bind_problems(
    ctx: FamilyContext,
    event: Mapping[str, Any],
    obj: Mapping[str, Any],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    problems: list[str] = []
    run = obj.get("run")
    manifest = manifests.get(str(run))
    if manifest is None:
        return [f"no run manifest for {run!r}"]

    receipt = _consumed_receipt(ctx, str(run))
    if receipt is None:
        problems.append(
            f"{run} consumed no admission receipt, so it cannot discharge the obligation"
        )
    elif receipt.checkpoint not in BASELINE_CHECKPOINTS:
        problems.append(
            f"{run} was admitted as {receipt.checkpoint!r}; only "
            f"{' or '.join(BASELINE_CHECKPOINTS)} discharges the obligation"
        )

    lock_sha = obj.get("lock_object")
    try:
        lock = read_object(ctx.study_dir, str(lock_sha)) if isinstance(lock_sha, str) else None
    except WorkflowError as exc:
        lock = None
        problems.append(f"lock object {str(lock_sha)[:12]}… unreadable: {exc}")
    if lock is None:
        problems.append("the bind names no readable lock object")
        return problems

    metrics = manifest.get("metrics")
    rows = evaluate_targets(lock_targets(lock), metrics if isinstance(metrics, Mapping) else {})
    verdict = bind_verdict(str(manifest.get("disposition")), rows)
    if canonical_json(rows) != canonical_json(obj.get("targets") or []):
        problems.append("the recorded target arithmetic does not recompute from the run manifest")
    if verdict != obj.get("verdict"):
        problems.append(
            f"the recorded verdict {obj.get('verdict')!r} recomputes as {verdict!r}"
        )
    return problems


def _challenger_checks(
    ctx: FamilyContext, binds: list[tuple[Mapping[str, Any], dict[str, Any]]]
) -> list[Check]:
    """No challenger may be ADMITTED before the obligation is discharged.

    Order is read on the extension chain — the tightest of the three witnesses
    for two events that both live in it — so a receipt written between the
    failing run and its repair is caught even when no core event separates them.
    """
    name = "expert obligation"
    discharged = reproduced_bind(binds)
    threshold = _sequence(discharged[0]) if discharged else None
    offenders: list[str] = []
    for event in ctx.events:
        if event.get("type") != "admission_checked" or event.get("verdict") != "admitted":
            continue
        sha = event.get("payload_sha256")
        try:
            receipt = read_object(ctx.study_dir, str(sha)) if isinstance(sha, str) else None
        except WorkflowError:
            continue
        if receipt is None:
            continue
        intended = receipt.get("intended_action")
        hypothesis = intended.get("hypothesis_id") if isinstance(intended, Mapping) else None
        if receipt.get("checkpoint") not in CHALLENGER_CHECKPOINTS and not hypothesis:
            continue
        if threshold is None or _sequence(event) < threshold:
            offenders.append(f"{event.get('id')} ({receipt.get('checkpoint')})")
    if not offenders:
        if discharged:
            return [
                _pass(
                    name,
                    f"the obligation was discharged by {discharged[1].get('run')} before any "
                    "challenger was admitted",
                )
            ]
        return []
    return [
        _fail(
            name,
            "challenger admission(s) recorded while the baseline obligation was open: "
            + ", ".join(offenders),
        )
    ]


def _repair_checks(
    ctx: FamilyContext,
    repairs: list[tuple[Mapping[str, Any], dict[str, Any]]],
    binds: list[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    name = "expert repairs"
    if not repairs:
        return []
    if ctx.repo is None:
        return [_warn(name, "not a git repository; repaired files cannot be read at a commit")]
    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(ctx.study_dir)}
    except WorkflowError as exc:
        return [_fail(name, f"run manifests unreadable: {exc}")]
    problems: list[str] = []
    checked = 0
    for event, obj in repairs:
        after = _sequence(event)
        following = next(((e, o) for e, o in binds if _sequence(e) > after), None)
        if following is None:
            continue
        run = manifests.get(str(following[1].get("run")))
        candidate = run.get("candidate_commit") if isinstance(run, Mapping) else None
        if not isinstance(candidate, str):
            problems.append(f"repair {obj.get('version')}: the next bound run has no candidate commit")
            continue
        for entry in obj.get("changed_files") or ():
            if not isinstance(entry, Sequence) or isinstance(entry, (str, bytes)) or len(entry) != 2:
                problems.append(f"repair {obj.get('version')}: malformed changed_files entry")
                continue
            path, recorded = entry
            blob = git_blob(ctx.repo, candidate, relative(ctx.repo, ctx.study_dir / str(path)))
            if blob is None:
                problems.append(
                    f"repair {obj.get('version')}: {path} is absent from {candidate[:12]}"
                )
            elif sha256_bytes(blob) != recorded:
                problems.append(
                    f"repair {obj.get('version')}: {path} at {candidate[:12]} is not the file "
                    "the repair recorded"
                )
            checked += 1
    if problems:
        return [_fail(name, "; ".join(problems[:8]))]
    return [
        _pass(
            name,
            f"{len(repairs)} repair(s); {checked} changed file(s) match the candidate commit of "
            "the run that followed them",
        )
    ]


def _review_checks(
    ctx: FamilyContext, reviews: list[tuple[Mapping[str, Any], dict[str, Any]]]
) -> tuple[list[Check], bool]:
    """``(checks, independent)`` — the review rung, and why it is what it is."""
    name = "expert review"
    if not reviews:
        return [], False
    experimenter = roster_experimenter(ctx.study_dir)
    checks: list[Check] = []
    independent = False
    for _event, obj in reviews:
        reviewer = obj.get("reviewer")
        reviewer = reviewer if isinstance(reviewer, Mapping) else {}
        who = reviewer.get("name")
        receipt = reviewer.get("session_receipt")
        if not receipt:
            checks.append(
                _warn(
                    name,
                    f"review by {who!r} carries no session receipt — testimony without an "
                    "artefact keeps the outcome at source-reconstructed",
                )
            )
            continue
        if same_actor(str(who) if who else None, experimenter):
            checks.append(
                _warn(
                    name,
                    f"reviewer {who!r} matches the roster experimenter {experimenter!r} — a "
                    "review by the actor under review raises no rung",
                )
            )
            continue
        if experimenter is None:
            checks.append(
                _warn(
                    name,
                    f"review by {who!r} has a session receipt but program.md's roster names no "
                    "experimenter, so independence cannot be established",
                )
            )
            continue
        independent = True
        checks.append(
            _pass(name, f"independent review by {who!r} with session receipt {str(receipt)[:12]}…")
        )
    return checks, independent


def verify_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``expert`` family: integrity of the record, and the review rung."""
    events = list(ctx.events)
    locks = joined(ctx.study_dir, events, LOCK_TYPE)
    binds = joined(ctx.study_dir, events, BIND_TYPE)
    repairs = joined(ctx.study_dir, events, REPAIR_TYPE)
    reviews = joined(ctx.study_dir, events, REVIEW_TYPE)
    records = joined(ctx.study_dir, events, REFERENCE_TYPE)

    checks: list[Check] = []
    checks += _card_checks(ctx, locks)
    checks += _reference_checks(ctx, locks, records)
    checks += _obligation_checks(ctx, locks, binds)
    checks += _repair_checks(ctx, repairs, binds)
    review_checks, independent = _review_checks(ctx, reviews)
    checks += review_checks

    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    if reproduced_bind(binds) is None:
        outcome = "incomplete"
    elif independent:
        outcome = "independent-review"
    else:
        outcome = "source-reconstructed"
    return checks, {"integrity": integrity, "outcome": outcome, "repairs": len(repairs)}


#: The registration.  Everything above is reachable only through this object.
CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(
        _rule_baseline_needs_a_locked_card,
        _rule_repair_needs_a_repair_object,
        _rule_challenger_needs_a_reproduced_baseline,
    ),
    verify_family=verify_family,
)


# --------------------------------------------------------------------------
# object builders (used by the CLI; kept here so the shapes live with the rules)
# --------------------------------------------------------------------------


def lock_object(
    *,
    study: str,
    version: int,
    frontmatter: Mapping[str, Any],
    card_sha256: str,
    parent_ids: Sequence[str],
    late: bool,
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "expert_lock",
        "study": study,
        "version": version,
        "card_path": CARD_NAME,
        "card_sha256": card_sha256,
        "frontmatter": _plain(frontmatter),
        "parent_ids": list(parent_ids),
        "late": bool(late),
    }


def bind_object(
    *,
    study: str,
    run: str,
    checkpoint: str,
    verdict: str,
    targets: Sequence[Mapping[str, Any]],
    lock_sha: str,
    repair_sha: str | None,
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "expert_bind",
        "study": study,
        "run": run,
        "checkpoint": checkpoint,
        "verdict": verdict,
        "targets": [dict(row) for row in targets],
        "lock_object": lock_sha,
        "repair_object": repair_sha,
    }


def repair_object(
    *,
    study: str,
    version: int,
    parent_ids: Sequence[str],
    changed_files: Sequence[Sequence[Any]],
    note: str,
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "expert_repair",
        "study": study,
        "version": version,
        "parent_ids": list(parent_ids),
        "changed_files": [list(entry) for entry in changed_files],
        "note": note,
    }


def review_object(
    *,
    study: str,
    name: str,
    model: str | None,
    tool: str | None,
    session_receipt: str | None,
    statement: str,
    lock_sha: str,
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "expert_review",
        "study": study,
        "reviewer": {
            "name": name,
            "model": model,
            "tool": tool,
            "session_receipt": session_receipt,
        },
        "statement": statement,
        "lock_object": lock_sha,
    }


def reference_link_object(*, study: str, record_id: str, record_sha256: str) -> dict[str, Any]:
    """The STUDY's copy of "this study rests on that record".

    The record itself is repo-level; this object is what puts it in the study's
    own chain, so a later edit of the record file is detectable from the study.
    """
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "reference_link",
        "study": study,
        "record_id": record_id,
        "record_sha256": record_sha256,
    }
