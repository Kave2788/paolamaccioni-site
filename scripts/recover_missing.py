#!/usr/bin/env python3
"""Recupera immagini protette 403 via Playwright (browser reale con sessione Wix)."""

import asyncio
import os
from playwright.async_api import async_playwright

ROOT = "/Users/andrea/Projects/Sito Paola"

# (titolo, slug, sub-path, indici immagini mancanti 0-based)
MISSING = [
    ("Vedova nera", "vedova-nera", "vita", [1, 2]),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await ctx.new_page()

        # Visita prima la home per acquisire cookies di sessione Wix
        await page.goto("https://www.paolamaccioni.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        for title, slug, sub, indices in MISSING:
            url = f"https://www.paolamaccioni.com/portfolio-collections/{sub}/{slug}"
            print(f"\n=== {title} ({url}) ===")
            # Cattura tutte le risposte immagine
            captured = {}
            async def on_response(resp):
                u = resp.url
                if "wixstatic.com/media/854adf_" in u and resp.status == 200:
                    ctype = resp.headers.get("content-type", "")
                    if "image" in ctype:
                        try:
                            captured[u] = await resp.body()
                        except Exception:
                            pass
            page.on("response", on_response)

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            # Scrolla per forzare lazy-load
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2500)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(1500)

            page.remove_listener("response", on_response)

            # Ottieni URL JSON-LD attesi
            jsonld_urls = await page.evaluate("""() => {
                const s = document.querySelector('script[type="application/ld+json"]');
                if (!s) return [];
                try {
                    const d = JSON.parse(s.textContent);
                    return (d.images || []).map(i => i.url).filter(u => u.includes('854adf_'));
                } catch(e) { return []; }
            }""")

            print(f"  JSON-LD attesi: {len(jsonld_urls)}")
            print(f"  Catturati live: {len(captured)}")

            # Cerca i missing tra catturate
            opera_dir = os.path.join(ROOT, "images/opere", slug)
            os.makedirs(opera_dir, exist_ok=True)
            for idx in indices:
                if idx >= len(jsonld_urls):
                    print(f"  idx {idx+1}: fuori range")
                    continue
                expected = jsonld_urls[idx]
                # Match per hash base
                base_hash = expected.split("854adf_")[1].split("~")[0]
                match_url = None
                match_body = None
                for u, body in captured.items():
                    if base_hash in u:
                        # Preferisci la versione più grande (più bytes)
                        if match_body is None or len(body) > len(match_body):
                            match_url = u
                            match_body = body
                if match_body:
                    dest = os.path.join(opera_dir, f"{idx+1:02d}.jpg")
                    with open(dest, "wb") as f:
                        f.write(match_body)
                    print(f"  ✓ {idx+1:02d}.jpg recuperato ({len(match_body)} bytes) <- {match_url[:80]}")
                else:
                    print(f"  ✗ {idx+1:02d}.jpg non catturata (hash {base_hash})")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
