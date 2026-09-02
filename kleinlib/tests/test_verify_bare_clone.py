"""E0b — ``klein verify`` on a bare clone.

Two classes of artifact are deliberately never committed: prepared datasets
(``.gitignore``: ``data/``) and unsafe model payloads (``*.joblib`` and friends,
whose manifests say ``committed: false, availability: local``).  Their bytes are
absent in every fresh clone, and before this change the "prepared-data
fingerprint" and "ledger integrity" checks read that absence as damage — so
every shipped study FAILED ``klein verify`` on a machine that was not the
author's.

The rule this module pins: **absence of a policy-local artifact is a ``[WARN]``
with the recorded hash; presence is checked byte-for-byte exactly as before.**
``klein verify --require-local`` restores the strict reading for the CI job that
regenerates the data first.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from kleinlib import cli
from kleinlib.checks import verify_study
from kleinlib.workflow import load_manifests, run_one

GITIGNORE = "**/data/prepared/\n*.joblib\n"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    if _git(repo, "status", "--porcelain") == "":
        return
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )


def _model_command(value: float, *, name: str = "best.joblib") -> list[str]:
    """A metric command that also drops an unsafe model payload, like a real run."""
    return [
        sys.executable,
        "-c",
        "import pathlib; "
        "d = pathlib.Path('models'); d.mkdir(exist_ok=True); "
        f"(d / {name!r}).write_bytes(b'not really a model'); "
        f"print('primary_metric:    {value}'); "
        "print('metric_name:       val_auc'); print('metric_goal:       higher')",
    ]


@pytest.fixture
def bare_clone_study(ready_study) -> tuple[Path, Path]:
    """``ready_study`` with the repository's real ignore policy, one kept run.

    The scaffolded fixture commits everything; the shipped repository does not.
    Untrack the prepared data (and ignore model payloads) so the study on disk
    matches what a `git clone` of this repository actually hands a stranger.
    """
    repo, study = ready_study
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    _git(repo, "rm", "-r", "-q", "--cached", "--", "studies/03-demo/data/prepared")
    _commit(repo, "ignore prepared data and model payloads")

    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = True\n", encoding="utf-8")
    run_one(study, command=_model_command(0.9), echo=False)
    assert _git(repo, "status", "--porcelain") == ""
    return repo, study


def _named(checks, name: str):
    return next(check for check in checks if check.name == name)


def test_full_checkout_verifies_identically_with_and_without_require_local(
    bare_clone_study,
) -> None:
    """Presence changes nothing: the byte checks run exactly as they did before."""
    _, study = bare_clone_study
    relaxed = verify_study(study)
    strict = verify_study(study, require_local=True)
    assert [(c.name, c.ok, c.message) for c in relaxed] == [
        (c.name, c.ok, c.message) for c in strict
    ]
    assert all(check.ok for check in relaxed), [c.message for c in relaxed if not c.ok]
    assert "[WARN]" not in _named(relaxed, "prepared-data fingerprint").message
    assert _named(relaxed, "ledger integrity").message == "derived view matches manifests"


def test_absent_policy_local_artifacts_warn_with_their_recorded_hashes(
    bare_clone_study,
) -> None:
    """The bare-clone case: nothing on disk, nothing failed, both hashes quoted."""
    _, study = bare_clone_study
    manifest = load_manifests(study)[0]
    model_rel = next(rel for rel in manifest["artifacts"] if rel.endswith(".joblib"))
    model_sha = manifest["artifacts"][model_rel]["sha256"]
    assert manifest["artifacts"][model_rel]["committed"] is False
    assert manifest["artifacts"][model_rel]["availability"] == "local"
    data_sha = json.loads((study / "study_state.json").read_text(encoding="utf-8"))[
        "fingerprints"
    ]["data"]

    (study / "data" / "prepared" / "fixture.csv").unlink()
    (study / model_rel).unlink()

    checks = verify_study(study)
    assert all(check.ok for check in checks), [c.message for c in checks if not c.ok]

    prepared = _named(checks, "prepared-data fingerprint")
    assert prepared.message.startswith("[WARN] local artifact absent (not committed by policy)")
    assert data_sha in prepared.message
    assert "re-run prepare.py" in prepared.message

    ledger = _named(checks, "ledger integrity")
    assert ledger.message.startswith("[WARN] ")
    assert "local artifact absent (not committed by policy)" in ledger.message
    assert model_rel in ledger.message
    assert model_sha in ledger.message


def test_require_local_restores_the_strict_failure_on_absence(bare_clone_study) -> None:
    _, study = bare_clone_study
    manifest = load_manifests(study)[0]
    model_rel = next(rel for rel in manifest["artifacts"] if rel.endswith(".joblib"))
    (study / "data" / "prepared" / "fixture.csv").unlink()
    (study / model_rel).unlink()

    checks = verify_study(study, require_local=True)
    prepared = _named(checks, "prepared-data fingerprint")
    ledger = _named(checks, "ledger integrity")
    assert not prepared.ok and "prepared data does not exist" in prepared.message
    assert not ledger.ok and f"local artifact missing: {model_rel}" in ledger.message


def test_a_present_but_tampered_local_artifact_still_fails_either_way(
    bare_clone_study,
) -> None:
    """The relaxation is for absence only — wrong bytes are wrong bytes."""
    _, study = bare_clone_study
    manifest = load_manifests(study)[0]
    model_rel = next(rel for rel in manifest["artifacts"] if rel.endswith(".joblib"))
    (study / model_rel).write_bytes(b"tampered")

    for require_local in (False, True):
        ledger = _named(verify_study(study, require_local=require_local), "ledger integrity")
        assert not ledger.ok
        assert f"local artifact hash mismatch: {model_rel}" in ledger.message


def test_an_absent_tracked_prepared_file_is_still_a_failure(ready_study) -> None:
    """No ignore rule means no policy: a missing tracked file is real damage."""
    _, study = ready_study
    (study / "data" / "prepared" / "fixture.csv").unlink()
    prepared = _named(verify_study(study), "prepared-data fingerprint")
    assert not prepared.ok
    assert "prepared data does not exist" in prepared.message


def test_cli_verify_exposes_require_local(bare_clone_study, capsys) -> None:
    _, study = bare_clone_study
    manifest = load_manifests(study)[0]
    model_rel = next(rel for rel in manifest["artifacts"] if rel.endswith(".joblib"))
    (study / "data" / "prepared" / "fixture.csv").unlink()
    (study / model_rel).unlink()

    assert cli.main(["verify", "--study", str(study)]) == 0
    relaxed = capsys.readouterr().out
    assert "summary: " in relaxed and relaxed.rstrip().endswith("0 failed")
    assert relaxed.count("[WARN] local artifact absent (not committed by policy)") == 1
    assert relaxed.count("local artifact absent (not committed by policy)") == 2

    assert cli.main(["verify", "--study", str(study), "--require-local"]) == 2
    strict = capsys.readouterr().out
    assert strict.rstrip().endswith("2 failed")
