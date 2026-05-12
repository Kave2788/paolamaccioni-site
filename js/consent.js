// Consent Mode v2 + banner cookie GDPR — Paola Maccioni
// Sostituisci G-XXXXXXXXXX con il vero GA4 ID

const GA_ID = 'G-FPHJKXEM94';
const STORAGE_KEY = 'paola-cookie-consent';
const STORAGE_VERSION = 1;

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
  wrap.innerHTML = `
    <div class="cookie-banner-inner">
      <div class="cookie-banner-text">
        <h3>Privacy e cookie</h3>
        <p>Usiamo cookie tecnici per il funzionamento del sito e cookie di analisi (Google Analytics) per capire come viene usato il sito. Puoi accettare, rifiutare o personalizzare le tue scelte. Maggiori dettagli nella <a href="/privacy.html">Privacy Policy</a> e <a href="/cookie-policy.html">Cookie Policy</a>.</p>
      </div>
      <div class="cookie-banner-prefs" hidden>
        <label class="cookie-toggle">
          <input type="checkbox" checked disabled>
          <span><strong>Necessari</strong> — sempre attivi (sicurezza, sessione).</span>
        </label>
        <label class="cookie-toggle">
          <input type="checkbox" data-cookie="analytics">
          <span><strong>Analisi</strong> — Google Analytics aggregato, IP anonimizzato.</span>
        </label>
      </div>
      <div class="cookie-banner-actions">
        <button class="cookie-btn cookie-btn-secondary" data-action="reject">Rifiuta tutti</button>
        <button class="cookie-btn cookie-btn-secondary" data-action="customize">Personalizza</button>
        <button class="cookie-btn cookie-btn-primary" data-action="accept">Accetta tutti</button>
      </div>
      <div class="cookie-banner-actions cookie-banner-save" hidden>
        <button class="cookie-btn cookie-btn-primary" data-action="save">Salva preferenze</button>
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
