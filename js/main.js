document.addEventListener('DOMContentLoaded', function () {
  // Premio Comel: accesso persistente per i giudici.
  // Chi entra da /comel/ riceve un flag nel browser: da quel momento il link
  // "Premio Comel" resta nel menu su tutte le pagine, così può navigare
  // liberamente il sito e tornare alla sezione quando vuole.
  // I visitatori normali non hanno il flag e non vedono nulla.
  if (location.pathname.includes('/comel/')) {
    try { localStorage.setItem('comelAccess', '1'); } catch (e) {}
  }
  let hasComelAccess = false;
  try { hasComelAccess = localStorage.getItem('comelAccess') === '1'; } catch (e) {}

  let comelLink = document.getElementById('comel-nav-link');
  const navMenu = document.querySelector('nav ul');
  if (hasComelAccess && !comelLink && navMenu) {
    // Il link non è nell'HTML di questa pagina: lo iniettiamo nel menu,
    // prima dell'ultima voce (Contatti).
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.id = 'comel-nav-link';
    a.href = '/comel/premio-2026/';
    a.textContent = 'Premio Comel';
    li.appendChild(a);
    const items = navMenu.querySelectorAll('li');
    if (items.length) {
      navMenu.insertBefore(li, items[items.length - 1]);
    } else {
      navMenu.appendChild(li);
    }
    comelLink = a;
  }
  if (comelLink) {
    comelLink.style.display = hasComelAccess ? 'block' : 'none';
  }

  // Highlight active nav link
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('nav a').forEach(link => {
    if (link.getAttribute('href') === page) link.classList.add('active');
  });

  // Language switcher: toggle between /it/ and /en/
  const langLinks = document.querySelectorAll('.lang-switcher a');
  langLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const currentPath = location.pathname;
      let newPath;

      // Determina lingua attuale e percorso relativo
      let currentLang, relativePath;

      if (currentPath.startsWith('/en/')) {
        currentLang = 'en';
        relativePath = currentPath.slice(4); // Rimuovi '/en/'
      } else if (currentPath.startsWith('/it/')) {
        currentLang = 'it';
        relativePath = currentPath.slice(4); // Rimuovi '/it/'
      } else {
        // Root (/ o /index.html, /bio.html, etc) è considerato italiano
        currentLang = 'it';
        relativePath = currentPath.replace(/^\//, ''); // Rimuovi leading '/'
      }

      // Costruisci il nuovo percorso
      if (currentLang === 'it') {
        newPath = '/en/' + relativePath;
      } else {
        newPath = '/' + (relativePath || '');
      }

      location.href = newPath;
    });
  });

  // Mobile nav toggle
  const toggle = document.querySelector('.nav-toggle');
  const menu = document.querySelector('nav ul');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('open');
      menu.classList.toggle('open');
    });
    menu.querySelectorAll('a').forEach(a =>
      a.addEventListener('click', () => {
        toggle.classList.remove('open');
        menu.classList.remove('open');
      })
    );
  }

  // Scroll reveal for gallery tiles
  const tiles = document.querySelectorAll('.work-tile');
  if (tiles.length) {
    tiles.forEach((t, i) => {
      t.style.transitionDelay = `${(i % 6) * 0.07}s`;
    });
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.08 });
    tiles.forEach(t => io.observe(t));
  }
});

