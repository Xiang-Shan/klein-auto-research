"""E4 — the partition comes from the contract, and the notary checks it.

War story 8, in full: a study-09 evaluator kept a retired split seed, a whole
ledger lane measured the wrong partition, and nobody noticed until the claims
lock's numeral scan caught it a study later. Three mechanisms close that door and
each is pinned here:

1. ``kleinlib.data.contract_split`` / ``load_partition`` build the partition from
   ``study.yaml`` alone — no argument can change it.
2. The partition PRINTS a fingerprint of its realized membership; the DATA gate
   freezes the expected one; ``klein run-one`` crashes a run whose printed
   fingerprint disagrees.
3. Absence is a notice, never a pass — and preflight says so.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from kleinlib.data import (
    contract_split,
    load_partition,
    partition_fingerprints,
    split_fingerprint,
    three_way_split,
)
from kleinlib.state import registered_partition_fingerprints, split_policy_hash
from kleinlib.workflow import (
    SPLIT_FINGERPRINT_MISMATCH,
    WorkflowError,
    load_state,
    preflight_checks,
    record_gate,
    run_one,
)

ROWS = 60


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    if _git(repo, "status", "--porcelain") == "":
        return
    _git(repo, "-c", "user.name=T", "-c", "user.email=t@e.invalid", "commit", "-q", "-m", message)


def _write_frame(study: Path) -> None:
    frame = pd.DataFrame(
        {
            "x": range(ROWS),
            "y": [i % 2 for i in range(ROWS)],
        }
    )
    path = study / "data" / "prepared" / "fixture.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


@pytest.fixture
def split_study(ready_study_v3) -> tuple[Path, Path]:
    """``ready_study_v3`` with enough rows to actually split, gates re-recorded."""
    repo, study = ready_study_v3
    _write_frame(study)
    record_gate(study, "data", acknowledged_by="tester")
    _commit(repo, "sixty rows and a frozen split")
    return repo, study


def _entrypoint(study: Path, *, value: float, fingerprint: str | None = None) -> list[str]:
    """A stand-in entrypoint that prints a block plus a chosen fingerprint."""
    lines = [
        f"print('primary_metric:    {value}')",
        "print('metric_name:       val_auc')",
        "print('metric_goal:       higher')",
    ]
    if fingerprint is not None:
        lines.append(f"print('split_fingerprint: {fingerprint}')")
    return [sys.executable, "-c", "; ".join(lines)]


# ---------------------------------------------------------------------------
# 1. the split comes from the contract
# ---------------------------------------------------------------------------


def test_contract_split_reproduces_three_way_split_exactly(split_study) -> None:
    """The helper is a READER of study.yaml, not a second splitter."""
    _, study = split_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    frame = pd.read_csv(study / "data" / "prepared" / "fixture.csv")
    expected = three_way_split(
        frame.drop(columns=["y"]),
        frame["y"],
        task="classification",
        strategy="stratified",
        development_size=0.2,
        test_size=0.2,
        seed=int(contract["data"]["split"]["seed"]),
    )
    got = contract_split(study)
    for expected_part, got_part in zip(expected, got, strict=True):
        assert list(expected_part.index) == list(got_part.index)


def test_load_partition_selects_by_evaluation_kind_and_prints_its_fingerprint(
    split_study, capsys, monkeypatch
) -> None:
    _, study = split_study
    X_tr, X_dev, X_te, _, _, _ = contract_split(study)

    monkeypatch.setenv("KLEIN_EVALUATION_KIND", "development")
    fit_X, eval_X, _, _ = load_partition(study_dir=study)
    printed = capsys.readouterr().out
    assert list(fit_X.index) == list(X_tr.index)
    assert list(eval_X.index) == list(X_dev.index)
    assert f"split_fingerprint: {split_fingerprint(X_tr, X_dev)}" in printed

    monkeypatch.setenv("KLEIN_EVALUATION_KIND", "final_test")
    fit_X, eval_X, _, _ = load_partition(study_dir=study)
    printed = capsys.readouterr().out
    # The sealed run fits on the frozen chosen configuration's training data.
    assert list(eval_X.index) == list(X_te.index)
    assert sorted(fit_X.index) == sorted([*X_tr.index, *X_dev.index])
    assert f"split_fingerprint: {split_fingerprint(fit_X, X_te)}" in printed


def test_load_partition_refuses_an_invented_evaluation_kind(split_study) -> None:
    _, study = split_study
    with pytest.raises(ValueError, match="invalid evaluation kind"):
        load_partition("peek", study_dir=study)


def test_the_fingerprint_is_membership_not_order(split_study) -> None:
    _, study = split_study
    X_tr, X_dev, _, _, _, _ = contract_split(study)
    assert split_fingerprint(X_tr, X_dev) == split_fingerprint(X_tr.iloc[::-1], X_dev)
    # ... but which partition is which still matters.
    assert split_fingerprint(X_tr, X_dev) != split_fingerprint(X_dev, X_tr)
    # ... and one different row changes it.
    assert split_fingerprint(X_tr, X_dev) != split_fingerprint(X_tr, X_dev.iloc[1:])


# ---------------------------------------------------------------------------
# 2. the gate freezes it, and a policy change afterwards is refused
# ---------------------------------------------------------------------------


def test_the_data_gate_freezes_policy_and_realized_fingerprints(split_study) -> None:
    _, study = split_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    state = load_state(study, contract)
    registered = registered_partition_fingerprints(state)
    assert registered == partition_fingerprints(study)
    assert isinstance(split_policy_hash(state), str)


def test_a_split_policy_change_after_evidence_is_refused(split_study) -> None:
    repo, study = split_study
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    run_one(
        study,
        command=_entrypoint(study, value=0.7, fingerprint=partition_fingerprints(study)["development"]),
        echo=False,
    )

    path = study / "study.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("seed: 42", "seed: 7"), encoding="utf-8")
    _commit(repo, "retire the split seed mid-study")
    with pytest.raises(WorkflowError, match="data.split changed after evidence exists"):
        record_gate(study, "data", acknowledged_by="tester")


# ---------------------------------------------------------------------------
# 3. run-one enforces it
# ---------------------------------------------------------------------------


def test_a_run_on_the_wrong_partition_is_a_crash_not_a_discard(split_study) -> None:
    """A number computed on the wrong rows is not evidence in either direction."""
    _, study = split_study
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_entrypoint(study, value=0.99, fingerprint="f" * 64), echo=False)
    assert manifest["disposition"] == "crash"
    assert SPLIT_FINGERPRINT_MISMATCH in manifest["decision_reason"]
    # A crash records no metric, however good the number looked.
    assert manifest["primary_metric"] is None


def test_the_registered_partition_is_accepted_and_recorded(split_study) -> None:
    _, study = split_study
    fingerprint = partition_fingerprints(study)["development"]
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_entrypoint(study, value=0.7, fingerprint=fingerprint), echo=False)
    assert manifest["disposition"] == "keep"
    assert manifest["fingerprints"]["split_partition"] == fingerprint


def test_a_run_that_prints_no_fingerprint_proceeds_with_a_notice(split_study, capsys) -> None:
    """Silence is not a pass, but neither is it a lie: the run is recorded."""
    _, study = split_study
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=_entrypoint(study, value=0.7), echo=True)
    assert manifest["disposition"] == "keep"
    assert "note: partition not verified" in capsys.readouterr().out
    assert "split_partition" not in manifest["fingerprints"]


# ---------------------------------------------------------------------------
# 4. preflight says whether the door is actually closed
# ---------------------------------------------------------------------------


def test_preflight_warns_when_no_source_asks_the_contract_for_a_partition(
    split_study,
) -> None:
    _, study = split_study
    check = next(c for c in preflight_checks(study) if c.name == "contract-driven split")
    assert check.ok  # advisory: a verifier-only study has no row partitions
    assert "[WARN] no study source calls" in check.message
    assert "war story 8" in check.message


def test_preflight_reports_the_registered_fingerprints_once_a_source_uses_them(
    split_study,
) -> None:
    repo, study = split_study
    train = study / "train.py"
    train.write_text(
        "from kleinlib.data import load_partition\n\nload_partition()\n", encoding="utf-8"
    )
    _commit(repo, "route the partition through the contract")
    check = next(c for c in preflight_checks(study) if c.name == "contract-driven split")
    assert check.ok
    assert "[WARN]" not in check.message
    assert "train.py" in check.message
    assert "development=" in check.message and "final_test=" in check.message


def test_schema_2_never_sees_the_contract_split_check(ready_study) -> None:
    _, study = ready_study
    assert not [c for c in preflight_checks(study) if c.name == "contract-driven split"]
