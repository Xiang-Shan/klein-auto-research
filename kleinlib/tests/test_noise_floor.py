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
