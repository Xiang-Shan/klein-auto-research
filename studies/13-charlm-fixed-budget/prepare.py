"""Prepare the tiny-Shakespeare corpus as a contiguous BLOCK INDEX.

A character language model has no feature table. What the contract can split is
the corpus itself, cut into contiguous blocks of 1024 characters, one row per
block, ordered by character offset. `data.split.kind: time` over `start_char`
then makes the partitions ranges rather than a shuffle — which is the only
honest split for ordered natural language — and Klein's own
`kleinlib.data.contract_split` produces them from `study.yaml` alone.

What this script writes
-----------------------
================================== =============================================
`data/prepared/prepared.csv`        the block table the contract splits
`data/prepared/index.csv`           `id, group, time, split` — the split index
                                    table the mechanized leakage audit reads
`data/prepared/tokens.bin`          the whole corpus as raw uint8 token ids
`data/prepared/vocab.json`          the 65-character vocabulary, index-ordered
`tables/corpus_profile.tsv`         the profile the data card quotes
`tables/near_duplicates.tsv`        cross-partition duplicate / near-duplicate
                                    audit at a stated similarity
`tables/reference_losses.tsv`       two computable reference levels a reader
                                    needs to read a cross-entropy at all
================================== =============================================

The identity anchor
-------------------
The bundled README records 1,115,394 characters, a 65-character vocabulary, and
a sha256 of the decompressed text. This script re-derives all three and STOPS on
any mismatch, before anything else happens: a study that silently trained on a
truncated corpus would produce numbers nobody could compare with anything.

Group policy
------------
`group` in the index table is the sha256 prefix of the block's NORMALIZED text
(casefolded, whitespace collapsed), so the mechanized group-overlap check has
real teeth: it fails if the same passage appears in two partitions under a
cosmetic difference. Exact block duplicates and 8-gram near-duplicates across
partitions are counted separately and reported on the card.

Sealed discipline
-----------------
Nothing here computes a loss, an entropy or any other quantity ON the sealed
partition. The sealed blocks take part only in the split arithmetic and in the
cross-partition leakage audit, which is the one thing the DATA gate must check
on them.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kleinlib.data import contract_split, partition_fingerprints
from kleinlib.sources import resolve

#: One row of the prepared table is this many characters. Small enough that the
#: partitions land within 0.05% of the intended 80/10/10, large enough that a
#: 128-character evaluation window never needs to straddle two blocks.
BLOCK_CHARS = 1024

#: The corpus identity, transcribed from `datasets/tinyshakespeare/README.md`.
EXPECTED_CHARS = 1_115_394
EXPECTED_VOCAB = 65
EXPECTED_TEXT_SHA256 = "86c4e6aa9db7c042ec79f339dcb96d42b0075e16b8fc2e86bf0ca57e2dc565ed"

#: The near-duplicate audit: character n-gram length and the Jaccard similarity
#: above which two blocks are called near-duplicates. Both are stated on the
#: data card because a near-duplicate rate without a threshold means nothing.
NGRAM = 8
NEAR_DUPLICATE_SIMILARITY = 0.5

SOURCE_TAG = "bundled:tinyshakespeare/tinyshakespeare.txt.gz"
PREPARED = Path("data/prepared")
TABLES = Path("tables")


def _normalized(text: str) -> str:
    """Casefold and collapse whitespace — the 'dirty key' a group must survive."""
    return " ".join(text.casefold().split())


def _ngram_codes(block_tokens: np.ndarray, vocab_size: int, n: int = NGRAM) -> frozenset[int]:
    """The block's distinct character n-grams, as base-`vocab_size` integers.

    Deterministic on purpose: Python's `hash()` of a string is salted per
    process, so a near-duplicate rate computed with it would not reproduce.
    With a 65-character vocabulary an 8-gram is at most 65**8 = 3.2e14, well
    inside int64.
    """
    if len(block_tokens) < n:
        return frozenset()
    codes = np.zeros(len(block_tokens) - n + 1, dtype=np.int64)
    for k in range(n):
        codes = codes * vocab_size + block_tokens[k : len(block_tokens) - n + 1 + k].astype(np.int64)
    return frozenset(codes.tolist())


def _max_similarity(target: frozenset[int], pool: list[frozenset[int]]) -> float:
    best = 0.0
    for other in pool:
        inter = len(target & other)
        if not inter:
            continue
        j = inter / (len(target) + len(other) - inter)
        if j > best:
            best = j
    return best


def main() -> int:
    PREPARED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    resolved = resolve(
        SOURCE_TAG, study_dir=Path("."), offline=os.environ.get("KLEIN_OFFLINE") == "1"
    )
    assert resolved.path is not None
    with gzip.open(resolved.path, "rt", encoding="utf-8") as handle:
        text = handle.read()

    # --- the identity anchor: three numbers, and a hard stop on any mismatch --
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    vocab = sorted(set(text))
    problems = []
    if len(text) != EXPECTED_CHARS:
        problems.append(f"characters {len(text)} != {EXPECTED_CHARS}")
    if len(vocab) != EXPECTED_VOCAB:
        problems.append(f"vocabulary {len(vocab)} != {EXPECTED_VOCAB}")
    if digest != EXPECTED_TEXT_SHA256:
        problems.append(f"sha256 {digest} != {EXPECTED_TEXT_SHA256}")
    if problems:
        print("IDENTITY ANCHOR FAILED: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(f"identity anchor OK: {len(text)} characters, {len(vocab)} distinct, sha256 {digest}")

    stoi = {ch: i for i, ch in enumerate(vocab)}
    tokens = np.array([stoi[ch] for ch in text], dtype=np.uint8)
    tokens.tofile(PREPARED / "tokens.bin")
    (PREPARED / "vocab.json").write_text(
        json.dumps({"itos": vocab, "block_chars": BLOCK_CHARS}, ensure_ascii=False),
        encoding="utf-8",
    )

    # --- the block table -----------------------------------------------------
    n_blocks = len(text) // BLOCK_CHARS
    starts = [i * BLOCK_CHARS for i in range(n_blocks)]
    lengths = [BLOCK_CHARS] * n_blocks
    # The trailing remainder joins the LAST block rather than being dropped:
    # every character of the corpus belongs to exactly one partition.
    lengths[-1] = len(text) - starts[-1]
    blocks = [text[s : s + n] for s, n in zip(starts, lengths, strict=True)]

    frame = pd.DataFrame(
        {
            "block_id": range(n_blocks),
            "start_char": starts,
            "n_chars": lengths,
            "n_distinct_chars": [len(set(b)) for b in blocks],
            "content_group": [
                hashlib.sha256(_normalized(b).encode("utf-8")).hexdigest()[:16] for b in blocks
            ],
        }
    )
    frame.to_csv(PREPARED / "prepared.csv", index=False)

    # --- the realized partitions, from the contract and nothing else ---------
    X_train, X_dev, X_test, *_ = contract_split(".")
    label = {}
    for name, part in (("train", X_train), ("development", X_dev), ("test", X_test)):
        for row in part.index:
            label[int(row)] = name
    index = pd.DataFrame(
        {
            "id": [f"b{i:04d}" for i in frame["block_id"]],
            "group": frame["content_group"],
            "time": frame["start_char"],
            "split": [label[i] for i in frame["block_id"]],
        }
    )
    index.to_csv(PREPARED / "index.csv", index=False)

    spans = {}
    for name, part in (("train", X_train), ("development", X_dev), ("test", X_test)):
        ids = sorted(int(i) for i in part.index)
        first, last = ids[0], ids[-1]
        chars = int(frame.loc[ids, "n_chars"].sum())
        contiguous = ids == list(range(first, last + 1))
        spans[name] = (first, last, chars, contiguous)
        print(
            f"partition {name}: blocks {first}-{last} ({len(ids)}), {chars} characters, "
            f"contiguous={contiguous}"
        )
    if not all(span[3] for span in spans.values()):
        print("PARTITIONS ARE NOT CONTIGUOUS — the time split did not order by offset", file=sys.stderr)
        return 1

    # --- duplicates and near-duplicates across partitions --------------------
    grams = [
        _ngram_codes(tokens[s : s + n], len(vocab))
        for s, n in zip(starts, lengths, strict=True)
    ]
    part_ids = {name: sorted(int(i) for i in part.index) for name, part in
                (("train", X_train), ("development", X_dev), ("test", X_test))}
    rows = []
    for later, earlier_names in (("development", ["train"]), ("test", ["train", "development"])):
        pool_ids = [i for name in earlier_names for i in part_ids[name]]
        pool = [grams[i] for i in pool_ids]
        pool_groups = {frame.at[i, "content_group"] for i in pool_ids}
        sims = [_max_similarity(grams[i], pool) for i in part_ids[later]]
        exact = sum(1 for i in part_ids[later] if frame.at[i, "content_group"] in pool_groups)
        near = sum(1 for s in sims if s >= NEAR_DUPLICATE_SIMILARITY)
        rows.append(
            {
                "partition": later,
                "compared_against": "+".join(earlier_names),
                "n_blocks": len(sims),
                "exact_duplicate_blocks": exact,
                "near_duplicate_blocks": near,
                "near_duplicate_rate": round(near / len(sims), 6),
                "max_jaccard": round(max(sims), 6),
                "mean_jaccard": round(float(np.mean(sims)), 6),
                "ngram": NGRAM,
                "similarity_threshold": NEAR_DUPLICATE_SIMILARITY,
            }
        )
    pd.DataFrame(rows).to_csv(TABLES / "near_duplicates.tsv", sep="\t", index=False)
    for row in rows:
        print(
            f"near-duplicates {row['partition']} vs {row['compared_against']}: "
            f"exact={row['exact_duplicate_blocks']} "
            f"near(J>={NEAR_DUPLICATE_SIMILARITY})={row['near_duplicate_blocks']} "
            f"max_jaccard={row['max_jaccard']}"
        )

    # --- two computable reference levels, on train/development ONLY ----------
    # Not candidates and not a track: a cross-entropy is unreadable without the
    # level a context-free model reaches and the level of pure chance.
    train_ids, dev_ids = part_ids["train"], part_ids["development"]
    train_lo = int(frame.at[train_ids[0], "start_char"])
    train_hi = train_lo + int(frame.loc[train_ids, "n_chars"].sum())
    dev_lo = int(frame.at[dev_ids[0], "start_char"])
    dev_hi = dev_lo + int(frame.loc[dev_ids, "n_chars"].sum())
    counts = np.bincount(tokens[train_lo:train_hi], minlength=len(vocab)).astype(float)
    probs = (counts + 1.0) / (counts.sum() + len(vocab))  # add-one, so no zero
    dev_tokens = tokens[dev_lo + 1 : dev_hi]  # the characters a model predicts
    unigram_nats = float(-np.mean(np.log(probs[dev_tokens])))
    uniform_nats = float(np.log(len(vocab)))
    pd.DataFrame(
        [
            {
                "reference": "uniform",
                "description": f"uniform over the {len(vocab)}-character vocabulary",
                "val_nats_per_char": round(uniform_nats, 6),
                "val_bits_per_char": round(uniform_nats / np.log(2), 6),
            },
            {
                "reference": "unigram",
                "description": "add-one character frequencies fitted on the train partition",
                "val_nats_per_char": round(unigram_nats, 6),
                "val_bits_per_char": round(unigram_nats / np.log(2), 6),
            },
        ]
    ).to_csv(TABLES / "reference_losses.tsv", sep="\t", index=False)
    print(f"reference levels on development: uniform {uniform_nats:.6f} nats, "
          f"unigram {unigram_nats:.6f} nats")

    # --- the profile the data card quotes ------------------------------------
    pd.DataFrame(
        [
            {"statistic": "characters", "value": len(text)},
            {"statistic": "vocabulary_size", "value": len(vocab)},
            {"statistic": "blocks", "value": n_blocks},
            {"statistic": "block_chars", "value": BLOCK_CHARS},
            {"statistic": "last_block_chars", "value": lengths[-1]},
            {"statistic": "train_blocks", "value": len(part_ids["train"])},
            {"statistic": "development_blocks", "value": len(part_ids["development"])},
            {"statistic": "sealed_blocks", "value": len(part_ids["test"])},
            {"statistic": "train_chars", "value": spans["train"][2]},
            {"statistic": "development_chars", "value": spans["development"][2]},
            {"statistic": "sealed_chars", "value": spans["test"][2]},
            {"statistic": "distinct_content_groups", "value": frame["content_group"].nunique()},
            {"statistic": "min_block_distinct_chars", "value": int(frame["n_distinct_chars"].min())},
            {"statistic": "max_block_distinct_chars", "value": int(frame["n_distinct_chars"].max())},
        ]
    ).to_csv(TABLES / "corpus_profile.tsv", sep="\t", index=False)

    fingerprints = partition_fingerprints(".")
    for name, value in fingerprints.items():
        print(f"fingerprint {name}: {value}")
    print("prepared: data/prepared/{prepared.csv,index.csv,tokens.bin,vocab.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
