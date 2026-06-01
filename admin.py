#!/usr/bin/env python3
"""Admin server locale — Paola Maccioni."""

import json, os, re, shutil, subprocess, unicodedata
import http.server, socketserver, urllib.parse, cgi, webbrowser
from html import escape
from PIL import Image, ImageOps

PORT       = 8765
ROOT       = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(ROOT, "data/series.json")
SITE_URL   = "https://paolamaccioni.com"   # dominio live (per canonical/og/schema)
GA_ID      = "G-FPHJKXEM94"
VALID_SER  = {"struttura-tensione", "forma-organica"}
IMG_EXTS   = {".jpg", ".jpeg", ".png", ".webp"}
CANVAS_BG  = (25, 21, 20)   # sfondo scuro identico al --bg del sito

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

def render_opera_page(serie, work, lang):
    """Genera l'HTML completo di una pagina opera (lang = 'it' | 'en')."""
    sid, wid, title = serie["id"], work["id"], work["title"]
    is_en = (lang == "en")
    desc = (work.get("description_en") or work.get("description") or "") if is_en \
           else (work.get("description") or "")
    serie_name = serie["name"]
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
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
</head>
<body>

{nav}

<section class="page-section opera-section">
  <div class="opera-wrap container">

    <a href="{base}/serie/{sid}/" class="back-link">← {escape(serie_name)}</a>

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

def _serie_tiles(serie, prefix):
    return "\n".join(
        f"""      <a class="work-tile" href="{prefix}/opera/{w['id']}/">
        <div class="work-tile-img">
          <img src="/{w.get('canvas') or w.get('thumb') or w.get('image','')}" alt="{escape(w['title'])}" loading="lazy" decoding="async">
        </div>
        <div class="work-tile-body">
          <p class="label">{escape(str(w.get('year') or ''))}</p>
          <h3>{escape(w['title'])}</h3>
        </div>
      </a>"""
        for w in serie["works"])

def update_serie_grid(serie):
    """Riscrive in-place la griglia <div class="serie-works"> nelle pagine serie IT+EN."""
    for path, prefix in [(os.path.join(ROOT, "serie", serie["id"], "index.html"), ""),
                         (os.path.join(ROOT, "en", "serie", serie["id"], "index.html"), "/en")]:
        if not os.path.isfile(path):
            continue
        html = open(path, encoding="utf-8").read()
        if '<div class="serie-works">' not in html or "</section>" not in html:
            continue
        head, _, rest = html.partition('<div class="serie-works">')
        _, _, tail = rest.partition("</section>")
        new = (head + '<div class="serie-works">\n' + _serie_tiles(serie, prefix) +
               "\n    </div>\n\n  </div>\n</section>" + tail)
        open(path, "w", encoding="utf-8").write(new)

def remove_opera_pages(work_id):
    for d in (os.path.join(ROOT, "opera", work_id),
              os.path.join(ROOT, "en", "opera", work_id)):
        if os.path.isdir(d):
            shutil.rmtree(d)

def resync(serie_id, work_id=None, deleted=False):
    """Riallinea JSON↔disco e rigenera pagina opera (IT+EN) + griglia serie.
    Da chiamare DOPO che il chiamante ha già modificato e salvato il JSON."""
    data  = load_data()
    serie = next((s for s in data["series"] if s["id"] == serie_id), None)
    if not serie:
        return
    if work_id and not deleted:
        work = next((w for w in serie["works"] if w["id"] == work_id), None)
        if work:
            rebuild_galleries(serie_id, work)
            save_data(data)
            write_opera_pages(serie, work)
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
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

# ── pubblicazione su GitHub → Netlify ────────────────────────────────────────

def _git(*args):
    """Esegue un comando git nella cartella del sito, catturando l'output."""
    return subprocess.run(
        ["git", *args], cwd=ROOT,
        capture_output=True, text=True,
    )

def git_publish(msg="Aggiornamento dal pannello admin"):
    """
    Pubblica TUTTE le modifiche locali sul sito in un solo push:
      1. controlla se c'è qualcosa da pubblicare
      2. commit di tutto
      3. pull (sincronizza eventuali modifiche fatte da altri)
      4. push  → Netlify ricostruisce il sito
    Pensata per essere chiamata UNA volta a fine sessione (un push = una build).
    Ritorna un dict pronto per la UI.
    """
    st = _git("status", "--porcelain")
    if st.returncode != 0:
        return {"ok": False,
                "error": "Git non disponibile su questo PC. Contatta Andrea."}
    if not st.stdout.strip():
        return {"ok": True, "published": False,
                "message": "Niente da pubblicare — il sito è già aggiornato."}

    if _git("add", "-A").returncode != 0:
        return {"ok": False, "error": "Errore nel preparare le modifiche."}

    commit = _git("commit", "-m", msg)
    if commit.returncode != 0:
        err = (commit.stderr + commit.stdout).strip()
        if any(k in err.lower() for k in
               ("identity", "user.name", "user.email", "tell me who you are")):
            return {"ok": False,
                    "error": "Git non sa chi sei: nome/email non configurati. "
                             "Vanno impostati una volta sola. Contatta Andrea."}
        return {"ok": False, "error": "Commit fallito: " + (err[:200] or "?")}

    pull = _git("pull", "--no-edit")
    if pull.returncode != 0:
        return {"ok": False,
                "error": "Sincronizzazione fallita (possibile conflitto). "
                         "Le foto sono salvate sul PC. Contatta Andrea."}

    push = _git("push")
    if push.returncode != 0:
        return {"ok": False,
                "error": "Pubblicazione fallita: controlla la connessione a "
                         "internet e riprova. Se persiste, contatta Andrea."}

    return {"ok": True, "published": True,
            "message": "Sito aggiornato! Sarà online tra circa un minuto."}

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
    # aggiorna i campi image/thumb/canvas nel JSON
    data  = load_data()
    serie = next((s for s in data["series"] if s["id"] == serie_id), None)
    if not serie:
        return
    work = next((w for w in serie["works"] if w["id"] == work_id), None)
    if not work:
        return
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
    Ritorna (gallery, thumb_gallery, canvas_gallery).
    """
    raw = form["images"] if "images" in form else None
    if raw is None:
        return [], [], []
    items = raw if isinstance(raw, list) else [raw]
    valid = [it for it in items
             if getattr(it, "filename", None)
             and os.path.splitext(it.filename)[1].lower() in IMG_EXTS]
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
    start = (max(nums) + 1) if nums else 1
    gallery, thumb_gallery, canvas_gallery = [], [], []
    for i, it in enumerate(valid, start=start):
        base = f"{i:02d}"
        mname, tname, cname = process_image(it.file, opera_dir, base)
        gallery.append(       f"{serie_id}/{work_id}/{mname}")
        thumb_gallery.append( f"{serie_id}/{work_id}/thumb/{tname}")
        canvas_gallery.append(f"{serie_id}/{work_id}/canvas/{cname}")
    return gallery, thumb_gallery, canvas_gallery

# ── HTTP handler ────────────────────────────────────────────────────────────

class Handler(http.server.SimpleHTTPRequestHandler):

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass

    # GET

    def do_GET(self):
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
            if not s or not w or s not in VALID_SER:
                return self._err("Parametri mancanti", 400)
            return self._json({"files": list_main_images(s, w)})

        return super().do_GET()

    # POST

    def do_POST(self):
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
            "/api/reorder-works":  self._reorder_works,
            "/api/publish":        self._publish,
        }
        fn = dispatch.get(path)
        if fn:
            return fn(p)
        self.send_error(404)

    # ── multipart ──────────────────────────────────────────────────────────

    def _handle_multipart(self, path):
        ctype, _ = cgi.parse_header(self.headers.get("Content-Type", ""))
        if ctype != "multipart/form-data":
            return self._err("Multipart richiesto", 400)
        form = cgi.FieldStorage(
            fp=self.rfile, headers=self.headers,
            environ={"REQUEST_METHOD": "POST",
                     "CONTENT_TYPE": self.headers["Content-Type"]},
        )
        if path == "/upload":        return self._upload(form)
        if path == "/api/add-images": return self._add_images(form)

    def _upload(self, form):
        title    = form.getfirst("title",       "").strip()
        desc     = form.getfirst("description", "").strip()
        serie_id = form.getfirst("serie",       "").strip()
        year     = form.getfirst("year",        "").strip()
        try:    pix = int(form.getfirst("primary_index", "0"))
        except: pix = 0

        if not title or serie_id not in VALID_SER:
            return self._err("Titolo e serie obbligatori", 400)

        slug      = slugify(title)
        opera_dir = os.path.join(ROOT, serie_id, slug)
        os.makedirs(opera_dir, exist_ok=True)

        data  = load_data()
        serie = next(s for s in data["series"] if s["id"] == serie_id)
        if any(w["id"] == slug for w in serie["works"]):
            return self._err(f"Opera '{slug}' esiste già", 400)

        gallery, thumb_g, canvas_g = save_uploaded_images(form, opera_dir, serie_id, slug, pix)
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
                           "url": f"/opera/{slug}/"})

    def _add_images(self, form):
        s = form.getfirst("serie_id", "").strip()
        w = form.getfirst("work_id",  "").strip()
        if not s or not w or s not in VALID_SER:
            return self._err("Parametri mancanti", 400)
        opera_dir = os.path.join(ROOT, s, w)
        if not os.path.isdir(opera_dir):
            return self._err("Opera non trovata", 404)
        gallery, thumb_g, canvas_g = save_uploaded_images(form, opera_dir, s, w)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if serie:
            work = next((x for x in serie["works"] if x["id"] == w), None)
            if work:
                work.setdefault("gallery",        []).extend(gallery)
                work.setdefault("thumb_gallery",  []).extend(thumb_g)
                work.setdefault("canvas_gallery", []).extend(canvas_g)
                if not work.get("thumb")   and thumb_g:   work["thumb"]   = thumb_g[0]
                if not work.get("canvas")  and canvas_g:  work["canvas"]  = canvas_g[0]
                save_data(data)
        try: regenerate_opera_page(s, w)
        except Exception: pass
        return self._json({"ok": True, "uploaded": len(gallery)})

    # ── JSON endpoints ─────────────────────────────────────────────────────

    def _update_work(self, p):
        s = p.get("serie_id", "").strip()
        w = p.get("work_id",  "").strip()
        if not s or not w:
            return self._err("Parametri mancanti", 400)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie: return self._err("Serie non trovata", 404)
        work = next((x for x in serie["works"] if x["id"] == w), None)
        if not work:  return self._err("Opera non trovata", 404)
        for k in ("title", "year", "description", "description_en"):
            if k in p: work[k] = str(p[k])
        save_data(data)
        # Rigenera pagine opera + griglia serie col nuovo titolo/anno/descrizione
        if s in VALID_SER:
            resync(s, w)
        return self._json({"ok": True})

    def _delete_work(self, p):
        s = p.get("serie_id", "").strip()
        w = p.get("work_id",  "").strip()
        if not s or not w or s not in VALID_SER:
            return self._err("Parametri mancanti", 400)
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie: return self._err("Serie non trovata", 404)
        before = len(serie["works"])
        serie["works"] = [x for x in serie["works"] if x["id"] != w]
        if len(serie["works"]) == before:
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
        if not all([s, w, fn]) or s not in VALID_SER:
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
        # aggiorna JSON
        data  = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if serie:
            work = next((x for x in serie["works"] if x["id"] == w), None)
            if work:
                full = f"{s}/{w}/{fn}"
                work["gallery"]        = [g for g in work.get("gallery",        []) if g != full]
                work["thumb_gallery"]  = [g for g in work.get("thumb_gallery",  []) if os.path.splitext(os.path.basename(g))[0] != base]
                work["canvas_gallery"] = [g for g in work.get("canvas_gallery", []) if os.path.splitext(os.path.basename(g))[0] != base]
                if work.get("image", "").endswith(f"/{fn}"):
                    imgs = list_main_images(s, w)
                    work["image"] = f"{s}/{w}/{imgs[0]}" if imgs else ""
                for key, sub in [("thumb", "thumb"), ("canvas", "canvas")]:
                    if os.path.splitext(os.path.basename(work.get(key, "")))[0] == base:
                        gk = f"{key}_gallery"
                        work[key] = work[gk][0] if work.get(gk) else ""
                save_data(data)
        try: regenerate_opera_page(s, w)
        except Exception: pass
        return self._json({"ok": True})

    def _set_primary(self, p):
        s  = p.get("serie_id", "").strip()
        w  = p.get("work_id",  "").strip()
        fn = p.get("filename", "").strip()
        if not all([s, w, fn]):
            return self._err("Parametri mancanti", 400)
        try:
            swap_primary(s, w, fn)
            try: regenerate_opera_page(s, w)
            except Exception: pass
            return self._json({"ok": True})
        except Exception as e:
            return self._err(str(e), 500)

    def _reorder_works(self, p):
        s = p.get("serie_id", "").strip()
        if not s or s not in VALID_SER:
            return self._err("Serie non valida", 400)
        order = p.get("order", [])
        if not isinstance(order, list) or not order:
            return self._err("Ordine non valido", 400)
        data = load_data()
        serie = next((x for x in data["series"] if x["id"] == s), None)
        if not serie:
            return self._err("Serie non trovata", 404)
        # Valida che tutti gli ID nell'ordine esistono
        work_ids = set(w["id"] for w in serie["works"])
        if set(order) != work_ids:
            return self._err("IDs opera non corrispondenti", 400)
        # Riordina le opere
        work_map = {w["id"]: w for w in serie["works"]}
        serie["works"] = [work_map[wid] for wid in order]
        # Aggiorna position
        for i, work in enumerate(serie["works"]):
            work["position"] = i
        save_data(data)
        # Riordina la griglia nella pagina serie (IT+EN)
        resync(s)
        return self._json({"ok": True})

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

def main():
    os.chdir(ROOT)
    httpd = socketserver.ThreadingTCPServer(("", PORT), Handler)
    httpd.allow_reuse_address = True
    url = f"http://localhost:{PORT}/"
    print(f"\n  Admin — {url}  (Ctrl+C per fermare)\n")
    try: webbrowser.open(url)
    except: pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stop.")
        httpd.shutdown()

if __name__ == "__main__":
    main()
