"""Build data/elections/2016_senators_complete.csv from the 2016 NLE transmission feed.

The 2016 source (``results_nle2016_05092016_1950.txt``) is an election-night
transmission feed in **long/tidy** form — one pipe-delimited row per
*(precinct, candidate)* reading, no header, all contests mixed together — not the
wide per-precinct table the pipeline expects. This script filters it to the
senatorial contest, pivots long->wide into a precinct x candidate vote matrix, and
maps it onto the schema ``configs/config_2016.ini`` consumes (the same schema as
``2013_senators_complete.csv``). See ``data/README.md`` for the full audit.

Two structural limits of this source (documented, not fixed here):

* **Coverage is partial.** The feed is a ~18:37 election-night snapshot: ~22,986
  senator precincts out of ~92,509 nationally (~25%). It fully supersets the older
  truncated ``results_nle2016_05122016_1545.csv`` (once that file's stripped
  leading zeros are restored), so there is nothing to merge in from it.
* **No geography.** Rows carry only a numeric precinct id, no region/province/
  municipality names. Without an external precinct->location lookup the maps and
  the municipality-level p-sweep cannot be built, so the four geography columns are
  filled with a ``PLACEHOLDER`` sentinel by default. Pass ``--geo-lookup`` with a
  CSV keyed by 8-digit precinct id to join real geography when one is found; the
  output schema is identical to the other years so it slots straight in.

Column layout of the source (10 fields, unlabeled):
    1 precinct id (8 digits)         6 ballot position / sequence
    2 contest code (senator=00399009) 7 precinct constant (~registered voters)
    3 candidate "SURNAME, NAME (PARTY)" 8 per-precinct constant (~total sen. votes)
    4 candidate code                 9 small per-contest integer
    5 votes for this candidate       10 transmission timestamp

    python scripts/prepare_2016_csv.py \
        --src /path/to/results_nle2016_05092016_1950.txt \
        --out data/elections/2016_senators_complete.csv
"""

import argparse
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "elections" / "2016_senators_complete.csv"

SENATOR_CONTEST = "00399009"
COLS = ["precinct", "contest", "cand", "ccode", "votes", "pos", "c7", "c8", "c9", "ts"]
GEO_PLACEHOLDER = "PLACEHOLDER"
GEO_COLS = ["REGION", "PROVINCE", "CITY_MUNICIPALITY", "BARANGAY"]


def read_senator_rows(src: Path, chunksize: int = 500_000) -> pd.DataFrame:
    """Stream the pipe-delimited feed, keeping only senator-contest rows.

    Read in chunks (the raw file is ~390 MB / ~5M rows) so memory stays bounded;
    precinct ids are kept as zero-padded 8-char strings (the older CSV export
    stored them as integers, dropping leading zeros — we keep the padded form).
    """
    keep = []
    reader = pd.read_csv(
        src, sep="|", header=None, names=COLS, dtype=str,
        na_filter=False, chunksize=chunksize, quoting=3,  # csv.QUOTE_NONE
    )
    for chunk in reader:
        keep.append(chunk[chunk["contest"] == SENATOR_CONTEST])
    df = pd.concat(keep, ignore_index=True)
    df["precinct"] = df["precinct"].str.zfill(8)
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce")
    bad = df["votes"].isna().sum()
    if bad:
        print(f"warning: dropping {bad} rows with non-numeric votes")
        df = df.dropna(subset=["votes"])
    return df


def build(src: Path, out: Path, geo_lookup: Path | None = None) -> None:
    df = read_senator_rows(src)

    # long -> wide: one row per precinct, one column per candidate.
    wide = df.pivot_table(
        index="precinct", columns="cand", values="votes", aggfunc="sum", fill_value=0
    ).astype(int)
    cand = list(wide.columns)
    print(f"pivoted: {wide.shape[0]:,} precincts x {len(cand)} candidates")

    # per-precinct ~registered-voters proxy (col 7): constant within a precinct;
    # take the first reading. row_max normalization does not use it — kept for
    # reference / parity with the other years' schema.
    rv = df.groupby("precinct")["c7"].first()
    rv = pd.to_numeric(rv, errors="coerce").fillna(0).astype(int)

    out_df = pd.DataFrame(index=wide.index)
    if geo_lookup is not None:
        geo = pd.read_csv(geo_lookup, dtype=str).set_index("precinct")
        geo.index = geo.index.str.zfill(8)
        for c in GEO_COLS:
            out_df[c] = geo[c].reindex(out_df.index).fillna(GEO_PLACEHOLDER)
        matched = (out_df["REGION"] != GEO_PLACEHOLDER).sum()
        print(f"geography joined: {matched:,}/{len(out_df):,} precincts matched")
    else:
        # No geography available. Fill placeholders so preprocess (which requires a
        # REGION column and drops excluded_regions) runs; maps stay degenerate.
        for c in GEO_COLS:
            out_df[c] = GEO_PLACEHOLDER

    out_df["CLUSTERED_PRECINCT"] = wide.index
    out_df["information.numberOfRegisteredVoters"] = rv.reindex(out_df.index).values

    # Prefix each candidate header with "N. " so preprocessing.candidate_label
    # (which strips up to the first ".") keeps names that contain a period.
    for i, c in enumerate(cand, 1):
        out_df[f"{i}. {c}"] = wide[c].values

    if out_df.isna().to_numpy().sum():
        raise ValueError("NaN left in output — load_complete would drop those rows")

    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.reset_index(drop=True).to_csv(out, index=False)
    print(f"wrote {out}  ({out_df.shape[0]:,} precincts x {len(cand)} candidates, "
          f"sen_col_start=6)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path,
                    help="path to results_nle2016_05092016_1950.txt")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--geo-lookup", type=Path, default=None,
                    help="optional CSV keyed by 8-digit 'precinct' id with columns "
                         "REGION, PROVINCE, CITY_MUNICIPALITY, BARANGAY")
    args = ap.parse_args()
    build(args.src, args.out, args.geo_lookup)


if __name__ == "__main__":
    main()
