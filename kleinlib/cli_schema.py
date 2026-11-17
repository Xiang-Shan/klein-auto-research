"""``klein schema`` — the JSON Schemas of the envelope and of every verb's ``data``.

The schemas ship in the package (``kleinlib/_schemas``); ``docs/embedding.md`` has the
compatibility rule a host can rely on.
"""

from __future__ import annotations

import argparse
import json

from .api import emit


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "schema",
        help="the JSON Schemas for the --json envelope and each verb's data (list, or print one)",
        description="klein schema lists the schemas and which verbs use each; klein schema envelope "
        "prints one as JSON (draft 2020-12). With --json the answer is the usual envelope.",
    )
    parser.add_argument("name", nargs="?", default="", help="a schema name, e.g. envelope or checks")
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from .resources import load_schema, schema_index, schema_names

    if args.name:
        schema = load_schema(args.name)
        emit({"name": args.name, "schema": schema})
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        return 0
    names, verbs = schema_names(), schema_index()
    emit({"schemas": names, "verbs": verbs})
    default = verbs.get("*")
    for name in names:
        users = [verb for verb, target in verbs.items() if target == name and verb != "*"]
        note = ", ".join(users) if users else ("every other verb" if name == default else "")
        print(f"{name:<16} {note}".rstrip())
    return 0
