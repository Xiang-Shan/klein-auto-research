"""The ``benchmark`` capability — a planted truth, committed to before anyone looks.

"The system discovered the interaction" is worth exactly as much as the answer
was hard to obtain, and a benchmark is the only way to hold that constant.  This
capability implements the custodian half of one: a salted commitment recorded
before any participant sees the data, frozen submissions, a matching rule fixed
at METHOD, one sealed scoring cell, and a recomputation of every match from the
same bytes.

**Two studies, two roles, and they are not the same study.**  The CUSTODIAN owns
an ordinary ``simulate`` study that declares ``benchmark``: it holds the full DGP
card, the generator, the seed blocks, the structural truth and the scorer.  Each
PARTICIPANT owns a separate ``discover`` study — a different workspace, on a
different machine — that receives the public bundle only and declares no
``benchmark`` capability at all.  Every verb here runs in the custodian study;
``submit`` IMPORTS a participant's frozen file.

Four moves, in this order and no other:

1. **Commit** (``benchmark commit``), after the custodian's METHOD gate and
   before any participant access: hash the public bundle, compute
   ``sha256(salt ‖ private-bundle bytes)`` and ``sha256(salt)``, pin the scorer
   and the submission schema, and freeze the arms, budgets, hypothesis cap,
   false-positive penalty, matching rule, seed blocks and per-arm recovery
   predictions.  The salt itself never enters the repository.
2. **Submit** (``benchmark submit --arm``), once per arm, after the commitment
   and before the reveal: validate the participant's ranked structures against
   the schema and the cap, copy the file to ``submissions/<arm>.json``, hash it.
3. **Reveal** (``benchmark reveal``), after every arm has submitted (or has a
   recorded missing trial): recompute the commitment from the same salt and
   bundle.  A mismatch is REFUSED and RECORDED — ``benchmark_reveal_failed`` is
   evidence, not an error message.
4. **Score**: an ordinary ``klein run-one --final-test`` on the registered
   scoring track, admitted with ``--action sealed``, whose entrypoint calls the
   study's ``lib/score_submissions.py``, prints ``recall_<arm>``,
   ``precision_<arm>``, ``null_fp_<arm>``, ``cost_<arm>`` and (optionally)
   ``predictive_<arm>``, and pins ``tables/benchmark_scores.tsv`` — one row per
   arm × submitted structure with its match result.  ONE sealed cell covers all
   arms (R-BEN-4).

**What the machine matches, and what it does not.**  A submitted structure
matches a planted truth when its variable SET is the same, its relationship
string is the same, and its direction sign is the same — the three mechanical
conditions the locked ``matching_rule`` names.  The fourth condition A5 requires,
*context*, is written into the lock as a preregistered sentence and adjudicated
by the custodian per row: the pinned table carries a ``context_ok`` column, and a
row whose ``context_ok`` is 0 is not a match however well its variables line up.
Verification re-applies the three mechanical conditions and TAKES ``context_ok``
from the table — the oracle's judgement is labelled as such, never laundered into
arithmetic.

Each planted truth counts ONCE (A5 §3, "unique planted truths correctly
recovered"): the best-ranked structure that matches it claims it, a later
structure matching the same truth is a duplicate rather than a second recovery,
and a structure matching nothing is a false positive against which the declared
penalty is charged.

**What recovery establishes.**  In-silico performance on this generator, at this
sample size, under this matching rule.  Not real-world discovery: a
``known-dgp-teaching`` claim carries ``scope: in-silico``, and a ``confirmed``
claim resting on the scoring table is refused outright (R-INV-6).

**What a hash never establishes.**  Secrecy.  Byte integrity says the private
bundle did not change; it says nothing about who read it.  Isolation is accounts,
containers or machines with denied access — never another directory of the same
readable worktree — and the only record of it is a custody attestation
(:mod:`kleinlib.generation.custody`).  Without one the outcome is ``unverified``,
which is the honest word.  A benchmark known to have leaked is retired
(``benchmark retire``) and its results are RETAINED: the exercise happened, and
deleting it would be a second dishonesty on top of the first.

Registered, not wired in: this module exports one
:class:`~kleinlib.generation.registry.Capability` and the spine finds it through
:data:`kleinlib.generation.capabilities.MODULES`.  ``benchmark`` requires
``parity`` (``CAPABILITY_DEPENDENCIES``), which requires ``expertise``, so the
shared helpers imported from :mod:`kleinlib.generation.expert` add no edge the
manifest does not already demand.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..contract import normalize_tracks, registered_predictions
from ..errors import WorkflowError
from ..manifest import load_manifests
from ..primitives import canonical_json, sha256_bytes, sha256_file
from ..transaction import git_blob, relative
from . import custody as gc
from .chronology import run_started_events
from .envelope import GENERATION_SCHEMA
from .expert import _plain, joined
from .ledger import read_events
from .registry import Capability
from .verify import Check

if TYPE_CHECKING:  # pragma: no cover - types only
    from .admission import Context
    from .registry import FamilyContext

__all__ = [
    "BENCHMARK_NAME",
    "CAPABILITY",
    "CAPABILITY_NAME",
    "COMMIT_TYPE",
    "DIRECTIONS",
    "FRAMEWORKS",
    "OUTCOMES",
    "RETIRE_TYPE",
    "REVEAL_FAILED_TYPE",
    "REVEAL_POLICIES",
    "REVEAL_TYPE",
    "SCHEMA_NAME",
    "SCORES_TABLE",
    "SUBMISSIONS_DIR",
    "SUBMIT_TYPE",
    "arm_ids",
    "benchmark_family",
    "benchmark_path",
    "benchmark_subjects",
    "bundle_bytes",
    "commit_object",
    "commitment_of",
    "matches_mechanically",
    "read_benchmark_file",
    "read_scores_table",
    "read_submission",
    "read_truth",
    "retire_object",
    "reveal_object",
    "score_arms",
    "seed_block_overlap",
    "submission_object",
    "submission_problems",
    "validation_problems",
]

CAPABILITY_NAME = "benchmark"

#: The human artifact, at the study root beside ``study.yaml``.  A reviewer has
#: to be able to read the terms of the benchmark without opening the object store.
BENCHMARK_NAME = "benchmark.yaml"

#: Where an imported submission is filed, one file per arm.
SUBMISSIONS_DIR = "submissions"

#: The packaged submission schema, copied into the study by ``commit`` and
#: hashed there.  A study may extend it; the hash records which one was in force.
SCHEMA_NAME = "benchmark-submission.schema.json"

#: The pinned per-row table the sealed scoring cell prints and verify recomputes.
SCORES_TABLE = "tables/benchmark_scores.tsv"

COMMIT_TYPE = "benchmark_committed"
SUBMIT_TYPE = "benchmark_submitted"
REVEAL_TYPE = "benchmark_revealed"
REVEAL_FAILED_TYPE = "benchmark_reveal_failed"
RETIRE_TYPE = "benchmark_retired"

#: The sign vocabulary a structure's direction may carry.
DIRECTIONS: tuple[str, ...] = ("positive", "negative", "none")

#: What an arm ran.  ``none`` is the AI-free control A5's design requires.
FRAMEWORKS: tuple[str, ...] = ("klein-2.1", "klein-2.0", "none")

#: The only reveal policy this version implements: every arm first.
REVEAL_POLICIES: tuple[str, ...] = ("after-all-arms",)

#: The comparison this version implements for each matching-rule dimension.
#: ``context`` is deliberately absent: it is a preregistered SENTENCE the
#: custodian adjudicates, recorded per row as ``context_ok``.
MATCH_COMPARISONS: dict[str, tuple[str, ...]] = {
    "variables": ("exact",),
    "relationship": ("exact",),
    "direction": ("sign",),
}

#: The capability outcome.  ``unverified`` is not an integrity failure — it is
#: the word for a benchmark nobody attested custody of.
OUTCOMES: tuple[str, ...] = ("unscored", "scored", "retired", "unverified")

#: The columns the pinned table must carry, in this order.
SCORE_COLUMNS: tuple[str, ...] = (
    "arm",
    "rank",
    "variables",
    "relationship",
    "direction",
    "context_ok",
    "matched",
    "truth_id",
)

_NA = "NA"


# --------------------------------------------------------------------------
# the file
# --------------------------------------------------------------------------


def benchmark_path(study_dir: Path) -> Path:
    return study_dir / BENCHMARK_NAME


def read_benchmark_file(study_dir: Path) -> dict[str, Any]:
    path = benchmark_path(study_dir)
    if not path.is_file():
        raise WorkflowError(
            f"{BENCHMARK_NAME} does not exist — author it first "
            "(`.claude/skills/klein/assets/benchmark-template.yaml`)"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read {BENCHMARK_NAME}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{BENCHMARK_NAME} must contain a top-level mapping")
    return value


def arms(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("arms")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def arm_ids(payload: Mapping[str, Any]) -> list[str]:
    return [str(row.get("id")) for row in arms(payload)]


def seed_block_overlap(payload: Mapping[str, Any]) -> list[str]:
    """Seed-block ids that appear in BOTH the development and the sealed list."""
    blocks = payload.get("seed_blocks")
    if not isinstance(blocks, Mapping):
        return []
    development = {str(item) for item in _string_list(blocks.get("development"))}
    sealed = {str(item) for item in _string_list(blocks.get("sealed"))}
    return sorted(development & sealed)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str | int | float)]


# --------------------------------------------------------------------------
# the bundles and the commitment
# --------------------------------------------------------------------------


def bundle_bytes(path: Path) -> bytes:
    """The canonical bytes of a bundle — a file's own, a directory's manifest.

    A directory hashes as ``canonical_json([[relative path, sha256], …])`` over
    every file inside it, sorted by path: the same rule
    :func:`kleinlib.generation.admission.surface_digest` uses, so "what does this
    tree hash to" has one answer in this package rather than two.
    """
    if path.is_file():
        return path.read_bytes()
    if path.is_dir():
        entries = [
            [item.relative_to(path).as_posix(), sha256_file(item)]
            for item in sorted(path.rglob("*"))
            if item.is_file()
        ]
        if not entries:
            raise WorkflowError(f"bundle directory {path.name!r} is empty")
        return canonical_json(entries).encode()
    raise WorkflowError(f"bundle {path} does not exist")


def packaged_schema(repo: Path | None) -> Path | None:
    """The shipped ``benchmark-submission.schema.json``, if this install carries it.

    Looked for in the study's own repository first — a study vendored into a
    foreign repo may carry its own copy of the skill tree — and then beside the
    Klein source this process is running from.  A wheel install has neither, and
    the custodian is then told to place the participant-facing schema in the
    study by hand rather than having one invented for them.
    """
    roots: list[Path] = []
    if repo is not None:
        roots.append(repo)
    roots.append(Path(__file__).resolve().parents[2])
    for root in roots:
        candidate = root / ".claude" / "skills" / "klein" / "assets" / SCHEMA_NAME
        if candidate.is_file():
            return candidate
    return None


def commitment_of(salt: bytes, payload: bytes) -> str:
    """``sha256(salt ‖ canonical bundle bytes)`` — the salted commitment."""
    return sha256_bytes(salt + payload)


def read_salt(path: Path) -> bytes:
    try:
        salt = path.read_bytes()
    except OSError as exc:
        raise WorkflowError(f"could not read the salt file: {exc}") from exc
    if not salt.strip():
        raise WorkflowError(
            "the salt file is empty — an unsalted commitment of a small structural "
            "bundle is a guessable one"
        )
    return salt


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def _text_problem(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label} is required"]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(float(value)) else None


def _relative_path_problem(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label} is required (a study-relative path)"]
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return [f"{label} must be a study-relative path inside the study"]
    return []


def validation_problems(
    payload: Mapping[str, Any], *, study: str, contract: Mapping[str, Any]
) -> list[str]:
    """Everything wrong with an authored ``benchmark.yaml``, one line each."""
    problems: list[str] = []
    if payload.get("type") not in (None, "benchmark"):
        problems.append(f"type is {payload.get('type')!r}, expected 'benchmark'")
    declared_study = payload.get("study")
    if declared_study is not None and str(declared_study) != study:
        problems.append(f"study is {declared_study!r}, expected {study!r}")

    tracks = normalize_tracks(contract)
    track = payload.get("scoring_track")
    spec = tracks.get(str(track)) if isinstance(track, str) else None
    if spec is None:
        problems.append(
            f"scoring_track {track!r} is not declared in study.yaml "
            f"(declared: {', '.join(sorted(tracks)) or 'none'})"
        )
    elif str(spec.get("mode", "frontier")) != "registered":
        problems.append(
            f"scoring_track {track!r} is a {spec.get('mode', 'frontier')!r} track; scoring "
            "is a registered cell, not a frontier candidate "
            "(`references/registered-mode.md`)"
        )

    problems.extend(_bundle_problems(payload.get("public_bundle"), "public_bundle"))
    problems.extend(_relative_path_problem(payload.get("truth_file"), "truth_file"))
    problems.extend(_commitment_problems(payload.get("private_commitment")))
    problems.extend(_custody_problems(payload.get("custody")))
    problems.extend(_arm_problems(payload))
    problems.extend(_matching_rule_problems(payload.get("matching_rule")))
    problems.extend(_seed_block_problems(payload))

    cap = payload.get("hypothesis_cap")
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        problems.append(
            "hypothesis_cap must be an integer >= 1 — the cap is what stops an arm from "
            "listing every possible interaction and calling one of them a discovery"
        )
    penalty = _number(payload.get("false_positive_penalty"))
    if penalty is None or penalty < 0:
        problems.append(
            "false_positive_penalty must be a finite number >= 0 (charged per structure "
            "that matches no planted truth)"
        )
    if payload.get("reveal_policy") not in REVEAL_POLICIES:
        problems.append(
            f"reveal_policy is {payload.get('reveal_policy')!r}; this version implements "
            + ", ".join(REVEAL_POLICIES)
        )

    scorer = payload.get("scorer")
    if not isinstance(scorer, Mapping):
        problems.append("scorer.path is required (e.g. lib/score_submissions.py)")
    else:
        problems.extend(_relative_path_problem(scorer.get("path"), "scorer.path"))
    problems.extend(
        _relative_path_problem(payload.get("submission_schema"), "submission_schema")
    )
    problems.extend(_recovery_prediction_problems(payload, contract))
    return problems


def _bundle_problems(value: Any, label: str) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{label} must declare a path (and, once committed, its sha256)"]
    problems = _relative_path_problem(value.get("path"), f"{label}.path")
    digest = value.get("sha256")
    if digest is not None and not (isinstance(digest, str) and len(digest) == 64):
        problems.append(
            f"{label}.sha256 must be a sha256 hex digest or null (`benchmark commit` "
            "computes it and refuses a declared value that disagrees)"
        )
    return problems


def _commitment_problems(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return [
            "private_commitment must be null (computed by `benchmark commit`) or a "
            "mapping of sha256 and salt_sha256"
        ]
    problems: list[str] = []
    for key in ("sha256", "salt_sha256"):
        digest = value.get(key)
        if digest is not None and not (isinstance(digest, str) and len(digest) == 64):
            problems.append(f"private_commitment.{key} must be a sha256 hex digest or null")
    return problems


def _custody_problems(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return [
            "custody must name the holder and the mechanism (accounts, containers or "
            "machines — a directory of the same checkout is not isolation)"
        ]
    problems = _text_problem(value.get("holder"), "custody.holder")
    problems += _text_problem(value.get("mechanism"), "custody.mechanism")
    if "attestation" not in value:
        problems.append(
            "custody.attestation is required (a study-relative path to the attestation "
            "document, or null — `klein generation custody attest` records the testimony "
            "either way)"
        )
    elif value.get("attestation") is not None:
        problems.extend(
            _relative_path_problem(value.get("attestation"), "custody.attestation")
        )
    return problems


def _arm_problems(payload: Mapping[str, Any]) -> list[str]:
    rows = payload.get("arms")
    if not isinstance(rows, list) or not rows:
        return ["arms must be a non-empty list — a benchmark with no arm measures nothing"]
    problems: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, Mapping):
            problems.append(f"arm {index}: must be a mapping")
            continue
        arm = raw.get("id")
        label = f"arm {arm!r}" if isinstance(arm, str) and arm else f"arm {index}"
        if not isinstance(arm, str) or not arm.strip():
            problems.append(f"{label}: id is required (a short id, e.g. arm-a)")
        elif not arm.replace("-", "").replace("_", "").isalnum():
            problems.append(f"{label}: id must be alphanumeric with dashes or underscores")
        elif arm in seen:
            problems.append(f"{label}: id is listed twice")
        else:
            seen.add(arm)
        problems.extend(_text_problem(raw.get("description"), f"{label}: description"))
        problems.extend(_text_problem(raw.get("model"), f"{label}: model"))
        if raw.get("framework") not in FRAMEWORKS:
            problems.append(
                f"{label}: framework is {raw.get('framework')!r}, expected one of "
                + ", ".join(FRAMEWORKS)
            )
        budget = raw.get("budget")
        if not isinstance(budget, Mapping) or not budget:
            problems.append(
                f"{label}: budget must name at least one unit and its amount — arms that "
                "did not have matched resources were not compared"
            )
        elif any(_number(item) is None for item in budget.values()):
            problems.append(f"{label}: every budget amount must be a finite number")
    return problems


def _matching_rule_problems(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return [
            "matching_rule must declare variables, relationship, direction and context "
            "— fixed at METHOD, before any submission (R-BEN-2)"
        ]
    problems: list[str] = []
    for key, allowed in MATCH_COMPARISONS.items():
        if value.get(key) not in allowed:
            problems.append(
                f"matching_rule.{key} is {value.get(key)!r}; this version implements "
                + ", ".join(allowed)
            )
    problems.extend(
        _text_problem(
            value.get("context"),
            "matching_rule.context (the preregistered sentence the custodian adjudicates "
            "per row, recorded as the table's context_ok column)",
        )
    )
    return problems


def _seed_block_problems(payload: Mapping[str, Any]) -> list[str]:
    blocks = payload.get("seed_blocks")
    if not isinstance(blocks, Mapping):
        return ["seed_blocks must name a development list and a sealed list"]
    problems: list[str] = []
    for key in ("development", "sealed"):
        if not _string_list(blocks.get(key)):
            problems.append(f"seed_blocks.{key} must be a non-empty list of block ids")
    overlap = seed_block_overlap(payload)
    if overlap:
        problems.append(
            "seed_blocks.development and seed_blocks.sealed share "
            + ", ".join(overlap)
            + " — a block scored as sealed evidence after it was handed out as development "
            "data is not sealed evidence (R-BEN-4)"
        )
    return problems


def _recovery_prediction_problems(
    payload: Mapping[str, Any], contract: Mapping[str, Any]
) -> list[str]:
    """Every arm names the registered predictions its recovery adjudicates."""
    declared = payload.get("recovery_predictions")
    if not isinstance(declared, Mapping):
        return [
            "recovery_predictions must map every arm id to the registered prediction ids "
            "that adjudicate its recovery"
        ]
    registered = registered_predictions(contract)
    track = payload.get("scoring_track")
    ids = arm_ids(payload)
    problems: list[str] = []
    for arm in ids:
        names = declared.get(arm)
        if not isinstance(names, list) or not names:
            problems.append(f"recovery_predictions.{arm} must list at least one P#")
            continue
        for name in names:
            entry = registered.get(str(name))
            if entry is None:
                problems.append(
                    f"recovery_predictions.{arm} names {name!r}, which study.yaml does not "
                    f"register ({', '.join(sorted(registered)) or 'none registered'})"
                )
            elif entry.get("track") is not None and str(entry["track"]) != str(track):
                problems.append(
                    f"{name} belongs to track {entry.get('track')!r}, not the scoring track "
                    f"{track!r}"
                )
    extra = [str(key) for key in declared if key not in set(ids)]
    if extra:
        problems.append(
            "recovery_predictions names arm(s) the benchmark does not declare: "
            + ", ".join(sorted(extra))
        )
    return problems


# --------------------------------------------------------------------------
# submissions
# --------------------------------------------------------------------------


def read_submission(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"could not read the submission {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{path.name} must contain a top-level JSON object")
    return value


def submission_problems(payload: Mapping[str, Any], *, arm: str, cap: int) -> list[str]:
    """The submission schema, enforced in plain Python.

    The packaged ``benchmark-submission.schema.json`` states the same rules in
    JSON Schema for the participant's tooling and is hashed into the commitment;
    Klein depends on no schema library, so the authority here is this function
    and the two are kept in step by the tests.
    """
    problems: list[str] = []
    declared_arm = payload.get("arm")
    if declared_arm is not None and str(declared_arm) != arm:
        problems.append(f"the file declares arm {declared_arm!r}, imported as {arm!r}")
    problems.extend(_text_problem(payload.get("study"), "study (the participant's study id)"))
    rows = payload.get("structures")
    if not isinstance(rows, list):
        return [*problems, "structures must be a list of ranked structures"]
    if len(rows) > cap:
        problems.append(
            f"{len(rows)} structures submitted; the committed cap is {cap} — the cap is "
            "what makes precision mean something"
        )
    ranks: set[int] = set()
    for index, raw in enumerate(rows, start=1):
        label = f"structure {index}"
        if not isinstance(raw, Mapping):
            problems.append(f"{label}: must be a mapping")
            continue
        rank = raw.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            problems.append(f"{label}: rank must be an integer >= 1")
        elif rank in ranks:
            problems.append(f"{label}: rank {rank} is used twice")
        else:
            ranks.add(rank)
        variables = raw.get("variables")
        if (
            not isinstance(variables, list)
            or not variables
            or any(not isinstance(item, str) or not item.strip() for item in variables)
        ):
            problems.append(f"{label}: variables must be a non-empty list of names")
        elif len({item.strip() for item in variables}) != len(variables):
            problems.append(f"{label}: variables lists a name twice")
        problems.extend(_text_problem(raw.get("relationship"), f"{label}: relationship"))
        if raw.get("direction") not in DIRECTIONS:
            problems.append(
                f"{label}: direction is {raw.get('direction')!r}, expected one of "
                + ", ".join(DIRECTIONS)
            )
        if not isinstance(raw.get("context"), str):
            problems.append(f"{label}: context must be a string (it may be empty)")
        h_ids = raw.get("h_ids")
        if not isinstance(h_ids, list) or any(not isinstance(item, str) for item in h_ids):
            problems.append(
                f"{label}: h_ids must be a list of <study>#Hn ids (empty means the arm "
                "recorded no hypothesis provenance)"
            )
    return problems


def submission_structures(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The submitted structures in RANK order — the order recovery is scored in."""
    rows = payload.get("structures")
    if not isinstance(rows, list):
        return []
    structures = [dict(row) for row in rows if isinstance(row, Mapping)]
    return sorted(structures, key=lambda row: (_int(row.get("rank")), _key(row)))


def _int(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _key(row: Mapping[str, Any]) -> str:
    return canonical_json(_plain(dict(row)))


# --------------------------------------------------------------------------
# the truth, and the matching rule
# --------------------------------------------------------------------------


def read_truth(path: Path) -> list[dict[str, Any]]:
    """The revealed planted structures, in declaration order.

    Shape: ``{"structures": [{"id", "variables": [...], "relationship",
    "direction", "context", "seed_block"}, …]}``.  A null-only benchmark
    declares ``structures: []`` — recall is then undefined and the false-positive
    rate is the whole result (A5 §3).
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"could not read the revealed truth {path.name}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("structures"), list):
        raise WorkflowError(
            f"{path.name} must be an object with a 'structures' list of planted structures"
        )
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(value["structures"], start=1):
        if not isinstance(raw, Mapping):
            raise WorkflowError(f"{path.name}: planted structure {index} is not a mapping")
        row = dict(raw)
        if not isinstance(row.get("id"), str) or not row["id"].strip():
            raise WorkflowError(f"{path.name}: planted structure {index} has no id")
        rows.append(row)
    return rows


def _variable_set(row: Mapping[str, Any]) -> tuple[str, ...]:
    value = row.get("variables")
    if not isinstance(value, list):
        return ()
    return tuple(sorted({str(item).strip().casefold() for item in value}))


def _norm(value: Any) -> str:
    return str(value).strip().casefold()


def matches_mechanically(structure: Mapping[str, Any], truth: Mapping[str, Any]) -> bool:
    """The three conditions a machine can decide: variables, relationship, sign.

    The fourth — context — is the custodian's preregistered adjudication and
    arrives as the pinned table's ``context_ok`` column.
    """
    return (
        _variable_set(structure) == _variable_set(truth)
        and _variable_set(structure) != ()
        and _norm(structure.get("relationship")) == _norm(truth.get("relationship"))
        and _norm(structure.get("direction")) == _norm(truth.get("direction"))
    )


def score_arms(
    submissions: Mapping[str, Sequence[Mapping[str, Any]]],
    truth: Sequence[Mapping[str, Any]],
    context_ok: Mapping[tuple[str, int], bool],
    *,
    penalty: float,
) -> dict[str, Any]:
    """Recompute every row and every arm's metrics from the same three inputs.

    Returns ``{"rows": [...], "arms": {...}}``.  ``rows`` is the table this
    function says the scorer should have pinned, one entry per arm × submitted
    structure, in the same order; ``arms`` carries recall, precision, the
    false-positive count and the charged penalty.

    Each planted truth is claimed ONCE, by the best-ranked structure that matches
    it: a later structure matching the same truth is a duplicate (``matched`` 0
    with a ``truth_id``), and a structure matching nothing is a false positive
    (``matched`` 0 with ``truth_id`` ``NA``).
    """
    truth_ids = [str(row.get("id")) for row in truth]
    rows: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    for arm in sorted(submissions):
        claimed: dict[str, str] = {}
        matched = 0
        false_positives = 0
        for structure in submissions[arm]:
            rank = _int(structure.get("rank"))
            adjudicated = bool(context_ok.get((arm, rank), False))
            candidates = [
                str(row.get("id"))
                for row in truth
                if adjudicated and matches_mechanically(structure, row)
            ]
            free = [tid for tid in candidates if tid not in claimed]
            if free:
                tid = free[0]
                claimed[tid] = arm
                matched += 1
                row_truth: str | None = tid
                row_matched = 1
            elif candidates:
                row_truth = candidates[0]
                row_matched = 0
            else:
                row_truth = None
                row_matched = 0
                false_positives += 1
            rows.append(
                {
                    "arm": arm,
                    "rank": rank,
                    "variables": [str(item) for item in structure.get("variables") or ()],
                    "relationship": str(structure.get("relationship")),
                    "direction": str(structure.get("direction")),
                    "context_ok": 1 if adjudicated else 0,
                    "matched": row_matched,
                    "truth_id": row_truth,
                }
            )
        submitted = len(submissions[arm])
        metrics[arm] = {
            "recall": (len(claimed) / len(truth_ids)) if truth_ids else None,
            "precision": (matched / submitted) if submitted else None,
            "null_fp": float(false_positives),
            "penalty": float(false_positives) * float(penalty),
            "submitted": float(submitted),
            "recovered": float(len(claimed)),
        }
    return {"rows": rows, "arms": metrics}


def read_scores_table(path: Path) -> list[dict[str, Any]]:
    """Parse ``tables/benchmark_scores.tsv`` into one dict per row."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"could not read {path.name}: {exc}") from exc
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise WorkflowError(f"{path.name} is empty")
    header = lines[0].split("\t")
    missing = [name for name in SCORE_COLUMNS if name not in header]
    if missing:
        raise WorkflowError(
            f"{path.name} is missing column(s): {', '.join(missing)} — the pinned table "
            "carries one row per arm and submitted structure with its match result"
        )
    index = {name: header.index(name) for name in header}
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != len(header):
            raise WorkflowError(
                f"{path.name} line {number}: {len(cells)} cells, header has {len(header)}"
            )
        raw_truth = cells[index["truth_id"]].strip()
        rows.append(
            {
                "arm": cells[index["arm"]].strip(),
                "rank": _cell_int(cells[index["rank"]], path.name, number, "rank"),
                "variables": [
                    item.strip()
                    for item in cells[index["variables"]].split(",")
                    if item.strip()
                ],
                "relationship": cells[index["relationship"]].strip(),
                "direction": cells[index["direction"]].strip(),
                "context_ok": _cell_int(cells[index["context_ok"]], path.name, number, "context_ok"),
                "matched": _cell_int(cells[index["matched"]], path.name, number, "matched"),
                "truth_id": None if raw_truth in ("", _NA) else raw_truth,
            }
        )
    return rows


def _cell_int(raw: str, where: str, line: int, column: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise WorkflowError(f"{where} line {line}: {column} is {raw.strip()!r}") from exc


# --------------------------------------------------------------------------
# object builders
# --------------------------------------------------------------------------


def commit_object(
    *,
    study: str,
    payload: Mapping[str, Any],
    file_sha256: str,
    public_bundle: Mapping[str, Any],
    private_commitment: Mapping[str, Any],
    scorer: Mapping[str, Any],
    submission_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """The commitment: the file VERBATIM plus everything hashed at commit time."""
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "benchmark_commit",
        "study": study,
        "file_path": BENCHMARK_NAME,
        "file_sha256": file_sha256,
        # PyYAML resolves an unquoted `2026-09-05` to a `date`, which the object
        # store's canonical JSON cannot carry; `_plain` is the package's shared
        # coercion rather than a third copy of it.
        "payload": _plain(payload),
        "public_bundle": dict(public_bundle),
        "private_commitment": dict(private_commitment),
        "scorer": dict(scorer),
        "submission_schema": dict(submission_schema),
    }


def submission_object(
    *,
    study: str,
    arm: str,
    commit_sha: str,
    file_path: str,
    file_sha256: str,
    structures: int,
    participant: str | None,
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "benchmark_submission",
        "study": study,
        "arm": arm,
        "commit_object": commit_sha,
        "participant": participant or None,
        "file_path": file_path,
        "file_sha256": file_sha256,
        "structures": int(structures),
    }


def reveal_object(
    *,
    study: str,
    commit_sha: str,
    commitment: str,
    salt_sha256: str,
    private_bundle: Mapping[str, Any],
    truth: Mapping[str, Any],
    missing_arms: Sequence[Mapping[str, Any]],
    matched: bool,
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        # A reveal that did not recompute is a DIFFERENT kind of object, not a
        # reveal with a flag: a reader walking the store must not have to know
        # that `matched: false` voids everything else in the record.
        "kind": "benchmark_reveal" if matched else "benchmark_reveal_failed",
        "study": study,
        "commit_object": commit_sha,
        "commitment": commitment,
        "salt_sha256": salt_sha256,
        "private_bundle": dict(private_bundle),
        "truth": dict(truth),
        "missing_arms": [dict(row) for row in missing_arms],
        "matched": bool(matched),
    }


def retire_object(*, study: str, commit_sha: str, reason: str) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "kind": "benchmark_retirement",
        "study": study,
        "commit_object": commit_sha,
        "reason": reason,
    }


# --------------------------------------------------------------------------
# chain reads
# --------------------------------------------------------------------------


def commits(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    return joined(study_dir, events, COMMIT_TYPE)


def submissions(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    return joined(study_dir, events, SUBMIT_TYPE)


def reveals(
    study_dir: Path, events: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    return joined(study_dir, events, REVEAL_TYPE)


def _sequence(event: Mapping[str, Any]) -> int:
    return int(event.get("sequence") or 0)


def _core_sequence(event: Mapping[str, Any]) -> int:
    anchor = event.get("core_anchor")
    return int(anchor.get("sequence") or 0) if isinstance(anchor, Mapping) else 0


def _artifact_sha(manifest: Mapping[str, Any], rel: str) -> str | None:
    artifacts = manifest.get("artifacts")
    entry = artifacts.get(rel) if isinstance(artifacts, Mapping) else None
    sha = entry.get("sha256") if isinstance(entry, Mapping) else None
    return sha if isinstance(sha, str) else None


# --------------------------------------------------------------------------
# admission (registered into the spine, never appended to its list)
# --------------------------------------------------------------------------


def _rule_sealed_scoring_needs_a_reveal(ctx: Context) -> list[str]:
    """The scoring track's seal cannot be spent before the truth is revealed.

    Scoring reads the revealed structures; a sealed look taken before the reveal
    either scored against nothing or scored against a truth the custodian had
    privately and had not yet committed to disclosing.  Both are the same
    problem, and this is where it is refused — before the look, not after it.
    """
    if ctx.action != "sealed":
        return []
    events = read_events(ctx.study_dir)
    locked = commits(ctx.study_dir, events)
    if not locked:
        return []
    payload = locked[-1][1].get("payload") or {}
    if str(payload.get("scoring_track")) != str(ctx.track):
        return []
    if reveals(ctx.study_dir, events):
        return []
    return [
        f"track {ctx.track!r} is the benchmark's scoring track and no `klein generation "
        "benchmark reveal` has recomputed the commitment: every arm submits, then the "
        "private bundle is revealed, and only then is the scoring cell sealed (R-BEN-1)"
    ]


def _receipt_inputs(ctx: Context) -> dict[str, str | None]:
    """Which benchmark artifact was in force when this admission was taken."""
    events = read_events(ctx.study_dir)
    revealed = reveals(ctx.study_dir, events)
    if revealed:
        return {"benchmark": str(revealed[-1][0].get("payload_sha256"))}
    locked = commits(ctx.study_dir, events)
    return {"benchmark": str(locked[-1][0].get("payload_sha256"))} if locked else {}


# --------------------------------------------------------------------------
# the verify family
# --------------------------------------------------------------------------

COMMITMENT_CHECK = "benchmark commitment"
SUBMISSION_CHECK = "benchmark submissions"
SCORER_CHECK = "benchmark scorer"
SCORING_CHECK = "benchmark scoring"
CUSTODY_CHECK = "benchmark custody"
CEILING_CHECK = "benchmark ceiling"

#: How far a printed metric may sit from the recomputed one.  Recall and
#: precision are exact rationals over small integers, so the only honest source
#: of a gap is the scorer's own print precision — six decimals costs 5e-7.
PRINT_TOLERANCE = 1e-6


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def benchmark_family(ctx: FamilyContext) -> tuple[list[Check], dict[str, Any]]:
    """The ``benchmark`` family: integrity of the record, then the outcome."""
    events = list(ctx.events)
    locked = commits(ctx.study_dir, events)
    submitted = submissions(ctx.study_dir, events)
    revealed = reveals(ctx.study_dir, events)
    failed_reveals = joined(ctx.study_dir, events, REVEAL_FAILED_TYPE)
    retired = joined(ctx.study_dir, events, RETIRE_TYPE)
    attested = gc.attestations(ctx.study_dir, events)

    checks: list[Check] = []
    checks += _commitment_checks(ctx, locked, revealed, failed_reveals)
    payload: Mapping[str, Any] = (
        locked[-1][1].get("payload") if locked and isinstance(locked[-1][1].get("payload"), Mapping)
        else {}
    )
    checks += _submission_checks(ctx, payload, locked, submitted, revealed)

    try:
        manifests = {str(m.get("experiment")): m for m in load_manifests(ctx.study_dir)}
    except WorkflowError as exc:
        manifests = {}
        checks.append(_fail(SCORING_CHECK, f"run manifests unreadable: {exc}"))

    sealed = _scoring_runs(payload, manifests)
    checks += _scorer_checks(ctx, locked, sealed, manifests)
    scoring_checks, arm_metrics, scored = _scoring_checks(
        ctx, payload, locked, submitted, revealed, sealed, manifests
    )
    checks += scoring_checks
    checks += _custody_checks(ctx, payload, attested)
    checks += _ceiling_checks(ctx)
    if retired:
        checks.append(
            _warn(
                COMMITMENT_CHECK,
                "the benchmark is retired from hidden evaluation ("
                + str(retired[-1][1].get("reason"))
                + ") — its results are RETAINED and stay readable; it is simply never used "
                "as a hidden benchmark again",
            )
        )

    # Only attestations ABOUT this benchmark move its custody word.
    state = gc.custody_state(_split_attestations(payload, attested)[0])
    if retired:
        outcome = "retired"
    elif state == gc.UNVERIFIED:
        outcome = "unverified"
    elif scored:
        outcome = "scored"
    else:
        outcome = "unscored"
    integrity = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return checks, {
        "integrity": integrity,
        "outcome": outcome,
        "custody": state,
        "arms": arm_metrics,
    }


def _commitment_checks(
    ctx: FamilyContext,
    locked: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    revealed: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    failed: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    if not locked:
        return [
            _fail(
                COMMITMENT_CHECK,
                f"{BENCHMARK_NAME} is not committed — `klein generation benchmark commit` "
                "records the salted commitment before any participant sees the public bundle",
            )
        ]
    problems: list[str] = []
    if len(locked) > 1:
        problems.append(
            f"{len(locked)} commitments recorded; a benchmark commits ONCE and the terms "
            "are frozen from that moment"
        )
    event, obj = locked[-1]
    path = benchmark_path(ctx.study_dir)
    if not path.is_file():
        problems.append(f"{BENCHMARK_NAME} is missing; the commitment hashed it")
    elif sha256_file(path) != obj.get("file_sha256"):
        problems.append(
            f"{BENCHMARK_NAME} is {sha256_file(path)[:12]}… but the commitment recorded "
            f"{str(obj.get('file_sha256'))[:12]}… — committed terms are immutable"
        )
    payload = obj.get("payload") if isinstance(obj.get("payload"), Mapping) else {}
    problems.extend(
        f"seed blocks overlap: {name}" for name in seed_block_overlap(payload)
    )
    problems.extend(_recovery_prediction_problems(payload, ctx.contract))
    for reveal_event, _reveal in failed:
        problems.append(
            f"{reveal_event.get('id')}: a reveal did not recompute to the commitment — the "
            "bundle disclosed is not the bundle committed to (R-BEN-1)"
        )
    if len(revealed) > 1:
        problems.append(f"{len(revealed)} reveals recorded; the bundle is disclosed once")
    problems.extend(_reveal_problems(ctx, obj, revealed))
    if problems:
        return [_fail(COMMITMENT_CHECK, "; ".join(problems[:6]))]
    blocks = payload.get("seed_blocks") if isinstance(payload.get("seed_blocks"), Mapping) else {}
    commitment = str((obj.get("private_commitment") or {}).get("sha256"))
    detail = (
        f"commitment {commitment[:12]}… anchored at core sequence {_core_sequence(event)}; "
        f"{len(_string_list(blocks.get('development')))} development and "
        f"{len(_string_list(blocks.get('sealed')))} sealed seed block(s), disjoint"
    )
    checks = [_pass(COMMITMENT_CHECK, detail)]
    if revealed:
        checks.append(
            _pass(
                COMMITMENT_CHECK,
                f"{revealed[-1][0].get('id')} revealed the bundle and it recomputed to the "
                "commitment (the salt itself is never in the repository, so this is the "
                "reveal's own arithmetic, re-checked against its recorded result)",
            )
        )
    return checks


def _reveal_problems(
    ctx: FamilyContext,
    commit: Mapping[str, Any],
    revealed: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[str]:
    """The reveal names the same commitment, the same salt, and the same bytes."""
    if not revealed:
        return []
    _event, obj = revealed[-1]
    pinned = commit.get("private_commitment") if isinstance(commit.get("private_commitment"), Mapping) else {}
    problems: list[str] = []
    if obj.get("commitment") != pinned.get("sha256"):
        problems.append(
            "the reveal records a commitment that is not the one committed to "
            f"({str(obj.get('commitment'))[:12]}… vs {str(pinned.get('sha256'))[:12]}…)"
        )
    if obj.get("salt_sha256") != pinned.get("salt_sha256"):
        problems.append("the reveal used a different salt than the commitment pinned")
    if not obj.get("matched"):
        problems.append("the reveal is recorded as not matching its commitment")
    truth = obj.get("truth") if isinstance(obj.get("truth"), Mapping) else {}
    rel = truth.get("path")
    if not isinstance(rel, str):
        problems.append("the reveal records no revealed truth file")
    else:
        path = ctx.study_dir / rel
        if not path.is_file():
            problems.append(f"the revealed truth {rel} is missing")
        elif sha256_file(path) != truth.get("sha256"):
            problems.append(
                f"the revealed truth {rel} is not the file the reveal hashed — the bytes "
                "the scoring cell read must be the bytes inside the commitment"
            )
    return problems


def _submission_checks(
    ctx: FamilyContext,
    payload: Mapping[str, Any],
    locked: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    submitted: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    revealed: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    if not locked:
        return []
    commit_sequence = _sequence(locked[-1][0])
    reveal_sequence = _sequence(revealed[-1][0]) if revealed else None
    cap = payload.get("hypothesis_cap")
    cap = cap if isinstance(cap, int) and not isinstance(cap, bool) else 0
    declared = set(arm_ids(payload))
    problems: list[str] = []
    seen: dict[str, str] = {}
    for event, obj in submitted:
        arm = str(obj.get("arm"))
        label = f"{event.get('id')} ({arm})"
        if _sequence(event) < commit_sequence:
            problems.append(f"{label}: submitted before the commitment")
        if reveal_sequence is not None and _sequence(event) > reveal_sequence:
            problems.append(
                f"{label}: submitted AFTER the reveal — a submission that saw the answer "
                "is not a submission (R-BEN-2)"
            )
        if arm in seen:
            problems.append(f"{label}: arm already submitted by {seen[arm]}")
        else:
            seen[arm] = str(event.get("id"))
        if arm not in declared:
            problems.append(f"{label}: the benchmark declares no such arm")
        rel = obj.get("file_path")
        if isinstance(rel, str):
            path = ctx.study_dir / rel
            if not path.is_file():
                problems.append(f"{label}: {rel} is missing")
            elif sha256_file(path) != obj.get("file_sha256"):
                problems.append(
                    f"{label}: {rel} is not the file that was imported — a frozen "
                    "submission is frozen"
                )
        count = obj.get("structures")
        if cap and isinstance(count, int) and count > cap:
            problems.append(f"{label}: {count} structures against a cap of {cap}")
    missing_recorded = {
        str(row.get("arm"))
        for _event, obj in revealed
        for row in obj.get("missing_arms") or ()
        if isinstance(row, Mapping)
    }
    if revealed:
        for arm in sorted(declared - set(seen) - missing_recorded):
            problems.append(
                f"arm {arm!r} never submitted and no missing trial was recorded for it — a "
                "missing arm is a recorded trial, not an absence"
            )
    if problems:
        return [_fail(SUBMISSION_CHECK, "; ".join(problems[:6]))]
    checks = [
        _pass(
            SUBMISSION_CHECK,
            f"{len(seen)} of {len(declared)} arm(s) submitted between the commitment and "
            f"the reveal, each within the cap of {cap}"
            if revealed
            else f"{len(seen)} of {len(declared)} arm(s) submitted; no reveal yet",
        )
    ]
    if missing_recorded:
        checks.append(
            _warn(
                SUBMISSION_CHECK,
                "missing trial(s) recorded at the reveal: "
                + ", ".join(sorted(missing_recorded))
                + " — counted in the denominator, never dropped from it",
            )
        )
    return checks


def _scoring_runs(
    payload: Mapping[str, Any], manifests: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    track = str(payload.get("scoring_track"))
    return sorted(
        str(m.get("experiment"))
        for m in manifests.values()
        if m.get("evaluation_kind") == "final_test" and str(m.get("track")) == track
    )


def _scorer_checks(
    ctx: FamilyContext,
    locked: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    sealed: Sequence[str],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[Check]:
    """R-INV-3: the checker is never the searcher, and never changes after it.

    The pin is read at the SCORING cell's candidate commit, because that is the
    scorer the sealed evidence actually ran through; before that cell exists the
    on-disk file is compared instead, as a warning rather than a verdict.
    """
    if not locked:
        return []
    scorer = locked[-1][1].get("scorer")
    scorer = scorer if isinstance(scorer, Mapping) else {}
    rel = scorer.get("path")
    if not isinstance(rel, str):
        return [_fail(SCORER_CHECK, "the commitment pinned no scorer path")]
    pinned = scorer.get("sha256")
    if not sealed:
        path = ctx.study_dir / rel
        if not path.is_file():
            return [_warn(SCORER_CHECK, f"{rel} is missing; the commitment pinned it")]
        if sha256_file(path) != pinned:
            return [
                _warn(
                    SCORER_CHECK,
                    f"{rel} has changed since the commitment; the pin is re-read at the "
                    "scoring cell's candidate commit, and a scorer edited after the "
                    "submissions arrived is a scorer tuned to the answers",
                )
            ]
        return [_pass(SCORER_CHECK, f"{rel} still matches the pinned {str(pinned)[:12]}…")]
    if ctx.repo is None:
        return [_warn(SCORER_CHECK, "not a git repository; the pinned scorer cannot be read")]
    run = sealed[0]
    candidate = manifests.get(run, {}).get("candidate_commit")
    if not isinstance(candidate, str):
        return [_fail(SCORER_CHECK, f"{run} has no candidate commit to read the scorer at")]
    blob = git_blob(ctx.repo, candidate, relative(ctx.repo, ctx.study_dir / rel))
    if blob is None:
        return [_fail(SCORER_CHECK, f"{rel} is absent from {candidate[:12]} ({run})")]
    if sha256_bytes(blob) != pinned:
        return [
            _fail(
                SCORER_CHECK,
                f"{rel} at {candidate[:12]} is not the scorer the commitment pinned "
                f"({str(pinned)[:12]}…) — the matching code is frozen at METHOD, before "
                "any submission (R-BEN-2)",
            )
        ]
    return [
        _pass(SCORER_CHECK, f"{rel} at {run}'s candidate commit IS the pinned {str(pinned)[:12]}…")
    ]


def _scoring_checks(
    ctx: FamilyContext,
    payload: Mapping[str, Any],
    locked: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    submitted: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    revealed: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    sealed: Sequence[str],
    manifests: Mapping[str, Mapping[str, Any]],
) -> tuple[list[Check], dict[str, Any], bool]:
    if not locked:
        return [], {}, False
    if not sealed:
        return (
            [
                _warn(
                    SCORING_CHECK,
                    "no sealed scoring cell yet — one registered cell scores every arm, "
                    "after the reveal",
                )
            ],
            {},
            False,
        )
    problems: list[str] = []
    if len(sealed) > 1:
        problems.append(
            f"track {payload.get('scoring_track')!r} has {len(sealed)} sealed runs "
            f"({', '.join(sealed)}); ONE sealed scoring cell covers all arms (R-BEN-4)"
        )
    run = sealed[0]
    manifest = manifests[run]
    receipt = _consumed_receipt(ctx, run)
    if receipt is None:
        problems.append(f"{run} consumed no admission receipt")
    elif receipt.checkpoint != "sealed":
        problems.append(
            f"{run} was admitted as {receipt.checkpoint!r}; the scoring cell is a sealed "
            "admission"
        )
    if not revealed:
        problems.append(
            f"{run} scored before any reveal — the truth it matched against was never "
            "disclosed against the commitment"
        )
    else:
        started = run_started_events(ctx.core)
        sequence = int((started.get(run) or {}).get("sequence") or 0)
        anchor = _core_sequence(revealed[-1][0])
        if sequence and sequence < anchor:
            problems.append(
                f"{run} ran at core sequence {sequence}, before the reveal anchored at "
                f"{anchor}"
            )
    if problems:
        return [_fail(SCORING_CHECK, "; ".join(problems[:6]))], {}, False

    try:
        recomputed = _recompute(ctx, payload, submitted, revealed, manifest)
    except WorkflowError as exc:
        return [_fail(SCORING_CHECK, f"{run}: the scoring cannot be recomputed: {exc}")], {}, False

    if recomputed["mismatches"]:
        return (
            [
                _fail(
                    SCORING_CHECK,
                    f"{run}: the pinned table does not agree with the matching rule "
                    "re-applied to the same submissions and the revealed truth: "
                    + "; ".join(recomputed["mismatches"][:4]),
                )
            ],
            {},
            False,
        )
    printed_problems = _printed_problems(manifest, recomputed["arms"])
    if printed_problems:
        return (
            [_fail(SCORING_CHECK, f"{run}: " + "; ".join(printed_problems[:6]))],
            recomputed["arms"],
            False,
        )
    return (
        [
            _pass(
                SCORING_CHECK,
                f"{run} is the sole sealed scoring cell; {len(recomputed['rows'])} table "
                f"row(s) over {recomputed['arm_count']} arm(s) and "
                f"{recomputed['truth_count']} planted structure(s) recompute from "
                f"{str(recomputed['table_sha256'])[:12]}…",
            )
        ],
        recomputed["arms"],
        True,
    )


def _recompute(
    ctx: FamilyContext,
    payload: Mapping[str, Any],
    submitted: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    revealed: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-apply the matching rule to the pinned bytes and compare, row by row."""
    recorded = _artifact_sha(manifest, SCORES_TABLE)
    if recorded is None:
        raise WorkflowError(
            f"the cell pinned no `artifact: {SCORES_TABLE}` — the scoring cell's evidence "
            "IS the per-row match table, and a cell that did not pin it scored nothing"
        )
    table_path = ctx.study_dir / SCORES_TABLE
    if not table_path.is_file():
        raise WorkflowError(f"{SCORES_TABLE} is missing; the cell hashed it as {recorded[:12]}…")
    if sha256_file(table_path) != recorded:
        raise WorkflowError(
            f"{SCORES_TABLE} is {sha256_file(table_path)[:12]}… but the cell pinned "
            f"{recorded[:12]}…"
        )
    truth_ref = revealed[-1][1].get("truth") or {}
    truth = read_truth(ctx.study_dir / str(truth_ref.get("path")))
    files: dict[str, list[Mapping[str, Any]]] = {}
    for _event, obj in submitted:
        rel = obj.get("file_path")
        if not isinstance(rel, str):
            continue
        files[str(obj.get("arm"))] = submission_structures(
            read_submission(ctx.study_dir / rel)
        )
    rows = read_scores_table(table_path)
    context_ok = {
        (str(row["arm"]), int(row["rank"])): bool(row["context_ok"]) for row in rows
    }
    penalty = _number(payload.get("false_positive_penalty")) or 0.0
    scored = score_arms(files, truth, context_ok, penalty=penalty)
    mismatches = _row_mismatches(rows, scored["rows"])
    return {
        "rows": scored["rows"],
        "arms": scored["arms"],
        "mismatches": mismatches,
        "table_sha256": recorded,
        "arm_count": len(files),
        "truth_count": len(truth),
    }


def _row_mismatches(
    pinned: Sequence[Mapping[str, Any]], recomputed: Sequence[Mapping[str, Any]]
) -> list[str]:
    if len(pinned) != len(recomputed):
        return [
            f"the table has {len(pinned)} row(s); the submissions carry "
            f"{len(recomputed)} structure(s)"
        ]
    problems: list[str] = []
    order = sorted(range(len(pinned)), key=lambda i: (str(pinned[i]["arm"]), int(pinned[i]["rank"])))
    for position, index in enumerate(order):
        left = pinned[index]
        right = recomputed[position]
        where = f"{left['arm']} rank {left['rank']}"
        if str(left["arm"]) != str(right["arm"]) or int(left["rank"]) != int(right["rank"]):
            problems.append(f"{where}: the table has no such submitted structure")
            continue
        for key in ("relationship", "direction"):
            if _norm(left[key]) != _norm(right[key]):
                problems.append(
                    f"{where}: table {key} {left[key]!r}, submission {right[key]!r}"
                )
        if _variable_set(left) != _variable_set(right):
            problems.append(f"{where}: the table's variables are not the submitted ones")
        if int(left["matched"]) != int(right["matched"]):
            problems.append(
                f"{where}: table matched={left['matched']}, the matching rule gives "
                f"{right['matched']}"
            )
        if (left["truth_id"] or None) != (right["truth_id"] or None):
            problems.append(
                f"{where}: table truth_id={left['truth_id']!r}, the matching rule gives "
                f"{right['truth_id']!r}"
            )
    return problems


def _printed_problems(
    manifest: Mapping[str, Any], metrics: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """Every arm's numbers were printed, and they are the table's own numbers."""
    printed = manifest.get("metrics")
    printed = printed if isinstance(printed, Mapping) else {}
    problems: list[str] = []
    for arm, row in sorted(metrics.items()):
        for name, value in (
            (f"recall_{arm}", row.get("recall")),
            (f"precision_{arm}", row.get("precision")),
            (f"null_fp_{arm}", row.get("null_fp")),
        ):
            if value is None:
                continue  # undefined by construction (null-only or empty submission)
            told = printed.get(name)
            if not isinstance(told, int | float) or isinstance(told, bool):
                problems.append(
                    f"{name} was never printed — an omitted metric is not a passed one"
                )
                continue
            if abs(float(told) - float(value)) > PRINT_TOLERANCE:
                problems.append(
                    f"{name}: printed {float(told):.12g}, the pinned table gives "
                    f"{float(value):.12g}"
                )
        if f"cost_{arm}" not in printed:
            problems.append(
                f"cost_{arm} was never printed — matched budgets are part of the result, "
                "not a footnote"
            )
    return problems


def _consumed_receipt(ctx: FamilyContext, run: str) -> Any:
    for sha, consumer in ctx.match.consumed.items():
        if consumer == run:
            return next((receipt for receipt in ctx.receipts if receipt.sha == sha), None)
    return None


def _custody_checks(
    ctx: FamilyContext,
    payload: Mapping[str, Any],
    attested: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> list[Check]:
    """R-BEN-3: attested by a named holder, or reported ``unverified``.

    Never a FAIL.  A study that did not attest has not broken its record; it has
    declined to claim something the mechanism could not check anyway, and the
    outcome says so in one word.

    **An attestation counts for THIS benchmark only if it is about it.**  The
    verb is capability-agnostic on purpose — a study may attest the custody of a
    sample chain, a later time block, an interview transcript — so counting any
    attestation would let a statement about something else turn a benchmark's
    outcome from ``unverified`` to ``custodied``.  Whatever else was attested
    stays on the record and is reported by name, under its own subject.
    """
    declared = payload.get("custody") if isinstance(payload.get("custody"), Mapping) else {}
    reference = declared.get("attestation")
    checks: list[Check] = []
    if isinstance(reference, str) and not (ctx.study_dir / reference).is_file():
        checks.append(
            _fail(
                CUSTODY_CHECK,
                f"benchmark.yaml names the custody attestation {reference!r} and it is not "
                "in the study",
            )
        )
    mine, others = _split_attestations(payload, attested)
    if not mine:
        checks.append(
            _warn(
                CUSTODY_CHECK,
                "no `klein generation custody attest` names this benchmark: the outcome is "
                "reported `unverified`. Isolation is accounts, containers or machines with "
                "denied access — another directory of the same readable worktree is not "
                "custody, and a hash is not secrecy"
                + (
                    ". Attestations about other subjects: "
                    + ", ".join(f"{holder} on {subject}" for holder, subject in others)
                    if others
                    else ""
                ),
            )
        )
        return checks
    names = gc.holders(mine)
    checks.append(
        _pass(
            CUSTODY_CHECK,
            "custody attested by "
            + ", ".join(names)
            + " — TESTIMONY, never verified: the record carries the claim, and no check "
            "here establishes that anyone was actually denied access"
            + (
                f"; {len(others)} attestation(s) about other subjects are not counted here"
                if others
                else ""
            ),
        )
    )
    return checks


def benchmark_subjects(payload: Mapping[str, Any]) -> set[str]:
    """The names an attestation may use to mean "this benchmark's hidden evidence"."""
    subjects: set[str] = set()
    bundle = payload.get("public_bundle")
    if isinstance(bundle, Mapping) and isinstance(bundle.get("path"), str):
        subjects.add(str(bundle["path"]).strip())
    if isinstance(payload.get("truth_file"), str):
        subjects.add(str(payload["truth_file"]).strip())
    custody = payload.get("custody")
    if isinstance(custody, Mapping) and isinstance(custody.get("holder"), str):
        subjects.add(str(custody["holder"]).strip())
    return {name for name in subjects if name}


def _split_attestations(
    payload: Mapping[str, Any],
    attested: Sequence[tuple[Mapping[str, Any], dict[str, Any]]],
) -> tuple[
    list[tuple[Mapping[str, Any], dict[str, Any]]], list[tuple[str, str]]
]:
    """``(the ones about this benchmark, [(holder, subject)] for the rest)``.

    A null ``subject`` means "this study's own bundle" — the default the verb
    documents — so it counts.  Anything else has to name the public bundle, the
    truth file, or the holder ``benchmark.yaml`` itself declares.
    """
    subjects = benchmark_subjects(payload)
    mine: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    others: list[tuple[str, str]] = []
    for event, obj in attested:
        subject = obj.get("subject")
        if subject is None or (isinstance(subject, str) and subject.strip() in subjects):
            mine.append((event, obj))
        else:
            others.append((str(obj.get("holder")), str(subject)))
    return mine, others


def _ceiling_checks(ctx: FamilyContext) -> list[Check]:
    """R-INV-6: in-silico recovery is never a confirmed claim.

    Recovering a structure a generator planted says the pipeline can find that
    structure in that simulator.  Confirmation needs evidence independent of the
    selection, in a separately registered ``test`` study — so a ``confirmed``
    claim resting on the scoring table is refused here, by name.
    """
    from ..claims import claims_map, detect_lock_schema, load_lock, numbers_map

    try:
        lock = load_lock(ctx.study_dir)
    except WorkflowError:
        return [_pass(CEILING_CHECK, "no claims lock yet")]
    schema = detect_lock_schema(lock)
    artifacts = lock.get("artifacts")
    aliases = {
        str(alias)
        for alias, meta in (artifacts.items() if isinstance(artifacts, Mapping) else ())
        if isinstance(meta, Mapping) and str(meta.get("path")) == SCORES_TABLE
    }
    if not aliases:
        return [_pass(CEILING_CHECK, f"no claim pins {SCORES_TABLE}")]
    numbers = numbers_map(lock, schema)
    claims = claims_map(lock, schema)
    offenders: list[str] = []
    for cid, entry in claims.items():
        if not isinstance(entry, Mapping) or entry.get("strength") != "confirmed":
            continue
        cited = {
            str(item)
            for item in (entry.get("evidence") or [])
            if isinstance(item, str) and item.startswith("art:")
        }
        if cited & {f"art:{alias}" for alias in aliases}:
            offenders.append(str(cid))
            continue
        for alias in entry.get("numbers") or ():
            number = numbers.get(str(alias))
            art = number.get("art", number.get("artifact")) if isinstance(number, Mapping) else None
            if isinstance(art, str) and art in aliases:
                offenders.append(str(cid))
                break
    if offenders:
        return [
            _fail(
                CEILING_CHECK,
                "confirmed claim(s) "
                + ", ".join(sorted(set(offenders)))
                + f" rest on {SCORES_TABLE}: recovering a planted structure establishes "
                "in-silico performance on this generator, never a confirmed finding — "
                "confirmation needs a separately registered `test` study (R-INV-6)",
            )
        ]
    return [
        _pass(
            CEILING_CHECK,
            f"{len(aliases)} alias(es) pin {SCORES_TABLE} and no confirmed claim rests on "
            "them (the ceiling is exploratory / in-silico)",
        )
    ]


CAPABILITY = Capability(
    name=CAPABILITY_NAME,
    admission_rules=(_rule_sealed_scoring_needs_a_reveal,),
    verify_family=benchmark_family,
    receipt_inputs=_receipt_inputs,
)
