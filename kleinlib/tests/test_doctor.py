"""Tests for kleinlib.doctor (`klein doctor`'s report) and kleinlib.cli_doctor.

`klein doctor` NEVER fetches — every test that could reach the network proves
it does not, either by monkeypatching `urllib.request.urlopen` to explode or
by pointing `--study` at a tag whose readiness `describe()` must answer
purely from the filesystem.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import pytest

from kleinlib import cli_doctor, doctor

# --------------------------------------------------------------------------
# run_doctor — shape and JSON friendliness
# --------------------------------------------------------------------------

_ENV_CHECK_NAMES = {
    "python",
    "uv",
    "git",
    "extra: encoders",
    "extra: parquet",
    "extra: gbdt",
    "extra: deep",
    "extra: foundation",
    "tutorial renderer",
    "device",
    "DATA_HUB",
}


def test_run_doctor_reports_every_environment_check() -> None:
    report = doctor.run_doctor()
    names = {check["name"] for check in report["checks"]}
    assert _ENV_CHECK_NAMES <= names
    assert isinstance(report["ok"], bool)
    for check in report["checks"]:
        assert set(check) == {"name", "ok", "message"}
        assert isinstance(check["ok"], bool)
        assert isinstance(check["message"], str) and check["message"]


def test_run_doctor_ok_is_conjunction_of_checks() -> None:
    report = doctor.run_doctor()
    assert report["ok"] == all(check["ok"] for check in report["checks"])


def test_run_doctor_report_is_json_serializable() -> None:
    report = doctor.run_doctor()
    blob = json.dumps(report)
    assert json.loads(blob) == report


def test_run_doctor_without_study_adds_no_data_source_check() -> None:
    report = doctor.run_doctor(study_dir=None)
    assert "data source" not in {c["name"] for c in report["checks"]}
    assert "study contract" not in {c["name"] for c in report["checks"]}


def test_format_report_marks_ok_and_warn(monkeypatch) -> None:
    fake = {
        "ok": False,
        "checks": [
            {"name": "a", "ok": True, "message": "fine"},
            {"name": "b", "ok": False, "message": "not fine"},
        ],
    }
    text = doctor.format_report(fake)
    assert "[OK] a: fine" in text
    assert "[WARN] b: not fine" in text
    assert "2 checks, 1 not-ok" in text
    assert text.endswith("\n")


# --------------------------------------------------------------------------
# --study: study.yaml reading, tolerant of everything
# --------------------------------------------------------------------------


def test_probe_study_source_missing_study_yaml(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    checks = doctor._probe_study_source(study)
    assert len(checks) == 1
    assert checks[0]["name"] == "study contract"
    assert checks[0]["ok"] is False


def test_probe_study_source_malformed_yaml(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    (study / "study.yaml").write_text("data: [this is not: valid: yaml", encoding="utf-8")
    checks = doctor._probe_study_source(study)
    assert checks[0]["ok"] is False
    assert "does not parse" in checks[0]["message"]


def test_probe_study_source_no_data_block_is_informational(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    (study / "study.yaml").write_text("goal: fixture\n", encoding="utf-8")
    checks = doctor._probe_study_source(study)
    assert checks[0]["ok"] is True
    assert "no data.source" in checks[0]["message"]


def test_probe_study_source_resolvable_csv_tag(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    (study / "x.csv").write_text("a\n1\n", encoding="utf-8")
    (study / "study.yaml").write_text("data:\n  source: csv:x.csv\n", encoding="utf-8")
    checks = doctor._probe_study_source(study)
    assert checks[0]["name"] == "data source"
    assert checks[0]["ok"] is True


def test_probe_study_source_unpinned_openml_is_not_ok_without_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError))
    study = tmp_path / "study"
    study.mkdir()
    (study / "study.yaml").write_text("data:\n  source: openml:41214\n", encoding="utf-8")
    checks = doctor._probe_study_source(study)
    assert checks[0]["ok"] is False
    assert "openml" in checks[0]["message"]


def test_probe_study_source_legacy_tag_is_reported_not_crashed(tmp_path: Path) -> None:
    """Schema-2 studies use `data_hub:`/`kaggle:` free-text labels — doctor
    must report them as an unresolvable tag, never raise."""
    study = tmp_path / "study"
    study.mkdir()
    (study / "study.yaml").write_text("data:\n  source: data_hub:freMTPL2\n", encoding="utf-8")
    checks = doctor._probe_study_source(study)
    assert checks[0]["ok"] is False
    assert "unknown scheme" in checks[0]["message"]


def test_run_doctor_with_study_never_touches_network(tmp_path: Path, monkeypatch) -> None:
    def _boom(*_a, **_k):
        raise AssertionError("klein doctor must never fetch")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    study = tmp_path / "study"
    study.mkdir()
    (study / "study.yaml").write_text("data:\n  source: url:https://example.test/a.csv\n", encoding="utf-8")
    report = doctor.run_doctor(study_dir=study)
    assert any(c["name"] == "data source" for c in report["checks"])


# --------------------------------------------------------------------------
# Individual probes
# --------------------------------------------------------------------------


def test_probe_python_reports_version_and_executable() -> None:
    check = doctor._probe_python()
    assert check["ok"] is True
    assert "at" in check["message"]


def test_probe_extras_flags_a_missing_module(monkeypatch) -> None:
    monkeypatch.setitem(doctor._EXTRA_PROBES, "encoders", ("no_such_module_xyz",))
    checks = doctor._probe_extras()
    encoders_check = next(c for c in checks if c["name"] == "extra: encoders")
    assert encoders_check["ok"] is False
    assert "no_such_module_xyz" in encoders_check["message"]
    assert "uv sync --locked --extra encoders" in encoders_check["message"]


def test_probe_data_hub_unset_is_ok(monkeypatch) -> None:
    monkeypatch.delenv("DATA_HUB", raising=False)
    check = doctor._probe_data_hub()
    assert check["ok"] is True
    assert "not set" in check["message"]


def test_probe_data_hub_set_but_not_a_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_HUB", str(tmp_path / "does-not-exist"))
    check = doctor._probe_data_hub()
    assert check["ok"] is False


def test_probe_data_hub_set_without_loader_module_is_still_ok(monkeypatch, tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DATA_HUB", str(hub))
    check = doctor._probe_data_hub()
    assert check["ok"] is True
    assert "not importable" in check["message"] or "loaders.python.hub" in check["message"]


def test_probe_device_respects_klein_device_override(monkeypatch) -> None:
    # Without torch the probe reports "torch not installed" and never reads the
    # override; the core CI job installs only the encoders extra.
    pytest.importorskip("torch")
    monkeypatch.setenv("KLEIN_DEVICE", "cpu")
    check = doctor._probe_device()
    assert check["ok"] is True
    assert "cpu" in check["message"]
    assert "KLEIN_DEVICE" in check["message"]


def test_probe_device_without_torch_is_ok_and_explains(monkeypatch) -> None:
    import importlib.util

    real_find_spec = importlib.util.find_spec

    def _no_torch(name, *args, **kwargs):
        if name == "torch":
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(doctor.importlib.util, "find_spec", _no_torch)
    check = doctor._probe_device()
    assert check["ok"] is True
    assert "torch not installed" in check["message"]


# --------------------------------------------------------------------------
# cli_doctor
# --------------------------------------------------------------------------


def _args(**overrides) -> argparse.Namespace:
    base = {"study": None, "json": False, "strict": False}
    base.update(overrides)
    return argparse.Namespace(**base)


def test_cli_doctor_register_adds_the_subparser() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command_name")
    cli_doctor.register(subparsers)
    parsed = parser.parse_args(["doctor", "--json", "--strict"])
    assert parsed.command_name == "doctor"
    assert parsed.json is True
    assert parsed.strict is True
    assert parsed.study is None


def test_cli_doctor_run_prints_text_by_default_and_exits_0(capsys) -> None:
    rc = cli_doctor.run(_args())
    assert rc == 0
    out = capsys.readouterr().out
    assert "[OK] python:" in out
    assert "summary:" in out


def test_cli_doctor_run_json_flag_emits_valid_json(capsys) -> None:
    rc = cli_doctor.run(_args(json=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "checks" in payload and "ok" in payload


def test_cli_doctor_run_strict_exits_1_only_when_not_ok(monkeypatch) -> None:
    # cli_doctor imports `run_doctor` by name (`from .doctor import run_doctor`),
    # so the name to patch is cli_doctor's own binding, not doctor's.
    monkeypatch.setattr(cli_doctor, "run_doctor", lambda study_dir=None: {"ok": True, "checks": []})
    assert cli_doctor.run(_args(strict=True)) == 0

    monkeypatch.setattr(cli_doctor, "run_doctor", lambda study_dir=None: {"ok": False, "checks": []})
    assert cli_doctor.run(_args(strict=True)) == 1
    assert cli_doctor.run(_args(strict=False)) == 0
