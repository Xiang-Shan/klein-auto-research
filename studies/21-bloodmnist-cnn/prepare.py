"""Prepare BloodMNIST items: a payload array + an index table (study 21).

Source: MedMNIST v2 `bloodmnist.npz` (28 x 28 RGB, Zenodo record 10519652), a
`url:` pin with sha256 — resolved and digest-checked by kleinlib.sources before a
byte is read. The dataset ships an OFFICIAL train / val / test split (Yang et al.
2023); it is kept as-is (`data.split.kind: predefined`) with val -> development and
test -> test (sealed).

Writes `data/prepared/images.npy` (row i = the image of index row i, uint8,
shape (N, 28, 28, 3)) and `data/prepared/index.csv` (`id, label, split`). Nothing
is normalized, augmented or resampled here: those are training choices and live in
train.py / model.py.

Cross-split near-duplicates are REMOVED from the evaluation partitions (the DATA
gate found them: the official split is a random image-level split and carries a
handful of byte-identical copies across train / val / test). With the audit's own
rule — 64-bit dHash, Hamming distance <= 4 (kleinlib.neardup) — a development item
is dropped when it has a near-copy in train, and a test item when it has one in
train or in the kept development items. Train is never touched. The dropped ids are
printed, so the run log of prepare.py is the record.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from kleinlib.neardup import dhash_many, hamming_min
from kleinlib.sources import resolve

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "prepared"
PARTS = (("train", "train"), ("val", "development"), ("test", "test"))
NEAR_DUP_BITS = 4  # the leakage audit's default threshold


def main() -> None:
    contract = yaml.safe_load((HERE / "study.yaml").read_text(encoding="utf-8"))
    data = contract["data"]
    source = resolve(
        data["source"], study_dir=HERE, offline=os.environ.get("KLEIN_OFFLINE") == "1",
        expected_sha256=data["sha256"],
    )
    archive = np.load(source.path)
    images, rows = [], []
    for name, partition in PARTS:
        x = archive[f"{name}_images"]
        y = archive[f"{name}_labels"].reshape(-1).astype(int)
        start = sum(len(chunk) for chunk in images)
        images.append(x)
        rows += [
            {"id": f"{name}{i:05d}", "label": int(label), "split": partition}
            for i, label in enumerate(y)
        ]
        assert len(rows) == start + len(y)
    pixels = np.concatenate(images).astype(np.uint8)
    index = pd.DataFrame(rows, columns=["id", "label", "split"])
    hashes = dhash_many(pixels)
    keep = np.ones(len(index), dtype=bool)
    reference = hashes[(index["split"] == "train").to_numpy()]
    for partition in ("development", "test"):
        positions = np.flatnonzero((index["split"] == partition).to_numpy())
        distance, _ = hamming_min(hashes[positions], reference)
        dropped = positions[distance <= NEAR_DUP_BITS]
        keep[dropped] = False
        print(f"near-duplicates dropped from {partition}: {len(dropped)} "
              f"{sorted(index.loc[dropped, 'id'].tolist())}")
        reference = np.concatenate([reference, hashes[positions[distance > NEAR_DUP_BITS]]])
    pixels, index = pixels[keep], index[keep].reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "images.npy", pixels)
    index.to_csv(OUT / "index.csv", index=False, lineterminator="\n")
    counts = index.groupby("split").size().to_dict()
    print(f"prepared {len(index)} images of shape {archive['train_images'].shape[1:]}: {counts}")


if __name__ == "__main__":
    main()
