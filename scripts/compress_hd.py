#!/usr/bin/env python3
"""Comprime HD originali in-place a 1400px max, qualità 82."""

import os, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

ROOT = "/Users/andrea/Projects/Sito Paola"
MAX_DIM = 1400
QUALITY = 82

def compress(path):
    try:
        size_before = os.path.getsize(path)
        im = Image.open(path)
        if max(im.size) <= MAX_DIM:
            return (path, size_before, size_before)
        im.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        # Usa lo stesso path/estensione
        ext = os.path.splitext(path)[1].lower()
        fmt = "JPEG" if ext in (".jpg", ".jpeg") else "WEBP" if ext == ".webp" else None
        if not fmt: return (path, size_before, size_before)
        im.save(path, fmt, quality=QUALITY, optimize=True)
        size_after = os.path.getsize(path)
        return (path, size_before, size_after)
    except Exception as e:
        return (path, 0, 0)

def main():
    d = json.load(open(f"{ROOT}/data/series.json"))
    paths = []
    for s in d["series"]:
        for w in s["works"]:
            for g in w.get("gallery", []):
                p = os.path.join(ROOT, g)
                if os.path.exists(p): paths.append(p)
    print(f"Comprimo {len(paths)} HD…")

    total_before = total_after = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(compress, p) for p in paths]
        done = 0
        for f in as_completed(futs):
            _, b, a = f.result()
            total_before += b
            total_after += a
            done += 1
            if done % 30 == 0: print(f"  {done}/{len(paths)}")
    print(f"\nPrima: {total_before/1024/1024:.0f} MB")
    print(f"Dopo:  {total_after/1024/1024:.0f} MB")
    print(f"Risparmio: {(1-total_after/total_before)*100:.0f}%")

if __name__ == "__main__":
    main()
