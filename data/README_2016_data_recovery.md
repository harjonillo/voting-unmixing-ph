# 2016 senatorial data — recovery attempt & why the gap persists

**Investigation date:** 2026-09-21. See `data/README.md` (section
*"2016 — `elections/results_nle2016_05092016_1950.txt`"*) for the current in-repo
2016 dataset and pipeline. This file documents a dedicated hunt for the **complete**
national senator-per-precinct results, and records — with receipts — why they could
**not** be recovered from public archives.

## The problem in one line

The in-repo 2016 senator data covers **~22,986 precincts (~25%)** of the ~92,509
national clustered precincts. It is an **election-night transmission snapshot**
(in-row timestamps stop at 2016-05-09 18:37), so whole late-transmitting cities
(Manila, Quezon City, …) are absent. We wanted the near-complete national feed.

## Realistic ceiling: ~96%, not 100%

2016 was an automated election run over a transmission network, and the controversy
that year (the mid-count "script/hash change" on the transparency server) is about
that transmission. The most complete public compilation ever published — the
NAMFREL raw feed **as of 2016-05-12 15:45** — reached **~90,642 clustered precincts
(~96%)**; NAMFREL/PPCRV expected ~94,276. **The missing ~4% is a
transmission-integrity gap, not an archival gap** — no better archive fixes it.

## Where the senator-per-precinct data actually lived (both sources are gone)

There were two source paths that carried **all contests including senators** at the
precinct level. Both are unrecoverable:

### 1. NAMFREL raw transmission feed  → dead Azure IP, never archived
`http://www.elections.org.ph/2016/results/raw-data.php` (the page titled
*"Transmitted Raw Data"*) embeds an iframe:

    <iframe src="http://168.63.241.64/rawfiles/">

That bare Azure IP (`168.63.241.64`) is the open directory that served the
pipe-delimited `results_nle2016_<date>_<time>.txt` dumps — i.e. **the exact origin
of the repo's `results_nle2016_05092016_1950.txt`.** A later, more-complete dump
would live there.
- **Wayback captures of `168.63.241.64`: 0.** Crawlers skip bare-IP iframes.
- The IP is long dead. → **Not recoverable.**

### 2. COMELEC results site `pilipinaselectionresults2016.com` → only navigation nodes archived
This is the source behind the FigShare VP dataset and the `ianalis/scraper2016`
tool. It served a JSON tree walked down to precinct level:

    Country → Region → Province → Municipality → Barangay → LVG (clustered precinct, level 6)

**Senator votes live only in the level-6 leaf JSONs.** Wayback record:
- **485 total captures** of the domain across 2016–2025, but most of the 2018+ ones
  are **domain-parked spam** (the domain lapsed).
- From the election period, only **~12 data JSONs** were captured, all on
  **2016-05-10/11**, and every one is a **navigation node** (a list of child
  divisions), e.g. `root.json`, `NCR.json`, `7600.json` (province), `7603.json`
  (municipality), `7603009.json` (barangay "New Alabang Village").
- **Zero precinct vote-leaf JSONs were archived.** Verified: the deepest captured
  node (`7603009.json`) contains no `senator`/`candidate`/`contest` fields — those
  appear one level deeper, in files that don't exist in the archive.
- The live site is offline; `scraper2016` therefore cannot be re-run. → **Not
  recoverable.**

## What *is* archived (useful, but president — not senators)

NAMFREL also published **per-contest, per-precinct CSVs** under
`elections.org.ph/2016/results/files1/`. Wayback crawled only the **president**
one — the senator sibling was never captured:

| file | status |
|---|---|
| `president-per-region-per-precinct-with-accumulated-result-may12-1545.csv.zip` | **archived, downloadable** |
| `senator-…-may12-1545.csv.zip` (same format) | **404 on Wayback; live site 522 (dead)** |

Recovered president file (Wayback snapshot `20190922173105`): 3.8 MB zip → 13.4 MB
CSV, **90,359 precinct rows (~96%)**. Saved locally as
`data/elections/2016_president_per-precinct_may12-1545.csv` (gitignored like the
other raw CSVs; rebuild by downloading the archived URL under *Key URLs* below and
unzipping). Columns:

    item, region_name, province_name, municipal_name, precincts_code, contest_code,
    binay, roxas, poe, seneres, defensor, duterte, vv, overvotes, undervotes, rv,
    datestamp, precinct_reported, accumulated undervotes, accumulated_overvotes,
    rv_overtime, vv_overtime

`contest_code = 199009` is president. `precincts_code` is the **same 8-digit format
as the repo's 2016 precinct ids**. This proves a senator sibling existed in
identical shape, and — even as president data — is independently useful as:
- a **validated ~96% precinct master list** for 2016, and
- a **turnout / registered-voters layer** (`rv`, `vv`, over/undervotes per
  precinct) — which the current 2016 dataset lacks (its weighted/unweighted map
  toggle is identical for want of actual-voter counts).

`senators-051216-345pm.php/.htm` on the same site is only a **national summary
image**, not per-precinct data.

## Live server status (checked 2026-09-21)

`elections.org.ph` returns **HTTP 522 (Cloudflare: origin unreachable)** on every
path — homepage, `files1/`, the senator variants, and even the known-good president
filename. The origin backend is dead; the Wayback copy is the only survivor.

## Access note (for anyone re-running this)

Some networks (incl. several PH ISPs) **fail to resolve the `web.archive.org`
subdomain** even though `archive.org` resolves — Safari reports *"can't find the
server."* Workaround: pin the host to its IP.

    # get the current IP via DNS-over-HTTPS, then:
    curl --resolve web.archive.org:443:207.241.237.3 -L \
      "https://web.archive.org/web/<timestamp>id_/<original-url>"

`https://archive.org/wayback/available?url=…` (the availability API, no `web.`
prefix) is reachable directly and is the easiest way to find the nearest snapshot.

## Remaining routes to the real senator data (require a human request)

1. **Christian Alis (`ianalis`)** — `scraper2016` pulled *all* contests incl.
   senators; only the **VP** subset was published
   ([FigShare 3380116](https://figshare.com/articles/dataset/2016_Philippine_vice-presidential_elections_precinct-level_data/3380116),
   90,642 precincts, NAMFREL raw data as-of 2016-05-12 15:45). He may still hold the
   raw scrape JSON. **Highest-probability route.**
2. **NAMFREL / PPCRV** — compiled the `senator-…-may12-1545.csv` (the file Wayback
   missed). Direct request or COMELEC FOI.

(Draft request messages for both are kept with the session notes / provided
separately, not in the repo.)

## Key URLs

- NAMFREL raw-data page (archived):
  `https://web.archive.org/web/20160521071444/http://www.elections.org.ph/2016/results/raw-data.php`
- President per-precinct CSV (archived, downloadable):
  `https://web.archive.org/web/20190922173105/http://www.elections.org.ph/2016/results/files1/president-per-region-per-precinct-with-accumulated-result-may12-1545.csv.zip`
- COMELEC results site (mostly navigation nodes + parked spam):
  `https://web.archive.org/web/*/pilipinaselectionresults2016.com/*`
- Scraper: <https://github.com/ianalis/scraper2016>
- FigShare VP dataset: <https://figshare.com/articles/dataset/2016_Philippine_vice-presidential_elections_precinct-level_data/3380116>
