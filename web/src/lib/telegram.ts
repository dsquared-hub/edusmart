// Telegram Mini App: https://core.telegram.org/bots/webapps
type TelegramWebApp = {
  initData: string;
  ready: () => void;
  expand: () => void;
  HapticFeedback?: {
    notificationOccurred: (type: "success" | "error" | "warning") => void;
    impactOccurred: (style: "light" | "medium" | "heavy") => void;
  };
};

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function miniApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  const app = window.Telegram?.WebApp;
  return app && app.initData ? app : null;
}

export function haptic(type: "success" | "error") {
  try {
    miniApp()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    /* не во всех клиентах есть вибрация */
  }
}
