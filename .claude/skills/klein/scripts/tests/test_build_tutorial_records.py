"""Record-derived assembly: the evidence block, accurately identified source
exhibits, the track/kind-aware ledger, and subsection anchors.

Kept apart from ``test_build_tutorial.py`` on purpose — these exercise what the
builder reads out of a study's RECEIPTS (``claims.lock``, ``study_state.json``,
run manifests, git) rather than what the tutor typed into a fragment.

The module is loaded through ``importlib.util`` for the same reason as its
sibling: ``.claude/skills/klein/scripts/`` is deliberately not a package, so the
whole skill directory stays copy-a-directory portable.
"""

from __future__ import annotations

import json
import subprocess
import types
from pathlib import Path

import pytest
from test_build_tutorial import (
    FRAGMENTS,
    STUDY_YAML,
    TRAIN_PY,
    _load_build_tutorial,
    scaffold,
)


@pytest.fixture(scope="session")
def build_module() -> types.ModuleType:
    """Own loader, not the sibling's fixture: pytest resolves a fixture by name
    in the test module or a conftest, and these scripts are not a package."""
    return _load_build_tutorial()


# CI runners have no git identity; every fixture commit brings its own.
GIT_ID = ("-c", "user.name=t", "-c", "user.email=t@t")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def lock_v2(**overrides) -> dict:
    """A schema-2 claims.lock shaped like the shipped ones."""
    payload = {
        "lock_schema": 2,
        "git_head": "753eeac11d470ea873fdc2895380fa9c70e87bb7",
        "klein_version": "2.0.0",
        "errata": {},
        "claims": {
            "C1": {
                "claim": "The anchor held.",
                "class": "empirical-description",
                "errata": [],
                "evidence": ["E0001"],
                "numbers": ["anchor"],
                "strength": "confirmed",
            },
            "C2": {
                "claim": "The challenger did not.",
                "class": "research-discipline",
                "errata": ["E1"],
                "evidence": ["E0002"],
                "numbers": [],
                "strength": "exploratory",
            },
        },
    }
    payload.update(overrides)
    return payload


def finalization(**overrides) -> dict:
    payload = {
        "label": "confirmed",
        "referee": {
            "independent_of_experimenter": True,
            "referee": "klein-referee (model: claude-opus-5[1m])",
            "status": "refereed",
            "verdict": "PASS-WITH-NOTES",
        },
    }
    payload.update(overrides)
    return payload


def with_evidence_marker(**extra: str) -> dict[str, str]:
    """The default fragments, with the evidence marker in 05-findings."""
    frags = dict(FRAGMENTS)
    frags["05-findings.html"] = frags["05-findings.html"] + "\n<!--EVIDENCE-->"
    frags.update(extra)
    return frags


# ---------------------------------------------------------------------------
# R-1 — <!--EVIDENCE--> is generated from the records
# ---------------------------------------------------------------------------


def test_evidence_block_copies_the_lock_and_the_finalization(build_module, tmp_path):
    study = scaffold(tmp_path / "00-evidence", fragments=with_evidence_marker())
    write_json(study / "claims.lock", lock_v2())
    write_json(study / "study_state.json", {"finalization": finalization()})

    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")

    assert 'data-generated="evidence"' in page
    assert "<!--EVIDENCE-->" not in page
    # counts, each inside <code> so the advisory numeral scan skips it
    assert "confirmed <code>1</code>" in page
    assert "exploratory <code>1</code>" in page
    assert "empirical-description <code>1</code>" in page
    assert "research-discipline <code>1</code>" in page
    assert "<code>1</code> of <code>2</code> claims tagged" in page
    # verbatim strings, never recomputed
    assert "<code>753eeac11d47</code>" in page  # short git_head
    assert "753eeac11d470ea873fdc2895380fa9c70e87bb7" not in page
    assert "<code>2.0.0</code>" in page
    assert "PASS-WITH-NOTES" in page
    assert "independent of the experimenter: yes" in page
    assert build_module.acceptance_violations(page) == []


def test_class_counts_are_alphabetical_and_strength_is_ranked(build_module, tmp_path):
    lock = lock_v2()
    lock["claims"]["C3"] = {
        "claim": "A third.",
        "class": "aardvark-class",
        "errata": [],
        "evidence": [],
        "numbers": [],
        "strength": "speculative",
    }
    study = scaffold(tmp_path / "00-order", fragments=with_evidence_marker())
    write_json(study / "claims.lock", lock)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    # confirmed, exploratory, then anything else alphabetically
    assert page.index("confirmed <code>") < page.index("exploratory <code>")
    assert page.index("exploratory <code>") < page.index("speculative <code>")
    # classes purely alphabetically
    assert page.index("aardvark-class <code>") < page.index("empirical-description <code>")


def test_v1_lock_shape_is_reported_as_not_recorded(build_module, tmp_path):
    """Study 07's lock has no lock_schema and {art, claim, value} entries."""
    study = scaffold(tmp_path / "00-lockv1", fragments=with_evidence_marker())
    write_json(
        study / "claims.lock",
        {
            "study": "07-iris-90years",
            "git_head": "abc",
            "claims": {"C1": {"art": "results.tsv", "claim": "…", "value": "1.0"}},
        },
    )
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "not recorded (schema 2)" in page
    assert "by strength" not in page


def test_missing_records_are_named_not_guessed(build_module, tmp_path):
    study = scaffold(tmp_path / "00-norecords", fragments=with_evidence_marker())
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "not recorded (schema 2)" in page  # claims.lock
    assert "finalization</dt><dd>not recorded" in page


def test_missing_finalization_with_a_lock_present(build_module, tmp_path):
    study = scaffold(tmp_path / "00-nofinal", fragments=with_evidence_marker())
    write_json(study / "claims.lock", lock_v2())
    write_json(study / "study_state.json", {"gates": {}})
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "finalization</dt><dd>not recorded" in page
    assert "<code>2</code> locked" in page


def test_dependent_experimenter_renders_no(build_module, tmp_path):
    state = {"finalization": finalization()}
    state["finalization"]["referee"]["independent_of_experimenter"] = False
    study = scaffold(tmp_path / "00-dependent", fragments=with_evidence_marker())
    write_json(study / "study_state.json", state)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "independent of the experimenter: no" in page


def test_unrefereed_study_copies_the_recorded_reason(build_module, tmp_path):
    """`klein finalize --no-referee --reason` writes {status, reason}; the reason
    is the study's own disclosure and is copied, never paraphrased."""
    study = scaffold(tmp_path / "00-unrefereed", fragments=with_evidence_marker())
    (study / "study.yaml").write_text("schema_version: 3\n" + STUDY_YAML, encoding="utf-8")
    write_json(
        study / "study_state.json",
        {
            "finalization": {
                "label": "exploratory",
                "referee": {"status": "unrefereed", "reason": "solo session, no second model"},
            }
        },
    )
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "unrefereed (finalized with --no-referee: solo session, no second model)" in page


def test_schema3_study_without_records_says_not_recorded_without_blaming_schema_2(
    build_module, tmp_path
):
    study = scaffold(tmp_path / "00-s3-norecords", fragments=with_evidence_marker())
    (study / "study.yaml").write_text("schema_version: 3\n" + STUDY_YAML, encoding="utf-8")
    write_json(study / "study_state.json", {"finalization": {"label": "exploratory"}})
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "claims.lock</dt><dd>not recorded</dd>" in page
    assert "referee</dt><dd>not recorded</dd>" in page
    assert "(schema 2)" not in page


def test_confirmation_gaps_are_copied_verbatim(build_module, tmp_path):
    gap = "verify: track 'n_small' has no development run to reproduce"
    study = scaffold(tmp_path / "00-gaps", fragments=with_evidence_marker())
    write_json(
        study / "study_state.json",
        {"finalization": finalization(confirmation_gaps={"n_small": [gap]})},
    )
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "confirmation gap · n_small" in page
    assert "no development run to reproduce" in page


def test_lock_without_the_marker_fails_the_acceptance_guard(build_module, tmp_path, capsys):
    study = scaffold(tmp_path / "00-nomarker")  # default fragments: no marker
    write_json(study / "claims.lock", lock_v2())
    rc = build_module.main([str(study)])
    assert rc == 4
    err = capsys.readouterr().err
    assert "claims.lock exists but no fragment carries <!--EVIDENCE-->" in err
    assert "05-findings.html" in err


def test_a_study_without_a_lock_builds_without_the_marker(build_module, tmp_path):
    study = scaffold(tmp_path / "00-nolock")
    assert build_module.main([str(study)]) == 0


def test_every_marker_occurrence_is_replaced(build_module, tmp_path):
    frags = with_evidence_marker()
    frags["07-next-steps.html"] = FRAGMENTS["07-next-steps.html"] + "\n<!--EVIDENCE-->"
    study = scaffold(tmp_path / "00-twomarkers", fragments=frags)
    write_json(study / "claims.lock", lock_v2())
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert page.count('data-generated="evidence"') == 2


# ---------------------------------------------------------------------------
# R-2 — accurately identified source exhibits
# ---------------------------------------------------------------------------

FIRST_TRAIN = 'CELL = "first-commit"\nprint(CELL)\n'
SECOND_TRAIN = 'CELL = "working-tree"\nprint(CELL)\n'


def run_fixture(tmp_path: Path, name: str, *, fragments: dict[str, str]) -> tuple[Path, str]:
    """A study inside a real repo with two commits and a manifest naming the FIRST."""
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q")
    studies = repo / "studies"
    studies.mkdir()
    study = scaffold(studies / "01-run", fragments=fragments)
    (study / "study.yaml").write_text(
        "schema_version: 3\n"
        'goal: "Show the executed cell"\n'
        "entrypoint:\n"
        '  command: ["uv", "run", "--locked", "python", "-u", "train.py"]\n'
        '  mutable: ["train.py"]\n'
        "metric:\n"
        '  name: "val_auc"\n'
        "  goal: higher\n",
        encoding="utf-8",
    )
    (study / "train.py").write_text(FIRST_TRAIN, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, *GIT_ID, "commit", "-q", "-m", "first")
    first = git(repo, "rev-parse", "HEAD")
    # run-one RESTORES the mutable surface, so the working tree moves on:
    (study / "train.py").write_text(SECOND_TRAIN, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, *GIT_ID, "commit", "-q", "-m", "second")
    write_json(
        study / "runs" / "E0001" / "manifest.json",
        {
            "candidate_commit": first,
            "evaluation_kind": "final_test",
            "track": "primary",
            "experiment": "E0001",
        },
    )
    return study, first


def test_data_run_includes_the_bytes_the_run_executed(build_module, tmp_path):
    frags = with_evidence_marker(
        **{
            "06-coding-advice.html": (
                '<h2>C</h2><pre data-code="train.py" data-lang="python" data-run="E0001"></pre>'
            )
        }
    )
    study, first = run_fixture(tmp_path, "repo-run", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")

    assert "first-commit" in page
    assert "working-tree" not in page  # NOT the file on disk
    assert 'data-run="E0001"' in page
    assert "executed by <code>E0001</code> (final_test, track primary)" in page
    assert f"at commit <code>{first[:12]}</code>" in page
    assert "· sha256 <code>" in page
    assert '<details class="source"' in page
    assert '<pre class="klein-code" data-code-source="train.py">' in page


def test_bare_mutable_include_is_refused_with_the_fix_named(build_module, tmp_path, capsys):
    frags = with_evidence_marker(
        **{"06-coding-advice.html": '<h2>C</h2><pre data-code="train.py"></pre>'}
    )
    study, _first = run_fixture(tmp_path, "repo-bare", fragments=frags)
    assert build_module.main([str(study)]) == 6
    err = capsys.readouterr().err
    assert "data-code='train.py' is the mutable surface" in err
    assert 'add data-run="E####" to include the executed source' in err
    assert 'data-role="template" to label it' in err
    assert not (study / "report" / "index.html").exists()


def test_template_role_builds_and_says_restored_template(build_module, tmp_path):
    frags = with_evidence_marker(
        **{
            "06-coding-advice.html": (
                '<h2>C</h2><pre data-code="train.py" data-role="template"></pre>'
            )
        }
    )
    study, _first = run_fixture(tmp_path, "repo-template", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "restored template on disk, not a run's cell" in page
    assert 'data-role="template"' in page
    assert "working-tree" in page  # the template IS the file on disk


def test_attribute_order_is_free(build_module, tmp_path):
    frags = with_evidence_marker(
        **{
            "06-coding-advice.html": (
                '<h2>C</h2><pre data-code="train.py" data-run="E0001" data-lang="python"></pre>'
            )
        }
    )
    study, _first = run_fixture(tmp_path, "repo-order", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'class="language-python"' in page
    assert "first-commit" in page


def test_non_mutable_file_still_includes_bare(build_module, tmp_path):
    frags = with_evidence_marker(
        **{"06-coding-advice.html": '<h2>C</h2><pre data-code="verify.py"></pre>'}
    )
    study = scaffold(tmp_path / "00-verifier", fragments=frags)
    (study / "verify.py").write_text(TRAIN_PY, encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "current file at build (outside the mutable surface)" in page
    assert 'data-code-source="verify.py"' in page


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        ("no-manifest", "has no readable manifest"),
        ("no-commit", "records no 'candidate_commit'"),
        ("bad-commit", "git show"),
    ],
)
def test_broken_run_provenance_is_a_code_error(build_module, tmp_path, capsys, mutation, needle):
    frags = with_evidence_marker(
        **{"06-coding-advice.html": '<h2>C</h2><pre data-code="train.py" data-run="E0001"></pre>'}
    )
    study, _first = run_fixture(tmp_path, f"repo-{mutation}", fragments=frags)
    manifest = study / "runs" / "E0001" / "manifest.json"
    if mutation == "no-manifest":
        manifest.unlink()
    elif mutation == "no-commit":
        write_json(manifest, {"evaluation_kind": "final_test", "track": "primary"})
    else:
        write_json(manifest, {"candidate_commit": "0" * 40, "track": "primary"})
    assert build_module.main([str(study)]) == 6
    err = capsys.readouterr().err
    assert needle in err
    assert "06-coding-advice.html" in err
    assert "E0001" in err


def test_unknown_role_is_refused(build_module, tmp_path, capsys):
    frags = with_evidence_marker(
        **{
            "06-coding-advice.html": '<h2>C</h2><pre data-code="verify.py" data-role="winner"></pre>'
        }
    )
    study = scaffold(tmp_path / "00-badrole", fragments=frags)
    (study / "verify.py").write_text(TRAIN_PY, encoding="utf-8")
    assert build_module.main([str(study)]) == 6
    assert "is not a known role" in capsys.readouterr().err


def test_an_unknown_attribute_fails_closed(build_module, tmp_path, capsys):
    frags = with_evidence_marker(
        **{"06-coding-advice.html": '<h2>C</h2><pre data-code="verify.py" data-cell="x"></pre>'}
    )
    study = scaffold(tmp_path / "00-badattr", fragments=frags)
    (study / "verify.py").write_text(TRAIN_PY, encoding="utf-8")
    assert build_module.main([str(study)]) == 6
    assert "unconsumed data-code" in capsys.readouterr().err


def test_mutable_surface_mirrors_the_contract_rule(build_module, tmp_path):
    assert build_module.mutable_surface({}) == ("train.py",)
    assert build_module.mutable_surface({"schema_version": 2, "mutable": ["a.py"]}) == ("train.py",)
    assert build_module.mutable_surface({"schema_version": 3, "mutable": ["a.py", "b.py"]}) == (
        "a.py",
        "b.py",
    )
    assert build_module.mutable_surface({"schema_version": 3, "mutable": []}) == ("train.py",)


def test_tiny_parser_reads_the_surface_and_the_schema(build_module, tmp_path):
    study = tmp_path / "00-tiny"
    study.mkdir()
    (study / "study.yaml").write_text(
        "schema_version: 3\n"
        'goal: "Tiny"\n'
        "entrypoint:\n"
        "  mutable:\n"
        "    - search.py\n"
        "    - lib/cells.py\n"
        "tracks:\n"
        "  n_small:\n"
        "    metric:\n"
        '      name: "points"\n'
        '      goal: "higher"\n',
        encoding="utf-8",
    )
    saved = build_module.yaml
    try:
        build_module.yaml = None
        meta = build_module.load_study_meta(study)
    finally:
        build_module.yaml = saved
    assert meta["schema_version"] == 3
    assert meta["mutable"] == ["search.py", "lib/cells.py"]
    assert meta["tracks"] == [("n_small", "points", "higher")]
    assert build_module.mutable_surface(meta) == ("search.py", "lib/cells.py")


# ---------------------------------------------------------------------------
# R-3 — the track/kind-aware ledger
# ---------------------------------------------------------------------------

TRACKED_TSV = (
    "experiment\ttrack\tprimary_metric\tstatus\tcommit\tdescription\n"
    "E0001\tprimary\t0.612000\tkeep\tabc1234\tanchor\n"
    "E0002\tprimary\t0.640000\tdiscard\tdef5678\tchallenger\n"
)


def test_ledger_without_a_track_column_omits_it(build_module, tmp_path):
    study = scaffold(tmp_path / "00-notrack")  # RESULTS_TSV has no track field
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "<th>Track</th>" not in page
    assert "<th>Kind</th>" not in page  # no run manifests either
    assert '<td class="num">0.625462</td>' in page
    # the key names the metric and its direction, read from study.yaml
    assert 'class="ledger-key"' in page
    assert "<strong>val_auc</strong> (higher is better)" in page


def test_ledger_shows_track_and_kind_when_the_records_carry_them(build_module, tmp_path):
    study = scaffold(tmp_path / "00-tracked")
    (study / "results.tsv").write_text(TRACKED_TSV, encoding="utf-8")
    (study / "study.yaml").write_text(
        "schema_version: 3\n"
        'goal: "Tracked"\n'
        "tracks:\n"
        "  primary:\n"
        "    metric:\n"
        '      name: "val_auc"\n'
        '      goal: "higher"\n',
        encoding="utf-8",
    )
    write_json(
        study / "runs" / "E0002" / "manifest.json",
        {"evaluation_kind": "final_test", "track": "primary"},
    )
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert (
        "<th>Exp</th><th>Track</th><th>Kind</th><th>Metric</th><th>Status</th>"
        "<th>Description</th>" in page
    )
    assert "kind-final_test" in page
    assert "<td>final_test</td>" in page
    assert "<td>—</td>" in page  # E0001 has no manifest
    assert "primary — <strong>val_auc</strong> (higher is better)" in page


def test_ledger_key_is_omitted_when_study_yaml_declares_no_metric(build_module, tmp_path):
    study = scaffold(tmp_path / "00-nokey")
    (study / "study.yaml").write_text('goal: "No metric"\n', encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'class="ledger-key"' not in page


# ---------------------------------------------------------------------------
# R-10 — subsection anchors
# ---------------------------------------------------------------------------

TWO_H3 = (
    "<h2>Coding Advice</h2>"
    "<h3>Read the floor from the contract</h3><p>a</p>"
    "<h3>Print every guardrail</h3><p>b</p>"
)


def test_h3_ids_and_subnav(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = TWO_H3
    study = scaffold(tmp_path / "00-subnav", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert '<h3 id="read-the-floor-from-the-contract">' in page
    assert '<h3 id="print-every-guardrail">' in page
    assert '<nav class="subnav" aria-label="In this section">' in page
    assert '<a href="#read-the-floor-from-the-contract">' in page
    # the nav sits right after the section heading, before the first h3
    assert page.index('class="subnav"') < page.index('<h3 id="read-the-floor')
    assert build_module.acceptance_violations(page) == []


def test_single_h3_gets_an_id_but_no_subnav(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = "<h2>Coding Advice</h2><h3>One only</h3><p>a</p>"
    study = scaffold(tmp_path / "00-onesub", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert '<h3 id="one-only">' in page
    assert 'class="subnav"' not in page  # the stylesheet names it; the markup must not


def test_duplicate_headings_are_numbered_and_existing_ids_kept(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = (
        "<h2>Coding Advice</h2>"
        "<h3>Pitfalls</h3><h3>Pitfalls</h3>"
        '<h3 id="hand-written">Chosen by hand</h3>'
    )
    frags["07-next-steps.html"] = "<h2>Next Steps</h2><h3>Pitfalls</h3><h3>More</h3>"
    study = scaffold(tmp_path / "00-dupes", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert '<h3 id="pitfalls">' in page
    assert '<h3 id="pitfalls-2">' in page
    assert '<h3 id="pitfalls-3">' in page  # de-duplication is PAGE-wide
    assert '<h3 id="hand-written">' in page
    assert '<a href="#hand-written">Chosen by hand</a>' in page


def test_h3_inside_a_pre_is_left_alone(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = (
        "<h2>Coding Advice</h2><h3>Real</h3><h3>Second</h3>"
        "<pre><code>&lt;h3&gt;not a heading&lt;/h3&gt;</code></pre>"
    )
    study = scaffold(tmp_path / "00-preh3", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "&lt;h3&gt;not a heading&lt;/h3&gt;" in page
    assert "not-a-heading" not in page


def test_h3_slug_cannot_steal_a_section_anchor(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["05-findings.html"] = "<h2>Findings</h2><h3>Findings</h3><h3>Surprises</h3>"
    study = scaffold(tmp_path / "00-collide", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert '<h3 id="findings-2">' in page
    assert '<section id="findings">' in page


def test_anchor_ids_are_deterministic_and_stable_under_append(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = TWO_H3
    study = scaffold(tmp_path / "00-stable", fragments=frags)
    assert build_module.main([str(study)]) == 0
    first = (study / "report" / "index.html").read_bytes()
    assert build_module.main([str(study)]) == 0
    assert (study / "report" / "index.html").read_bytes() == first

    section = study / "report" / "sections" / "06-coding-advice.html"
    section.write_text(TWO_H3 + "<h3>Added later</h3>", encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert '<h3 id="read-the-floor-from-the-contract">' in page
    assert '<h3 id="print-every-guardrail">' in page
    assert '<h3 id="added-later">' in page
