"""The materiality / profile vocabulary scan on `findings.md`.

`knowledge/research-discipline.md` lesson 10: detectable is not actionable.
A gain of 0.29x the floor at n = 8 is detectable and not actionable (study 08);
study 09 banned the conflation of measurement resolution with business
materiality outright. Schema 3 makes that a FAILURE: the word is priced or it
is not used. The profile's own banned list is a WARNING — vocabulary is the
profile's business and the referee's, and the engine checks the same things in
every profile (`references/profiles/README.md`, knob 7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kleinlib.checks import (
    MATERIALITY_WORDS,
    profile_banned_words,
    verify_study,
    vocabulary_problems,
)
from kleinlib.state import record_gate

PROFILES = Path(".claude/skills/klein/references/profiles")


MATERIALITY_BLOCK = {
    "currency": "EUR",
    "unit": "annual gross written premium",
    "threshold": 250000.0,
    "priced_by": "the pricing actuary",
    "priced_on": "2026-09-01",
    "basis": (
        "the 2025 book at current rates, holding retention flat and applying the "
        "measured lift to the top two deciles only"
    ),
    "applies_to": "the motor own-damage portfolio",
}


# --------------------------------------------------------------------------
# reading a profile's banned list
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "profile,expected",
    [
        ("generic", ["blind", "proved", "significant", "material", "actionable"]),
        ("insurance", ["material", "actionable", "lift", "significant"]),
        ("math", ["proved", "proof", "optimal", "impossible", "cannot exist"]),
        ("ml-research", ["SOTA", "state of the art", "beats", "converged"]),
    ],
)
def test_every_shipped_profile_parses_to_its_banned_list(profile, expected) -> None:
    text = (PROFILES / f"{profile}.md").read_text(encoding="utf-8")
    assert profile_banned_words(text) == expected


def test_the_suggested_replacement_is_not_read_as_banned() -> None:
    """generic.md bans "blind" and SUGGESTS "locked before" in the same sentence."""
    text = (PROFILES / "generic.md").read_text(encoding="utf-8")
    assert "locked before" not in profile_banned_words(text)


def test_words_that_must_merely_be_qualified_are_not_banned() -> None:
    """ml-research's "faster"/"generalizes" live after "Must be qualified"."""
    text = (PROFILES / "ml-research.md").read_text(encoding="utf-8")
    banned = profile_banned_words(text)
    assert "faster" not in banned and "generalizes" not in banned


def test_a_document_without_a_vocabulary_section_bans_nothing() -> None:
    assert profile_banned_words("# Profile\n\n## 1. Audience\nAnyone.\n") == []
    assert profile_banned_words("## 7. Vocabulary\nHonest verbs: measured.\n") == []


# --------------------------------------------------------------------------
# the scan
# --------------------------------------------------------------------------


def _write_findings(study: Path, text: str) -> None:
    (study / "findings.md").write_text(text, encoding="utf-8")


def _set(study: Path, *, regate: bool = False, **keys) -> dict:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    contract.update(keys)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    if regate:
        # study.yaml is a consult-gate artifact: re-record so its hash matches.
        record_gate(study, "consult", acknowledged_by="tester")
    return contract


def _install_profiles(study: Path) -> Path:
    """Put Klein's real profile documents where a checkout keeps them.

    The fixture's temp repo is a bare git repo with no `.claude/` tree, which
    is exactly the wheel-install case the scan degrades on — so a test that
    wants the scan to RUN has to supply the documents.
    """
    root = study.parent.parent
    target = root / PROFILES
    target.mkdir(parents=True, exist_ok=True)
    for source in Path(PROFILES).glob("*.md"):
        (target / source.name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return target


def test_no_findings_file_means_nothing_to_scan(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert vocabulary_problems(study, contract) == {}


def test_unpriced_materiality_is_a_failure_on_schema_three(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    _write_findings(
        study,
        "# Findings\n\nThe swap-rate change is material for the book.\n"
        "It is actionable today.\n",
    )
    problems = vocabulary_problems(study, contract)
    assert len(problems["materiality"]) == 2
    assert "line 3:" in problems["materiality"][0]
    assert "material for the book" in problems["materiality"][0]


@pytest.mark.parametrize("word", MATERIALITY_WORDS)
def test_every_materiality_word_is_caught(ready_study_v3, word) -> None:
    _repo, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    _write_findings(study, f"# Findings\n\nThe gain is {word} on the sealed set.\n")
    assert vocabulary_problems(study, contract)["materiality"]


def test_a_priced_block_licenses_the_word(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    contract = _set(study, materiality=MATERIALITY_BLOCK)
    _write_findings(study, "# Findings\n\nThe gain is material for the book.\n")
    assert "materiality" not in vocabulary_problems(study, contract)


def test_schema_two_findings_are_never_scanned_for_materiality(ready_study) -> None:
    """03 and 05-09 were written before the rule and must not retro-fail."""
    _repo, study = ready_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    _write_findings(study, "# Findings\n\nThe lift is material and actionable.\n")
    assert "materiality" not in vocabulary_problems(study, contract)


def test_related_words_are_not_false_positives(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    _write_findings(
        study,
        "# Findings\n\nThe materiality of the gap is unpriced, and the difference\n"
        "is immaterial in the materials we reviewed.\n",
    )
    assert "materiality" not in vocabulary_problems(study, contract)


def test_the_profile_banned_words_are_a_warning_not_a_failure(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    _install_profiles(study)
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["profile"] == "generic"
    _write_findings(
        study,
        "# Findings\n\nThe result is significant and the selection was blind.\n",
    )
    problems = vocabulary_problems(study, contract)
    assert problems["profile"]
    assert "significant" in problems["profile"][0]

    checks = {c.name: c for c in verify_study(study)}
    assert checks["profile vocabulary"].ok
    assert checks["profile vocabulary"].message.startswith("[WARN]")


def test_the_profile_scan_follows_the_declared_profile(ready_study_v3) -> None:
    """`converged` is banned for ml-research and unremarkable for generic."""
    _repo, study = ready_study_v3
    _install_profiles(study)
    _write_findings(study, "# Findings\n\nThe optimizer converged by step 400.\n")

    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert "profile" not in vocabulary_problems(study, contract)

    contract = _set(study, profile="ml-research")
    problems = vocabulary_problems(study, contract)
    assert "converged" in problems["profile"][0]


def test_profile_doc_is_supported_and_wins(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    doc = study / "house_profile.md"
    doc.write_text(
        "# Profile: house\n\n## 7. Vocabulary\nBanned: \"breakthrough\" without a "
        "replication, \"obviously\" at all. Must be qualified: \"large\".\n\n"
        "## 8. CONSULT hints\nnone\n",
        encoding="utf-8",
    )
    contract = _set(study, profile_doc="house_profile.md")
    _write_findings(study, "# Findings\n\nObviously a breakthrough.\n")
    problems = vocabulary_problems(study, contract)
    assert "profile" in problems
    # The house list, not generic's: "significant" is not on it.
    assert "breakthrough" in problems["profile"][0].lower()


def test_an_unresolvable_profile_skips_the_scan_rather_than_failing(
    ready_study_v3,
) -> None:
    """A wheel install has no `.claude/` tree; that is not a study's fault."""
    _repo, study = ready_study_v3
    contract = _set(study, profile_doc="docs/profiles/nowhere.md")
    _write_findings(study, "# Findings\n\nThe result is significant and blind.\n")
    assert "profile" not in vocabulary_problems(study, contract)


def test_verify_fails_a_schema_three_study_that_claims_unpriced_materiality(
    ready_study_v3,
) -> None:
    _repo, study = ready_study_v3
    _write_findings(study, "# Findings\n\nA material improvement.\n")
    failures = [c for c in verify_study(study) if not c.ok]
    assert [c.name for c in failures] == ["materiality vocabulary"]
    assert "no priced consequence on the record" in failures[0].message
    assert "Measurement resolution is never business value" in failures[0].message


def test_verify_passes_once_the_consequence_is_priced(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    _set(study, regate=True, materiality=MATERIALITY_BLOCK)
    _write_findings(study, "# Findings\n\nA material improvement.\n")
    assert not [c for c in verify_study(study) if not c.ok]


def test_a_clean_findings_page_gains_no_check_lines(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    _write_findings(
        study, "# Findings\n\nThe candidate cleared the registered bar by 1.4 floors.\n"
    )
    names = {c.name for c in verify_study(study)}
    assert "materiality vocabulary" not in names
    assert "profile vocabulary" not in names


def test_only_the_first_few_offending_lines_are_quoted(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    _write_findings(study, "# Findings\n" + "material.\n" * 20)
    assert len(vocabulary_problems(study, contract)["materiality"]) == 3
