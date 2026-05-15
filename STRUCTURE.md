# Struttura del Sito — Paola Maccioni

## 📁 Organizzazione File

```
sito-paola/
├── index.html              # Home Italian (root)
├── bio.html                # Biography Italian
├── portfolio.html          # Portfolio Italian
├── contatti.html           # Contact Italian
├── commissioni.html        # Commissions Italian
├── privacy.html            # Privacy Policy
├── cookie-policy.html      # Cookie Policy
├── serie.html              # Series template (unused)
├── opera.html              # Artwork template (unused)
├── admin.html              # Admin panel (local only)
├── admin.py                # Admin server (local only)
│
├── en/                     # English versions
│   ├── index.html
│   ├── bio.html
│   ├── portfolio.html
│   ├── contatti.html
│   ├── commissioni.html
│   ├── privacy.html
│   ├── cookie-policy.html
│   ├── serie/              # English series pages
│   │   ├── struttura-tensione/index.html
│   │   └── forma-organica/index.html
│   └── opera/              # English artwork pages (51 folders)
│
├── it/                     # Italian versions (legacy, for compatibility)
│   ├── index.html
│   ├── bio.html
│   ├── portfolio.html
│   └── ... (mirrors root pages)
│
├── serie/                  # Italian series pages
│   ├── struttura-tensione/
│   │   └── index.html      # Series page with 28 artworks
│   └── forma-organica/
│       └── index.html      # Series page with 21 artworks
│
├── opera/                  # Italian artwork pages (52 folders)
│   ├── lombra-della-luce/index.html
│   ├── lux-eterna/index.html
│   └── ... (49 total)
│
├── images/                 # Images used in pages
│   ├── home-incide.jpg
│   ├── home-hero.jpg
│   └── ...
│
├── struttura-tensione/     # Artwork images organized by series
│   ├── lombra-della-luce/  # Each artwork folder contains:
│   │   ├── 01.jpg          #   - Original images (numbered)
│   │   ├── 02.jpg          #   - Thumbnails (webp)
│   │   ├── thumb/          #   - Canvas versions (webp)
│   │   └── canvas/
│   └── ... (28 total)
│
├── forma-organica/         # Artwork images (21 folders)
│   ├── globigerina/
│   ├── riccio-di-mare/
│   └── ...
│
├── css/
│   └── main.css            # Main stylesheet (all pages)
│
├── js/
│   ├── main.js             # Main functionality (nav, language toggle, gallery)
│   └── consent.js          # Cookie consent management
│
├── data/
│   └── series.json         # Central data file (49 works, 2 series)
│
├── sitemap.xml             # XML sitemap for search engines
├── robots.txt              # Search engine directives
└── config.json             # Configuration file (GA4 ID, site info)
```

## 🌍 Bilingual Architecture

**Italian (Default)**: `/` (root)
- Pages: `/index.html`, `/bio.html`, `/portfolio.html`, etc.
- Series: `/serie/[serie-id]/`
- Artworks: `/opera/[artwork-id]/`

**English**: `/en/`
- Pages: `/en/index.html`, `/en/bio.html`, `/en/portfolio.html`, etc.
- Series: `/en/serie/[serie-id]/`
- Artworks: `/en/opera/[artwork-id]/`

**Language Toggle**: JavaScript dynamically switches paths based on current location.

---

## 📊 Data

### series.json
Central source of truth for all artwork data:
```json
{
  "series": [
    {
      "id": "struttura-tensione",
      "name": "Struttura e Tensione",
      "year": "2022–2024",
      "works": [
        {
          "id": "lombra-della-luce",
          "title": "L'ombra della luce",
          "image": "struttura-tensione/lombra-della-luce/01.jpg",
          "gallery": [...],
          "description": "..."
        }
      ]
    }
  ]
}
```

---

## 🔧 Key Files Explained

| File | Purpose |
|------|---------|
| `js/main.js` | Navigation, language switcher, gallery reveal |
| `js/consent.js` | Cookie consent banner |
| `css/main.css` | All styling (mobile-first, CSS variables) |
| `data/series.json` | All artwork metadata (49 works) |
| `sitemap.xml` | SEO — tells search engines all pages |
| `robots.txt` | SEO — directs crawlers, blocks admin |
| `config.json` | Global settings (GA4 ID, contact email, etc.) |

---

## 📝 How to Add a New Artwork

1. **Add data to `data/series.json`**:
   ```json
   {
     "id": "new-work",
     "title": "Titolo Opera",
     "year": "2025",
     "image": "serie-folder/new-work/01.jpg",
     "gallery": ["serie-folder/new-work/01.jpg", ...],
     "description": "Description text..."
   }
   ```

2. **Create image folders**:
   ```
   /struttura-tensione/new-work/
     ├── 01.jpg
     ├── 02.jpg
     └── thumb/ (optional WebP versions)
   ```

3. **Language toggle handles the rest** — pages automatically appear in both IT and EN.

---

## 🎨 CSS Architecture

Main file: `css/main.css`

Uses CSS variables for:
- Colors (--platinum, --text, --bg, etc.)
- Fonts (--font-s, --font-ss)
- Spacing & breakpoints

Mobile-first approach: `@media (max-width: 1024px)` for tablet+desktop.

---

## 📱 Responsive Design

- **Mobile**: Single column, font-size adjusts
- **Tablet** (600px+): 2-column grid
- **Desktop** (1024px+): Full layout with sidebar nav

---

## ✅ SEO Setup

- ✓ Sitemap.xml (all 126 pages)
- ✓ robots.txt (allows crawlers, blocks admin)
- ✓ Meta tags (og:locale, og:image, hreflang)
- ✓ Structured data (schema.org for artworks)
- ✓ Google Analytics 4 (tracking ID: G-FPHJKXEM94)
- ✓ Language alternates (hreflang)

---

## 🚀 Deployment

**Hosting**: Netlify (https://paola-maccioni.netlify.app)
**Domain**: paolamaccioni.com (configure DNS)
**Build**: Static site — no build process needed
**Sitemap**: Auto-submitted to Google Search Console

---

## 🔐 Admin Panel

**Local development only** — runs on `http://localhost:8765`

```bash
python3 admin.py
```

Features:
- Upload artwork photos
- Auto-update `data/series.json`
- View recently uploaded works

---

## 📚 For Future Developers

- Keep image paths absolute (`/images/...` not `images/...`)
- Test both `/it/` and `/en/` paths when adding pages
- Update both `sitemap.xml` and `robots.txt` when adding major sections
- GA4 tracking ID is in all `<head>` tags — don't remove!
