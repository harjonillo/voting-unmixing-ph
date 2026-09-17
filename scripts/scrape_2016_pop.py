"""Scrape the 2016 COMELEC Project of Precincts (POP) into a precinct->geography lookup.

The 2016 senatorial transmission feed (see ``scripts/prepare_2016_csv.py``) carries
only an 8-digit precinct id and no place names. COMELEC's public POP for 2016
supplies the missing geography. Despite looking like a click-through site, the POP
is served as **static HTML fragments** — no API, no session, no JavaScript needed:

    province list        html-scripts/2016NLE/province2016.html
    municipalities in P  php-sys-generated/2016NLE/pop-2016nle/prov_<P>/prov_list<P>2016.html
    precinct table P,M   php-sys-generated/2016NLE/pop-2016nle/prov_<P>/mun_<M>/mun_pop<M>2016.html

Each precinct table lists barangays (section headers) and, per cluster, a cluster
number and its member precincts. The feed's id decodes as

    id(8) = province(2) + municipality-within-province(2) + cluster-number(4)

verified against the feed (e.g. ABRA/BANGUED cluster 3 -> 01 01 0003 -> 01010003),
and matching the 2019 CSV's ``CLUSTERED_PRECINCT`` (``1010001`` = the same key with
its leading zero dropped). So (province, municipality, cluster#) -> the 8-digit key.

Output: a CSV keyed by 8-digit ``precinct`` with ``REGION, PROVINCE,
CITY_MUNICIPALITY, BARANGAY`` — exactly the ``--geo-lookup`` format
``prepare_2016_csv.py`` consumes.

REGION is not on the POP page; it is joined from the 2013 election CSV (same
ARMM/CARAGA-era region labels as 2016), falling back to 2019, with NCR handled by
province code. Provinces that fail to map are printed so they can be added to
``REGION_OVERRIDES``.

    python scripts/scrape_2016_pop.py --out data/elections/2016_precinct_geo.csv

Files are cached under ``--cache`` so re-runs don't re-hit the server; delete the
cache dir to force a fresh crawl.
"""

import argparse
import html
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.comelec.gov.ph"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

PROVINCE_URL = "html-scripts/2016NLE/province2016.html"
MUNI_URL = "php-sys-generated/2016NLE/pop-2016nle/prov_{P}/prov_list{P}2016.html"
POP_URL = "php-sys-generated/2016NLE/pop-2016nle/prov_{P}/mun_{M}/mun_pop{M}2016.html"

# NCR is split into districts in the POP; these province codes are Metro Manila.
# src/geo.py maps province -> METROPOLITAN MANILA whenever REGION normalizes to NCR.
NCR_CODES = {"39", "74", "75", "76"}
# Provinces that fail the 2013/2019 name join get a region here (code -> region).
# The two 2016 "special provinces" are the special geographic areas: Cotabato City
# (administratively Region XII / SOCCSKSARGEN) and Isabela City, Basilan (Region IX
# / Zamboanga Peninsula — it stayed out of ARMM).
REGION_OVERRIDES: dict[str, str] = {
    "98": "REGION XII",   # SPECIAL PROVINCE - COTABATO CITY
    "97": "REGION IX",    # SPECIAL PROVINCE - ISABELA CITY
}

OPTION = re.compile(r"<option value='([^']*)'[^>]*>(.*?)</option>", re.S | re.I)
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
TB = re.compile(r"<span class='tb'>(.*?)</span>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    return " ".join(html.unescape(TAG.sub("", s)).split())


def norm_prov(s: str) -> str:
    """Normalize a province name for the region join (drop parentheticals/punct)."""
    s = html.unescape(s).upper()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^A-Z ]", " ", s)
    return " ".join(s.split())


class Fetcher:
    def __init__(self, cache: Path, delay: float):
        self.cache = cache
        self.delay = delay
        self.fail: list[str] = []

    def get(self, url: str) -> str | None:
        cf = self.cache / url
        if cf.exists():
            return cf.read_text(encoding="utf-8")
        req = urllib.request.Request(f"{BASE}/{url}", headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                raw = urllib.request.urlopen(req, timeout=30).read()
                text = raw.decode("utf-8", "replace")
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(text, encoding="utf-8")
                if self.delay:
                    time.sleep(self.delay)
                return text
            except Exception as e:  # noqa: BLE001 - network hiccups, retry then give up
                if attempt == 3:
                    self.fail.append(f"{url}  ({e})")
                    return None
                time.sleep(1.5 * (attempt + 1))
        return None


def region_map() -> dict[str, str]:
    """norm_prov(province) -> REGION, from 2013 (era-correct) then 2019."""
    m: dict[str, str] = {}
    for yr in ("2019", "2013"):  # 2013 second so it overwrites -> era-correct labels win
        path = REPO_ROOT / "data" / "elections" / f"{yr}_senators_complete.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, usecols=["REGION", "PROVINCE"], dtype=str)
        for row in df.dropna().drop_duplicates(["PROVINCE"]).itertuples(index=False):
            m[norm_prov(row.PROVINCE)] = str(row.REGION).strip()
    return m


def parse_table(text: str, P: str, M_key: str, region: str, prov: str, muni: str):
    rows = []
    cur_bgy = ""
    for tr in TR.findall(text):
        tb = TB.search(tr)
        if tb:
            cur_bgy = clean(tb.group(1))
            continue
        tds = TD.findall(tr)
        if len(tds) < 5:
            continue
        cluster = clean(tds[3])          # CLUSTER/GROUP NUMBER column
        if not cluster.isdigit():
            continue
        pid = f"{int(P):02d}{int(M_key):02d}{int(cluster):04d}"
        rows.append((pid, region, prov, muni, cur_bgy))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "data" / "elections" / "2016_precinct_geo.csv")
    ap.add_argument("--cache", type=Path, default=REPO_ROOT / ".pop_cache_2016")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--delay", type=float, default=0.05,
                    help="seconds to sleep after each *network* fetch (cached hits skip it)")
    ap.add_argument("--fallback", default="2019",
                    help="election year whose *_senators_complete.csv fills precincts POP "
                         "cannot key (NCR/big cities); '' to disable")
    args = ap.parse_args()

    f = Fetcher(args.cache, args.delay)
    regions = region_map()

    prov_html = f.get(PROVINCE_URL)
    if not prov_html:
        sys.exit("could not fetch province list")
    provinces = [(v, clean(n)) for v, n in OPTION.findall(prov_html) if v.strip()]
    print(f"provinces: {len(provinces)}")

    # Resolve region per province; NCR by code, else by name join.
    unmatched = []
    prov_region = {}
    for code, name in provinces:
        if code in NCR_CODES:
            prov_region[code] = "NCR"
        elif code in REGION_OVERRIDES:
            prov_region[code] = REGION_OVERRIDES[code]
        else:
            reg = regions.get(norm_prov(name))
            prov_region[code] = reg or "UNKNOWN"
            if reg is None:
                unmatched.append((code, name))
    if unmatched:
        print("  ! no region match (add to REGION_OVERRIDES):")
        for code, name in unmatched:
            print(f"      {code}  {name}")

    # Gather all (P, M, prov_name, muni_name) municipality tasks.
    tasks = []
    for code, name in provinces:
        mh = f.get(MUNI_URL.format(P=code))
        if not mh:
            continue
        for val, mname in OPTION.findall(mh):
            if not val.strip():
                continue
            m_url = val[2:14]            # getpop: muni_v.substring(2,14) — file path part
            m_key = val[2:4]             # 2-digit city/municipality code for the 8-digit id
            # Big cities split into legislative districts (e.g. QUEZON CITY, 1ST
            # DISTRICT -> '7404-1') share one city code; their POP cluster numbers
            # overlap across districts, so the city+cluster key is not unique for
            # them. None of these appear in the (partial) 2016 feed, so the
            # ambiguity is harmless — the rows are kept best-effort and deduped.
            tasks.append((code, m_url, m_key, name, clean(mname)))
    print(f"municipalities: {len(tasks)}")

    # Fetch + parse each municipality's POP table (threaded; cache makes reruns cheap).
    all_rows = []

    def work(task):
        code, m_url, m_key, pname, mname = task
        text = f.get(POP_URL.format(P=code, M=m_url))
        if not text:
            return []
        prov_out = "NCR" if code in NCR_CODES else pname
        return parse_table(text, code, m_key, prov_region[code], prov_out, mname)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, rows in enumerate(ex.map(work, tasks), 1):
            all_rows.extend(rows)
            if i % 200 == 0:
                print(f"  {i}/{len(tasks)} municipalities, {len(all_rows):,} precincts")

    df = pd.DataFrame(all_rows,
                      columns=["precinct", "REGION", "PROVINCE", "CITY_MUNICIPALITY", "BARANGAY"])
    df = df.drop_duplicates("precinct")
    df["source"] = "pop2016"
    pop_n = len(df)

    # Fill gaps from the 2019 CSV (same precinct-id scheme, authoritative geography).
    # POP encodes NCR/other big cities by legislative district and its cluster
    # numbers there are not unique per city, so those ids don't key to the feed;
    # the 2019 complete file already resolves them. POP wins where both have a
    # precinct; 2019 only adds ids POP lacks.
    fb = REPO_ROOT / "data" / "elections" / f"{args.fallback}_senators_complete.csv"
    if fb.exists():
        f19 = pd.read_csv(fb, usecols=["REGION", "PROVINCE", "CITY_MUNICIPALITY",
                                       "BARANGAY", "CLUSTERED_PRECINCT"], dtype=str)
        f19["precinct"] = f19["CLUSTERED_PRECINCT"].str.zfill(8)
        f19 = f19[~f19["precinct"].isin(set(df["precinct"]))].copy()
        f19["source"] = f"nle{args.fallback}"
        df = pd.concat([df, f19[["precinct", "REGION", "PROVINCE",
                                 "CITY_MUNICIPALITY", "BARANGAY", "source"]]],
                       ignore_index=True)
        print(f"fallback {args.fallback}: added {len(f19):,} precincts POP lacked")
    else:
        print(f"fallback {args.fallback} CSV not found — POP only")

    df = df.drop_duplicates("precinct").sort_values("precinct")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}  ({len(df):,} precincts; {pop_n:,} from POP, "
          f"{len(df) - pop_n:,} from fallback)")
    print(f"  regions: {df['REGION'].nunique()}  provinces: {df['PROVINCE'].nunique()}  "
          f"municipalities: {df['CITY_MUNICIPALITY'].nunique()}")
    if (df['REGION'] == 'UNKNOWN').any():
        print(f"  ! {int((df['REGION']=='UNKNOWN').sum()):,} precincts have REGION=UNKNOWN")
    if f.fail:
        print(f"  ! {len(f.fail)} fetch failures (first few):")
        for u in f.fail[:5]:
            print(f"      {u}")


if __name__ == "__main__":
    main()
