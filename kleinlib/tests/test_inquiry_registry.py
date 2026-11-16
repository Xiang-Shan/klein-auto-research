"""The inquiry model as data: kinds are closed, modalities and profiles are open.

``kleinlib/inquiry.py`` is the ONE place the three axes live; ``contract`` and
``schema`` hold views of it, and no other engine module branches on a literal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kleinlib import contract, inquiry, schema
from kleinlib.inquiry import (
    KINDS,
    KindSpec,
    ModalitySpec,
    ProfileSpec,
    register_modality,
    register_profile,
    required_card_sections,
)

PACKAGE = Path(__file__).resolve().parents[1]

EXPECTED_KINDS = {
    #            track mode    entrypoint     confirmation  verifier
    "predict": ("frontier", "train.py", ("sealed",), False),
    "estimate": ("registered", "analyze.py", ("sealed",), False),
    "test": ("registered", "analyze.py", ("sealed",), False),
    "simulate": ("registered", "simulate.py", ("sealed",), False),
    "replicate": ("registered", "analyze.py", ("sealed",), False),
    "discover": ("registered", "analyze.py", (), False),
    "optimize": ("frontier", "search.py", ("verify",), True),
}


@pytest.fixture
def scratch_registry():
    """Remove whatever a test registers, so no other test sees it."""
    modalities, profiles = dict(inquiry._MODALITIES), dict(inquiry._PROFILES)
    yield
    inquiry._MODALITIES.clear()
    inquiry._MODALITIES.update(modalities)
    inquiry._PROFILES.clear()
    inquiry._PROFILES.update(profiles)


# --------------------------------------------------------------------------
# kind — closed, seven
# --------------------------------------------------------------------------


def test_the_seven_kinds_in_documented_order() -> None:
    assert inquiry.kind_names() == tuple(EXPECTED_KINDS)
    assert len(KINDS) == 7


@pytest.mark.parametrize("name", list(EXPECTED_KINDS))
def test_each_kind_fixes_its_mode_entrypoint_confirmation_and_verifier(name: str) -> None:
    mode, entrypoint, confirmation, verifier = EXPECTED_KINDS[name]
    spec = inquiry.kind_spec(name)
    assert isinstance(spec, KindSpec) and spec.name == name
    assert (spec.track_mode, spec.entrypoint, spec.confirmation, spec.requires_verifier) == (
        mode,
        entrypoint,
        confirmation,
        verifier,
    )


def test_only_optimize_requires_a_verifier() -> None:
    assert [n for n, spec in KINDS.items() if spec.requires_verifier] == ["optimize"]


def test_an_absent_or_unknown_kind_reads_as_the_default() -> None:
    assert inquiry.DEFAULT_KIND == "predict"
    assert inquiry.kind_spec(None) is KINDS["predict"]
    assert inquiry.kind_spec("guess") is KINDS["predict"]


def test_the_contract_tables_are_views_of_the_kind_registry() -> None:
    assert contract.KNOWN_KINDS == tuple(KINDS)
    assert contract.CONFIRMATION_DEFAULTS == {n: s.confirmation for n, s in KINDS.items()}
    assert contract.ENTRYPOINT_BY_KIND == {n: s.entrypoint for n, s in KINDS.items()}
    assert contract.CONFIRMATION_DEFAULTS["discover"] == ()  # a discovery confirms nothing


# --------------------------------------------------------------------------
# modality and profile — open; schema holds views of the built-ins
# --------------------------------------------------------------------------


def test_the_builtin_names_are_what_ships_before_any_plugin() -> None:
    assert schema.KNOWN_MODALITIES == (
        "tabular", "timeseries", "image", "sequence", "graph", "text", "simulation", "none",
    )
    assert schema.KNOWN_PROFILES == (
        "generic", "ml-research", "math", "insurance", "llm", "cv", "data-science",
    )
    assert set(schema.KNOWN_MODALITIES) <= set(inquiry.modality_names())
    assert set(schema.KNOWN_PROFILES) <= set(inquiry.profile_names())


def test_the_schema_section_tables_are_views_of_the_registry() -> None:
    for name in schema.KNOWN_MODALITIES:
        spec = inquiry.modality_spec(name)
        assert schema.MODALITY_CARD_SECTIONS[name] == spec.card_sections
        assert schema.POLICY_CARD_SECTIONS.get(name, ()) == spec.policy_sections
    # a table holds only the entries that have headings
    assert set(schema.POLICY_CARD_SECTIONS) == {"image", "sequence", "graph", "text"}
    assert schema.PROFILE_CARD_SECTIONS == {"llm": ("Contamination audit",)}
    for name in schema.KNOWN_PROFILES:
        assert schema.PROFILE_CARD_SECTIONS.get(name, ()) == inquiry.profile_spec(name).card_sections


def test_every_modality_card_carries_the_universal_headings() -> None:
    for name in schema.KNOWN_MODALITIES:
        sections = schema.MODALITY_CARD_SECTIONS[name]
        assert sections[:3] == ("Source & shape", "Ranked go / no-go issues", "Go / no-go"), name


@pytest.mark.parametrize(
    ("modality", "profile", "extra"),
    [
        ("tabular", "generic", ("Profile summary", "Clean-room leakage audit")),
        ("timeseries", "insurance", ("Time policy",)),
        ("simulation", "math", ("DGP card",)),
        ("none", "generic", ("Verifier card",)),
        ("image", "cv", ("Group policy", "Near-duplicate audit")),
        ("text", "llm", ("Group policy", "Near-duplicate audit", "Contamination audit")),
    ],
)
def test_required_card_sections_stack_modality_policy_and_profile(modality, profile, extra) -> None:
    sections = required_card_sections(modality, profile)
    assert sections[:3] == ("Source & shape", "Ranked go / no-go issues", "Go / no-go")
    for heading in extra:
        assert heading in sections, heading
    assert len(sections) == len(set(sections))


def test_text_under_llm_is_the_union_in_a_fixed_order() -> None:
    assert required_card_sections("text", "llm") == (
        "Source & shape", "Ranked go / no-go issues", "Go / no-go",
        "Profile summary", "Clean-room leakage audit", "Group policy",
        "Near-duplicate audit",
        "Contamination audit",
    )


def test_an_unknown_modality_or_profile_contributes_no_headings() -> None:
    assert inquiry.modality_spec("nope") is None and inquiry.profile_spec(None) is None
    assert required_card_sections("nope", "nope") == ()
    assert required_card_sections("none", "nope") == schema.MODALITY_CARD_SECTIONS["none"]


# --------------------------------------------------------------------------
# registering
# --------------------------------------------------------------------------


def test_registering_the_same_spec_twice_is_a_no_op(scratch_registry) -> None:
    modality = ModalitySpec("spectra", ("Source & shape",), summary="s")
    profile = ProfileSpec("climate", ("Station audit",), summary="p")
    for _ in range(2):
        register_modality(modality)
        register_profile(profile)
    assert inquiry.modality_names().count("spectra") == 1
    assert inquiry.profile_names().count("climate") == 1
    assert inquiry.modality_spec("spectra") == modality


def test_a_conflicting_spec_under_the_same_name_is_refused(scratch_registry) -> None:
    register_modality(ModalitySpec("spectra", ("A",)))
    with pytest.raises(ValueError, match="modality 'spectra' is already registered"):
        register_modality(ModalitySpec("spectra", ("B",)))
    register_profile(ProfileSpec("climate", ("A",)))
    with pytest.raises(ValueError, match="profile 'climate' is already registered"):
        register_profile(ProfileSpec("climate", ("B",)))
    with pytest.raises(ValueError):  # a builtin is not overridable either
        register_profile(ProfileSpec("generic", ("Extra",)))
    assert inquiry.modality_spec("spectra").card_sections == ("A",)  # the first spec stands


def test_a_registered_pair_feeds_required_card_sections(scratch_registry) -> None:
    register_modality(ModalitySpec("spectra", ("Source & shape", "Calibration"), ("Instrument audit",)))
    register_profile(ProfileSpec("climate", ("Station audit",)))
    assert required_card_sections("spectra", "climate") == (
        "Source & shape", "Calibration", "Instrument audit", "Station audit",
    )


# --------------------------------------------------------------------------
# no engine module branches on an axis literal outside inquiry.py
# --------------------------------------------------------------------------


def _engine_modules() -> list[Path]:
    skipped = {"tests", "recipes", "generation"}
    return sorted(
        path
        for path in PACKAGE.rglob("*.py")
        if path.name != "inquiry.py" and not skipped & set(path.relative_to(PACKAGE).parts)
    )


def _literals(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        return {v for elt in node.elts for v in _literals(elt)}
    return set()


def _branches_on(names: set[str], subject_word: str, modules: list[Path] | None = None) -> list[str]:
    hits: list[str] = []
    for path in modules if modules is not None else _engine_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not all(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in node.ops):
                continue
            literals = _literals(node.left).union(*(_literals(c) for c in node.comparators))
            if literals & names and subject_word in ast.unparse(node).replace(repr(subject_word), ""):
                hits.append(f"{path.name}:{node.lineno}: {ast.unparse(node)}")
    return hits


def test_the_scan_sees_the_modules_it_claims_to_guard() -> None:
    modules = {p.name for p in _engine_modules()}
    assert {"contract.py", "workflow.py", "scaffold.py", "checks.py"} <= modules
    assert "inquiry.py" not in modules


def test_no_engine_module_branches_on_a_kind_literal() -> None:
    assert _branches_on(set(KINDS), "kind") == []


def test_no_engine_module_branches_on_a_modality_or_profile_literal() -> None:
    # "none" is also a split kind and an evaluator's word, so only compare on lines
    # that name the axis itself.
    modalities = set(inquiry.BUILTIN_MODALITIES) - {"none"}
    assert _branches_on(modalities, "modality") == []
    assert _branches_on(set(inquiry.BUILTIN_PROFILES), "profile") == []


def test_the_scan_would_catch_a_branch_if_there_were_one(tmp_path) -> None:
    probe = tmp_path / "offender.py"
    probe.write_text('def f(kind):\n    return kind == "optimize" or kind in {"predict"}\n', encoding="utf-8")
    hits = _branches_on(set(KINDS), "kind", [probe])
    assert len(hits) == 2 and all("offender.py" in hit for hit in hits)
