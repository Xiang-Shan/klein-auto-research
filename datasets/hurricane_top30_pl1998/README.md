# hurricane_top30_pl1998 — bundled dataset

The 30 most-damaging US hurricanes **1900–1995**, normalized to 1995 US dollars by
inflation, personal-property increases, and coastal-county population changes —
**Table 8 of Pielke & Landsea (1998)**, transcribed from NOAA AOML/HRD and used by
`studies/06-hurricane-gqls-returnlevels`.

- Source of record: Pielke, R. A. Jr. & Landsea, C. W. (1998), "Normalized
  Hurricane Damages in the United States: 1925–95", *Weather and Forecasting*
  13(3), 621–631 — Table 8 ("Top 30 Damaging Hurricanes … (1900–1995)").
- Transcribed from the NOAA AOML/HRD normalized-damage page (fetched 2026-07-31;
  all 30 values verified against the page).
- Units: `damage_bn_1995` is **billions of 1995 US dollars**. Loss-model fitting
  in the study happens on the **log-dollar** scale (`log(damage_bn_1995 × 1e9)`).
- 30 rows — this file IS the complete dataset; a data-hub copy exists under the
  same name, and `kleinlib.data.load_data_hub("hurricane_top30_pl1998")` resolves
  the hub first (`$DATA_HUB`) and this bundled copy from a bare clone.

Two provenance traps, both load-bearing for reproduction (details in the study's
`data_card.md`):

1. **The "1925–1995" period label is a mislabel** — in the source paper's own
   title and in downstream literature. Table 8 includes three supplemental
   pre-1925 storms (1900 Galveston, 1915 Galveston, 1919 S Texas), flagged here
   with `pre1925_flag = 1`. The top-30 of the R `extRemes::damage` dataset (which
   truly covers 1925–1995) is a DIFFERENT sample and does not reproduce the
   summary statistics below.
2. **Quantile convention:** the sample's published quartiles (q1 4.0560,
   q3 12.4340) reproduce only under Hazen plotting positions
   (`np.quantile(x, p, method="hazen")`), and the published sd (13.6251) uses
   `ddof=1`.

Acceptance statistics (all reproduce to ≤3.3e-5): n=30, min 2.2660, q1 4.0560,
median 7.6885, q3 12.4340, max 72.3030, mean 11.7499, sd 13.6251.

## Provenance / licensing note

The damage estimates are a compilation of US federal (NOAA) data published in an
American Meteorological Society journal article. No license is asserted here; the
data are redistributed as a small factual table for scientific reproduction with
citation. If you reuse it, cite Pielke & Landsea (1998).
