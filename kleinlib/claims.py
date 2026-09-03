"""``claims.lock`` — the machine surface under ``findings.md``.

``findings.md`` is what a study says; ``claims.lock`` is what a stranger can
check.  The normative text is ``.claude/skills/klein/references/claims-protocol.md``:
this module implements its two lock shapes, the five classes and their strength
ceilings, the seven-check claims law, and the numbers law.

**Lock schema 2** is a claims registry: ``artifacts`` (alias -> path + sha256),
``numbers`` (alias -> value, art, claim, precision), ``claims``
(``Cn`` -> class, strength, sentence, numbers[], evidence[], errata[]) and an
``errata`` registry.

**Lock schema 1** is what studies 07, 08 and 09 hand-built before the engine
produced locks: a NUMBERS ledger whose top-level ``claims`` map is what schema 2
calls ``numbers``.  It is recognised by the ABSENCE of ``lock_schema``, verified
under the reduced schema-1 rules the protocol lists (artifact hashes, numbers in
their artifacts, claim ids present in findings, append-only history, ``git_head``
resolvable) and NEVER rewritten.  Its quirks are real and load-bearing: artifact
paths are repo-relative, ``art`` and ``artifact`` both occur, entries may be
scalars (``"klein_version": "1.2.0"``), values may be strings or nested
mappings, and ``claim`` may be ``"floor"``/``"contract"`` instead of a ``Cn``.

Nothing here reaches the network — a ``ref:`` citation resolves against
``references.yaml``, and DOI liveness stays the referee's job.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .checks import Check
from .contract import load_contract
from .errors import WorkflowError
from .events import append_event
from .primitives import atomic_write_json, sha256_file, utc_now
from .references import is_verified, load_references, reference_problems
from .transaction import commit_state_writes, git

__all__ = [
    "CLAIM_CLASSES",
    "LOCK_NAME",
    "LOCK_SCHEMA",
    "STRENGTHS",
    "STRENGTH_RANK",
    "add_claim",
    "add_number",
    "canonical_lock_text",
    "claims_checks",
    "detect_lock_schema",
    "file_erratum",
    "init_lock",
    "lock_path",
    "load_lock",
    "pin_artifact",
    "verify_lock",
    "write_lock",
]

#: The lock, study-relative.
LOCK_NAME = "claims.lock"

#: The shape this engine writes.  A lock without the key is schema 1.
LOCK_SCHEMA = 2

#: The five classes and the strongest strength each may ever carry
#: (claims-protocol.md "The five classes and their ceilings").
CLAIM_CLASSES: dict[str, str] = {
    "empirical-description": "confirmed",
    "procedural-verdict": "confirmed",
    "mechanism-interpretation": "exploratory",
    "known-dgp-teaching": "confirmed",
    "research-discipline": "exploratory",
}

STRENGTHS = ("exploratory", "confirmed", "refuted")

#: Ordering for "downgrade only".  ``refuted`` is the strongest downgrade: it is
#: never written at first authoring, only by an erratum or a later refutation.
STRENGTH_RANK = {"confirmed": 2, "exploratory": 1, "refuted": 0}

#: A ``numbers`` entry with no ``precision`` matches at three decimals.
DEFAULT_PRECISION = 3

#: The sentence `klein claims init` writes when a study has no law of its own.
DEFAULT_LAW = (
    "Every number in findings.md, this lock and report/index.html is a copy of a "
    "value in a pinned artifact; every claim cites evidence that resolves; claims "
    "and numbers are appended or erratum-tagged, never removed."
)

CLAIM_ID_RE = re.compile(r"^C\d+$")
FINDINGS_MARKER_RE = re.compile(r"\*\*\[(C\d+)\]\*\*")
RUN_ID_RE = re.compile(r"^E\d{4}$")
PREDICTION_ID_RE = re.compile(r"^P\d+$")
CROSS_STUDY_RE = re.compile(r"^(?P<study>[A-Za-z0-9._-]+)#(?P<claim>C\d+)$")
REPLICATION_RE = re.compile(r"^(?P<mode>rep|verify):(?P<run>E\d{4})@(?P<stamp>.+)$")

#: Numeric literals in a text artifact or a claim sentence.
#:
#: The leading sign is taken only when it is NOT glued to a preceding word
#: character.  English prose hyphenates constantly — "depth-2 tree", "top-10
#: lift", "5-fold CV" — and reading that hyphen as a minus reports the numeral
#: with the WRONG VALUE (``-2`` for a sentence that says two), which is the
#: false positive this module's docstring calls the worst kind: it looks
#: plausible and it cannot be found anywhere.  ``x=-5``, ``(-0.5)`` and a
#: leading ``-0.07`` in a TSV cell all still keep their sign, and an exponent's
#: sign (``5e-3``) is inside the alternatives, untouched.
NUMERAL_RE = re.compile(
    r"(?:(?<![A-Za-z0-9_])[-+])?"
    r"(?:\d+\.\d+(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)"
)

#: Tokens a claim sentence may carry without an alias (claims-protocol.md, the
#: numbers law): identifiers, years, and small counts that name their unit or
#: source ("24 objects", "k = 5 seeds", "0 of 42 cells").  A bare reference value
#: ("not 465") is NOT exempt — it needs a pinned alias like any other number.
#: Stripped before the sentence is scanned.
SENTENCE_EXEMPT_RE = re.compile(
    r"\b(?:E\d{4}|P\d+|C\d+|RQ\d+|S\d+|1[89]\d{2}|20\d{2})\b"
    r"|\b[nk]\s*=\s*\d{1,4}(?!\.\d)\b"
    r"|\b\d{1,4}\s+of\s+\d{1,4}\b"
    r"|\b\d{1,4}\s+(?:objects?|rows?|nebulae|cells?|seeds?|runs?|trials?|"
    r"families|candidates?|challengers?|draws?|resamples?|features?|columns?|"
    r"items?|parameters?|steps?|epochs?|folds?|blocks?|groups?|decimals?|"
    r"transactions?|experiments?|keeps?|discards?|crashes?)\b"
)

#: The law's one escape hatch, which the referee reads every instance of.
NUMBERS_OK_RE = re.compile(r"klein:numbers-ok:(?P<reason>[^>]*)")

#: Aliases a ``numbers`` entry may name in ``claim`` instead of a ``Cn`` id.
CONTRACT_CLAIM_IDS = ("floor", "contract")


@dataclass(frozen=True)
class Problem:
    """One finding of one law check: a failure, or a warning ``--strict`` promotes."""

    level: str  # "fail" | "warn"
    message: str


def _fail(message: str) -> Problem:
    return Problem("fail", message)


def _warn(message: str) -> Problem:
    return Problem("warn", message)


# --------------------------------------------------------------------------
# Loading, shape detection, canonical bytes
# --------------------------------------------------------------------------


def lock_path(study_dir: Path) -> Path:
    return study_dir / LOCK_NAME


def load_lock(study_dir: Path) -> dict[str, Any]:
    path = lock_path(study_dir)
    if not path.is_file():
        raise WorkflowError(f"{LOCK_NAME} not found under {study_dir}")
    return _parse_lock(path.read_text(encoding="utf-8"), str(path))


def _parse_lock(text: str, where: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{where} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{where} must contain a top-level JSON object")
    return value


def detect_lock_schema(lock: Mapping[str, Any]) -> int:
    """2 when the lock declares ``lock_schema``; 1 (the legacy ledger) otherwise."""
    raw = lock.get("lock_schema")
    if raw is None:
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise WorkflowError(f"invalid lock_schema: {raw!r}") from exc


def canonical_lock_text(lock: Mapping[str, Any]) -> str:
    """The lock's canonical bytes: sorted keys, 2-space indent, trailing newline.

    The same form :func:`kleinlib.primitives.atomic_write_json` writes, exposed so
    a caller (or a test) can assert byte-stability without touching the disk.
    """
    return json.dumps(lock, indent=2, sort_keys=True) + "\n"


def write_lock(study_dir: Path, lock: Mapping[str, Any]) -> Path:
    path = lock_path(study_dir)
    atomic_write_json(path, dict(lock))
    return path


def numbers_map(lock: Mapping[str, Any], schema: int | None = None) -> dict[str, Any]:
    """The numbers ledger — schema 1 keeps it under ``claims``, schema 2 under ``numbers``."""
    schema = detect_lock_schema(lock) if schema is None else schema
    raw = lock.get("claims" if schema == 1 else "numbers")
    return dict(raw) if isinstance(raw, Mapping) else {}


def claims_map(lock: Mapping[str, Any], schema: int | None = None) -> dict[str, Any]:
    """The ``Cn`` claim registry — empty for schema 1, which has no claim entries."""
    schema = detect_lock_schema(lock) if schema is None else schema
    if schema == 1:
        return {}
    raw = lock.get("claims")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _art_alias(entry: Mapping[str, Any]) -> Any:
    """``art`` (07, schema 2) or ``artifact`` (08, 09) — both spellings occur."""
    return entry.get("art", entry.get("artifact"))


# --------------------------------------------------------------------------
# Numbers law helpers
# --------------------------------------------------------------------------


def _numeric_leaves(value: Any, prefix: str = "") -> list[tuple[str, float]]:
    """Every number inside a scalar, list or mapping value, with its path."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [(prefix, float(value))]
    if isinstance(value, Mapping):
        found: list[tuple[str, float]] = []
        for key, sub in value.items():
            found.extend(_numeric_leaves(sub, f"{prefix}.{key}" if prefix else str(key)))
        return found
    if isinstance(value, (list, tuple)):
        found = []
        for index, sub in enumerate(value):
            found.extend(_numeric_leaves(sub, f"{prefix}[{index}]"))
        return found
    return []


def text_numerals(text: str) -> list[float]:
    values: list[float] = []
    for match in NUMERAL_RE.finditer(text):
        try:
            values.append(float(match.group()))
        except ValueError:  # pragma: no cover - the regex only matches parseable forms
            continue
    return values


def _fmt(value: float) -> str:
    """A numeral as the lock spells it: 0, not 0.0; 0.04826, not 0.048259999."""
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return repr(value)


def numeral_matches(value: float, literals: Sequence[float], precision: int) -> bool:
    """True when ``value`` appears among ``literals`` exactly or at ``precision`` decimals."""
    try:
        rounded = round(value, precision)
    except (OverflowError, ValueError):  # pragma: no cover - defensive
        return False
    for literal in literals:
        if literal == value:
            return True
        try:
            if round(literal, precision) == rounded:
                return True
        except (OverflowError, ValueError):  # pragma: no cover - defensive
            continue
    return False


def _read_text_artifact(path: Path) -> str | None:
    """The artifact's text, or None when it is binary (the protocol's [WARN] case)."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


# --------------------------------------------------------------------------
# Artifact resolution
# --------------------------------------------------------------------------


def _repo_root(study_dir: Path) -> Path | None:
    probe = git(study_dir, ["rev-parse", "--show-toplevel"], check=False)
    if probe.returncode:
        return None
    return Path(probe.stdout.strip()).resolve()


def _resolve_artifact(study_dir: Path, rel: str, repo: Path | None) -> Path | None:
    """Study-relative first, then repo-relative (lock schema 1 pinned repo paths)."""
    candidate = study_dir / rel
    if candidate.is_file():
        return candidate
    if repo is not None:
        candidate = repo / rel
        if candidate.is_file():
            return candidate
    return None


# --------------------------------------------------------------------------
# The seven checks
# --------------------------------------------------------------------------


def _check_shape(lock: Mapping[str, Any], schema: int) -> list[Problem]:
    problems: list[Problem] = []
    if schema not in (1, 2):
        return [_fail(f"unknown lock_schema {schema} — this engine writes schema {LOCK_SCHEMA}")]
    if not (lock.get("study_id") or lock.get("study")):
        problems.append(_fail("missing study id ('study_id', or 'study' on lock schema 1)"))
    if not isinstance(lock.get("git_head"), str) or not lock.get("git_head"):
        problems.append(_fail("missing or non-string 'git_head'"))
    if not isinstance(lock.get("law"), str) or not lock.get("law"):
        problems.append(_warn("no 'law' sentence — the lock states its own promise"))

    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, Mapping):
        problems.append(_fail("'artifacts' must be a mapping of alias -> {path, sha256}"))
        artifacts = {}
    for alias, meta in artifacts.items():
        if not isinstance(meta, Mapping):
            problems.append(_fail(f"artifact {alias!r}: entry must be a mapping"))
            continue
        path = meta.get("path")
        if not isinstance(path, str) or not path:
            problems.append(_fail(f"artifact {alias!r}: missing 'path'"))
        elif path.startswith("/") or "\\" in path:
            problems.append(_fail(f"artifact {alias!r}: path must be relative and POSIX: {path!r}"))
        if not isinstance(meta.get("sha256"), str):
            problems.append(_fail(f"artifact {alias!r}: missing 'sha256'"))

    numbers = lock.get("claims" if schema == 1 else "numbers")
    if not isinstance(numbers, Mapping):
        problems.append(
            _fail(f"'{'claims' if schema == 1 else 'numbers'}' must be a mapping of alias -> entry")
        )
        numbers = {}
    for alias, entry in numbers.items():
        if not isinstance(entry, Mapping):
            if schema == 1:
                # 07 pins "klein_version": "1.2.0" as a bare scalar.
                problems.append(_warn(f"number {alias!r}: schema-1 scalar entry, not machine-checked"))
            else:
                problems.append(_fail(f"number {alias!r}: entry must be a mapping"))
            continue
        art = _art_alias(entry)
        if art is not None and art not in artifacts:
            problems.append(_fail(f"number {alias!r}: 'art' {art!r} is not a pinned alias"))
        if schema == 2 and "value" not in entry:
            problems.append(_fail(f"number {alias!r}: missing 'value'"))
        precision = entry.get("precision", DEFAULT_PRECISION)
        if not isinstance(precision, int) or isinstance(precision, bool) or precision < 0:
            problems.append(_fail(f"number {alias!r}: 'precision' must be a non-negative int"))
        claim_id = entry.get("claim")
        if claim_id is not None and not isinstance(claim_id, str):
            problems.append(_fail(f"number {alias!r}: 'claim' must be a string id"))
        elif (
            isinstance(claim_id, str)
            and claim_id not in CONTRACT_CLAIM_IDS
            and not CLAIM_ID_RE.match(claim_id)
        ):
            problems.append(
                _fail(f"number {alias!r}: 'claim' {claim_id!r} is neither a Cn id nor "
                      f"one of {CONTRACT_CLAIM_IDS}")
            )
        klass = entry.get("class")
        if klass is not None and klass not in CLAIM_CLASSES:
            problems.append(_fail(f"number {alias!r}: unknown class {klass!r}"))

    if schema == 1:
        return problems

    problems.extend(_check_shape_schema2(lock, numbers))
    return problems


def _check_shape_schema2(lock: Mapping[str, Any], numbers: Mapping[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    claims = lock.get("claims")
    if not isinstance(claims, Mapping):
        problems.append(_fail("'claims' must be a mapping of Cn -> claim entry"))
        claims = {}
    errata = lock.get("errata")
    if errata is None:
        errata = {}
    if not isinstance(errata, Mapping):
        problems.append(_fail("'errata' must be a mapping of erratum id -> entry"))
        errata = {}

    for cid, entry in claims.items():
        if not CLAIM_ID_RE.match(str(cid)):
            problems.append(_fail(f"claim {cid!r}: id must look like C1, C2, …"))
        if not isinstance(entry, Mapping):
            problems.append(_fail(f"claim {cid!r}: entry must be a mapping"))
            continue
        klass = entry.get("class")
        if klass is None:
            problems.append(
                _fail(
                    f"claim {cid!r}: class is null — `klein claims init` writes a skeleton, "
                    "not a finished lock; give every claim one of "
                    f"{sorted(CLAIM_CLASSES)}"
                )
            )
        elif klass not in CLAIM_CLASSES:
            problems.append(_fail(f"claim {cid!r}: unknown class {klass!r}"))
        strength = entry.get("strength")
        if strength not in STRENGTHS:
            problems.append(_fail(f"claim {cid!r}: strength must be one of {list(STRENGTHS)}"))
        elif klass in CLAIM_CLASSES:
            ceiling = CLAIM_CLASSES[klass]
            if STRENGTH_RANK[strength] > STRENGTH_RANK[ceiling]:
                problems.append(
                    _fail(
                        f"claim {cid!r}: class {klass!r} ceilings at {ceiling!r}; "
                        f"{strength!r} exceeds it"
                    )
                )
        if not isinstance(entry.get("claim"), str) or not entry.get("claim"):
            problems.append(_fail(f"claim {cid!r}: 'claim' must be the sentence from findings.md"))
        for field in ("numbers", "evidence", "errata"):
            value = entry.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                problems.append(_fail(f"claim {cid!r}: {field!r} must be a list of strings"))
        if klass == "known-dgp-teaching" and entry.get("scope") != "in-silico":
            problems.append(
                _fail(
                    f"claim {cid!r}: a known-dgp-teaching claim carries \"scope\": \"in-silico\" — "
                    "it is never a claim about real data"
                )
            )
        for eid in entry.get("errata", []) if isinstance(entry.get("errata"), list) else []:
            if eid not in errata:
                problems.append(
                    _fail(f"claim {cid!r}: erratum {eid!r} is not in the errata registry")
                )

    for eid, entry in errata.items():
        if not isinstance(entry, Mapping):
            problems.append(_fail(f"erratum {eid!r}: entry must be a mapping"))
            continue
        named = entry.get("claims")
        if not isinstance(named, list) or not named:
            problems.append(_fail(f"erratum {eid!r}: 'claims' must name at least one claim"))
            named = []
        for cid in named:
            if cid not in claims:
                problems.append(_fail(f"erratum {eid!r}: names unknown claim {cid!r}"))
            elif eid not in (claims.get(cid, {}) or {}).get("errata", []):
                problems.append(
                    _fail(f"erratum {eid!r}: claim {cid!r} does not carry the tag — "
                          "errata re-scope, and the claim wears the tag")
                )
        if not isinstance(entry.get("note"), str) or not entry.get("note"):
            problems.append(_fail(f"erratum {eid!r}: missing 'note' (what is now known)"))
        if not isinstance(entry.get("filed"), str):
            problems.append(_warn(f"erratum {eid!r}: no 'filed' date"))

    for cid, entry in claims.items():
        if not isinstance(entry, Mapping):
            continue
        for alias in entry.get("numbers", []) if isinstance(entry.get("numbers"), list) else []:
            if alias not in numbers:
                problems.append(_fail(f"claim {cid!r}: numbers alias {alias!r} is not in 'numbers'"))
    return problems


def _check_artifacts(study_dir: Path, lock: Mapping[str, Any], repo: Path | None) -> list[Problem]:
    problems: list[Problem] = []
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return [_fail("no 'artifacts' map to check")]
    if not artifacts:
        return [_warn("no artifacts pinned — every number needs a home")]
    for alias, meta in artifacts.items():
        if not isinstance(meta, Mapping) or not isinstance(meta.get("path"), str):
            continue  # already reported by the shape check
        path = _resolve_artifact(study_dir, meta["path"], repo)
        if path is None:
            problems.append(_fail(f"artifact {alias!r}: pinned file is missing: {meta['path']}"))
            continue
        expected = meta.get("sha256")
        actual = sha256_file(path)
        if actual != expected:
            problems.append(
                _fail(f"artifact {alias!r}: sha256 mismatch — pinned {expected}, on disk {actual}")
            )
        elif repo is not None and not _is_tracked(repo, path):
            problems.append(
                _warn(
                    f"artifact {alias!r}: {meta['path']} is not tracked by git — the hash is "
                    "checkable here and nowhere else"
                )
            )
    return problems


def _is_tracked(repo: Path, path: Path) -> bool:
    result = git(repo, ["ls-files", "--error-unmatch", "--", str(path)], check=False)
    return result.returncode == 0


def _check_presence(study_dir: Path, lock: Mapping[str, Any], schema: int) -> list[Problem]:
    problems: list[Problem] = []
    findings = study_dir / "findings.md"
    if not findings.is_file():
        message = "findings.md is missing — claim ids cannot be located"
        return [_fail(message) if schema >= 2 else _warn(message)]
    text = findings.read_text(encoding="utf-8", errors="replace")
    numbers = numbers_map(lock, schema)
    claims = claims_map(lock, schema)

    if schema == 1:
        # Schema 1 is a numbers ledger: the claim ids it names must exist in
        # findings, but findings legitimately carries claim ids the ledger never
        # pinned a number for, so the reverse direction does not apply.
        for alias, entry in numbers.items():
            if not isinstance(entry, Mapping):
                continue
            cid = entry.get("claim")
            if isinstance(cid, str) and CLAIM_ID_RE.match(cid):
                # 07 writes "**[C1]**", 08 writes "**C1 · …**", 09 writes
                # "**[C1] · class · strength.**" — match the id, not one layout.
                if not re.search(rf"\b{cid}\b", text):
                    problems.append(
                        _fail(f"number {alias!r}: claim {cid} does not appear in findings.md")
                    )
        return problems

    marked = set(FINDINGS_MARKER_RE.findall(text))
    for cid in claims:
        if cid not in marked:
            problems.append(_fail(f"claim {cid}: no **[{cid}]** line in findings.md"))
    for cid in sorted(marked - set(claims)):
        problems.append(_fail(f"findings.md declares **[{cid}]** but the lock has no such claim"))
    for cid, entry in claims.items():
        if not isinstance(entry, Mapping):
            continue
        for alias in entry.get("numbers", []) if isinstance(entry.get("numbers"), list) else []:
            if alias not in numbers:
                problems.append(_fail(f"claim {cid}: alias {alias!r} does not exist in 'numbers'"))
    return problems


def _resolve_evidence(
    study_dir: Path,
    evidence: str,
    lock: Mapping[str, Any],
    *,
    confirmed: bool,
    references: Mapping[str, Any],
) -> Problem | None:
    """None when the id resolves; a Problem naming why it does not (or a warning)."""
    if RUN_ID_RE.match(evidence):
        if not (study_dir / "runs" / evidence / "manifest.json").is_file():
            return _fail(f"evidence {evidence!r}: no runs/{evidence}/manifest.json")
        return None

    if evidence.startswith("sweep:"):
        name = evidence[len("sweep:") :]
        if not name:
            return _fail("evidence 'sweep:': no sweep name")
        state_path = study_dir / "study_state.json"
        registered = False
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
            sweeps = state.get("sweeps") if isinstance(state, Mapping) else None
            registered = isinstance(sweeps, Mapping) and name in sweeps
        if registered:
            return None
        if (study_dir / "sweeps" / f"{name}.sidecar.tsv").is_file():
            return _warn(
                f"evidence {evidence!r}: sidecar present but not registered in "
                "study_state.sweeps — register it with `klein sweep register`"
            )
        return _fail(f"evidence {evidence!r}: neither state.sweeps nor sweeps/{name}.sidecar.tsv")

    replication = REPLICATION_RE.match(evidence)
    if replication:
        run = replication.group("run")
        stamp = replication.group("stamp")
        record = study_dir / "runs" / run / "replications" / f"{stamp}.json"
        if not record.is_file():
            return _fail(f"evidence {evidence!r}: no runs/{run}/replications/{stamp}.json")
        if replication.group("mode") == "verify":
            try:
                payload = json.loads(record.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return _warn(f"evidence {evidence!r}: replication record is not valid JSON")
            if isinstance(payload, Mapping) and payload.get("mode") != "verify":
                return _warn(
                    f"evidence {evidence!r}: record exists but its mode is "
                    f"{payload.get('mode')!r}, not 'verify'"
                )
        return None

    if evidence.startswith("ref:"):
        key = evidence[len("ref:") :]
        entry = references.get(key)
        if entry is None:
            return _fail(f"evidence {evidence!r}: no such key in references.yaml")
        if confirmed and not is_verified(entry):
            return _warn(
                f"evidence {evidence!r}: reference is not verified: true, and it stands "
                "behind a confirmed claim"
            )
        return None

    if evidence.startswith("art:"):
        alias = evidence[len("art:") :]
        artifacts = lock.get("artifacts")
        if not isinstance(artifacts, Mapping) or alias not in artifacts:
            return _fail(f"evidence {evidence!r}: {alias!r} is not a pinned artifact alias")
        return None

    if PREDICTION_ID_RE.match(evidence):
        return _resolve_prediction(study_dir, evidence)

    cross = CROSS_STUDY_RE.match(evidence)
    if cross:
        return _resolve_cross_study(study_dir, evidence, cross)

    return _fail(
        f"evidence {evidence!r}: not an id in the inquiry-model grammar "
        "(E####, sweep:, rep:/verify:, ref:, art:, P#, <study>#Cn)"
    )


def _resolve_prediction(study_dir: Path, evidence: str) -> Problem | None:
    try:
        contract = load_contract(study_dir)
    except WorkflowError as exc:
        return _warn(f"evidence {evidence!r}: contract unreadable ({exc})")
    registered = contract.get("predictions")
    if isinstance(registered, Mapping):
        return None if evidence in registered else _fail(
            f"evidence {evidence!r}: no such prediction in study.yaml"
        )
    entries = registered if isinstance(registered, list) else contract.get("predictions_to_falsify")
    if not isinstance(entries, list) or not entries:
        return _fail(f"evidence {evidence!r}: study.yaml registers no predictions")
    for entry in entries:
        if isinstance(entry, Mapping) and entry.get("id") == evidence:
            return None
    index = int(evidence[1:])
    if 1 <= index <= len(entries):
        return None
    return _fail(
        f"evidence {evidence!r}: study.yaml registers only {len(entries)} predictions"
    )


def _resolve_cross_study(study_dir: Path, evidence: str, match: re.Match[str]) -> Problem | None:
    slug = match.group("study")
    cid = match.group("claim")
    for sibling in (study_dir.parent / slug, study_dir.parent / slug.lstrip("0")):
        other = lock_path(sibling)
        if other.is_file():
            try:
                payload = _parse_lock(other.read_text(encoding="utf-8"), str(other))
            except WorkflowError as exc:
                return _warn(f"evidence {evidence!r}: {exc}")
            other_schema = detect_lock_schema(payload)
            if cid in claims_map(payload, other_schema):
                return None
            named = {
                entry.get("claim")
                for entry in numbers_map(payload, other_schema).values()
                if isinstance(entry, Mapping)
            }
            if cid in named:
                return None
            return _fail(f"evidence {evidence!r}: {slug}'s lock has no claim {cid}")
    return _warn(f"evidence {evidence!r}: study {slug!r} is not at hand — not resolved")


def _check_evidence(study_dir: Path, lock: Mapping[str, Any], schema: int) -> list[Problem]:
    if schema == 1:
        return []
    claims = claims_map(lock, schema)
    if not claims:
        return [_warn("no claims to resolve evidence for")]
    try:
        references = load_references(study_dir)
    except WorkflowError as exc:
        return [_fail(str(exc))]
    problems = [_fail(f"references.yaml: {p}") for p in reference_problems(references)]
    for cid, entry in claims.items():
        if not isinstance(entry, Mapping):
            continue
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            problems.append(_fail(f"claim {cid}: no evidence — every claim cites evidence"))
            continue
        confirmed = entry.get("strength") == "confirmed"
        for item in evidence:
            if not isinstance(item, str):
                continue
            problem = _resolve_evidence(
                study_dir, item, lock, confirmed=confirmed, references=references
            )
            if problem is not None:
                problems.append(Problem(problem.level, f"claim {cid}: {problem.message}"))
    return problems


def _check_numbers(
    study_dir: Path,
    lock: Mapping[str, Any],
    schema: int,
    repo: Path | None,
    *,
    sentences: bool,
) -> list[Problem]:
    problems: list[Problem] = []
    artifacts = lock.get("artifacts") if isinstance(lock.get("artifacts"), Mapping) else {}
    numbers = numbers_map(lock, schema)
    literals: dict[str, list[float] | None] = {}

    def artifact_literals(alias: str) -> list[float] | None:
        if alias not in literals:
            meta = artifacts.get(alias)
            path = (
                _resolve_artifact(study_dir, meta["path"], repo)
                if isinstance(meta, Mapping) and isinstance(meta.get("path"), str)
                else None
            )
            text = _read_text_artifact(path) if path is not None else None
            literals[alias] = None if text is None else text_numerals(text)
        return literals[alias]

    # A derived quantity (a ratio, a row count, a sum) is a real and honest thing
    # to pin, and lock schema 1 pins several — so a value the artifact does not
    # spell out is a warning there and a failure once the engine writes the lock.
    missing_level = _warn if schema == 1 else _fail

    for alias, entry in numbers.items():
        if not isinstance(entry, Mapping):
            continue
        if "value" not in entry:
            problems.append(_warn(f"number {alias!r}: no 'value' — not machine-checkable"))
            continue
        art = _art_alias(entry)
        if art is None:
            problems.append(_warn(f"number {alias!r}: no 'art' — the value has no pinned home"))
            continue
        if art not in artifacts:
            continue  # the shape check already failed this
        leaves = _numeric_leaves(entry["value"])
        if not leaves:
            problems.append(
                _warn(f"number {alias!r}: value is prose, not a numeral — read it, do not trust it")
            )
            continue
        found = artifact_literals(str(art))
        if found is None:
            problems.append(
                _warn(f"number {alias!r}: artifact {art!r} is binary or unreadable — not scanned")
            )
            continue
        precision = entry.get("precision", DEFAULT_PRECISION)
        precision = precision if isinstance(precision, int) and not isinstance(precision, bool) else DEFAULT_PRECISION
        for path, value in leaves:
            if numeral_matches(value, found, precision):
                continue
            label = f"{alias}.{path}" if path else alias
            problems.append(
                missing_level(
                    f"number {label}: {_fmt(value)} is not in artifact {art!r} at "
                    f"{precision} decimals or exactly"
                )
            )

    if sentences and schema >= 2:
        problems.extend(_check_claim_sentences(lock, schema, numbers))
    return problems


def _check_claim_sentences(
    lock: Mapping[str, Any], schema: int, numbers: Mapping[str, Any]
) -> list[Problem]:
    """Every numeral in a claim sentence is covered by one of its aliases."""
    problems: list[Problem] = []
    for cid, entry in claims_map(lock, schema).items():
        if not isinstance(entry, Mapping) or not isinstance(entry.get("claim"), str):
            continue
        aliases = entry.get("numbers") if isinstance(entry.get("numbers"), list) else []
        covered: list[tuple[float, int]] = []
        for alias in aliases:
            number = numbers.get(alias)
            if not isinstance(number, Mapping):
                continue
            precision = number.get("precision", DEFAULT_PRECISION)
            precision = (
                precision
                if isinstance(precision, int) and not isinstance(precision, bool)
                else DEFAULT_PRECISION
            )
            covered.extend((value, precision) for _, value in _numeric_leaves(number.get("value")))
        marker = NUMBERS_OK_RE.search(entry["claim"])
        if marker:
            # The law's documented escape hatch, and the referee reads every one.
            problems.append(
                _warn(f"claim {cid}: numerals exempted by marker — {marker.group('reason').strip()}")
            )
            continue
        sentence = SENTENCE_EXEMPT_RE.sub(" ", entry["claim"])
        for numeral in text_numerals(sentence):
            if not any(
                numeral_matches(numeral, [value], precision) for value, precision in covered
            ):
                problems.append(
                    _fail(
                        f"claim {cid}: the sentence quotes {_fmt(numeral)}, which no alias in "
                        f"{list(aliases)} carries — a numeral without a home is not a claim"
                    )
                )
    return problems


def _lock_revisions(study_dir: Path, repo: Path | None) -> list[tuple[str, dict[str, Any]]]:
    """``claims.lock`` at every commit that touched it, oldest first."""
    if repo is None:
        return []
    path = lock_path(study_dir)
    try:
        rel = path.resolve().relative_to(repo).as_posix()
    except ValueError:
        return []
    log = git(repo, ["log", "--follow", "--format=%H", "--", rel], check=False)
    if log.returncode:
        return []
    revisions = [line.strip() for line in log.stdout.splitlines() if line.strip()]
    history: list[tuple[str, dict[str, Any]]] = []
    for revision in reversed(revisions):
        # --follow reports renames, so ask each revision for its own path.
        name = git(
            repo,
            ["log", "--follow", "--format=", "--name-only", "-1", revision, "--", rel],
            check=False,
        )
        blob_path = next((line.strip() for line in name.stdout.splitlines() if line.strip()), rel)
        blob = git(repo, ["show", f"{revision}:{blob_path}"], check=False)
        if blob.returncode:
            continue
        try:
            history.append((revision, _parse_lock(blob.stdout, f"{revision}:{blob_path}")))
        except WorkflowError:
            continue
    return history


def _check_append_only(study_dir: Path, lock: Mapping[str, Any], repo: Path | None) -> list[Problem]:
    history = _lock_revisions(study_dir, repo)
    if not history:
        return [
            _warn(
                "no committed history for claims.lock — the append-only promise becomes "
                "mechanical at the first commit"
            )
        ]
    revisions: list[tuple[str, Mapping[str, Any]]] = [*history, ("working tree", lock)]
    problems: list[Problem] = []
    for (old_rev, older), (new_rev, newer) in zip(revisions, revisions[1:], strict=False):
        problems.extend(_diff_revision(older, newer, f"{_short(old_rev)} -> {_short(new_rev)}"))
    return problems


def _short(revision: str) -> str:
    return revision[:12] if len(revision) == 40 else revision


def _diff_revision(
    older: Mapping[str, Any], newer: Mapping[str, Any], where: str
) -> list[Problem]:
    problems: list[Problem] = []
    old_schema = detect_lock_schema(older)
    new_schema = detect_lock_schema(newer)
    old_numbers = numbers_map(older, old_schema)
    new_numbers = numbers_map(newer, new_schema)
    for alias, entry in old_numbers.items():
        if alias not in new_numbers:
            problems.append(_fail(f"{where}: number {alias!r} was removed"))
            continue
        after = new_numbers[alias]
        if not isinstance(entry, Mapping) or not isinstance(after, Mapping):
            if entry != after:
                problems.append(_fail(f"{where}: number {alias!r} changed"))
            continue
        for field, reader in (
            ("value", lambda e: e.get("value")),
            ("art", _art_alias),
            ("claim", lambda e: e.get("claim")),
            ("class", lambda e: e.get("class")),
        ):
            before_value = reader(entry)
            after_value = reader(after)
            if field == "class" and before_value is None:
                continue  # a class may be assigned once; it may never change after
            if before_value != after_value:
                problems.append(
                    _fail(
                        f"{where}: number {alias!r} {field} changed "
                        f"({before_value!r} -> {after_value!r})"
                    )
                )

    old_claims = claims_map(older, old_schema)
    new_claims = claims_map(newer, new_schema)
    new_errata = newer.get("errata") if isinstance(newer.get("errata"), Mapping) else {}
    old_errata = older.get("errata") if isinstance(older.get("errata"), Mapping) else {}
    added_errata = {eid for eid in new_errata if eid not in old_errata}
    erratum_claims = {
        cid
        for eid in added_errata
        for cid in (new_errata.get(eid, {}) or {}).get("claims", [])
        if isinstance((new_errata.get(eid, {}) or {}).get("claims"), list)
    }
    for cid, entry in old_claims.items():
        if cid not in new_claims:
            problems.append(_fail(f"{where}: claim {cid} was removed"))
            continue
        after = new_claims[cid]
        if not isinstance(entry, Mapping) or not isinstance(after, Mapping):
            continue
        # A skeleton claim (`init` writes class null) is not yet authored: its
        # class, sentence and placeholder strength may still be filled in once.
        authored = entry.get("class") is not None
        if authored:
            for field in ("class", "claim"):
                if entry.get(field) != after.get(field):
                    problems.append(
                        _fail(
                            f"{where}: claim {cid} {field} changed — errata re-scope, never rewrite"
                        )
                    )
        for field in ("numbers", "evidence", "errata"):
            before_list = entry.get(field) or []
            after_list = after.get(field) or []
            if isinstance(before_list, list) and isinstance(after_list, list):
                dropped = [item for item in before_list if item not in after_list]
                if dropped:
                    problems.append(_fail(f"{where}: claim {cid} {field} lost {dropped}"))
        if authored and entry.get("strength") != after.get("strength") and cid not in erratum_claims:
            problems.append(
                _fail(
                    f"{where}: claim {cid} strength changed "
                    f"({entry.get('strength')!r} -> {after.get('strength')!r}) without an "
                    "erratum naming it in the same revision"
                )
            )
    return problems


def _check_ancestry(lock: Mapping[str, Any], repo: Path | None) -> list[Problem]:
    head = lock.get("git_head")
    if not isinstance(head, str) or not head:
        return [_fail("no 'git_head' to check ancestry for")]
    if repo is None:
        return [_warn("not a git repository — ancestry not checked")]
    problems: list[Problem] = []
    exists = git(repo, ["cat-file", "-e", f"{head}^{{commit}}"], check=False)
    if exists.returncode:
        problems.append(_fail(f"git_head {head[:12]} does not resolve in this repository"))
    else:
        ancestor = git(repo, ["merge-base", "--is-ancestor", head, "HEAD"], check=False)
        if ancestor.returncode:
            problems.append(
                _fail(f"git_head {head[:12]} is not an ancestor of HEAD — the lock describes "
                      "a commit this branch never saw")
            )
    engine = lock.get("klein_commit")
    if isinstance(engine, str) and engine:
        resolved = git(repo, ["cat-file", "-e", f"{engine}^{{commit}}"], check=False)
        if resolved.returncode:
            problems.append(
                _warn(f"klein_commit {engine[:12]} does not resolve here (advisory: the engine "
                      "repository may not be at hand)")
            )
    return problems


# --------------------------------------------------------------------------
# The law, rolled up into Checks
# --------------------------------------------------------------------------


def _roll_up(name: str, problems: Iterable[Problem], ok_message: str, *, strict: bool) -> Check:
    problems = list(problems)
    failures = [p.message for p in problems if p.level == "fail"]
    warnings = [p.message for p in problems if p.level == "warn"]
    if strict:
        failures = failures + warnings
        warnings = []
    if failures:
        message = "; ".join(failures)
        if warnings:
            message += " | [WARN] " + "; ".join(warnings)
        return Check(name, False, message)
    if warnings:
        return Check(name, True, "[WARN] " + "; ".join(warnings))
    return Check(name, True, ok_message)


def verify_lock(study_dir: Path, *, numbers: bool = False, strict: bool = False) -> list[Check]:
    """The seven checks of the claims law, in the protocol's order.

    ``numbers`` adds the claim-sentence numeral scan to check 5 (the value ->
    artifact half always runs); ``strict`` promotes every warning to a failure.
    """
    lock = load_lock(study_dir)
    schema = detect_lock_schema(lock)
    repo = _repo_root(study_dir)
    label = f"lock schema {schema}"
    return [
        _roll_up("claims shape", _check_shape(lock, schema), f"{label}: fields and classes valid", strict=strict),
        _roll_up(
            "claims artifacts",
            _check_artifacts(study_dir, lock, repo),
            f"{len(lock.get('artifacts') or {})} pinned artifacts hash as recorded",
            strict=strict,
        ),
        _roll_up(
            "claims presence",
            _check_presence(study_dir, lock, schema),
            "every claim id resolves in findings.md",
            strict=strict,
        ),
        _roll_up(
            "claims evidence",
            _check_evidence(study_dir, lock, schema),
            "every cited evidence id resolves"
            if schema >= 2
            else f"{label} carries no evidence lists — not applicable",
            strict=strict,
        ),
        _roll_up(
            "claims numbers",
            _check_numbers(study_dir, lock, schema, repo, sentences=numbers),
            "every pinned value is found in its artifact"
            + (" and every claim numeral has an alias" if numbers and schema >= 2 else ""),
            strict=strict,
        ),
        _roll_up(
            "claims append-only",
            _check_append_only(study_dir, lock, repo),
            "no claim or number removed or mutated across git history",
            strict=strict,
        ),
        _roll_up(
            "claims ancestry",
            _check_ancestry(lock, repo),
            "git_head is an ancestor of HEAD",
            strict=strict,
        ),
    ]


def claims_checks(
    study_dir: Path,
    contract_schema: int,
    *,
    sentences: bool | None = None,
    strict: bool = False,
) -> list[Check]:
    """The claims law as ``klein verify`` runs it: enforcing on schema 3, advisory below.

    Returns ``[]`` when the study has no lock — the law starts at SYNTHESIZE.
    A schema-2 study (07, 08, 09 and every study written before the engine grew
    these verbs) NEVER retro-fails: its failures come back as ``ok=True`` with a
    ``[WARN]`` message.

    ``sentences`` adds check 5's claim-sentence numeral scan (``klein verify
    --claims``); ``None`` means the schema default — on for schema 3, off below
    it, so a schema-2 study's verify output is unchanged unless it is asked for.
    """
    if not lock_path(study_dir).is_file():
        return []
    enforcing = contract_schema >= 3
    sentences = enforcing if sentences is None else sentences
    try:
        checks = verify_lock(study_dir, numbers=sentences, strict=strict)
    except WorkflowError as exc:
        if enforcing:
            return [Check("claims lock", False, str(exc))]
        return [Check("claims lock", True, f"[WARN] advisory on schema {contract_schema}: {exc}")]
    if enforcing:
        return checks
    return [
        check
        if check.ok
        else Check(check.name, True, f"[WARN] advisory on schema {contract_schema}: {check.message}")
        for check in checks
    ]


# --------------------------------------------------------------------------
# The mutating verbs
# --------------------------------------------------------------------------


def _head_commit(study_dir: Path) -> str:
    repo = _repo_root(study_dir)
    if repo is None:
        return ""
    result = git(repo, ["rev-parse", "HEAD"], check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _study_id(study_dir: Path) -> str:
    try:
        contract = load_contract(study_dir)
    except WorkflowError:
        return study_dir.name
    value = contract.get("study_id")
    return str(value) if value else study_dir.name


def _findings_claims(study_dir: Path) -> dict[str, str]:
    """``Cn`` -> the sentence its ``**[Cn]**`` line carries, in findings order."""
    findings = study_dir / "findings.md"
    if not findings.is_file():
        return {}
    found: dict[str, str] = {}
    for line in findings.read_text(encoding="utf-8", errors="replace").splitlines():
        for cid in FINDINGS_MARKER_RE.findall(line):
            if cid in found:
                continue
            sentence = FINDINGS_MARKER_RE.sub("", line).strip()
            sentence = sentence.lstrip("-*|# ").strip()
            found[cid] = sentence or f"(sentence for {cid} — copy it from findings.md)"
    return found


def _commit(study_dir: Path, message: str) -> None:
    """File the lock the verb just wrote — the lock, and nothing else.

    The lock is append-only across its git history, so its commits must be
    readable one by one: a ``klein claims`` commit that also carried an
    in-progress ``findings.md`` edit would put a sentence into the record that
    no claims verb ever checked.  ``scope="own"`` leaves that edit in the tree.
    """
    commit_state_writes(study_dir, message, paths=[LOCK_NAME], scope="own")


def _require_schema2(lock: Mapping[str, Any], verb: str) -> None:
    if detect_lock_schema(lock) == 1:
        raise WorkflowError(
            f"claims {verb}: this is a lock schema 1 ledger (studies 07-09) and is never "
            "rewritten — `klein claims init --from-legacy` migrates it into schema 2 first"
        )


def init_lock(study_dir: Path, *, from_legacy: bool = False, commit: bool = True) -> dict[str, Any]:
    """Write the skeleton lock: claims from findings' ``**[Cn]**`` lines, numbers empty.

    With ``from_legacy`` the study's existing lock schema 1 ledger is migrated
    into schema 2 — its numbers keep their aliases, values, arts and claim ids
    (so the append-only check reads straight through the migration), the classes
    it recorded per number become the claims' classes, and the whole original map
    is preserved verbatim under ``legacy`` so nothing is ever removed.
    """
    from . import __version__

    path = lock_path(study_dir)
    legacy: dict[str, Any] | None = None
    if from_legacy:
        if not path.is_file():
            raise WorkflowError(f"claims init --from-legacy: no {LOCK_NAME} to migrate")
        legacy = load_lock(study_dir)
        if detect_lock_schema(legacy) != 1:
            raise WorkflowError(
                f"claims init --from-legacy: {LOCK_NAME} is already lock schema "
                f"{detect_lock_schema(legacy)}"
            )
    elif path.is_file():
        raise WorkflowError(
            f"{LOCK_NAME} already exists — `init` writes the skeleton once; use pin/number/"
            "add/erratum afterwards (or --from-legacy to migrate a schema-1 ledger)"
        )

    sentences = _findings_claims(study_dir)
    lock: dict[str, Any] = {
        "lock_schema": LOCK_SCHEMA,
        "study_id": _study_id(study_dir),
        "git_head": _head_commit(study_dir),
        "klein_commit": _head_commit(study_dir),
        "klein_version": __version__,
        "law": DEFAULT_LAW,
        "artifacts": {},
        "numbers": {},
        "claims": {},
        "errata": {},
    }
    classes: dict[str, str] = {}
    if legacy is not None:
        lock["law"] = legacy.get("law", DEFAULT_LAW)
        lock["git_head"] = legacy.get("git_head") or lock["git_head"]
        lock["legacy"] = {"lock_schema": 1, "claims": legacy.get("claims", {})}
        study_prefix = f"studies/{study_dir.name}/"
        for alias, meta in (legacy.get("artifacts") or {}).items():
            if not isinstance(meta, Mapping):
                continue
            rel = str(meta.get("path", ""))
            if rel.startswith(study_prefix):
                rel = rel[len(study_prefix) :]
            lock["artifacts"][alias] = {"path": rel, "sha256": meta.get("sha256")}
        for alias, entry in numbers_map(legacy, 1).items():
            migrated = _migrate_number(entry)
            lock["numbers"][alias] = migrated
            cid = migrated.get("claim")
            klass = entry.get("class") if isinstance(entry, Mapping) else None
            if isinstance(cid, str) and CLAIM_ID_RE.match(cid) and isinstance(klass, str):
                classes.setdefault(cid, klass)
        # A migrated number may name a claim findings never marked up: keep the
        # claim rather than lose the pointer, with a placeholder to be replaced.
        for migrated in lock["numbers"].values():
            cid = migrated.get("claim")
            if isinstance(cid, str) and CLAIM_ID_RE.match(cid):
                sentences.setdefault(cid, f"(sentence for {cid} — copy it from findings.md)")

    for cid, sentence in sentences.items():
        aliases = sorted(
            alias
            for alias, entry in lock["numbers"].items()
            if isinstance(entry, Mapping) and entry.get("claim") == cid
        )
        lock["claims"][cid] = {
            "class": classes.get(cid),
            "strength": "exploratory",
            "claim": sentence,
            "numbers": aliases,
            "evidence": [],
            "errata": [],
        }
    write_lock(study_dir, lock)
    if commit:
        _commit(study_dir, f"claims: init lock for {lock['study_id']} ({len(lock['claims'])} claims)")
    return lock


def _migrate_number(entry: Any) -> dict[str, Any]:
    """One schema-1 ledger entry as a schema-2 ``numbers`` entry, losing nothing."""
    if not isinstance(entry, Mapping):
        return {"value": entry, "migrated_from": "lock schema 1 scalar entry"}
    migrated: dict[str, Any] = {}
    if "value" in entry:
        migrated["value"] = entry["value"]
    else:
        # 07's `ladder` / `crash_rung` / `rq_verdicts`: the whole mapping IS the value.
        migrated["value"] = {
            key: value
            for key, value in entry.items()
            if key not in {"art", "artifact", "claim", "class", "note", "erratum"}
        }
        migrated["migrated_from"] = "lock schema 1 entry without a 'value' key"
    art = _art_alias(entry)
    if art is not None:
        migrated["art"] = art
    for field in ("claim", "note"):
        if field in entry:
            migrated[field] = entry[field]
    extras = {
        key: value
        for key, value in entry.items()
        if key not in {"value", "art", "artifact", "claim", "class", "note"}
    }
    if extras and "value" in entry:
        migrated["legacy_fields"] = extras
    return migrated


def pin_artifact(study_dir: Path, alias: str, rel_path: str, *, commit: bool = True) -> dict[str, Any]:
    """Pin one artifact by alias: study-relative POSIX path + sha256 of its bytes."""
    lock = load_lock(study_dir)
    _require_schema2(lock, "pin")
    candidate = Path(rel_path)
    if candidate.is_absolute():
        raise WorkflowError(f"claims pin: path must be study-relative, got {rel_path!r}")
    target = study_dir / candidate
    if not target.is_file():
        raise WorkflowError(f"claims pin: {rel_path} is not a file under {study_dir}")
    try:
        posix = target.resolve().relative_to(study_dir.resolve()).as_posix()
    except ValueError as exc:
        raise WorkflowError(f"claims pin: {rel_path} escapes the study directory") from exc
    artifacts = lock.setdefault("artifacts", {})
    entry = {"path": posix, "sha256": sha256_file(target)}
    artifacts[alias] = entry
    write_lock(study_dir, lock)
    if commit:
        _commit(study_dir, f"claims: pin {alias} -> {posix}")
    return entry


def _refuse_homeless_number(
    study_dir: Path,
    alias: str,
    entry: Mapping[str, Any],
    artifacts: Mapping[str, Any],
) -> None:
    """Refuse a number whose value is not in the artifact it names.

    Check 5 of the claims law fails a number the artifact does not spell out --
    and check 6 makes a number's ``art`` immutable once the verb has committed
    it.  So an alias written against the wrong home is a DEAD END: it can never
    be repointed, never removed, and the lock can never verify again.  Catching
    it here, before anything is written, is the only place the mistake is still
    recoverable, and it costs one read of a file the verb already names.

    Deliberately not an escape hatch: a value its artifact does not contain is
    exactly what check 5 exists to reject, so refusing it at write time only
    makes the same law arrive on time.  The two cases check 5 treats as warnings
    -- a binary artifact, a prose value -- are warnings here too, which means
    they pass.
    """
    meta = artifacts.get(str(entry.get("art")))
    path = (
        _resolve_artifact(study_dir, meta["path"], _repo_root(study_dir))
        if isinstance(meta, Mapping) and isinstance(meta.get("path"), str)
        else None
    )
    text = _read_text_artifact(path) if path is not None else None
    if text is None:
        return
    leaves = _numeric_leaves(entry["value"])
    if not leaves:
        return
    found = text_numerals(text)
    precision = entry.get("precision", DEFAULT_PRECISION)
    precision = (
        precision
        if isinstance(precision, int) and not isinstance(precision, bool)
        else DEFAULT_PRECISION
    )
    missing = [value for _path, value in leaves if not numeral_matches(value, found, precision)]
    if missing:
        raise WorkflowError(
            f"claims number: {alias!r} = {_fmt(missing[0])} is not in artifact "
            f"{entry.get('art')!r} at {precision} decimals or exactly - a number needs a "
            "home that actually holds it. Pin the artifact that does and use that alias. "
            "Nothing was written: a number's `art` can never be changed once the lock "
            "has committed it, so this is the last moment the mistake is recoverable."
        )


def add_number(
    study_dir: Path,
    alias: str,
    *,
    value: Any,
    art: str,
    claim: str | None = None,
    precision: int | None = None,
    note: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Give a headline number a home: its value, its artifact, its claim."""
    lock = load_lock(study_dir)
    _require_schema2(lock, "number")
    artifacts = lock.get("artifacts") or {}
    if art not in artifacts:
        raise WorkflowError(f"claims number: {art!r} is not a pinned artifact — `klein claims pin` it first")
    if claim is not None and claim not in CONTRACT_CLAIM_IDS and not CLAIM_ID_RE.match(claim):
        raise WorkflowError(
            f"claims number: --claim {claim!r} is neither a Cn id nor one of {CONTRACT_CLAIM_IDS}"
        )
    numbers = lock.setdefault("numbers", {})
    existing = numbers.get(alias)
    entry: dict[str, Any] = {"value": value, "art": art}
    if claim is not None:
        entry["claim"] = claim
    if precision is not None:
        entry["precision"] = precision
    if note is not None:
        entry["note"] = note
    if isinstance(existing, Mapping):
        for field, reader in (("value", lambda e: e.get("value")), ("art", _art_alias), ("claim", lambda e: e.get("claim"))):
            before = reader(existing)
            after = reader(entry)
            if field == "claim" and after is None:
                entry["claim"] = before
                continue
            if before != after:
                raise WorkflowError(
                    f"claims number: {alias!r} already pins {field}={before!r}; a number's "
                    f"{field} never changes (file an erratum instead)"
                )
        merged = dict(existing)
        merged.update(entry)
        entry = merged
    _refuse_homeless_number(study_dir, alias, entry, artifacts)
    numbers[alias] = entry
    if isinstance(claim, str) and CLAIM_ID_RE.match(claim):
        target = (lock.get("claims") or {}).get(claim)
        if isinstance(target, Mapping) and alias not in (target.get("numbers") or []):
            target.setdefault("numbers", []).append(alias)
            target["numbers"] = sorted(target["numbers"])
    write_lock(study_dir, lock)
    if commit:
        _commit(study_dir, f"claims: number {alias} = {value!r} ({art})")
    return entry


def add_claim(
    study_dir: Path,
    claim_id: str,
    *,
    claim_class: str,
    strength: str,
    claim: str,
    numbers: Sequence[str] = (),
    evidence: Sequence[str] = (),
    scope: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Record one claim with its class, strength, sentence, aliases and evidence."""
    lock = load_lock(study_dir)
    _require_schema2(lock, "add")
    if not CLAIM_ID_RE.match(claim_id):
        raise WorkflowError(f"claims add: {claim_id!r} is not a Cn id")
    if claim_class not in CLAIM_CLASSES:
        raise WorkflowError(f"claims add: unknown class {claim_class!r}; one of {sorted(CLAIM_CLASSES)}")
    if strength not in STRENGTHS:
        raise WorkflowError(f"claims add: unknown strength {strength!r}; one of {list(STRENGTHS)}")
    ceiling = CLAIM_CLASSES[claim_class]
    if STRENGTH_RANK[strength] > STRENGTH_RANK[ceiling]:
        raise WorkflowError(
            f"claims add: class {claim_class!r} ceilings at {ceiling!r} — "
            f"{strength!r} exceeds it (claims-protocol.md, the five classes)"
        )
    if strength == "refuted":
        raise WorkflowError(
            "claims add: 'refuted' is never written at first authoring — it is set by "
            "`klein claims erratum --strength refuted` or a later study's refutation"
        )
    known = lock.get("numbers") or {}
    unknown = [alias for alias in numbers if alias not in known]
    if unknown:
        raise WorkflowError(f"claims add: aliases not in 'numbers': {unknown}")
    entry: dict[str, Any] = {
        "class": claim_class,
        "strength": strength,
        "claim": claim,
        "numbers": sorted(set(numbers)),
        "evidence": list(evidence),
        "errata": [],
    }
    if claim_class == "known-dgp-teaching":
        entry["scope"] = scope or "in-silico"
    elif scope is not None:
        entry["scope"] = scope
    registry = lock.setdefault("claims", {})
    existing = registry.get(claim_id)
    if isinstance(existing, Mapping):
        # `init` writes a skeleton with class null; `add` authors it once. After
        # that the class, the sentence and the strength are frozen.
        if existing.get("class") is not None:
            for field in ("class", "claim"):
                if existing.get(field) != entry[field]:
                    raise WorkflowError(
                        f"claims add: {claim_id} already records {field}={existing.get(field)!r} — "
                        "a claim's class and sentence never change; file an erratum"
                    )
            if existing.get("strength") != entry["strength"]:
                raise WorkflowError(
                    f"claims add: {claim_id} is {existing.get('strength')!r}; a strength changes "
                    "only through `klein claims erratum`"
                )
        merged = dict(existing)
        merged.update(entry)
        merged["numbers"] = sorted(set(existing.get("numbers") or []) | set(entry["numbers"]))
        merged["evidence"] = list(existing.get("evidence") or []) + [
            item for item in entry["evidence"] if item not in (existing.get("evidence") or [])
        ]
        merged["errata"] = list(existing.get("errata") or [])
        entry = merged
    registry[claim_id] = entry
    write_lock(study_dir, lock)
    if commit:
        _commit(study_dir, f"claims: add {claim_id} ({claim_class}, {strength})")
    return entry


def file_erratum(
    study_dir: Path,
    erratum_id: str,
    *,
    claims: Sequence[str],
    note: str,
    strength: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Re-scope claims without deleting them: tag them, optionally downgrade, log the event."""
    lock = load_lock(study_dir)
    _require_schema2(lock, "erratum")
    registry = lock.get("claims") or {}
    named = [cid.strip() for cid in claims if cid.strip()]
    if not named:
        raise WorkflowError("claims erratum: name at least one claim")
    unknown = [cid for cid in named if cid not in registry]
    if unknown:
        raise WorkflowError(f"claims erratum: unknown claims {unknown}")
    if not note.strip():
        raise WorkflowError("claims erratum: --note says what is now known; it is not optional")
    if strength is not None:
        if strength not in STRENGTHS:
            raise WorkflowError(f"claims erratum: unknown strength {strength!r}")
        for cid in named:
            current = registry[cid].get("strength")
            if current in STRENGTH_RANK and STRENGTH_RANK[strength] >= STRENGTH_RANK[current]:
                raise WorkflowError(
                    f"claims erratum: {cid} is {current!r}; an erratum downgrades only "
                    f"({strength!r} is not weaker)"
                )
    errata = lock.setdefault("errata", {})
    if erratum_id in errata:
        raise WorkflowError(f"claims erratum: {erratum_id} is already filed — errata are appended")
    entry = {"filed": utc_now()[:10], "claims": named, "note": note}
    errata[erratum_id] = entry
    for cid in named:
        claim = registry[cid]
        tags = claim.setdefault("errata", [])
        if erratum_id not in tags:
            tags.append(erratum_id)
        if strength is not None:
            claim["strength"] = strength
    write_lock(study_dir, lock)
    append_event(
        study_dir,
        "erratum_filed",
        erratum=erratum_id,
        claims=named,
        note=note,
        strength=strength,
    )
    if commit:
        _commit(study_dir, f"claims: erratum {erratum_id} re-scopes {', '.join(named)}")
    return entry
