"""Build data/elections/2013_senators_complete.csv from the 2013 per-precinct .xls.

The 2013 source (``2013_per_precincts_senators.xls``, a legacy OLE2 Excel file)
is shaped differently from the other years' ``*_senators_complete.csv`` files:
17 sheets (one per region), wide per-precinct rows, geography + Total Registered
Voters + one column per candidate. This script concatenates the sheets and maps
them onto the schema the pipeline expects, so ``configs/config_2013.ini`` can be
run like any other year. See ``data/README.md`` for the full audit.

Requires ``xlrd>=2.0.1`` (in requirements.txt) to read the .xls.

    python scripts/prepare_2013_csv.py \
        --src /path/to/2013_per_precincts_senators.xls \
        --out data/elections/2013_senators_complete.csv
"""

import argparse
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "elections" / "2013_senators_complete.csv"


def canon_region(r: str) -> str:
    """Match the other years' REGION spelling:
    'N.C.R.'->'NCR', 'C.A.R'->'CAR', 'Region IV - A'->'REGION IV-A'."""
    s = str(r).upper().replace(".", "")
    s = re.sub(r"\s*-\s*", "-", s)      # "IV - A" -> "IV-A"
    return " ".join(s.split())


def build(src: Path, out: Path) -> None:
    xf = pd.ExcelFile(src, engine="xlrd")
    df = pd.concat([xf.parse(s, header=0) for s in xf.sheet_names], ignore_index=True)

    cols = list(df.columns)
    geo, trv, cand = cols[:5], cols[5], cols[6:39]
    if len(cand) != 33:
        raise ValueError(f"expected 33 candidate columns, got {len(cand)}")

    out_df = pd.DataFrame()
    out_df["REGION"] = df[geo[0]].map(canon_region)
    out_df["PROVINCE"] = df[geo[1]].astype("string").str.strip()
    out_df["CITY_MUNICIPALITY"] = df[geo[2]].astype("string").str.strip()
    out_df["BARANGAY"] = df[geo[3]].astype("string").str.strip()
    out_df["CLUSTERED_PRECINCT"] = df[geo[4]]
    # Only registered voters are available (no valid-ballot/turnout counts).
    # ~23% of rows are empty placeholder precincts (no votes AND no registration);
    # 0-fill keeps them out of load_complete's any-NaN row drop, and the pipeline
    # then drops them anyway via min_precinct_votes. Real precincts have complete
    # registration. config_2013.ini normalizes by row_max, not this column.
    rv = pd.to_numeric(df[trv], errors="coerce").fillna(0).astype(int)
    out_df["information.numberOfRegisteredVoters"] = rv

    # Prefix each candidate header with "N. " so preprocessing.candidate_label
    # (which strips up to the first ".") keeps names that contain a period
    # (ENRILE, JUAN PONCE JR.(NPC); VILLANUEVA, BRO.EDDIE (BP)).
    for i, c in enumerate(cand, 1):
        out_df[f"{i}. {c}"] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    if out_df.isna().to_numpy().sum():
        raise ValueError("NaN left in output — load_complete would drop those rows")

    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    print(f"wrote {out}  ({out_df.shape[0]:,} precincts x {len(cand)} candidates, "
          f"sen_col_start=6)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path,
                    help="path to 2013_per_precincts_senators.xls")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    build(args.src, args.out)


if __name__ == "__main__":
    main()
