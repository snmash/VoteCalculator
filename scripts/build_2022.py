#!/usr/bin/env python3
"""Aggregate MEDSL 2022 precinct returns to county turnout totals.

Input: the unzipped state CSVs from MEDSL's 2022 general election repository
(https://github.com/MEDSL/2022-elections-official, individual_states/*.zip).

For each county, turnout is measured as the highest total vote count among:
  * each statewide race (U.S. Senate, governor, other statewide offices and
    statewide ballot questions), and
  * U.S. House, summed across all districts touching the county
    (each voter casts exactly one House vote).
This "highest office" approach is the standard proxy for ballots cast when no
single race appears on every ballot.

Rules applied so each vote is counted once:
  * Pseudo-candidate rows (undervotes, overvotes, blanks, "total votes",
    "ballots cast", etc.) are dropped.
  * Where a precinct reports both TOTAL and per-method rows for the same
    candidate, only TOTAL is used; otherwise the methods are summed.
  * Multi-seat races (magnitude > 1) and runoffs are excluded.

Output: county_votes_2022.csv with columns fips,total_votes_2022,source.
Counties with no precinct data are filled from official county totals in
scripts/county_votes_2022_fill.csv (see that file's source column).

Usage:
  python3 scripts/build_2022.py --in-dir 2022_state_csvs --out scripts/county_votes_2022.csv
"""
import argparse
import csv
import glob
import os

import pandas as pd

NON_VOTES = {
    "OVER VOTES", "UNDER VOTES", "OVERVOTES", "UNDERVOTES", "OVERVOTE", "UNDERVOTE",
    "BLANK", "BLANK BALLOTS", "BLANK/VOID", "BLANK VOTES", "BLANK (2)", "BLANK WRITE-IN",
    "VOID", "SPOILED", "CONTEST TOTALS", "TOTAL VOTES", "TOTAL VOTES CAST",
    "WRITE-IN TOTALS", "BALLOTS CAST", "TOTAL BALLOTS CAST", "REGISTERED VOTERS",
    # Michigan tabulator summary rows
    "CAST VOTES", "REJECTED", "UNRESOLVED", "REJECTED WRITE-INS", "UNRESOLVED WRITE-IN",
    # New York ballot-count rows (counts of ballots by type, not candidate votes)
    "PUBLIC COUNTER", "ABSENTEE / MILITARY", "AFFIDAVIT", "FEDERAL", "SPECIAL VOTES",
    "MANUALLY COUNTED EMERGENCY", "EMERGENCY", "UNQUALIFIED WRITE-IN", "NOT QUALIFIED",
    "TOTAL", "TOTALS",
}
WRITEIN_PATTERN = r"WRITE.?IN|SCATTER"
COLS = ["state_po", "county_fips", "precinct", "office", "dataverse", "district",
        "mode", "candidate", "votes", "stage", "special", "magnitude"]


def county_totals(path):
    df = pd.read_csv(path, usecols=lambda c: c in COLS, dtype=str, low_memory=False)
    state = df["state_po"].dropna().iloc[0]
    df = df[df["dataverse"].isin(["SENATE", "HOUSE", "STATE"])]
    df = df[df["stage"].fillna("GEN") == "GEN"]
    dist = df["district"].fillna("").str.upper()
    # Statewide state races: district "STATEWIDE" or blank (e.g. Michigan governor).
    df = df[(df["dataverse"] != "STATE") | dist.isin(["STATEWIDE", ""])]
    mag = pd.to_numeric(df["magnitude"], errors="coerce").fillna(1)
    df = df[mag <= 1]
    df = df[~df["candidate"].fillna("").str.upper().str.strip().isin(NON_VOTES)]
    # Some states (e.g. NJ) include "<County> Totals" / "District N Totals" rows.
    df = df[~df["precinct"].fillna("").str.contains(r"\bTOTALS?\b", case=False, regex=True)]
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0)
    # Missing or "UNSPECIFIED" mode is the all-methods total (e.g. New York).
    df["mode"] = df["mode"].fillna("TOTAL").str.upper().replace({"UNSPECIFIED": "TOTAL"})
    df["county_fips"] = df["county_fips"].fillna("").str.replace(r"\.0$", "", regex=True)
    if state == "AK":
        df["county_fips"] = "02000"
    df = df[df["county_fips"] != ""]
    df["county_fips"] = df["county_fips"].str.zfill(5)

    # Race key: House is one "race" per county (summed across districts).
    is_house = df["dataverse"] == "HOUSE"
    df["race"] = df["office"].fillna("") + "|" + df["special"].fillna("") + "|" + df["district"].fillna("")
    # House races sum across districts; keyed by office so DC's duplicated
    # "DELEGATE TO THE HOUSE" / "US HOUSE" listings aren't added together.
    df.loc[is_house, "race"] = "US HOUSE|" + df.loc[is_house, "office"].fillna("")

    key = ["county_fips", "race", "precinct", "district", "candidate"]
    has_total = df.assign(t=df["mode"] == "TOTAL").groupby(key, dropna=False)["t"].transform("any")
    df = df[(~has_total) | (df["mode"] == "TOTAL")]

    # Guard against mis-coded aggregate rows labelled as write-ins (e.g. Putnam
    # County, NY, where a "WRITE-IN" row repeats the whole race total): drop any
    # generic write-in row holding half or more of its race's county votes.
    cand = df["candidate"].fillna("").str.upper()
    is_wi = cand.str.contains(WRITEIN_PATTERN, regex=True)
    race_sum = df.groupby(["county_fips", "race"])["votes"].transform("sum")
    wi_sum = df["votes"].where(is_wi, 0).groupby([df["county_fips"], df["race"]]).transform("sum")
    df = df[~(is_wi & (race_sum > 0) & (wi_sum >= 0.5 * race_sum))]

    race_totals = df.groupby(["county_fips", "race"])["votes"].sum().reset_index()
    office = race_totals["race"].str.split("|").str[0].str.upper()
    race_totals["core"] = race_totals["race"].str.startswith("US HOUSE|") | office.str.startswith("US SENATE") \
        | office.str.match(r"^GOVERNOR")
    core = race_totals[race_totals["core"]].groupby("county_fips")["votes"].max()
    other = race_totals[~race_totals["core"]].groupby("county_fips")["votes"].max()
    best = {}
    for fips in set(core.index) | set(other.index):
        c = core.get(fips, 0)
        o = other.get(fips, 0)
        # Other statewide races can't always be split by seat (e.g. several
        # judgeships share one office name), so they only count when they are
        # within 10% of the Senate/Governor/House anchor.
        best[fips] = max(c, o) if (c == 0 or o <= 1.10 * c) else c
    return state, pd.Series(best)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--fill", default=os.path.join(os.path.dirname(__file__), "county_votes_2022_fill.csv"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "county_votes_2022.csv"))
    args = ap.parse_args()

    fill = {}
    if os.path.exists(args.fill):
        with open(args.fill, newline="") as f:
            for r in csv.DictReader(f):
                fill[r["fips"].zfill(5)] = (int(r["total_votes_2022"]), r["source"])

    out = {}
    for path in sorted(glob.glob(os.path.join(args.in_dir, "*.csv"))):
        state, best = county_totals(path)
        for fips, v in best.items():
            out[fips] = (int(round(v)), "MEDSL precinct returns")
        print(f"{state}: {len(best)} counties")

    # Official county totals override/fill where precinct data is incomplete.
    for fips, (v, src) in fill.items():
        out[fips] = (v, src)

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fips", "total_votes_2022", "source"])
        for fips in sorted(out):
            w.writerow([fips, out[fips][0], out[fips][1]])
    print(f"Wrote {len(out)} counties to {args.out}")


if __name__ == "__main__":
    main()
