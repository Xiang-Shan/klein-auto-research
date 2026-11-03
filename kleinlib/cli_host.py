"""CLI verbs for host bridges (Klein 2.3): ``klein refs verify``, ``klein mcp``, ``klein notebook``.

Same per-group convention as ``cli_doctor.py``: ``register(subparsers)`` adds the
parsers and hangs a handler on each; ``kleinlib.cli.main`` dispatches through it.
None of these verbs writes a study receipt or commits: ``refs verify --record``
edits ``references.yaml`` in the working tree for the person to review and commit,
``mcp`` only reads, and ``notebook`` writes a derivative file outside the ledger.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    refs = subparsers.add_parser(
        "refs", help="resolve references.yaml DOIs / arXiv ids against Crossref, OpenAlex and arXiv (network)"
    )
    refs_sub = refs.add_subparsers(dest="refs_action", required=True)
    verify = refs_sub.add_parser(
        "verify",
        help="look up every DOI / arXiv id and compare titles; refused under KLEIN_OFFLINE=1",
    )
    verify.add_argument("--study", type=Path, default=Path("."), help="study directory")
    verify.add_argument("--key", action="append", default=[], help="only this citation key (repeatable)")
    verify.add_argument(
        "--record",
        action="store_true",
        help="write resolved_by / resolved_title / resolved_at for each match into references.yaml "
        "(comments kept; never downgrades or overwrites a human verification)",
    )
    verify.add_argument("--json", action="store_true", help="emit the results as JSON")
    verify.set_defaults(handler=_refs_verify)

    mcp = subparsers.add_parser(
        "mcp",
        help="serve read-only Klein tools over MCP stdio (next, status, doctor, preflight, verify, "
        "predictions, claims_verify, explain)",
    )
    mcp.add_argument("--root", type=Path, default=Path("."), help="repository root holding studies/")
    mcp.set_defaults(handler=_mcp)

    notebook = subparsers.add_parser(
        "notebook",
        help="write a run as a reading-copy .ipynb: the executed source at its candidate commit + its printed block",
    )
    notebook.add_argument("experiment", help="experiment id, e.g. E0007")
    notebook.add_argument("--study", type=Path, default=Path("."), help="study directory")
    notebook.add_argument("--out", type=Path, default=None, help="output path (default ./<study>-<E####>.ipynb)")
    notebook.set_defaults(handler=_notebook)


def _refs_verify(args: argparse.Namespace) -> int:
    from .refs_net import verify_references

    results, recorded = verify_references(args.study, keys=args.key, record=args.record)
    if args.json:
        print(json.dumps([r.__dict__ for r in results] + [{"recorded": recorded}], indent=2))
    else:
        for result in results:
            print(f"[{'ok' if result.ok else 'FAIL'}] {result.key}: {result.message}")
        failed = sum(not r.ok for r in results)
        print(f"summary: {len(results)} references, {failed} failed" + (f", recorded {len(recorded)}" if args.record else ""))
        if recorded:
            print("references.yaml edited — review the diff and commit it with the method card")
    return 1 if any(not r.ok for r in results) else 0


def _mcp(args: argparse.Namespace) -> int:
    from .mcp_server import serve

    return serve(args.root)


def _notebook(args: argparse.Namespace) -> int:
    from .notebook import write_notebook

    path = write_notebook(args.study, args.experiment, args.out)
    print(f"wrote {path} (a reading copy — the manifest and candidate commit are the evidence)")
    return 0
