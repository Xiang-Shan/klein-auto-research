"""Prepare Fashion-MNIST as an image payload + a predefined split index.

Inputs (all four pinned by sha256 in `study.yaml`, resolved through
`kleinlib.sources`, so `KLEIN_OFFLINE=1` refuses the network and a changed remote
file is refused by its pin):

=============================== ===========================================
`data.source`                    train-images-idx3-ubyte.gz (60,000 x 28 x 28)
`data.inputs[0]`                 train-labels-idx1-ubyte.gz (60,000)
`data.inputs[1]`                 t10k-images-idx3-ubyte.gz  (10,000 x 28 x 28)
`data.inputs[2]`                 t10k-labels-idx1-ubyte.gz  (10,000)
=============================== ===========================================

Outputs (`data.prepared_path`, the directory the DATA gate fingerprints):

* `data/prepared/images.npy` — uint8, shape (70000, 28, 28): the 60,000 official
  train images in file order, then the 10,000 official t10k images in file order.
  Row i is the image of index row i. Raw pixel values; the training protocol
  (`lib/protocol.py`) divides by 255.
* `data/prepared/index.csv` — `id, label, split`, LF line endings:
  `tr00000` … `tr59999` for the official train rows and `te00000` … `te09999` for
  the t10k rows. The lanes are POSITIONS, not a seed (`data.split.kind:
  predefined`): train = official train rows 0-49,999; development = official
  train rows 50,000-59,999; test = the official t10k rows (sealed).

The IDX files are parsed with numpy alone (big-endian header, magic 0x0803 for
images and 0x0801 for labels). Nothing here fits, scores or summarizes pixels of
any partition: the sealed rows take part only in the split arithmetic. The output
is byte-deterministic — re-running it reproduces the same two files.
"""

from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from kleinlib.sources import resolve, resolve_inputs

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "prepared"

TRAIN_IMAGES = "train-images-idx3-ubyte.gz"
TRAIN_LABELS = "train-labels-idx1-ubyte.gz"
TEST_IMAGES = "t10k-images-idx3-ubyte.gz"
TEST_LABELS = "t10k-labels-idx1-ubyte.gz"

#: The file identity the official README states; anything else stops the script.
EXPECTED_SHAPES = {
    TRAIN_IMAGES: (60_000, 28, 28),
    TRAIN_LABELS: (60_000,),
    TEST_IMAGES: (10_000, 28, 28),
    TEST_LABELS: (10_000,),
}
N_CLASSES = 10

#: The predefined lanes, by official-train row position (half-open ranges).
TRAIN_ROWS = (0, 50_000)
DEVELOPMENT_ROWS = (50_000, 60_000)

_IDX_UBYTE = 0x08
_IDX_MAGIC = {1: 0x00000801, 3: 0x00000803}


def read_idx(path: Path) -> np.ndarray:
    """One gzip IDX file as a uint8 array of its declared shape."""
    with gzip.open(path, "rb") as stream:
        raw = stream.read()
    if len(raw) < 4 or raw[0] != 0 or raw[1] != 0:
        raise SystemExit(f"{path.name}: not an IDX file (bad magic prefix)")
    if raw[2] != _IDX_UBYTE:
        raise SystemExit(f"{path.name}: IDX element type 0x{raw[2]:02x}, expected unsigned byte 0x08")
    ndim = raw[3]
    magic = int.from_bytes(raw[0:4], "big")
    if _IDX_MAGIC.get(ndim) != magic:
        raise SystemExit(f"{path.name}: unexpected IDX magic 0x{magic:08x} for {ndim} dimension(s)")
    header = 4 + 4 * ndim
    dims = tuple(int.from_bytes(raw[4 + 4 * i : 8 + 4 * i], "big") for i in range(ndim))
    payload = np.frombuffer(raw, dtype=np.uint8, offset=header)
    if payload.size != int(np.prod(dims)):
        raise SystemExit(f"{path.name}: header says {dims} but the payload holds {payload.size} bytes")
    return payload.reshape(dims).copy()


def resolve_files() -> dict[str, Path]:
    """The four pinned files, keyed by their official basenames."""
    contract = yaml.safe_load((HERE / "study.yaml").read_text(encoding="utf-8"))
    offline = os.environ.get("KLEIN_OFFLINE") == "1"
    data = contract["data"]
    resolved = [
        resolve(str(data["source"]), study_dir=HERE, offline=offline, expected_sha256=data.get("sha256")),
        *resolve_inputs(contract, study_dir=HERE, offline=offline),
    ]
    files: dict[str, Path] = {}
    for item in resolved:
        if item.path is None:
            raise SystemExit(f"{item.provenance_line}: resolved to no file")
        files[item.path.name] = item.path
    if set(files) != set(EXPECTED_SHAPES):
        raise SystemExit(f"expected the four Fashion-MNIST files {sorted(EXPECTED_SHAPES)}, got {sorted(files)}")
    return files


def load_arrays(files: dict[str, Path]) -> dict[str, np.ndarray]:
    arrays = {name: read_idx(path) for name, path in files.items()}
    for name, shape in EXPECTED_SHAPES.items():
        if arrays[name].shape != shape:
            raise SystemExit(f"{name}: shape {arrays[name].shape}, expected {shape}")
    for name in (TRAIN_LABELS, TEST_LABELS):
        values = np.unique(arrays[name])
        if values.tolist() != list(range(N_CLASSES)):
            raise SystemExit(f"{name}: label values {values.tolist()}, expected 0..{N_CLASSES - 1}")
    return arrays


def build_index(train_labels: np.ndarray, test_labels: np.ndarray) -> pd.DataFrame:
    n_train, n_test = len(train_labels), len(test_labels)
    split = np.full(n_train, "", dtype=object)
    split[TRAIN_ROWS[0] : TRAIN_ROWS[1]] = "train"
    split[DEVELOPMENT_ROWS[0] : DEVELOPMENT_ROWS[1]] = "development"
    if TRAIN_ROWS[0] != 0 or TRAIN_ROWS[1] != DEVELOPMENT_ROWS[0] or DEVELOPMENT_ROWS[1] != n_train:
        raise SystemExit("the predefined lanes must cover every official train row exactly once")
    return pd.DataFrame(
        {
            "id": [f"tr{i:05d}" for i in range(n_train)] + [f"te{i:05d}" for i in range(n_test)],
            "label": np.concatenate([train_labels, test_labels]).astype(np.int64),
            "split": np.concatenate([split, np.full(n_test, "test", dtype=object)]),
        }
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


#: Pixel-space near-copy rule (DATA gate, 2026-11-03): a held-out image whose
#: pixel-nearest reference differs by at most this many grey levels RMS is a copy.
#: A 64-bit dHash is too coarse for 28x28 silhouettes (56% of held-out images
#: collided, none byte-identical); the same rule is the audit's `--pixel-rmse 4`.
NEAR_COPY_RMSE = 4.0


def drop_near_copies(images: np.ndarray, index: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """Remove development items copied from train, and test items copied from train or
    the kept development items (the sealed run fits on both). Train is never touched."""
    from kleinlib.neardup import pixel_rmse_min

    split = index["split"].to_numpy()
    keep = np.ones(len(index), dtype=bool)
    reference = np.flatnonzero(split == "train")
    for name in ("development", "test"):
        positions = np.flatnonzero(split == name)
        distance = pixel_rmse_min(images[positions], images[reference])
        dropped = positions[distance <= NEAR_COPY_RMSE]
        keep[dropped] = False
        print(f"near-copies dropped from {name}: {len(dropped)} {sorted(index['id'].iloc[dropped].tolist())}")
        reference = np.concatenate([reference, positions[distance > NEAR_COPY_RMSE]])
    return images[keep], index[keep].reset_index(drop=True)


def main() -> None:
    arrays = load_arrays(resolve_files())
    images = np.concatenate([arrays[TRAIN_IMAGES], arrays[TEST_IMAGES]]).astype(np.uint8)
    index = build_index(arrays[TRAIN_LABELS], arrays[TEST_LABELS])
    if len(index) != len(images):
        raise SystemExit("index and payload disagree on the number of items")
    images, index = drop_near_copies(images, index)

    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "images.npy", images, allow_pickle=False)
    index.to_csv(OUT / "index.csv", index=False, lineterminator="\n")

    print(f"prepared {len(index)} images of shape {images.shape[1:]} ({images.dtype}) in {N_CLASSES} classes")
    for name in ("train", "development", "test"):
        part = index[index["split"] == name]
        counts = part["label"].value_counts()
        print(
            f"split {name:<12} n={len(part):>6}  ids {part['id'].iloc[0]}..{part['id'].iloc[-1]}  "
            f"per-class n min={int(counts.min())} max={int(counts.max())}"
        )
    for name in ("images.npy", "index.csv"):
        print(f"wrote data/prepared/{name}  sha256={_sha256(OUT / name)}")


if __name__ == "__main__":
    main()
