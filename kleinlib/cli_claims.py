"""``klein claims …`` — the verbs of the claims protocol.

One module per verb group so packages landing in parallel do not collide in
``cli.py``: ``register(subparsers)`` builds the whole ``claims`` sub-command and
hangs its handler off the parsed namespace, and ``cli.py`` carries a single
registration line.  The verbs are the protocol's
(``.claude/skills/klein/references/claims-protocol.md`` "Verbs"):

    klein claims init    --study <dir> [--from-legacy]
    klein claims pin     --study <dir> <alias> <path>
    klein claims number  --study <dir> <alias> --value … --art … [--claim …]
    klein claims add     --study <dir> <Cn> --class … --strength … --claim "…"
    klein claims erratum --study <dir> <En> --claims C3,C7 --note "…"
    klein claims verify  --study <dir> [--numbers] [--strict]

Every mutating verb rewrites the lock canonically and self-commits it: the lock
is a receipt, never hand-edited after ``init``.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from .claims import (
    CLAIM_CLASSES,
    STRENGTHS,
    add_claim,
    add_number,
    file_erratum,
    init_lock,
    pin_artifact,
    verify_lock,
)
from .contract import resolve_study

__all__ = ["parse_value", "register"]


def parse_value(raw: str) -> Any:
    """``--value`` as JSON when it parses, otherwise the literal string.

    So ``--value 454.16`` is a float, ``--value '[1, 2, 3]'`` a list, and
    ``--value 'NOT FIRED by rule'`` the sentence it looks like.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _study(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", default=".", help="study directory (default: .)")


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein claims`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    claims = subparsers.add_parser(
        "claims",
        help="author and verify claims.lock — the machine surface under findings.md",
        description=(
            "claims.lock is what a stranger can check: pinned artifacts, numbers with "
            "homes, claims with a class, a strength and evidence that resolves. "
            "See .claude/skills/klein/references/claims-protocol.md."
        ),
    )
    actions = claims.add_subparsers(dest="claims_action", required=True)

    init = actions.add_parser(
        "init",
        help="write the skeleton lock: claims from findings' **[Cn]** lines, numbers empty",
    )
    _study(init)
    init.add_argument(
        "--from-legacy",
        action="store_true",
        help="migrate this study's lock schema 1 ledger (studies 07-09 shape) into schema 2",
    )
    init.set_defaults(handler=_run_init)

    pin = actions.add_parser("pin", help="pin an artifact by alias: study-relative path + sha256")
    _study(pin)
    pin.add_argument("alias", help="the alias numbers refer to, e.g. results")
    pin.add_argument("path", help="study-relative path, e.g. results.tsv")
    pin.set_defaults(handler=_run_pin)

    number = actions.add_parser("number", help="give a headline value a home: artifact + claim")
    _study(number)
    number.add_argument("alias", help="the number's alias, e.g. k_free_intercept")
    number.add_argument("--value", required=True, help="the value (JSON when it parses, else text)")
    number.add_argument("--art", required=True, help="a pinned artifact alias")
    number.add_argument("--claim", help="the claim id it belongs to (Cn, or 'floor'/'contract')")
    number.add_argument(
        "--precision", type=int, help="decimals the numbers law matches at (default: 3)"
    )
    number.add_argument("--note", help="free-text note stored with the number")
    number.set_defaults(handler=_run_number)

    add = actions.add_parser("add", help="record a claim with its class, strength and evidence")
    _study(add)
    add.add_argument("claim_id", metavar="Cn", help="the claim id as findings.md writes it")
    add.add_argument(
        "--class",
        dest="claim_class",
        required=True,
        choices=sorted(CLAIM_CLASSES),
        help="one of the five classes; each carries a strength ceiling",
    )
    add.add_argument(
        "--strength",
        required=True,
        choices=[s for s in STRENGTHS if s != "refuted"],
        help="exploratory or confirmed ('refuted' is only ever set by an erratum)",
    )
    add.add_argument("--claim", required=True, help="the sentence as it appears in findings.md")
    add.add_argument(
        "--numbers", default="", help="comma-separated aliases the sentence quotes"
    )
    add.add_argument(
        "--evidence",
        default="",
        help="comma-separated evidence ids (E####, sweep:, rep:/verify:, ref:, art:, P#)",
    )
    add.add_argument("--scope", help="scope qualifier; a known-dgp-teaching claim is 'in-silico'")
    add.set_defaults(handler=_run_add)

    erratum = actions.add_parser(
        "erratum", help="re-scope claims without deleting them (tag, optionally downgrade)"
    )
    _study(erratum)
    erratum.add_argument("erratum_id", metavar="En", help="the erratum id, e.g. E1")
    erratum.add_argument("--claims", required=True, help="comma-separated claim ids, e.g. C3,C7")
    erratum.add_argument("--note", required=True, help="what is now known")
    erratum.add_argument(
        "--strength",
        choices=list(STRENGTHS),
        help="downgrade only: an erratum never strengthens a claim",
    )
    erratum.set_defaults(handler=_run_erratum)

    verify = actions.add_parser("verify", help="run the seven checks of the claims law")
    _study(verify)
    verify.add_argument(
        "--numbers",
        action="store_true",
        help="also scan every claim sentence: each numeral must be carried by one of its aliases",
    )
    verify.add_argument("--strict", action="store_true", help="promote every warning to a failure")
    verify.set_defaults(handler=_run_verify)

    return claims


def _split(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _run_init(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    lock = init_lock(study, from_legacy=args.from_legacy)
    print(
        f"claims.lock written: lock_schema {lock['lock_schema']}, "
        f"{len(lock['claims'])} claims, {len(lock['numbers'])} numbers, "
        f"{len(lock['artifacts'])} artifacts"
    )
    if any(entry.get("class") is None for entry in lock["claims"].values()):
        print("next: give every claim its class — a null class fails verification")
    return 0


def _run_pin(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    entry = pin_artifact(study, args.alias, args.path)
    print(f"pinned {args.alias}: {entry['path']} sha256={entry['sha256'][:12]}…")
    return 0


def _run_number(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    entry = add_number(
        study,
        args.alias,
        value=parse_value(args.value),
        art=args.art,
        claim=args.claim,
        precision=args.precision,
        note=args.note,
    )
    print(f"number {args.alias}: {entry['value']!r} in {entry['art']} (claim {entry.get('claim')})")
    return 0


def _run_add(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    entry = add_claim(
        study,
        args.claim_id,
        claim_class=args.claim_class,
        strength=args.strength,
        claim=args.claim,
        numbers=_split(args.numbers),
        evidence=_split(args.evidence),
        scope=args.scope,
    )
    print(
        f"{args.claim_id}: {entry['class']} / {entry['strength']} — "
        f"{len(entry['numbers'])} numbers, {len(entry['evidence'])} evidence ids"
    )
    return 0


def _run_erratum(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    entry = file_erratum(
        study,
        args.erratum_id,
        claims=_split(args.claims),
        note=args.note,
        strength=args.strength,
    )
    downgrade = f", downgraded to {args.strength}" if args.strength else ""
    print(f"erratum {args.erratum_id} filed on {', '.join(entry['claims'])}{downgrade}")
    return 0


def _run_verify(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    checks = verify_lock(study, numbers=args.numbers, strict=args.strict)
    failures = 0
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.message}")
        failures += not check.ok
    print(f"summary: {len(checks)} checks, {failures} failed")
    return int(failures)
