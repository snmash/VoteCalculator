#!/usr/bin/env python3
"""Render per-county link previews for votepower.us.

For every county in voter_turnout_data.csv this writes og/<FIPS>.png, a
1200x630 Open Graph image of the 2022 midterm figure, plus og/default.png.
The county pages that reference them (c/<FIPS>/index.html) are written by
scripts/build_pages.py. Link unfurlers (iMessage, X, Facebook, Slack, LinkedIn)
read those pages' meta tags, so each shared county link shows its own number.

Requires: playwright (with Chromium) and Pillow. Run from the repo root:
  python3 scripts/render_previews.py            # pre-election copy
  python3 scripts/render_previews.py --after    # "My vote counts for" copy
"""
import argparse
import base64
import csv
import io
import os
import socketserver
import threading
from decimal import ROUND_HALF_UP, Decimal
from functools import partial
from http.server import SimpleHTTPRequestHandler

from PIL import Image
from playwright.sync_api import sync_playwright

SITE = "https://votepower.us"
ELECTION = "2022 midterm"

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}



def whole_pct(s):
    return str(Decimal(s.rstrip("%")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def place_short(state, county):
    return STATE_NAMES[state] if county.startswith("Statewide") else f"{county}, {state}"


def area(state, county):
    return STATE_NAMES[state] if county.startswith("Statewide") else county


def quantized_png(data_url):
    raw = base64.b64decode(data_url.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    out = io.BytesIO()
    img.quantize(colors=48, method=Image.Quantize.MEDIANCUT).save(out, format="PNG", optimize=True)
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", action="store_true", help="use post-election copy")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()
    lead = "MY VOTE COUNTS FOR" if args.after else "I'M VOTING FOR"

    root = os.getcwd()
    rows = list(csv.DictReader(open(os.path.join(root, "voter_turnout_data.csv"), newline="")))
    os.makedirs("og", exist_ok=True)

    handler = partial(SimpleHTTPRequestHandler, directory=root)
    handler.log_message = lambda *a, **k: None
    server = socketserver.TCPServer(("127.0.0.1", args.port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{args.port}/scripts/og/og.html")

        default = {"lead": lead, "number": "?", "place": "Every U.S. county",
                   "election": "", "turnout": "", "sub": "Real turnout data, 2022 & 2024"}
        with open("og/default.png", "wb") as f:
            f.write(quantized_png(page.evaluate("d => renderOg(d)", default)))

        for i, r in enumerate(rows):
            fips, state, county = r["FIPS"], r["State"], r["County Name"]
            vp = r["Vote Power 2022"]
            turnout = whole_pct(r["Voter Turnout 2022"])
            d = {"lead": lead, "number": vp, "place": place_short(state, county),
                 "election": ELECTION, "turnout": turnout + "%"}
            with open(f"og/{fips}.png", "wb") as f:
                f.write(quantized_png(page.evaluate("d => renderOg(d)", d)))

            if (i + 1) % 250 == 0:
                print(f"{i + 1}/{len(rows)}", flush=True)

        browser.close()
    server.shutdown()
    print(f"Rendered {len(rows)} county preview images + default")


if __name__ == "__main__":
    main()
