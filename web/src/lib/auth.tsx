"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setApiToken, setUnauthorizedHandler } from "./api";
import { applySettings } from "./settings";
import { miniApp } from "./telegram";
import type { Me, UserSettings } from "./types";

const TOKEN_KEY = "edu.token";

type Status = "loading" | "guest" | "authed";

type AuthState = {
  status: Status;
  me: Me | null;
  isMiniApp: boolean;
  /** Mini App внутри бота: вход по initData */
  loginTelegram: (payload: { init_data: string }) => Promise<void>;
  loginCode: (login: string, code: string) => Promise<void>;
  logout: () => void;
  logoutEverywhere: () => Promise<void>;
  refresh: () => Promise<void>;
  saveSettings: (patch: Partial<UserSettings>) => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

function storeToken(value: string | null) {
  setApiToken(value);
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* токен останется только в памяти вкладки */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const [isMiniApp, setIsMiniApp] = useState(false);

  const signIn = useCallback((token: string, profile: Me) => {
    storeToken(token);
    setMe(profile);
    applySettings(profile.settings);
    setStatus("authed");
  }, []);

  const logout = useCallback(() => {
    storeToken(null);
    setMe(null);
    setStatus("guest");
  }, []);

  // «Выйти» на сайте — отзываем все токены на сервере (выход на всех устройствах)
  const logoutEverywhere = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* даже если сервер недоступен — выходим локально */
    }
    logout();
  }, [logout]);

  const loginTelegram = useCallback<AuthState["loginTelegram"]>(
    async (payload) => {
      const r = await api<{ token: string; me: Me }>("/auth/telegram", { method: "POST", json: payload });
      signIn(r.token, r.me);
    },
    [signIn],
  );

  const loginCode = useCallback<AuthState["loginCode"]>(
    async (login, code) => {
      const r = await api<{ token: string; me: Me }>("/auth/code", { method: "POST", json: { login, code } });
      signIn(r.token, r.me);
    },
    [signIn],
  );

  const refresh = useCallback(async () => {
    const profile = await api<Me>("/me");
    setMe(profile);
    applySettings(profile.settings);
  }, []);

  const saveSettings = useCallback<AuthState["saveSettings"]>(async (patch) => {
    applySettings(patch); // сразу — ребёнок видит результат без ожидания
    setMe((prev) => (prev ? { ...prev, settings: { ...prev.settings, ...patch } } : prev));
    const profile = await api<Me>("/me/settings", { method: "PATCH", json: patch });
    setMe(profile);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    let cancelled = false;

    (async () => {
      // 1) Открыто как Mini App — входим автоматически по initData (подпись проверяет бэкенд).
      const app = miniApp();
      if (app) {
        setIsMiniApp(true);
        app.ready();
        app.expand();
        try {
          await loginTelegram({ init_data: app.initData });
          return;
        } catch {
          /* упадём в обычный вход */
        }
      }
      // 2) Сохранённый токен.
      let saved: string | null = null;
      try {
        saved = localStorage.getItem(TOKEN_KEY);
      } catch {
        saved = null;
      }
      if (saved) {
        setApiToken(saved);
        try {
          const profile = await api<Me>("/me");
          if (!cancelled) signIn(saved, profile);
          return;
        } catch {
          storeToken(null);
        }
      }
      if (!cancelled) setStatus("guest");
    })();

    return () => {
      cancelled = true;
      setUnauthorizedHandler(null);
    };
  }, [loginTelegram, logout, signIn]);

  const value = useMemo(
    () => ({
      status, me, isMiniApp, loginTelegram, loginCode, logout, logoutEverywhere, refresh, saveSettings,
    }),
    [status, me, isMiniApp, loginTelegram, loginCode, logout, logoutEverywhere, refresh, saveSettings],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth вне AuthProvider");
  return ctx;
}
