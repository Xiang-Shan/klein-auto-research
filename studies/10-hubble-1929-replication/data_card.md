---
type: data-card
domain: "astronomy"
modality: "tabular"
status: go-with-cautions
concepts: [replication, prospective-lock, derived-column, distance-modulus]
related: [scouting_ledger.md, method_card.md, study.yaml]
---

# Data card — 10-hubble-1929-replication

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source tags** (both members of one bundled dataset, both named in the hashed
  contract and resolved from it by `prepare.py` — no path is hardcoded anywhere):
  - `data.source` = `bundled:hubble1929/hubble1929_table1.csv`
    → `datasets/hubble1929/hubble1929_table1.csv`
    · sha256 `86fda6be6fd3096a7c25669354bb306a0fbe030fb6f89039c7a5c49e301d0f28`
  - `data.source_table2` = `bundled:hubble1929/hubble1929_table2.csv`
    → `datasets/hubble1929/hubble1929_table2.csv`
    · sha256 `99a287b546d1742bd7d1943bf405c0bac8eecb0ced8d7db713f11978baef2838`

  Both digests as printed by `prepare.py`, and both match the checksums recorded in
  `datasets/hubble1929/DATA_LICENSE`. **Pin:** `data.sha256` not required — `bundled:`
  is repo-local and the DATA gate fingerprints `prepare.py`'s output; the two digests
  above are recorded here anyway because a replication of a printed table is worth
  nothing if the bytes can drift.
- **Origin & licence.** Hubble, E. (1929), "A relation between distance and radial
  velocity among extra-galactic nebulae," *PNAS* **15**(3):168–173,
  DOI [10.1073/pnas.15.3.168](https://doi.org/10.1073/pnas.15.3.168).
  **Public domain** in the United States — the 95-year term for the unrenewed 1929
  publication expired at the end of 2024, and a bare table of measured facts is not
  copyrightable subject matter in any case (*Feist v. Rural Telephone*, 499 U.S. 340
  (1991)). Full text of the terms: **`datasets/hubble1929/DATA_LICENSE`**, which is
  the licence file this study cites and which also carries the two checksums above.
- **Transcription provenance.** The bundling agent could not fetch pnas.org or PMC
  (a Cloudflare challenge and a reCAPTCHA gate on 2026-09-02) and instead diffed two
  independent sources cell by cell across all 46 rows: the Internet Archive scan of
  the journal pages (item `B-001-001-868`) and NASA APOD's manual retyping of the
  article. **Zero substantive discrepancies.** The only divergence was OCR sign-loss
  on several Table-1 `M_t` values, resolved in favour of the clean transcription and
  confirmed by the paper's own printed column means. The R package `gamair`'s
  `hubble` dataset was checked as a candidate second source and **rejected**: it is
  Freedman et al. (2001) HST Key Project data — 24 *different*, modern galaxies —
  and using it would have been a data-identity error. Details in
  `datasets/hubble1929/README.md`.
- **Modality:** tabular · **Prepared rows × cols:** 46 × 9 (24 Table 1 + 22 Table 2)
  · **Target / estimand:** `v_kms` regressed on `r_mpc`; the estimand is
  **K, the velocity–distance constant, in km/s/Mpc**.
- **Units.** `r_mpc` in 10⁶ parsecs (Mpc); `v_kms`, `vs_kms` in km/s; `m_s`, `m_t`
  apparent magnitudes; `M_t` absolute magnitude.
- **Split policy:** `data.split.kind: none`. See **Partition policy** below.
- **Profiler used:** the global `dataset-profiler` skill
  (`~/.claude/skills/dataset-profiler/scripts/profile.py`), cross-checked against
  `kleinlib.profile_fallback`; both agree on shape, dtypes and missingness. The
  measurements the bundled profilers do not make are produced by the re-runnable
  `data_gate_profile.py` in this study directory, whose output is quoted verbatim
  below.

## Partition policy — a prospective lock, not a random draw

`data.split.kind: none` because nothing here is drawn. The partition is the paper's
own structure and `prepare.py` assigns it from the source file a row came from — no
seed, no shuffle, no rule an argument can change:

| Block | Rows | Role | Fingerprint (`data_gate_profile.py` §1) |
|---|---|---|---|
| `table1` — 24 objects, distances estimated independently of velocity | 24 | **development**; everything adaptive happens here | `106a725532097219283d5c3bf547d675af5a4b7227101b1d85a413cae0ccfd24` |
| `table2` — 22 nebulae | 22 | **sealed**; one access per the reproduction track | `b3d8796e91bc0906f9892e562643339fbd110508804ac4e01b0ce4116e8e9610` |

Every cell reaches its data through one door, `lib/hubble.py:load_block()`, which
resolves `KLEIN_EVALUATION_KIND`, **refuses the sealed block outside a
`--final-test` run**, honours `KLEIN_SEALED_DRYRUN=1` by serving the development
block and printing `sealed_dryrun: 1`, drops Table 2's forbidden columns, and prints
`split_fingerprint:`.

**Two disclosures, both structural, neither hidden:**

1. `kleinlib.data.contract_split` refuses `kind: none` by design ("comparability comes
   from declared seed blocks, not from row partitions"), so this gate registers **no
   realized partition fingerprints** and `klein run-one` prints
   `note: partition not verified` on every cell. Silence is not a pass — so the two
   digests above are published here instead, and a stranger recomputes them from the
   contract plus the bytes with `uv run --locked python -u data_gate_profile.py`.
   For the same reason `klein preflight` reports
   `[WARN] no study source calls kleinlib.data.contract_split / load_partition`.
   That WARN is correct and expected: this study has no row partition to split, and
   `load_block()` re-implements the same contract (`KLEIN_EVALUATION_KIND`,
   `KLEIN_SEALED_DRYRUN`, a printed fingerprint) for a partition that is two files.
2. The seal is a **prospective ANALYSIS lock**. The driving agent read all 22 sealed
   rows before the contract existed (`scouting_ledger.md` §0/S6). What is locked, and
   hashed at the CONSULT gate in `study.yaml:sealed_lock`, is the statistic, the
   columns it may use, the K it takes and the tolerance; the access is spent once.
   The word "blind" is banned in this profile for exactly this confusion, and a
   "fresh bootstrap block" reseal was rejected before the contract as dishonest.

## Profile summary

46 rows × 9 columns. `m_s` and `vs_kms` are printed only for a subset of rows *in the
paper itself* (`..` in the original), which is why their missingness is high and
**informative, not a data-quality problem**: `m_s` (magnitude of the brightest
resolved star) exists only for the 14 objects whose distance came from that method,
and `vs_kms` only for Table 2.

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `block` | free text, 2 values `table1`/`table2` | 0.0 | 2 | no | no | the partition itself |
| `object_id` | free text, `<block>:<normalized name>` | 0.0 | 46 | **yes** (46/46) | no | identity key; never a feature |
| `object` | free text (`S. Mag.`, `N.G.C.6822`, bare NGC numbers) | 0.0 | 46 | **yes** | no | as printed; never a feature |
| `m_s` | continuous numeric, 17.0–20.0, no sentinels | 69.6 | 9 | no | no | Table 1 only, and only for the 14 "brightest resolved star" distances |
| `r_mpc` | continuous numeric, 0.032–3.45, no sentinels | 2.2 | 34 | no | **Table 2 only: DERIVED** | Table 1: independent distance. Table 2: computed from velocity — see row 1 of the audit |
| `v_kms` | integral numeric, −220…1800, no sentinels | 0.0 | 32 | no | no | the response; the 5 negative values in Table 1 and 1 in Table 2 are real (approaching galaxies) |
| `vs_kms` | integral numeric, −215…220, no sentinels | 52.2 | 19 | no | **DERIVED** | Table 2 only; tied to `r_mpc` by an exact identity |
| `m_t` | continuous numeric, 0.5–12.5, no sentinels | 0.0 | 29 | no | no | total apparent magnitude; a primary column of the sealed statistic |
| `M_t` | continuous numeric, −17.7…−12.7, no sentinels | 2.2 | 30 | no | **Table 2 only: the printed answer** | Table 1: a reproduction target (P9). Table 2: forbidden |

**Value-pattern check (mandatory war story).** Performed on the ACTUAL values, not
`dtype`, by `data_gate_profile.py` §2 — verbatim:

```
     block  missing=  0.0%  free text; e.g. ['table1', 'table1', 'table1']
 object_id  missing=  0.0%  free text; e.g. ['table1:smag', 'table1:lmag', 'table1:6822']
    object  missing=  0.0%  free text; e.g. ['S. Mag.', 'L. Mag.', 'N.G.C.6822']
       m_s  missing= 69.6%  continuous numeric, min=17 max=20; no sentinels
     r_mpc  missing=  2.2%  continuous numeric, min=0.032 max=3.45; no sentinels
     v_kms  missing=  0.0%  integral numeric, min=-220 max=1800; no sentinels
    vs_kms  missing= 52.2%  integral numeric, min=-215 max=220; no sentinels
       m_t  missing=  0.0%  continuous numeric, min=0.5 max=12.5; no sentinels
       M_t  missing=  2.2%  continuous numeric, min=-17.7 max=-12.7; no sentinels
```

No string-encoded booleans, no numbers-in-strings, no sentinels (`-999`, `"NA"`,
`"unknown"`). The paper's `..` for a missing value arrives as an empty CSV field and
is read as `NaN`, which is what it means. The five negative velocities in Table 1
(N.G.C. 6822, 598, 221, 224 and 3031 — galaxies approaching us) and the one in Table 2
(N.G.C. 404) are **real measurements, not sentinels**, and the study never filters
on sign except where a distance would be undefined.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | **WARN** | **Table 2's `r_mpc` and `vs_kms` are derived from the velocity with Hubble's adopted K ≈ 500** — proven below to the paper's own printed precision. Using either as evidence about K would be circular. | Mechanized: `lib/hubble.py:TABLE2_FORBIDDEN_COLUMNS` and `load_block()` drop `r_mpc`, `vs_kms` and `M_t` from the sealed block before any cell sees it. The sealed statistic uses only `v_kms` and `m_t`, and `study.yaml:sealed_lock` names both lists. |
| 2 | **WARN** | **n = 24.** Every interval in this study rests on 24 points, and the percentile bootstrap is known to under-cover in small samples. | The `simulate` track exists for exactly this: P6 measures the coverage of that interval under a declared DGP at these 24 design points, and its refutation branch (downgrade every interval to descriptive) is pre-registered. |
| 3 | **WARN** | **`split.kind: none` means no realized partition fingerprints are registered**, so `run-one` prints `note: partition not verified` on every cell and `preflight` warns that no source calls `contract_split`. | Disclosed above and in `program.md`; the two block digests are published here so the check a stranger wants is available by hand. |
| 4 | **WARN** | **`m_s` is 69.6 % missing** and `vs_kms` 52.2 %. | Informative missingness (the paper prints each only where the method applied); no cell uses either column, so no imputation decision is needed. |
| 5 | **NOTE** | **Table 2's N.G.C. 404 has `r_mpc` and `M_t` blank** — Hubble judged its corrected velocity (−65 km/s) too small against peculiar motion to assign a distance. Its `v_kms` is −25. | The sealed statistic is registered over rows with `v_kms > 0`, so this object is excluded by the registered rule rather than by a later choice. |
| 6 | **NOTE** | **Four Table-1 objects (N.G.C. 4382, 4472, 4486, 4649) share the distance 2.0 Mpc** — the Virgo cluster mean luminosity, not four independent measurements. | Not a blocker for a replication of Hubble's own arithmetic, but it makes those four points correlated. The jackknife cell (E on the estimate track) measures their joint influence and findings report it. |
| 7 | **NOTE** | Table 1's `r_mpc` is printed to 2–3 significant figures and `v_kms` to the nearest 10 km/s in most rows. | Rounding at the source bounds every reproduction tolerance; the tolerances registered in `study.yaml` are all far wider than this. |

**No BLOCKER is open.** There is no literal split seed in any entrypoint or evaluator
(war story 8): this study has no row partition, `load_block()` selects a block from
the contract, and the one seed constant in `data_gate_profile.py` seeds a permutation
control that nothing downstream reads.

### Mechanized evidence for issue 1 — `data_gate_profile.py` §3, verbatim

```
rows with r_mpc and vs_kms printed: 21 of 22
identity r_mpc == (v_kms - vs_kms) / 500
max |deviation| = 0.0100000000 Mpc over 21 rows
rows satisfying it exactly (< 1e-9): 20 of 21
```

Twenty of the twenty-one rows satisfy `r = (v − v_s)/500` to floating-point exactness;
the twenty-first (N.G.C. 3115: `v` 600, `v_s` 105, printed `r` 1.00, implied 0.99)
misses by exactly one unit in the paper's last printed decimal. That is a *rounding*
residual, not a disagreement: an exact algebraic identity holding on 20 of 21 rows and
rounding on the 21st is the signature of a **computed** column, and it is why Table 2's
title in the paper reads "NEBULAE WHOSE DISTANCES ARE ESTIMATED FROM RADIAL VELOCITIES".

## Clean-room leakage audit

Rows 3–4 are mechanized. This study runs the auditor in **both** modes: dataframe mode
reports N/A for the contaminations that need row partitions (there are none), and
index-table mode audits the realized partition that `prepare.py` writes to
`data/prepared/index.csv` — which is how a `kind: none` study still gets row 3
mechanized instead of waived. Both were run after the profile was complete, reading
only `study.yaml`, `prepare.py`, `lib/hubble.py`, the prepared artifact and the
profile; `program.md` was not read.

```bash
uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study .   # 10/10 clean
uv run --locked python -m kleinlib.leakage data/prepared/prepared.csv --target v_kms --study .   # 9/9 clean
```

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | **PASS, with a mechanized exclusion** | Table 1's `r_mpc` is an *independent* distance (Cepheids, brightest resolved stars, cluster mean luminosity) — that independence is the whole content of the 1929 result. Table 2's `r_mpc` and `vs_kms` are **not**: `r = (v − v_s)/500` holds exactly on 20 of 21 printed rows and rounds on the 21st (§3 above), so both are the velocity re-expressed through Hubble's adopted K. They are dropped by `load_block()` together with `M_t` (the printed answer), and `study.yaml:sealed_lock.columns_forbidden` names all three. The sealed statistic uses `v_kms` and `m_t` only. |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | **N/A** | Nothing is fitted to be reused: every cell is a closed-form computation on one block. There is no encoder, no imputer, no scaler and no time axis anywhere in the study. |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` alone | **PASS (mechanized, index mode)** | `[OK] index-table: 46 rows partitioned by the split column (train=24 development=0 test=22)` · `[OK] duplicate-rows: no id straddles partitions` · `[OK] group-overlap: 46 normalized group ids each stay in one partition` · `[OK] time-order: N/A`. Independently, `prepare.py` hard-fails if any object name normalizes into both tables and printed `objects shared: 0`. Dataframe mode adds `[OK] split-reproduces: N/A — split kind 'none'`. |
| 4. Eval-harness sanity — metric direction matches the contract; a constant predictor and a label-shuffled predictor both score at chance | **PASS (direction mechanized; chance by hand)** | Direction: `[OK] metric-direction[reproduction] targets_outside_tolerance 'lower'`, `[OK] metric-direction[estimate] k_kms_per_mpc 'lower'`, `[OK] metric-direction[simulate] coverage 'higher'` — all three accepted as custom metrics of the scalar family. The auditor reports the chance rows N/A ("no development partition to score") and asks for row 4 from the study's own evaluation path, so `data_gate_profile.py` §5 supplies it: permuting the 24 velocities against the distances 2000 times gives K mean −0.91, sd 118.89 against 454.16 on the real pairing, and **0 of 2000** permutations reach the real value. Breaking the pairing destroys the relation, so the harness carries no answer of its own. |

**Any FAIL is a BLOCKER. There are none.**

## Go / no-go

> **Decision:** GO-WITH-CAUTIONS
>
> **Rationale.** The bytes are pinned, licensed for redistribution, transcribed from
> two independent sources and diffed to zero substantive discrepancies; the identity
> anchors reproduce; both mechanized audits are clean; and the one genuine leakage
> hazard — Table 2's velocity-derived `r_mpc` — is proven by arithmetic and excluded
> at the single door every cell must pass through. The cautions carried forward are
> the four WARNs: the derived columns (mechanized, issue 1), n = 24 (measured, not
> assumed, by the `simulate` track, issue 2), the unregisterable partition
> fingerprints under `kind: none` (published here instead, issue 3), and the
> informative missingness that no cell reads (issue 4). None of them blocks modeling;
> all of them are named in `findings.md`'s scope.

## Appendix — DGP card (the `simulate` track)

The `simulate` track's evidence source is not this table but a declared generating
process. Its card lives here, as an appendix, because the DGP is *calibrated to* the
development block and a reader should meet both in one place.

**Declared truth.** For each of Hubble's 24 Table-1 design points `r_i`:

```
v_i = k_true * r_i + eps_i ,      eps_i ~ Normal(0, sigma)     (i = 1..24, independent)
```

| Parameter | Value | Where it comes from |
|---|---|---|
| `k_true` | **450.0** km/s/Mpc | declared in `study.yaml:simulation`, a round figure near the scale Table 1 exhibits. It is the TRUTH the interval must cover; nothing in the study estimates it. |
| design points `r_i` | Table 1's own 24 printed `r_mpc` values, min 0.032, max 2.0 | fixed, not resampled — so the simulation asks about **this** design, not a generic n = 24 |
| `sigma` | **232.910670** km/s | the residual standard deviation (n − 2 dof) of Table 1's free-intercept fit, measured at this gate: `data_gate_profile.py` §4. Calibrating the scatter to the real data is what makes the lab "Hubble-like"; the value is a measurement of the development block and is disclosed as such. |
| `n_obs` | 24 | matches the paper |
| `n_rep` | 1000 replicates | `study.yaml:simulation` |
| `n_boot` | 500 resamples per replicate | `study.yaml:simulation` |
| `ci_level` | 0.95 | `study.yaml:simulation` |

**Seed blocks**, declared before any cell ran (`study.yaml:simulation.seed_blocks`):

| Block | Seed | Use |
|---|---|---|
| A | 20260903 | the `estimate` track's bootstrap on the real 24 rows |
| B | 20260904 | `simulate` **development** — the coverage cells |
| C | 20260905 | `simulate` **SEALED** — a fresh block never used in development; one access |
| floor | 20260911–20260915 | Phase-0 coverage floor only; never a reported coverage |

**What "recover" means numerically.** A replicate *covers* when its 95 % interval for
the slope contains `k_true` exactly: `low <= 450.0 <= high`. **Coverage** is the
fraction of replicates that cover, and it is the `simulate` track's primary metric.
P6's rule reads it directly: `coverage >= 0.90`.

**Leakage rows for this appendix.** Rows 1–3 are **N/A — the data is generated, so
there is nothing to leak from and no partition to contaminate**; the audit of a
simulation is this card. Row 4 holds: the interval machinery is the same
`lib/hubble.py` code the estimate track runs, and it never sees `k_true`.

**In-silico scope sentence** — carried by every `known-dgp-teaching` claim this track
produces:

> Measured in a known-truth lab where the velocity–distance relation is exactly linear
> with Gaussian scatter at Hubble's 24 design points; it describes the behaviour of the
> interval machinery under that process, not the behaviour of the real universe or of
> Hubble's actual measurement errors.
