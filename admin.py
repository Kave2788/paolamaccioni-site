#!/usr/bin/env python3
"""Admin server locale — Paola Maccioni."""

import json, os, re, shutil, subprocess, unicodedata
import http.server, socketserver, urllib.parse, cgi, webbrowser
from PIL import Image, ImageOps

PORT       = 8765
ROOT       = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(ROOT, "data/series.json")
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

def regenerate_opera_page(serie_id, work_id):
    """
    Aggiorna le pagine statiche IT e EN dell'opera dopo ogni modifica alle immagini.
    Riscrive: JSON-LD image[], counter 1/N, thumbnail buttons, JS gallery[].
    """
    images = list_main_images(serie_id, work_id)
    n      = len(images)

    try:
        data  = load_data()
        serie = next((s for s in data["series"] if s["id"] == serie_id), None)
        work  = next((w for w in serie["works"] if w["id"] == work_id), None) if serie else None
        title = work["title"] if work else work_id
    except Exception:
        title = work_id

    base_url      = f"https://paola-maccioni.netlify.app/{serie_id}/{work_id}/"
    img_urls      = ", ".join(f'"{base_url}{img}"' for img in images)
    gallery_items = ", ".join(f'"{serie_id}/{work_id}/{img}"' for img in images)
    thumbs_html   = "".join(
        f'<button class="opera-thumb" data-i="{i}" data-src="/{serie_id}/{work_id}/{img}">'
        f'<img src="/{serie_id}/{work_id}/canvas/{os.path.splitext(img)[0]}.webp" '
        f'alt="{title} {i+1}" loading="lazy"></button>'
        for i, img in enumerate(images)
    )

    pages = [
        os.path.join(ROOT, "opera",      work_id, "index.html"),
        os.path.join(ROOT, "en", "opera", work_id, "index.html"),
    ]
    for path in pages:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        # counter 1 / N
        html = re.sub(
            r'(<span class="opera-counter"[^>]*>)1 / \d+(</span>)',
            rf'\g<1>1 / {n}\2', html)

        # JSON-LD "image": [...]
        html = re.sub(
            r'("image": \[)[^\]]+(\])',
            rf'\g<1>{img_urls}\2', html)

        # thumbnail buttons
        html = re.sub(
            r'(<div class="opera-thumbs"[^>]*>)(.*?)(</div>)',
            rf'\g<1>{thumbs_html}\3', html, flags=re.DOTALL)

        # JS gallery array
        html = re.sub(
            r'(const gallery = \[)[^\]]+(\];)',
            rf'\g<1>{gallery_items}\2', html)

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

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
    start = len(existing) + 1
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
            "/api/update-work":  self._update_work,
            "/api/delete-work":  self._delete_work,
            "/api/delete-image": self._delete_image,
            "/api/set-primary":  self._set_primary,
            "/api/publish":      self._publish,
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
        for k in ("title", "year", "description"):
            if k in p: work[k] = str(p[k])
        save_data(data)
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
