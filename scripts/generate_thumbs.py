#!/usr/bin/env python3
"""Genera thumbnail WebP 600px per miniature. HD originali restano intatti."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

ROOT = "/Users/andrea/Projects/Sito Paola"
DATA = os.path.join(ROOT, "data/series.json")
THUMB_MAX = 800  # max side per thumbnail
THUMB_QUALITY = 78
THUMB_DIR_NAME = "thumb"  # sottocartella accanto a HD

def make_thumb(src_rel):
    src = os.path.join(ROOT, src_rel)
    if not os.path.exists(src):
        return None
    folder = os.path.dirname(src)
    fname = os.path.basename(src)
    stem = os.path.splitext(fname)[0]
    thumb_dir = os.path.join(folder, THUMB_DIR_NAME)
    os.makedirs(thumb_dir, exist_ok=True)
    dest = os.path.join(thumb_dir, stem + ".webp")
    rel_dest = os.path.join(os.path.dirname(src_rel), THUMB_DIR_NAME, stem + ".webp")
    if os.path.exists(dest):
        return rel_dest
    try:
        im = Image.open(src)
        im.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        im.save(dest, "webp", quality=THUMB_QUALITY, method=6)
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

    print(f"Genero {len(tasks)} thumbnails…")
    thumb_map = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(make_thumb, t[1]): t[1] for t in tasks}
        done = 0
        for f in as_completed(futs):
            r = f.result()
            if r:
                thumb_map[futs[f]] = r
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(tasks)}")

    # Aggiungi campo "thumb_gallery" e "thumb" al JSON
    for s in d["series"]:
        for w in s["works"]:
            w["thumb_gallery"] = [thumb_map.get(g, g) for g in w.get("gallery", [])]
            if w.get("image"):
                w["thumb"] = thumb_map.get(w["image"], w["image"])

    json.dump(d, open(DATA, "w"), ensure_ascii=False, indent=2)
    # Calcola peso
    total_thumb = 0
    for s in d["series"]:
        for w in s["works"]:
            for t in w.get("thumb_gallery", []):
                fp = os.path.join(ROOT, t)
                if os.path.exists(fp):
                    total_thumb += os.path.getsize(fp)
    print(f"\nThumb totali: {len(thumb_map)} file, {total_thumb/1024/1024:.1f} MB")

if __name__ == "__main__":
    main()
