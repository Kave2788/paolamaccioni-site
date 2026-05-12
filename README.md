# paolamaccioni.com

Portfolio moderno per Paola Maccioni — scultrice contemporanea in alluminio (brand PIEMME).

## Struttura

```
.
├── index.html          Home — hero con citazione
├── bio.html            Biografia
├── portfolio.html      Serie sculturali → dettaglio opere
├── commissioni.html    Lavori su commissione
├── contatti.html       Form di contatto
├── css/main.css        Tutti gli stili
├── js/main.js          Navigazione base
├── js/portfolio.js     Logica serie e opere
├── data/series.json    Dati: serie, opere, descrizioni, immagini
└── images/             Foto delle sculture
```

## Aggiornare i contenuti

Modifica `data/series.json` per aggiungere/modificare serie e opere.

### Aggiungere una serie
```json
{
  "id": "nome-serie",
  "name": "Nome Serie",
  "year": "2023–2024",
  "description": "Descrizione breve della serie",
  "works": [...]
}
```

### Aggiungere un'opera
```json
{
  "id": "id-univoco",
  "title": "Titolo Opera",
  "year": 2024,
  "image": "images/nome-file.jpg",
  "description": "Descrizione filosofica dell'opera."
}
```

## Avviare in locale

```bash
python3 -m http.server 8000
# apri http://localhost:8000
```

## Deploy

### Vercel (consigliato)
```bash
npm i -g vercel && vercel
```

### Netlify
```bash
npm i -g netlify-cli && netlify deploy --prod --dir=.
```

### GitHub Pages
Settings → Pages → Source: main branch → root

## Contenuti da fornire

- [ ] Foto alta risoluzione delle sculture (min 1200px)
- [ ] Nomi e descrizioni delle serie
- [ ] Titoli, anni e testi filosofici delle opere
- [ ] Foto profilo per la pagina biografia
- [ ] Testo biografico aggiornato

© 2024 PIEMME di Paola Maccioni
