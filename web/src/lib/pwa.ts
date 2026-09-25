// PWA: service worker, Web Push-подписка и установка на главный экран.
import { api } from "@/lib/api";

export type PushState =
  | "unsupported" // браузер не умеет (или открыт внутри Telegram)
  | "ios_install" // iPhone: пуши работают только из установленного приложения
  | "disabled" // сервер без VAPID-ключей
  | "denied" // пользователь запретил в настройках браузера
  | "off"
  | "on";

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;
}

function isIos(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isTelegram(): boolean {
  return Boolean((window as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData);
}

export function registerServiceWorker(): void {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || isTelegram()) return;
  // В dev не регистрируем: кэш сборки мешал бы горячей перезагрузке
  if (process.env.NODE_ENV !== "production") return;
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
}

function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function registration(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  return (await navigator.serviceWorker.getRegistration("/")) ?? null;
}

let keyCache: Promise<string | null> | null = null;
function publicKey(): Promise<string | null> {
  keyCache ??= api<{ public_key: string | null }>("/v1/push/key")
    .then((r) => r.public_key)
    .catch(() => {
      keyCache = null;
      return null;
    });
  return keyCache;
}

export async function pushState(): Promise<PushState> {
  if (isTelegram()) return "unsupported";
  if (!pushSupported()) return isIos() && !isStandalone() ? "ios_install" : "unsupported";
  if (!(await publicKey())) return "disabled";
  if (Notification.permission === "denied") return "denied";
  const reg = await registration();
  const sub = await reg?.pushManager.getSubscription();
  return sub && Notification.permission === "granted" ? "on" : "off";
}

function base64UrlToBytes(value: string): Uint8Array {
  const padded = (value + "=".repeat((4 - (value.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** Включить уведомления на этом устройстве. Возвращает новое состояние. */
export async function enablePush(): Promise<PushState> {
  const key = await publicKey();
  if (!key) return "disabled";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "off";

  let reg = await registration();
  if (!reg) {
    reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  }
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: base64UrlToBytes(key) as BufferSource,
    });
  }
  const json = sub.toJSON();
  await api("/v1/push/subscribe", { method: "POST", json: { endpoint: json.endpoint, keys: json.keys } });
  return "on";
}

/** Выключить на этом устройстве (и при выходе из аккаунта — чтобы чужие уведомления не приходили). */
export async function disablePush(): Promise<void> {
  const sub = await (await registration())?.pushManager.getSubscription().catch(() => null);
  if (!sub) return;
  await api("/v1/push/unsubscribe", { method: "POST", json: { endpoint: sub.endpoint } }).catch(() => undefined);
  await sub.unsubscribe().catch(() => undefined);
}

export async function testPush(): Promise<number> {
  const r = await api<{ delivered: number }>("/v1/push/test", { method: "POST" });
  return r.delivered;
}

// --- Установка на главный экран (Chrome/Edge/Android) ---

type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
let deferred: InstallPrompt | null = null;
const listeners = new Set<() => void>();

let capturing = false;

export function captureInstallPrompt(): void {
  if (typeof window === "undefined" || capturing) return;
  capturing = true;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); // покажем свою кнопку в профиле, а не баннер браузера
    deferred = e as InstallPrompt;
    listeners.forEach((fn) => fn());
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    listeners.forEach((fn) => fn());
  });
}

export function canInstall(): boolean {
  return deferred !== null;
}

export function onInstallChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false;
  const prompt = deferred;
  deferred = null;
  await prompt.prompt();
  const { outcome } = await prompt.userChoice;
  listeners.forEach((fn) => fn());
  return outcome === "accepted";
}

export function iosInstallHint(): boolean {
  return typeof window !== "undefined" && isIos() && !isStandalone() && !isTelegram();
}
