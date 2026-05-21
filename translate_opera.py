#!/usr/bin/env python3
"""
Traduce le pagine opera EN leggendo le descrizioni IT originali.
Usa Claude API (claude-haiku-4-5) per velocità e costo ridotto.

Uso:
    export ANTHROPIC_API_KEY=sk-...
    python3 translate_opera.py
"""

import os, re, json, time, urllib.request, urllib.parse
from pathlib import Path

DEEPL_KEY = os.environ.get("DEEPL_API_KEY", "")

def extract_it_data(html: str) -> dict:
    """Estrae titolo, descrizione corpo, meta description e serie dalla pagina IT."""
    # Titolo opera
    title = re.search(r'<h1>([^<]+)</h1>', html)
    title = title.group(1).strip() if title else ""

    # Paragrafi descrizione (dentro opera-info, dopo la rule)
    body_desc = re.search(r'<div class="rule"></div>\s*(.*?)\s*<p class="label opera-serie-label">', html, re.DOTALL)
    body_html = body_desc.group(1).strip() if body_desc else ""
    # Estrai solo il testo dei paragrafi
    paragraphs = re.findall(r'<p>(.*?)</p>', body_html, re.DOTALL)
    body_text = "\n\n".join(p.strip() for p in paragraphs if p.strip())

    # Meta description
    meta = re.search(r'<meta name="description" content="([^"]+)"', html)
    meta_text = meta.group(1) if meta else ""

    # Serie label
    serie_label = re.search(r'<p class="label opera-serie-label">([^<]+)</p>', html)
    serie_text = serie_label.group(1).strip() if serie_label else ""

    # Back link testo
    back = re.search(r'<a href="/serie/[^"]*" class="back-link">← ([^<]+)</a>', html)
    back_text = back.group(1).strip() if back else ""

    # JSON-LD artform, artMedium, artworkSurface
    jld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    jld_data = {}
    if jld:
        try:
            jld_data = json.loads(jld.group(1))
        except:
            pass

    return {
        "title": title,
        "body_text": body_text,
        "meta_text": meta_text,
        "serie_label": serie_text,
        "back_text": back_text,
        "jld_description": jld_data.get("description", ""),
    }

def deepl_translate(text: str) -> str:
    """Traduce un testo IT → EN con DeepL API Free."""
    if not text.strip():
        return text
    url = "https://api-free.deepl.com/v2/translate"
    data = urllib.parse.urlencode({
        "text": text,
        "source_lang": "IT",
        "target_lang": "EN-GB",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"DeepL-Auth-Key {DEEPL_KEY}")
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    return result["translations"][0]["text"]

def translate_with_deepl(it_data: dict, opera_id: str) -> dict:
    """Traduce tutti i campi con DeepL."""
    paragraphs = [p for p in it_data['body_text'].split("\n\n") if p.strip()]
    translated_paragraphs = [deepl_translate(p) for p in paragraphs]

    return {
        "body_paragraphs": translated_paragraphs,
        "meta_description": deepl_translate(it_data['meta_text'])[:160],
        "serie_label": deepl_translate(it_data['serie_label']),
        "back_text": deepl_translate(it_data['back_text']),
        "jld_description": deepl_translate(it_data['jld_description']),
    }

def update_en_page(en_html: str, it_html: str, translated: dict, opera_id: str) -> str:
    """Aggiorna la pagina EN con i testi tradotti."""

    # 1. Meta description
    en_html = re.sub(
        r'(<meta name="description" content=")[^"]*(")',
        lambda m: m.group(1) + translated['meta_description'][:160] + m.group(2),
        en_html
    )

    # 2. og:description e twitter:description
    en_html = re.sub(
        r'(<meta property="og:description" content=")[^"]*(")',
        lambda m: m.group(1) + translated['meta_description'][:160] + m.group(2),
        en_html
    )
    en_html = re.sub(
        r'(<meta name="twitter:description" content=")[^"]*(")',
        lambda m: m.group(1) + translated['meta_description'][:160] + m.group(2),
        en_html
    )

    # 3. JSON-LD: description, artform, artMedium, artworkSurface
    def fix_jld(m):
        try:
            data = json.loads(m.group(1))
            data['description'] = translated['jld_description']
            data['artform'] = 'Sculpture'
            data['artMedium'] = 'Hand-chased aluminum'
            data['artworkSurface'] = 'Aluminum sheet'
            return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'
        except:
            return m.group(0)
    en_html = re.sub(
        r'<script type="application/ld\+json">(.*?)</script>',
        fix_jld,
        en_html,
        flags=re.DOTALL
    )

    # 4. Corpo: paragrafi descrizione
    new_paragraphs = "\n".join(f"<p>{p}</p>" for p in translated['body_paragraphs'])
    en_html = re.sub(
        r'(<div class="rule"></div>\s*).*?(\s*<p class="label opera-serie-label">)',
        lambda m: m.group(1) + new_paragraphs + '\n        ' + m.group(2),
        en_html,
        flags=re.DOTALL
    )

    # 5. Serie label
    if translated.get('serie_label'):
        en_html = re.sub(
            r'(<p class="label opera-serie-label">)[^<]*(</p>)',
            lambda m: m.group(1) + 'From the series ' + translated['serie_label'] + m.group(2),
            en_html
        )

    # 6. Back link
    if translated.get('back_text'):
        en_html = re.sub(
            r'(<a href="/en/serie/[^"]*" class="back-link">← )[^<]*(</a>)',
            lambda m: m.group(1) + translated['back_text'] + m.group(2),
            en_html
        )

    # 7. Alt immagine principale
    it_title_m = re.search(r'<h1>([^<]+)</h1>', it_html)
    it_title = it_title_m.group(1).strip() if it_title_m else opera_id
    # Lascia il titolo dell'opera invariato nell'alt (è un nome proprio)

    # 8. Pulsanti prev/next aria-label
    en_html = en_html.replace('aria-label="Precedente"', 'aria-label="Previous"')
    en_html = en_html.replace('aria-label="Successiva"', 'aria-label="Next"')

    return en_html

def main():
    base = Path(__file__).parent
    opera_dirs = sorted((base / "opera").iterdir())

    errors = []

    for i, opera_dir in enumerate(opera_dirs):
        if not opera_dir.is_dir():
            continue
        opera_id = opera_dir.name
        it_path = opera_dir / "index.html"
        en_path = base / "en" / "opera" / opera_id / "index.html"

        if not it_path.exists() or not en_path.exists():
            print(f"  SKIP {opera_id}: file mancante")
            continue

        print(f"[{i+1}/49] {opera_id}...", end=" ", flush=True)

        it_html = it_path.read_text(encoding="utf-8")
        en_html = en_path.read_text(encoding="utf-8")

        # Salta se già tradotta (meta description non contiene parole IT tipiche)
        it_markers = ["dell'", "dell ", "dello ", "della ", "delle ", "degli ", " che ", " con ", " una ", " uno "]
        en_meta = re.search(r'<meta name="description" content="([^"]*)"', en_html)
        if en_meta:
            en_meta_text = en_meta.group(1)
            if not any(m in en_meta_text for m in it_markers):
                print("già tradotta, skip")
                continue

        try:
            it_data = extract_it_data(it_html)
            if not it_data['body_text']:
                print("SKIP (no body text)")
                continue

            # Retry su 429
            for attempt in range(3):
                try:
                    translated = translate_with_deepl(it_data, opera_id)
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < 2:
                        print(f"rate limit, attendo 30s...", end=" ", flush=True)
                        time.sleep(30)
                    else:
                        raise

            new_en_html = update_en_page(en_html, it_html, translated, opera_id)
            en_path.write_text(new_en_html, encoding="utf-8")
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append((opera_id, str(e)))

        # Pausa per rate limiting
        time.sleep(2)

    if errors:
        print(f"\nErrori ({len(errors)}):")
        for op, err in errors:
            print(f"  {op}: {err}")
    else:
        print("\nTutte le pagine tradotte correttamente.")

if __name__ == "__main__":
    main()
