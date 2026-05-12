#!/usr/bin/env python3
"""Rinomina slug Wix brutti in slug SEO-friendly, mantiene 301 redirect."""

import json
import os
import re
import shutil
import unicodedata

ROOT = "/Users/andrea/Projects/Sito Paola"

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text

def main():
    data = json.load(open(f"{ROOT}/data/series.json"))

    # Costruisci mappa vecchio_slug → nuovo_slug
    mapping = {}  # serie_id → {old_slug: new_slug}
    redirects_pairs = []  # (old_path, new_path) tuples

    for serie in data["series"]:
        serie_dir = serie["id"]
        used = set()
        mapping[serie_dir] = {}
        for w in serie["works"]:
            old = w["id"]
            # Bad slugs: 'my-project', 'progetto-senza-titolo', o solo cifre/codici
            is_bad = old.startswith("my-project") or old.startswith("progetto-senza-titolo") \
                     or bool(re.search(r"-[0-9a-f]{6}$", old)) and "farfalla-5ec760" in old
            new = slugify(w["title"]) if is_bad else old
            # Garantisci unicità all'interno della serie
            base = new; i = 2
            while new in used:
                new = f"{base}-{i}"; i += 1
            used.add(new)
            mapping[serie_dir][old] = new
            if old != new:
                redirects_pairs.append((f"/opera/{old}/", f"/opera/{new}/"))

    # Applica filesystem rename
    n_renamed = 0
    for serie in data["series"]:
        sdir = os.path.join(ROOT, serie["id"])
        for w in serie["works"]:
            old, new = w["id"], mapping[serie["id"]][w["id"]]
            if old == new: continue
            src = os.path.join(sdir, old)
            dst = os.path.join(sdir, new)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.move(src, dst)
                n_renamed += 1

    # Aggiorna JSON: id + image + gallery + thumb + thumb_gallery
    for serie in data["series"]:
        for w in serie["works"]:
            old, new = w["id"], mapping[serie["id"]][w["id"]]
            w["id"] = new
            if old == new: continue
            for k in ("image", "thumb"):
                if w.get(k):
                    w[k] = w[k].replace(f"/{old}/", f"/{new}/")
            for k in ("gallery", "thumb_gallery"):
                if w.get(k):
                    w[k] = [g.replace(f"/{old}/", f"/{new}/") for g in w[k]]

    json.dump(data, open(f"{ROOT}/data/series.json", "w"), ensure_ascii=False, indent=2)

    # Append redirects 301 vecchi slug → nuovi
    redirects_file = f"{ROOT}/_redirects"
    existing = open(redirects_file).read() if os.path.exists(redirects_file) else ""
    new_lines = "\n# 301 redirect slug Wix → SEO-friendly\n"
    for old, new in redirects_pairs:
        new_lines += f"{old}  {new}  301\n"
    if "# 301 redirect slug Wix" not in existing:
        with open(redirects_file, "w") as f:
            f.write(existing + new_lines)

    print(f"Rename: {n_renamed} cartelle")
    print(f"Redirects: {len(redirects_pairs)} aggiunti a _redirects")
    print(f"\nNuovi slug:")
    for sid, m in mapping.items():
        for old, new in m.items():
            if old != new:
                print(f"  {old:42s} → {new}")

if __name__ == "__main__":
    main()
