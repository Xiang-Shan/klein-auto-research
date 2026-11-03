"""Prepare the evaluation items of study 20: GSM8K originals, GSM8K sample, twin blocks.

Writes `data/prepared/index.csv` — one row per item, columns ``id, question,
answer, block, template, split`` — which the contract splits as
``kind: predefined``:

* split ``train``, block ``original`` (50): the GSM8K test items the templates
  were made from (ids ``gsm-<line>``), ``template`` = the template id;
* split ``development``, block ``gsm8k`` (300): the first 300 candidates of the
  selection permutation that are NOT template sources (ids ``gsm-<line>``);
* split ``development``, block ``twin_dev`` (200): ``twins.generate(20261104, 4)``
  (ids ``twA-<template>-<k>``);
* split ``test``, block ``twin_sealed`` (200): ``twins.generate(20261105, 4)``,
  disjoint from twin_dev by construction (ids ``twC-<template>-<k>``) — SEALED.

The source is the contract's ``data.source`` (the bundled GSM8K test split),
resolved by ``kleinlib.sources.resolve`` and checked against the sha256 its
README publishes. ``twins.validate()`` runs first and any failure aborts the
preparation. Deterministic: same bytes in, same index out (LF, no index column).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from lib import twins

from kleinlib.contract import load_contract
from kleinlib.data import index_path
from kleinlib.sources import resolve

HERE = Path(__file__).resolve().parent

#: The digest `datasets/gsm8k-test/README.md` publishes for the bundled file.
EXPECTED_SHA256 = "3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14"

#: Size of the development GSM8K sample (block `gsm8k`).
N_GSM8K_DEV = 300

COLUMNS = ["id", "question", "answer", "block", "template", "split"]


def main() -> None:
    contract = load_contract(HERE)
    source = resolve(
        contract["data"]["source"],
        study_dir=HERE,
        offline=os.environ.get("KLEIN_OFFLINE") == "1",
    )
    if source.path is None or source.digest != EXPECTED_SHA256:
        raise SystemExit(
            f"GSM8K test bytes do not match the published sha256: got {source.digest}, "
            f"expected {EXPECTED_SHA256}"
        )
    records = twins.read_gsm8k(source.path)

    summary = twins.validate(records)  # raises AssertionError on any template defect
    print(
        f"twins.validate: {summary['templates']} templates, {summary['skipped']} skipped, "
        f"{summary['exact_text']} reproduce their question byte-for-byte, "
        f"{summary['candidates_consumed']} candidates consumed"
    )

    sources = {template.source_index for template in twins.TEMPLATES}
    rows: list[dict[str, object]] = []
    for template in twins.TEMPLATES:
        record = records[template.source_index]
        rows.append({
            "id": f"gsm-{template.source_index}",
            "question": record["question"],
            "answer": record["gold"],
            "block": "original",
            "template": template.tid,
            "split": "train",
        })

    gsm8k = [index for index in twins.candidate_order() if index not in sources][:N_GSM8K_DEV]
    for index in gsm8k:
        record = records[index]
        rows.append({
            "id": f"gsm-{index}",
            "question": record["question"],
            "answer": record["gold"],
            "block": "gsm8k",
            "template": "",
            "split": "development",
        })

    twin_dev, twin_sealed = twins.declared_blocks()
    for block, split, twin_rows in (
        ("twin_dev", "development", twin_dev),
        ("twin_sealed", "test", twin_sealed),
    ):
        for row in twin_rows:
            rows.append({**row, "block": block, "split": split})

    index = pd.DataFrame(rows, columns=COLUMNS)
    if index["id"].duplicated().any():
        raise SystemExit(f"duplicate ids: {index.loc[index['id'].duplicated(), 'id'].tolist()[:5]}")
    out = index_path(HERE, contract)
    if out is None:
        raise SystemExit("study.yaml:data.split.index is required")
    out.parent.mkdir(parents=True, exist_ok=True)
    index.to_csv(out, index=False, lineterminator="\n")

    counts = index.groupby(["block", "split"], sort=False).size()
    print(f"prepared {len(index)} items -> {out.relative_to(HERE).as_posix()}")
    for (block, split), n in counts.items():
        print(f"  {block:<12} {split:<12} {n}")


if __name__ == "__main__":
    main()
