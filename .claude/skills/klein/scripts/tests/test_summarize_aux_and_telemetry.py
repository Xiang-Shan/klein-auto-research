"""Tests for the new summarize_results.py features: aux panels (automatic
val_brier/val_lift_top10 + user-requested --aux), phase telemetry (actual
vs budget from study.yaml + aux wall_seconds), and --expand-study (sweep
sidecar passthrough). Each degrades gracefully when its sidecar/file is
absent — that is asserted explicitly, not just the happy path.
"""

from __future__ import annotations

from pathlib import Path

RESULTS = (
    "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
    "1\t0.60\tkeep\taaaaaaa\tbaseline\n"
    "2\t0.62\tkeep\tbbbbbbb\ttweak\n"
    "3\t0.58\tdiscard\tccccccc\tworse\n"
    "4\t0.65\tkeep\tddddddd\tbest\n"
)

AUX = (
    "experiment\tmetric\tvalue\n"
    "1\tval_brier\t0.05\n"
    "1\twall_seconds\t300\n"
    "1\tval_lift_top10\t2.0\n"
    "2\tval_brier\t0.04\n"
    "2\twall_seconds\t300\n"
    "2\tval_lift_top10\t2.5\n"
    "3\tval_brier\t0.06\n"
    "3\twall_seconds\t400\n"
    "3\tval_lift_top10\t1.5\n"
    "4\tval_brier\t0.03\n"
    "4\twall_seconds\t400\n"
    "4\tval_lift_top10\t3.0\n"
)

STUDY_YAML = (
    "goal: demo aux+telemetry fixture\n"
    "phases:\n"
    "  - id: phase0\n"
    "    budget_h: 0.2\n"
    "    experiments: {min: 1, max: 2}\n"
    "  - id: phase1\n"
    "    budget_h: 0.1\n"
    "    experiments: {min: 3, max: 4}\n"
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


def test_summary_contains_automatic_aux_panels_and_phase_table(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    code = summarize_module.main([str(results_path), "--goal", "higher"])
    assert code == 0

    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" in summary
    assert "val_brier" in summary
    assert "val_lift_top10" in summary
    assert "## Phase Telemetry" in summary
    assert "phase0" in summary and "phase1" in summary


def test_aux_panel_ranks_by_goal(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path), "--goal", "higher"])
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")

    brier_section = _section(summary, "### val_brier")
    # val_brier goal is "lower": experiment 4 (0.03) must rank above 3 (0.06).
    assert brier_section.index("| 4 |") < brier_section.index("| 3 |")

    lift_section = _section(summary, "### val_lift_top10")
    # val_lift_top10 goal is "higher": experiment 4 (3.0) must rank above 3 (1.5).
    assert lift_section.index("| 4 |") < lift_section.index("| 3 |")


def test_custom_aux_flag_adds_a_panel(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path), "--goal", "higher", "--aux", "wall_seconds", "--aux-goal", "lower"])
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    assert "### wall_seconds (lower) — top 10" in summary


def test_phase_table_actual_vs_budget(summarize_module, tmp_path):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path), "--goal", "higher"])
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    phase_section = _section(summary, "## Phase Telemetry")

    # phase0: (300+300)s = 600s = 0.1667h actual vs 0.20h budget -> under budget
    assert "phase0" in phase_section
    assert "0.17" in phase_section  # actual hours, rounded to 2dp
    assert "under budget" in phase_section

    # phase1: (400+400)s = 800s = 0.2222h actual vs 0.10h budget -> OVER budget
    assert "phase1" in phase_section
    assert "0.22" in phase_section
    assert "OVER budget" in phase_section


def test_phase_table_matches_with_yaml_fallback_parser(summarize_module, tmp_path, monkeypatch):
    # Force the stdlib-only tiny parser (simulating a foreign repo without
    # PyYAML) and confirm it produces the identical phase table.
    results_path = _write_fixture(tmp_path)
    monkeypatch.setattr(summarize_module, "yaml", None)
    summarize_module.main([str(results_path), "--goal", "higher"])
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    phase_section = _section(summary, "## Phase Telemetry")
    assert "0.17" in phase_section
    assert "under budget" in phase_section
    assert "0.22" in phase_section
    assert "OVER budget" in phase_section


def test_expand_study_renders_fixture_sidecar(summarize_module, tmp_path, capsys):
    results_path = _write_fixture(tmp_path)
    summarize_module.main([str(results_path), "--goal", "higher", "--expand-study", "demo-sweep"])
    out = capsys.readouterr().out
    assert "demo-sweep.sidecar.tsv" in out
    assert "trial" in out and "val_auc" in out
    assert "0.60" in out and "0.63" in out


def test_expand_study_missing_sidecar_degrades_gracefully(summarize_module, tmp_path, capsys):
    results_path = _write_fixture(tmp_path)
    code = summarize_module.main([str(results_path), "--goal", "higher", "--expand-study", "no-such-sweep"])
    assert code == 0  # never crashes
    out = capsys.readouterr().out
    assert "not found" in out


# --------------------------------------------------------------------------
# Graceful degradation: no sidecar / no study.yaml at all
# --------------------------------------------------------------------------


def test_no_aux_sidecar_means_no_aux_section(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    code = summarize_module.main([str(results_path), "--goal", "higher"])
    assert code == 0
    summary = results_path.with_name("results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" not in summary
    assert "## Phase Telemetry" not in summary
    # The base summary must still render correctly (source behavior kept).
    assert "## Frontier" in summary
    assert "- keep: 3" in summary


def test_custom_aux_requested_but_sidecar_missing_notes_it(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    summarize_module.main([str(results_path), "--goal", "higher", "--aux", "val_brier"])
    summary = results_path.with_name("results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" in summary
    assert "not found" in summary


def test_no_study_yaml_means_no_phase_section_even_with_aux(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "aux_metrics.tsv").write_text(AUX, encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    summarize_module.main([str(results_path), "--goal", "higher"])
    summary = results_path.with_name("results_summary.md").read_text(encoding="utf-8")
    assert "## Aux Panels" in summary  # sidecar present -> still rendered
    assert "## Phase Telemetry" not in summary  # no study.yaml -> no crash, no section


def test_malformed_study_yaml_degrades_gracefully(summarize_module, tmp_path):
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "aux_metrics.tsv").write_text(AUX, encoding="utf-8")
    (tmp_path / "study.yaml").write_text("phases: [this is not a list of mappings\n", encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    code = summarize_module.main([str(results_path), "--goal", "higher"])
    assert code == 0  # never crashes on malformed study.yaml


def test_phase_table_uses_id_ranges_not_count_bounds(summarize_module, tmp_path):
    # assets/study-template.yaml phases carry BOTH count bounds
    # (min_experiments/max_experiments, for the stop rule) and an explicit
    # `experiments: {min,max}` ID range (for telemetry). The parser must
    # attribute wall-clock by the ID range and IGNORE the count bounds —
    # treating counts as ranges double-counted study-02's phases.
    template_shape_yaml = (
        "goal: template-shape fixture\n"
        "phases:\n"
        "  - id: 0\n"
        "    desc: anchors\n"
        "    min_experiments: 1\n"
        "    max_experiments: 2\n"
        "    experiments: {min: 1, max: 2}\n"
        "    budget_h: 0.2\n"
        "  - id: 1\n"
        "    desc: exploration\n"
        "    min_experiments: 3\n"  # count bound == 3 but ID range is 3-4;
        "    max_experiments: 5\n"  # if counts were misread as ranges this
        "    experiments: {min: 3, max: 4}\n"  # phase would grab exp 5 too
        "    budget_h: 0.1\n"
    )
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "aux_metrics.tsv").write_text(AUX, encoding="utf-8")
    (tmp_path / "study.yaml").write_text(template_shape_yaml, encoding="utf-8")
    results_path = tmp_path / "results.tsv"
    code = summarize_module.main([str(results_path), "--goal", "higher"])
    assert code == 0

    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    assert "## Phase Telemetry" in summary
    phase_section = _section(summary, "## Phase Telemetry")
    # AUX fixture wall_seconds: exps 1-2 sum to 600s, exps 3-4 to 800s
    assert "| 1-2 |" in phase_section and "0.17" in phase_section
    assert "| 3-4 |" in phase_section and "0.22" in phase_section
    assert "OVER budget" in phase_section
    # numeric phase id 0 must render as 0, not n/a (falsy-zero regression)
    assert "| 0 |" in phase_section
    assert "n/a" not in phase_section


def test_phase_with_only_count_bounds_gets_no_range(summarize_module, tmp_path):
    # A phase declaring ONLY count bounds must not be attributed any
    # experiments (no ID range -> no wall-clock attribution).
    yaml_text = (
        "phases:\n"
        "  - id: 0\n"
        "    min_experiments: 1\n"
        "    max_experiments: 4\n"
        "    budget_h: 0.2\n"
    )
    (tmp_path / "results.tsv").write_text(RESULTS, encoding="utf-8")
    (tmp_path / "aux_metrics.tsv").write_text(AUX, encoding="utf-8")
    (tmp_path / "study.yaml").write_text(yaml_text, encoding="utf-8")
    code = summarize_module.main([str(tmp_path / "results.tsv"), "--goal", "higher"])
    assert code == 0
    summary = (tmp_path / "results_summary.md").read_text(encoding="utf-8")
    # 1-4 (counts misread as a range) must NOT appear as this phase's range
    if "## Phase Telemetry" in summary:
        assert "| 1-4 |" not in _section(summary, "## Phase Telemetry")
