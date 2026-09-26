// Service worker EDU: установка как приложение, офлайн-заглушка и Web Push.
// API не кэшируем никогда — там личные данные; страницы всегда берём из сети.
const VERSION = "edu-v2"; // новая модель в /models/ — поменяй версию, чтобы сбросить кэш
const SHELL = ["/offline.html", "/icons/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  // Страницы: сеть, без сети — офлайн-заглушка
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match("/offline.html")));
    return;
  }
  // Сборка Next (имена с хешем, не меняются) и 3D-модели: сначала кэш
  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/models/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(VERSION).then((c) => c.put(req, copy));
            }
            return res;
          }),
      ),
    );
  }
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "EDU", {
      body: data.body || "",
      tag: data.tag || undefined,
      renotify: Boolean(data.tag),
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      lang: data.lang || undefined,
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin);
  if (target.origin !== self.location.origin) return; // открываем только свои страницы
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (new URL(w.url).origin === target.origin && "focus" in w) {
          return w.focus().then((c) => (c && "navigate" in c ? c.navigate(target.href) : c));
        }
      }
      return self.clients.openWindow(target.href);
    }),
  );
});
