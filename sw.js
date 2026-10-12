// Prépa HYROX — fonctionne hors ligne à la salle.
// L'app est servie depuis le cache puis rafraîchie en arrière-plan ; data.json passe d'abord par le réseau.
const CACHE = "prepa-v1";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./data.json", "./icons/icon-180.png", "./icons/icon-192.png", "./icons/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.endsWith("/data.json")) {
    e.respondWith(fetch(e.request, { cache: "no-store" }).then(r => {
      const copy = r.clone(); caches.open(CACHE).then(c => c.put("./data.json", copy)); return r;
    }).catch(() => caches.match("./data.json")));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => {
    const net = fetch(e.request).then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; }).catch(() => hit);
    return hit || net;
  }));
});
