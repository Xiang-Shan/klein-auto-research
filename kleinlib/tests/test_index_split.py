"""Index-table and predefined splits (Klein 2.3): non-tabular studies get a REAL split check.

Before 2.3, an image / text / sequence / graph study had no feature frame to hand
the splitter, so the DATA gate stored a ``[WARN] realized split fingerprints not
recorded`` note and every run proceeded "partition not verified".  With
``data.split.index`` (a table inside the prepared directory) and
``kind: predefined`` (official partitions), the gate freezes fingerprints over
ITEM IDS and run-one enforces them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from test_workflow_v3 import _fill, commit_all, git

from kleinlib.contract import load_contract, validate_contract
from kleinlib.data import contract_split, load_items, partition_fingerprints, split_fingerprint
from kleinlib.scaffold import scaffold_study
from kleinlib.state import load_state, record_gate
from kleinlib.workflow import run_one


def _write_index(prepared: Path, *, n: int = 40, predefined: bool = False, dup: bool = False) -> None:
    prepared.mkdir(parents=True, exist_ok=True)
    rows = ["id,label,split" if predefined else "id,label"]
    for i in range(n):
        item = f"img{i:03d}"
        label = i % 2
        if predefined:
            part = "train" if i < n * 0.6 else ("development" if i < n * 0.8 else "test")
            rows.append(f"{item},{label},{part}")
        else:
            rows.append(f"{item},{label}")
    if dup:
        rows.append("img000,0")
    (prepared / "index.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    np.save(prepared / "images.npy", np.arange(n * 4, dtype=np.uint8).reshape(n, 2, 2))


def _image_study(tmp_path: Path, split: dict) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies",
        "03-images",
        goal="classify images",
        domain="test",
        target="label",
        task_type="classification",
        method_depth="brief",
        family="cnn",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
        data_path="data/prepared",
        max_run_seconds=5,
        schema_version=3,
        kind="predict",
        modality="image",
        profile="generic",
        audience="the maintainers of this test suite",
    )
    _fill(study)
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    contract["data"]["split"] = split
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    return repo, study


RANDOM = {
    "kind": "stratified",
    "seed": 7,
    "development_size": 0.25,
    "test_size": 0.25,
    "index": "index.csv",
    "id_column": "id",
    "label_column": "label",
}
PREDEFINED = {"kind": "predefined", "index": "index.csv", "label_column": "label", "split_column": "split"}


def test_index_split_is_indexed_by_item_ids(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, RANDOM)
    _write_index(study / "data" / "prepared")
    X_tr, X_dev, X_te, y_tr, y_dev, y_te = contract_split(study)
    assert len(X_tr) + len(X_dev) + len(X_te) == 40
    assert all(str(i).startswith("img") for i in X_tr.index)
    assert set(X_tr.index).isdisjoint(X_te.index)
    assert "label" not in X_tr.columns
    prints = partition_fingerprints(study)
    assert prints["development"] == split_fingerprint(X_tr, X_dev)
    assert validate_contract(load_contract(study), study) == []


def test_duplicate_ids_are_refused(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, RANDOM)
    _write_index(study / "data" / "prepared", dup=True)
    with pytest.raises(ValueError, match="duplicate ids"):
        contract_split(study)


def test_predefined_split_uses_the_official_partitions(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, PREDEFINED)
    _write_index(study / "data" / "prepared", predefined=True)
    X_tr, X_dev, X_te, *_ = contract_split(study)
    assert (len(X_tr), len(X_dev), len(X_te)) == (24, 8, 8)
    assert "split" not in X_tr.columns
    assert validate_contract(load_contract(study), study) == []


def test_predefined_split_refuses_unknown_partition_names(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, PREDEFINED)
    prepared = study / "data" / "prepared"
    _write_index(prepared, predefined=True)
    text = (prepared / "index.csv").read_text(encoding="utf-8").replace(",test", ",val")
    (prepared / "index.csv").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="only"):
        contract_split(study)


def test_contract_requires_the_split_column_and_a_stratification_label(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, {"kind": "predefined", "index": "index.csv"})
    assert any("split_column" in p for p in validate_contract(load_contract(study), study))
    bad = dict(RANDOM)
    bad.pop("label_column")
    _, study2 = _image_study(tmp_path / "b", bad)
    assert any("label_column" in p for p in validate_contract(load_contract(study2), study2))
    escape = dict(RANDOM, index="../outside.csv")
    _, study3 = _image_study(tmp_path / "c", escape)
    assert any("data.split.index" in p for p in validate_contract(load_contract(study3), study3))


def test_data_gate_freezes_real_fingerprints_and_run_one_enforces_them(tmp_path: Path) -> None:
    repo, study = _image_study(tmp_path, PREDEFINED)
    _write_index(study / "data" / "prepared", predefined=True)
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    frozen = load_state(study, load_contract(study))["fingerprints"]["split"]
    assert "note" not in frozen, frozen.get("note")
    assert frozen["development"] and frozen["final_test"]
    commit_all(repo, "ready")
    git(repo, "switch", "-q", "-c", "experiments/03-images")

    # An entrypoint that loads its items through the contract prints the right print.
    ids_script = (
        "import json; from kleinlib.data import load_items; "
        "fit, ev = load_items(); "
        "print('primary_metric: 0.7'); print('metric_name: val_auc'); print('metric_goal: higher')"
    )
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 1\n", encoding="utf-8")
    manifest = run_one(study, command=[sys.executable, "-c", ids_script], echo=False)
    assert manifest["disposition"] == "keep", manifest["decision_reason"]
    assert manifest["fingerprints"]["split_partition"] == frozen["development"]

    # A wrong partition is a crash, never a number.
    train.write_text(train.read_text(encoding="utf-8") + "\nCANDIDATE = 2\n", encoding="utf-8")
    wrong = (
        "print('split_fingerprint: deadbeef'); print('primary_metric: 0.9'); "
        "print('metric_name: val_auc'); print('metric_goal: higher')"
    )
    manifest = run_one(study, command=[sys.executable, "-c", wrong], echo=False)
    assert manifest["disposition"] == "crash"
    assert "wrong rows" in manifest["decision_reason"]


def test_load_items_returns_ids(tmp_path: Path, monkeypatch) -> None:
    _, study = _image_study(tmp_path, PREDEFINED)
    _write_index(study / "data" / "prepared", predefined=True)
    fit, ev = load_items("development", study_dir=study, echo=False)
    assert len(fit) == 24 and len(ev) == 8
    fit, ev = load_items("final_test", study_dir=study, echo=False)
    assert len(fit) == 32 and len(ev) == 8
    assert json.dumps(fit)  # plain strings


def _with_policy(study: Path, **policy: str) -> None:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    contract["policy"] = policy
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


def test_policy_validation(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, PREDEFINED)
    _with_policy(study, card_sections="enforce", realized_split="required")
    assert validate_contract(load_contract(study), study) == []
    _with_policy(study, card_sections="always")
    assert any("policy.card_sections" in p for p in validate_contract(load_contract(study), study))
    _with_policy(study, bogus="x")
    assert any("unknown keys" in p for p in validate_contract(load_contract(study), study))


def test_enforced_card_sections_block_the_data_gate(tmp_path: Path) -> None:
    from kleinlib.errors import WorkflowError

    _, study = _image_study(tmp_path, PREDEFINED)
    _with_policy(study, card_sections="enforce")
    _write_index(study / "data" / "prepared", predefined=True)
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    with pytest.raises(WorkflowError, match="Near-duplicate audit"):
        record_gate(study, "data", acknowledged_by="tester")
    card = "# Data card\n\n" + "".join(
        f"## {name}\n\ntext\n\n"
        for name in (
            "Source & shape",
            "Profile summary",
            "Clean-room leakage audit",
            "Ranked go / no-go issues",
            "Go / no-go",
            "Group policy",
            "Near-duplicate audit",
        )
    ) + "> **Decision:** **GO**\n"
    (study / "data_card.md").write_text(card, encoding="utf-8")
    from kleinlib.state import missing_card_sections

    assert missing_card_sections(load_contract(study), card) == []
    record_gate(study, "data", acknowledged_by="tester")


def test_required_realized_split_refuses_an_unrealizable_split(tmp_path: Path) -> None:
    from kleinlib.errors import WorkflowError

    _, study = _image_study(tmp_path, PREDEFINED)
    _with_policy(study, realized_split="required")
    prepared = study / "data" / "prepared"
    prepared.mkdir(parents=True)
    (prepared / "index.csv").write_text("id,label\na,0\n", encoding="utf-8")  # no split column
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    record_gate(study, "consult", acknowledged_by="tester")
    with pytest.raises(WorkflowError, match="realized_split"):
        record_gate(study, "data", acknowledged_by="tester")
