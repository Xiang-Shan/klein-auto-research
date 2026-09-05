"""The ``design`` capability — say what the evidence is FOR, before you have it.

Klein's five objects (``references/inquiry-model.md``) are enough to run a
study: a Question, a Prediction, Evidence, a Claim, a Decision.  They are not
enough to say what a number MEANS.  A metric that improved says nothing about
which quantity was estimated, on which population, under which identification
assumptions, how far the result was meant to travel, or which warrant carries it
to a claim.  Those commitments are cheap to write afterwards, in whatever shape
the result happened to take — which is exactly why they have to be written
first.

``evidence_design.yaml`` is that artifact: one document, five blocks, locked
into the extension chain **before the DATA gate**.  Before, because the DATA
gate is where the evidence source is first profiled, and a design registered
after the data has been looked at is a description, not a commitment.

1. **Question** — estimand, population, units, measurement process,
   identification assumptions, intended generalization.
2. **Prediction** — uncertainty method, validity conditions, practical
   threshold, provenance.  Each validity condition names a REGISTERED
   prediction (``P#``) whose rule can actually fire it.
3. **Evidence** — representations, dependency hierarchy, permitted reuse, the
   seal's holder and mechanism, and an acquisition ledger.
4. **Claim** — the warrant that carries the evidence to the claim, and the
   evidence ids that support it.
5. **Decision** — the typed continuation, and the predecessor/successor studies
   it links.

**The load-bearing rule is R-DES-2: a validity condition is executable or it is
decoration.**  ``validity_conditions[].rule_ref`` must name a prediction that
carries an ``inconclusive_if`` RULE, or whose ``rule`` is a combinator
(``all_of`` / ``any_of`` / ``not``).  A plain leaf comparison encodes "did the
number clear the bar", never "was this run in a position to answer at all"; a
prose ``inconclusive_if`` is a sidecar, and the whole point of the requirement
is that the condition reaches the arithmetic ``run-one`` actually runs.

**The second rule is R-BEN-3's neighbour: import chronology is not acquisition
chronology.**  An ``evidence.acquisition[]`` entry with ``kind: import`` records
when bytes arrived here, and needs nothing more.  One with ``kind:
acquisition`` claims when the measurement was TAKEN — a claim about the world
that Klein cannot check — so it must name a custody chain and an attestor, or it
is refused.

**What a locked design establishes.**  That these commitments predate the data
gate and have not changed since.  Not that the identification assumptions hold,
not that the estimand is the right one, not that the custody chain was honoured
— every one of those is a matter for the referee and for the reader.  The
capability outcome is exactly two words: ``locked`` or ``unlocked``.

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability` and the spine finds it through
:data:`kleinlib.generation.capabilities.MODULES`.
"""

from __future__ import annotations

import datetime as _datetime
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ..contract import PREDICTION_ID_RE, registered_predictions
from ..decision import COMBINATOR_KEYS
from ..errors import WorkflowError
from ..primitives import sha256_file
from ..transaction import relative
from .chronology import gate_events, introducing_commit, is_ancestor
from .envelope import GENERATION_SCHEMA
from .ledger import read_object
from .registry import Capability, FamilyContext
from .verify import Check

__all__ = [
    "ACQUISITION_KINDS",
    "BLOCKS",
    "CAPABILITY",
    "CAPABILITY_NAME",
    "CONTINUATIONS",
    "DESIGN_NAME",
    "LOCK_TYPE",
    "WARRANTS",
    "acquisition_problems",
    "design_problems",
    "document_problems",
    "encodes_a_condition",
    "lock_object",
    "locks",
    "parse_design",
    "rule_ref_problems",
]

CAPABILITY_NAME = "design"

#: The human artifact.  Study root, not ``generation/``: a design is meant to be
#: READ — by the referee, by the next study, by a stranger — and the lock is what
#: turns it from a description into a commitment.
DESIGN_NAME = "evidence_design.yaml"

LOCK_TYPE = "design_locked"

#: The five blocks, in the order A4's "minimal generalization" names them.
BLOCKS: tuple[str, ...] = ("question", "prediction", "evidence", "claim", "decision")

#: What carries the evidence to the claim (A4 "Claim").  The vocabulary is
#: closed on purpose: a warrant nobody can name is a warrant nobody can review.
WARRANTS: tuple[str, ...] = (
    "prediction",
    "conditional-estimation",
    "causal-inference",
    "exploratory-structure",
    "checked-witness",
)

#: How a piece of external evidence entered the study.  ``import`` = these bytes
#: arrived here then; ``acquisition`` = this measurement was TAKEN then — a
#: claim about the world, which is why it costs a custody chain and an attestor.
ACQUISITION_KINDS: tuple[str, ...] = ("import", "acquisition")

#: The typed continuation (A4 "Decision").
CONTINUATIONS: tuple[str, ...] = ("continue", "stop", "escalate", "pivot")

_QUESTION_TEXT: tuple[str, ...] = (
    "estimand",
    "population",
    "units",
    "measurement_process",
    "intended_generalization",
)
_PREDICTION_TEXT: tuple[str, ...] = ("uncertainty_method", "practical_threshold", "provenance")
_EVIDENCE_TEXT: tuple[str, ...] = ("dependency_hierarchy", "permitted_reuse")


# --------------------------------------------------------------------------
# the document
# --------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Coerce a YAML value into something ``canonical_json`` can hash.

    PyYAML resolves an unquoted ``2026-09-05`` to a ``date``, which JSON cannot
    carry — and ``acquired_at`` is exactly the field a driver writes unquoted.
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


def parse_design(path: Path) -> dict[str, Any]:
    """The design document as a plain, hashable mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"could not read {DESIGN_NAME}: {exc}") from exc
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkflowError(f"{DESIGN_NAME}: invalid YAML: {exc}") from exc
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{DESIGN_NAME} must contain a top-level mapping")
    return _plain(value)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _listing(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _text_list_problems(value: Any, label: str) -> list[str]:
    if not _listing(value) or not value:
        return [f"{label} must be a non-empty list"]
    return [
        f"{label}[{index}] must be a non-empty string"
        for index, item in enumerate(value, start=1)
        if not _text(item)
    ]


def _question_problems(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return ["question must be a mapping (estimand, population, units, …)"]
    problems = [
        f"question.{field} is required and must be a non-empty string"
        for field in _QUESTION_TEXT
        if not _text(block.get(field))
    ]
    problems.extend(
        _text_list_problems(
            block.get("identification_assumptions"),
            "question.identification_assumptions",
        )
    )
    return problems


def _prediction_problems(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return ["prediction must be a mapping (uncertainty_method, validity_conditions, …)"]
    problems = [
        f"prediction.{field} is required and must be a non-empty string"
        for field in _PREDICTION_TEXT
        if not _text(block.get(field))
    ]
    conditions = block.get("validity_conditions")
    if not _listing(conditions) or not conditions:
        return problems + [
            "prediction.validity_conditions must be a non-empty list of "
            "{condition, rule_ref} — a design with no condition claims the result is "
            "valid under every circumstance"
        ]
    for index, item in enumerate(conditions, start=1):
        label = f"prediction.validity_conditions[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{label} must be a mapping")
            continue
        if not _text(item.get("condition")):
            problems.append(f"{label}.condition must say, in words, when the result does not hold")
        ref = item.get("rule_ref")
        if not _text(ref) or not PREDICTION_ID_RE.fullmatch(str(ref).strip()):
            problems.append(f"{label}.rule_ref must name a registered prediction (P<number>)")
    return problems


def _evidence_problems(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return ["evidence must be a mapping (representations, dependency_hierarchy, …)"]
    problems = _text_list_problems(block.get("representations"), "evidence.representations")
    problems.extend(
        f"evidence.{field} is required and must be a non-empty string"
        for field in _EVIDENCE_TEXT
        if not _text(block.get(field))
    )
    seal = block.get("seal")
    if seal is not None:
        if not isinstance(seal, Mapping):
            problems.append("evidence.seal must be null or a mapping of {holder, mechanism}")
        else:
            problems.extend(
                f"evidence.seal.{field} must be a non-empty string"
                for field in ("holder", "mechanism")
                if not _text(seal.get(field))
            )
    if not _listing(block.get("acquisition")):
        problems.append(
            "evidence.acquisition must be a list (empty asserts that no evidence came "
            "from outside this study)"
        )
    return problems


def acquisition_problems(doc: Mapping[str, Any]) -> list[str]:
    """R-DES-1's custody half: an acquisition claim costs a chain and an attestor.

    ``import`` says bytes arrived; ``acquisition`` says a measurement was taken.
    The second is a statement about the world that no hash can check, so it is
    admitted only with a custody chain and a named attestor — and even then the
    record says who attested, never that the attestation is true.
    """
    evidence = doc.get("evidence")
    entries = evidence.get("acquisition") if isinstance(evidence, Mapping) else None
    if not _listing(entries):
        return []
    problems: list[str] = []
    for index, item in enumerate(entries, start=1):
        label = f"evidence.acquisition[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{label} must be a mapping")
            continue
        if not _text(item.get("source")):
            problems.append(f"{label}.source must name where the evidence came from")
        kind = item.get("kind")
        if kind not in ACQUISITION_KINDS:
            problems.append(
                f"{label}.kind {kind!r} must be one of {', '.join(ACQUISITION_KINDS)}"
            )
        if not _text(item.get("acquired_at")):
            problems.append(f"{label}.acquired_at must record when, as the source reports it")
        if kind != "acquisition":
            continue
        for field, why in (
            ("custody", "who held the evidence between the measurement and this study"),
            ("attested_by", "who attests that chain, by name"),
        ):
            if not _text(item.get(field)):
                problems.append(
                    f"{label}.{field} is required for kind: acquisition — {why}. "
                    "Import chronology does not prove acquisition chronology; record it "
                    "as kind: import if only the arrival of the bytes is known"
                )
    return problems


def _claim_problems(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return ["claim must be a mapping (warrant, supporting_evidence)"]
    problems: list[str] = []
    if block.get("warrant") not in WARRANTS:
        problems.append(
            f"claim.warrant {block.get('warrant')!r} must be one of {', '.join(WARRANTS)}"
        )
    problems.extend(_text_list_problems(block.get("supporting_evidence"), "claim.supporting_evidence"))
    return problems


def _decision_problems(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        return ["decision must be a mapping (continuation, predecessor, successor)"]
    problems: list[str] = []
    if block.get("continuation") not in CONTINUATIONS:
        problems.append(
            f"decision.continuation {block.get('continuation')!r} must be one of "
            f"{', '.join(CONTINUATIONS)}"
        )
    for field in ("predecessor", "successor"):
        if field not in block:
            problems.append(f"decision.{field} is required (null when there is none)")
        elif block.get(field) is not None and not _text(block.get(field)):
            problems.append(f"decision.{field} must be a study id or null")
    return problems


def document_problems(doc: Mapping[str, Any], *, study: str) -> list[str]:
    """Every reason this document is not a well-formed evidence design.

    Shape only — the cross-check against ``study.yaml``'s registered predictions
    is :func:`rule_ref_problems`, and the acquisition ledger is
    :func:`acquisition_problems`, because each is reported as its own verify
    check.
    """
    problems: list[str] = []
    if doc.get("type") != "evidence-design":
        problems.append(f"type must be 'evidence-design', got {doc.get('type')!r}")
    if doc.get("study") != study:
        problems.append(f"study is {doc.get('study')!r}, expected {study!r}")
    unknown = set(doc) - {"type", "study", *BLOCKS}
    if unknown:
        problems.append(f"unknown top-level keys {sorted(unknown)}")
    problems.extend(_question_problems(doc.get("question")))
    problems.extend(_prediction_problems(doc.get("prediction")))
    problems.extend(_evidence_problems(doc.get("evidence")))
    problems.extend(_claim_problems(doc.get("claim")))
    problems.extend(_decision_problems(doc.get("decision")))
    return problems


# --------------------------------------------------------------------------
# R-DES-2 — a validity condition is executable, or it is decoration
# --------------------------------------------------------------------------


def encodes_a_condition(prediction: Mapping[str, Any]) -> bool:
    """Can this registered prediction express "this run could not answer"?

    Two shapes can.  An ``inconclusive_if`` RULE is checked before the rule and
    returns ``inconclusive`` when it fires — literally the pre-registered
    admission that some runs cannot decide the question.  A combinator ``rule``
    (``all_of`` / ``any_of`` / ``not``) carries its own conjuncts, so a validity
    condition can be one of them.

    A plain leaf comparison cannot: it asks "did the number clear the bar", and
    a bar cleared by a run that had no business answering is the failure mode
    the whole requirement exists to prevent.  A prose ``inconclusive_if`` cannot
    either — it documents a human condition the machine never sees, which is the
    sidecar B §3 rules out.
    """
    if isinstance(prediction.get("inconclusive_if"), Mapping):
        return True
    rule = prediction.get("rule")
    return isinstance(rule, Mapping) and bool(COMBINATOR_KEYS & set(rule))


def rule_ref_problems(contract: Mapping[str, Any], doc: Mapping[str, Any]) -> list[str]:
    """R-DES-2: every ``rule_ref`` resolves, and resolves to something executable."""
    block = doc.get("prediction")
    conditions = block.get("validity_conditions") if isinstance(block, Mapping) else None
    if not _listing(conditions):
        return []
    registered = registered_predictions(contract)
    problems: list[str] = []
    for index, item in enumerate(conditions, start=1):
        if not isinstance(item, Mapping):
            continue
        raw = item.get("rule_ref")
        if not _text(raw):
            continue
        ref = str(raw).strip()
        prediction = registered.get(ref)
        label = f"prediction.validity_conditions[{index}].rule_ref"
        if prediction is None:
            declared = ", ".join(sorted(registered)) or "none"
            problems.append(
                f"{label} names {ref!r}, which is not a registered prediction in "
                f"study.yaml (registered: {declared})"
            )
        elif not encodes_a_condition(prediction):
            problems.append(
                f"{label} names {ref!r}, whose rule cannot express a validity condition: "
                "a validity condition must reach the arithmetic, as an `inconclusive_if` "
                "rule or an all_of/any_of/not combinator. A plain leaf comparison asks "
                "only whether the number cleared the bar, and a prose `inconclusive_if` "
                "is a sidecar the machine never reads"
            )
    return problems


def design_problems(
    contract: Mapping[str, Any], doc: Mapping[str, Any], *, study: str
) -> list[str]:
    """Everything the lock refuses on, in one list."""
    return [
        *document_problems(doc, study=study),
        *acquisition_problems(doc),
        *rule_ref_problems(contract, doc),
    ]


# --------------------------------------------------------------------------
# reading the ledger
# --------------------------------------------------------------------------


def locks(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    """``[(event, lock object)]`` in chain order.

    An event whose object is unreadable is skipped here and reported by the
    spine's ``generation orphans`` family — one broken object must not blind
    every other check.
    """
    rows: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for event in events:
        if event.get("type") != LOCK_TYPE:
            continue
        sha = event.get("payload_sha256")
        if not isinstance(sha, str):
            continue
        try:
            rows.append((event, read_object(study_dir, sha)))
        except WorkflowError:
            continue
    return rows


# --------------------------------------------------------------------------
# admission rules
# --------------------------------------------------------------------------


def _rule_cell_needs_a_locked_design(ctx: Any) -> list[str]:
    """A registered cell measures something; the design says what.

    WP-06's discovery cells will add their own rules on top of this one.  The
    ordering matters more than the wording: a cell admitted before the design is
    locked is a measurement whose meaning was settled afterwards.
    """
    if ctx.action != "cell" and not ctx.cell:
        return []
    from .ledger import read_events

    if locks(ctx.study_dir, read_events(ctx.study_dir)):
        return []
    return [
        "the evidence design is not locked: run `klein generation design lock` before a "
        "cell admission, so the estimand, the validity conditions and the warrant "
        "precede the measurement that is supposed to satisfy them"
    ]


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _lock_order_problems(
    ctx: FamilyContext, first: tuple[Mapping[str, Any], dict[str, Any]]
) -> list[str]:
    """The lock must precede the DATA gate by BOTH sequence and ancestry.

    The DATA gate, not CONSULT: the design is about what the evidence will mean,
    and the first moment the evidence itself is looked at is the data gate's
    profile.  A design locked after it describes what was found.
    """
    gates = gate_events(ctx.core, "data")
    if not gates:
        return []
    event, _obj = first
    anchor = event.get("core_anchor")
    anchor_sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else None
    gate_sequence = gates[0].get("sequence")
    problems: list[str] = []
    if not isinstance(anchor_sequence, int) or not isinstance(gate_sequence, int):
        return ["the design lock anchor or the data gate record has no sequence"]
    if anchor_sequence >= gate_sequence:
        problems.append(
            f"the design lock is anchored at core sequence {anchor_sequence}, at or after "
            f"the data gate record (sequence {gate_sequence})"
        )
    repo = ctx.repo
    sha = event.get("payload_sha256")
    if repo is not None and isinstance(sha, str):
        from .chronology import study_event_commit

        lock_commit = introducing_commit(
            repo, relative(repo, ctx.study_dir / "generation" / "objects" / f"{sha}.json")
        )
        gate_hash = gates[0].get("event_hash")
        gate_commit = (
            study_event_commit(repo, ctx.study_dir, str(gate_hash))
            if isinstance(gate_hash, str)
            else None
        )
        if lock_commit is None:
            problems.append("the design lock object is not committed, so ancestry cannot be read")
        elif gate_commit is not None and not is_ancestor(repo, lock_commit, gate_commit):
            problems.append(
                f"the lock commit {lock_commit[:12]} is not an ancestor of the data "
                f"gate commit {gate_commit[:12]}"
            )
    return problems


def _lock_checks(
    ctx: FamilyContext, rows: list[tuple[Mapping[str, Any], dict[str, Any]]]
) -> list[Check]:
    name = "design lock"
    if not rows:
        return [
            _fail(
                name,
                f"{DESIGN_NAME} is not locked — `klein generation design lock` freezes the "
                "estimand, the validity conditions and the warrant before the DATA gate",
            )
        ]
    problems: list[str] = []
    if len(rows) > 1:
        problems.append(
            f"{len(rows)} design locks recorded — the design is locked once; a change "
            "is a successor study, not a second lock"
        )
    event, first = rows[0]
    if first.get("late"):
        problems.append(
            "the design was locked with --allow-late, after the data gate: a design "
            "registered once the evidence has been looked at is a description"
        )
    problems.extend(_lock_order_problems(ctx, rows[0]))

    path = ctx.study_dir / DESIGN_NAME
    if not path.is_file():
        problems.append(f"{DESIGN_NAME} is missing but a lock exists")
    else:
        current = sha256_file(path)
        if current != first.get("design_sha256"):
            problems.append(
                f"{DESIGN_NAME} sha256 {current[:12]}… does not match the lock "
                f"({str(first.get('design_sha256'))[:12]}…) — a locked design is not "
                "edited in place"
            )
    if problems:
        return [_fail(name, "; ".join(problems))]
    anchor = event.get("core_anchor")
    sequence = anchor.get("sequence") if isinstance(anchor, Mapping) else "?"
    return [
        _pass(
            name,
            f"{DESIGN_NAME} locked at core sequence {sequence}, before the data gate, "
            f"unchanged since ({str(first.get('design_sha256'))[:12]}…)",
        )
    ]


def _document_checks(doc: Mapping[str, Any] | None, study: str) -> list[Check]:
    name = "design document"
    if doc is None:
        return []
    problems = document_problems(doc, study=study)
    if problems:
        return [_fail(name, "; ".join(problems[:8]))]
    question = doc.get("question")
    assumptions = question.get("identification_assumptions") if isinstance(question, Mapping) else []
    claim = doc.get("claim")
    warrant = claim.get("warrant") if isinstance(claim, Mapping) else "?"
    return [
        _pass(
            name,
            f"five blocks complete; warrant {warrant!r}; "
            f"{len(assumptions) if _listing(assumptions) else 0} identification assumption(s)",
        )
    ]


def _acquisition_checks(doc: Mapping[str, Any] | None) -> list[Check]:
    name = "design acquisition"
    if doc is None:
        return []
    problems = acquisition_problems(doc)
    if problems:
        return [_fail(name, "; ".join(problems[:8]))]
    evidence = doc.get("evidence")
    entries = evidence.get("acquisition") if isinstance(evidence, Mapping) else []
    entries = list(entries) if _listing(entries) else []
    acquired = [e for e in entries if isinstance(e, Mapping) and e.get("kind") == "acquisition"]
    if not entries:
        return [_pass(name, "no external evidence declared")]
    return [
        _pass(
            name,
            f"{len(entries)} acquisition entr{'y' if len(entries) == 1 else 'ies'}; "
            f"{len(acquired)} attested acquisition(s), the rest imports "
            "(an import records arrival, never when the measurement was taken)",
        )
    ]


def _validity_conditions(doc: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """The design's validity conditions, or ``[]`` for anything unusable."""
    block = doc.get("prediction") if isinstance(doc, Mapping) else None
    raw = block.get("validity_conditions") if isinstance(block, Mapping) else None
    if not _listing(raw):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _condition_checks(ctx: FamilyContext, doc: Mapping[str, Any] | None) -> list[Check]:
    """R-DES-2, re-read against the contract AS IT IS NOW.

    The design's copy is frozen; ``study.yaml`` is not.  A prediction whose
    ``inconclusive_if`` was dropped after the lock leaves a validity condition
    pointing at a rule that can no longer express it — which is exactly the
    silent drift this check exists to catch.
    """
    name = "design conditions"
    if doc is None:
        return []
    problems = rule_ref_problems(ctx.contract, doc)
    if problems:
        return [_fail(name, "; ".join(problems[:4]))]
    refs = [
        str(item.get("rule_ref"))
        for item in _validity_conditions(doc)
        if _text(item.get("rule_ref"))
    ]
    return [
        _pass(
            name,
            f"{len(refs)} validity condition(s) reach the arithmetic: "
            + ", ".join(refs)
            + " each carry an inconclusive_if rule or a combinator",
        )
    ]


def verify_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``design`` family: is the design locked, intact, and still executable?"""
    from .manifest import study_id

    rows = locks(ctx.study_dir, list(ctx.events))
    doc = rows[0][1].get("document") if rows else None
    doc = doc if isinstance(doc, Mapping) else None

    checks = _lock_checks(ctx, rows)
    checks += _document_checks(doc, study_id(ctx.study_dir, ctx.contract))
    checks += _acquisition_checks(doc)
    checks += _condition_checks(ctx, doc)

    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return checks, {
        "integrity": integrity,
        "outcome": "locked" if rows else "unlocked",
        "validity_conditions": len(_validity_conditions(doc)),
    }


#: The registration.  Everything above is reachable only through this object.
CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(_rule_cell_needs_a_locked_design,),
    verify_family=verify_family,
)


# --------------------------------------------------------------------------
# object builder (used by the CLI; kept here so the shape lives with the rules)
# --------------------------------------------------------------------------


def lock_object(
    *,
    study: str,
    document: Mapping[str, Any],
    design_sha256: str,
    late: bool,
) -> dict[str, Any]:
    """The lock: the document VERBATIM, plus the hash of the bytes it came from.

    Verbatim because the verify family re-validates the design rather than
    trusting a recorded verdict, and re-validating a summary would only prove
    the summary.
    """
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "design_lock",
        "study": study,
        "design_path": DESIGN_NAME,
        "design_sha256": design_sha256,
        "document": _plain(document),
        "late": bool(late),
    }
