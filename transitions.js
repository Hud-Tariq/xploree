(function () {
  'use strict';

  const PAGE_ORDER = ['index.html', 'identify.html', 'discovery.html', 'memories.html'];

  /* ── ALL inner pages do REAL navigation — no SPA DOM swap ── */
  const HARD_NAVIGATE = ['identify.html', 'discovery.html', 'memories.html', 'profile.html'];

  const pageCache = {};
  let isTransitioning = false;
  let mouseMoveHandler = null;

  /* ── Helpers ── */

  function pageName(href) {
    const s = (href || window.location.pathname).split('/').pop();
    const clean = s.split('?')[0].split('#')[0];
    return clean || 'index.html';
  }

  function currentPage() {
    return pageName(window.location.pathname);
  }

  /* ── Parallax for index cover ── */
  function initParallax() {
    const book = document.getElementById('book');
    if (!book) return;
    if (mouseMoveHandler) document.removeEventListener('mousemove', mouseMoveHandler);
    mouseMoveHandler = function (e) {
      const bookEl = document.getElementById('book');
      if (!bookEl) { document.removeEventListener('mousemove', mouseMoveHandler); mouseMoveHandler = null; return; }
      const x = (e.clientX / window.innerWidth  - 0.5) * 6;
      const y = (e.clientY / window.innerHeight - 0.5) * 4;
      bookEl.style.transform = 'perspective(1000px) rotateY(' + (x * 0.5) + 'deg) rotateX(' + (-y * 0.3) + 'deg)';
    };
    document.addEventListener('mousemove', mouseMoveHandler);
  }

  /* ── Page Preloading (only used for index.html cover animation) ── */
  function preloadPage(url) {
    const cleanUrl = pageName(url);
    if (pageCache[cleanUrl]) return Promise.resolve(pageCache[cleanUrl]);
    return fetch(url)
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
      .then(html => {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        pageCache[cleanUrl] = doc;
        return doc;
      })
      .catch(err => { console.warn('Preload failed', err); });
  }

  /* ── Dynamic Script Execution ── */
  function executeScripts(container) {
    container.querySelectorAll('script').forEach(old => {
      const s = document.createElement('script');
      if (old.src) { if (old.src.indexOf('transitions.js') !== -1) return; s.src = old.src; }
      else { s.textContent = old.textContent; }
      old.parentNode.removeChild(old);
      document.body.appendChild(s);
    });
  }

  /* ── Cover open animation (index → identify only) ── */
  function openCoverTo(url) {
    const cover = document.getElementById('book');
    const decos = document.querySelectorAll('.cover-deco');
    decos.forEach(d => d.classList.add('deco-exit'));
    if (cover) {
      cover.classList.add('cover-opening');
      setTimeout(() => { window.location.href = url; }, 600);
    } else {
      window.location.href = url;
    }
  }

  /* ── Main navigation handler ── */
  function navigateTo(url) {
    if (isTransitioning) return;
    const from = currentPage();
    const to   = pageName(url);
    if (from === to) return;

    isTransitioning = true;

    /* index → first inner page: play cover open then hard navigate */
    if ((from === 'index.html' || from === '') && to !== 'index.html') {
      openCoverTo(url);
      return;
    }

    /* Everything else: just hard navigate — clean, reliable, no DOM swap bugs */
    window.location.href = url;
  }

  /* ── Intercept ALL link clicks ── */
  document.addEventListener('click', function (e) {
    const a = e.target.closest('a[href]');
    if (!a) return;
    const href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#') return;
    if (href.indexOf('http') === 0 || href.indexOf('//') === 0) return;
    if (href.indexOf('mailto:') === 0) return;
    if (href.slice(-5) !== '.html') return;
    e.preventDefault();
    navigateTo(href);
  }, true);

  /* ── Boot ── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initParallax);
  } else {
    initParallax();
  }

})();