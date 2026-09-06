"""The opt-in, process-verifiable **generation layer** (schema 3 only).

Klein's core makes the *verification* half of research auditable: typed
question, registered prediction, notarized evidence, locked claim, independent
referee.  This subpackage records the *generation* half — what was committed to
BEFORE the evidence existed — without touching one line of that core.

Three boundaries hold this package in place and are tested (see
``kleinlib/tests/test_generation_spine.py``):

1. **Core never imports generation.**  Import direction is strictly
   ``generation → core read helpers``.  ``kleinlib.cli`` carries two lines that
   register the verb group; the handlers in :mod:`kleinlib.cli_generation`
   import this package lazily, so a defect here cannot break ``klein run-one``
   or any legacy verb at import time.
2. **The layer records, hashes, and computes arithmetic on rows the driver
   wrote.  It never proposes, ranks, selects, schedules, or retries.**  No verb
   here calls ``run_one``; no module here calls a model API or the network.
3. **Write ownership.**  Every verb writes only under ``<study>/generation/``
   and commits only those paths.  Core state (``study_state.json``,
   ``events.jsonl``, ``runs/``, ``claims.lock``, ``verify_receipt.json``,
   ``study.yaml``) is read, never written.

Submodules are deliberately NOT imported here: ``import kleinlib.generation``
must stay cheap, and the CLI imports what a handler actually needs.

- :mod:`kleinlib.generation.envelope` — the extension event envelope and its hash
- :mod:`kleinlib.generation.ledger` — ``generation/events.jsonl`` + ``objects/``
- :mod:`kleinlib.generation.manifest` — the opt-in manifest and capability registry
- :mod:`kleinlib.generation.chronology` — the three local chronology witnesses
- :mod:`kleinlib.generation.registry` — the ``Capability`` a later package registers
- :mod:`kleinlib.generation.capabilities` — the capability modules THIS version ships
- :mod:`kleinlib.generation.admission` — admission receipts and the run↔receipt matcher
- :mod:`kleinlib.generation.verify` — the check families and ``generation/verify_receipt.json``
- :mod:`kleinlib.generation.label` — ``generation/label.json``
- :mod:`kleinlib.generation.recover` — voiding orphans, filing an uncommitted ledger

The protocol is ``.claude/skills/klein/references/generation-protocol.md``.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
