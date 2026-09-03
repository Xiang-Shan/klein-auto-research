"""The schema-3 floor bar: `minimum_delta >= max(2*std, range/2)`.

Schema 2 keeps its original `>= std` bar — studies 03 and 05-09 were run and
closed against it and must keep verifying byte-identically. Schema 3 raises it
to the number `consult-protocol.md` states and study 07 paid for
(`knowledge/research-discipline.md` lesson 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kleinlib.checks import floor_bar_problems, preflight_checks


def _floor(std: float, value_range: float, **extra) -> dict:
    return {"k": 5, "std": std, "range": value_range, **extra}


def _metric(minimum_delta: float) -> dict:
    return {"name": "val_auc", "goal": "higher", "minimum_delta": minimum_delta}


# --------------------------------------------------------------------------
# the arithmetic
# --------------------------------------------------------------------------


def test_schema_two_keeps_its_one_std_bar() -> None:
    floor = _floor(0.01, 0.04)  # bar would be max(0.02, 0.02) = 0.02 on schema 3
    assert floor_bar_problems(_metric(0.015), floor, 2) == []
    assert floor_bar_problems(_metric(0.01), floor, 2) == []
    problems = floor_bar_problems(_metric(0.009), floor, 2)
    assert len(problems) == 1
    assert "the exact dishonesty the measurement exists to prevent" in problems[0]


def test_schema_three_requires_twice_the_std() -> None:
    floor = _floor(0.01, 0.01)  # max(0.02, 0.005) = 0.02
    assert floor_bar_problems(_metric(0.02), floor, 3) == []
    problems = floor_bar_problems(_metric(0.015), floor, 3)
    assert len(problems) == 1
    assert "max(2*std 0.02, range/2 0.005) = 0.02" in problems[0]
    assert "a delta inside its own floor" in problems[0]


def test_schema_three_requires_half_the_range_when_that_is_larger() -> None:
    """A 20-draw lottery with one wild draw: the range is the honest bar."""
    floor = _floor(std=0.2236, value_range=1.0)  # max(0.4472, 0.5) = 0.5
    assert floor_bar_problems(_metric(0.5), floor, 3) == []
    problems = floor_bar_problems(_metric(0.46), floor, 3)
    assert "range/2 0.5" in problems[0]


def test_a_delta_that_cleared_schema_two_can_fail_schema_three() -> None:
    floor = _floor(0.03, 0.06)
    assert floor_bar_problems(_metric(0.04), floor, 2) == []
    assert floor_bar_problems(_metric(0.04), floor, 3) != []


def test_a_malformed_block_is_left_to_the_contract_check() -> None:
    """One voice per problem: validate_contract already reported it."""
    assert floor_bar_problems(_metric(0.1), {"std": "wide"}, 3) == []
    assert floor_bar_problems(_metric(0.1), {"std": 0.01}, 3) == []  # no range
    assert floor_bar_problems({"minimum_delta": None}, _floor(0.01, 0.01), 3) == []


# --------------------------------------------------------------------------
# through preflight
# --------------------------------------------------------------------------


def _set_floor(study: Path, *, minimum_delta: float, std: float, value_range: float,
               estimand: str = "marginal-resplit") -> None:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]
    metric["minimum_delta"] = minimum_delta
    metric["noise_floor"] = {
        "k": 5,
        "std": std,
        "range": value_range,
        "mean": 0.5,
        "values": [0.5, 0.51, 0.49, 0.5, 0.5],
        "source": "sweeps/lottery.sidecar.tsv",
        "estimand": estimand,
    }
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


def _floor_check(study: Path):
    checks = preflight_checks(study, require_clean=False, require_branch=False)
    return next(c for c in checks if c.name == "noise floor")


def test_preflight_enforces_the_schema_three_bar(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    _set_floor(study, minimum_delta=0.02, std=0.01, value_range=0.01)
    check = _floor_check(study)
    assert check.ok
    assert "minimum_delta 0.02 >= max(2*std, range/2) = 0.02" in check.message
    assert "estimand 'marginal-resplit'" in check.message

    _set_floor(study, minimum_delta=0.015, std=0.01, value_range=0.01)
    check = _floor_check(study)
    assert not check.ok
    assert "the schema-3 bar" in check.message
    assert "track 'primary'" in check.message


def test_preflight_keeps_the_schema_two_message_verbatim(ready_study) -> None:
    _repo, study = ready_study
    _set_floor(study, minimum_delta=0.015, std=0.01, value_range=0.04)
    check = _floor_check(study)
    # 0.015 >= std 0.01 — passes schema 2 though it would fail the schema-3 bar.
    assert check.ok
    assert check.message == (
        "track 'primary': minimum_delta 0.015 vs measured seed std 0.01"
    )

    _set_floor(study, minimum_delta=0.005, std=0.01, value_range=0.04)
    check = _floor_check(study)
    assert not check.ok
    assert check.message.endswith(
        "— declaring a floor then keeping inside it is the exact dishonesty the "
        "measurement exists to prevent"
    )


def test_fit_noise_alone_is_named_as_not_being_the_bar(ready_study_v3) -> None:
    """A seed spread recorded, no floor measured: say so rather than stay silent."""
    _repo, study = ready_study_v3
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]
    metric.pop("noise_floor", None)
    metric["fit_noise"] = {
        "k": 5,
        "std": 0.001,
        "range": 0.004,
        "mean": 0.5,
        "values": [0.5, 0.501, 0.499, 0.5, 0.5],
        "source": "sweeps/kseed.sidecar.tsv",
    }
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    check = _floor_check(study)
    assert check.ok
    assert "metric.fit_noise is recorded" in check.message
    assert "measures the FIT, not the comparison" in check.message


def test_an_exact_metric_still_waives_the_floor(ready_study_v3) -> None:
    """Package A's waiver is untouched by the new bar."""
    _repo, study = ready_study_v3
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]
    metric["exactness"] = "exact"
    metric["exactness_note"] = "an integer count of cells; resolution is exactly 1"
    metric["minimum_delta"] = 1
    metric.pop("noise_floor", None)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    check = _floor_check(study)
    assert check.ok
    assert "floor waived" in check.message


@pytest.mark.parametrize("std,rng,delta,ok", [
    (0.01, 0.01, 0.02, True),
    (0.01, 0.01, 0.0199, False),
    (0.0, 0.0, 0.0, True),
    (0.1, 1.0, 0.5, True),
    (0.1, 1.0, 0.49, False),
])
def test_the_bar_is_exactly_the_maximum_of_the_two_terms(std, rng, delta, ok) -> None:
    assert (floor_bar_problems(_metric(delta), _floor(std, rng), 3) == []) is ok
