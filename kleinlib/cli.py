"""Command-line interface for the Klein v0.2 research workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .cli_claims import register as register_claims
from .cli_doctor import register as register_doctor
from .cli_predict import register as register_predict
from .cli_replicate import register as register_replicate
from .cli_stop import register as register_stop
from .cli_sweep import register as register_sweep
from .contract import KNOWN_KINDS
from .noise_floor import add_recipe_arguments
from .scaffold import scaffold_study
from .schema import KNOWN_MODALITIES, KNOWN_PROFILES
from .workflow import (
    WorkflowError,
    acknowledge_headroom,
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

    new = sub.add_parser("new", help="scaffold a schema-3 study (--schema-version 2 for the frozen v2 shape)")
    new.add_argument("slug", help="study id, e.g. 03-calibration")
    new.add_argument("--root", type=Path, default=Path("studies"), help="parent directory for the study (default: studies/)")
    new.add_argument("--goal", help="one-sentence falsifiable study goal")
    new.add_argument("--domain", help="problem domain, e.g. insurance, optimization")
    new.add_argument("--target", help="target column (or 'synthetic' for known-truth labs)")
    new.add_argument("--task-type", choices=("classification", "regression", "simulation", "scalar"), default="classification", help="evaluator shape for the study (scalar = known-truth labs and closed-form objectives; simulation is its schema-2 spelling)")
    new.add_argument("--method-depth", choices=("brief", "full"), default="full", help="METHOD-gate depth: full = 5-part method card")
    new.add_argument("--family", help="model family the study explores, e.g. linear, gbdt")
    new.add_argument(
        "--schema-version",
        type=int,
        choices=(2, 3),
        default=3,
        help="contract rule set (default: 3 — the typed inquiry; 2 is the frozen shape)",
    )
    new.add_argument(
        "--kind",
        choices=KNOWN_KINDS,
        help="the question's shape; also names the scaffolded entrypoint "
        "(train.py / analyze.py / simulate.py / search.py). Schema 3 only",
    )
    new.add_argument(
        "--modality",
        choices=KNOWN_MODALITIES,
        help="the evidence source's shape; selects the Gate-1 card. Schema 3 only",
    )
    new.add_argument(
        "--profile",
        choices=KNOWN_PROFILES,
        help="the audience whose vocabulary is honest here. Schema 3 only",
    )
    new.add_argument(
        "--profile-doc",
        help="a repo-relative .md profile of your own, instead of --profile. Schema 3 only",
    )
    new.add_argument(
        "--audience",
        help="who reads this study, in a sentence. Schema 3 only",
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
    new.add_argument("--max-run-seconds", type=int, default=600, help="hard per-run timeout enforced by run-one (default: 600)")

    gate = sub.add_parser("gate", help="record or explicitly override a gate")
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
    _study_arg(preflight)
    preflight.add_argument("--allow-dirty", action="store_true", help=argparse.SUPPRESS)

    run = sub.add_parser("run-one", help="commit and execute exactly one candidate transaction")
    _study_arg(run)
    run.add_argument("--track")
    run.add_argument("--description", default="")
    run.add_argument("--timeout-seconds", type=float)
    run.add_argument("--final-test", action="store_true")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="with --final-test: rehearse the sealed run on development data. "
        "Spends no id, commit, manifest, row or seal; exits 3 if the entrypoint "
        "never printed `sealed_dryrun: 1`",
    )
    run.add_argument(
        "--tests",
        metavar="P1[,P2]",
        help="adjudicate these registered predictions against this run's printed "
        "block (schema 3)",
    )
    run.add_argument("--quiet", action="store_true")
    run.add_argument(
        "--allow-rerun",
        action="store_true",
        help="permit an intentional identical replication (empty train.py diff)",
    )
    run.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="test/debug override; default is: uv run --locked python -u train.py",
    )

    recovery = sub.add_parser("recover", help="finish an interrupted evidence transaction")
    _study_arg(recovery)
    status = sub.add_parser("status", help="show gates, frontiers, transactions, and sealed-test use")
    _study_arg(status)
    final = sub.add_parser("finalize", help="mark findings exploratory or confirmed")
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
        help="validate a v1 or v2 study; v1 studies get deprecation errata, never a rewrite",
    )
    _study_arg(verify)
    verify.add_argument(
        "--require-local",
        action="store_true",
        help="fail (instead of [WARN]) when an artifact policy keeps out of git — "
        "prepared data, a model blob marked committed:false — is absent; use after "
        "regenerating the study's local artifacts",
    )

    register_claims(sub)  # kleinlib/cli_<group>.py owns its own verbs
    register_doctor(sub)
    register_predict(sub)
    register_replicate(sub)
    register_stop(sub)
    register_sweep(sub)
    return parser


def _print_checks(checks) -> int:
    failures = 0
    for check in checks:
        marker = "OK" if check.ok else "FAIL"
        print(f"[{marker}] {check.name}: {check.message}")
        failures += not check.ok
    print(f"summary: {len(checks)} checks, {failures} failed")
    return int(failures)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if (handler := getattr(args, "handler", None)) is not None:
            return handler(args)  # a cli_<group> module's verb, dispatched generically
        if args.command_name == "new":
            study = scaffold_study(
                args.root,
                args.slug,
                goal=args.goal,
                domain=args.domain,
                target=args.target,
                task_type=args.task_type,
                method_depth=args.method_depth,
                family=args.family,
                tracks=args.track,
                metric_name=args.metric,
                metric_goal=args.goal_direction,
                minimum_delta=args.minimum_delta,
                data_source=args.data,
                data_path=args.prepared_path,
                split_kind=args.split_kind,
                split_seed=args.split_seed,
                group_column=args.group_column,
                time_column=args.time_column,
                max_run_seconds=args.max_run_seconds,
                schema_version=args.schema_version,
                kind=args.kind,
                modality=args.modality,
                profile=args.profile,
                profile_doc=args.profile_doc,
                audience=args.audience,
            )
            print(f"scaffolded {study}")
            print(f"next: git switch -c experiments/{args.slug}")
            return 0
        if args.command_name == "noise-floor":
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
                sidecar = args.sidecar or (study / "sweeps" / "noise_floor.sidecar.tsv")
                floor_stats = floor_from_sidecar(sidecar)
                try:
                    source = str(sidecar.resolve().relative_to(study.resolve()))
                except ValueError:
                    source = str(sidecar)
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
        study = resolve_study(args.study)
        if args.command_name == "gate":
            record_gate(
                study,
                args.gate,
                acknowledged_by=args.acknowledged_by,
                note=args.note,
                override_reason=getattr(args, "reason", None),
                phase=args.phase,
            )
            past = {"record": "recorded", "override": "overridden"}[args.gate_action]
            print(f"{past} gate {args.gate}")
            return 0
        if args.command_name == "headroom":
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
        if args.command_name == "preflight":
            return _print_checks(preflight_checks(study, require_clean=not args.allow_dirty))
        if args.command_name == "run-one":
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
                return sealed_dry_run(
                    study,
                    track=args.track,
                    timeout_seconds=args.timeout_seconds,
                    command=args.command or None,
                    echo=not args.quiet,
                )
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
            )
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
                print(
                    f"train.py restored to pre-candidate base "
                    f"{manifest['base_commit'][:12]} {holder}; "
                    f"candidate stays resolvable at {manifest['candidate_commit'][:12]}"
                )
            return 0 if manifest["disposition"] != "crash" else 1
        if args.command_name == "recover":
            recovered = recover(study)
            print("recovered: " + (", ".join(recovered) if recovered else "none"))
            return 0
        if args.command_name == "status":
            print(status_summary(study), end="")
            return 0
        if args.command_name == "finalize":
            label = finalize(
                study,
                allow_exploratory=args.allow_exploratory,
                allow_open_predictions=args.allow_open_predictions,
                open_predictions_reason=args.reason,
                no_referee=args.no_referee,
                referee_reason=args.reason,
            )
            print(f"finalized: {label}")
            return 0
        if args.command_name == "verify":
            return _print_checks(verify_study(study, require_local=args.require_local))
    except (WorkflowError, FileExistsError, ValueError) as exc:
        print(f"klein: error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command {args.command_name}")


if __name__ == "__main__":
    raise SystemExit(main())
