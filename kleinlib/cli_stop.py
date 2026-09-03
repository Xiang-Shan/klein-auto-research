"""``klein stop ack`` — putting a pre-scripted stop decision on the record.

One module per verb group so packages landing in parallel do not collide in
``cli.py``.  The spelling is the one ``SKILL.md`` documents::

    klein stop ack --study studies/NN-slug --track <track> \\
        --acknowledged-by <actor> --note "..."

Deliberately shaped like ``klein headroom ack``: both are the same move — a
door the contract said would close has closed, and the study records which
branch it takes before spending anything more.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .contract import resolve_study
from .stop import acknowledge_stop

__all__ = ["register"]


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein stop`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    stop = subparsers.add_parser(
        "stop",
        help="acknowledge a fired stop rule (consecutive discards) before spending more",
        description=(
            "The schema-3 stop: block pre-registers how many consecutive discards end "
            "a losing phase. When the count is reached, run-one refuses before "
            "allocating an experiment id until this verb records which branch the "
            "study takes. The acknowledgement covers THAT COUNT only — the next "
            "discard asks again."
        ),
    )
    actions = stop.add_subparsers(dest="stop_action", required=True)

    ack = actions.add_parser(
        "ack", help="record the branch taken at a fired stop rule (valid for that count)"
    )
    ack.add_argument(
        "--study", type=Path, default=Path("."), help="study directory (default: .)"
    )
    ack.add_argument("--track", default="primary", help="track whose run of discards fired")
    ack.add_argument(
        "--acknowledged-by", required=True, help="who acknowledged (user name or agent id)"
    )
    ack.add_argument(
        "--note",
        required=True,
        help="the registered branch: 'continue: <what the next run buys>' or "
        "'stop: <the phase is closed>'",
    )
    ack.set_defaults(handler=_run_ack)
    return stop


def _run_ack(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    entry = acknowledge_stop(
        study,
        track=args.track,
        acknowledged_by=args.acknowledged_by,
        note=args.note,
    )
    print(
        f"acknowledged: {entry['count']} consecutive discards (scope {entry['scope']}, "
        f"registered limit {entry['max_consecutive_discards']}) — the branch is now "
        "on the record; the next discard asks again"
    )
    return 0
