# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**paolamaccioni.com** is a bilingual static portfolio for Paola Maccioni, a contemporary aluminum sculptor (brand PIEMME). The site showcases 49 artworks across 2 series with full Italian and English versions. Hosted on Netlify, no build process required.

## Key Architecture

### Bilingual Structure
- **Italian (default)**: `/` root — `/index.html`, `/bio.html`, `/opera/[id]/`, `/serie/[id]/`
- **English**: `/en/` prefix — `/en/index.html`, `/en/bio.html`, `/en/opera/[id]/`, `/en/serie/[id]/`
- **Language Toggle**: `js/main.js` dynamically switches paths. The language switcher converts `/something` ↔ `/en/something`
- **Backwards Compatibility**: `/it/` legacy paths auto-redirect via `_redirects` (Netlify)

### Single Source of Truth: `data/series.json`
All artwork metadata (49 works, 2 series) is centralized here. The structure:
```json
{
  "series": [
    {
      "id": "struttura-tensione",
      "name": "Materia e Trasformazione",
      "year": "2022–2024",
      "works": [
        {
          "id": "lombra-della-luce",
          "title": "L'ombra della luce",
          "year": "",
          "image": "struttura-tensione/lombra-della-luce/01.jpg",
          "gallery": [...],
          "thumb_gallery": [...],
          "canvas_gallery": [...],
          "description": "...",
          "description_en": "...",
          "thumb": "...",
          "canvas": "..."
        }
      ]
    }
  ]
}
```
Every artwork page (HTML) dynamically reads from this JSON via script tags.

### File Organization
```
.
├── Root Italian Pages: index.html, bio.html, portfolio.html, commissioni.html, contatti.html, privacy.html, cookie-policy.html
├── en/                 # English page duplicates
├── opera/              # Italian artwork pages (52 folders, auto-generated from series.json)
├── serie/              # Italian series listing pages
├── it/                 # Legacy Italian paths (redirect to root)
├── [series-folders]/   # Image directories (struttura-tensione/, forma-organica/)
│   └── [artwork-id]/   # One folder per artwork
│       ├── 01.jpg, 02.jpg, ...   # Full-res originals
│       ├── thumb/                 # WebP thumbnails
│       └── canvas/                # Dark-background WebP (800×1000)
├── data/series.json    # Central metadata
├── css/main.css        # All styles (CSS variables, mobile-first)
├── js/main.js          # Nav, lang toggle, scroll reveal
├── js/consent.js       # Cookie consent
├── config.json         # Site config (GA4 ID, artist info, etc.)
└── sitemap.xml, robots.txt, _redirects
```

### Page Generation Pattern
Artwork pages are **static HTML** but dynamically populate from `data/series.json`. E.g. `/opera/lombra-della-luce/index.html` contains a script that:
1. Fetches `../../../data/series.json`
2. Finds the matching artwork by ID
3. Renders title, description, gallery, etc. into the DOM

Same pattern for series pages and portfolio listings.

### Styling Architecture
- **Main file**: `css/main.css` (all-in-one, ~1500 lines)
- **Design system**: CSS variables in `:root` (colors, fonts, spacing)
  - Colors: `--bg`, `--text`, `--muted`, `--accent`, `--platinum`, `--border`, `--bg2`, `--text2`
  - Fonts: `--font-s` (Georgia serif), `--font-ss` (system sans)
- **Responsive**: Mobile-first with `@media (max-width: 1024px)` for tablet+desktop
- **No build tool**: Pure CSS, no preprocessing

### JavaScript
- **main.js**: Nav highlight, language switcher, mobile hamburger, scroll-reveal for gallery tiles using IntersectionObserver
- **consent.js**: Cookie consent banner (loads config.json for GA4 ID)
- **No frameworks**: Vanilla JS only

## Common Development Tasks

### Running Locally
```bash
python3 -m http.server 8000
# Open http://localhost:8000
```

### Admin Panel (Image Upload & Processing)
Local-only tool for uploading artwork images and auto-updating `data/series.json`.
```bash
python3 admin.py
# Open http://localhost:8765
```

**What it does**:
- Accepts image uploads per series + artwork ID
- Auto-generates three variants per image:
  - `main/`: Full-res JPEG (1400px, 85q)
  - `thumb/`: WebP thumbnail (800px, 82q)
  - `canvas/`: Dark-background WebP (800×1000 on `--bg` color, 82q)
- Updates `data/series.json` with new gallery arrays and image paths
- Stores images in correct directory structure

**`admin.py` is tracked on purpose.** The launcher on Paola's PC updates itself with `git pull`, so the file has to live in git — do not "clean it up" out of the repo. It still never reaches the public site: `.netlifyignore` keeps it out of the deploy, and `_redirects` (`/admin.py` → 404) plus `robots.txt` block it. The `admin.py` line in `.gitignore` is inert, since the file was already tracked before it was added.

**Never commit** test uploads — the images created while trying the panel out.

### Adding a New Artwork
1. **Update `data/series.json`**:
   - Add object to appropriate series' `works` array
   - Set `id`, `title`, `year`, `description`, `description_en`
   - Set `image` path (e.g., `"struttura-tensione/nuovo-nome/01.jpg"`)
   - Set `gallery`, `thumb_gallery`, `canvas_gallery` arrays with all image paths
   - Set `thumb` (single thumbnail path) and `canvas` paths

2. **Upload images**:
   - Use admin panel, or manually create directory structure:
     ```
     /struttura-tensione/nuovo-nome/
       ├── 01.jpg, 02.jpg, ...
       ├── thumb/ (01.webp, 02.webp, ...)
       └── canvas/ (01.webp, 02.webp, ...)
     ```

3. **Regenerate static pages** (if needed):
   - Artwork pages auto-populate from JSON — no regeneration needed
   - Portfolio listing (`portfolio.html`) and series pages (`serie/*/index.html`) also read from JSON dynamically

4. **Update sitemap & robots.txt**:
   - If adding a major section, add entries to `sitemap.xml`
   - Update `robots.txt` if needed (currently allows all crawlers except `/admin`)

### Adding a New Series
1. Add entry to `config.json` (informational only):
   ```json
   {
     "id": "new-series",
     "name": "New Series Name",
     "year_range": "2024–2025",
     "work_count": 0
   }
   ```

2. Add series object to `data/series.json`:
   ```json
   {
     "id": "new-series",
     "name": "New Series Name",
     "year": "2024–2025",
     "description": "...",
     "description_en": "...",
     "works": [...]
   }
   ```

3. Manually create `/new-series/index.html` listing page (can copy from existing `serie/struttura-tensione/index.html`)
   - Update title, series ID in the script tag
   - English version goes in `/en/serie/new-series/index.html`

### Updating Content Across Both Languages
When modifying text:
- Modify both **Italian** (root) and **English** (`/en/`) versions
- For metadata in `data/series.json`: both `description` and `description_en` fields
- For pages: update both root and `/en/` versions

**Helper**: Recent commits show bulk edits using find/replace across all language variants.

### SEO Maintenance
- **Sitemap**: Update `sitemap.xml` when adding major pages (series, key artworks)
- **Robots**: Keep `/admin` blocked (`Disallow: /admin`)
- **Meta tags**: All pages have proper `og:locale`, `og:image`, `hreflang` (language alternates)
- **Structured data**: Artwork pages use schema.org `ArtworkSchema` in JSON-LD
- **GA4**: Tracking ID `G-FPHJKXEM94` in config.json — automatically inserted into all pages via `consent.js`

### Contact Form
Currently uses **Formspree** (recent switch from Netlify Forms):
- Form submission endpoint: configured in `contatti.html` and `/en/contatti.html`
- No backend needed — Formspree handles email delivery
- Configuration in HTML form action attribute

## Key Files Reference

| File | Purpose |
|------|---------|
| `data/series.json` | Single source of truth: all 49 artworks + 2 series |
| `config.json` | Site metadata (GA4 ID, artist name, etc.) |
| `js/main.js` | Nav, language toggle, mobile menu, scroll reveal |
| `js/consent.js` | Cookie banner, GA4 injection |
| `css/main.css` | All styling (design system via CSS vars, mobile-first) |
| `admin.py` | Image upload + processing (local dev only) |
| `sitemap.xml` | 126 pages, submitted to Google Search Console |
| `robots.txt` | Crawler directives (allows all except `/admin`) |
| `_redirects` | Netlify redirects: `/it/` → `/` paths |
| `netlify.toml` | Netlify config: cache headers, no build command |

## Deployment

**Platform**: Netlify (static site, no build)
**Domain**: paolamaccioni.com
**Build**: None required — push to git, Netlify auto-publishes

- CSS/JS/images cached for 1 year (cache-busting via `netlify.toml`)
- HTML cached for 1 hour
- All pages served from root `./` directory

## Language Toggle Implementation

The language switcher in `nav` converts current path:
- `location.pathname` → extract language and relative path
- If Italian (root or `/it/`): switch to `/en/{relativePath}`
- If English (`/en/`): switch to `/{relativePath}`

**Example flows**:
- `/opera/lombra-della-luce/` → `/en/opera/lombra-della-luce/`
- `/en/bio.html` → `/bio.html`
- `/en/index.html` → `/index.html`

Legacy `/it/` paths redirect to root via `_redirects`.

## Important Conventions

### Paths
- Use **absolute paths** for images and links: `/images/...`, `/opera/...`, not relative
- Language paths: `/en/` for English, nothing for Italian (root is default)
- Series/artwork IDs use kebab-case: `struttura-tensione`, `lombra-della-luce`

### Image Handling
- All artwork images stored in series folders: `/{serie-id}/{artwork-id}/`
- Three variants per image:
  - `01.jpg` (full-res, JPEG)
  - `thumb/01.webp` (thumbnail, WebP)
  - `canvas/01.webp` (800×1000, dark background, WebP)
- Use admin panel to auto-generate variants

### Data Consistency
- Update `data/series.json` as single source
- Artwork pages auto-render from JSON — no manual HTML editing per artwork
- Sitemap and canonical tags reflect live URLs

### Testing
- Test both `/it/` legacy redirects and root Italian paths
- Test both `/` root and `/en/` language toggle flows
- Verify gallery image paths resolve correctly
- Check GA4 tracking fires (open DevTools → Network, look for `google-analytics`)

## Notes for Future Work

- All pages use **dynamic rendering from JSON** — scaling to more artworks requires only `data/series.json` updates
- No build step keeps development workflow simple: edit, save, refresh
- Static site means fast CDN delivery and zero server costs
- Admin panel not deployed — image uploads are local-only workflow
