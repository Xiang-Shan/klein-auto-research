"""E3 — the schema-3 contract: the typed inquiry, and what it refuses.

Two properties are load-bearing and each gets a test of its own:

1. **``schema_version`` selects the rule set.** A schema-2 contract sees exactly
   the checks it was notarized under; nothing schema 3 adds can retro-fail the
   shipped studies.
2. **Nothing in the contract is ever executed.** A prediction is decided by
   arithmetic on a closed operator set — no ``eval``, no ``exec``, no
   ``compile`` — and the last test in this module greps for that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from kleinlib.contract import (
    CONFIRMATION_DEFAULTS,
    ENTRYPOINT_BY_KIND,
    KNOWN_KINDS,
    SOURCE_TAG_RE,
    SUPPORTED_SCHEMA_VERSIONS,
    confirmation_require,
    entrypoint_spec,
    mutable_surface,
    normalize_tracks,
    schema_version,
    study_kind,
    task_family,
    track_kind,
    validate_contract,
)
from kleinlib.decision import validate_rule
from kleinlib.schema import KNOWN_MODALITIES, KNOWN_PROFILES, MODALITY_CARD_SECTIONS

V3 = """
schema_version: 3
study_id: "03-demo"
goal: "does the candidate beat the baseline"
domain: "test"
target: "y"
kind: "predict"
profile: "generic"
audience: "the maintainers of this test suite"
task_type: "classification"
method_depth: "brief"
family: "linear"
entrypoint:
  command: ["uv", "run", "--locked", "python", "-u", "train.py"]
  mutable: ["train.py"]
tracks:
  primary:
    mode: frontier
    metric:
      name: "val_auc"
      goal: "higher"
      minimum_delta: 0.01
    guardrails: {}
data:
  source: "csv:fixture.csv"
  modality: "tabular"
  prepared_path: "data/prepared/fixture.csv"
  split:
    kind: stratified
    seed: 42
    development_size: 0.20
    test_size: 0.20
max_run_seconds: 60
phases:
  - id: adaptive-1
    description: "adaptive"
    budget_seconds: 600
    max_experiments: 4
  - id: confirmation
    description: "sealed"
    budget_seconds: 300
    max_experiments: 1
research_questions:
  - id: RQ1
    question: "does it?"
    prior: "no"
deliverables:
  - findings.md
"""


def base() -> dict:
    return yaml.safe_load(V3)


@pytest.fixture
def study_dir(tmp_path: Path) -> Path:
    """A bare directory named as the contract's ``study_id`` demands."""
    study = tmp_path / "studies" / "03-demo"
    study.mkdir(parents=True)
    (study / "train.py").write_text("# the mutable surface\n", encoding="utf-8")
    return study


def problems(contract: dict, study: Path | None = None) -> list[str]:
    return validate_contract(contract, study)


# ---------------------------------------------------------------------------
# The version switch
# ---------------------------------------------------------------------------


def test_both_rule_sets_are_supported_and_nothing_else_is() -> None:
    assert SUPPORTED_SCHEMA_VERSIONS == {2, 3}
    for bad in (1, 4, 0):
        assert problems({"schema_version": bad}) == [
            f"schema_version must be 2 or 3 (got {bad}; version-1 studies are "
            "readable at tag v1.3.0)"
        ]


def test_a_valid_v3_contract_has_no_problems(study_dir: Path) -> None:
    assert problems(base(), study_dir) == []


def test_schema_2_never_sees_a_schema_3_rule(study_dir: Path) -> None:
    """The whole safety argument: drop the version and every schema-3 key stops
    being checked — which is why studies 03 and 05-09 keep verifying forever."""
    contract = base()
    contract["schema_version"] = 2
    for key in ("kind", "profile", "audience", "entrypoint"):
        contract.pop(key)
    contract["data"].pop("modality")
    contract["tracks"]["primary"].pop("mode")
    contract["predictions"] = [{"id": "not-an-id", "nonsense": True}]
    assert problems(contract, study_dir) == []


# ---------------------------------------------------------------------------
# The three axes
# ---------------------------------------------------------------------------


def test_kind_is_required_and_closed(study_dir: Path) -> None:
    assert len(KNOWN_KINDS) == 7 and "optimize" in KNOWN_KINDS
    contract = base()
    contract["kind"] = "guess"
    assert f"kind must be one of {list(KNOWN_KINDS)}" in problems(contract, study_dir)
    contract.pop("kind")
    assert f"kind must be one of {list(KNOWN_KINDS)}" in problems(contract, study_dir)


def test_a_track_may_override_the_study_kind(study_dir: Path) -> None:
    """Study 09 ran a registered test beside a known-truth simulation."""
    contract = base()
    contract["tracks"]["sim"] = {
        "kind": "simulate",
        "mode": "registered",
        "metric": {"name": "val_auc", "goal": "higher", "minimum_delta": 0.01},
        "guardrails": {},
    }
    contract["phases"][-1]["max_experiments"] = 2
    assert problems(contract, study_dir) == []
    tracks = normalize_tracks(contract)
    assert study_kind(contract) == "predict"
    assert track_kind(contract, tracks["primary"]) == "predict"
    assert track_kind(contract, tracks["sim"]) == "simulate"

    contract["tracks"]["sim"]["kind"] = "guess"
    assert any("kind override" in p for p in problems(contract, study_dir))


def test_modality_is_required_and_selects_the_card_headings(study_dir: Path) -> None:
    assert len(KNOWN_MODALITIES) == 8
    assert set(MODALITY_CARD_SECTIONS) == set(KNOWN_MODALITIES)
    for modality, expected in (
        ("timeseries", "Time policy"),
        ("image", "Group policy"),
        ("simulation", "DGP card"),
        ("none", "Verifier card"),
    ):
        assert expected in MODALITY_CARD_SECTIONS[modality]
    assert "Clean-room leakage audit" not in MODALITY_CARD_SECTIONS["none"]
    for sections in MODALITY_CARD_SECTIONS.values():
        assert "Go / no-go" in sections

    contract = base()
    contract["data"].pop("modality")
    assert any("data.modality is required" in p for p in problems(contract, study_dir))


def test_profile_is_a_shipped_name_or_a_repo_local_document(tmp_path: Path) -> None:
    study = tmp_path / "studies" / "03-demo"
    study.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (study / "train.py").write_text("", encoding="utf-8")
    assert KNOWN_PROFILES == ("generic", "ml-research", "math", "insurance")

    contract = base()
    contract["profile"] = "climate"
    assert any("profile must be one of" in p for p in problems(contract, study))

    contract.pop("profile")
    contract["profile_doc"] = "profiles/climate.md"
    assert "profile_doc does not exist: profiles/climate.md" in problems(contract, study)

    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "climate.md").write_text("# Climate\n", encoding="utf-8")
    assert problems(contract, study) == []


def test_a_contract_with_neither_profile_nor_profile_doc_is_refused(study_dir: Path) -> None:
    contract = base()
    contract.pop("profile")
    assert any("profile_doc must name" in p for p in problems(contract, study_dir))


# ---------------------------------------------------------------------------
# The entrypoint and the mutable surface
# ---------------------------------------------------------------------------


def test_entrypoint_paths_stay_inside_the_study(study_dir: Path) -> None:
    contract = base()
    contract["entrypoint"]["mutable"] = ["../elsewhere.py"]
    assert any("no absolute path, no '..'" in p for p in problems(contract, study_dir))

    contract["entrypoint"]["mutable"] = ["/etc/passwd"]
    assert any("no absolute path, no '..'" in p for p in problems(contract, study_dir))

    contract["entrypoint"]["mutable"] = ["missing.py"]
    assert "entrypoint.mutable names a missing file: missing.py" in problems(contract, study_dir)

    contract["entrypoint"] = {"command": [], "mutable": ["train.py"]}
    assert "entrypoint.command must be a non-empty list of strings" in problems(
        contract, study_dir
    )

    contract.pop("entrypoint")
    assert "entrypoint is required: {command: [...], mutable: [...]}" in problems(
        contract, study_dir
    )


def test_the_scaffolded_entrypoint_is_named_by_kind() -> None:
    assert set(ENTRYPOINT_BY_KIND) == set(KNOWN_KINDS)
    assert ENTRYPOINT_BY_KIND["predict"] == "train.py"
    assert ENTRYPOINT_BY_KIND["simulate"] == "simulate.py"
    assert ENTRYPOINT_BY_KIND["optimize"] == "search.py"
    assert {ENTRYPOINT_BY_KIND[k] for k in ("estimate", "test", "replicate", "discover")} == {
        "analyze.py"
    }


def test_mutable_surface_defaults_to_train_py_on_schema_2() -> None:
    contract = base()
    contract["schema_version"] = 2
    assert mutable_surface(contract) == ("train.py",)
    assert entrypoint_spec({})["command"][-1] == "train.py"

    contract["schema_version"] = 3
    contract["entrypoint"]["mutable"] = ["search.py", "lib/moves.py"]
    assert mutable_surface(contract) == ("search.py", "lib/moves.py")


# ---------------------------------------------------------------------------
# Track mode, exactness, external incumbent, verifier
# ---------------------------------------------------------------------------


def test_mode_defaults_to_frontier_only_on_schema_3() -> None:
    """Setting the key on a schema-2 contract would change what schema-2 sees."""
    contract = base()
    contract["tracks"]["primary"].pop("mode")
    assert normalize_tracks(contract)["primary"]["mode"] == "frontier"
    contract["schema_version"] = 2
    assert "mode" not in normalize_tracks(contract)["primary"]


def test_mode_is_closed(study_dir: Path) -> None:
    contract = base()
    contract["tracks"]["primary"]["mode"] = "exploratory"
    assert any("mode must be frontier or registered" in p for p in problems(contract, study_dir))


def test_exact_metrics_must_say_what_their_resolution_is(study_dir: Path) -> None:
    contract = base()
    contract["tracks"]["primary"]["metric"]["exactness"] = "exact"
    assert any("requires metric.exactness_note" in p for p in problems(contract, study_dir))

    contract["tracks"]["primary"]["metric"]["exactness_note"] = "integer objective; resolution 1"
    assert problems(contract, study_dir) == []

    contract["tracks"]["primary"]["metric"]["exactness"] = "stochastic"
    assert any("applies to exact metrics only" in p for p in problems(contract, study_dir))

    contract["tracks"]["primary"]["metric"].pop("exactness_note")
    contract["tracks"]["primary"]["metric"]["exactness"] = "approximate"
    assert any("must be exact or stochastic" in p for p in problems(contract, study_dir))


def test_an_external_incumbent_carries_its_citation_and_date(study_dir: Path) -> None:
    contract = base()
    metric = contract["tracks"]["primary"]["metric"]
    metric["incumbent_external"] = {"value": 0.94}
    found = problems(contract, study_dir)
    assert any("incumbent_external.source is required" in p for p in found)
    assert any("incumbent_external.verified_on is required" in p for p in found)

    metric["incumbent_external"] = {
        "value": 0.94,
        "source": "Smith et al. 2024, Table 3",
        "verified_on": "2026-08-01",
    }
    assert problems(contract, study_dir) == []


def test_optimize_requires_a_verifier_that_is_not_the_searcher(study_dir: Path) -> None:
    study = study_dir
    (study / "search.py").write_text("", encoding="utf-8")
    (study / "verify.py").write_text("", encoding="utf-8")
    contract = base()
    contract["kind"] = "optimize"
    contract["entrypoint"] = {
        "command": ["uv", "run", "--locked", "python", "-u", "search.py"],
        "mutable": ["search.py"],
    }
    assert any("requires a declared verifier" in p for p in problems(contract, study))

    verifier = {
        "command": ["uv", "run", "--locked", "python", "-u", "verify.py"],
        "tolerance": 0.0,
        "artifact_key": "solution",
    }
    contract["tracks"]["primary"]["verifier"] = verifier
    assert problems(contract, study) == []

    # The one rule that makes a declared verifier mean anything.
    contract["entrypoint"]["mutable"] = ["search.py", "verify.py"]
    assert any(
        "the checker is never the searcher" in p for p in problems(contract, study)
    )

    contract["entrypoint"]["mutable"] = ["search.py"]
    verifier["command"] = ["uv", "run", "python", "-u", "absent.py"]
    assert any("verifier script does not exist: absent.py" in p for p in problems(contract, study))

    verifier["command"] = ["uv", "run", "python", "-u", "verify.py"]
    verifier["tolerance"] = -1
    assert any("verifier.tolerance must be finite and >= 0" in p for p in problems(contract, study))


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------


def test_a_prediction_needs_an_id_a_statement_and_exactly_one_decider(study_dir: Path) -> None:
    contract = base()
    contract["predictions"] = [
        {"id": "P1", "statement": "candidate beats baseline", "rule": {"key": "primary_metric", "op": ">=", "value": 0.65}},
        {"id": "P2", "statement": "the referee agrees", "manual": True},
    ]
    assert problems(contract, study_dir) == []

    contract["predictions"].append({"id": "P1", "statement": "again", "manual": True})
    assert "prediction P1: duplicate prediction id" in problems(contract, study_dir)

    contract["predictions"] = [{"id": "3", "statement": "x", "manual": True}]
    assert any("id is required and must match P<number>" in p for p in problems(contract, study_dir))

    contract["predictions"] = [{"id": "P1", "statement": "x"}]
    assert any("exactly one of rule or manual" in p for p in problems(contract, study_dir))

    contract["predictions"] = [
        {"id": "P1", "statement": "x", "manual": True, "rule": {"key": "a", "op": "gt", "value": 1}}
    ]
    assert any("give a rule OR manual: true" in p for p in problems(contract, study_dir))

    contract["predictions"] = [{"id": "P1", "statement": "x", "manual": True, "track": "ghost"}]
    assert any("is not a declared track" in p for p in problems(contract, study_dir))


def test_the_legacy_alias_and_the_register_are_never_both_present(study_dir: Path) -> None:
    contract = base()
    contract["predictions_to_falsify"] = [{"lever": "swap rate", "predicted_delta": "+0.001"}]
    assert problems(contract, study_dir) == []  # the readable alias alone is fine

    contract["predictions"] = [{"id": "P1", "statement": "x", "manual": True}]
    assert any("never both" in p for p in problems(contract, study_dir))


# ---------------------------------------------------------------------------
# The rule grammar (evaluation is the predictions ledger's job; shape is ours)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule",
    [
        {"key": "primary_metric", "op": ">=", "value": 0.65},
        {"key": "primary_metric", "operator": "gt", "value": 0.65},
        {"key": "ci_low", "op": "gt", "value": 70},
        {"key": "slope", "op": "eq", "value": 465, "tol": 10},
        {"key": "slope", "op": "within", "target": 465, "tol": 10},
        {"key": "slope", "op": "within", "value": {"target": 465, "tol": 10}},
        {"key": "delta", "op": "abs_lt", "value": 0.001},
        {"key": "slope", "op": "between", "value": [400, 500]},
        {"key": "slope", "op": "between", "low": 400, "high": 500},
        {"all_of": [{"key": "a", "op": "gt", "value": 1}, {"key": "b", "op": "lt", "value": 2}]},
        {"any_of": [{"not": {"key": "a", "op": "gt", "value": 1}}]},
    ],
)
def test_every_declared_operator_shape_is_accepted(rule: dict) -> None:
    assert validate_rule(rule) == []


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ({"key": "a", "op": "approximately", "value": 1}, "unknown op"),
        ({"key": "a", "op": "gt"}, "requires a finite numeric value"),
        ({"op": "gt", "value": 1}, "key is required"),
        ({"key": "a", "op": "eq", "value": 1}, "requires an explicit tol"),
        ({"key": "a", "op": "gt", "value": 1, "tol": 1}, "tol applies to eq and within only"),
        ({"key": "a", "op": "between", "value": [2, 1]}, "requires low <= high"),
        ({"key": "a", "op": "within", "target": 1}, "requires a finite tol"),
        ({"key": "a", "op": "gt", "value": float("inf")}, "requires a finite numeric value"),
        ({"all_of": []}, "requires a non-empty list"),
        ({"all_of": [{"key": "a", "op": "gt", "value": 1}], "any_of": []}, "exactly one of"),
        ({"key": "a", "op": "gt", "value": 1, "shell": "rm -rf /"}, "unknown keys"),
        ("primary_metric > 0.5", "must be a mapping"),
    ],
)
def test_the_grammar_refuses_what_it_cannot_decide(rule, expected: str) -> None:
    found = validate_rule(rule)
    assert found and any(expected in p for p in found), found


def test_rule_nesting_is_bounded() -> None:
    leaf = {"key": "a", "op": "gt", "value": 1}
    assert validate_rule({"all_of": [{"any_of": [leaf]}]}) == []
    too_deep = {"all_of": [{"any_of": [{"not": leaf}]}]}
    assert any("exceeds depth 3" in p for p in validate_rule(too_deep))


def test_no_contract_text_is_ever_executed() -> None:
    """The operator set is closed data; nothing on this path compiles a string."""
    forbidden = re.compile(r"(?<![.\w])(eval|exec|compile)\s*\(")
    for name in ("decision.py", "contract.py"):
        source = (Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8")
        assert not forbidden.findall(source), f"{name} calls a builtin evaluator"


# ---------------------------------------------------------------------------
# stop, materiality, confirmation, sources, task family
# ---------------------------------------------------------------------------


def test_stop_rule_shape(study_dir: Path) -> None:
    contract = base()
    contract["stop"] = {"max_consecutive_discards": 5, "scope": "track"}
    assert problems(contract, study_dir) == []
    contract["stop"] = {"max_consecutive_discards": 0}
    assert any("must be a positive integer" in p for p in problems(contract, study_dir))
    contract["stop"] = {"max_consecutive_discards": 5, "scope": "vibes"}
    assert any("stop.scope must be" in p for p in problems(contract, study_dir))


def test_materiality_is_priced_or_absent(study_dir: Path) -> None:
    contract = base()
    contract["materiality"] = {
        "currency": "EUR",
        "unit": "per policy-year",
        "threshold": 250000.0,
        "priced_by": "the pricing team",
        "priced_on": "2026-08-01",
        "basis": "portfolio-level loss-ratio impact at the 2025 exposure mix, net of reinsurance",
        "applies_to": "the 2027 rate filing",
    }
    assert problems(contract, study_dir) == []

    contract["materiality"]["basis"] = "it felt big"
    assert any("at least 40 characters" in p for p in problems(contract, study_dir))

    contract["materiality"].pop("priced_by")
    assert "materiality.priced_by is required" in problems(contract, study_dir)


def test_confirmation_require_is_closed_and_defaults_by_kind(study_dir: Path) -> None:
    assert set(CONFIRMATION_DEFAULTS) == set(KNOWN_KINDS)
    assert CONFIRMATION_DEFAULTS["optimize"] == ("verify",)
    assert CONFIRMATION_DEFAULTS["discover"] == ()

    contract = base()
    assert confirmation_require(contract) == ("sealed",)
    contract["kind"] = "optimize"
    assert confirmation_require(contract) == ("verify",)

    contract["confirmation"] = {"require": ["sealed", "replicate"]}
    assert confirmation_require(contract) == ("sealed", "replicate")

    contract["confirmation"] = {"require": ["vibes"]}
    assert any("confirmation.require may only contain" in p for p in problems(contract, study_dir))


@pytest.mark.parametrize(
    "tag",
    [
        "csv:data/prepared/x.csv",
        "parquet:data/prepared/x.parquet",
        "synthetic:make_data.py",
        "bundled:hurricane-landfalls",
        "hub:fremtpl2",
        "sklearn:load_iris",
    ],
)
def test_offline_source_tags_need_no_pin(tag: str, study_dir: Path) -> None:
    assert SOURCE_TAG_RE.match(tag)
    contract = base()
    contract["data"]["source"] = tag
    assert problems(contract, study_dir) == []


@pytest.mark.parametrize("tag", ["openml:41214", "url:https://example.invalid/x.csv"])
def test_bytes_that_can_change_are_pinned(tag: str, study_dir: Path) -> None:
    contract = base()
    contract["data"]["source"] = tag
    assert any("data.sha256" in p and "mandatory" in p for p in problems(contract, study_dir))

    contract["data"]["sha256"] = "a" * 64
    assert problems(contract, study_dir) == []

    contract["data"]["sha256"] = "not-a-digest"
    assert any("64 lowercase hex" in p or "mandatory" in p for p in problems(contract, study_dir))


def test_an_unknown_source_scheme_is_refused(study_dir: Path) -> None:
    contract = base()
    contract["data"]["source"] = "kaggle:some/slug"
    assert any("must be a source tag" in p for p in problems(contract, study_dir))


def test_load_contract_takes_a_string_like_every_neighbouring_loader(study_dir: Path) -> None:
    """An entrypoint reading its own contract writes `load_contract(".")`; that
    used to raise a raw TypeError out of a path join."""
    import os

    from kleinlib.contract import WorkflowError, load_contract

    (study_dir / "study.yaml").write_text("schema_version: 3\nstudy_id: s\n", encoding="utf-8")
    cwd = os.getcwd()
    os.chdir(study_dir)
    try:
        assert load_contract(".")["study_id"] == "s"
        assert load_contract(str(study_dir))["study_id"] == "s"
        assert load_contract(study_dir)["study_id"] == "s"
    finally:
        os.chdir(cwd)
    with pytest.raises(WorkflowError, match="could not read study.yaml"):
        load_contract(str(study_dir / "nowhere"))


def test_the_source_scheme_vocabulary_has_one_owner(study_dir: Path) -> None:
    """`data.source` validation reads `kleinlib.sources.parse_source`; the
    contract regex is only the cheap pre-check, so the accepted scheme set is
    exactly `SourceKind` and cannot drift from it."""
    from kleinlib.contract import PINNED_SOURCE_SCHEMES
    from kleinlib.sources import SourceKind

    for kind in SourceKind:
        contract = base()
        contract["data"]["source"] = f"{kind.value}:whatever"
        if kind.value in PINNED_SOURCE_SCHEMES:
            contract["data"]["sha256"] = "a" * 64
        assert problems(contract, study_dir) == [], kind


def test_scalar_is_the_schema_3_spelling_of_the_simulation_family(study_dir: Path) -> None:
    contract = base()
    contract["task_type"] = "scalar"
    contract["tracks"]["primary"]["metric"]["name"] = "abs_premium_error_pct"
    contract["data"]["split"] = {"kind": "none"}
    assert problems(contract, study_dir) == []
    assert task_family(contract) == "scalar"

    contract["task_type"] = "simulation"
    assert problems(contract, study_dir) == []
    assert task_family(contract) == "scalar"

    # ... and it stays a schema-3 spelling: schema 2 knows the three it shipped.
    contract["schema_version"] = 2
    contract["task_type"] = "scalar"
    assert "task_type must be classification, regression, or simulation" in problems(
        contract, study_dir
    )


def test_schema_version_reads_the_contract() -> None:
    assert schema_version({"schema_version": 3}) == 3
    assert schema_version({}) == 1
