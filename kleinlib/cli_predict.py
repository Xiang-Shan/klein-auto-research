"""``klein predict …`` — reading and hand-adjudicating the predictions ledger.

One module per verb group so packages landing in parallel do not collide in
``cli.py``: ``register(subparsers)`` builds the whole ``predict`` sub-command
and hangs its handler off the parsed namespace, and ``cli.py`` carries a single
registration line (the convention ``cli_claims.py`` / ``cli_doctor.py``
established).  The verbs:

    klein predict list       --study <dir> [--open] [--json]
    klein predict adjudicate --study <dir> P7 --verdict … --evidence …
                             --acknowledged-by … [--note …] [--force --reason …]

``list`` is read-only — the synthesist copies findings §② from it and the
referee runs it as one of the read-only verbs of ``referee-protocol.md``.
``adjudicate`` is for evidence the notary cannot read: a sidecar table, a
colleague's result, a figure a human had to look at.  It pins every path it is
given by sha256, self-commits the state write, and files a
``prediction_adjudicated`` event — the same receipt ``run-one --tests`` files,
with the source recorded as ``manual`` so a reader can tell them apart.
"""

from __future__ import annotations

import argparse
import json

from .contract import load_contract, registered_predictions, resolve_study, schema_version
from .decision import VALID_VERDICTS
from .errors import WorkflowError
from .predictions import format_ledger, ledger, pin_evidence, record_verdict
from .primitives import StudyLock
from .state import load_state, save_state
from .transaction import commit_state_writes

__all__ = ["register"]


def _study(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", default=".", help="study directory (default: .)")


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein predict`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    predict = subparsers.add_parser(
        "predict",
        help="read the predictions ledger, or adjudicate a prediction by hand",
        description=(
            "A registered prediction is a belief written down before the evidence, "
            "with the arithmetic that decides it. `run-one --tests P#` adjudicates "
            "the machine-readable ones; this verb reads the ledger and records the "
            "ones only a human can close. See "
            ".claude/skills/klein/references/registered-mode.md."
        ),
    )
    actions = predict.add_subparsers(dest="predict_action", required=True)

    listing = actions.add_parser(
        "list",
        help="every registered prediction with its ledger verdict, evidence and rule",
    )
    _study(listing)
    listing.add_argument(
        "--open",
        action="store_true",
        dest="only_open",
        help="show only the predictions with no verdict — what finalize refuses to close over",
    )
    listing.add_argument("--json", action="store_true", help="emit the ledger as JSON")
    listing.set_defaults(handler=_run_list)

    adjudicate = actions.add_parser(
        "adjudicate",
        help="record a verdict from evidence the notary cannot read (sidecar, external, human)",
    )
    _study(adjudicate)
    adjudicate.add_argument("prediction", metavar="P7", help="the registered prediction id")
    adjudicate.add_argument(
        "--verdict",
        required=True,
        choices=sorted(VALID_VERDICTS),
        help="supported, refuted or inconclusive (there is no 'open' verdict)",
    )
    adjudicate.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="evidence id (E####, sweep:<name>, rep:/verify:, ref:<key>, art:<alias>, P#) "
        "or a study-relative path, which is pinned by sha256; repeatable, comma-separated too",
    )
    adjudicate.add_argument(
        "--note", default="", help="why this evidence decides it, in a sentence"
    )
    adjudicate.add_argument(
        "--acknowledged-by", required=True, help="who adjudicated (user name or agent id)"
    )
    adjudicate.add_argument(
        "--force",
        action="store_true",
        help="required to hand-adjudicate a prediction that carries an arithmetic rule",
    )
    adjudicate.add_argument(
        "--reason", help="why the machine rule is being bypassed (required with --force)"
    )
    adjudicate.set_defaults(handler=_run_adjudicate)

    return predict


def _split(values: list[str]) -> list[str]:
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


def _run_list(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    contract = load_contract(study)
    rows = ledger(contract, load_state(study, contract))
    if args.only_open:
        rows = [row for row in rows if row["verdict"] == "open"]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(format_ledger(rows), end="")
    return 0


def _run_adjudicate(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    contract = load_contract(study)
    if schema_version(contract) < 3:
        raise WorkflowError(
            "the predictions ledger is a schema-3 mechanism; this study is schema 2"
        )
    name = args.prediction
    entry = registered_predictions(contract).get(name)
    if entry is None:
        raise WorkflowError(
            f"unknown prediction {name!r}; study.yaml registers "
            f"{sorted(registered_predictions(contract)) or 'none'}"
        )
    if entry.get("rule") is not None and not args.force:
        raise WorkflowError(
            f"prediction {name!r} carries an arithmetic rule — adjudicate it with "
            "`klein run-one --tests " + name + "` so the verdict comes from a printed "
            "block inside a transaction. To overrule the machine anyway, pass --force "
            '--reason "<why the rule cannot decide this>".'
        )
    if args.force and not (args.reason or "").strip():
        raise WorkflowError("--force requires --reason: overruling a rule goes on the record")
    evidence = _split(args.evidence)
    if not evidence:
        raise WorkflowError(
            "--evidence is required: a verdict with no evidence is an opinion "
            "(an id, or a study-relative path that gets pinned by sha256)"
        )
    if not args.acknowledged_by.strip():
        raise WorkflowError("--acknowledged-by is required")

    with StudyLock(study):
        state = load_state(study, contract)
        ids, pinned = pin_evidence(study, evidence)
        record_verdict(
            study,
            state,
            name,
            verdict=args.verdict,
            explanation=args.note or f"adjudicated by {args.acknowledged_by} from {', '.join(ids)}",
            source="manual",
            evidence=ids,
            artifacts=pinned,
            note=args.note or None,
            acknowledged_by=args.acknowledged_by,
            reason=args.reason if args.force else None,
        )
        save_state(study, state)
        commit_state_writes(study, f"klein: {name} adjudicated {args.verdict}")

    pins = "".join(
        f"\n  pinned {rel} sha256={meta['sha256'][:12]}…" for rel, meta in pinned.items()
    )
    print(f"{name}: {args.verdict} (evidence: {', '.join(ids)}){pins}")
    return 0
