// Consent Mode v2 + banner cookie GDPR — Paola Maccioni
// Sostituisci G-XXXXXXXXXX con il vero GA4 ID

const GA_ID = 'G-FPHJKXEM94';
const STORAGE_KEY = 'paola-cookie-consent';
const STORAGE_VERSION = 1;

// === Lingua ===
// Le pagine inglesi hanno <html lang="en"> e stanno sotto /en/: si guardano
// entrambi, così il banner resta corretto anche se una pagina perde l'attributo.
const LANG = ((document.documentElement.lang || '').toLowerCase().startsWith('en')
              || location.pathname.startsWith('/en/')) ? 'en' : 'it';

const TESTI = {
  it: {
    titolo:      'Privacy e cookie',
    descrizione: 'Usiamo cookie tecnici per il funzionamento del sito e cookie di analisi '
               + '(Google Analytics) per capire come viene usato il sito. Puoi accettare, '
               + 'rifiutare o personalizzare le tue scelte. Maggiori dettagli nella '
               + '<a href="/privacy.html">Privacy Policy</a> e '
               + '<a href="/cookie-policy.html">Cookie Policy</a>.',
    necessari:   '<strong>Necessari</strong> — sempre attivi (sicurezza, sessione).',
    analisi:     '<strong>Analisi</strong> — Google Analytics aggregato, IP anonimizzato.',
    rifiuta:     'Rifiuta tutti',
    personalizza:'Personalizza',
    accetta:     'Accetta tutti',
    salva:       'Salva preferenze',
  },
  en: {
    titolo:      'Privacy and cookies',
    descrizione: 'We use technical cookies to run the site and analytics cookies '
               + '(Google Analytics) to understand how it is used. You can accept, '
               + 'reject or customise your choices. More details in the '
               + '<a href="/en/privacy.html">Privacy Policy</a> and '
               + '<a href="/en/cookie-policy.html">Cookie Policy</a>.',
    necessari:   '<strong>Necessary</strong> — always on (security, session).',
    analisi:     '<strong>Analytics</strong> — aggregated Google Analytics, anonymised IP.',
    rifiuta:     'Reject all',
    personalizza:'Customise',
    accetta:     'Accept all',
    salva:       'Save preferences',
  },
}[LANG];

// === Google Consent Mode v2: default deny ===
window.dataLayer = window.dataLayer || [];
function gtag(){ dataLayer.push(arguments); }
gtag('consent', 'default', {
  ad_storage: 'denied',
  ad_user_data: 'denied',
  ad_personalization: 'denied',
  analytics_storage: 'denied',
  functionality_storage: 'granted',
  security_storage: 'granted',
  wait_for_update: 500,
});
gtag('js', new Date());

// === State ===
function loadConsent() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const c = JSON.parse(raw);
    if (c.v !== STORAGE_VERSION) return null;
    // Consenso scade dopo 12 mesi
    if (Date.now() - c.t > 365 * 24 * 3600 * 1000) return null;
    return c;
  } catch { return null; }
}

function saveConsent(prefs) {
  const c = { v: STORAGE_VERSION, t: Date.now(), ...prefs };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(c));
  applyConsent(c);
}

function applyConsent(c) {
  gtag('consent', 'update', {
    analytics_storage: c.analytics ? 'granted' : 'denied',
    ad_storage: c.marketing ? 'granted' : 'denied',
    ad_user_data: c.marketing ? 'granted' : 'denied',
    ad_personalization: c.marketing ? 'granted' : 'denied',
  });
  if (c.analytics && !window.__gaLoaded) loadGA();
}

function loadGA() {
  if (GA_ID === 'G-XXXXXXXXXX') return; // placeholder, skip
  window.__gaLoaded = true;
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);
  gtag('config', GA_ID, { anonymize_ip: true });
}

// === Banner UI ===
function buildBanner(initialMode = 'simple') {
  const wrap = document.createElement('div');
  wrap.className = 'cookie-banner';
  wrap.lang = LANG;
  wrap.innerHTML = `
    <div class="cookie-banner-inner">
      <div class="cookie-banner-text">
        <h3>${TESTI.titolo}</h3>
        <p>${TESTI.descrizione}</p>
      </div>
      <div class="cookie-banner-prefs" hidden>
        <label class="cookie-toggle">
          <input type="checkbox" checked disabled>
          <span>${TESTI.necessari}</span>
        </label>
        <label class="cookie-toggle">
          <input type="checkbox" data-cookie="analytics">
          <span>${TESTI.analisi}</span>
        </label>
      </div>
      <div class="cookie-banner-actions">
        <button class="cookie-btn cookie-btn-secondary" data-action="reject">${TESTI.rifiuta}</button>
        <button class="cookie-btn cookie-btn-secondary" data-action="customize">${TESTI.personalizza}</button>
        <button class="cookie-btn cookie-btn-primary" data-action="accept">${TESTI.accetta}</button>
      </div>
      <div class="cookie-banner-actions cookie-banner-save" hidden>
        <button class="cookie-btn cookie-btn-primary" data-action="save">${TESTI.salva}</button>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);

  const prefsEl = wrap.querySelector('.cookie-banner-prefs');
  const actionsEl = wrap.querySelector('.cookie-banner-actions');
  const saveEl = wrap.querySelector('.cookie-banner-save');

  wrap.addEventListener('click', e => {
    const a = e.target.dataset.action;
    if (!a) return;
    if (a === 'accept') {
      saveConsent({ analytics: true, marketing: false });
      close();
    } else if (a === 'reject') {
      saveConsent({ analytics: false, marketing: false });
      close();
    } else if (a === 'customize') {
      prefsEl.hidden = false;
      actionsEl.hidden = true;
      saveEl.hidden = false;
    } else if (a === 'save') {
      const analytics = wrap.querySelector('[data-cookie="analytics"]').checked;
      saveConsent({ analytics, marketing: false });
      close();
    }
  });

  function close() { wrap.classList.add('cookie-banner-closing'); setTimeout(() => wrap.remove(), 300); }

  if (initialMode === 'customize') {
    prefsEl.hidden = false;
    actionsEl.hidden = true;
    saveEl.hidden = false;
    // Precompila con preferenze attuali
    const c = loadConsent();
    if (c) wrap.querySelector('[data-cookie="analytics"]').checked = !!c.analytics;
  }

  requestAnimationFrame(() => wrap.classList.add('cookie-banner-show'));
}

// === Init ===
document.addEventListener('DOMContentLoaded', () => {
  const c = loadConsent();
  if (c) {
    applyConsent(c);
  } else {
    buildBanner('simple');
  }

  // Link "Gestisci cookie" (chiama dal footer/legal-bar)
  document.querySelectorAll('[data-cookie-settings]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      if (!document.querySelector('.cookie-banner')) buildBanner('customize');
    });
  });
});
