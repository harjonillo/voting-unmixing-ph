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
  (77,829/77,830 — the one dup is a stray total row).

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

### Data-quality issues to clean before use
- **`Total Registered Voters` is 23% missing** (18,156 NaN, 1 zero). This is the
  only normalization denominator available, and it's registered voters, not
  valid ballots — so `normalization = valid_ballots` has no exact analog here.
- **~13% of candidate vote cells are blank/non-numeric** (331,915 / 2,568,390);
  coerce to numeric and decide fill-vs-drop.
- **98 rows contain "TOTAL"-like text** (region/municipal subtotals mixed into
  the data) — must be dropped.
- Vote values range 0–975, all non-negative; per-precinct senator-vote sum ÷
  registered voters has median ≈ 7.65 (each ballot allows up to 12 senator
  votes) — consistent with real per-precinct senator votes.

### To make it usable in this pipeline
1. Read all 17 sheets (needs `xlrd>=2.0.1`; not currently in
   `voting_unmixing_ph_env`) and concatenate.
2. Drop the ~98 subtotal/total rows; coerce vote cells to numeric.
3. Rename geography columns to the `REGION/PROVINCE/CITY_MUNICIPALITY/BARANGAY`
   convention and reformat candidate headers if matching the other years.
4. Choose a normalization denominator — only `Total Registered Voters` exists
   (23% missing); either impute, drop those precincts, or use `row_max`/`none`
   normalization instead of `valid_ballots`.

**Verdict:** a solid, near-complete national per-precinct senator dataset —
recommended as the 2013 source once cleaned. The main compromises are the
missing valid-ballot/turnout fields (registered-voter proxy only) and the 23%
gap in that proxy.
