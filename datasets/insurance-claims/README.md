# insurance-claims — bundled dataset

The full auto-insurance claims dataset used by `studies/00-glm-claims-quickstart`
and `studies/01-dae-claims`, bundled so a fresh clone reproduces both studies with
**no credentials, no downloads, no private infrastructure**.

| Fact | Value |
|---|---|
| File | `insurance_claims.csv.gz` (675 KB; 11.8 MB decompressed) |
| Records | 58,592 policies + header row |
| Target | `claim_status` (binary, ~6.4% positive) |
| Source | Kaggle [`litvinenko630/insurance-claims`](https://www.kaggle.com/datasets/litvinenko630/insurance-claims) |
| License | Apache-2.0, as declared by the uploader — full text + attribution in [`DATA_LICENSE`](DATA_LICENSE) (verified on the live page 2026-07-10) |
| Integrity | gzip (`gzip -n`) of the raw published CSV, byte-identical on decompression — sha256 `99d5ae73…f194d29` (full hash in `DATA_LICENSE`) |

## How it is resolved

`kleinlib.data.load_data_hub("insurance-claims")` resolves, in order:

1. `$DATA_HUB` — an external [data-hub directory](../../README.md), if you keep one;
2. **this bundled copy** (found relative to the installed `kleinlib`, so it works
   from any working directory);
3. otherwise it raises an actionable error.

The loader prints `data source: hub|bundled — <path>` so you always know which
copy fed an experiment. Both paths read the same bytes with the same
`pandas.read_csv` call, so results are identical either way.

A 2,000-row stratified sample of this file is committed at
`studies/00-glm-claims-quickstart/fixtures/` for fast CI smoke runs; column
definitions and value-pattern notes live in the study's `data_card.md`.
