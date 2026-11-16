"""``klein generation …`` — the verbs of the opt-in generation layer.

One module per verb group so packages landing in parallel do not collide (see
:mod:`kleinlib.cli_doctor` for the convention and :mod:`kleinlib.cli_claims` for a
group with sub-subcommands): ``register(subparsers)`` builds the whole
``generation`` sub-command and hangs its handlers off the parsed namespace.  The
spine's verbs live in :mod:`.spine`, each capability's in its own module
(:mod:`.expert`, :mod:`.slate`, …), and what more than one of them needs in
:mod:`._shared`.  The plug-in seam (:mod:`kleinlib.generation.plugin`) calls
:func:`register`.  The verbs are the protocol's
(``.claude/skills/klein/references/generation-protocol.md`` "Verbs"):

    klein generation init    --study <dir> [--capability X]… [--allow-late]
    klein generation check   --study <dir> --action <checkpoint> --track <id>
    klein generation verify  --study <dir>
    klein generation label   --study <dir>
    klein generation status  --study <dir>
    klein generation recover --study <dir>

Capability packages add their own sub-groups the same way — one module with a
``register(actions)`` and one call in :func:`register`, and no edit to the spine's
verbs.  One line per group, in the
order of :data:`kleinlib.generation.capabilities.MODULES`:

    klein generation expert       lock | amend | bind | repair | review
    klein generation reference    record
    klein generation slate        lock | amend | score | show --phase <id>
    klein generation design       lock
    klein generation premortem    record | respond --phase <id>
    klein generation parity       lock | amend | bind | assess | show
    klein generation contribution record | show
    klein generation escalate     lock | record | close | pivot | show
    klein generation knowledge    promote | contest | resolve | query | decide | show
    klein generation surprise     register | record | show
    klein generation benchmark    commit | submit | reveal | retire | show
    klein generation custody      attest

``expert`` and ``reference`` are both the ``expertise`` capability
(``references/expert-protocol.md``, ``references/reference-protocol.md``);
``custody`` belongs to no capability at all and any generation-enabled study may
record one.  Every group takes ``--study <dir>``.

**The engine subpackage is imported inside the handlers, never at module scope.**
``register`` builds argparse and nothing else, so a defect in
``kleinlib.generation`` cannot break ``klein run-one`` — or any other verb — at
import time.  ``kleinlib/tests/generation/test_generation_spine.py`` asserts that
``import kleinlib.cli`` leaves ``kleinlib.generation`` unimported.

Exit codes are three-valued and mean different things on purpose:

``0``  the verb did what it says.
``1``  an ERROR, on stderr — the question could not be ASKED. Malformed
       arguments; an argument naming a file, run, claim, trigger or decision
       that does not exist; a study that is not schema 3, has no manifest, a
       broken chain, orphan objects, a dirty tree, or no git repository at all.
       Nothing is recorded.
``2``  a REFUSAL or a FAILING audit, on stdout — the question was asked and a
       rule of the study, the ledger or the authored artifact answered no.  The
       reasons are the ANSWER, so they print where an answer prints.  Only
       ``check`` RECORDS its refusal (the receipt is written, hashed and
       committed before the exit: a refusal is evidence); every other verb
       prints its refusal and leaves the ledger untouched.
"""

from __future__ import annotations

import argparse

from . import (
    benchmark,
    contribution,
    design,
    escalate,
    expert,
    knowledge,
    parity,
    premortem,
    slate,
    spine,
    surprise,
)

__all__ = ["register"]


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein generation`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    generation = subparsers.add_parser(
        "generation",
        help="opt-in generation layer: admission receipts before actions, verified after",
        description=(
            "The generation layer records what was committed to BEFORE the evidence "
            "existed. It records, hashes, and computes arithmetic on rows the driver "
            "wrote; it never proposes, ranks, selects, schedules, or retries. Opt in "
            "before the CONSULT gate. Schema 3 only. See "
            ".claude/skills/klein/references/generation-protocol.md."
        ),
    )
    actions = generation.add_subparsers(dest="generation_action", required=True)

    # --- the spine: init | check | verify | label | status | recover ----------
    spine.register(actions)

    # --- expertise acquisition + reference records ----------------------------
    expert.register(actions)

    # --- hypothesis slates + calibration --------------------------------------
    slate.register(actions)

    # --- evidence design ------------------------------------------------------
    design.register(actions)

    # --- the slate-time pre-mortem --------------------------------------------
    premortem.register(actions)

    # --- expert parity + contribution ledger ----------------------------------
    parity.register(actions)
    contribution.register(actions)

    # --- escalation ladder + successor studies --------------------------------
    escalate.register(actions)

    # --- cross-study knowledge ------------------------------------------------
    knowledge.register(actions)

    # --- surprise mining ------------------------------------------------------
    surprise.register(actions)

    # --- planted-truth benchmark + custody receipts ---------------------------
    benchmark.register(actions)
    spine.register_custody(actions)

    return generation
