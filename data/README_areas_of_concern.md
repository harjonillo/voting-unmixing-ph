# Election areas-of-concern / watchlist dataset (2013–2025)

**Built:** 2026-10-27. Which cities/municipalities were tagged as COMELEC/PNP election
security "hotspots" — *election watchlist areas* (EWAs), *areas of concern*, the
green/yellow/orange/red categories, and placements **under COMELEC control** — for the
five Senate elections in this repo, keyed to the exact vote-CSV labels.

## Why this exists (and why it's from news)

- **COMELEC does not publish these lists as documents.** Nothing on comelec.gov.ph
  (checked 2026-10-27). Classifications are approved by the COMELEC en banc / regional
  joint security control centres (RJSCC: COMELEC + PNP + AFP) on PNP/AFP
  recommendations, then **announced at press briefings and on COMELEC's Facebook page**.
  The only formal documents are the resolutions placing areas under COMELEC control
  (e.g. Res. No. 10531 in 2019, Res. No. 11131 in 2025).
- So, like [`README_coalitions.md`](README_coalitions.md), this is compiled from
  **contemporaneous news** (no Facebook posts). National outlets usually reported counts;
  **town names mostly came from regional reports**, so coverage before 2025 is partial.
- **2025 is the exception:** PCIJ published the full municipality-level classification
  of all 1,642 LGUs as a Datawrapper table (January 9 and March 19 lists), whose totals match
  COMELEC's announced counts exactly (Mar 19: 36 red / 156 orange / 194 yellow / 1,256 green).

> **Version control:** like the coalitions file, this CSV is hand-curated and **committed**
> (explicit `.gitignore` exception), unlike the re-downloadable vote dumps in `elections/`.

## The file

`elections/areas_of_concern_2013-2025.csv` — **one row per (place, category, source,
snapshot)**. Lists changed through each campaign, so the same town can appear several
times in a year (different snapshot dates, issuers, or outlets). That is intentional: pick
the snapshot you need with `list_as_of` / `issuer`, don't treat rows as unique towns.

### Schema

| column | meaning |
|---|---|
| `year` | Election year (2013, 2016, 2019, 2022, 2025 — May national/local polls only; no BSKE, no BARMM parliamentary). |
| `level` | `municipality` (a named city/town), `province` (a whole-province designation, e.g. 2016 "entire province of Siquijor", 2022 Misamis Occidental under COMELEC control), or `aggregate` (a count only — the number is in `notes`). |
| `category_std` | Harmonized category — see the next table. Blank on aggregate rows that don't carry one. |
| `category_as_reported` | The article's own wording, verbatim. |
| `scheme` | `color` (green/yellow/orange/red), `EWA category` (2013–16 numbered categories), `comelec_control`, or `other`. |
| `provisional` | `True` when the row is a recommendation / initial / "possible" / pending list rather than an approved classification (detected from the wording, issuer and notes). |
| `issuer` | Who issued the list (COMELEC en banc, regional COMELEC, RJSCC, PNP regional/provincial office, …). A **PNP recommendation is not a COMELEC classification** — filter on this if it matters. |
| `list_as_of` | Date the list was valid (YYYY-MM-DD, or YYYY-MM / YYYY when only that is known). |
| `province_as_reported`, `municipality_as_reported` | Place names **exactly as printed**, typos included (e.g. "Bueva Ecija", "Lanao del Dur"). |
| `PROVINCE`, `CITY_MUNICIPALITY` | **Join keys:** the exact labels in that year's `elections/<year>_senators_complete.csv`. Blank for province/aggregate rows and for towns absent from that year's vote data. |
| `in_vote_data` | Whether the join keys are filled. |
| `match` | `exact` (name normalization only), `manual` (spelling/rename resolved by hand — all listed below), `not_in_vote_data`. |
| `source_outlet`, `source_title`, `source_url`, `source_date` | The article. |
| `verified` | `fetched` = the article text was read; `snippet` = only the search-engine snippet could be read (the site blocked access) — treat as lower confidence. |
| `notes` | Count for aggregate rows, flagged news errors, conflicts between sources, confidence remarks. |

### `category_std`

| value | includes |
|---|---|
| `red` | red; "area of grave concern"; EWA Category 3 |
| `orange` | orange; "area of immediate concern"; EWA Category 2 |
| `yellow` | yellow; EWA Category 1; bare "area of concern" **only** in sources that use the three-tier concern / immediate / grave wording |
| `green` | green / "no security concern" (only where a source listed it explicitly) |
| `comelec_control` | placed under COMELEC control (always also a red-level area) |
| `comelec_control_pending` | "approved in principle" / under consideration for control (2016) |
| `watchlist_unspecified` | on a watchlist / "area of concern" / EWA with **no tier given** (most of 2013–16) |
| `failure_of_election` | 2022 Lanao del Sur failure-of-election declarations (not a security tier; kept for context) |
| `other` | "areas of interest" (explicitly *not* EWAs), downgrade/removal proposals, unclear wording |

The 2013–16 numbered EWA categories map onto the later colours **by order**, not by
identical definition. In 2016, Cat 1 was political rivalry, Cat 2 the presence of armed
groups and Cat 3 both, which parallels yellow/orange/red. 2013 reporting also used
"immediate" and "grave" concern for Cat 2 and Cat 3.

### Joining back to votes

`(year, PROVINCE, CITY_MUNICIPALITY)` matches the vote CSV columns
`(PROVINCE, CITY_MUNICIPALITY)` byte-for-byte. One exception: **2019 Manila** is
`CITY_MUNICIPALITY = "MANILA"`, but the vote CSV lists Manila by district (Tondo,
Binondo, …). `src/geo.py` merges those districts the same way. Matching rules: names
must match within the **reported province**, or within the **reported region** when an
article named only a region. A town is never matched by name alone across provinces.

## How it was built

1. Four research passes (2013+2016, 2019, 2022, 2025) searched national and regional
   outlets and recorded only places that an article names with a category. Each row
   carries its own URL.
2. 2025 rows come mainly from PCIJ's Datawrapper dataset
   (`https://datawrapper.dwcdn.net/iBHG3/2/dataset.csv`), one row per LGU per snapshot
   (Jan 9, Mar 19). Its **green rows are omitted**: PCIJ covers every LGU, so for 2025 any
   LGU absent from the PCIJ rows was green.
3. Names were matched to each year's vote-CSV labels. 87 rows needed manual resolution
   (listed below); every match is province-checked.
4. National totals cross-checked: the 2025 Mar 19 PCIJ rows reproduce COMELEC's
   36/156/194 exactly.

There is no rebuild script. The CSV itself is the curated source, so edit it directly
and keep the schema. To add a source, append rows with its URL.

## Coverage summary

Named-LGU rows by `category_std` (rows, not distinct towns; snapshots repeat):

| category_std | 2013 | 2016 | 2019 | 2022 | 2025 |
|---|---:|---:|---:|---:|---:|
| `red` | 0 | 1 | 129 | 48 | 166 |
| `orange` | 0 | 27 | 92 | 51 | 363 |
| `yellow` | 0 | 3 | 103 | 40 | 436 |
| `green` | 0 | 0 | 18 | 23 | 0 |
| `comelec_control` | 0 | 3 | 13 | 64 | 7 |
| `comelec_control_pending` | 0 | 3 | 0 | 0 | 0 |
| `watchlist_unspecified` | 42 | 136 | 19 | 8 | 0 |
| `failure_of_election` | 0 | 0 | 0 | 3 | 0 |
| `other` | 0 | 23 | 10 | 0 | 0 |
| **all named-LGU rows** | 42 | 196 | 384 | 237 | 972 |

All rows (incl. province/aggregate): 2013: 87, 2016: 275, 2019: 453, 2022: 271, 2025: 989 — total 2075; `snippet` rows: 97; distinct sources: 121.

Distinct LGUs matched to vote data (any category): 2013: 41, 2016: 174, 2019: 180, 2022: 163, 2025: 460.

## Per-year notes and caveats

### 2013 — almost entirely province-level
- National designations were **provinces**: DILG/PNP's 15 "high-risk" provinces (Nov 2012),
  COMELEC's 15–16 "areas of concern" (Mar 2013, Inquirer, snippet), with Sulu and Misamis
  Oriental added late. COMELEC said on 2013-04-29 that no area was yet under "grave
  concern" (snippet).
- Town names exist only for **Central Visayas** (33 AFP-PNP hotspots, Jan 2013 — the
  article says 34; Cebu province not stated but all are Cebu LGUs, resolved manually),
  **La Union** (Tubao, Agoo; Caba/Aringay are "traditional" hotspots only), and
  retrospective mentions in 2016 articles (Bangued, Dolores, Lagayan, Bogo, San Carlos).
- Rappler's headline "Comelec-controlled Nueva Ecija" is the only hint of a 2013 control
  placement. It is low confidence, and GMA (2016) contradicts it.

### 2016 — EWA categories, regional lists
- PNP's national tally: 260 EWAs in 10 regions (GMA News Research, Apr 2016). Per-province
  counts for 35 provinces come from GMA's infographic image (aggregate rows). National
  category totals: Cat 1 = 133, Cat 2 = 54, Cat 3 = 99 municipalities. GMA says these
  cover "the six provinces", which is implausible, so they are probably national.
- Named lists: Northern Mindanao (53), Central Luzon (all LGUs; 24 + 17 Nueva Ecija named),
  Davao Region (preliminary), Region 12 (10), Bohol (7), Cebu (3 snapshots), Negros Island
  (Guihulngan **Cat 3**, 7 NegOr **Cat 2** — the only per-town category numbers found).
- **Most 2016 town rows have no tier** (`watchlist_unspecified`).
- COMELEC control: **Pantar, Lanao del Norte** (en banc, 2016-04-26; resolution number not
  given). Abra (whole province) and Marawi were "approved in principle" 2016-05-03/04.
  Philstar wrongly puts Pantar in Lanao del Sur.
- Western Visayas had **zero** EWAs. Its 21 "areas of interest" are recorded as `other`.
- The 2016 vote data covers only part of the country (recovered subset), so 8 named towns
  are `not_in_vote_data`.

### 2019 — colours from Feb 12; Mindanao red en bloc
- Scheme timeline: PNP Category 3 "grave concern" lists of 18 (Dec 29) and 19 (Jan 14).
  Colours from Feb 12 (Res. No. 10481). On Mar 19 COMELEC put **the whole Mindanao island
  group** (454 LGUs; one region-level row, not itemized), all of Abra, Jones (Isabela) and
  Lope de Vega (Northern Samar) in red.
- **Main source:** SunStar Manila 2019-05-10, which carries **COMELEC Res. No. 10531**
  (May 6): the red list for NCR, Luzon and the Visayas, Cebu orange/yellow, and COMELEC
  control of **Daraga, Cotabato City (since ~Jan 15) and Moises Padilla (May 6)**. The
  article gives Abra, Masbate, Negros Oriental and the Samars without town names.
- Good regional lists: Western Visayas (PRO-6; red/orange/yellow), Negros Occidental (PJSCC,
  incl. green), Negros Oriental, Cordillera (Abra, Lubuagan), Samar 1st district.
- National totals don't reconcile across outlets (941 vs 943 vs 946; PhilStar's parts sum
  to 941). ABS-CBN says NCR had no areas of concern on the same day others list 5 yellow
  NCR cities.
- **Cotabato City and Sultan Dumalondong are not in the 2019 vote data** (`not_in_vote_data`).
- Inquirer (Cloudflare) and old PNA URLs (404 since PNA's site migration) could not be
  read. PNA text was read via PTV News reposts where available. The rest is `snippet`.

### 2022 — national red list (104 + 14) never published by name
- COMELEC said 104 municipalities + 14 cities were red but did not release names; the PNP
  recommended 100 + 14, the DILG cited 105 + 15. All are kept as aggregate rows.
- Named content: **COMELEC control** (the fullest list: 24 towns + 4 cities as of May 4,
  GMA 2022-05-06; earlier Tubaran/Malabang, then 6 Maguindanao towns + Marawi + Maguing,
  then Pilar (Abra) and **all of Misamis Occidental**). Also PRO-BARMM's red list (16 towns
  + 2 cities), Negros Occidental (3 snapshots, three-tier wording), Bohol, Pangasinan (7
  orange, COMELEC en banc), Batangas, Zamboanga del Norte, Pilar (Abra) orange→red (Apr 29).
- Many 2022 lists are **provincial/regional PNP**, not COMELEC — see `issuer`. In late
  March COMELEC was re-verifying PNP lists, and some red areas moved to green and back.
- Northern Mindanao police listed **barangays**, not towns. Only barangay counts are
  recorded (aggregate rows).
- The MNLF/MILF "high-risk" towns in Lanao del Norte are not an official list (`other`
  scheme, `watchlist_unspecified`).

### 2025 — complete (PCIJ), two snapshots
- **Mar 19 snapshot (high confidence):** PCIJ's table totals 36/156/194/1,256, matching
  COMELEC exactly. Its 36 reds equal GMA's Mar 19 list, and its regional orange counts equal
  Inquirer's.
- **Jan 9 snapshot (medium confidence):** PCIJ totals 38/178/187 vs COMELEC's announced
  38/177/188. Its regional yellow counts differ from Inquirer's January breakdown (BARMM 35
  vs 49, Zamboanga Peninsula 32 vs 18).
- GMA's Jan 9 article names only 36 of the 38 reds (missing Balindong and Pandag) and
  prints **"Mangudadatu, Tawi-Tawi"** — a typo for Maguindanao del Sur (resolved manually).
  GMA calls them "proposed" reds.
- **Conflict:** Inquirer (2025-03-20) lists Datu Hoffer Ampatuan and Shariff Aguak as
  orange→red. GMA, PCIJ and Malaya's province count all have them orange. Both are kept, and
  the Inquirer rows are flagged in `notes`.
- COMELEC control: **Datu Odin Sinsuat** (2025-04-04) and **Buluan** (2025-04-15, Res.
  No. 11131). PCIJ's map dates Buluan to Apr 25, which looks wrong. Abra was petitioned
  but not placed under control.
- **No town-level list after Mar 19 was found.** PNP gave only counts (362 areas, 34 red,
  as of Apr 15).
- Sulu appears under Region 9 in PCIJ (after the 2024 Supreme Court ruling removing it from
  BARMM). Several renamed Sulu/Maguindanao/Lanao towns needed manual matching (below).
- The 2025 Cebu/Bohol "yellow" rows (5) are a **recommendation** pending the Apr 28 RJSCC.
  The outcome was not found (`provisional`).

## Judgement calls (read before analysis)

1. **Snapshots, not a single list.** Use `list_as_of` to choose. For "final pre-election
   status", take each town's latest approved (`provisional == False`) row, and remember
   that before 2025 the absence of a row does **not** mean green.
2. **Coverage is uneven and regional before 2025.** Absence = "not reported in an article
   we could read", not "not on the list". Don't treat the pre-2025 data as a complete
   national treatment indicator.
3. **Issuer heterogeneity.** PNP provincial lists, RJSCC lists and COMELEC en banc
   classifications are mixed. Filter on `issuer` for a stricter definition.
4. **Manual name resolutions involving a guess** (all others are unambiguous spelling
   variants or official renamings):
   - 2019 "Cagayan, Negros Occidental" → CAUAYAN (no Cagayan exists in NegOcc).
   - 2019 "Cabaldon" → GABALDON.
   - 2019 "Polar, Cebu" → PILAR.
   - 2019 "Dumalundong" → Sultan Dumalondong.
   - 2016 "Median" → MEDINA.
   - 2013/2016 Cebu towns with no province in the article → CEBU (Cebu City dateline,
     regional list).
5. **Snippet rows** (97, from Inquirer/Manila Bulletin/PNA/PressReader, which blocked
   access) were not read in full. Their names and categories come from search-engine
   excerpts.

## Manual name resolutions (`match == "manual"`)

| year | as reported | matched to |
|---|---|---|
| 2013 | Danao (city), — | DANAO CITY, CEBU |
| 2013 | Pinamungajan, — | PINAMUNGAHAN, CEBU |
| 2013 | San Fernando, — | SAN FERNANDO, CEBU |
| 2013 | Sta. Fe, — | SANTA FE, CEBU |
| 2013 | Sogod, — | SOGOD, CEBU |
| 2013 | Tuburan, — | TUBURAN, CEBU |
| 2016 | Baliwag, Bulacan | BALIUAG, BULACAN |
| 2016 | San Francisco, — | SAN FRANCISCO, CEBU |
| 2016 | Kolambogan, Lanao del Norte | KOLAMBUGAN, LANAO DEL NORTE |
| 2016 | Tangkal, Lanao del Norte | TANGCAL, LANAO DEL NORTE |
| 2016 | Ozamiz, Misamis Occidental | OZAMIS CITY, MISAMIS OCCIDENTAL |
| 2016 | Median, Misamis Oriental | MEDINA, MISAMIS ORIENTAL |
| 2016 | Senator Ninoy Aquino, Sultan Kudarat | SEN. NINOY AQUINO, SULTAN KUDARAT |
| 2019 | Valderama, Antique | VALDERRAMA, ANTIQUE |
| 2019 | Emery, Batangas | LEMERY, BATANGAS |
| 2019 | Polar, Cebu | PILAR, CEBU |
| 2019 | Balaon, La Union | BALAOAN, LA UNION |
| 2019 | Balawan, La Union | BALAOAN, LA UNION |
| 2019 | Manila, Metro Manila (NCR) | MANILA, NATIONAL CAPITAL REGION - MANILA |
| 2019 | Manila, NCR | MANILA, NATIONAL CAPITAL REGION - MANILA |
| 2019 | Cagayan, Negros Occidental | CAUAYAN, NEGROS OCCIDENTAL |
| 2019 | E.B. Magalona, Negros Occidental | ENRIQUE B. MAGALONA (SARAVIA), NEGROS OCCIDENTAL |
| 2019 | EB Magalona, Negros Occidental | ENRIQUE B. MAGALONA (SARAVIA), NEGROS OCCIDENTAL |
| 2019 | Don Salvador Benedicto, Negros Occidental | SALVADOR BENEDICTO, NEGROS OCCIDENTAL |
| 2019 | Sipalag City, Negros Occidental | SIPALAY CITY, NEGROS OCCIDENTAL |
| 2019 | Aliaga, Bueva Ecija | ALIAGA, NUEVA ECIJA |
| 2019 | Bongabon, Bueva Ecija | BONGABON, NUEVA ECIJA |
| 2019 | Carranglan, Bueva Ecija | CARRANGLAN, NUEVA ECIJA |
| 2019 | Cabaldon, Bueva Ecija | GABALDON (BITULOK AND SABANI), NUEVA ECIJA |
| 2019 | General Natividad, Bueva Ecija | GENERAL MAMERTO NATIVIDAD, NUEVA ECIJA |
| 2019 | Guimba, Bueva Ecija | GUIMBA, NUEVA ECIJA |
| 2019 | Pantabangan, Bueva Ecija | PANTABANGAN, NUEVA ECIJA |
| 2019 | Rizal, Bueva Ecija | RIZAL, NUEVA ECIJA |
| 2019 | Pagsangjan, Samar | PAGSANGHAN, SAMAR (WESTERN SAMAR) |
| 2022 | Baliwag, Bulacan | BALIUAG, BULACAN |
| 2022 | Tuburan, Lanao del Sur | TUBARAN, LANAO DEL SUR |
| 2022 | Ozamiz City, Misamis Occidental | CITY OF OZAMIS, MISAMIS OCCIDENTAL |
| 2022 | Don Salvador Benedicto, Negros Occidental | SALVADOR BENEDICTO, NEGROS OCCIDENTAL |
| 2025 | SAN LORENZO, Camarines Norte | SAN LORENZO RUIZ, CAMARINES NORTE |
| 2025 | Balindong Watu, Lanao del Dur | BALINDONG, LANAO DEL SUR |
| 2025 | BALINDONG WATU, Lanao del Sur | BALINDONG, LANAO DEL SUR |
| 2025 | BUADIPUSO BUNTONG, Lanao del Sur | BUADIPOSO-BUNTONG, LANAO DEL SUR |
| 2025 | Buadipuso Buntong, Lanao del Sur | BUADIPOSO-BUNTONG, LANAO DEL SUR |
| 2025 | LUMBA BAYABAO MAGUING, Lanao del Sur | LUMBA-BAYABAO, LANAO DEL SUR |
| 2025 | PAGAYAWAN TATARIKAN, Lanao del Sur | PAGAYAWAN, LANAO DEL SUR |
| 2025 | PICONG SULTAN GUMANDER, Lanao del Sur | PICONG, LANAO DEL SUR |
| 2025 | POONA BAYABAO GATA, Lanao del Sur | POONA BAYABAO, LANAO DEL SUR |
| 2025 | DATU BLAH SINSUAT, Maguindanao del Norte | DATU BLAH T. SINSUAT, MAGUINDANAO DEL NORTE |
| 2025 | DATU ABDULAH SANGKI, Maguindanao del Sur | DATU ABDULLAH SANGKI, MAGUINDANAO DEL SUR |
| 2025 | GSK PENDATUN, Maguindanao del Sur | GEN. S. K. PENDATUN, MAGUINDANAO DEL SUR |
| 2025 | Mangudadatu, Tawi-Tawi | MANGUDADATU, MAGUINDANAO DEL SUR |
| 2025 | DATU MONTAWAL, Maguindanao del Sur | PAGAGAWAN, MAGUINDANAO DEL SUR |
| 2025 | Rajan Buayan, Maguindanao del Sur | RAJAH BUAYAN, MAGUINDANAO DEL SUR |
| 2025 | Shariff Saydon Mustapha, Maguindanao del Sur | SHARIFF SAYDONA MUSTAPHA, MAGUINDANAO DEL SUR |
| 2025 | SULTAN SA BARONGIS LAMBAYONG, Maguindanao del Sur | SULTAN SA BARONGIS, MAGUINDANAO DEL SUR |
| 2025 | Sultan Barongis Lambayong, Maguindanao del Sur | SULTAN SA BARONGIS, MAGUINDANAO DEL SUR |
| 2025 | Sultan Sa Barongis Lambayong, Maguindanao del Sur | SULTAN SA BARONGIS, MAGUINDANAO DEL SUR |
| 2025 | OZAMIZ CITY, Misamis Occidental | CITY OF OZAMIS, MISAMIS OCCIDENTAL |
| 2025 | KINOGITAN, Misamis Oriental | KINOGUITAN, MISAMIS ORIENTAL |
| 2025 | K. CALUANG, Sulu | KALINGALAN CALUANG, SULU |
| 2025 | PANAMAO, Sulu | OLD PANAMAO, SULU |
| 2025 | E. ESTINO, Sulu | PANGLIMA ESTINO, SULU |
| 2025 | BANGUINGUI, Sulu | TONGKIL, SULU |

Towns named in the news but absent from that year's vote data (`not_in_vote_data`):
2016 New Corella (Davao del Norte); 2016 Talaingod (Davao del Norte); 2016 Nunungan (Lanao del Norte); 2016 Pantar (Lanao del Norte); 2016 Tagoloan (Lanao del Norte); 2016 Pantar (Lanao del Sur); 2016 Don Victoriano (Misamis Occidental); 2016 Sugbongcogon (Misamis Oriental); 2016 President Quirino (Sultan Kudarat); 2019 City of Cotabato (—); 2019 Cotabato City (—); 2019 Cotabato City (Bangsamoro region); 2019 Dumalundong (Lanao del Sur); 2019 Sultan Dumalondong (Lanao del Sur)

## Sources

Every source behind every row, by election year. "rows" counts CSV rows from that source,
"named LGUs" the rows naming a specific town/city. Articles dated in another year are
retrospective mentions (e.g. 2016 articles recalling 2013 EWAs).

### 2013

| date | outlet | title | rows | named LGUs | verified |
|---|---|---|---:|---:|---|
| 2012-11-17 | The Philippine Star | [Police monitoring 15 'high risk' areas for 2013 polls](https://www.philstar.com/headlines/2012/11/17/867650/police-monitoring-15-high-risk-areas-2013-polls) | 16 | 0 | fetched |
| 2013-01-06 | The Philippine Star (Freeman News Service) | [34 poll hotspots, 10 private armies identified in Central Visayas](https://www.philstar.com/nation/2013/01/06/893646/34-poll-hotspots-10-private-armies-identified-central-visayas) | 34 | 33 | fetched |
| 2013-03 | Philippine Daily Inquirer | [Comelec monitoring 15 'areas of concern'](https://newsinfo.inquirer.net/376403/comelec-monitoring-15-areas-of-concern) | 16 | 0 | snippet |
| 2013-04-26 | The Philippine Star (via PressReader) | [Misamis Oriental among 'areas of immediate concern'](https://www.pressreader.com/philippines/the-philippine-star/20130426/281590943058718) | 1 | 0 | snippet |
| 2013-04-27 | Rappler | [More provinces to be declared election hotspots](https://www.rappler.com/philippines/elections/27641-more-provinces-declared-election-hotspots/) | 6 | 0 | fetched |
| 2013-04-29 | Philippine Daily Inquirer | [Sulu added to Comelec 'list of concern'](https://newsinfo.inquirer.net/399311/sulu-added-to-comelec-list-of-concern) | 2 | 0 | snippet |
| 2013-05-06 | Rappler | [Police chiefs pulled out of La Union hot spots](https://www.rappler.com/philippines/elections/28238-police-chiefs-taken-off-la-union-hot-spots/) | 4 | 4 | fetched |
| 2013-05-13 | Rappler | [Pol rivalry in Comelec-controlled Nueva Ecija](https://www.rappler.com/philippines/elections/28852-nueva-ecija-early-result-governor/) | 2 | 0 | fetched |
| 2016-04-06 | Rappler (SunStar content-sharing) | [Cebu: 1 city, 6 towns being watched for poll-related violence](https://www.rappler.com/philippines/elections/128491-cebu-election-violence-watch-listw/) | 2 | 1 | fetched |
| 2016-04-19 | GMA News Online (GMA News Research) | [260 cities and towns placed on PNP's election watch list](https://www.gmanetwork.com/news/topstories/specialreports/563240/260-cities-and-towns-placed-on-pnp-s-election-watch-list/story/) | 4 | 4 | fetched |

### 2016

| date | outlet | title | rows | named LGUs | verified |
|---|---|---|---:|---:|---|
| 2015-12-09 | GMA News Online | [PNP tags 6 provinces as poll 'hot spots'](https://www.gmanetwork.com/news/topstories/nation/547330/pnp-tags-6-provinces-as-poll-hot-spots/story/) | 10 | 0 | fetched |
| 2015-12-09 | SunStar Davao | [Poll watchlist areas in Davao identified](https://www.sunstar.com.ph/more-articles/poll-watchlist-areas-in-davao-identified) | 22 | 22 | fetched |
| 2016-01-11 | The Freeman (Philstar) | [In Eastern Visayas PRO-8 identifies 44 towns as poll's areas of concern](https://www.philstar.com/the-freeman/region/2016/01/11/1541776/eastern-visayas-pro-8-identifies-44-towns-polls-areas-concern) | 7 | 1 | fetched |
| 2016-01-12 | The Freeman (Philstar) | [In Bohol Comelec puts 7 towns under poll's watchlist](https://www.philstar.com/the-freeman/region/2016/01/12/1542105/bohol-comelec-puts-7-towns-under-polls-watchlist) | 7 | 7 | fetched |
| 2016-01-15 | Rappler | [No election hot spots in Negros Occidental for now – Comelec](https://www.rappler.com/philippines/elections/119094-no-election-hotspots-negros-occidental/) | 1 | 0 | fetched |
| 2016-01-17 | Rappler | [Northern Mindanao poll violence watchlist: 47 towns, 7 cities](https://www.rappler.com/philippines/elections/119097-northern-mindanao-election-violence-watchlist/) | 54 | 53 | fetched |
| 2016-01-28 | The Philippine Star | [All Central Luzon cities, towns on election watchlist](https://www.philstar.com/nation/2016/01/28/1547294/all-central-luzon-cities-towns-election-watchlist) | 42 | 41 | fetched |
| 2016-02-01 | The Philippine Star | [20 Pangasinan areas in poll watchlist](https://www.philstar.com/nation/2016/02/01/1548748/nation) | 2 | 0 | fetched |
| 2016-02-07 | Rappler | [Cagayan Valley towns being watched for poll violence – PNP](https://www.rappler.com/philippines/elections/121242-cagayan-valley-election-violence-watchlist/) | 2 | 1 | fetched |
| 2016-04-01 | Rappler | [3 provinces added to PNP's election watchlist areas](https://www.rappler.com/philippines/elections/127853-provinces-included-pnp-election-watchlist-area/) | 9 | 0 | fetched |
| 2016-04-06 | Rappler (SunStar content-sharing) | [Cebu: 1 city, 6 towns being watched for poll-related violence](https://www.rappler.com/philippines/elections/128491-cebu-election-violence-watch-listw/) | 7 | 7 | fetched |
| 2016-04-14 | The Freeman (Philstar) | [Deployment of troops: Cops to prioritize places in poll body's watchlist](https://www.philstar.com/the-freeman/cebu-news/2016/04/14/1573116/deployment-troops-cops-prioritize-places-poll-bodys-watchlist) | 10 | 9 | fetched |
| 2016-04-19 | GMA News Online (GMA News Research) | [260 cities and towns placed on PNP's election watch list](https://www.gmanetwork.com/news/topstories/specialreports/563240/260-cities-and-towns-placed-on-pnp-s-election-watch-list/story/) | 41 | 5 | fetched |
| 2016-04-21 | SunStar Cebu | [Police add San Francisco, Camotes on poll watchlist](https://www.sunstar.com.ph/more-articles/police-add-san-francisco-camotes-on-poll-watchlist) | 2 | 1 | fetched |
| 2016-04-26 | Rappler | [Lanao del Norte town 'under Comelec control'](https://www.rappler.com/?p=130887) | 3 | 2 | fetched |
| 2016-05-03 | Rappler | [Marawi, Abra soon under 'Comelec control'](https://www.rappler.com/nation/politics/elections/2016/131668-marawi-abra-comelec-control-abas) | 3 | 2 | fetched |
| 2016-05-04 | The Philippine Star | [Abra, Marawi placed under Comelec control](https://www.philstar.com/nation/2016/05/04/1579817/abra-marawi-placed-under-comelec-control) | 3 | 2 | fetched |
| 2016-05-06 | Rappler | [8 election hot spots, 4 'areas of concern' tagged in Negros Island](https://www.rappler.com/philippines/elections/132019-negros-island-election-hot-spots/) | 12 | 12 | fetched |
| 2016-05-07 | Rappler (MindaNews) | [10 municipalities in Region 12 declared 'areas of concern'](https://www.rappler.com/philippines/elections/132107-municipalities-region-12-soccsksargen-areas-concern/) | 11 | 10 | fetched |
| 2016-05-08 | Rappler (SunStar content-sharing) | [Zero areas in Western Visayas on election watchlist – Comelec](https://www.rappler.com/philippines/elections/132230-zero-areas-western-visayas-election-watchlist-comelec/) | 22 | 21 | fetched |
| 2016-05-08 | Rappler (SunStar content-sharing) | [Cebu police bare risks on election day](https://www.rappler.com/philippines/elections/132352-cebu-police-risks-election-day/) | 4 | 0 | fetched |
| 2016-05-09 | Rappler (Newsbreak IQ) | [5 provinces in PNP watchlist for 4 straight election years](https://www.rappler.com/newsbreak/iq/132435-provinces-pnp-election-watchlist/) | 1 | 0 | fetched |

### 2019

| date | outlet | title | rows | named LGUs | verified |
|---|---|---|---:|---:|---|
| 2018-12-29 | ABS-CBN News | [LIST: PNP identifies 'hot spots' in 2019 midterm polls](https://abs-cbn.com/news/12/29/18/list-pnp-identifies-hot-spots-in-2019-midterm-polls) | 18 | 18 | fetched |
| 2018-12-29 | Rappler | [PNP places 18 areas on election watchlist](https://www.rappler.com/philippines/elections/219909-philippine-national-police-areas-election-watchlist-2019-elections/) | 19 | 18 | fetched |
| 2019-01-05 | Asian Journal | [PNP names 18 'areas of grave concern' amid 2019 elections](https://www.asianjournal.com/philippines/across-the-islands/pnp-names-18-areas-of-grave-concern-amid-2019-elections/) | 4 | 3 | fetched |
| 2019-01-11 | GMA News Online | [19 election hot spots under close watch —PNP](https://www.gmanetwork.com/news/news/nation/681133/19-election-hot-spots-under-close-watch-pnp/story/) | 1 | 0 | fetched |
| 2019-01-15 | PhilStar (The Philippine Star) | [PNP bares 19 poll watchlist areas](https://www.philstar.com/headlines/2019/01/15/1885242/pnp-bares-19-poll-watchlist-areas) | 20 | 19 | fetched |
| 2019-02 | Philippine Daily Inquirer | [PNP: 'Grave' poll hot spots up to 94 from 19 last month](https://newsinfo.inquirer.net/1085012/pnp-grave-poll-hot-spots-up-to-94-from-19-last-month) | 7 | 6 | snippet |
| 2019-02-12 | Rappler | [PNP tags Manila, 4 other Metro Manila cities as election hotspots](https://www.rappler.com/philippines/elections/223324-manila-declared-hotspot/) | 6 | 5 | fetched |
| 2019-02-12 | ABS-CBN News | [701 election 'hotspots' under watch - PNP](https://abs-cbn.com/news/02/12/19/701-election-hotspots-under-watch-pnp) | 6 | 2 | fetched |
| 2019-02-12 | PTV News (PNA) | [701 hotspots identified for 2019 polls: PNP](https://ptvnews.ph/?p=106302) | 27 | 5 | fetched |
| 2019-02-13 | The Freeman (PhilStar) | [2 Cebu towns election hotspots](https://www.philstar.com/the-freeman/cebu-news/2019/02/13/1893330/2-cebu-towns-election-hotspots) | 24 | 23 | fetched |
| 2019-03-19 | PTV News (Comelec PR) | [Comelec declares entire Mindanao and other areas as election hotspots](https://ptvnews.ph/?p=111570) | 4 | 4 | fetched |
| 2019-03-26 | PhilStar (The Philippine Star) | [PNP: 941 Mindanao towns, cities poll hotspots](https://www.philstar.com/headlines/2019/03/26/1904601/headlines) | 7 | 2 | fetched |
| 2019-03-29 | PTV News (PNA) | [True colors: A closer look at poll 'hotspots'](https://ptvnews.ph/true-colors-a-closer-look-at-poll-hotspots/) | 12 | 11 | fetched |
| 2019-03-29 | GMA News Online | [Albayalde visits 'red' election hotspot Abra](https://www.gmanetwork.com/news/topstories/nation/689641/albayalde-visits-red-election-hotspot-abra/story/) | 1 | 1 | fetched |
| 2019-04-09 | PhilStar (The Philippine Star) | [PNP identifies 43 Western Visayas election hotspots](https://www.philstar.com/nation/2019/04/09/1908437/nation) | 47 | 46 | fetched |
| 2019-04-10 | PTV News (PNA) | [Enough forces for poll 'hotspots' in W. Visayas assured](https://ptvnews.ph/enough-forces-for-poll-hotspots-in-w-visayas-assured/) | 44 | 43 | fetched |
| 2019-04-13 | PhilStar (The Philippine Star) | [More Negros areas identified as poll hotspots](https://www.philstar.com/nation/2019/04/13/1909546/nation) | 28 | 27 | fetched |
| 2019-04-24 | PTV News (PNA) | [Another poll 'area of immediate concern' seen in NegOcc](https://ptvnews.ph/?p=115996) | 33 | 33 | fetched |
| 2019-04-28 | SunStar Baguio | [Abra, Lubuagan still areas of grave concern](https://www.sunstar.com.ph/baguio/local-news/abra-lubuagan-still-areas-of-grave-concern) | 6 | 6 | fetched |
| 2019-05-05 | Manila Bulletin | [30 areas in Mimaropa listed as election hotspots](https://mb.com.ph/2019/05/05/30-areas-in-mimaropa-listed-as-election-hotspots/) | 15 | 14 | snippet |
| 2019-05-06 | Calbayog Journal | [PNP, AFP On-Alert for May 13 Elections; Identified Hot Spots for Samar 1st District](https://www.calbayogjournal.com/pnp-afp-on-alert-for-may-13-elections-identified-hot-spots-for-samar-1st-district) | 10 | 10 | fetched |
| 2019-05-07 | PhilStar (The Philippine Star) | [Negros town placed under Comelec control](https://www.philstar.com/nation/2019/05/07/1915634/nation) | 7 | 3 | fetched |
| 2019-05-08 | Philippine Daily Inquirer | [946 election hotspots identified](https://newsinfo.inquirer.net/1115161/946-election-hotspots-identified) | 4 | 0 | snippet |
| 2019-05-08 | SunStar Baguio | [Abra town remains peaceful](https://www.sunstar.com.ph/baguio/local-news/abra-town-remains-peaceful) | 2 | 2 | fetched |
| 2019-05-10 | Radyo Inquirer | [Comelec: Election hotspots mahigit 1,000 na](https://radyo.inquirer.net/179167/comelec-election-hotspots-mahigit-1000-na) | 1 | 0 | snippet |
| 2019-05-10 | Philippine News Agency | [Security beefed up in 6 election 'hotspots' in Soccsksargen](https://www.pna.gov.ph/articles/1069460) | 6 | 6 | snippet |
| 2019-05-10 | SunStar Cebu | [Comelec names 20 hotspots in Cebu](https://www.sunstar.com.ph/cebu/local-news/comelec-names-20-hotspots-in-cebu) | 22 | 20 | fetched |
| 2019-05-10 | SunStar Manila | [Comelec identifies more election hotspots](https://www.sunstar.com.ph/manila/local-news/comelec-identifies-more-election-hotspots) | 59 | 58 | fetched |
| 2019-05-11 | Philippine News Agency | [Security heightened in 11 poll hotspots on Samar Island](https://www.pna.gov.ph/articles/1069530) | 12 | 11 | snippet |
| 2022-02-24 | Visayan Daily Star | [4 Negros LGUs under 'Red' category](https://visayandailystar.com/?p=22514) | 1 | 1 | fetched |

### 2022

| date | outlet | title | rows | named LGUs | verified |
|---|---|---|---:|---:|---|
| 2021-12-13 | GMA News | [PNP considers over 500 areas as Eleksyon 2022 hotspots](https://www.gmanetwork.com/news/topstories/nation/814351/pnp-considers-over-500-areas-as-eleksyon-2022-hotspots/story) | 2 | 0 | fetched |
| 2021-12-14 | Negros Now Daily | [2 NegOcc LGUs tagged as potential election hotspots](https://negrosnowdaily.com/?p=11635) | 1 | 0 | fetched |
| 2021-12-14 | Visayan Daily Star | [Red category for some WV areas in 2022 elections](https://visayandailystar.com/?p=20631) | 1 | 0 | fetched |
| 2022-01-12 | Visayan Daily Star | [PRO6 chief to 4 new prov'l directors: Ensure peaceful elections in WV](https://visayandailystar.com/?p=21298) | 2 | 2 | fetched |
| 2022-02-08 | Visayan Daily Star | [Comelec identifies NegOcc 'areas of concern'](https://visayandailystar.com/?p=22075) | 13 | 12 | fetched |
| 2022-02-09 | The Manila Times | [12 areas in Negros under poll watchlist](https://www.manilatimes.net/2022/02/09/news/regions/12-areas-in-negros-under-poll-watchlist/1832246/amp) | 4 | 3 | fetched |
| 2022-02-14 | Rappler | [18 'areas of concern' identified in Negros Occidental](https://rappler.com/nation/comelec-areas-concern-negros-occidental-2022-polls) | 13 | 12 | fetched |
| 2022-02-19 | GMA News (Regional) | [7 Bohol towns under 'areas of immediate concern'](https://www.gmanetwork.com/news/topstories/regions/822386/7-bohol-towns-under-areas-of-immediate-concern/story) | 47 | 47 | fetched |
| 2022-03-02 | Visayan Daily Star | [2,028 police personnel readied for polls](https://visayandailystar.com/?p=22670) | 19 | 18 | fetched |
| 2022-03-09 | The Manila Times | [9 Abra towns under close Comelec watch](https://www.manilatimes.net/2022/03/09/news/regions/9-abra-towns-under-close-comelec-watch/1835594/amp) | 1 | 0 | fetched |
| 2022-03-22 | PhilStar | [PNP monitors 3 regions for poll hot spots](https://www.philstar.com/nation/2022/03/22/2168948/pnp-monitors-3-regions-poll-hot-spots/amp/) | 1 | 0 | fetched |
| 2022-03-24 | Rappler | [Comelec watchlist flags 217 Northern Mindanao villages as 'areas of concern'](https://rappler.com/nation/villages-northern-mindanao-comelec-watchlist-areas-concern-2022) | 13 | 6 | fetched |
| 2022-03-25 | Rappler | [Police tag 11 towns, 1 city in Batangas as 'election areas of concern'](https://www.rappler.com/nation/elections/police-batangas-place-election-areas-of-concern/) | 13 | 13 | fetched |
| 2022-03-26 | Manila Bulletin | [PNP tags seven towns in Cagayan as hotspots](https://mb.com.ph/2022/3/26/pnp-tags-seven-towns-in-cagayan-as-hotspots) | 7 | 7 | snippet |
| 2022-03-28 | PhilStar | [Comelec to release 'areas of concern' list this week](https://www.philstar.com/headlines/2022/03/28/2170476/comelec-release-areas-concern-list-week/amp/) | 1 | 0 | fetched |
| 2022-03-31 | ABS-CBN News | [PNP: 102 towns, cities in BARMM are areas of concern in May 9 polls](https://www.abs-cbn.com/news/03/31/22/pnp-102-towns-cities-in-barmm-are-areas-of-concern-in-may-9-polls) | 19 | 18 | fetched |
| 2022-03-31 | Rappler | [Comelec withholds release of 'areas of concern' list as verification drags on](https://www.rappler.com/philippines/elections/comelec-withholds-release-election-hotspot-list-amid-verification/) | 1 | 0 | fetched |
| 2022-04-02 | Rappler | [Dipolog, 12 towns in Zamboanga del Norte under 'category red'](https://www.rappler.com/philippines/elections/dipolog-zamboanga-del-norte-towns-under-category-red/) | 4 | 3 | fetched |
| 2022-04-05 | Edge Davao (PNA wire) | [PNP tags 100 towns, 14 cities as poll 'hotspots'](https://edgedavao.net/latest-news/2022/04/pnp-tags-100-towns-14-cities-as-poll-hotspots/) | 2 | 0 | fetched |
| 2022-04-05 | Philippine Daily Inquirer | [PNP wants to place over 100 areas of concern under red category](https://newsinfo.inquirer.net/?p=1578504) | 1 | 0 | snippet |
| 2022-04-07 | Philippine Daily Inquirer | [DILG chief: 120 cities, municipalities tagged as 'red' areas in May 2022 polls](https://newsinfo.inquirer.net/1579837/dilg-chief-120-cities-municipalities-tagged-as-red-areas-in-may-2022-polls/amp) | 1 | 0 | snippet |
| 2022-04-18 | GMA News | [2 Lanao del Sur towns declared under Comelec control — PNP official](https://www.gmanetwork.com/news/topstories/regions/828821/2-lanao-del-sur-towns-declared-under-comelec-control-pnp-official/story) | 3 | 2 | fetched |
| 2022-04-20 | ABS-CBN News | [Comelec keeps eye on Maguindanao following blast](https://www.abs-cbn.com/news/04/20/22/maguindanao-under-comelec-watch-after-blast) | 2 | 2 | fetched |
| 2022-04-23 | Manila Bulletin | [Areas of concern: Comelec says 104 municipalities, 14 cities under red category](https://mb.com.ph/2022/4/23/areas-of-concern-comelec-says-104-municipalities-14-cities-under-red-category) | 1 | 0 | snippet |
| 2022-04-23 | Philippine Daily Inquirer | [San Jose del Monte City, 7 Bulacan towns tagged as 'areas of concern' in May polls](https://newsinfo.inquirer.net/1586901/san-jose-del-monte-city-7-bulacan-towns-tagged-as-areas-of-concern-in-may-polls) | 9 | 8 | snippet |
| 2022-04-25 | Philippine Daily Inquirer | [Comelec yet to release list of 104 election areas of concern](https://newsinfo.inquirer.net/1587620/comelec-yet-to-release-list-of-104-election-areas-of-concern) | 1 | 0 | snippet |
| 2022-04-26 | GMA News | [Marawi City, towns in Maguindanao, Lanao del Sur placed under Comelec control](https://www.gmanetwork.com/news/story/829783/) | 10 | 10 | fetched |
| 2022-04-27 | The Manila Times | [51 CL areas identified as election hotspots](https://www.manilatimes.net/2022/04/27/news/regions/51-cl-areas-identified-as-election-hotspots/1841340/amp) | 1 | 0 | fetched |
| 2022-04-28 | Rappler | [7 Pangasinan towns placed under 'Orange Category'](https://www.rappler.com/philippines/elections/towns-pangasinan-placed-under-comelec-orange-category-2022/) | 7 | 7 | fetched |
| 2022-04-29 | GMA News | [Comelec's Ferolino: Pilar, Abra placed on red category](https://www.gmanetwork.com/news/topstories/regions/830198/comelec-s-ferolino-pilar-abra-placed-on-red-category/story) | 2 | 2 | fetched |
| 2022-05 | Philippine Daily Inquirer | [7 Soccsksargen towns tagged as election season 'areas of grave concern'](https://newsinfo.inquirer.net/1593482/7-soccsksargen-towns-tagged-as-election-season-areas-of-grave-concern) | 7 | 7 | snippet |
| 2022-05 | Philippine Daily Inquirer | [Police beef up security in 6 South Cotabato towns](https://newsinfo.inquirer.net/1593112/police-beef-up-security-in-6-south-cotabato-towns/amp) | 6 | 6 | snippet |
| 2022-05-04 | GMA News | [Misamis Occidental, Abra town placed under Comelec control](https://www.gmanetwork.com/news/topstories/nation/830574/misamis-occidental-abra-town-placed-under-comelec-control/story) | 12 | 12 | fetched |
| 2022-05-04 | ABS-CBN News | [Misamis Occidental province, Pilar town in Abra placed under Comelec control](https://www.abs-cbn.com/news/05/04/22/2-more-areas-placed-under-comelec-control) | 12 | 12 | fetched |
| 2022-05-06 | GMA News | [PNP: 24 towns, 4 cities under Comelec control for 2022 polls](https://www.gmanetwork.com/news/topstories/nation/830816/pnp-24-towns-4-cities-under-comelec-control-for-2022-polls/story) | 29 | 28 | fetched |
| 2022-05-11 | PressOnePH | [Failure of elections declared in 14 Lanao del Sur areas](https://pressone.ph/?p=30903) | 3 | 3 | fetched |

### 2025

| date | outlet | title | rows | named LGUs | verified |
|---|---|---|---:|---:|---|
| 2025-01-09 | The Manila Times | [1,239 election hotspots identified](https://manilatimes.net/2025/01/09/news/1239-election-hotspots-identified/2036044) | 1 | 0 | fetched |
| 2025-01-09 | Inquirer.net | [Comelec names 38 places as areas under serious threats in 2025 elections](https://www.inquirer.net/424801/comelec-names-38-places-as-areas-under-serious-threats-in-2025-elections/) | 1 | 0 | fetched |
| 2025-01-09 | GMA News Online | [Comelec: 38 election areas of concern under 'red' category](https://www.gmanetwork.com/news/topstories/nation/932331/comelec-38-election-areas-of-concern-under-red-category/story) | 40 | 39 | fetched |
| 2025-01-10 | GMA Regional TV | [COMELEC places four areas in Luzon under red category](https://www.gmanetwork.com/regionaltv/news/106038/comelec-places-four-areas-in-luzon-under-red-category/story) | 13 | 12 | fetched |
| 2025-01-17 | Negros Now Daily | [Comelec identifies 5 areas of concern in Negros Occ.](https://negrosnowdaily.com/comelec-identifies-5-areas-of-concern-in-negros-occ/) | 6 | 5 | fetched |
| 2025-01-23 | Inquirer.net | [14 areas in Central Luzon under close watch for May polls](https://www.inquirer.net/426149/14-areas-in-central-luzon-under-close-watch-for-may-polls/) | 15 | 14 | fetched |
| 2025-02-10 | Inquirer.net | [8 Pangasinan LGUs named 'areas of concern' for May polls](https://www.inquirer.net/428059/8-pangasinan-lgus-named-areas-of-concern-for-may-polls/) | 8 | 8 | fetched |
| 2025-02-12 | Inquirer.net | [27 areas in Eastern Visayas poll 'areas of concern'](https://www.inquirer.net/428421/27-areas-in-eastern-visayas-poll-areas-of-concern/) | 27 | 27 | fetched |
| 2025-03-04 | Visayan Daily Star | [NIR election areas of concern named by March 19](https://visayandailystar.com/nir-election-areas-of-concern-named-by-march-19/) | 1 | 0 | fetched |
| 2025-03-14 | Inquirer.net | [Election-related violence escalates in Abra](https://www.inquirer.net/432385/poll-violence-escalates-in-abra/) | 9 | 9 | fetched |
| 2025-03-18 | Negros Now Daily | [25 LGUs in NegOr tagged as poll 'areas of concern'](https://negrosnowdaily.com/25-lgus-in-negor-tagged-as-poll-areas-of-concern/) | 5 | 4 | fetched |
| 2025-03-18 | Visayan Daily Star | [26 NIR towns tagged as Comelec areas of concern](https://visayandailystar.com/26-nir-towns-tagged-as-comelec-areas-of-concern/) | 5 | 4 | fetched |
| 2025-03-19 | GMA News Online | [Comelec: Areas under 'red' category down from 38 to 36](https://www.gmanetwork.com/news/topstories/nation/939804/comelec-areas-of-concern-eleksyon-2025/story) | 37 | 36 | fetched |
| 2025-03-19 | Inquirer.net | [Comelec: Fewer areas under serious threats for 2025 polls](https://www.inquirer.net/433065/fwd-comelec-places-fewer-areas-under-serious-threats-for-2025-polls/) | 1 | 0 | fetched |
| 2025-03-19 | Malaya Business Insight | [36 areas under 'red' category for May polls](https://malaya.com.ph/news/national-news/36-areas-under-red-category-for-may-polls/) | 1 | 0 | fetched |
| 2025-03-20 | Inquirer.net | [11 more LGUs now 'red' in poll security watch](https://www.inquirer.net/433092/11-more-lgus-now-red-in-poll-security-watch/) | 12 | 11 | fetched |
| 2025-03-21 | PCIJ | [MAP: Updated areas of concern in the 2025 elections (embedded Datawrapper table iBHG3 '…](https://pcij.org/2025/03/21/map-updated-areas-of-concern-in-the-2025-elections/) | 790 | 789 | fetched |
| 2025-04-04 | GMA News Online | [Datu Odin Sinsuat now under Comelec control ahead of Eleksyon 2025](https://www.gmanetwork.com/news/topstories/nation/941671/datu-odin-sinsuat-now-under-comelec-control-ahead-of-eleksyon-2025/story) | 1 | 1 | fetched |
| 2025-04-08 | SunStar Zamboanga | [Westmincom mobilizes task forces to strengthen poll security](https://www.sunstar.com.ph/zamboanga/westmincom-mobilizes-task-forces-to-strengthen-poll-security) | 1 | 1 | fetched |
| 2025-04-15 | Daily Tribune | [Another Maguindanao town placed under Comelec control](https://tribune.net.ph/2025/04/15/another-maguindanao-town-placed-under-comelec-control) | 2 | 2 | fetched |
| 2025-04-15 | Inquirer.net | [Comelec puts Buluan, Maguindanao del Sur under its control](https://www.inquirer.net/436752/comelec-puts-buluan-maguindanao-del-sur-under-its-control/) | 1 | 1 | fetched |
| 2025-04-25 | Inquirer.net | [PNP sees fewer 'areas of concern' in 2025 compared to previous elections](https://www.inquirer.net/438198/pnp-sees-fewer-areas-of-concern-in-2025-compared-to-previous-elections/) | 1 | 0 | fetched |
| 2025-04-25 | SunStar Cebu | [Tighter security eyed for 5 LGUs in Cebu, Bohol](https://www.sunstar.com.ph/cebu/tighter-security-eyed-for-5-lgus-in-cebu-bohol) | 5 | 5 | fetched |
| 2025-05-07 | PCIJ | [MAP: Updated areas of concern in the 2025 elections (Datawrapper map bNkxH v7, last mod…](https://datawrapper.dwcdn.net/bNkxH/7/) | 3 | 2 | fetched |
| 2025-05-08 | Inquirer.net | [Private armed groups back in Abra – PNP](https://www.inquirer.net/440310/private-armed-groups-back-in-abra-pnp/) | 3 | 2 | fetched |

### Tried but unreadable (not used, or snippet only)

- **Inquirer** (newsinfo., plus., radyo., cebudailynews.) — Cloudflare 403 for all
  pre-2025 articles. Rows from it are `snippet`. Notable unread items: 2019 "'Grave' poll
  hot spots increase to 570", 2019 "29 Central Visayas cities, towns on election watch
  list", 2022 "8 more areas placed under Comelec control", 2013 "PNP tags 127 places in
  Visayas".
- **PNA** (pna.gov.ph) — every old `/articles/<id>` URL returns 404 since the site
  migration. 2019 PNA text was read through PTV News reposts. The four 2025 PNA stories
  ("403 areas of concern", Abra, NegOr, Central Luzon) could not be located or read.
- **Manila Bulletin, MindaNews, PressReader** — 403. Notably PressReader/SunStar Pampanga
  2022-04-23 ("'Election areas of concern' in Central Luzon named"), the most promising
  unread source for 2022 Central Luzon names.
- **Punch (Dagupan)** — down. Its May 2016 "16 towns under election watch list finally
  named" would give Pangasinan's final 2016 list.
- **ABS-CBN 2025** — JavaScript-only pages. **Manila Times** — paywalled after the lead
  (counts only).
- **web.archive.org** was not reachable from the build environment. Re-fetching the
  blocked URLs in a normal browser (or via the Wayback Machine) would upgrade the
  `snippet` rows and could fill gaps.

## Known gaps worth filling (e.g. via an eFOI request to COMELEC/PNP)

- Full national town lists for 2013, 2016, 2019 (outside Res. 10531 / Mindanao), 2022.
- 2022 names behind: Abra's 9 yellow, Caraga's 7 red, Zamboanga del Norte's 12 red/10
  orange, Central Luzon's 51, Negros Occidental's 6 mid-February additions.
- 2019 town names for Masbate, Negros Oriental (May), the Samars, Bicol's February reds.
- 2025 final (late April / May) town-level list.
