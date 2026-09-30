// Vigie : permet d'ouvrir l'application sans réseau (métro, tunnel).
// Fichiers de l'app : réseau d'abord (toujours la dernière version), copie locale en secours.
// Outils Firebase et polices : copie locale d'abord (ils ne changent pas).
// Le relais (/api/) n'est jamais mis en cache : les offres restent en temps réel.
const CACHE = "vigie-v1";
const COQUILLE = ["/", "/index.html", "/styles.css", "/app.js", "/firebase.js", "/manifest.webmanifest", "/icone-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(COQUILLE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((cles) => Promise.all(cles.filter((c) => c !== CACHE).map((c) => caches.delete(c))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) return;

  const immuable = url.hostname === "www.gstatic.com" || url.hostname.endsWith("fonts.gstatic.com") || url.hostname === "fonts.googleapis.com";
  if (immuable) {
    e.respondWith(
      caches.match(req).then((copie) => copie || fetch(req).then((rep) => {
        if (rep.ok) { const clone = rep.clone(); caches.open(CACHE).then((c) => c.put(req, clone)); }
        return rep;
      }))
    );
    return;
  }
  if (url.origin !== self.location.origin) return;

  e.respondWith(
    fetch(req).then((rep) => {
      if (rep.ok) { const clone = rep.clone(); caches.open(CACHE).then((c) => c.put(req, clone)); }
      return rep;
    }).catch(() => caches.match(req).then((copie) => copie || caches.match("/index.html")))
  );
});
