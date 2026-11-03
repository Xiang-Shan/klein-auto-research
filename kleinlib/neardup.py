"""Near-duplicate and contamination audits for non-tabular evidence (Klein 2.3).

Exact-id and exact-group overlap (``kleinlib.leakage --index``) cannot see the leak
that makes most image and text benchmarks look better than they are: the SAME
item under two ids — a re-encoded photo, a crop, a lightly edited sentence, a
benchmark question that also sits in the few-shot pool.  This module measures
that, with no dependency beyond numpy (and Pillow, already installed with
matplotlib, for image resizing):

* **images** — a 64-bit difference hash (dHash) per image; two images whose
  hashes differ in at most ``threshold`` bits are near-duplicates.  Hashes are
  compared across partitions with uint64 XOR and a popcount.
* **text** — normalized word n-gram shingles (13-grams by default, the length
  used in published contamination analyses); an evaluation item is contaminated
  when it shares any n-gram with the reference pool (the training partition, a
  few-shot exemplar pool, a prompt template).  Items shorter than ``n`` words
  are compared by their whole normalized text.

The numbers these functions return go on the data card under
``## Near-duplicate audit`` / ``## Contamination audit`` with the threshold that
produced them.  They are measurements, not verdicts: the card states the rate
and the threshold, and a rate above the study's declared maximum is a BLOCKER.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

__all__ = [
    "DEFAULT_NGRAM",
    "DEFAULT_THRESHOLD",
    "NearDupReport",
    "cross_partition_image_dups",
    "dhash",
    "dhash_many",
    "hamming_min",
    "normalize_text",
    "shingles",
    "text_contamination",
]

#: Bits of difference at or below which two 64-bit dHashes count as the same image.
DEFAULT_THRESHOLD = 4

#: Word n-gram length for text contamination.
DEFAULT_NGRAM = 13


@dataclass(frozen=True)
class NearDupReport:
    """Items of ``query`` that have a near-duplicate in ``reference``."""

    query_n: int
    reference_n: int
    hits: int
    threshold: float
    examples: tuple[tuple[int, int, float], ...]  # (query_pos, reference_pos, distance)

    @property
    def rate(self) -> float:
        return self.hits / self.query_n if self.query_n else 0.0


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------


_LUMA = np.array([0.299, 0.587, 0.114])


def _to_gray_batch(images: np.ndarray) -> np.ndarray:
    """``(N, H, W)`` float gray images from (N,H,W), (N,H,W,C) or (N,C,H,W)."""
    array = np.asarray(images, dtype=np.float64)
    if array.ndim == 3:
        return array
    if array.ndim == 4:
        if array.shape[-1] in (3, 4):
            return array[..., :3] @ _LUMA
        if array.shape[-1] == 1:
            return array[..., 0]
        if array.shape[1] in (1, 3):  # channel-first
            moved = np.moveaxis(array, 1, -1)
            return moved[..., 0] if moved.shape[-1] == 1 else moved @ _LUMA
        return array.mean(axis=-1)
    raise ValueError(f"images must be (N,H,W) or (N,H,W,C), got shape {array.shape}")


def _bin_mean(array: np.ndarray, axis: int, size: int) -> np.ndarray:
    """Mean over ``size`` contiguous, non-overlapping bins along ``axis`` (nearest if upsampling)."""
    length = array.shape[axis]
    if length >= size:
        starts = (np.arange(size) * length) // size
        sums = np.add.reduceat(array, starts, axis=axis)
        counts = np.diff(np.append(starts, length))
        shape = [1] * array.ndim
        shape[axis] = size
        return sums / counts.reshape(shape)
    picks = np.minimum((np.arange(size) * length) // size, length - 1)
    return np.take(array, picks, axis=axis)


def dhash_many(images: Iterable[np.ndarray] | np.ndarray, hash_size: int = 8) -> np.ndarray:
    """64-bit difference hash of every image, as a uint64 array.

    Each image is reduced to ``hash_size`` x ``hash_size + 1`` grey bins (exact
    box means over contiguous pixel blocks — deterministic, numpy only); bit
    ``k`` says whether a bin is brighter than its right neighbour.
    """
    if not isinstance(images, np.ndarray):
        images = np.stack([np.asarray(image) for image in images])
    if images.ndim == 2:
        images = images[None]
    gray = _to_gray_batch(images)
    small = _bin_mean(_bin_mean(gray, 1, hash_size), 2, hash_size + 1)
    bits = (small[:, :, 1:] > small[:, :, :-1]).reshape(len(gray), -1)
    weights = np.left_shift(np.uint64(1), np.arange(bits.shape[1] - 1, -1, -1, dtype=np.uint64))
    return (bits.astype(np.uint64) * weights).sum(axis=1, dtype=np.uint64)


def dhash(image: np.ndarray, hash_size: int = 8) -> int:
    """64-bit difference hash of one image (see :func:`dhash_many`)."""
    array = np.asarray(image)
    if array.ndim == 3 and array.shape[-1] not in (1, 3, 4) and array.shape[0] in (1, 3):
        array = np.moveaxis(array, 0, -1)
    return int(dhash_many(array[None], hash_size)[0])


def _popcount(values: np.ndarray) -> np.ndarray:
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(values)
    # numpy < 2.0 fallback: byte-wise lookup.
    as_bytes = values.view(np.uint8).reshape(values.shape + (8,))
    table = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)
    return table[as_bytes].sum(axis=-1)


def hamming_min(query: np.ndarray, reference: np.ndarray, *, chunk: int = 4096) -> tuple[np.ndarray, np.ndarray]:
    """For each query hash: (min Hamming distance to any reference hash, its position)."""
    query = np.asarray(query, dtype=np.uint64)
    reference = np.asarray(reference, dtype=np.uint64)
    best = np.full(query.shape[0], 65, dtype=np.int64)
    where = np.full(query.shape[0], -1, dtype=np.int64)
    if reference.size == 0:
        return best, where
    for start in range(0, query.shape[0], chunk):
        block = query[start : start + chunk, None] ^ reference[None, :]
        distances = _popcount(block).astype(np.int64)
        best[start : start + chunk] = distances.min(axis=1)
        where[start : start + chunk] = distances.argmin(axis=1)
    return best, where


def cross_partition_image_dups(
    query_hashes: np.ndarray,
    reference_hashes: np.ndarray,
    *,
    threshold: int = DEFAULT_THRESHOLD,
    examples: int = 5,
) -> NearDupReport:
    """How many query images have a reference image within ``threshold`` bits."""
    best, where = hamming_min(query_hashes, reference_hashes)
    hit_positions = np.flatnonzero(best <= threshold)
    sample = tuple(
        (int(pos), int(where[pos]), float(best[pos])) for pos in hit_positions[:examples]
    )
    return NearDupReport(
        query_n=int(len(query_hashes)),
        reference_n=int(len(reference_hashes)),
        hits=int(hit_positions.size),
        threshold=float(threshold),
        examples=sample,
    )


# ---------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------

_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def normalize_text(text: Any) -> str:
    """Lowercase, punctuation stripped, whitespace collapsed."""
    lowered = str(text).lower()
    return _SPACE.sub(" ", _NON_WORD.sub(" ", lowered)).strip()


def shingles(text: Any, n: int = DEFAULT_NGRAM) -> set[tuple[str, ...]]:
    """Word n-grams of the normalized text; the whole text as one shingle when shorter."""
    words = normalize_text(text).split()
    if not words:
        return set()
    if len(words) < n:
        return {tuple(words)}
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def text_contamination(
    query: Sequence[Any],
    reference: Sequence[Any],
    *,
    n: int = DEFAULT_NGRAM,
    examples: int = 5,
) -> NearDupReport:
    """How many query texts share at least one n-gram with the reference pool."""
    index: dict[tuple[str, ...], int] = {}
    for position, text in enumerate(reference):
        for gram in shingles(text, n):
            index.setdefault(gram, position)
    hits: list[tuple[int, int, float]] = []
    for position, text in enumerate(query):
        grams = shingles(text, n)
        match = next((index[g] for g in grams if g in index), None)
        if match is not None:
            shared = len(grams & shingles(reference[match], n))
            hits.append((position, match, float(shared)))
    return NearDupReport(
        query_n=len(query),
        reference_n=len(reference),
        hits=len(hits),
        threshold=float(n),
        examples=tuple(hits[:examples]),
    )
