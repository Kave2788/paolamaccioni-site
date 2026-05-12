#!/usr/bin/env python3
"""Admin server locale per gestione opere — Paola Maccioni."""

import json
import os
import re
import shutil
import sys
import unicodedata
import http.server
import socketserver
import urllib.parse
import cgi
import webbrowser
from io import BytesIO

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data/series.json")

SERIE_FOLDER = {
    "struttura-tensione": "struttura-tensione",
    "forma-organica": "forma-organica",
}

def slugify(text):
    """Trasforma titolo in slug-url-safe."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text or "opera-senza-titolo"

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.path = "/admin.html"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/upload":
            self.send_error(404)
            return

        ctype, pdict = cgi.parse_header(self.headers.get("Content-Type", ""))
        if ctype != "multipart/form-data":
            self.send_error(400, "Multipart richiesto")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers["Content-Type"]},
        )

        title = form.getfirst("title", "").strip()
        description = form.getfirst("description", "").strip()
        serie_id = form.getfirst("serie", "").strip()
        year = form.getfirst("year", "").strip()
        mode = form.getfirst("mode", "create").strip()  # create | edit
        existing_id = form.getfirst("existing_id", "").strip()

        if not title or not serie_id or serie_id not in SERIE_FOLDER:
            return self.json_response({"error": "Titolo e serie obbligatori"}, 400)

        slug = existing_id if (mode == "edit" and existing_id) else slugify(title)
        opera_dir = os.path.join(ROOT, SERIE_FOLDER[serie_id], slug)
        os.makedirs(opera_dir, exist_ok=True)

        # Salva immagini caricate
        files = form["images"] if "images" in form else None
        uploaded = []
        if files is not None:
            file_list = files if isinstance(files, list) else [files]
            # Numero progressivo basato su file esistenti
            existing = sorted([f for f in os.listdir(opera_dir) if re.match(r"^\d+\.", f)])
            start_idx = len(existing) + 1
            for i, item in enumerate(file_list, start=start_idx):
                if not getattr(item, "filename", None):
                    continue
                ext = os.path.splitext(item.filename)[1].lower() or ".jpg"
                if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                    continue
                fname = f"{i:02d}{ext}"
                fpath = os.path.join(opera_dir, fname)
                with open(fpath, "wb") as out:
                    shutil.copyfileobj(item.file, out)
                uploaded.append(f"{SERIE_FOLDER[serie_id]}/{slug}/{fname}")

        # Aggiorna JSON
        data = load_data()
        serie = next(s for s in data["series"] if s["id"] == serie_id)

        existing_work = next((w for w in serie["works"] if w["id"] == slug), None)
        if existing_work and mode != "edit":
            return self.json_response({"error": f"Opera '{slug}' esiste già. Usa edit."}, 400)

        if existing_work:
            existing_work["title"] = title
            existing_work["description"] = description
            existing_work["year"] = year
            existing_work["gallery"].extend(uploaded)
            if not existing_work.get("image") and existing_work["gallery"]:
                existing_work["image"] = existing_work["gallery"][0]
        else:
            new_work = {
                "id": slug,
                "title": title,
                "year": year,
                "image": uploaded[0] if uploaded else "",
                "gallery": uploaded,
                "description": description,
            }
            serie["works"].append(new_work)

        save_data(data)
        return self.json_response({
            "ok": True,
            "slug": slug,
            "serie": serie_id,
            "uploaded": len(uploaded),
            "url": f"/opera.html?serie={serie_id}&id={slug}",
        })

    def json_response(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def main():
    os.chdir(ROOT)
    addr = ("", PORT)
    httpd = socketserver.ThreadingTCPServer(addr, Handler)
    httpd.allow_reuse_address = True
    url = f"http://localhost:{PORT}/admin.html"
    print(f"\n  Admin server attivo su {url}")
    print("  Apri il browser e gestisci le opere da lì.\n  Ctrl+C per fermare.\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stop.")
        httpd.shutdown()

if __name__ == "__main__":
    main()
