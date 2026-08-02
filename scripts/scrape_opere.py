#!/usr/bin/env python3
"""Scrape Wix opera pages, build series.json, download HD images."""

import json
import re
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.parse
from html.parser import HTMLParser

BASE = "https://www.paolamaccioni.com"

# (titolo, slug, serie_id)
OPERE = [
    # ESSENZA -> Materia e Trasformazione
    ("L'ombra della luce", "lombra-della-luce", "struttura-tensione"),
    ("Lux Eterna", "lux-eterna", "struttura-tensione"),
    ("Il Rinoceronte – omaggio a Dürer", "il-rinoceronte", "struttura-tensione"),
    ("Rondini in gabbia", "rondini-in-gabbia", "struttura-tensione"),
    ("Equilibrio fratturato", "equilibrio-fratturato", "struttura-tensione"),
    ("Fibonacci", "fibonacci", "struttura-tensione"),
    ("Sfera", "progetto-senza-titolo-6e3e20", "struttura-tensione"),
    ("Fazzoletto", "progetto-senza-titolo-77d42e", "struttura-tensione"),
    ("Specchio nero", "specchio-nero", "struttura-tensione"),
    ("Cubi", "cubi", "struttura-tensione"),
    ("Bubbles", "bubbles", "struttura-tensione"),
    ("Onde Riflesse", "onde-riflesse", "struttura-tensione"),
    ("Sotto la superficie", "progetto-senza-titolo-a4bc4d", "struttura-tensione"),
    ("Il peso dell'ingiustizia", "progetto-senza-titolo-1a5129", "struttura-tensione"),
    ("Scacco matto", "checkmate", "struttura-tensione"),
    ("Senza catene", "senza-catene", "struttura-tensione"),
    ("Trittico", "trittico", "struttura-tensione"),
    ("Iconica", "lady", "struttura-tensione"),
    ("Pensiero", "pensiero", "struttura-tensione"),
    ("Boes", "my-project-e17e75", "struttura-tensione"),
    ("Ex voto", "titolomarionette-ex-voto", "struttura-tensione"),
    ("Verso l'Orizzonte", "veliero", "struttura-tensione"),
    ("Mare in tempesta", "mare-in-tempesta", "struttura-tensione"),
    ("Oblò", "oblo", "struttura-tensione"),
    ("Paesaggio d'Oriente", "giappone", "struttura-tensione"),
    ("Volo d'Argento", "progetto-senza-titolo-0f5967", "struttura-tensione"),
    ("Nessun Dorma", "nessu-dorma", "struttura-tensione"),
    ("L'unione", "my-project-4d8295", "struttura-tensione"),
    # VITA -> Forme Organiche
    ("Globigerina", "my-project-528a5b", "forma-organica"),
    ("Riccio di mare", "progetto-senza-titolo-f37006", "forma-organica"),
    ("Creatura Abissale", "polipo", "forma-organica"),
    ("Armatura primordiale", "armatura-primordiale", "forma-organica"),
    ("Carapace", "granchio", "forma-organica"),
    ("Autodifesa", "pesce-palla", "forma-organica"),
    ("Sguardo primordiale", "iguana", "forma-organica"),
    ("Dragone", "progetto-senza-titolo-e6dd84", "forma-organica"),
    ("Memoria", "elefante", "forma-organica"),
    ("Zebra", "progetto-senza-titolo", "forma-organica"),
    ("Tartaruga", "tartaruga-c8e51f", "forma-organica"),
    ("Aragosta", "aragosta", "forma-organica"),
    ("Dualità", "carpa-koi", "forma-organica"),
    ("Armonia", "fenicotteri", "forma-organica"),
    ("Trota", "progetto-senza-titolo-2ae9b3", "forma-organica"),
    ("Sentinella tropicale", "tucano", "forma-organica"),
    ("Vedova nera", "vedova-nera", "forma-organica"),
    ("Libellule in amore", "progetto-senza-titolo-a6dbf4", "forma-organica"),
    ("Linee di passaggio", "rondinelle", "forma-organica"),
    ("Sospensione", "rana", "forma-organica"),
    ("Metamorfosi", "farfalla-5ec760", "forma-organica"),
]

URL_TPL = {
    "struttura-tensione": BASE + "/portfolio-collections/essenza/{slug}",
    "forma-organica":     BASE + "/portfolio-collections/vita/{slug}",
}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15"

# --- Estrazione contenuto ---
class TextExtractor(HTMLParser):
    """Estrae tutto il testo visibile."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            t = data.strip()
            if t:
                self.parts.append(t)

def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="ignore")

def extract_wix_images(html):
    """Trova immagini Wix CDN, escludi piccole icon/SVG."""
    urls = re.findall(r'https://static\.wixstatic\.com/media/854adf_[a-f0-9]+~mv2\.[a-z]+', html)
    # dedupe preservando ordine
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def extract_meta_description(html):
    # og:description ha la VERA descrizione opera (non il title-meta)
    m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html, re.I)
    if m: return _html_unescape(m.group(1))
    m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html, re.I)
    return _html_unescape(m.group(1)) if m else ""

def _html_unescape(s):
    import html as _h
    return _h.unescape(s).replace("&#39;", "'").strip()

def extract_jsonld_images(html):
    """Estrae immagini da JSON-LD schema.org, scarta og:image generate dinamicamente (UUID 403)."""
    m = re.search(r'<script type="application/ld\+json">(.+?)</script>', html, re.S)
    if not m: return []
    try:
        data = json.loads(m.group(1))
        imgs = data.get("images") or []
        # Tieni solo URL con prefisso 854adf_ (vere immagini caricate da Paola)
        return [i["url"] for i in imgs if i.get("url") and "854adf_" in i["url"]]
    except Exception:
        return []

def extract_year(text):
    """Cerca anno YYYY tra 1990 e 2030."""
    m = re.search(r'\b(19[89]\d|20[0-2]\d|2030)\b', text)
    return m.group(1) if m else ""

def extract_paragraphs(html):
    """Trova testo lungo nella pagina opera (probabile descrizione)."""
    e = TextExtractor()
    e.feed(html)
    parts = e.parts
    skip_words = {
        "home", "biografia", "portfolio", "commissioni", "contatti", "more",
        "use tab to navigate through the menu items.",
        "passa al contenuto principale", "top of page", "bottom of page",
        "© 2023 piemme", "scopri di più", "torna indietro",
        "informativa sulla privacy", "impostazioni", "rifiuta tutti", "accetta",
        "utilizziamo i cookie",
    }
    long_parts = []
    for p in parts:
        pl = p.lower().strip()
        if any(pl.startswith(s) for s in skip_words):
            continue
        if len(p) > 40 and not p.startswith("©"):
            long_parts.append(p)
    return long_parts

# --- Worker ---
def scrape_opera(opera):
    title, slug, serie_id = opera
    url = URL_TPL[serie_id].format(slug=slug)
    try:
        html = fetch_url(url)
    except Exception as e:
        print(f"[FAIL] {title} -> {e}", file=sys.stderr)
        return None
    desc = extract_meta_description(html)
    jsonld_imgs = extract_jsonld_images(html)
    imgs = jsonld_imgs or extract_wix_images(html)
    main_imgs = [i for i in imgs if "90c07f2c" not in i and "cb3167de" not in i and "11062b" not in i]
    year = extract_year(desc) or extract_year(html[:5000])
    print(f"[OK] {title} | imgs={len(main_imgs)} | desc={len(desc)}c")
    return {
        "title": title,
        "slug": slug,
        "serie_id": serie_id,
        "url": url,
        "year": year,
        "description": desc,
        "images": main_imgs,
    }

# --- Image download ---
def hd_url(base):
    """Se URL già contiene /v1/, usa così. Altrimenti aggiungi HD path."""
    if "/v1/" in base:
        return base
    return base + "/v1/fit/w_1600,h_1600,q_90/file.jpg"

def download_image(url, dest):
    if os.path.exists(dest):
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
        return dest
    except Exception as e:
        print(f"[IMG FAIL] {url}: {e}", file=sys.stderr)
        return None

# --- Main ---
def main():
    project = "/Users/andrea/Projects/Sito Paola"
    img_dir = os.path.join(project, "images/opere")
    data_dir = os.path.join(project, "data")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    print(f"Scraping {len(OPERE)} opere…")
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(scrape_opera, o): o for o in OPERE}
        for fut in as_completed(futures):
            r = fut.result()
            if r:
                results.append(r)

    print(f"\nScaricate {len(results)} pagine. Ora scarico TUTTE le immagini HD…")
    # Cartella dedicata per opera con tutte le sue immagini
    img_tasks = []
    for r in results:
        if not r["images"]: continue
        opera_dir = os.path.join(img_dir, r["slug"])
        os.makedirs(opera_dir, exist_ok=True)
        r["local_images"] = []
        for idx, src in enumerate(r["images"], 1):
            ext = "." + src.rsplit(".", 1)[-1].split("?")[0]
            if ext not in (".jpg", ".jpeg", ".png", ".webp"): ext = ".jpg"
            local = os.path.join(opera_dir, f"{idx:02d}{ext}")
            rel = f"images/opere/{r['slug']}/{idx:02d}{ext}"
            r["local_images"].append(rel)
            img_tasks.append((hd_url(src), local))
        # principale = la prima
        r["local_image"] = r["local_images"][0]

    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(download_image, u, d) for u, d in img_tasks]
        ok = sum(1 for f in as_completed(futs) if f.result())
    print(f"Immagini scaricate: {ok}/{len(img_tasks)}")

    # Costruisci series.json
    series = {
        "struttura-tensione": {
            "id": "struttura-tensione",
            "name": "Materia e Trasformazione",
            "year": "2022–2024",
            "description": "Attraverso lo sbalzo dell'alluminio, la superficie si trasforma in uno spazio tra segno, luce e volume, rivelando la tensione nascosta della materia.",
            "works": []
        },
        "forma-organica": {
            "id": "forma-organica",
            "name": "Forme Organiche",
            "year": "2021–2023",
            "description": "Forme naturali e strutture viventi vengono reinterpretate nell'alluminio attraverso il rilievo, il segno e il movimento della superficie.",
            "works": []
        }
    }

    for r in results:
        sid = r["serie_id"]
        work = {
            "id": r["slug"],
            "title": r["title"],
            "year": r["year"] or "",
            "image": r.get("local_image", ""),
            "gallery": r.get("local_images", []),
            "description": r["description"],
        }
        series[sid]["works"].append(work)

    out = {"series": list(series.values())}
    json_path = os.path.join(data_dir, "series.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nScritto {json_path}")
    print(f"Struttura: {len(series['struttura-tensione']['works'])} opere")
    print(f"Forma org: {len(series['forma-organica']['works'])} opere")

if __name__ == "__main__":
    main()
