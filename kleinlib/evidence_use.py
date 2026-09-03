"""The 2026 failure modes, as arithmetic on the receipt (plan item D14).

Three things a study can do that no existing check catches, because each is an
ABSENCE rather than a broken invariant:

1. **Ignored evidence.**  A run that discarded, crashed or measured is evidence;
   a registered measurement sweep is evidence.  A study that never mentions one
   again has quietly filtered its own record.  :func:`evidence_use` counts what
   fraction of the non-keep ledger and the sweep registry is cited in
   ``program.md`` or ``findings.md`` — ``evidence_use_rate``.
2. **Refutation without revision.**  A prediction adjudicated ``refuted`` whose
   program never records a decision is a belief that was contradicted and then
   left standing.  Belief revision is a recorded act, so the law asks for a
   dated ``Decision:`` line naming the id.
3. **Single-source confirmation.**  A claim whose ``strength`` is ``confirmed``
   on one kind of evidence is confirmed by one look at one number.  Convergent
   evidence means at least two of: a development run, a sealed final test, a
   replication (``rep:``), a re-verification (``verify:``).

Everything here is read-only and returns findings; ``checks.py`` decides which
become ``[WARN]`` and which become failures, and ``klein status`` prints the
three numbers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .claims import claims_map, detect_lock_schema, lock_path
from .predictions import ledger as prediction_ledger

__all__ = [
    "CITATION_SOURCES",
    "DECISION_DATE_WINDOW",
    "DECISION_LINE_RE",
    "EvidenceUse",
    "NON_KEEP_DISPOSITIONS",
    "decided_prediction_ids",
    "evidence_use",
]

#: The dispositions that are evidence but never a frontier move.  ``keep`` is
#: excluded on purpose: the incumbent chain reports itself.
NON_KEEP_DISPOSITIONS = frozenset({"discard", "crash", "measured"})

#: Where a study is allowed to cite its own evidence.  ``program.md`` is the lab
#: notebook and ``findings.md`` is the report; a run mentioned in neither was
#: not used, whatever else it appears in.
CITATION_SOURCES: tuple[str, ...] = ("program.md", "findings.md")

#: A decision the program records.  The protocol's own spelling, anywhere on the
#: line (a bullet, a table cell, a bolded lead-in all qualify).
DECISION_LINE_RE = re.compile(r"(?im)^.*\bDecision\b\s*:.*$")

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

#: How far above a ``Decision:`` line the date may live.  A program entry
#: normally carries its date on the heading right above the decision, not
#: inside the sentence; five lines covers that shape without letting a date from
#: an unrelated section count.
DECISION_DATE_WINDOW = 5


@dataclass(frozen=True)
class EvidenceUse:
    """The three D14 numbers and the lists behind them."""

    #: every non-keep run id and ``sweep:<name>`` the study produced
    evidence: tuple[str, ...] = ()
    #: those of them that program.md or findings.md actually mention
    cited: tuple[str, ...] = ()
    #: those of them nothing mentions
    uncited: tuple[str, ...] = ()
    #: refuted predictions with no dated ``Decision:`` line naming them
    undecided_refutations: tuple[str, ...] = ()
    #: every refuted prediction, decided or not
    refuted: tuple[str, ...] = ()
    #: confirmed claims resting on fewer than two kinds of evidence
    single_source_claims: tuple[str, ...] = ()
    #: kinds cited, per confirmed claim — for the receipt and the message
    claim_kinds: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def rate(self) -> float:
        """``evidence_use_rate`` — 1.0 when there is nothing to ignore."""
        return 1.0 if not self.evidence else len(self.cited) / len(self.evidence)

    def summary(self) -> str:
        """The one line ``klein status`` prints."""
        return (
            f"evidence use: {self.rate:.2f} "
            f"({len(self.cited)}/{len(self.evidence)} cited), "
            f"{len(self.undecided_refutations)} refutation(s) without a recorded "
            f"decision, {len(self.single_source_claims)} single-source confirmed claim(s)"
        )


def _citation_text(study_dir: Path) -> str:
    parts: list[str] = []
    for name in CITATION_SOURCES:
        path = study_dir / name
        if path.is_file():
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:  # pragma: no cover - defensive
                continue
    return "\n".join(parts)


def _is_cited(token: str, corpus: str) -> bool:
    """Whole-token match, so ``E0001`` never matches inside ``E00010``."""
    return re.search(rf"(?<![\w:]){re.escape(token)}\b", corpus) is not None


def decided_prediction_ids(program_text: str) -> set[str]:
    """Prediction ids named on a DATED ``Decision:`` line.

    The date may sit on the decision line itself or on one of the
    :data:`DECISION_DATE_WINDOW` lines above it — the shape a program entry
    actually has, where the heading carries the date and the bullet carries the
    decision.
    """
    lines = program_text.splitlines()
    decided: set[str] = set()
    for index, line in enumerate(lines):
        if not DECISION_LINE_RE.match(line):
            continue
        window = lines[max(0, index - DECISION_DATE_WINDOW) : index + 1]
        if not any(_ISO_DATE_RE.search(entry) for entry in window):
            continue
        decided.update(re.findall(r"\bP\d+\b", line))
    return decided


def _evidence_kind(study_dir: Path, item: str) -> str | None:
    """Which of the four convergent kinds a piece of evidence belongs to."""
    if re.fullmatch(r"E\d{4,}", item):
        manifest = study_dir / "runs" / item / "manifest.json"
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "run"
        kind = payload.get("evaluation_kind") if isinstance(payload, Mapping) else None
        return "sealed" if kind == "final_test" else "run"
    if item.startswith("rep:"):
        return "replication"
    if item.startswith("verify:"):
        return "verification"
    return None


def _confirmed_claim_kinds(study_dir: Path) -> dict[str, tuple[str, ...]]:
    """For each ``confirmed`` claim, the distinct evidence kinds it cites."""
    path = lock_path(study_dir)
    if not path.is_file():
        return {}
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(lock, Mapping):
        return {}
    try:
        schema = detect_lock_schema(lock)
    except Exception:  # pragma: no cover - a broken lock is the claims law's job
        return {}
    found: dict[str, tuple[str, ...]] = {}
    for cid, entry in claims_map(lock, schema).items():
        if not isinstance(entry, Mapping) or entry.get("strength") != "confirmed":
            continue
        evidence = entry.get("evidence")
        items = evidence if isinstance(evidence, Sequence) and not isinstance(evidence, str) else ()
        kinds: list[str] = []
        for item in items:
            if not isinstance(item, str):
                continue
            kind = _evidence_kind(study_dir, item)
            if kind is not None and kind not in kinds:
                kinds.append(kind)
        found[str(cid)] = tuple(kinds)
    return found


def evidence_use(
    study_dir: Path,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    manifests: Sequence[Mapping[str, Any]],
) -> EvidenceUse:
    """Compute the three D14 numbers for one study."""
    tokens: list[str] = [
        str(manifest.get("experiment"))
        for manifest in manifests
        if str(manifest.get("disposition")) in NON_KEEP_DISPOSITIONS
        and manifest.get("experiment")
    ]
    registry = state.get("sweeps")
    if isinstance(registry, Mapping):
        tokens.extend(f"sweep:{name}" for name in sorted(registry))

    corpus = _citation_text(study_dir)
    cited = tuple(token for token in tokens if _is_cited(token, corpus))
    uncited = tuple(token for token in tokens if token not in set(cited))

    program = study_dir / "program.md"
    program_text = program.read_text(encoding="utf-8", errors="replace") if program.is_file() else ""
    decided = decided_prediction_ids(program_text)
    refuted = tuple(
        str(row["id"])
        for row in prediction_ledger(contract, state)
        if str(row.get("verdict")) == "refuted"
    )
    undecided = tuple(name for name in refuted if name not in decided)

    claim_kinds = _confirmed_claim_kinds(study_dir)
    single = tuple(cid for cid, kinds in sorted(claim_kinds.items()) if len(kinds) < 2)

    return EvidenceUse(
        evidence=tuple(tokens),
        cited=cited,
        uncited=uncited,
        undecided_refutations=undecided,
        refuted=refuted,
        single_source_claims=single,
        claim_kinds=claim_kinds,
    )
