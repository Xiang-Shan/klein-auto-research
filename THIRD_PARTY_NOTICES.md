# Third-party notices

The MIT license in [`LICENSE`](LICENSE) applies to the Klein Auto Research
software and documentation authored for this repository. It does not replace
the licenses of separately distributed third-party material.

## Insurance Claims Dataset

- Source: [Kaggle dataset `litvinenko630/insurance-claims`](https://www.kaggle.com/datasets/litvinenko630/insurance-claims)
- Author/uploader: Kaggle user `litvinenko630`
- Declared license: Apache License 2.0
- Repository copies: `datasets/insurance-claims/insurance_claims.csv.gz` and the
  derived 2,000-row fixture under `studies/12-insurance-claims-frequency/fixtures/`
- Integrity and attribution: [`datasets/insurance-claims/DATA_LICENSE`](datasets/insurance-claims/DATA_LICENSE)

The repository copy is a deterministic gzip of the published CSV. The full
Apache-2.0 text, verification note, and SHA-256 of the decompressed data are kept
beside it in `DATA_LICENSE`.

## Hurricane damages dataset (Pielke & Landsea 1998, Table 8)

- Source of record: Pielke, R. A. Jr. & Landsea, C. W. (1998), "Normalized
  Hurricane Damages in the United States: 1925–95", *Weather and Forecasting*
  13(3), 621–631 — Table 8, as republished on the NOAA AOML/HRD normalized-damage
  page (transcribed 2026-07-31).
- Repository copy: `datasets/hurricane_top30_pl1998/hurricane_top30_pl1998.csv`
  (30 rows, the complete table); used by `studies/06-hurricane-gqls-returnlevels`.
- Licence: none asserted by the source; a small factual table compiled from US
  federal (NOAA) data and redistributed for scientific reproduction with citation.
  Provenance notes (including the source's own period-label trap) live in
  [`datasets/hurricane_top30_pl1998/README.md`](datasets/hurricane_top30_pl1998/README.md).

## Hubble (1929) velocity–distance tables

- Source: Hubble, E. (1929), "A relation between distance and radial velocity among
  extra-galactic nebulae", *Proceedings of the National Academy of Sciences* 15(3),
  168–173, DOI 10.1073/pnas.15.3.168 — Tables 1 (24 objects) and 2 (22 nebulae).
- Repository copies: `datasets/hubble1929/hubble1929_table1.csv`,
  `datasets/hubble1929/hubble1929_table2.csv`; used by `studies/10-hubble-1929-replication`.
- Licence: a 1929 scientific table of measured facts, in the public domain;
  transcribed from two independent sources and diffed cell by cell — provenance,
  anchors and the one OCR caveat are in
  [`datasets/hubble1929/README.md`](datasets/hubble1929/README.md) and `DATA_LICENSE`.

## Tiny Shakespeare corpus

- Source: `https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt`
  — the concatenation of Shakespeare plays distributed with
  [karpathy/char-rnn](https://github.com/karpathy/char-rnn) (MIT, per that
  repository's README) and reused by nanoGPT; the text itself is public domain.
- Repository copy: `datasets/tinyshakespeare/tinyshakespeare.txt.gz` (deterministic
  gzip; sha256 of the decompressed 1,115,394 bytes recorded in
  [`datasets/tinyshakespeare/README.md`](datasets/tinyshakespeare/README.md) and
  `DATA_LICENSE`); used by `studies/13-charlm-fixed-budget`.

## Research workflow lineage

Klein's lab-notebook and edit-run-log doctrine was inspired by
[karpathy/autoresearch](https://github.com/karpathy/autoresearch) and the portable
workflow treatment in
[elan-elan/agent-smith](https://github.com/elan-elan/agent-smith). Those projects
are referenced for lineage; their source code is not vendored here. Consult each
upstream repository for its own license and notices.

## Python dependencies

Runtime and optional Python packages are installed from their upstream
distributions and retain their own licenses. The resolved versions and artifact
hashes are recorded in `uv.lock`; package metadata supplies the corresponding
license terms.

## Tutorial math rendering (ziamath + bundled typefaces)

Generated tutorials typeset mathematics at build time via
[ziamath](https://github.com/cdelker/ziamath) and
[ziafont](https://github.com/cdelker/ziafont) (both MIT, © Collin J. Delker;
their MIT texts ship in the installed distributions recorded in `uv.lock`).
ziamath bundles the **STIX Two Math** typeface (SIL Open Font License 1.1,
© The STIX Fonts project; license text at
`https://scripts.sil.org/OFL` and in the upstream STIX repository), and
ziafont bundles **DejaVu Sans** (Bitstream Vera license terms) as a fallback.
Rendered `report/index.html` pages embed glyph OUTLINES as static SVG paths —
rendered artwork, not the font programs themselves. The font names are not
used to promote this software, and this notice travels with the repository.
