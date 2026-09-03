# Fixtures — 12-insurance-claims-frequency

## `insurance_claims_sample_2k.csv`

- **Provenance:** deterministic stratified sample
  (`sklearn.model_selection.train_test_split`, `random_state=0`, `train_size=2000`,
  `stratify=claim_status`) of this study's PREPARED output — i.e. `prepare.py`'s
  `preprocess()` applied to the full `bundled:insurance-claims` frame. The file is
  already prepared (45 columns, `is_*` already int, `max_torque` / `max_power` already
  parsed to numeric), not raw.
- **Source dataset:** Kaggle `litvinenko630/insurance-claims` (58,592 policies, claim
  rate 0.063968), bundled in this repository at `datasets/insurance-claims/`.
- **Licence:** Apache-2.0 — full text and attribution in
  `datasets/insurance-claims/DATA_LICENSE`; repository-level notice in
  `THIRD_PARTY_NOTICES.md`.
- **Purpose:** the CI / offline path. `uv run --locked python prepare.py --sample`
  reads this file directly and writes it to the contract's prepared path, so a
  smoke-level run needs neither the bundled archive nor a network.
- **Continuity with the v1 quickstart.** This file is byte-identical
  (sha256 `b8c9333f3dd63388dab0c02122147db428f011d1a7e964cf982c599bb5247786`) to the
  fixture the v1 study `00-glm-claims-quickstart` carried at tag `v1.3.0`. It was not
  copied: it was REGENERATED from this study's own `prepare.py` output by the recipe
  below, and the digests then compared. That equality is the study's evidence that the
  port's data preparation is faithful — see `scouting_ledger.md` S6.
- **Regeneration:**
  ```bash
  uv run --locked python prepare.py            # writes data/prepared/…prepared.csv
  ```
  ```python
  import pandas as pd
  from sklearn.model_selection import train_test_split
  df = pd.read_csv("data/prepared/insurance_claims_prepared.csv")
  sample, _ = train_test_split(df, train_size=2000, random_state=0, stratify=df["claim_status"])
  sample.sort_index().reset_index(drop=True).to_csv("fixtures/insurance_claims_sample_2k.csv", index=False)
  ```
