"""Tests for the new summarize_results.py features: aux panels (automatic
val_brier/val_lift_top10 + user-requested --aux) and --expand-study (sweep
sidecar passthrough). Each degrades gracefully when its sidecar/file is
absent — that is asserted explicitly, not just the happy path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RESULTS = (
    "experiment\ttrack\tprimary_metric\tstatus\tcommit\tdescription\n"
    "E0001\tprimary\t0.60\tkeep\taaaaaaa\tbaseline\n"
    "E0002\tprimary\t0.62\tkeep\tbbbbbbb\ttweak\n"
    "E0003\tprimary\t0.58\tdiscard\tccccccc\tworse\n"
    "E0004\tprimary\t0.65\tkeep\tddddddd\tbest\n"
)

AUX = (
    "experiment\tmetric\tvalue\n"
    "E0001\tval_brier\t0.05\n"
    "E0001\twall_seconds\t300\n"
    "E0001\tval_lift_top10\t2.0\n"
    "E0002\tval_brier\t0.04\n"
    "E0002\twall_seconds\t300\n"
    "E0002\tval_lift_top10\t2.5\n"
    "E0003\tval_brier\t0.06\n"
    "E0003\twall_seconds\t400\n"
    "E0003\tval_lift_top10\t1.5\n"
    "E0004\tval_brier\t0.03\n"
    "E0004\twall_seconds\t400\n"
    "E0004\tval_lift_top10\t3.0\n"
)

STUDY_YAML = (
    "schema_version: 3\n"
    "tracks:\n"
    "  primary:\n"
    "    metric: {name: val_auc, goal: higher, minimum_delta: 0.0}\n"
)

SIDECAR = "trial\tlr\tval_auc\n" "1\t0.01\t0.60\n" "2\t0.05\t0.63\n"


def _write_fixture(tmp_path: Path) -> Path:
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "aux_metrics.tsv").write_text(AUX, encoding="utf-8")
    (tmp_path / "study.yaml").write_text(STUDY_YAML, encoding="utf-8")
    sweeps = tmp_path / "sweeps"
    sweeps.mkdir()
    (sweeps / "demo-sweep.sidecar.tsv").write_text(SIDECAR, encoding="utf-8")
    return tmp_path / "results.tsv"


def _section(text: str, heading: str) -> str:
    """Return the text of a "## heading" ... up to the next "## " block."""
    start = text.index(heading)
    rest = text[start + len(heading) :]
    next_h2 = rest.find("\n## ")
    return rest if next_h2 == -1 else rest[:next_h2]


def test_summary_contains_automatic_aux_panels(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    code = summarize_module.main([str(results_path)])
    assert code == 0

    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" in summary
    assert "val_brier" in summary
    assert "val_lift_top10" in summary


def test_aux_panel_ranks_by_goal(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path)])
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")

    brier_section = _section(summary, "### val_brier")
    # val_brier goal is "lower": experiment 4 (0.03) must rank above 3 (0.06).
    assert brier_section.index("| E0004 |") < brier_section.index("| E0003 |")

    lift_section = _section(summary, "### val_lift_top10")
    # val_lift_top10 goal is "higher": experiment 4 (3.0) must rank above 3 (1.5).
    assert lift_section.index("| E0004 |") < lift_section.index("| E0003 |")


def test_custom_aux_flag_adds_a_panel(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path), "--aux", "wall_seconds", "--aux-goal", "lower"])
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    assert "### wall_seconds (lower) — top 10" in summary


def test_expand_study_renders_fixture_sidecar(summarize_module, tmp_path, capsys):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path), "--expand-study", "demo-sweep"])
    out = capsys.readouterr().out
    assert "demo-sweep.sidecar.tsv" in out
    assert "trial" in out and "val_auc" in out
    assert "0.60" in out and "0.63" in out


def test_expand_study_missing_sidecar_degrades_gracefully(summarize_module, tmp_path, capsys):
    results_path = _write_fixture(tmp_path)
    code = summarize_module.main([str(results_path), "--expand-study", "no-such-sweep"])
    assert code == 0  # never crashes
    out = capsys.readouterr().out
    assert "not found" in out


# --------------------------------------------------------------------------
# Graceful degradation: no sidecar / no study.yaml at all
# --------------------------------------------------------------------------


def test_no_aux_sidecar_means_no_aux_section(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "study.yaml").write_text(STUDY_YAML, encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    code = summarize_module.main([str(results_path)])
    assert code == 0
    summary = results_path.with_name("results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" not in summary
    # The base summary must still render correctly (source behavior kept).
    assert "## Frontier" in summary
    assert "- keep: 3" in summary


def test_custom_aux_requested_but_sidecar_missing_notes_it(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "study.yaml").write_text(STUDY_YAML, encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    summarize_module.main([str(results_path), "--aux", "val_brier"])
    summary = results_path.with_name("results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" in summary
    assert "not found" in summary


def test_malformed_study_yaml_fails_instead_of_guessing_direction(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "aux_metrics.tsv").write_text(AUX, encoding="utf-8")
    (tmp_path / "study.yaml").write_text("phases: [this is not a list of mappings\n", encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    with pytest.raises(ValueError, match="could not parse metric direction"):
        summarize_module.main([str(results_path)])

