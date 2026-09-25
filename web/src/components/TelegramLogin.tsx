"use client";

import { useEffect, useRef, useState } from "react";
import { Dots } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

/** Страница, с которой начат вход: student — обычная, teacher — ментора. */
export type LoginRole = "student" | "teacher";

// Поля, которые Telegram добавляет к адресу возврата (их подпись проверяет бэкенд)
const TG_FIELDS = ["id", "first_name", "last_name", "username", "photo_url", "auth_date", "hash"];

/** Данные входа, с которыми Telegram вернул пользователя на страницу входа (режим data-auth-url). */
export function telegramRedirectData(): Record<string, string> | null {
  const params = new URLSearchParams(window.location.search);
  if (!params.get("hash") || !params.get("id")) return null;
  const data: Record<string, string> = {};
  for (const key of TG_FIELDS) {
    const value = params.get(key);
    if (value !== null) data[key] = value;
  }
  return data;
}

/** Официальный Telegram Login Widget (домен сайта нужно указать боту в @BotFather → /setdomain).
 *  Режим data-auth-url: Telegram возвращает на returnPath с подписанными полями. Режим
 *  data-onauth не используем — виджет выполняет его через eval, а наша CSP это запрещает. */
export function TelegramWidget({ botUsername, returnPath }: { botUsername: string; returnPath: string }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "16");
    script.setAttribute("data-request-access", "write");
    script.setAttribute("data-auth-url", `${window.location.origin}${returnPath}`);
    box.current?.replaceChildren(script);
  }, [botUsername, returnPath]);
  return <div ref={box} className="flex min-h-[48px] justify-center" />;
}

type BotLoginStart = { token: string; code: number; url: string; expires_in: number };

const POLL_MS = 2500;

/** Вход через бота: работает на любом адресе сайта (виджету нужен домен из @BotFather).
 *  Сайт показывает число, человек нажимает его в боте — так чужая ссылка на вход бесполезна. */
export function BotLogin({ onError, asRole }: { onError: (code: string | null) => void; asRole?: LoginRole }) {
  const t = useT();
  const { pollBotLogin } = useAuth();
  const [pending, setPending] = useState<(BotLoginStart & { until: number }) | null>(null);
  const [busy, setBusy] = useState(false);

  const begin = async () => {
    onError(null);
    setBusy(true);
    try {
      const started = await api<BotLoginStart>("/auth/bot/start", {
        method: "POST",
        json: asRole ? { as_role: asRole } : undefined,
      });
      setPending({ ...started, until: Date.now() + started.expires_in * 1000 });
      // Попробуем сразу открыть Telegram; если браузер заблокирует — есть кнопка ниже
      window.open(started.url, "_blank", "noopener");
    } catch (e) {
      onError(errorCode(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!pending) return;
    let stopped = false;
    const timer = window.setInterval(async () => {
      if (stopped) return;
      if (Date.now() > pending.until) {
        stopped = true;
        setPending(null);
        onError("bot_login_expired");
        return;
      }
      try {
        if (await pollBotLogin(pending.token)) stopped = true; // вошли — страница уйдёт сама
      } catch (e) {
        const code = errorCode(e);
        if (code === "network" || code === "rate_limited") return; // временно — пробуем дальше
        stopped = true;
        setPending(null);
        onError(code);
      }
    }, POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [pending, pollBotLogin, onError]);

  if (!pending) {
    return (
      <button type="button" className="btn btn-primary" onClick={begin} disabled={busy}>
        {busy ? <Dots /> : <>✈️ {t("login.bot")}</>}
      </button>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 text-center" aria-live="polite">
      <p className="font-bold">{t("login.bot_code")}</p>
      <div className="rounded-3xl bg-soft px-8 py-3 font-mono text-5xl font-black tracking-widest text-primary">
        {pending.code}
      </div>
      <a className="btn btn-primary" href={pending.url} target="_blank" rel="noopener noreferrer">
        ✈️ {t("login.bot_open")}
      </a>
      <div className="flex items-center gap-2 text-sm font-bold text-muted">
        <Dots /> {t("login.bot_waiting")}
      </div>
      <button type="button" className="text-sm font-bold text-muted underline underline-offset-4" onClick={() => setPending(null)}>
        {t("login.bot_cancel")}
      </button>
    </div>
  );
}
