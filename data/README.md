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

## Preliminary report — `elections/results_nle2016_05122016_1545.csv`

An old 2016 NLE file with no surviving build scripts. **It is not in the same
format as the `YYYY_senators_complete.csv` files and is not pipeline-ready as
is.** Findings from inspecting it directly (2026-09-14):

### What it is
A raw election-night **transmission feed in long/tidy form** — one row per
*(precinct, candidate)* reading — not the wide per-precinct table the pipeline
expects. No header row. All contests are mixed together (party-list, senator,
president/VP, and local races) and must be filtered by contest code. The
filename timestamp is an export of 2016-05-12 15:45; the in-row timestamps are
2016-05-09 (election night, ~17:05–17:42), i.e. **early/partial returns**.

### Inferred schema (10 comma-separated columns, unlabeled)
| # | example | inferred meaning | confidence |
|---|---|---|---|
| 1 | `10030074` | precinct / VCM id (numeric only, no geography name) | high |
| 2 | `399009` | contest code — **`399009` = SENATOR** | high |
| 3 | `"PACQUIAO, MANNY (UNA)"` | candidate name (quoted; contains commas) | high |
| 4 | `163` | candidate code | high |
| 5 | `200` | **votes for this candidate in this precinct** | high |
| 6 | `36` | ballot position / sequence no. (1–50) | medium |
| 7 | `535` | precinct-level constant (registered voters or ballots) | low |
| 8 | `2318` | per-(precinct,contest) constant (≈ total senator votes) | low |
| 9 | `8` | small per-contest integer | low |
| 10 | `5/9/2016 17:07` | transmission timestamp | high |

Vote counts are recoverable: filtering contest `399009` and reading the votes
column reproduces plausible 2016 leaders per precinct (Villanueva, Recto,
Hontiveros, Drilon, Pangilinan, Lacson, Pacquiao all top the sample precinct).

### How it differs from `2019/2022/2025_senators_complete.csv`
| aspect | `*_senators_complete.csv` | this 2016 file |
|---|---|---|
| shape | **wide** — 1 row/clustered precinct, 1 column/senator | **long** — 1 row/(precinct, candidate) |
| header | yes, named columns | **none** |
| geography | `REGION … BARANGAY` names | **numeric precinct id only** |
| turnout / valid-ballot cols | `information.*`, `statistic.*` | **absent** (only unlabeled proxies, cols 7–9) |
| contests | senators only | **all races mixed** (filter by contest code) |
| normalization input | `information.numberOfValidBallot` | **not present in labeled form** |

### Coverage — the file is truncated
Exactly **1,048,576 rows = 2²⁰**, the classic spreadsheet/export row cap →
this is a **partial slice**, not the full national results:
- **5,231** distinct precincts total; **4,834** carry senator data (4,829 with
  the full 50-candidate slate, 5 partial at the cut boundary).
- For scale, the 2025 complete file has ~92,500 clustered precincts, so this
  2016 export covers only **≈5%** of a national precinct count.
- The surviving precincts span many region-code prefixes, so the truncation is
  by transmission/export order, not a clean geographic subset.

### To make it usable in this pipeline (not yet done)
1. Filter to contest `399009` (senators).
2. Pivot long→wide into a precinct × candidate vote matrix (50 candidates).
3. Recover a normalization denominator — the pipeline divides by
   `information.numberOfValidBallot`, which is **not labeled here**; cols 7–8
   are unverified candidates for a proxy.
4. Join numeric precinct ids to geography for the maps — needs an external
   precinct→location lookup (reportedly unavailable).

**Blockers:** truncation (~5% coverage), no geography names, no labeled
turnout/valid-ballot fields, and unverified secondary numeric columns. Treat
any 2016 result derived from this file as a partial-data sanity check only,
pending a complete, headered source.

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
