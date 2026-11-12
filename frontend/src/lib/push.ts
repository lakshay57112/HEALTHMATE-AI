"use client";
import { api } from "./api";

export function notificationsSupported() {
  return typeof window !== "undefined" && "Notification" in window;
}

export async function registerServiceWorker() {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js");
  } catch {
    return null;
  }
}

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/** Returns a human-readable status. Never pretends background push works when it doesn't. */
export async function enablePush(): Promise<{ ok: boolean; message: string }> {
  if (!notificationsSupported()) return { ok: false, message: "This browser doesn't support notifications." };
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return { ok: false, message: "Notifications are blocked. Allow them in your browser settings." };
  const cfg = await api<{ enabled: boolean; public_key: string | null; note: string | null }>("/notifications/push/config");
  const reg = await registerServiceWorker();
  if (!cfg.enabled || !cfg.public_key) {
    return { ok: true, message: cfg.note || "In-app notifications enabled. Background push is not configured on this server." };
  }
  if (!reg || !("pushManager" in reg)) return { ok: true, message: "Notifications enabled while the app is open. This device does not support background push." };
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(cfg.public_key) });
  const json = sub.toJSON();
  await api("/notifications/push/subscribe", { method: "POST", json: { endpoint: json.endpoint, keys: json.keys } });
  return { ok: true, message: "Background push notifications are on for this device." };
}

export function showLocalNotification(title: string, body: string, url = "/app/medicines/schedule") {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  navigator.serviceWorker?.getRegistration().then((reg) => {
    if (reg) reg.showNotification(title, { body, icon: "/icon.svg", badge: "/icon.svg", data: { url }, tag: title });
    else new Notification(title, { body });
  });
}
