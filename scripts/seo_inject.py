#!/usr/bin/env python3
"""Inietta SEO meta tags (title, description, OG, Twitter, canonical, JSON-LD) in tutte le pagine statiche."""

import os
import re
import json

ROOT = "/Users/andrea/Projects/Sito Paola"
SITE_URL = "https://paola-maccioni.netlify.app"  # cambierà a paolamaccioni.com dopo collegamento

# Per ogni pagina statica: title, description, og_image relativa, schema_type
PAGES = {
    "index.html": {
        "title": "Paola Maccioni — Scultura contemporanea in alluminio | PIEMME",
        "description": "Paola Maccioni, scultrice contemporanea. Opere d'arte uniche in alluminio lavorato a sbalzo. Brand PIEMME. «Il gesto non aggiunge materia: la spinge dall'interno.»",
        "keywords": "paola maccioni, piemme, scultura alluminio, sbalzo, arte contemporanea, scultrice italiana, opere uniche, scultura veneto",
        "og_image": "/images/home-incide.jpg",
        "path": "/",
        "schema_type": "Person",
    },
    "bio.html": {
        "title": "Chi sono — Paola Maccioni | Biografia",
        "description": "Paola Maccioni (Cagliari, 1980) vive e lavora in Veneto. Artista autodidatta, dal 2019 concentra la ricerca sull'alluminio lavorato a sbalzo con bulini a punta tonda.",
        "keywords": "paola maccioni biografia, scultrice cagliari, artista veneto, sbalzo alluminio, bulino punta tonda, scultura contemporanea italiana",
        "og_image": "/images/home-opera.jpg",
        "path": "/bio.html",
        "schema_type": "Person",
    },
    "portfolio.html": {
        "title": "Portfolio — Paola Maccioni | Opere in alluminio",
        "description": "Opere d'arte contemporanea in alluminio. Due serie di ricerca: Materia e Trasformazione (2022–2024) e Forme Organiche (2021–2023). 49 lavori unici a sbalzo.",
        "keywords": "portfolio paola maccioni, opere alluminio, materia trasformazione, forme organiche, sculture sbalzo, arte italiana contemporanea",
        "og_image": "/struttura-tensione/lombra-della-luce/01.jpg",
        "path": "/portfolio.html",
        "schema_type": "ImageGallery",
    },
    "commissioni.html": {
        "title": "Commissioni — Paola Maccioni | Opere su commissione personalizzate",
        "description": "Opere d'arte su commissione realizzate a mano in alluminio a sbalzo. Progetti unici sviluppati in dialogo con il collezionista. Processo in 4 fasi: contatto, progetto, realizzazione, consegna.",
        "keywords": "commissioni arte, opere personalizzate, scultura su commissione, paola maccioni commissioni, opera unica alluminio, arte collezionista",
        "og_image": "/images/home-opera.jpg",
        "path": "/commissioni.html",
        "schema_type": "Service",
    },
    "contatti.html": {
        "title": "Contatti — Paola Maccioni",
        "description": "Contatta Paola Maccioni per informazioni, commissioni o acquisto opere. Email: infopiemmeart@gmail.com — Instagram @piemmeart_ — Telegram @piemmecrafts.",
        "keywords": "paola maccioni contatti, piemme contatti, infopiemmeart, contattare scultrice, acquisto opere",
        "og_image": "/images/home-incide.jpg",
        "path": "/contatti.html",
        "schema_type": "ContactPage",
    },
}

# JSON-LD persona base (riutilizzata su tutte le pagine bio/home)
PERSON_JSONLD = {
    "@context": "https://schema.org",
    "@type": "Person",
    "name": "Paola Maccioni",
    "alternateName": "PIEMME",
    "jobTitle": "Scultrice contemporanea",
    "birthPlace": {"@type": "Place", "name": "Cagliari, Italia"},
    "birthDate": "1980",
    "workLocation": {"@type": "Place", "name": "Veneto, Italia"},
    "url": SITE_URL + "/",
    "sameAs": [
        "https://instagram.com/piemmeart_",
        "https://t.me/piemmecrafts",
    ],
    "email": "infopiemmeart@gmail.com",
    "description": "Artista autodidatta, dal 2019 concentra la ricerca sull'alluminio lavorato a sbalzo con bulini a punta tonda. Sviluppa un processo di sbalzo in negativo basato su pressione controllata.",
    "knowsAbout": ["Scultura", "Sbalzo dell'alluminio", "Arte contemporanea"],
}

WEBSITE_JSONLD = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Paola Maccioni — PIEMME",
    "url": SITE_URL + "/",
    "author": {"@type": "Person", "name": "Paola Maccioni"},
    "inLanguage": "it-IT",
}

def build_seo_block(page_key, meta):
    """Genera blocco <head> SEO completo per una pagina."""
    canonical = SITE_URL + meta["path"]
    og_image_url = SITE_URL + meta["og_image"]

    jsonld_list = [WEBSITE_JSONLD]
    if page_key in ("index.html", "bio.html"):
        jsonld_list.append(PERSON_JSONLD)

    jsonld_scripts = "\n".join(
        f'  <script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>'
        for j in jsonld_list
    )

    return f"""  <title>{meta['title']}</title>
  <meta name="description" content="{meta['description']}">
  <meta name="keywords" content="{meta['keywords']}">
  <meta name="author" content="Paola Maccioni">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{canonical}">

  <!-- Open Graph -->
  <meta property="og:type" content="website">
  <meta property="og:locale" content="it_IT">
  <meta property="og:site_name" content="Paola Maccioni — PIEMME">
  <meta property="og:title" content="{meta['title']}">
  <meta property="og:description" content="{meta['description']}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image_url}">
  <meta property="og:image:alt" content="Paola Maccioni — Scultura contemporanea in alluminio">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{meta['title']}">
  <meta name="twitter:description" content="{meta['description']}">
  <meta name="twitter:image" content="{og_image_url}">

  <!-- Favicon -->
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <!-- Structured Data -->
{jsonld_scripts}"""

def inject_into_page(filepath, seo_block):
    """Sostituisce title + description nella pagina esistente con il blocco SEO completo."""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Rimuovi vecchi tag SEO se presenti
    patterns = [
        r'\s*<title>[^<]*</title>',
        r'\s*<meta\s+name="description"[^>]*>',
        r'\s*<meta\s+name="keywords"[^>]*>',
        r'\s*<meta\s+name="author"[^>]*>',
        r'\s*<meta\s+name="robots"[^>]*>',
        r'\s*<link\s+rel="canonical"[^>]*>',
        r'\s*<meta\s+property="og:[^"]+"[^>]*>',
        r'\s*<meta\s+name="twitter:[^"]+"[^>]*>',
        r'\s*<link\s+rel="icon"[^>]*>',
        r'\s*<link\s+rel="apple-touch-icon"[^>]*>',
        r'\s*<script\s+type="application/ld\+json">[\s\S]*?</script>',
        # rimuovi anche meta no-cache obsoleti (Netlify gestisce via toml)
        r'\s*<meta\s+http-equiv="Cache-Control"[^>]*>',
        r'\s*<meta\s+http-equiv="Pragma"[^>]*>',
        r'\s*<meta\s+http-equiv="Expires"[^>]*>',
    ]
    for p in patterns:
        html = re.sub(p, '', html, flags=re.I)

    # Inserisci blocco SEO subito prima del <link rel="stylesheet">
    new_html = re.sub(
        r'(\s*<link\s+rel="stylesheet")',
        '\n' + seo_block + r'\1',
        html, count=1
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_html)

def main():
    for page, meta in PAGES.items():
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            print(f"SKIP {page} (not found)")
            continue
        seo = build_seo_block(page, meta)
        inject_into_page(path, seo)
        print(f"✓ {page}")

if __name__ == "__main__":
    main()
