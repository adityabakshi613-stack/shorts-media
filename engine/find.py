#!/usr/bin/env python3
"""python3 find.py "query" [n] -> Commons file titles (bitmap, >=1000px) for spec 'commons:' sources."""
import sys, json, urllib.request, urllib.parse
q = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
u = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=20"
     "&prop=imageinfo&iiprop=size|mime&gsrsearch=" + urllib.parse.quote(q))
import time
for i in range(6):
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "WealthExtremeShorts/1.0 (https://www.instagram.com/wealth.extreme/)"}), timeout=40)); break
    except Exception:
        if i == 5: raise
        time.sleep(4 * (i + 1))
k = 0
for p in sorted(d.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
    ii = p.get("imageinfo", [{}])[0]
    if ii.get("mime") in ("image/jpeg", "image/png", "image/svg+xml") and (ii.get("width", 0) >= 900 or ii.get("mime") == "image/svg+xml"):
        print(p["title"][5:], f'{ii.get("width")}x{ii.get("height")}'); k += 1
        if k >= n: break
