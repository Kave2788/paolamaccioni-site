#!/usr/bin/env python3
"""Inietta consent.js + link privacy/cookie nel legal-bar su tutte le pagine HTML."""

import os
import re
import glob

ROOT = "/Users/andrea/Projects/Sito Paola"

LEGAL_NEW = '<div class="legal-bar">© 2023 PIEMME di Paola Maccioni | C.F MCCPLA80R64B354E | <a href="mailto:infopiemmeart@gmail.com">infopiemmeart@gmail.com</a> | <a href="/privacy.html">Privacy</a> | <a href="/cookie-policy.html">Cookie</a> | <a href="#" data-cookie-settings>Gestisci cookie</a> | Tutti i diritti sono riservati</div>'

LEGAL_HOME = '<p class="legal-bar">© 2023 PIEMME di Paola Maccioni | C.F. MCCPLA80R64B354E | <a href="/privacy.html">Privacy</a> | <a href="/cookie-policy.html">Cookie</a> | <a href="#" data-cookie-settings>Gestisci cookie</a></p>'

CONSENT_TAG = '<script src="/js/consent.js"></script>'
MAIN_TAG = '<script src="/js/main.js"></script>'
MAIN_TAG_REL = '<script src="js/main.js"></script>'

def patch(path):
    with open(path, "r", encoding="utf-8") as f:
        h = f.read()
    original = h

    # 1. Aggiungi consent.js subito dopo main.js se non c'è
    if "consent.js" not in h:
        if MAIN_TAG in h:
            h = h.replace(MAIN_TAG, MAIN_TAG + "\n" + CONSENT_TAG)
        elif MAIN_TAG_REL in h:
            h = h.replace(MAIN_TAG_REL, MAIN_TAG_REL + "\n" + CONSENT_TAG)

    # 2. Aggiorna legal-bar (solo se non già aggiornato)
    is_home = '<p class="legal-bar"' in h
    if "data-cookie-settings" not in h:
        if is_home:
            h = re.sub(r'<p class="legal-bar">[^<]*(?:<[^>]+>[^<]*)*</p>',
                       LEGAL_HOME, h, count=1)
        else:
            h = re.sub(r'<div class="legal-bar">[^<]*(?:<[^>]+>[^<]*)*</div>',
                       LEGAL_NEW, h, count=1)

    if h != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(h)
        return True
    return False

def main():
    targets = []
    for f in glob.glob(f"{ROOT}/*.html"):
        if "admin" not in os.path.basename(f):
            targets.append(f)
    for f in glob.glob(f"{ROOT}/serie/*/index.html"):
        targets.append(f)
    for f in glob.glob(f"{ROOT}/opera/*/index.html"):
        targets.append(f)

    n = 0
    for t in targets:
        if patch(t):
            n += 1
    print(f"✓ {n}/{len(targets)} file patchati")

if __name__ == "__main__":
    main()
