#!/usr/bin/env python3
"""Build the static, indexable pages for votepower.us from voter_turnout_data.csv.

Writes:
  c/<FIPS>/index.html          one page per county (share link + search landing page)
  state/<slug>/index.html      one page per state: counties ranked by vote power
  state/index.html             states ranked by turnout
  sitemap.xml, robots.txt

Run from the repo root after build_data.py (and render_previews.py for images):
  python3 scripts/build_pages.py            # pre-election social copy
  python3 scripts/build_pages.py --after    # "My vote counts for" social copy
"""
import argparse
import csv
import datetime
import html
import json
import os
import re
from collections import defaultdict

SITE = "https://votepower.us"
GA = """<script async src="https://www.googletagmanager.com/gtag/js?id=G-VGYJ2GP82F"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-VGYJ2GP82F');</script>"""

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
NOTES = {
    "small-population": "Small county: the Census estimate behind this number has a wide margin of error, so treat it as approximate.",
    "ineligible-residents": "Turnout here may look low partly because the Census count of eligible citizens includes people who don't vote locally, such as people in prison, or military personnel and college students registered elsewhere.",
}

e = html.escape


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def pct(x, digits=1):
    return f"{x:.{digits}f}%"


def num(n):
    return f"{n:,}"


def page(title, desc, canonical, body, og_title=None, og_desc=None, og_image=None, og_alt=None,
         jsonld=None, extra_head=""):
    og_title = og_title or title
    og_desc = og_desc or desc
    og_image = og_image or f"{SITE}/og/default.png"
    ld = ""
    for block in (jsonld or []):
        ld += '<script type="application/ld+json">' + json.dumps(block, separators=(",", ":")) + "</script>\n"
    alt = f'\n<meta property="og:image:alt" content="{e(og_alt)}">' if og_alt else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="theme-color" content="#FFD23F">
<link rel="preload" href="/fonts/anton-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/archivo-500.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/pages.css">
<meta property="og:site_name" content="votepower">
<meta property="og:title" content="{e(og_title)}">
<meta property="og:description" content="{e(og_desc)}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">{alt}
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(og_title)}">
<meta name="twitter:description" content="{e(og_desc)}">
<meta name="twitter:image" content="{og_image}">
{ld}{GA}
{extra_head}</head>
<body>
<main class="wrap">
<header class="top">
<a class="wordmark" href="/">VOTEPOWER</a>
<a class="top-link" href="/">Find your number &rarr;</a>
</header>
{body}
<footer class="credit">&copy; 2026 <a href="https://www.linkedin.com/in/snmahesh/" rel="noopener">Steven Maheshwary</a>. All rights reserved.</footer>
</main>
</body>
</html>
"""


def crumbs(items):
    lis = []
    for name, url in items:
        lis.append(f'<li><a href="{url}">{e(name)}</a></li>' if url else f'<li aria-current="page">{e(name)}</li>')
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + (url or "")}
        for i, (name, url) in enumerate(items) if url is not None or i == len(items) - 1]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>', ld


SOURCES = """<section class="sources">
<strong>Sources.</strong> Votes cast: MIT Election Data and Science Lab, county presidential returns (2024) and precinct-level returns (2022; highest statewide or U.S. House vote total per county). Eligible citizens: U.S. Census Bureau citizen voting-age population, 2020&ndash;2024 ACS 5-year estimates. <a href="/#methodology">How it works</a>.
</section>"""


def load():
    rows = list(csv.DictReader(open("voter_turnout_data.csv", newline="")))
    out = []
    for r in rows:
        c = {
            "fips": r["FIPS"], "st": r["State"], "state": STATE_NAMES[r["State"]],
            "raw_name": r["County Name"],
            "statewide": r["County Name"].startswith("Statewide"),
            "cvap": int(r["CVAP 2020-2024"]),
            "v22": int(r["Total Votes 2022"]), "t22": float(r["Voter Turnout 2022"].rstrip("%")), "vp22": float(r["Vote Power 2022"]),
            "v24": int(r["Total Votes 2024"]), "t24": float(r["Voter Turnout"].rstrip("%")), "vp24": float(r["Vote Power"]),
            "notes": [n for n in r["Note"].split(";") if n],
        }
        c["name"] = c["state"] if c["statewide"] else c["raw_name"]
        c["label"] = f'{c["state"]} (statewide)' if c["statewide"] else f'{c["raw_name"]}, {c["st"]}'
        c["long"] = c["state"] if c["statewide"] else f'{c["raw_name"]}, {c["state"]}'
        out.append(c)
    return out


def state_totals(counties):
    v22 = sum(c["v22"] for c in counties)
    v24 = sum(c["v24"] for c in counties)
    cv = sum(c["cvap"] for c in counties)
    return {"v22": v22, "v24": v24, "cvap": cv, "t22": 100 * v22 / cv, "t24": 100 * v24 / cv,
            "vp22": cv / v22, "vp24": cv / v24}


def comparison(x, ref):
    d = x - ref
    if abs(d) < 0.5:
        return "about the same as"
    return f"{abs(d):.1f} points {'higher' if d > 0 else 'lower'} than"


def county_page(c, peers, st_tot, nat, lead_social):
    fips = c["fips"]
    state_slug = slug(c["state"])
    ranked = sorted(peers, key=lambda x: (-x["vp22"], x["t22"]))
    rank = ranked.index(c) + 1
    n = len(ranked)
    nonvoters = max(c["cvap"] - c["v22"], 0)

    title = (f"{c['label']} Voter Turnout: Your Vote Counts for {c['vp22']:.1f} People"
             if not c["statewide"] else f"Alaska Voter Turnout: Your Vote Counts for {c['vp22']:.1f} People")
    desc = (f"{pct(c['t22'], 0)} of eligible citizens in {c['long']} voted in the 2022 midterm "
            f"({pct(c['t24'], 0)} in 2024), so each ballot spoke for {c['vp22']:.1f} people. "
            f"See how {c['name']} ranks and find your own number.")
    og_title = f"{lead_social} {c['vp22']:.1f} people in {c['label'].replace(' (statewide)', '')}"
    only = "Only " if c["t22"] < 75 else ""
    og_desc = f"{only}{pct(c['t22'], 0)} of {c['name']} voted in the 2022 midterm. How many people are you voting for?"

    h1 = f"{c['name']} voter turnout" if not c["statewide"] else "Alaska voter turnout"
    place_in = c["long"]

    paras = [
        f"In the November 2022 midterm, {num(c['v22'])} of {c['name']}&rsquo;s {num(c['cvap'])} eligible citizens voted: "
        f"<strong>{pct(c['t22'])} turnout</strong>. That&rsquo;s {comparison(c['t22'], st_tot['t22'])} {e(c['state'])} overall "
        f"({pct(st_tot['t22'])}) and {comparison(c['t22'], nat['t22'])} the national rate ({pct(nat['t22'])}). "
        f"With {num(nonvoters)} eligible citizens sitting it out, each ballot cast spoke for <strong>{c['vp22']:.1f} people</strong>.",
        f"In the 2024 presidential election, turnout was {pct(c['t24'])}, so each ballot spoke for {c['vp24']:.1f} people. "
        f"Midterm turnout here ran {abs(c['t24'] - c['t22']):.1f} points {'below' if c['t22'] < c['t24'] else 'above'} the presidential year, "
        f"which is why every vote in a midterm like 2026 carries extra weight.",
    ]
    if not c["statewide"] and n > 1:
        paras.append(f"{e(c['name'])} ranks <strong>#{rank} of {n}</strong> counties in {e(c['state'])} for vote power "
                     f"(#1 has the lowest turnout, so each vote there counts for the most people).")

    stats = [
        ("2022 midterm turnout", pct(c["t22"]), f"{c['vp22']:.1f} people per vote"),
        ("2024 presidential turnout", pct(c["t24"]), f"{c['vp24']:.1f} people per vote"),
        ("Eligible citizens", num(c["cvap"]), "citizens 18+"),
        ("Didn&rsquo;t vote in 2022", num(nonvoters), "eligible citizens"),
    ]
    if not c["statewide"] and n > 1:
        stats.append((f"Rank in {e(c['state'])}", f"#{rank} of {n}", "for vote power"))
    stat_html = "".join(f'<div class="stat"><div class="k">{k}</div><div class="v">{v}</div><div class="d">{d}</div></div>'
                        for k, v, d in stats)

    notes = "".join(f'<p class="note">{NOTES[x]}</p>' for x in c["notes"] if x in NOTES)

    similar = ""
    if not c["statewide"] and n > 1:
        i = rank - 1
        window = ranked[max(0, i - 3): i + 4]
        rows = "".join(
            f'<tr{" class=\"me\"" if x is c else ""}><td>'
            + (f'{e(x["raw_name"])}' if x is c else f'<a href="/c/{x["fips"]}/">{e(x["raw_name"])}</a>')
            + f'</td><td>#{ranked.index(x) + 1}</td><td>{pct(x["t22"])}</td><td class="vp">{x["vp22"]:.1f}</td></tr>'
            for x in window)
        similar = f"""<div class="table-wrap"><table>
<caption>Counties near {e(c['name'])} in the {e(c['state'])} ranking (2022 midterm)</caption>
<thead><tr><th scope="col">County</th><th scope="col">Rank</th><th scope="col">Turnout</th><th scope="col">Per vote</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p><a href="/state/{state_slug}/">See all {n} {e(c['state'])} counties ranked &rarr;</a></p>"""

    crumb_items = [("Home", "/"), (c["state"], f"/state/{state_slug}/")]
    if not c["statewide"] and n > 1:
        crumb_items.append((c["raw_name"], None))
    nav, ld = crumbs(crumb_items)

    body = f"""{nav}
<h1>{e(h1)}</h1>
<p class="lede">How many people does one vote speak for in {e(place_in)}?</p>
<section class="card" aria-label="Vote power in {e(place_in)}">
<span class="lead">Each vote here counts for</span>
<span class="num">{c['vp22']:.1f}</span>
<span class="unit">people</span>
<p>{only}{pct(c['t22'], 0)} of eligible citizens in {e(c['name'])} voted in the 2022 midterm.</p>
<p class="sub">2024 presidential: {pct(c['t24'], 0)} turnout &middot; {c['vp24']:.1f} people per vote</p>
</section>
{notes}
<div class="ctas">
<a class="btn primary" href="/?c={fips}">This is my county &mdash; share my number</a>
<a class="btn" href="/">Check another county</a>
</div>
<section class="stats" aria-label="Turnout statistics">{stat_html}</section>
<section class="panel">
<h2>Turnout in {e(c['name'])}</h2>
{''.join(f'<p>{p}</p>' for p in paras)}
<p><a href="https://www.vote.org" rel="noopener">Election Day is Tuesday, November 3, 2026 &mdash; register or check your status at vote.org</a>.</p>
</section>
{similar}
{SOURCES}"""
    return page(title, desc, f"{SITE}/c/{fips}/", body, og_title=og_title, og_desc=og_desc,
                og_image=f"{SITE}/og/{fips}.png",
                og_alt=f"Sticker reading {lead_social} {c['vp22']:.1f} people, {c['label']}",
                jsonld=[ld])


SORT_JS = """<script>
document.querySelectorAll('th button[data-col]').forEach(function(b){b.addEventListener('click',function(){
var t=b.closest('table'),tb=t.tBodies[0],i=+b.dataset.col,num=b.dataset.type==='n',asc=b.dataset.dir!=='asc';
t.querySelectorAll('th button').forEach(function(x){x.removeAttribute('data-dir');x.closest('th').removeAttribute('aria-sort');});
b.dataset.dir=asc?'asc':'desc';b.closest('th').setAttribute('aria-sort',asc?'ascending':'descending');
Array.from(tb.rows).sort(function(a,c){var x=a.cells[i].dataset.v||a.cells[i].textContent,y=c.cells[i].dataset.v||c.cells[i].textContent;
if(num){x=parseFloat(x);y=parseFloat(y);}return (x>y?1:x<y?-1:0)*(asc?1:-1);}).forEach(function(r){tb.appendChild(r);});});});
</script>"""


def state_page(st, counties, st_tot, nat, all_states):
    name = STATE_NAMES[st]
    s = slug(name)
    ranked = sorted(counties, key=lambda x: (-x["vp22"], x["t22"]))
    single = len(ranked) == 1
    title = f"{name} Voter Turnout by County (2022 & 2024) | votepower"
    desc = (f"{name} voter turnout by county: {pct(st_tot['t22'])} statewide in the 2022 midterm and {pct(st_tot['t24'])} in 2024. "
            f"See how many people each vote counts for in every {name} county.")
    if single:
        desc = (f"{name} voter turnout: {pct(st_tot['t22'])} in the 2022 midterm and {pct(st_tot['t24'])} in 2024. "
                "See how many people each vote counts for.")
    top, bottom = ranked[0], ranked[-1]
    nav, ld = crumbs([("Home", "/"), ("States", "/state/"), (name, None)])

    intro = (f"In the 2022 midterm, {num(st_tot['v22'])} of {name}&rsquo;s {num(st_tot['cvap'])} eligible citizens voted "
             f"(<strong>{pct(st_tot['t22'])}</strong>), so each ballot spoke for <strong>{st_tot['vp22']:.1f} people</strong>. "
             f"In 2024, turnout was {pct(st_tot['t24'])} ({st_tot['vp24']:.1f} people per vote). Nationally, 2022 turnout was {pct(nat['t22'])}.")
    if not single:
        intro += (f" Vote power is highest in <a href=\"/c/{top['fips']}/\">{e(top['raw_name'])}</a> "
                  f"({top['vp22']:.1f} people per vote) and lowest in <a href=\"/c/{bottom['fips']}/\">{e(bottom['raw_name'])}</a> "
                  f"({bottom['vp22']:.1f}).")

    rows = "".join(
        f'<tr><td><a href="/c/{c["fips"]}/">{e(c["name"] if not c["statewide"] else name + " (statewide)")}</a></td>'
        f'<td data-v="{i + 1}">#{i + 1}</td>'
        f'<td class="vp" data-v="{c["vp22"]}">{c["vp22"]:.1f}</td><td data-v="{c["t22"]}">{pct(c["t22"])}</td>'
        f'<td data-v="{c["vp24"]}">{c["vp24"]:.1f}</td><td data-v="{c["t24"]}">{pct(c["t24"])}</td></tr>'
        for i, c in enumerate(ranked))
    table = f"""<div class="table-wrap"><table>
<caption>{e(name)} counties ranked by vote power (2022 midterm)</caption>
<thead><tr>
<th scope="col"><button type="button" data-col="0" data-type="s">County</button></th>
<th scope="col" aria-sort="ascending"><button type="button" data-col="1" data-type="n">Rank</button></th>
<th scope="col"><button type="button" data-col="2" data-type="n">Per vote &rsquo;22</button></th>
<th scope="col"><button type="button" data-col="3" data-type="n">Turnout &rsquo;22</button></th>
<th scope="col"><button type="button" data-col="4" data-type="n">Per vote &rsquo;24</button></th>
<th scope="col"><button type="button" data-col="5" data-type="n">Turnout &rsquo;24</button></th>
</tr></thead>
<tbody>{rows}</tbody></table></div>"""

    others = "".join(f'<li><a href="/state/{slug(STATE_NAMES[o])}/">{e(STATE_NAMES[o])}</a></li>'
                     for o in all_states if o != st)
    body = f"""{nav}
<h1>{e(name)} voter turnout by county</h1>
<section class="card" aria-label="{e(name)} vote power">
<span class="lead">Each vote in {e(name)} counts for</span>
<span class="num">{st_tot['vp22']:.1f}</span>
<span class="unit">people</span>
<p>{pct(st_tot['t22'], 0)} of eligible {e(name)} citizens voted in the 2022 midterm.</p>
</section>
<section class="panel"><p>{intro}</p>
<p><a href="https://www.vote.org" rel="noopener">Election Day is Tuesday, November 3, 2026 &mdash; register or check your status at vote.org</a>.</p></section>
<div class="ctas"><a class="btn primary" href="/">Find your county&rsquo;s number</a></div>
{table}
<section class="panel"><h2>Other states</h2><ul class="states">{others}</ul></section>
{SOURCES}
{SORT_JS}"""
    return page(title, desc, f"{SITE}/state/{s}/", body,
                og_title=f"How many people are you voting for in {name}?",
                og_desc=f"Only {pct(st_tot['t22'], 0)} of {name} voted in the 2022 midterm. Find your county's number.",
                jsonld=[ld])


def states_index(states, totals, nat):
    ranked = sorted(states, key=lambda s: totals[s]["t22"])
    rows = "".join(
        f'<tr><td><a href="/state/{slug(STATE_NAMES[s])}/">{e(STATE_NAMES[s])}</a></td>'
        f'<td data-v="{i + 1}">#{i + 1}</td>'
        f'<td class="vp" data-v="{totals[s]["vp22"]:.3f}">{totals[s]["vp22"]:.1f}</td><td data-v="{totals[s]["t22"]:.3f}">{pct(totals[s]["t22"])}</td>'
        f'<td data-v="{totals[s]["vp24"]:.3f}">{totals[s]["vp24"]:.1f}</td><td data-v="{totals[s]["t24"]:.3f}">{pct(totals[s]["t24"])}</td></tr>'
        for i, s in enumerate(ranked))
    nav, ld = crumbs([("Home", "/"), ("States", None)])
    body = f"""{nav}
<h1>Voter turnout by state, 2022 &amp; 2024</h1>
<section class="panel"><p>Nationally, {pct(nat['t22'])} of eligible citizens voted in the 2022 midterm and {pct(nat['t24'])} in the 2024 presidential election.
In a low-turnout state, each ballot speaks for more people. Pick a state to see every county ranked.</p></section>
<div class="table-wrap"><table>
<caption>States ranked by vote power (2022 midterm)</caption>
<thead><tr>
<th scope="col"><button type="button" data-col="0" data-type="s">State</button></th>
<th scope="col" aria-sort="ascending"><button type="button" data-col="1" data-type="n">Rank</button></th>
<th scope="col"><button type="button" data-col="2" data-type="n">Per vote &rsquo;22</button></th>
<th scope="col"><button type="button" data-col="3" data-type="n">Turnout &rsquo;22</button></th>
<th scope="col"><button type="button" data-col="4" data-type="n">Per vote &rsquo;24</button></th>
<th scope="col"><button type="button" data-col="5" data-type="n">Turnout &rsquo;24</button></th>
</tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="ctas"><a class="btn primary" href="/">Find your county&rsquo;s number</a></div>
<p class="sources">State figures are the sum of county totals: 2022 uses each county&rsquo;s highest statewide or U.S. House vote total, so they can differ slightly from official statewide turnout.</p>
{SOURCES}
{SORT_JS}"""
    return page("Voter Turnout by State, 2022 Midterm & 2024 | votepower",
                f"Voter turnout by state: {pct(nat['t22'])} nationally in the 2022 midterm and {pct(nat['t24'])} in 2024. "
                "See how many people each vote counts for in every state and county.",
                f"{SITE}/state/", body, jsonld=[ld])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", action="store_true")
    args = ap.parse_args()
    lead_social = "My vote counts for" if args.after else "I'm voting for"

    counties = load()
    by_state = defaultdict(list)
    for c in counties:
        by_state[c["st"]].append(c)
    totals = {s: state_totals(v) for s, v in by_state.items()}
    nat = state_totals(counties)
    states = sorted(by_state, key=lambda s: STATE_NAMES[s])

    for c in counties:
        os.makedirs(f"c/{c['fips']}", exist_ok=True)
        with open(f"c/{c['fips']}/index.html", "w") as f:
            f.write(county_page(c, by_state[c["st"]], totals[c["st"]], nat, lead_social))
    for s in states:
        d = f"state/{slug(STATE_NAMES[s])}"
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/index.html", "w") as f:
            f.write(state_page(s, by_state[s], totals[s], nat, states))
    with open("state/index.html", "w") as f:
        f.write(states_index(states, totals, nat))

    # Homepage "Voter turnout by state" links (between markers in index.html).
    links = "".join(f'<li><a href="/state/{slug(STATE_NAMES[s])}/">{e(STATE_NAMES[s])}</a></li>' for s in states)
    home = open("index.html").read()
    start, end = "<!--STATES:START-->", "<!--STATES:END-->"
    i, j = home.index(start) + len(start), home.index(end)
    home = home[:i] + f'\n            <ul class="states">{links}</ul>\n            ' + home[j:]
    with open("index.html", "w") as f:
        f.write(home)

    today = datetime.date.today().isoformat()
    urls = [(f"{SITE}/", "1.0"), (f"{SITE}/state/", "0.8")]
    urls += [(f"{SITE}/state/{slug(STATE_NAMES[s])}/", "0.8") for s in states]
    urls += [(f"{SITE}/c/{c['fips']}/", "0.6") for c in sorted(counties, key=lambda c: c["fips"])]
    with open("sitemap.xml", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u, p in urls:
            f.write(f"<url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{p}</priority></url>\n")
        f.write("</urlset>\n")
    with open("robots.txt", "w") as f:
        f.write(f"User-agent: *\nAllow: /\nDisallow: /scripts/\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"Wrote {len(counties)} county pages, {len(states)} state pages, state index, sitemap ({len(urls)} URLs)")
    print(f"National 2022 turnout {nat['t22']:.1f}%, 2024 {nat['t24']:.1f}%")


if __name__ == "__main__":
    main()
