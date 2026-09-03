from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kleinlib.noise_floor import floor_from_sidecar, summarize_noise, yaml_block


def test_known_values_statistics_and_suggested_delta() -> None:
    floor = summarize_noise([0.670, 0.669, 0.671, 0.668, 0.672], seeds=[42, 43, 44, 45, 46])
    assert floor.k == 5
    assert floor.mean == pytest.approx(0.670, abs=1e-9)
    assert floor.std == pytest.approx(0.00158113883, rel=1e-6)  # ddof=1
    assert floor.value_range == pytest.approx(0.004, abs=1e-12)
    # max(2*std, range/2) = max(0.00316, 0.002)
    assert floor.suggested_minimum_delta == pytest.approx(2 * floor.std)


def test_fewer_than_three_values_refused() -> None:
    with pytest.raises(ValueError, match="k >= 3"):
        summarize_noise([0.5, 0.6])
    with pytest.raises(ValueError, match="finite"):
        summarize_noise([0.5, float("nan"), 0.6])
    with pytest.raises(ValueError, match="same length"):
        summarize_noise([0.5, 0.6, 0.7], seeds=[1, 2])


def test_sidecar_parsing_skips_non_ok_rows(tmp_path: Path) -> None:
    sidecar = tmp_path / "noise_floor.sidecar.tsv"
    sidecar.write_text(
        "trial\tparams_json\tprimary_metric\twall_seconds\tstatus\terror\n"
        '1\t{"seed": 42}\t0.670\t1.0\tok\t\n'
        '2\t{"seed": 43}\tNA\t1.0\tcrash\tboom\n'
        '3\t{"seed": 44}\t0.669\t1.0\tok\t\n'
        '4\t{"seed": 45}\t0.671\t1.0\tok\t\n',
        encoding="utf-8",
    )
    floor = floor_from_sidecar(sidecar)
    assert floor.k == 3
    assert floor.values == (0.670, 0.669, 0.671)

    short = tmp_path / "short.sidecar.tsv"
    short.write_text(
        "trial\tparams_json\tprimary_metric\twall_seconds\tstatus\terror\n"
        '1\t{}\t0.5\t1.0\tok\t\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=">= 3 ok rows"):
        floor_from_sidecar(short)


def test_yaml_block_round_trips_through_safe_load() -> None:
    floor = summarize_noise([1.0, 1.1, 0.9], seeds=[1, 2, 3])
    block = yaml_block("primary", floor, source="sweeps/noise_floor.sidecar.tsv",
                       measured_after="E0001")
    # strip the alignment comment on minimum_delta before parsing the fragment
    body = "\n".join(
        line[6:] for line in block.splitlines() if line.startswith("      ")
    )
    parsed = yaml.safe_load(body)
    assert parsed["noise_floor"]["k"] == 3
    assert parsed["noise_floor"]["seeds"] == [1, 2, 3]
    assert parsed["noise_floor"]["measured_after"] == "E0001"
    assert parsed["minimum_delta"] == pytest.approx(floor.suggested_minimum_delta, rel=1e-4)
    # method: is omitted unless given, and round-trips when it is
    assert "method" not in parsed["noise_floor"]
    with_method = yaml_block(
        "primary", floor, source="--values", method="paired-bootstrap"
    )
    parsed_method = yaml.safe_load(
        "\n".join(
            line[6:] for line in with_method.splitlines() if line.startswith("      ")
        )
    )
    assert parsed_method["noise_floor"]["method"] == "paired-bootstrap"


# --------------------------------------------------------------------------
# `klein noise-floor --recipe --estimand` (the consult protocol's vocabulary)
# --------------------------------------------------------------------------


def test_recipe_defaults_the_estimand_and_a_mismatch_may_be_declared() -> None:
    from kleinlib.noise_floor import resolve_estimand

    assert resolve_estimand("seed-sweep", None) == "fit-noise"
    assert resolve_estimand("split-lottery", None) == "marginal-resplit"
    assert resolve_estimand("paired-bootstrap", None) == "paired-comparison"
    assert resolve_estimand(None, None) is None
    # Study 09 ran a split lottery that produced PAIRED differences; the pair
    # is legal, but it has to be said out loud.
    assert resolve_estimand("split-lottery", "paired-comparison") == "paired-comparison"
    with pytest.raises(ValueError, match="estimand must be one of"):
        resolve_estimand(None, "vibes")
    with pytest.raises(ValueError, match="recipe must be one of"):
        resolve_estimand("grid-search", None)


def test_the_recipes_and_estimands_match_the_metrology_module() -> None:
    """Two spellings of one vocabulary would be one spelling too many."""
    from kleinlib import metrology
    from kleinlib.noise_floor import ESTIMANDS, RECIPE_ESTIMAND, RECIPES

    assert RECIPES == metrology.RECIPES
    assert ESTIMANDS == metrology.ESTIMANDS
    assert RECIPE_ESTIMAND == metrology.RECIPE_ESTIMAND


def test_fit_noise_lands_under_its_own_key_with_no_minimum_delta() -> None:
    from kleinlib.noise_floor import block_key, yaml_block

    assert block_key("fit-noise") == "fit_noise"
    assert block_key("marginal-resplit") == "noise_floor"
    assert block_key(None) == "noise_floor"

    floor = summarize_noise([1.0, 1.1, 0.9], seeds=[1, 2, 3])
    block = yaml_block("primary", floor, source="--values", estimand="fit-noise")
    parsed = yaml.safe_load(
        "\n".join(line[6:] for line in block.splitlines() if line.startswith("      "))
    )
    assert set(parsed) == {"fit_noise"}
    assert "minimum_delta" not in block
    assert parsed["fit_noise"]["estimand"] == "fit-noise"
    assert "NOT the keep bar" in block


def test_a_bar_carrying_estimand_is_written_into_the_noise_floor_block() -> None:
    from kleinlib.noise_floor import yaml_block

    floor = summarize_noise([1.0, 1.1, 0.9])
    block = yaml_block(
        "primary",
        floor,
        source="sweeps/lottery.sidecar.tsv",
        method="split-lottery",
        estimand="marginal-resplit",
    )
    parsed = yaml.safe_load(
        "\n".join(line[6:] for line in block.splitlines() if line.startswith("      "))
    )
    assert parsed["noise_floor"]["estimand"] == "marginal-resplit"
    assert parsed["noise_floor"]["method"] == "split-lottery"
    assert parsed["minimum_delta"] == pytest.approx(
        floor.suggested_minimum_delta, rel=1e-4
    )


def test_cli_seed_sweep_refuses_to_hand_over_a_bar(capsys) -> None:
    from kleinlib import cli

    argv = ["noise-floor", "--values", "1.0,1.1,0.9", "--recipe", "seed-sweep"]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "estimand=fit-noise" in out
    assert "recipe=seed-sweep" in out
    assert "fit noise — NOT a keep bar" in out
    assert "fit_noise:" in out
    assert "minimum_delta" not in out
    assert "measure the floor that will JUDGE the comparison" in out


def test_cli_paired_bootstrap_prints_the_estimand_line_and_the_bar(capsys) -> None:
    from kleinlib import cli

    argv = [
        "noise-floor",
        "--values",
        "0.01,0.02,0.015,0.03",
        "--recipe",
        "paired-bootstrap",
    ]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert 'estimand: "paired-comparison"' in out
    assert 'method: "paired-bootstrap"' in out
    assert "suggested minimum_delta=" in out


def test_cli_estimand_may_be_declared_against_the_recipe_default(capsys) -> None:
    from kleinlib import cli

    argv = [
        "noise-floor",
        "--values",
        "0.1,0.2,0.15",
        "--recipe",
        "split-lottery",
        "--estimand",
        "paired-comparison",
    ]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert 'method: "split-lottery"' in out
    assert 'estimand: "paired-comparison"' in out


def test_cli_refuses_recipe_and_method_together() -> None:
    from kleinlib import cli

    argv = [
        "noise-floor",
        "--values",
        "1,2,3",
        "--recipe",
        "seed-sweep",
        "--method",
        "hand-waving",
    ]
    with pytest.raises(SystemExit):
        cli.main(argv)


def test_cli_without_a_recipe_prints_exactly_what_it_always_did(capsys) -> None:
    """The legacy invocation is byte-identical: no recipe, no estimand line."""
    from kleinlib import cli

    assert cli.main(["noise-floor", "--values", "1.0,1.1,0.9"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        "k=3  mean=1  std=0.1  range=0.2  suggested minimum_delta=0.2\n"
    )
    assert "estimand" not in out
    assert "recipe=" not in out
    assert "noise_floor:" in out


def test_module_entry_point_and_cli_verb_print_the_same_report(capsys) -> None:
    from kleinlib import cli
    from kleinlib.noise_floor import _main

    argv = ["--values", "1.0,1.1,0.9", "--recipe", "split-lottery"]
    assert _main(argv) == 0
    module_out = capsys.readouterr().out
    assert cli.main(["noise-floor", *argv]) == 0
    assert capsys.readouterr().out == module_out


_SIDECAR_TEXT = (
    "trial\tparams_json\tprimary_metric\twall_seconds\tstatus\terror\n"
    '1\t{"seed": 42}\t0.670\t1.0\tok\t\n'
    '2\t{"seed": 43}\t0.669\t1.0\tok\t\n'
    '3\t{"seed": 44}\t0.671\t1.0\tok\t\n'
)


def _floor_study(tmp_path: Path) -> Path:
    study = tmp_path / "studies" / "99-floor"
    study.mkdir(parents=True)
    (study / "study.yaml").write_text("study_id: 99-floor\n", encoding="utf-8")
    return study


def test_an_explicit_sidecar_is_resolved_against_the_study_like_the_default(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """`--sidecar sweeps/x.sidecar.tsv` is the study-relative spelling every
    document uses (consult-protocol Phase 0, `klein sweep register --sidecar`),
    and the verb's own default is `<study>/sweeps/noise_floor.sidecar.tsv` —
    so a relative path must not be read against the process working directory."""
    from kleinlib import cli

    study = _floor_study(tmp_path)
    (study / "sweeps").mkdir()
    (study / "sweeps" / "split_lottery.sidecar.tsv").write_text(_SIDECAR_TEXT, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert cli.main(
        ["noise-floor", "--study", str(study), "--sidecar", "sweeps/split_lottery.sidecar.tsv"]
    ) == 0
    out = capsys.readouterr().out
    assert "k=3" in out
    # the `source:` the block advertises is study-relative and POSIX
    assert 'source: "sweeps/split_lottery.sidecar.tsv"' in out


def test_a_sidecar_that_exists_nowhere_is_a_clean_error_not_a_traceback(
    tmp_path: Path, capsys
) -> None:
    from kleinlib import cli

    study = _floor_study(tmp_path)
    assert cli.main(["noise-floor", "--study", str(study), "--sidecar", "sweeps/nope.tsv"]) == 2
    err = capsys.readouterr().err
    assert "--sidecar does not exist" in err
    assert "study-relative" in err and "working-directory-relative" in err
