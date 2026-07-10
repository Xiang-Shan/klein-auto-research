"""Tests for kleinlib.profile_fallback.profile_dataframe's flags and checklist."""

from __future__ import annotations

import pandas as pd

from kleinlib import profile_fallback


def test_profile_dataframe_flags_id_yesno_and_missingness():
    n = 20
    df = pd.DataFrame(
        {
            "policy_id": [f"P{i:04d}" for i in range(n)],  # ID-like: all unique
            "has_claim": ["Yes" if i % 3 == 0 else "No" for i in range(n)],  # Yes/No
            "mostly_missing": [None] * 15 + [1.0] * 5,  # 75% missing
            "age": list(range(20, 20 + n)),
        }
    )

    report = profile_fallback.profile_dataframe(df)

    assert "ID-like" in report
    assert "policy_id" in report
    assert "Yes/No-pattern string" in report
    assert "has_claim" in report
    assert "High missingness" in report
    assert "mostly_missing" in report
    assert "Modeling implications" in report


def test_profile_dataframe_target_balance_and_imbalance_note():
    n = 100
    df = pd.DataFrame(
        {
            "x": range(n),
            "claim_status": [1 if i < 6 else 0 for i in range(n)],  # 6% positive
        }
    )
    report = profile_fallback.profile_dataframe(df, target="claim_status")
    assert "Target balance" in report
    assert "imbalanced" in report


def test_profile_dataframe_continuous_target_shows_stats_not_counts():
    n = 50
    df = pd.DataFrame({"x": range(n), "severity": [float(i) * 100 for i in range(n)]})
    report = profile_fallback.profile_dataframe(df, target="severity")
    assert "Target balance" in report
    assert "mean:" in report


def test_profile_dataframe_no_flags_clean_data():
    # Repeated ints (not a sequential-looking ID) + a continuous float
    # column (near-unique but exempt from ID-like — see `_is_floaty`).
    df = pd.DataFrame(
        {
            "a": [1, 2, 1, 2, 3, 1, 2, 3],
            "b": [5.0, 6.0, 5.5, 6.2, 5.8, 6.1, 5.3, 6.4],
        }
    )
    report = profile_fallback.profile_dataframe(df)
    assert "(none)" in report
    assert "No structural red flags" in report
