"""Near-duplicate and contamination audits (Klein 2.3): library and ``--index`` CLI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from test_index_split import PREDEFINED, _image_study

from kleinlib.leakage import audit_index, main
from kleinlib.neardup import (
    cross_partition_image_dups,
    dhash,
    dhash_many,
    normalize_text,
    shingles,
    text_contamination,
)


def _images(n: int = 40, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (n, 16, 16, 3), dtype=np.uint8)


def test_dhash_is_stable_and_robust_to_small_noise() -> None:
    images = _images()
    hashes = dhash_many(images)
    assert hashes.dtype == np.uint64 and len(set(hashes.tolist())) == len(images)
    assert dhash(images[3]) == int(hashes[3])
    noisy = np.clip(images[:5].astype(int) + 2, 0, 255)  # a uniform brightness shift
    report = cross_partition_image_dups(dhash_many(noisy), hashes, threshold=4)
    assert report.hits == 5 and report.rate == 1.0
    unrelated = cross_partition_image_dups(dhash_many(_images(10, seed=9)), hashes, threshold=4)
    assert unrelated.hits == 0


def test_dhash_accepts_gray_and_channel_first() -> None:
    gray = _images()[..., 0]
    assert dhash_many(gray).shape == (40,)
    chw = np.moveaxis(_images(), -1, 1)
    assert dhash_many(chw).tolist() == dhash_many(_images()).tolist()


def test_text_contamination_uses_ngrams_and_short_item_equality() -> None:
    assert normalize_text("Hello,  World!") == "hello world"
    assert shingles("a b c", n=13) == {("a", "b", "c")}
    long = " ".join(f"w{i}" for i in range(30))
    report = text_contamination([long, "something else entirely"], ["x " + long[:80]], n=5)
    assert report.hits == 1 and report.examples[0][0] == 0
    short = text_contamination(["What is 2+2?"], ["what is 2 2"], n=13)
    assert short.hits == 1


def test_index_audit_derives_the_split_and_flags_planted_duplicates(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, PREDEFINED)
    prepared = study / "data" / "prepared"
    prepared.mkdir(parents=True)
    n = 40
    rows = ["id,label,split"]
    for i in range(n):
        part = "train" if i < 24 else ("development" if i < 32 else "test")
        rows.append(f"img{i:03d},{i % 2},{part}")
    (prepared / "index.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    images = _images(n)
    np.save(prepared / "images.npy", images)
    clean = audit_index(
        prepared / "index.csv", study_dir=study, near_dup="image", payload=prepared / "images.npy"
    )
    assert all(c.ok for c in clean if c.name.startswith("near-duplicates")), clean
    images[35] = images[2]  # a test image that is a copy of a train image
    np.save(prepared / "images.npy", images)
    planted = audit_index(
        prepared / "index.csv", study_dir=study, near_dup="image", payload=prepared / "images.npy"
    )
    failing = [c for c in planted if c.name.startswith("near-duplicates") and not c.ok]
    assert len(failing) == 1 and "test vs train" in failing[0].name
    tolerant = audit_index(
        prepared / "index.csv",
        study_dir=study,
        near_dup="image",
        payload=prepared / "images.npy",
        max_rate=0.2,
    )
    assert all(c.ok for c in tolerant if c.name.startswith("near-duplicates"))
    code = main(
        [
            "--index",
            str(prepared / "index.csv"),
            "--study",
            str(study),
            "--near-dup",
            "image",
            "--payload",
            str(prepared / "images.npy"),
        ]
    )
    assert code == 1


def test_index_audit_text_contamination_against_a_prompt_pool(tmp_path: Path) -> None:
    _, study = _image_study(tmp_path, PREDEFINED)
    prepared = study / "data" / "prepared"
    prepared.mkdir(parents=True)
    rows = ["id,label,split,question"]
    for i in range(20):
        part = "train" if i < 12 else ("development" if i < 16 else "test")
        rows.append(f"q{i},0,{part},question number {i} about apples and pears please")
    (prepared / "index.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    pool = tmp_path / "fewshot.txt"
    pool.write_text("question number 17 about apples and pears please\n", encoding="utf-8")
    checks = audit_index(
        prepared / "index.csv",
        study_dir=study,
        near_dup="text",
        text_column="question",
        against=pool,
        threshold=8,
    )
    contamination = [c for c in checks if c.name.startswith("contamination")]
    assert len(contamination) == 1 and not contamination[0].ok
    assert "1/8" in contamination[0].message


def test_multiclass_track_gets_a_balanced_accuracy_chance_audit(tmp_path: Path) -> None:
    import subprocess

    from kleinlib.leakage import audit_split
    from kleinlib.scaffold import scaffold_study

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    study = scaffold_study(
        repo / "studies", "03-mc", goal="g", domain="d", target="y", task_type="classification",
        method_depth="brief", family="f", metric_name="val_macro_f1", metric_goal="higher",
        data_source="csv:x.csv", data_path="data/prepared/x.csv", max_run_seconds=5,
        schema_version=3, kind="predict", modality="tabular", profile="generic", audience="tests",
    )
    rng = np.random.default_rng(0)
    rows = ["a,b,y"] + [f"{rng.normal():.4f},{rng.normal():.4f},{['cat','dog','eel'][i % 3]}" for i in range(300)]
    prepared = study / "data" / "prepared"
    prepared.mkdir(parents=True)
    (prepared / "x.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    checks = audit_split(prepared / "x.csv", target="y", study_dir=study)
    chance = [c for c in checks if "chance[" in c.name]
    assert len(chance) == 2 and all(c.ok for c in chance), chance
    assert all("1/K = 0.3333" in c.message for c in chance)
