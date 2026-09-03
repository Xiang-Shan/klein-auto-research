"""E9 — `klein verify`'s receipt, its flags, and its schema posture.

``klein verify`` on a schema-3 study writes ``verify_receipt.json`` and commits
it the way every verb commits the state it generates: a stranger reading the
repository later can see which engine ran the audit, against which bytes, and
what it found.  Schema 2 stays receipt-less and byte-identical.

Pinned here: the receipt's shape and hashes, the commit, the tri-state flags,
the referee-gate and predictions-closure checks Package B's helpers make
possible, the figure re-render, and the promise that studies 03 and 05–09 keep
verifying with 0 failed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from test_commit_state_writes import modified_paths
from test_referee_gate import FINDINGS, close, write_report
from test_registered_mode import amend
from test_workflow_v3 import commit_all, git

from kleinlib import checks, cli
from kleinlib.checks import RECEIPT_NAME, verify_study
from kleinlib.workflow import load_contract, load_state, record_gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def _named(checks, name):
    return [check for check in checks if check.name == name]


def _receipt(study: Path) -> dict:
    return json.loads((study / RECEIPT_NAME).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. the receipt
# ---------------------------------------------------------------------------


def test_schema_3_verify_writes_and_commits_the_receipt(ready_study_v3) -> None:
    repo, study = ready_study_v3
    checks = verify_study(study)
    assert (study / RECEIPT_NAME).is_file()
    assert _named(checks, "verify receipt")[0].message == f"written to {RECEIPT_NAME}"
    # filed by the verb, not left for the operator: the loop contract requires a
    # clean tree at run-one and verify must not be the thing that dirties it.
    assert git(repo, "status", "--porcelain") == ""
    assert RECEIPT_NAME in git(repo, "show", "--name-only", "--format=", "HEAD")


def test_the_receipt_commit_leaves_the_operators_own_edits_alone(
    ready_study_v3, capsys
) -> None:
    """E15: verify files ``verify_receipt.json`` — not the draft beside it.

    The defect: ``klein verify`` on a tree with an in-progress findings edit, a
    program note and a re-rendered figure filed all three under a
    ``klein: verify receipt (…)`` subject, so the receipt described a tree
    nobody had deliberately committed.
    """
    repo, study = ready_study_v3
    (study / "figures").mkdir(exist_ok=True)
    (study / "figures" / "x.png").write_bytes(b"\x89PNG first\n")
    (study / "findings.md").write_text("# Findings\n\nstill a draft\n", encoding="utf-8")
    commit_all(repo, "a draft and a figure")

    # the operator is mid-edit when verify runs
    (study / "findings.md").write_text("# Findings\n\nstill a draft, moving\n", encoding="utf-8")
    (study / "figures" / "x.png").write_bytes(b"\x89PNG second\n")
    program = study / "program.md"
    program.write_text(program.read_text(encoding="utf-8") + "\n- a note\n", encoding="utf-8")

    verify_study(study)

    committed = set(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert committed == {f"studies/03-demo/{RECEIPT_NAME}"}
    assert modified_paths(repo) == {
        "studies/03-demo/findings.md",
        "studies/03-demo/figures/x.png",
        "studies/03-demo/program.md",
    }
    out = capsys.readouterr().out
    assert "note: 3 uncommitted edit(s) left in the tree" in out
    assert "(figures/x.png, findings.md, program.md)" in out
    assert "not part of this commit" in out


def test_the_receipt_records_the_engine_the_head_and_the_bytes(ready_study_v3) -> None:
    repo, study = ready_study_v3
    verify_study(study)
    payload = _receipt(study)
    assert payload["schema"] == 3
    assert payload["study"] == "03-demo"
    assert payload["klein_version"]
    assert payload["timestamp"].endswith("Z")
    assert payload["git_head"] == git(repo, "rev-parse", "HEAD~1")  # before its own commit
    assert payload["inputs"]["study.yaml"] == _sha(study / "study.yaml")
    assert payload["inputs"]["study_state.json"]
    assert set(payload["summary"]) == {"checks", "failed", "warned"}
    assert payload["summary"]["checks"] == len(payload["checks"])
    assert payload["evidence_use_rate"] == 1.0


def _sha(path: Path) -> str:
    from kleinlib.primitives import sha256_file

    return sha256_file(path)


def test_every_check_line_is_on_the_receipt(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    checks = verify_study(study)
    payload = _receipt(study)
    # The receipt records the checks that ran BEFORE it; its own line is the
    # only one it cannot carry (it does not exist until the file is written).
    assert [row["name"] for row in payload["checks"]] == [
        check.name for check in checks if check.name != "verify receipt"
    ]
    assert payload["summary"]["failed"] == sum(not row["ok"] for row in payload["checks"])


def test_the_receipt_hashes_every_run_manifest(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    run = study / "runs" / "E0001"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text('{"experiment": "E0001"}', encoding="utf-8")
    verify_study(study)
    manifests = _receipt(study)["manifests"]
    assert manifests["E0001"] == _sha(run / "manifest.json")


def test_the_receipt_carries_the_three_d14_lists(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    verify_study(study)
    payload = _receipt(study)
    assert payload["uncited_evidence"] == []
    assert payload["undecided_refutations"] == []
    assert payload["single_source_claims"] == []


def test_no_receipt_suppresses_it(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    checks = verify_study(study, receipt=False)
    assert not (study / RECEIPT_NAME).exists()
    assert _named(checks, "verify receipt") == []


def test_schema_2_writes_no_receipt_but_can_be_asked_for_one(ready_study) -> None:
    repo, study = ready_study
    assert not (study / RECEIPT_NAME).exists()
    verify_study(study)
    assert not (study / RECEIPT_NAME).exists()
    verify_study(study, receipt=True)
    payload = _receipt(study)
    assert payload["schema"] == 2
    assert RECEIPT_NAME in git(repo, "show", "--name-only", "--format=", "HEAD")


# ---------------------------------------------------------------------------
# 2. the flags
# ---------------------------------------------------------------------------


def test_the_verify_verb_carries_every_flag_the_docs_promise() -> None:
    parser = cli.build_parser()
    flags = parser._subparsers._group_actions[0].choices["verify"].format_help()
    for flag in (
        "--require-local",
        "--numbers",
        "--claims",
        "--evidence-use",
        "--receipt",
        "--no-receipt",
        "--strict",
    ):
        assert flag in flags, flag


def test_the_new_flags_are_tri_state_so_absence_means_the_schema_default() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["verify"])
    assert (args.numbers, args.claims, args.evidence_use, args.receipt) == (
        None,
        None,
        None,
        None,
    )
    assert args.strict is False
    asked = parser.parse_args(
        ["verify", "--numbers", "--claims", "--evidence-use", "--no-receipt", "--strict"]
    )
    assert (asked.numbers, asked.claims, asked.evidence_use) == (True, True, True)
    assert asked.receipt is False and asked.strict is True


def test_the_cli_threads_every_flag_through(monkeypatch, ready_study_v3, capsys) -> None:
    _repo, study = ready_study_v3
    seen: dict = {}

    def _verify(target, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(cli, "verify_study", _verify)
    assert (
        cli.main(
            [
                "verify",
                "--study",
                str(study),
                "--numbers",
                "--evidence-use",
                "--no-receipt",
                "--strict",
            ]
        )
        == 0
    )
    assert seen == {
        "require_local": False,
        "numbers": True,
        "claims": None,
        "evidence": True,
        "strict": True,
        "receipt": False,
    }


# ---------------------------------------------------------------------------
# 3. the numbers scan, through verify
# ---------------------------------------------------------------------------


def test_an_unsourced_findings_numeral_fails_a_schema_3_verify(ready_study_v3) -> None:
    repo, study = ready_study_v3
    (study / "findings.md").write_text(
        "# Findings\n\nThe anchor improved by 0.004733 — exploratory.\n", encoding="utf-8"
    )
    commit_all(repo, "a numeral from nowhere")
    check = _named(verify_study(study, receipt=False), "findings numbers")[0]
    assert check.ok is False
    assert "0.004733" in check.message
    assert "klein:numbers-ok" in check.message


def test_the_marker_is_the_documented_way_out(ready_study_v3) -> None:
    repo, study = ready_study_v3
    (study / "findings.md").write_text(
        "# Findings\n\nAvogadro is 6.02214076e23 "
        "<!-- klein:numbers-ok: an SI definition, not a measurement -->\n"
        "The study is exploratory.\n",
        encoding="utf-8",
    )
    commit_all(repo, "an exempted numeral")
    assert _named(verify_study(study, receipt=False), "findings numbers")[0].ok is True


def test_the_tutorial_pass_never_fails_a_study(ready_study_v3) -> None:
    repo, study = ready_study_v3
    (study / "findings.md").write_text("# Findings\n\nexploratory.\n", encoding="utf-8")
    (study / "report").mkdir(exist_ok=True)
    (study / "report" / "index.html").write_text(
        "<p>the anchor scored 0.987654</p>", encoding="utf-8"
    )
    commit_all(repo, "a tutorial with a homeless numeral")
    check = _named(verify_study(study, receipt=False, strict=True), "tutorial numbers")[0]
    assert check.ok is True
    assert "advisory" in check.message and "0.987654" in check.message


def test_schema_2_numbers_are_silent_by_default_and_advisory_when_asked(ready_study) -> None:
    repo, study = ready_study
    (study / "findings.md").write_text(
        "# Findings\n\nThe gap was 0.004733.\n", encoding="utf-8"
    )
    commit_all(repo, "schema-2 findings")
    assert _named(verify_study(study), "findings numbers") == []
    asked = _named(verify_study(study, numbers=True), "findings numbers")[0]
    assert asked.ok is True
    assert "advisory on schema 2" in asked.message


# ---------------------------------------------------------------------------
# 4. the referee gate and predictions closure (Package B's helpers)
# ---------------------------------------------------------------------------


def test_an_unrefereed_study_still_in_the_loop_is_only_warned(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    check = _named(verify_study(study, receipt=False), "referee gate")[0]
    assert check.ok is True
    assert "[WARN] not yet refereed" in check.message


def test_a_recorded_gate_is_reported_with_its_independence_rung(ready_study_v3) -> None:
    repo, study = ready_study_v3
    write_report(study, verdict="PASS-WITH-NOTES", referee="R (opus)", independent="yes")
    commit_all(repo, "referee report")
    record_gate(study, "referee", acknowledged_by="tester")
    check = _named(verify_study(study, receipt=False), "referee gate")[0]
    assert check.ok is True
    assert "PASS-WITH-NOTES" in check.message
    assert "independent-of-experimenter: yes" in check.message


def test_finalized_with_no_gate_and_no_disclosed_reason_fails(ready_study_v3) -> None:
    repo, study = ready_study_v3
    (study / "findings.md").write_text(FINDINGS, encoding="utf-8")
    commit_all(repo, "findings")
    close(study, no_referee=True, referee_reason="solo session, disclosed")
    assert _named(verify_study(study, receipt=False), "referee gate")[0].ok is True

    # Now strip the disclosure the way a hand-edited receipt would.
    state_path = study / "study_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["finalization"].pop("referee")
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    commit_all(repo, "the disclosure removed")
    check = _named(verify_study(study, receipt=False), "referee gate")[0]
    assert check.ok is False
    assert "no recorded --no-referee reason" in check.message


def test_open_predictions_are_listed(ready_study_v3) -> None:
    repo, study = ready_study_v3
    amend(
        study,
        lambda c: c.update(predictions=[{"id": "P1", "statement": "it clears 0.6"}]),
        note="one prediction",
    )
    commit_all(repo, "a registered prediction")
    check = _named(verify_study(study, receipt=False), "predictions closure")[0]
    assert check.ok is True
    assert "[WARN] 1 open: P1" in check.message


def test_the_referee_and_prediction_checks_are_silent_on_schema_2(ready_study) -> None:
    _repo, study = ready_study
    checks = verify_study(study)
    assert _named(checks, "referee gate") == []
    assert _named(checks, "predictions closure") == []
    assert _named(checks, "belief revision") == []


# ---------------------------------------------------------------------------
# 5. the figure re-render (referee rubric item 9)
# ---------------------------------------------------------------------------

RENDERER = '''\
import argparse, pathlib
p = argparse.ArgumentParser()
p.add_argument("--study", required=True)
p.add_argument("--out", required=True)
a = p.parse_args()
out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / "exhibit.png").write_bytes({payload!r})
'''


def _renderer(study: Path, payload: bytes) -> None:
    figures = study / "figures"
    figures.mkdir(exist_ok=True)
    (figures / "make_figures.py").write_text(RENDERER.format(payload=payload), encoding="utf-8")


def test_a_deterministic_renderer_passes(ready_study_v3) -> None:
    repo, study = ready_study_v3
    _renderer(study, b"deterministic bytes")
    (study / "figures" / "exhibit.png").write_bytes(b"deterministic bytes")
    commit_all(repo, "figures")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "1 figure(s) re-render byte-identically" in check.message


def test_a_figure_whose_bytes_move_fails(ready_study_v3) -> None:
    repo, study = ready_study_v3
    _renderer(study, b"today's bytes")
    (study / "figures" / "exhibit.png").write_bytes(b"yesterday's bytes")
    commit_all(repo, "figures that drifted")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is False
    assert "exhibit.png" in check.message


def test_a_renderer_with_no_out_flag_is_warned_never_run(ready_study_v3) -> None:
    repo, study = ready_study_v3
    figures = study / "figures"
    figures.mkdir(exist_ok=True)
    (figures / "make_figures.py").write_text(
        "raise SystemExit('this must never run — it would overwrite the evidence')\n",
        encoding="utf-8",
    )
    commit_all(repo, "an in-place renderer")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "takes no --out" in check.message


def test_a_renderer_that_crashes_is_a_warning_not_a_failure(ready_study_v3) -> None:
    repo, study = ready_study_v3
    figures = study / "figures"
    figures.mkdir(exist_ok=True)
    (figures / "make_figures.py").write_text(
        "import sys\n"
        "# --out is advertised, but the plotting stack is missing on this machine\n"
        "raise SystemExit('ModuleNotFoundError: matplotlib')\n",
        encoding="utf-8",
    )
    commit_all(repo, "a renderer that cannot run here")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "[WARN]" in check.message


def test_no_renderer_means_no_line(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    assert _named(verify_study(study, receipt=False), "figure re-render") == []


def _png(path: Path, pixel: tuple[int, int, int], *, compress_level: int) -> None:
    from PIL import Image

    image = Image.new("RGB", (8, 8), pixel)
    image.save(path, format="PNG", compress_level=compress_level)


def test_the_same_pixels_through_another_png_encoder_pass(ready_study_v3, tmp_path: Path) -> None:
    """macOS and Linux link different zlibs: same image, different bytes."""
    repo, study = ready_study_v3
    rendered = tmp_path / "rendered.png"
    _png(rendered, (10, 20, 30), compress_level=9)
    _renderer(study, rendered.read_bytes())
    (study / "figures").mkdir(exist_ok=True)
    _png(study / "figures" / "exhibit.png", (10, 20, 30), compress_level=1)
    assert (study / "figures" / "exhibit.png").read_bytes() != rendered.read_bytes()
    commit_all(repo, "figures re-encoded")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "pixel-identical through a different PNG encoder (exhibit.png)" in check.message


def _drifted_pixels(ready_study_v3, tmp_path: Path) -> tuple[Path, Path]:
    repo, study = ready_study_v3
    rendered = tmp_path / "rendered.png"
    _png(rendered, (10, 20, 30), compress_level=9)
    _renderer(study, rendered.read_bytes())
    (study / "figures").mkdir(exist_ok=True)
    _png(study / "figures" / "exhibit.png", (11, 20, 30), compress_level=9)
    commit_all(repo, "figures that drifted by one pixel value")
    return repo, study


def test_different_pixels_fail_on_the_platform_that_rendered_them(ready_study_v3, tmp_path: Path, monkeypatch) -> None:
    _repo, study = _drifted_pixels(ready_study_v3, tmp_path)
    monkeypatch.setattr(checks, "_render_platform", lambda _study: ("macos", "arm64"))
    monkeypatch.setattr(checks, "_current_platform", lambda: ("macos", "arm64"))
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is False
    assert "exhibit.png" in check.message
    assert "re-rendered on macos/arm64" in check.message


def test_different_pixels_without_a_fingerprint_fail_too(ready_study_v3, tmp_path: Path, monkeypatch) -> None:
    _repo, study = _drifted_pixels(ready_study_v3, tmp_path)
    monkeypatch.setattr(checks, "_render_platform", lambda _study: None)
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is False


def test_different_pixels_on_another_cpu_family_warn_and_name_both(ready_study_v3, tmp_path: Path, monkeypatch) -> None:
    """study 12's Lorenz curve moved a pixel between arm64 and x86_64; the law holds where it can."""
    _repo, study = _drifted_pixels(ready_study_v3, tmp_path)
    monkeypatch.setattr(checks, "_render_platform", lambda _study: ("macos", "arm64"))
    monkeypatch.setattr(checks, "_current_platform", lambda: ("linux", "x86_64"))
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "[WARN]" in check.message
    assert "exhibit.png" in check.message
    assert "different pixels on linux/x86_64" in check.message
    assert "rendered on macos/arm64" in check.message
    assert "0 of 1 figure(s) re-render identically here" in check.message


IN_PLACE_RENDERER = '''\
import argparse, pathlib
p = argparse.ArgumentParser()
p.add_argument("--study", required=True)
p.add_argument("--out", required=True)
a = p.parse_args()
out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / "exhibit.png").write_bytes({payload!r})
# the engine's trajectory plotter wrote into <study>/figures regardless of --out (until 2.1)
(pathlib.Path(a.study) / "figures" / "trajectory.png").write_bytes({in_place!r})
if {stray!r}:
    (pathlib.Path(a.study) / "figures" / "stray.txt").write_bytes(b"left behind")
'''


def _in_place_renderer(study: Path, payload: bytes, in_place: bytes, *, stray: bool = False) -> None:
    figures = study / "figures"
    figures.mkdir(exist_ok=True)
    (figures / "make_figures.py").write_text(
        IN_PLACE_RENDERER.format(payload=payload, in_place=in_place, stray=stray), encoding="utf-8"
    )


def test_an_in_place_rewrite_with_the_same_bytes_is_invisible(ready_study_v3) -> None:
    repo, study = ready_study_v3
    _in_place_renderer(study, b"exhibit bytes", b"trajectory bytes")
    (study / "figures" / "exhibit.png").write_bytes(b"exhibit bytes")
    (study / "figures" / "trajectory.png").write_bytes(b"trajectory bytes")
    commit_all(repo, "figures, one of them written in place by the script")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "1 figure(s) re-render byte-identically" in check.message
    assert "in place" not in check.message
    assert (study / "figures" / "trajectory.png").read_bytes() == b"trajectory bytes"


def test_a_stray_file_the_script_leaves_in_figures_is_named_and_removed(ready_study_v3) -> None:
    repo, study = ready_study_v3
    _in_place_renderer(study, b"exhibit bytes", b"trajectory bytes", stray=True)
    (study / "figures" / "exhibit.png").write_bytes(b"exhibit bytes")
    (study / "figures" / "trajectory.png").write_bytes(b"trajectory bytes")
    commit_all(repo, "figures")
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is True
    assert "[WARN] re-rendered but never committed: stray.txt" in check.message
    assert "wrote 1 file(s) into figures/ in place" in check.message
    assert not (study / "figures" / "stray.txt").exists()


def test_an_in_place_rewrite_that_drifts_fails_and_is_restored(ready_study_v3, monkeypatch) -> None:
    repo, study = ready_study_v3
    _in_place_renderer(study, b"exhibit bytes", b"today's trajectory")
    (study / "figures" / "exhibit.png").write_bytes(b"exhibit bytes")
    (study / "figures" / "trajectory.png").write_bytes(b"yesterday's trajectory")
    commit_all(repo, "figures whose in-place one drifted")
    monkeypatch.setattr(checks, "_render_platform", lambda _study: None)
    check = _named(verify_study(study, receipt=False), "figure re-render")[0]
    assert check.ok is False
    assert "trajectory.png" in check.message
    # verify is read-only: the committed bytes are back, the stray file is gone
    assert (study / "figures" / "trajectory.png").read_bytes() == b"yesterday's trajectory"
    assert not (study / "figures" / "stray.txt").exists()


def test_render_platform_reads_the_earliest_manifest_fingerprint(tmp_path: Path) -> None:
    study = tmp_path / "study"
    (study / "runs" / "E0002").mkdir(parents=True)
    (study / "runs" / "E0001").mkdir(parents=True)
    (study / "runs" / "E0002" / "manifest.json").write_text(
        '{"environment": {"platform": "Linux-6.8.0-x86_64-with-glibc2.39", "machine": "x86_64"}}',
        encoding="utf-8",
    )
    (study / "runs" / "E0001" / "manifest.json").write_text(
        '{"environment": {"platform": "macOS-26.5.1-arm64-arm-64bit-Mach-O", "machine": "arm64"}}',
        encoding="utf-8",
    )
    assert checks._render_platform(study) == ("macos", "arm64")
    assert checks._platform_family("Windows-10-10.0.20348-SP0", "AMD64") == ("windows", "amd64")


def test_render_platform_is_none_without_a_fingerprint(tmp_path: Path) -> None:
    study = tmp_path / "study"
    (study / "runs" / "E0001").mkdir(parents=True)
    (study / "runs" / "E0001" / "manifest.json").write_text('{"experiment": "E0001"}', encoding="utf-8")
    assert checks._render_platform(study) is None
    assert checks._render_platform(tmp_path / "nowhere") is None


# ---------------------------------------------------------------------------
# 6. the shipped studies keep verifying, unchanged
# ---------------------------------------------------------------------------

SHIPPED = (
    "03-noisy-rosenbrock-dfo",
    "05-fremtpl2-gap-forensics",
    "06-hurricane-gqls-returnlevels",
    "07-iris-90years",
    "08-iris-rematch",
    "09-iris-first-lesson",
)


@pytest.mark.parametrize("slug", SHIPPED)
def test_a_shipped_schema_2_study_verifies_with_zero_failed_and_no_receipt(slug: str) -> None:
    study = REPO_ROOT / "studies" / slug
    if not (study / "study.yaml").is_file():  # pragma: no cover - a trimmed checkout
        pytest.skip(f"{slug} is not in this checkout")
    checks = verify_study(study)
    assert [check.name for check in checks if not check.ok] == []
    assert not (study / RECEIPT_NAME).exists()
    # none of the schema-3 lines appear at all — the output is byte-identical
    for name in (
        "referee gate",
        "predictions closure",
        "belief revision",
        "evidence use",
        "convergent evidence",
        "findings numbers",
        "tutorial numbers",
        "figure re-render",
        "verify receipt",
    ):
        assert _named(checks, name) == [], name


def test_the_shipped_studies_still_pass_through_the_cli(capsys) -> None:
    study = REPO_ROOT / "studies" / "09-iris-first-lesson"
    if not (study / "study.yaml").is_file():  # pragma: no cover
        pytest.skip("09 is not in this checkout")
    assert cli.main(["verify", "--study", str(study)]) == 0
    printed = capsys.readouterr().out
    assert ", 0 failed" in printed
    assert "verify receipt" not in printed


def test_the_repository_stays_clean_after_verifying_a_shipped_study() -> None:
    """`klein verify` on schema 2 writes nothing, so it cannot dirty the tree."""
    study = REPO_ROOT / "studies" / "09-iris-first-lesson"
    if not (study / "study.yaml").is_file():  # pragma: no cover
        pytest.skip("09 is not in this checkout")
    before = subprocess.run(
        ["git", "status", "--porcelain", "--", str(study)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    verify_study(study)
    after = subprocess.run(
        ["git", "status", "--porcelain", "--", str(study)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert before == after


def test_load_state_and_contract_still_read_a_receipt_bearing_study(ready_study_v3) -> None:
    """The receipt is a sibling file; nothing else in the study notices it."""
    _repo, study = ready_study_v3
    verify_study(study)
    contract = load_contract(study)
    assert load_state(study, contract)["study_id"] == "03-demo"
