**Voting Impact Calculator** — [votepower.us](https://votepower.us)

The Voting Impact Calculator shows how powerful your vote can be, especially in low-turnout counties. Pick your county and see how many eligible voters your vote represents.

**Features**

State & county selection: choose your state and county.

Voting power calculation: shows how many eligible citizens each actual voter represents, with caveats for small-population counties and counties with large ineligible populations.

Social sharing: share your result on Facebook, X, Threads, LinkedIn, or Instagram (Instagram copies the text to paste).

**Technologies Used**

HTML, CSS, JavaScript; PapaParse for CSV parsing; Python for the data build.

**Usage**

Select your state, choose your county, click "Calculate!", and share your results.

**Methodology**

`Vote Power = CVAP / total presidential votes = 100 / turnout %`

- Numerator: total votes for U.S. President, November 2024 general election, by county.
- Denominator: citizen voting-age population (CVAP), 2020–2024 ACS 5-year estimates.
- Connecticut: CVAP is reported for the 9 planning regions, but election returns use the 8 historical counties. Town-level CVAP is summed to those counties using `scripts/ct_town_county.csv`.
- Alaska: returns are by state house district, which doesn't nest into boroughs, so Alaska is one statewide row.
- Kansas City, MO (separate election board) is folded into Jackson County. Kalawao County, HI is combined with Maui. Shannon County, SD is mapped to Oglala Lakota County (FIPS 46102).
- Turnout above 100% (ACS sampling error in tiny counties) is capped at 100%.
- The `Note` column flags `small-population` (CVAP margin of error >10% of the estimate, or raw turnout >100%) and `ineligible-residents` (turnout <40%, typically prison or military-base counties).

Known limitations: undervotes for president are not counted, so turnout is slightly understated. CVAP includes incarcerated people and military personnel who vote elsewhere. Midterm-year turnout is substantially lower than presidential-year turnout.

**Rebuilding the data**

1. Download `countypres_2000-2024.csv` from [Harvard Dataverse](https://doi.org/10.7910/DVN/VOQCHQ).
2. Download and unzip the [2020–2024 CVAP CSV files](https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap/2020-2024-CVAP.html).
3. Run:

```
python3 scripts/build_data.py --medsl countypres_2000-2024.csv \
    --cvap-dir CVAP_2020-2024_ACS_csv_files --out voter_turnout_data.csv
```

**Data Sources**

- MIT Election Data and Science Lab, 2018, "County Presidential Election Returns 2000–2024," Harvard Dataverse, https://doi.org/10.7910/DVN/VOQCHQ (data version 2026-02-25).
- U.S. Census Bureau, "Citizen Voting Age Population by Race and Ethnicity, 2020–2024," American Community Survey 5-year special tabulation (released January 2026), https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap/2020-2024-CVAP.html

Earlier versions of this site (2024) used 2020 presidential returns and 2016–2020 CVAP.

**License**

This project is under the GPL-3.0 license.
