"""``references.yaml`` — the loader and the shape checker (no network, ever)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kleinlib.errors import WorkflowError
from kleinlib.references import (
    is_verified,
    load_references,
    reference_problems,
    references_path,
)

WRAPPED = """
references:
  fisher1936:
    title: "The use of multiple measurements in taxonomic problems"
    authors: "Fisher, R. A."
    year: 1936
    doi: "10.1111/j.1469-1809.1936.tb02137.x"
    verified: true
  preprint2026:
    title: "A preprint nobody checked"
    arxiv: "2601.00001"
    verified: false
"""

BARE = """
fisher1936:
  title: "The use of multiple measurements in taxonomic problems"
  url: "https://example.invalid/fisher"
  verified: true
"""


def test_missing_file_is_an_empty_registry(tmp_path: Path) -> None:
    assert load_references(tmp_path) == {}


def test_wrapped_and_bare_forms_both_load(tmp_path: Path) -> None:
    references_path(tmp_path).write_text(WRAPPED, encoding="utf-8")
    wrapped = load_references(tmp_path)
    assert set(wrapped) == {"fisher1936", "preprint2026"}
    assert is_verified(wrapped["fisher1936"])
    assert not is_verified(wrapped["preprint2026"])

    references_path(tmp_path).write_text(BARE, encoding="utf-8")
    bare = load_references(tmp_path)
    assert set(bare) == {"fisher1936"}
    assert reference_problems(bare) == []


def test_shape_problems_are_returned_never_raised(tmp_path: Path) -> None:
    references_path(tmp_path).write_text(
        "references:\n"
        "  a_string_entry: not-a-mapping\n"
        "  no_locator:\n"
        "    title: 'Something'\n"
        "    verified: true\n"
        "  bad_flag:\n"
        "    title: 'Something else'\n"
        "    doi: '10.0/x'\n"
        "    verified: 'yes'\n"
        "  bare_bones:\n"
        "    doi: '10.0/y'\n",
        encoding="utf-8",
    )
    problems = reference_problems(load_references(tmp_path))
    joined = " | ".join(problems)
    assert "a_string_entry: entry must be a mapping" in joined
    assert "no_locator: needs at least one locator" in joined
    assert "bad_flag: 'verified' must be a boolean" in joined
    assert "bare_bones: missing required field 'title'" in joined
    assert "bare_bones: missing required field 'verified'" in joined


def test_malformed_yaml_and_non_mapping_are_workflow_errors(tmp_path: Path) -> None:
    references_path(tmp_path).write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="top-level mapping"):
        load_references(tmp_path)

    references_path(tmp_path).write_text("references: [1, 2]\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="mapping of key -> entry"):
        load_references(tmp_path)

    references_path(tmp_path).write_text("a: [\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="could not read"):
        load_references(tmp_path)


def test_is_verified_is_true_only_for_the_literal_true(tmp_path: Path) -> None:
    assert is_verified({"verified": True})
    assert not is_verified({"verified": "true"})
    assert not is_verified({"verified": 1})
    assert not is_verified({})
    assert not is_verified("not a mapping")
