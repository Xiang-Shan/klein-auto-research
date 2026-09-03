"""E3 — ``klein new`` scaffolds a typed schema-3 study.

The scaffold's job is to hand CONSULT a contract that is already the right
SHAPE: typed on all three axes, with the entrypoint named by kind, one block per
declared track, and a final phase with room for a sealed run per track.  What it
must NOT do is fill in what only a human can decide — those stay ``{{...}}``
placeholders, and the consult gate refuses a contract that still carries one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from kleinlib import cli
from kleinlib.contract import (
    ENTRYPOINT_BY_KIND,
    entrypoint_spec,
    mutable_surface,
    normalize_tracks,
    validate_contract,
)
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import verify_event_chain

COMMON = dict(
    goal="g",
    domain="d",
    target="y",
    family="linear",
    metric_name="val_auc",
    metric_goal="higher",
    data_source="csv:x.csv",
)


def build(root: Path, slug: str = "03-smoke", **kwargs) -> Path:
    return scaffold_study(root, slug, **{**COMMON, **kwargs})


def contract_of(study: Path) -> dict:
    return yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))


def unresolved(study: Path) -> list[str]:
    return [p for p in validate_contract(contract_of(study), study) if "placeholder" in p]


def structural(study: Path) -> list[str]:
    """Contract problems other than the placeholders CONSULT is meant to fill."""
    return [p for p in validate_contract(contract_of(study), study) if "placeholder" not in p]


def test_scaffold_is_v3_by_default_from_the_cli(tmp_path: Path, capsys) -> None:
    rc = cli.main(
        [
            "new",
            "03-cli-v3",
            "--root", str(tmp_path),
            "--goal", "test the CLI",
            "--domain", "test",
            "--target", "y",
            "--family", "linear",
            "--metric", "val_auc",
            "--goal-direction", "higher",
            "--data", "csv:fixture.csv",
            "--kind", "predict",
            "--modality", "tabular",
            "--profile", "generic",
            "--audience", "researchers",
        ]
    )
    assert rc == 0
    capsys.readouterr()
    study = tmp_path / "03-cli-v3"
    contract = contract_of(study)
    assert contract["schema_version"] == 3
    assert json.loads((study / "study_state.json").read_text())["schema_version"] == 3
    assert structural(study) == []
    assert verify_event_chain(study) == []


def test_schema_2_mode_still_scaffolds_the_frozen_shape(tmp_path: Path, capsys) -> None:
    """The old contract stays reachable, byte-for-byte, forever."""
    rc = cli.main(
        [
            "new", "03-cli-v2",
            "--root", str(tmp_path),
            "--goal", "test the CLI",
            "--domain", "test",
            "--target", "y",
            "--family", "linear",
            "--metric", "val_auc",
            "--goal-direction", "higher",
            "--data", "csv:fixture.csv",
            "--schema-version", "2",
        ]
    )
    assert rc == 0
    capsys.readouterr()
    study = tmp_path / "03-cli-v2"
    contract = contract_of(study)
    assert contract["schema_version"] == 2
    assert "kind" not in contract and "entrypoint" not in contract
    assert "modality" not in contract["data"]
    assert (study / "train.py").is_file()
    assert json.loads((study / "study_state.json").read_text())["schema_version"] == 2


@pytest.mark.parametrize("kind", sorted(ENTRYPOINT_BY_KIND))
def test_the_entrypoint_is_named_by_kind_and_declared(tmp_path: Path, kind: str) -> None:
    study = build(
        tmp_path / kind,
        schema_version=3,
        kind=kind,
        modality="tabular",
        profile="generic",
        audience="researchers",
    )
    expected = ENTRYPOINT_BY_KIND[kind]
    assert (study / expected).is_file()
    contract = contract_of(study)
    assert entrypoint_spec(contract)["command"][-1] == expected
    assert mutable_surface(contract) == (expected,)
    # Every scaffolded entrypoint refuses to run outside `klein run-one`, and
    # says how to smoke it — the one sanctioned off-loop check.
    source = (study / expected).read_text(encoding="utf-8")
    assert "KLEIN_SMOKE=1" in source
    assert "must be invoked through `klein run-one`" in source
    assert structural(study) == []


def test_optimize_scaffolds_a_real_verifier_outside_the_mutable_surface(tmp_path: Path) -> None:
    """An `optimize` contract cannot validate without one, so it is not a hint."""
    study = build(
        tmp_path,
        schema_version=3,
        kind="optimize",
        modality="none",
        profile="math",
        audience="mathematicians",
        task_type="scalar",
        metric_name="objective",
        metric_goal="higher",
        split_kind="none",
    )
    contract = contract_of(study)
    verifier = normalize_tracks(contract)["primary"]["verifier"]
    assert verifier["command"][-1] == "verify.py"
    assert verifier["artifact_key"] == "solution"
    assert (study / "verify.py").is_file()
    assert "verify.py" not in mutable_surface(contract)
    assert "KLEIN_ARTIFACT" in (study / "verify.py").read_text(encoding="utf-8")
    assert structural(study) == []


def test_repeatable_tracks_carry_their_modes_and_size_the_final_phase(tmp_path: Path) -> None:
    study = build(
        tmp_path,
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="researchers",
        tracks=["primary", "control:registered", "ablation"],
    )
    contract = contract_of(study)
    tracks = normalize_tracks(contract)
    assert [(n, s["mode"]) for n, s in tracks.items()] == [
        ("primary", "frontier"),
        ("control", "registered"),
        ("ablation", "frontier"),
    ]
    # One sealed final-test evaluation per track has to fit in the last phase.
    assert contract["phases"][-1]["max_experiments"] == 3
    assert structural(study) == []


def test_a_registered_kind_defaults_every_track_to_registered_mode(tmp_path: Path) -> None:
    study = build(
        tmp_path,
        schema_version=3,
        kind="estimate",
        modality="tabular",
        profile="generic",
        audience="researchers",
        tracks=["primary", "sensitivity"],
    )
    modes = {n: s["mode"] for n, s in normalize_tracks(contract_of(study)).items()}
    assert modes == {"primary": "registered", "sensitivity": "registered"}


def test_split_seed_is_written_into_the_contract(tmp_path: Path) -> None:
    study = build(
        tmp_path,
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="researchers",
        split_seed=20260912,
    )
    assert contract_of(study)["data"]["split"]["seed"] == 20260912


def test_profile_doc_replaces_the_profile_name(tmp_path: Path) -> None:
    root = tmp_path / "studies"
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "climate.md").write_text("# Climate\n", encoding="utf-8")
    study = build(
        root,
        schema_version=3,
        kind="predict",
        modality="timeseries",
        profile_doc="profiles/climate.md",
        audience="climate scientists",
        split_kind="time",
        time_column="event_time",
    )
    contract = contract_of(study)
    assert contract["profile_doc"] == "profiles/climate.md"
    assert "profile" not in contract
    assert structural(study) == []


def test_what_consult_must_still_decide_stays_a_placeholder(tmp_path: Path) -> None:
    study = build(tmp_path, schema_version=3)
    text = (study / "study.yaml").read_text(encoding="utf-8")
    for placeholder in ("{{KIND}}", "{{MODALITY}}", "{{PROFILE}}", "{{AUDIENCE}}"):
        assert placeholder in text
    # ... and the contract does not validate until they are filled in.
    assert unresolved(study)


def test_the_scaffolded_notebook_states_its_own_schema_version(tmp_path: Path) -> None:
    """A schema-3 study's lab notebook must not open by calling itself schema 2.

    `program.md` is the study's own record of what it is; the scaffold used to
    hard-code "schema-v2" into every study's first Decisions line, so every
    schema-3 study was born with a false sentence in the file SYNTHESIZE later
    mines.  Schema 2's wording is unchanged, byte for byte.
    """
    for schema_version in (2, 3):
        study = build(
            tmp_path / f"v{schema_version}",
            slug=f"0{schema_version}-notebook",
            schema_version=schema_version,
            **({"kind": "predict", "modality": "tabular", "profile": "generic"}
               if schema_version == 3 else {}),
        )
        text = (study / "program.md").read_text(encoding="utf-8")
        assert f"schema-v{schema_version} study scaffolded" in text
        assert f"schema-v{3 if schema_version == 2 else 2} study" not in text


def test_schema_3_options_are_refused_on_a_schema_2_scaffold(tmp_path: Path) -> None:
    for kwargs, expected in (
        ({"kind": "predict"}, "schema-3 options"),
        ({"modality": "tabular"}, "schema-3 options"),
        ({"profile": "math"}, "schema-3 options"),
        ({"audience": "x"}, "schema-3 options"),
        ({"split_seed": 7}, "--split-seed is a schema-3 option"),
        ({"tracks": ["a", "b"]}, "multi-track scaffolding"),
        ({"tracks": ["a:registered"]}, "multi-track scaffolding"),
    ):
        with pytest.raises(ValueError, match=expected):
            build(tmp_path / str(sorted(kwargs)), schema_version=2, **kwargs)


def test_the_scaffold_rejects_unknown_axis_values(tmp_path: Path) -> None:
    for kwargs, expected in (
        ({"kind": "guess"}, "kind must be one of"),
        ({"modality": "audio"}, "modality must be one of"),
        ({"profile": "climate"}, "profile must be one of"),
        ({"profile": "math", "profile_doc": "p.md"}, "not both"),
        ({"profile_doc": "profiles/climate.txt"}, "must point at a .md file"),
        ({"tracks": ["a:vibes"]}, "track mode must be"),
        ({"tracks": ["a", "a"]}, "duplicate track"),
        ({"tracks": ["not a track"]}, "safe identifier"),
    ):
        with pytest.raises(ValueError, match=expected):
            build(tmp_path / str(sorted(kwargs)), schema_version=3, **kwargs)
    with pytest.raises(ValueError, match="schema_version must be 2 or 3"):
        build(tmp_path / "bad-version", schema_version=4)
