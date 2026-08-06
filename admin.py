#!/usr/bin/env python3
"""Pannello admin locale — Paola Maccioni.

Gira sul PC Windows di Paola e sul Mac di Andrea.
L'unica dipendenza esterna è Pillow: il parser multipart è interno, così il
pannello funziona su qualunque Python 3.8+ (il modulo `cgi` della libreria
standard, usato dalle versioni precedenti, è stato rimosso da Python 3.13).
"""

import json, os, re, shutil, subprocess, sys, tempfile, traceback, unicodedata
import http.server, socketserver, urllib.parse, webbrowser
from html import escape

try:
    from PIL import Image, ImageOps
except ImportError:
    print("\n  ERRORE: manca la libreria Pillow (serve per elaborare le foto).\n"
          "  Chiudi questa finestra, apri il Prompt dei comandi e scrivi:\n\n"
          "      py -m pip install Pillow\n")
    sys.exit(1)

PORT       = int(os.environ.get("PANNELLO_PORT", 8765))
HOST       = "127.0.0.1"   # solo questo PC: niente richieste del firewall Windows
ROOT       = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(ROOT, "data", "series.json")
BACKUP_PATH = DATA_PATH + ".bak"
SITE_URL   = "https://paolamaccioni.com"   # dominio live (per canonical/og/schema)
# Nota: l'ID di Google Analytics NON sta qui — le pagine generate caricano
# js/consent.js, che attiva il tracciamento solo dopo il consenso ai cookie.
IMG_EXTS   = {".jpg", ".jpeg", ".png", ".webp"}
CANVAS_BG  = (25, 21, 20)   # sfondo scuro identico al --bg del sito
MAX_UPLOAD = 2 * 1024 * 1024 * 1024   # 2 GB per richiesta: limite di sicurezza

# ── multipart/form-data ─────────────────────────────────────────────────────
#
# Parser minimale e in streaming, sostituisce `cgi.FieldStorage`. Le foto non
# vengono tenute in memoria: ogni parte oltre 1 MB finisce su file temporaneo,
# quindi si possono caricare decine di foto pesanti senza saturare la RAM.

class _Part:
    """Una parte del form: campo di testo o file caricato."""
    __slots__ = ("name", "filename", "file")

    def __init__(self, name, filename, file):
        self.name, self.filename, self.file = name, filename, file

    def value(self):
        self.file.seek(0)
        return self.file.read().decode("utf-8", "replace")


class Form:
    """Interfaccia compatibile con cgi.FieldStorage per ciò che serve qui."""

    def __init__(self, parts):
        self._parts = parts          # dict: nome → lista di _Part

    def __contains__(self, name):
        return name in self._parts

    def __getitem__(self, name):
        return self._parts[name]     # sempre una lista

    def getfirst(self, name, default=""):
        parts = self._parts.get(name)
        return parts[0].value() if parts else default


def _boundary_of(content_type):
    """Estrae il boundary dall'header Content-Type."""
    m = re.search(r'boundary=("([^"]+)"|([^;\s]+))', content_type or "", re.I)
    if not m:
        return None
    return (m.group(2) or m.group(3)).encode("ascii", "replace")


def _parse_multipart(rfile, boundary, length, chunk=256 * 1024):
    """Legge `length` byte da rfile e ritorna un dict nome → [ _Part, ... ]."""
    delim  = b"--" + boundary
    sep    = b"\r\n" + delim
    parts  = {}
    buf    = b""
    left   = length

    def fill(target):
        """Porta il buffer ad almeno `target` byte (o fino a fine stream)."""
        nonlocal buf, left
        while len(buf) < target and left > 0:
            data = rfile.read(min(chunk, left))
            if not data:
                left = 0
                break
            left -= len(data)
            buf += data

    # salta il preambolo, fino al primo delimitatore
    fill(len(delim) + 4)
    start = buf.find(delim)
    if start < 0:
        raise ValueError("form multipart non valido")
    buf = buf[start + len(delim):]

    while True:
        fill(2)
        if buf[:2] == b"--":         # delimitatore di chiusura
            break
        if buf[:2] != b"\r\n":
            raise ValueError("form multipart non valido")
        buf = buf[2:]

        # intestazioni della parte
        while b"\r\n\r\n" not in buf:
            before = len(buf)
            fill(len(buf) + chunk)
            if len(buf) == before:
                raise ValueError("caricamento interrotto")
        raw_head, _, buf = buf.partition(b"\r\n\r\n")

        disposition = ""
        for line in raw_head.split(b"\r\n"):
            k, _, v = line.partition(b":")
            if k.strip().lower() == b"content-disposition":
                disposition = v.decode("utf-8", "replace")
        name = _dispo_param(disposition, "name")
        filename = _dispo_param(disposition, "filename")

        # corpo della parte, fino al prossimo delimitatore
        out = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
        while True:
            pos = buf.find(sep)
            if pos >= 0:
                out.write(buf[:pos])
                buf = buf[pos + len(sep):]
                break
            keep = len(sep) - 1      # possibile separatore spezzato a metà
            if len(buf) > keep:
                out.write(buf[:-keep])
                buf = buf[-keep:]
            before = len(buf)
            fill(len(buf) + chunk)
            if len(buf) == before:
                out.close()
                raise ValueError("caricamento interrotto")
        out.seek(0)

        if name:
            parts.setdefault(name, []).append(_Part(name, filename, out))
        else:
            out.close()

    return parts


def _dispo_param(disposition, key):
    """Legge un parametro (name/filename) da un Content-Disposition."""
    m = re.search(r'%s="([^"]*)"' % key, disposition, re.I)
    if not m:
        m = re.search(r"%s=([^;]+)" % key, disposition, re.I)
        return m.group(1).strip() if m else None
    return m.group(1)

# ── image processing ────────────────────────────────────────────────────────

def _resize_contain(img, max_w, max_h):
    """Ridimensiona mantenendo proporzioni, senza mai ingrandire."""
    w, h = img.size
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img

def _make_canvas(img, cw, ch):
    """Centra l'immagine su un canvas cw×ch con sfondo scuro."""
    fitted = _resize_contain(img, cw, ch)
    canvas = Image.new("RGB", (cw, ch), CANVAS_BG)
    x = (cw - fitted.width)  // 2
    y = (ch - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas

def process_image(file_obj, opera_dir, basename):
    """
    Apre file_obj, crea tre varianti:
      - main/{basename}.jpg  (JPEG 85q, max 1400px)
      - thumb/{basename}.webp (WebP 82q, max 800px)
      - canvas/{basename}.webp (WebP 82q, 800×1000 su sfondo scuro)
    Ritorna (main_name, thumb_name, canvas_name).
    """
    img = ImageOps.exif_transpose(Image.open(file_obj))
    if img.mode != "RGB":
        img = img.convert("RGB")

    # main
    main  = _resize_contain(img, 1400, 1400)
    mname = f"{basename}.jpg"
    main.save(os.path.join(opera_dir, mname), "JPEG", quality=85, optimize=True)

    # thumb
    thumb_dir = os.path.join(opera_dir, "thumb")
    os.makedirs(thumb_dir, exist_ok=True)
    tname = f"{basename}.webp"
    _resize_contain(img, 800, 800).save(
        os.path.join(thumb_dir, tname), "WEBP", quality=82)

    # canvas
    canvas_dir = os.path.join(opera_dir, "canvas")
    os.makedirs(canvas_dir, exist_ok=True)
    cname = f"{basename}.webp"
    _make_canvas(img, 800, 1000).save(
        os.path.join(canvas_dir, cname), "WEBP", quality=82)

    return mname, tname, cname

# ── static page sync ────────────────────────────────────────────────────────
#
# Principio: il DISCO è la fonte di verità per le immagini. Dopo ogni operazione
# si ricostruiscono le gallery dai file reali e si rigenerano da zero la pagina
# opera (IT+EN) e la griglia della pagina serie. Niente patch fragili: una sola
# funzione `resync()` riallinea tutto ed è impossibile lasciare il sito a metà.

def _numkey(fn):
    m = re.match(r"(\d+)", fn)
    return (int(m.group(1)) if m else 9999, fn)

def rebuild_galleries(serie_id, work):
    """Ricostruisce gallery/thumb/canvas (+ image/thumb/canvas) dai file su disco."""
    base = os.path.join(ROOT, serie_id, work["id"])
    files = sorted(list_main_images(serie_id, work["id"]), key=_numkey) if os.path.isdir(base) else []
    gallery, thumb_g, canvas_g = [], [], []
    for f in files:
        stem = os.path.splitext(f)[0]
        gallery.append(f"{serie_id}/{work['id']}/{f}")
        thumb_g.append(f"{serie_id}/{work['id']}/thumb/{stem}.webp")
        canvas_g.append(f"{serie_id}/{work['id']}/canvas/{stem}.webp")
    work["gallery"], work["thumb_gallery"], work["canvas_gallery"] = gallery, thumb_g, canvas_g
    work["image"]  = gallery[0]  if gallery  else ""
    work["thumb"]  = thumb_g[0]  if thumb_g  else ""
    work["canvas"] = canvas_g[0] if canvas_g else ""

def _first_paragraph(text, max_len=155):
    if not text:
        return ""
    p = text.replace("\r", "").split("\n")[0].strip()
    return (p[:max_len].rsplit(" ", 1)[0] + "…") if len(p) > max_len else p

def _desc_paragraphs(text):
    return "".join(f"<p>{escape(p.strip())}</p>"
                   for p in (text or "").replace("\r", "").split("\n") if p.strip())

_OPERA_JS = r"""
<script src="/js/main.js"></script>
<script src="/js/consent.js"></script>
<script>
(() => {
  const gallery = __GALLERY__;
  const thumbs = document.querySelectorAll('.opera-thumb');
  const mainImg = document.getElementById('opera-img');
  const counter = document.getElementById('opera-counter');
  let current = 0;
  function preload(i){ [i-1,i+1].forEach(k=>{const idx=(k+gallery.length)%gallery.length;const im=new Image();im.src='/'+gallery[idx];}); }
  function show(i){ current=(i+gallery.length)%gallery.length; mainImg.removeAttribute('srcset'); mainImg.src='/'+gallery[current]; mainImg.alt=__TITLE__+' '+(current+1); counter.textContent=(current+1)+' / '+gallery.length; thumbs.forEach((t,idx)=>t.classList.toggle('active',idx===current)); preload(current); }
  const lb=document.createElement('div'); lb.className='opera-lightbox';
  lb.innerHTML=`<button class="opera-lightbox-close" aria-label="__CLOSE__">×</button><button class="opera-lightbox-prev" aria-label="__PREV__">‹</button><button class="opera-lightbox-next" aria-label="__NEXT__">›</button><img alt="" decoding="async"><div class="opera-lightbox-caption"></div>`;
  document.body.appendChild(lb);
  const lbImg=lb.querySelector('img'); const lbCap=lb.querySelector('.opera-lightbox-caption'); const operaTitle=__TITLE__;
  function openLb(){ lbImg.src='/'+gallery[current]; lbImg.alt=operaTitle; lbCap.textContent=operaTitle+' — '+(current+1)+' / '+gallery.length; lb.classList.add('open'); document.body.style.overflow='hidden'; }
  function closeLb(){ lb.classList.remove('open'); document.body.style.overflow=''; }
  function lbShow(i){ show(i); lbImg.src='/'+gallery[current]; lbCap.textContent=operaTitle+' — '+(current+1)+' / '+gallery.length; }
  if(gallery.length>1){
    thumbs.forEach(t=>t.addEventListener('click',()=>show(parseInt(t.dataset.i))));
    document.getElementById('prev-img').addEventListener('click',()=>show(current-1));
    document.getElementById('next-img').addEventListener('click',()=>show(current+1));
    document.addEventListener('keydown',e=>{ if(lb.classList.contains('open'))return; if(e.key==='ArrowLeft')show(current-1); if(e.key==='ArrowRight')show(current+1); });
    thumbs[0]?.classList.add('active'); preload(0);
  } else { document.getElementById('prev-img').style.display='none'; document.getElementById('next-img').style.display='none'; counter.style.display='none'; }
  mainImg.addEventListener('click',openLb);
  lb.querySelector('.opera-lightbox-close').addEventListener('click',closeLb);
  lb.addEventListener('click',e=>{ if(e.target===lb)closeLb(); });
  lb.querySelector('.opera-lightbox-prev').addEventListener('click',e=>{ e.stopPropagation(); lbShow(current-1); });
  lb.querySelector('.opera-lightbox-next').addEventListener('click',e=>{ e.stopPropagation(); lbShow(current+1); });
  document.addEventListener('keydown',e=>{ if(!lb.classList.contains('open'))return; if(e.key==='Escape')closeLb(); if(e.key==='ArrowLeft'&&gallery.length>1)lbShow(current-1); if(e.key==='ArrowRight'&&gallery.length>1)lbShow(current+1); });
})();
</script>"""

def _opera_js(work, title, is_en):
    js = (_OPERA_JS.replace("__GALLERY__", json.dumps(work.get("gallery", [])))
                   .replace("__TITLE__", json.dumps(title)))
    pairs = (("Close", "Previous", "Next") if is_en else ("Chiudi", "Precedente", "Successiva"))
    return js.replace("__CLOSE__", pairs[0]).replace("__PREV__", pairs[1]).replace("__NEXT__", pairs[2])

def _back_target(serie, work_id):
    """Dove riporta il link «indietro» di una pagina opera: (percorso, etichetta).

    Un'opera aperta da una sotto-serie deve tornare alla sotto-serie, non alla
    serie principale: prima tornavano tutte alla serie e chi arrivava da una
    sotto-serie si ritrovava due passi indietro, in un elenco dove l'opera
    appena vista non c'era nemmeno.

    Se l'opera sta ANCHE nella griglia principale (qualcuna e' di proposito in
    entrambe) vince la serie: e' il posto da cui la si raggiunge piu' spesso.
    """
    if any(w["id"] == work_id for w in serie.get("works", [])):
        return f'/serie/{serie["id"]}/', serie["name"]
    for sub in _subseries(serie):
        if any(w["id"] == work_id for w in sub.get("works", [])):
            return f'/serie/{serie["id"]}/{sub["id"]}/', sub.get("name") or serie["name"]
    return f'/serie/{serie["id"]}/', serie["name"]

def render_opera_page(serie, work, lang):
    """Genera l'HTML completo di una pagina opera (lang = 'it' | 'en')."""
    sid, wid, title = serie["id"], work["id"], work["title"]
    is_en = (lang == "en")
    desc = (work.get("description_en") or work.get("description") or "") if is_en \
           else (work.get("description") or "")
    serie_name = serie["name"]
    back_href, back_label = _back_target(serie, wid)
    canon = f"{SITE_URL}/{'en/' if is_en else ''}opera/{wid}/"
    other = f"{SITE_URL}/{'' if is_en else 'en/'}opera/{wid}/"
    og_image = f"{SITE_URL}/{work.get('image','')}"
    year = str(work.get("year") or "")
    n = len(work.get("gallery", []))
    if desc:
        meta = _first_paragraph(desc)
    elif is_en:
        meta = f"{title} — aluminium sculpture by Paola Maccioni, {serie_name} series."
    else:
        meta = f"{title} — scultura in alluminio di Paola Maccioni, serie {serie_name}."

    jsonld = {
        "@context": "https://schema.org", "@type": "VisualArtwork", "name": title,
        "description": desc, "creator": {"@type": "Person", "name": "Paola Maccioni"},
        "url": canon, "image": [f"{SITE_URL}/{g}" for g in work.get("gallery", [])],
        "artform": "Sculpture" if is_en else "Scultura",
        "artMedium": "Hand-chased aluminium" if is_en else "Alluminio lavorato a sbalzo",
        "artworkSurface": "Aluminium sheet" if is_en else "Lastra di alluminio",
        "inLanguage": "en-GB" if is_en else "it-IT",
    }
    if year:
        jsonld["dateCreated"] = year

    base = "/en" if is_en else ""
    L = (lambda it, en: en if is_en else it)
    nav = f"""<nav>
  <div class="inner">
    <button class="nav-toggle" aria-label="Menu"><span></span><span></span><span></span></button>
    <ul>
      <li><a href="{base}/index.html">Home</a></li>
      <li><a href="{base}/bio.html">{L('Biografia','Biography')}</a></li>
      <li><a href="{base}/portfolio.html">Portfolio</a></li>
      <li><a href="{base}/commissioni.html">{L('Commissioni','Commissions')}</a></li>
      <li><a href="{base}/contatti.html">{L('Contatti','Contact')}</a></li>
    </ul>
    <div class="lang-switcher">
      <a href="/opera/{wid}/"{'' if is_en else ' class="active"'}>IT</a>
      <span>|</span>
      <a href="/en/opera/{wid}/"{' class="active"' if is_en else ''}>EN</a>
    </div>
  </div>
</nav>"""
    thumbs_html = "".join(
        f'<button class="opera-thumb" data-i="{i}" data-src="/{work["gallery"][i]}">'
        f'<img src="/{work["canvas_gallery"][i]}" alt="{escape(title)} {i+1}" loading="lazy" decoding="async"></button>'
        for i in range(n))
    legal = ('<div class="legal-bar">© 2026 PIEMME di Paola Maccioni | C.F. MCCPLA80R64B354E | '
             '<a href="mailto:infopiemmeart@gmail.com">infopiemmeart@gmail.com</a> | '
             f'<a href="{base}/privacy.html">Privacy</a> | <a href="{base}/cookie-policy.html">Cookie</a> | '
             f'<a href="#" data-cookie-settings>{L("Gestisci cookie","Manage cookies")}</a> | '
             f'{L("Tutti i diritti sono riservati","All rights reserved")}</div>')

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'it'}">
<head>
  <meta charset="UTF-8">
  <link rel="preconnect" href="https://formspree.io">
  <link rel="dns-prefetch" href="https://www.googletagmanager.com">
  <link rel="dns-prefetch" href="https://www.google-analytics.com">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0e0d0c">
  <title>{escape(title)} — Paola Maccioni</title>
  <meta name="description" content="{escape(meta)}">
  <meta name="keywords" content="{escape(title.lower())}, paola maccioni, {escape(serie_name.lower())}, {L('scultura alluminio sbalzo','aluminium sculpture')}">
  <meta name="author" content="Paola Maccioni">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{canon}">
  <link rel="alternate" hreflang="{'it' if is_en else 'en'}" href="{other}">
  <link rel="alternate" hreflang="{'en' if is_en else 'it'}" href="{canon}">

  <meta property="og:type" content="article">
  <meta property="og:locale" content="{'en_GB' if is_en else 'it_IT'}">
  <meta property="og:site_name" content="Paola Maccioni — PIEMME">
  <meta property="og:title" content="{escape(title)} — Paola Maccioni">
  <meta property="og:description" content="{escape(meta)}">
  <meta property="og:url" content="{canon}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:width" content="1400">
  <meta property="og:image:height" content="1400">
  <meta property="article:author" content="Paola Maccioni">
  <meta property="article:section" content="{escape(serie_name)}">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)} — Paola Maccioni">
  <meta name="twitter:description" content="{escape(meta)}">
  <meta name="twitter:image" content="{og_image}">

  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
  <link rel="stylesheet" href="/css/main.css">
  <!-- Analytics: caricata da js/consent.js solo dopo il consenso ai cookie (GDPR) -->
</head>
<body>

{nav}

<section class="page-section opera-section">
  <div class="opera-wrap container">

    <a href="{base}{back_href}" class="back-link">← {escape(back_label)}</a>

    <div class="opera-grid">
      <div class="opera-img-wrap">
        <img id="opera-img" src="/{work.get('image','')}" alt="{escape(title)}" srcset="/{work.get('image','')} 1400w, /{work.get('image','')} 800w" decoding="async" fetchpriority="high">
        <button class="opera-nav prev" id="prev-img" aria-label="{L('Precedente','Previous')}">‹</button>
        <button class="opera-nav next" id="next-img" aria-label="{L('Successiva','Next')}">›</button>
        <span class="opera-counter" id="opera-counter">1 / {n}</span>
      </div>
      <div class="opera-info">
        <p class="label">{escape(year)}</p>
        <h1>{escape(title)}</h1>
        <div class="rule"></div>
        {_desc_paragraphs(desc)}
        <p class="label opera-serie-label">{L('Dalla serie','From the series')} {escape(serie_name)}</p>
      </div>
    </div>

    <div class="opera-thumbs" id="opera-thumbs">{thumbs_html}</div>

  </div>
</section>

{legal}
{_opera_js(work, title, is_en)}
</body>
</html>
"""

def write_opera_pages(serie, work):
    for lang in ("it", "en"):
        d = os.path.join(ROOT, *(("en", "opera") if lang == "en" else ("opera",)), work["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_opera_page(serie, work, lang))

def _work_tile(w, prefix):
    return (
        f'      <a class="work-tile" href="{prefix}/opera/{w["id"]}/">\n'
        f'        <div class="work-tile-img">\n'
        f'          <img src="/{w.get("canvas") or w.get("thumb") or w.get("image","")}" alt="{escape(w["title"])}" loading="lazy" decoding="async">\n'
        f'        </div>\n'
        f'        <div class="work-tile-body">\n'
        f'          <p class="label">{escape(str(w.get("year") or ""))}</p>\n'
        f'          <h3>{escape(w["title"])}</h3>\n'
        f'        </div>\n'
        f'      </a>'
    )

def _subseries_tile(sub, serie_id, prefix):
    cover = sub.get("cover") or (sub["works"][0].get("canvas", "") if sub.get("works") else "")
    href = f"{prefix}/serie/{serie_id}/{sub['id']}/"
    count = len(sub.get("works", []))
    is_it = (prefix == "")
    label = f"Sotto-serie · {count} opere" if is_it else f"Sub-series · {count} works"
    name = sub.get("name", sub["id"])
    return (
        f'      <a class="work-tile subseries-tile" href="{href}">\n'
        f'        <div class="work-tile-img">\n'
        f'          <img src="/{cover}" alt="{escape(name)}" loading="lazy" decoding="async">\n'
        f'        </div>\n'
        f'        <div class="work-tile-body">\n'
        f'          <p class="label">{label}</p>\n'
        f'          <h3>{escape(name)} →</h3>\n'
        f'        </div>\n'
        f'      </a>'
    )

def _main_serie_tiles(serie, prefix):
    """Griglia della pagina serie: works + tile sotto-serie, ordinati per `position`."""
    entries = []
    for i, w in enumerate(serie.get("works", [])):
        entries.append((w.get("position", i), _work_tile(w, prefix)))
    for j, sub in enumerate(_subseries(serie)):
        entries.append((sub.get("position", 9000 + j), _subseries_tile(sub, serie["id"], prefix)))
    entries.sort(key=lambda t: t[0])
    return "\n".join(h for _, h in entries)

def _subseries_page_tiles(sub, prefix):
    """Griglia della pagina di una sotto-serie: solo i suoi works."""
    return "\n".join(_work_tile(w, prefix) for w in sub.get("works", []))

# alias di compatibilità
def _serie_tiles(serie, prefix):
    return _main_serie_tiles(serie, prefix)

def _serie_jsonld_images(serie, prefix):
    """Lista `image` dei dati strutturati della pagina serie.

    Segue lo stesso ordine della griglia: le voci ordinate per `position`, e
    ogni sotto-serie sostituita dalle opere che contiene. Un'opera presente
    sia nella griglia sia in una sotto-serie compare una volta sola.
    """
    voci = []
    for i, w in enumerate(serie.get("works", [])):
        voci.append((w.get("position", i), [w]))
    for j, sub in enumerate(_subseries(serie)):
        voci.append((sub.get("position", 9000 + j), list(sub.get("works", []))))
    voci.sort(key=lambda t: t[0])

    immagini, visti = [], set()
    for _, opere in voci:
        for w in opere:
            if w["id"] in visti:
                continue
            visti.add(w["id"])
            immagini.append({
                "@type": "ImageObject",
                "name": w.get("title", ""),
                "contentUrl": f'{SITE_URL}/{w.get("image", "")}',
                "url": f'{SITE_URL}{prefix}/opera/{w["id"]}/',
            })
    return immagini

def _update_serie_jsonld(path, serie, prefix):
    """Riallinea al catalogo la lista `image` dei dati strutturati.

    Si riscrive SOLO `image`: `name`, `description` e il resto sono scritti a
    mano e sono diversi tra italiano e inglese, quindi vanno lasciati stare.
    Senza questo, il blocco restava quello generato una volta sola e finiva per
    citare opere eliminate o spostate in un'altra serie, con contentUrl di
    immagini inesistenti.
    """
    if not os.path.isfile(path):
        return
    html = open(path, encoding="utf-8").read()
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', html, re.S)
    if not m:
        return
    try:
        dati = json.loads(m.group(2))
    except ValueError:
        return          # blocco malformato: meglio non peggiorarlo
    if dati.get("@type") != "ImageGallery":
        return          # non e' la galleria della serie
    dati["image"] = _serie_jsonld_images(serie, prefix)
    nuovo = m.group(1) + json.dumps(dati, ensure_ascii=False) + m.group(3)
    open(path, "w", encoding="utf-8").write(html[:m.start()] + nuovo + html[m.end():])

def update_serie_grid(serie):
    """Riscrive in-place la griglia <div class="serie-works"> nelle pagine serie
    principale IT+EN e in ogni pagina sotto-serie IT+EN, e riallinea i dati
    strutturati della pagina serie principale."""
    def _rewrite(path, tiles_html):
        if not os.path.isfile(path):
            return
        html = open(path, encoding="utf-8").read()
        if '<div class="serie-works">' not in html or "</section>" not in html:
            return
        head, _, rest = html.partition('<div class="serie-works">')
        _, _, tail = rest.partition("</section>")
        new = (head + '<div class="serie-works">\n' + tiles_html +
               "\n    </div>\n\n  </div>\n</section>" + tail)
        open(path, "w", encoding="utf-8").write(new)

    sid = serie["id"]
    for path, prefix in [(os.path.join(ROOT, "serie", sid, "index.html"), ""),
                         (os.path.join(ROOT, "en", "serie", sid, "index.html"), "/en")]:
        _rewrite(path, _main_serie_tiles(serie, prefix))
        _update_serie_jsonld(path, serie, prefix)
    for sub in _subseries(serie):
        for path, prefix in [(os.path.join(ROOT, "serie", sid, sub["id"], "index.html"), ""),
                             (os.path.join(ROOT, "en", "serie", sid, sub["id"], "index.html"), "/en")]:
            _rewrite(path, _subseries_page_tiles(sub, prefix))

def remove_opera_pages(work_id):
    for d in (os.path.join(ROOT, "opera", work_id),
              os.path.join(ROOT, "en", "opera", work_id)):
        if os.path.isdir(d):
            shutil.rmtree(d)

def resync(serie_id, work_id=None, deleted=False):
    """Riallinea JSON↔disco e rigenera pagina opera (IT+EN) + griglie serie.
    Da chiamare DOPO che il chiamante ha già modificato e salvato il JSON.
    Se l'opera è duplicata (main + sotto-serie), aggiorna tutte le istanze."""
    data  = load_data()
    serie = next((s for s in data["series"] if s["id"] == serie_id), None)
    if not serie:
        return
    if work_id and not deleted:
        instances = _find_all_instances(serie, work_id)
        if instances:
            primary = instances[0]
            rebuild_galleries(serie_id, primary)
            # Propaga i campi immagine/gallery alle altre istanze
            for w in instances[1:]:
                for k in ("image", "thumb", "canvas"):
                    w[k] = primary.get(k, "")
                for k in ("gallery", "thumb_gallery", "canvas_gallery"):
                    w[k] = list(primary.get(k, []))
            save_data(data)
            write_opera_pages(serie, primary)
    elif work_id and deleted:
        remove_opera_pages(work_id)
    update_serie_grid(serie)

# compat: vecchio nome usato in giro → ora riallinea tutto
def regenerate_opera_page(serie_id, work_id):
    resync(serie_id, work_id)

# ── helpers ────────────────────────────────────────────────────────────────

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-") or "opera-senza-titolo"

def load_data():
    """Legge series.json; se fosse illeggibile ricade sull'ultimo backup."""
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "series" not in data:
            raise ValueError("struttura inattesa")
        return data
    except (OSError, ValueError) as e:
        if os.path.isfile(BACKUP_PATH):
            print(f"  ! series.json illeggibile ({e}): uso il backup")
            with open(BACKUP_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        raise

def save_data(d):
    """Scrittura atomica + backup: un crash a metà non può corrompere i dati."""
    if os.path.isfile(DATA_PATH):
        try:
            shutil.copy2(DATA_PATH, BACKUP_PATH)
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DATA_PATH), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA_PATH)   # atomico anche su Windows
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

def valid_series():
    """ID delle serie esistenti, letti dal JSON: niente elenco hard-coded che
    si disallinea quando si aggiunge una serie nuova."""
    try:
        return {s["id"] for s in load_data().get("series", []) if s.get("id")}
    except Exception:
        return set()

# ── subseries-aware helpers ──────────────────────────────────────────────────
#
# Una serie può contenere sotto-serie (`subseries`). Un'opera può comparire sia
# nei `works` principali che dentro una sotto-serie (duplicato voluto, p.es.
# "L'ombra della luce" presente sia nella griglia di Materia e Trasformazione sia
# nella sotto-serie omonima). Tutte le operazioni che cercano un'opera per id
# devono guardare ovunque; le modifiche di contenuto vanno propagate a tutte le
# istanze.

def _subseries(serie):
    return serie.get("subseries", []) or []

def _all_works(serie):
    yield from serie.get("works", [])
    for sub in _subseries(serie):
        yield from sub.get("works", [])

def _find_work(serie, work_id):
    for w in _all_works(serie):
        if w["id"] == work_id:
            return w
    return None

def _find_all_instances(serie, work_id):
    """Tutte le istanze di un'opera (può essere duplicata main+sub)."""
    return [w for w in _all_works(serie) if w["id"] == work_id]

def _work_exists(serie, work_id):
    return _find_work(serie, work_id) is not None

def _next_position(works):
    """Posizione da assegnare a un'opera che arriva in fondo a un elenco.
    `position` può essere decimale (le sotto-serie usano -0.8, 0.1…), quindi
    non si può assumere che sia un intero."""
    nums = [w["position"] for w in (works or [])
            if isinstance(w.get("position"), (int, float))
            and not isinstance(w.get("position"), bool)]
    return (max(nums) + 1) if nums else len(works or [])

def _media_serie_of(data, work_id, work=None):
    """In quale cartella-serie stanno DAVVERO le foto dell'opera.

    Non si può dedurlo dalla serie in cui l'opera è elencata: la stessa opera
    può comparire sotto due serie diverse, ma le foto sul disco stanno in un
    posto solo. Si parte dal percorso salvato e, se non torna, si cercano.
    """
    prefix = ((work or {}).get("image") or "").split("/")[0]
    if prefix and os.path.isdir(os.path.join(ROOT, prefix, work_id)):
        return prefix
    for s in data.get("series", []):
        if os.path.isdir(os.path.join(ROOT, s["id"], work_id)):
            return s["id"]
    return None

def _propagate_media(data, work_id, primary):
    """Allinea i percorsi delle foto su OGNI istanza dell'opera, in tutte le
    serie e sotto-serie: se le foto si spostano, nessuna copia resta a puntare
    a una cartella che non esiste più."""
    for s in data.get("series", []):
        for w in _all_works(s):
            if w["id"] == work_id and w is not primary:
                for k in ("image", "thumb", "canvas"):
                    w[k] = primary.get(k, "")
                for k in ("gallery", "thumb_gallery", "canvas_gallery"):
                    w[k] = list(primary.get(k, []))

def _fix_covers(data, work_id, primary):
    """Aggiorna le copertine delle sotto-serie che mostravano questa opera:
    se l'opera è ancora lì si conserva lo scatto scelto (si ripiega sul primo
    solo quando quel file non esiste più), se se n'è andata si ripiega sulla
    prima opera rimasta."""
    for s in data.get("series", []):
        for sub in _subseries(s):
            cover = sub.get("cover") or ""
            if f"/{work_id}/" not in cover:
                continue
            works = sub.get("works", [])
            if any(w["id"] == work_id for w in works):
                # Una copertina scelta a mano (p.es. .../canvas/03.webp) va
                # rispettata: sovrascriverla col primo scatto rendeva quella
                # scelta impossibile da fissare.
                if cover in primary.get("canvas_gallery", []):
                    continue
                sub["cover"] = primary.get("canvas") or primary.get("thumb") or ""
            else:
                sub["cover"] = works[0].get("canvas", "") if works else ""

def _locations_of(serie, work_id):
    """Dove sta l'opera dentro una serie: ('main' | id-sotto-serie, …)."""
    where = []
    if any(w["id"] == work_id for w in serie.get("works", [])):
        where.append("main")
    for sub in _subseries(serie):
        if any(w["id"] == work_id for w in sub.get("works", [])):
            where.append(sub["id"])
    return where

# ── pubblicazione su GitHub → Netlify ────────────────────────────────────────

SAFE_NOTE = "Le foto restano salvate sul computer: non si perde niente."

class GitMissing(Exception):
    pass

def _git(*args, timeout=180):
    """Esegue un comando git nella cartella del sito, catturando l'output.

    GIT_TERMINAL_PROMPT=0: senza questa variabile git può restare in attesa di
    una password sul terminale e il pannello sembrerebbe bloccato per sempre.
    """
    env = dict(os.environ,
               GIT_TERMINAL_PROMPT="0",
               GIT_OPTIONAL_LOCKS="0",
               LC_ALL="C")
    try:
        return subprocess.run(["git", *args], cwd=ROOT, env=env,
                              capture_output=True, text=True,
                              errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise GitMissing()
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout")

def _git_out(res):
    return ((res.stderr or "") + (res.stdout or "")).strip()

def _ensure_identity():
    """Se git non sa chi è l'autore, lo imposta da solo per questo repo:
    è la causa più comune di 'commit fallito' su un PC nuovo."""
    if not _git("config", "user.email").stdout.strip():
        _git("config", "user.email", "infopiemmeart@gmail.com")
    if not _git("config", "user.name").stdout.strip():
        _git("config", "user.name", "Paola Maccioni")

def _repair_state():
    """Se una pubblicazione precedente si è interrotta a metà (merge in corso),
    riporta il repo in uno stato pulito invece di fallire per sempre."""
    git_dir = os.path.join(ROOT, ".git")
    if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
        _git("merge", "--abort")
    if os.path.exists(os.path.join(git_dir, "index.lock")):
        # residuo di un git ucciso a metà: rimuoverlo è sicuro se nessun git gira
        try: os.remove(os.path.join(git_dir, "index.lock"))
        except OSError: pass

# Pagine costruite interamente da admin.py a partire da series.json. Se un
# conflitto tocca solo queste, non c'è niente da salvare: si ributtano via e si
# rigenerano. Le foto e series.json invece NON sono in questo elenco: un
# conflitto lì è vero e deve passare da Andrea.
_PAGINA_OPERA = re.compile(r"^(?:en/)?opera/([^/]+)/index\.html$")
_PAGINA_SERIE = re.compile(r"^(?:en/)?serie/([^/]+)(?:/[^/]+)?/index\.html$")

DATA_REL = "data/series.json"

def _rigenerabile(path):
    return bool(_PAGINA_OPERA.match(path) or _PAGINA_SERIE.match(path))

# ── unione intelligente di series.json ──────────────────────────────────────
#
# Se Andrea dal Mac e Paola dal suo PC aggiungono due opere diverse, git vede
# due righe cambiate nello stesso punto dell'elenco e si ferma, pur non essendo
# un vero disaccordo. Qui si uniscono le due versioni ragionando per opera:
# quelle nuove si tengono tutte, e ci si arrende solo se la STESSA opera è
# stata modificata in due modi diversi.

def _git_bytes(*args):
    """Come _git ma senza decodifica: per leggere file con accenti."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    try:
        return subprocess.run(["git", *args], cwd=ROOT, env=env,
                              capture_output=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

def _indice(works):
    return {w["id"]: w for w in (works or []) if isinstance(w, dict) and w.get("id")}

def _unisci_opere(base, nostro, loro):
    """Unione a tre vie di un elenco di opere, per id. None se ambiguo."""
    b, n, l = _indice(base), _indice(nostro), _indice(loro)
    out = []
    for i in list(dict.fromkeys(list(n) + list(l))):   # prima le nostre, poi le loro
        vb, vn, vl = b.get(i), n.get(i), l.get(i)
        if vn is not None and vl is not None:
            if   vn == vl: out.append(vn)
            elif vb == vn: out.append(vl)      # modificata solo dall'altra parte
            elif vb == vl: out.append(vn)      # modificata solo da noi
            else:          return None         # stessa opera, due modifiche diverse
        elif vn is not None:
            if vb is None:   out.append(vn)    # opera nuova nostra
            elif vb == vn:   continue          # cancellata dall'altra parte
            else:            return None       # noi modificata, loro cancellata
        else:
            if vb is None:   out.append(vl)    # opera nuova loro
            elif vb == vl:   continue          # cancellata da noi
            else:            return None
    return out

def _unisci_campi(base, nostro, loro, salta):
    """Unisce i campi semplici di un oggetto. None se in disaccordo."""
    out = {}
    for k in list(dict.fromkeys(list(nostro) + list(loro))):
        if k in salta:
            continue
        vb, vn, vl = base.get(k), nostro.get(k), loro.get(k)
        if k not in nostro:   out[k] = vl
        elif k not in loro:   out[k] = vn
        elif vn == vl:        out[k] = vn
        elif vb == vn:        out[k] = vl
        elif vb == vl:        out[k] = vn
        else:                 return None
    return out

def _per_id(elenco):
    """Indicizza per id, ignorando quello che non ha la forma attesa."""
    return {x["id"]: x for x in (elenco or [])
            if isinstance(x, dict) and x.get("id")}

def _unisci_series_json(base, nostro, loro):
    """Unisce i tre series.json. None se serve l'intervento di Andrea."""
    if not all(isinstance(d, dict) for d in (base, nostro, loro)):
        return None
    b_ser, n_ser, l_ser = (_per_id(d.get("series")) for d in (base, nostro, loro))
    # Se qualche serie non ha la forma prevista, meglio non improvvisare.
    for d in (nostro, loro):
        if len(_per_id(d.get("series"))) != len(d.get("series") or []):
            return None
    fuse = []
    for sid in list(dict.fromkeys(list(n_ser) + list(l_ser))):
        sb, sn, sl = b_ser.get(sid, {}), n_ser.get(sid), l_ser.get(sid)
        if sn is None or sl is None:            # serie aggiunta o tolta da un lato
            fuse.append(sn or sl)
            continue
        unita = _unisci_campi(sb, sn, sl, salta={"works", "subseries"})
        if unita is None:
            return None
        opere = _unisci_opere(sb.get("works"), sn.get("works"), sl.get("works"))
        if opere is None:
            return None
        unita["works"] = opere
        if "subseries" in sn or "subseries" in sl:
            b_sub, n_sub, l_sub = (_per_id(x.get("subseries"))
                                   for x in (sb, sn, sl))
            sotto = []
            for xid in list(dict.fromkeys(list(n_sub) + list(l_sub))):
                xb, xn, xl = b_sub.get(xid, {}), n_sub.get(xid), l_sub.get(xid)
                if xn is None or xl is None:
                    sotto.append(xn or xl)
                    continue
                xu = _unisci_campi(xb, xn, xl, salta={"works"})
                if xu is None:
                    return None
                xo = _unisci_opere(xb.get("works"), xn.get("works"), xl.get("works"))
                if xo is None:
                    return None
                xu["works"] = xo
                sotto.append(xu)
            unita["subseries"] = sotto
        fuse.append(unita)
    testa = _unisci_campi(base, nostro, loro, salta={"series"})
    if testa is None:
        return None
    testa["series"] = fuse
    return testa

def _risolvi_series_json():
    """Prova a unire series.json dai tre stadi del merge. True se riuscito."""
    versioni = {}
    for stadio, nome in ((1, "base"), (2, "nostro"), (3, "loro")):
        r = _git_bytes("show", f":{stadio}:{DATA_REL}")
        if r is None or r.returncode != 0:
            return False
        try:
            versioni[nome] = json.loads(r.stdout.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return False
    unito = _unisci_series_json(versioni["base"], versioni["nostro"], versioni["loro"])
    if not unito or not unito.get("series"):
        return False
    n = sum(len(s.get("works", [])) for s in unito["series"])
    if n < max(sum(len(s.get("works", [])) for s in v["series"])
               for v in (versioni["nostro"], versioni["loro"])):
        return False                    # rete di sicurezza: mai perdere opere
    save_data(unito)
    print(f"  series.json unito da solo: {n} opere, nessuna persa.")
    return True

def _rigenera_pagine(paths):
    """Riscrive le pagine indicate a partire dal series.json appena unito.

    Attenzione: qui si RENDERIZZA soltanto. Non si chiama resync(), che
    ricostruirebbe le gallery dal disco: dopo una sincronizzazione le foto
    dell'altra persona potrebbero non essere ancora tutte materializzate
    (Git LFS) e si svuoterebbero le sue opere.
    """
    data = load_data()
    opere = {m.group(1) for p in paths if (m := _PAGINA_OPERA.match(p))}
    serie_ids = {m.group(1) for p in paths if (m := _PAGINA_SERIE.match(p))}
    for serie in data.get("series", []):
        for w in _all_works(serie):
            if w["id"] in opere:
                write_opera_pages(serie, w)
        if serie["id"] in serie_ids:
            update_serie_grid(serie)

def _risolvi_conflitti(lato_online="--theirs", chiudi_merge=True):
    """Risolve da sola i conflitti che non sono veri disaccordi: le pagine
    generate (ricostruibili da series.json) e l'elenco delle opere quando le
    due parti ne hanno aggiunte di diverse. Ritorna True se ce l'ha fatta.

    `lato_online` dice quale dei due lati del conflitto è la versione
    pubblicata, e cambia a seconda di come il conflitto è nato: vedi
    ripara_avvio(). `chiudi_merge=False` serve quando non c'è nessun merge
    aperto da concludere con un commit.

    Qualunque imprevisto qui dentro vale come 'non ci sono riuscita': meglio
    fermarsi e far chiamare Andrea che rischiare di rovinare i dati.
    """
    try:
        return _prova_a_risolvere(lato_online, chiudi_merge)
    except Exception:
        traceback.print_exc()
        return False

def _elenco_conflitti():
    """File lasciati a metà da git. None se git non risponde."""
    res = _git("diff", "--name-only", "--diff-filter=U")
    if res.returncode != 0:
        return None
    return [p.strip() for p in res.stdout.splitlines() if p.strip()]

def _prova_a_risolvere(lato_online="--theirs", chiudi_merge=True):
    conflitti = _elenco_conflitti()
    if not conflitti:
        return False
    pagine = [p for p in conflitti if _rigenerabile(p)]
    resto  = [p for p in conflitti if not _rigenerabile(p) and p != DATA_REL]
    if resto:
        return False                      # foto o file veri: decide Andrea

    if DATA_REL in conflitti and not _risolvi_series_json():
        return False

    # Le pagine si ripartono dalla versione online (che porta anche le
    # modifiche fatte a mano fuori dalla griglia), poi si rigenerano.
    for p in pagine:
        if _git("checkout", lato_online, "--", p).returncode != 0:
            return False
    if _git("add", "--", *conflitti).returncode != 0:
        return False
    if chiudi_merge and _git("commit", "--no-edit").returncode != 0:
        return False

    try:
        _rigenera_pagine(pagine or _tutte_le_pagine_serie())
    except Exception:
        traceback.print_exc()
        return False                      # merge già chiuso: il push riallineerà
    if chiudi_merge and _git("status", "--porcelain").stdout.strip():
        _git("add", "-A")
        _git("commit", "-m", "Riallinea le pagine generate dopo la sincronizzazione")
    print(f"  Conflitti risolti da solo su {len(conflitti)} file.")
    return True

# ── riparazione all'avvio ───────────────────────────────────────────────────
#
# Il launcher fa `git pull --autostash`: mette da parte il lavoro non ancora
# pubblicato di Paola, scarica gli aggiornamenti e glielo rimette. Se il
# ripristino va in conflitto git esce con SUCCESSO ma lascia i file a metà, e
# il pannello non deve partire così. Prima di arrendersi però conviene
# provarci: nel caso tipico (Andrea ritocca i testi delle serie, Paola
# aggiunge opere) non c'è nessun vero disaccordo.
#
# ATTENZIONE ai due lati, è la parte che si sbaglia facilmente:
#   • in un MERGE vero      --theirs = la versione online,  --ours = la locale
#   • in un conflitto da    --ours   = la versione online (il pull è già
#     AUTOSTASH                        andato a buon fine), --theirs = il
#                                      lavoro di Paola che git stava
#                                      rimettendo al suo posto
# Prendere il lato sbagliato qui significa riportare in vita i testi vecchi.

def _merge_in_corso():
    return os.path.exists(os.path.join(ROOT, ".git", "MERGE_HEAD"))

def ripara_avvio():
    """Tenta di sbloccare un conflitto lasciato dal pull del launcher.
    True = il pannello può partire."""
    conflitti = _elenco_conflitti()
    if conflitti is None:
        return False                      # git non risponde: meglio fermarsi
    if not conflitti:
        return True                       # niente da riparare
    if _merge_in_corso():
        return _risolvi_conflitti("--theirs", chiudi_merge=True)
    # Conflitto da autostash: nessun merge aperto da chiudere con un commit.
    # Le modifiche restano lì, pronte per il tasto "Pubblica".
    return _risolvi_conflitti("--ours", chiudi_merge=False)

def _tutte_le_pagine_serie():
    """Percorsi delle pagine serie, per riallinearle quando è cambiato solo
    l'elenco delle opere."""
    try:
        return [f"serie/{s['id']}/index.html" for s in load_data().get("series", [])]
    except Exception:
        return []

def _pull():
    """Sincronizza col sito remoto. --no-rebase è necessario: dalle versioni
    recenti git si rifiuta di fare pull se non gli si dice come riconciliare.
    Ritorna (ok, esito_del_comando)."""
    res = _git("pull", "--no-rebase", "--no-edit", timeout=300)
    if res.returncode == 0:
        return True, res
    if _risolvi_conflitti():
        return True, res
    _git("merge", "--abort")     # niente stato a metà per il prossimo giro
    return False, res

def _push():
    res = _git("push", timeout=600)
    if res.returncode != 0 and "no upstream branch" in _git_out(res).lower():
        res = _git("push", "-u", "origin", "HEAD", timeout=600)
    return res

def git_publish(msg="Aggiornamento dal pannello admin"):
    """
    Pubblica TUTTE le modifiche locali sul sito in un solo push:
      1. ripara eventuali stati sporchi lasciati da un tentativo precedente
      2. commit di tutto
      3. pull (sincronizza eventuali modifiche fatte da altri)
      4. push  → Netlify ricostruisce il sito
    Pensata per essere chiamata UNA volta a fine sessione (un push = una build).
    Ritorna un dict pronto per la UI.
    """
    try:
        _repair_state()
        st = _git("status", "--porcelain")
        if st.returncode != 0:
            return {"ok": False,
                    "error": "Questa cartella non è collegata al sito. Contatta Andrea."}

        if st.stdout.strip():
            _ensure_identity()
            add = _git("add", "-A")
            if add.returncode != 0:
                return {"ok": False,
                        "error": "Non riesco a preparare le modifiche. Chiudi eventuali "
                                 "foto aperte in altri programmi e riprova. " + SAFE_NOTE}
            commit = _git("commit", "-m", msg)
            if commit.returncode != 0 and "nothing to commit" not in _git_out(commit).lower():
                return {"ok": False,
                        "error": "Salvataggio delle modifiche non riuscito. " + SAFE_NOTE}

        # Ramo locale collegato a GitHub? Se non lo è, si salta il pull e il
        # push lo collega da solo (`push -u`).
        has_upstream = _git("rev-parse", "--abbrev-ref", "@{u}").returncode == 0

        # C'è qualcosa da mandare online? (anche commit di sessioni precedenti)
        if has_upstream:
            ahead = _git("rev-list", "--count", "@{u}..HEAD")
            if ahead.returncode == 0 and ahead.stdout.strip() == "0":
                return {"ok": True, "published": False,
                        "message": "Niente da pubblicare — il sito è già aggiornato."}

        pull_ok, pull = (_pull() if has_upstream else (True, None))
        if not pull_ok:
            out = _git_out(pull).lower()
            if "conflict" in out:
                return {"ok": False,
                        "error": "Qualcun altro ha modificato la stessa opera nello "
                                 "stesso momento. Serve una mano di Andrea. " + SAFE_NOTE}
            if any(k in out for k in ("could not resolve host", "unable to access",
                                      "timed out", "timeout", "network")):
                return {"ok": False,
                        "error": "Nessuna connessione a internet. Controlla la rete "
                                 "e premi di nuovo «Pubblica». " + SAFE_NOTE}
            return {"ok": False,
                    "error": "Sincronizzazione non riuscita. Riprova tra poco; "
                             "se continua, avvisa Andrea. " + SAFE_NOTE}

        push = _push()
        if push.returncode != 0:
            out = _git_out(push).lower()
            if any(k in out for k in ("authentication", "403", "permission denied",
                                      "could not read username", "invalid username")):
                return {"ok": False,
                        "error": "Il permesso di pubblicare è scaduto e va rinnovato: "
                                 "avvisa Andrea. " + SAFE_NOTE}
            if any(k in out for k in ("could not resolve host", "unable to access",
                                      "timed out", "timeout")):
                return {"ok": False,
                        "error": "Nessuna connessione a internet. Controlla la rete "
                                 "e premi di nuovo «Pubblica». " + SAFE_NOTE}
            # Le foto grandi passano da Git LFS, che ha un limite mensile:
            # senza questo controllo l'errore sarebbe incomprensibile.
            if "lfs" in out and any(k in out for k in ("quota", "exceeded", "bandwidth",
                                                       "over the limit", "batch response")):
                return {"ok": False,
                        "error": "Lo spazio per le foto su GitHub è esaurito per questo "
                                 "mese: serve Andrea per sbloccarlo. " + SAFE_NOTE}
            if "fetch first" in out or "non-fast-forward" in out or "rejected" in out:
                if _pull()[0] and _push().returncode == 0:
                    return {"ok": True, "published": True,
                            "message": "Sito aggiornato! Sarà online tra circa un minuto."}
            return {"ok": False,
                    "error": "Pubblicazione non riuscita. Riprova tra poco; "
                             "se continua, avvisa Andrea. " + SAFE_NOTE}

        return {"ok": True, "published": True,
                "message": "Sito aggiornato! Sarà online tra circa un minuto."}
    except GitMissing:
        return {"ok": False,
                "error": "Git non è installato su questo PC: senza non si può "
                         "pubblicare. Contatta Andrea. " + SAFE_NOTE}

def list_main_images(serie_id, work_id):
    d = os.path.join(ROOT, serie_id, work_id)
    if not os.path.isdir(d):
        return []
    return sorted(
        f for f in os.listdir(d)
        if re.match(r'^\d+\.(jpg|jpeg|png|webp)$', f, re.I)
        and os.path.isfile(os.path.join(d, f))
    )

def find_file(folder, base_num):
    if not os.path.isdir(folder):
        return None
    return next(
        (f for f in os.listdir(folder)
         if os.path.splitext(f)[0] == base_num
         and os.path.isfile(os.path.join(folder, f))),
        None
    )

def swap_files(folder, base_a, base_b):
    fa = find_file(folder, base_a)
    fb = find_file(folder, base_b)
    if not fa or not fb:
        return
    ext_a = os.path.splitext(fa)[1]
    ext_b = os.path.splitext(fb)[1]
    tmp = os.path.join(folder, f"__tmp{os.getpid()}{ext_b}")
    os.rename(os.path.join(folder, fb), tmp)
    os.rename(os.path.join(folder, fa), os.path.join(folder, base_b + ext_a))
    os.rename(tmp, os.path.join(folder, base_a + ext_b))

def swap_primary(serie_id, work_id, filename):
    target_num = os.path.splitext(filename)[0]
    if target_num == "01":
        return
    work_dir = os.path.join(ROOT, serie_id, work_id)
    for sub in [work_dir, os.path.join(work_dir, "canvas"), os.path.join(work_dir, "thumb")]:
        if os.path.isdir(sub):
            swap_files(sub, "01", target_num)
    # aggiorna i campi image/thumb/canvas in ogni istanza (main + sotto-serie)
    data  = load_data()
    serie = next((s for s in data["series"] if s["id"] == serie_id), None)
    if not serie:
        return
    instances = _find_all_instances(serie, work_id)
    if not instances:
        return
    for work in instances:
        for folder, key in [
            (work_dir,                            "image"),
            (os.path.join(work_dir, "thumb"),     "thumb"),
            (os.path.join(work_dir, "canvas"),    "canvas"),
        ]:
            f = find_file(folder, "01")
            if f:
                rel = os.path.relpath(os.path.join(folder, f), ROOT).replace(os.sep, "/")
                work[key] = rel
    save_data(data)

def save_uploaded_images(form, opera_dir, serie_id, work_id, primary_idx=0):
    """
    Salva e processa le immagini caricate.
    Ritorna (gallery, thumb_gallery, canvas_gallery, scartate) dove `scartate`
    è la lista dei nomi di file non caricabili (formato non supportato o file
    danneggiato): la UI li mostra invece di farli sparire in silenzio.
    """
    raw = form["images"] if "images" in form else None
    if raw is None:
        return [], [], [], []
    items = raw if isinstance(raw, list) else [raw]
    named = [it for it in items if getattr(it, "filename", None)]
    valid, skipped = [], []
    for it in named:
        if os.path.splitext(it.filename)[1].lower() in IMG_EXTS:
            valid.append(it)
        else:
            skipped.append(it.filename)
    if valid and 0 <= primary_idx < len(valid):
        valid = [valid[primary_idx]] + [f for j, f in enumerate(valid) if j != primary_idx]
    existing = sorted(
        f for f in os.listdir(opera_dir)
        if re.match(r"^\d+\.(jpg|jpeg|png|webp)$", f, re.I)
        and os.path.isfile(os.path.join(opera_dir, f))
    )
    # Riparti dal numero più alto + 1 (non dal conteggio): evita di sovrascrivere
    # file esistenti quando la numerazione ha dei buchi (dopo cancellazioni).
    nums = [int(os.path.splitext(f)[0]) for f in existing]
    n = (max(nums) + 1) if nums else 1
    gallery, thumb_gallery, canvas_gallery = [], [], []
    for it in valid:
        base = f"{n:02d}"
        try:
            mname, tname, cname = process_image(it.file, opera_dir, base)
        except Exception as e:
            # Una foto illeggibile non deve far fallire tutto il caricamento:
            # si salta, si segnala, e le altre proseguono.
            print(f"  ! foto scartata {it.filename}: {e}")
            skipped.append(it.filename)
            _cleanup_partial(opera_dir, base)
            continue
        gallery.append(       f"{serie_id}/{work_id}/{mname}")
        thumb_gallery.append( f"{serie_id}/{work_id}/thumb/{tname}")
        canvas_gallery.append(f"{serie_id}/{work_id}/canvas/{cname}")
        n += 1
    return gallery, thumb_gallery, canvas_gallery, skipped

def _skipped_msg(skipped):
    """Avviso leggibile sulle foto scartate (None se non ce ne sono)."""
    if not skipped:
        return None
    names = ", ".join(skipped[:5]) + ("…" if len(skipped) > 5 else "")
    heic = any(os.path.splitext(f)[1].lower() in (".heic", ".heif") for f in skipped)
    msg = f"{len(skipped)} foto non caricate ({names})."
    if heic:
        msg += (" Sono in formato HEIC (foto da iPhone): sul telefono vai in "
                "Impostazioni → Fotocamera → Formati e scegli «Massima compatibilità», "
                "oppure convertile in JPG prima di caricarle.")
    else:
        msg += " Formati accettati: JPG, PNG, WEBP."
    return msg

def _no_images_msg(skipped):
    """Messaggio quando non è stata caricata nessuna foto valida."""
    return _skipped_msg(skipped) or "Nessuna foto selezionata: aggiungi almeno una foto."

def _cleanup_partial(opera_dir, base):
    """Rimuove i file lasciati a metà da una foto che non si è potuta elaborare."""
    for folder, ext in ((opera_dir, ".jpg"),
                        (os.path.join(opera_dir, "thumb"),  ".webp"),
                        (os.path.join(opera_dir, "canvas"), ".webp")):
        p = os.path.join(folder, base + ext)
        if os.path.isfile(p):
            try: os.remove(p)
            except OSError: pass

# ── HTTP handler ────────────────────────────────────────────────────────────

class Handler(http.server.SimpleHTTPRequestHandler):

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass

    # Rete: browser che annulla un caricamento, tab chiusa a metà... sono
    # eventi normali, non devono riempire la finestra nera di errori rossi.
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    # Rete a parte, QUALSIASI errore imprevisto diventa un messaggio leggibile
    # invece di una richiesta che resta appesa senza risposta.
    def do_GET(self):
        try:
            self._get()
        except Exception:
            self._crash()

    def do_POST(self):
        try:
            self._post()
        except Exception:
            self._crash()

    def _crash(self):
        traceback.print_exc()
        try:
            self._err("Si è verificato un errore imprevisto. Le foto e i dati "
                      "sul computer non sono stati persi: riprova, e se succede "
                      "di nuovo avvisa Andrea.", 500)
        except Exception:
            pass

    # GET

    def _get(self):
        path = self.path.split("?")[0]
        qs   = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")

        if path == "/":
            self.path = "/admin.html"
            return super().do_GET()

        if path == "/api/data":
            return self._json(load_data())

        if path == "/api/images":
            s = qs.get("serie", [""])[0]
            w = qs.get("work",  [""])[0]
            if not s or not w or s not in valid_series():
                return self._err("Parametri mancanti", 400)
            return self._json({"files": list_main_images(s, w)})

        return super().do_GET()

    # POST

    def _post(self):
        path = self.path.split("?")[0]

        if path in ("/upload", "/api/add-images"):
            return self._handle_multipart(path)

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        try:
            p = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self._err("JSON non valido", 400)

        dispatch = {
            "/api/update-work":    self._update_work,
            "/api/delete-work":    self._delete_work,
            "/api/delete-image":   self._delete_image,
            "/api/set-primary":    self._set_primary,
            "/api/set-cover":      self._set_cover,
            "/api/reorder-works":  self._reorder_works,
            "/api/reorder-subseries": self._reorder_subseries,
            "/api/move-work":      self._move_work,
            "/api/publish":        self._publish,
        }
        fn = dispatch.get(path)
        if fn:
            return fn(p)
        self.send_error(404)

    # ── multipart ──────────────────────────────────────────────────────────

    def _handle_multipart(self, path):
        ctype = self.headers.get("Content-Type", "")
        if not ctype.lower().startswith("multipart/form-data"):
            return self._err("Formato della richiesta non valido", 400)
        boundary = _boundary_of(ctype)
        if not boundary:
            return self._err("Formato della richiesta non valido", 400)
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0:
            return self._err("Nessun dato ricevuto: riprova", 400)
        if length > MAX_UPLOAD:
            return self._err("Caricamento troppo grande: carica meno foto per volta", 413)
        try:
            form = Form(_parse_multipart(self.rfile, boundary, length))
        except ValueError as e:
            return self._err(f"Caricamento non riuscito ({e}): riprova", 400)

        if path == "/upload":         return self._upload(form)
        if path == "/api/add-images": return self._add_images(form)

    def _upload(self, form):
        title    = form.getfirst("title",       "").strip()
        desc     = form.getfirst("description", "").strip()
        serie_id = form.getfirst("serie",       "").strip()
        year     = form.getfirst("year",        "").strip()
        try:              pix = int(form.getfirst("primary_index", "0"))
        except ValueError: pix = 0

        if not title:
            return self._err("Manca il titolo dell'opera", 400)
        if serie_id not in valid_series():
            return self._err("Scegli una serie valida", 400)

        slug  = slugify(title)
        data  = load_data()
        serie = next(s for s in data["series"] if s["id"] == serie_id)
        if _work_exists(serie, slug):
            return self._err(f"Esiste già un'opera con questo titolo ({slug}). "
                             f"Cambia titolo, oppure aggiungi le foto a quella "
                             f"esistente da «Opere → Modifica».", 400)

        opera_dir = os.path.join(ROOT, serie_id, slug)
        os.makedirs(opera_dir, exist_ok=True)
        gallery, thumb_g, canvas_g, skipped = save_uploaded_images(
            form, opera_dir, serie_id, slug, pix)
        if not gallery:
            # Nessuna foto valida: non lasciare a metà né cartella né JSON.
            try: os.rmdir(opera_dir)
            except OSError: pass
            return self._err(_no_images_msg(skipped), 400)

        serie["works"].append({
            "id": slug, "title": title, "year": year,
            "image":          gallery[0]   if gallery   else "",
            "gallery":        gallery,
            "thumb":          thumb_g[0]   if thumb_g   else "",
            "thumb_gallery":  thumb_g,
            "canvas":         canvas_g[0]  if canvas_g  else "",
            "canvas_gallery": canvas_g,
            "description":    desc,
        })
        save_data(data)
        # Ricostruisce gallery dal disco + crea pagine opera IT/EN + aggiorna serie
        resync(serie_id, slug)
        return self._json({"ok": True, "slug": slug, "uploaded": len(gallery),
                           "skipped": skipped, "warning": _skipped_msg(skipped),
                           "url": f"/opera/{slug}/"})

    def _add_images(self, form):
        s = form.getfirst("serie_id", "").strip()
        w = form.getfirst("work_id",  "").strip()
        if not s or not w or s not in valid_series():
            return self._err("Parametri mancanti", 400)
        opera_dir = os.path.join(ROOT, s, w)
        if not os.path.isdir(opera_dir):
            return self._err("Opera non trovata", 404)
        gallery, thumb_g, canvas_g, skipped = save_uploaded_images(form, opera_dir, s, w)
        if not gallery:
            return self._err(_no_images_msg(skipped), 400)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if serie:
            instances = _find_all_instances(serie, w)
            for work in instances:
                work.setdefault("gallery",        []).extend(gallery)
                work.setdefault("thumb_gallery",  []).extend(thumb_g)
                work.setdefault("canvas_gallery", []).extend(canvas_g)
                if not work.get("thumb")   and thumb_g:   work["thumb"]   = thumb_g[0]
                if not work.get("canvas")  and canvas_g:  work["canvas"]  = canvas_g[0]
            if instances:
                save_data(data)
        regenerate_opera_page(s, w)
        return self._json({"ok": True, "uploaded": len(gallery),
                           "skipped": skipped, "warning": _skipped_msg(skipped)})

    # ── JSON endpoints ─────────────────────────────────────────────────────

    def _update_work(self, p):
        s = p.get("serie_id", "").strip()
        w = p.get("work_id",  "").strip()
        if not s or not w:
            return self._err("Parametri mancanti", 400)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie: return self._err("Serie non trovata", 404)
        instances = _find_all_instances(serie, w)
        if not instances: return self._err("Opera non trovata", 404)
        for k in ("title", "year", "description", "description_en"):
            if k in p:
                for work in instances:
                    work[k] = str(p[k])
        save_data(data)
        # Rigenera pagine opera + griglia serie col nuovo titolo/anno/descrizione
        if s in valid_series():
            resync(s, w)
        return self._json({"ok": True})

    def _delete_work(self, p):
        s = p.get("serie_id", "").strip()
        w = p.get("work_id",  "").strip()
        if not s or not w or s not in valid_series():
            return self._err("Parametri mancanti", 400)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie: return self._err("Serie non trovata", 404)
        before_main = len(serie.get("works", []))
        serie["works"] = [x for x in serie.get("works", []) if x["id"] != w]
        removed_sub = 0
        for sub in _subseries(serie):
            before = len(sub.get("works", []))
            sub["works"] = [x for x in sub.get("works", []) if x["id"] != w]
            removed_sub += before - len(sub["works"])
        if len(serie["works"]) == before_main and removed_sub == 0:
            return self._err("Opera non trovata", 404)
        save_data(data)
        d = os.path.join(ROOT, s, w)
        if os.path.isdir(d):
            shutil.rmtree(d)
        # Rimuove le pagine opera IT/EN e aggiorna la griglia serie
        resync(s, w, deleted=True)
        return self._json({"ok": True})

    def _delete_image(self, p):
        s  = p.get("serie_id", "").strip()
        w  = p.get("work_id",  "").strip()
        fn = p.get("filename", "").strip()
        if not all([s, w, fn]) or s not in valid_series():
            return self._err("Parametri mancanti", 400)
        if not re.match(r'^\d+\.(jpg|jpeg|png|webp)$', fn, re.I):
            return self._err("File non valido", 400)
        work_dir = os.path.join(ROOT, s, w)
        fpath    = os.path.join(work_dir, fn)
        if not os.path.isfile(fpath):
            return self._err("File non trovato", 404)
        base = os.path.splitext(fn)[0]
        os.remove(fpath)
        for sub in ["canvas", "thumb"]:
            sub_dir = os.path.join(work_dir, sub)
            f = find_file(sub_dir, base)
            if f: os.remove(os.path.join(sub_dir, f))
        # aggiorna JSON su tutte le istanze (main + sotto-serie)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if serie:
            instances = _find_all_instances(serie, w)
            for work in instances:
                full = f"{s}/{w}/{fn}"
                work["gallery"]        = [g for g in work.get("gallery",        []) if g != full]
                work["thumb_gallery"]  = [g for g in work.get("thumb_gallery",  []) if os.path.splitext(os.path.basename(g))[0] != base]
                work["canvas_gallery"] = [g for g in work.get("canvas_gallery", []) if os.path.splitext(os.path.basename(g))[0] != base]
                if work.get("image", "").endswith(f"/{fn}"):
                    imgs = list_main_images(s, w)
                    work["image"] = f"{s}/{w}/{imgs[0]}" if imgs else ""
                for key, _sub in [("thumb", "thumb"), ("canvas", "canvas")]:
                    if os.path.splitext(os.path.basename(work.get(key, "")))[0] == base:
                        gk = f"{key}_gallery"
                        work[key] = work[gk][0] if work.get(gk) else ""
            if instances:
                save_data(data)
        regenerate_opera_page(s, w)
        return self._json({"ok": True})

    def _set_primary(self, p):
        s  = p.get("serie_id", "").strip()
        w  = p.get("work_id",  "").strip()
        fn = p.get("filename", "").strip()
        if not all([s, w, fn]) or s not in valid_series():
            return self._err("Parametri mancanti", 400)
        if not re.match(r'^\d+\.(jpg|jpeg|png|webp)$', fn, re.I):
            return self._err("File non valido", 400)
        swap_primary(s, w, fn)
        regenerate_opera_page(s, w)
        return self._json({"ok": True})

    def _set_cover(self, p):
        """Sceglie quale scatto dell'opera fa da copertina alla sotto-serie."""
        s  = p.get("serie_id", "").strip()
        w  = p.get("work_id",  "").strip()
        fn = p.get("filename", "").strip()
        if not all([s, w, fn]) or s not in valid_series():
            return self._err("Parametri mancanti", 400)
        if not re.match(r'^\d+\.(jpg|jpeg|png|webp)$', fn, re.I):
            return self._err("File non valido", 400)

        cover = f"{s}/{w}/canvas/{os.path.splitext(fn)[0]}.webp"
        if not os.path.isfile(os.path.join(ROOT, cover)):
            return self._err("Questo scatto non ha una versione copertina: "
                             "ricarica la foto e riprova", 400)

        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        subs  = [sub for sub in _subseries(serie or {})
                 if any(x["id"] == w for x in sub.get("works", []))]
        if not subs:
            return self._err("Quest'opera non sta dentro una sotto-serie, "
                             "quindi non fa da copertina a niente", 400)

        for sub in subs:
            sub["cover"] = cover
        save_data(data)
        update_serie_grid(serie)
        return self._json({"ok": True, "cover": cover,
                           "subseries": [sub.get("name") or sub["id"] for sub in subs]})

    def _reorder_works(self, p):
        s = p.get("serie_id", "").strip()
        if not s or s not in valid_series():
            return self._err("Serie non valida", 400)
        order = p.get("order", [])
        if not isinstance(order, list) or not order:
            return self._err("Ordine non valido", 400)
        data = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie:
            return self._err("Serie non trovata", 404)

        # Nella griglia del sito opere e sotto-serie stanno mescolate e sono
        # ordinate tutte insieme per `position`: per poter portare un quadro
        # prima di una sotto-serie l'elenco deve poter contenere entrambe.
        # Voci ammesse: {"kind": "work"|"sub", "id": ...}, oppure la vecchia
        # stringa (= opera), così un pannello non ancora aggiornato continua
        # a funzionare invece di ricevere un errore.
        voci = []
        for v in order:
            if isinstance(v, str):
                voci.append(("work", v))
            elif isinstance(v, dict) and v.get("kind") in ("work", "sub") and v.get("id"):
                voci.append((v["kind"], v["id"]))
            else:
                return self._err("Ordine non valido", 400)

        opere = {w["id"]: w for w in serie.get("works", [])}
        sotto = {x["id"]: x for x in _subseries(serie)}
        atteso = {("work", i) for i in opere} | {("sub", i) for i in sotto}
        # Formato vecchio: solo opere. Le sotto-serie restano dove sono.
        if all(k == "work" for k, _ in voci) and len(voci) == len(opere):
            atteso = {("work", i) for i in opere}
        if len(voci) != len(atteso) or set(voci) != atteso:
            return self._err("L'elenco non corrisponde al contenuto della serie", 400)

        for i, (kind, vid) in enumerate(voci):
            (opere if kind == "work" else sotto)[vid]["position"] = i
        # L'elenco `works` segue le position, così il JSON resta leggibile.
        serie["works"] = sorted(serie.get("works", []),
                                key=lambda w: w.get("position", 0))
        save_data(data)
        # Riordina la griglia nella pagina serie (IT+EN)
        resync(s)
        return self._json({"ok": True})

    def _reorder_subseries(self, p):
        """Riordina le opere DENTRO una sotto-serie.

        Qui si riordina soltanto la lista `works` della sotto-serie, senza
        toccare `position`: la pagina della sotto-serie la scorre nell'ordine
        in cui sta nel JSON, e un'opera può comparire sia qui sia nella
        griglia principale — scrivere `position` rischierebbe di spostarla
        anche lì.
        """
        s      = p.get("serie_id", "").strip()
        sub_id = p.get("sub_id", "").strip()
        order  = p.get("order", [])
        if not s or s not in valid_series():
            return self._err("Serie non valida", 400)
        if not isinstance(order, list) or not order:
            return self._err("Ordine non valido", 400)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie:
            return self._err("Serie non trovata", 404)
        sub = next((x for x in _subseries(serie) if x["id"] == sub_id), None)
        if not sub:
            return self._err("Sotto-serie non trovata", 404)

        mappa = {w["id"]: w for w in sub.get("works", [])}
        if len(order) != len(mappa) or set(order) != set(mappa):
            return self._err("L'elenco non corrisponde al contenuto della sotto-serie", 400)

        sub["works"] = [mappa[wid] for wid in order]
        save_data(data)
        resync(s)
        return self._json({"ok": True})

    def _move_work(self, p):
        """Sposta un'opera già esistente in un'altra serie o sotto-serie.

        Si sposta UNA collocazione per volta: `from` dice da dove ("" = griglia
        principale della serie, altrimenti l'id di una sotto-serie) e `target`
        dice dove ("serie" oppure "serie/sotto-serie"). Le eventuali altre
        collocazioni della stessa opera restano dove sono — qualche opera
        compare di proposito sia nella griglia della serie sia in una
        sotto-serie, e uno spostamento non deve cancellare quella scelta.

        Le foto stanno sul disco in un posto solo: se serve si spostano, e i
        percorsi vengono riallineati su tutte le istanze.
        """
        s          = p.get("serie_id", "").strip()
        w          = p.get("work_id",  "").strip()
        src_sub_id = p.get("from",     "").strip()
        dst        = p.get("target",   "").strip()
        if not s or not w or s not in valid_series():
            return self._err("Parametri mancanti", 400)

        dst_sid, _, dst_sub_id = dst.partition("/")
        data = load_data()
        src  = next((x for x in data["series"] if x["id"] == s),       None)
        tgt  = next((x for x in data["series"] if x["id"] == dst_sid), None)
        if not src:
            return self._err("Serie di partenza non trovata", 404)
        if not tgt:
            return self._err("Scegli una serie di destinazione valida", 400)

        # elenco di partenza
        if src_sub_id:
            src_sub = next((x for x in _subseries(src) if x["id"] == src_sub_id), None)
            if not src_sub:
                return self._err("Sotto-serie di partenza non trovata", 400)
            src_list = src_sub.setdefault("works", [])
        else:
            src_list = src.setdefault("works", [])

        # elenco di arrivo
        if dst_sub_id:
            dst_sub = next((x for x in _subseries(tgt) if x["id"] == dst_sub_id), None)
            if not dst_sub:
                return self._err("Sotto-serie di destinazione non trovata", 400)
            dest_list = dst_sub.setdefault("works", [])
        else:
            dst_sub   = None
            dest_list = tgt.setdefault("works", [])

        work = next((x for x in src_list if x["id"] == w), None)
        if not work:
            return self._err("Opera non trovata", 404)
        if src_list is dest_list:
            return self._json({"ok": True, "moved": False,
                               "message": "L'opera è già in questa serie."})

        # Dove stanno le foto adesso, e dove devono finire.
        cur_media = _media_serie_of(data, w, work)
        if not cur_media:
            return self._err("Non trovo la cartella delle fotografie di questa "
                             "opera, quindi non la sposto. Avvisa Andrea.", 500)
        src_dir = os.path.join(ROOT, cur_media, w)
        dst_dir = os.path.join(ROOT, dst_sid,   w)
        if cur_media != dst_sid and os.path.exists(dst_dir):
            return self._err(
                f"Nella serie «{tgt['name']}» c'è già un'opera con questo nome. "
                f"Cambia prima il titolo di una delle due.", 400)

        src_list[:] = [x for x in src_list if x["id"] != w]

        if cur_media != dst_sid:
            # Le foto seguono l'opera. Si spostano PRIMA di salvare il JSON: se
            # lo spostamento fallisce, sul disco resta tutto com'era.
            try:
                os.makedirs(os.path.join(ROOT, dst_sid), exist_ok=True)
                shutil.move(src_dir, dst_dir)
            except OSError as e:
                print(f"  ! spostamento cartella non riuscito: {e}")
                return self._err(
                    "Non riesco a spostare le foto dell'opera. Chiudi eventuali "
                    "foto aperte in altri programmi e riprova. " + SAFE_NOTE, 500)

        # Se l'opera era GIÀ nell'elenco di arrivo, non se ne aggiunge una copia:
        # si è solo tolta dall'altra collocazione.
        if not any(x["id"] == w for x in dest_list):
            work["position"] = _next_position(dest_list)
            dest_list.append(work)

        rebuild_galleries(dst_sid, work)
        _propagate_media(data, w, work)
        _fix_covers(data, w, work)
        save_data(data)

        # Pagine opera (IT+EN) e griglia della serie di arrivo…
        resync(dst_sid, w)
        # …e griglia della serie di partenza, da cui l'opera è sparita.
        if s != dst_sid:
            resync(s)

        # Le altre collocazioni dell'opera restano: lo si dice, così non sembra
        # che il pannello abbia fatto le cose a metà.
        altrove = [loc for x in data["series"] for loc in _locations_of(x, w)
                   if not (x["id"] == dst_sid and loc == (dst_sub_id or "main"))]
        dest_name = f"{tgt['name']} → {dst_sub['name']}" if dst_sub else tgt["name"]
        msg = f"«{work['title']}» spostata in {dest_name}."
        if altrove:
            msg += " Resta anche dove compariva già altrove."
        return self._json({"ok": True, "moved": True, "serie_id": dst_sid,
                           "message": msg})

    def _publish(self, p):
        res = git_publish()
        return self._json(res, 200 if res.get("ok") else 500)

    # ── response helpers ───────────────────────────────────────────────────

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=400):
        self._json({"ok": False, "error": msg}, status)


# ── entry point ─────────────────────────────────────────────────────────────

class Server(socketserver.ThreadingTCPServer):
    daemon_threads      = True    # la finestra si chiude senza restare appesa
    allow_reuse_address = True    # riavvio immediato dopo uno stop


def _startup_checks():
    """Controlli prima di partire: meglio un messaggio chiaro adesso che un
    errore incomprensibile a metà lavoro."""
    if not os.path.isfile(DATA_PATH):
        print("\n  ERRORE: non trovo i dati del sito (data/series.json).\n"
              "  Il pannello va avviato dalla cartella del sito. Avvisa Andrea.\n")
        return False
    try:
        load_data()
    except Exception as e:
        print(f"\n  ERRORE: i dati del sito non sono leggibili ({e}).\n"
              "  Avvisa Andrea: non caricare altre foto per ora.\n")
        return False
    try:
        if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
            print("  ! Attenzione: questa cartella non è collegata a GitHub.\n"
                  "    Puoi caricare le foto, ma «Pubblica sul sito» non funzionerà.\n")
        elif _needs_lfs() and _git("lfs", "version").returncode != 0:
            # Le foto delle serie sono gestite da Git LFS: senza, verrebbero
            # pubblicate in un formato che il sito non sa mostrare.
            print("  ! ATTENZIONE: manca Git LFS su questo computer.\n"
                  "    Carica pure le foto, ma NON premere «Pubblica sul sito»:\n"
                  "    avvisa prima Andrea.\n")
    except GitMissing:
        print("  ! Attenzione: git non è installato.\n"
              "    Puoi caricare le foto, ma «Pubblica sul sito» non funzionerà.\n")
    return True


def _needs_lfs():
    """Il repo si aspetta Git LFS per le foto delle serie?"""
    ga = os.path.join(ROOT, ".gitattributes")
    try:
        with open(ga, encoding="utf-8") as f:
            return "filter=lfs" in f.read()
    except OSError:
        return False


def main():
    os.chdir(ROOT)
    if not _startup_checks():
        sys.exit(1)

    url = f"http://localhost:{PORT}/"
    try:
        httpd = Server((HOST, PORT), Handler)
    except OSError:
        # Porta occupata: quasi sempre è il pannello già aperto in un'altra
        # finestra. Si apre il browser su quello invece di dare errore.
        print("\n  Il pannello risulta già aperto: apro il browser su quello.\n"
              "  (Se non funziona, chiudi tutte le finestre nere e riprova.)\n")
        try: webbrowser.open(url)
        except Exception: pass
        return

    print(f"\n  Pannello attivo — {url}\n  Chiudi questa finestra quando hai finito.\n")
    try: webbrowser.open(url)
    except Exception: pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()
        print("\n  Pannello chiuso.")

if __name__ == "__main__":
    # Modalità di servizio usata dal launcher prima di aprire il pannello:
    # esce 0 se il repo è a posto (o è riuscita a sistemarlo), 1 se serve
    # davvero Andrea. Non avvia nessun server.
    if "--ripara-conflitto" in sys.argv:
        sys.exit(0 if ripara_avvio() else 1)
    main()
