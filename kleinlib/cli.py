"""Command-line interface for Klein."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from . import __version__, api
from .cli_claims import register as register_claims
from .cli_demo import register as register_demo
from .cli_doctor import register as register_doctor
from .cli_host import register as register_host
from .cli_map import register as register_map
from .cli_predict import register as register_predict
from .cli_probe import register as register_probe
from .cli_replicate import register as register_replicate
from .cli_schema import register as register_schema
from .cli_skill import register as register_skill
from .cli_stop import register as register_stop
from .cli_sweep import register as register_sweep
from .contract import load_contract, mutable_surface
from .inquiry import kind_names, modality_names, profile_names
from .noise_floor import add_recipe_arguments
from .plugins import cli_registrars
from .recipes import RECIPES, apply_recipe, recipe_defaults
from .scaffold import apply_runner, scaffold_study
from .workflow import (
    WorkflowError,
    abandon_detached,
    acknowledge_headroom,
    collect_detached,
    finalize,
    preflight_checks,
    record_gate,
    recover,
    resolve_study,
    run_one,
    sealed_dry_run,
    status_summary,
    verify_study,
)


def _study_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", type=Path, default=Path("."), help="study directory (default: .)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein", description="Auditable single-machine ML research")
    parser.add_argument("--version", action="version", version=f"klein {__version__}")
    sub = parser.add_subparsers(dest="command_name", required=True)

    new = sub.add_parser("new", help="scaffold a study: a typed contract, templates and an empty ledger")
    new.set_defaults(handler=_cmd_new)
    new.add_argument("slug", help="study id, e.g. 03-calibration")
    new.add_argument("--root", type=Path, default=Path("studies"), help="parent directory for the study (default: studies/)")
    new.add_argument("--goal", help="one-sentence falsifiable study goal")
    new.add_argument("--domain", help="problem domain, e.g. insurance, optimization")
    new.add_argument("--target", help="target column (or 'synthetic' for known-truth labs)")
    new.add_argument("--task-type", choices=("classification", "regression", "simulation", "scalar"), default=None, help="evaluator shape for the study (default: classification, or the recipe's; scalar = known-truth labs, closed-form objectives and item/benchmark scores; simulation is its schema-2 spelling)")
    new.add_argument(
        "--recipe",
        choices=sorted(RECIPES),
        help="a domain recipe (Klein 2.3): pre-fills kind / modality / profile / metric / split, "
        "writes working example code on an offline default source and the 2.3 contract "
        "blocks (printed block, seeds, policy). Explicit flags still win. Judgment stays "
        "{{placeholders}} the gates refuse",
    )
    new.add_argument(
        "--runner",
        choices=("uv", "python"),
        default="uv",
        help="how the entrypoint is launched: `uv run --locked python` (default) or plain "
        "`python` for hosts without uv (conda envs, Claude Science task environments)",
    )
    new.add_argument("--method-depth", choices=("brief", "full"), default="full", help="METHOD-gate depth: full = 5-part method card")
    new.add_argument("--family", help="model family the study explores, e.g. linear, gbdt")
    new.add_argument(
        "--kind",
        choices=kind_names(),
        help="the question's shape; also names the scaffolded entrypoint "
        "(train.py / analyze.py / simulate.py / search.py)",
    )
    new.add_argument(
        "--modality",
        choices=modality_names(),
        help="the evidence source's shape; selects the Gate-1 card",
    )
    new.add_argument(
        "--profile",
        choices=profile_names(),
        help="the audience whose vocabulary is honest here",
    )
    new.add_argument(
        "--profile-doc",
        help="a repo-relative .md profile of your own, instead of --profile",
    )
    new.add_argument(
        "--audience",
        help="who reads this study, in a sentence",
    )
    new.add_argument(
        "--track",
        action="append",
        metavar="NAME[:MODE]",
        help="a metric track, repeatable; MODE is frontier or registered "
        "(default: primary, mode from --kind)",
    )
    new.add_argument("--metric", help="primary metric name, e.g. val_auc (see kleinlib.eval metric registry)")
    new.add_argument("--goal-direction", choices=("higher", "lower"), help="metric direction; must match the metric's canonical direction")
    new.add_argument("--minimum-delta", type=float, default=0.0, help="smallest improvement that counts as a keep (measure it at Phase 0)")
    new.add_argument("--data", help="data source tag, e.g. data_hub:name, kaggle:slug, csv:/path, synthetic:name")
    new.add_argument("--prepared-path", help="path prepare.py writes (default: data/prepared/prepared.csv)")
    new.add_argument(
        "--split-kind",
        choices=("stratified", "random", "group", "time", "none"),
        help="default: stratified for classification, random for regression, none for simulation",
    )
    new.add_argument("--group-column", help="grouping column for split-kind=group")
    new.add_argument("--time-column", help="timestamp column for split-kind=time")
    new.add_argument("--split-seed", type=int, default=42, help="seed written into data.split (default: 42)")
    new.add_argument("--max-run-seconds", type=int, default=None, help="hard per-run timeout enforced by run-one (default: 600, or the recipe's)")

    gate = sub.add_parser("gate", help="record or explicitly override a gate")
    gate.set_defaults(handler=_cmd_gate)
    gate_sub = gate.add_subparsers(dest="gate_action", required=True)
    gate_help = {
        "record": "record a gate acknowledgement (artifact must exist, placeholder-free)",
        "override": "proceed against a gate's conclusion, with a recorded reason",
    }
    for action in ("record", "override"):
        p = gate_sub.add_parser(action, help=gate_help[action])
        # `referee` is recordable but never overridable: a FAIL is never
        # softened into a note. The documented escape is
        # `klein finalize --no-referee --reason`, which labels the study.
        choices = ("consult", "data", "method", "referee", "phase") if action == "record" else (
            "consult",
            "data",
            "method",
        )
        p.add_argument("gate", choices=choices, help="which gate")
        _study_arg(p)
        p.add_argument("--acknowledged-by", required=True, help="who acknowledged (user name or agent id)")
        p.add_argument("--note", default="", help="free-text note stored in the gate record")
        p.add_argument("--phase", help="phase id (required for 'record phase')")
        if action == "override":
            p.add_argument("--reason", required=True, help="why the gate's conclusion is being overridden")

    headroom = sub.add_parser(
        "headroom",
        help="acknowledge a keep-infeasible frontier (headroom h < 1) before spending transactions",
    )
    headroom.set_defaults(handler=_cmd_headroom)
    headroom_sub = headroom.add_subparsers(dest="headroom_action", required=True)
    headroom_ack = headroom_sub.add_parser(
        "ack",
        help="register awareness that no keep is arithmetically possible on a track",
    )
    _study_arg(headroom_ack)
    headroom_ack.add_argument(
        "--track", default="primary", help="track whose headroom is acknowledged"
    )
    headroom_ack.add_argument(
        "--acknowledged-by", required=True, help="who acknowledged (user name or agent id)"
    )
    headroom_ack.add_argument(
        "--note",
        required=True,
        help="registered branch: 're-scope: ...' or 'run-anyway: <pre-committed door-closed sentence>'",
    )

    preflight = sub.add_parser("preflight", help="enforce gates, git, fingerprints, and ledger integrity")
    preflight.set_defaults(handler=_cmd_preflight)
    _study_arg(preflight)
    preflight.add_argument("--allow-dirty", action="store_true", help=argparse.SUPPRESS)

    run = sub.add_parser("run-one", help="commit and execute exactly one candidate transaction")
    run.set_defaults(handler=_cmd_run_one)
    _study_arg(run)
    run.add_argument("--track")
    run.add_argument("--description", default="")
    run.add_argument("--timeout-seconds", type=float)
    run.add_argument("--final-test", action="store_true")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="with --final-test: rehearse the sealed run on development data. Spends no experiment id, no manifest, no result row and no seal; leaves a log and one sealed_dryrun event, which the real sealed run requires.",
    )
    run.add_argument(
        "--tests",
        metavar="P1[,P2]",
        help="adjudicate these registered predictions against this run's printed block",
    )
    run.add_argument("--quiet", action="store_true")
    run.add_argument(
        "--allow-rerun",
        action="store_true",
        help="permit an intentional identical replication (empty train.py diff)",
    )
    run.add_argument(
        "--detach",
        action="store_true",
        help="Klein 2.3: do every pre-run check and the candidate commit, then file a DETACH "
        "commit with runs/E####/job.json for a host to execute (`klein job exec`); needs "
        "entrypoint.execution: [local, detached]. The study is frozen until --collect/--abandon",
    )
    run.add_argument(
        "--collect",
        metavar="E####",
        help="judge a detached run from its job_result/ (receipt checked against the job bundle)",
    )
    run.add_argument(
        "--abandon",
        metavar="E####",
        help="close an open detached run as a crash, on the record (needs --reason)",
    )
    run.add_argument("--reason", default="", help="why a detached run is abandoned")
    run.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="test/debug override; default is: uv run --locked python -u train.py",
    )

    job = sub.add_parser("job", help="execute a detached run's job bundle (Klein 2.3)")
    job.set_defaults(handler=_cmd_job)
    job_sub = job.add_subparsers(dest="job_action", required=True)
    job_exec = job_sub.add_parser(
        "exec",
        help="run runs/E####/job.json and write job_result/ + receipt.json for --collect",
    )
    job_exec.add_argument("job_json", type=Path, help="path to runs/E####/job.json")
    job_exec.add_argument(
        "--executor",
        choices=("local", "here"),
        default="local",
        help="local: a throwaway worktree of this repo at HEAD (default); here: this checkout "
        "(a dedicated clone on the host, at the detach commit)",
    )
    job_exec.add_argument("--quiet", action="store_true")

    recovery = sub.add_parser("recover", help="finish an interrupted evidence transaction")
    recovery.set_defaults(handler=_cmd_recover)
    _study_arg(recovery)
    status = sub.add_parser("status", help="show gates, frontiers, transactions, and sealed-test use")
    status.set_defaults(handler=_cmd_status)
    _study_arg(status)
    nxt = sub.add_parser(
        "next",
        help="the ONE next action this study needs, with the exact command (read-only)",
    )
    nxt.set_defaults(handler=_cmd_next)
    _study_arg(nxt)
    final = sub.add_parser("finalize", help="mark findings exploratory or confirmed")
    final.set_defaults(handler=_cmd_finalize)
    _study_arg(final)
    final.add_argument("--allow-exploratory", action="store_true")
    final.add_argument(
        "--allow-open-predictions",
        action="store_true",
        help="close the study with unadjudicated predictions; needs --reason, which is recorded",
    )
    final.add_argument(
        "--no-referee",
        action="store_true",
        help="close without the Gate-3 referee record; needs --reason and labels "
        "the study `unrefereed` on its receipt and in klein status",
    )
    final.add_argument(
        "--reason",
        default="",
        help="why predictions stay open (--allow-open-predictions) or why the "
        "study closes unrefereed (--no-referee)",
    )

    floor = sub.add_parser(
        "noise-floor",
        help="compute the measured noise floor from a k-seed sweep; prints the study.yaml block",
    )
    floor.set_defaults(handler=_cmd_noise_floor)
    _study_arg(floor)
    floor.add_argument("--track", default="primary", help="track the floor belongs to")
    floor.add_argument(
        "--sidecar",
        type=Path,
        help="measurement sweep sidecar (default: <study>/sweeps/noise_floor.sidecar.tsv)",
    )
    floor.add_argument("--values", help="comma-separated metric values (instead of --sidecar)")
    floor.add_argument("--seeds", help="comma-separated seeds (with --values)")
    floor.add_argument("--measured-after", help="anchor experiment id, e.g. E0001")
    add_recipe_arguments(floor)  # --recipe / --estimand / --method, declared once

    verify = sub.add_parser(
        "verify",
        help="re-check the whole study: contract, gates, ledger, predictions, claims, numbers; "
        "writes a receipt (--no-receipt only reads)",
    )
    verify.set_defaults(handler=_cmd_verify)
    _study_arg(verify)
    verify.add_argument(
        "--require-local",
        action="store_true",
        help="fail (instead of [WARN]) when an artifact policy keeps out of git — "
        "prepared data, a model blob marked committed:false — is absent; use after "
        "regenerating the study's local artifacts",
    )
    # --numbers, --claims and --evidence-use are on by default; the flags stay so
    # that every documented `klein verify --numbers --evidence-use` keeps working.
    verify.add_argument(
        "--numbers",
        action="store_true",
        default=None,
        help="scan findings.md for numerals with no home in a pinned artifact; "
        "report/index.html gets a second, always-advisory pass. On by default",
    )
    verify.add_argument(
        "--claims",
        action="store_true",
        default=None,
        help="add the claim-sentence numeral scan to the claims law's check 5 "
        "(`references/claims-protocol.md`). On by default",
    )
    verify.add_argument(
        "--evidence-use",
        dest="evidence_use",
        action="store_true",
        default=None,
        help="check that every discard, crash, measured cell and registered sweep is "
        "cited in program.md or findings.md (evidence_use_rate), that every refuted "
        "prediction has a dated `Decision:` line, and that confirmed claims cite two "
        "or more evidence kinds. On by default",
    )
    verify.add_argument(
        "--receipt",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="write and commit verify_receipt.json (default); --no-receipt only "
        "reads — use it to check a study you do not own",
    )
    verify.add_argument(
        "--strict",
        action="store_true",
        help="promote every [WARN] this verb owns into a failure — an uncited "
        "discard, an advisory claims warning, a single-source confirmed claim",
    )

    register_claims(sub)  # kleinlib/cli_<group>.py owns its own verbs
    register_demo(sub)
    register_doctor(sub)
    register_host(sub)
    register_map(sub)
    register_predict(sub)
    register_probe(sub)
    register_replicate(sub)
    register_skill(sub)
    register_schema(sub)
    register_stop(sub)
    register_sweep(sub)
    # Everything outside the kernel arrives through the plug-in seam — the opt-in
    # generation layer included (kleinlib/plugins.py).
    _register_plugin_verbs(sub)
    _mark_leaves(parser, ())
    return parser


def _register_plugin_verbs(sub: argparse._SubParsersAction) -> None:
    """Add each plug-in's verbs; one that fails, or reaches for a core verb, is undone.

    The promise is "a plug-in can add, never judge, and never breaks a core verb".
    What is enforced here: a registrar that raises is recorded (``klein doctor``
    reports it) and every verb it added is removed; a registrar may not replace
    or re-handle a verb that existed before it ran.
    """
    from . import plugins

    for index, register in enumerate(cli_registrars()):
        before = dict(sub.choices)
        handlers = {name: parser.get_default("handler") for name, parser in before.items()}
        listed = list(sub._choices_actions)
        try:
            register(sub)
            touched = sorted(
                name
                for name, parser in before.items()
                if sub.choices.get(name) is not parser
                or parser.get_default("handler") is not handlers[name]
            )
            if touched:
                raise ValueError(f"a plug-in may not replace an existing verb: {', '.join(touched)}")
        except Exception as exc:  # noqa: BLE001 - a broken plug-in must not break the kernel
            for name in list(sub.choices):
                if name not in before:
                    del sub.choices[name]
            for name, parser in before.items():
                sub.choices[name] = parser
                parser.set_defaults(handler=handlers[name])
            sub._choices_actions[:] = listed
            label = getattr(register, "__module__", None) or f"plug-in verbs #{index + 1}"
            plugins.record_error(f"{label} (verbs)", exc)


def _mark_leaves(parser: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
    """Give every leaf verb its name (``_verb``) and a ``--json`` flag.

    One envelope for every verb (``kleinlib.api``): a verb with structured output
    fills ``data``; any other verb's printed text comes back as ``data.text``.
    """
    children = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    if children:
        for action in children:
            for name, child in action.choices.items():
                _mark_leaves(child, (*path, name))
        return
    parser.set_defaults(_verb=" ".join(path))
    if "--json" not in parser._option_string_actions:
        parser.add_argument(
            "--json",
            action="store_true",
            help="print one machine-readable envelope instead of text (kleinlib.api)",
        )


#: Verbs whose arguments belong to a script that ships with the skill: everything
#: after the verb is handed over untouched, `--help` included.
_PASSTHROUGH: tuple[tuple[tuple[str, ...], str], ...] = (
    (("summarize",), "summarize_results.py"),
    (("report", "build"), "build_tutorial.py"),
)


def main(argv: list[str] | None = None) -> int:
    utf8_streams()
    # The probe variables mean something only inside a probe's child process. In
    # THIS process they would empty the sealed partition a gate fingerprints.
    from .probe import clear_probe_environment

    clear_probe_environment()
    raw = list(sys.argv[1:] if argv is None else argv)
    for verb, script in _PASSTHROUGH:
        if tuple(raw[: len(verb)]) == verb:
            from .cli_skill import _run_script

            rest = raw[len(verb) :]
            as_json = "--json" in rest
            captured = io.StringIO()
            try:
                if as_json:
                    with contextlib.redirect_stdout(captured):
                        code = _run_script(script, [arg for arg in rest if arg != "--json"])
                else:
                    code = _run_script(script, rest)
            except WorkflowError as exc:
                if as_json:
                    print(json.dumps(api.refusal(" ".join(verb), exc), indent=2, sort_keys=True))
                else:
                    print(f"klein: error: {exc}", file=sys.stderr)
                return 2
            if as_json:
                reply = api.envelope(" ".join(verb), {"text": captured.getvalue()}, ok=code == 0)
                print(json.dumps(reply, indent=2, sort_keys=True))
            return code
    args = build_parser().parse_args(argv)
    if not getattr(args, "json", False):
        return _dispatch(args)
    if getattr(args, "_verb", "") == "mcp":
        print("klein: error: `klein mcp` is a server on stdio; it has no --json mode", file=sys.stderr)
        return 2
    # --json: the verb runs exactly as in text mode, with its prints captured;
    # what it emitted (api.emit), or the JSON it printed, becomes `data`.
    verb = getattr(args, "_verb", "") or str(getattr(args, "command_name", ""))
    sink: dict = {}
    captured, errors = io.StringIO(), io.StringIO()
    previous, api._SINK = api._SINK, sink
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(errors):
            code = _dispatch(args)
    finally:
        api._SINK = previous
    data: dict = dict(sink)
    text = captured.getvalue()
    if not data and text.strip():
        try:
            printed = json.loads(text)
        except ValueError:
            data = {"text": text}
        else:
            data = printed if isinstance(printed, dict) else {"items": printed}
    problems = [
        {"level": "error", "code": "refused", "message": line.removeprefix("klein: error: ")}
        for line in errors.getvalue().splitlines()
        if line.startswith("klein: error: ")
    ]
    # Nothing a verb said is dropped: warnings and notices come back as problems.
    problems += [
        {"level": "warn", "code": "notice", "message": line.removeprefix("klein: warning: ")}
        for line in (*errors.getvalue().splitlines(), *(text.splitlines() if data else ()))
        if line.startswith(("klein: warning: ", "note: "))
    ]
    problems += [
        {
            "level": "error" if row["level"] == "fail" else "warn",
            "code": "check",
            "name": row["name"],
            "message": row["message"],
        }
        for row in data.get("checks", [])
        if isinstance(row, dict) and row.get("level") in {"fail", "warn"}
    ]
    print(json.dumps(api.envelope(verb, data, ok=code == 0, problems=problems), indent=2, sort_keys=True))
    return code


def _print_checks(checks) -> int:
    api.emit_checks(checks)
    failures = 0
    for check in checks:
        marker = "OK" if check.ok else "FAIL"
        print(f"[{marker}] {check.name}: {check.message}")
        failures += not check.ok
    print(f"summary: {len(checks)} checks, {failures} failed")
    return int(failures)


def _resolve_sidecar(study: Path, sidecar: Path | None) -> Path:
    """Locate ``klein noise-floor --sidecar`` the way its own default reads.

    The default is ``<study>/sweeps/noise_floor.sidecar.tsv`` and every
    documented invocation writes the study-relative spelling
    (``--sidecar sweeps/<name>.sidecar.tsv``, as ``consult-protocol.md``
    Phase 0 and ``klein sweep register --sidecar`` both do), so a relative
    path is resolved against the STUDY first.  A path that only exists
    relative to the process working directory still resolves, so a caller
    already inside the study directory keeps working.  A path that exists
    nowhere is a :class:`WorkflowError` naming both places it was looked
    for — never a bare ``FileNotFoundError`` traceback.
    """
    if sidecar is None:
        return study / "sweeps" / "noise_floor.sidecar.tsv"
    if sidecar.is_absolute():
        if not sidecar.is_file():
            raise WorkflowError(f"--sidecar does not exist: {sidecar.as_posix()}")
        return sidecar
    in_study = study / sidecar
    if in_study.is_file():
        return in_study
    if sidecar.is_file():
        return sidecar
    raise WorkflowError(
        f"--sidecar does not exist: looked for {in_study.as_posix()} (study-relative) "
        f"and {sidecar.as_posix()} (working-directory-relative)"
    )


def utf8_streams() -> None:
    """Never let a console encoding crash a verb.

    On Windows a PIPED stdout defaults to the ANSI code page (cp1252), where the
    arrows in Klein's messages raise ``UnicodeEncodeError`` — the CI e2e lane
    died in ``klein predict list`` that way. The stream keeps its encoding (so
    every reader on that platform still decodes what it always did); a
    character the encoding cannot carry becomes a backslash escape instead of
    an exception. A UTF-8 stream is left untouched.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        encoding = str(getattr(stream, "encoding", None) or "").lower().replace("-", "").replace("_", "")
        if reconfigure is None or encoding == "utf8":
            continue
        try:
            reconfigure(errors="backslashreplace")
        except (ValueError, OSError):  # pragma: no cover - a closed or exotic stream
            continue


def _cmd_new(args: argparse.Namespace) -> int:
    defaults: dict[str, object] = {}
    if args.recipe:
        defaults = recipe_defaults(args.recipe)
    def pick(name: str, value: object, fallback: object = None) -> object:
        return value if value is not None else defaults.get(name, fallback)
    explicit_profile_doc = args.profile_doc is not None
    study = scaffold_study(
        args.root,
        args.slug,
        goal=args.goal,
        domain=args.domain,
        target=pick("target", args.target),
        task_type=pick("task_type", args.task_type, "classification"),
        method_depth=args.method_depth,
        family=pick("family", args.family),
        tracks=args.track,
        metric_name=pick("metric_name", args.metric),
        metric_goal=pick("metric_goal", args.goal_direction),
        minimum_delta=args.minimum_delta,
        data_source=pick("data_source", args.data),
        data_path=pick("data_path", args.prepared_path),
        split_kind=pick("split_kind", args.split_kind),
        split_seed=args.split_seed,
        group_column=args.group_column,
        time_column=args.time_column,
        max_run_seconds=pick("max_run_seconds", args.max_run_seconds, 600),
        kind=pick("kind", args.kind),
        modality=pick("modality", args.modality),
        profile=None if explicit_profile_doc else pick("profile", args.profile),
        profile_doc=args.profile_doc,
        audience=args.audience,
    )
    if args.recipe:
        written = apply_recipe(study, args.recipe, split_seed=args.split_seed)
        print(f"recipe {args.recipe}: wrote {', '.join(written)}")
    if args.runner == "python":
        apply_runner(study, "python")
    api.emit({"study": str(study), "branch": f"experiments/{args.slug}"})
    print(f"scaffolded {study}")
    print(f"next: git switch -c experiments/{args.slug}   # then: klein next --study {study}")
    return 0


def _cmd_noise_floor(args: argparse.Namespace) -> int:
    from .noise_floor import (
        floor_from_sidecar,
        floor_report,
        resolve_estimand,
        summarize_noise,
    )

    method = args.recipe or args.method
    if args.values:
        seeds = [int(v) for v in args.seeds.split(",")] if args.seeds else None
        floor_stats = summarize_noise(
            [float(v) for v in args.values.split(",")], seeds=seeds
        )
        source = "--values"
    else:
        study = resolve_study(args.study)
        sidecar = _resolve_sidecar(study, args.sidecar)
        floor_stats = floor_from_sidecar(sidecar)
        try:
            source = sidecar.resolve().relative_to(study.resolve()).as_posix()
        except ValueError:
            source = sidecar.as_posix()
        # Unchanged default when no recipe is declared: a bare
        # `klein noise-floor --sidecar ...` prints exactly what it did.
        method = method or "seed-sweep"
    print(
        floor_report(
            args.track,
            floor_stats,
            source=source,
            measured_after=args.measured_after,
            method=method,
            estimand=resolve_estimand(args.recipe, args.estimand),
        ),
        end="",
    )
    return 0


def _cmd_job(args: argparse.Namespace) -> int:
    from .job import exec_job

    result = exec_job(args.job_json, executor=args.executor, echo=not args.quiet)
    receipt = json.loads((result / "receipt.json").read_text(encoding="utf-8"))
    print(
        f"job {receipt['experiment']}: exit {receipt['exit_code']}"
        f"{' (timeout)' if receipt['timed_out'] else ''} — receipt at {result / 'receipt.json'}"
    )
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    record_gate(
        study,
        args.gate,
        acknowledged_by=args.acknowledged_by,
        note=args.note,
        override_reason=getattr(args, "reason", None),
        phase=args.phase,
    )
    past = {"record": "recorded", "override": "overridden"}[args.gate_action]
    api.emit({"gate": args.gate, "status": past})
    print(f"{past} gate {args.gate}")
    return 0


def _cmd_headroom(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    entry = acknowledge_headroom(
        study,
        track=args.track,
        acknowledged_by=args.acknowledged_by,
        note=args.note,
    )
    print(
        f"acknowledged: track {args.track!r} headroom h={entry['h']:.3f} < 1 — "
        "the closed door is now on the record"
    )
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    return _print_checks(preflight_checks(study, require_clean=not args.allow_dirty))


def _cmd_run_one(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    if args.collect or args.abandon:
        if args.collect and args.abandon:
            raise WorkflowError("--collect and --abandon are different acts; pick one")
        if args.collect:
            manifest = collect_detached(study, args.collect, echo=not args.quiet)
        else:
            manifest = abandon_detached(study, args.abandon, reason=args.reason)
        print(
            f"{manifest['experiment']}: {manifest['disposition']} "
            f"metric={manifest['primary_metric']} (detached; attested, not observed)"
        )
        return 0 if manifest["disposition"] != "crash" or args.abandon else 1
    if args.dry_run:
        if not args.final_test:
            raise WorkflowError(
                "--dry-run rehearses a sealed run: pass it with --final-test "
                "(a development run needs no rehearsal — it spends nothing "
                "that cannot be spent again)"
            )
        if args.tests:
            raise WorkflowError(
                "--dry-run adjudicates nothing: a rehearsal on development "
                "data is not evidence for a registered prediction"
            )
        code = sealed_dry_run(
            study,
            track=args.track,
            timeout_seconds=args.timeout_seconds,
            command=args.command or None,
            echo=not args.quiet,
        )
        # The same shape `kleinlib.api.sealed_dry_run` returns: a host must not have
        # to read prose to learn whether the rehearsal passed.
        api.emit({"exit_code": code, "passed": code == 0})
        return code
    manifest = run_one(
        study,
        track=args.track,
        description=args.description,
        timeout_seconds=args.timeout_seconds,
        final_test=args.final_test,
        command=args.command or None,
        echo=not args.quiet,
        allow_rerun=args.allow_rerun,
        tests=args.tests,
        detach=args.detach,
    )
    if args.detach:
        job = f"{study}/runs/{manifest['experiment']}/job.json"
        print(f"{manifest['experiment']}: detached — candidate {manifest['candidate_commit'][:12]}")
        print(f"next: klein job exec {job}   (on the host; --executor local runs it here in a worktree)")
        print(f"then: klein run-one --study {study} --collect {manifest['experiment']}")
        return 0
    label = manifest["disposition"]
    if (
        manifest.get("evaluation_kind") == "final_test"
        and label == "discard"
    ):
        # Correct mechanics, clearer vocabulary: the sealed run is
        # confirmation evidence, recorded as discard so it never
        # enters the adaptive frontier.
        label = (
            "sealed (recorded as discard — confirmation evidence, "
            "excluded from the adaptive frontier)"
        )
    api.emit({"run": api.run_summary(manifest)})
    print(
        f"{manifest['experiment']}: {label} "
        f"metric={manifest['primary_metric']} commit={manifest['candidate_commit']}"
    )
    restored = (
        manifest["disposition"] != "keep"
        or manifest.get("evaluation_kind") == "final_test"
    )
    if restored and manifest.get("base_commit"):
        anchor = manifest.get("incumbent")
        holder = (
            f"(= {anchor}'s kept config)" if anchor else "(pre-candidate scaffold state)"
        )
        surface = ", ".join(mutable_surface(load_contract(study)))
        print(
            f"{surface} restored to pre-candidate base "
            f"{manifest['base_commit'][:12]} {holder}; "
            f"candidate stays resolvable at {manifest['candidate_commit'][:12]}"
        )
    return 0 if manifest["disposition"] != "crash" else 1


def _cmd_recover(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    recovered = recover(study)
    api.emit({"recovered": list(recovered)})
    print("recovered: " + (", ".join(recovered) if recovered else "none"))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    from .next_step import status_data

    api.emit(status_data(study))
    print(status_summary(study), end="")
    return 0


def _cmd_next(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    from .next_step import format_next, next_step

    result = next_step(study)
    api.emit(result)
    print(format_next(result), end="")
    return 0


def _cmd_finalize(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    label = finalize(
        study,
        allow_exploratory=args.allow_exploratory,
        allow_open_predictions=args.allow_open_predictions,
        open_predictions_reason=args.reason,
        no_referee=args.no_referee,
        referee_reason=args.reason,
    )
    api.emit({"label": label})
    print(f"finalized: {label}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    return _print_checks(
        verify_study(
            study,
            require_local=args.require_local,
            numbers=args.numbers,
            claims=args.claims,
            evidence=args.evidence_use,
            strict=args.strict,
            receipt=args.receipt,
        )
    )



def _dispatch(args: argparse.Namespace) -> int:
    try:
        if (handler := getattr(args, "handler", None)) is not None:
            return handler(args)  # a verb's own handler: a core _cmd_<verb> or a cli_<group> module's
    except (WorkflowError, FileExistsError, ValueError) as exc:
        print(f"klein: error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command {args.command_name}")


if __name__ == "__main__":
    raise SystemExit(main())
