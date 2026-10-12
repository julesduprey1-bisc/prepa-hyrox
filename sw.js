// Prépa HYROX — fonctionne hors ligne à la salle.
// La page et data.json passent d'abord par le réseau (toujours la dernière version), le cache sert hors ligne.
const CACHE = "prepa-v3";
const NOTIF = "prepa-notif"; // carte « date → séances du jour », écrite par l'app
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./data.json", "./icons/icon-180.png", "./icons/icon-192.png", "./icons/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE && k !== NOTIF).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const page = e.request.mode === "navigate" || url.pathname.endsWith("/") || url.pathname.endsWith("/index.html");
  if (page || url.pathname.endsWith("/data.json")) {
    const key = page ? "./index.html" : "./data.json";
    e.respondWith(fetch(e.request, { cache: "no-store" }).then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(key, copy)); } return r;
    }).catch(() => caches.match(key)));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => {
    const net = fetch(e.request).then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; }).catch(() => hit);
    return hit || net;
  }));
});

// Notification du matin : le serveur envoie un simple signal, le texte est composé ici
// à partir du programme et des reports / annulations enregistrés sur le téléphone.
function ymd(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
self.addEventListener("push", e => {
  e.waitUntil((async () => {
    let m = null;
    try { const r = await (await caches.open(NOTIF)).match("./notif.json"); if (r) m = (await r.json())[ymd(new Date())] || null; } catch (err) {}
    await self.registration.showNotification(m ? m.title : "Prépa HYROX", {
      body: m ? m.body : "Ouvre l'app pour voir ta séance du jour.",
      icon: "icons/icon-192.png", badge: "icons/icon-192.png", tag: "jour"
    });
  })());
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(ws => ws.length ? ws[0].focus() : self.clients.openWindow("./")));
});
