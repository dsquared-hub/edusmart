"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { AuthProvider, useAuth } from "@/lib/auth";
import { I18nProvider, isLang, type Lang } from "@/lib/i18n";
import { captureInstallPrompt, registerServiceWorker } from "@/lib/pwa";
import { applySettings, SETTINGS_CACHE_KEY } from "@/lib/settings";

function cachedLang(): Lang | null {
  try {
    const lang = JSON.parse(localStorage.getItem(SETTINGS_CACHE_KEY) || "{}").lang;
    return isLang(lang) ? lang : null;
  } catch {
    return null;
  }
}

/** Язык: у вошедшего — из профиля (общий с ботом), у гостя — из браузера. */
function LocalizedApp({ children }: { children: ReactNode }) {
  const { me, saveSettings } = useAuth();
  const [guestLang, setGuestLang] = useState<Lang>("ru");

  useEffect(() => {
    const cached = cachedLang();
    if (cached) setGuestLang(cached);
  }, []);

  const profileLang = me?.settings.lang;
  const lang: Lang = isLang(profileLang) ? profileLang : guestLang;

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback(
    (next: Lang) => {
      setGuestLang(next);
      if (me) saveSettings({ lang: next }).catch(() => undefined);
      else applySettings({ lang: next });
    },
    [me, saveSettings],
  );

  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <AppShell>{children}</AppShell>
    </I18nProvider>
  );
}

export function Providers({ children }: { children: ReactNode }) {
  useEffect(() => {
    captureInstallPrompt();
    registerServiceWorker();
  }, []);

  return (
    <AuthProvider>
      <LocalizedApp>{children}</LocalizedApp>
    </AuthProvider>
  );
}
