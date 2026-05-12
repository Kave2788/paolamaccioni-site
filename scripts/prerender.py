#!/usr/bin/env python3
"""Pre-render pagine statiche /serie/<slug>/ e /opera/<slug>/ con SEO completo."""

import json
import os
import re
import shutil
from html import escape

ROOT = "/Users/andrea/Projects/Sito Paola"
SITE_URL = "https://paola-maccioni.netlify.app"
DATA = json.load(open(f"{ROOT}/data/series.json"))


def first_paragraph(text, max_len=200):
    """Estrae primo paragrafo da descrizione opera, max max_len chars."""
    if not text: return ""
    p = text.split("\n")[0].strip()
    if len(p) > max_len:
        p = p[:max_len].rsplit(" ", 1)[0] + "…"
    return p


def render_serie(serie):
    """HTML statico pagina serie con tutte le opere pre-renderizzate."""
    canonical = f"{SITE_URL}/serie/{serie['id']}/"
    cover_img = serie['works'][0].get('image', '') if serie['works'] else ''
    og_image = f"{SITE_URL}/{cover_img}" if cover_img else f"{SITE_URL}/images/home-incide.jpg"
    title = f"{serie['name']} ({serie['year']}) — Paola Maccioni"
    desc = serie['description']

    # JSON-LD ImageGallery
    jsonld = {
        "@context": "https://schema.org",
        "@type": "ImageGallery",
        "name": serie['name'],
        "description": serie['description'],
        "url": canonical,
        "author": {"@type": "Person", "name": "Paola Maccioni"},
        "image": [
            {
                "@type": "ImageObject",
                "name": w['title'],
                "contentUrl": f"{SITE_URL}/{w['image']}",
                "url": f"{SITE_URL}/opera/{w['id']}/",
            }
            for w in serie['works'] if w.get('image')
        ],
    }

    # Render works grid (anche server-side per SEO/no-JS users)
    works_html = "\n".join(
        f"""      <a class="work-tile" href="/opera/{w['id']}/">
        <div class="work-tile-img">
          <img src="/{w.get('thumb') or w.get('image','')}" alt="{escape(w['title'])}" loading="lazy">
        </div>
        <div class="work-tile-body">
          <p class="label">{escape(str(w.get('year') or ''))}</p>
          <h3>{escape(w['title'])}</h3>
        </div>
      </a>"""
        for w in serie['works']
    )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(desc)}">
  <meta name="keywords" content="{serie['name'].lower()}, paola maccioni, sculture alluminio, sbalzo, arte contemporanea italiana">
  <meta name="author" content="Paola Maccioni">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{canonical}">

  <meta property="og:type" content="website">
  <meta property="og:locale" content="it_IT">
  <meta property="og:site_name" content="Paola Maccioni — PIEMME">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(desc)}">
  <meta name="twitter:image" content="{og_image}">

  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
  <link rel="stylesheet" href="/css/main.css">
</head>
<body>

<nav>
  <div class="inner">
    <button class="nav-toggle" aria-label="Menu"><span></span><span></span><span></span></button>
    <ul>
      <li><a href="/index.html">Home</a></li>
      <li><a href="/bio.html">Biografia</a></li>
      <li><a href="/portfolio.html">Portfolio</a></li>
      <li><a href="/commissioni.html">Commissioni</a></li>
      <li><a href="/contatti.html">Contatti</a></li>
    </ul>
  </div>
</nav>

<section class="page-section serie-section">
  <div class="serie-wrap container">

    <header class="serie-header">
      <a href="/portfolio.html" class="back-link">← Portfolio</a>
      <p class="label">{escape(serie['year'])}</p>
      <h1>{escape(serie['name'])}</h1>
      <div class="rule"></div>
      <p class="serie-tagline">{escape(serie['description'])}</p>
    </header>

    <div class="serie-works">
{works_html}
    </div>

  </div>
</section>

<div class="legal-bar">© 2023 PIEMME di Paola Maccioni | C.F MCCPLA80R64B354E | <a href="mailto:infopiemmeart@gmail.com">infopiemmeart@gmail.com</a> | <a href="/privacy.html">Privacy</a> | <a href="/cookie-policy.html">Cookie</a> | <a href="#" data-cookie-settings>Gestisci cookie</a> | Tutti i diritti sono riservati</div>

<script src="/js/main.js"></script>
<script src="/js/consent.js"></script>
</body>
</html>
"""


def render_opera(serie, opera):
    """HTML statico singola opera con SEO completo."""
    canonical = f"{SITE_URL}/opera/{opera['id']}/"
    main_image = opera.get('image', '')
    og_image = f"{SITE_URL}/{main_image}" if main_image else f"{SITE_URL}/images/home-incide.jpg"
    title = f"{opera['title']} — Paola Maccioni"
    desc = first_paragraph(opera.get('description', ''))
    serie_url = f"/serie/{serie['id']}/"

    # JSON-LD VisualArtwork
    jsonld = {
        "@context": "https://schema.org",
        "@type": "VisualArtwork",
        "name": opera['title'],
        "description": opera.get('description', ''),
        "creator": {"@type": "Person", "name": "Paola Maccioni"},
        "url": canonical,
        "image": [f"{SITE_URL}/{g}" for g in opera.get('gallery', []) if g],
        "artform": "Scultura",
        "artMedium": "Alluminio lavorato a sbalzo",
        "artworkSurface": "Lastra di alluminio",
        "inLanguage": "it-IT",
    }
    if opera.get('year'):
        jsonld['dateCreated'] = str(opera['year'])

    # Render description con newline → <p>
    desc_html = "".join(
        f"<p>{escape(p.strip())}</p>" for p in opera.get('description', '').split("\n") if p.strip()
    ) or "<p>—</p>"

    # Thumbs strip (server-rendered per SEO)
    gallery = opera.get('gallery', [])
    thumbs = opera.get('thumb_gallery', gallery)
    thumbs_html = "".join(
        f'<button class="opera-thumb" data-i="{i}" data-src="/{g}"><img src="/{thumbs[i] if i < len(thumbs) else g}" alt="{escape(opera["title"])} {i+1}" loading="lazy"></button>'
        for i, g in enumerate(gallery)
    )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(desc)}">
  <meta name="keywords" content="{escape(opera['title'].lower())}, paola maccioni, {serie['name'].lower()}, scultura alluminio sbalzo">
  <meta name="author" content="Paola Maccioni">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{canonical}">

  <meta property="og:type" content="article">
  <meta property="og:locale" content="it_IT">
  <meta property="og:site_name" content="Paola Maccioni — PIEMME">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta property="article:author" content="Paola Maccioni">
  <meta property="article:section" content="{escape(serie['name'])}">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(desc)}">
  <meta name="twitter:image" content="{og_image}">

  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
  <link rel="stylesheet" href="/css/main.css">
</head>
<body>

<nav>
  <div class="inner">
    <button class="nav-toggle" aria-label="Menu"><span></span><span></span><span></span></button>
    <ul>
      <li><a href="/index.html">Home</a></li>
      <li><a href="/bio.html">Biografia</a></li>
      <li><a href="/portfolio.html">Portfolio</a></li>
      <li><a href="/commissioni.html">Commissioni</a></li>
      <li><a href="/contatti.html">Contatti</a></li>
    </ul>
  </div>
</nav>

<section class="page-section opera-section">
  <div class="opera-wrap container">

    <a href="{serie_url}" class="back-link">← {escape(serie['name'])}</a>

    <div class="opera-grid">
      <div class="opera-img-wrap">
        <img id="opera-img" src="/{main_image}" alt="{escape(opera['title'])}">
        <button class="opera-nav prev" id="prev-img" aria-label="Precedente">‹</button>
        <button class="opera-nav next" id="next-img" aria-label="Successiva">›</button>
        <span class="opera-counter" id="opera-counter">1 / {len(gallery)}</span>
      </div>
      <div class="opera-info">
        <p class="label">{escape(str(opera.get('year') or ''))}</p>
        <h1>{escape(opera['title'])}</h1>
        <div class="rule"></div>
        {desc_html}
        <p class="label opera-serie-label">Dalla serie {escape(serie['name'])}</p>
      </div>
    </div>

    <div class="opera-thumbs" id="opera-thumbs">{thumbs_html}</div>

  </div>
</section>

<div class="legal-bar">© 2023 PIEMME di Paola Maccioni | C.F MCCPLA80R64B354E | <a href="mailto:infopiemmeart@gmail.com">infopiemmeart@gmail.com</a> | <a href="/privacy.html">Privacy</a> | <a href="/cookie-policy.html">Cookie</a> | <a href="#" data-cookie-settings>Gestisci cookie</a> | Tutti i diritti sono riservati</div>

<script src="/js/main.js"></script>
<script>
// Gallery navigation client-side (arricchisce pre-rendered HTML)
(() => {{
  const gallery = {json.dumps(gallery)};
  const thumbs = document.querySelectorAll('.opera-thumb');
  const mainImg = document.getElementById('opera-img');
  const counter = document.getElementById('opera-counter');
  let current = 0;

  function preload(i) {{
    [i-1, i+1].forEach(k => {{
      const idx = (k + gallery.length) % gallery.length;
      const im = new Image();
      im.src = '/' + gallery[idx];
    }});
  }}

  function show(i) {{
    current = (i + gallery.length) % gallery.length;
    mainImg.src = '/' + gallery[current];
    mainImg.alt = {json.dumps(opera['title'])} + ' ' + (current+1);
    counter.textContent = (current+1) + ' / ' + gallery.length;
    thumbs.forEach((t, idx) => t.classList.toggle('active', idx === current));
    preload(current);
  }}

  if (gallery.length > 1) {{
    thumbs.forEach(t => t.addEventListener('click', () => show(parseInt(t.dataset.i))));
    document.getElementById('prev-img').addEventListener('click', () => show(current - 1));
    document.getElementById('next-img').addEventListener('click', () => show(current + 1));
    document.addEventListener('keydown', e => {{
      if (e.key === 'ArrowLeft') show(current - 1);
      if (e.key === 'ArrowRight') show(current + 1);
    }});
    thumbs[0]?.classList.add('active');
    preload(0);
  }} else {{
    document.getElementById('prev-img').style.display = 'none';
    document.getElementById('next-img').style.display = 'none';
    counter.style.display = 'none';
  }}
}})();
</script>
</body>
</html>
"""


def main():
    out_serie = os.path.join(ROOT, "serie")
    out_opera = os.path.join(ROOT, "opera")

    # Pulisci output precedente
    if os.path.exists(out_serie): shutil.rmtree(out_serie)
    if os.path.exists(out_opera): shutil.rmtree(out_opera)

    n_serie = n_opera = 0
    for serie in DATA["series"]:
        # /serie/<id>/index.html
        d = os.path.join(out_serie, serie["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_serie(serie))
        n_serie += 1

        for opera in serie["works"]:
            d = os.path.join(out_opera, opera["id"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
                f.write(render_opera(serie, opera))
            n_opera += 1

    print(f"✓ {n_serie} pagine serie + {n_opera} pagine opera pre-renderizzate")


if __name__ == "__main__":
    main()
