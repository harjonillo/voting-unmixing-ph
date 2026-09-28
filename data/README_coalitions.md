# Senate coalition / alliance dataset (2013–2025)

**Built:** 2026-09-28. Companion to the per-candidate **party** data already encoded
in the vote CSV column headers (`SURNAME, NAME (PARTY)`). This adds the *other* layer
of grouping over parties — the campaign **coalition / alliance / slate** each
senatorial candidate ran with.

## Why this exists (and why not just party)

Philippine Senate candidates run **at large**, and the meaningful bloc is usually the
**slate/coalition** (Team PNoy, UNA, Otso Diretso, Hugpong, Alyansa, DuterTen…), not
the registered party. Parties are fluid and coalitions cut across them — e.g. in 2013
"Team PNoy" bundled LP, NP, NPC, Akbayan and LDP candidates on one ticket. Crucially:

- **There is no official COMELEC registry of Senate slates.** COMELEC records a
  candidate's *party* on the Certificate of Candidacy, but the campaign alliance is a
  political arrangement documented only by **news media** (and, secondarily, Wikipedia).
- So this dataset is compiled from **contemporaneous news coverage** — mainly the
  slate-announcement and "LIST" articles from Rappler, the *Philippine Daily Inquirer*,
  *PhilStar*, the *Philippine News Agency* and *Manila Bulletin*. Wikipedia was used
  only as a cross-check, never as the sole source for a membership.

## The file

`elections/coalitions_2013-2025.csv` — one row per *(candidate, coalition)* pairing.
A candidate can have **multiple rows in one year** when they were a guest / cross-endorsed
on more than one slate (common in 2016 and 2022).

> **Note on version control:** unlike the vote CSVs in `elections/` (which are gitignored
> re-downloadable dumps), this file is **hand-curated and committed** — `.gitignore`
> carries an explicit exception for it.

### Schema

| column | meaning |
|---|---|
| `year` | Senate election year (2013, 2016, 2019, 2022, 2025). |
| `coalition` | Short slate/alliance label (join key for grouping). `Independent / none` = ran with no multi-party coalition (true independents **and** minor single-party slates). |
| `coalition_full` | Expanded name + brief composition. |
| `membership` | `core` = the slate's own committed lineup (party members / firmly adopted); `guest` = adopted/invited candidate who ran under their own party or as independent and appeared on ≥1 other slate too; `none` = independents / unaffiliated. |
| `ballot_label` | **Exact** candidate string as it appears (minus the leading `"N. "`) in that year's `*_senators_complete.csv` header — the join key back to the vote data. |
| `party` | Party code parsed from `ballot_label` (blank where the ballot label carried none, e.g. 2013 Escudero/Poe). |

### Joining back to votes

`ballot_label` is byte-identical to the vote-CSV column header with the numeric prefix
stripped (`"3. AQUINO, BENIGNO BAM (LP)"` → `"AQUINO, BENIGNO BAM (LP)"`). Every slate
membership was verified in the build to match **exactly one** candidate column that year.

## How it was built

`scripts/build_coalitions.py`: reads each year's CSV header, hand-codes coalition
membership keyed on a distinctive substring of the exact ballot label, asserts each key
hits exactly one candidate, and writes the long CSV.
Any candidate not matched to a coalition is emitted as `Independent / none`. Re-running
regenerates the file deterministically.

## Coalitions per year (with member counts and sources)

Counts below are candidates **present in our vote CSVs**; a slate member who withdrew
before election day (so never appears as a vote column) is noted but not in the data.

### 2013 — Team PNoy vs UNA
- **Team PNoy** (12): LP-led admin coalition (LP/NP/NPC/Akbayan/LDP). 9 core +
  3 guest/common (Escudero, Legarda, Poe — independents/NPC adopted onto the ticket).
- **UNA** (12): United Nationalist Alliance (Binay/Estrada). 9 core + the same
  3 common candidates, whom **UNA later dropped** for skipping its sorties — recorded
  here as `guest` in both slates to reflect the shared-then-split arrangement.
- **Makabayan** (1): Teddy Casiño. **Ang Kapatiran** (3) and **Democratic Party of the
  Philippines** (3) are single-party slates, not coalitions — labelled as such.
- Sources: [Inquirer – UNA slate complete](https://newsinfo.inquirer.net/278550/una-senatorial-slate-for-2013-polls-complete-binay);
  [Inquirer – 9 Team PNoy, 3 UNA in Magic 12](https://newsinfo.inquirer.net/408363/9-team-pnoy-3-una-candidates-in-magic-12-as-of-1104-p-m-monday);
  [Rappler – How Team PNoy ran its 2013 campaign](https://www.rappler.com/philippines/elections/28653-campaign-team-pnoy-assessment/);
  [PhilStar – INC endorses 7 Team PNoy, 5 UNA](https://www.philstar.com/headlines/2013/05/10/940437/inc-endorses-7-team-pnoy-5-una-bets).

### 2016 — three overlapping slates
- **Koalisyon ng Daang Matuwid** (12): LP-led admin coalition (Roxas). 11 core + Lacson (guest).
- **Partido Galing at Puso** (12): Poe–Escudero slate. Heavy overlap with UNA (Ople,
  Gordon, Zubiri, Sotto guested on both) and with Daang Matuwid (Recto).
- **UNA** (12): Binay. 6 core + 6 guests (Ople, Sotto, Lacson, Gordon, Zubiri, Romualdez).
- **Makabayan** (1): Colmenares (also guested by Poe).
- Sources: [Inquirer – LP bares 'Koalisyon ng Daang Matuwid'](https://newsinfo.inquirer.net/730103/lp-bares-slate-dubbed-koalisyon-ng-daang-matuwid);
  [Rappler – Ruling coalition completes 12-person slate](https://www.rappler.com/philippines/elections/108924-liberal-party-2016-senate-slate/);
  [PhilStar – Grace, Chiz bare complete slate](https://www.philstar.com/headlines/2015/10/28/1516150/grace-chiz-bare-complete-senatorial-slate);
  [Rappler – Poe-Escudero complete slate](https://www.rappler.com/philippines/elections/111011-grace-poe-chiz-escudero-complete-final-senate-slate/);
  [Inquirer – UNA slate has 5 guests](https://newsinfo.inquirer.net/734692/una-senatorial-slate-has-5-guests);
  [Rappler – Binay completes UNA slate](https://www.rappler.com/philippines/elections/109926-una-senate-slate-complete/).

### 2019 — midterm
- **Hugpong ng Pagbabago** (14 in data): Sara Duterte's admin coalition. HNP endorsed
  **15**, but Harry Roque withdrew before the polls, so 14 appear as vote columns.
- **Otso Diretso** (8): opposition (LP/Akbayan/Aksyon/Magdalo).
- **Labor Win** (5): labor coalition (incl. Colmenares, De Guzman, Matula).
- **Katipunan ng Demokratikong Pilipino** (5): party slate (Casiño Toti, Chong, Javellana,
  Sahidulla, Valdes).
- Sources: [PNA – Hugpong picks 15 bets](https://www.pna.gov.ph/articles/1053189);
  [Rappler – Hugpong bares 2 Senate slates](https://www.rappler.com/nation/politics/elections/2019/213071-sara-duterte-hugpong-ng-pagbabago-senate-slates-2019-elections);
  [PhilStar – Who is the Labor Win Alliance](https://www.philstar.com/headlines/2019/03/04/1898590/who-labor-win-alliance);
  [Inquirer – Opposition completes 8-member slate (Otso Diretso)](https://newsinfo.inquirer.net/1043782/opposition-senatorial-slate-2019-elections).

### 2022 — presidential year, heavy cross-endorsement
Six+ presidential slates, with many candidates guesting across several. Recorded here:
**UniTeam** (Marcos–Duterte, 9 core + Honasan/Legarda guests), **Tropang Angat**
(Robredo–Pangilinan, 7 core + 4 guests), **Pacquiao MP3/PROMDI** (8, guests only in data),
**Aksyon/Isko Moreno** (4), **Lacson–Sotto** (3 + Honasan guest), **LEAD/PLM**
(De Guzman–Bello, 3), **Makabayan** (Colmenares, Labog).
- Source: [PhilStar – **LIST: 2022 senatorial slate of presidential candidates**](https://www.philstar.com/headlines/2022/05/09/2179800/list-2022-senatorial-slate-presidential-candidates)
  (the single most complete per-slate roster);
  [BusinessWorld – Robredo's Senate slate](https://bworldonline.com/the-nation/2021/10/15/403910/political-foes-and-senate-reelectionists-make-up-rest-of-robredos-senate-slate/).

### 2025 — midterm
- **Alyansa para sa Bagong Pilipinas** (12): admin coalition (PFP/Lakas/NP/NUP/NPC), Marcos.
- **DuterTen** (10): Duterte-aligned (PDP-Laban).
- **KiBam** (2): Aquino–Pangilinan, Liberal-backed.
- **Makabayan** (11): progressive party-list bloc.
- **Partido Lakas ng Masa / Bunyog** (3): De Guzman, Espiritu, D'Angelo — labor-left bloc.
- Sources: [PhilStar – Marcos bares Alyansa slate](https://www.philstar.com/headlines/2024/09/27/2388238/marcos-bares-alyansa-2025-senatorial-slate);
  [Rappler – Duterte's men / DuterTen file COCs](https://www.rappler.com/philippines/elections/dela-rosa-bong-go-phillip-salvador-run-file-certificates-candidacy-senator-2025/);
  [Manila Bulletin – DuterTen bets](https://mb.com.ph/2025/05/09/duterten-senatorial-bets-vow-to-continue-reforms-of-ex-president-duterte-during-miting-de-avance);
  [Rappler – Makabayan bets](https://www.rappler.com/philippines/elections/makabayan-coalition-runs-files-certificates-candidacy-senator-2025/);
  [Inquirer – Makabayan to field 11 bets](https://newsinfo.inquirer.net/1988003).

## Caveats & judgement calls (please read before analysis)

1. **`core` vs `guest` is a modelling choice, not an official status.** Coalitions
   freely "adopted" each other's bets. Where a candidate ran under their own party but
   was announced on another slate, they are `guest` there. If you only want each
   candidate's *primary* home, filter to `membership == 'core'` (note: a few pure
   guests — e.g. 2022 Pacquiao's list — then have no `core` row that year).
2. **Cross-endorsements are recorded but not exhaustive** for 2016 and 2022. We captured
   the well-sourced overlaps (shared guests between Poe/UNA in 2016; UniTeam/Pacquiao/
   Tropang Angat guests in 2022). Fringe or disputed guestings may be missing.
3. **2025 realignment:** Imee Marcos and Camille Villar were fielded as **Alyansa** but
   publicly drifted toward the Duterte camp late in the campaign; they are kept as Alyansa
   `core` (as filed). Adjust if your analysis is about *final* alignment rather than slate
   of record.
4. **`MATA, DOC MARITES (IND)` = Richard Mata** — the doctor-vlogger ("Doc Marites"
   online), Bong Go's uncle, adopted as DuterTen's 10th bet. The ballot uses his handle;
   news uses his real name. Verified same person, mapped to DuterTen.
   ([Inquirer](https://www.inquirer.net/436293/pdp-officially-adopts-doctor-vlogger-richard-mata-on-senate-slate/))
5. **`Independent / none` is a mixed bucket:** genuine independents *and* small
   single-party slates that aren't multi-party coalitions. Use the `party` column to
   separate them if needed.

## Rebuild

```
python3 scripts/build_coalitions.py   # from repo root; reads data/elections/*_senators_complete.csv
```

The builder self-checks that every slate key matches exactly one candidate column and
prints per-year coalition counts; a mismatch exits non-zero.
