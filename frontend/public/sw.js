/* HealthMate service worker — receives Web Push and focuses the app on click. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { title: "HealthMate", body: event.data && event.data.text() }; }
  const title = data.title || "HealthMate reminder";
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || "",
    icon: "/icon.svg",
    badge: "/icon.svg",
    tag: data.id || title,
    data: { url: data.url || "/app/notifications" },
    requireInteraction: data.kind === "medicine_due",
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/app";
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ("focus" in c) { c.navigate(url); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
