"""A contract key that is nearly a known key is almost always a typo (Klein 3.1).

An unknown top-level key is legal — two exhibits carry keys their own library
reads — so it is ignored. That makes a typo dangerous: `polcy: {rigor: quick}`
would be judged at full rigor, `confimation:` would drop a requirement, and
nothing would say so. Preflight now says so, as a warning.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from kleinlib.checks import preflight_checks
from kleinlib.contract import KNOWN_TOP_LEVEL_KEYS, misspelled_keys

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_a_near_miss_of_a_known_key_is_named_with_the_key_it_nearly_is() -> None:
    contract = {"polcy": {}, "predicitons": [], "confimation": {}, "policy": {}}
    assert misspelled_keys(contract) == [
        ("polcy", "policy"),
        ("predicitons", "predictions"),
        ("confimation", "confirmation"),
    ]


def test_a_study_s_own_keys_are_left_alone() -> None:
    assert misspelled_keys({"simulation": {}, "sealed_lock": 1, "notes": "x", "study_id": "01-x"}) == []


def test_no_shipped_exhibit_carries_a_near_miss() -> None:
    studies = sorted((REPO_ROOT / "studies").glob("[0-9][0-9]-*/study.yaml"))
    assert studies
    for path in studies:
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert misspelled_keys(contract) == [], path
        # and every key the exhibits use that the engine reads is known
        assert {"study_id", "tracks", "phases"} <= KNOWN_TOP_LEVEL_KEYS


def test_preflight_warns_about_a_typo_and_says_nothing_otherwise(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    names = [check.name for check in preflight_checks(study, require_clean=False)]
    assert "contract keys" not in names  # no row when there is nothing to say

    path = study / "study.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\npolcy:\n  rigor: quick\n", encoding="utf-8")
    rows = [check for check in preflight_checks(study, require_clean=False) if check.name == "contract keys"]
    assert len(rows) == 1 and rows[0].ok is True
    assert rows[0].message.startswith("[WARN] ") and "did you mean `policy`" in rows[0].message
