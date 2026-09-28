#!/usr/bin/env python3
"""Build the coalition/alliance dataset from the per-year senator CSV headers.

Coalition memberships are hand-coded from news sources (see README_coalitions.md).
We key each membership on a distinctive substring of the *exact* ballot label used
as a column header in the vote CSVs, so the output joins 1:1 on `ballot_label`.
A candidate can appear in >1 coalition in a year (guest / cross-endorsement).
"""
import csv, re, sys
from pathlib import Path

ROOT = Path("data/elections")
YEARS = ["2013", "2016", "2019", "2022", "2025"]

# Full names for the short coalition labels.
FULL = {
    "Team PNoy": "Team PNoy (LP-led administration coalition: LP, NP, NPC, Akbayan, LDP)",
    "UNA": "United Nationalist Alliance",
    "Makabayan": "Makabayan coalition (progressive party-list bloc)",
    "Ang Kapatiran": "Ang Kapatiran Party (party slate)",
    "Democratic Party of the Philippines": "Democratic Party of the Philippines (party slate)",
    "Koalisyon ng Daang Matuwid": "Koalisyon ng Daang Matuwid (LP-led administration coalition, Roxas)",
    "Partido Galing at Puso": "Partido Galing at Puso (Poe-Escudero slate)",
    "Hugpong ng Pagbabago": "Hugpong ng Pagbabago (administration regional coalition, Sara Duterte)",
    "Otso Diretso": "Otso Diretso (opposition coalition: LP, Akbayan, Aksyon, Magdalo)",
    "Labor Win": "Labor Win (labor coalition)",
    "Katipunan ng Demokratikong Pilipino": "Katipunan ng Demokratikong Pilipino (party slate)",
    "UniTeam": "UniTeam Alliance (Marcos-Duterte: Lakas, PDP-Laban faction, NP, others)",
    "Tropang Angat": "Team Robredo-Pangilinan / Tropang Angat (opposition)",
    "Pacquiao (MP3/PROMDI)": "Manny Pacquiao slate (MP3 Alliance / PROMDI-PDP faction)",
    "Aksyon (Isko Moreno)": "Isko Moreno slate (Aksyon Demokratiko)",
    "Lacson-Sotto": "Lacson-Sotto slate (Partido Reporma / NPC)",
    "LEAD (PLM)": "Leody de Guzman-Walden Bello / LEAD (Partido Lakas ng Masa)",
    "Alyansa para sa Bagong Pilipinas": "Alyansa para sa Bagong Pilipinas (administration coalition: PFP, Lakas, NP, NUP, NPC)",
    "DuterTen": "DuterTen (Duterte-aligned slate, PDP-Laban)",
    "KiBam": "KiBam (Aquino-Pangilinan, Liberal-backed)",
    "Partido Lakas ng Masa": "Partido Lakas ng Masa / Bunyog (labor-left bloc)",
}

# Per year: coalition -> {membership: [distinctive ballot-label substrings]}
# membership is "core" (own committed lineup) or "guest" (adopted/invited, ran under own party/IND).
MAP = {
"2013": {
    "Team PNoy": {"core": ["ANGARA, EDGARDO", "AQUINO, BENIGNO BAM", "CAYETANO, ALAN PETER",
                            "HONTIVEROS", "MADRIGAL", "MAGSAYSAY, RAMON JR", "PIMENTEL, KOKO",
                            "TRILLANES", "VILLAR, CYNTHIA"],
                  "guest": ["ESCUDERO, CHIZ", "LEGARDA, LOREN", "POE, GRACE"]},
    "UNA": {"core": ["BINAY, NANCY", "COJUANGCO, TINGTING", "EJERCITO ESTRADA, JV",
                     "ENRILE, JUAN PONCE JR", "GORDON, DICK", "HONASAN, GRINGO",
                     "MACEDA", "MAGSAYSAY, MITOS", "ZUBIRI, MIGZ"],
            "guest": ["ESCUDERO, CHIZ", "LEGARDA, LOREN", "POE, GRACE"]},  # later dropped by UNA
    "Makabayan": {"core": ["CASINO, TEDDY"]},
    "Ang Kapatiran": {"core": ["DAVID, LITO", "DELOS REYES, JC", "LLASOS"]},
    "Democratic Party of the Philippines": {"core": ["BELGICA, GRECO", "FALCONE", "SENERES"]},
},
"2016": {
    "Koalisyon ng Daang Matuwid": {
        "core": ["DRILON", "GUINGONA", "PANGILINAN, KIKO", "DE LIMA", "PETILLA",
                 "VILLANUEVA, JOEL", "LAPID, MARK", "HONTIVEROS", "AMBOLODTO",
                 "PAEZ", "RECTO, RALPH"],
        "guest": ["LACSON, PANFILO PING"]},
    "Partido Galing at Puso": {
        "core": ["KAPUNAN", "ROMULO, ROMAN", "MANZANO", "PAGDILAO", "DOMAGOSO", "GATCHALIAN"],
        "guest": ["OPLE", "GORDON, DICK", "ZUBIRI, MIGZ", "SOTTO", "COLMENARES", "RECTO, RALPH"]},
    "UNA": {
        "core": ["PACQUIAO", "NAPEÑAS", "LACSAMANA", "KIRAM", "LANGIT", "MONTANO, ALLAN"],
        "guest": ["OPLE", "SOTTO", "LACSON, PANFILO PING", "GORDON, DICK", "ZUBIRI, MIGZ", "ROMUALDEZ"]},
    "Makabayan": {"core": ["COLMENARES"]},
},
"2019": {
    "Hugpong ng Pagbabago": {"core": ["VILLAR, CYNTHIA", "MARCOS, IMEE", "CAYETANO, PIA",
                                       "GO, BONG GO", "DELA ROSA, BATO", "EJERCITO, ESTRADA JV",
                                       "ESTRADA, JINGGOY", "ANGARA, EDGARDO SONNY", "PIMENTEL, KOKO",
                                       "MANGUDADATU", "MANICAD", "BONG REVILLA", "ONG, DOC WILLIE",
                                       "TOLENTINO, FRANCIS"]},
    "Otso Diretso": {"core": ["AQUINO, BENIGNO BAM", "ALEJANO", "DIOKNO", "GUTOC", "HILBAY",
                              "MACALINTAL", "ROXAS, MAR", "TAÑADA"]},
    "Labor Win": {"core": ["MATULA", "ARELLANO", "DE GUZMAN, KA LEODY", "COLMENARES", "MONTAÑO, ALLAN"]},
    "Katipunan ng Demokratikong Pilipino": {"core": ["CASIÑO, TOTI", "CHONG, GLENN", "JAVELLANA",
                                                     "SAHIDULLA", "VALDES"]},
},
"2022": {
    "UniTeam": {"core": ["BAUTISTA", "ESTRADA, JINGGOY", "GADON", "GATCHALIAN", "PADILLA, ROBIN",
                         "ROQUE", "TEODORO", "VILLAR, MARK", "ZUBIRI"],
                "guest": ["HONASAN", "LEGARDA"]},
    "Tropang Angat": {"core": ["BAGUILAT", "DIOKNO", "DE LIMA", "HONTIVEROS", "LACSON, KUYA ALEX",
                               "MATULA", "TRILLANES"],
                      "guest": ["BINAY, JOJO", "ESCUDERO", "GORDON", "VILLANUEVA"]},
    "Pacquiao (MP3/PROMDI)": {"guest": ["BARBO", "EJERCITO, JV ESTRADA", "ESCUDERO", "LEGARDA",
                                        "TULFO", "VILLANUEVA", "ZUBIRI", "BINAY, JOJO"]},
    "Aksyon (Isko Moreno)": {"core": ["BALITA", "CASTRICIONES", "GUTOC", "SISON"]},
    "Lacson-Sotto": {"core": ["ELEAZAR", "PADILLA, DRA. MINGUITA", "PIÑOL"],
                     "guest": ["HONASAN"]},
    "LEAD (PLM)": {"core": ["CABONEGRO", "D'ANGELO", "ESPIRITU"]},
    "Makabayan": {"core": ["COLMENARES", "LABOG"]},
},
"2025": {
    "Alyansa para sa Bagong Pilipinas": {"core": ["ABALOS", "BINAY, ABBY", "CAYETANO, PIA",
                                                  "LACSON, PING", "LAPID, LITO", "MARCOS, IMEE",
                                                  "PACQUIAO", "BONG REVILLA", "SOTTO", "TOLENTINO",
                                                  "TULFO, ERWIN", "VILLAR, CAMILLE"]},
    "DuterTen": {"core": ["BONDOC", "DELA ROSA, BATO", "GO, BONG GO", "HINLO", "LAMBINO",
                          "MARCOLETA", "MATA, DOC MARITES", "QUIBOLOY", "RODRIGUEZ, ATTY. VIC",
                          "SALVADOR"]},
    "KiBam": {"core": ["AQUINO, BAM", "PANGILINAN, KIKO"]},
    "Makabayan": {"core": ["ADONIS", "ANDAMO", "ARAMBULO", "BROSAS", "CASIÑO, TEDDY",
                           "CASTRO, TEACHER FRANCE", "DORINGO", "FLORANDA", "LIDASAN", "MAZA", "RAMOS"]},
    "Partido Lakas ng Masa": {"core": ["DE GUZMAN, KA LEODY", "ESPIRITU", "D'ANGELO"]},
},
}

def load_candidates(year):
    with open(ROOT / f"{year}_senators_complete.csv", newline="") as f:
        hdr = next(csv.reader(f))
    return [c for c in hdr if c and c[0].isdigit() and ". " in c]

def strip_num(label):
    return re.sub(r"^\d+\.\s*", "", label).strip()

def party_of(label):
    m = re.search(r"\(([^()]*)\)\s*$", label)
    return m.group(1).strip() if m else ""

rows = []
problems = []
for year in YEARS:
    cands = [strip_num(c) for c in load_candidates(year)]
    assigned = set()
    for coalition, memberships in MAP[year].items():
        for membership, keys in memberships.items():
            for key in keys:
                matches = [c for c in cands if key.upper() in c.upper()]
                if len(matches) != 1:
                    problems.append(f"{year} [{coalition}/{membership}] key {key!r} matched {len(matches)}: {matches}")
                    continue
                lab = matches[0]
                assigned.add(lab)
                rows.append({"year": year, "coalition": coalition,
                             "coalition_full": FULL[coalition], "membership": membership,
                             "ballot_label": lab, "party": party_of(lab)})
    # Everything unassigned -> Independent / none
    for c in cands:
        if c not in assigned:
            rows.append({"year": year, "coalition": "Independent / none",
                         "coalition_full": "No coalition / independent or minor-party slate",
                         "membership": "none", "ballot_label": c, "party": party_of(c)})

rows.sort(key=lambda r: (r["year"], r["coalition"], r["ballot_label"]))

out = ROOT / "coalitions_2013-2025.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["year", "coalition", "coalition_full", "membership",
                                      "ballot_label", "party"])
    w.writeheader()
    w.writerows(rows)

# Report
print(f"Wrote {len(rows)} rows -> {out}\n")
if problems:
    print("!!! KEY-MATCH PROBLEMS (fix before trusting output):")
    for p in problems:
        print("   ", p)
    sys.exit(1)
print("All slate keys matched exactly one candidate.\n")
from collections import Counter
for year in YEARS:
    yr = [r for r in rows if r["year"] == year]
    coals = Counter(r["coalition"] for r in yr)
    print(f"{year}: {len(yr)} rows")
    for co, n in coals.items():
        print(f"    {co}: {n}")
