"""The claims lock: lock schema 1 (the shipped 07/08/09 ledgers) and schema 2.

The FIRST tests here are the three real files.  They are read-only evidence of
finished studies: under the schema-1 rules of ``references/claims-protocol.md``
they must verify with zero failures forever, warnings and all, and no verb of
this engine may ever rewrite them.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from test_commit_state_writes import modified_paths

from kleinlib import claims as claims_module
from kleinlib import cli
from kleinlib.claims import (
    CLAIM_CLASSES,
    add_claim,
    add_number,
    canonical_lock_text,
    claims_checks,
    detect_lock_schema,
    file_erratum,
    init_lock,
    load_lock,
    lock_path,
    numbers_map,
    pin_artifact,
    verify_lock,
    write_lock,
)
from kleinlib.errors import WorkflowError
from kleinlib.events import read_events
from kleinlib.references import references_path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ("07-iris-90years", "08-iris-rematch", "09-iris-first-lesson")


def _failures(checks) -> list[str]:
    return [f"{c.name}: {c.message}" for c in checks if not c.ok]


def _check(checks, name):
    return next(c for c in checks if c.name == name)


# ---------------------------------------------------------------------------
# The three shipped locks — lock schema 1, verified unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", SHIPPED)
def test_shipped_lock_verifies_unchanged(slug: str) -> None:
    """07, 08 and 09 verify with 0 failed under lock-schema-1 rules."""
    study = REPO_ROOT / "studies" / slug
    before = lock_path(study).read_bytes()
    checks = verify_lock(study)
    assert len(checks) == 7, [c.name for c in checks]
    assert _failures(checks) == []
    assert lock_path(study).read_bytes() == before, "verify must never rewrite a lock"


def test_study09_lock_verifies_unchanged() -> None:
    """The named first test of the package, spelled out (E8, plan item)."""
    study = REPO_ROOT / "studies" / "09-iris-first-lesson"
    checks = verify_lock(study)
    assert _failures(checks) == []
    assert _check(checks, "claims artifacts").message.startswith("16 pinned artifacts")
    assert _check(checks, "claims append-only").ok
    assert _check(checks, "claims ancestry").message == "git_head is an ancestor of HEAD"


@pytest.mark.parametrize("slug", SHIPPED)
def test_shipped_locks_are_lock_schema_one(slug: str) -> None:
    lock = load_lock(REPO_ROOT / "studies" / slug)
    assert detect_lock_schema(lock) == 1
    assert "lock_schema" not in lock
    # The schema-1 quirks the protocol names, present in the real files.
    numbers = numbers_map(lock, 1)
    assert numbers, "the schema-1 'claims' map IS the numbers ledger"
    entries = [e for e in numbers.values() if isinstance(e, dict)]
    spellings = {"art" if "art" in e else "artifact" for e in entries if "art" in e or "artifact" in e}
    assert spellings <= {"art", "artifact"} and spellings
    for meta in lock["artifacts"].values():
        assert meta["path"].startswith("studies/"), "schema-1 paths are repo-relative"


def test_study07_carries_a_non_dict_entry_and_still_passes() -> None:
    """07 pins ``"klein_version": "1.2.0"`` as a bare scalar; that is a warning."""
    study = REPO_ROOT / "studies" / "07-iris-90years"
    lock = load_lock(study)
    assert lock["claims"]["klein_version"] == "1.2.0"
    shape = _check(verify_lock(study), "claims shape")
    assert shape.ok and "schema-1 scalar entry" in shape.message


def test_shipped_locks_carry_non_claim_ids_and_prose_values() -> None:
    lock = load_lock(REPO_ROOT / "studies" / "07-iris-90years")
    assert lock["claims"]["minimum_delta"]["claim"] == "floor"
    assert isinstance(lock["claims"]["floor_recipe"]["value"], str)
    checks = verify_lock(REPO_ROOT / "studies" / "07-iris-90years")
    assert _failures(checks) == []
    assert "value is prose" in _check(checks, "claims numbers").message


@pytest.mark.parametrize("slug", SHIPPED)
def test_strict_reports_the_schema_one_warnings_as_failures(slug: str) -> None:
    """``--strict`` has teeth: the legacy locks' derived values surface as failures."""
    checks = verify_lock(REPO_ROOT / "studies" / slug, strict=True)
    assert any(not c.ok for c in checks)
    assert lock_path(REPO_ROOT / "studies" / slug).is_file()


@pytest.mark.parametrize("slug", SHIPPED)
def test_shipped_locks_are_never_rewritten_by_a_mutating_verb(slug: str, tmp_path: Path) -> None:
    """Every mutating verb refuses a lock schema 1 ledger outright."""
    study = tmp_path / slug
    study.mkdir()
    for name in ("claims.lock", "findings.md", "study.yaml"):
        source = REPO_ROOT / "studies" / slug / name
        if source.is_file():
            (study / name).write_bytes(source.read_bytes())
    before = (study / "claims.lock").read_bytes()
    with pytest.raises(WorkflowError, match="lock schema 1"):
        pin_artifact(study, "results", "findings.md", commit=False)
    with pytest.raises(WorkflowError, match="lock schema 1"):
        add_number(study, "x", value=1.0, art="results", commit=False)
    with pytest.raises(WorkflowError, match="lock schema 1"):
        add_claim(
            study,
            "C1",
            claim_class="empirical-description",
            strength="exploratory",
            claim="x",
            commit=False,
        )
    with pytest.raises(WorkflowError, match="lock schema 1"):
        file_erratum(study, "E1", claims=["C1"], note="n", commit=False)
    assert (study / "claims.lock").read_bytes() == before


def test_from_legacy_migrates_a_copy_and_keeps_every_number(tmp_path: Path) -> None:
    slug = "08-iris-rematch"
    shipped = REPO_ROOT / "studies" / slug
    study = tmp_path / slug
    study.mkdir()
    for name in ("claims.lock", "findings.md", "study.yaml"):
        (study / name).write_bytes((shipped / name).read_bytes())
    original = load_lock(study)

    migrated = init_lock(study, from_legacy=True, commit=False)

    assert migrated["lock_schema"] == 2
    assert set(migrated["numbers"]) == set(original["claims"])
    for alias, before in original["claims"].items():
        after = migrated["numbers"][alias]
        assert after["value"] == before["value"]
        assert after.get("art") == (before.get("art") or before.get("artifact"))
        assert after.get("claim") == before.get("claim")
    # Nothing is ever removed: the whole original ledger survives verbatim.
    assert migrated["legacy"]["claims"] == original["claims"]
    # Repo-relative paths become study-relative, with the hashes untouched.
    assert migrated["artifacts"]["results"]["path"] == "results.tsv"
    assert migrated["artifacts"]["results"]["sha256"] == original["artifacts"]["results"]["sha256"]
    # The shipped file itself is untouched.
    assert (shipped / "claims.lock").read_bytes() != (study / "claims.lock").read_bytes()


# ---------------------------------------------------------------------------
# Lock schema 2 — the shape this engine writes
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def locked_study(ready_study) -> tuple[Path, Path]:
    """A schema-2 study carrying findings, an artifact and a finished lock."""
    repo, study = ready_study
    (study / "findings.md").write_text(
        "# Findings\n\n"
        "- **[C1]** The anchor scores 0.026744 on the development split.\n"
        "- **[C2]** The ladder closed: no challenger earned a keep.\n",
        encoding="utf-8",
    )
    (study / "tables").mkdir()
    (study / "tables" / "anchor.tsv").write_text(
        "run\tbrier\nE0001\t0.026744\nE0002\t0.055198\n", encoding="utf-8"
    )
    (study / "runs" / "E0001").mkdir(parents=True)
    (study / "runs" / "E0001" / "manifest.json").write_text("{}\n", encoding="utf-8")
    references_path(study).write_text(
        "references:\n"
        "  fisher1936:\n"
        "    title: 'The use of multiple measurements'\n"
        "    doi: '10.1111/j.1469-1809.1936.tb02137.x'\n"
        "    verified: true\n"
        "  unchecked:\n"
        "    title: 'A preprint nobody checked'\n"
        "    arxiv: '2601.00001'\n"
        "    verified: false\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        "findings and artifacts",
    )
    init_lock(study)
    pin_artifact(study, "anchor", "tables/anchor.tsv")
    add_number(study, "anchor_brier", value=0.026744, art="anchor", claim="C1", precision=6)
    add_claim(
        study,
        "C1",
        claim_class="empirical-description",
        strength="exploratory",
        claim="The anchor scores 0.026744 on the development split.",
        numbers=["anchor_brier"],
        evidence=["E0001", "art:anchor", "ref:fisher1936"],
    )
    add_claim(
        study,
        "C2",
        claim_class="procedural-verdict",
        strength="exploratory",
        claim="The ladder closed: no challenger earned a keep.",
        evidence=["E0001"],
    )
    return repo, study


def test_a_claims_commit_carries_the_lock_and_nothing_else(locked_study, capsys) -> None:
    """E15: ``klein claims`` files ``claims.lock``, never the findings draft.

    The lock is append-only across its git history, so its commits are read one
    by one.  A ``klein: claims`` commit that also carried an in-progress
    ``findings.md`` would put a sentence on the record that no claims verb ever
    checked.
    """
    repo, study = locked_study
    findings = study / "findings.md"
    findings.write_text(
        findings.read_text(encoding="utf-8") + "\n- a sentence still moving\n",
        encoding="utf-8",
    )

    add_claim(
        study,
        "C3",
        claim_class="procedural-verdict",
        strength="exploratory",
        claim="A third verdict, filed alone.",
        evidence=["E0001"],
    )

    committed = set(_git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert committed == {"studies/03-demo/claims.lock"}
    assert modified_paths(repo) == {"studies/03-demo/findings.md"}
    assert (
        "note: 1 uncommitted edit(s) left in the tree (findings.md) "
        "— not part of this commit"
    ) in capsys.readouterr().out


def test_schema2_lock_round_trips_and_verifies_clean(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    assert detect_lock_schema(lock) == 2
    assert lock["study_id"] == "03-demo"
    assert lock["claims"]["C1"]["numbers"] == ["anchor_brier"]
    checks = verify_lock(study, numbers=True)
    assert _failures(checks) == [], _failures(checks)
    assert len(checks) == 7


def test_canonical_output_is_stable_across_two_writes(locked_study) -> None:
    _repo, study = locked_study
    first = lock_path(study).read_bytes()
    write_lock(study, load_lock(study))
    second = lock_path(study).read_bytes()
    assert first == second
    text = second.decode("utf-8")
    assert text == canonical_lock_text(json.loads(text))
    assert text.endswith("}\n")
    assert '\n  "artifacts"' in text  # sorted keys, two-space indent


def test_init_skeleton_fails_verification_until_classes_are_given(ready_study) -> None:
    _repo, study = ready_study
    (study / "findings.md").write_text("- **[C1]** A sentence.\n", encoding="utf-8")
    lock = init_lock(study)
    assert lock["claims"]["C1"]["class"] is None
    shape = _check(verify_lock(study), "claims shape")
    assert not shape.ok and "class is null" in shape.message


def test_init_refuses_to_overwrite_an_existing_lock(locked_study) -> None:
    _repo, study = locked_study
    with pytest.raises(WorkflowError, match="already exists"):
        init_lock(study)


# --- the seven checks, one failing case each ------------------------------


def test_check1_shape_refuses_an_unknown_class_and_a_ceiling_breach(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C2"]["class"] = "vibes"
    write_lock(study, lock)
    assert "unknown class 'vibes'" in _check(verify_lock(study), "claims shape").message

    lock["claims"]["C2"]["class"] = "mechanism-interpretation"
    lock["claims"]["C2"]["strength"] = "confirmed"
    write_lock(study, lock)
    shape = _check(verify_lock(study), "claims shape")
    assert not shape.ok and "ceilings at 'exploratory'" in shape.message


def test_check2_artifacts_catch_a_flipped_byte(locked_study) -> None:
    _repo, study = locked_study
    table = study / "tables" / "anchor.tsv"
    table.write_text(table.read_text(encoding="utf-8").replace("0.026744", "0.026745"), encoding="utf-8")
    artifacts = _check(verify_lock(study), "claims artifacts")
    assert not artifacts.ok and "sha256 mismatch" in artifacts.message


def test_check2_warns_when_a_pinned_artifact_is_not_tracked(locked_study) -> None:
    repo, study = locked_study
    (study / "tables" / "loose.tsv").write_text("k\n1.5\n", encoding="utf-8")
    pin_artifact(study, "loose", "tables/loose.tsv")
    artifacts = _check(verify_lock(study), "claims artifacts")
    assert artifacts.ok and "is not tracked by git" in artifacts.message
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=T", "-c", "user.email=t@x.invalid", "commit", "-q", "-m", "track")
    assert "not tracked" not in _check(verify_lock(study), "claims artifacts").message


def test_check5_honours_the_numbers_ok_marker(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C2"]["claim"] = (
        "The ladder closed after 4 rungs <!-- klein:numbers-ok: rung count, see Table 1 -->"
    )
    write_lock(study, lock)
    numbers = _check(verify_lock(study, numbers=True), "claims numbers")
    assert numbers.ok
    assert "numerals exempted by marker — rung count, see Table 1" in numbers.message
    assert not _check(verify_lock(study, numbers=True, strict=True), "claims numbers").ok


def test_check3_presence_is_two_way_on_schema_two(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C9"] = dict(lock["claims"]["C2"], claim="A claim findings never makes.")
    write_lock(study, lock)
    presence = _check(verify_lock(study), "claims presence")
    assert not presence.ok and "no **[C9]** line in findings.md" in presence.message

    del lock["claims"]["C9"]
    del lock["claims"]["C2"]
    write_lock(study, lock)
    presence = _check(verify_lock(study), "claims presence")
    assert "findings.md declares **[C2]** but the lock has no such claim" in presence.message


def test_check4_evidence_must_resolve(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C2"]["evidence"] = [
        "E0404",
        "sweep:never_ran",
        "rep:E0001@2026-01-01T00:00:00Z",
        "ref:nobody",
        "art:nosuch",
        "not-an-id",
    ]
    write_lock(study, lock)
    evidence = _check(verify_lock(study), "claims evidence")
    assert not evidence.ok
    for fragment in (
        "no runs/E0404/manifest.json",
        "neither state.sweeps nor sweeps/never_ran.sidecar.tsv",
        "no runs/E0001/replications/2026-01-01T00:00:00Z.json",
        "no such key in references.yaml",
        "is not a pinned artifact alias",
        "not an id in the inquiry-model grammar",
    ):
        assert fragment in evidence.message, fragment


def test_check4_unverified_reference_behind_a_confirmed_claim_warns(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C2"]["evidence"] = ["E0001", "ref:unchecked"]
    write_lock(study, lock)
    evidence = _check(verify_lock(study), "claims evidence")
    assert evidence.ok, evidence.message  # exploratory: an unverified ref is fine

    lock["claims"]["C2"]["strength"] = "confirmed"
    write_lock(study, lock)
    evidence = _check(verify_lock(study), "claims evidence")
    assert evidence.ok and "[WARN]" in evidence.message
    assert "behind a confirmed claim" in evidence.message
    strict = _check(verify_lock(study, strict=True), "claims evidence")
    assert not strict.ok


def test_check5_numbers_value_must_live_in_its_artifact(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["numbers"]["anchor_brier"]["value"] = 0.123456
    write_lock(study, lock)
    numbers = _check(verify_lock(study), "claims numbers")
    assert not numbers.ok
    assert "0.123456 is not in artifact 'anchor' at 6 decimals" in numbers.message


def test_check5_a_sentence_numeral_needs_an_alias(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C2"]["claim"] = "In 2026 the ladder closed after 4 rungs (see C1, E0001, RQ1, P2)."
    write_lock(study, lock)
    # The value -> artifact half is silent about sentences; --numbers is not.
    assert _check(verify_lock(study), "claims numbers").ok
    numbers = _check(verify_lock(study, numbers=True), "claims numbers")
    assert not numbers.ok
    assert "the sentence quotes 4" in numbers.message
    # Years and identifiers are exempt: only the bare 4 is reported.
    assert "quotes 2026" not in numbers.message
    assert "quotes 1" not in numbers.message


def test_check6_append_only_catches_removals_and_mutations(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    del lock["numbers"]["anchor_brier"]
    lock["claims"]["C1"]["numbers"] = []
    write_lock(study, lock)
    append_only = _check(verify_lock(study), "claims append-only")
    assert not append_only.ok
    assert "number 'anchor_brier' was removed" in append_only.message
    assert "claim C1 numbers lost ['anchor_brier']" in append_only.message

    lock = load_lock(study)  # restore the alias, then mutate its value instead
    lock["numbers"]["anchor_brier"] = {"value": 0.9, "art": "anchor", "claim": "C1", "precision": 6}
    lock["claims"]["C1"]["numbers"] = ["anchor_brier"]
    write_lock(study, lock)
    append_only = _check(verify_lock(study), "claims append-only")
    assert "number 'anchor_brier' value changed" in append_only.message


def test_check6_a_removed_claim_fails(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    del lock["claims"]["C2"]
    write_lock(study, lock)
    assert "claim C2 was removed" in _check(verify_lock(study), "claims append-only").message


def test_check6_strength_changes_only_beside_an_erratum(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C1"]["strength"] = "confirmed"
    write_lock(study, lock)
    append_only = _check(verify_lock(study), "claims append-only")
    assert not append_only.ok
    assert "strength changed" in append_only.message
    assert "without an erratum naming it" in append_only.message


def test_check7_ancestry_rejects_an_unresolvable_and_a_non_ancestor_head(locked_study) -> None:
    repo, study = locked_study
    lock = load_lock(study)
    lock["git_head"] = "0" * 40
    write_lock(study, lock)
    ancestry = _check(verify_lock(study), "claims ancestry")
    assert not ancestry.ok and "does not resolve" in ancestry.message

    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _git(repo, "switch", "-q", "-c", "sidetrack")
    (study / "playbook.md").write_text("side\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=T", "-c", "user.email=t@x.invalid", "commit", "-q", "-m", "side")
    side = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-q", branch)
    lock = load_lock(study)
    lock["git_head"] = side
    write_lock(study, lock)
    ancestry = _check(verify_lock(study), "claims ancestry")
    assert not ancestry.ok and "is not an ancestor of HEAD" in ancestry.message


def test_klein_commit_that_does_not_resolve_is_advisory(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["klein_commit"] = "1" * 40
    write_lock(study, lock)
    ancestry = _check(verify_lock(study), "claims ancestry")
    assert ancestry.ok and "does not resolve here (advisory" in ancestry.message


# --- errata ----------------------------------------------------------------


def test_erratum_tags_downgrades_logs_and_keeps_the_claim(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C1"]["strength"] = "confirmed"
    write_lock(study, lock)
    file_erratum(
        study,
        "E1",
        claims=["C1"],
        note="the ledger lane ran on the retired partition",
        strength="exploratory",
    )
    lock = load_lock(study)
    assert lock["claims"]["C1"]["strength"] == "exploratory"
    assert lock["claims"]["C1"]["errata"] == ["E1"]
    assert lock["claims"]["C1"]["claim"].startswith("The anchor scores")  # never deleted
    assert lock["errata"]["E1"]["claims"] == ["C1"]
    assert [e["type"] for e in read_events(study)][-1] == "erratum_filed"
    assert _failures(verify_lock(study)) == []


def test_erratum_refuses_an_upgrade_a_reused_id_and_an_unknown_claim(locked_study) -> None:
    _repo, study = locked_study
    with pytest.raises(WorkflowError, match="downgrades only"):
        file_erratum(study, "E1", claims=["C1"], note="n", strength="confirmed")
    with pytest.raises(WorkflowError, match="unknown claims"):
        file_erratum(study, "E1", claims=["C99"], note="n")
    file_erratum(study, "E1", claims=["C1"], note="a real erratum")
    with pytest.raises(WorkflowError, match="already filed"):
        file_erratum(study, "E1", claims=["C2"], note="again")


def test_an_orphan_erratum_tag_fails_the_shape_check(locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C1"]["errata"] = ["E7"]
    write_lock(study, lock)
    shape = _check(verify_lock(study), "claims shape")
    assert not shape.ok and "erratum 'E7' is not in the errata registry" in shape.message


# --- authoring guards ------------------------------------------------------


def test_add_enforces_the_class_ceiling_and_never_writes_refuted(locked_study) -> None:
    _repo, study = locked_study
    with pytest.raises(WorkflowError, match="ceilings at 'exploratory'"):
        add_claim(
            study,
            "C2",
            claim_class="research-discipline",
            strength="confirmed",
            claim="x",
            commit=False,
        )
    with pytest.raises(WorkflowError, match="never written at first authoring"):
        add_claim(
            study,
            "C2",
            claim_class="procedural-verdict",
            strength="refuted",
            claim="x",
            commit=False,
        )
    assert set(CLAIM_CLASSES) == {
        "empirical-description",
        "procedural-verdict",
        "mechanism-interpretation",
        "known-dgp-teaching",
        "research-discipline",
    }


def test_known_dgp_teaching_claims_are_scoped_in_silico(locked_study) -> None:
    _repo, study = locked_study
    (study / "findings.md").write_text(
        (study / "findings.md").read_text(encoding="utf-8")
        + "- **[C3]** Under the declared DGP the estimator converges.\n",
        encoding="utf-8",
    )
    entry = add_claim(
        study,
        "C3",
        claim_class="known-dgp-teaching",
        strength="confirmed",
        claim="Under the declared DGP the estimator converges.",
        evidence=["E0001"],
        commit=False,
    )
    assert entry["scope"] == "in-silico"
    lock = load_lock(study)
    lock["claims"]["C3"].pop("scope")
    write_lock(study, lock)
    shape = _check(verify_lock(study), "claims shape")
    assert not shape.ok and '"scope": "in-silico"' in shape.message


def test_a_number_never_changes_its_value_art_or_claim(locked_study) -> None:
    _repo, study = locked_study
    with pytest.raises(WorkflowError, match="a number's value never changes"):
        add_number(study, "anchor_brier", value=0.9, art="anchor", claim="C1", commit=False)
    with pytest.raises(WorkflowError, match="not a pinned artifact"):
        add_number(study, "other", value=1.0, art="nope", commit=False)
    # A note may grow.
    entry = add_number(
        study, "anchor_brier", value=0.026744, art="anchor", claim="C1", note="E0001", commit=False
    )
    assert entry["note"] == "E0001"


def test_pin_refuses_absolute_paths_and_missing_files(locked_study, tmp_path: Path) -> None:
    _repo, study = locked_study
    with pytest.raises(WorkflowError, match="study-relative"):
        pin_artifact(study, "abs", str(tmp_path / "x.tsv"), commit=False)
    with pytest.raises(WorkflowError, match="is not a file"):
        pin_artifact(study, "gone", "tables/missing.tsv", commit=False)


# --- integration: the CLI and klein verify ---------------------------------


def test_cli_claims_verify_prints_the_seven_checks(capsys) -> None:
    rc = cli.main(["claims", "verify", "--study", str(REPO_ROOT / "studies" / "09-iris-first-lesson")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "summary: 7 checks, 0 failed" in out
    assert "[OK] claims append-only" in out


def test_cli_claims_verify_strict_exits_nonzero(capsys) -> None:
    rc = cli.main(
        ["claims", "verify", "--study", str(REPO_ROOT / "studies" / "08-iris-rematch"), "--strict"]
    )
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_claims_pin_number_add_are_wired(locked_study, capsys) -> None:
    _repo, study = locked_study
    assert cli.main(["claims", "pin", "--study", str(study), "sealed", "results.tsv"]) == 0
    assert "pinned sealed: results.tsv" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "claims",
                "number",
                "--study",
                str(study),
                "n_transactions",
                "--value",
                "0",
                "--art",
                "sealed",
                "--claim",
                "contract",
            ]
        )
        == 0
    )
    assert load_lock(study)["numbers"]["n_transactions"]["value"] == 0


def test_cli_claims_errors_exit_two(locked_study, capsys) -> None:
    _repo, study = locked_study
    assert cli.main(["claims", "init", "--study", str(study)]) == 2
    assert "klein: error:" in capsys.readouterr().err


def test_mutating_verbs_self_commit_the_lock(locked_study) -> None:
    repo, study = locked_study
    assert _git(repo, "status", "--porcelain") == "", "the lock verbs file their own writes"
    revisions = _git(repo, "log", "--format=%H", "--", "studies/03-demo/claims.lock").splitlines()
    assert len(revisions) >= 4  # init, pin, number, add, add


def test_verify_study_runs_the_law_advisory_on_schema_two(monkeypatch, locked_study) -> None:
    _repo, study = locked_study
    lock = load_lock(study)
    lock["claims"]["C1"]["class"] = None  # a failing shape
    write_lock(study, lock)

    advisory = claims_checks(study, 2)
    assert len(advisory) == 7
    assert all(c.ok for c in advisory)
    assert any("[WARN] advisory on schema 2" in c.message for c in advisory)

    enforcing = claims_checks(study, 3)
    assert any(not c.ok for c in enforcing)


def test_verify_study_adds_nothing_without_a_lock(ready_study) -> None:
    _repo, study = ready_study
    assert not lock_path(study).is_file()
    assert claims_checks(study, 3) == []


def test_shipped_study_verify_adds_seven_advisory_checks() -> None:
    from kleinlib.workflow import verify_study

    study = REPO_ROOT / "studies" / "07-iris-90years"
    checks = verify_study(study)
    claims_named = [c for c in checks if c.name.startswith("claims ")]
    assert len(claims_named) == 7
    assert all(c.ok for c in claims_named)


def test_a_lock_outside_a_git_repo_warns_rather_than_crashes(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    (study / "findings.md").write_text("- **[C1]** A sentence with 1.5 in it.\n", encoding="utf-8")
    write_lock(
        study,
        {
            "lock_schema": 2,
            "study_id": "99-orphan",
            "git_head": "f" * 40,
            "law": "…",
            "artifacts": {},
            "numbers": {},
            "claims": {
                "C1": {
                    "class": "research-discipline",
                    "strength": "exploratory",
                    "claim": "A sentence with 1.5 in it.",
                    "numbers": [],
                    "evidence": ["E0001"],
                    "errata": [],
                }
            },
            "errata": {},
        },
    )
    checks = verify_lock(study)
    append_only = _check(checks, "claims append-only")
    assert append_only.ok and "no committed history" in append_only.message
    assert claims_module.detect_lock_schema(load_lock(study)) == 2


def test_sentence_exemptions_follow_the_numbers_law() -> None:
    """Counts naming their unit are exempt; a bare reference value is not."""
    from kleinlib.claims import NUMERAL_RE, SENTENCE_EXEMPT_RE

    sentence = (
        "A free-intercept fit of Hubble's 24 objects gives K = 454.16 km/s/Mpc, not 465; "
        "0 of 42 cells cleared with k = 5 seeds in 1929 (E0003, P2, C2)"
    )
    left = NUMERAL_RE.findall(SENTENCE_EXEMPT_RE.sub(" ", sentence))
    assert left == ["454.16", "465"], left


def test_a_version_tag_in_a_claim_sentence_is_not_a_numeral() -> None:
    """`v1` is an identifier, and both halves of the numbers law must agree.

    `kleinlib.numbers.DOCUMENT_EXEMPT_PATTERNS` already exempts version tokens
    when scanning a whole document; before this branch existed the SENTENCE
    scanner did not, so a claim that named the study generation it ports from
    ("all three v1 rungs reproduce") was read as quoting the numeral 1 — a
    number that was never measured and therefore has no honest alias.
    """
    from kleinlib.claims import NUMERAL_RE, SENTENCE_EXEMPT_RE
    from kleinlib.numbers import DOCUMENT_EXEMPT_RE

    sentence = "All three v1 rungs reproduce under schema v2.0; the tag is v1.3.0 and the bar is 0.0375805"
    left = NUMERAL_RE.findall(SENTENCE_EXEMPT_RE.sub(" ", sentence))
    assert left == ["0.0375805"], left
    # the document half already agreed, and must keep agreeing
    assert DOCUMENT_EXEMPT_RE.search("v1.3.0")
