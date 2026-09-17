# Data provenance

Everything in this folder is **gitignored** (except this README). Rebuild it as follows.

## Copied from `../2025-PH-elections/data/`

| file | description |
|---|---|
| `2025_senators_complete.csv` | Per clustered precinct: geography, turnout stats, votes per senatorial candidate (2025 NLE). |
| `2025_senators_filtered.csv` | Same, filtered version used by older notebooks. |
| `2025_clustered_precincts_*.txt` | Precinct ID lists (all / local / overseas). |
| `results_hannahtest/` | MATLAB unmixing outputs (N-FINDR pre-estimate spectra + coefficients), kept for cross-checking. |

## Copied from `BSthesis-main-2` (previous advisee's shapefiles)

- `shapefiles/regions/Regions.shp` (+ sidecars)
- `shapefiles/provinces/Provinces.shp` (+ sidecars)

## Downloaded

- `shapefiles/municipalities.geojson` — municipal/city boundaries
  (see `scripts/fetch_boundaries.py`; optional, the app falls back to
  region/province maps if this file is missing).

## Generated

- `processed/` — outputs of `scripts/run_pipeline.py`
  (`endmembers.csv`, `abundances.parquet`, `meta.json`). The Streamlit app
  reads only these + the shapefiles.

## 2016 — `elections/results_nle2016_05092016_1950.txt`

Two 2016 exports of the same election-night transmission feed exist outside the
repo. The **larger, current one** is
`results_nle2016_05092016_1950.txt` (pipe-delimited, ~390 MB, ~4.97 M rows); it
supersedes the older, truncated `results_nle2016_05122016_1545.csv`. Audited
2026-09-17. **The senator votes are built into the pipeline and geocoded**
(below). The feed itself has no place names; geography is recovered separately
from COMELEC's 2016 Project of Precincts (see *Geography* below). 2016 remains a
**partial** source (~25% coverage) — not a complete national result.

### What it is
A raw election-night **transmission feed in long/tidy form** — one row per
*(precinct, candidate)* reading — not the wide per-precinct table the pipeline
expects. No header row. All contests are mixed together (president, VP, senator,
party-list, and local races) and must be filtered by contest code. In-row
timestamps run to **2016-05-09 18:37** (election night), i.e. **partial
returns**.

### Schema (10 pipe-delimited columns, unlabeled)
| # | example | meaning | confidence |
|---|---|---|---|
| 1 | `10030074` | precinct / VCM id — 8-digit, numeric only, no geography | high |
| 2 | `00399009` | contest code — **`00399009` = SENATOR** | high |
| 3 | `SOTTO, VICENTE (NPC)` | candidate `SURNAME, NAME (PARTY)` | high |
| 4 | `099` | candidate code | high |
| 5 | `199` | **votes for this candidate in this precinct** | high |
| 6 | `46` | ballot position / sequence no. (1–50) | medium |
| 7 | `535` | precinct-level constant (≈ registered voters) | low |
| 8 | `2318` | per-(precinct,contest) constant (≈ total senator votes) | low |
| 9 | `8` | small per-contest integer | low |
| 10 | `05/09/2016 17:07:49` | transmission timestamp | high |

Contest row counts: party-list `01199009` 2.64 M, **senator `00399009` 1.15 M**,
VP `00299009` 138 k, president `00199009` 138 k, then many local contests. The
senator national tally reproduces the real 2016 top tier (Villanueva, Drilon,
Sotto, Gordon, Lacson, Hontiveros, Pangilinan, Zubiri, Gatchalian, Pacquiao,
Recto, de Lima), so the feed is parsed correctly.

### Coverage — larger than the old file, but still partial (~25%)
- **22,986** precincts carry senator data (22,970 with the full 50-candidate
  slate; a handful partial). That is **~25%** of the ~92,509 clustered precincts
  nationally — a large election-night snapshot, **not** complete national
  results.
- No longer truncated at 2²⁰: the old `…_1545.csv` was capped at exactly
  1,048,576 rows (4,834 senator precincts, ~5%). This file is ~4.75× larger.
- **The two files are not complementary — do not merge them.** The old CSV
  stored precinct ids as integers, dropping leading zeros; once those are
  restored (zero-pad to 8 digits) its senator precincts are a **strict subset**
  of this feed (0 precincts unique to the old file). So this file alone is the
  source; the old one adds nothing.

### How it differs from `2019/2022/2025_senators_complete.csv`
| aspect | `*_senators_complete.csv` | this 2016 file |
|---|---|---|
| shape | **wide** — 1 row/clustered precinct, 1 column/senator | **long** — 1 row/(precinct, candidate) |
| delimiter / header | comma, named header | **pipe, no header** |
| geography | `REGION … BARANGAY` names | **numeric precinct id only** |
| turnout / valid-ballot cols | `information.*`, `statistic.*` | **absent** (only unlabeled proxies, cols 7–9) |
| contests | senators only | **all races mixed** (filter by contest code) |
| normalization input | `information.numberOfValidBallot` | **not present** (uses `row_max`, as 2013 does) |

### Geography — recovered from the 2016 Project of Precincts
The feed carries only an 8-digit precinct id. `scripts/scrape_2016_pop.py` builds
a `precinct → REGION, PROVINCE, CITY_MUNICIPALITY, BARANGAY` lookup
(`data/elections/2016_precinct_geo.csv`) from COMELEC's public 2016 POP. That page
looks click-only but is served as **static HTML fragments** (no API/JS needed):

    html-scripts/2016NLE/province2016.html                          (province list)
    php-sys-generated/2016NLE/pop-2016nle/prov_<P>/prov_list<P>2016.html   (municipalities)
    php-sys-generated/2016NLE/pop-2016nle/prov_<P>/mun_<M>/mun_pop<M>2016.html  (precinct table)

The precinct table gives barangay + cluster number, and the feed's id decodes as
**`province(2) + municipality-within-province(2) + cluster-number(4)`** (verified:
ABRA/BANGUED cluster 3 → `01 01 0003` → `01010003`; matches the 2019 CSV's
`CLUSTERED_PRECINCT` `1010001` with its leading zero dropped). REGION is not on the
POP page — it is joined from the 2013 CSV's province→region map (same ARMM/CARAGA
era), NCR by code, with two special provinces (Cotabato City, Isabela City) fixed
in `REGION_OVERRIDES`. NCR / big cities are split into legislative districts on the
POP page with cluster numbers that don't key uniquely to the feed, so those ids are
**filled from the 2019 CSV** instead. Net: **97.9%** of the feed's precincts get
geography (22,016 from POP + 482 from 2019); the ~2% remainder stay `PLACEHOLDER`.
The lookup joins the shapefiles about as well as 2019 (municipality match ~0.95).

### DONE — `2016_senators_complete.csv` built, geocoded, and run
`scripts/prepare_2016_csv.py` + `configs/config_2016.ini` produce and consume a
2016 dataset, mirroring the 2013 setup:

- **CSV** (`data/elections/2016_senators_complete.csv`, 22,986 precincts × 50
  candidates), built by `scripts/prepare_2016_csv.py --geo-lookup
  data/elections/2016_precinct_geo.csv`: filters the feed to contest `00399009`,
  pivots long→wide, joins geography, and writes the 2013-style schema
  (`REGION, PROVINCE, CITY_MUNICIPALITY, BARANGAY, CLUSTERED_PRECINCT,
  information.numberOfRegisteredVoters`, then 50 `N. ` candidate columns,
  `sen_col_start = 6`). Precinct ids are kept zero-padded to 8 digits. col 7 is
  stored as the registered-voters proxy (unverified; `row_max` does not use it).
  The ~2% of precincts without a POP/2019 match keep `PLACEHOLDER` geography and
  drop out of the province/municipality maps (like other years' unmatched rows).
- **Pipeline** (`config_2016.ini`, `normalization = row_max`, `n_archetypes =
  4`): all 50 candidates and all 22,986 precincts pass the filters; HySime
  `kf = 6`; reconstruction RMSE ≈ 0.084 (row_max scale). The four archetypes are
  politically coherent: an LP/administration bloc (Drilon, De Lima, Pangilinan),
  an independents bloc (Gordon, Zubiri, Tolentino), the broad national leaders
  (Sotto, Villanueva, Lacson), and an Eastern-Visayas regional signature
  (Romualdez, Petilla). `n_archetypes = 4` matches 2013 for cross-year
  comparability.
- **Sweep** (`scripts/run_sweep.py --config configs/config_2016.ini`): run for
  p2–p7 (now possible — the municipal aggregation has real geography).
- **Sanity checks**: 2016 is wired into `notebooks/07_cross_year_sanity_checks`
  (`YEARS` includes `2016`); its region section now shows real regions plus a
  small `PLACEHOLDER` bucket.

**Caveats for 2016:** ~25% national coverage (an election-night snapshot, so the
leaderboard *ranking* is provisional, and whole big cities like Manila/QC that
transmitted after ~18:37 are absent); no turnout layer (no actual-voter counts,
so the weighted/unweighted map toggle is identical, as in 2013); and ~2% of
precincts geographically unplaced. A complete national feed would supersede it.

## Preliminary report — `2013_per_precincts_senators.xls`

Located outside the repo at
`research_hyperspectral_unmixing/datasets/elections/2013_per_precincts_senators.xls`.
A genuine legacy Excel binary (OLE2 `.xls`, 26 MB, authored 2013-07-08).
Inspected 2026-09-14. **This one is close to the pipeline format and usable
with moderate cleaning** — unlike the 2016 file.

### What it is
A **wide, per-precinct senator table**, already the right shape (one row per
precinct, one column per candidate). Split across **17 sheets, one per region**
(`Region 1`…`Region 12`, `ARMM`, `CARAGA`, `CAR`, `NCR`); concatenating them
gives one national table. Precinct-level granularity (not clustered precincts).

### Structure (consistent across all 17 sheets: 39 columns)
- 6 leading columns: `Region`, `Province`, `Municipality/City`, `Barangay`,
  `Precinct Code`, `Total Registered Voters`.
- 33 candidate columns — the full 2013 senatorial slate (`ALCANTARA, SAMSON
  (SJS)` … `ZUBIRI, MIGZ (UNA)`), header format `SURNAME, NAME (PARTY)`.
- Combined: **77,830 precinct rows**; precinct codes essentially unique
  (77,829/77,830, one duplicate). No subtotal/total rows — an earlier count of
  "98 TOTAL-like rows" was a false positive from barangays named "… GRANDE".

### How it compares to `2019/2022/2025_senators_complete.csv`
| aspect | `*_senators_complete.csv` | this 2013 file |
|---|---|---|
| shape | wide, 1 row/clustered precinct | **wide, 1 row/precinct** ✓ same idea |
| file layout | single CSV | **17 region sheets** (concatenate) |
| header | yes | **yes** ✓ |
| geography | `REGION … BARANGAY` | `Region … Barangay` ✓ (rename to match) |
| candidate cols | `N. SURNAME NAME (PARTY)` | `SURNAME, NAME (PARTY)` (no rank prefix) |
| normalization input | `information.numberOfValidBallot` | **only `Total Registered Voters`** (proxy) |
| turnout / valid-votes stats | present | **absent** |
| granularity | clustered precincts | individual precincts |

### Data-quality notes
- **~18,150 rows (23%) are empty placeholder precincts** — no votes *and* no
  registered voters (the two blanks overlap on 18,149 rows). These are not
  precincts with missing data; among the ~59,700 vote-bearing precincts,
  registered voters is essentially complete (only 8 zeros). So the earlier
  framing of "23% missing registration" was really just these empty rows, which
  the pipeline drops on its own (total votes < 1). They ARE geographically
  skewed — as a share of each region's rows: ARMM ~65%, Region IX / CAR ~38%,
  Region II / X ~30%, down to NCR ~9%. That skew is why a registration-based
  normalization was rejected (it would have thinned ARMM/Mindanao/CAR); `row_max`
  sidesteps it, and because the skew lives entirely in dropped empty rows the
  retained precincts and their maps are not biased by it.
- Blank candidate cells = 0 votes (filled with 0 when building the CSV).
- Only `Total Registered Voters` is available as a size/denominator — no
  valid-ballot or turnout stats — so `normalization = valid_ballots` has no
  analog; the build uses `row_max` (self-contained, keeps every real precinct).
- Vote values range 0–975; per-precinct senator-vote sum ÷ registered voters has
  median ≈ 7.65 (a ballot allows up to 12 senator votes) — consistent with real
  per-precinct senator votes.

### Region/province naming vs the newer years
2013's geography strings do not match the 2019/2022/2025 conventions, which
matters because `src/geo.py` matches on normalized names and the site derives
region polygons from the data's own province→region map. What differs and how
`scripts/prepare_2013_csv.py` reconciles it:

- **Region codes are dotted / spaced**: `N.C.R.`, `C.A.R`, `A.R.M.M`,
  `Region IV - A`. The other years use `NCR`, `CAR`, `BARMM`, `REGION IV-A`.
  The builder upper-cases, strips periods, and tightens `" - "`→`"-"`, giving
  `NCR / CAR / ARMM / REGION IV-A / …`.
- **NCR is the load-bearing one**: `src/geo.py:canonical_province` maps a
  province to `METROPOLITAN MANILA` *only when the region normalizes to `NCR`*.
  Raw `N.C.R.` normalizes to `N C R` (≠ `NCR`), which would silently drop all of
  Metro Manila from the province/region maps — hence the explicit fix.
- **NCR province strings**: 2013 uses the long `NATIONAL CAPITAL REGION - MANILA`
  form (same as 2019); 2025 uses `NCR - MANILA`. Both resolve via the region-based
  NCR rule, so no per-string mapping is needed, but the municipality-level
  Manila-district dissolve (keyed on `PROVINCE == "NCR - MANILA"`) doesn't fire
  for 2013 — same behavior as 2019.
- **Region set differs by era**: 2013 has `ARMM` (not `BARMM`) and labels Caraga
  `CARAGA` (the others use `REGION XIII`), and it has no Negros Island Region.
  Region geometry is dissolved per year from that year's province→region map, so
  these labels stay internally consistent and need no cross-year alignment beyond
  NCR.
- **Provinces/municipalities** are already upper-case and match by name through
  the existing `src/geo.py` alias/variant logic (2013-era names like
  `COMPOSTELA VALLEY` are handled by the same `PROVINCE_ALIASES`).
- **Match outcome**: 17 regions, 81 provinces, 1,497 municipalities join to the
  shared shapefiles — comparable to the other years.

### DONE — `2013_senators_complete.csv` built and wired into the site
`scripts/prepare_2013_csv.py` + `configs/config_2013.ini` now produce and
consume a 2013 dataset (reading the `.xls` needs `xlrd>=2.0.1`, now in
`requirements.txt`):

- **CSV** (`data/elections/2013_senators_complete.csv`, 77,830 rows), built by
  `scripts/prepare_2013_csv.py`: columns `REGION, PROVINCE, CITY_MUNICIPALITY,
  BARANGAY, CLUSTERED_PRECINCT, information.numberOfRegisteredVoters`, then 33
  candidate columns prefixed `N. ` (so `candidate_label`'s `.`-split keeps names
  like `ENRILE, JUAN PONCE JR.(NPC)`). `REGION` canonicalized to the other
  years' scheme (`N.C.R.`→`NCR`, `Region IV - A`→`REGION IV-A`, …).
- **Pipeline** (`config_2013.ini`, `sen_col_start = 6`, `normalization =
  row_max`, `n_archetypes = 4`): filters to 31 candidates × 59,679 precincts
  (2 fringe candidates below the 25th-pctile cut; empty rows dropped),
  reconstruction RMSE ≈ 0.094 (row_max scale — not comparable to the
  valid-ballot years). Top archetype loads on **POE, GRACE** (the 2013
  topnotcher). `n_archetypes = 4` chosen over HySime's kf(=4)/2019-matching 5
  because the sweep is far more stable at p=4 (~0.97 vs ~0.78 mean cosine).
- **Sweep** (`run_sweep.py`) run for p2–p7. `run_sweep` now uses uniform weights
  when no valid-ballot column exists, so 2013's weighted view equals its
  unweighted view (matching `build_static`'s own fallback) instead of crashing.
- **Site**: `build_static.py` `YEARS` now includes `2013`; `site/data` rebuilt
  and the shell regenerated. The year selector picks up 2013 from the manifest.

**Caveats for 2013 on the site:** no turnout layer (no actual-voter counts), and
the ballot-weighted / unweighted map toggle shows identical maps (uniform
weighting). Everything else — region/province/municipality maps, loadings, the
p-sweep comparison and lineage — is populated.
