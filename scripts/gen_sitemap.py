#!/usr/bin/env python3
"""Genera sitemap.xml + robots.txt + _redirects Netlify."""

import json
import os
from datetime import date

ROOT = "/Users/andrea/Projects/Sito Paola"
SITE_URL = "https://paola-maccioni.netlify.app"
TODAY = date.today().isoformat()

PAGES_LEGAL = [
    ("/privacy.html", "0.3", "yearly"),
    ("/cookie-policy.html", "0.3", "yearly"),
]
PAGES = [
    ("/", "1.0", "weekly"),
    ("/bio.html", "0.9", "monthly"),
    ("/portfolio.html", "0.9", "weekly"),
    ("/commissioni.html", "0.7", "monthly"),
    ("/contatti.html", "0.6", "yearly"),
]

def main():
    d = json.load(open(f"{ROOT}/data/series.json"))

    urls = []
    for path, priority, freq in PAGES:
        urls.append((SITE_URL + path, TODAY, freq, priority))
    for path, priority, freq in PAGES_LEGAL:
        urls.append((SITE_URL + path, TODAY, freq, priority))

    for s in d["series"]:
        urls.append((f"{SITE_URL}/serie/{s['id']}/", TODAY, "weekly", "0.8"))
        for w in s["works"]:
            urls.append((f"{SITE_URL}/opera/{w['id']}/", TODAY, "monthly", "0.7"))

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u, lastmod, freq, prio in urls:
        xml += f"  <url>\n"
        xml += f"    <loc>{u}</loc>\n"
        xml += f"    <lastmod>{lastmod}</lastmod>\n"
        xml += f"    <changefreq>{freq}</changefreq>\n"
        xml += f"    <priority>{prio}</priority>\n"
        xml += f"  </url>\n"
    xml += "</urlset>\n"

    with open(f"{ROOT}/sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml)

    robots = f"""User-agent: *
Allow: /
Disallow: /admin.html
Disallow: /admin.py
Disallow: /scripts/

Sitemap: {SITE_URL}/sitemap.xml
"""
    with open(f"{ROOT}/robots.txt", "w", encoding="utf-8") as f:
        f.write(robots)

    # Redirect Netlify: vecchi URL ?id= → nuovi pretty URL
    redirects = """# Redirect legacy URLs to pretty SEO URLs
/serie.html  /serie/:id/  302  id=:id
/opera.html  /opera/:id/  302  id=:id

# Trailing slash normalization
/serie/*/   /serie/:splat/  200
/opera/*/   /opera/:splat/  200
"""
    with open(f"{ROOT}/_redirects", "w", encoding="utf-8") as f:
        f.write(redirects)

    print(f"✓ sitemap.xml ({len(urls)} URL)")
    print(f"✓ robots.txt")
    print(f"✓ _redirects")

if __name__ == "__main__":
    main()
