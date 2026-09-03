# hubble1929 — bundled dataset

Edwin Hubble's two original data tables from **"A relation between distance and
radial velocity among extra-galactic nebulae,"** *Proceedings of the National
Academy of Sciences* 15(3):168–173 (communicated January 17, 1929; published
March 15, 1929), DOI [10.1073/pnas.15.3.168](https://doi.org/10.1073/pnas.15.3.168)
— the paper that established the linear velocity–distance relation now called
Hubble's law.

| Fact | Value |
|---|---|
| `hubble1929_table1.csv` | Table 1 — 24 objects, individually estimated distances |
| `hubble1929_table2.csv` | Table 2 — 22 nebulae, distances derived from radial velocities |
| Units | `r_mpc` in units of 10⁶ parsecs (= Mpc); `v_kms`/`vs_kms` in km/s; `m_s`/`m_t` apparent magnitudes; `M_t` absolute magnitude |
| Licence | Public domain (facts from a 1929 publication) — see [`DATA_LICENSE`](DATA_LICENSE) |

- Source of record: as above. **Table 1** ("Nebulae whose distances have been
  estimated from stars involved or from mean luminosities in a cluster")
  columns as printed: `object, m_s, r_mpc, v_kms, m_t, M_t`. **Table 2**
  ("Nebulae whose distances are estimated from radial velocities") columns as
  printed: `object, v_kms, vs_kms, r_mpc, m_t, M_t` (`vs_kms` = velocity
  corrected for solar motion).
- **Correction to the working brief:** the phrase "distances estimated from
  mean luminosity" describes Table 1's *last four rows* (the Virgo-cluster
  objects, whose distance is assigned from the mean luminosity of the
  cluster), not Table 2. Table 2's own printed title is "NEBULAE WHOSE
  DISTANCES ARE ESTIMATED FROM RADIAL VELOCITIES": its `r_mpc` column is
  *calculated* from `vs_kms` via Hubble's adopted K ≈ 500 km/s/Mpc, then used
  to cross-check the resulting `M_t` distribution against Table 1's — it is
  not an independent luminosity-based measurement. Recorded here rather than
  silently reshaped to match the brief.
- Missing values are printed as `..` in the original tables and stored as
  empty CSV fields: `m_s` is blank for the 6 closest (Cepheid/Shapley-based)
  objects and the 4 Virgo-cluster objects in Table 1 (it is only tabulated for
  the 14 "brightest resolved star" distances in between); `r_mpc` and `M_t`
  are blank for N.G.C. 404 in Table 2 (its corrected velocity, −65 km/s, was
  judged too small relative to peculiar motion to assign a distance).
- Object names and sign conventions are kept exactly as printed (e.g.
  `S. Mag.`, `L. Mag.`, `N.G.C.6822`, bare NGC numbers like `598` for the
  rest); printed leading `+` on positive velocities is represented as an
  unsigned positive number (standard numeric CSV), negative values keep their
  `-` sign — no sign information is lost.
- 24 + 22 = 46 rows — these two files ARE the complete per-object dataset from
  the paper. Hubble's text separately reports a 9-group aggregation of the
  same 24 objects (for a second solar-motion solution) and a single aggregate
  point for the 22 Table-2 nebulae (mean distance 1.4 Mpc at 745 km/s); neither
  is a per-object table in the paper, so neither is reproduced as a CSV here.

**Both sources, fetched and diffed.** Per the plan, the PNAS page (https://www.pnas.org/doi/10.1073/pnas.15.3.168)
and the PMC copy (https://pmc.ncbi.nlm.nih.gov/articles/PMC522427/) were tried
first; both blocked automated fetching on access date 2026-09-02 (a Cloudflare
"Just a moment…" challenge on pnas.org, a reCAPTCHA gate on
pmc.ncbi.nlm.nih.gov). The two sources actually used instead:

- **(a) "The paper itself":** Internet Archive digitized scan of the original
  journal pages, item [`B-001-001-868`](https://archive.org/details/B-001-001-868)
  ("A relation between distance and radial velocity among extra-galactic
  nebulae // PNAS 1929 15 (3) 168-173"), OCR text at
  `https://archive.org/download/B-001-001-868/168.full_djvu.txt`. Accessed
  2026-09-02.
- **(b) Independent transcription:** NASA APOD's "Scale of the Universe Debate
  1996" page, a manually retyped reproduction of the article,
  https://apod.nasa.gov/debate/1996/hub_1929.html. Accessed 2026-09-02. (A
  byte-identical mirror of this same transcription — it ends with the same
  "Return to The Scale of the Universe Debate 1996" footer — is also hosted as
  a PDF by the University of Groningen at
  `https://www.astro.rug.nl/~weygaert/tim1publication/cosmo2007/literature/hubble.1929.pdf`;
  that is a copy of source (b), not a third source.)
- **Rejected candidate second source:** the R package `gamair`'s `hubble`
  dataset (suggested as an example in the plan) was checked against its own
  documentation before use and found to be **Freedman et al. (2001),
  "Final results from the Hubble Space Telescope key project to measure the
  Hubble constant," ApJ 553:47–72** — 24 *different*, modern galaxies with
  Cepheid distances from the HST Key Project, not Hubble's 1929 data. Using it
  as a second source would have been a genuine data-identity error, so it was
  not used.
- **Diff result:** source (a) and source (b) were compared cell-by-cell across
  all 46 rows and both tables (up to 6 columns each). **Zero substantive
  discrepancies.** The only divergence was OCR sign-loss in the archive.org
  scan on several Table 1 `M_t` values (e.g. printed as `17.2` instead of
  `-17.2` by the OCR pass) — resolved in favor of source (b)'s clean
  transcription, consistent with (i) every `M_t` value in the paper being a
  negative absolute magnitude by definition and (ii) the paper's own printed
  column means only reproducing under the corrected signs: Table 1 mean `M_t`
  = −15.5 (recomputed from this CSV: −15.4792, rounds to the printed value);
  Table 2 means `m_t` = 10.5, `M_t` = −15.3 (recomputed from this CSV:
  10.499999…, −15.299999…, i.e. exact to floating-point noise). No paper-wins
  correction was needed anywhere in either table.

**Identity anchors (scouting values, not evidence).** Computed with `numpy`
(2.5.1) from `hubble1929_table1.csv`'s 24 rows —
`sum_r = r_mpc.sum()`, `sum_v = v_kms.sum()`, `K0 = sum(r·v)/sum(r²)` (OLS
slope through the origin), `K1, intercept = np.linalg.lstsq([r, 1], v)` (free
intercept):

| anchor | computed here | plan's scouting value |
|---|---|---|
| rows, Table 1 / Table 2 | 24 / 22 | 24 / 22 |
| sum(r_mpc) | 21.873000 | ≈ 21.873 |
| sum(v_kms) | 8955.000000 | ≈ 8955 |
| K0 (OLS through origin) | 423.937323 | ≈ 423.94 |
| K1 (free-intercept OLS slope) | 454.158441 | ≈ 454.16 |
| intercept (free-intercept OLS) | −40.783649 | ≈ −40.78 |

All four numeric anchors reproduce the plan's scouting values to the last
printed digit. For context only (not reproduced here, and not expected to
match K0/K1): Hubble's own published constant, from a joint 4-parameter fit
that also removes the ~300 km/s solar peculiar motion before regressing on
distance, is **K = 465 ± 50 km/s/Mpc (24 objects individually)** and
**513 ± 60 km/s/Mpc (9 groups)**. K0/K1 sit 2–9% below 465 — expected, not a
discrepancy: K0/K1 are a naive one/two-parameter OLS of the *raw, uncorrected*
`v_kms` on `r_mpc`, whereas 465 comes from the full 4-parameter
(K, X, Y, Z) solar-motion solution described in the paper. Reproducing 465±50
exactly would require re-implementing that joint fit, which is out of scope
for a bundling README — reported here honestly rather than tuned to match.

## Provenance / licensing note

Both tables are a compilation of numeric facts (distances, velocities,
magnitudes) transcribed from a 1929 *Proceedings of the National Academy of
Sciences* article. The article has been in the public domain in the United
States since January 1, 2025 (the 95-year term for an unrenewed 1929
publication expired at the end of 2024); a bare table of measured facts is in
any case not independently copyrightable (*Feist Publications, Inc. v. Rural
Telephone Service Co.*, 499 U.S. 340 (1991)). No license is asserted here
beyond that public-domain status; the data are redistributed as a small
factual table for scientific and pedagogical reproduction. If you reuse it,
cite Hubble, E. (1929), "A relation between distance and radial velocity among
extra-galactic nebulae," *PNAS* 15(3):168–173, DOI 10.1073/pnas.15.3.168.
