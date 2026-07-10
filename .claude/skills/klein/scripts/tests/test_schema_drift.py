"""Red-test: the fallback schema literals embedded in the skill scripts (for
foreign-repo mode, where kleinlib is not on the path) must stay
byte-identical to ``kleinlib.schema``. This is the structural guard the plan
requires against the 4-vs-5-column drift bug documented in
``kleinlib/schema.py`` and this repo's AGENTS.md ("Schema discipline") —
drift between the skill's embedded copy and the real schema must be
impossible to miss.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _helpers import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kleinlib import schema  # noqa: E402


def test_fallback_results_columns_match_kleinlib_schema(preflight_module):
    assert preflight_module._FALLBACK_RESULTS_COLUMNS == tuple(schema.RESULTS_COLUMNS)


def test_fallback_optional_columns_match_kleinlib_schema(preflight_module):
    assert preflight_module._FALLBACK_OPTIONAL == tuple(schema.OPTIONAL_COLUMNS)


def test_fallback_valid_statuses_match_kleinlib_schema(preflight_module):
    assert preflight_module.VALID_STATUSES == frozenset(schema.VALID_STATUSES) == frozenset(
        preflight_module._FALLBACK_VALID_STATUSES
    )


def test_fallback_aux_columns_match_kleinlib_schema(preflight_module):
    assert preflight_module._FALLBACK_AUX_COLUMNS == tuple(schema.AUX_COLUMNS)


def test_preflight_module_resolved_names_equal_kleinlib(preflight_module):
    # Post drift-check, the names preflight.py actually uses must be bound to
    # kleinlib's values (not silently left on the embedded fallback) whenever
    # kleinlib was importable — which it is here, in-repo.
    assert preflight_module._KLEINLIB_AVAILABLE is True
    assert preflight_module.RESULTS_COLUMNS == tuple(schema.RESULTS_COLUMNS)
    assert preflight_module.AUX_COLUMNS == tuple(schema.AUX_COLUMNS)


def test_preflight_reports_kleinlib_as_schema_source(preflight_module):
    # When kleinlib IS importable (as it is here, in-repo), preflight must
    # say so explicitly — never silently fall back without announcing which
    # schema source is in effect.
    result = preflight_module.check_schema_source()
    assert result.status == "OK"
    assert "kleinlib.schema" in result.message


def test_summarize_aux_columns_match_kleinlib_schema(summarize_module):
    assert summarize_module.AUX_COLUMNS == tuple(schema.AUX_COLUMNS)


def test_drift_detected_when_kleinlib_disagrees(preflight_module):
    """The historical bug this guards against: a 4-column kleinlib schema
    (or any other field drifting) must be caught by find_schema_drift, not
    just "no drift currently" — this exercises the comparison itself, not
    merely today's happy-path equality.
    """
    truncated = ("experiment", "primary_metric", "status", "commit")  # missing "description"
    drift = preflight_module.find_schema_drift(
        truncated,
        preflight_module._FALLBACK_OPTIONAL,
        preflight_module._FALLBACK_VALID_STATUSES,
        preflight_module._FALLBACK_NA_METRIC,
        preflight_module._FALLBACK_NO_COMMIT,
        preflight_module._FALLBACK_AUX_COLUMNS,
    )
    assert len(drift) == 1
    assert "RESULTS_COLUMNS" in drift[0]


def test_no_drift_when_kleinlib_matches(preflight_module):
    drift = preflight_module.find_schema_drift(
        preflight_module._FALLBACK_RESULTS_COLUMNS,
        preflight_module._FALLBACK_OPTIONAL,
        preflight_module._FALLBACK_VALID_STATUSES,
        preflight_module._FALLBACK_NA_METRIC,
        preflight_module._FALLBACK_NO_COMMIT,
        preflight_module._FALLBACK_AUX_COLUMNS,
    )
    assert drift == []
