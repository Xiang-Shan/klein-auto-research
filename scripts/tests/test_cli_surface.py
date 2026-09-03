from __future__ import annotations

import json
from pathlib import Path

import pytest

from kleinlib import cli
from kleinlib.workflow import Check, WorkflowError


@pytest.fixture
def study(tmp_path: Path) -> Path:
    path = tmp_path / "study"
    path.mkdir()
    (path / "study.yaml").write_text("goal: fixture\n", encoding="utf-8")
    return path


def test_cli_new_builds_v2_study(tmp_path: Path, capsys) -> None:
    rc = cli.main(
        [
            "new",
            "03-cli-smoke",
            "--root",
            str(tmp_path),
            "--goal",
            "test the CLI",
            "--domain",
            "test",
            "--target",
            "y",
            "--family",
            "linear",
            "--metric",
            "val_auc",
            "--goal-direction",
            "higher",
            "--data",
            "csv:fixture.csv",
        ]
    )
    assert rc == 0
    assert (tmp_path / "03-cli-smoke" / "study_state.json").is_file()
    assert "experiments/03-cli-smoke" in capsys.readouterr().out


def test_cli_help_advertises_every_verb_and_the_schema_3_flags(capsys) -> None:
    """The docs are the spec for the surface: what they promise must parse."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    top = capsys.readouterr().out
    for verb in ("new", "gate", "preflight", "run-one", "recover", "status",
                 "finalize", "noise-floor", "verify", "headroom"):
        assert verb in top

    for argv, attr, expected in (
        (["new", "x", "--schema-version", "2"], "schema_version", 2),
        (["new", "x"], "schema_version", 3),
        (["new", "x", "--kind", "optimize"], "kind", "optimize"),
        (["new", "x", "--modality", "graph"], "modality", "graph"),
        (["new", "x", "--profile", "math"], "profile", "math"),
        (["new", "x", "--profile-doc", "profiles/p.md"], "profile_doc", "profiles/p.md"),
        (["new", "x", "--audience", "chemists"], "audience", "chemists"),
        (["new", "x", "--track", "a", "--track", "b:registered"], "track", ["a", "b:registered"]),
        (["new", "x", "--split-seed", "7"], "split_seed", 7),
        (["verify", "--require-local"], "require_local", True),
    ):
        assert getattr(parser.parse_args(argv), attr) == expected

    for argv in (["new", "x", "--kind", "guess"], ["new", "x", "--modality", "audio"],
                 ["new", "x", "--profile", "climate"], ["new", "x", "--schema-version", "4"]):
        with pytest.raises(SystemExit):
            parser.parse_args(argv)
        capsys.readouterr()


def test_cli_gate_and_preflight_paths(monkeypatch, study: Path, capsys) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(cli, "resolve_study", lambda _path: study)
    monkeypatch.setattr(cli, "record_gate", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert (
        cli.main(
            [
                "gate",
                "override",
                "data",
                "--study",
                str(study),
                "--acknowledged-by",
                "tester",
                "--reason",
                "fixture override",
            ]
        )
        == 0
    )
    assert calls[0][1]["override_reason"] == "fixture override"

    monkeypatch.setattr(
        cli,
        "preflight_checks",
        lambda *_args, **_kwargs: [Check("one", True, "ok"), Check("two", False, "bad")],
    )
    assert cli.main(["preflight", "--study", str(study)]) == 1
    assert "1 failed" in capsys.readouterr().out


def test_cli_run_status_recover_finalize_and_verify(monkeypatch, study: Path, capsys) -> None:
    monkeypatch.setattr(cli, "resolve_study", lambda _path: study)
    monkeypatch.setattr(
        cli,
        "run_one",
        lambda *_args, **_kwargs: {
            "experiment": "E0001",
            "disposition": "keep",
            "primary_metric": 0.7,
            "candidate_commit": "a" * 40,
        },
    )
    assert cli.main(["run-one", "--study", str(study), "--quiet"]) == 0
    assert "E0001: keep" in capsys.readouterr().out

    monkeypatch.setattr(cli, "recover", lambda _study: ["E0001"])
    assert cli.main(["recover", "--study", str(study)]) == 0
    assert "recovered: E0001" in capsys.readouterr().out

    monkeypatch.setattr(cli, "status_summary", lambda _study: "status fixture\n")
    assert cli.main(["status", "--study", str(study)]) == 0
    assert capsys.readouterr().out == "status fixture\n"

    monkeypatch.setattr(cli, "finalize", lambda *_args, **_kwargs: "exploratory")
    assert cli.main(["finalize", "--study", str(study), "--allow-exploratory"]) == 0
    assert "finalized: exploratory" in capsys.readouterr().out

    seen: dict[str, object] = {}

    def _verify(_study, *, require_local=False):
        seen["require_local"] = require_local
        return [Check("contract", True, "valid")]

    monkeypatch.setattr(cli, "verify_study", _verify)
    assert cli.main(["verify", "--study", str(study)]) == 0
    assert "0 failed" in capsys.readouterr().out
    assert seen["require_local"] is False
    assert cli.main(["verify", "--study", str(study), "--require-local"]) == 0
    capsys.readouterr()
    assert seen["require_local"] is True


def test_cli_verify_reports_v1_errata_without_rewriting(monkeypatch, tmp_path: Path, capsys) -> None:
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "study.yaml").write_text("goal: legacy\n", encoding="utf-8")
    ledger = legacy / "results.tsv"
    ledger.write_text(
        "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()
    monkeypatch.setattr(cli, "resolve_study", lambda _path: legacy)
    assert cli.main(["verify", "--study", str(legacy)]) == 0
    out = capsys.readouterr().out
    assert "deprecated v1 adapter" in out
    assert "create a new v2 study" in out
    assert ledger.read_bytes() == before


def test_cli_doctor_help_and_text_and_json_smoke(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["doctor", "--help"])
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    assert "--study" in help_text
    assert "--json" in help_text
    assert "--strict" in help_text

    assert cli.main(["doctor"]) == 0
    text_out = capsys.readouterr().out
    assert "[OK] python:" in text_out
    assert "summary:" in text_out

    assert cli.main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "ok" in payload and "checks" in payload


def test_cli_crash_exit_and_workflow_error(monkeypatch, study: Path, capsys) -> None:
    monkeypatch.setattr(cli, "resolve_study", lambda _path: study)
    monkeypatch.setattr(
        cli,
        "run_one",
        lambda *_args, **_kwargs: {
            "experiment": "E0002",
            "disposition": "crash",
            "primary_metric": None,
            "candidate_commit": "b" * 40,
        },
    )
    assert cli.main(["run-one", "--study", str(study)]) == 1

    monkeypatch.setattr(cli, "status_summary", lambda _study: (_ for _ in ()).throw(WorkflowError("nope")))
    assert cli.main(["status", "--study", str(study)]) == 2
    assert "klein: error: nope" in capsys.readouterr().err


CLAIMS_VERBS = ("init", "pin", "number", "add", "erratum", "verify")


def test_cli_claims_verbs_are_registered_with_help(capsys) -> None:
    """`klein claims <verb>` exists with the spelling the protocol documents."""
    parser = cli.build_parser()
    actions = [a for a in parser._subparsers._group_actions if a.dest == "command_name"]
    claims = actions[0].choices["claims"]
    sub = [a for a in claims._subparsers._group_actions if a.dest == "claims_action"][0]
    assert set(sub.choices) == set(CLAIMS_VERBS)
    for verb in CLAIMS_VERBS:
        help_text = sub.choices[verb].format_help()
        assert "--study" in help_text
        assert sub.choices[verb].description or sub._choices_actions

    flags = sub.choices["verify"].format_help()
    assert "--numbers" in flags and "--strict" in flags
    assert "--from-legacy" in sub.choices["init"].format_help()
    for flag in ("--value", "--art", "--claim", "--precision", "--note"):
        assert flag in sub.choices["number"].format_help(), flag
    for flag in ("--class", "--strength", "--claim", "--numbers", "--evidence"):
        assert flag in sub.choices["add"].format_help(), flag
    for flag in ("--claims", "--note", "--strength"):
        assert flag in sub.choices["erratum"].format_help(), flag

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["claims", "--help"])
    assert exit_info.value.code == 0
    assert "claims.lock" in capsys.readouterr().out


def test_cli_claims_dispatches_through_the_generic_handler(monkeypatch, tmp_path: Path) -> None:
    """A cli_<group> module hangs its handler on the namespace; main() calls it."""
    seen: list[str] = []

    def fake(args) -> int:
        seen.append(args.claims_action)
        return 0

    parser = cli.build_parser()
    for verb in CLAIMS_VERBS:
        argv = ["claims", verb, *(["a", "b"] if verb == "pin" else []), *_required(verb)]
        assert callable(parser.parse_args(argv).handler), verb

    args = parser.parse_args(["claims", "verify", "--study", str(tmp_path)])
    args.handler = fake
    monkeypatch.setattr(cli, "build_parser", lambda: parser)
    monkeypatch.setattr(parser, "parse_args", lambda _argv=None: args)
    assert cli.main(["claims", "verify"]) == 0
    assert seen == ["verify"]


def test_cli_sweep_register_is_registered_with_help(capsys) -> None:
    """`klein sweep register` exists with the spelling sweep-rules.md documents."""
    parser = cli.build_parser()
    actions = [a for a in parser._subparsers._group_actions if a.dest == "command_name"]
    sweep = actions[0].choices["sweep"]
    sub = [a for a in sweep._subparsers._group_actions if a.dest == "sweep_action"][0]
    assert set(sub.choices) == {"register"}

    help_text = sub.choices["register"].format_help()
    for flag in ("--study", "--sidecar", "--script"):
        assert flag in help_text, flag
    assert "name" in help_text

    argv = ["sweep", "register", "noise_floor", "--sidecar", "s.tsv", "--script", "s.py"]
    assert callable(parser.parse_args(argv).handler)

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["sweep", "--help"])
    assert exit_info.value.code == 0
    assert "sweep-rules.md" in capsys.readouterr().out


def test_cli_stop_ack_is_registered_with_help(capsys) -> None:
    """`klein stop ack` exists with the spelling SKILL.md documents."""
    parser = cli.build_parser()
    actions = [a for a in parser._subparsers._group_actions if a.dest == "command_name"]
    stop = actions[0].choices["stop"]
    sub = [a for a in stop._subparsers._group_actions if a.dest == "stop_action"][0]
    assert set(sub.choices) == {"ack"}

    help_text = sub.choices["ack"].format_help()
    for flag in ("--study", "--track", "--acknowledged-by", "--note"):
        assert flag in help_text, flag

    argv = ["stop", "ack", "--acknowledged-by", "tester", "--note", "continue: x"]
    assert callable(parser.parse_args(argv).handler)

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["stop", "--help"])
    assert exit_info.value.code == 0
    assert "consecutive discards" in capsys.readouterr().out


def _required(verb: str) -> list[str]:
    """The smallest argv each verb's required flags accept."""
    return {
        "number": ["alias", "--value", "1", "--art", "a"],
        "add": ["C1", "--class", "procedural-verdict", "--strength", "exploratory", "--claim", "x"],
        "erratum": ["E1", "--claims", "C1", "--note", "n"],
    }.get(verb, [])


def test_cli_replicate_verb_is_registered_with_help(capsys) -> None:
    """`klein replicate` exists with the spelling the protocol documents."""
    parser = cli.build_parser()
    actions = [a for a in parser._subparsers._group_actions if a.dest == "command_name"]
    replicate = actions[0].choices["replicate"]
    help_text = replicate.format_help()
    for flag in ("--study", "--tolerance", "--verify-only", "--list"):
        assert flag in help_text, flag
    args = parser.parse_args(["replicate", "E0003", "--tolerance", "0.01"])
    assert (args.experiment, args.tolerance) == ("E0003", 0.01)
    assert args.verify_only is False and args.list_records is False
    assert callable(args.handler)
    assert parser.parse_args(["replicate", "--list"]).list_records is True

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["replicate", "--help"])
    assert exit_info.value.code == 0
    assert "replication-protocol.md" in capsys.readouterr().out
