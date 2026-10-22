#!/usr/bin/env python3
"""Render per-county link previews for votepower.us.

For every county in voter_turnout_data.csv this writes:
  og/<FIPS>.png        1200x630 Open Graph image (2022 midterm figure)
  c/<FIPS>/index.html  a tiny page whose <meta> tags point at that image and
                       which forwards visitors to /?c=<FIPS>
plus og/default.png for the home page.

Link unfurlers (iMessage, X, Facebook, Slack, LinkedIn) read the meta tags and
never run JavaScript, so each shared county link shows its own number.

Requires: playwright (with Chromium) and Pillow. Run from the repo root:
  python3 scripts/render_previews.py            # pre-election copy
  python3 scripts/render_previews.py --after    # "My vote counts for" copy
"""
import argparse
import base64
import csv
import html
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

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{image}">
<script>location.replace("/?c={fips}" + (location.search ? "&" + location.search.slice(1) : ""));</script>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#FFD23F;color:#17112E;font:700 18px system-ui,sans-serif}}a{{color:#17112E}}</style>
</head>
<body>
<a href="/?c={fips}">See how many people you're voting for &rarr;</a>
</body>
</html>
"""


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
    lead_sentence = "My vote counts for" if args.after else "I'm voting for"

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

            only = "Only " if float(r["Voter Turnout 2022"].rstrip("%")) < 75 else ""
            title = f"{lead_sentence} {vp} people in {place_short(state, county)}"
            desc = (f"{only}{turnout}% of {area(state, county)} voted in the 2022 midterm. "
                    "How many people are you voting for?")
            os.makedirs(f"c/{fips}", exist_ok=True)
            with open(f"c/{fips}/index.html", "w") as f:
                f.write(PAGE.format(
                    title=html.escape(title), desc=html.escape(desc),
                    alt=html.escape(f"Sticker reading {lead_sentence} {vp} people, {place_short(state, county)}"),
                    url=f"{SITE}/c/{fips}/", image=f"{SITE}/og/{fips}.png", fips=fips))
            if (i + 1) % 250 == 0:
                print(f"{i + 1}/{len(rows)}", flush=True)

        browser.close()
    server.shutdown()
    print(f"Rendered {len(rows)} county previews + default")


if __name__ == "__main__":
    main()
