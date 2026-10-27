#!/usr/bin/env python3
"""Notify IndexNow search engines (Bing, Yandex, Seznam, Naver; Bing feeds
DuckDuckGo, Yahoo and others) of every URL in sitemap.xml.

The key file <key>.txt must be served at the site root. Runs from the
IndexNow GitHub Action after each push that changes sitemap.xml.
"""
import glob
import json
import os
import re
import sys
import urllib.request

HOST = "votepower.us"
keys = [os.path.basename(p)[:-4] for p in glob.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}\.txt", os.path.basename(p))]
if len(keys) != 1:
    sys.exit(f"Expected exactly one IndexNow key file, found {keys}")
key = keys[0]
urls = re.findall(r"<loc>(.*?)</loc>", open("sitemap.xml").read())
body = json.dumps({"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt", "urlList": urls[:10000]}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                             headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
with urllib.request.urlopen(req, timeout=60) as r:
    print(f"IndexNow: submitted {len(urls)} URLs, HTTP {r.status}")
