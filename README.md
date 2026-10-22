**Voting Impact Calculator** — [votepower.us](https://votepower.us)

The Voting Impact Calculator shows how powerful your vote can be, especially in low-turnout counties. Pick your county and see how many eligible voters your vote represents.

**Features**

State & county selection: choose your state and county.

Voting power calculation: shows how many eligible citizens each actual voter represents, with caveats for small-population counties and counties with large ineligible populations.

Social sharing: share your result on Facebook, X, Threads, LinkedIn, or Instagram (Instagram copies the text to paste).

**Sharing and link previews**

- The result card reads "I'm voting for N people" (switching to "My vote counts for" after Election Day), with a one-tap share that generates a 4:5 sticker image in the browser (`share-card.js`).
- Every county has a share URL, `votepower.us/c/<FIPS>/`, whose Open Graph image (`og/<FIPS>.png`) shows that county's 2022 midterm number, so links unfurl with the number in iMessage, X, Threads, Slack and LinkedIn. Regenerate them after any data change with `python3 scripts/render_previews.py` (add `--after` once the election is over).
- Fonts (Anton, Archivo, Bricolage Grotesque) are self-hosted under `fonts/` with their SIL Open Font Licenses.

**Technologies Used**

HTML, CSS, JavaScript; PapaParse for CSV parsing; Python for the data build.

**Usage**

Pick Midterm (2022) or Presidential (2024), select your state and county, click "Calculate!", and share your results. The site defaults to the midterm view because 2026 is a midterm year.

**Methodology**

`Vote Power = CVAP / votes cast = 100 / turnout %`

- Numerator, 2024: total votes for U.S. President, November 2024 general election, by county.
- Numerator, 2022: highest county vote total among statewide races (U.S. Senate, governor, other statewide offices and ballot questions) and U.S. House summed across districts. Built by `scripts/build_2022.py` from MEDSL precinct returns, which:
  - drops pseudo-candidate rows (undervotes, overvotes, blanks, "cast votes", NY ballot-count rows, "Totals" summary precincts);
  - counts each vote once when a precinct reports both TOTAL and per-method rows;
  - excludes runoffs and multi-seat races;
  - only counts non-Senate/Governor/House statewide races when they're within 10% of those, because several judgeships can share one office name;
  - drops generic write-in rows holding half or more of a race (a data error in Putnam County, NY).
- 2022 gaps: Indiana (many counties lacking precinct data), Phillips County, AR and Power County, ID use county totals from the certified results (`scripts/county_votes_2022_fill.csv`). The national 2022 total is 110.7M votes, about 46% of CVAP.
- Denominator: citizen voting-age population (CVAP), 2020–2024 ACS 5-year estimates, used for both years.
- Connecticut: CVAP is reported for the 9 planning regions, but election returns use the 8 historical counties. Town-level CVAP is summed to those counties using `scripts/ct_town_county.csv`.
- Alaska: returns are by state house district, which doesn't nest into boroughs, so Alaska is one statewide row.
- Kansas City, MO (separate election board) is folded into Jackson County. Kalawao County, HI is combined with Maui. Shannon County, SD is mapped to Oglala Lakota County (FIPS 46102).
- Turnout above 100% (ACS sampling error in tiny counties) is capped at 100%.
- The `Note` column flags `small-population` (CVAP margin of error >10% of the estimate, or raw turnout >100%) and `ineligible-residents` (2024 turnout <40% or 2022 turnout <25%, typically prison, military-base or college counties).

Known limitations: ballots that skip the top race are not counted, so turnout is slightly understated. CVAP includes incarcerated people, military personnel and students who vote elsewhere.

**Rebuilding the data**

1. Download `countypres_2000-2024.csv` from [Harvard Dataverse](https://doi.org/10.7910/DVN/VOQCHQ).
2. Download and unzip the [2020–2024 CVAP CSV files](https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap/2020-2024-CVAP.html).
3. Optional, only to regenerate `scripts/county_votes_2022.csv`: clone [MEDSL/2022-elections-official](https://github.com/MEDSL/2022-elections-official) and unzip `individual_states/*.zip` into one folder.
4. Run:

```
python3 scripts/build_2022.py --in-dir 2022_state_csvs      # optional, step 3
python3 scripts/build_data.py --medsl countypres_2000-2024.csv \
    --cvap-dir CVAP_2020-2024_ACS_csv_files --out voter_turnout_data.csv
```

**Data Sources**

- MIT Election Data and Science Lab, 2018, "County Presidential Election Returns 2000–2024," Harvard Dataverse, https://doi.org/10.7910/DVN/VOQCHQ (data version 2026-02-25).
- MIT Election Data and Science Lab, "2022 General Election Precinct-Level Returns," https://github.com/MEDSL/2022-elections-official (accessed October 2026).
- 2022 county totals for Indiana, Phillips County AR and Power County ID from Wikipedia's county results tables of the certified results, cross-checked against MEDSL where both exist (`scripts/county_votes_2022_fill.csv`).
- U.S. Census Bureau, "Citizen Voting Age Population by Race and Ethnicity, 2020–2024," American Community Survey 5-year special tabulation (released January 2026), https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap/2020-2024-CVAP.html

Earlier versions of this site (2024) used 2020 presidential returns and 2016–2020 CVAP.

**License**

This project is under the GPL-3.0 license.
