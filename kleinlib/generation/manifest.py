"""``<study>/generation/manifest.yaml`` — the opt-in, and the capability registry.

A study is generation-enabled if and only if this file exists.  It is written
once by ``klein generation init``, before the CONSULT gate is recorded, and is
immutable afterwards: its sha256 is carried in the ``generation_opted_in``
event, and ``klein generation verify`` re-hashes it.

**Capability additions after opt-in are not available in this release.**  There
is no amendment verb and no manifest amendment event: a study declares its full
capability set at ``init``, and a study that wants another one is a successor
study.  ``scope.late_added`` therefore exists in the receipt and is always
``[]`` — the key is part of the receipt's fixed shape, not a feature.

The vocabulary is fixed and the availability is versioned:

``KNOWN_CAPABILITIES``
    The whole ten-name vocabulary the generation layer will ever use.  A name
    outside it is a typo and is refused as *unknown*.

``SUPPORTED_CAPABILITIES``
    What THIS version can actually check.  It was empty in the spine release and
    now carries all ten; opting in with no capability still buys exactly the
    admission discipline (receipt before action, verified afterwards).  The two
    refusals stay distinct — a name outside the vocabulary is *unknown*, a name
    inside it that the running build cannot check is *not available* — because
    "you misspelled it" and "this build does not ship that module" are different
    problems for the driver, and a study carried to an older Klein meets the
    second one.

``CAPABILITY_DEPENDENCIES``
    Enforced on every declaration: a pre-mortem reviews a slate, parity compares
    against a reproduced expert baseline, a contribution ledger covers slate
    rows, a planted-truth benchmark is scored by the parity machinery, and a
    surprise is mined from a registered evidence design.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ..errors import WorkflowError
from ..primitives import sha256_bytes, sha256_file
from .envelope import GENERATION_SCHEMA

__all__ = [
    "CAPABILITY_DEPENDENCIES",
    "CAPABILITY_PROTOCOLS",
    "GENERATION_SCHEMA_VERSION",
    "KNOWN_CAPABILITIES",
    "PROTOCOL_KEYS",
    "SKILL_ROOT",
    "SPINE_PROTOCOL",
    "SUPPORTED_CAPABILITIES",
    "build_manifest",
    "capability_problems",
    "load_manifest",
    "manifest_object",
    "manifest_path",
    "manifest_sha256",
    "protocol_hashes",
    "protocol_keys",
    "render_manifest",
    "study_id",
]

GENERATION_SCHEMA_VERSION = 1

KNOWN_CAPABILITIES: tuple[str, ...] = (
    "expertise",
    "slates",
    "premortem",
    "parity",
    "contribution",
    "surprise",
    "escalation",
    "knowledge",
    "benchmark",
    "design",
)

#: What this version can verify — all ten, as of the planted-truth package.  The
#: spine shipped none: the admission discipline plus the chronology witnesses, and
#: nothing that scores research.  Each capability package appends its own name here
#: and its module to :data:`kleinlib.generation.capabilities.MODULES`, and nothing
#: else.
SUPPORTED_CAPABILITIES: tuple[str, ...] = (
    # --- WP-01: expertise ---
    "expertise",
    # --- WP-02: hypothesis slates + calibration ---
    "slates",
    # --- WP-09: evidence design ---
    "design",
    # --- WP-03: slate-time pre-mortem ---
    "premortem",
    # --- WP-04: expert parity + contribution ledger ---
    "parity",
    "contribution",
    # --- WP-07: escalation ladder + successor studies ---
    "escalation",
    # --- WP-08: cross-study knowledge ---
    "knowledge",
    # --- WP-06: surprise mining (requires design) ---
    "surprise",
    # --- WP-05: planted-truth benchmark (the CUSTODIAN's declaration) ---
    "benchmark",
)

CAPABILITY_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "premortem": ("slates",),
    "parity": ("expertise",),
    "contribution": ("slates",),
    "benchmark": ("parity",),
    "surprise": ("design",),
}

#: Where the SPINE's protocol lives, relative to the skill root.  Hashing it
#: pins WHICH rules a receipt was taken under.
SPINE_PROTOCOL = "references/generation-protocol.md"

#: The protocol file each capability's rules are written in, if it has one of
#: its own.  ``slates`` and ``design`` are documented inside the spine protocol
#: and add nothing here; ``parity`` and ``contribution`` share one document, and
#: it is listed once.  A receipt that declares a capability pins the rules that
#: capability was actually taken under — pinning only the spine's file left the
#: nine documents that decide almost everything unhashed.
CAPABILITY_PROTOCOLS: dict[str, str] = {
    "expertise": "references/expert-protocol.md",
    "premortem": "references/premortem-protocol.md",
    "parity": "references/expert-parity-protocol.md",
    "contribution": "references/expert-parity-protocol.md",
    "surprise": "references/surprise-protocol.md",
    "escalation": "references/escalation-protocol.md",
    "knowledge": "references/knowledge-protocol.md",
    "benchmark": "references/planted-truth-protocol.md",
}

#: Kept as the spine's own single-element view, for readers that want "the
#: protocol" without a capability list.
PROTOCOL_KEYS: tuple[str, ...] = (SPINE_PROTOCOL,)


def protocol_keys(capabilities: Sequence[str] = ()) -> tuple[str, ...]:
    """The spine's protocol, then one file per declared capability that has one."""
    keys = [SPINE_PROTOCOL]
    for name in capabilities:
        key = CAPABILITY_PROTOCOLS.get(str(name))
        if key is not None and key not in keys:
            keys.append(key)
    return tuple(keys)

#: The skill directory, relative to the study's REPOSITORY root.  When Klein is
#: installed as a dependency of a foreign repo the directory is absent; the hash
#: is then recorded as null and drift simply cannot be observed (a WARN, never a
#: FAIL — see :mod:`kleinlib.generation.verify`).
SKILL_ROOT = ".claude/skills/klein"


def manifest_path(study_dir: Path) -> Path:
    return study_dir / "generation" / "manifest.yaml"


def study_id(study_dir: Path, contract: Mapping[str, Any] | None = None) -> str:
    """The study's own id: the contract's, else the state's, else the directory."""
    if contract is not None:
        for key in ("study_id", "id", "slug"):
            value = contract.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    state = study_dir / "study_state.json"
    if state.is_file():
        import json

        try:
            value = json.loads(state.read_text(encoding="utf-8")).get("study_id")
        except (OSError, ValueError):
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return study_dir.name


def capability_problems(capabilities: Sequence[str]) -> list[str]:
    """Unknown names, unsupported names, duplicates, unmet dependencies."""
    problems: list[str] = []
    seen: list[str] = []
    for name in capabilities:
        if name in seen:
            problems.append(f"capability {name!r} is listed twice")
            continue
        seen.append(name)
        if name not in KNOWN_CAPABILITIES:
            problems.append(
                f"unknown capability {name!r} — the vocabulary is "
                + ", ".join(KNOWN_CAPABILITIES)
            )
        elif name not in SUPPORTED_CAPABILITIES:
            problems.append(
                f"capability {name!r} is not available in this version of Klein "
                "(supported here: " + (", ".join(SUPPORTED_CAPABILITIES) or "none") + ")"
            )
    declared = set(seen)
    for name in seen:
        for needed in CAPABILITY_DEPENDENCIES.get(name, ()):
            if needed not in declared:
                problems.append(f"capability {name!r} requires {needed!r}")
    return problems


def protocol_hashes(
    repo_root: Path | None, capabilities: Sequence[str] = ()
) -> dict[str, str | None]:
    """sha256 of each protocol file, or null when the skill tree is absent."""
    hashes: dict[str, str | None] = {}
    for key in protocol_keys(capabilities):
        path = None if repo_root is None else repo_root / SKILL_ROOT / key
        hashes[key] = sha256_file(path) if path is not None and path.is_file() else None
    return hashes


def build_manifest(
    *,
    study: str,
    capabilities: Sequence[str],
    protocols: Mapping[str, str | None],
    predecessor: Mapping[str, Any] | None = None,
    custody: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "generation_schema": GENERATION_SCHEMA_VERSION,
        "study_id": study,
        "capabilities": list(capabilities),
        "protocol_hashes": dict(protocols),
        "predecessor": dict(predecessor) if predecessor else None,
        "custody": dict(custody) if custody else None,
    }


def render_manifest(manifest: Mapping[str, Any]) -> str:
    """Deterministic YAML — the bytes the opt-in event hashes."""
    return yaml.safe_dump(dict(manifest), sort_keys=True, default_flow_style=False, allow_unicode=True)


def manifest_object(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The object-store copy of the manifest (schema-tagged, hashable)."""
    return {"schema": GENERATION_SCHEMA, "kind": "manifest", **dict(manifest)}


def load_manifest(study_dir: Path) -> dict[str, Any]:
    path = manifest_path(study_dir)
    if not path.is_file():
        raise WorkflowError(
            "this study is not generation-enabled: generation/manifest.yaml is missing "
            "(`klein generation init` opts in, and must run before the CONSULT gate)"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"could not read generation/manifest.yaml: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError("generation/manifest.yaml must contain a top-level mapping")
    return value


def manifest_sha256(study_dir: Path) -> str:
    return sha256_bytes(manifest_path(study_dir).read_bytes())
