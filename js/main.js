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
  // La sezione Comel esiste in due lingue: un giurato che sta navigando le
  // pagine inglesi deve restare in inglese anche cliccando questa voce.
  const isEN = (document.documentElement.lang || '').toLowerCase().startsWith('en')
               || location.pathname.startsWith('/en/');
  if (hasComelAccess && !comelLink && navMenu) {
    // Il link non è nell'HTML di questa pagina: lo iniettiamo nel menu,
    // prima dell'ultima voce (Contatti).
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.id = 'comel-nav-link';
    a.href = isEN ? '/en/comel/premio-2026/' : '/comel/premio-2026/';
    a.textContent = isEN ? 'Comel Prize' : 'Premio Comel';
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
    // '' = display naturale (inline, come gli altri link del menu); evita
    // il disallineamento che darebbe 'block' in un menu flex.
    comelLink.style.display = hasComelAccess ? '' : 'none';
  }

  // Highlight active nav link
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('nav a').forEach(link => {
    if (link.getAttribute('href') === page) link.classList.add('active');
  });

  // Selettore di lingua: nessun JavaScript.
  // Ogni pagina ha già nell'HTML i due indirizzi corretti (verificato su tutte
  // e 148 le pagine che lo montano), quindi basta lasciar seguire il link.
  // Il vecchio gestore intercettava il click e RIBALTAVA sempre la lingua,
  // ignorando quale dei due link fosse stato premuto: chi cliccava «IT» stando
  // già su una pagina italiana finiva sulla versione inglese.

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

