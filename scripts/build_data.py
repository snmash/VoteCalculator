#!/usr/bin/env python3
"""Rebuild voter_turnout_data.csv for votepower.us.

Also reads scripts/county_votes_2022.csv (committed; produced by
scripts/build_2022.py from MEDSL 2022 precinct returns) for the midterm view.

Inputs (not committed; download from the sources below):
  --medsl  countypres_2000-2024.csv  MIT Election Data and Science Lab,
           "County Presidential Election Returns 2000-2024",
           Harvard Dataverse, doi:10.7910/DVN/VOQCHQ
  --cvap-dir  folder with County.csv and MCD.csv from the U.S. Census Bureau
           "Citizen Voting Age Population by Race and Ethnicity 2020-2024"
           (ACS 5-year special tabulation, released Jan 2026)

Method:
  turnout    = 2024 total presidential votes / 2020-2024 CVAP estimate
  vote power = 100 / turnout  (eligible citizens represented per actual voter)

Special cases:
  * Connecticut: MEDSL reports the 8 historical counties; the 2020-2024 CVAP
    uses the 9 planning regions adopted in 2022. Town-level CVAP (MCD.csv) is
    summed to the historical counties via scripts/ct_town_county.csv.
  * Alaska: MEDSL reports by state house district, which does not nest into
    boroughs, so Alaska is published as one statewide row.
  * Turnout above 100% (small-county sampling error in the ACS) is capped at
    100% and flagged.

Usage:
  python3 scripts/build_data.py --medsl countypres_2000-2024.csv \
      --cvap-dir CVAP_2020-2024_ACS_csv_files --out voter_turnout_data.csv
"""
import argparse
import csv
import os
from collections import defaultdict

YEAR = "2024"
LOW_TURNOUT_FLAG = 40.0   # % — often driven by prison/military populations
LOW_TURNOUT_FLAG_2022 = 25.0  # % — midterm equivalent of the flag above
MOE_FLAG = 0.10          # CVAP margin of error > 10% of the estimate

STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
CT_COUNTY_FIPS = {
    "Fairfield": "09001", "Hartford": "09003", "Litchfield": "09005",
    "Middlesex": "09007", "New Haven": "09009", "New London": "09011",
    "Tolland": "09013", "Windham": "09015",
}


def read_cvap(path):
    """Yield total-row records (lnnumber 1) from a CVAP csv."""
    with open(path, encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            if row["lnnumber"] == "1":
                yield row


def load_votes(medsl_path):
    """Return {fips: total presidential votes} for YEAR.

    In the 2024 file `totalvotes` is the county total repeated on every
    candidate/mode row, so one value per county is taken (never summed).
    """
    votes, names = {}, {}
    with open(medsl_path, newline="") as f:
        for row in csv.DictReader(f):
            if row["year"] != YEAR:
                continue
            fips = row["county_fips"].zfill(5)
            tv = int(float(row["totalvotes"]))
            if fips in votes and votes[fips] != tv:
                raise ValueError(f"Inconsistent totalvotes for {fips}")
            votes[fips] = tv
            names[fips] = row["county_name"]
    # Kansas City, MO has its own election board (MEDSL code 36000) covering
    # the part of the city inside Jackson County; fold it into Jackson.
    if "36000" in votes:
        votes["29095"] += votes.pop("36000")
    # Shannon County, SD was renamed Oglala Lakota (FIPS 46113 -> 46102) in 2015.
    if "46113" in votes:
        votes["46102"] = votes.pop("46113")
    return votes, names


def load_votes_2022(path):
    """Return {fips: total votes, highest office} from scripts/build_2022.py output."""
    votes = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            votes[row["fips"].zfill(5)] = int(row["total_votes_2022"])
    if "36000" in votes:
        votes["29095"] = votes.get("29095", 0) + votes.pop("36000")
    if "46113" in votes:
        votes["46102"] = votes.pop("46113")
    return votes


def load_cvap(cvap_dir, ct_crosswalk):
    """Return {fips: (name, cvap_est, cvap_moe)} for counties, with CT
    rebuilt on historical counties from town-level data."""
    out = {}
    for row in read_cvap(os.path.join(cvap_dir, "County.csv")):
        fips = row["geoid"][-5:]
        if fips[:2] not in STATE_FIPS or fips[:2] == "09":
            continue  # skip Puerto Rico; CT handled below
        name = row["geoname"].rsplit(",", 1)[0]
        out[fips] = (name, int(row["cvap_est"]), int(row["cvap_moe"]))

    # Kalawao County, HI (~80 residents) votes as part of Maui County.
    if "15005" in out:
        _, k_est, k_moe = out.pop("15005")
        name, est, moe = out["15009"]
        out["15009"] = (name, est + k_est, round((moe ** 2 + k_moe ** 2) ** 0.5))

    town_to_county = {}
    with open(ct_crosswalk, newline="") as f:
        for r in csv.DictReader(f):
            town_to_county[r["town"]] = r["county"]

    ct_est, ct_moe_sq, matched = defaultdict(int), defaultdict(int), set()
    for row in read_cvap(os.path.join(cvap_dir, "MCD.csv")):
        if row["geoid"][9:11] != "09":
            continue
        town_label = row["geoname"].split(",")[0]
        if not town_label.endswith(" town"):
            # "County subdivisions not defined" = offshore water areas (0-1 people)
            if int(row["cvap_est"]) > 10:
                raise ValueError(f"Unexpected CT subdivision: {row['geoname']}")
            continue
        town = town_label[: -len(" town")]
        county = town_to_county[town]
        ct_est[county] += int(row["cvap_est"])
        ct_moe_sq[county] += int(row["cvap_moe"]) ** 2  # Census approx. for sums
        matched.add(town)
    missing = set(town_to_county) - matched
    if missing:
        raise ValueError(f"CT towns missing from CVAP: {sorted(missing)}")
    for county, fips in CT_COUNTY_FIPS.items():
        out[fips] = (f"{county} County", ct_est[county], round(ct_moe_sq[county] ** 0.5))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--medsl", required=True)
    ap.add_argument("--cvap-dir", required=True)
    ap.add_argument("--ct-crosswalk", default=os.path.join(os.path.dirname(__file__), "ct_town_county.csv"))
    ap.add_argument("--votes-2022", default=os.path.join(os.path.dirname(__file__), "county_votes_2022.csv"))
    ap.add_argument("--out", default="voter_turnout_data.csv")
    args = ap.parse_args()

    votes, _ = load_votes(args.medsl)
    votes22 = load_votes_2022(args.votes_2022)
    cvap = load_cvap(args.cvap_dir, args.ct_crosswalk)

    # Alaska: collapse house districts and boroughs to one statewide row.
    ak_votes = sum(v for f, v in votes.items() if f.startswith("02"))
    ak_cvap = [c for f, c in cvap.items() if f.startswith("02")]
    for f in [f for f in votes if f.startswith("02")]:
        del votes[f]
    for f in [f for f in cvap if f.startswith("02")]:
        del cvap[f]
    votes["02000"] = ak_votes
    cvap["02000"] = (
        "Statewide (Alaska reports by election district)",
        sum(c[1] for c in ak_cvap),
        round(sum(c[2] ** 2 for c in ak_cvap) ** 0.5),
    )

    unmatched_votes = sorted(set(votes) - set(cvap))
    unmatched_cvap = sorted(set(cvap) - set(votes))
    if unmatched_votes or unmatched_cvap:
        raise ValueError(f"Join failure. votes-only: {unmatched_votes} cvap-only: {unmatched_cvap}")
    unmatched22 = sorted(set(cvap) ^ set(votes22))
    if unmatched22:
        raise ValueError(f"2022 join failure: {unmatched22}")

    rows = []
    for fips in cvap:
        name, est, moe = cvap[fips]
        raw = 100.0 * votes[fips] / est
        turnout = min(raw, 100.0)
        notes = []
        if raw > 100.0:
            notes.append("small-population")
        elif moe / est > MOE_FLAG:
            notes.append("small-population")
        if turnout < LOW_TURNOUT_FLAG:
            notes.append("ineligible-residents")
        raw22 = 100.0 * votes22[fips] / est
        turnout22 = min(raw22, 100.0)
        if turnout22 < LOW_TURNOUT_FLAG_2022 and "ineligible-residents" not in notes:
            notes.append("ineligible-residents")
        rows.append({
            "State": STATE_FIPS[fips[:2]],
            "County Name": name,
            "Vote Power": f"{100.0 / turnout:.1f}",
            "Voter Turnout": f"{turnout:.1f}%",
            "FIPS": fips,
            "Total Votes 2024": votes[fips],
            "CVAP 2020-2024": est,
            "CVAP MOE": moe,
            "Note": ";".join(dict.fromkeys(notes)),
            "Vote Power 2022": f"{100.0 / turnout22:.1f}",
            "Voter Turnout 2022": f"{turnout22:.1f}%",
            "Total Votes 2022": votes22[fips],
        })
    rows.sort(key=lambda r: (r["State"], r["County Name"]))

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
