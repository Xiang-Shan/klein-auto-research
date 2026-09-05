"""How a capability plugs into the spine — by REGISTRATION, never by editing it.

The spine (admission, chronology, verify, label) is finished.  Everything that
comes after it — expertise obligations, slates, pre-mortems, parity, surprise —
arrives as a :class:`Capability`: a name, some admission rules, and one verify
family.  Nothing in ``admission.py`` or ``verify.py`` learns a capability's name
or grows a branch for it; they iterate what
:func:`kleinlib.generation.capabilities.load` returns and intersect it with what
the study's ``generation/manifest.yaml`` DECLARED.  A capability the manifest
does not declare is not consulted, and a capability the manifest declares that
this version cannot load is a FAIL — never a silent skip.

**Integrity is not outcome, and a family reports both.**  ``integrity`` says
whether the RECORD is intact (``PASS`` / ``FAIL``); ``outcome`` says what the
research got (``demo``, ``incomplete``, ``covered``, …), and the spine never
reads it as a judgement.  A study whose every outcome is ``incomplete`` can
still carry ``generation-verified``; a study with one ``FAIL`` integrity cannot.

Import direction: this module names :mod:`kleinlib.generation.admission` and
:mod:`kleinlib.generation.verify` types under ``TYPE_CHECKING`` only (annotations
are strings under ``from __future__ import annotations``), and those two modules
import the loader lazily INSIDE the function that needs it — so the registry can
be typed against the spine without either side importing the other at load time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - types only; a runtime import would cycle
    from .admission import Context, Match, Receipt
    from .verify import Check

__all__ = ["Capability", "FamilyContext"]


@dataclass(frozen=True)
class FamilyContext:
    """Everything a verify family may read.  Read-only, and already gathered.

    The spine assembles this once per audit and hands the same object to every
    declared capability, so a family costs no extra chain read, no extra git
    call and no extra manifest parse.
    """

    study_dir: Path
    repo: Path | None
    contract: Mapping[str, Any]
    state: Mapping[str, Any]
    manifest: Mapping[str, Any]
    events: Sequence[Mapping[str, Any]]
    """The extension chain (``generation/events.jsonl``), in order."""
    core: Sequence[Mapping[str, Any]]
    """The core chain (``events.jsonl``), in order."""
    match: Match
    receipts: Sequence[Receipt]


@dataclass(frozen=True)
class Capability:
    """One registerable capability.  A later work package ships exactly this.

    ``name``
        The manifest vocabulary name (``kleinlib.generation.manifest``'s
        ``KNOWN_CAPABILITIES``), not necessarily the module's own name.
    ``admission_rules``
        Predicates over an :class:`~kleinlib.generation.admission.Context`, each
        returning the reasons it objects to the intended action.  They run after
        the spine's own rules, and only when the manifest declares this
        capability.
    ``verify_family``
        Returns ``(checks, outcome)``.  ``outcome`` MUST carry
        ``"integrity": "PASS" | "FAIL"`` and ``"outcome": <str>``; it is written
        verbatim to ``generation/verify_receipt.json`` under
        ``capabilities[<name>]``, and the label copies its ``outcome``.
    ``receipt_inputs``
        Returns the ``inputs`` this capability pins into an admission receipt —
        ``{"slate": "<object sha>"}`` and the like.  The receipt's ``inputs``
        key set is fixed by the spine's receipt envelope; a capability may only FILL
        one of those slots, never add a key, and returning ``{}`` leaves them
        all null.  Like the rules, it runs only when the manifest declares this
        capability.
    """

    name: str
    admission_rules: tuple[Callable[[Context], list[str]], ...] = ()
    verify_family: Callable[[FamilyContext], tuple[list[Check], dict[str, Any]]] | None = None
    receipt_inputs: Callable[[Context], Mapping[str, str | None]] | None = None
