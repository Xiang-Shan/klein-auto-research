from __future__ import annotations

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

    monkeypatch.setattr(cli, "verify_study", lambda _study: [Check("contract", True, "valid")])
    assert cli.main(["verify", "--study", str(study)]) == 0
    assert "0 failed" in capsys.readouterr().out


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


def _required(verb: str) -> list[str]:
    """The smallest argv each verb's required flags accept."""
    return {
        "number": ["alias", "--value", "1", "--art", "a"],
        "add": ["C1", "--class", "procedural-verdict", "--strength", "exploratory", "--claim", "x"],
        "erratum": ["E1", "--claims", "C1", "--note", "n"],
    }.get(verb, [])
