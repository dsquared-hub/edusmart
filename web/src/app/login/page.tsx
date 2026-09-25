"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { LanguagePicker } from "@/components/LanguagePicker";
import { Mascot } from "@/components/Mascot";
import { PhoneLogin } from "@/components/PhoneLogin";
import { BotLogin, TelegramWidget, telegramRedirectData } from "@/components/TelegramLogin";
import { Notice, Page, Splash } from "@/components/ui";
import { api, errorCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import type { PublicConfig } from "@/lib/types";

const NEXT_KEY = "edu.next";

function safePath(next: string | null): string | null {
  // только внутренние пути — без открытых редиректов
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

function nextPath(): string {
  const fromUrl = safePath(new URLSearchParams(window.location.search).get("next"));
  let saved: string | null = null;
  try {
    saved = safePath(sessionStorage.getItem(NEXT_KEY));
  } catch {
    saved = null;
  }
  return fromUrl ?? saved ?? "/";
}

export default function LoginPage() {
  const t = useT();
  const router = useRouter();
  const { status, me, loginCode, loginTelegram } = useAuth();
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [login, setLogin] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Первый вход по номеру — роли ещё нет: сначала выбрать её
    if (status === "authed") router.replace(me?.role ? nextPath() : "/welcome");
  }, [status, me, router]);

  useEffect(() => {
    api<PublicConfig>("/config").then(setConfig).catch(() => setConfig(null));
    // Запоминаем, куда вернуть после входа через Telegram (он вернёт на /login без next)
    const next = safePath(new URLSearchParams(window.location.search).get("next"));
    try {
      if (next) sessionStorage.setItem(NEXT_KEY, next);
    } catch {
      /* без sessionStorage вернём на главную */
    }
  }, []);

  // Вернулись от Telegram с подписанными данными — входим и убираем их из адреса
  const onTelegram = useCallback(
    async (user: Record<string, string>) => {
      setError(null);
      try {
        await loginTelegram({ widget: user, as_role: "student" });
      } catch (e) {
        setError(errorCode(e));
      }
    },
    [loginTelegram],
  );

  useEffect(() => {
    if (status !== "guest") return;
    const data = telegramRedirectData();
    if (!data) return;
    window.history.replaceState(null, "", "/login");
    onTelegram(data);
  }, [status, onTelegram]);

  if (status === "loading" || status === "authed") return <Splash />;

  const widgetAllowed = window.location.protocol === "https:";

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginCode(login.trim().toLowerCase(), code.trim());
    } catch (err) {
      setError(errorCode(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="justify-center gap-6">
      <LanguagePicker compact />
      <header className="flex flex-col items-center gap-3 text-center anim-rise">
        <Mascot size={120} className="anim-bob" />
        <h1 className="text-4xl font-black">{t("login.title")}</h1>
        <p className="text-lg font-bold text-muted">{t("login.subtitle")}</p>
      </header>

      {error && <Notice tone="error">{t(`errors.${error}`)}</Notice>}

      <section className="card flex flex-col gap-3 anim-rise" aria-labelledby="phone-title">
        <h2 id="phone-title" className="text-center text-xl font-black">
          📱 {t("phone.title")}
        </h2>
        <PhoneLogin onError={setError} />
      </section>

      <section className="card flex flex-col gap-3 anim-rise" aria-labelledby="tg-title">
        <h2 id="tg-title" className="text-center text-xl font-black">
          ✈️ {t("login.telegram")}
        </h2>
        {config?.bot_username ? (
          <>
            <BotLogin onError={setError} asRole="student" />
            {/* Виджет работает только на HTTPS-домене, указанном боту в @BotFather → /setdomain */}
            {widgetAllowed && <TelegramWidget botUsername={config.bot_username} returnPath="/login" />}
          </>
        ) : (
          <p className="text-center text-muted">{t("login.widget_unavailable")}</p>
        )}
        <p className="text-center text-sm font-semibold text-muted">{t("login.telegram_hint")}</p>
      </section>

      <div className="flex items-center gap-3 text-sm font-extrabold uppercase text-muted" aria-hidden="true">
        <span className="h-0.5 flex-1 rounded bg-line" />
        {t("login.or")}
        <span className="h-0.5 flex-1 rounded bg-line" />
      </div>

      <form onSubmit={onSubmit} className="card flex flex-col gap-4 anim-rise">
        <h2 className="text-center text-xl font-black">🔑 {t("login.with_code")}</h2>
        <label>
          <span className="label">{t("login.login_label")}</span>
          <input
            className="field"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder={t("login.login_placeholder")}
            autoCapitalize="none"
            autoCorrect="off"
            autoComplete="username"
            spellCheck={false}
            required
            minLength={3}
          />
        </label>
        <label>
          <span className="label">{t("login.code_label")}</span>
          <input
            className="field text-center text-2xl font-black tracking-[0.4em] placeholder:text-lg placeholder:font-bold placeholder:tracking-normal"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder={t("login.code_placeholder")}
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            minLength={6}
          />
        </label>
        <button className="btn btn-primary" disabled={busy || login.trim().length < 3 || code.length < 6}>
          {t("login.submit")}
        </button>
        <p className="text-center text-sm font-semibold text-muted">{t("login.code_hint")}</p>
      </form>

      <a href="/mentor" className="btn btn-soft anim-rise">
        👩‍🏫 {t("login.mentor_link")}
      </a>
    </Page>
  );
}
