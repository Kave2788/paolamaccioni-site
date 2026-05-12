#!/usr/bin/env python3
"""Genera thumbnail uniformi su canvas dark — formato 4:5 portrait, opera intera centrata."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageFilter

ROOT = "/Users/andrea/Projects/Sito Paola"
DATA = f"{ROOT}/data/series.json"

# Canvas: 4:5 portrait (proporzione gallery-pulita), 800x1000
CANVAS_W = 800
CANVAS_H = 1000
BG_COLOR = (24, 22, 20)  # --bg2 #181614
PADDING = 40             # margine interno per non aderire al bordo
QUALITY = 80
SUBFOLDER = "canvas"     # sottocartella accanto a HD per separare dai thumb classici

def make_canvas(src_rel):
    src = os.path.join(ROOT, src_rel)
    if not os.path.exists(src):
        return None
    folder = os.path.dirname(src)
    fname = os.path.basename(src)
    stem = os.path.splitext(fname)[0]
    out_dir = os.path.join(folder, SUBFOLDER)
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, stem + ".webp")
    rel_dest = os.path.join(os.path.dirname(src_rel), SUBFOLDER, stem + ".webp")
    if os.path.exists(dest):
        return rel_dest
    try:
        im = Image.open(src).convert("RGB")
        # Resize mantenendo aspect ratio, dentro area utile (canvas - padding)
        inner_w = CANVAS_W - 2 * PADDING
        inner_h = CANVAS_H - 2 * PADDING
        im.thumbnail((inner_w, inner_h), Image.LANCZOS)

        # Canvas + paste centrato
        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
        x = (CANVAS_W - im.width) // 2
        y = (CANVAS_H - im.height) // 2
        canvas.paste(im, (x, y))
        canvas.save(dest, "webp", quality=QUALITY, method=6)
        return rel_dest
    except Exception as e:
        print(f"FAIL {src_rel}: {e}")
        return None


def main():
    d = json.load(open(DATA))
    tasks = []
    for s in d["series"]:
        for w in s["works"]:
            for g in w.get("gallery", []):
                tasks.append((w, g))

    print(f"Genero {len(tasks)} canvas thumbnail uniformi 4:5…")
    canvas_map = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(make_canvas, t[1]): t[1] for t in tasks}
        done = 0
        for f in as_completed(futs):
            r = f.result()
            if r: canvas_map[futs[f]] = r
            done += 1
            if done % 30 == 0: print(f"  {done}/{len(tasks)}")

    # Aggiorna JSON: campo "canvas" e "canvas_gallery"
    for s in d["series"]:
        for w in s["works"]:
            w["canvas_gallery"] = [canvas_map.get(g, g) for g in w.get("gallery", [])]
            if w.get("image") and canvas_map.get(w["image"]):
                w["canvas"] = canvas_map[w["image"]]

    json.dump(d, open(DATA, "w"), ensure_ascii=False, indent=2)

    # Statistiche
    total = 0
    for s in d["series"]:
        for w in s["works"]:
            for c in w.get("canvas_gallery", []):
                fp = os.path.join(ROOT, c)
                if os.path.exists(fp): total += os.path.getsize(fp)
    print(f"\n✓ {len(canvas_map)} canvas generate, totale {total/1024/1024:.1f} MB")

if __name__ == "__main__":
    main()
