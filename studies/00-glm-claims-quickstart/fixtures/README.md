# Fixtures — 00-glm-claims-quickstart

## `insurance_claims_sample_2k.csv`

- **Provenance:** deterministic stratified sample (`sklearn.model_selection.train_test_split`,
  `random_state=0`, `train_size=2000`, `stratify=claim_status`) of this study's PREPARED
  output (`prepare.py`'s `preprocess()` applied to the full `data_hub:insurance-claims`
  frame — i.e. this file is already prepared, not raw).
- **Source dataset:** kaggle `litvinenko630/insurance-claims` (58,592 policies, ~6.4%
  claim rate) — the full raw CSV is bundled at `datasets/insurance-claims/` in this repo.
- **License:** Apache-2.0 — full text + attribution in `datasets/insurance-claims/DATA_LICENSE`.
- **Purpose:** CI/offline path — `uv run prepare.py --sample` reads this file directly
  (no network, no `data_hub` dependency) and writes it to the conventional prepared-data
  path. It is a fixture of the *prepared* schema (45 columns, `is_*` already int,
  `max_torque`/`max_power` already parsed to numeric), not a raw download.
- **Regeneration:** run `uv run prepare.py` (full data_hub path) once, then re-sample:
  ```python
  import pandas as pd
  from sklearn.model_selection import train_test_split
  df = pd.read_csv("data/prepared/insurance_claims_prepared.csv")
  sample, _ = train_test_split(df, train_size=2000, random_state=0, stratify=df["claim_status"])
  sample.sort_index().reset_index(drop=True).to_csv("fixtures/insurance_claims_sample_2k.csv", index=False)
  ```
