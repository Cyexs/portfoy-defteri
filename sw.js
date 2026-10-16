// Portföy Defteri: keeps the app usable offline. Prices are fetched fresh when online.
const CACHE = 'portfoy-defteri-v10';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192-v2.png', 'icons/icon-512-v2.png', 'icons/apple-touch-icon-v2.png', 'icons/icon-maskable-512-v2.png', 'icons/favicon-64-v2.png'];
// Small JSON files that change: always network first, last copy when offline.
const TAZE = ['fiyatlar.json', 'api.json', 'firebase-ayar.json', 'manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

// Outside files kept for offline use: fonts and the versioned Firebase library. Sign-in and database traffic is never touched.
const disaridanSakla = (url) => url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com' || (url.hostname === 'www.gstatic.com' && url.pathname.startsWith('/firebasejs/'));

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.origin !== location.origin && !disaridanSakla(url)) return;
  const taze = url.origin === location.origin && TAZE.find((f) => url.pathname.endsWith(f));
  if (taze) {
    e.respondWith(fetch(e.request).then((r) => { const copy = r.clone(); if (r.ok) caches.open(CACHE).then((c) => c.put(taze, copy)); return r; }).catch(() => caches.match(taze)));
    return;
  }
  // App page: network first so updates arrive, cache when offline.
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put('index.html', copy)); return r; }).catch(() => caches.match('index.html')));
    return;
  }
  // Everything else (icons, fonts, Firebase library): cache first, then network.
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
    return r;
  })));
});
