"""Unit tests for scripts/verify_shipped_studies.py.

Discovery, schema-version detection, and summary-line parsing only — no real
``klein verify`` subprocess ever runs here. ``main()``'s subprocess boundary
is replaced with a fake responder keyed on the ``--study`` argument, so the
end-to-end tests exercise the real discovery/table/exit-code logic in
milliseconds regardless of what the shipped studies' actual verify state is
on the day the suite runs (that live check is the CI step this script feeds,
not a unit test's job).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_shipped_studies.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("klein_verify_shipped_studies", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["klein_verify_shipped_studies"] = module
    spec.loader.exec_module(module)
    return module


def _write_study(studies_dir: Path, slug: str, *, v2: bool) -> Path:
    study_dir = studies_dir / slug
    study_dir.mkdir(parents=True)
    contract = f'schema_version: 2\nstudy_id: "{slug}"\n' if v2 else 'goal: "legacy study, no schema_version key"\n'
    (study_dir / "study.yaml").write_text(contract, encoding="utf-8")
    return study_dir


def _completed(stdout: str, returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["klein", "verify"], returncode=returncode, stdout=stdout, stderr="")


def _fake_run(responses: dict[str, subprocess.CompletedProcess[str]]):
    def _run(command, **kwargs):
        study_arg = command[command.index("--study") + 1]
        return responses[study_arg]

    return _run


# --------------------------------------------------------------------------
# discover_studies / schema_version
# --------------------------------------------------------------------------


def test_discover_studies_finds_only_directories_with_a_contract(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "09-has-contract", v2=True)
    (studies_dir / "not-a-study").mkdir(parents=True)  # no study.yaml — must be ignored
    (studies_dir / "not-a-study" / "notes.txt").write_text("stray file", encoding="utf-8")

    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)
    found = module.discover_studies()
    assert [p.name for p in found] == ["09-has-contract"]


def test_discover_studies_sorts_deterministically(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "09-iris-first-lesson", v2=True)
    _write_study(studies_dir, "00-glm-claims-quickstart", v2=False)
    _write_study(studies_dir, "03-noisy-rosenbrock-dfo", v2=True)

    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)
    found = [p.name for p in module.discover_studies()]
    assert found == ["00-glm-claims-quickstart", "03-noisy-rosenbrock-dfo", "09-iris-first-lesson"]


def test_schema_version_reads_top_level_key(tmp_path: Path) -> None:
    module = _load_module()
    contract = tmp_path / "study.yaml"
    contract.write_text('schema_version: 2\nstudy_id: "x"\n', encoding="utf-8")
    assert module.schema_version(contract) == 2


def test_schema_version_missing_key_means_v1(tmp_path: Path) -> None:
    module = _load_module()
    contract = tmp_path / "study.yaml"
    contract.write_text('goal: "no schema_version here"\n', encoding="utf-8")
    assert module.schema_version(contract) is None


def test_schema_version_ignores_indented_occurrences(tmp_path: Path) -> None:
    module = _load_module()
    contract = tmp_path / "study.yaml"
    # A nested key sharing the name must not be mistaken for the top-level
    # contract version — only a column-0 key counts.
    contract.write_text("tracks:\n  primary:\n    schema_version: 999\n", encoding="utf-8")
    assert module.schema_version(contract) is None


# --------------------------------------------------------------------------
# parse_summary / count_warned
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("[OK] x: y\nsummary: 19 checks, 0 failed\n", (19, 0)),
        ("[OK] x: y\n[FAIL] z: w\nsummary: 19 checks, 2 failed\n", (19, 2)),
        ("summary:   7 checks,   1 failed", (7, 1)),  # extra whitespace tolerated
    ],
)
def test_parse_summary_extracts_counts(stdout: str, expected: tuple[int, int]) -> None:
    module = _load_module()
    assert module.parse_summary(stdout) == expected


def test_parse_summary_returns_none_without_a_summary_line() -> None:
    module = _load_module()
    assert module.parse_summary("klein: error: study contract missing\n") is None


def test_count_warned_counts_embedded_tags() -> None:
    module = _load_module()
    stdout = (
        "[OK] train.py: [WARN] syntax valid but scaffold stubs remain\n"
        "[OK] guardrail visibility: [WARN] track 'primary' declares 'wall_seconds'\n"
        "[OK] event chain: valid\n"
    )
    assert module.count_warned(stdout) == 2
    assert module.count_warned("[OK] event chain: valid\n") == 0


# --------------------------------------------------------------------------
# render_table
# --------------------------------------------------------------------------


def test_render_table_aligns_columns_with_header_and_rule() -> None:
    module = _load_module()
    rows = [
        ("studies/03-noisy-rosenbrock-dfo", "16", "0", "1", "1"),
        ("studies/09-iris-first-lesson", "17", "0", "2", "2"),
    ]
    table = module.render_table(rows)
    lines = table.splitlines()
    assert lines[0].split() == ["study", "passed", "warned", "failed", "exit"]
    assert set(lines[1].replace(" ", "")) == {"-"}
    assert len(lines) == 2 + len(rows)
    for row, line in zip(rows, lines[2:], strict=True):
        assert line.split() == list(row)


# --------------------------------------------------------------------------
# main() — subprocess boundary faked, no real `klein verify` runs
# --------------------------------------------------------------------------


def test_main_all_clean_exits_zero(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "09-clean", v2=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        _fake_run({"studies/09-clean": _completed("summary: 19 checks, 0 failed\n", 0)}),
    )

    assert module.main([]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    row = next(line for line in out.splitlines() if line.startswith("studies/09-clean"))
    assert row.split() == ["studies/09-clean", "19", "0", "0", "0"]


def test_main_any_failure_exits_one_and_v1_study_skipped_with_note(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "00-legacy", v2=False)
    _write_study(studies_dir, "09-broken", v2=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        _fake_run({"studies/09-broken": _completed("summary: 19 checks, 2 failed\n", 2)}),
    )

    assert module.main([]) == 1
    out, err = capsys.readouterr()
    # a red row names itself on stderr (CI logs show nothing but this script's output)
    assert "error: studies/09-broken: 2 failed check(s) (exit 2)" in err
    assert "studies/00-legacy is schema v1 (no schema_version key) — skipped" in out
    row = next(line for line in out.splitlines() if line.startswith("studies/09-broken"))
    assert row.split() == ["studies/09-broken", "17", "0", "2", "2"]


def test_main_reports_missing_summary_line_as_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "09-crashed", v2=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        _fake_run({"studies/09-crashed": _completed("klein: error: study contract missing\n", 2)}),
    )

    assert module.main([]) == 1
    out, err = capsys.readouterr()
    assert "produced no summary line (exit 2)" in err
    row = next(line for line in out.splitlines() if line.startswith("studies/09-crashed"))
    assert row.split() == ["studies/09-crashed", "?", "0", "?", "2"]


def test_main_studies_filter_matches_slug_and_studies_prefix(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "03-a", v2=True)
    _write_study(studies_dir, "09-b", v2=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        _fake_run({"studies/03-a": _completed("summary: 5 checks, 0 failed\n", 0)}),
    )

    assert module.main(["--studies", "studies/03-a"]) == 0
    out = capsys.readouterr().out
    assert "studies/03-a" in out
    assert "09-b" not in out


def test_main_unknown_studies_filter_is_a_usage_error(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    _write_study(studies_dir, "09-b", v2=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)

    assert module.main(["--studies", "no-such-study"]) == 2
    err = capsys.readouterr().err
    assert "no-such-study" in err


def test_main_no_studies_discovered_is_a_usage_error(tmp_path: Path, monkeypatch, capsys) -> None:
    module = _load_module()
    studies_dir = tmp_path / "studies"
    studies_dir.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "STUDIES_DIR", studies_dir)

    assert module.main([]) == 2
    err = capsys.readouterr().err
    assert "no studies discovered" in err
