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


def test_cli_migrate_stdout_and_report(monkeypatch, study: Path, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli, "resolve_study", lambda _path: study)
    monkeypatch.setattr(cli, "migration_report", lambda _study: "# compatibility\n")
    assert cli.main(["migrate", "--dry-run", "--study", str(study)]) == 0
    assert capsys.readouterr().out == "# compatibility\n"

    report = tmp_path / "migration.md"
    assert (
        cli.main(
            [
                "migrate",
                "--dry-run",
                "--study",
                str(study),
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert report.read_text(encoding="utf-8") == "# compatibility\n"
    assert str(report) in capsys.readouterr().out


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
