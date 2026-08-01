# Third-party notices

The MIT license in [`LICENSE`](LICENSE) applies to the Klein Auto Research
software and documentation authored for this repository. It does not replace
the licenses of separately distributed third-party material.

## Insurance Claims Dataset

- Source: [Kaggle dataset `litvinenko630/insurance-claims`](https://www.kaggle.com/datasets/litvinenko630/insurance-claims)
- Author/uploader: Kaggle user `litvinenko630`
- Declared license: Apache License 2.0
- Repository copies: `datasets/insurance-claims/insurance_claims.csv.gz` and the
  derived 2,000-row fixture under `studies/00-glm-claims-quickstart/fixtures/`
- Integrity and attribution: [`datasets/insurance-claims/DATA_LICENSE`](datasets/insurance-claims/DATA_LICENSE)

The repository copy is a deterministic gzip of the published CSV. The full
Apache-2.0 text, verification note, and SHA-256 of the decompressed data are kept
beside it in `DATA_LICENSE`.

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
