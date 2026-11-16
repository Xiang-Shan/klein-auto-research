"""``klein explain``, ``klein skill install``, ``klein summarize``, ``klein report build``.

The verbs that make an installed Klein self-sufficient: everything they read ships
in the package (``kleinlib/resources.py``), so none of them needs a checkout or a
particular working directory.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

from .api import emit
from .errors import WorkflowError


def register(subparsers: argparse._SubParsersAction) -> None:
    explain = subparsers.add_parser(
        "explain",
        help="print a protocol or a glossary term (run with no topic for the list)",
        description="klein explain gate · klein explain consult · klein explain claims-protocol · "
        "klein explain profile:math. Works from any directory: the text ships in the package.",
    )
    explain.add_argument("topic", nargs="?", default="", help="a term, a stage, or a protocol name")
    explain.set_defaults(handler=_explain)

    skill = subparsers.add_parser("skill", help="the protocols and worker agents that ship with Klein")
    skill_sub = skill.add_subparsers(dest="skill_command", required=True)
    install = skill_sub.add_parser(
        "install",
        help="copy the skill and the worker agents into a repository (default: the current one)",
        description="Writes .claude/skills/klein/ and .claude/agents/klein-*.md into --target, so "
        "an agent working there loads them and a study pins the protocols it ran under.",
    )
    install.add_argument("--target", type=Path, default=Path("."), help="the repository root (default: .)")
    install.add_argument("--no-agents", action="store_true", help="install the skill only")
    install.add_argument("--force", action="store_true", help="overwrite files that differ")
    install.set_defaults(handler=_install)
    where = skill_sub.add_parser("path", help="print where the skill resolves from on this machine")
    where.set_defaults(handler=_where)

    summarize = subparsers.add_parser(
        "summarize",
        help="summarize a results ledger (results_summary.md, progress.svg); arguments pass through",
        add_help=False,
    )
    summarize.add_argument("script_args", nargs=argparse.REMAINDER)
    summarize.set_defaults(handler=lambda args: _run_script("summarize_results.py", args.script_args))

    report = subparsers.add_parser("report", help="the teaching report (TUTORIAL stage)")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    build = report_sub.add_parser(
        "build",
        help="build report/index.html for a study; arguments pass through to the builder",
        add_help=False,
    )
    build.add_argument("script_args", nargs=argparse.REMAINDER)
    build.set_defaults(handler=lambda args: _run_script("build_tutorial.py", args.script_args))


def _explain(args: argparse.Namespace) -> int:
    from .resources import explain_topic

    result = explain_topic(args.topic)
    emit(result)
    print(result["text"], end="" if result["text"].endswith("\n") else "\n")
    return 0


def _install(args: argparse.Namespace) -> int:
    from .resources import install_skill

    result = install_skill(args.target, agents=not args.no_agents, force=args.force)
    emit(result)
    print(f"installed the klein skill: {result['files']} file(s) under {result['skill']}")
    if result["agents"]:
        print(f"installed {len(result['agents'])} worker agent(s): {', '.join(result['agents'])}")
    print("commit them with your study: they are the protocols it is run under")
    return 0


def _where(_args: argparse.Namespace) -> int:
    from .resources import agents_root, skill_root

    root = skill_root()
    emit({"skill": str(root) if root else None, "agents": str(agents_root() or "") or None})
    if root is None:
        raise WorkflowError("the skill is not on this machine (a damaged installation?)")
    print(root)
    return 0


def _run_script(name: str, argv: list[str]) -> int:
    """Run one of the skill's scripts in this interpreter, as if called directly."""
    from .resources import script_path

    path = script_path(name)
    if path is None:
        raise WorkflowError(f"{name} is not on this machine (a damaged installation?)")
    saved = sys.argv
    sys.argv = [str(path), *argv]
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int) or code is None:
            return code or 0
        print(code, file=sys.stderr)  # `sys.exit("message")`: the message is the error
        return 1
    finally:
        sys.argv = saved
    return 0
